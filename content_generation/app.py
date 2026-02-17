from typing import Annotated
from langchain_community.chat_models import ChatPerplexity
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from content_generation import prompt
from pydantic import BaseModel
from typing import List, Optional
from content_generation.helper_functions import scrape_url_content,update_combined_tokens
from content_generation.db import add_blog_data #,logger,shutdown_engine
import os,asyncio,json,aiohttp,random,asyncio,platform


if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
load_dotenv()
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["PPLX_API_KEY"]=os.getenv('PERPLEXITY_API_KEY').strip()
os.environ["GOOGLE_API_KEY"]=os.getenv('GOOGLE_API_KEY')


# GoogleSerperAPIWrapper parameters
k=5   # Number of search results to fetch
gl="IN"  # Country code for Google search results
# Maximum tokens allowed for each model claude-3-5-sonnet-20240620
max_tokens = 8192
perplexity_max_tokens = 1000
llm = ChatAnthropic(model="claude-3-5-sonnet-20240620",max_tokens=max_tokens)
searchllm = ChatPerplexity(model="llama-3.1-sonar-large-128k-online", max_tokens=perplexity_max_tokens)
class InputState(TypedDict):
    user_input: str

class OutputState(TypedDict):
    graph_output: str

class OverallState(TypedDict):
    user_input: str
    urls: str
    web_scrap_data: list
    research_data: list
    seo_expert_data: str
    websearch_data:list
    seo_blog_data: str
    qc_data: str
    combined_tokens: dict

# Pydantic model for the structured data returned by the SEO Expert agent
class blog_content_data(BaseModel):
    title: Optional[str] = None
    metaDescription: Optional[str] = None
    contentoutline: Optional[List[dict]] = None
    primary_keyword: Optional[str] = None
    secondary_keywords: Optional[List[str]] = None
    schemasuggestions: Optional[List[str]] = None
    missingData: Optional[List[dict]] = None
parser = JsonOutputParser(pydantic_object=blog_content_data)

# Google Search the Node 1
async def google_search (state:InputState) -> OverallState:
    search = GoogleSerperAPIWrapper(k=k,gl=gl)
    results =await search.aresults(state["user_input"])
    all_urls=[]
    for x in results["organic"]:
        all_urls.append(x["link"])
    return {"urls":all_urls}

# Web Scrap the Node 2
async def web_scroll(state: OverallState) -> OverallState:
    tasks = [scrape_url_content(url) for url in state["urls"]]
    responses = await asyncio.gather(*tasks)  # No `return_exceptions=True` needed if no errors are expected
    return {"web_scrap_data": responses}

# Research Agent Node 3
async def research_agent(state: OverallState) -> OverallState:
    prompt_template = PromptTemplate.from_template(prompt.research_agent_prompt)
    async def process_data(data):       
            # Format the prompt and invoke the model for each data entry
            return await llm.ainvoke(prompt_template.format(web_scrap_data=data, keyword=state["user_input"]))
    # Create tasks for all web_scrap_data entries
    tasks = [process_data(data) for data in state["web_scrap_data"]]
    # Run tasks concurrently and gather responses
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    combined_tokens = {"total_tokens": 0,"input_tokens": 0,"output_tokens": 0}
    # Extract content and token usage, handling exceptions if needed
    results = [response.content for response in responses]
    tokens = [response.usage_metadata for response in responses]
    for token in tokens:
        print(token)
        combined_tokens=update_combined_tokens(token, combined_tokens)
    return {"research_data": results,"combined_tokens": combined_tokens}

# SEO Expert Agent Node 4
async def seo_expert_agent(state:OverallState) -> OverallState:
        prompt_template = PromptTemplate.from_template(prompt.seo_expert_prompt)
        chain = prompt_template | llm
        response = await chain.ainvoke({"research_summary": state["research_data"], "keyword": state["user_input"]})
        parsed_response=parser.invoke(response)
        print(response.usage_metadata)
        combined_tokens=update_combined_tokens(response.usage_metadata, state["combined_tokens"])
        return {"seo_expert_data": parsed_response,"combined_tokens": combined_tokens}

# Web Search Node 5
async def Web_search(state):
    prompt_template = PromptTemplate.from_template("{prompt}")
    async def process_prompt(item):
        try:
            # Format the prompt and invoke the model
            response = await searchllm.ainvoke(prompt_template.format(prompt=item["prompt"]))
            return {"prompt": item["prompt"], "response": response.content}
        except Exception as e:
            print(f"Error processing prompt: {e}")
            return {"prompt": item["prompt"], "error": str(e)}
    # Check for missing data prompts
    missing_data = state.get("seo_expert_data", {}).get("competitorinsights", {}).get("missingData", [])
    if not missing_data:
        return {"websearch_data" : "No missing data found."}
    # Create tasks for processing each prompt in missingData
    tasks = [process_prompt(item) for item in missing_data if "prompt" in item]
    # Run tasks concurrently and gather responses
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    # Pair prompts with responses
    paired_results = [
        {"prompt": response.get("prompt"), "response": response.get("response", response.get("error"))}
        for response in responses]
    return {"websearch_data" : paired_results}

# SEO Copywriting Agent Node 6
async def seo_copywriting_agent(state:OverallState) -> OverallState:
    prompt_template = PromptTemplate.from_template(prompt.seo_copywriting_prompt)
    response=await llm.ainvoke(prompt_template.format(seo_expert_data=state["seo_expert_data"],keyword= state["user_input"],missing_data_information=state["websearch_data"]))
    print(response.usage_metadata)
    combined_tokens=update_combined_tokens(response.usage_metadata, state["combined_tokens"])
    return {"seo_blog_data": response.content,"combined_tokens": combined_tokens}

# Blog QC Agent Node 7
async def blog_qc_agent(state:OverallState) -> OverallState:
    prompt_template = PromptTemplate.from_template(prompt.blog_qc_prompt)
    response=await llm.ainvoke(prompt_template.format(seo_blog_data=state["seo_blog_data"],scrap_data=state["web_scrap_data"],keyword=state["user_input"]))
    print(response.usage_metadata)
    combined_tokens=update_combined_tokens(response.usage_metadata, state["combined_tokens"])
    return {"qc_data": response.content,"combined_tokens": combined_tokens}

builder =StateGraph(OverallState,input=InputState,output=OverallState)

# ADD GRAPHS NODES HERE
builder.add_node("node_1", google_search)
builder.add_node("node_2", web_scroll)
builder.add_node("node_3", research_agent)
builder.add_node("node_4", seo_expert_agent)
builder.add_node("node_5", Web_search)
builder.add_node("node_6", seo_copywriting_agent)
builder.add_node("node_7", blog_qc_agent)

# ADD MORE EDGES HERE
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
builder.add_edge("node_2", "node_3")
builder.add_edge("node_3", "node_4")
builder.add_edge("node_4", "node_5")
builder.add_edge("node_5", "node_6")
builder.add_edge("node_6", "node_7")  
builder.add_edge("node_7", END)

# Compile the graph
graph = builder.compile()

async def invoke(event):
    """Main entry point for the invocation."""
    response=await graph.ainvoke({"user_input":event})
    add_blog_data(response)    
    return response


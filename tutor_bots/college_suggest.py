from langchain_community.chat_models import ChatPerplexity
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder,PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.callbacks.manager import get_openai_callback
from langchain_google_genai import ChatGoogleGenerativeAI
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic
from content_generation.helper_functions import update_combined_tokens
from dotenv import load_dotenv
from tutor_bots import prompt
from tutor_bots.classes import RequestData
import os,logging,re,json,asyncio,platform,constants
from typing import List
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.prebuilt import ToolNode,tools_condition
from langgraph.graph import StateGraph,START,END
from langgraph.graph.message import add_messages
from langchain_community.utilities import GoogleSerperAPIWrapper
from tutor_bots.web_scraper import scrape_url_content
import os,asyncio,json,aiohttp,random,asyncio,platform
from langchain_core.output_parsers import JsonOutputParser
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")
os.environ["PPLX_API_KEY"]=os.getenv('PERPLEXITY_API_KEY').strip()

searchllm= ChatPerplexity(model="sonar-reasoning")
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")



class State(TypedDict):
  messages:Annotated[list,add_messages]
  student_profile:str

# Function to clean up the response
def cleanup(response):
   clean_content = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
   clean_content = clean_content.strip()
   # Regular expression pattern to match [number], e.g., [1], [2], etc.
   pattern = r'\[\d+\]'
   # Use re.sub() to replace the pattern with an empty string
   cleaned_text = re.sub(pattern, '', clean_content)
   return cleaned_text

def safe_json_serialize(obj):
    def default(o):
        return str(o)  # Convert non-serializable to string
    return json.dumps(obj, default=default)


async def chatbot(state:State):
  system_prompt = ChatPromptTemplate.from_messages([("system",prompt.sub_query_prompt),MessagesPlaceholder(variable_name="messages")])
  response =await llm_with_tools.ainvoke(system_prompt.format(messages=state["messages"],user_profile=state["student_profile"]))
  return {"messages":response}

# Google Search the Node 1
async def google_search (query):
    try:
        search = GoogleSerperAPIWrapper(k=constants.K,gl=constants.GL)
        results =await search.aresults(query)
        all_urls=[]
        for x in results["organic"]:
            all_urls.append(x["link"])
        return all_urls
    except Exception as e:
        logging.error(f"Error in google_search: {e}")

# Web Scrap the Node 2
async def web_scroll(urls:List[str]) -> dict:
    "Web search for NEET-based questions concurrently"
    try:
        tasks = [scrape_url_content(url) for url in urls]
        responses = await asyncio.gather(*tasks)  # No `return_exceptions=True` needed if no errors are expected
        return  responses
    except Exception as e:
        logging.error(f"Error in web_scroll: {e}")

async def sumarize_data(data,state):
    "Summarize the scraped data"
    try:
        data=str(data)
        system_prompt = PromptTemplate.from_template(prompt.summarize_prompt)
        response =await llm.ainvoke(system_prompt.format(scraped_data=data,user_profile=state["student_profile"]))
        return response
    except Exception as e:
        logging.error(f"Error in sumarize_data: {e}")

async def web_Search(subqueries:list[str])-> dict:
    "Web search for NEET-based questions concurrently"

    async def fetch_answer(subquery):
        urls=await google_search(subquery)
        scraped_data=await web_scroll(urls)
        sumarized_data =await sumarize_data(scraped_data,State)
        return subquery,sumarized_data # sumarized_data # Return tuple (query, response)
    tasks = [fetch_answer(subquery) for subquery in subqueries]
    results = await asyncio.gather(*tasks)  # Run all tasks concurrently
    retrieved_answers = {subquery: content for subquery, content in results}
    return {"retrieved_answers": retrieved_answers}

# Asynchronous model call
async def finall_call(state: State) -> State:
    information_retrived=str(state["messages"][-1].content)
    state["messages"] = state["messages"][:-2]
    system_prompt = ChatPromptTemplate.from_messages([("system",prompt.final_call_prompt),MessagesPlaceholder(variable_name="messages")])
    response = await llm.ainvoke(system_prompt.format(messages=state["messages"],information=information_retrived,user_profile=state["student_profile"]))
    return {"messages": response}

tools=[web_Search]
llm_with_tools=llm.bind_tools(tools=tools)

graph_builder=StateGraph(State)

graph_builder.add_node("chatbot",chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("llm_call", finall_call)

graph_builder.add_conditional_edges("chatbot",tools_condition,)
graph_builder.add_edge("tools", "llm_call")
graph_builder.add_edge(START,"chatbot")
graph=graph_builder.compile()


class ChatbotResponseGenerator:
    def __init__(self):
        # Initialize the model
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
        self.system_prompt = PromptTemplate.from_template(prompt.reated_questions_prompt)
        self.parser = JsonOutputParser()
        self.chain= self.system_prompt | self.llm | self.parser

    def generate_related_question(self,request_data:RequestData,profile_context,response):
        try:
            output=self.chain.invoke({"original_query":request_data.message,"user_profile":profile_context,"response_text":response})
            print(output)
            return output
        except Exception as e:
            logging.error(f"Error generating related question: {e}")
            return None
        
 
    # Generate a response from the model
    async def generate_response(self,request_data:RequestData):
        try:
            history=history_logic(request_data.history)    
            messages,message=input_msg(request_data.message,request_data.url,history)
            profile_context=safe_json_serialize(request_data.studentProfile)
            response=await graph.ainvoke({"messages":messages,"student_profile":profile_context}) 
            tokens=response["messages"][-1].usage_metadata
            output=response["messages"][-1].content
            history=get_history(history,output,messages)        
            chat_title = None
            if len(history) < 3:
                chat_title = generate_chat_title([output])
            history=str(history)
            related_question=self.generate_related_question(request_data,profile_context,output)
            return output,history,chat_title,tokens,related_question
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return None 

collegesuggest_bot=ChatbotResponseGenerator()

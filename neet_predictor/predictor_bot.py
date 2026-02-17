from langchain_community.chat_models import ChatPerplexity
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.callbacks.manager import get_openai_callback
from langchain_google_genai import ChatGoogleGenerativeAI
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic
from content_generation.helper_functions import update_combined_tokens
from dotenv import load_dotenv
from neet_predictor import prompts
import os,logging,re,json,asyncio
from typing import List
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.prebuilt import ToolNode,tools_condition
from langgraph.graph import StateGraph,START,END
from langgraph.graph.message import add_messages

# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")
os.environ["PPLX_API_KEY"]=os.getenv('PERPLEXITY_API_KEY').strip()

searchllm= ChatPerplexity(model="sonar-reasoning")
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")

class State(TypedDict):
  messages:Annotated[list,add_messages]   

# Function to clean up the response
def cleanup(response):
   clean_content = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
   clean_content = clean_content.strip()
   # Regular expression pattern to match [number], e.g., [1], [2], etc.
   pattern = r'\[\d+\]'
   # Use re.sub() to replace the pattern with an empty string
   cleaned_text = re.sub(pattern, '', clean_content)
   return cleaned_text


async def chatbot(state:State):
  prompt = ChatPromptTemplate.from_messages([("system",prompts.system_prompt_1),MessagesPlaceholder(variable_name="messages")])
  response =await llm_with_tools.ainvoke(prompt.format(messages=state["messages"]))
  return {"messages":response}

async def web_Search(subqueries:list[str])-> dict:
    "Web search for NEET-based questions concurrently"

    async def fetch_answer(subquery):
        answer = await searchllm.ainvoke(subquery)  # Call LLM
        output=cleanup(answer.content)
        return subquery, output  # Return tuple (query, response)
    tasks = [fetch_answer(subquery) for subquery in subqueries]
    results = await asyncio.gather(*tasks)  # Run all tasks concurrently
    retrieved_answers = {subquery: content for subquery, content in results}
    return {"retrieved_answers": retrieved_answers}

# Asynchronous model call
async def finall_call(state: State) -> State:
    information_retrived=state["messages"][-1].content
    state["messages"] = state["messages"][:-2]
    prompt = ChatPromptTemplate.from_messages([("system",prompts.system_prompt_2),MessagesPlaceholder(variable_name="messages")])
    response = await llm.ainvoke(prompt.format(messages=state["messages"],information=information_retrived,user_profile=state["student_profile"]))
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


# Generate a response from the model
async def predictor_response(message:str,url:str,history:list):
    try:
        history=history_logic(history)      
        messages,message=input_msg(message,url,history)
        response=await graph.ainvoke({"messages":messages}) 
        tokens=response["messages"][-1].usage_metadata
        print(response)   
        output=response["messages"][-1].content
        history=get_history(history,output,messages)        
        chat_title = None
        if len(history) < 3:
            chat_title = generate_chat_title([output])
        history=str(history)
        return output,history,chat_title,tokens
    except Exception as e:
        logging.error(f"Error generating response: {e}")
        return None 
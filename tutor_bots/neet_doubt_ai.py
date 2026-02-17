from langchain_core.tools import tool
from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from dotenv import load_dotenv
import os,logging,requests 
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic,extract_tokens
from tutor_bots.text_processing_functions import clean_solution
from tutor_bots.neet_chapter_bot import llm,tools
from tutor_bots.classes import RequestData

# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")
#Initialize the Prompt
response = requests.get(os.getenv("NEET_COMMON_BOT_PROMPT"))
system_prompt = response.text

# Initialize the model

prompt = ChatPromptTemplate.from_messages([("system", system_prompt),MessagesPlaceholder(variable_name="messages"),MessagesPlaceholder(variable_name="agent_scratchpad")])
agent = create_tool_calling_agent(llm,tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Generate a response from the model
async def generate_response_common(request_data:RequestData):
    try:
        history=history_logic(request_data.history)   
        messages,message=input_msg(request_data.message,request_data.url,history)    
        response, tokens = await model_call(messages)  
        answer=response["output"]
        output=clean_solution(answer)
        history=get_history(history,answer,messages)        
        chat_title = None
        if len(history) < 3:
            chat_title = generate_chat_title([output])
        history=str(history)
        return output,history,chat_title,tokens
    except Exception as e:
        logging.error(f"Error generating response: {e}")
        return None

async def model_call(messages:list):
    try:
        # Using synchronous context manager
        with get_openai_callback() as cb:
            # Making the model call asynchronously
            result = await agent_executor.ainvoke({"messages": messages, "agent_scratchpad": []})
            tokens = extract_tokens(cb)
            return result, tokens
    except Exception as e:
        # Add appropriate error handling and logging here
        print(f"Error occurred in model_call: {e}")
        raise e
    

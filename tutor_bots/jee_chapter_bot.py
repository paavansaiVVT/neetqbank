from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.callbacks.manager import get_openai_callback
from langchain_astradb import AstraDBVectorStore
import langchain_astradb
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os,logging,requests # PyMuPDF
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic,extract_tokens,rate_limiter
from tutor_bots.text_processing_functions import clean_solution,clean_context
from tutor_bots.classes import RequestData



# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")
#Initialize the Prompt
response = requests.get(os.getenv("JEE_CHAPTERWISE_PROMPT"))
system_prompt = response.text

# Initialize the DB connection
embedding = OpenAIEmbeddings()
vstore = AstraDBVectorStore(
    embedding=embedding,
    collection_name="jee_notes",
    token=os.getenv("ASTRA_DB_TOKEN"),
    api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
    setup_mode=langchain_astradb.utils.astradb.SetupMode.OFF
)

@tool
async def vectorsearch(query: str) -> str:
  "Query with chapter name and retrive chapter context"
  data =await vstore.asimilarity_search_with_score(query=query,k=10)
  return data

# Initialize the model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001",google_api_key=os.getenv('GOOGLE_API_KEY'),rate_limiter=rate_limiter)

prompt = ChatPromptTemplate.from_messages([("system", system_prompt),MessagesPlaceholder(variable_name="messages"),MessagesPlaceholder(variable_name="agent_scratchpad")])
tools=[vectorsearch]
agent = create_tool_calling_agent(llm,tools, prompt)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Generate a response from the model
async def jee_response_chapterwise(request_data: RequestData):
    try:
        history=history_logic(request_data.history)   
        messages,message=input_msg(request_data.message,request_data.url,history)
        #messages=messages[-6:]
        response, tokens = await model_call(agent_executor, messages, request_data.chapter)  
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


# Asynchronous model call
async def model_call(agent_executor, messages:list,chapter:str):
    try:
        with get_openai_callback() as cb:
            result =await agent_executor.ainvoke({"messages": messages, "chapter": chapter, "agent_scratchpad": []})
            print(result)          
            tokens =extract_tokens(cb)
            return result, tokens
    except Exception as e:
        print(f"Error occurred in model_call: {e}")
        return None
    
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.callbacks.manager import get_openai_callback
from langchain_astradb import AstraDBVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import langchain_astradb
import os,logging,requests # PyMuPDF
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic,extract_tokens,rate_limiter
from tutor_bots.text_processing_functions import clean_solution,clean_context
from tutor_bots.classes import RequestData
from tutor_bots.sql import extract_pyq



# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")

#Initialize the Prompt
response = requests.get(os.getenv("NEET_CHAPTERWISE_PROMPT"))
system_prompt = response.text

# Initialize the DB connection
embedding = OpenAIEmbeddings()
vstore = AstraDBVectorStore(
    embedding=embedding,
    collection_name="chapter_notes",
    token=os.getenv("ASTRA_DB_TOKEN"),
    api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
    setup_mode=langchain_astradb.utils.astradb.SetupMode.OFF

)

@tool
async def vectorsearch(query: str) -> str:
  "Query with chapter name and retrive chapter context"
  data =await vstore.asimilarity_search_with_score(query=query,k=10)
  return data

@tool
async def get_pyqs(chapter:str) -> str:
        """
        Extract PYQs of the chapter.
        Args:
            chapter (str): the chapter to extract PYQs for.

        Returns:
            str: The extracted PYQs for the specified chapter.
        """
        data = await extract_pyq(chapter_id)
        return data

# Initialize the model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001",google_api_key=os.getenv('GOOGLE_API_KEY'),rate_limiter=rate_limiter)
prompt = ChatPromptTemplate.from_messages([("system", system_prompt),MessagesPlaceholder(variable_name="messages"),MessagesPlaceholder(variable_name="agent_scratchpad")])
tools=[vectorsearch]
agent = create_tool_calling_agent(llm,tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Generate a response from the model
async def generate_response_chapterwise(request_data:RequestData):
    try:
        global chapter_name,chapter_id
        chapter_name=request_data.chapter
        chapter_id=request_data.chapter_id
        history=history_logic(request_data.history)   
        messages,message=input_msg(request_data.message,request_data.url,history)
        response, tokens = await model_call(messages, request_data)  
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
async def model_call(messages:list,request_data:RequestData):
    try:
        with get_openai_callback() as cb:
            result =await agent_executor.ainvoke({"messages": messages, "chapter": request_data.chapter,"topics":request_data.topic_list, "agent_scratchpad": []})   
            tokens=extract_tokens(cb)
    except Exception as e:
        print(f"Error occurred in model_call: {e}")
        raise e
    return result, tokens
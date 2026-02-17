from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.callbacks.manager import get_openai_callback
from langchain_astradb import AstraDBVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os,logging,re,random # PyMuPDF
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic,extract_tokens,rate_limiter
from tutor_bots.text_processing_functions import clean_solution,clean_context,image_format,process_image_links_in_history,clean_retrived_data
from tutor_bots.classes import RequestData
from tutor_bots.sql import extract_pyq
from tutor_bots.prompt import neet_pyq_prompt
from typing import Optional
import langchain_astradb

# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")

# Initialize the DB connection
embedding = OpenAIEmbeddings()
vstore = AstraDBVectorStore(
    embedding=embedding,
    collection_name="pyqs",
    token=os.getenv("ASTRA_DB_TOKEN"),
    api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
    setup_mode=langchain_astradb.utils.astradb.SetupMode.OFF

)

@tool
async def PYQFinder(query: str, year: Optional[int] = None) -> str:
    "Retrieve previous year exam questions by querying subject, chapter, or topic keywords, with an optional filter for a specific year."
    
    broad_subjects = ["physics", "chemistry", "biology", "botany", "zoology","random"]
    # Determine the number of questions to fetch
    k = 100 if any(subject in query.lower() for subject in broad_subjects) else 5
    # Fetch data
    if year is None:
        data = await vstore.asimilarity_search_with_score(query=query, k=k)
    else:
        data = await vstore.asimilarity_search_with_score(query=query, k=k, filter={"Year": year})
    # If k=100, randomly pick 5 questions
    if k == 100:
        data = random.sample(data, min(len(data), 5))  # Ensuring we don't exceed available data
    cleaned_questions=clean_retrived_data(data)
    return cleaned_questions

# Initialize the model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001",google_api_key=os.getenv('GOOGLE_API_KEY'),rate_limiter=rate_limiter)
prompt = ChatPromptTemplate.from_messages([("system", neet_pyq_prompt),MessagesPlaceholder(variable_name="messages"),MessagesPlaceholder(variable_name="agent_scratchpad")])
tools=[PYQFinder]
agent = create_tool_calling_agent(llm,tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Generate a response from the model
async def generate_response_pyq(request_data:RequestData):
    try:
        history=history_logic(request_data.history)
        if history:
            history=process_image_links_in_history(history)
        messages,message=input_msg(request_data.message,request_data.url,history)
        response, tokens = await model_call(messages)  
        answer=response["output"]
        output=clean_solution(answer)
        output=image_format(output)
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
async def model_call(messages:list):
    try:
        with get_openai_callback() as cb:
            result =await agent_executor.ainvoke({"messages": messages, "agent_scratchpad": []})   
            tokens =extract_tokens(cb)
    except Exception as e:
        print(f"Error occurred in model_call: {e}")
        raise e
    return result, tokens


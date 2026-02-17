from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.callbacks.manager import get_openai_callback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os,logging,requests,time # PyMuPDF
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic,extract_tokens,rate_limiter
from tutor_bots.text_processing_functions import clean_solution,clean_context
from tutor_bots.classes import RequestData
from topall.ai_coach.prompt import system_prompt
from topall.ai_coach.analyze_data import student_data
# Load environment variables from .env file and set up environment
load_dotenv()

class ChatbotResponseGenerator:
    def __init__(self):
        # Initialize the chain
        # self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001",google_api_key=os.getenv('GOOGLE_API_KEY'),rate_limiter=rate_limiter)
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-04-17",google_api_key=os.getenv('GOOGLE_API_KEY'),rate_limiter=rate_limiter)
        self.prompt = ChatPromptTemplate.from_messages([("system", system_prompt), MessagesPlaceholder(variable_name="messages")])
        self.chain = self.prompt | self.llm | StrOutputParser()

    # Asynchronous model call
    async def model_call(self, messages: list, weak_areas):
        try:
            with get_openai_callback() as cb:
                # Generate result and get token usage info
                result = await self.chain.ainvoke({"messages": messages, "weak_areas": weak_areas})
                tokens = extract_tokens(cb)
            return result, tokens
        except Exception as e:
            logging.error(f"Error occurred in model_call: {e}")
            raise e
    
    # Main function to generate a response
    async def generate_response(self, request_data: RequestData):
        try:
            history = history_logic(request_data.history)
            # Get messages and history
            messages, message = input_msg(request_data.message, request_data.url, history)
            # Fetch student-specific weak areas
            start=time.time()
            weak_areas = await student_data.get_student_data(request_data.userId)
            end=time.time()
            logging.info(f"Time taken to get student data: {end - start} seconds")
            # Get model response and token info
            answer, tokens = await self.model_call(messages, weak_areas)
            # Clean the solution text
            output = clean_solution(answer)
            # Update history and generate chat title if needed
            history = get_history(history, answer, messages)
            chat_title = None
            if len(history) < 3:
                chat_title = generate_chat_title([output])
            return output, str(history), chat_title, tokens
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return None
        
# Instantiate the ChatbotResponseGenerator
topall_bot = ChatbotResponseGenerator()
      
    

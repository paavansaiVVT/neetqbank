from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.callbacks.manager import get_openai_callback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os,logging,requests # PyMuPDF
from tutor_bots.chat import generate_chat_title,input_msg,get_history,history_logic,extract_tokens,rate_limiter
from tutor_bots.classes import RequestData
from tutor_bots import prompt
# Load environment variables from .env file and set up environment
load_dotenv()


class ChatbotResponseGenerator:
    def __init__(self):
        # Initialize the model
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001",google_api_key=os.getenv('GOOGLE_API_KEY'),rate_limiter=rate_limiter)
        # Define the prompt and chain
        self.prompt_11_12 = ChatPromptTemplate.from_messages([("system", prompt.carrer_coach_prompt_11_12), MessagesPlaceholder(variable_name="messages")])
        self.prompt_7_8 = ChatPromptTemplate.from_messages([("system", prompt.carrer_coach_prompt_7_8), MessagesPlaceholder(variable_name="messages")])
        self.prompt_9_10 = ChatPromptTemplate.from_messages([("system", prompt.carrer_coach_prompt_9_10), MessagesPlaceholder(variable_name="messages")])
        self.chain_1 = self.prompt_11_12 | self.llm | StrOutputParser()
        self.chain_2 = self.prompt_7_8 | self.llm | StrOutputParser()
        self.chain_3 = self.prompt_9_10 | self.llm | StrOutputParser()
   
    # Asynchronous model call
    async def model_call(self, messages: list,request_data: RequestData):
        try:
            with get_openai_callback() as cb:
                # Generate result and get token usage info
                if request_data.classId in [11,12]:
                    print("Came in 11_12")
                    result = await self.chain_1.ainvoke({"messages": messages,"big_five_text":request_data.careerFitResult.bigFiveText,"riasec_text":request_data.careerFitResult.topRiasecText})
                elif request_data.classId in [7,8]:
                    print("Came in 7_8")
                    print(request_data.careerFitResult.profileTitle)
                    print(request_data.careerFitResult.profileDescription)
                    print(request_data.careerFitResult.scoreSummary)
                    print(request_data.careerFitResult.strengths)
                    print(request_data.careerFitResult.activities)
                    print(request_data.careerFitResult.careers)
                    result = await self.chain_2.ainvoke({"messages": messages,"profile_title":request_data.careerFitResult.profileTitle,"profile_description":request_data.careerFitResult.profileDescription,"score_summary":request_data.careerFitResult.scoreSummary,"strenghts":request_data.careerFitResult.strengths,"activities":request_data.careerFitResult.activities,"carrers":request_data.careerFitResult.careers})
                elif request_data.classId in [9,10]:
                    print("Came in 9_10")
                    print(request_data.careerFitResult.quizScores)
                    print(request_data.careerFitResult.report)
                    result = await self.chain_3.ainvoke({"messages":messages,"quizScores":request_data.careerFitResult.quizScores,"report":request_data.careerFitResult.report})
                else:
                    print("Invalid classId provided.")
                    result = None
                tokens = extract_tokens(cb)
            return result, tokens
        except Exception as e:
            logging.error(f"Error occurred in model_call: {e}")
            raise e

    # Main function to generate a response
    async def generate_response(self, request_data: RequestData):
        try:
            history = history_logic(request_data.history)
            messages, message = input_msg(request_data.message, request_data.url, history)
            answer, tokens = await self.model_call(messages,request_data)
            # Update history and generate chat title if needed
            history = get_history(history, answer, messages)
            chat_title = None
            if len(history) < 3:
                chat_title = generate_chat_title([answer])
            return answer, str(history), chat_title, tokens
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return None
         


# Instantiate the ChatbotResponseGenerator
carrer_coach_bot = ChatbotResponseGenerator()
      
    

from langchain_google_genai import ChatGoogleGenerativeAI
import json,time,asyncio,os,re,logging
from dotenv import load_dotenv
import constants
from question_banks.classes import QuestionBankRequest,Topall_Data
from question_banks.question_explanation import format_mcq
from langchain_core.output_parsers import JsonOutputParser
from question_banks import topall_prompts
from langchain_core.prompts import PromptTemplate
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
import asyncio
import random
import pymysql
from sqlalchemy.future import select
from sqlalchemy.exc import OperationalError
from question_banks.db import async_session_factory
from constants import cognitive_levels, question_types
import logging
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import SystemMessage,HumanMessage

logger = logging.getLogger(__name__)
semaphore = asyncio.Semaphore(50)
parser=JsonOutputParser()
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


class question_tagger:
    def __init__(self):
        self.DATABASE_URL=os.getenv("DATABASE_URL_5") 
        self.engine = create_async_engine(self.DATABASE_URL,echo=False,pool_size=100, max_overflow=50,pool_timeout=60,pool_recycle=1800,pool_pre_ping=True)
        self.async_session_factory = sessionmaker(bind=self.engine,expire_on_commit=False,class_=AsyncSession)
        
    async def get_session(self):
        """Creates and returns a new database session."""
        return self.async_session_factory()
    
    def clean_output(self,output):
        """Cleans the output string by removing unwanted characters and formatting it."""
        output=output.content
        output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        return output
    
    def image_agumentation(self,request:QuestionBankRequest,prompt_input ):
        """Formats the input message for the Gemini AI models according to inputs"""
        try:
            if request.image_url:
                prefix="https://qbank.csprep.in/HTML/"
                image_url=prefix+request.image_url
                formatted_prompt=[HumanMessage([{"type": "text","text": prompt_input.text},{"type": "image_url", "image_url": {"url":image_url}}])]
                return formatted_prompt
            else:
                return prompt_input.text
        except Exception as e:
            print(f"Error occurred in image_agumentation: {e}")
            return prompt_input.text
                
    async def topall_question_tagger(self,request:QuestionBankRequest):
        "Taggs Already generated Questions From top wall question bank"
        try:
            llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview",api_key=os.getenv("GOOGLE_API_KEY"))
            mcq=format_mcq(request,explanation="not_required")
            prompt = PromptTemplate.from_template(topall_prompts.tagging_prompt)
            #chain=prompt |RunnableLambda(self.image_agumentation) | llm |RunnableLambda(self.clean_output) |parser
            #chain = prompt| RunnableLambda(lambda inputs: self.image_augmentation(request, str(inputs)))| llm| RunnableLambda(self.clean_output)| parser
            chain=llm |RunnableLambda(self.clean_output) |parser
            b=await prompt.ainvoke({"mcq":mcq})
            a=self.image_agumentation(request,b)
            response=chain.invoke(a)
            print(response)
            asyncio.create_task(self.update_cognitive_and_time(response[0],request))
            # Printing the extracted item
            return response
        except Exception as e:
            print(f"Error occurred in topall_question_tagger: {e}")
            print(f"Output: {response}")

    async def update_cognitive_and_time(self, entry: dict,request:QuestionBankRequest):
        """
        Update the cognitive_level and estimated_time fields in vr_questions table
        using q_id provided in the entry dict.
        Example of entry: {"q_id": 123, "cognitive_level": 2, "estimated_time": 3.5}
        """

        try:
            q_id = request.question_id
            new_cognitive_level =constants.cognitive_levels[entry.get("cognitive_level")]
            new_estimated_time = entry.get("estimated_time")

            if q_id is None or new_cognitive_level is None or new_estimated_time is None:
                logger.warning("Incomplete entry data provided. Skipping update.")
                return
            async with semaphore:  # control concurrency
                async with self.async_session_factory() as session:
                    async with session.begin():
                        result = await session.execute(select(Topall_Data).where(Topall_Data.vr_ques_id == q_id))
                        record = result.scalar_one_or_none()
                        if not record:
                            logger.warning(f"No question found with q_id: {q_id}")
                            return
                        # Update the values
                        record.cognitive_level = new_cognitive_level
                        record.estimated_time = new_estimated_time
                        await session.commit()
                        logger.info(f"Successfully updated question ID {q_id}")
        except Exception as e:
            logger.error(f"Error updating question ID {q_id}: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


topwall_tag=question_tagger()

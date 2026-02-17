from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
import os, logging, time, asyncio, re, json,constants
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from cs_data_collection import prompts
from cs_data_collection.cs_basic_details import CollegeRequest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from langchain_core.prompts import PromptTemplate
from sqlalchemy import text
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float
from sqlalchemy.orm import sessionmaker
load_dotenv()
from sqlalchemy import select, update
from sqlalchemy.ext.declarative import declarative_base
from typing import List, Optional
# Define a base class for the models
Base = declarative_base()

class acitivities(Base):
    __tablename__ = "Counseling_Schedules"
    schedule_id = Column(Integer, primary_key=True)
    college_id = Column(Integer)
    authority_id = Column(Integer)
    admission_year = Column(Integer)
    round_id = Column(String)
    activity_name = Column(String)
    start_datetime = Column(String)
    end_datetime = Column(String)
    notes = Column(String)

class cs_acitivities:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL_6")
        self.engine = create_async_engine(self.DATABASE_URL,echo=False,pool_size=100, max_overflow=50,pool_timeout=60,pool_recycle=1800)
        self.async_session_factory = sessionmaker(bind=self.engine,expire_on_commit=False,class_=AsyncSession)
        self.parser = JsonOutputParser()
        self.search_tool = GenAITool(google_search={})
        self.llm = (ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[self.search_tool]))
        self.prompt =PromptTemplate.from_template(prompts.system_prompt_counselling_activites)
        self.chain = self.prompt | self.llm |RunnableLambda(self.clean_llm_output)| self.parser
    
    def clean_llm_output(self,raw_text) -> str:
        raw_text = raw_text.content
        raw_text = re.sub(r"\([^)]*\)", "", raw_text)
        return raw_text
    
    async def get_data(self,request: CollegeRequest, college_id:int, state_id:int):
        """Fetch counselling schedule details  data using the chain and insert into the Counseling_Schedules table."""
        authority_id, authority_name= await self.authority_details(state_id)
        #authority_name= "Dr. NTR University of Health Sciences, Vijayawada"
        response =await self.chain.ainvoke({"authority_name":authority_name,"year":request.year})
        #print(response)
        data=await self.insert_data(data=response,year=request.year,college_id=college_id,authority_id=authority_id)
        return response
    
    async def insert_data(self,data,year,college_id, authority_id:int):
        """Insert counselling schedule details data into the database."""
        async with self.async_session_factory() as session:
            try:

                for x in data["activities"]:
                    # Insert the new authority into the database
                    rankings_data =acitivities(
                    college_id =college_id,
                    authority_id =authority_id,
                    admission_year = year,
                    round_id =self.decode_round(x["round"]),
                    activity_name = x["activity_name"],
                    start_datetime =x["start_date"] ,
                    end_datetime =x["end_date"],
                    notes = x["notes"]
                    )   
                    session.add(rankings_data)
                await session.commit()
                print(f"✅ schedule activity data inserted successfully")
            except Exception as e:
                await session.rollback()
                print(f"❌ Error occurred: {e}")
            finally:
                await session.close()

    async def authority_details(self,state_id):
        """Insert counselling schedule details data into the database."""
        async with self.async_session_factory() as session:
            try:
                result_quth = await session.execute(
                    text("SELECT authority_id, authority_name FROM Counseling_Authorities WHERE state_id = :state_id"),{"state_id": state_id})
                row_auth = result_quth.fetchone()
                if not row_auth:
                    raise Exception(f"❌ Authority '{state_id}' not found!")
                authority_id = row_auth.authority_id
                authority_name = row_auth.authority_name
            except Exception as e:
                await session.rollback()
                print(f"❌ Error occurred: {e}")
            finally:
                await session.close()
                return authority_id, authority_name

    
    def decode_round(self,x):
        try:
          round=int(x)
          return round
        except:
          round= constants.rounds_dict[x]
          return round


cs_schedule_data =cs_acitivities()

from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
import os, logging, time, asyncio, re, json
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

class infrastructure(Base):
    __tablename__ = "College_Infrastructure"
    infra_id = Column(Integer, primary_key=True)
    college_id = Column(Integer)
    data_year = Column(Integer)
    hospital_beds = Column(Integer)
    avg_daily_opd = Column(Integer)
    campus_area_acres = Column(Integer)
    library_details = Column(String)
    lab_details = Column(String)
    other_facilities = Column(String)

class cs_infrastructure:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL_6")
        self.engine = create_async_engine(self.DATABASE_URL,echo=False,pool_size=100, max_overflow=50,pool_timeout=60,pool_recycle=1800)
        self.async_session_factory = sessionmaker(bind=self.engine,expire_on_commit=False,class_=AsyncSession)
        self.parser = JsonOutputParser()
        self.search_tool = GenAITool(google_search={})
        self.llm = (ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[self.search_tool]))
        self.prompt =PromptTemplate.from_template(prompts.system_prompt_infrastructure)
        self.chain = self.prompt | self.llm |RunnableLambda(self.clean_llm_output)| self.parser
    
    def clean_llm_output(self,raw_text) -> str:
        raw_text = raw_text.content
        raw_text = re.sub(r"\([^)]*\)", "", raw_text)
        raw_text = re.sub(r"\[[^\]]*\]", "", raw_text)
        return raw_text
    
    async def get_data(self,request: CollegeRequest, college_id:int):
        """Fetch college infrastructure data using the chain and insert into the College_Infrastructure table."""
        # Step 1: Get authority names based on state_id
        response =await self.chain.ainvoke({"college_name":request.college_name,"state_name":request.state_name,"year":request.year,})
        data=await self.insert_data(response, college_id, request.year)
        return response
    
    async def insert_data(self,data, college_id, data_year):
        """Insert College Infrastructure data into the database."""
        async with self.async_session_factory() as session:
            try:
                # Insert the new authority into the database
                Infrasctructure_data = infrastructure(
                college_id=college_id,
                data_year= data_year,
                hospital_beds =data["hospital_beds"],
                avg_daily_opd =data["avg_daily_opd"],
                campus_area_acres =data["campus_area_acres"],
                library_details =data["library_details"],
                lab_details =data["lab_details"] ,
                other_facilities =data["other_facilities"])
                session.add(Infrasctructure_data)
                await session.commit()
                print(f"✅ Infrasctructure data for college_id {college_id} inserted successfully")
            except Exception as e:
                await session.rollback()
                print(f"❌ Error occurred: {e}")
            finally:
                await session.close()
    
cs_infrastructure_data = cs_infrastructure()

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

class bonds(Base):
    __tablename__ = "College_Bonds"
    bond_id = Column(Integer, primary_key=True)
    program_id = Column(Integer)
    quota_id = Column(Integer)
    bond_exists = Column(Integer)
    bond_duration_years = Column(Integer)
    penalty_amount = Column(Integer)
    penalty_currency = Column(String)
    bond_details_url = Column(String)
    bond_notes = Column(String)

class cs_bonds:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL_6")
        self.engine = create_async_engine(self.DATABASE_URL,echo=False,pool_size=100, max_overflow=50,pool_timeout=60,pool_recycle=1800)
        self.async_session_factory = sessionmaker(bind=self.engine,expire_on_commit=False,class_=AsyncSession)
        self.parser = JsonOutputParser()
        self.search_tool = GenAITool(google_search={})
        self.llm = (ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[self.search_tool]))
        self.prompt =PromptTemplate.from_template(prompts.system_prompt_bonds)
        self.chain = self.prompt | self.llm |RunnableLambda(self.clean_llm_output)| self.parser
    
    def clean_llm_output(self,raw_text) -> str:
        raw_text = raw_text.content
        raw_text = re.sub(r"\([^)]*\)", "", raw_text)
        raw_text = re.sub(r"\[[^\]]*\]", "", raw_text)
        return raw_text
    
    async def get_data(self,request: CollegeRequest, course, program_id:int, quota:str, quota_id:int):
        """Fetch college bond details  data using the chain and insert into the College_Infrastructure table."""
        response =await self.chain.ainvoke({"college_name":request.college_name,"state_name":request.state_name,"year":request.year,"course":course,"quota":quota})
        data=await self.insert_data(response, program_id, quota_id)
        return response
    
    async def insert_data(self,data,program_id: int, quota_id:int):
        """Insert College bond details data into the database."""
        async with self.async_session_factory() as session:
            try:
                bond_data =bonds(
                program_id = program_id,
                quota_id = quota_id,
                bond_exists = data["bond_exists"],
                bond_duration_years =data["bond_duration_years"],
                penalty_amount = data["penalty_amount"],
                penalty_currency = data["penalty_currency"],
                bond_details_url = data["bond_details_url"],
                bond_notes =   data["bond_notes"])
                session.add(bond_data)
                await session.commit()
                #print(f"✅ bond data inserted successfully")
            except Exception as e:
                await session.rollback()
                print(f"❌ Error occurred: {e}")
            finally:
                await session.close()
    
cs_bond_data = cs_bonds()

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

class Rankings(Base):
    __tablename__ = "College_Rankings"
    ranking_id = Column(Integer, primary_key=True)
    college_id = Column(Integer)
    ranking_body = Column(String)
    ranking_type = Column(String)
    ranking_year = Column(Integer)
    rank_value = Column(Integer)
    score = Column(Float)
    ranking_url = Column(String)

class cs_Rankings:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL_6")
        self.engine = create_async_engine(self.DATABASE_URL,echo=False,pool_size=100, max_overflow=50,pool_timeout=60,pool_recycle=1800)
        self.async_session_factory = sessionmaker(bind=self.engine,expire_on_commit=False,class_=AsyncSession)
        self.parser = JsonOutputParser()
        self.format_guide = self.parser.get_format_instructions()
        self.search_tool = GenAITool(google_search={})
        self.llm = (ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[self.search_tool]))
        #self.prompt =PromptTemplate.from_template(prompts.system_prompt_college_rankings)
        self.prompt = ChatPromptTemplate.from_messages([("system", prompts.system_prompt_college_rankings),("user","COLLEGE: {college_name}\n""STATE  : {state_name}\n""YEAR: {year}\n\n""FORMAT GUIDE: {format_guide}"),])
        self.chain = self.prompt | self.llm |RunnableLambda(self.clean_llm_output)| self.parser
    
    def clean_llm_output(self,raw_text) -> str:
        raw_text = raw_text.content
        raw_text = re.sub(r"\([^)]*\)", "", raw_text)
        #raw_text = re.sub(r"\[[^\]]*\]", "", raw_text)
        return raw_text
    
    async def get_data(self,request: CollegeRequest,college_id:int):
        """Fetch college ranking details  data using the chain and insert into the College_Rankings table."""
        response =await self.chain.ainvoke({"college_name":request.college_name,"state_name":request.state_name,"year":request.year,"format_guide":self.format_guide})
        await self.insert_data(college_id=college_id, data=response, year=request.year)
        return response
    
    async def insert_data(self, college_id, data, year):
        """Insert College ranking details data into the database."""
        async with self.async_session_factory() as session:
            try:
                for x in data["rankings"]:
                    # Insert the new authority into the database
                    rankings_data =Rankings(
                    college_id =college_id,
                    ranking_body = x["ranking_body"],
                    ranking_type = x["ranking_type"],
                    ranking_year = year,
                    rank_value =x["rank_value"],
                    score =x["score"],
                    ranking_url = x["ranking_url"]
                    )
                    session.add(rankings_data)
                await session.commit()
                print(f"✅ ranking data inserted successfully")
            except Exception as e:
                await session.rollback()
                print(f"❌ Error occurred: {e}")
            finally:
                await session.close()
    
cs_ranking_data =cs_Rankings()

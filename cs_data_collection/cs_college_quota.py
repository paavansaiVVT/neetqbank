from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
import os, logging, time, asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from cs_data_collection.cs_basic_details import CollegeRequest
from cs_data_collection import prompts, cs_quota
from sqlalchemy import text
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

load_dotenv()

parser = JsonOutputParser()
search_tool = GenAITool(google_search={})

class ClgQuotaResponseGenerator:
    def __init__(self):
        self.format_guide = parser.get_format_instructions()
        self.DATABASE_URL_6 = os.getenv("DATABASE_URL_6")
        self.llm = (ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[search_tool]))

    async def get_all_quota_codes_async(self, sqlalchemy_url: str):
        """Fetch all quota_code values from the College_Quota table asynchronously."""
        engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        query = text(""" SELECT quota_name FROM Quotas """)
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(query)
                quota_codes = [row[0] for row in result.fetchall()]
        return quota_codes

    async def create_chatbot_response_generator(self, system_prompt_template: str):
        """ Creates a ChatbotResponseGenerator instance with the given system prompt template. """
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt_template),("user","COLLEGE: {college_name}\n""STATE  : {state_name}\n""QUOTA CODES: {quota_codes}\n""YEAR: {year}\n\n""{format_guide}"),])
        chain = prompt | self.llm | parser
        return chain

    async def model_call(self,request:CollegeRequest,quota_codes,prompts_temp) -> dict:
        try:
            start = time.time()
            chain=await self.create_chatbot_response_generator(prompts_temp)
            raw_result = await chain.ainvoke({"college_name": request.college_name,"state_name": request.state_name, "quota_codes": quota_codes, "year":request.year, "format_guide": self.format_guide})
            logging.info("LLM call took %.2f s", time.time() - start)
            return raw_result
        except Exception as e:
            logging.exception("Model call failed")
            return {"error": str(e)}
        
    async def fetch_all_program_levels(self, request:CollegeRequest, college_id:int):
        """Runs all 4 course-level prompts (UG, PG, Diploma, SuperSpecialty)and merges the outputs."""
        quota_codes = await self.get_all_quota_codes_async(self.DATABASE_URL_6)
        chatbot_ug = self.model_call(request,quota_codes, prompts_temp=prompts.system_prompt_ug_quotas_notes)
        chatbot_pg = self.model_call(request,quota_codes, prompts_temp=prompts.system_prompt_pg_quotas_notes)
        chatbot_diploma = self.model_call(request,quota_codes, prompts_temp=prompts.system_prompt_diploma_quotas_notes)
        chatbot_super = self.model_call(request,quota_codes, prompts_temp=prompts.system_prompt_ss_quotas_notes)
        tasks = [chatbot_ug,chatbot_pg,chatbot_diploma,chatbot_super,]
        results = await asyncio.gather(*tasks)
        merged_courses = []
        college = None
        state = None
        year_id = None
        for result in results:
            if "error" not in result:
                if not college:
                    college = result.get("college_name")
                state = result.get("state_name")
                merged_courses.extend(result.get("available_quotas", []))
        merged_output = {"college_name": college or request.college_name,"state_name": state or request.state_name,"year": year_id or request.year,"available_quotas": merged_courses}
        await self.insert_college_data_async(self.DATABASE_URL_6, merged_output, college_id)
        return merged_output
    
    async def insert_college_data_async(self, sqlalchemy_url: str, cleaned_data: dict, college_id: int):
            """Inserts course data into the database asynchronously."""
            engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
            async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            async with async_session() as session:
                async with session.begin():
                    insert_sql = text("""INSERT INTO College_Quota (college_id,course_level,quota_id,quota_notes) VALUES (:college_id,:course_level,:quota_id,:quota_notes)""")
                    for quota in cleaned_data.get("available_quotas", []):
                        result_quota = await session.execute(
                            text("SELECT quota_id FROM Quotas WHERE quota_name LIKE :quota_name"),{"quota_name": f"%{quota['quota_name']}%"})
                        row_quota = result_quota.fetchone()
                        if not row_quota:
                            #print(f"⚠️ Quota '{quota['quota_name']}' not found! Skipping...")
                            quota_name = quota['quota_name']
                            result, quota_id = await cs_quota.cs_quota_data_bot.model_call(quota_name=quota_name)
                            quota_id = quota_id
                            #print(f"✅ Quota Created '{quota['quota_name']}' with quota_id = {quota_id}")
                            continue
                        quota_id = row_quota.quota_id
                        #print(f"✅ Found quota_id = {quota_id} for course '{quota['quota_name']}'")
                        insert_data = {"college_id": college_id,"course_level": quota.get("course_level"),"quota_id": quota_id,"quota_notes": quota.get("quota_notes")}
                        await session.execute(insert_sql, insert_data)
                await session.commit()
                print("✅ All College quota inserted successfully!")
            return college_id

cs_college_quota_bot= ClgQuotaResponseGenerator()
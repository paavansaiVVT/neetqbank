from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
import os, logging, time, asyncio, re, json
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from cs_data_collection import prompts
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from cs_data_collection.cs_basic_details import CollegeRequest
from sqlalchemy import text
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker
load_dotenv()

parser = JsonOutputParser()
search_tool = GenAITool(google_search={})

class CourseResponseGenerator:
    def __init__(self):
        self.format_guide = parser.get_format_instructions()
        self.DATABASE_URL_6 = os.getenv("DATABASE_URL_6")
        #self.llm = (ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[search_tool]))
        self.llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-pro-preview-05-06", api_key=os.getenv("GOOGLE_API_KEY"))

    async def get_all_course_codes_async(self, sqlalchemy_url: str):
        """Fetch all course_code values from the College_Courses table asynchronously."""
        engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        query = text("""SELECT course_code FROM Courses""")
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(query)
                course_codes = [row[0] for row in result.fetchall()]
        return course_codes
    async def create_chatbot_response_generator(self, system_prompt_template: str):
        """ Creates a ChatbotResponseGenerator instance with the given system prompt template. """
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt_template),("user","COLLEGE: {college_name}\n""STATE  : {state_name}\n""YEAR: {year}\n\n""{format_guide}"),])
        chain = prompt | self.llm | parser
        return chain

    async def model_call(self,request:CollegeRequest,course_codes,prompts_temp) -> dict:
        try:
            start = time.time()
            chain=await self.create_chatbot_response_generator(prompts_temp)
            raw_result = await chain.ainvoke({"college_name": request.college_name,"state_name": request.state_name, "course_codes": course_codes, "year":request.year, "format_guide": self.format_guide})
            logging.info("LLM call took %.2f s", time.time() - start)
            return raw_result
        except Exception as e:
            logging.exception("Model call failed")
            return {"error": str(e)}
        
    async def fetch_all_course_levels(self,request:CollegeRequest, college_id:int):
        """Runs all 4 course-level prompts (UG, PG, Diploma, SuperSpecialty)and merges the outputs."""
        course_codes = await self.get_all_course_codes_async(self.DATABASE_URL_6)
        chatbot_ug = self.model_call(request,course_codes, prompts_temp=prompts.system_prompt_crs_ug)
        chatbot_pg = self.model_call(request,course_codes, prompts_temp=prompts.system_prompt_crs_pg)
        chatbot_diploma = self.model_call(request,course_codes, prompts_temp=prompts.system_prompt_crs_diploma)
        chatbot_super = self.model_call(request,course_codes, prompts_temp=prompts.system_prompt_crs_superspecialty)
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
                if not state:
                    state = result.get("state_name")
                if not year_id:
                    year_id = result.get("year")
                merged_courses.extend(result.get("courses", []))
        merged_output = {"college_name": college or request.college_name,"state_name": state or request.state_name,"year": year_id or request.year,"courses": merged_courses}
        cleaned_output= self.fill_nmc_year_if_missing(merged_output)
        await self.insert_college_data_async(self.DATABASE_URL_6, cleaned_output, college_id)
        return college_id
    
    def fill_nmc_year_if_missing(self, merged_data: dict) -> dict:
        """If any course has valid nmc_approved_intake_year, fill it into courses where it is 'None'."""
        valid_year = None
        for course in merged_data.get("courses", []):
            year = course.get("nmc_approved_intake_year")
            if year and year != "None":
                valid_year = year
                break
        if valid_year:
            for course in merged_data.get("courses", []):
                if course.get("nmc_approved_intake_year") == "None":
                    course["nmc_approved_intake_year"] = valid_year
        return merged_data

    async def insert_college_data_async(self, sqlalchemy_url: str, cleaned_data: dict, college_id: int):
        """Inserts course data into the database asynchronously."""
        engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with async_session() as session:
            async with session.begin():
                result_college = await session.execute(
                    text("SELECT college_id FROM Colleges WHERE college_name LIKE :college_name"),{"college_name": f"%{cleaned_data['college_name']}%"})
                row_college = result_college.fetchone()
                if not row_college:
                    raise Exception(f"❌ College '{cleaned_data['college_name']}' not found!")
                college_id = row_college.college_id
                #print(f"✅ Found college_id = {college_id} for college '{cleaned_data['college_name']}'")
                insert_sql = text("""INSERT INTO College_Courses (college_id,course_id,year,total_sanctioned_intake,nmc_approved_intake_year
                    ) VALUES (:college_id,:course_id,:year,:total_sanctioned_intake,:nmc_approved_intake_year)
                    ON DUPLICATE KEY UPDATE total_sanctioned_intake = VALUES(total_sanctioned_intake),nmc_approved_intake_year = VALUES(nmc_approved_intake_year)""")
                for course in cleaned_data.get("courses", []):
                    result_course = await session.execute(
                        text("SELECT course_id FROM Courses WHERE course_code LIKE :course_code"),{"course_code": f"%{course['course_name']}%"})
                    row_course = result_course.fetchone()
                    if not row_course:
                        print(f"⚠️ Course '{course['course_name']}' not found! Skipping...")
                        continue
                    course_id = row_course.course_id
                    #print(f"✅ Found course_id = {course_id} for course '{course['course_name']}'")
                    insert_data = {"college_id": college_id,"course_id": course_id,"year": cleaned_data.get("year"),"total_sanctioned_intake": course.get("total_sanctioned_intake"),"nmc_approved_intake_year": course.get("nmc_approved_intake_year")}
                    await session.execute(insert_sql, insert_data)
            await session.commit()
            print("✅ All College Courses and Program inserted successfully!")

cs_course_data_bot= CourseResponseGenerator()
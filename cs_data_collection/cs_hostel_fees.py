from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
import os, logging, time, json
from dotenv import load_dotenv
from cs_data_collection import prompts
from cs_data_collection.cs_basic_details import CollegeRequest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker
load_dotenv()

parser = JsonOutputParser()
search_tool = GenAITool(google_search={})

    
class HostelFeesResponseGenerator:
    def __init__(self):
        self.format_guide = parser.get_format_instructions()
        self.DATABASE_URL_6 = os.getenv("DATABASE_URL_6")
        #self.llm = (ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[search_tool]))
        self.llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-pro-preview-05-06", api_key=os.getenv("GOOGLE_API_KEY"))
        self.prompt = ChatPromptTemplate.from_messages([("system", prompts.system_prompt_get_hostel_fee_details),("user","COLLEGE: {college_name}\n""STATE  : {state_name}\n""YEAR: {year}\n\n""{format_guide}"),])
        self.chain = self.prompt | self.llm | parser

    async def model_call(self, request: CollegeRequest) -> dict:
        try:
            start = time.time()
            result = await self.chain.ainvoke({"college_name": request.college_name,"state_name": request.state_name,"format_guide": self.format_guide,"year": request.year})
            logging.info("LLM call took %.2f s", time.time() - start)
            college_hostel_id= await self.insert_quota_data_async(sqlalchemy_url=self.DATABASE_URL_6, cleaned_data=result)
            return result, college_hostel_id
        except Exception as e:
            logging.exception("Model call failed")
            return {"error": str(e)}

    async def insert_quota_data_async(self, sqlalchemy_url: str, cleaned_data: dict):
        """ Inserts Hostel fee data into the database asynchronously and returns the inserted college_hostel_id. """
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
                cleaned_data["college_id"]=college_id
                #print(f"✅ Found college_id = {college_id} for college '{cleaned_data['college_name']}'")
                insert_sql = text("""INSERT INTO College_Hostel (college_id,academic_year,boys_hostel,boys_hostel_fee,girls_hostel,girls_hostel_fee,mess_fee,other_facilities,room_type,with_mess,other_hostel_fee_details
                ) VALUES (:college_id,:academic_year,:boys_hostel,:boys_hostel_fee,:girls_hostel,:girls_hostel_fee,:mess_fee,:other_facilities,:room_type,:with_mess,:other_hostel_fee_details)""")
                result = await session.execute(insert_sql, cleaned_data)
                college_hostel_id = None
                if hasattr(result, "lastrowid"):
                    college_hostel_id = result.lastrowid
                elif hasattr(result, "cursor") and hasattr(result.cursor, "lastrowid"):
                    college_hostel_id = result.cursor.lastrowid
                if not college_hostel_id:
                    raise Exception(f"❌ Failed to insert College name '{cleaned_data['college_name']}'!")
                print(f"✅ Inserted College name '{cleaned_data['college_name']}' with college_hostel_id = {college_hostel_id}")
        return college_hostel_id

cs_hostel_fees_data_bot= HostelFeesResponseGenerator()
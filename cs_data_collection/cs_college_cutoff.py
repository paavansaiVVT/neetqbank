from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
import os, logging, time, asyncio, re, json
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from cs_data_collection.cs_basic_details import CollegeRequest
from sqlalchemy import text
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker
from cs_data_collection import prompts, cs_quota, cs_category
load_dotenv()
parser = JsonOutputParser()
search_tool = GenAITool(google_search={})

class CollegefeesRequest(BaseModel):
    college_name: str
    state_name: str
    year: int
    program_name: str
    quota_name_list: list[str]

class cutoffResponseGenerator:
    def __init__(self):
        self.format_guide = parser.get_format_instructions()
        self.DATABASE_URL_6 = os.getenv("DATABASE_URL_6")
        self.llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-pro-preview-05-06", api_key=os.getenv("GOOGLE_API_KEY"))

    async def create_chatbot_response_generator(self, system_prompt_template: str):
        """ Creates a ChatbotResponseGenerator instance with the given system prompt template. """
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt_template),("user","COLLEGE: {college_name}\n""STATE  : {state_name}\n""YEAR: {year}\n""PROGRAM: {program_name}\n""QUOTA NAME LIST: {quota_name_list}\n\n""{format_guide}"),])
        mbbs_prompt = ChatPromptTemplate.from_messages([("system", system_prompt_template),("user","COLLEGE: {college_name}\n""STATE  : {state_name}\n""YEAR: {year}\n\n""{format_guide}"),])
        chain = prompt | self.llm | parser
        mbbs_chain = mbbs_prompt | self.llm | parser
        return chain, mbbs_chain

    async def model_call(self,request:CollegefeesRequest,prompts_temp, program_id) -> dict:
        try:
            start = time.time()
            chain, mbbs_chain=await self.create_chatbot_response_generator(prompts_temp)
            result = await chain.ainvoke({"college_name": request.college_name,"state_name": request.state_name, "year":request.year, "format_guide": self.format_guide, "program_name": request.program_name, "quota_name_list": request.quota_name_list})
            logging.info("LLM call took %.2f s", time.time() - start)
            for item in result["quota_wise_cutoff_distribution"]:
              item["program_id"] = program_id
            return result
        except Exception as e:
            logging.exception("Model call failed")
            return {"error": str(e)}

    async def mbbs_model_call(self,request:CollegeRequest,prompts_temp, program_id, college_id) -> dict:
        try:
            start = time.time()
            chain, mbbs_chain=await self.create_chatbot_response_generator(prompts_temp)
            result = await mbbs_chain.ainvoke({"college_name": request.college_name,"state_name": request.state_name,"format_guide": self.format_guide,"year": request.year})
            #print(json.dumps(result, indent=2))
            logging.info("LLM call took %.2f s", time.time() - start)
            for item in result["quota_wise_cutoff_distribution"]:
              item["program_id"] = program_id
            seat_id_list= await self.insert_college_data_async(self.DATABASE_URL_6, result, college_id)
            return result
        except Exception as e:
            logging.exception("MBBS Model call failed")
            return {"error": str(e)}

    async def get_course_and_quota_details(self, sqlalchemy_url: str, college_id: int):
        engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with async_session() as session:
            async with session.begin():
                course_query = text("""SELECT c.course_code, c.course_name, c.course_level, cc.program_id FROM College_Courses cc JOIN Courses c ON cc.course_id = c.course_id WHERE cc.college_id = :college_id AND cc.total_sanctioned_intake != 0 """)
                course_result = await session.execute(course_query, {"college_id": college_id})
                course_rows = course_result.fetchall()
                course_list = []
                unique_levels = set()
                for row in course_rows:
                    course_list.append({"course_code": row[0],"course_name": row[1],"course_level": row[2],"program_id": row[3]})
                    unique_levels.add(row[2])
                quota_map = {}

                for level in unique_levels:
                    quota_query = text(""" SELECT q.quota_code, q.quota_name FROM College_Quota cq JOIN Quotas q ON cq.quota_id = q.quota_id WHERE cq.college_id = :college_id AND cq.course_level = :course_level """)
                    quota_result = await session.execute(quota_query, {"college_id": college_id, "course_level": level})
                    rows = quota_result.fetchall()
                    quota_map[level] = {"quota_code": [r[0] for r in rows],"quota_name": [r[1] for r in rows]}

                for course in course_list:
                    level = course["course_level"]
                    course["quota_code"] = quota_map.get(level, {}).get("quota_code", [])
                    course["quota_name"] = quota_map.get(level, {}).get("quota_name", [])
        return course_list

    async def get_all_program_fee_data(self, request: CollegeRequest,college_id:int) -> dict:
            course_data= await self.get_course_and_quota_details(self.DATABASE_URL_6, college_id)
            tasks = []
            for course in course_data:
                if course["course_code"] == "MBBS":
                    program_id=course["program_id"]
                    await self.mbbs_model_call(request, prompts.quota_wise_cutoff_data_mbbs, program_id, college_id)
                else:
                    program_id=course["program_id"]
                    new_request = CollegefeesRequest(college_name=request.college_name,state_name=request.state_name,year=request.year,program_name=course["course_code"],quota_name_list=course["quota_name"])
                    tasks.append(self.model_call(new_request, prompts.quota_wise_cutoff_data_program, program_id))

            all_results = await asyncio.gather(*tasks)
            merged_cutoff_quota = []
            college = None
            state = None
            year_id = None
            for result in all_results:
                if "error" not in result:
                    if not college:
                        college = result.get("college_name")
                    if not state:
                        state = result.get("state_name")
                    if not year_id:
                        year_id = result.get("year")
                    merged_cutoff_quota.extend(result.get("quota_wise_cutoff_distribution", []))
            merged_output = {"college_name": college or request.college_name,"state_name": state or request.state_name,"year": year_id or request.year,"quota_wise_cutoff_distribution": merged_cutoff_quota}
            seat_id_list= await self.insert_college_data_async(self.DATABASE_URL_6, merged_output, college_id)
            return merged_output

    async def insert_college_data_async(self, sqlalchemy_url: str, cleaned_data: dict, college_id: int):
            """Inserts cutoff data into the database asynchronously."""
            engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
            async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            async with async_session() as session:
                async with session.begin():
                    insert_sql = text("""INSERT INTO Cutoffs (year, college_id, program_id, quota_id, category_id, round_id, opening_rank, closing_rank, opening_score, closing_score, data_source_reference)
                                      VALUES (:year, :college_id, :program_id, :quota_id, :category_id, :round_id, :opening_rank, :closing_rank, :opening_score, :closing_score, :data_source_reference)""")
                    cutoff_id_list = []
                    for quota in cleaned_data.get("quota_wise_cutoff_distribution", []):
                        quota_name = quota['quota_name']
                        category_names = quota['category_name'].split("/") if '/' in quota['category_name'] else [quota['category_name']]
                        result_quota = await session.execute(
                            text("SELECT quota_id FROM Quotas WHERE quota_name LIKE :quota_name"),{"quota_name": f"%{quota['quota_name']}%"})
                        row_quota = result_quota.fetchone()
                        if not row_quota:
                            result, quota_id = await cs_quota.cs_quota_data_bot.model_call(quota_name=quota_name)
                            #print(f"✅ Quota Created '{quota['quota_name']}' with quota_id = {quota_id}")
                            continue
                        else:
                            quota_id = row_quota.quota_id

                        if not isinstance(quota_id, int):
                            print(f"❌ Invalid quota_id for quota '{quota_name}'. Skipping.")
                            continue

                        for category_name in category_names:
                            result_category = await session.execute(
                                text("SELECT category_id FROM Categories WHERE category_name = :category_name"),{"category_name": category_name})
                            row_category = result_category.fetchone()
                            if not row_category:
                                result_category = await session.execute(
                                    text("SELECT category_id FROM Categories WHERE category_code = :category_name"),{"category_name": category_name})
                                row_category = result_category.fetchone()
                            if not row_category:
                                category_name = category_name
                                category_id = await cs_category.cs_category_data_bot.model_call(category_name=category_name)
                                category_id = category_id
                                #print(f"✅ Category Created '{category_name}' with category_id = {category_id}")
                            else:
                                category_id = row_category.category_id
                            #insert_data = {"year": cleaned_data.get("year"), "college_id": college_id,"program_id": quota.get("program_id"),"quota_id": quota_id,"category_id": category_id,"round_id": quota.get("round_id") if quota.get("round_id") != "null" else 1, "opening_rank": quota.get("closing_rank") if quota.get("closing_rank") != "null" else None, "closing_rank": quota.get("closing_rank") if quota.get("closing_rank") != "null" else None,
                            #              "opening_score": quota.get("closing_score") if quota.get("closing_score") != "null" else None,"closing_score": quota.get("closing_score") if quota.get("closing_score") != "null" else None,"data_source_reference": quota.get("data_source_reference") if quota.get("data_source_reference") != "Not Found" else None}
                            insert_data = {"year": cleaned_data.get("year"),"college_id": college_id,"program_id": quota.get("program_id"),"quota_id": quota_id,"category_id": category_id,"round_id": quota.get("round_id") if quota.get("round_id") != "null" else 1,"opening_rank": None,
                                           "closing_rank": quota.get("closing_rank") if quota.get("closing_rank") not in [0, "0", "null", None] else None,"opening_score": None,"closing_score": quota.get("closing_score") if quota.get("closing_score") not in [0, "0", "null", None] else None,"data_source_reference": quota.get("data_source_reference") if quota.get("data_source_reference") != "Not Found" else None}
                            result_insert = await session.execute(insert_sql, insert_data)
                            cutoff_id = result_insert.lastrowid
                            cutoff_id_list.append(cutoff_id)
                            if not cutoff_id:
                                raise Exception(f"❌ Failed to insert cutoff data for college '{cleaned_data['college_name']}'!")
                            #print(f"✅ Inserted Cutoff data for Quota '{quota_name}' (quota_id: {quota_id}), Category '{category_name}' (category_id: {category_id}) with cutoff_id = {cutoff_id}")
                    await session.commit()
                    print("✅ All College Cutoff inserted successfully!")

            return cutoff_id_list
cs_cutoff_bot= cutoffResponseGenerator()
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
from cs_data_collection.cs_college_cutoff import cs_cutoff_bot
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

class seatsResponseGenerator:
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
            for item in result["quota_wise_seat_distribution"]:
              item["program_id"] = program_id
            return result
        except Exception as e:
            logging.exception("Model call failed")
            return {"error": str(e)}

    async def mbbs_model_call(self,request:CollegeRequest,prompts_temp, program_id) -> dict:
        try:
            start = time.time()
            chain, mbbs_chain=await self.create_chatbot_response_generator(prompts_temp)
            result = await mbbs_chain.ainvoke({"college_name": request.college_name,"state_name": request.state_name,"format_guide": self.format_guide,"year": request.year})
            logging.info("LLM call took %.2f s", time.time() - start)
            for item in result["quota_wise_seat_distribution"]:
              item["program_id"] = program_id
            seat_id_list= await self.insert_college_data_async(self.DATABASE_URL_6, result)
            #print(json.dumps(result, indent=2))
            return result
        except Exception as e:
            logging.exception("Model call failed")
            return {"error": str(e)}

    async def get_all_program_fee_data(self, request: CollegeRequest, college_id: int):
            course_data = await cs_cutoff_bot.get_course_and_quota_details(self.DATABASE_URL_6, college_id)
            tasks = []
            for course in course_data:
                if course["course_code"] == "MBBS":
                    program_id=course["program_id"]
                    await self.mbbs_model_call(request, prompts.seat_intake_mbbs, program_id)
                else:
                    program_id=course["program_id"]
                    new_request = CollegefeesRequest(
                        college_name=request.college_name,
                        state_name=request.state_name,
                        year=request.year,
                        program_name=course["course_code"],
                        quota_name_list=course["quota_name"]
                    )
                    tasks.append(self.model_call(new_request, prompts.seat_intake_per_program, program_id))

            all_results = await asyncio.gather(*tasks)

            merged_seats_quota = []
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
                    merged_seats_quota.extend(result.get("quota_wise_seat_distribution", []))
            merged_output = {"college_name": college or request.college_name,"state_name": state or request.state_name,"year": year_id or request.year,"quota_wise_seat_distribution": merged_seats_quota}
            seat_id_list= await self.insert_college_data_async(self.DATABASE_URL_6, merged_output)
            return merged_output

    async def insert_college_data_async(self, sqlalchemy_url: str, cleaned_data: dict):
            """Inserts seat matrix data into the database asynchronously."""
            engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
            async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            async with async_session() as session:
                async with session.begin():
                    insert_sql = text("""INSERT INTO Seat_Matrix (year, program_id, quota_id, category_id, round_id, Total_seat_intake, number_of_seats, data_source_reference)
                                      VALUES (:year, :program_id, :quota_id, :category_id, :round_id, :Total_seat_intake, :number_of_seats, :data_source_reference)""")
                    seat_id_list = []
                    for quota in cleaned_data.get("quota_wise_seat_distribution", []):
                        quota_name = quota['quota_name']
                        category_names = quota['category_name'].split("/") if '/' in quota['category_name'] else [quota['category_name']]
                        result_quota = await session.execute(
                            text("SELECT quota_id FROM Quotas WHERE quota_name LIKE :quota_name"),{"quota_name": f"%{quota['quota_name']}%"})
                        row_quota = result_quota.fetchone()
                        if not row_quota:
                            result, quota_id = await cs_quota.cs_quota_data_bot.model_call(quota_name=quota_name)
                            #print(f"✅ Quota Created '{quota['quota_name']}' with quota_id = {quota_id}")
                            continue
                        quota_id = row_quota.quota_id

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
                            insert_data = {"year": cleaned_data.get("year"),"program_id": quota.get("program_id"),"quota_id": quota_id,"category_id": category_id,"round_id": quota.get("round_id") if quota.get("round_id") != "null" else 1, "Total_seat_intake": quota.get("Total_seat_intake") if quota.get("Total_seat_intake") != "null" else None,
                                          "number_of_seats": quota.get("number_of_seats") if quota.get("number_of_seats") != "null" else None,"data_source_reference": quota.get("data_source_reference") if quota.get("data_source_reference") != "Not Found" else None}
                            result_insert = await session.execute(insert_sql, insert_data)
                            seat_matrix_id = result_insert.lastrowid
                            seat_id_list.append(seat_matrix_id)
                            if not seat_matrix_id:
                                raise Exception(f"❌ Failed to insert seat matrix data for college '{cleaned_data['college_name']}'!")
                            #print(f"✅ Inserted seat matrix data for Quota '{quota_name}' (quota_id: {quota_id}), Category '{category_name}' (category_id: {category_id}) with seat_matrix_id = {seat_matrix_id}")
                    await session.commit()
                    print("✅ All College seat intakes inserted successfully!")

            return seat_id_list
cs_seat_intake_bot= seatsResponseGenerator()
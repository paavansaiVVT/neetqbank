from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
import os, logging, time, json
from dotenv import load_dotenv
from cs_data_collection import prompts
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
load_dotenv()

parser = JsonOutputParser()
search_tool = GenAITool(google_search={})

class CategoryResponseGenerator:
    def __init__(self):
        self.format_guide = parser.get_format_instructions()
        self.DATABASE_URL_6 = os.getenv("DATABASE_URL_6")
        self.llm = (ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[search_tool]))
        self.prompt = PromptTemplate.from_template(prompts.system_prompt_category)
        self.chain = self.prompt | self.llm | parser

    async def model_call(self, category_name: str) -> dict:
        try:
            print(f"🔍 Searching category data for '{category_name}'")
            start = time.time()
            result = await self.chain.ainvoke({"category_name": category_name, "format_guide": self.format_guide,})
            #logging.info("LLM call took %.2f s", time.time() - start)
            category_id = await self.insert_category_data_async(self.DATABASE_URL_6, result)
            if not category_id:
                raise Exception(f"❌ Category ID is None after inserting '{category_name}'.")
            return category_id
        except Exception as e:
            logging.exception(f"Model call failed for category '{category_name}'")
            return {"error": str(e)}

    async def insert_category_data_async(self, sqlalchemy_url: str, cleaned_data: dict):
        """ Inserts category data into the database asynchronously and returns the inserted category_id. """
        cleaned_data["is_pwd"] = 1 if cleaned_data.get("is_pwd") == "YES" else 0
        cleaned_data["is_central_list"] = 1 if cleaned_data.get("is_central_list") == "YES" else 0
        engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with async_session() as session:
            async with session.begin():
                result_check = await session.execute(
                    text("SELECT category_id FROM Categories WHERE category_code = :category_code"),{"category_code": cleaned_data["category_code"]})
                row = result_check.fetchone()
                if row:
                    #logging.info(f"✅ Category already exists: {cleaned_data['category_code']} (category_id = {row.category_id})")
                    return row.category_id
                if cleaned_data.get("state_name") and cleaned_data["state_name"] != "None":
                    result_state = await session.execute(text("SELECT state_id FROM States WHERE state_name = :state_name"),{"state_name": cleaned_data["state_name"]})
                    row = result_state.fetchone()
                    if not row:
                        result_check = await session.execute(
                    text("INSERT INTO Categories (state_name) VALUES (:state_name)"),{"state_name": cleaned_data["state_name"]})
                        #logging.info(f"✅ State '{cleaned_data['state_name']}' Created")
                    
                    state_id = row.state_id
                    #logging.info(f"✅ Found state_id = {state_id} for state '{cleaned_data['state_name']}'")
                    cleaned_data["state_id"] = state_id
                else:
                    cleaned_data["state_id"] = None
                    logging.info(f"❗ No state name provided or it is 'None', skipping state_id lookup.")
                insert_sql = text("""INSERT INTO Categories (category_code,category_name,category_description,is_pwd,is_central_list,state_id
                ) VALUES (:category_code,:category_name,:category_description,:is_pwd,:is_central_list,:state_id)""")
                result = await session.execute(insert_sql, cleaned_data)
                category_id = getattr(result, "lastrowid", None)
                if not category_id:
                    raise Exception(f"❌ Failed to insert category '{cleaned_data['category_name']}'!")
                #logging.info(f"✅ Inserted category '{cleaned_data['category_name']}' with category_id = {category_id}")
        return category_id
    
cs_category_data_bot = CategoryResponseGenerator()
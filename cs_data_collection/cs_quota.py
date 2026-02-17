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

class QuotaResponseGenerator:
    def __init__(self):
        self.format_guide = parser.get_format_instructions()
        self.DATABASE_URL_6 = os.getenv("DATABASE_URL_6")
        self.llm = (ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY"),).bind(tools=[search_tool]))
        self.prompt = PromptTemplate.from_template(prompts.system_prompt_quota)
        self.chain = self.prompt | self.llm | parser

    async def model_call(self, quota_name: str) -> dict:
        try:
            start = time.time()
            result = await self.chain.ainvoke({"quota_name": quota_name,"format_guide": self.format_guide,})
            logging.info("LLM call took %.2f s", time.time() - start)
            quota_id= await self.insert_quota_data_async(self.DATABASE_URL_6, result)
            return result, quota_id
        except Exception as e:
            logging.exception("Model call failed")
            return {"error": str(e)}

    async def insert_quota_data_async(self, sqlalchemy_url: str, cleaned_data: dict):
        """ Inserts quota data into the database asynchronously and returns the inserted quota_id."""
        cleaned_data["likely_context"] = json.dumps(cleaned_data.get("likely_context", []))
        cleaned_data["quota_type"] = json.dumps(cleaned_data.get("quota_type", []))
        engine = create_async_engine(sqlalchemy_url, echo=False, future=True)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with async_session() as session:
            async with session.begin():
                insert_sql = text("""INSERT INTO Quotas (quota_code,quota_name,quota_description,likely_context,quota_type,requires_institutional_affiliation
                ) VALUES (:quota_code,:quota_name,:quota_description,:likely_context,:quota_type,:requires_institutional_affiliation)""")
                result = await session.execute(insert_sql, cleaned_data)
                quota_id = None
                if hasattr(result, "lastrowid"):
                    quota_id = result.lastrowid
                elif hasattr(result, "cursor") and hasattr(result.cursor, "lastrowid"):
                    quota_id = result.cursor.lastrowid
                if not quota_id:
                    raise Exception(f"❌ Failed to insert quota '{cleaned_data['quota_name']}'!")
                print(f"✅ Inserted quota '{cleaned_data['quota_name']}' with quota_id = {quota_id}")
        return quota_id

cs_quota_data_bot= QuotaResponseGenerator()
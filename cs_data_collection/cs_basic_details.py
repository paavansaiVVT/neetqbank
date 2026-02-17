from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage

import os, logging, time, asyncio, re, json
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, JSON, text
from cs_data_collection import prompts

load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SQLAlchemy ORM Base
Base = declarative_base()

# ORM Model
class College(Base):
    __tablename__ = "Colleges"
    college_id = Column(Integer, primary_key=True)
    college_name = Column(String)
    college_code_mcc = Column(String)
    college_code_state = Column(String)
    mobile_number = Column(String)
    college_email_id = Column(String)
    state_id = Column(Integer)
    district = Column(String)
    city = Column(String)
    college_address = Column(String)
    college_pincode = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    college_type = Column(String)
    establishment_year = Column(Integer)
    university_affiliation = Column(String)
    nmc_recognized = Column(Integer)
    website_url = Column(String)
    minority_status = Column(String)
    female_only = Column(Integer)
    hostel_available = Column(Integer)
    misc_details = Column(JSON)


# Request Model
class CollegeRequest(BaseModel):
    college_name: str
    state_name: str
    year: int


class BasicResponseGenerator:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL_6")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL_6 not found in environment variables.")
        
        self.engine = create_async_engine(self.DATABASE_URL, echo=False, pool_size=100, max_overflow=50, pool_timeout=60, pool_recycle=1800)
        self.async_session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)

        self.parser = JsonOutputParser()
        self.format_guide = self.parser.get_format_instructions()  # 🔥 Added missing part

        self.search_tool = GenAITool(google_search={})
        #self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash",api_key=os.getenv("GOOGLE_API_KEY")).bind(tools=[self.search_tool])
        self.llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-pro-preview-05-06", api_key=os.getenv("GOOGLE_API_KEY"))
        self.prompt = PromptTemplate.from_template(prompts.system_prompt_basic_dl)

        self.chain = self.prompt | self.llm | RunnableLambda(self.clean_llm_output) | self.parser

    def clean_llm_output(self, raw_text) -> str:
        if isinstance(raw_text, AIMessage):
            raw_text = raw_text.content

        raw_text = re.sub(r"\([^)]*\)", "", raw_text)  # Remove (...) parts
        raw_text = re.sub(r"\[[^\]]*\]", "", raw_text)  # Remove [...] parts
        return raw_text

    def clean_llm_output_basic(self, raw_output: str) -> dict:
        raw_output = raw_output.replace("'", '"')
        raw_output = re.sub(r',\s*}', '}', raw_output)

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input: {e}")

        def strip_brackets(value):
            if isinstance(value, str):
                value = re.sub(r'\([^)]*\)', '', value)
                value = re.sub(r'\[[^]]*\]', '', value)
                return value.strip()
            return value

        misc = {}
        for key, value in parsed.items():
            if isinstance(value, str):
                cleaned = strip_brackets(value)
                if key in ['phone_number', 'email_id']:
                    items = re.split(r',|/', cleaned)
                    items = [i.strip() for i in items if i.strip()]
                    parsed[key] = items[0] if items else cleaned
                    if len(items) > 1:
                        misc[f"alternate_{key}s"] = items[1:]
                else:
                    parsed[key] = cleaned
            elif isinstance(value, list):
                parsed[key] = [strip_brackets(i) for i in value if isinstance(i, str)]

        if 'fees' in parsed:
            misc['fees'] = parsed.pop('fees')
        if 'campus_size' in parsed:
            misc['campus_size'] = parsed.pop('campus_size')

        parsed['misc_details'] = misc
        return parsed

    async def model_call(self, request: CollegeRequest) -> dict:
        try:
            start = time.time()
            raw_result = await self.chain.ainvoke({
                "college_name": request.college_name,
                "state_name": request.state_name,
                "year": request.year,
                "format_guide": self.format_guide
            })
            logging.info("LLM call took %.2f seconds", time.time() - start)

            cleaned_input = json.dumps(raw_result) if isinstance(raw_result, dict) else raw_result
            clean_result = self.clean_llm_output_basic(cleaned_input)
            #print("Cleaned Result:", clean_result)
            if not clean_result:
                raise ValueError("Empty or invalid response from LLM.")
            college_id, state_id = await self.insert_college_basic_data(clean_result)

            return {"college_id": college_id, "state_id": state_id}

        except Exception as e:
            logging.exception("Model call failed")
            return {"college_id": None, "state_id": None, "error": str(e)}

    async def insert_college_basic_data(self, cleaned_data: dict):
        if isinstance(cleaned_data.get("misc_details"), dict):
            cleaned_data["misc_details"] = json.dumps(cleaned_data["misc_details"])

        async with self.async_session_factory() as session:
            async with session.begin():
                try:
                    result_state = await session.execute(
                        text("SELECT state_id FROM States WHERE state_name = :state_name"),
                        {"state_name": cleaned_data["state_name"]}
                    )
                    row = result_state.fetchone()
                    if not row:
                        raise Exception(f"❌ State '{cleaned_data['state_name']}' not found!")
                    state_id = row.state_id

                    new_college = College(
                        college_name=cleaned_data["college_name"],
                        college_code_mcc=cleaned_data["college_code_mcc"],
                        college_code_state=cleaned_data["college_code_state"],
                        mobile_number=cleaned_data["phone_number"],
                        college_email_id=cleaned_data["email_id"],
                        state_id=state_id,
                        district=cleaned_data["district"],
                        city=cleaned_data["city"],
                        college_address=cleaned_data["address"],
                        college_pincode=cleaned_data["pincode"],
                        latitude=cleaned_data["latitude"],
                        longitude=cleaned_data["longitude"],
                        college_type=cleaned_data["college_type"],
                        establishment_year=cleaned_data["establishment_year"],
                        university_affiliation=cleaned_data["university_affiliation"],
                        nmc_recognized=cleaned_data["nmc_recognized"],
                        website_url=cleaned_data["website_url"],
                        minority_status=cleaned_data["minority_status"],
                        female_only=cleaned_data["female_only"],
                        hostel_available=cleaned_data["hostel_available"],
                        misc_details=cleaned_data["misc_details"]
                    )

                    session.add(new_college)
                    await session.flush()  # Flush to get auto-incremented college_id

                    college_id = new_college.college_id

                    if not college_id:
                        raise Exception(f"❌ Failed to insert college '{cleaned_data['college_name']}'!")
                    
                    await session.commit()

                    logging.info(f"✅ Inserted College '{cleaned_data['college_name']}' with college_id = {college_id}")
                    return college_id, state_id

                except Exception as e:
                    await session.rollback()
                    logging.error(f"❌ Error during DB operation: {e}")
                    raise

# Create Object
cs_basic_data_bot = BasicResponseGenerator()

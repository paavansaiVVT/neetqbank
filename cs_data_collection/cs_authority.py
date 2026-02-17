from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from cs_data_collection import prompts
from cs_data_collection.cs_basic_details import CollegeRequest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text, select, update
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String
import os, logging, asyncio, json, time, re
from typing import List, Optional

load_dotenv()

# --- Define Base for SQLAlchemy
Base = declarative_base()

# --- Table Models
class Counseling_Authorities(Base):
    __tablename__ = "Counseling_Authorities"
    authority_id = Column(Integer, primary_key=True)
    state_id = Column(Integer)
    authority_name = Column(String)
    website_url = Column(String)
    authority_type = Column(String)

class Colleges(Base):
    __tablename__ = "Colleges"
    college_id = Column(Integer, primary_key=True)
    authority_id = Column(String)   # Comma-separated list of authority IDs
    college_name = Column(String)

# --- Generator Class
class Generator:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL_6")
        self.engine = create_async_engine(
            self.DATABASE_URL,
            echo=False,
            pool_size=100,
            max_overflow=50,
            pool_timeout=60,
            pool_recycle=1800,
        )
        self.async_session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, class_=AsyncSession
        )
        self.parser = JsonOutputParser()
        self.format = self.parser.get_format_instructions()
        self.search_tool = GenAITool(google_search={})
        self.llm = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-pro-preview-05-06",
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", prompts.system_prompt_authorities),
            ("user", "COLLEGE: {college_name}\nSTATE  : {state_name}\nauthority_names_list: {authority_names_list}\n\nformat_guide: {format_guide}")
        ])
        self.chain = self.prompt | self.llm | self.parser

    async def get_data(self, request: CollegeRequest, college_id: int, state_id: int) -> dict:
        """Fetch authority data and update the Colleges table with authority IDs."""
        authority_names_list = await self.get_authority_names(state_id)
        response = self.chain.invoke({
            "college_name": request.college_name,
            "state_name": request.state_name,
            "authority_names_list": authority_names_list,
            "format_guide": self.format
        })
        await self.insert_authority_id_into_college(response, college_id, state_id)
        return response

    async def get_authority_names(self, state_id: int) -> List[str]:
        """Fetch list of authority names for the given state."""
        async with self.async_session_factory() as session:
            try:
                result = await session.execute(
                    select(Counseling_Authorities).where(Counseling_Authorities.state_id == state_id)
                )
                authorities = result.scalars().all()
                return [authority.authority_name for authority in authorities]
            except Exception as e:
                print(f"❌ Error fetching authority names: {e}")
                return []

    async def insert_authority_id_into_college(self, data: dict, college_id: int, state_id: int):
        """Insert authorities if needed and update the Colleges table."""
        async with self.async_session_factory() as session:
            try:
                authority_id_list = []
                for authority_info in data["authorities"]:
                    if authority_info["authority_type"] == "Central":
                        print("Central Authority")
                        authority_id = 35  # Hardcoded Central Authority ID
                    elif authority_info["authority_type"] == "State":
                        print("State Authority")
                        authority_id = await self.insert_authority(session, authority_info, state_id, "State")
                    elif authority_info["authority_type"] == "Institutional":
                        print("Institutional Authority")
                        authority_id = await self.insert_authority(session, authority_info, state_id, "Institutional")
                    else:
                        print("Unknown Authority Type")
                        continue
                    
                    authority_id_list.append(authority_id)

                # Create a comma-separated string of unique authority_ids
                authority_id_csv = ",".join(map(str, set(authority_id_list)))

                # Update college with authority IDs
                await session.execute(
                    update(Colleges)
                    .where(Colleges.college_id == college_id)
                    .values(authority_id=authority_id_csv)
                )
                await session.commit()
                print(f"✅ Updated college_id {college_id} with authority_id(s) {authority_id_list}")

            except Exception as e:
                await session.rollback()
                print(f"❌ Error updating college authorities: {e}")
                import traceback; traceback.print_exc()

    async def insert_authority(self, session: AsyncSession, data: dict, state_id: int, authority_type: str) -> int:
        """Insert a new authority if not already existing."""
        try:
            authority_name = data["authority_name"]
            result = await session.execute(
                select(Counseling_Authorities).where(Counseling_Authorities.authority_name == authority_name)
            )
            existing_authority = result.scalars().first()

            if existing_authority:
                print(f"⚡ Authority '{authority_name}' already exists. Skipping insert.")
                return existing_authority.authority_id
            else:
                new_authority = Counseling_Authorities(
                    state_id=state_id,
                    authority_name=authority_name,
                    website_url=data.get("authority_url"),
                    authority_type=authority_type,
                )
                session.add(new_authority)
                await session.flush()  # To assign ID
                print(f"✅ Inserted new authority '{authority_name}' successfully.")
                return new_authority.authority_id

        except Exception as e:
            await session.rollback()
            print(f"❌ Error inserting authority: {e}")
            import traceback; traceback.print_exc()
            return -1

# --- Instance creation
cs_authority_data = Generator()

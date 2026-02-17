from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from tutor_bots.classes import Milestone
from dotenv import load_dotenv
from sqlalchemy import select,func
from tutor_bots.classes import RequestData,AIQuestion
import logging,os


# Create an asynchronous engine (adjust the connection string as needed)
load_dotenv()
DATABASE_URL=os.getenv("DATABASE_URL_2")
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



engine = create_async_engine(DATABASE_URL, echo=False)

# Create an async session factory
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

        

async def insert_milestone(request_data:RequestData, new_level: int):
    """
    Insert or update a milestone record in the database.

    Args:
        chapter_name (str): The chapter name.
        user_id (int): The user ID.
        chapter_id (int): The chapter ID.
        new_level (int): The level to insert or update.
        topic_ids (list): List of topic IDs.

    Returns:
        str: A message indicating whether a record was inserted or updated.
    """
    async with async_session_factory() as session:
        try:
            # Convert topic_ids list to a comma-separated string
            topic_ids_str = ",".join(map(str,request_data.topic_ids))

            # Create a new entry if no matching record exists
            new_record = Milestone(chapter_name=request_data.chapter,chapter_id=request_data.chapter_id,user_id=request_data.user_id,level=new_level,topic_ids=topic_ids_str,date=request_data.studyPlanDate,instruction_id=request_data.instruction_id)
            session.add(new_record)
            await session.commit()
            await session.refresh(new_record)
            logger.info(f"Inserted new milestone: {new_record}")
            return "Inserted new milestone"

        except Exception as e:
            logger.error(f"Error inserting/updating milestone: {e}")
            return None
        

async def extract_pyq(chapter_id:int):
    async with async_session_factory() as session:
        try:
            # Construct the select statement
            query = (select(AIQuestion.question,AIQuestion.correct_opt,AIQuestion.option_a,AIQuestion.option_b,AIQuestion.option_c,AIQuestion.option_d).where((AIQuestion.year != 0) & (AIQuestion.c_id == chapter_id)).order_by(func.random()).limit(5))
            # Execute the query
            result = await session.execute(query)
            # Fetch all matching records
            #records = result.fetchall()
            records = result.mappings().all()
            return records
        except Exception as e:
            logger.error(f"Error in Extracting PYQs: {e}")
            return None





    
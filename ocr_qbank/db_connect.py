from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os, logging, asyncio,constants
#from constants import #difficulty_level, cognitive_levels, question_types,
from ocr_qbank import classes, refine_question
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL_2")
engine = create_async_engine(DATABASE_URL,pool_size=100,max_overflow=50,pool_recycle=1800, pool_pre_ping=True, connect_args={"connect_timeout": 600})
AsyncSessionLocal = sessionmaker(bind=engine,class_=AsyncSession,expire_on_commit=False)

Base = declarative_base()
retry_on_failure = retry(stop=stop_after_attempt(3),wait=wait_fixed(5),before_sleep=before_sleep_log(logger, logging.WARNING))

async def fetch_topic_details(topic_name, question= None, topic_list = [] , retry_id = 0):
    session = get_session()
    for attempt in range(3):
        try:
            async with session.begin():
                result_topic = await session.execute(
                    text("SELECT s_no, s_id, c_id FROM neetguide.topics WHERE t_name = :t_name"),{"t_name": topic_name.strip()})
                row_topic = result_topic.fetchone()
                if row_topic:
                    return row_topic.s_no, row_topic.s_id, row_topic.c_id
                if retry_id == 0:
                    logger.info(f"Topic '{topic_name}' not found in database. Trying question bank fallback.")
                    topic_id, subject_id, chapter_id = await refine_question.refine_function.topic_check(question=question,old_topic=topic_name,topic_name_list=topic_list)
                    return topic_id, subject_id, chapter_id
                else:
                    logger.error(f"❌ Topic name '{topic_name}' not found after fallback.")
                    return None, None, None

        except OperationalError as e:
            logger.warning(f"OperationalError on attempt {attempt + 1} for topic '{topic_name}': {e}")
            await asyncio.sleep(2)  # wait before retry
        except Exception as e:
            logger.error(f"Unexpected error fetching topic '{topic_name}': {e}")
            return None, None, None
        finally:
            await session.close()

    return None, None, None

def get_session():
    return AsyncSessionLocal()

@retry_on_failure
async def add_mcq_data(request: classes.RefineMCQs, all_data, table_name):
    session = get_session()
    try:
        mcq_objects = []
        for entry in all_data:
            try:
                mcq = table_name(
                    user_id=request.user_id,
                    uuid=request.uuid,
                    stream= entry['stream'],
                    file_name = request.file_name,
                    question=entry['question'],
                    correct_opt=entry["correct_option"],
                    option_a=entry['options'][0],
                    option_b=entry['options'][1],
                    option_c=entry['options'][2],
                    option_d=entry['options'][3],
                    answer_desc=entry['explanation'],
                    difficulty=entry['difficulty'],
                    question_type=entry['question_type'],
                    keywords=entry['concepts'],
                    cognitive_level=entry['cognitive_level'],
                    t_id=entry['t_id'],
                    s_id=entry['s_id'],
                    c_id=entry['c_id'],
                    estimated_time=entry["estimated_time"],
                    QC=entry["QC"],
                    model=entry['model'],
                    model_id=1,
                    reason= entry.get("reason", None),
                    q_image=entry.get("q_image", None),
                    option_1_image=entry.get("option_1_image", None),
                    option_2_image=entry.get("option_2_image", None),
                    option_3_image=entry.get("option_3_image", None),
                    option_4_image=entry.get("option_4_image", None)
                )
                mcq_objects.append(mcq)
            except Exception as e:
                logger.error(f"Error preparing question: {entry}. Error: {e}")
                continue

        session.add_all(mcq_objects)
        await session.commit()
        logger.info(f"Committed batch of {len(mcq_objects)} records.")
    except Exception as e:
        await session.rollback()
        logger.error(f"An error occurred in add MCQ in database: {e}")
        raise

    finally:
        await session.close()
        #logger.info("Session closed.")

from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os, logging, asyncio,constants
#from constants import #difficulty_level, cognitive_levels, question_types,

from cs_qbanks import cs_classes, cs_question_bank
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL_7")
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
                    text("SELECT s_no, s_id, c_id FROM cs_qbank.topics WHERE t_name = :t_name"),{"t_name": topic_name.strip()})
                row_topic = result_topic.fetchone()
                if row_topic:
                    return row_topic.s_no, row_topic.s_id, row_topic.c_id
                if retry_id == 0:
                    logger.info(f"Topic '{topic_name}' not found in database. Trying question bank fallback.")
                    topic_id, subject_id, chapter_id = await cs_question_bank.question_banks.topic_check(question=question,old_topic=topic_name,topic_name_list=topic_list)
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
async def add_mcq_data(request: cs_classes.QuestionRequest, all_data, table_name):
    session = get_session()
    try:
        mcq_objects = []
        for entry in all_data:
            try:
                mcq = table_name(
                    user_id=request.user_id,
                    uuid=request.uuid,
                    stream= entry['stream'],
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
                    model_id=request.model,
                    reason= entry.get("reason", None)
                )
                mcq_objects.append(mcq)
            except Exception as e:
                logger.error(f"Error preparing question: {entry}. Error: {e}")
                continue

        session.add_all(mcq_objects)
        await session.commit()
        logger.info(f"Committed batch of {len(mcq_objects)} records.")
        #asyncio.create_task(update_progress(uuid= request.uuid, progress= 5))
        result = {"Combination": [request.stream, request.chapter_name, request.topic_name, request.difficulty, request.cognitive_level],
                  "Question_count": {len(mcq_objects)}}
        return result
    except Exception as e:
        await session.rollback()
        logger.error(f"An error occurred in add MCQ in database: {e}")
        raise

    finally:
        await session.close()
        #logger.info("Session closed.")

async def old_mcq_data(question_id, user_query, model, row_ques):
    """Insert old MCQs into another table."""
    session = get_session()
    try:
        old_mcq = cs_classes.cs_oldMCQ(
            q_id=question_id,
            question=row_ques.question,
            correct_opt=row_ques.correct_opt,
            option_a=row_ques.option_a,
            option_b=row_ques.option_b,
            option_c=row_ques.option_c,
            option_d=row_ques.option_d,
            answer_desc=row_ques.answer_desc,
            difficulty=row_ques.difficulty,
            question_type=row_ques.question_type,
            keywords=row_ques.keywords,
            cognitive_level=row_ques.cognitive_level,
            t_id=row_ques.t_id,
            s_id=row_ques.s_id,
            c_id=row_ques.c_id,
            estimated_time=row_ques.estimated_time,
            QC=row_ques.QC,
            user_query=str(user_query),
            model= model
        )
        session.add(old_mcq)
        await session.commit()
        logger.info("Old MCQ data inserted successfully.")

    except Exception as e:
        logger.error(f"Error preparing question: {row_ques.question}. Error: {e}")
    finally:
        await session.close()

async def question_det(question_id, user_query, model):
    """Fetch question details from the database where s_no = question_id."""
    session = get_session()
    for attempt in range(3):
        try:
            async with session.begin():
                query = text(""" SELECT q.question, q.correct_opt, q.option_a, q.option_b, q.option_c, q.option_d, q.difficulty, q.t_id, q.c_id, q.s_id, q.estimated_time, q.QC, q.answer_desc, q.question_type, q.keywords, t.t_name AS topic_name, s.s_name AS subject_name, c.c_name AS chapter_name, q.cognitive_level
                    FROM cs_qbank.ai_questions q JOIN cs_qbank.topics t ON q.t_id = t.s_no JOIN cs_qbank.subjects s ON q.s_id = s.s_no JOIN cs_qbank.chapters c ON q.c_id = c.s_no WHERE q.s_no = :s_no """)
                result_question = await session.execute((query),{"s_no": question_id})
                row_ques = result_question.fetchone()
                if not row_ques:
                    raise Exception(f"❌ Question ID {question_id} not found!")
                difficulty = next((k for k, v in constants.difficulty_level.items() if v == row_ques.difficulty), None)
                question_type = next((k for k, v in constants.question_types.items() if v == row_ques.question_type), None)
                cognitive_level = next((k for k, v in constants.cognitive_levels.items() if v == row_ques.cognitive_level), None)
                ques_dict= {
                "question": row_ques.question,
                "correct_option": row_ques.correct_opt,
                "options": [row_ques.option_a, row_ques.option_b, row_ques.option_c, row_ques.option_d],
                "explanation": row_ques.answer_desc,
                "difficulty": difficulty,
                "subject_name": row_ques.subject_name,
                "chapter_name": row_ques.chapter_name,
                "topic_name": row_ques.topic_name,
                "cognitive_level": cognitive_level,
                "question_type": question_type,
                "concepts": row_ques.keywords
                }
                asyncio.create_task(old_mcq_data(question_id, user_query, model, row_ques))
                return ques_dict
        except OperationalError as e:
            logger.warning(f"Retry {attempt+1}/3 - DB timeout for q_id={question_id}: {e}")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Unexpected error fetching question {question_id}: {e}")
            return None
        finally:
            await session.close()
    return None

async def update_mcq_data(request: cs_classes.ImprovedQuestionReq, old_ques_data, ques_data):
    """Update improved MCQ into the database where s_no = request.question_id."""
    session = get_session()
    try:
        topic_id, subject_id, chapter_id = await fetch_topic_details(
            ques_data['topic_name'],
            ques_data['question'],
            old_ques_data['topic_name'],
            retry_id=0
        )

        correct_answer = ques_data['correct_answer']
        correct_opt = ques_data['options'].index(correct_answer) + 1

        # Fetch existing record by question_id (s_no)
        existing_mcq = await session.get(cs_classes.cs_MCQData, request.question_id)

        if not existing_mcq:
            raise Exception(f"Question with s_no={request.question_id} not found.")

        existing_mcq.question = ques_data['question']
        existing_mcq.correct_opt = correct_opt
        existing_mcq.option_a = ques_data['options'][0]
        existing_mcq.option_b = ques_data['options'][1]
        existing_mcq.option_c = ques_data['options'][2]
        existing_mcq.option_d = ques_data['options'][3]
        existing_mcq.answer_desc = ques_data['explanation']
        existing_mcq.difficulty = constants.difficulty_level[ques_data['difficulty'].lower()]
        existing_mcq.question_type = constants.question_types[ques_data['question_type']]
        existing_mcq.keywords = ', '.join(ques_data['concepts']) if isinstance(ques_data['concepts'], list) else ques_data['concepts']
        existing_mcq.cognitive_level = constants.cognitive_levels[ques_data['cognitive_level'].lower()]
        existing_mcq.t_id = topic_id
        existing_mcq.s_id = subject_id
        existing_mcq.c_id = chapter_id

        await session.commit()
        logger.info(f"Updated question with s_no={request.question_id} successfully.")
        return {"status": "success", "message": f"Question {request.question_id} updated successfully"}

    except Exception as e:
        await session.rollback()
        raise e
    finally:
        await session.close()
        logger.info("Session closed")

async def get_question_det_repo(topic_id: int, cog_id: int):
    session = get_session()
    questions = []
    for attempt in range(3):
        try:
            async with session.begin():
                result_question = await session.execute(
                    text("SELECT question FROM cs_qbank.ai_questions_repo WHERE t_id = :t_id AND cognitive_level = :cognitive_level"), 
                    {"t_id": topic_id, "cognitive_level": cog_id}
                )
                rows_questions = result_question.fetchall()
                for row in rows_questions:
                    if row.question:
                        questions.append(row.question)
                if questions:
                    return questions
                else:
                    logger.info(f"❌ The is no Question from this topic ID {topic_id}.")
                    return None
        except OperationalError as e:
            logger.warning(f"OperationalError on attempt {attempt + 1} for topic '{topic_id}': {e}")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Unexpected error fetching topic '{topic_id}': {e}")
            return None
        finally:
            await session.close()
    return None

async def get_topic_det(chapter_name):
    session = get_session()
    topic_dets = []
    for attempt in range(3):
        try:
            async with session.begin():
                result_top = await session.execute(
                    text("SELECT DISTINCT t.s_no, t.t_name AS topic_name, s.s_name AS subject_name, c.c_name AS chapter_name FROM cs_qbank.topics t JOIN cs_qbank.subjects s ON t.s_id = s.s_no JOIN cs_qbank.chapters c ON t.c_id = c.s_no WHERE c.c_name = :c_name;"), 
                    {"c_name": chapter_name.strip()}
                )
                rows_details = result_top.fetchall()
                for row in rows_details:
                    if row:
                        topic_dets.append(row)
                if topic_dets:
                    return topic_dets
                else:
                    logger.info(f"❌ The chapter name: {chapter_name} is not found.")
                    return None
        except OperationalError as e:
            logger.warning(f"OperationalError on attempt {attempt + 1} for chapter '{chapter_name}': {e}")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Unexpected error fetching chapter '{chapter_name}': {e}")
            return None
        finally:
            await session.close()
    return None

async def update_progress(uuid: str, progress: int):
    session = get_session()
    try:
        stmt = select(cs_classes.ProgressData).where(cs_classes.ProgressData.uuid == uuid)
        result = await session.execute(stmt)
        existing_record = result.scalar_one_or_none()

        if not existing_record:
            logger.error(f"❌ Progress record for UUID {uuid} not found. Did creation fail or was it not committed?")
            raise Exception(f"Progress record for UUID {uuid} not found.")

        previous_progress = existing_record.progress_percent
        new_progress = previous_progress + progress

        if new_progress > 100:
            logger.warning(f"⚠️ Capping progress at 100%. Attempted update: {new_progress}")
            new_progress = 100

        existing_record.progress_percent = new_progress
        await session.commit()
        logger.info(f"✅ Updated progress for UUID {uuid}: {previous_progress}% → {new_progress}%")
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error updating progress for UUID {uuid}: {e}")
        raise
    finally:
        await session.close()

async def add_progress(uuid: str):
    session = get_session()
    try:
        async with session.begin():
            # Check if a record with the UUID already exists
            existing = await session.execute(
                text("SELECT 1 FROM cs_qbank.progress_table WHERE uuid = :uuid"),
                {"uuid": uuid}
            )
            if existing.scalar():
                logger.info(f"⚠️ Progress record already exists for UUID: {uuid}")
                stmt = select(cs_classes.ProgressData).where(cs_classes.ProgressData.uuid == uuid)
                result = await session.execute(stmt)
                existing_record = result.scalar_one_or_none()
                existing_record.progress_percent = 5
                await session.commit()
                return 

            mcq = cs_classes.ProgressData(
                uuid=uuid,
                progress_percent=5
            )
            session.add(mcq)
            await session.flush()
            await session.refresh(mcq)
            logger.info(f"✅ Created progress record for UUID: {uuid}")

    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error creating progress record for UUID {uuid}: {e}")
        raise
    finally:
        await session.close()

async def delete_progress(uuid):
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                text("DELETE FROM cs_qbank.progress_table WHERE uuid = :uuid"),
                {"uuid": uuid}
            )
            if result.rowcount > 0:
                logger.info(f"🗑️ Deleted progress record for UUID: {uuid}")
            else:
                logger.warning(f"⚠️ No progress record found for UUID: {uuid}")
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error deleting progress record for UUID {uuid}: {e}")
        raise
    finally:
        await session.close()

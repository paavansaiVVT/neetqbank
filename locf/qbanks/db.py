from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os, logging, asyncio,constants, json
import re
from sqlalchemy.exc import IntegrityError

#from constants import difficulty_level, cognitive_levels, question_types
from locf.qbanks import classes, core
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL_8")

engine = create_async_engine(DATABASE_URL,echo=False,pool_size=100,max_overflow=50,pool_recycle=1800, pool_pre_ping=True, connect_args={"connect_timeout": 600})
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
                    topic_id, subject_id, chapter_id = await core.question_banks.topic_check(question=question,old_topic=topic_name,topic_name_list=topic_list)
                    return topic_id, subject_id, chapter_id
                else:
                    logger.error(f"❌ Topic name '{topic_name}' not found after fallback.")
                    return None, None, None

        except OperationalError as e:
            logger.warning(f"OperationalError on attempt {attempt + 1} for topic '{topic_name}': {e}")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Unexpected error fetching topic '{topic_name}': {e}")
            return None, None, None
        finally:
            await session.close()

    return None, None, None

def get_session():
    return AsyncSessionLocal()

@retry_on_failure
async def add_mcq_data(request: classes.QuestionRequest, all_data, table_name):
    session = get_session()
    try:
        mcq_objects = []
        for entry in all_data:
            try:
                if entry.get("correct_option") == "": crt_opt = entry.get("correct_answer", "")
                else: crt_opt = entry.get("correct_option")
                mcq = table_name(
                    user_id=request.user_id,
                    uuid=request.uuid,
                    stream= entry['stream'],
                    question=entry['question'],
                    correct_opt=crt_opt,
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
                    p_id=entry['p_id'],
                    co_id= entry['co_id'],
                    course_id= entry['course_id'],
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
        result = ["success", f"Added {len(mcq_objects)} questions to the database."]
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
        old_mcq = classes.oldMCQ(
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

async def update_mcq_data(request: classes.ImprovedQuestionReq, old_ques_data, ques_data):
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
        existing_mcq = await session.get(classes.MCQData, request.question_id)

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
        stmt = select(classes.ProgressData).where(classes.ProgressData.uuid == uuid)
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
                stmt = select(classes.ProgressData).where(classes.ProgressData.uuid == uuid)
                result = await session.execute(stmt)
                existing_record = result.scalar_one_or_none()
                existing_record.progress_percent = 5
                await session.commit()
                return 

            mcq = classes.ProgressData(
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


@retry_on_failure
async def get_chapters(chapter_name:str, retry_id=0, question=None, chapter_list=None, subject_id=None, program_id=None):
    """Get or create an chapter entry in the database."""
    session = get_session()
    try:
        async with session.begin():
            # Check for existing Chapter entry
            result = await session.execute(select(classes.Chapters)
                .where(
                    classes.Chapters.c_name == chapter_name.strip( ),
                    classes.Chapters.s_id == subject_id,
                    classes.Chapters.p_id == program_id
                )
            )
            # Handle multiple rows by taking the first one
            existing = result.scalars().first()
            if existing:
                cha_id = existing.id
                sub_id = existing.s_id
                await session.commit()
                logger.info(f"✅ Found chapter '{chapter_name}' with ID {cha_id}")
                return sub_id, cha_id
            if retry_id == 0:
                logger.info(f"Chapter '{chapter_name}' not found in database. Trying question bank fallback.")
                sub_id, cha_id = await core.question_banks.chapter_check(question=question,old_chapter=chapter_name,chapter_name_list=chapter_list,subject_id=subject_id)
                return sub_id, cha_id
            else:
                logger.error(f"❌ Chapter name '{chapter_name}' not found after fallback.")
                return None, None
            
    except OperationalError as e:
        logger.error(f"Database operation failed in get_chapter_id: {e}")
        await session.rollback()
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error occurred in get_chapter_id: {e}")
        await session.rollback()
        return None, None
    finally:
        await session.close()
        
@retry_on_failure
async def get_topic(program_id: int, subject_id: int, chapter_id: int, topic_name: str):
    """Get or create an topic entry in the database."""
    session = get_session()
    try:
        async with session.begin():
            # Check for existing subject entry
            result = await session.execute(select(classes.Topics)
                .where(
                    classes.Topics.t_name ==topic_name.strip( ),
                    classes.Topics.c_id == chapter_id,
                    classes.Topics.s_id == subject_id,
                    classes.Topics.p_id == program_id
                )
            )
            # Handle multiple rows by taking the first one
            existing = result.scalars().first()
            if existing:
                p_id = existing.p_id
                s_id = existing.s_id
                c_id = existing.c_id
                t_id = existing.id
                await session.commit()
                logger.info(f"✅ Found topic '{topic_name}' with ID {t_id}")
                return p_id, s_id, c_id, t_id
            else:
                logger.warning(f"⚠️ Topic '{topic_name}' not found in database")
                await session.commit()
                return None, None, None, None
            # else:
            #     new_entry = classes.Topics(
            #         p_id= program_id,
            #         c_id= chapter_id,
            #         s_id= subject_id,
            #         t_name= topic_name.strip( ),
            #         status= 1,
            #         is_deleted = 0
            #     )
            #     session.add(new_entry)
            #     await session.flush()
            #     p_id = new_entry.p_id
            #     s_id = new_entry.s_id
            #     c_id = new_entry.c_id
            #     t_id = new_entry.id

    except OperationalError as e:
        logger.error(f"Database operation failed in get_topic_id: {e}")
        await session.rollback()
        return None, None, None, None
    except Exception as e:
        logger.error(f"Unexpected error occurred in get_topic_id: {e}")
        await session.rollback()
        return None, None, None, None
    finally:
        await session.close()
        
@retry_on_failure
async def get_course_units(chapter_id:int):
    """Get or create an course_units entry in the database."""
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(select(classes.course_units)
                .where(
                    classes.course_units.title == chapter_id,
                )
            )
            existing = result.scalars().first()
            if existing:
                course_units_id = existing.id
            else:
                     course_units_id = 0
            await session.commit()
            return course_units_id
    except OperationalError as e:
        logger.error(f"Database operation failed in course_units_id: {e}")
        await session.rollback()
        return 0
    except Exception as e:
        logger.error(f"Unexpected error occurred in course_units_id: {e}")
        await session.rollback()
        return 0
    finally:
        await session.close()

@retry_on_failure
async def get_course_outcomes_list(course_id: int):
    """Get list of course outcomes in formatted structure."""
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                select(classes.course_outcomes)
                .where(classes.course_outcomes.course_id == course_id)
            )
            outcomes = result.scalars().all()

            formatted_outcomes = [
                {
                    "name": co.co_number,
                    "description": co.content
                }
                for co in outcomes
            ]

            await session.commit()
            return formatted_outcomes

    except OperationalError as e:
        logger.error(f"Database operation failed in get_course_outcomes_list: {e}")
        await session.rollback()
    except Exception as e:
        logger.error(f"Unexpected error in get_course_outcomes_list: {e}")
        await session.rollback()
    finally:
        await session.close()

# Optional: normalize inputs like "co-4", "Co 4" -> "CO4"
_CO_RE = re.compile(r"co[\s\-\:_]*([0-9]+)$", re.IGNORECASE)
def _normalize_co(co: str) -> str:
    m = _CO_RE.search(co.strip())
    return f"CO{int(m.group(1))}" if m else co.strip().upper()
       
@retry_on_failure
async def get_course_outcomes(course_outcome: str, course_id: int, chapter_id: int | None = None) -> int | None:
    session = get_session()
    code = _normalize_co(course_outcome)
    try:
        async with session.begin():
            conds = [
                classes.course_outcomes.co_number == code,
                classes.course_outcomes.course_id == course_id,
            ]
            conds.append(
                classes.course_outcomes.chapter_id.is_(None)
                if chapter_id is None else
                classes.course_outcomes.chapter_id == chapter_id
            )
            result = await session.execute(select(classes.course_outcomes.id).where(*conds))
            existing = result.scalars().first()
            if existing:
                # existing is already the ID (int), no need for .id
                await session.commit()
                return existing
            else:
                await session.commit()
                return None
    except OperationalError as e:
        logger.error(f"Database operation failed in course_outcomes_id: {e}")
        await session.rollback()
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred in course_outcomes_id: {e}")
        await session.rollback()
        return None
    finally:
        await session.close()
        
@retry_on_failure
async def get_course_outcomes2(chapter_id:int, course_id:int):
    """Get or create an course_units entry in the database."""
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(select(classes.course_outcomes)
                .where(
                    classes.course_outcomes.chapter_id == chapter_id, classes.course_outcomes.course_id == course_id
                )
            )
            existing = result.scalars().first()
            if existing:
                course_outcomes_id = existing.id
                await session.commit()
                return course_outcomes_id
            else:
                await session.commit()
                return None
    except OperationalError as e:
        logger.error(f"Database operation failed in course_outcomes_id: {e}")
        await session.rollback()
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred in course_outcomes_id: {e}")
        await session.rollback()
        return None
    finally:
        await session.close()
        
@retry_on_failure
async def get_courses(subject_id:int, program_id:int):
    """Get or create an courses entry in the database."""
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(select(classes.courses)
                .where(
                    classes.courses.course_name_id == subject_id, classes.courses.program_id == program_id
                )
            )
            existing = result.scalars().first()
            if existing:
                course_id = existing.id
                sem_id = existing.semester_id
                await session.commit()
                return course_id, sem_id
            else:
                await session.commit()
                return None, None
    except OperationalError as e:
        logger.error(f"Database operation failed in course_id: {e}")
        await session.rollback()
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error occurred in course_id: {e}")
        await session.rollback()
        return None, None
    finally:
        await session.close()

@retry_on_failure
async def get_program_content(program_id: int, content: int, clean_content: dict = None):
    """Get or create (or update) a program content entry in the database."""
    session = get_session()
    try:
        async with session.begin():
            # Check if entry already exists
            result = await session.execute(
                select(classes.program_content).where(
                    classes.program_content.program_id == program_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update the existing entry
                existing.content = content
                existing.clean_content = clean_content.get("combined_output")
                existing.raw_json = json.dumps(clean_content)
                await session.flush()
                p_content_id = existing.id
            else:
                # Create a new entry
                new_entry = classes.program_content(
                    program_id=program_id,
                    content=content,
                    clean_content=clean_content.get("combined_output"),
                    raw_json=json.dumps(clean_content)
                )
                session.add(new_entry)
                await session.flush()
                p_content_id = new_entry.id

            await session.commit()
            return p_content_id

    except OperationalError as e:
        logger.error(f"Database operation failed in get_program_content: {e}")
        await session.rollback()
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred in get_program_content: {e}")
        await session.rollback()
        return None
    finally:
        await session.close()


@retry_on_failure
async def get_chapter_and_content(subject_id: int):
    """Get chapter names and related content for a given subject ID."""
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                select(
                    classes.Chapters.c_name,
                    classes.course_units.content
                ).join(
                    classes.course_units,
                    classes.Chapters.id == classes.course_units.title
                ).where(
                    classes.Chapters.s_id == subject_id
                )
            )

            data = [{"chapter_name": row.c_name, "content": row.content} for row in result.fetchall()]
            return data if data else None

    except OperationalError as e:
        logger.error(f"Database operation failed in get_chapter_and_content: {e}")
        await session.rollback()
    except Exception as e:
        logger.error(f"Unexpected error occurred in get_chapter_and_content: {e}")
        await session.rollback()
    finally:
        await session.close()

async def get_chapter_and_topic(program_id: int, subject_id: int):
    """Get chapter names and related topics for a given subject ID."""
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                select(
                    classes.Chapters.c_name,
                    classes.Topics.t_name
                ).join(
                    classes.Topics,
                    classes.Chapters.id == classes.Topics.c_id
                ).where(
                    classes.Chapters.s_id == subject_id,
                    classes.Chapters.p_id == program_id,
                    classes.Topics.p_id == program_id
                )
            )

            # Group topics under their chapter names
            chapter_topic_map = {}
            for row in result.fetchall():
                chapter_name = row.c_name
                topic_name = row.t_name

                if chapter_name not in chapter_topic_map:
                    chapter_topic_map[chapter_name] = []

                chapter_topic_map[chapter_name].append(topic_name)

            # Convert to list of dicts
            grouped_data = [
                {"chapter_name": chapter, "topics": topics}
                for chapter, topics in chapter_topic_map.items()
            ]

            return grouped_data if grouped_data else None

    except OperationalError as e:
        logger.error(f"Database operation failed in get_chapter_and_topic: {e}")
        await session.rollback()
    except Exception as e:
        logger.error(f"Unexpected error occurred in get_chapter_and_topic: {e}")
        await session.rollback()
    finally:
        await session.close()

@retry_on_failure
async def token_update_fc(request_data:classes.QuestionRequest, token_data:dict, model_name:str, bot_name:str = "question_bank"):
    session= get_session()
    try:
        token_data= classes.UserTokenUsage(
            user_id=request_data.user_id,
            session_uuid=request_data.uuid,
            bot_name=bot_name,
            model_name=model_name,
            input=token_data.get("input_tokens") or token_data.get("total_input_tokens", 0),
            output=token_data.get("output_tokens") or token_data.get("total_output_tokens", 0),
            total=token_data.get("total_tokens", 0)
        )
        session.add(token_data)
        await session.commit()
        logger.info(f"✅ Token usage updated for User ID: {request_data.user_id}.")
    except Exception as e:
        logger.error(f"Error updating token usage: {e}")
        return None
    finally:
        await session.close()
        
async def user_request_log(request_data: classes.QuestionRequest):
    session = get_session()
    try:
        user_request = classes.QbankRequest(
            user_id=request_data.user_id,
            uuid=request_data.uuid,
            program_name=request_data.program_name,
            subject_name=request_data.subject_name,
            chapter_name=request_data.chapter_name,
            topic_name=request_data.topic_name,
            question_type=request_data.question_type,
            cognitive_level=request_data.cognitive_level,
            difficulty=request_data.difficulty,
            number_of_questions=request_data.number_of_questions,
            model_id=request_data.model,
        )
        session.add(user_request)
        await session.commit()
        logger.info(f"✅ User request logged for User ID: {request_data.user_id}.")
    except Exception as e:
        logger.error(f"Error logging user request: {e}")
        return None
    finally:
        await session.close()
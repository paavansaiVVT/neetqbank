from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from typing import Iterable, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os, logging, asyncio,constants, json, re
from locf.c_paper_correction import classes
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL_8")
engine = create_async_engine(DATABASE_URL,pool_size=100,max_overflow=50,pool_recycle=1800, pool_pre_ping=True, connect_args={"connect_timeout": 600})
AsyncSessionLocal = sessionmaker(bind=engine,class_=AsyncSession,expire_on_commit=False)

Base = declarative_base()
retry_on_failure = retry(stop=stop_after_attempt(3),wait=wait_fixed(5),before_sleep=before_sleep_log(logger, logging.WARNING))

def get_session():
    return AsyncSessionLocal()

@retry_on_failure
async def fetch_question_paper_data(request: classes.AnswerSheetRequest):
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                select(classes.DbQuestionData).where(
                    classes.DbQuestionData.id == request.question_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing.instruction_set, existing.md_list, existing.subject_name, existing.class_name
            else:
                return None
    except OperationalError as e:
        logger.error(f"Database operation (fetch_question_paper_data)failed: {str(e)}")
        raise
    finally:
        await session.close()

from dataclasses import asdict, is_dataclass

def to_jsonable(obj):
    # pydantic v2
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return obj.model_dump()
    # pydantic v1
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    # dataclass
    if is_dataclass(obj):
        return asdict(obj)
    # already a mapping/list/primitive
    if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
        return obj
    # last resort: string repr (or return None)
    return str(obj)

def dumps_safe(obj) -> str | None:
    try:
        return json.dumps(to_jsonable(obj), ensure_ascii=False, default=str)
    except Exception:
        return None
    
def _iter_dict_items(obj: Any) -> Iterable[Dict[str, Any]]:
    """Yield dict items from arbitrarily nested lists/tuples of dicts. Accepts: - dict -> yields it - list/tuple -> recursively yield dicts from children - anything else -> ignored """
    if isinstance(obj, dict):
        yield obj
    elif isinstance(obj, (list, tuple)):
        for child in obj:
            yield from _iter_dict_items(child)

@retry_on_failure
async def save_answer_sheet_correction(request: classes.AnswerSheetRequest, correction_json, student_id: int, exam_id: int):
    session = get_session()
    try:
        dict_items = list(_iter_dict_items(correction_json))
        if not dict_items:
            logger.warning("save_answer_sheet_correction: No valid dict items found in correction_json")
            return

        async with session.begin():
            for item in dict_items:
                q_num = int(item.get("question_number"))
                part_label = item.get("part_label")  # NEW: Get part_label for sub-questions
                
                # Build WHERE clause for uniqueness
                # For single questions: (user_id, qp_id, student_id, question_number, part_label IS NULL)
                # For sub-questions: (user_id, qp_id, student_id, question_number, part_label = '(a)')
                if part_label:
                    result = await session.execute(
                        select(classes.DbAnswerSheetCorrection).where(
                            classes.DbAnswerSheetCorrection.user_id == request.user_id,
                            classes.DbAnswerSheetCorrection.qp_id == request.question_id,
                            classes.DbAnswerSheetCorrection.student_id == student_id,
                            classes.DbAnswerSheetCorrection.question_number == q_num,
                            classes.DbAnswerSheetCorrection.part_label == part_label
                        )
                    )
                else:
                    result = await session.execute(
                        select(classes.DbAnswerSheetCorrection).where(
                            classes.DbAnswerSheetCorrection.user_id == request.user_id,
                            classes.DbAnswerSheetCorrection.qp_id == request.question_id,
                            classes.DbAnswerSheetCorrection.student_id == student_id,
                            classes.DbAnswerSheetCorrection.question_number == q_num,
                            classes.DbAnswerSheetCorrection.part_label.is_(None)
                        )
                    )
                
                #print(f"Confidence level: {item.get('confidence_level')}")
                existing = result.scalar_one_or_none()

                if existing:
                    existing.uuid = request.uuid
                    existing.q_id = item.get("ques_id") or None
                    existing.exam_id = exam_id
                    existing.section = item.get("section") or None
                    existing.part_label = part_label  # NEW: Store part_label
                    existing.has_sub_questions = item.get("has_sub_questions")  # NEW: Store has_sub_questions
                    existing.question_text = item.get("question_text") or "Not provided"
                    existing.student_answer_text = item.get("student_answer_text") or "Not provided"
                    existing.actual_answer = item.get("expected_answer") or "Not provided"
                    existing.feedback = item.get("feedback") or "Not provided"
                    existing.maximum_marks = float(item.get("maximum_marks") or 0.0)
                    existing.marks_awarded = float(item.get("marks_awarded") or 0.0)
                    existing.model_used = "gemini-2.0-flash"
                    existing.cdl_level = classes.cdl_level[request.cdl_level.lower()]
                    existing.confidence_level = float(item.get("confident_level") or 0.0)
                    #logger.info(f"Updated correction for Q{existing.question_number}, Roll {existing.student_id}")
                else:
                    new_entry = classes.DbAnswerSheetCorrection(
                        uuid = request.uuid,
                        user_id = request.user_id,
                        qp_id=request.question_id,
                        q_id=item.get("ques_id") or None,
                        student_id=student_id,
                        exam_id=exam_id,
                        section=item.get("section") or None,
                        question_number=q_num,
                        part_label=part_label,  # NEW: Store part_label for sub-questions
                        has_sub_questions=item.get("has_sub_questions"),  # NEW: Store has_sub_questions
                        question_text=item.get("question_text") or "Not provided",
                        student_answer_text=item.get("student_answer_text") or "Not provided",
                        actual_answer=item.get("expected_answer") or "Not provided",
                        feedback=item.get("feedback") or "Not provided",
                        maximum_marks=float(item.get("maximum_marks") or 0.0),
                        marks_awarded=float(item.get("marks_awarded") or 0.0),
                        model_used="gemini-2.0-flash",
                        cdl_level=classes.cdl_level[request.cdl_level.lower()],
                        confidence_level = float(item.get("confident_level") or 0.0)
                    )
                    session.add(new_entry)
                    #logger.info(f"Inserted correction for Q{new_entry.question_number}, Roll {new_entry.student_id}")

        logger.info(f"Processed {len(dict_items)} records for q_id {request.question_id}")
    except OperationalError as e:
        logger.error(f"Database operation (save_answer_sheet_correction) failed: {str(e)}")
        raise
    finally:
        await session.close()

@retry_on_failure
async def fetch_question_paper_data2(request: classes.AnswerSheetRequest):
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                select(classes.DbAnswerSheetCorrection).where(
                    classes.DbAnswerSheetCorrection.qp_id == request.question_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                answer_result = {
                    "section": existing.section,
                    "question_number": existing.question_number,
                    "question_text": existing.question_text,
                    "student_answer_text": existing.student_answer_text,
                    "actual_answer": existing.actual_answer,
                    "feedback": existing.feedback,
                    "maximum_marks": existing.maximum_marks,
                    "marks_awarded": existing.marks_awarded,
                    "model_used": existing.model_used,
                    "cdl_level": existing.cdl_level
                }
                return existing.question_paper_json, existing.contain_image_list, existing.instruction_set, existing.md_list
            else:
                return None
    except OperationalError as e:
        logger.error(f"Database operation (fetch_question_paper_data)failed: {str(e)}")
        raise
    finally:
        await session.close()
        
        
async def update_student_details(student_details: dict):
    session = get_session()
    try:
        result = await session.execute(
                select(classes.DbStudentDetails).where(
                    classes.DbStudentDetails.role_number == student_details['rollno']
                )
            )
        existing = result.scalar_one_or_none()
        if existing:
            existing.student_name = student_details.get("name") or None
            existing.section = student_details.get("section") or None
            existing.class_name = student_details.get("class") or None
            await session.commit()
            logger.info("Student details updated successfully.")
            return existing.id
        else:
            new_entry = classes.DbStudentDetails(
            student_name = student_details.get("name") or None,
            role_number = student_details.get("rollno") or None,
            section = student_details.get("section") or None,
            class_name = student_details.get("class") or None,
            )
            session.add(new_entry)
            await session.commit()
            logger.info("New student details added successfully.")
            return new_entry.id
    except Exception as e:
        logger.error(f"Database operation (update_student_details) failed: {str(e)}")
        
async def update_exam_details(request: classes.AnswerSheetRequest, student_id: int, exam_details: dict, missed_ans: list, subject_name: str, analysis_data: dict, max_marks: float):
    session = get_session()
    try:
        req_json_str = dumps_safe(request)
        result = await session.execute(
                select(classes.DbExamDetails).where(
                    classes.DbExamDetails.user_id == request.user_id,
                    classes.DbExamDetails.student_id == student_id,
                    classes.DbExamDetails.qp_id == request.question_id,
                    classes.DbExamDetails.cdl_id == classes.cdl_level[request.cdl_level.lower()]
                    
                )
            )
        existing = result.scalar_one_or_none()
        if existing:
            existing.uuid = request.uuid
            existing.exam_date   = exam_details.get("date") or None
            existing.pdf_url = request.pdf_url
            existing.subject     = subject_name
            existing.phase       = exam_details.get("phase") or None
            existing.request_json = req_json_str
            existing.missed_answers = missed_ans
            existing.gen_response = exam_details
            existing.max_marks = max_marks
            existing.grader_id = 2
            existing.awarded_marks = analysis_data["total_awarded_marks"]
            existing.confidence_level = analysis_data["average_confidence_percentage"]
            existing.result_analysis = analysis_data
            await session.commit()
            logger.info("Exam details updated successfully.")
            return existing.id
        else:
            new_entry = classes.DbExamDetails(
                uuid = request.uuid,
                user_id = request.user_id,
                student_id = student_id,
                qp_id = request.question_id,
                cdl_id = classes.cdl_level[request.cdl_level.lower()],
                exam_date    = exam_details.get("date") or None,
                pdf_url = request.pdf_url,
                subject      = subject_name,
                phase        = exam_details.get("phase") or None,
                request_json = req_json_str,
                missed_answers = missed_ans,
                gen_response = exam_details,
                max_marks = max_marks,
                grader_id = 2,
                awarded_marks = analysis_data["total_awarded_marks"],
                confidence_level = analysis_data["average_confidence_percentage"],
                result_analysis = analysis_data                
            )
            session.add(new_entry)
            await session.commit()
            logger.info("New exam details added successfully.")
            return new_entry.id
    except Exception as e:
        logger.error(f"Database operation (update_exam_details) failed: {str(e)}")

async def fetch_q_id(request: classes.AnswerSheetRequest):
    session = get_session()
    try:        
        async with session.begin():
            result = await session.execute(
                select(classes.QuestionData).where(
                    classes.QuestionData.qp_id == request.question_id
                )
            )
            rows = result.scalars().all()  # fetch all rows
            
            if rows:
                data = [
                    {
                        "question_number": row.question_number,
                        "ques_id": row.id
                    }
                    for row in rows
                ]
                return data
            else:
                logger.error(f"No questions found for Question Paper ID {request.question_id}")
                return None
    except OperationalError as e:
        logger.error(f"Database operation (fetch_q_id) failed: {str(e)}")
        raise
    finally:
        await session.close()
    
async def fetch_question_json(qp_id: int):
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                select(classes.QuestionData)
                .where(classes.QuestionData.qp_id == qp_id)
                .order_by(classes.QuestionData.question_number, classes.QuestionData.part_label)
            )
            rows = result.scalars().all()

        if not rows:
            logger.warning(f"No questions found for Question Paper ID {qp_id}")
            return []

        data = [
            {
                "ques_id": row.id,
                "question_number": row.question_number,
                "part_label": row.part_label,  # NEW: Sub-question part label
                "has_sub_questions": row.has_sub_questions,  # NEW: "True"/"False"
                "question_type": classes.question_type_dict.get(row.question_type),
                "question_text": row.question,
                "image_description": row.image_description if row.is_image == 1 else None,
                # "image_url": row.image_url if row.is_image == 1 else None,
                "image_part_of": row.image_part_of if row.is_image == 1 else None,
                "options": [row.option_a, row.option_b, row.option_c, row.option_d] if row.question_type == 1 or row.question_type == 5 else None,
                "correct_opt": classes.crt_opt.get(int(row.correct_opt), None) if row.correct_opt and row.correct_opt.isdigit() else None,
                "max_marks": row.max_marks,
                # "explanation": row.explanation if row.question_type == 1 else None,
                "expected_answer": row.expected_answer,
                "marking_scheme": row.marking_scheme,
                "key_points": row.key_points,
                # NEW: Context fields for better grading
                "cognitive_level": classes.cognitive_level_dict.get(row.cognitive_level),  # 1-6 (Bloom's Taxonomy)
                "difficulty": classes.difficulty_level_dict.get(row.difficulty),  # 1-3 (Easy/Medium/Hard)
                "estimated_time": row.estimated_time,  # Float (minutes)
            }
            for row in rows
        ]
        return data

    except OperationalError as e:
        logger.error(f"Database operation (fetch_question_json) failed: {e}")
        raise
    finally:
        await session.close()
    
@retry_on_failure
async def token_update_fc(request_data:classes.AnswerSheetRequest, token_data:dict, model_name:str, bot_name:str = "OCR_Answer_Sheet_Grader_Agent"):
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
        logger.info(f"✅ Token usage updated for Student ID: {request_data.user_id}.")
    except Exception as e:
        logger.error(f"Error updating token usage: {e}")
        return None
    finally:
        await session.close()
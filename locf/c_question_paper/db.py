from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os, logging, asyncio,constants, json
from locf.c_question_paper import classes
from typing import Iterable, Dict, Any, Tuple
from datetime import date, datetime
from enum import Enum
from dataclasses import is_dataclass, asdict
from sqlalchemy import JSON as SA_JSON
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

# --- helpers ---

try:
    # Pydantic v2
    from pydantic import BaseModel
    def _dump_pydantic(model: "BaseModel"):
        return model.model_dump(mode="json", by_alias=True)
except ImportError:
    # Pydantic v1
    from pydantic import BaseModel
    def _dump_pydantic(model: "BaseModel"):
        return model.dict(by_alias=True)

def to_jsonable(obj):
    """Recursively convert to JSON-serializable primitives/lists/dicts."""
    if isinstance(obj, BaseModel):
        return to_jsonable(_dump_pydantic(obj))
    if is_dataclass(obj):
        return to_jsonable(asdict(obj))
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x) for x in obj]
    return obj  # primitives pass through

def _serialize_for_column(value, column):
    """
    If the SQLAlchemy column is JSON, store Python dict/list directly.
    Otherwise (TEXT/VARCHAR/etc.), store as JSON string when value is dict/list.
    """
    if isinstance(column.type, SA_JSON):
        return to_jsonable(value)
    # Non-JSON column types
    v = to_jsonable(value)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)  # <- stringify for TEXT columns
    return v

def add_image_details(final_data):
    for i in final_data:
        s3_url_list = []
        part_of_list = []   
        if i['images']:
            for j in i['images']:
                s3_url_list.append(j['s3_url'])
                part_of_list.append(j['part_of'])
        i['s3_url_list'] = s3_url_list
        i['part_of_list'] = part_of_list
    return final_data
    
@retry_on_failure
async def add_question_paper_data(
    request: classes.QuestionPaperRequest,
    question_paper,
    image_urls: list,
    gen_response,
    md_results,
    miss_ques
):
    session = get_session()
    try:
        # Normalize inputs
        if isinstance(question_paper, (dict, list, BaseModel)):
            qp_payload = to_jsonable(question_paper)
        elif isinstance(question_paper, str):
            try:
                qp_payload = to_jsonable(json.loads(question_paper))
            except Exception:
                qp_payload = question_paper  # plain string as-is
        else:
            qp_payload = to_jsonable(question_paper)

        urls_payload = to_jsonable(image_urls or [])
        md_payload   = to_jsonable(md_results)

        # NEW: normalize the two fields that were raw
        instr_payload = to_jsonable(gen_response)
        miss_payload  = to_jsonable(miss_ques or [])

        # Column refs to decide per-field serialization
        tbl = classes.DbQuestionData.__table__.c
        qp_value    = _serialize_for_column(qp_payload,    tbl.question_paper_json)
        urls_value  = _serialize_for_column(urls_payload,  tbl.contain_image_list)
        md_value    = _serialize_for_column(md_payload,    tbl.md_list)
        instr_value = _serialize_for_column(instr_payload, tbl.instruction_set)     # <— FIX
        miss_value  = _serialize_for_column(miss_payload,  tbl.missed_questions)    # <— FIX

        async with session.begin():
            result = await session.execute(
                select(classes.DbQuestionData).where(
                    classes.DbQuestionData.user_id      == request.user_id,
                    classes.DbQuestionData.class_name   == request.class_name,
                    classes.DbQuestionData.subject_name == request.subject,
                    classes.DbQuestionData.exam_name    == request.exam_title,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.uuid                = request.uuid
                existing.grader_id           = 2
                existing.pdf_url             = request.pdf_url
                existing.class_name          = request.class_name
                existing.subject_name        = request.subject
                existing.grade_level         = request.grade_level
                existing.exam_name           = request.exam_title
                existing.exam_date           = request.exam_date
                existing.duration_minutes    = request.duration_minutes
                existing.description         = request.description
                existing.question_paper_json = qp_value
                existing.contain_image_list  = urls_value
                existing.instruction_set     = instr_value
                existing.md_list             = md_value
                existing.missed_questions    = miss_value
                # optional: rely on the `begin()` context to commit
                await session.commit()
                return existing.id
            else:
                new_entry = classes.DbQuestionData(
                    uuid                = request.uuid,
                    user_id             = request.user_id,
                    grader_id           = 2,
                    question_paper_name = request.question_paper_name,
                    pdf_url             = request.pdf_url,
                    class_name          = request.class_name,
                    subject_name        = request.subject,
                    grade_level         = request.grade_level,
                    exam_name           = request.exam_title,
                    exam_date           = request.exam_date,
                    duration_minutes    = request.duration_minutes,
                    description         = request.description,
                    question_paper_json = qp_value,
                    contain_image_list  = urls_value,
                    instruction_set     = instr_value,
                    md_list             = md_value,
                    missed_questions    = miss_value,
                )
                session.add(new_entry)
                # optional: rely on the `begin()` context to commit
                await session.commit()
                return new_entry.id

    except OperationalError as e:
        logger.error(f"Database operation failed in add_question_paper_data: {e}")
        await session.rollback()
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred in add_question_paper_data: {e}")
        await session.rollback()
        return None
    finally:
        await session.close()



async def add_ques_answer_data(
    request: classes.QuestionPaperRequest, gen_result, ques_id
) -> None:
    session = get_session()
    
    def _iter_dict_items(obj: Any) -> Iterable[Dict[str, Any]]:
        """
        Yield dict items from arbitrarily nested lists/tuples of dicts.
        Accepts:
        - dict -> yields it
        - list/tuple -> recursively yield dicts from children
        - anything else -> ignored
        """
        if isinstance(obj, dict):
            yield obj
        elif isinstance(obj, (list, tuple)):
            for child in obj:
                yield from _iter_dict_items(child)

    def none_if_blank(v, default=None):
        # keep 0/False; only empty strings -> default
        if v is None:
            return default
        if isinstance(v, str):
            s = v.strip()
            return s if s != "" else default
        return v

    def to_int_safe(v, default=0):
        try:
            if v is None or (isinstance(v, str) and v.strip() == ""):
                return default
            if isinstance(v, (int, float)):
                return int(v)
            return int(float(str(v).strip()))
        except Exception:
            return default

    try:
        dict_items = list(_iter_dict_items(gen_result))
        if not dict_items:
            logger.warning("add_ques_answer_data: No valid dict items found in gen_result")
            return

        async with session.begin():  # auto-commit/rollback
            for item in dict_items:
                qnum = item.get("question_number")
                if qnum is None or (isinstance(qnum, str) and qnum.strip() == ""):
                    logger.warning("Skipping entry without question_number: %s", item)
                    continue  # or raise, depending on your policy

                # Get part_label for proper uniqueness check
                part_label = item.get("part_label")
                has_sub = item.get("has_sub_questions", False)
                alternative_ques = item.get("alternative_ques", False)
                is_or_question = item.get("is_or_question", False)
                or_option = item.get("or_option")
                
                # Build WHERE clause based on question type
                # This ensures proper uniqueness for different question types:
                # - Normal questions: question_number + part_label=NULL
                # - Sub-questions: question_number + part_label
                # - OR questions: question_number + or_option + part_label=NULL
                
                if is_or_question and or_option:
                    # OR question - check question_number, or_option, and part_label IS NULL
                    result = await session.execute(
                        select(classes.QuestionData).where(
                            classes.QuestionData.user_id == request.user_id,
                            classes.QuestionData.qp_id == ques_id,
                            classes.QuestionData.question_number == qnum,
                            classes.QuestionData.or_option == or_option,
                            classes.QuestionData.part_label.is_(None)
                        )
                    )
                elif part_label is None:
                    # Normal single question - check question_number and part_label IS NULL
                    result = await session.execute(
                        select(classes.QuestionData).where(
                            classes.QuestionData.user_id == request.user_id,
                            classes.QuestionData.qp_id == ques_id,
                            classes.QuestionData.question_number == qnum,
                            classes.QuestionData.part_label.is_(None),
                            classes.QuestionData.or_option.is_(None)
                        )
                    )
                else:
                    # Sub-question part - check question_number and part_label match
                    result = await session.execute(
                        select(classes.QuestionData).where(
                            classes.QuestionData.user_id == request.user_id,
                            classes.QuestionData.qp_id == ques_id,
                            classes.QuestionData.question_number == qnum,
                            classes.QuestionData.part_label == part_label
                        )
                    )
                existing = result.scalar_one_or_none()

                # Convert cognitive_level and difficulty from string to integer
                cognitive_level_str = item.get("cognitive_level")
                cognitive_level_int = classes.cognitive_level_dict.get(cognitive_level_str) if cognitive_level_str else None
                
                difficulty_str = item.get("difficulty")
                difficulty_int = classes.difficulty_dict.get(difficulty_str) if difficulty_str else None
                
                # estimated_time should be float
                estimated_time_val = item.get("estimated_time")
                if estimated_time_val is not None:
                    try:
                        estimated_time_val = float(estimated_time_val)
                    except (ValueError, TypeError):
                        estimated_time_val = None
                
                # ✅ CRITICAL: Handle options array for MCQ/A&R questions
                options = item.get("options")
                option_a = option_b = option_c = option_d = None
                correct_opt = None
                
                if options and isinstance(options, list):
                    # Split options array into individual option columns
                    if len(options) > 0:
                        option_a = none_if_blank(options[0])
                    if len(options) > 1:
                        option_b = none_if_blank(options[1])
                    if len(options) > 2:
                        option_c = none_if_blank(options[2])
                    if len(options) > 3:
                             option_d = none_if_blank(options[3])
                    
                    # ✅ CRITICAL: Calculate correct_opt based on expected_answer index
                    expected_answer = item.get("expected_answer")
                    if expected_answer and isinstance(expected_answer, str):
                        expected_answer_clean = expected_answer.strip()
                        options_clean = [opt.strip() for opt in options if isinstance(opt, str)]
                        
                        try:
                            # Find the index of expected_answer in options (0-based)
                            correct_index = options_clean.index(expected_answer_clean)
                            # Convert to 1-based index for correct_opt
                            correct_opt = str(correct_index + 1)
                        except ValueError:
                            # expected_answer not found in options - this should have been caught by validation
                            correct_opt = None
                
                # Build a payload without clobbering 0/False
                # Note: question_number is stored as INTEGER (e.g., 14)
                # part_label is stored separately (e.g., "(a)", "(b)", or None)
                # Uniqueness is ensured by combination of (user_id, qp_id, question_number, part_label)
                # NO DEFAULTS - All required fields must be present (validation done in core.py)
                question_type = item.get("question_type")
                payload = {
                    "uuid": request.uuid,
                    "user_id": request.user_id,
                    "question_type":classes.question_type_dict.get(question_type),# item.get("question_type"),
                    "max_marks": to_int_safe(item.get("max_marks"), 0),  # Use 0 if not convertible
                    "is_image": 1 if item.get("s3_url_list") else 0,  # 1 if image exists, 0 if not
                    "image_description": none_if_blank(item.get("image_description")),
                    "question": item.get("question"),  # REQUIRED - must exist
                    "correct_opt": correct_opt,  # ✅ CRITICAL: Use calculated correct_opt from expected_answer index
                    "option_a": option_a,  # ✅ CRITICAL: Use processed options from array
                    "option_b": option_b,  # ✅ CRITICAL: Use processed options from array
                    "option_c": option_c,  # ✅ CRITICAL: Use processed options from array
                    "option_d": option_d,  # ✅ CRITICAL: Use processed options from array
                    "explanation": item.get("explanation"),  # REQUIRED - validated in core.py
                    "expected_answer": item.get("expected_answer"),  # REQUIRED - validated in core.py
                    "marking_scheme": item.get("marking_scheme"),  # REQUIRED - validated in core.py
                    "key_points": item.get("key_points"),  # REQUIRED - validated in core.py
                    "cognitive_level": cognitive_level_int,  # Integer 1-6 (Bloom's Taxonomy)
                    "difficulty": difficulty_int,  # Integer 1-3 (Easy/Medium/Hard)
                    "estimated_time": estimated_time_val,  # Float (minutes)
                    "image_part_of": item.get("part_of_list"),
                    "image_url": item.get("s3_url_list"),
                    "has_sub_questions": str(has_sub) if has_sub is not None else "False",
                    "alternative_ques": str(alternative_ques) if alternative_ques is not None else "False",
                    "is_or_question": str(is_or_question) if is_or_question is not None else "False",
                    "or_option": none_if_blank(or_option),
                    "part_label": none_if_blank(part_label, None),
                    "model": "gemini-2.0-flash",
                    "model_id": 1,
                }

                if existing:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    #logger.info("Updated question Q%s", existing.question_number)
                else:
                    new_entry = classes.QuestionData(
                        qp_id=ques_id,
                        question_number=qnum,
                        **payload,
                    )
                    session.add(new_entry)
                    #logger.info("Inserted question Q%s", qnum)
            # logger.info(f"✅ {len(dict_items)} Question data added successfully.")

    except OperationalError as e:
        logger.error(f"Database operation (add_ques_answer_data) failed: {e}")
        raise
    finally:
        await session.close()

@retry_on_failure
async def token_update_fc(request_data:classes.QuestionPaperRequest, token_data:dict, model_name:str, bot_name:str = "OCR_Question_Paper_Schema_Agent"):
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
        # logger.info(f"✅ Token usage updated for Question ID: {request_data.user_id}.")
    except Exception as e:
        logger.error(f"Error updating token usage: {e}")
        return None
    finally:
        await session.close()        
    
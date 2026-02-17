from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os, logging, asyncio,constants, json
from locf.s_question_paper import classes
from typing import Iterable, Dict, Any
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
                existing.grader_id           = 1
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
                    grader_id           = 1,
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

                result = await session.execute(
                    select(classes.QuestionData).where(
                        classes.QuestionData.user_id == request.user_id,
                        classes.QuestionData.qp_id == ques_id,
                        classes.QuestionData.question_number == qnum
                    )
                )
                existing = result.scalar_one_or_none()

                # Build a payload without clobbering 0/False
                payload = {
                    "uuid": request.uuid,
                    "user_id": request.user_id,
                    "question_type": none_if_blank(item.get("question_type")),
                    "max_marks": to_int_safe(item.get("max_marks"), 0),
                    "is_image": item.get("is_image") if item.get("is_image") is not None else None,
                    "image_description": none_if_blank(item.get("image_description"), "Not provided"),
                    "question": none_if_blank(item.get("question"), "Not provided"),
                    "correct_opt": item.get("crt_option") if item.get("crt_option") is not None else "Not provided",
                    "option_a": none_if_blank(item.get("option_a"), "Not provided"),
                    "option_b": none_if_blank(item.get("option_b"), "Not provided"),
                    "option_c": none_if_blank(item.get("option_c"), "Not provided"),
                    "option_d": none_if_blank(item.get("option_d"), "Not provided"),
                    "explanation": none_if_blank(item.get("explanation"), "Not provided"),
                    "expected_answer": none_if_blank(item.get("expected_answer"), "Not provided"),
                    "marking_scheme": none_if_blank(item.get("marking_scheme"), "Not provided"),
                    "key_points": none_if_blank(item.get("key_points"), "Not provided"),
                    "image_part_of": none_if_blank(item.get("part_of"), "Not provided"),
                    "image_url": none_if_blank(item.get("s3_url"), "Not provided"),
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
            logger.info(f"✅ {len(dict_items)} Question data added successfully.")

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
        logger.info(f"✅ Token usage updated for Question ID: {request_data.user_id}.")
    except Exception as e:
        logger.error(f"Error updating token usage: {e}")
        return None
    finally:
        await session.close()        
    
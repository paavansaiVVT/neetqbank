from locf.data_extraction.classes import Topics,file_request,LearningObjective,WebResource,co_po_mappings,course_units,CourseOutcome,Textbook,ReferenceBook,Chapters, CourseOutcomePo, ProgramOutcomes, list_of_programs
from sqlalchemy import select, func, text
from typing import Iterable
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import os, logging, json

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL_8")
engine = create_async_engine(DATABASE_URL,echo=False,pool_size=100,max_overflow=50,pool_recycle=1800, pool_pre_ping=True, connect_args={"connect_timeout": 600})
AsyncSessionLocal = sessionmaker(bind=engine,class_=AsyncSession,expire_on_commit=False)

Base = declarative_base()
retry_on_failure = retry(stop=stop_after_attempt(3),wait=wait_fixed(5),before_sleep=before_sleep_log(logger, logging.WARNING))
def get_session():
    return AsyncSessionLocal()

class PostCourse:
    def __init__(self):
        self.session = get_session()
    """Class to handle post-course data operations."""
    
    # async def add_co_po(self,output: dict, course_id: int):
    #     """Add CO-PO mappings to the database in structured format."""
    #     session = get_session()
    #     try:
    #         async with session.begin():
    #             for co_label, mappings in output.items():
    #                 for po_label, value in mappings.items():
    #                     data = co_po_mappings(
    #                         course_id=course_id,
    #                         co_label=co_label,
    #                         po_label=po_label,
    #                         value=value
    #                     )
    #                     session.add(data)
    #             await session.commit()
    #             logger.info("CO-PO mappings added successfully.")
    #     except OperationalError as e:
    #         logger.error(f"Database operation failed in co-po mapping: {e}")
    #         await session.rollback()
    #     except Exception as e:
    #         logger.error(f"An error occurred while adding CO-PO mappings: {e}")
    #         await session.rollback()
    #     finally:
    #         await session.close()


    async def add_co_po(self,output, course_id: int):
        """Add CO-PO mappings (including TOTAL and AVERAGE) to the database."""
        try:
            session = get_session()
            async with session.begin():
                for item in output:
                    for x,y in item.items():
                        if 'TOTAL' in x or 'AVERAGE' in x:
                            key = 'TOTAL' if 'TOTAL' in x else 'AVERAGE'
                            for po_label, value in y.items():
                                data = co_po_mappings(
                                    course_id=course_id,
                                    co_label=key,  # 'TOTAL' or 'AVERAGE'
                                    po_label=po_label,
                                    value=value,
                                    justification=None
                                )
                                session.add(data)
                        else:
                            for i,j in y.items():
                                # Regular CO-PO mapping with strength and justification
                                data=co_po_mappings(
                                    course_id=course_id,
                                    co_label=x,
                                    po_label=i,
                                    value=y[i]["strength"],  # No numerical value for these rows
                                    justification=y[i]["justification"]
                                )
                                session.add(data)
                await session.commit()  # Commit the transaction
                logger.info("All CO-PO mappings including TOTAL and AVERAGE added successfully.")
        except OperationalError as e:
            logger.error("Database operation failed in add_co_po: {e}")
        except Exception as e:
            logger.error(f"An error occurred while adding CO-PO mappings: {e}")
            await session.rollback()
        finally:
            await session.close()
            return True

    @retry_on_failure
    async def get_chapters(self,s_name,sub_id, pro_id):
        """Get or create an Chapter entry in the database."""
        session = get_session()
        try:
            async with session.begin():
                # Check for existing subject entry
                result = await session.execute(select(Chapters)
                    .where(Chapters.c_name ==s_name,Chapters.s_id == sub_id, Chapters.p_id == pro_id))
                existing = result.scalar_one_or_none()
                if existing:
                    cha_id = existing.id
                else:
                    new_entry = Chapters(c_name=s_name,s_id=sub_id,status=1,p_id=pro_id )
                    session.add(new_entry)
                    await session.flush()
                    cha_id = new_entry.id

                await session.commit()
                return cha_id
        except OperationalError as e:
            logger.error(f"Database operation failed in get_chapter_id: {e}")
            await session.rollback()
        except Exception as e:
            logger.error(f"Unexpected error occurred in get_chapter_id: {e}")
            await session.rollback()
        finally:
            await session.close()
            
    @retry_on_failure
    async def get_topic(self, program_id: int, subject_id: int, chapter_id: int, topic_name: str):
        """Get or create an topic entry in the database."""
        session = get_session()
        try:
            async with session.begin():
                # Check for existing subject entry
                result = await session.execute(select(Topics)
                    .where(
                        Topics.t_name ==topic_name.strip( ),
                        Topics.c_id == chapter_id,
                        Topics.p_id == program_id
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    p_id = existing.p_id
                    s_id = existing.s_id
                    c_id = existing.c_id
                    t_id = existing.id
                else:
                    new_entry = Topics(
                        p_id= program_id,
                        c_id= chapter_id,
                        s_id= subject_id,
                        t_name= topic_name.strip( ),
                        status= 1,
                        is_deleted = 0
                    )
                    session.add(new_entry)
                    await session.flush()
                    p_id = new_entry.p_id
                    s_id = new_entry.s_id
                    c_id = new_entry.c_id
                    t_id = new_entry.id

                await session.commit()
                return p_id, s_id, c_id, t_id
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
    async def add_units(self, output, course_id, sub_id, program_id):
        """Add course units to the database."""
        session = get_session()
        chapter_ids = []
        
        logger.info(f"Processing {len(output)} units for course_id: {course_id}")

        try:
            async with session.begin():
                for idx, unit in enumerate(output):
                    try:
                        # Validate required fields
                        required_fields = ["title", "unit_number", "content", "hours_allocated"]
                        missing_fields = [field for field in required_fields if field not in unit]
                        
                        if missing_fields:
                            logger.warning(f"Unit {idx + 1} missing required fields: {missing_fields}. Unit data: {unit}")
                            # Use defaults for missing fields
                            unit.setdefault("content", "Not specified")
                            unit.setdefault("title", f"Unit {idx + 1}")
                            unit.setdefault("unit_number", idx + 1)
                            unit.setdefault("hours_allocated", 0)
                        
                        chapter_id = await self.get_chapters(unit["title"], sub_id, program_id)
                        chapter_ids.append(chapter_id)

                        data = course_units(
                            course_id=course_id,
                            unit_number=unit["unit_number"],
                            content=unit["content"],
                            hours_allocated=unit["hours_allocated"],
                            title=chapter_id 
                        )
                        session.add(data)

                        # Handle topics if present
                        topics = unit.get("topics", [])
                        if topics and isinstance(topics, list):
                            for topic in topics:
                                await self.get_topic(
                                    program_id=program_id,
                                    subject_id=sub_id,
                                    chapter_id=chapter_id,
                                    topic_name=topic
                                )
                        else:
                            logger.warning(f"Unit {idx + 1} has no topics or invalid topics format")

                    except Exception as e:
                        logger.error(f"Skipping unit {idx + 1} due to error: {e}. Unit data: {unit}")
                        continue

                await session.commit()
                logger.info("Units and topics added successfully.")

        except OperationalError as e:
            logger.error(f"Database operation failed in add_units: {e}")
            await session.rollback()
        except Exception as e:
            logger.error(f"An error occurred in add_units: {e}")
            await session.rollback()
        finally:
            await session.close()
        
        logger.info(f"Returning {len(chapter_ids)} chapter IDs: {chapter_ids}")
        return chapter_ids



    @retry_on_failure
    async def add_course_outcomes(self, output: list, course_id: int, chapter_ids: list):
        """Add course outcomes to the database."""
        session = get_session()
        try:
            async with session.begin():
                for i, x in enumerate(output):
                    try:
                        # Validate required fields
                        if not isinstance(x, dict):
                            logger.error(f"Skipping invalid CO at index {i}: Expected dict, got {type(x)}")
                            continue
                        
                        co_number = x.get("CO")
                        description = x.get("description")
                        
                        if not co_number or not description:
                            logger.warning(f"CO at index {i} missing required fields. CO: {co_number}, description: {description}. Data: {x}")
                            if not co_number:
                                co_number = f"CO{i + 1}"
                            if not description:
                                description = "Not specified"
                        
                        # Safe chapter_id assignment with proper fallback
                        if chapter_ids and i < len(chapter_ids):
                            chapter_id = chapter_ids[i]
                        elif chapter_ids:
                            chapter_id = chapter_ids[0]
                        else:
                            # If no chapter_ids available, use a default value or skip
                            logger.warning(f"No chapter IDs available for CO {co_number}. Using default chapter_id=1")
                            chapter_id = 1  # Default fallback, or you could create a default chapter

                        co = CourseOutcome(
                            co_number=co_number,
                            content=description,
                            course_id=course_id,
                            chapter_id=chapter_id
                        )
                        session.add(co)
                        
                    except Exception as co_error:
                        logger.error(f"Skipping CO at index {i} due to error: {co_error}. Data: {x}")
                        continue

                # Flush early to catch DB errors
                await session.flush()

            logger.info("Course outcomes added successfully.")

        except OperationalError as e:
            logger.error(f"Database operation failed in add_course_outcomes: {e}")
            await session.rollback()
        except Exception as e:
            logger.error(f"Error occurred in add_course_outcomes: {e}")
            await session.rollback()
        finally:
            await session.close()

            
    @retry_on_failure
    async def add_course_outcomes_po(self, output: list, course_id: int, chapter_ids: list, program_id: int):
        """Add course outcomes and store matched PO IDs in the po_id column."""
        session = get_session()
        try:
            async with session.begin():
                for i, outcome in enumerate(output):
                    try:
                        # Validate data structure
                        if not isinstance(outcome, dict):
                            logger.error(f"Skipping invalid outcome at index {i}: Expected dict, got {type(outcome)}")
                            continue
                        
                        co_number = outcome.get("CO")
                        description = outcome.get("description")
                        po_codes = outcome.get("programme_outcomes", [])
                        
                        if not co_number or not description:
                            logger.warning(f"Outcome at index {i} missing required fields. CO: {co_number}, description: {description}. Data: {outcome}")
                            if not co_number:
                                co_number = f"CO{i + 1}"
                            if not description:
                                description = "Not specified"

                        # Get chapter_id safely with proper fallback
                        if chapter_ids and i < len(chapter_ids):
                            chapter_id = chapter_ids[i]
                        elif chapter_ids:
                            chapter_id = chapter_ids[0]
                        else:
                            logger.warning(f"No chapter IDs available for CO {co_number}. Using default chapter_id=1")
                            chapter_id = 1  # Default fallback

                        # Fetch PO IDs from program_outcomes table
                        if po_codes and isinstance(po_codes, list):
                            result = await session.execute(
                                select(ProgramOutcomes.id)
                                .where(
                                    ProgramOutcomes.code.in_(po_codes),
                                    ProgramOutcomes.program_id == program_id
                                )
                            )
                            rows = result.fetchall()

                            if not rows:
                                logger.warning(f"No matching PO found for CO {co_number} with codes: {po_codes}")
                                po_ids = []
                            else:
                                po_ids = [row[0] for row in rows]
                        else:
                            logger.warning(f"No valid programme_outcomes for CO {co_number}")
                            po_ids = []

                        co = CourseOutcomePo(
                            co_number=co_number,
                            content=description,
                            course_id=course_id,
                            chapter_id=chapter_id,
                            po_id=json.dumps(po_ids)  # Store list of matching PO IDs
                        )

                        session.add(co)

                    except Exception as e:
                        logger.error(f"Skipping outcome at index {i} due to error: {e}. Data: {outcome}")
                        continue

                await session.commit()
                logger.info("Course outcomes with matched PO IDs added successfully.")

        except OperationalError as e:
            logger.error(f"Database operation failed in add_course_outcomes_po: {e}")
            await session.rollback()
        except Exception as e:
            logger.error(f"Unexpected error in add_course_outcomes_po: {e}")
            await session.rollback()
        finally:
            await session.close()


    @retry_on_failure
    async def add_textbooks(self,textbooks_data: list,course_id: int):
        """Add textbooks to the database."""
        session = get_session()
        try:
            async with session.begin():
                for book in textbooks_data:
                    try:
                        tb = Textbook(
                            title=book.get("title", ""),
                            author=book.get("author", ""),
                            edition=book.get("edition", ""),
                            year=book.get("year", ""),
                            publisher=book.get("publisher", ""),
                            course_id=course_id
                        )
                        session.add(tb)
                    except Exception as e:
                        logger.error(f"Skipping textbook due to error: {e}")
                        continue
                await session.commit()
                logger.info("Textbooks added successfully.")
        except OperationalError as e:
            logger.error(f"Database operation failed in add_textbooks: {e}")
            await session.rollback()
        except Exception as e:
            logger.error(f"An error occurred in add_textbooks: {e}")
            await session.rollback()
        finally:
            await session.close()


    @retry_on_failure
    async def add_reference_books(self, books_data: list,course_id: int):
        """Add reference books to the database."""
        session = get_session()
        try:
            async with session.begin():
                for book in books_data:
                    try:
                        rb = ReferenceBook(
                            title=book.get("title", ""),
                            author=book.get("author", ""),
                            edition=book.get("edition", ""),
                            year=book.get("year", ""),
                            publisher=book.get("publisher", ""),
                            course_id=course_id
                        )
                        session.add(rb)
                    except Exception as e:
                        logger.error(f"Skipping reference book due to error: {e}")
                        continue
                await session.commit()
                logger.info("Reference books added successfully.")
        except OperationalError as e:
            logger.error(f"Database operation failed in add_reference_books: {e}")
            await session.rollback()
        finally:
            await session.close()


    @retry_on_failure
    async def add_web_resources(self,urls: list,course_id: int):
        """Add web resources to the database."""
        session = get_session()
        try:
            async with session.begin():
                for url in urls:
                    try:
                        resource = WebResource(
                            url=url,
                            course_id=course_id
                        )
                        session.add(resource)
                    except Exception as e:
                        logger.error(f"Skipping URL due to error: {e}")
                        continue
                await session.commit()
                logger.info("Web resources added successfully.")
        except OperationalError as e:
            logger.error(f"Database operation failed in add_web_resources: {e}")
            await session.rollback()
        except Exception as e:
            logger.error(f"An error occurred in add_web_resources: {e}")
            await session.rollback()
        finally:
            await session.close()

    @retry_on_failure
    async def add_learning_objectives(self,objectives: list, course_id: int):
        session = get_session()
        try:
            async with session.begin():
                for idx, obj in enumerate(objectives):
                    try:
                        if not isinstance(obj, dict):
                            logger.error(f"Skipping invalid learning objective at index {idx}: Expected dict, got {type(obj)}")
                            continue
                        
                        lo_value = obj.get("LO", "")
                        description = obj.get("description", "")
                        
                        # Handle LO number conversion safely
                        try:
                            if isinstance(lo_value, int):
                                lo_number = lo_value
                            elif isinstance(lo_value, str):
                                # Remove "LO" prefix if present and convert to int
                                lo_str = lo_value.replace("LO", "").strip()
                                lo_number = int(lo_str) if lo_str else idx + 1
                            else:
                                lo_number = idx + 1
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid LO number '{lo_value}' at index {idx}, using {idx + 1}")
                            lo_number = idx + 1
                        
                        if not description:
                            logger.warning(f"Learning objective {lo_number} has no description. Data: {obj}")
                            description = "Not specified"
                        
                        lo = LearningObjective(
                            lo_number=lo_number,
                            description=description,
                            course_id=course_id
                        )
                        session.add(lo)
                    except Exception as e:
                        logger.error(f"Skipping learning objective at index {idx} due to error: {e}. Data: {obj}")
                        continue
                await session.commit()
                logger.info("Learning objectives added successfully.")
        except Exception as e:
            logger.error(f"Error while adding learning objectives: {e}")
            await session.rollback()
        finally:
            await session.close()

    @retry_on_failure
    async def add_list_of_programs(self,program_id: int,course_id: int,descriptions: list[str]):
        """Insert multiple list_of_programs rows. Returns number of rows added."""
        # get_session() should be an async session factory, e.g. async_sessionmaker()
        async with get_session() as session:
            try:
                # Build objects first
                to_insert = []
                for des in descriptions:
                    if des is None:
                        continue
                    des = str(des).strip()
                    if not des:
                        continue
                    to_insert.append(
                        list_of_programs(
                            course_id=course_id,
                            program_id=program_id,
                            description=des
                        )
                    )

                if not to_insert:
                    logger.info("No valid descriptions to insert.")
                    return 0

                async with session.begin():
                    session.add_all(to_insert)

                logger.info("List of programs added successfully.")
                return len(to_insert)

            except OperationalError as e:
                logger.exception(f"Database operation failed in add_list_of_programs {e}")
                # session.begin() context auto-rolls back on exception; no explicit rollback needed here
                raise
            except SQLAlchemyError as e:
                logger.exception(f"SQLAlchemy error in add_list_of_programs {e}")
                raise
            except Exception:
                logger.exception("Unexpected error in add_list_of_programs")
                raise

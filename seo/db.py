
from question_banks.classes import slug_data,slug
from question_banks.db import retry_on_failure,engine,async_session_factory,get_session,fetch_topic_details

from sqlalchemy.future import select
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



async def update_slug(request:slug_data,data):
    """
    Update the slug in the database with the generated slug.
    Args:
        data (dict): A dictionary containing the following  keys:     
            - subject (str): The subject of the question.
            - chapter (str): The chapter of the question.
            - topic (str): The topic of the question.
            - existingSlug (str): The existing slug (optional).
            - questionText (str): The text of the question."""

    # Create a session
    session = get_session()
    try:
        async with async_session_factory() as session:
            async with session.begin():
                for entry in data:
                    try:
                        # Fetch the record by s_no
                        record = await session.execute(select(slug).where(slug.s_no == request.question_id))
                        record = record.scalar_one_or_none()                
                        if not record:
                            logger.warning(f"No record found with s_no: {request.question_id}")
                            continue  # Skip to the next entry
                            # Update the answer_desc
                        record.slug = entry['slug']
                        record.title = entry['meta_title']
                        record.description = entry['meta_description']
                        logger.info(f"Updating answer_desc for s_no {request.question_id}")
                    except Exception as e:
                            logger.error(f"Failed to update s_no {request.question_id}: {e}")
                            continue  # Skip to the next entry
                    # Commit the transaction after processing all entries
                await session.commit()
                logger.info("All updates committed successfully.")   
    except Exception as e:
        print(f"Error occurred in update_slug: {e}")
        return None
    
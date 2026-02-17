from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine, Column, Integer, String, text,Text, JSON,BLOB,ARRAY,Float
from sqlalchemy.orm import sessionmaker
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from typing import List, Optional
from dotenv import load_dotenv
import pymysql,os,logging,ast
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()
# Install pymysql as MySQLdb
pymysql.install_as_MySQLdb()
embedding = OpenAIEmbeddings(api_key=os.getenv("OpenAI_API_KEY"))

DATABASE_URL=os.getenv("DATABASE_URL_2")
engine = create_async_engine(DATABASE_URL,echo=False,pool_size=100,max_overflow=50,pool_timeout=60,pool_recycle=1800)

# Create session factory
async def get_session_3():
    """Creates and returns a new database session."""
    async_session_factory = sessionmaker(bind=engine,expire_on_commit=False,class_=AsyncSession)
    return async_session_factory()

# Define a base class for the models
Base = declarative_base()
 
class FlashcardDb(Base):
    __tablename__ = 'flash_cards'
    id = Column(Integer, primary_key=True, autoincrement=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    front_embedding = Column(JSON, nullable=False)  # Column to store the embedding vector
    t_id = Column(Integer, nullable=False)
    c_id = Column(Integer, nullable=False)
    s_id = Column(Integer, nullable=False)
    duplicates = Column(JSON, nullable=True)
    concepts = Column(Text, nullable=True)

class FlashcardRequest(BaseModel):
    topic: Optional[str] = None
    subject: Optional[str] = None
    chapter: Optional[str] = None
    class_no: Optional[int] = None
    topic_id: Optional[int] = None
    chapter_id: Optional[int] = None
    subject_id: Optional[int] = None
# Variable for retry mechanism
retry_on_failure = retry(stop=stop_after_attempt(3),wait=wait_fixed(5),before_sleep=before_sleep_log(logger, logging.WARNING))

# Assuming you have a function to get the embedding for a query:
async def get_embedding(query):
    try:
        # Replace with your actual embedding function
        return await embedding.aembed_query(query)
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")

@retry_on_failure
async def dump_flashcards(request: FlashcardRequest, all_entries: List[dict]):
    """Dump the generated flash cards to the database, marking duplicates with the original flashcard id."""
    session = None  # Initialize session to avoid UnboundLocalError
    try:
        session = await get_session_3()
        for entry in all_entries:
            result = await session.execute(
                text("SELECT s_no, front, front_embedding FROM flash_cards WHERE t_id = :topic_id AND c_id = :chapter_id AND s_id = :subject_id"),
                {"topic_id": request.topic_id, "chapter_id": request.chapter_id, "subject_id": request.subject_id})
            existing_flashcards = result.fetchall()
            
            duplicates = []  # List to store all duplicates with their similarity scores
            for flashcard in existing_flashcards:
                flashcard_id = flashcard[0]  # 'id' column is at index 0
                existing_front = flashcard[1]  # 'front' column is at index 1
                if entry["Front"] == existing_front:
                    logger.info(f"Skipping entry because the front matches an existing flashcard: {entry['Front']}")
                    break
            else:
                # Compute the embedding for the flashcard's front text only once
                new_embedding = await get_embedding(entry['Front'])
                if existing_flashcards:
                    # Check for duplicates (comparing the front only)
                    for flashcard in existing_flashcards:
                        flashcard_id = flashcard[0]  # 'id' column is at index 0
                        existing_front = flashcard[1]  # 'front' column is at index 1
                        existing_embedding = ast.literal_eval(flashcard[2])  # 'front_embedding' column is at index 2

                        # Compute cosine similarity between the new and existing embeddings
                        similarity = cosine_similarity([new_embedding], [existing_embedding])[0][0]
                        # If similarity is above threshold, add to the duplicates list
                        if similarity > 0.9:
                            duplicates.append({"duplicate_id": flashcard_id,"similarity": similarity})
                            logger.info(f"Duplicate flashcard found with similarity {similarity}. Duplicate flashcard id {flashcard_id}")

                # Insert the new flashcard, marking duplicates in the 'duplicates' column
                data = FlashcardDb(
                    front=entry['Front'],
                    back=entry['Back'],
                    front_embedding=new_embedding,
                    t_id=request.topic_id,
                    c_id=request.chapter_id,
                    s_id=request.subject_id,
                    duplicates=duplicates if duplicates else None , # Store duplicates as a list or None if no duplicates
                    concepts=entry.get("concepts", None) ) # Add concepts if available
                session.add(data)
                await session.commit()
                logger.info("Flashcards added to the database.")
    except pymysql.MySQLError as e:
        await session.rollback()
        logger.error(f"MySQL error occurred: {e}")
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        await session.close()
        logger.info("Session closed.")

@retry_on_failure
async def pull_flashcards(request: FlashcardRequest):
    """Pull Already generated flashcards from the database to Avoid Duplication."""
    session = None  # Initialize to avoid UnboundLocalError
    try:
        session = await get_session_3()
        async with session.begin():
            result = await session.execute(
                text("SELECT front FROM flash_cards WHERE t_id = :topic_id AND c_id = :chapter_id AND s_id = :subject_id"),
                {"topic_id": request.topic_id,"chapter_id": request.chapter_id,"subject_id": request.subject_id})
            existing_flashcards = result.fetchall()
            if existing_flashcards:
                return [card[0] for card in existing_flashcards]
            else:
                return None
    except pymysql.MySQLError as e:
        logger.error(f"MySQL error occurred: {e}")
        raise
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        if session:
            await session.close()
            logger.info("Session closed.")

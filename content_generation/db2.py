from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import logging  
from sqlalchemy.orm import sessionmaker

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Define a base class for the models
Base = declarative_base()
DATABASE_URL_2 = "mysql+aiomysql://admin:Cs-NeeTGuiDe@cs-neetguide.crzbseg7lazz.ap-south-1.rds.amazonaws.com:3306/neetguide?charset=utf8mb4"

engine2 = create_async_engine(DATABASE_URL_2,
    echo=True,
    pool_size=100,  # Increase pool size
    max_overflow=50,  # Allow additional connections beyond the pool size
    pool_timeout=60,  # Increase timeout for acquiring a connection
    pool_recycle=1800,
    pool_pre_ping=True
)

def get_session():
    """Creates and returns a new database session."""
    Session = sessionmaker(bind=engine2)
    return Session()

class blog(Base):
    __tablename__ = 'articles_bot'
    #__table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True)
    keyword = Column(Text, nullable=True)
    url = Column(JSON, nullable=True)
    tokens = Column(JSON, nullable=True)
    web_scrap_data = Column(BLOB, nullable=True)
    qc_data = Column(BLOB, nullable=True)
    blog = Column(BLOB, nullable=True)
    websearch_data = Column(BLOB, nullable=True)
    seo_expert_data = Column(BLOB, nullable=True)
    research_data = Column(BLOB, nullable=True)

# Create session factory
async_session_factory = sessionmaker(
    bind=engine2,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def add_blog_data(data):
    try:
        async with async_session_factory() as session:
            async with session.begin():
                new_blog_entry = blog(
                    keyword=data.get('user_input'),
                    url=data.get('urls'),
                    web_scrap_data=data.get('web_scrap_data'),
                    research_data=data.get('research_data'),
                    seo_expert_data=data.get('seo_expert_data'),
                    websearch_data=data.get('websearch_data'),
                    blog=data.get('seo_blog_data'),
                    qc_data=data.get('qc_data'),
                    tokens=data.get('combined_tokens'),
                )
                session.add(new_blog_entry)
                await session.commit()
                logger.info("All entries added successfully.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        await shutdown_engine()
        logger.info("Connection closed.")

async def shutdown_engine():
    """Shuts down the database engine properly."""
    await engine2.dispose()
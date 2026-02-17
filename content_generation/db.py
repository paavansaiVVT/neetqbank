from sqlalchemy import create_engine, Column, Integer, Text, JSON, BLOB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging,json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a base class for the models
Base = declarative_base()

# Database URL for synchronous connection
DATABASE_URL_2 = "mysql+pymysql://admin:Cs-NeeTGuiDe@cs-neetguide.crzbseg7lazz.ap-south-1.rds.amazonaws.com:3306/neetguide?charset=utf8mb4"

# Create a synchronous engine
engine2 = create_engine(
    DATABASE_URL_2,
    echo=True,
    pool_size=100,       # Increase pool size
    max_overflow=50,     # Allow additional connections beyond the pool size
    pool_timeout=60,     # Increase timeout for acquiring a connection
    pool_recycle=1800,   # Recycle connections after 30 minutes
    pool_pre_ping=True   # Enable connection health checks
)

# Create a session factory
Session = sessionmaker(bind=engine2)
session = Session()

# Define the Blog model
class blog(Base):
    __tablename__ = 'articles_bot'
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

import json

def convert_to_blob(data):
    return json.dumps(data).encode('utf-8') if isinstance(data, (dict, list)) else data.encode('utf-8')

def convert_to_json(data):
    return data if isinstance(data, (dict, list)) else json.loads(data)


def add_blog_data(data):
    try:
        new_blog_entry = blog(
            keyword=data.get('user_input'),
            url=data.get('urls'),
            web_scrap_data=convert_to_blob(data.get('web_scrap_data')),
            research_data=convert_to_blob(data.get('research_data')),
            seo_expert_data=convert_to_blob(data.get('seo_expert_data')),
            websearch_data=convert_to_blob(data.get('websearch_data')),
            blog=convert_to_blob(data.get('seo_blog_data')),
            qc_data=convert_to_blob(data.get('qc_data')),
            tokens=convert_to_json(data.get('combined_tokens')),
        )
        session.add(new_blog_entry)
        session.commit()
        logger.info("All entries added successfully.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        session.rollback()
        raise
    finally:
        session.close()
        logger.info("Session closed.")

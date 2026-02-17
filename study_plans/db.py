from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float
import pymysql
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Install pymysql as MySQLdb
pymysql.install_as_MySQLdb()

# Define the database URL with increased timeouts and connection settings
DATABASE_URL = "mysql+pymysql://admin:Cs-NeeTGuiDe@cs-neetguide.crzbseg7lazz.ap-south-1.rds.amazonaws.com:3306/neetguide?charset=utf8mb4"

# Create a new engine instance with connection pooling and pool_recycle to handle timeout issues
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections every hour
    connect_args={"connect_timeout": 600, "read_timeout": 600}  # Increase timeouts
)

# Define a base class for the models
Base = declarative_base()

class analyze(Base):
    __tablename__ = 'ai_analysis'
    
    s_no = Column(Integer, primary_key=True, autoincrement=True)  # Topic ID
    Strong_Areas = Column(Text, nullable=True)
    Areas_Of_Improvement = Column(Text, nullable=True)
    Practice_Strategies = Column(Text, nullable=True)
    Time_Saving_Tips = Column(Text, nullable=True)


# Variable for retry mechanism
retry_on_failure = retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)

def get_session():
    """Creates and returns a new database session."""
    Session = sessionmaker(bind=engine)
    return Session()

# Create the table in the database if it doesn't exist
Base.metadata.create_all(engine)

def add_analyze_data(data):
    "generated studyplans  are inserted"
    # Create a session
    session = get_session()
    
    try:
        mcq = analyze()
        session.add(mcq)
            
            # Commit the transaction after each batch
        session.commit()
        logger.info(f"Committed  records.")
    
    except pymysql.MySQLError as e:
        # Rollback in case of a MySQL error
        session.rollback()
        logger.error(f"MySQL error occurred: {e}")
        raise  # Trigger retry
    
    except Exception as e:
        # Handle other exceptions
        session.rollback()
        logger.error(f"An error occurred: {e}")
        raise
    
    finally:
        # Ensure the session is closed
        session.close()
        logger.info("Session closed.")
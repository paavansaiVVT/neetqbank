from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from constants import difficulty_level,cognitive_levels,question_types
from question_banks.classes import MCQData,Topics
from dotenv import load_dotenv
import pymysql,os,logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Install pymysql as MySQLdb
pymysql.install_as_MySQLdb()

load_dotenv()
DATABASE_URL=os.getenv("DATABASE_URL")
DATABASE_URL_2=os.getenv("DATABASE_URL_2")
DATABASE_URL_3=os.getenv("DATABASE_URL_3")


# Create a new engine instance with connection pooling and pool_recycle to handle timeout issues
engine = create_engine(
    DATABASE_URL,
    pool_size=100,
    max_overflow=50,
    pool_recycle=1800,  # Recycle connections every hour
    connect_args={"connect_timeout": 600, "read_timeout": 600}  # Increase timeouts
)

engine2 = create_async_engine(DATABASE_URL_2,
    echo=False,
    pool_size=100,  # Increase pool size
    max_overflow=50,  # Allow additional connections beyond the pool size
    pool_timeout=60,  # Increase timeout for acquiring a connection
    pool_recycle=1800
)

# Use create_async_engine instead of create_engine
engine3 = create_async_engine(
    DATABASE_URL_3,
    pool_size=100,
    max_overflow=50,
    pool_recycle=1800,  # Recycle connections every hour
    echo=False
    #connect_args={"connect_timeout": 600} #, "read_timeout": 600}  # Increase timeouts
)

# Create session factory
async_session_factory = sessionmaker(
    bind=engine2,
    expire_on_commit=False,
    class_=AsyncSession,
)
# Define a base class for the models
Base = declarative_base()
   
# Variable for retry mechanism
retry_on_failure = retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)

def fetch_topic_details(session, selected_input):
    """Fetches topic, subject, and chapter details based on the topic name."""
    topic = session.query(Topics).filter(Topics.t_name == selected_input).first()
    if not topic:
        raise Exception(f"Topic '{selected_input}' not found in the database.")
    return topic.s_no, topic.s_id, topic.c_id  # topic_id, subject_id, chapter_id
                
def scale_score(value, min_old=0, max_old=0.25, min_new=1, max_new=10):
    #return (value - min_old) / (max_old - min_old) * (max_new - min_new) + min_new
    return value


# Create the table in the database if it doesn't exist
#Base.metadata.create_all(engine)

def get_session():
    """Creates and returns a new database session."""
    Session = sessionmaker(bind=engine)
    return Session()

async def get_session_3():
    """Creates and returns a new database session."""
    async_session_factory = sessionmaker(
    bind=engine3,
    expire_on_commit=False,
    class_=AsyncSession)
    return async_session_factory()

# Create session factory


@retry_on_failure
def add_mcq_data(all_data,selected_subject, selected_chapter, selected_input, difficulty):
    "New generated questions are inserted"
    # Create a session
    session = get_session()
    
    try:        
        topic_id, subject_id, chapter_id = fetch_topic_details(session, selected_input)
        # Determine the correct option number based on the correct answer
         
        # Process data in batches
        # Insert the data into the database
        for entry in all_data:
            try:
                correct_answer = entry['correct_answer']
                correct_opt = entry['options'].index(correct_answer) + 1
                difficulty_calibration_scores = [entry['scores']["difficulty_calibration"]["time_requirement"],entry['scores']["difficulty_calibration"]["concept_integration"]]
                individual_scores = [entry['scores']["content_accuracy"],entry['scores']["question_construction"],entry['scores']["subject_specific_criteria"],entry['scores']["cognitive_level_assessment"],entry['scores']["discrimination_power"]]+difficulty_calibration_scores
                
                # Calculate each scaled score separately
                time_requirement_scaled = scale_score(entry['scores']["difficulty_calibration"]["time_requirement"])
                step_complexity_scaled = 0 #scale_score(entry['scores']["difficulty_calibration"]["step_complexity"])
                concept_integration_scaled = scale_score(entry['scores']["difficulty_calibration"]["concept_integration"])
                reasoning_depth_scaled = 0 #scale_score(entry['scores']["difficulty_calibration"]["reasoning_depth"])

                # Calculate the average of the scaled scores
                average_score = (time_requirement_scaled + step_complexity_scaled + concept_integration_scaled + reasoning_depth_scaled) / 2


                mcq = MCQData(
                    question=entry['question'],
                    correct_opt=correct_opt,
                    option_a=entry['options'][0],  # First option
                    option_b=entry['options'][1],  # Second option
                    option_c=entry['options'][2],  # Third option
                    option_d=entry['options'][3],  # Fourth option
                    answer_desc=entry['explanation'],
                    difficulty=difficulty_level[difficulty.lower()],
                    question_type=question_types[entry["question_type"]], #"single correct answer",
                    keywords=entry['concepts'],
                    cognitive_level=cognitive_levels[entry["cognitive_level"].lower()],
                    t_id=topic_id,  # Insert the topic_id (s_no)
                    s_id=subject_id,  # Insert the subject_id (s_id)
                    c_id=chapter_id, # Insert the chapter_id (c_id)
                    estimated_time=entry["estimated_time"],
                    # Insert individual scores
                    
                    content_accuracy=entry['scores']["content_accuracy"],
                    question_construction=entry['scores']["question_construction"],
                    subject_specific_criteria=entry['scores']["subject_specific_criteria"],
                    cognitive_level_assessment=entry['scores']["cognitive_level_assessment"],
                    discrimination_power=entry['scores']["discrimination_power"],
                    difficulty_calibration=sum(difficulty_calibration_scores),
                    time_requirement= entry['scores']["difficulty_calibration"]["time_requirement"],
                    step_complexity= 0, # entry['scores']["difficulty_calibration"]["step_complexity"],
                    concept_integration= entry['scores']["difficulty_calibration"]["concept_integration"],
                    reasoning_depth= 0 ,# entry['scores']["difficulty_calibration"]["reasoning_depth"],
                    
                    # Apply the scaling to each score
                    time_requirement_scaled = time_requirement_scaled,
                    step_complexity_scaled = step_complexity_scaled,
                    concept_integration_scaled = concept_integration_scaled,
                    reasoning_depth_scaled = reasoning_depth_scaled,
                    difficulty_scaled = average_score,
                    
                    QC = entry["QC"],
                    recommendations=entry['recommendations'],
                    category_scores=entry['categoryScores'],

                    content_accuracy_details=entry['categoryScores']['contentAccuracy'] if 'contentAccuracy' in entry['categoryScores'] else None,
                    question_construction_details=entry['categoryScores']['question_construction'] if 'question_construction' in entry['categoryScores'] else None,
                    subject_specific_details=entry['categoryScores']['subject_specific_criteria'] if 'subject_specific_criteria' in entry['categoryScores'] else None,
                    difficulty_calibration_details=entry['categoryScores']['difficulty_calibration'] if 'difficulty_calibration' in entry['categoryScores'] else None,
                    discrimination_power_details=entry['categoryScores']['discrimination_power'] if 'discrimination_power' in entry['categoryScores'] else None,
                    violations=entry["violations"],
                    # Sum all individual score
                    total_score = sum(individual_scores) * difficulty,
                    question_origin=1 )
                session.add(mcq)
            except Exception as e:
                    # Log the error for debugging purposes
                    print(f"Error inserting entry: {e}")
                    # Optionally continue to next entry
                    continue
            
            # Commit the transaction after each batch
            session.commit()
            logger.info(f"Committed batch of {len(all_data)} records.")
    
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


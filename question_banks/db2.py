from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
import pymysql
import logging
from constants import difficulty_level,cognitive_levels,question_types,status
from question_banks.classes import MCQData,Topall_Data,explanation,Topics,QuestionBankRequest,qc
from question_banks.db import retry_on_failure,engine,async_session_factory,get_session,get_session_3,fetch_topic_details

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Install pymysql as MySQLdb
pymysql.install_as_MySQLdb()
# Define a base class for the models
Base = declarative_base()
#Create the table in the database if it doesn't exist
# Base.metadata.create_all(engine)

@retry_on_failure
def add_varied_mcq(all_data:list,selected_subject, selected_chapter, selected_input, difficulty,year,question_id):
    "PYQ variations are inserted"
    # Create a session
    session = get_session()
    try:
        # Query for topic_id, subject_id, and chapter_id based on selected_input (topic_name)
        topic_id, subject_id, chapter_id = fetch_topic_details(session, selected_input)      
        # Insert the data into the database
        for entry in all_data:
            try:
                correct_answer = entry['correct_answer']
                correct_opt = entry['options'].index(correct_answer) + 1
                difficulty_calibration_scores = [entry['scores']["difficulty_calibration"]["time_requirement"],entry['scores']["difficulty_calibration"]["concept_integration"]]
                individual_scores = [entry['scores']["content_accuracy"],entry['scores']["question_construction"],entry['scores']["subject_specific_criteria"],entry['scores']["cognitive_level_assessment"],entry['scores']["discrimination_power"]]+difficulty_calibration_scores                
                # Calculate each scaled score separately
                time_requirement = entry['scores']["difficulty_calibration"]["time_requirement"]
                concept_integration = entry['scores']["difficulty_calibration"]["concept_integration"]
                # Calculate the average of the scaled scores
                average_score = (time_requirement + concept_integration ) / 2
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
                    time_requirement= time_requirement,
                    concept_integration=concept_integration ,
                    # Apply the scaling to each score
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
                    # Version control
                    original_question_id=question_id,
                    variation_type=entry["version_control"]["variation_type"],
                    change_log=entry["version_control"]["change_log"],
                    year=year,
                    total_score = sum(individual_scores),
                    question_origin=2)
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




@retry_on_failure
def update_tagging_data(request:QuestionBankRequest,all_data:list,batch_size=100):
    """
    Update the answer_desc, cognitive_level, estimated_time, and concepts
    for given question
    """
    # Create a session
    session = get_session()
    try:
        # Process data in batches
        for i in range(0, len(all_data), batch_size):
            batch = all_data[i:i + batch_size]            
            # Insert the data into the database
            for entry in batch:
              try:
                # Fetch the record by s_no                
                mcq = MCQData(
                question=request.question,
                correct_opt=request.correct_opt,
                option_a=request.option_a,  # First option
                option_b=request.option_b ,  # Second option
                option_c=request.option_c ,  # Third option
                option_d=request.option_d,  # Fourth option
                answer_desc = entry['explanation'],
                cognitive_level =cognitive_levels[entry["cognitive_level"].lower()],
                estimated_time = entry['estimated_time'],
                keywords =entry['concepts'],               
                difficulty=request.difficulty,
                question_type=request.question_type, #"single correct answer",
                original_question_id=request.question_id,
                t_id=request.t_id,  # Insert the topic_id (s_no)
                s_id=request.s_id,  # Insert the subject_id (s_id)
                c_id=request.c_id, # Insert the chapter_id (c_id) 
                question_origin=3
                )
                session.add(mcq)
              except Exception as e:
                # Log the error for debugging purposes
                print(f"Error inserting entry: {e}")
                # Optionally continue to next entry
                continue
            
            # Commit the transaction after each batch
            session.commit()
            logger.info(f"Committed batch of {len(batch)} records.")
    
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


@retry_on_failure
async def update_tagging_topall(request: QuestionBankRequest, entry: dict):
    entry = entry[0]
    session = None  # Initialize session to avoid UnboundLocalError
    try:
        # Await the session creation function
        session = await get_session_3()
        async with session.begin():
                # Fetch the record asynchronously
                result = await session.execute(
                    select(Topall_Data).where(Topall_Data.vr_ques_id == request.question_id)
                )
                mcq = result.scalar_one_or_none()
                if mcq:
                    mcq.cognitive_level = cognitive_levels.get(entry["cognitive_level"].lower())
                    mcq.vr_ques_type = question_types.get(entry["question_type"].lower())
                    mcq.keywords = entry["concepts"]
                    # Commit asynchronously
                    await session.commit()
                    logger.info(f"Updated question_id {request.question_id} successfully.")
                else:
                    logger.warning(f"Question ID {request.question_id} not found.")
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


# Define the function for updating answer_desc
@retry_on_failure
async def update_qc(request: QuestionBankRequest, data):
    """
    Update the QC results for a given s_no value in the table.
    """
    try:
        async with async_session_factory() as session:
            async with session.begin():
                entry = data  # Extract the single dictionary from the list
                # Fetch the record from the database
                result = await session.execute(select(qc).filter(qc.s_no == request.question_id))
                record = result.scalar_one_or_none()
                
                if record:
                    record.result = status[entry['result']]
                    record.reason = entry['reason'] if "reason" in entry else None
                else:
                    logger.warning(f"No record found with s_no: {request.question_id}")
                
                await session.commit()
    except Exception as e:
        # Rollback in case of an error
        await session.rollback()
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        await session.close()
        logger.info("Session closed.")


# Define the function for updating answer_desc
@retry_on_failure
async def update_answer_desc(data):
    """
    Update the answer_desc for given s_no values in the table.
    """
    # Create a session
    session = get_session()
    try:
        async with async_session_factory() as session:
            async with session.begin():
                for entry in data:
                    try:
                         # Fetch the record by s_no
                        record = await session.execute(
                            select(explanation).where(explanation.s_no == entry['question_id'])
                        )
                        record = record.scalar_one_or_none()                
                        if not record:
                            logger.warning(f"No record found with s_no: {entry['question_id']}")
                            continue  # Skip to the next entry
                        # Update the answer_desc
                        record.answer_desc = entry['explanation']
                        logger.info(f"Updating answer_desc for s_no {entry['question_id']}")
                    except Exception as e:
                        logger.error(f"Failed to update s_no {entry['question_id']}: {e}")
                        continue  # Skip to the next entry
                # Commit the transaction after processing all entries
                await session.commit()
                logger.info("All updates committed successfully.")   
    except Exception as e:
        # Rollback in case of an error
        await session.rollback()
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        # Ensure the session is closed
        await session.close()
        logger.info("Session closed.")




@retry_on_failure
async def update_options_and_exp(request,options,correct_answer,question_explanation):
    """
    Update the answer_desc for given s_no values in the table.
    """
    # Create a session
    session = get_session()
    try:
        async with async_session_factory() as session:
            async with session.begin():
                try:
                    # Fetch the record by s_no
                    correct_opt = options.index(correct_answer) + 1
                    record = await session.execute(select(explanation).where(explanation.s_no == request.question_id))
                    record = record.scalar_one_or_none()                
                    if not record:
                        logger.warning(f"No record found with s_no: {request.question_id}")
                        return
                    # Update the answer_desc
                    record.option_a = options[0]
                    record.option_b = options[1]
                    record.option_c = options[2]
                    record.option_d = options[3]
                    record.correct_opt = correct_opt
                    record.answer_desc = question_explanation["explanation"]
                    await session.commit()
                    logger.info("All updates committed successfully.") 
                except Exception as e:
                    logger.error(f"Failed to update s_no {request.question_id}: {e}")
    except Exception as e:
        # Rollback in case of an error
        await session.rollback()
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        # Ensure the session is closed
        await session.close()
        logger.info("Session closed.")
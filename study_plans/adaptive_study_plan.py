import time,json,os,re,asyncio,logging
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from study_plans.studyplan_prompts import study_prompt,adaptive_study_prompt
from study_plans.study_plan_fomatings import ResultProcessor,mapper,adaptive_mapper,process_and_fix_data,format_json,fix_missing_commas,distribute_study_days_with_scores
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from study_plans.parsers import adaptive_plan_parser
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
class adaptive_StudyPlanRequest(BaseModel):
    current_plan: dict       
    backlog_plan: dict  

@retry(
    stop=stop_after_attempt(3),  # Stop after 3 attempts
    wait=wait_fixed(5),  # Wait 5 seconds between retries
    before_sleep=before_sleep_log(logger, logging.WARNING)  # Log before sleeping
)
async def studyplan(current_plan,backlog):
    """ Make LLM calls and format data in Json"""
    try:
        start_time = time.perf_counter()
        response= llm.invoke(adaptive_study_prompt.format(backlog_topics_list=current_plan,current_topics_list=backlog))        
        tokens=response.usage_metadata
        print(response.content)
        data=adaptive_plan_parser.invoke(response.content)
    except Exception as e:
        print(f"Error occurred: {e}")
        data = None
    finally:
        end_time = time.perf_counter()
        total = end_time - start_time
        print("Time taken:", total)
    return data,tokens

async def adaptive_main(request: adaptive_StudyPlanRequest):
    """ Task Assigner: Allocates tasks to respective functions """
    try:
        tasks = []
        backlog_subjects = {}  # Store only subjects with a backlog
        final_study_plan = {}  # Store the final combined plan
        total_tokens_used = 0  # Track total token usage

        # Loop through each subject in the current plan
        for subject in ["Botany", "Zoology", "Chemistry", "Physics"]:
            current_data = request.current_plan.get(subject, {})  # Get current study plan
            backlog_data = request.backlog_plan.get(subject, None)  # Get backlog if exists

            if backlog_data:
                # If backlog exists, call studyplan function
                backlog_subjects[subject] = backlog_data
                tasks.append(
                    studyplan(current_plan=current_data, backlog=backlog_data)
                )
            else:
                # No backlog, directly add current plan to results
                final_study_plan[subject] = current_data

        # If no backlog exists for any subject, return the current plan as is
        if not tasks:
            logging.warning("No backlog subjects found. Returning the current plan as is.")
            return request.current_plan, 0  # Assuming 0 tokens used

        # Run backlog processing tasks concurrently
        results = await asyncio.gather(*tasks)

        # Process results properly
        processor = ResultProcessor()
        processed_results = processor.process_results(results)

        # Debugging: Log what processed_results contains
        logging.info(f"Processed Results: {processed_results}")

        # Ensure correct unpacking
        if isinstance(processed_results, tuple) and len(processed_results) == 2:
            combined_data, combined_tokens = processed_results
        else:
            logging.error(f"Unexpected result format from process_results: {processed_results}")
            return None, None  # Handle error case

        # Handle `combined_tokens` if it's a dict
        if isinstance(combined_tokens, dict):
            logging.error(f"Unexpected dict format in combined_tokens: {combined_tokens}")

            # Extract numeric values if present
            possible_keys = ["total_tokens", "tokens_used", "token_count"]  # Adjust based on actual keys in dict
            for key in possible_keys:
                if key in combined_tokens and isinstance(combined_tokens[key], (int, float)):
                    combined_tokens = combined_tokens[key]
                    break
            else:
                logging.error("No valid numeric token value found, defaulting to 0.")
                combined_tokens = 0  # Default to 0 if no numeric token is found

        total_tokens_used += int(combined_tokens)  # Ensure it’s an integer

        final_study_plan.update(combined_data)  # Merge backlog data into final study plan
        final_study_plan = adaptive_mapper(final_study_plan)  # Apply any transformation
        return final_study_plan, total_tokens_used

    except Exception as e:
        logging.error(f"Error generating response: {e}")
        return None, None




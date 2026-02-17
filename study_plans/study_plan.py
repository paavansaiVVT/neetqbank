import time,json,os,re,asyncio,logging
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from study_plans.studyplan_prompts import study_prompt
from study_plans.study_plan_fomatings import ResultProcessor,mapper,process_and_fix_data,format_json,fix_missing_commas,distribute_study_days_with_scores
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Load environment variables from .env file and set up environment
load_dotenv()
os.environ["OPENAI_API_KEY"] =os.getenv("OpenAI_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
class StudyPlanRequest(BaseModel):
    subjects: dict         # Example: {"Physics": [{"chapter": "Laws of Motion","weightage": 14, "topics": [...], ...]}
    total_days: int       # Total preparation days before the exam
    #subject_scores: dict  # Example: {"Physics": 60 ,"Biology": 70,"chemistry": 85}
    hours: int            # Hours available per day
    level: dict  # Example: {"Physics": "Beginner" ,"Biology": "Intermediate","chemistry": "Expert"}

@retry(
    stop=stop_after_attempt(3),  # Stop after 3 attempts
    wait=wait_fixed(5),  # Wait 5 seconds between retries
    before_sleep=before_sleep_log(logger, logging.WARNING)  # Log before sleeping
)
async def studyplan(prompt,agent_data,hours):
    """ Make LLM calls and format data in Json"""
    text_before_json=7
    try:
        start_time = time.perf_counter()
        response= llm.invoke(study_prompt.format(topics_list=agent_data,hours=hours))        
        tokens=response.usage_metadata
        response=response.content
        output = response[text_before_json:]
        output=format_json(output)
        # Use executor to offload the JSON decoding to a separate thread
        data = json.loads(output) 
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        print("Received output:", output)
        json_string = fix_missing_commas(output)
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            print("Error decoding fixed JSON:", e)
            data = None
    except Exception as e:
        print(f"Error occurred: {e}")
        data = None
    finally:
        end_time = time.perf_counter()
        total = end_time - start_time
        print("Time taken:", total)
    return data,tokens


async def main(request:StudyPlanRequest):
    """ Task Assigner: Allocates tasks to respective functions"""
    try:
        # Create a list of tasks with different parameters        
        mapped_data = distribute_study_days_with_scores(request.subjects,request.total_days,request.level,subject_scores={"Physics": 56 ,"Botany": 56,"Zoology": 56,"Chemistry": 56})
        tasks = []
        
        # Check if the mapped data for each subject is not empty before adding the task
        if "Botany" in mapped_data and mapped_data["Botany"]:
            tasks.append(studyplan(study_prompt, agent_data=mapped_data["Botany"], hours=request.hours))
        if "Zoology" in mapped_data and mapped_data["Zoology"]:
            tasks.append(studyplan(study_prompt, agent_data=mapped_data["Zoology"], hours=request.hours))
        if "Chemistry" in mapped_data and mapped_data["Chemistry"]:
            tasks.append(studyplan(study_prompt, agent_data=mapped_data["Chemistry"], hours=request.hours))
        if "Physics" in mapped_data and mapped_data["Physics"]:
            tasks.append(studyplan(study_prompt, agent_data=mapped_data["Physics"], hours=request.hours))

        # Await the tasks to run them concurrently, if any tasks were added
        if tasks:
            results = await asyncio.gather(*tasks)

            # Process the results if tasks were successfully completed
            processor = ResultProcessor()
            combined_data, combined_tokens = processor.process_results(results)
            combined_data = mapper(combined_data)
            #combined_data = process_and_fix_data(combined_data)
            return combined_data, combined_tokens
        else:
            logging.warning("No valid subject data to process")
            return None, None

    except Exception as e:
        logging.error(f"Error generating response: {e}")
        return None, None



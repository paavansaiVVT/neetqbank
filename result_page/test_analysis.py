from langchain_google_genai import ChatGoogleGenerativeAI
from question_banks.question_bank_helpers import format_json,parse_json,format_results,calculate_total_tokens,clean_json_data
import json,time,asyncio,os,re
import concurrent.futures
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
import constants
from result_page import prompts
#from question_banks.db import add_mcq_data
load_dotenv()

os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"]=os.getenv('OpenAI_API_KEY')
os.environ["GOOGLE_API_KEY"]=os.getenv('GOOGLE_API_KEY')

async def single_test_analyze(test_data:str):
    try:
        prompt=prompts.single_analysis_prompt
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
        generation_response=await llm.ainvoke(prompt.format(test_data=test_data))
        response=generation_response.content
        output = response[constants.json_slice]
        output=format_json(output)
        output = parse_json(output)
        tokens=generation_response.usage_metadata
        # Printing the extracted item
        return output,tokens
    except Exception as e:
        print(f"Error occurred: {e}")
        print(output)


async def overall_test_analyze(input_analysis:str):
    try:
        prompt=prompts.overall_analysis_prompt
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
        generation_response=await llm.ainvoke(prompt.format(input_analysis=input_analysis))
        print(generation_response)
        response=generation_response.content
        output = response[constants.json_slice]
        output=format_json(output)
        output = parse_json(output)
        tokens=generation_response.usage_metadata
        # Printing the extracted item
        return output,tokens
    except Exception as e:
        print(f"Error occurred: {e}")
        print(output)
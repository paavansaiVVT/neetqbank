from seo.prompt import prompt,description_prompt
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from question_banks.question_bank_helpers import format_json,parse_json,format_results,calculate_total_tokens,clean_json_data
import json,time,asyncio,os,re
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import constants
from question_banks.db2 import add_varied_mcq,update_answer_desc,update_tagging_data,update_qc
from question_banks.classes import slug_data
from seo.db import update_slug
async def generate_slug(request:slug_data):
    """
    Generate an SEO-friendly URL slug from the given data.
    Args:
        data (dict): A dictionary containing the following keys:
            - subject (str): The subject of the question.
            - chapter (str): The chapter of the question.
            - topic (str): The topic of the question.
            - questionText (str): The text of the question. """
    try:
        #llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro")
        response=await llm.ainvoke(prompt.format(subject=request.subject,chapter=request.chapter,topic=request.topic,questionText=request.question))
        output=response.content
        output = output[constants.json_slice]
        tokens=response.usage_metadata
        output=format_json(output)
        output = output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        data = parse_json(output)
        asyncio.create_task(update_slug(request,data))
        # Printing the extracted item
        return data,tokens   
    except Exception as e:
        print(f"Error occurred in generate_slug: {e}")
        return None
    
async def generate_desc(request:slug_data):
    """
    Generate an SEO-friendly desc from the given data.
    Args:
        data (dict): A dictionary containing the following keys:
            - subject (str): The subject of the question.
            - chapter (str): The chapter of the question.
            - topic (str): The topic of the question. """
    try:
        #llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro")
        subject = request.subject if hasattr(request, 'subject') else ""
        chapter = request.chapter if hasattr(request, 'chapter') else ""
        topic = request.topic if hasattr(request, 'topic') else ""
        response=await llm.ainvoke(description_prompt.format(subject=subject,chapter=chapter,topic=topic))
        output=response.content
        output = output[constants.json_slice]
        tokens=response.usage_metadata
        output=format_json(output)
        output = output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        data = parse_json(output)
        # Printing the extracted item
        return data,tokens   
    except Exception as e:
        print(f"Error occurred in generate_slug: {e}")
        return None
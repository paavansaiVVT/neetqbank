
from typing import List, Optional
from langchain_core.output_parsers import JsonOutputParser
import os,re,time,json,requests,fitz,asyncio,logging
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate
from flashcard.prompt import prompt
from flashcard.db import dump_flashcards,pull_flashcards,FlashcardRequest
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import RunnableLambda
import constants
prompt_template = PromptTemplate.from_template(prompt)
class FlashcardParser(BaseModel):
    Front:Optional[str] = None
    Back:Optional[str] = None


rate_limiter = InMemoryRateLimiter(requests_per_second=constants.REQUESTS_PER_SECOND,check_every_n_seconds=constants.CHECK_EVERY_N_SECONDS,max_bucket_size=constants.MAX_BUCKET_SIZE)
parser = JsonOutputParser(pydantic_object=FlashcardParser)
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001",google_api_key=os.getenv('GOOGLE_API_KEY'),rate_limiter=rate_limiter)

def cleaner(data):
    data = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', data.content)
    return data  

chain = prompt_template | llm | RunnableLambda(cleaner) | parser

async def generate_flashcard(request:FlashcardRequest)->str:
    """Generate flashcards for a given subject and chapter"""
    try:
        existing_flashcards=await pull_flashcards(request)
        current_count = len(existing_flashcards) if existing_flashcards else 0
        print(f"Initial flashcard count: {current_count}")

        while current_count < 50:
            response= await chain.ainvoke({"class":request.class_no,"sub":request.subject,"chapter":request.chapter,"topic":request.topic,"existing_flashcards":existing_flashcards})
            await dump_flashcards(request,response)
            current_count += len(response)
            if existing_flashcards:
                existing_flashcards.extend(response) # Update the list with new flashcards
            else:
                existing_flashcards = response
            print(f"Flashcards after generation: {current_count}")
        return existing_flashcards #response
    except Exception as e:
        print(str(e))



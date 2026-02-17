from tutor_bots.neet_doubt_ai import generate_response_common
from tutor_bots.neet_chapter_studyplan_bot import generate_response_studyplan_wise
from tutor_bots.neet_chapter_bot import generate_response_chapterwise
from tutor_bots.jee_chapter_bot import jee_response_chapterwise
from tutor_bots.jee_doubt_ai import jee_response_common
from tutor_bots.classes import RequestData
from tutor_bots.cbse_chapter_bot import generate_response_cbse_chapterwise
from tutor_bots.neet_pyq_bot import generate_response_pyq
from tutor_bots.cbse_doubt_ai import generate_response_cbse_common
from tutor_bots.career_coach import carrer_coach_bot
from tutor_bots.college_suggest import collegesuggest_bot
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Neet Guide chapter bot
@router.post("/neet-chapterwise-bot")
async def neet_chapterwise_data(request_data: RequestData):
    try:
        # Assuming generate_answer is an asynchronous function you've defined
        result, history,chat_title,tokens = await generate_response_chapterwise(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Neet Guide Study plan chapter bot
@router.post("/neet-chapterwise-studyplan-bot")
async def neet_studyplan_wise_data(request_data: RequestData):
    try:
        result, history,chat_title,tokens = await generate_response_studyplan_wise(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Neet Guide doubts AI bot
@router.post("/neet-common-bot")
async def neet_common_data(request_data: RequestData):
    try:    
        result, history,chat_title,tokens =await generate_response_common(request_data)
        return {"result": result, "data": history,"tokens": tokens,"chat_title":chat_title}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Neet PYQ bot
@router.post("/neet-pyq-bot")
async def neet_pyq_data(request_data: RequestData):
    try:  
        result, history,chat_title,tokens =await generate_response_pyq(request_data)
        return {"result": result, "data": history,"tokens": tokens,"chat_title":chat_title}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
    

# JEE Chapter wise bot
@router.post("/jee-chapterwise-bot")
async def jee_chapterwise_data(request_data: RequestData):
    try:
        result, history,chat_title,tokens = await jee_response_chapterwise(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# JEE Doubts AI bot
@router.post("/jee-common-bot")
async def jee_common_data(request_data: RequestData):
    try:    
        result, history,chat_title,tokens =await jee_response_common(request_data)
        return {"result": result, "data": history,"tokens": tokens,"chat_title":chat_title}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# CBSE chapter bot
@router.post("/cbse-chapterwise-bot")
async def cbse_chapterwise_data(request_data: RequestData):
    try:
        # Assuming generate_answer is an asynchronous function you've defined
        result, history,chat_title,tokens = await generate_response_cbse_chapterwise(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# CBSE chapter bot
@router.post("/cbse-common-bot")
async def cbse_chapterwise_data(request_data: RequestData):
    try:
        # Assuming generate_answer is an asynchronous function you've defined
        result, history,chat_title,tokens = await generate_response_cbse_common(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# college Suggest bot
@router.post("/college-suggest-bot")
async def college_suggest(request_data: RequestData):
    try:
        result, history,chat_title,tokens,related_question = await collegesuggest_bot.generate_response(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens,"related_question":related_question}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    

# Carrer Coach
@router.post("/career-coach-bot")
async def career_bot(request_data: RequestData):
    try:
        result, history,chat_title,tokens = await carrer_coach_bot.generate_response(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

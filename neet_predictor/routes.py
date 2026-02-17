from fastapi import APIRouter, HTTPException
from neet_predictor.predictor_bot import predictor_response
from tutor_bots.classes import RequestData
router = APIRouter()

# Neet predictor
@router.post("/neet-predictor-bot")
async def neet_bot(request_data: RequestData):
    try:
        # Assuming generate_answer is an asynchronous function you've defined
        result, history,chat_title,tokens = await predictor_response(request_data.message, request_data.url, request_data.history)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
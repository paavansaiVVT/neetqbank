
from topall.ai_coach.ai_coach import topall_bot
from topall.models import TopallQWeakRequest
from tutor_bots.classes import RequestData
from fastapi import APIRouter, HTTPException

router = APIRouter()
# Topall AI Coach
@router.post("/topall-bot")
async def top_all_bot(request_data: RequestData):
    try:
        result, history,chat_title,tokens = await topall_bot.generate_response(request_data)
        return {"result": result, "data": history,"chat_title":chat_title,"tokens":tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

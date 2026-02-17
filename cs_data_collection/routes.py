
from fastapi import APIRouter, HTTPException
from cs_data_collection.cs_basic_details import CollegeRequest
from cs_data_collection.cs_assigner_function import college_suggest_dc

router = APIRouter()
# College Suggestion data collection bot
@router.post("/cs-data-collection-bot")
async def cs_data_bot(request: CollegeRequest):
    try:
        result = await college_suggest_dc(request)
        return result
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    


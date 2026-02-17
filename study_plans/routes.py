from study_plans.study_plan import main,StudyPlanRequest
from study_plans.adaptive_study_plan import adaptive_main,adaptive_StudyPlanRequest
from fastapi import APIRouter

router = APIRouter()

# Study Plan
@router.post("/neet_study_plan")
async def get_study_plan(request: StudyPlanRequest):
    try:
        data, tokens = await main(request)
        return {"data": data,"tokens": tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        return {"error": str(e)}
    
# Adaptive Study Plan
@router.post("/neet_adaptive_study_plan")
async def get_adatptive_plan(request:adaptive_StudyPlanRequest):
    try:
        data, tokens = await adaptive_main(request)
        return {"data": data,"tokens": tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        return {"error": str(e)}
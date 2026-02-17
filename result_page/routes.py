# Import FastAPI from the fastapi module
from fastapi import Request
from result_page.test_analysis import single_test_analyze,overall_test_analyze
from fastapi import APIRouter

router = APIRouter()

#Single Test analysis 
@router.post("/single_test_anlaysis")
async def test_anlayzer(request: Request):
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
        response,tokens =await single_test_analyze(body_str)
        return {"response": response,"tokens": tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Overall test analysis    
@router.post("/overall_test_anlaysis")
async def all_test_anlayzer(request: Request):
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
        response,tokens =await overall_test_analyze(body_str)
        return {"response": response,"tokens": tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
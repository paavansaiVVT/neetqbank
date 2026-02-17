# Import FastAPI from the fastapi module
from fastapi import HTTPException,Request
from question_banks.question_bank import bulk_question_bank_generator
from question_banks.question_bank_variation import bulk_question_bank_generator_variation
from question_banks.question_explanation import question_explanation_generator,question_tagger,questions_QC,questions_choices_regenerate,question_tagger_topall
from question_banks.classes import QuestionBankRequest
from question_banks.classes import slug_data
from seo.app import generate_slug,generate_desc
from question_banks.topwall_questions import topwall_tag
from fastapi import APIRouter, HTTPException

router = APIRouter()



# Neet question bank
@router.post("/neet_question_bank")
async def question_bank(selected_subject,selected_chapter,selected_input, difficulty, No):
    try:    
        response,tokens =await bulk_question_bank_generator(selected_subject,selected_chapter,selected_input, difficulty, No)
        return {"tokens":tokens,"No of Mcqs":len(response),"response": response}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
    
# Neet question bank with variation
@router.post("/neet_question_bank_with_variation")
async def question_bank_variation(selected_subject,selected_chapter,selected_input,difficulty,No,year,question_id,mcq):
    try:
        No = int(No)
        response,tokens =await bulk_question_bank_generator_variation(selected_subject,selected_chapter,selected_input,difficulty,No,year,question_id,mcq)
        return {"tokens":tokens,"No of Mcqs":len(response),"response": response}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Neet question bank Explanation
@router.post("/neet_question_bank_explanation")
async def question_bank_explanation(request: Request):
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
        api_call="YES"
        response =await question_explanation_generator(body_str,api_call)
        return {"No of Mcqs":len(response),"response": response}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Question bank tagging
@router.post("/neet_question_bank_tagging")
async def question_bank_tagger(request: QuestionBankRequest):
    try:
        response =await question_tagger(request)
        return {"No of Mcqs":len(response),"response": response}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Top all Question bank tagging
@router.post("/neet_topall_question_bank_tagging")
async def question_bank_tagger(request: QuestionBankRequest):
    try:
        response =await question_tagger_topall(request)
        return {"No of Mcqs":len(response),"response": response}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Question bank options regenerate
@router.post("/neet_question_bank_options")
async def question_bank_options(request: QuestionBankRequest):
    try:
        response,explanation =await questions_choices_regenerate(request)
        return {"response": response,"explanation":explanation}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# Question bank QC
@router.post("/neet_question_bank_qc")
async def question_bank_qc(request: QuestionBankRequest):
    try:
        response =await questions_QC(request)
        return {"response": response}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# TopAll Tagging questions
@router.post("/topwall-tag-mcqs")
async def topall_mcqs_tagger(request_data: QuestionBankRequest):
    try:
        result = await topwall_tag.topall_question_tagger(request_data)
        return {"result": result}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Slug generator
@router.post("/slug")
async def slugs_gen(request: slug_data):
    try:
        response,tokens =await generate_slug(request)
        return {"response": response,"tokens": tokens}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
    
# slug description generator    
@router.post("/seo_description")
async def slugs_gen(request: slug_data):
    try:
        response,tokens =await generate_desc(request)
        return {"response": response,"tokens": tokens,"input":request}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
    

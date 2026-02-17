import time
from cs_qbanks import cs_classes, cs_question_bank,question__improver
from fastapi import APIRouter

router = APIRouter()    
    
@router.post("/neet_cs_question_bank")
async def question_bank(request: cs_classes.QuestionRequest):
    try:
        start_time = time.time()
        response, tokens, total_questions, db_report = await cs_question_bank.question_banks.cs_question_bank_generator(table_name=cs_classes.cs_MCQData, request=request)
        print(f"Time taken for Question Generation: {time.time()-start_time}")
        #return {"response":response}
        return {True}
    except Exception as e:
        print(f"Error occurred: {e}")
        return {False}

@router.post("/cs_qbank_improved_question")
async def improved_question(request: cs_classes.ImprovedQuestionReq):
    try:
        start_time = time.time()
        result, tokens = await question__improver.question_refiner.question_improvement_generator(request)
        #print(f"Result: {result}")
        print(f"Time taken for Question Improvement: {time.time()-start_time}")
        return{True}
    except Exception as e:
        print(f"Error occurred: {e}")
        return {False}

@router.post("/cs_question_bank_repo")
async def question_gen_repo(request: cs_classes.TopicRequest):
    try:
        start_time = time.time()
        total_questions, total_tokens, db_report = await cs_question_bank.question_banks.assigner_function(request)
        print(f"Time taken for Question Generation: {time.time()-start_time}")
        return {"Total_questions": total_questions, "total_tokens": total_tokens, "db_report": db_report}
        #return {True}
    except Exception as e:
        print(f"Error occurred in cs_question_bank API: {e}")
        return {False}
    
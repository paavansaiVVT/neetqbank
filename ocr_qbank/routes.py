
from fastapi import APIRouter
from ocr_qbank import classes, refine_question
import time
router = APIRouter()


@router.post("/pdf_question_bank")
async def question_refine(request: classes.RefineMCQs):
    try:
        start_time = time.time()
        total_questions, total_tokens, no_of_question = await refine_question.refine_function.assigner_function(request)
        print(f"Time taken for Question Generation: {time.time()-start_time}")
        return {"total_questions_processed": total_questions, "total_tokens_info": total_tokens, "num_questions_extracted": no_of_question}
        #return {True}
    except Exception as e:
        print(f"Error occurred in cs_question_bank API: {e}")
        return {False}
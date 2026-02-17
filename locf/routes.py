from fastapi import APIRouter
from locf.data_extraction.core import data_extract
from locf.data_extraction.classes import file_request
import time
import asyncio
import logging
from locf.qbanks import classes, core, pro_content_md, db
from locf.s_question_paper import core as s_ocr_core, classes as s_ocr_classes
from locf.s_paper_correction import core as s_pc_core, classes as s_pc_classes
from locf.c_question_paper import core as c_ocr_core, classes as c_ocr_classes
from locf.c_paper_correction import core as c_pc_core, classes as c_pc_classes
router = APIRouter()

@router.post("/locf/extract_pdf_content")
async def locf(request: file_request):
    try:
        response = await data_extract.extract_content(request)
        # response = await data_extract.language_process(request)
        return {"response": response}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
    
@router.post("/locf/program_pdf_content")
async def locf_program_con(request: classes.pro_file_request):
    try:
        pro_id= await pro_content_md.program_content.generate_md_format(request)
        return {"program_content_id": pro_id}
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
    
@router.post("/locf/question_bank")
async def locf_question_bank(request: classes.QuestionRequest):
    try:
        start_time = time.time()
        response, tokens, total_questions, db_report = await core.question_banks.question_bank_organizer(table_name=classes.MCQData, request=request)
        #print(f"Time taken for Question Generation: {time.time()-start_time}")
        # return {"response":response, "tokens":tokens, "total_questions":total_questions, "db_report":db_report}
        return True
    except Exception as e:
        print(f"Error occurred: {e}")
        return False
    
@router.post("/locf/pre_generator_qbanks")
async def locf_pre_generator_qbanks(request: classes.TopicQuestionrequest):
    try:
        start_time = time.time()
        response= await core.question_banks.pre_question_bank_organizer(request=request)
        #print(f"Time taken for Pre Question Generation: {time.time()-start_time}")
        #return {"response":response}
        return True
    except Exception as e:
        print(f"Error occurred: {e}")
        return False
    
@router.post("/locf/school_question_paper_ocr")
async def ocr_question_paper(request: s_ocr_classes.QuestionPaperRequest):
    try:
        start_time = time.time()
        #response, image_ulrs, gen_response, md_results= await ocr_core.ocr_instance.ocr_process(request=request)
        response = await s_ocr_core.ocr_instance.question_scheme(request=request)
        print(f"Time taken for OCR Question Paper: {time.time()-start_time}")
        # return {"response":response}
        return True
    except Exception as e:
        print(f"Error occurred: {e}")
        return False
    
@router.post("/locf/school_answer_paper_ocr")
async def ocr_question_paper(request: s_pc_classes.AnswerSheetRequest):
    try:
        start_time = time.time()
        response, total_tokens= await s_pc_core.answer_pc_instance.assigner_function(request=request)
        print(f"Time taken for OCR Answer Paper: {time.time()-start_time}")
        # return response
        return True
    except asyncio.CancelledError:
        logging.warning("Answer paper OCR request was cancelled during shutdown")
        return False
    except Exception as e:
        print(f"Error occurred: {e}")
        return False

@router.post("/locf/college_question_paper_ocr")
async def ocr_question_paper(request: c_ocr_classes.QuestionPaperRequest):
    try:
        start_time = time.time()
        #response, image_ulrs, gen_response, md_results= await ocr_core.ocr_instance.ocr_process(request=request)
        response = await c_ocr_core.ocr_instance.question_scheme(request=request)
        print(f"Time taken for OCR Question Paper: {time.time()-start_time}")
        # return {"response":response}
        return True
    except Exception as e:
        print(f"Error occurred: {e}")
        return False
    
@router.post("/locf/college_answer_paper_ocr")
async def ocr_question_paper(request: c_pc_classes.AnswerSheetRequest):
    try:
        start_time = time.time()
        response, total_tokens= await c_pc_core.answer_pc_instance.assigner_function(request=request)
        print(f"Time taken for OCR Answer Paper: {time.time()-start_time}")
        # return response
        return True
    except asyncio.CancelledError:
        logging.warning("Answer paper OCR request was cancelled during shutdown")
        return False
    except Exception as e:
        print(f"Error occurred: {e}")
        return False

@router.post("/article/art_mcq_generator")
async def locf_question_bank(request: classes.QuestionRequest):
    try:
        response, tokens, total_questions, db_report = await core.question_banks.question_bank_organizer(table_name=None, request=request)
        # return {"response":response, "tokens":tokens}
        return True
    except Exception as e:
        print(f"Error occurred: {e}")
        return False
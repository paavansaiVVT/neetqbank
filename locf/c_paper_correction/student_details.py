import google.generativeai as genai
import json, os, requests, logging
from typing import Dict
from io import BytesIO
from locf.c_paper_correction.prompts import detail_exaction_prompt
from locf.c_paper_correction.helper_function import processing_answer_sheet
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
def extract_student_info(pdf_url):
    """Extract student information directly from PDF URL without downloading to disk"""
    total_tokens: Dict[str, int] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            }
    genai.configure(api_key=GOOGLE_API_KEY)
    try:
        #logging.info("Getting student details...")
        response = requests.get(pdf_url, stream=True, timeout=30)
        response.raise_for_status()
        pdf_buffer = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            pdf_buffer.write(chunk)
        pdf_buffer.seek(0)
        pdf_data = pdf_buffer.getvalue()
        pdf_file = genai.upload_file(
            BytesIO(pdf_data),
            mime_type="application/pdf",
            display_name="exam_sheet.pdf"
        )
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        ai_response = model.generate_content([detail_exaction_prompt, pdf_file])
        json_start = ai_response.text.find('{')
        json_end = ai_response.text.rfind('}') + 1
        json_text = ai_response.text[json_start:json_end]
        student_info = json.loads(json_text)
        total_tokens = processing_answer_sheet._extract_tokens(response)
        return student_info, total_tokens
    except requests.RequestException as e:
        logging.info(f":x: Error streaming PDF (extract_student_info): {e}")
        return None, total_tokens
    except json.JSONDecodeError as e:
        logging.info(f":x: Error parsing JSON response (extract_student_info): {e}")
        return None, total_tokens
    except Exception as e:
        logging.info(f":x: Error extracting info (extract_student_info): {e}")
        return None, total_tokens
    finally:
        try:
            pdf_buffer.close()
            genai.delete_file(pdf_file.name)
            logging.info(":wastebasket: Memory cleanup completed")
        except:
            pass

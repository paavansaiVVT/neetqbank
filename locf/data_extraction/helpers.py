import google.generativeai as genai
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import requests
from typing import Optional, Dict
import httpx
import logging

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

http_client = httpx.Client(timeout=60)
def answer_sheet_extraction(pdf_url: str, system_prompt: str) -> Optional[str]:
        total_tokens: Dict[str, int] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            }
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-pro")
            session = requests.Session()
            retries = Retry(total=5,
                            backoff_factor=1,
                            status_forcelist=[500, 502, 503, 504, 429],
                            allowed_methods=["GET"])
            session.mount("https://", HTTPAdapter(max_retries=retries))

            try:
                response = session.get(pdf_url, timeout=30)
                response.raise_for_status()
                pdf_data = response.content
            except requests.exceptions.RequestException as e:
                raise ValueError(f"Failed to download PDF from {pdf_url} after retries: {e}")

            prompt_content = [{"mime_type": "application/pdf", "data": pdf_data},system_prompt]
            response = model.generate_content(prompt_content,generation_config={"temperature": 0})
            md_text = response.text or ""
            #total_tokens = processing_answer_sheet._extract_tokens(response)
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                prompt_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count
                total_token = prompt_tokens + output_tokens
                total_tokens["total_input_tokens"] += prompt_tokens
                total_tokens["total_output_tokens"] += output_tokens
                total_tokens["total_tokens"] += total_token
                #print(f"Token usage: Prompt tokens: {prompt_tokens}, Output tokens: {output_tokens}, Total tokens: {total_token}")

            return md_text

        except Exception as e:
            logging.error(f"Error in answer_sheet_extraction: {e}")
            return None

def get_file_size(url):
    try:
        response = requests.head(url, allow_redirects=True)
        response = requests.head(url)
        if response.status_code == 200 and 'Content-Length' in response.headers:
            file_size = int(response.headers['Content-Length'])      
        else:
            print("Could not retrieve file size")
            file_size=0
        return file_size
    except requests.RequestException as e:
        print(f"Error fetching file size: {e}")
        return 0
    
# def saggreagate(maps):
#   d=["TOTAL","AVERAGE"]
#   commons_items=[]
#   core_items=[]
#   for x, y in maps.items():  # <-- Safe copy
#       if x in d:
#           commons_items.append({x: y})
#       else:
#           core_items.append({x:y})
#   return commons_items,core_items


def saggreagate(maps):
    d = ["TOTAL", "AVERAGE"]
    commons_items = {}
    core_items = {}

    for key, value in maps.items():
        if key in d:
            commons_items[key] = value
        else:
            core_items[key] = value

    return commons_items, core_items

def cal_total_and_average(result):
    try:
        mapping_with_programme_outcomes = result["mapping_with_programme_outcomes"]

        # Remove existing TOTAL and AVERAGE keys if present
        mapping_with_programme_outcomes.pop("TOTAL", None)
        mapping_with_programme_outcomes.pop("AVERAGE", None)

        # Initialize total and average
        total = {}
        average = {}
        count = len(mapping_with_programme_outcomes)  # Number of COs

        # Sum PO values
        for co, po_values in mapping_with_programme_outcomes.items():
            for po, val in po_values.items():
                if isinstance(val, (int, float)):  # Only sum numeric values
                    total[po] = total.get(po, 0) + val

        # Calculate average
        for po, val in total.items():
            average[po] = round(val / count, 1) if count else 0

        # Add recalculated TOTAL and AVERAGE
        mapping_with_programme_outcomes["TOTAL"] = total
        mapping_with_programme_outcomes["AVERAGE"] = average
        return result
    
    except Exception as e:
        print(f"Error calculating total and average: {e}")
        return result

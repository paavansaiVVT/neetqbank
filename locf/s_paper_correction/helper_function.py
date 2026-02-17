import os, re, json, boto3, requests, fitz, io, httpx, logging, uuid
from mistralai import Mistral, DocumentURLChunk
from typing import Union, List, Optional, Tuple, Any, Dict, Iterable
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv
from locf.s_paper_correction import classes, db, prompts
from statistics import mean, median
from math import sqrt
import google.generativeai as genai
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()
API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("MISTRAL_API_KEY env var is missing.")
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

http_client = httpx.Client(timeout=60)

client = Mistral(
    api_key=API_KEY,
    server_url="https://api.mistral.ai",
)

s3 = boto3.client("s3",
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)

AWS_S3_REGION = os.getenv("AWS_S3_REGION")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_S3_SECRET_ACCESS_KEY = os.getenv("AWS_S3_SECRET_ACCESS_KEY")
AWS_S3_ACCESS_KEY_ID = os.getenv("AWS_S3_ACCESS_KEY_ID")

class helper_function:
    def __init__(self):
        self.parser = JsonOutputParser()
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_S3_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_S3_SECRET_ACCESS_KEY,
            region_name=AWS_S3_REGION
        )
    def build_user_message_dict(self,
        message: Optional[str] = None,
        urls: Optional[Union[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        if not message and not urls:
            raise ValueError("Either message or urls must be provided.")

        if isinstance(urls, str):
            urls = [urls]

        parts = []
        if message:
            parts.append({"type": "text", "text": message})

        if urls:
            for u in urls:
                parts.append({"type": "image_url", "image_url": {"url": u}})

        # Role + content structure
        return [{"role": "user", "content": parts}]
    def answer_sheet_content(self, pdf_link: str) -> Optional[str]:
        try:
            # Validate that this looks like a URL
            if not (pdf_link.startswith("http://") or pdf_link.startswith("https://")):
                raise ValueError(f"Invalid PDF URL: {pdf_link}")

            resp = client.ocr.process(
                model="mistral-ocr-latest",
                document=DocumentURLChunk(document_url=pdf_link),
                include_image_base64=True,
            )

            pages = getattr(resp, "pages", None)
            if not pages:
                print("OCR returned no pages.")
                return ""

            in_text_content = "\n\n--- PAGE BREAK ---\n\n".join(
                getattr(page, "markdown", "") for page in pages if getattr(page, "markdown", "")
            )
            all_text_content = f"'{in_text_content}' This is my answer sheet text. and Correct the answer sheet according to this images. If any diagram, chart, or chemical structure is present in the answer sheet image, describe it in `student_answer_text`."
            return all_text_content

        except httpx.HTTPStatusError as e:
            # If you used client with httpx and raise_for_status elsewhere
            status = e.response.status_code if e.response else "unknown"
            body = e.response.text if e.response else ""
            print(f"HTTPStatusError: {status} body={body[:500]}")
            if status == 401:
                print(
                    "401 Unauthorized. Check:\n"
                    "- API key value (print len, no quotes/newlines)\n"
                    "- Billing/activation for your Mistral account\n"
                    "- Correct base URL (https://api.mistral.ai)\n"
                    "- No proxy stripping Authorization header"
                )
            
            all_text_content = "Analyze the provided images carefully and correct the answer sheet according to this images. If any diagram, chart, or chemical structure is present in the answer sheet image, describe it in `student_answer_text`."
            return all_text_content

        except httpx.HTTPError as e:
            print(f"Network error talking to Mistral API: {e}")
            return None

        except Exception as e:
            # This will also catch SDK-level 401 errors that surface as generic Exceptions
            msg = str(e)
            print(f"Error extracting text from PDF: {msg}")
            if "401" in msg or "Unauthorized" in msg:
                print(
                    "Likely authentication: verify MISTRAL_API_KEY and account status."
                )
            return None

    def fallback_extract_when_json_fails(self, result_exp: str) -> Tuple[Optional[Dict], Optional[str], Optional[List]]:
        """
        Emergency extraction when json.loads() fails.
        Use this in your except block.
        """
        try:
            cleaned = result_exp.strip().strip('"""').strip()
            
            # Extract student_details
            student_details = {}
            details_match = re.search(r'"student_details"\s*:\s*\{([^}]+)\}', cleaned, re.DOTALL)
            if details_match:
                details_content = details_match.group(1)
                fields = {
                    'date': r'"date"\s*:\s*"([^"]*)"',
                    'name': r'"name"\s*:\s*"([^"]*)"',
                    'class': r'"class"\s*:\s*(null|"[^"]*")',
                    'phase': r'"phase"\s*:\s*"([^"]*)"',
                    'rollno': r'"rollno"\s*:\s*"([^"]*)"',
                    'section': r'"section"\s*:\s*"([^"]*)"',
                    'subject': r'"subject"\s*:\s*"([^"]*)"'
                }
                for field, pattern in fields.items():
                    match = re.search(pattern, details_content)
                    if match:
                        value = match.group(1)
                        student_details[field] = None if value == 'null' else value
            
            # Extract student_answer_content
            content_patterns = [
                r'"student_answer_content"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,',
                r'"student_answer_content"\s*:\s*"((?:[^"\\]|\\.)*)"'
            ]
            student_answer_content = None
            for pattern in content_patterns:
                match = re.search(pattern, cleaned, re.DOTALL)
                if match:
                    content = match.group(1)
                    student_answer_content = content.replace('\\"', '"').replace('\\n', '\n')
                    break
            
            # Extract list_of_pages
            pages_match = re.search(r'"list_of_pages"\s*:\s*\[([^\]]*)\]', cleaned)
            list_of_pages = None
            if pages_match:
                try:
                    list_of_pages = json.loads('[' + pages_match.group(1) + ']')
                except:
                    numbers = re.findall(r'\d+', pages_match.group(1))
                    list_of_pages = [int(num) for num in numbers]
            
            return (student_details if student_details else None, student_answer_content, list_of_pages)
        except:
            return None, None, None
        
    def answer_sheet_extraction(self, pdf_url: str, system_prompt: str) -> Optional[str]:
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

            return md_text, total_tokens

        except Exception as e:
            logging.error(f"Error in answer_sheet_extraction: {e}")
            return None, total_tokens
        
    def answer_extraction_logic(self, pdf_url: str) -> Optional[str]:
        try:
            result_ext, total_tokens = self.answer_sheet_extraction(pdf_url, system_prompt=prompts.extraction_prompt_v2)
            try:
                ext_parsed_json=self.parser.parse(result_ext)
                sdnt_details=ext_parsed_json.get("student_details")
                student_answer_content=ext_parsed_json.get("student_answer_content")
                list_of_pages=ext_parsed_json.get("list_of_pages")
            except:
                sdnt_details, student_answer_content, list_of_pages = self.fallback_extract_when_json_fails(result_ext)
            return sdnt_details, student_answer_content, list_of_pages, total_tokens
        except Exception as e:
            logging.error(f"Error in answer_extraction_logic: {e}")
            return None, None, None, None
            
    def _parse_qrange(self, questions_range: str) -> Tuple[int, int]:
        """Parse question range string and return (lo, hi) tuple."""
        try:
            # Handle different separators: dash, "to", space
            if " to " in questions_range:
                parts = questions_range.split(" to ")
            elif "-" in questions_range:
                parts = questions_range.split("-")
            elif "to" in questions_range:
                parts = questions_range.split("to")
            else:
                # Single number
                num = int(questions_range.strip())
                return num, num
            
            # Extract and convert to integers
            lo = int(parts[0].strip())
            hi = int(parts[1].strip())
            return lo, hi
            
        except (ValueError, IndexError) as e:
            logging.error(f"Error parsing _parse_qrange '{questions_range}': {e}")
            return 0, 0  # Return default range


    def _build_q_to_section_map(self, instruction_set: dict) -> Dict[str, Tuple[str, int]]:
        try:
            mapping: Dict[str, Tuple[str, int]] = {}
            for dist in instruction_set.get("marks_distribution", []):
                sec = dist["section"]
                marks_each = int(dist["marks_each"])
                
                # Parse the range with better error handling
                try:
                    lo, hi = self._parse_qrange(dist["questions_range"])
                    #logging.info(f"Parsed range: {lo}-{hi} for section {sec}")
                    
                    for q in range(lo, hi + 1):
                        mapping[str(q)] = (sec, marks_each)
                        
                except Exception as parse_error:
                    logging.error(f"Failed to parse range '{dist['questions_range']}': {parse_error}")
                    continue
                    
            #logging.info(f"Final mapping created with {len(mapping)} questions")
            return mapping
            
        except Exception as e:
            logging.error(f"Error in _build_q_to_section_map: {e}")
            return {}


    def _apply_narrow_mode(self, instruction_set: Union[dict, str], target_qs: List[Union[int, str]]) -> Tuple[dict, int]:
        try:
            # Ensure instruction_set is a dict
            if isinstance(instruction_set, str):
                instruction_set = json.loads(instruction_set)

            tqs = [str(q) for q in target_qs]

            # Deep copy
            patched = json.loads(json.dumps(instruction_set))
            patched["target_question_numbers"] = tqs

            q2sec = self._build_q_to_section_map(patched)
            if target_qs is None:
                narrow_total = int(instruction_set.get("exam_metadata", {}).get("total_marks", 0)) or \
                                sum(int(d.get("marks_each", 0)) *
                                    (int(d["questions_range"].split("-")[1]) - int(d["questions_range"].split("-")[0]) + 1)
                                    for d in instruction_set.get("marks_distribution", []))
            else:
                narrow_total = sum(q2sec[q][1] for q in tqs if q in q2sec)
            return patched, narrow_total

        except Exception as e:
            logging.error(f"Error in _apply_narrow_mode: {e}")
            return {}, 0
        
    def pick_questions(self, raw_data: List[Dict[str, Any]], question_list: List[int]) -> Tuple[List[Dict[str, Any]], List[int]]:
        def to_num(v):
            try:
                return int(str(v).strip())
            except Exception:
                return None

        # Index by question_number (supports int or str in the data)
        index = {to_num(q.get("question_number")): q for q in raw_data if "question_number" in q}

        # Preserve the order of question_list
        selected = [index[n] for n in question_list if n in index]
        missing  = [n for n in question_list if n not in index]
        return selected, missing
    
    def strip_urls_from_output(self, objs):
        url_re = re.compile(r"https?://\S+")
        for obj in objs:
            for k in ("student_answer_text", "question_text", "actual_answer", "feedback"):
                if k in obj and isinstance(obj[k], str):
                    obj[k] = url_re.sub("[image omitted]", obj[k])
        return objs
    
    def to_int(self, v):
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return None
        
    # def split_pdf_and_upload_to_s3(self, pdf_url: str, s3_prefix: str = '') -> List[str]:
    #     """
    #     Downloads a PDF, splits it into PNG images, uploads them to S3,
    #     and returns a list of their URLs.
    #     """
    #     logging.info(f"--- Starting PDF to S3 Process for: {pdf_url} ---")

    #     try:
    #         # 1. Download PDF
    #         #logging.info("-> Downloading PDF...")
    #         response = requests.get(pdf_url, stream=True)
    #         response.raise_for_status()
    #         pdf_bytes = response.content
    #         #logging.info("-> PDF downloaded successfully.")
    #     except requests.exceptions.RequestException as e:
    #         logging.error(f"Error: Failed to download PDF. {e}")
    #         return []

    #     s3_urls = []
    #     try:
    #         unique_id = str(uuid.uuid4())
    #         pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    #         logging.info(f"-> PDF has {len(pdf_document)} pages.")
    #         base_filename = os.path.splitext(os.path.basename(pdf_url.split('?')[0]))[0]

    #         if s3_prefix and not s3_prefix.endswith('/'):
    #             s3_prefix += '/'

    #         for i, page in enumerate(pdf_document):
    #             page_num = i + 1
    #             s3_object_key = f"{s3_prefix}{unique_id}_page_{page_num}.png"

    #             pix = page.get_pixmap(dpi=200)
    #             img_bytes = pix.tobytes("png")

    #             try:
    #                 self.s3_client.upload_fileobj(
    #                     io.BytesIO(img_bytes),
    #                     AWS_S3_BUCKET_NAME,
    #                     s3_object_key,
    #                     ExtraArgs={'ContentType': 'image/png'}
    #                 )

    #                 s3_url = f"https://{AWS_S3_BUCKET_NAME}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_object_key}"
    #                 s3_urls.append(s3_url)
    #                 #print(f"  - Page {page_num} uploaded successfully.")

    #             except Exception as e:
    #                 logging.error(f"  - Error uploading page {page_num}: {e}")

    #         #print(f"\n-> All pages processed. Generated S3 URLs: in total {len(s3_urls)}")
    #         # for url in s3_urls:
    #         #     print(url)

    #         return s3_urls
    #     except Exception as e:
    #         print(f"An error occurred during PDF processing: {e}")
    #         return []
    
    def split_pdf_and_upload_to_s3(self, pdf_url: str, s3_prefix: str = '', pages_list: List[int] = []) -> List[str]:
        """
        Downloads a PDF, splits it into PNG images, uploads them to S3,
        and returns a list of their URLs.
        """
        logging.info(f"--- Starting PDF to S3 Process for: {pdf_url} ---")

        try:
            # 1. Download PDF
            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()
            pdf_bytes = response.content
        except requests.exceptions.RequestException as e:
            logging.error(f"Error: Failed to download PDF. {e}")
            return []

        s3_urls = []
        try:
            unique_id = str(uuid.uuid4())
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            logging.info(f"-> PDF has {len(pdf_document)} pages.")
            
            if s3_prefix and not s3_prefix.endswith('/'):
                s3_prefix += '/'

            # Process all pages if pages_list is empty, otherwise process only specified pages
            pages_to_process = pages_list if pages_list else list(range(1, len(pdf_document) + 1))
            
            for page_num in pages_to_process:
                if 1 <= page_num <= len(pdf_document):  # Validate page number
                    page = pdf_document.load_page(page_num - 1)  # PyMuPDF uses 0-based indexing
                    s3_object_key = f"{s3_prefix}{unique_id}_page_{page_num}.png"

                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("png")

                    try:
                        self.s3_client.upload_fileobj(
                            io.BytesIO(img_bytes),
                            AWS_S3_BUCKET_NAME,
                            s3_object_key,
                            ExtraArgs={'ContentType': 'image/png'}
                        )

                        s3_url = f"https://{AWS_S3_BUCKET_NAME}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_object_key}"
                        s3_urls.append(s3_url)
                    except Exception as e:
                        logging.error(f"  - Error uploading page {page_num}: {e}")
                else:
                    logging.warning(f"Page {page_num} is out of range")

            logging.info(f"\n-> All pages processed. Generated S3 URLs: in total {len(s3_urls)}")
            return s3_urls
            
        except Exception as e:
            logging.error(f"An error occurred during PDF processing: {e}")
            return []

        
    def get_no_of_questions(self, data):
        try:
            if isinstance(data, dict):
                # If data is already a dictionary, access directly
                num_of_questions = data['exam_metadata']['total_no_of_questions']
                return num_of_questions
            else:
                # If data is a string, extract the JSON part
                json_start = data.find('{')
                json_end = data.rfind('}')

                if json_start != -1 and json_end != -1:
                    # Extract the JSON string
                    json_string = data[json_start : json_end + 1]
                    result = json.loads(json_string)
                    num_of_questions = result['exam_metadata']['total_no_of_questions']
                    return num_of_questions
                else:
                    print("Could not find valid JSON within the extracted content.")
                    result = None

        except json.JSONDecodeError as e:
            print(f"JSON decoding error: {e}")
            result = None
        except KeyError as e:
            print(f"KeyError: Missing expected key {e}")
            result = None
        except Exception as e:
            print(f"An error occurred: {e}")
            result = None

        
    async def prepare_question_content(self, request: classes.AnswerSheetRequest) -> str:
        """Prepare question content processing for the AI model."""
        try:
            instruction_set, md_list, subject, standard = await db.fetch_question_paper_data(request)

            # Handle cases where md_list is not properly formatted
            try:
                md_list = json.loads(md_list)
            except (TypeError, json.JSONDecodeError) as e:
                print(f"Error loading md_list: {e}")
                md_list = []  # Fallback to an empty list if parsing fails
            
            qp_md = "\n\n".join([result["content"] for result in md_list if "content" in result])
            
            # Safely get the question count
            questions_count = self.get_no_of_questions(instruction_set)
            if questions_count is None or questions_count == 0:
                print("Warning: Invalid or zero questions count.")
                questions_count = 0  # Fallback to 0 if count is invalid
            
            #print(f"Total number of questions expected: {questions_count}")
            return instruction_set, qp_md, questions_count, subject, standard

        except Exception as e:
            print(f"Error preparing question content: {e}")
            return None, None, 0, None, None  # Ensure consistent return values
        
    def extract_number(self, q: Any) -> str:
        """Return only the first numeric run from a question number like '26b' or '34 OR'."""
        if q is None:
            return ""
        m = re.search(r"\d+", str(q))
        return m.group(0) if m else ""

    def iter_questions(self, obj: Any):
        """Yield all question dicts, even if nested inside lists."""
        if isinstance(obj, dict):
            if "question_no" in obj:  # looks like a question dict
                yield obj
            # but also walk through any nested lists/dicts
            for v in obj.values():
                yield from self.iter_questions(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from self.iter_questions(item)

    def build_question_index(self, paper: Dict) -> Dict[str, Dict]:
        """
        Build an index: { '27': <section_dict>, '28': <section_dict>, ... }
        where section_dict is the section object that contains that question.
        """
        index = {}
        for section in paper.get("sections", []):
            for q in self.iter_questions(section.get("questions", [])):
                num = self.extract_number(q.get("question_no"))
                if num:
                    index[num] = section
        return index

    def find_section_for_question(self, paper: Dict, question_number: Any) -> Optional[Dict]:
        """
        Return the section dict (e.g., {'section_name': 'Section-D', ...})
        that contains the given question number. If not found, returns None.
        """
        target = self.extract_number(question_number)
        if not target:
            return None

        index = self.build_question_index(paper)
        return index.get(target)

class processing_paper:
    def __init__(self):
        self.CONF_SCALE_MAX = 10
    def extract_qnumber(self, qnum: Any) -> str:
        """
        Extract only the digits from question_number.
        Examples:
        '26b' -> '26' ; '34 OR' -> '34' ; 'Q12.1' -> '12'
        """
        s = "" if qnum is None else str(qnum)
        m = re.search(r"\d+", s)
        return m.group(0) if m else "0"

    def _flatten(self, items: Iterable[Any]) -> List[Any]:
        """Flatten one level of nested lists (if any)."""
        out: List[Any] = []
        for it in items:
            if isinstance(it, list):
                out.extend(it)
            else:
                out.append(it)
        return out

    def preparing_answersheet(self, answer_sheet_content: Union[str, List[Any]]) -> List[Dict[str, Any]]:
        """
        Normalize a possibly nested/mixed collection into a list of dicts
        with 'question_number' cleaned to digits only.
        - Accepts: JSON string, list of dicts, list of lists, mixed.
        - Skips items without 'question_number'.
        """
        try:
            # If it's a JSON string, parse it.
            if isinstance(answer_sheet_content, str):
                import json
                answer_sheet_content = json.loads(answer_sheet_content)

            # If top-level is not a list, wrap it.
            if not isinstance(answer_sheet_content, list):
                answer_sheet_content = [answer_sheet_content]

            # Flatten one level if there are nested lists
            items = self._flatten(answer_sheet_content)

            answer_sheet: List[Dict[str, Any]] = []
            for content in items:
                if isinstance(content, dict):
                    if "question_number" in content:
                        q_no = self.extract_qnumber(content["question_number"])
                        # Create a shallow copy so we don't mutate caller's object
                        fixed = {**content, "question_number": q_no}
                        answer_sheet.append(fixed)
                    else:
                        # Optional: keep dicts that lack question_number
                        answer_sheet.append(content)
                else:
                    # Not a dict (e.g., stray string/int/list) -> skip or log
                    # print(f"Skipping non-dict item: {content!r}")
                    continue

            return answer_sheet

        except Exception as e:
            # Bubble the error with context instead of returning raw input
            raise RuntimeError(f"preparing_answersheet failed: {e}") from e
    
    def _extract_tokens(self, message) -> Dict[str, int]:
        """Return a unified token dict for an LLM message across providers. Tries usage_metadata, response_metadata, and additional_kwargs."""
        out = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

        try:
            um = getattr(message, "usage_metadata", None)
            if isinstance(um, dict):
                out["total_input_tokens"] += int(um.get("input_tokens") or um.get("prompt_tokens") or um.get("promptTokenCount") or 0)
                out["total_output_tokens"] += int(um.get("output_tokens") or um.get("completion_tokens") or um.get("candidatesTokenCount") or 0)
                out["total_tokens"]     += int(um.get("total_tokens") or um.get("totalTokenCount") or 0)

            # 2) Provider-specific data under response_metadata
            rm = getattr(message, "response_metadata", None) or {}
            if isinstance(rm, dict):
                tok = rm.get("token_usage") or rm.get("usage_metadata") or rm.get("usage") or {}
                out["total_input_tokens"] += int(tok.get("prompt_tokens") or tok.get("input_tokens") or tok.get("promptTokenCount") or 0)
                out["total_output_tokens"] += int(tok.get("completion_tokens") or tok.get("output_tokens") or tok.get("candidatesTokenCount") or 0)
                ttl = int(tok.get("total_tokens") or tok.get("totalTokenCount") or 0)
                if ttl:
                    out["total_tokens"] += ttl

            # 3) Sometimes tucked in additional_kwargs
            ak = getattr(message, "additional_kwargs", None) or {}
            if isinstance(ak, dict):
                um2 = ak.get("usage") or ak.get("usage_metadata") or ak.get("usageMetadata") or {}
                out["total_input_tokens"] += int(um2.get("prompt_tokens") or um2.get("input_tokens") or um2.get("promptTokenCount") or 0)
                out["total_output_tokens"] += int(um2.get("completion_tokens") or um2.get("output_tokens") or um2.get("candidatesTokenCount") or 0)
                out["total_tokens"]        += int(um2.get("total_tokens") or um2.get("totalTokenCount") or 0)
        except Exception:
            pass

        if out["total_tokens"] == 0:
            out["total_tokens"] = out["total_input_tokens"] + out["total_output_tokens"]
        return out    
    def map_ques_ids(self, id_list, qa_list):
        """
        id_list: [{"question_number": 1, "ques_id": 1}, ...]
        qa_list: [{"question_number": "1", "section": "A", ...}, ...]
        """
        # Build lookup dict: int(question_number) -> ques_id
        lookup = {}
        for item in id_list:
            num = int(item["question_number"])  # works for int or str
            lookup[num] = item["ques_id"]

        # Attach ques_id to qa_list
        out = []
        for row in qa_list:
            qnum = int(row["question_number"])   # force int always
            row["question_number"] = qnum        # overwrite with int
            row["ques_id"] = lookup.get(qnum)    # fetch ques_id or None
            out.append(row)
        return out
    
    def merge_answer_with_question(self, answer_sheet_list, question_paper_list):
        try:      
            merged_list = []
            # Create dictionaries for easier lookup by question_number
            answer_sheet_dict = {int(item['question_number']): item for item in answer_sheet_list if 'question_number' in item}
            question_paper_dict = {item['question_number']: item for item in question_paper_list if 'question_number' in item}

            # Iterate through the question paper questions and merge with corresponding answers
            for q_num, q_data in question_paper_dict.items():
                if q_num in answer_sheet_dict:
                    # Merge dictionaries, with answer_sheet_dict values overriding question_paper_dict if keys are the same
                    merged_list.append({**q_data, **answer_sheet_dict[q_num]})
                else:
                    # If no answer found, just add the question paper data
                    merged_list.append(q_data)
            return merged_list
        except Exception as e:
            logging.error(f"Error in merge_answer_with_question: {e}")
            return None
    
    def keys_check(self, response):
        try:
            passed_item=[]
            for entry in response:
                try:
                    # Basic presence check (optional but helpful)
                    missing = [k for k in classes.required_items if k not in entry]
                    if missing:
                        print(f"Warning: missing keys {missing} in entry with question_number={entry.get('question_number')}")
                        continue
                    passed_item.append(entry)
                except Exception as e:
                    print(f"Error keys_check (question_number={entry.get('question_number')}): {e}")
                    continue
            return passed_item
        except Exception as e:
            logging.error(f"Error in prepare_question_content: {e}")
            return response
        
    def result_analysis(self, valit_result):
        try:
                
            def pct(numerator, denominator):
                return (numerator / denominator) * 100.0 if denominator else 0.0

            def pearson(xs, ys):
                n = len(xs)
                if n < 2:
                    return None
                mx, my = mean(xs), mean(ys)
                num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                denx = sqrt(sum((x - mx) ** 2 for x in xs))
                deny = sqrt(sum((y - my) ** 2 for y in ys))
                if denx == 0 or deny == 0:
                    return None
                return num / (denx * deny)

            # --------------------------
            # Parse and analyze
            # --------------------------

            total_max_marks = 0
            total_awarded_marks = 0
            per_q = []  # per-question analysis rows
            sum_conf_pct_raw = 0.0 

            for r in valit_result:
                qn = str(r.get("question_number"))
                mm = float(r.get("maximum_marks", 0))
                ma = float(r.get("marks_awarded", 0))
                cl_raw = float(r.get("confident_level", 0))

                score_pct = pct(ma, mm)
                conf_pct = pct(cl_raw, self.CONF_SCALE_MAX)
                sum_conf_pct_raw += conf_pct
                delta = round(conf_pct - score_pct, 2)

                per_q.append({
                    "question_number": qn,
                    "maximum_marks": mm,
                    "marks_awarded": ma,
                    "score_pct": round(score_pct, 2),
                    "confident_level": cl_raw,
                    "confidence_pct": round(conf_pct, 2),
                    "confidence_minus_score_pct": delta
                })

                total_max_marks += mm
                total_awarded_marks += ma

            # Aggregate metrics
            overall_score_pct = round(pct(total_awarded_marks, total_max_marks), 2) if total_max_marks else 0.0
            avg_q_score_pct = round(mean([row["score_pct"] for row in per_q]) if per_q else 0.0, 2)
            avg_conf_pct = round(mean([row["confidence_pct"] for row in per_q]) if per_q else 0.0, 2)
            median_conf_pct = round(median([row["confidence_pct"] for row in per_q]) if per_q else 0.0, 2)
            sum_conf_pct = round(sum_conf_pct_raw, 2)

            # Correct/partial/incorrect buckets
            correct = sum(1 for r in per_q if r["marks_awarded"] == r["maximum_marks"] and r["maximum_marks"] > 0)
            partial = sum(1 for r in per_q if 0 < r["marks_awarded"] < r["maximum_marks"])
            incorrect = sum(1 for r in per_q if r["marks_awarded"] == 0 and r["maximum_marks"] > 0)

            # Correlation between confidence% and score%
            r_conf_score = pearson(
                [row["confidence_pct"] for row in per_q],
                [row["score_pct"] for row in per_q]
            )

            summary = {
                "total_maximum_marks": total_max_marks,
                "total_awarded_marks": total_awarded_marks,
                "overall_score_percentage": overall_score_pct,
                "average_question_score_percentage": avg_q_score_pct,
                "average_confidence_percentage": avg_conf_pct,
                "median_confidence_percentage": median_conf_pct,
                "sum_of_confidence_percentage": sum_conf_pct,
                "counts": {
                    "correct_full_marks": correct,
                    "partial": partial,
                    "incorrect": incorrect,
                    "total_questions": len(per_q),
                },
                "pearson_r_confidence_vs_score": None if r_conf_score is None else round(r_conf_score, 3),
            }

            return summary
        except Exception as e:
            logging.error(f"Error in result_analysis: {e}")
            return {}

                             
processing_answer_sheet = processing_paper()        
cls_helper_function = helper_function()
    
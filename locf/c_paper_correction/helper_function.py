import os, re, json, boto3, requests, fitz, io, httpx, logging, uuid
from mistralai import Mistral, DocumentURLChunk
from typing import Union, List, Optional, Tuple, Any, Dict, Iterable
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv
from locf.c_paper_correction import classes, db, prompts
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

class QuestionMapper:
    """Map ques_id from question database to graded results."""
    
    @staticmethod
    def map_ques_id_to_results(graded_results: List[Dict], question_data: List[Dict]) -> List[Dict]:
        """
        Map ques_id from question_data to graded_results by matching question_number and part_label.
        
        Args:
            graded_results: Results from LLM (no ques_id)
            question_data: Original question data from DB (with ques_id)
        
        Returns:
            graded_results with ques_id added
        """
        # Create lookup dict: (question_number as int, part_label) -> ques_id
        ques_id_map = {}
        for q in question_data:
            q_num = q.get("question_number")  # Already int from DB
            part_label = q.get("part_label")
            ques_id = q.get("ques_id")
            
            # Use tuple (question_number, part_label) as key
            # For single questions: (2, None)
            # For sub-questions: (1, "(a)"), (1, "(b)")
            key = (q_num, part_label)
            ques_id_map[key] = ques_id
        
        logging.info(f"📋 Created ques_id map with {len(ques_id_map)} entries")
        logging.info(f"   Map keys: {list(ques_id_map.keys())}")
        
        # Map ques_id to graded results
        mapped_count = 0
        logging.info(f"🔍 Mapping ques_id for {len(graded_results)} graded results...")
        
        for idx, result in enumerate(graded_results):
            q_num_str = result.get("question_number")
            part_label = result.get("part_label")
            
            # Convert question_number string to int for lookup
            try:
                q_num = int(q_num_str) if q_num_str else None
            except (ValueError, TypeError):
                q_num = None
                logging.error(f"❌ Invalid question_number: {q_num_str}")
            
            # Lookup ques_id
            key = (q_num, part_label)
            ques_id = ques_id_map.get(key)
            
            if ques_id is not None:
                result["ques_id"] = ques_id
                mapped_count += 1
                logging.info(f"   [{idx+1}] Q{q_num}{part_label if part_label else ''} → ques_id={ques_id} ✅")
            else:
                logging.error(f"   [{idx+1}] ❌ Could not find Q{q_num}{part_label if part_label else ''}")
                logging.error(f"       Looking for key: {key}")
                result["ques_id"] = None
        
        if mapped_count < len(graded_results):
            logging.error(f"⚠️ Only mapped {mapped_count}/{len(graded_results)} ques_id values")
            logging.error(f"   Available map keys: {list(ques_id_map.keys())}")
        else:
            logging.info(f"✅ Successfully mapped all {mapped_count} ques_id values")
        
        return graded_results

class GradingValidator:
    """Validate grading results to ensure data completeness."""
    
    @staticmethod
    def validate_grading_result(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a single grading result.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_missing_fields)
        """
        missing_fields = []
        
        for field in classes.required_grading_output_fields:
            if field in classes.optional_grading_fields:
                continue
                
            value = result.get(field)
            
            # Check if field exists and is not empty
            if value is None or value == "" or (isinstance(value, str) and value.strip() == ""):
                missing_fields.append(f"[Grading] {field}")
        
        # Validate marks logic
        max_marks = result.get("maximum_marks")
        awarded_marks = result.get("marks_awarded")
        
        if max_marks is not None and awarded_marks is not None:
            try:
                max_marks = float(max_marks)
                awarded_marks = float(awarded_marks)
                if awarded_marks > max_marks:
                    missing_fields.append("[Grading] marks_awarded > maximum_marks")
                if awarded_marks < 0:
                    missing_fields.append("[Grading] marks_awarded < 0")
            except (ValueError, TypeError):
                missing_fields.append("[Grading] marks are not numeric")
        
        # Validate confidence level
        confidence = result.get("confident_level")
        if confidence is not None:
            try:
                confidence = float(confidence)
                if not (0 <= confidence <= 10):
                    missing_fields.append("[Grading] confident_level not in range 0-10")
            except (ValueError, TypeError):
                missing_fields.append("[Grading] confident_level is not numeric")
        
        return (len(missing_fields) == 0, missing_fields)
    
    @staticmethod
    def validate_all_results(results: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict], Dict]:
        """
        Validate all grading results.
        
        Returns:
            Tuple[List[Dict], List[Dict], Dict]: (valid_results, failed_results, report)
        """
        valid_results = []
        failed_results = []
        validation_report = {
            "total_questions": len(results),
            "valid_count": 0,
            "failed_count": 0,
            "failed_question_numbers": [],
            "error_details": {}
        }
        
        for result in results:
            q_num = result.get("question_number")
            part_label = result.get("part_label")
            q_identifier = f"{q_num}{part_label if part_label else ''}"
            
            is_valid, missing = GradingValidator.validate_grading_result(result)
            
            if is_valid:
                valid_results.append(result)
                validation_report["valid_count"] += 1
            else:
                failed_results.append(result)
                validation_report["failed_count"] += 1
                validation_report["failed_question_numbers"].append(q_identifier)
                validation_report["error_details"][q_identifier] = missing
                
                logging.warning(f"❌ Question {q_identifier} FAILED validation:")
                for error in missing:
                    logging.warning(f"   ├─ {error}")
        
        return valid_results, failed_results, validation_report

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

        # Convert question_list to set for faster lookup
        target_set = set(question_list)
        
        # Filter raw_data to include ALL entries where question_number is in target_set
        # This preserves sub-questions (multiple entries with same question_number)
        selected = [q for q in raw_data if to_num(q.get("question_number")) in target_set]
        
        # Check for missing question numbers
        found_q_nums = {to_num(q.get("question_number")) for q in selected}
        missing = [n for n in set(question_list) if n not in found_q_nums]
        
        # Sort selected by question_number, then part_label for consistent order
        selected.sort(key=lambda q: (to_num(q.get("question_number")), q.get("part_label") or ""))
        
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
    
    def split_pdf_and_upload_to_s3(self, pdf_url: str, s3_prefix: str = '', pages_list: List[int] = []) -> List[str]:
        """
        Downloads a PDF, splits it into PNG images, uploads them to S3,
        and returns a list of their URLs.
        """
        logging.info(f"--- Starting PDF to S3 Process for: {pdf_url} ---")

        try:
            # 1. Download PDF with memory management
            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()
            
            # Process PDF in chunks to avoid memory issues
            pdf_bytes = b""
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    pdf_bytes += chunk
                    # Prevent excessive memory usage
                    if len(pdf_bytes) > 50 * 1024 * 1024:  # 50MB limit
                        logging.error("PDF too large (>50MB), aborting")
                        return []
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
            
            # Clean up memory
            pdf_document.close()
            del pdf_bytes
            del pdf_document
            
            return s3_urls
            
        except Exception as e:
            logging.error(f"An error occurred during PDF processing: {e}")
            # Clean up memory even on error
            try:
                if 'pdf_document' in locals():
                    pdf_document.close()
                if 'pdf_bytes' in locals():
                    del pdf_bytes
            except:
                pass
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
            
            # Create lookup dict using (question_number, part_label) as key
            # This supports sub-questions properly
            answer_sheet_dict = {}
            for item in answer_sheet_list:
                if 'question_number' not in item:
                    continue
                try:
                    q_num = int(item['question_number'])
                except (ValueError, TypeError):
                    continue
                part_label = item.get('part_label')
                key = (q_num, part_label)
                answer_sheet_dict[key] = item
            
            # For each question in question_paper_list, merge with graded answer
            for q_data in question_paper_list:
                q_num = q_data.get('question_number')
                part_label = q_data.get('part_label')
                key = (q_num, part_label)
                
                if key in answer_sheet_dict:
                    # Merge: question data + graded answer
                    # Graded answer includes: student_answer_text, feedback, marks_awarded, ques_id
                    merged_list.append({**q_data, **answer_sheet_dict[key]})
                else:
                    # If no graded answer found (student didn't attempt), add question only
                    merged_list.append(q_data)
            
            logging.info(f"✅ Merged {len(merged_list)} questions with graded answers")
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
        
    def result_analysis(self, valit_result, total_max_marks):
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
            # Enhanced Analysis with More Details
            # --------------------------

            # total_max_marks = 0
            total_awarded_marks = 0
            per_q = []  # per-question analysis rows
            sum_conf_pct_raw = 0.0 
            # mm = max_marks

            # Enhanced tracking for detailed analysis
            question_types = {}
            difficulty_levels = {}
            cognitive_levels = {}
            section_analysis = {}
            time_analysis = {}
            feedback_analysis = {"positive": 0, "negative": 0, "neutral": 0}
            marking_scheme_analysis = {}
            no_answer_count = 0
            high_confidence_low_score = 0
            low_confidence_high_score = 0

            for r in valit_result:
                qn = str(r.get("question_number"))
                mm = float(r.get("maximum_marks", 0))
                ma = float(r.get("marks_awarded", 0))
                cl_raw = float(r.get("confident_level", 0))

                score_pct = pct(ma, mm)
                conf_pct = pct(cl_raw, self.CONF_SCALE_MAX)
                sum_conf_pct_raw += conf_pct
                delta = round(conf_pct - score_pct, 2)

                # Enhanced per-question data
                question_data = {
                    "question_number": qn,
                    "maximum_marks": mm,
                    "marks_awarded": ma,
                    "score_pct": round(score_pct, 2),
                    "confident_level": cl_raw,
                    "confidence_pct": round(conf_pct, 2),
                    "confidence_minus_score_pct": delta,
                    "question_type": r.get("question_type", "Unknown"),
                    "difficulty": r.get("difficulty", "Unknown"),
                    "cognitive_level": r.get("cognitive_level", "Unknown"),
                    "section": r.get("section", "Unknown"),
                    "estimated_time": r.get("estimated_time", 0),
                    "feedback": r.get("feedback", ""),
                    "marking_scheme": r.get("marking_scheme", ""),
                    "student_answer_text": r.get("student_answer_text", ""),
                    "is_or_question": r.get("is_or_question", False),
                    "has_sub_questions": r.get("has_sub_questions", False),
                    "part_label": r.get("part_label", None)
                }

                per_q.append(question_data)

                # total_max_marks += mm
                total_awarded_marks += ma

                # Track question types
                q_type = r.get("question_type", "Unknown")
                if q_type not in question_types:
                    question_types[q_type] = {"count": 0, "total_marks": 0, "awarded_marks": 0, "avg_score_pct": 0}
                question_types[q_type]["count"] += 1
                question_types[q_type]["total_marks"] += mm
                question_types[q_type]["awarded_marks"] += ma

                # Track difficulty levels
                difficulty = r.get("difficulty", "Unknown")
                if difficulty not in difficulty_levels:
                    difficulty_levels[difficulty] = {"count": 0, "total_marks": 0, "awarded_marks": 0, "avg_score_pct": 0}
                difficulty_levels[difficulty]["count"] += 1
                difficulty_levels[difficulty]["total_marks"] += mm
                difficulty_levels[difficulty]["awarded_marks"] += ma

                # Track cognitive levels
                cognitive = r.get("cognitive_level", "Unknown")
                if cognitive not in cognitive_levels:
                    cognitive_levels[cognitive] = {"count": 0, "total_marks": 0, "awarded_marks": 0, "avg_score_pct": 0}
                cognitive_levels[cognitive]["count"] += 1
                cognitive_levels[cognitive]["total_marks"] += mm
                cognitive_levels[cognitive]["awarded_marks"] += ma

                # Track sections
                section = r.get("section", "Unknown")
                if section not in section_analysis:
                    section_analysis[section] = {"count": 0, "total_marks": 0, "awarded_marks": 0, "avg_score_pct": 0}
                section_analysis[section]["count"] += 1
                section_analysis[section]["total_marks"] += mm
                section_analysis[section]["awarded_marks"] += ma

                # Track time analysis
                est_time = float(r.get("estimated_time", 0))
                if est_time > 0:
                    time_analysis[qn] = {
                        "estimated_time": est_time,
                        "marks_awarded": ma,
                        "max_marks": mm,
                        "efficiency": round((ma / mm) * 100, 2) if mm > 0 else 0
                    }

                # Analyze feedback sentiment
                feedback = r.get("feedback", "").lower()
                if any(word in feedback for word in ["excellent", "good", "correct", "well", "accurate"]):
                    feedback_analysis["positive"] += 1
                elif any(word in feedback for word in ["incorrect", "wrong", "error", "mistake", "failed"]):
                    feedback_analysis["negative"] += 1
                else:
                    feedback_analysis["neutral"] += 1

                # Track marking schemes
                marking_scheme = r.get("marking_scheme", "")
                if marking_scheme:
                    scheme_key = marking_scheme[:50] + "..." if len(marking_scheme) > 50 else marking_scheme
                    if scheme_key not in marking_scheme_analysis:
                        marking_scheme_analysis[scheme_key] = {"count": 0, "total_marks": 0, "awarded_marks": 0}
                    marking_scheme_analysis[scheme_key]["count"] += 1
                    marking_scheme_analysis[scheme_key]["total_marks"] += mm
                    marking_scheme_analysis[scheme_key]["awarded_marks"] += ma

                # Track no-answer cases
                student_answer = r.get("student_answer_text", "").lower()
                if any(phrase in student_answer for phrase in ["no answer", "blank", "diagonal line", "not attempted"]):
                    no_answer_count += 1

                # Track confidence vs score discrepancies
                if conf_pct > 80 and score_pct < 50:
                    high_confidence_low_score += 1
                elif conf_pct < 50 and score_pct > 80:
                    low_confidence_high_score += 1

            # Calculate averages for each category
            for category in [question_types, difficulty_levels, cognitive_levels, section_analysis]:
                for key, data in category.items():
                    if data["total_marks"] > 0:
                        data["avg_score_pct"] = round(pct(data["awarded_marks"], data["total_marks"]), 2)

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

            # Performance distribution analysis
            score_distribution = {
                "excellent": sum(1 for r in per_q if r["score_pct"] >= 90),
                "good": sum(1 for r in per_q if 70 <= r["score_pct"] < 90),
                "average": sum(1 for r in per_q if 50 <= r["score_pct"] < 70),
                "poor": sum(1 for r in per_q if 0 < r["score_pct"] < 50),
                "zero": sum(1 for r in per_q if r["score_pct"] == 0)
            }

            # Enhanced summary with comprehensive details
            summary = {
                # Basic metrics (existing)
                "total_maximum_marks": total_max_marks,
                "total_awarded_marks": total_awarded_marks,
                "overall_score_percentage": overall_score_pct,
                "average_question_score_percentage": avg_q_score_pct,
                "average_confidence_percentage": avg_conf_pct,
                "median_confidence_percentage": median_conf_pct,
                "sum_of_confidence_percentage": sum_conf_pct,
                
                # Enhanced counts and distributions
                "counts": {
                    "correct_full_marks": correct,
                    "partial": partial,
                    "incorrect": incorrect,
                    "total_questions": len(per_q),
                    "no_answer_questions": no_answer_count,
                    "high_confidence_low_score": high_confidence_low_score,
                    "low_confidence_high_score": low_confidence_high_score
                },
                
                # Performance distribution
                "score_distribution": score_distribution,
                
                # Detailed analysis by categories
                "question_type_analysis": question_types,
                "difficulty_analysis": difficulty_levels,
                "cognitive_level_analysis": cognitive_levels,
                "section_analysis": section_analysis,
                
                # Time analysis
                "time_analysis": {
                    "total_estimated_time": sum(t["estimated_time"] for t in time_analysis.values()),
                    "average_efficiency": round(mean([t["efficiency"] for t in time_analysis.values()]), 2) if time_analysis else 0,
                    "time_per_question": time_analysis
                },
                
                # Feedback analysis
                "feedback_analysis": feedback_analysis,
                
                # Marking scheme analysis
                "marking_scheme_analysis": marking_scheme_analysis,
                
                # Statistical correlations
                "pearson_r_confidence_vs_score": None if r_conf_score is None else round(r_conf_score, 3),

                
                # Performance insights
                "performance_insights": {
                    "strongest_question_type": max(question_types.items(), key=lambda x: x[1]["avg_score_pct"])[0] if question_types else "N/A",
                    "weakest_question_type": min(question_types.items(), key=lambda x: x[1]["avg_score_pct"])[0] if question_types else "N/A",
                    "strongest_difficulty": max(difficulty_levels.items(), key=lambda x: x[1]["avg_score_pct"])[0] if difficulty_levels else "N/A",
                    "weakest_difficulty": min(difficulty_levels.items(), key=lambda x: x[1]["avg_score_pct"])[0] if difficulty_levels else "N/A",
                    "most_confident_section": max(section_analysis.items(), key=lambda x: x[1]["avg_score_pct"])[0] if section_analysis else "N/A",
                    "least_confident_section": min(section_analysis.items(), key=lambda x: x[1]["avg_score_pct"])[0] if section_analysis else "N/A"
                }
            }

            return summary
        except Exception as e:
            logging.error(f"Error in result_analysis: {e}")
            return {}

                             
processing_answer_sheet = processing_paper()        
cls_helper_function = helper_function()
    
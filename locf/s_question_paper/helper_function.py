import os, base64, asyncio, boto3, requests, logging
from typing import Any, Dict, List, Optional, Union, Tuple
from mistralai import Mistral
from io import BytesIO
from PyPDF2 import PdfReader
from typing import List, Optional, Literal, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv
import re, json
from locf.s_question_paper.classes import QuestionPaperRequest, ImageTag, required_items, question_type_dict
from locf.s_question_paper import prompts, parser_helper
import os
from pathlib import Path
import google.generativeai as genai
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')
client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
print(f"Mistral client initialized successfully with key {client}.")
# Initialize boto3 client

s3 = boto3.client("s3",
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
AWS_S3_REGION= os.getenv("AWS_S3_REGION")

class ImageTagger:
    def __init__(self):
        self.prompt = PromptTemplate.from_template(prompts.image_tagging_prompt_v3)
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=GOOGLE_API_KEY)
        self.parser = JsonOutputParser(pydantic_object=List[ImageTag])
        self.chain = self.prompt | self.llm | self.parser
        self.s3_folder = "ocr/question_images"
        self.bucket_name = AWS_S3_BUCKET_NAME

    def get_page_batches(self, pdf_url: str, batch_size=5):
        """Reads a PDF from a URL and splits it into page number batches."""
        try:
            response = requests.get(pdf_url)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            total_pages = len(reader.pages)
            batches = [list(range(i, min(i + batch_size, total_pages))) for i in range(0, total_pages, batch_size)]
            print(f"PDF has {total_pages} pages, split into {len(batches)} batches.")
            return batches
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None

    def perform_basic_ocr(self, file_url, batch):
        """
        Performs a fast OCR, getting only text and images, NOT the structured JSON.
        """
        try:
            # NOTE: We have removed the 'document_annotation_format' parameter for speed.
            pdf_response = client.ocr.process(
                document={"type": "document_url", "document_url": file_url},
                model="mistral-ocr-latest",
                pages=batch,
                include_image_base64=True
            )
            print(f"Successfully performed basic OCR for batch {batch}")
            return pdf_response
        except Exception as e:
            print(f"Error in Mistral OCR on batch {batch}: {e}")
            return None

    def save_images_to_s3(self, pdf_response, session_id: str, batch_no: int):
        """Saves extracted images to S3 and returns a map of image_id -> s3_key."""
        s3_key_map = {}
        if not (pdf_response and pdf_response.pages):
            return s3_key_map
            
        for page in pdf_response.pages:
            if page.images:
                for img in page.images:
                    image_bytes = base64.b64decode(img.image_base64.split(",")[1] if "," in img.image_base64 else img.image_base64)
                    file_name = f"{session_id}-{batch_no}-{img.id}.jpeg"
                    s3_key = f"{self.s3_folder}/{file_name}"
                    s3.put_object(Bucket=self.bucket_name, Key=s3_key, Body=image_bytes, ContentType="image/jpeg")
                    #print(f"Uploaded image to S3: {s3_key}")
                    s3_key_map[img.id] = s3_key
        return s3_key_map

    async def generate_image_tags(self, pdf_response):
        """Generates the list of ImageTag objects using the langchain model."""
        all_image_objects = [img for page in pdf_response.pages if page.images for img in page.images]
        if not all_image_objects:
            return []
            
        combined_text = "\n\n---\n\n".join([page.markdown for page in pdf_response.pages])
        image_ids = [img.id for img in all_image_objects]
        
        print(f"Sending {len(image_ids)} image IDs for tagging...")
        try:
            # `tags` will be a list of dictionaries from the parser
            tags_as_dicts = await self.chain.ainvoke({"question_text": combined_text, "image_list": ", ".join(image_ids)})
            print(f"Received {len(tags_as_dicts)} tags.")

            # FIX: Convert the list of dictionaries into a list of ImageTag objects
            return [ImageTag(**tag_dict) for tag_dict in tags_as_dicts]
            
        except Exception as e:
            print(f"Error generating tags with (generate_image_tags): {e}")
            return []

class llm_function:
    def __init__(self, batch_size: int = 7, include_images: bool = False):
        self.batch_size = batch_size
        self.include_images = include_images
        self.model_name = "gemini-2.0-flash-001"
        self.parser = JsonOutputParser()
        self.prompt = PromptTemplate.from_template(prompts.question_structure_prompt)
        self.llm = ChatGoogleGenerativeAI(model=self.model_name, api_key= GOOGLE_API_KEY, temperature=0.0)
        self.chain = self.prompt | self.llm | self.parser

    def get_page_batches(self, pdf_url: str) -> Optional[List[List[int]]]:
        """Download PDF from URL and split into 1-based page number batches."""
        try:
            r = requests.get(pdf_url, timeout=60)
            r.raise_for_status()
            reader = PdfReader(BytesIO(r.content))
            total_pages = len(reader.pages)
            pages = list(range(0, total_pages + 1))  # 1-based
            return [pages[i:i+self.batch_size] for i in range(0, len(pages), self.batch_size)]
        except Exception as e:
            print(f"Error reading PDF from URL: {e}")
            return None

    def mistral_ocr(self, file_url: str, pages: List[int]):
        """Run OCR on a batch of pages using Mistral API."""
        try:
            return client.ocr.process(
                document={"type": "document_url", "document_url": file_url},
                model="mistral-ocr-latest",
                pages=pages,
                include_image_base64=self.include_images,
            )
        except Exception as e:
            print(f"OCR error on pages {pages}: {e}")
            return None
    
    def build_user_message_dict(self,
        urls: Optional[Union[str, List[Union[str, Dict[str, Any]]]]] = None
    ) -> List[Dict[str, Any]]:
        message = "These are the images from question paper"
        if not message and not urls:
            raise ValueError("Either message or urls must be provided.")

        # Normalize urls to a list
        items: List[Union[str, Dict[str, Any]]] = []
        if isinstance(urls, str):
            s = urls.strip()
            if s.startswith("[") or s.startswith("{"):
                try:
                    parsed = json.loads(s)
                    items = parsed if isinstance(parsed, list) else [parsed]
                except Exception:
                    items = [s]  # treat as a single URL string
            else:
                items = [s]
        elif isinstance(urls, list):
            items = urls
        elif urls is None:
            items = []
        else:
            raise TypeError("`urls` must be a str, list, or None.")

        def extract_url(it: Union[str, Dict[str, Any]]) -> Optional[str]:
            if isinstance(it, str):
                return it
            return (
                it.get("s3_url")
                or it.get("url")
                or (it.get("image_url") if isinstance(it.get("image_url"), str) else None)
                or it.get("src")
            )

        def extract_qno(it: Union[str, Dict[str, Any]]) -> Optional[str]:
            if isinstance(it, dict):
                q = it.get("question_no") or it.get("qno") or it.get("question_number")
                if q is not None:
                    return str(q)
                # fallback: try to parse “…-Q12-…” or “…question-12…”
                for key in ("image_name", "s3_url", "url", "src"):
                    val = it.get(key)
                    if isinstance(val, str):
                        m = re.search(r"(?:Q(?:uestion)?[-_ ]*)?(\d{1,3})(?!\d)", val, re.IGNORECASE)
                        if m:
                            return m.group(1)
            # strings usually don't have qno
            return None

        parts: List[Dict[str, Any]] = []
        if message:
            parts.append({"type": "text", "text": message})

        for it in items:
            url = extract_url(it)
            if not url:
                continue
            qno = extract_qno(it)
            if qno:
                # Add a short caption/label BEFORE the image so the model sees the mapping
                parts.append({"type": "text", "text": f"Image for Question {qno}:"})
            else:
                parts.append({"type": "text", "text": "Image for Question (number unknown):"})

            parts.append({"type": "image_url", "image_url": {"url": url}})

        if not parts:
            raise ValueError("No valid message or image URLs were provided.")

        return [{"role": "user", "content": parts}]

    async def llm_model(self, content:str):
        try:
            gen_response = await self.chain.ainvoke({"content": content})
            return gen_response
        except Exception as e:
            print(f"Error in Instruction Set: {e}")
            return None

    async def llm_ocr_process(self, file_url: str):
        """Run OCR on all page batches and return list of structured results per batch."""
        try:
            print(f"Starting OCR for {file_url}")
            batches = self.get_page_batches(file_url)
            if not batches:
                return None

            all_results = []
            for i, batch in enumerate(batches, start=1):
                print(f"Processing batch {i}/{len(batches)}: pages {batch}")
                resp = self.mistral_ocr(file_url, batch)
                if not resp:
                    all_results.append({"batch_no": i, "pages": batch, "content": ""})
                    continue

                batch_texts = []
                pages = getattr(resp, "pages", None) or getattr(resp, "result", {}).get("pages")
                if pages:
                    for p in pages:
                        md = getattr(p, "markdown", None) or (p.get("markdown") if isinstance(p, dict) else None)
                        if md:
                            batch_texts.append(md)

                all_results.append({
                    "batch_no": i,
                    "pages": batch,
                    "content": "\n\n".join(batch_texts)
                })
            final_content = "\n\n".join([result["content"] for result in all_results])
            gen_response= await self.llm_model(final_content)

            return gen_response, all_results if all_results else None
        except Exception as e:
            print(f"Error in llm_ocr_process: {e}")
            return None
        
class question_paper_function:
    def _validate_questions_extracted(self, parsed_json: dict, expected_count: Optional[int] = None) -> Tuple[bool, List[int], int]:
        """
        Validates if all questions are present in the extracted JSON.
        
        Args:
            parsed_json: The parsed JSON from question extraction
            expected_count: Expected number of questions (optional)
        
        Returns:
            Tuple of (is_complete, missing_questions[], actual_count)
        """
        try:
            if not parsed_json or not isinstance(parsed_json, dict):
                return False, [], 0
            
            questions = parsed_json.get("questions", [])
            if not questions:
                return False, [], 0
            
            # Extract question numbers
            extracted_numbers = set()
            for q in questions:
                q_num_str = str(q.get("question_number", "")).strip()
                # Handle formats like "1", "2a", "3(i)" - extract the base number
                match = re.match(r"^(\d+)", q_num_str)
                if match:
                    extracted_numbers.add(int(match.group(1)))
            
            actual_count = len(extracted_numbers)
            
            # If we don't know expected count, just return what we got
            if expected_count is None or expected_count <= 0:
                return True, [], actual_count
            
            # Check for missing questions
            expected_set = set(range(1, expected_count + 1))
            missing = sorted(list(expected_set - extracted_numbers))
            
            is_complete = len(missing) == 0
            
            if not is_complete:
                print(f"⚠️ Validation: Expected {expected_count} questions, found {actual_count}. Missing: {missing}")
            else:
                print(f"✅ Validation: All {expected_count} questions successfully extracted.")
            
            return is_complete, missing, actual_count
            
        except Exception as e:
            print(f"Error in validation: {e}")
            return False, [], 0
    
    def _merge_question_extractions(self, base_result: dict, retry_result: dict) -> dict:
        """
        Merges retry extraction results with base results, keeping the best data.
        """
        try:
            if not base_result:
                return retry_result
            if not retry_result:
                return base_result
            
            # Merge questions by question_number
            base_questions = {str(q.get("question_number")): q for q in base_result.get("questions", [])}
            retry_questions = {str(q.get("question_number")): q for q in retry_result.get("questions", [])}
            
            # Update base with retry results (retry takes precedence for missing/failed questions)
            base_questions.update(retry_questions)
            
            # Reconstruct result
            merged = base_result.copy()
            merged["questions"] = list(base_questions.values())
            
            # Sort by question number
            merged["questions"].sort(key=lambda q: int(re.match(r"^(\d+)", str(q.get("question_number", "0"))).group(1)))
            
            return merged
            
        except Exception as e:
            print(f"Error merging extractions: {e}")
            return base_result
    
    def question_paper_extraction(
        self, 
        pdf_url: str, 
        expected_question_count: Optional[int] = None, 
        max_retries: int = 3, 
        strict_mode: bool = True,
        batch_size: int = 20
    ) -> Tuple[Optional[dict], Dict[str, int]]:
        """
        Extracts questions from PDF with batch processing and retry logic.
        
        Args:
            pdf_url: URL of the PDF file
            expected_question_count: Expected number of questions (REQUIRED for validation)
            max_retries: Maximum retry attempts for missing questions per batch (default: 3)
            strict_mode: If True, raises error if not all questions extracted (default: True)
            batch_size: Number of questions to extract per batch (default: 20)
        
        Returns:
            Tuple of (parsed_json, token_usage_dict)
            
        Raises:
            ValueError: If strict_mode=True and not all questions are extracted after max_retries
        """
        if expected_question_count is None or expected_question_count <= 0:
            raise ValueError(f"expected_question_count must be provided and > 0, got: {expected_question_count}")
        
        # Calculate number of batches needed
        num_batches = (expected_question_count + batch_size - 1) // batch_size
        
        print(f"\n{'='*70}")
        print(f"🎯 TARGET: Extract ALL {expected_question_count} questions from PDF")
        print(f"📦 Batch Processing: {num_batches} batches of {batch_size} questions each")
        print(f"📋 Strict Mode: {'ENABLED - Must extract ALL questions' if strict_mode else 'DISABLED - Partial results OK'}")
        print(f"🔄 Max Retries: {max_retries} per batch")
        print(f"{'='*70}")
        
        # Process questions in batches
        return self._extract_questions_in_batches(
            pdf_url=pdf_url,
            expected_question_count=expected_question_count,
            batch_size=batch_size,
            max_retries=max_retries,
            strict_mode=strict_mode
        )
    
    def _extract_questions_in_batches(
        self,
        pdf_url: str,
        expected_question_count: int,
        batch_size: int,
        max_retries: int,
        strict_mode: bool
    ) -> Tuple[Optional[dict], Dict[str, int]]:
        """
        Extract questions in batches for better manageability.
        
        Returns:
            Tuple of (result_dict, token_usage_dict)
        """
        # Create question number ranges for each batch
        batches = []
        for i in range(0, expected_question_count, batch_size):
            start = i + 1
            end = min(i + batch_size, expected_question_count)
            batches.append((start, end))
        
        print(f"\n📦 BATCH PLAN:")
        for idx, (start, end) in enumerate(batches, 1):
            print(f"   Batch {idx}: Questions {start}-{end} ({end - start + 1} questions)")
        print()
        
        # Download PDF once (reuse for all batches)
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
            print(f"✅ PDF downloaded successfully ({len(pdf_data)} bytes)\n")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to download PDF from {pdf_url} after retries: {e}")
        
        # Extract each batch
        all_questions = []
        batch_results = []
        extraction_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
        
        for batch_idx, (start_q, end_q) in enumerate(batches, 1):
            print(f"\n{'='*70}")
            print(f"📦 PROCESSING BATCH {batch_idx}/{len(batches)}")
            print(f"🎯 Target: Questions {start_q}-{end_q} ({end_q - start_q + 1} questions)")
            print(f"{'='*70}\n")
            
            batch_result, batch_tokens = self._extract_single_batch(
                pdf_data=pdf_data,
                start_question=start_q,
                end_question=end_q,
                batch_number=batch_idx,
                total_batches=len(batches),
                max_retries=max_retries,
                strict_mode=strict_mode
            )
            
            # Aggregate tokens from this batch
            if batch_tokens:
                extraction_tokens["total_input_tokens"] += batch_tokens.get("total_input_tokens", 0)
                extraction_tokens["total_output_tokens"] += batch_tokens.get("total_output_tokens", 0)
                extraction_tokens["total_tokens"] += batch_tokens.get("total_tokens", 0)
            
            if batch_result and "questions" in batch_result:
                batch_questions = batch_result["questions"]
                all_questions.extend(batch_questions)
                batch_results.append(batch_result)
                print(f"✅ Batch {batch_idx} complete: {len(batch_questions)} questions extracted\n")
            else:
                error_msg = f"Batch {batch_idx} failed to extract questions {start_q}-{end_q}"
                print(f"❌ {error_msg}\n")
                if strict_mode:
                    raise ValueError(error_msg)
        
        # Combine all batches into single result
        combined_result = {
            "questions": all_questions
        }
        
        # Final validation across all batches
        print(f"\n{'='*70}")
        print(f"📊 FINAL VALIDATION - ALL BATCHES")
        print(f"{'='*70}")
        
        is_complete, missing, actual_count = self._validate_questions_extracted(
            combined_result,
            expected_question_count
        )
        
        print(f"\n📊 FINAL RESULTS:")
        print(f"   ├─ Total Batches Processed: {len(batches)}")
        print(f"   ├─ Target Questions: {expected_question_count}")
        print(f"   ├─ Extracted Questions: {actual_count}")
        print(f"   ├─ Missing Questions: {missing if missing else 'None'}")
        print(f"   └─ Status: {'✅ COMPLETE' if is_complete else '⚠️ INCOMPLETE'}")
        
        # Print extraction token summary
        print(f"\n📊 EXTRACTION TOKENS (gemini-2.5-pro):")
        print(f"   ├─ Input: {extraction_tokens['total_input_tokens']}")
        print(f"   ├─ Output: {extraction_tokens['total_output_tokens']}")
        print(f"   └─ Total: {extraction_tokens['total_tokens']}\n")
        
        if is_complete:
            print(f"\n{'='*70}")
            print(f"✅ SUCCESS: All {expected_question_count} questions extracted!")
            print(f"{'='*70}\n")
            return combined_result, extraction_tokens
        else:
            print(f"\n{'='*70}")
            print(f"❌ BATCH EXTRACTION INCOMPLETE")
            print(f"{'='*70}")
            print(f"   ├─ Target: {expected_question_count}")
            print(f"   ├─ Extracted: {actual_count}")
            print(f"   ├─ Missing: {len(missing)} questions {missing}")
            print(f"   └─ Success Rate: {(actual_count/expected_question_count)*100:.1f}%")
            print(f"{'='*70}\n")
            
            if strict_mode:
                raise ValueError(
                    f"STRICT MODE VIOLATION: Batch extraction incomplete. "
                    f"Expected {expected_question_count} questions but only extracted {actual_count}. "
                    f"Missing questions: {missing}"
                )
            else:
                return combined_result, extraction_tokens
    
    def _extract_single_batch(
        self,
        pdf_data: bytes,
        start_question: int,
        end_question: int,
        batch_number: int,
        total_batches: int,
        max_retries: int,
        strict_mode: bool
    ) -> Tuple[Optional[dict], Dict[str, int]]:
        """
        Extract a single batch of questions with retry logic.
        
        Returns:
            Tuple of (result_dict, token_usage_dict)
        """
        target_questions = list(range(start_question, end_question + 1))
        expected_count = len(target_questions)
        
        all_results = None
        missing_questions = []
        batch_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
        
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-pro")
        
        for attempt in range(max_retries):
            try:
                print(f"{'─'*60}")
                print(f"📄 Batch {batch_number} - Attempt {attempt + 1}/{max_retries}")
                if attempt == 0:
                    print(f"🎯 Target: Questions {start_question}-{end_question} ({expected_count} questions)")
                else:
                    print(f"🎯 Retry Target: Missing questions {missing_questions}")
                print(f"{'─'*60}")
                
                # Build prompt for this batch
                if attempt > 0 and missing_questions:
                    missing_list_str = ', '.join(map(str, missing_questions))
                    print(f"🎯 Focusing on missing questions: {missing_list_str}")
                    
                    extraction_prompt = f"""**🔄 BATCH {batch_number} RETRY - CRITICAL MISSING QUESTIONS**

**BATCH TARGET: Questions {start_question} to {end_question} ({expected_count} questions total)**
**MISSING IN THIS BATCH: {missing_list_str}**

You are extracting BATCH {batch_number} of {total_batches}. This batch should contain questions {start_question} through {end_question}.

**ABSOLUTE PRIORITY:**
1. Extract ALL {expected_count} questions in this batch (Questions {start_question}-{end_question})
2. Pay EXTRA attention to missing questions: {missing_list_str}
3. Verify EVERY question from {start_question} to {end_question} is included

**CRITICAL VALIDATION:**
✅ Total questions in this batch = {expected_count}
✅ Questions numbered from {start_question} to {end_question}
✅ Missing questions {missing_list_str} are NOW present

{prompts.question_extraction_prompt}
"""
                else:
                    extraction_prompt = f"""**BATCH {batch_number} OF {total_batches} - EXTRACTION**

**BATCH TARGET: Questions {start_question} to {end_question} ({expected_count} questions)**

You are extracting a SPECIFIC BATCH of questions from the PDF.

**CRITICAL INSTRUCTIONS:**
1. Extract ONLY questions numbered {start_question} through {end_question}
2. You MUST extract exactly {expected_count} questions
3. Do NOT extract questions outside this range
4. Ensure ALL questions in this range are included

**VALIDATION CHECKLIST:**
✅ Extract questions {start_question} through {end_question} ONLY
✅ Total count in output = {expected_count} questions
✅ No questions missing from this range
✅ No questions outside this range included

{prompts.question_extraction_prompt}
"""
                
                prompt_content = [
                    {"mime_type": "application/pdf", "data": pdf_data},
                    extraction_prompt
                ]
                
                estimated_tokens = model.count_tokens(prompt_content).total_tokens
                print(f"📊 Estimated tokens: {estimated_tokens}")
                
                start_time = time.time()
                response = model.generate_content(
                    prompt_content,
                    generation_config={"temperature": 0}
                )
                end_time = time.time()
                print(f"⏱️ API call: {end_time - start_time:.2f}s")
                
                md_text = response.text or ""
                
                # Log and track token usage
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    prompt_tokens = response.usage_metadata.prompt_token_count
                    output_tokens = response.usage_metadata.candidates_token_count
                    total_tokens_count = prompt_tokens + output_tokens
                    print(f"🎯 Tokens: In={prompt_tokens}, Out={output_tokens}, Total={total_tokens_count}")
                    
                    # Aggregate tokens
                    batch_tokens["total_input_tokens"] += prompt_tokens
                    batch_tokens["total_output_tokens"] += output_tokens
                    batch_tokens["total_tokens"] += total_tokens_count
                
                # Parse JSON
                parser = JsonOutputParser()
                try:
                    parsed_json = parser.parse(md_text)
                except Exception as e:
                    logging.warning(f"Failed to parse JSON with LangChain parser. Falling back.")
                    gen_text = self._ensure_text(md_text)
                    parsed_json = parser_helper.json_helpers.parse_json(gen_text)
                
                if not parsed_json:
                    print(f"❌ Attempt {attempt + 1}: Failed to parse response")
                    continue
                
                # Filter to only include questions in this batch's range
                if "questions" in parsed_json:
                    batch_questions = []
                    for q in parsed_json["questions"]:
                        q_num_str = str(q.get("question_number", "")).strip()
                        match = re.match(r"^(\d+)", q_num_str)
                        if match:
                            q_num = int(match.group(1))
                            if start_question <= q_num <= end_question:
                                batch_questions.append(q)
                    
                    parsed_json["questions"] = batch_questions
                
                # Merge with previous results if this is a retry
                if all_results:
                    parsed_json = self._merge_question_extractions(all_results, parsed_json)
                
                all_results = parsed_json
                
                # Validate this batch
                is_complete, missing, actual_count = self._validate_questions_in_range(
                    parsed_json,
                    start_question,
                    end_question
                )
                
                print(f"\n📊 Batch {batch_number} Validation:")
                print(f"   ├─ Target: Q{start_question}-Q{end_question} ({expected_count} questions)")
                print(f"   ├─ Extracted: {actual_count} questions")
                print(f"   ├─ Missing: {missing if missing else 'None'}")
                print(f"   └─ Status: {'✅ COMPLETE' if is_complete else '⚠️ INCOMPLETE'}")
                
                if is_complete:
                    print(f"\n✅ Batch {batch_number} SUCCESS!\n")
                    return parsed_json, batch_tokens
                
                # Update missing questions for next retry
                missing_questions = missing
                
                if attempt < max_retries - 1:
                    print(f"\n🔄 Batch {batch_number} retry {attempt + 2}/{max_retries} for: {missing_questions}\n")
                else:
                    print(f"\n⚠️ Batch {batch_number} max retries reached. Missing: {missing_questions}\n")
                    if strict_mode:
                        raise ValueError(
                            f"Batch {batch_number} incomplete: Missing questions {missing_questions}"
                        )
                    return parsed_json, batch_tokens
                    
            except Exception as e:
                print(f"\n❌ Batch {batch_number} attempt {attempt + 1} error: {e}")
                if attempt == max_retries - 1:
                    if strict_mode:
                        raise ValueError(f"Batch {batch_number} failed: {e}")
                    return all_results, batch_tokens
                continue
        
        return all_results, batch_tokens
    
    def _validate_questions_in_range(
        self,
        parsed_json: dict,
        start_q: int,
        end_q: int
    ) -> Tuple[bool, List[int], int]:
        """
        Validates if all questions in a specific range are present.
        
        Args:
            parsed_json: The parsed JSON
            start_q: Start question number (inclusive)
            end_q: End question number (inclusive)
            
        Returns:
            Tuple of (is_complete, missing_questions[], actual_count)
        """
        try:
            if not parsed_json or not isinstance(parsed_json, dict):
                return False, list(range(start_q, end_q + 1)), 0
            
            questions = parsed_json.get("questions", [])
            if not questions:
                return False, list(range(start_q, end_q + 1)), 0
            
            # Extract question numbers in this range
            extracted_numbers = set()
            for q in questions:
                q_num_str = str(q.get("question_number", "")).strip()
                match = re.match(r"^(\d+)", q_num_str)
                if match:
                    q_num = int(match.group(1))
                    if start_q <= q_num <= end_q:
                        extracted_numbers.add(q_num)
            
            actual_count = len(extracted_numbers)
            
            # Check for missing questions in this range
            expected_set = set(range(start_q, end_q + 1))
            missing = sorted(list(expected_set - extracted_numbers))
            
            is_complete = len(missing) == 0
            
            return is_complete, missing, actual_count
            
        except Exception as e:
            print(f"Error in range validation: {e}")
            return False, list(range(start_q, end_q + 1)), 0
    
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
            print(f"An error occurred (get_no_of_questions): {e}")
            result = None
            
    def _extract_question_count_from_markdown(self, markdown_text: str) -> Optional[int]:
        """
        Intelligently extract question count from markdown when metadata extraction fails.
        Handles MULTIPLE question paper formats flexibly.
        
        Supports:
        - Table formats (| 1 |, | Question |)
        - Plain text numbering (1., 1), Q1, Question 1)
        - Section-based papers (Section A: Q1-20, Section B: Q21-30)
        - Roman numerals (I, II, III)
        - Mixed formats
        """
        if not markdown_text:
            return None
        
        # ========================================================================
        # STRATEGY 1: Explicit Total Question Mentions
        # ========================================================================
        total_patterns = [
            r'total[_\s]*(?:no|number)?[_\s]*(?:of[_\s]*)?questions?[:\s]*(\d+)',
            r'(\d+)[_\s]*total[_\s]*questions?',
            r'number[_\s]*of[_\s]*questions?[:\s]*(\d+)',
            r'questions?[_\s]*count[:\s]*(\d+)',
        ]
        for pattern in total_patterns:
            match = re.search(pattern, markdown_text, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                if 1 <= count <= 500:  # Sanity check
                    print(f"✓ [Strategy 1] Found explicit mention: {count} questions")
                    return count
        
        # ========================================================================
        # STRATEGY 2: Section-Based Question Ranges
        # ========================================================================
        # Pattern: "Section A: Q1-20" or "Questions 1-10" or "21-26"
        range_patterns = [
            r'[Qq]uestions?\s*(?:no|numbers?)?[:\s]*(\d+)\s*[-–to]+\s*(\d+)',
            r'[Qq]\s*(\d+)\s*[-–]\s*[Qq]?\s*(\d+)',
            r'(?:Section|Part)\s+[A-Z].*?(\d+)\s*[-–to]+\s*(\d+)',
            r'\|\s*(\d+)\s*[-–]\s*(\d+)\s*\|',  # Table format: | 1-20 |
        ]
        
        section_ranges = []
        for pattern in range_patterns:
            matches = re.finditer(pattern, markdown_text, re.IGNORECASE)
            for match in matches:
                start = int(match.group(1))
                end = int(match.group(2))
                if 1 <= start <= end <= 500:
                    section_ranges.append((start, end))
        
        if section_ranges:
            # Find the highest ending question number
            max_from_ranges = max(end for _, end in section_ranges)
            print(f"✓ [Strategy 2] Found from ranges: {max_from_ranges} questions (ranges: {section_ranges})")
            return max_from_ranges
        
        # ========================================================================
        # STRATEGY 3: Count Question Number Patterns (Most Common)
        # ========================================================================
        # Handles: | 1 |, Q1, Q.1, Question 1, 1., 1), etc.
        question_patterns = [
            # Table formats
            r'\|\s*(\d+)\s*\|',                           # | 1 |
            r'\|\s*[Qq](?:uestion)?\.?\s*(\d+)\s*\|',    # | Q.1 | or | Question 1 |
            
            # Plain text formats
            r'[Qq](?:uestion)?[:\s#]*(\d+)[:\.\)]',      # Question 1:, Q1., Q.1
            r'^\s*(\d+)\s*[.:\)]',                        # 1. or 1) at line start
            r'\n\s*(\d+)\s*[.:\)]',                       # 1. or 1) after newline
            
            # Bracket formats
            r'\(\s*(\d+)\s*\)',                           # (1)
            r'\[\s*(\d+)\s*\]',                           # [1]
        ]
        
        all_question_numbers = set()
        for pattern in question_patterns:
            matches = re.finditer(pattern, markdown_text, re.MULTILINE)
            for match in matches:
                qnum = int(match.group(1))
                # Filter: reasonable range and likely not dates/years/page numbers
                if 1 <= qnum <= 200 and qnum not in {2020, 2021, 2022, 2023, 2024, 2025}:
                    all_question_numbers.add(qnum)
        
        if all_question_numbers:
            max_qnum = max(all_question_numbers)
            min_qnum = min(all_question_numbers)
            coverage = len(all_question_numbers)
            
            # Good coverage: at least 50% of questions present
            # OR at least 5 questions found with reasonable sequence
            if (coverage >= max_qnum * 0.5) or (coverage >= 5 and max_qnum <= coverage * 1.5):
                print(f"✓ [Strategy 3] Extracted from numbering: {max_qnum} questions")
                print(f"   Found {coverage} unique numbers: {sorted(list(all_question_numbers)[:20])}{'...' if coverage > 20 else ''}")
                return max_qnum
            else:
                print(f"⚠ [Strategy 3] Found numbers but low coverage ({coverage}/{max_qnum}), trying next strategy...")
        
        # ========================================================================
        # STRATEGY 4: Roman Numerals
        # ========================================================================
        roman_patterns = [
            r'\|\s*([IVX]+)\s*\|',                    # | I |, | II |, | III |
            r'[Qq]uestion\s+([IVX]+)',                 # Question I, Question II
            r'^\s*([IVX]+)\s*[.:\)]',                 # I., II), III:
        ]
        
        roman_to_int = {
            'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 
            'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
            'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
            'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20
        }
        
        roman_numbers = set()
        for pattern in roman_patterns:
            matches = re.finditer(pattern, markdown_text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                roman = match.group(1).upper()
                if roman in roman_to_int:
                    roman_numbers.add(roman_to_int[roman])
        
        if roman_numbers and len(roman_numbers) >= 3:
            max_roman = max(roman_numbers)
            print(f"✓ [Strategy 4] Found roman numerals: {max_roman} questions ({sorted(roman_numbers)})")
            return max_roman
        
        # ========================================================================
        # STRATEGY 5: Count "Question" Word Occurrences
        # ========================================================================
        # Count lines/paragraphs that start with variations of "Question"
        question_markers = re.findall(
            r'(?:^|\n)\s*(?:[Qq]uestion|[Qq]\.|[Qq]\s+\d+|[Qq]uestion\s+\d+)',
            markdown_text
        )
        if len(question_markers) >= 5:
            print(f"✓ [Strategy 5] Counted 'Question' markers: ~{len(question_markers)} questions")
            return len(question_markers)
        
        # ========================================================================
        # STRATEGY 6: Fallback - User Prompt Override
        # ========================================================================
        # If request has qcount field, use it
        print("⚠ Could not reliably extract question count from markdown")
        print("   All strategies failed. Will rely on user input or raise error.")
        return None
    
    async def question_preparation(self, gen_response, md_results):
        """
        Prepare question data with intelligent question count extraction.
        Uses a multi-tier fallback strategy:
        1. Metadata extraction from LLM
        2. Regex pattern matching
        3. AI agent analysis (most robust)
        """
        try:
            questions_count = self.get_no_of_questions(gen_response)
            try:
                if isinstance(md_results, str):   # case: JSON string
                    md_results = json.loads(md_results)
                elif isinstance(md_results, list):  # case: already a list
                    pass  # nothing to do
                else:
                    md_results = []
            except (TypeError, json.JSONDecodeError) as e:
                print(f"Error loading md_list: {e}")
                md_results = []

            qp_md = "\n\n".join([result.get("content", "") for result in md_results if isinstance(result, dict)])

            # ===================================================================
            # TIER 1: Try to get question count from metadata (fastest)
            # ===================================================================
            try:
                qcount = int(str(questions_count).strip())
                print(f"✓ [Tier 1] Question count from metadata: {qcount}")
            except (TypeError, ValueError):
                print("⚠ Metadata extraction failed for question count.")
                
                # ===========================================================
                # TIER 2: Use AI agent (most robust, handles any format)
                # ===========================================================
                print("🤖 [Tier 2] Activating Question Count Agent...")
                import asyncio
                qcount = await question_count_agent.extract_question_count(qp_md)
                
                if qcount is None or qcount <= 0:
                    

                    # ===============================================================
                    # TIER 3: Try regex-based extraction (fast, works for common formats)
                    # ===============================================================
                    print("🔍 [Tier 3] Trying regex pattern matching...")
                    qcount = self._extract_question_count_from_markdown(qp_md)
                    
                    if qcount is None or qcount <= 0:
                        print("❌ All extraction methods failed!")
                        raise ValueError(
                            f"Failed to extract question count using all methods:\n"
                            f"  - Metadata: {questions_count!r}\n"
                            f"  - Regex: {qcount}\n"
                            f"  - AI Agent: {qcount}"
                        )
            
            if qcount <= 0:
                raise ValueError(f"Invalid questions_count: {qcount}")
            
            print(f"✅ Final question count: {qcount}")
            return qp_md, qcount
        
        except Exception as e:
            print(f"❌ Error in question_preparation: {e}")
            return None, 0
        
    def _extract_tokens(self, message) -> Dict[str, int]:
        """
        Return a unified token dict for an LLM message across providers.
        Tries usage_metadata, response_metadata, and additional_kwargs.
        """
        out = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

        try:
            # 1) Preferred: LangChain's normalized usage
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
        
    def _ensure_text(self, content: Any) -> str:
        """
        Normalize SDK / LangChain message content into a plain string.
        """
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                else:
                    val = getattr(part, "content", None) or getattr(part, "text", None) or str(part)
                    parts.append(val)
            return "".join(parts).strip()
        if isinstance(content, str):
            return content.strip()
        return (getattr(content, "content", None) or getattr(content, "text", None) or str(content)).strip()
    
    def merge_and_map(self, images, questions):
        try:
            image_lookup = {img["question_no"]: img for img in images}

            merged_data = []
            for q in questions:
                qno = q["question_number"]
                img = image_lookup.get(qno, {
                    "image_name": None,
                    "question_no": None,
                    "part_of": None,
                    "s3_url": None
                })
                merged_data.append({**q, **img})
            return merged_data
        except Exception as e:
            print(f"Error in merge_and_map: {e}")
            return questions
        
    def _normalize(self, s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        return " ".join(str(s).split())  # trims + collapses internal whitespace

    def _find_option_index(self, options: Optional[List[str]], answer: Optional[str]) -> Optional[int]:
        if not options or answer is None:
            return None
        norm_answer = self._normalize(answer)
        for i, opt in enumerate(options, 1):  # 1-based
            if self._normalize(opt) == norm_answer:
                return i
        return None

    def prepare_question_content(self, json_data, passed_qc: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        try:
            passed_qc = self.merge_and_map(json_data, passed_qc)
            prepared: List[Dict[str, Any]] = []
            for entry in passed_qc:
                try:
                    # Basic presence check (optional but helpful)
                    missing = [k for k in required_items if k not in entry]
                    if missing:
                        print(f"Warning: missing keys {missing} in entry with question_number={entry.get('question_number')}")
                        continue
                    
                    qtype_str = entry.get("question_type")
                    qtype_code = question_type_dict.get(qtype_str)
                    if qtype_code is None:
                        print(f"Warning: unknown question_type '{qtype_str}'. Using None.")
                        continue
                    if qtype_code == 1 or qtype_code == 5:
                        options = entry.get("options")
                        option_a = options[0]
                        option_b = options[1]
                        option_c = options[2]
                        option_d = options[3]
                        expected_answer = entry.get("expected_answer")
                        crt_option = self._find_option_index(options, expected_answer)
                        if crt_option is None:
                            print(f"Warning: expected_answer '{expected_answer}' not found in options with question_number={entry.get('question_number')}")
                            continue
                    else:
                        option_a = None
                        option_b = None
                        option_c = None
                        option_d = None
                        crt_option = None

                    is_image = bool(entry.get("image_name"))  # do not mutate original key

                    # Prefer keeping question_number as a string if that’s your DB schema; else cast safely
                    q_id = entry.get("question_number")
                    # If you need int: 
                    try: q_id = int(q_id) 
                    except: pass

                    question = {
                        "question_number": q_id,
                        "question_type": qtype_code,
                        "max_marks": entry.get("max_marks"),
                        "question_no": entry.get("question_no"),
                        "question": entry.get("question_text"),
                        "explanation": entry.get("explanation"),
                        "expected_answer": entry.get("expected_answer"),
                        "key_points": entry.get("key_points") or [],
                        "marking_scheme": entry.get("marking_scheme"),
                        "image_description": entry.get("image_description") or None,
                        "option_a": option_a,
                        "option_b": option_b,
                        "option_c": option_c,
                        "option_d": option_d,
                        "crt_option": crt_option,
                        "is_image": is_image,
                        "part_of": entry.get("part_of"),
                        "s3_url": entry.get("s3_url")
                    }

                    prepared.append(question)

                except Exception as e:
                    print(f"Error preparing question (question_number={entry.get('question_number')}): {e}")
                    continue

            return prepared

        except Exception as e:
            print(f"Error in prepare_question_content: {e}")
            return None     
        
class QuestionCountAgent:
    """
    Specialized AI agent for extracting question count from various question paper formats.
    Uses LLM to intelligently count questions when regex patterns fail.
    """
    
    def __init__(self):
        self.model_name = "gemini-2.0-flash"
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            api_key=GOOGLE_API_KEY,
            temperature=0.0  # Deterministic output
        )
        self.prompt = PromptTemplate.from_template(prompts.question_count_extraction_prompt)
        self.chain = self.prompt | self.llm
    
    async def extract_question_count(self, question_paper_text: str) -> Optional[int]:
        """
        Extract the total number of questions from question paper text using LLM.
        
        Args:
            question_paper_text: The full markdown text of the question paper
            
        Returns:
            Integer count of questions, or None if extraction fails
        """
        if not question_paper_text or len(question_paper_text.strip()) < 50:
            logging.warning("Question paper text too short for agent analysis")
            return None
        
        try:
            # Truncate if text is very long (to save tokens)
            max_chars = 8000
            truncated_text = question_paper_text[:max_chars]
            if len(question_paper_text) > max_chars:
                logging.info(f"Truncated question paper from {len(question_paper_text)} to {max_chars} chars for agent")
            
            # Call the LLM
            response = await self.chain.ainvoke({"question_paper_text": truncated_text})
            
            # Extract the number from response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean and extract integer
            # Remove any extra text, keep only the number
            numbers = re.findall(r'\b(\d+)\b', response_text.strip())
            
            if numbers:
                count = int(numbers[0])  # Take first number found
                
                # Sanity check
                if 1 <= count <= 500:
                    logging.info(f"✓ [Question Count Agent] Extracted: {count} questions")
                    return count
                else:
                    logging.warning(f"Agent returned unreasonable count: {count}")
                    return None
            else:
                logging.warning(f"Agent response contains no number: {response_text}")
                return None
                
        except Exception as e:
            logging.error(f"Error in Question Count Agent: {e}")
            return None     
        
class QuestionTaggingAgent:
    """Agent to tag questions with chapter, topic, cognitive level, difficulty, and estimated time."""
    
    def __init__(self):
        self.model_name = "gemini-2.0-flash"
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            api_key=GOOGLE_API_KEY,
            temperature=0.0
        )
        self.parser = JsonOutputParser()
        self.prompt = PromptTemplate.from_template(prompts.question_tagging_prompt)
        self.chain = self.prompt | self.llm | self.parser
    
    def _prepare_questions_summary(self, questions: List[Dict[str, Any]]) -> str:
        """Prepare a clean summary of questions for the LLM."""
        summary = []
        for q in questions:
            q_num = q.get("question_number")
            q_text = q.get("question", "")[:200]  # First 200 chars
            q_type = q.get("question_type", "")
            marks = q.get("max_marks", "")
            
            summary.append(
                f"Q{q_num} ({q_type}, {marks}m): {q_text}..."
            )
        return "\n".join(summary)
    
    async def tag_questions(
        self,
        questions: List[Dict[str, Any]],
        subject: str,
        class_name: str,
        question_paper_text: str = ""
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Tags questions with chapter, topic, cognitive_level, difficulty, and estimated_time.
        
        Args:
            questions: List of question dictionaries
            subject: Subject name (e.g., "Science", "Mathematics")
            class_name: Class/grade (e.g., "Class-10")
            question_paper_text: Optional full question paper text for context
        
        Returns:
            Tuple of (tagged_questions, token_usage)
        """
        if not questions:
            logging.warning("No questions provided for tagging")
            return [], {}
        
        # Prepare questions data
        questions_summary = self._prepare_questions_summary(questions)
        
        try:
            # Call LLM for tagging
            response = await self.chain.ainvoke({
                "subject": subject,
                "class_name": class_name,
                "question_paper_text": question_paper_text[:3000] if question_paper_text else "Not provided",
                "questions_data": questions_summary
            })
            
            # Parse response
            if isinstance(response, str):
                tagging_results = self.parser.parse(response)
            else:
                tagging_results = response
            
            # Extract token usage (if available)
            tokens = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
            }
            
            # Create a lookup map
            tag_map = {tag["question_number"]: tag for tag in tagging_results}
            
            # Merge tags into questions
            tagged_questions = []
            for q in questions:
                q_num = q.get("question_number")
                if q_num in tag_map:
                    tag_data = tag_map[q_num]
                    q_copy = q.copy()
                    q_copy.update({
                        "chapter": tag_data.get("chapter"),
                        "topic": tag_data.get("topic"),
                        "cognitive_level": tag_data.get("cognitive_level"),
                        "difficulty": tag_data.get("difficulty"),
                        "estimated_time": tag_data.get("estimated_time")
                    })
                    tagged_questions.append(q_copy)
                else:
                    logging.warning(f"No tags found for question {q_num}")
                    tagged_questions.append(q)
            
            logging.info(f"✅ Successfully tagged {len(tagged_questions)} questions")
            return tagged_questions, tokens
            
        except Exception as e:
            logging.error(f"Error in tagging agent: {e}")
            # Return original questions if tagging fails
            return questions, {}
    
    async def tag_questions_batch(
        self,
        questions: List[Dict[str, Any]],
        subject: str,
        class_name: str,
        question_paper_text: str = "",
        batch_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Tags questions in batches for better performance with large question sets.
        
        Args:
            questions: List of question dictionaries
            subject: Subject name
            class_name: Class/grade
            question_paper_text: Optional full question paper text
            batch_size: Number of questions per batch
        
        Returns:
            Tuple of (all_tagged_questions, total_token_usage)
        """
        all_tagged = []
        total_tokens = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }
        
        # Split into batches
        batches = [
            questions[i:i + batch_size]
            for i in range(0, len(questions), batch_size)
        ]
        
        for i, batch in enumerate(batches, 1):
            logging.info(f"Tagging batch {i}/{len(batches)} ({len(batch)} questions)")
            
            tagged_batch, batch_tokens = await self.tag_questions(
                batch, subject, class_name, question_paper_text
            )
            
            all_tagged.extend(tagged_batch)
            
            # Aggregate tokens
            total_tokens["total_input_tokens"] += batch_tokens.get("total_input_tokens", 0)
            total_tokens["total_output_tokens"] += batch_tokens.get("total_output_tokens", 0)
            total_tokens["total_tokens"] += batch_tokens.get("total_tokens", 0)
        
        return all_tagged, total_tokens

qllm_helper_function = question_paper_function()
llm_helper_function = llm_function()
ocr_helper_function = ImageTagger()
question_count_agent = QuestionCountAgent()
tagging_agent = QuestionTaggingAgent()
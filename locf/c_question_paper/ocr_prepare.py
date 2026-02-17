from locf.c_question_paper.helper_function import ocr_helper_function, llm_helper_function, qllm_helper_function
from locf.c_question_paper import classes
from locf.c_question_paper.db import add_image_details
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from locf.c_question_paper.parser_helper import json_helpers
from typing import List, Dict, Any, Tuple
import logging, json, re, traceback,boto3, os
from dotenv import load_dotenv

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

s3 = boto3.client("s3",
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)

AWS_S3_REGION= os.getenv("AWS_S3_REGION")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")

class ocr_prepare_function:
     def __init__(self):
          self.bucket_name = AWS_S3_BUCKET_NAME
          self.s3_region = AWS_S3_REGION
          self.batch_size = 5
          self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash",api_key=os.getenv('GOOGLE_API_KEY'))

     async def ocr_process(self, request: classes.QuestionPaperRequest) -> tuple[List[Dict[str, Any]], List[str], Any, Any]:
          """Orchestrates the entire streamlined image tagging process."""
          try:
               batches = ocr_helper_function.get_page_batches(request.pdf_url)
               if not batches:
                    return [], [], None, None

               all_final_tags = []
               base_s3_url = f"https://{self.bucket_name}.s3.{AWS_S3_REGION}.amazonaws.com"

               for i, batch in enumerate(batches, 1):
                    logging.info(f"\n--- Processing Batch {i}/{len(batches)} (Pages: {batch}) ---")

                    pdf_response = ocr_helper_function.perform_basic_ocr(request.pdf_url, batch)
                    if not pdf_response or not any(p.images for p in pdf_response.pages):
                         logging.warning(f"No images found in batch {i}. Skipping.")
                         continue

                    s3_key_map = ocr_helper_function.save_images_to_s3(pdf_response, request.uuid, i)
                    image_tags = await ocr_helper_function.generate_image_tags(pdf_response)

                    for tag in image_tags:
                         image_id = tag.image_name
                         if image_id in s3_key_map:
                              s3_key = s3_key_map[image_id]
                              final_tag = classes.FinalImageTag(
                                   **tag.model_dump(),
                                   s3_url=f"{base_s3_url}/{s3_key}"
                              )
                              all_final_tags.append(final_tag)
                         else:
                              logging.warning(f"Could not find a saved S3 key for image_id '{image_id}'")

               json_data = [tag.model_dump() for tag in all_final_tags]
               image_list = [img['s3_url'] for img in json_data]
               gen_response, md_results = await llm_helper_function.llm_ocr_process(request.pdf_url)
               
               return json_data, image_list, gen_response, md_results
          except Exception as e:
               logging.error(f"An unexpected error occurred in ocr_process: {e}")
               logging.error(traceback.format_exc())
               return [], [], None, None

     async def _process_batch_with_retry(self,batch: List[Dict],batch_num: int,question_type: str,prompt_text: str,messages_content: List[Dict],max_retries: int) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
          """process a single batch with retry logic for missing questions."""
          try:
               target_identifiers = set()
               for q in batch:
                    q_num = str(q.get('question_number'))
                    or_option = q.get('or_option')
                    
                    if or_option:
                         target_identifiers.add((q_num, or_option))
                    else:
                         target_identifiers.add(q_num)
               
               all_results = []
               batch_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
               
               current_batch = batch
               
               for attempt in range(max_retries):
                    try:
                         if attempt > 0:
                              logging.info(f"   🔄 Retry {attempt}/{max_retries - 1} for batch {batch_num}")
                         
                         prompt_template = ChatPromptTemplate.from_messages([("system", prompt_text),MessagesPlaceholder("human_messages")])
                         
                         cleaned_batch = []
                         for idx, q in enumerate(current_batch):
                              q_num = str(q.get('question_number'))
                              parts = q.get('parts', [])
                              
                              if parts:
                                   first_text = parts[0].get('text', '')[:80]
                              else:
                                   first_text = ''
                              
                              cleaned_q = {
                                   "question_number": q_num,
                                   "has_sub_questions": q.get('has_sub_questions', False),
                                   "parts": parts,
                                   "_text_preview": first_text
                              }
                              cleaned_batch.append(cleaned_q)
                                                  
                         msgs = prompt_template.format_messages(question_list=json.dumps(cleaned_batch, indent=2),human_messages=messages_content)
                         
                         response = await self.llm.ainvoke(msgs)
                         gen_content = response.content
                         
                         response_tokens = qllm_helper_function._extract_tokens(response)
                         if response_tokens:
                              qllm_helper_function._merge_tokens(batch_tokens, response_tokens)
                         
                         parser = JsonOutputParser()
                         try:
                              parsed_results = parser.parse(gen_content)
                              if isinstance(parsed_results, dict):
                                   parsed_results = [parsed_results]
                         except Exception as e:
                              logging.warning(f"Failed to parse JSON with LangChain parser. Falling back.")
                              gen_text = qllm_helper_function._ensure_text(gen_content)
                              parsed_results = json_helpers.parse_json(gen_text)
                              if isinstance(parsed_results, dict):
                                   parsed_results = [parsed_results]
                         
                         if not parsed_results:
                              logging.error(f"   ❌ Attempt {attempt + 1}: No results parsed")
                              continue
                         
                         returned_details = []
                         for r in parsed_results:
                              q_num = str(r.get('question_number'))
                              parts = r.get('parts', [])
                              if parts:
                                   text_preview = parts[0].get('text', '')[:40]
                                   returned_details.append(f"{q_num}:{text_preview}...")
                              else:
                                   returned_details.append(f"{q_num}:NO_TEXT")
                              
                         original_by_qnum = {}
                         for idx, q in enumerate(current_batch):
                              q_num = str(q.get('question_number'))
                              if q_num not in original_by_qnum:
                                   original_by_qnum[q_num] = []
                              original_by_qnum[q_num].append(q)
                         
                         for result_idx, result in enumerate(parsed_results):
                              q_num = str(result.get('question_number'))
                              result_parts = result.get('parts', [])
                              
                              already_processed = False
                              
                              if q_num in original_by_qnum:
                                   candidates = original_by_qnum[q_num]
                                   if candidates:
                                        original_question = candidates[0]
                                        has_sub_questions = original_question.get('has_sub_questions', False)
                                        alternative_ques = original_question.get('alternative_ques', False)
                                        
                                        if not has_sub_questions and not alternative_ques:
                                             existing_qnums = [str(r.get('question_number')) for r in all_results]
                                             already_processed = q_num in existing_qnums
                                             
                                        elif has_sub_questions and not alternative_ques:
                                             existing_keys = []
                                             for r in all_results:
                                                  r_qnum = str(r.get('question_number'))
                                                  r_parts = r.get('parts', [])
                                                  if r_qnum == q_num and r_parts:
                                                       r_part_label = r_parts[0].get('part_label')
                                                       existing_keys.append((r_qnum, r_part_label))
                                             
                                             same_qnum_results = [r for r in all_results if str(r.get('question_number')) == q_num]
                                             current_part_index = len(same_qnum_results)
                                             
                                             if current_part_index < len(candidates):
                                                  expected_part_label = candidates[current_part_index].get('parts', [{}])[0].get('part_label')
                                                  already_processed = (q_num, expected_part_label) in existing_keys
                                             else:
                                                  already_processed = True
                                             
                                        elif not has_sub_questions and alternative_ques:
                                             existing_keys = []
                                             for r in all_results:
                                                  r_qnum = str(r.get('question_number'))
                                                  r_or_option = r.get('or_option')
                                                  if r_qnum == q_num:
                                                       existing_keys.append((r_qnum, r_or_option))
                                             
                                             same_qnum_results = [r for r in all_results if str(r.get('question_number')) == q_num]
                                             current_or_index = len(same_qnum_results)
                                             
                                             if current_or_index < len(candidates):
                                                  expected_or_option = candidates[current_or_index].get('or_option')
                                                  already_processed = (q_num, expected_or_option) in existing_keys
                                             else:
                                                  already_processed = True
                              
                              if not already_processed:
                                   if q_num in original_by_qnum:
                                        candidates = original_by_qnum[q_num]
                                        
                                        if len(candidates) > 1:
                                             logging.info(f"   🔍 Order-based matching Q{q_num} with {len(candidates)} candidates")
                                             
                                             same_qnum_results = [r for r in all_results if str(r.get('question_number')) == q_num]
                                             candidate_index = len(same_qnum_results)
                                             
                                             if candidate_index < len(candidates):
                                                  original = candidates[candidate_index]
                                                  logging.info(f"   ✅ Order-matched Q{q_num} result #{candidate_index + 1} to candidate #{candidate_index + 1}")
                                             else:
                                                  logging.error(f"   ❌ No candidate available for Q{q_num} result #{candidate_index + 1}")
                                                  original = None
                                        elif len(candidates) == 1:
                                             original = candidates[0]
                                        else:
                                             logging.error(f"   ❌ No candidates found for Q{q_num}")
                                             original = None
                                   else:
                                        logging.error(f"   ❌ No original question found for Q{q_num}")
                                        original = None
                                   
                                   if original:
                                        result['or_option'] = original.get('or_option')
                                        result['is_or_question'] = original.get('is_or_question')
                                        result['alternative_ques'] = original.get('alternative_ques')
                                        result['s3_url'] = original.get('s3_url')
                                        result['part_of'] = original.get('part_of')
                                        result['image_name'] = original.get('image_name')
                                        
                                        result['_matched_original'] = original
                                        
                                   else:
                                        logging.warning(f"   ⚠️ Could not match Q{q_num} to any original question")
                                   
                                   all_results.append(result)
                              else:
                                   logging.warning(f"   ⚠️ Q{q_num} already processed, skipping duplicate")
                              
                         generated_identifiers = set()
                         for q in all_results:
                              q_num = str(q.get('question_number'))
                              or_option = q.get('or_option')
                              if or_option:
                                   generated_identifiers.add((q_num, or_option))
                              else:
                                   generated_identifiers.add(q_num)
                         
                         missing_identifiers = target_identifiers - generated_identifiers
                         
                         if not missing_identifiers:
                              logging.info(f"   ✅ Batch {batch_num} complete: {len(all_results)}/{len(batch)} questions enriched")
                              return all_results, batch_tokens

                         missing_list = sorted([str(m) if not isinstance(m, tuple) else f"{m[0]}-Opt{m[1]}" for m in missing_identifiers])
                         logging.warning(f"   ⚠️ Missing questions: {missing_list}")
                         
                         if attempt < max_retries - 1:
                              current_batch = []
                              for q in batch:
                                   q_num = str(q.get('question_number'))
                                   or_option = q.get('or_option')
                                   
                                   if or_option:
                                        identifier = (q_num, or_option)
                                   else:
                                        identifier = q_num
                                   
                                   if identifier in missing_identifiers:
                                             current_batch.append(q)
                              
                              logging.info(f"   🎯 Re-targeting {len(current_batch)} missing questions: {missing_list}")
                         else:
                              logging.error(f"   ⚠️ Batch {batch_num} incomplete after {max_retries} attempts")
                              logging.info(f"   📊 Generated: {len(all_results)}/{len(batch)}")
                              logging.error(f"   ❌ Still missing: {missing_list}")
                              return all_results, batch_tokens
                         
                    except Exception as e:
                         logging.error(f"Error in batch {batch_num} attempt {attempt + 1}: {e}")
                         if attempt == max_retries - 1:
                              logging.error(f"   ❌ All {max_retries} attempts failed for batch {batch_num}")
                              return all_results, batch_tokens
                         continue
               
               return all_results, batch_tokens
          except Exception as e:
               logging.error(f"An unexpected error occurred in _process_batch_with_retry for batch {batch_num}: {e}")
               logging.error(traceback.format_exc())
               return [], {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}

     def validate_question_data(self, question: Dict[str, Any]) -> Tuple[bool, List[str]]:
          """ Validate that a question has all required fields from both agents. """
          try:
               missing_fields = []
               
               for field in classes.required_items_extraction:
                    if field not in question or question[field] is None:
                         missing_fields.append(f"[Extraction] {field}")
               
               parts = question.get("parts", [])
               if not parts or len(parts) == 0:
                    missing_fields.append("[Extraction] parts (empty array)")
               else:
                    for idx, part in enumerate(parts):
                         for field in classes.required_part_fields_extraction:
                              if field == "part_label":
                                   continue
                              if field not in part or part.get(field) is None:
                                   missing_fields.append(f"[Extraction] parts[{idx}].{field}")
                         
                         for field in classes.required_part_fields_enrichment:
                              value = part.get(field)
                              if value is None:
                                   missing_fields.append(f"[Enrichment] parts[{idx}].{field}")
                              elif isinstance(value, str) and value.strip() == "":
                                   missing_fields.append(f"[Enrichment] parts[{idx}].{field} (empty)")
                              elif isinstance(value, list) and len(value) == 0:
                                   missing_fields.append(f"[Enrichment] parts[{idx}].{field} (empty array)")
                         
                         question_type = part.get("question_type")
                         if question_type in ["MCQ", "A/R"]:
                              expected_answer = part.get("expected_answer")
                              options = part.get("options")
                              
                              if not options or not isinstance(options, list) or len(options) == 0:
                                   missing_fields.append(f"[Validation] parts[{idx}].options (MCQ/A&R must have options)")
                              elif not expected_answer or not isinstance(expected_answer, str):
                                   missing_fields.append(f"[Validation] parts[{idx}].expected_answer (MCQ/A&R must have expected_answer)")
                              else:
                                   expected_answer_clean = expected_answer.strip()
                                   options_clean = [opt.strip() for opt in options if isinstance(opt, str)]
                                   
                                   if expected_answer_clean not in options_clean:
                                        missing_fields.append(f"[Validation] parts[{idx}].expected_answer does not match any option (MCQ/A&R)")
               
               return len(missing_fields) == 0, missing_fields
          except Exception as e:
               logging.error(f"An unexpected error occurred in validate_question_data: {e}")
               logging.error(traceback.format_exc())
               return False, []
     
     def validate_all_questions(self, questions: List[Dict]) -> Tuple[List[Dict], List[str], Dict]:
          """ Validate all questions and separate valid from invalid. """
          try:
               valid_questions = []
               failed_questions = []
               validation_report = {
                    "total_questions": len(questions),
                    "valid_questions": 0,
                    "failed_questions": 0,
                    "failures": {}
               }
               
               for question in questions:
                    q_num = str(question.get('question_number', 'unknown'))
                    is_valid, missing_fields = self.validate_question_data(question)
                    
                    if is_valid:
                         valid_questions.append(question)
                         validation_report["valid_questions"] += 1
                    else:
                         failed_questions.append(q_num)
                         validation_report["failed_questions"] += 1
                         validation_report["failures"][q_num] = missing_fields
                         
                         logging.error(f"❌ Question {q_num} FAILED validation:")
                         for field in missing_fields:
                              logging.error(f"   ├─ Missing: {field}")
                         
               logging.info(f"📊 VALIDATION SUMMARY:")
               logging.info(f"   ├─ Total Questions: {validation_report['total_questions']}")
               logging.info(f"   ├─ Valid: {validation_report['valid_questions']} ✅")
               logging.info(f"   ├─ Failed: {validation_report['failed_questions']} ❌")
               if failed_questions:
                    logging.info(f"   └─ Failed Question Numbers: {failed_questions}")
               else:
                    logging.info(f"   └─ All questions passed validation! ✅")
               
               return valid_questions, failed_questions, validation_report
          except Exception as e:
               logging.error(f"An unexpected error occurred in validate_all_questions: {e}")
               logging.error(traceback.format_exc())
               return [], [], {}

     def split_or_questions(self, questions: List[Dict]) -> List[Dict]:
          """ Detect and split OR questions into separate question entries. """
          try:
               processed_questions = []
               total_or_detected = 0
               
               logging.info(f"🔀 DETECTING AND SPLITTING OR QUESTIONS")
               
               for question in questions:
                    q_num = str(question.get('question_number', ''))
                    parts = question.get('parts', [])
                    
                    if not parts or len(parts) <= 1:
                         processed_questions.append(question)
                         continue
                    
                    alternative_ques_flag = question.get('alternative_ques', False)
                    has_or = False
                    or_part_indices = []
                    
                    for idx, part in enumerate(parts):
                         text = part.get('text', '')
                         if text.strip().startswith('[OR]') or text.strip().startswith('(OR)'):
                              has_or = True
                              or_part_indices.append(idx)
                    
                    if alternative_ques_flag and not has_or:
                         for idx in range(1, len(parts)):
                              or_part_indices.append(idx)
                         has_or = True
                    
                    if not has_or and not alternative_ques_flag:
                         processed_questions.append(question)
                         continue
                    
                    total_or_detected += 1
                    logging.info(f"📝 Question {q_num}: Detected OR alternative(s)")
                    logging.info(f"   ├─ Original parts: {len(parts)}")
                    logging.info(f"   ├─ OR alternatives at indices: {or_part_indices}")
                    
                    first_or_idx = or_part_indices[0]
                    main_parts = parts[:first_or_idx]
                    
                    if main_parts:
                         main_question = {**question}
                         main_question['parts'] = main_parts
                         main_question['has_sub_questions'] = len(main_parts) > 1
                         main_question['alternative_ques'] = True
                         main_question['is_or_question'] = True
                         main_question['or_option'] = 'A'
                         processed_questions.append(main_question)
                         logging.info(f"   ├─ Created Question {q_num} (Option A): {len(main_parts)} parts")
                    
                    for or_idx, part_idx in enumerate(or_part_indices):
                         if or_idx + 1 < len(or_part_indices):
                              or_parts = parts[part_idx:or_part_indices[or_idx + 1]]
                         else:
                              or_parts = parts[part_idx:]
                         
                         if or_parts:
                              or_parts[0] = {**or_parts[0]}
                              text = or_parts[0].get('text', '')
                              text = text.replace('[OR]', '').replace('(OR)', '').strip()
                              or_parts[0]['text'] = text
                         
                         or_question = {**question}
                         or_question['question_number'] = q_num
                         or_question['parts'] = or_parts
                         or_question['has_sub_questions'] = len(or_parts) > 1
                         or_question['alternative_ques'] = True
                         or_question['is_or_question'] = True
                         or_question['or_option'] = chr(66 + or_idx)
                         processed_questions.append(or_question)
                         logging.info(f"   └─ Created Question {q_num} (Option {chr(66 + or_idx)}): {len(or_parts)} parts")

               logging.info(f"✅ OR QUESTION SPLITTING COMPLETE")
               logging.info(f"   ├─ Total questions processed: {len(questions)}")
               logging.info(f"   ├─ OR questions detected: {total_or_detected}")
               logging.info(f"   └─ Questions after split: {len(processed_questions)}")
               return processed_questions
          except Exception as e:
               logging.error(f"An unexpected error occurred in split_or_questions: {e}")
               logging.error(traceback.format_exc())
               return []

     def flatten_questions_for_db(self, questions: List[Dict]) -> List[Dict]:
          """Flatten the new question structure (with parts array) to match the database schema. For questions with sub-parts, create multiple DB entries (one per sub-part)."""
          try:
               flattened = []
               for question in questions:
                    q_num_str = str(question.get('question_number', ''))
                    match = re.match(r'^(\d+)', q_num_str)
                    q_num_int = int(match.group(1)) if match else 0
                    
                    is_or_question = question.get('is_or_question', False)
                    alternative_ques = question.get('alternative_ques', False)
                    or_option = question.get('or_option', None)
                    
                    has_sub = question.get('has_sub_questions', False)
                    parts = question.get('parts', [])
                    
                    # s3_url = question.get('s3_url')
                    # part_of = question.get('part_of')
                    # image_name = question.get('image_name')
                    
                    if not has_sub and len(parts) == 1:
                         part = parts[0]
                         
                         reason_text = None
                         if is_or_question and or_option:
                              reason_text = f"OR_OPTION_{or_option}"
                         
                         qc_field = "ALTERNATIVE_QUESTION" if alternative_ques else None
                         
                         flattened.append({
                              "question_number": q_num_int,
                              "part_label": None,
                              "has_sub_questions": False,
                              "alternative_ques": alternative_ques,
                              "is_or_question": is_or_question,
                              "or_option": or_option,
                              "question_type": part.get('question_type'),
                              "max_marks": part.get('marks'),
                              "question": part.get('text', ''),
                              "options": part.get('options'),
                              "explanation": part.get('explanation', ''),
                              "expected_answer": part.get('expected_answer', ''),
                              "marking_scheme": part.get('marking_scheme', ''),
                              "key_points": part.get('key_points', []),
                              "cognitive_level": part.get('cognitive_level'),  # Bloom's Taxonomy
                              "difficulty": part.get('difficulty'),  # Easy/Medium/Hard
                              "estimated_time": part.get('estimated_time'),  # Float minutes
                              # "s3_url": s3_url,
                              # "part_of": part_of,
                              # "image_name": image_name,
                              "reason": reason_text,
                              "images": question.get('images'),
                              "s3_url_list": question.get('s3_url_list'),
                              "part_of_list": question.get('part_of_list'),
                              "QC": qc_field
                         })
                    else:
                         for part in parts:
                              reason_text = None
                              if is_or_question and or_option:
                                   reason_text = f"OR_OPTION_{or_option}"
                              
                              qc_field = "ALTERNATIVE_QUESTION" if alternative_ques else None
                              
                              flattened.append({
                                   "question_number": q_num_int,
                                   "part_label": part.get('part_label'),
                                   "has_sub_questions": True,
                                   "alternative_ques": alternative_ques,
                                   "is_or_question": is_or_question,
                                   "or_option": or_option,
                                   "question_type": part.get('question_type'),
                                   "max_marks": part.get('marks'),
                                   "question": part.get('text', ''),
                                   "options": part.get('options'),
                                   "explanation": part.get('explanation', ''),
                                   "expected_answer": part.get('expected_answer', ''),
                                   "marking_scheme": part.get('marking_scheme', ''),
                                   "key_points": part.get('key_points', []),
                                   "cognitive_level": part.get('cognitive_level'),  # Bloom's Taxonomy
                                   "difficulty": part.get('difficulty'),  # Easy/Medium/Hard
                                   "estimated_time": part.get('estimated_time'),  # Float minutes
                                   # "s3_url": s3_url,
                                   # "part_of": part_of,
                                   # "image_name": image_name,
                                   "reason": reason_text,
                                   "QC": qc_field,
                                   "images": question.get('images'),
                                   "s3_url_list": question.get('s3_url_list'),
                                   "part_of_list": question.get('part_of_list'),
                              })
               return flattened
          except Exception as e:
               logging.error(f"An unexpected error occurred in flatten_questions_for_db: {e}")
               logging.error(traceback.format_exc())
               return []
     
     def merge_enriched_data(self,original_questions: List[Dict],enriched_questions: List[Dict],json_data: List[Dict] = None) -> List[Dict]:
          """Merge enriched data (explanations, answers, etc.) back into original questions by matching question_number and part_label. Also merge image data by question_no."""
          try:
               enriched_lookup = {}
               for enriched in enriched_questions:
                    q_num = str(enriched.get('question_number', ''))
                    or_option = enriched.get('or_option')
                    
                    if or_option:
                         key = (q_num, or_option)
                    else:
                         key = q_num
                    
                    enriched_lookup[key] = enriched
               
               # Store MULTIPLE images per question (key: question_no, value: list of images)
               image_lookup = {}
               if json_data:
                    for img in json_data:
                         q_no = str(img.get('question_no', ''))
                         if q_no:
                              if q_no not in image_lookup:
                                   image_lookup[q_no] = []
                              image_lookup[q_no].append(img)
               
               merged_results = []
               
               for original in original_questions:
                    q_num = str(original.get('question_number', ''))
                    or_option = original.get('or_option')
                    
                    if or_option:
                         key = (q_num, or_option)
                    else:
                         key = q_num
                    
                    enriched = enriched_lookup.get(key)
                    
                    if or_option:
                         if enriched:
                              logging.info(f"✅ Matched Q{q_num} Option {or_option} with enriched data")
                         else:
                              logging.warning(f"⚠️ No enriched data found for Q{q_num} Option {or_option}")
                    
                    if enriched:
                         merged_question = {**original}
                         merged_question['has_sub_questions'] = enriched.get('has_sub_questions', False)
                         
                         original_parts = original.get('parts', [])
                         enriched_parts = enriched.get('parts', [])
                         
                         merged_parts = []
                         for orig_part in original_parts:
                              orig_label = orig_part.get('part_label')
                              
                              enriched_part = None
                              for enr_part in enriched_parts:
                                   if enr_part.get('part_label') == orig_label:
                                        enriched_part = enr_part
                                        break
                              
                              if enriched_part:
                                   merged_part = {**orig_part, **enriched_part}
                              else:
                                   merged_part = orig_part
                              
                              merged_parts.append(merged_part)
                         
                         merged_question['parts'] = merged_parts
                         
                         # Handle MULTIPLE images per question
                         img_list = image_lookup.get(q_num, [])
                         if img_list:
                              # Store first image in legacy fields for backward compatibility
                              # first_img = img_list[0]
                              # merged_question['s3_url'] = first_img.get('s3_url')
                              # merged_question['part_of'] = first_img.get('part_of')
                              # merged_question['image_name'] = first_img.get('image_name')
                              # Store ALL images in a new field for multiple image support
                              merged_question['images'] = img_list
                         else:
                              # merged_question['s3_url'] = None
                              # merged_question['part_of'] = None
                              # merged_question['image_name'] = None
                              merged_question['images'] = []
                         
                         merged_results.append(merged_question)
                    else:
                         logging.warning(f"No enriched data found for question {q_num}")
                         
                         # Handle MULTIPLE images per question
                         img_list = image_lookup.get(q_num, [])
                         original_with_img = {**original}
                         if img_list:
                              # Store first image in legacy fields for backward compatibility
                              # first_img = img_list[0]
                              # original_with_img['s3_url'] = first_img.get('s3_url')
                              # original_with_img['part_of'] = first_img.get('part_of')
                              # original_with_img['image_name'] = first_img.get('image_name')
                              # Store ALL images in a new field for multiple image support
                              original_with_img['images'] = img_list
                         else:
                              # original_with_img['s3_url'] = None
                              # original_with_img['part_of'] = None
                              # original_with_img['image_name'] = None
                              original_with_img['images'] = []
                         
                         merged_results.append(original_with_img)
               
               with_images = sum(1 for q in merged_results if q.get('images') is not None)
               without_images = len(merged_results) - with_images
               
               logging.info(f"✅ Merged {len(merged_results)} questions")
               logging.info(f"   ├─ With images: {with_images}")
               logging.info(f"   └─ Without images: {without_images}")
               return merged_results
          except Exception as e:
               logging.error(f"An unexpected error occurred in merge_enriched_data: {e}")
               logging.error(traceback.format_exc())
               return []

     def clean_invalid_parts(self, questions: List[Dict]) -> List[Dict]:
          """Remove invalid introductory/passage parts that have part_label = null/None and marks = 0 or null/None"""
          try:
               cleaned_questions = []
               total_removed = 0
                         
               for question in questions:
                    q_num = str(question.get('question_number', ''))
                    parts = question.get('parts', [])
                    
                    if not parts:
                         cleaned_questions.append(question)
                         continue
                    
                    valid_parts = []
                    removed_parts = []
                    
                    for idx, part in enumerate(parts):
                         part_label = part.get('part_label')
                         marks = part.get('marks')
                         
                         is_invalid = (
                         (part_label is None or part_label == '') and 
                         (marks is None or marks == 0 or marks == '')
                         )
                         
                         if is_invalid:
                              removed_parts.append({
                                   'index': idx,
                                   'text_preview': part.get('text', '')[:100] + '...' if len(part.get('text', '')) > 100 else part.get('text', ''),
                                   'marks': marks,
                                   'part_label': part_label
                              })
                              total_removed += 1
                         else:
                              valid_parts.append(part)
                    
                    if removed_parts:
                         logging.info(f"📝 Question {q_num}:")
                         logging.info(f"   ├─ Original parts: {len(parts)}")
                         logging.info(f"   ├─ Valid parts: {len(valid_parts)}")
                         logging.info(f"   └─ Removed parts: {len(removed_parts)}")
                         for removed in removed_parts:
                              logging.info(f"      ❌ Part {removed['index']}: '{removed['text_preview']}' (marks={removed['marks']}, label={removed['part_label']})")
                    
                    if valid_parts:
                         cleaned_question = {**question}
                         cleaned_question['parts'] = valid_parts
                         
                         if len(valid_parts) > 1:
                              cleaned_question['has_sub_questions'] = True
                         elif len(valid_parts) == 1:
                              cleaned_question['has_sub_questions'] = False
                         
                         cleaned_questions.append(cleaned_question)
                    else:
                         logging.info(f"⚠️ Question {q_num} has NO valid parts after cleaning! Keeping original.")
                         cleaned_questions.append(question)
               
               logging.info(f"✅ CLEANUP COMPLETE")
               logging.info(f"   ├─ Total questions processed: {len(questions)}")
               logging.info(f"   ├─ Total invalid parts removed: {total_removed}")
               logging.info(f"   └─ Questions remaining: {len(cleaned_questions)}")
               
               return cleaned_questions
          except Exception as e:
               logging.error(f"An unexpected error occurred in clean_invalid_parts: {e}")
               logging.error(traceback.format_exc())
               return []

                              
ocr_prepare_instance = ocr_prepare_function()
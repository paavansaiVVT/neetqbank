import os, base64, asyncio, boto3, requests, logging, re, uuid, json, traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Optional, Literal, Dict, Any, Tuple
from dotenv import load_dotenv
from io import BytesIO
from locf.c_question_paper import prompts, classes, db, parser_helper
from locf.c_question_paper.helper_function import ocr_helper_function, llm_helper_function, qllm_helper_function
from locf.c_question_paper.ocr_prepare import ocr_prepare_instance

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

GOOGLE_API_KEY= os.getenv('GOOGLE_API_KEY')

class doc_ocr:
    def __init__(self):
        self.batch_size = 5
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash",api_key=GOOGLE_API_KEY)
        self.json_parser = JsonOutputParser()

    async def process_questions_in_batches(self,questions_list: List[Dict],question_type: str,json_data: List[Dict],batch_size: int = 15,max_retries: int = 3) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """process questions in batches to add explanations, answers, etc. with retry logic."""
        try:
            if not questions_list:
                return [], {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
            
            messages_content = llm_helper_function.build_user_message_dict(urls=json_data)
            
            prompt_text = (prompts.single_question_processing_prompt if question_type == 'single' else prompts.sub_question_processing_prompt)
            
            target_question_identifiers = set()
            for q in questions_list:
                q_num = str(q.get('question_number'))
                or_option = q.get('or_option')
                
                if or_option:
                    target_question_identifiers.add((q_num, or_option))
                else:
                    target_question_identifiers.add(q_num)
            
            total_target = len(questions_list)
            
            num_batches = (len(questions_list) + batch_size - 1) // batch_size

            all_processed = []
            total_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
            
            tasks = []
            for batch_idx in range(0, len(questions_list), batch_size):
                batch = questions_list[batch_idx:batch_idx + batch_size]
                batch_num = (batch_idx // batch_size) + 1
                
                logging.info(f"📦 Batch {batch_num}/{num_batches}: Processing {len(batch)} questions")
                
                task = ocr_prepare_instance._process_batch_with_retry(batch=batch,batch_num=batch_num,question_type=question_type,prompt_text=prompt_text,messages_content=messages_content,max_retries=max_retries)
                tasks.append(task)
            
            logging.info(f"🚀 Starting parallel batch processing for {len(tasks)} batches...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"❌ Batch {i+1} failed with error: {result}")
                    continue
                
                batch_result, batch_tokens = result
                if batch_result:
                    all_processed.extend(batch_result)
                
                if batch_tokens:
                    qllm_helper_function._merge_tokens(total_tokens, batch_tokens)
            
            generated_identifiers = set()
            for q in all_processed:
                q_num = str(q.get('question_number'))
                or_option = q.get('or_option')
                
                if or_option:
                    generated_identifiers.add((q_num, or_option))
                else:
                    generated_identifiers.add(q_num)
            
            missing_identifiers = target_question_identifiers - generated_identifiers
            missing_questions = sorted([str(m) if not isinstance(m, tuple) else f"{m[0]}-Opt{m[1]}" for m in missing_identifiers])
            
            logging.info(f"📊 FINAL VALIDATION: {question_type.upper()} QUESTIONS")
            logging.info(f"   ├─ Target: {total_target} questions")
            logging.info(f"   ├─ Generated: {len(all_processed)} questions")
            logging.info(f"   ├─ Missing: {missing_questions if missing_questions else 'None'}")
            logging.info(f"   └─ Status: {'✅ COMPLETE' if not missing_questions else '⚠️ INCOMPLETE'}")
            
            if missing_questions:
                logging.warning(f"Missing {question_type} questions after all retries: {missing_questions}")
            
            return all_processed, total_tokens
        except Exception as e:
            logging.error(f"An unexpected error occurred in process_questions_in_batches: {e}")
            logging.error(traceback.format_exc())
            return [], {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
    
    async def question_scheme(self, request: classes.QuestionPaperRequest) -> List[Dict[str, Any]]:
        try:
            enrichment_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
            json_data, image_list, gen_response, md_results = await ocr_prepare_instance.ocr_process(request)            
            qp_md, qcount = await qllm_helper_function.question_preparation(gen_response, md_results)
            if not isinstance(qcount, int) or qcount <= 0:
                logging.error(f"Invalid question count received: {qcount}. Cannot proceed.")
                return []

            try:
                q_json, extraction_tokens = await qllm_helper_function.question_paper_extraction(pdf_url=request.pdf_url,expected_question_count=qcount,max_retries=3,strict_mode=True,batch_size=20)
                
                if not q_json or "questions" not in q_json:
                    raise ValueError("Question extraction returned invalid format")
                
                extracted_count = len(q_json.get("questions", []))
                if extracted_count != qcount:
                    raise ValueError(f"Final verification failed: Expected {qcount} questions, but got {extracted_count} in the result")
                
                logging.info(f"✅ Question extraction successful: All {qcount} questions extracted and verified")
                
            except ValueError as e:
                logging.error(f"❌ CRITICAL: Question extraction failed: {e}")
                logging.error(f"Cannot proceed without all {qcount} questions")
                raise RuntimeError(f"Failed to extract all {qcount} questions from PDF. This is a critical failure for exam processing. Error: {e}")

            raw_questions = q_json.get("questions", [])
            or_split_questions = ocr_prepare_instance.split_or_questions(raw_questions)
            cleaned_questions = ocr_prepare_instance.clean_invalid_parts(or_split_questions)
            q_json["questions"] = cleaned_questions
            single_questions = []
            sub_questions = []
            
            for item in cleaned_questions:
                if item.get('has_sub_questions') == False:
                    single_questions.append(item)
                else:
                    sub_questions.append(item)
            
            logging.info(f"✅ Single Questions (no sub-parts): {len(single_questions)}")
            logging.info(f"✅ Questions with Sub-parts: {len(sub_questions)}")

            tasks = []
            if single_questions:
                     tasks.append(
                    self.process_questions_in_batches(questions_list=single_questions,question_type='single',json_data=json_data,batch_size=15))
            else:
                async def empty_task():
                    return [], {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
                tasks.append(empty_task())
            
            if sub_questions:
                tasks.append(
                    self.process_questions_in_batches(questions_list=sub_questions,question_type='sub',json_data=json_data,batch_size=15))
            else:
                async def empty_task():
                    return [], {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
                tasks.append(empty_task())
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            enriched_single = []
            enriched_sub = []
            single_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
            sub_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
            
            if isinstance(results[0], Exception):
                logging.error(f"Error processing single questions: {results[0]}")
            elif isinstance(results[0], tuple) and len(results[0]) == 2:
                enriched_single, single_tokens = results[0]
            elif isinstance(results[0], list):
                enriched_single = results[0]
            
            if isinstance(results[1], Exception):
                     logging.error(f"Error processing sub-questions: {results[1]}")
            elif isinstance(results[1], tuple) and len(results[1]) == 2:
                enriched_sub, sub_tokens = results[1]
            elif isinstance(results[1], list):
                enriched_sub = results[1]
            
            qllm_helper_function._merge_tokens(enrichment_tokens, single_tokens)
            qllm_helper_function._merge_tokens(enrichment_tokens, sub_tokens)
            
            all_enriched = enriched_single + enriched_sub
            final_questions = ocr_prepare_instance.merge_enriched_data(original_questions=q_json.get("questions", []),enriched_questions=all_enriched,json_data=json_data)
            final_questions = sorted(final_questions,key=lambda x: qllm_helper_function.to_int(x.get("question_number")) or float('inf'))
            logging.info(f"✅ Total Final Questions: {len(final_questions)}")
            valid_questions, failed_question_numbers, validation_report = ocr_prepare_instance.validate_all_questions(final_questions)
            
            if failed_question_numbers:
                logging.warning(f"⚠️ {len(failed_question_numbers)} questions failed validation. Attempting retry...")
                failed_originals = [q for q in q_json.get("questions", []) 
                                  if str(q.get('question_number')) in failed_question_numbers]
                
                failed_single = [q for q in failed_originals if not q.get('has_sub_questions')]
                failed_sub = [q for q in failed_originals if q.get('has_sub_questions')]
                
                logging.info(f"🔄 RETRY VALIDATION FAILED QUESTIONS")
                logging.info(f"   ├─ Failed Single Questions: {len(failed_single)}")
                logging.info(f"   └─ Failed Sub-Questions: {len(failed_sub)}")
                
                retry_enriched_single = []
                retry_enriched_sub = []
                
                if failed_single:
                    logging.info(f"🔄 Retrying {len(failed_single)} failed single questions...")
                    retry_enriched_single, retry_single_tokens = await self.process_questions_in_batches(questions_list=failed_single,question_type='single',json_data=json_data,batch_size=15,max_retries=2)
                    qllm_helper_function._merge_tokens(enrichment_tokens, retry_single_tokens)
                
                if failed_sub:
                    logging.info(f"🔄 Retrying {len(failed_sub)} failed sub-questions...")
                    retry_enriched_sub, retry_sub_tokens = await self.process_questions_in_batches(questions_list=failed_sub,question_type='sub',json_data=json_data,batch_size=15,max_retries=2)
                    qllm_helper_function._merge_tokens(enrichment_tokens, retry_sub_tokens)
                
                all_retry_enriched = retry_enriched_single + retry_enriched_sub
                if all_retry_enriched:
                    final_questions = ocr_prepare_instance.merge_enriched_data(original_questions=q_json.get("questions", []),enriched_questions=all_enriched + all_retry_enriched,json_data=json_data)
                    valid_questions, failed_question_numbers, validation_report = ocr_prepare_instance.validate_all_questions(final_questions)
                    
                    if failed_question_numbers:
                        logging.error(f"❌ {len(failed_question_numbers)} questions still failed after retry: {failed_question_numbers}")
                    else:
                        logging.info(f"✅ All questions passed validation after retry!")
            
            all_question_numbers = set(str(q.get('question_number')) for q in valid_questions)
            expected_numbers = set(str(i) for i in range(1, qcount + 1))
            miss_ques_set = expected_numbers - all_question_numbers
            
            validation_failed_nums = set(failed_question_numbers)
            miss_ques_set = miss_ques_set.union(validation_failed_nums)
            miss_ques = sorted([int(q) for q in miss_ques_set]) if miss_ques_set else []

            final_questions_for_db = db.add_image_details(valid_questions)
            
            combined_total = extraction_tokens['total_tokens'] + enrichment_tokens['total_tokens']
            logging.info(f"📋 Flattening validated questions for database...")
            flattened_questions = ocr_prepare_instance.flatten_questions_for_db(final_questions_for_db)
            logging.info(f"   ├─ Valid questions: {len(final_questions_for_db)}")
            logging.info(f"   ├─ Failed questions (not saved): {len(failed_question_numbers)}")
            logging.info(f"   └─ Database entries: {len(flattened_questions)} (sub-parts expanded)")
            
            if failed_question_numbers:
                logging.warning(f"⚠️ WARNING: {len(failed_question_numbers)} questions will NOT be saved due to validation failure")
                logging.warning(f"   Failed questions: {failed_question_numbers}\n")
            
            ques_id = await db.add_question_paper_data(request, json_data, image_list, gen_response, md_results, miss_ques)
            
            if flattened_questions:
                await db.add_ques_answer_data(request, flattened_questions, ques_id)
                logging.info(f"   ├─ {len(flattened_questions)} valid question entries saved")
            else:
                logging.warning(f"   ├─ ⚠️ No valid questions to save!")
            
            await db.token_update_fc(request, extraction_tokens, "gemini-2.5-pro", bot_name="OCR_Question_Paper_Extraction_Agent")           
            await db.token_update_fc(request, enrichment_tokens, "gemini-2.0-flash", bot_name="OCR_Question_Paper_Enrichment_Agent")
            
            logging.info(f"   └─ ✅ All data saved successfully!\n")
            
            combined_tokens = {
                "extraction_tokens": extraction_tokens,
                "enrichment_tokens": enrichment_tokens,
                "total_tokens": combined_total,
                "validation_report": validation_report,
                "failed_questions": failed_question_numbers,
                "models": {
                    "extraction": "gemini-2.5-pro",
                    "enrichment": "gemini-2.0-flash"
                }
            }

            return valid_questions, combined_tokens

        except (requests.exceptions.RequestException, boto3.exceptions.Boto3Error) as e:
            logging.error(f"A network or cloud service error occurred: {e}")
            raise RuntimeError(f"Failed to process document due to a service error: {e}") from e
        except Exception as e:
            logging.error(f"An unexpected error occurred in question_scheme: {e}")
            logging.error(traceback.format_exc())
            raise

ocr_instance = doc_ocr()     
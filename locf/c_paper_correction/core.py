import os, logging, json, asyncio, psutil
from typing import Optional, List, Union, Any, Dict
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from locf.c_paper_correction import classes, helper_function, prompts, db, parser_helper, student_details
from locf.qbanks.core import question_banks

load_dotenv()
logging.basicConfig(level=logging.INFO)
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

SYSTEM_PROMPT_TEMPLATE = prompts.answer_paper_correction_prompt_v8
NO_URLS_SYSTEM_RULE = prompts.no_urls_system_rule

class PaperCorrection:
    def __init__(self):
        self.s3_prefix="ocr/answer_images"
        self.thinking_tokens = 250
        self.model_flash2   = "gemini-2.0-flash"
        self.model_flash25  = "gemini-2.5-flash"
        self.model_pro_25   = "gemini-2.5-pro-preview-05-06"
        self.model_o4_mini  = "o4-mini"

        self.llm_flash2  = ChatGoogleGenerativeAI(model=self.model_flash2)
        self.llm_flash25 = ChatGoogleGenerativeAI(model=self.model_flash25)
        try:
            self.llm_flasht25 = ChatGoogleGenerativeAI(model=self.model_flash25, thinking_budget=self.thinking_tokens)
        except TypeError:
            self.llm_flasht25 = self.llm_flash25
        self.llm_pro_25 = ChatGoogleGenerativeAI(model=self.model_pro_25)
        try:
            self.llm_o4_mini = ChatOpenAI(model=self.model_o4_mini)
        except Exception:
            self.llm_o4_mini = None

    def get_llm_by_model(self, model_id: int):
        return {
            1: self.llm_flash2,
            2: self.llm_flash25,
            3: self.llm_flasht25,
            4: self.llm_pro_25,
            5: self.llm_o4_mini or self.llm_flash25,
        }.get(model_id, self.llm_flash25)
        
    async def grade_as_agent(self, request: classes.AnswerSheetRequest, question_json, standard: str, subject: str, messages_content: Any, instruction_json: str, target_list: Optional[List[Union[int, str]]] = [], question_type: str = "single"):
        try:
            llm = self.get_llm_by_model(request.model)
            question_selected, missing = helper_function.cls_helper_function.pick_questions(question_json, target_list)
            
            # Debug: Log what questions are being sent to LLM
            logging.info(f"🎯 Sending {len(question_selected)} questions to LLM for {question_type} type")
            for q in question_selected:
                q_num = q.get('question_number', 'unknown')
                q_text_preview = q.get('question_text', '')[:50] + "..." if q.get('question_text') else 'no text'
                logging.info(f"   📝 Q{q_num}: {q_text_preview}")
            
            instr, narrow_total = helper_function.cls_helper_function._apply_narrow_mode(instruction_json, target_list)
            inst_json = json.dumps(instr, ensure_ascii=False)
            
            # Select appropriate prompt based on question type
            if question_type == "sub":
                SYSTEM_PROMPT = prompts.sub_question_grading_prompt
                logging.info(f"   Using SUB-QUESTION prompt for {len(question_selected)} sub-parts")
            elif question_type == "or":
                SYSTEM_PROMPT = prompts.or_question_grading_prompt
                logging.info(f"   Using OR-QUESTION prompt for {len(question_selected)} OR questions")
            else:
                SYSTEM_PROMPT = prompts.single_question_grading_prompt
                logging.info(f"   Using SINGLE-QUESTION prompt for {len(question_selected)} questions")
            
            prompt_template = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("system", NO_URLS_SYSTEM_RULE), MessagesPlaceholder(variable_name="human_messages")])

            chain = prompt_template | llm
            #logging.info("grader agent start working...")
            
            result = await chain.ainvoke({"standard": standard,"subject": subject,"cdl_level": request.cdl_level, "question_paper_json": question_selected,"instruction_set": inst_json,"max_marks": narrow_total,"human_messages": messages_content, "target_qs": target_list})

            text = getattr(result, "content", str(result))
            
            # Debug: Log the raw LLM response
            logging.info(f"🔍 Raw LLM response length: {len(text)} chars")
            logging.info(f"🔍 Raw LLM response preview: {text[:200]}...")
            
            parser = JsonOutputParser()
            try:
                json_parser= parser.parse(text)
                logging.info(f"✅ JSON parsing successful, got {len(json_parser) if isinstance(json_parser, list) else 'non-list'} items")
            except Exception as e:
                logging.warning(f"⚠️ JSON parsing failed: {e}")
                logging.warning(f"🔍 Problematic text: {text[:500]}...")
                gen_text = question_banks._ensure_text(result)
                json_parser = parser_helper.json_helpers.parse_json(gen_text)
                logging.info(f"✅ Fallback JSON parsing successful, got {len(json_parser) if isinstance(json_parser, list) else 'non-list'} items")
                
            gen_usage = helper_function.processing_answer_sheet._extract_tokens(result)

            tokens = {
                "total_input_tokens":  gen_usage["total_input_tokens"],
                "total_output_tokens": gen_usage["total_output_tokens"],
                "total_tokens":        gen_usage["total_tokens"],
            }
            # print(f"Tokens Usage {tokens}")

            return json_parser, tokens
        except Exception as e:
            logging.error(f"Error in grade_as_agent: {e}")
            return None, None
    
    def _merge_tokens(self, tot: Dict[str, int], add: Dict[str, int]) -> None:
        if not add:
            return
        tot["total_input_tokens"] = tot.get("total_input_tokens", 0) + add.get("total_input_tokens", 0)
        tot["total_output_tokens"] = tot.get("total_output_tokens", 0) + add.get("total_output_tokens", 0)
        tot["total_tokens"] = tot.get("total_tokens", 0) + add.get("total_tokens", 0)
    
    async def generation_logic(self, request: classes.AnswerSheetRequest, standard, subject, messages_content, instr, qcount, question_json, target_list):
        try:
            # Ensure qcount is an integer
            qcount = int(str(qcount).strip()) if qcount is not None else 0
            
            # Split questions into single, sub-questions, and OR questions
            single_questions = []
            sub_questions = []
            or_questions = []
            
            for q in question_json:
                has_sub = q.get("has_sub_questions")
                part_label = q.get("part_label")
                is_or_question = q.get("is_or_question")
                alternative_ques = q.get("alternative_ques")
                
                # If is_or_question is "True" OR alternative_ques is "True", it's an OR question
                if (is_or_question == "True" or alternative_ques == "True"):
                    or_questions.append(q)
                # If has_sub_questions is "True" AND has part_label, it's a sub-question
                elif has_sub == "True" and part_label:
                    sub_questions.append(q)
                else:
                    single_questions.append(q)
            
            logging.info(f"Split questions: {len(single_questions)} single, {len(sub_questions)} sub-parts, {len(or_questions)} OR questions")
            
            gen_question_list = []
            final_response = []
            total_attempts = 0
            max_attempts = 5
            llm_batch_size = 20
            
            total_tokens: Dict[str, int] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            }


            while (
                total_attempts < max_attempts and
                [i for i in target_list if i not in gen_question_list]
            ):
                total_attempts += 1

                re_target_list = [i for i in target_list if i not in gen_question_list]

                if not re_target_list:
                    break
                
                logging.info(f"Attempt {total_attempts}/{max_attempts}: Targeting questions {re_target_list}")
                
                # Create separate tasks for single and sub-questions IN PARALLEL
                tasks = []
                question_chunks = [
                    re_target_list[i : i + llm_batch_size]
                    for i in range(0, len(re_target_list), llm_batch_size)
                ]
                
                for chunk in question_chunks:
                    # Filter chunk to only include questions that exist in each category
                    single_q_nums = [q.get("question_number") for q in single_questions]
                    sub_q_nums = [q.get("question_number") for q in sub_questions]
                    or_q_nums = [q.get("question_number") for q in or_questions]
                    
                    single_chunk = [q_num for q_num in chunk if q_num in single_q_nums]
                    sub_chunk = [q_num for q_num in chunk if q_num in sub_q_nums]
                    or_chunk = [q_num for q_num in chunk if q_num in or_q_nums]
                    
                    # Process single questions (if any in this chunk)
                    if single_chunk and single_questions:
                        logging.info(f"→ Single questions task: {single_chunk}")
                        tasks.append(self.grade_as_agent(request, single_questions, standard, subject, messages_content, instr, single_chunk, question_type="single"))
                    
                    # Process sub-questions (if any in this chunk)
                    if sub_chunk and sub_questions:
                        logging.info(f"→ Sub-questions task: {sub_chunk}")
                        tasks.append(self.grade_as_agent(request, sub_questions, standard, subject, messages_content, instr, sub_chunk, question_type="sub"))
                    
                    # Process OR questions (if any in this chunk)
                    if or_chunk and or_questions:
                        logging.info(f"→ OR questions task: {or_chunk}")
                        tasks.append(self.grade_as_agent(request, or_questions, standard, subject, messages_content, instr, or_chunk, question_type="or"))

                logging.info(f"Sending {len(tasks)} parallel requests to the LLM.")
                logging.info("grader agent start working...")
                
                # Log memory usage before LLM calls
                memory_info = psutil.virtual_memory()
                logging.info(f"Memory usage before LLM calls: {memory_info.percent}% ({memory_info.used / 1024 / 1024:.1f}MB used)")
                
                try:
                    # Add memory management and timeout
                    responses_from_gather = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=300  # 5 minute timeout
                    )
                    
                    # Log memory usage after LLM calls
                    memory_info = psutil.virtual_memory()
                    logging.info(f"Memory usage after LLM calls: {memory_info.percent}% ({memory_info.used / 1024 / 1024:.1f}MB used)")
                    
                except asyncio.TimeoutError:
                    logging.error("LLM requests timed out after 5 minutes")
                    # Cancel all tasks and return empty results
                    for task in tasks:
                        if hasattr(task, 'cancel') and not task.done():
                            task.cancel()
                    responses_from_gather = []
                except asyncio.CancelledError:
                    logging.warning("Shutdown signal received. Cancelling tasks gracefully...")
                    # Cancel all pending tasks
                    for task in tasks:
                        if hasattr(task, 'cancel') and not task.done():
                            task.cancel()
                    # Return partial results instead of raising
                    expected = set(range(1, qcount + 1))
                    got = {helper_function.cls_helper_function.to_int(r.get("question_number") or r.get("question_no")) for r in final_response}
                    missing = sorted(expected - got)
                    return final_response, total_tokens, missing
                                
                for idx, response in enumerate(responses_from_gather):
                    if isinstance(response, asyncio.CancelledError):
                        logging.warning(f"Asyncio Task {idx+1} was cancelled (likely due to shutdown).")
                    elif isinstance(response, Exception):
                        logging.error(f"Asyncio Task {idx+1} failed with error: {repr(response)}")
                    else:
                        logging.info(f"Asyncio Task {idx+1} completed successfully.")

                all_responses_json = []
                for idx, res in enumerate(responses_from_gather):
                    if isinstance(res, Exception):
                        logging.error(f"An LLM call failed: {res}")
                        continue
                    
                    # Unpack the tuple
                    parsed_json, tokens = res
                    
                    # Debug: Log what we got from each LLM call
                    logging.info(f"📊 LLM Call {idx+1} returned: {len(parsed_json) if isinstance(parsed_json, list) else 'non-list'} items")
                    if isinstance(parsed_json, list) and len(parsed_json) > 0:
                        for item in parsed_json:
                            q_num = item.get('question_number', 'unknown')
                            logging.info(f"   📝 Got result for Q{q_num}")
                    
                    if parsed_json:
                        all_responses_json.extend(parsed_json)
                    
                    # Use your helper to aggregate tokens
                    if tokens:
                        self._merge_tokens(total_tokens, tokens)
                        
                resp = helper_function.cls_helper_function.strip_urls_from_output(all_responses_json)
                
                valid_ans = [
                    row for row in resp
                    if (helper_function.cls_helper_function.to_int(row.get("question_number")) in re_target_list)
                ]
                
                valid_ans = helper_function.processing_answer_sheet.keys_check(valid_ans)
                
                # ✅ NEW: Map ques_id from question_json to graded results
                from locf.c_paper_correction.helper_function import QuestionMapper
                valid_ans = QuestionMapper.map_ques_id_to_results(valid_ans, question_json)
                logging.info(f"✅ Mapped ques_id to {len(valid_ans)} graded results")
                
                final_response.extend(valid_ans)

                newly_generated_q_numbers = {
                    helper_function.cls_helper_function.to_int(item.get("question_number"))
                    for item in valid_ans
                    if helper_function.cls_helper_function.to_int(item.get("question_number")) is not None
                }
                gen_question_list.extend(list(newly_generated_q_numbers))
                gen_question_list = sorted(list(set(gen_question_list)))

                logging.info(f"Attempt {total_attempts}: Graded questions so far: {gen_question_list}")

            seen = set()
            deduped = []
            for row in final_response:
                qno = helper_function.cls_helper_function.to_int(row.get("question_number") or row.get("question_no"))
                part_label = row.get("part_label")
                q_identifier = (qno, part_label) if part_label else (qno, None)
                
                if qno is None:
                    continue
                if q_identifier not in seen:
                    deduped.append(row)
                    seen.add(q_identifier)
            final_response = deduped

            # ✅ NEW: Add validation
            logging.info("Validating grading results...")
            from locf.c_paper_correction.helper_function import GradingValidator
            
            valid_results, failed_results, validation_report = GradingValidator.validate_all_results(final_response)
            
            logging.info(f"✅ Validation complete: {validation_report['valid_count']}/{validation_report['total_questions']} passed")
            
            if failed_results:
                logging.warning(f"⚠️ {len(failed_results)} questions failed validation: {validation_report['failed_question_numbers']}")
                
                # Retry failed questions (up to 2 additional attempts)
                retry_count = 0
                max_validation_retries = 2
                
                while failed_results and retry_count < max_validation_retries:
                    retry_count += 1
                    logging.info(f"🔄 Validation retry {retry_count}/{max_validation_retries} for {len(failed_results)} questions")
                    
                    # Extract question numbers that failed
                    failed_q_numbers = [r.get("question_number") for r in failed_results]
                    
                    # Separate failed into single, sub, and OR questions
                    failed_single_nums = [int(r.get("question_number")) for r in failed_results if r.get("has_sub_questions") != "True" and r.get("is_or_question") != "True" and r.get("alternative_ques") != "True"]
                    failed_sub_nums = [int(r.get("question_number")) for r in failed_results if r.get("has_sub_questions") == "True"]
                    failed_or_nums = [int(r.get("question_number")) for r in failed_results if r.get("is_or_question") == "True" or r.get("alternative_ques") == "True"]
                    
                    # Re-grade only the failed questions (single, sub, and OR separately)
                    retry_tasks = []
                    if failed_single_nums and single_questions:
                        retry_tasks.append(self.grade_as_agent(
                            request, single_questions, standard, subject, messages_content, instr, failed_single_nums, question_type="single"
                        ))
                    if failed_sub_nums and sub_questions:
                        retry_tasks.append(self.grade_as_agent(
                            request, sub_questions, standard, subject, messages_content, instr, failed_sub_nums, question_type="sub"
                        ))
                    if failed_or_nums and or_questions:
                        retry_tasks.append(self.grade_as_agent(
                            request, or_questions, standard, subject, messages_content, instr, failed_or_nums, question_type="or"
                        ))
                    
                    if not retry_tasks:
                        break
                    
                    retry_responses = await asyncio.gather(*retry_tasks, return_exceptions=True)
                    
                    retry_response = []
                    retry_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}
                    
                    for resp in retry_responses:
                        if isinstance(resp, Exception):
                            continue
                        parsed, tokens = resp
                        if parsed:
                            retry_response.extend(parsed)
                        if tokens:
                            self._merge_tokens(retry_tokens, tokens)
                    
                    if retry_response:
                        self._merge_tokens(total_tokens, retry_tokens)
                        
                        # ✅ Map ques_id to retry results
                        from locf.c_paper_correction.helper_function import QuestionMapper
                        retry_response = QuestionMapper.map_ques_id_to_results(retry_response, question_json)
                        
                        # Validate retry results
                        retry_valid, retry_failed, retry_report = GradingValidator.validate_all_results(retry_response)
                        
                        # Remove old failed entries from valid_results
                        valid_q_identifiers = {(r.get("question_number"), r.get("part_label")) for r in valid_results}
                        failed_q_identifiers = {(r.get("question_number"), r.get("part_label")) for r in failed_results}
                        valid_results = [r for r in valid_results if (r.get("question_number"), r.get("part_label")) not in failed_q_identifiers]
                        
                        # Add newly valid results
                        valid_results.extend(retry_valid)
                        failed_results = retry_failed
                        
                        logging.info(f"✅ Retry {retry_count}: {len(retry_valid)} now valid, {len(retry_failed)} still failing")
                    else:
                        break
                
                # After retries, use valid results only
                final_response = valid_results
                
                # Track failed questions as missing
                final_failed_q_nums = [r.get("question_number") for r in failed_results]
                if final_failed_q_nums:
                    logging.error(f"❌ Final validation failures: {final_failed_q_nums}")

            expected = set(range(1, qcount + 1))
            got = {helper_function.cls_helper_function.to_int(r.get("question_number") or r.get("question_no")) for r in final_response}
            missing = sorted(expected - got)
            if missing:
                logging.warning(f"Incomplete grading. Missing questions: {missing}")
            else:
                missing =[]
            return final_response, total_tokens, missing
        except Exception as e:
            logging.error(f"Error in generation_logic: {e}")
            return None, {}, {}
        
    async def assigner_function(self, request: classes.AnswerSheetRequest):
        """Assigns the grading task to the appropriate model based on the request."""
        total_tokens: Dict[str, int] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            }
        try:   
            logging.info(f"Received request to process answer sheet.....")         
            instr, md_list, questions_count, subject, standard = await helper_function.cls_helper_function.prepare_question_content(request)
            
            question_result = await db.fetch_question_json(request.question_id)
            logging.info(f"question data fetched from db.....")
            
            # Keep question_result as-is (includes ques_id for mapping later)
            question_json = question_result
            
            try:
                qn_strs = [r.get('question_number') for r in question_result if 'question_number' in r]
                qn_ints = [int(q) for q in qn_strs if q is not None]
            except (TypeError, ValueError):
                qcount = int(str(questions_count).strip())
                qn_ints = [i for i in range(1, qcount + 1)]
            
            if len(qn_ints) <= 0:
                raise ValueError(f"Invalid questions_count: {questions_count!r}")

            #all_text_content = helper_function.cls_helper_function.answer_sheet_content(pdf_link=request.pdf_url)
            stu_det, all_text_content, list_of_pages, tokens_taken = helper_function.cls_helper_function.answer_extraction_logic(request.pdf_url)
            if list_of_pages is None or len(list_of_pages) == 0:
                list_of_pages = qn_ints[:5]
            if stu_det is None or all_text_content is None:
                all_text_content, tokens_taken = helper_function.cls_helper_function.answer_sheet_extraction(request.pdf_url, system_prompt=prompts.extraction_prompt)
                stu_det, tokens = student_details.extract_student_info(request.pdf_url)
                list_of_pages = qn_ints[:15]
                if tokens:
                    self._merge_tokens(total_tokens, tokens)
            
            logging.info(f"Answer sheet text extracted.....")
            uploaded_image_urls = helper_function.cls_helper_function.split_pdf_and_upload_to_s3(pdf_url=request.pdf_url,s3_prefix=self.s3_prefix, pages_list=list_of_pages)
            messages_content = helper_function.cls_helper_function.build_user_message_dict(all_text_content, uploaded_image_urls)
            final_response, total_tokens, missing = await self.generation_logic(request, standard, subject, messages_content, instr, questions_count, question_json, qn_ints)
            logging.info(f"Grading completed.....")
            if final_response is None:
                logging.error("Final response is None")
                return None, total_tokens
            merge_response = helper_function.processing_answer_sheet.merge_answer_with_question(final_response, question_result)
            
            max_marks = int(instr.get("exam_metadata", {}).get("max_marks", 0))
            if max_marks <= 0:
                max_marks = 0
            ana_result = helper_function.processing_answer_sheet.result_analysis(merge_response, max_marks)

            result = {"final_response": final_response,
            "merge_response": merge_response,
            "ana_result": ana_result,
            "total_tokens": total_tokens,
            "missing": missing,
            }
            max_marks = int(instr.get("exam_metadata", {}).get("max_marks", 0))
            if max_marks <= 0:
                max_marks = ana_result.get("total_maximum_marks", 0.0)
            student_id =await db.update_student_details(stu_det)    
            exam_id = await db.update_exam_details(request, student_id, stu_det, missing, subject, ana_result, max_marks)
            await db.save_answer_sheet_correction(request, merge_response, student_id, exam_id)
            await db.token_update_fc(request, total_tokens, "gemini-2.0-flash")
            await db.token_update_fc(request, tokens_taken, "gemini-2.5-pro")

            return result, total_tokens
        except asyncio.CancelledError:
            logging.warning("Assigner function cancelled during shutdown")
            return None, total_tokens
        except Exception as e:
            print(f"Error in assigner_function: {e}")
            return None, total_tokens

        
answer_pc_instance = PaperCorrection()
import os, logging, json, asyncio
from typing import Optional, List, Union, Any, Dict
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from locf.s_paper_correction import classes, helper_function, prompts, db, parser_helper, student_details
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
        
    async def grade_as_agent(self, request: classes.AnswerSheetRequest, question_json, standard: str, subject: str, messages_content: Any, instruction_json: str, target_list: Optional[List[Union[int, str]]] = []):
        try:
            llm = self.get_llm_by_model(request.model)
            question_selected, missing = helper_function.cls_helper_function.pick_questions(question_json, target_list)
            instr, narrow_total = helper_function.cls_helper_function._apply_narrow_mode(instruction_json, target_list)
            inst_json = json.dumps(instr, ensure_ascii=False)
            prompt_template = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT_TEMPLATE), ("system", NO_URLS_SYSTEM_RULE), MessagesPlaceholder(variable_name="human_messages")])

            chain = prompt_template | llm
            #logging.info("grader agent start working...")
            
            result = await chain.ainvoke({"standard": standard,"subject": subject,"cdl_level": request.cdl_level, "question_paper_json": question_selected,"instruction_set": inst_json,"max_marks": narrow_total,"human_messages": messages_content, "target_qs": target_list})

            text = getattr(result, "content", str(result))
            parser = JsonOutputParser()
            try:
                json_parser= parser.parse(text)
            except Exception:
                gen_text = question_banks._ensure_text(result)
                json_parser = parser_helper.json_helpers.parse_json(gen_text)
                
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
                
                tasks = []
                question_chunks = [
                    re_target_list[i : i + llm_batch_size]
                    for i in range(0, len(re_target_list), llm_batch_size)
                ]
                
                for chunk in question_chunks:
                    tasks.append(self.grade_as_agent(request, question_json, standard, subject, messages_content, instr, chunk))

                logging.info(f"Sending {len(tasks)} parallel requests to the LLM.")
                logging.info("grader agent start working...")                
                try:
                    responses_from_gather = await asyncio.gather(*tasks, return_exceptions=True)
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
                for res in responses_from_gather:
                    if isinstance(res, Exception):
                        logging.error(f"An LLM call failed: {res}")
                        continue
                    
                    # Unpack the tuple
                    parsed_json, tokens = res
                    
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
                if qno is None:
                    continue
                if qno not in seen:
                    deduped.append(row)
                    seen.add(qno)
            final_response = deduped

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
            question_json = [
                {k: v for k, v in item.items() if k != 'ques_id'}
                for item in question_result
            ]
            
            try:
                qn_strs = [r.get('question_number') for r in question_result if 'question_number' in r]
                qn_ints = [int(q) for q in qn_strs if q is not None]
            except (TypeError, ValueError):
                qcount = int(str(questions_count).strip())
                qn_ints = [i for i in range(1, qcount + 1)]
            
            if len(qn_ints) <= 0:
                raise ValueError(f"Invalid questions_count: {questions_count!r}")

            all_text_content = helper_function.cls_helper_function.answer_sheet_content(pdf_link=request.pdf_url)
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
            ana_result = helper_function.processing_answer_sheet.result_analysis(final_response)
            
            student_id =await db.update_student_details(stu_det)    
            exam_id = await db.update_exam_details(request, student_id, stu_det, missing, subject, ana_result)
            await db.save_answer_sheet_correction(request, merge_response, student_id, exam_id)
            await db.token_update_fc(request, total_tokens, "gemini-2.0-flash")
            await db.token_update_fc(request, tokens_taken, "gemini-2.5-pro")

            return messages_content, total_tokens

        except asyncio.CancelledError:
            logging.warning("Assigner function cancelled during shutdown")
            return None, total_tokens
        except Exception as e:
            print(f"Error in assigner_function: {e}")
            return None, total_tokens

        
answer_pc_instance = PaperCorrection()
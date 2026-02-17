from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import asyncio,os, time,re,constants,json,ast
from dotenv import load_dotenv
from cs_qbanks import cs_prompts
from cs_qbanks import cs_db_connect, cs_classes, helper_functions
from langchain_core.output_parsers import JsonOutputParser
from collections import defaultdict

load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

class question_bank:
    def __init__(self):
        self.max_questions_per_call =40
        self.thinking_tokens=250
        self.model_flash2= "gemini-2.0-flash-001"
        self.model_flash25= "gemini-2.5-flash-preview-09-2025"
        self.model_pro_25= "gemini-2.5-pro"
        self.model_o4_mini = "o4-mini"
        self.llm_o4_mini = ChatOpenAI(model=self.model_o4_mini)
        self.llm_flash2=ChatGoogleGenerativeAI(model=self.model_flash2)  
        self.llm_flash25=ChatGoogleGenerativeAI(model=self.model_flash25, thinking_budget=0) 
        self.llm_flasht25=ChatGoogleGenerativeAI(model=self.model_flash25, thinking_budget=self.thinking_tokens)
        self.llm_pro_25=ChatGoogleGenerativeAI(model=self.model_pro_25, thinking_budget=self.thinking_tokens)
        self.qc_llm = ChatGoogleGenerativeAI(model=self.model_flash2, temperature=0.3)
        self.parser= JsonOutputParser(pydantic_object=cs_classes.MCQ)
    
    def get_llm_by_model(self, model_id: int):
        if model_id == 1:
            return self.llm_flash2
        elif model_id == 2:
            return self.llm_flash25
        elif model_id == 3:
            return self.llm_flasht25
        elif model_id == 4:
            return self.llm_pro_25
        elif model_id == 5:
            return self.llm_o4_mini
        else:
            print(f"Unknown model_id {model_id}, defaulting to {self.model_flash2}")
            return self.llm_flash2
        
    async def question_bank_generator(self, request: cs_classes.QuestionRequest, No: int):
        try:
            all_data = []
            print(f"topic: {request.topic_name},NO of question hit received: {No},")
            start_time = time.time()
            cog_level_str = str(request.cognitive_level).strip().lower()
            question_type = cs_classes.cognitive_level_to_question_types[cog_level_str]
            self.llm = self.get_llm_by_model(request.model)
            generation_response = await self.llm.ainvoke(cs_prompts.normal_generation_template_v2.format(topic=request.topic_name,difficulty=request.difficulty,No=No,cognitive_level=request.cognitive_level,already_gen_mcqs=request.already_gen_mcqs, question_type=question_type))    
            print(f"Time taken for generation: {time.time() - start_time}")
            start_time2 = time.time()
            #print(generation_response.usage_metadata)
            if isinstance(generation_response.content, list):
                print(f"it is in list with len {len(generation_response.content)}")
                generation_text = generation_response.content[-1]
            else:
                generation_text = generation_response.content
            cleaned_data = helper_functions.json_helpers.parse_json(generation_text)           
            QC_response = await self.qc_llm.ainvoke(cs_prompts.normal_qc_template.format(mcqs=cleaned_data, topic=request.topic_name))
            #print(f"Time taken for QC: {time.time() - start_time2}")
            qc_output = self.parser.invoke(QC_response.content)
            output = helper_functions.helpers.merge_data(cleaned_data, qc_output)
            cln_output = helper_functions.helpers.check_options(output)
            tokens = helper_functions.helpers.calculate_total_tokens(generation_response.usage_metadata, QC_response.usage_metadata)
            passed_qc = [item for item in cln_output if item['QC'] == 'pass']
            failed_items = [item for item in cln_output if item['QC'] == 'fail']
            passed_items = await helper_functions.helpers.key_function(request, passed_qc)
            asyncio.create_task(helper_functions.helpers.cal_percentage(request.uuid, len(passed_items), request.number_of_questions))

            if failed_items:
                asyncio.create_task(cs_db_connect.add_mcq_data(request, failed_items,cs_classes.cs_MCQData))
            print(f"No of Total items queried: {No}, No of passed items: {len(passed_items)}, No of failed items: {len(failed_items)}")
            all_data.extend(passed_items)
            returned = len(passed_items)

            while returned < No:
                remaining = No - returned
                new_items, new_tokens, new_count = await self.fetch_remaining_questions(request, remaining, all_data, tokens, returned, No)
                all_data.extend(new_items)
                returned += new_count
            return all_data, tokens, len(all_data)

        except Exception as e:
            print(f"Error occurred in question_bank_generator: {e}")
            return [], {}, 0
        
    
    
    async def fetch_remaining_questions(self, request: cs_classes.QuestionRequest, remaining, all_data, total_tokens, total_questions, target_total):
        try:
            if request.already_gen_mcqs is None:
                questions_only = [item['question'] for item in all_data if 'question' in item]
            else:
                questions_only = []
                gen_questions = [item['question'] for item in all_data if 'question' in item]
                questions_only.extend(request.already_gen_mcqs)
                questions_only.extend(gen_questions)

            new_request = cs_classes.QuestionRequest(user_id=request.user_id,
                                          uuid=request.uuid,
                                          subject_name=request.subject_name,
                                          chapter_name=request.chapter_name,
                                          topic_name=request.topic_name,
                                          difficulty=request.difficulty,
                                          number_of_questions=request.number_of_questions,
                                          cognitive_level=request.cognitive_level,
                                          already_gen_mcqs=questions_only,
                                          model=request.model,
                                          stream=request.stream)
            additional_result = await self.question_bank_generator(new_request, remaining)

            if isinstance(additional_result, tuple) and len(additional_result) == 3:
                additional_data, additional_tokens, additional_count = additional_result
                questions_to_add = min(additional_count, target_total - total_questions)
                limited_data = additional_data[:questions_to_add]

                if isinstance(additional_tokens, dict):
                    total_tokens['total_input_tokens'] += additional_tokens.get("total_input_tokens", 0)
                    total_tokens['total_output_tokens'] += additional_tokens.get("total_output_tokens", 0)
                    total_tokens['total_tokens'] += additional_tokens.get("total_tokens", 0)

                return limited_data, additional_tokens, questions_to_add
            else:
                print("Invalid result format from question_bank_generator.")
                return [], {}, 0

        except Exception as e:
            print(f"Error while fetching remaining questions: {e}")
            return [], {}, 0

    async def cs_question_bank_generator(self, table_name, request: cs_classes.QuestionRequest, chunk_size: int = 2):
        """Generate MCQs with minimal token cost and avoid duplication by fixing task execution order and top-up logic."""
        try:
            asyncio.create_task(cs_db_connect.add_progress(request.uuid))
            total_need = int(request.number_of_questions)
            topics = list(request.topic_name)
            n_topics = len(topics)

            if total_need <= 0 or n_topics == 0:
                return [], {}, 0, []
            
            if len(request.topic_name) == 1 and request.number_of_questions > self.max_questions_per_call:
                return await self.split_and_generate_questions(request, request.number_of_questions)

            # ---- 1. Distribute questions across topics ----
            per_topic = [total_need // n_topics] * n_topics
            for i in range(total_need % n_topics):
                per_topic[i] += 1

            batches, current, current_q = [], [], 0
            for idx, topic in enumerate(topics):
                q_needed = per_topic[idx]
                if current_q + q_needed > self.max_questions_per_call and current:
                    batches.append(current)
                    current, current_q = [], 0
                current.append((idx, topic))
                current_q += q_needed
            if current:
                batches.append(current)

            # ---- 2. Prepare base request ----
            base = request.model_dump()
            base.pop("topic_name", None)
            base.pop("number_of_questions", None)

            tasks = []
            for batch in batches:
                idxs, batch_topics = zip(*batch)
                q_in_batch = sum(per_topic[i] for i in idxs)
                topic_req = cs_classes.QuestionRequest(
                    **base, topic_name=list(batch_topics), number_of_questions=request.number_of_questions)
                tasks.append((topic_req, lambda rq=topic_req, cnt=q_in_batch: self.question_bank_generator(rq, cnt)))

            # ---- 3. Run initial tasks ----
            results = await asyncio.gather(*[t[1]() for t in tasks], return_exceptions=True)

            all_data = []
            token_totals = {'total_input_tokens': 0, 'total_output_tokens': 0, 'total_tokens': 0}
            returned = 0
            retry_tasks = []

            for i, res in enumerate(results):
                if isinstance(res, Exception) or res is None:
                    retry_tasks.append(tasks[i][0])
                    continue
                batch_items, batch_tokens, batch_cnt = res
                all_data.extend(batch_items)
                if batch_tokens:
                    token_totals['total_input_tokens'] += batch_tokens.get("total_input_tokens", 0)
                    token_totals['total_output_tokens'] += batch_tokens.get("total_output_tokens", 0)
                    token_totals['total_tokens'] += batch_tokens.get("total_tokens", 0)
                returned += batch_cnt

            # ---- 4. Retry failed tasks ----
            if retry_tasks:
                retry_results = await asyncio.gather(
                    *[self.question_bank_generator(rq, rq.number_of_questions) for rq in retry_tasks],
                    return_exceptions=True
                )
                for res in retry_results:
                    if isinstance(res, Exception) or res is None:
                        continue
                    batch_items, batch_tokens, batch_cnt = res
                    all_data.extend(batch_items)
                    if batch_tokens:
                        token_totals['total_input_tokens'] += batch_tokens.get("total_input_tokens", 0)
                        token_totals['total_output_tokens'] += batch_tokens.get("total_output_tokens", 0)
                        token_totals['total_tokens'] += batch_tokens.get("total_tokens", 0)
                    returned += batch_cnt

            # ---- 5. Top-up if still short ----
            '''while returned < total_need:
                remaining = total_need - returned
                more_items, more_tokens, more_cnt = await self.fetch_remaining_questions(
                    request, remaining, all_data, token_totals, returned, total_need
                )
                all_data.extend(more_items)
                returned += more_cnt'''
            
            result_report = await cs_db_connect.add_mcq_data(request, all_data,table_name)
            #asyncio.create_task(cs_db_connect.delete_progress(request.uuid))
            print("✅ Final Question Count:", len(all_data))
            return all_data, token_totals, len(all_data), result_report

        except Exception as e:
            print(f"[cs_question_bank_generator] error: {e}")
            return [], {}, 0, []

    
    
        
    async def split_and_generate_questions(self, request: cs_classes.QuestionRequest, No: int):
        try:
            print(f"Splitting task: Total {No} questions for topic {request.topic_name[0]}")

            batch_size = self.max_questions_per_call
            total_passed = []
            if total_passed != []:
                if request.already_gen_mcqs is None:
                    questions_only = [item['question'] for item in total_passed]
                else:
                    questions_only = []
                    gen_questions = [item['question'] for item in total_passed]
                    questions_only.extend(request.already_gen_mcqs)
                    questions_only.extend(gen_questions)
                #print(f"Already generated questions: {len(questions_only)}")
                new_request = cs_classes.QuestionRequest(user_id=request.user_id,
                                                uuid=request.uuid,
                                                subject_name=request.subject_name,
                                                chapter_name=request.chapter_name,
                                                topic_name=request.topic_name,
                                                difficulty=request.difficulty,
                                                number_of_questions=request.number_of_questions,
                                                cognitive_level=request.cognitive_level,
                                                already_gen_mcqs=questions_only,
                                                model=request.model,
                                                stream=request.stream)
            else:
                new_request = request

            total_tokens = {"total_input_tokens": 0,"total_output_tokens": 0,"total_tokens": 0}
            total_required = No
            batch_num = 1

            while len(total_passed) < total_required:
                remaining_needed = total_required - len(total_passed)
                current_batch = min(batch_size, remaining_needed)

                print(f"Starting Batch {batch_num}: Need {remaining_needed}, asking for {current_batch}")

                passed_items, tokens, count = await self.question_bank_generator(new_request, current_batch)

                total_passed.extend(passed_items)
                if tokens:
                    total_tokens["total_input_tokens"] += tokens.get("total_input_tokens", 0)
                    total_tokens["total_output_tokens"] += tokens.get("total_output_tokens", 0)
                    total_tokens["total_tokens"] += tokens.get("total_tokens", 0)

                print(f"Batch {batch_num} done. Got {count} valid questions. Total so far: {len(total_passed)}")
                batch_num += 1

            print(f"All batches done. Total passed: {len(total_passed)}")
            result_report = await cs_db_connect.add_mcq_data(request, total_passed)
            return total_passed, total_tokens, len(total_passed), result_report

        except Exception as e:
            print(f"Error in split_and_generate_questions: {e}")
            return [], {}, 0, []        

    async def assigner_function(self, request: cs_classes.TopicRequest):
        try:
            report_new =[]
            total_questions_count= 0
            if isinstance(request.chapter_name, list):
                chapter_name = ' '.join(map(str, request.chapter_name))
            else:
                chapter_name = request.chapter_name

            # Fetch topic details from DB
            topic_det = await cs_db_connect.get_topic_det(chapter_name=chapter_name)
            #topic_det = [(441, 'N2-Metab0Lism', 'Botany', 'Mineral Nutrition')]

            total_questions = []
            total_tokens = {"total_input_tokens": 0,"total_output_tokens": 0,"total_tokens": 0}

            # Initialize deeply nested defaultdict
            report = defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(
                        lambda: defaultdict(
                            lambda: defaultdict(
                                lambda: defaultdict(int)
                            )
                        )
                    )
                )
            )

            # Loop through each topic
            for db_det in topic_det:
                topic_id = db_det[0]
                topic_name = db_det[1]
                subject_name = db_det[2]
                chapter_name = db_det[3]

                for difficulty in cs_classes.difficulty_levels:
                    tasks = []
                    task_info = []  # Reset for every difficulty level

                    for cog_level in cs_classes.cognitive_levels:
                        cognitive_id = constants.cognitive_levels.get(cog_level.lower())

                        # Fetch already generated questions
                        db_questions = await cs_db_connect.get_question_det_repo(topic_id=topic_id,cog_id=cognitive_id)
                        model_val = 1
                        stream_val = "CBSE"

                        # Prepare a new request for question generation
                        new_request = cs_classes.QuestionRequest(
                            user_id=1,
                            uuid="dummy_uuid",
                            subject_name=[subject_name],
                            chapter_name=[chapter_name],
                            topic_name=[topic_name],
                            difficulty=difficulty,
                            number_of_questions=request.number_of_questions,
                            cognitive_level=cog_level,
                            already_gen_mcqs=db_questions,
                            model=model_val,
                            stream=stream_val
                        )

                        tasks.append(
                            self.cs_question_bank_generator(
                                table_name=cs_classes.repo_MCQData,
                                request=new_request))
                        task_info.append((topic_name, difficulty, cog_level, model_val, stream_val))

                    # Run all generation tasks concurrently
                    responses = await asyncio.gather(*tasks)

                    # Handle all responses
                    for (topic_name, difficulty, cog_level, model_val, stream_val), response in zip(task_info, responses):
                        if response:
                            result, gen_tokens, total_questions_generated, db_report = response
                            total_questions.extend(result)

                            if gen_tokens:
                                total_tokens['total_input_tokens'] += gen_tokens.get("total_input_tokens", 0)
                                total_tokens['total_output_tokens'] += gen_tokens.get("total_output_tokens", 0)
                                total_tokens['total_tokens'] += gen_tokens.get("total_tokens", 0)
                            elif db_report:
                                report_new.append(db_report)
                            elif total_questions_generated:
                                total_questions_count += total_questions_generated

                            question_types = cs_classes.cognitive_level_to_question_types.get(cog_level.lower(), [])
                            for ques_type in question_types:
                                report[topic_name][difficulty][cog_level][ques_type][model_val][stream_val] += total_questions_generated

            report_new.append({
                "total_questions_count": total_questions_count,
            })
            return total_questions, total_tokens, report_new
        except Exception as e:
            print(f"Error in assigner_function: {e}")
            return [], {}, []
 
question_banks = question_bank()  
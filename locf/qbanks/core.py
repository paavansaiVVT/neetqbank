from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import asyncio, os, time, re, constants, json, ast, uuid
from itertools import product
from dotenv import load_dotenv
from locf.qbanks import prompts, db, classes, helper_functions
from collections import Counter
from langchain_core.output_parsers import JsonOutputParser
from collections import defaultdict
from typing import Any, Dict, List, Tuple

load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')


class question_bank:
    def __init__(self):
        self.max_questions_per_call = 20
        self.thinking_tokens = 250

        # Models
        self.model_flash2 = "gemini-2.0-flash-001"
        # self.model_flash2 = "gemini-2.5-flash-lite-preview-06-17"
        self.model_flash25 = "gemini-2.5-flash"
        self.model_pro_25 = "gemini-2.5-pro-preview-05-06"
        self.model_o4_mini = "o4-mini"

        # LLM instances
        self.llm_o4_mini = ChatOpenAI(model=self.model_o4_mini)
        self.llm_flash2 = ChatGoogleGenerativeAI(model=self.model_flash2)
        self.llm_flash25 = ChatGoogleGenerativeAI(model=self.model_flash25)
        self.llm_flasht25 = ChatGoogleGenerativeAI(model=self.model_flash25, thinking_budget=self.thinking_tokens)
        self.llm_pro_25 = ChatGoogleGenerativeAI(model=self.model_pro_25)
        
        # QC LLM
        self.qc_llm = ChatGoogleGenerativeAI(model=self.model_flash2, temperature=0.3)
        self.parser = JsonOutputParser(pydantic_object=classes.MCQ)

    # -------------------- utilities --------------------

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

    def _strip_code_fence(self, text: str) -> str:
        m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, flags=re.S | re.I)
        return m.group(1).strip() if m else text.strip()

    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """
        Robust, bounded parsing for QC outputs that should be a JSON array.
        Accepts: raw array, quoted array (stringified), or fenced ```json blocks.
        Performs minimal safe repairs only.
        """
        t = self._strip_code_fence(text)

        # Normalize stray unicode quotes and strip control chars / BOM
        if isinstance(t, str):
            t = t.replace("“", '"').replace("”", '"').replace("’", "'")
            t = re.sub(r'[\ufeff\x00-\x1F]+', '', t)

        # If the whole thing is a quoted string, unquote once
        if isinstance(t, str) and t.startswith('"') and t.endswith('"'):
            try:
                t = json.loads(t)  # becomes inner JSON string if it was quoted
            except Exception:
                pass

        if isinstance(t, str):
            t = t.strip()
            # slice to outermost [ ... ] if there is extra prose
            if '[' in t and ']' in t:
                t = t[t.find('['): t.rfind(']') + 1]
            # remove trailing commas before } or ]
            t = re.sub(r",\s*([}\]])", r"\1", t)
            return json.loads(t)

        # if already decoded once and is still a JSON string, load again
        return json.loads(t)

    def _merge_tokens(self, tot: Dict[str, int], add: Dict[str, int]) -> None:
        if not add:
            return
        tot["total_input_tokens"] = tot.get("total_input_tokens", 0) + add.get("total_input_tokens", 0)
        tot["total_output_tokens"] = tot.get("total_output_tokens", 0) + add.get("total_output_tokens", 0)
        tot["total_tokens"] = tot.get("total_tokens", 0) + add.get("total_tokens", 0)

    # -------------------- single-pass generation (no loops) --------------------

    async def _generate_one_batch(self,request: classes.QuestionRequest,n: int,co_outcomes=None) -> Tuple[List[Dict[str, Any]], Dict[str, int], int, int]:
        """Run exactly one LLM → parse → QC pass and return: (passed_items, tokens_dict, passed_count, failed_count)"""
        self.llm = self.get_llm_by_model(request.model)

        generation_response = await self.llm.ainvoke(
            prompts.mcq_question_generation_template.format(co_outcomes=co_outcomes,program=request.program_name,subject=request.subject_name,chapter=request.chapter_name,topics=request.topic_name,difficulty=request.difficulty,No=n,cognitive_level=request.cognitive_level,already_generated=request.already_gen_mcqs))
        #print("GEN META:", getattr(generation_response, "usage_metadata", None), getattr(generation_response, "response_metadata", None))

        gen_text = self._ensure_text(generation_response.content)
        # Use your existing helper JSON parser for generation (now that prompts are fixed)
        cleaned_data = helper_functions.json_helpers.parse_json(gen_text)

        QC_response = await self.qc_llm.ainvoke(
            prompts.qc_prompt.format(mcqs=cleaned_data)
        )
        #print("QC  META:", getattr(QC_response, "usage_metadata", None), getattr(QC_response, "response_metadata", None))
        qc_text = self._ensure_text(QC_response.content)
        # Parse QC with a plain array parser (schema ≠ MCQ)
        qc_output = self._parse_json_array(qc_text)

        merged = helper_functions.helpers.merge_data(cleaned_data, qc_output)
        cln_output = helper_functions.helpers.check_options(merged)

        passed_qc = [item for item in cln_output if item.get('QC') == 'pass']
        failed_qc = [item for item in cln_output if item.get('QC') == 'fail']

        passed_items = await helper_functions.helpers.key_function(request, passed_qc)
        print(f"len(passed_items): {len(passed_items)}")

        # Pull usage from both generation + QC calls
        gen_usage = helper_functions.helpers._extract_tokens(generation_response)
        qc_usage  = helper_functions.helpers._extract_tokens(QC_response)

        tokens = {
            "total_input_tokens":  gen_usage["total_input_tokens"]  + qc_usage["total_input_tokens"],
            "total_output_tokens": gen_usage["total_output_tokens"] + qc_usage["total_output_tokens"],
            "total_tokens":        gen_usage["total_tokens"]        + qc_usage["total_tokens"],
        }

        return passed_items, tokens, len(passed_items), len(failed_qc)
    
    async def _generate_one_sa_batch(self,request: classes.QuestionRequest,n: int,co_outcomes=None) -> Tuple[List[Dict[str, Any]], Dict[str, int], int, int]:
        """Run exactly one LLM → parse → QC pass and return: (passed_items, tokens_dict, passed_count, failed_count)"""
        self.llm = self.get_llm_by_model(request.model)

        generation_response = await self.llm.ainvoke(
            prompts.sa_question_generation_template.format(co_outcomes=co_outcomes,program=request.program_name,subject=request.subject_name,chapter=request.chapter_name,topics=request.topic_name,difficulty=request.difficulty,No=n,cognitive_level=request.cognitive_level,already_generated=request.already_gen_mcqs))
        #print("GEN META:", getattr(generation_response, "usage_metadata", None), getattr(generation_response, "response_metadata", None))

        gen_text = self._ensure_text(generation_response.content)
        # Use your existing helper JSON parser for generation (now that prompts are fixed)
        cleaned_data = helper_functions.json_helpers.parse_json(gen_text)

        QC_response = await self.qc_llm.ainvoke(
            prompts.sa_qc_prompt.format(saqs=cleaned_data)
        )
        #print("QC  META:", getattr(QC_response, "usage_metadata", None), getattr(QC_response, "response_metadata", None))
        qc_text = self._ensure_text(QC_response.content)
        # Parse QC with a plain array parser (schema ≠ MCQ)
        qc_output = self._parse_json_array(qc_text)

        merged = helper_functions.helpers.merge_data(cleaned_data, qc_output)
        # cln_output = helper_functions.helpers.check_options(merged)

        passed_qc = [item for item in merged if item.get('QC') == 'pass']
        failed_qc = [item for item in merged if item.get('QC') == 'fail']

        passed_items = await helper_functions.helpers.key_function(request, passed_qc)
        print(f"len(passed_items): {len(passed_items)}")

        # Pull usage from both generation + QC calls
        gen_usage = helper_functions.helpers._extract_tokens(generation_response)
        qc_usage  = helper_functions.helpers._extract_tokens(QC_response)

        tokens = {
            "total_input_tokens":  gen_usage["total_input_tokens"]  + qc_usage["total_input_tokens"],
            "total_output_tokens": gen_usage["total_output_tokens"] + qc_usage["total_output_tokens"],
            "total_tokens":        gen_usage["total_tokens"]        + qc_usage["total_tokens"],
        }

        return passed_items, tokens, len(passed_items), len(failed_qc)

    async def _generate_one_la_batch(self,request: classes.QuestionRequest,n: int,co_outcomes=None) -> Tuple[List[Dict[str, Any]], Dict[str, int], int, int]:
        """Run exactly one LLM → parse → QC pass and return: (passed_items, tokens_dict, passed_count, failed_count)"""
        self.llm = self.get_llm_by_model(request.model)

        generation_response = await self.llm.ainvoke(
            prompts.la_question_generation_template.format(co_outcomes=co_outcomes,program=request.program_name,subject=request.subject_name,chapter=request.chapter_name,topics=request.topic_name,difficulty=request.difficulty,No=n,cognitive_level=request.cognitive_level,already_generated=request.already_gen_mcqs))
        #print("GEN META:", getattr(generation_response, "usage_metadata", None), getattr(generation_response, "response_metadata", None))

        gen_text = self._ensure_text(generation_response.content)
        # Use your existing helper JSON parser for generation (now that prompts are fixed)
        cleaned_data = helper_functions.json_helpers.parse_json(gen_text)

        QC_response = await self.qc_llm.ainvoke(
            prompts.la_qc_prompt.format(laqs=cleaned_data)
        )
        #print("QC  META:", getattr(QC_response, "usage_metadata", None), getattr(QC_response, "response_metadata", None))
        qc_text = self._ensure_text(QC_response.content)
        # Parse QC with a plain array parser (schema ≠ MCQ)
        qc_output = self._parse_json_array(qc_text)

        merged = helper_functions.helpers.merge_data(cleaned_data, qc_output)
        # cln_output = helper_functions.helpers.check_options(merged)

        passed_qc = [item for item in merged if item.get('QC') == 'pass']
        failed_qc = [item for item in merged if item.get('QC') == 'fail']

        passed_items = await helper_functions.helpers.key_function(request, passed_qc)
        print(f"len(passed_items): {len(passed_items)}")

        # Pull usage from both generation + QC calls
        gen_usage = helper_functions.helpers._extract_tokens(generation_response)
        qc_usage  = helper_functions.helpers._extract_tokens(QC_response)

        tokens = {
            "total_input_tokens":  gen_usage["total_input_tokens"]  + qc_usage["total_input_tokens"],
            "total_output_tokens": gen_usage["total_output_tokens"] + qc_usage["total_output_tokens"],
            "total_tokens":        gen_usage["total_tokens"]        + qc_usage["total_tokens"],
        }

        return passed_items, tokens, len(passed_items), len(failed_qc)

    # -------------------- main generator (iterative, non-recursive) --------------------

    async def question_bank_generator(
        self,
        request: classes.QuestionRequest,
        No: int,
        co_outcomes=None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int], int]:
        """
        Keep generating until we fill exactly `No` passed items or hit `max_attempts`.
        If some items are rejected in a batch, we keep trying only for the deficit.
        """
        all_data: List[Dict[str, Any]] = []
        tokens: Dict[str, int] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

        returned = 0
        max_attempts = 8  # hard cap
        attempts = 0

        try:
            while returned < No and attempts < max_attempts:
                attempts += 1

                # Build de-duplication list from:
                # - anything the caller provided
                # - anything we've successfully accepted so far
                dedupe: List[str] = []
                if getattr(request, "already_gen_mcqs", None):
                    dedupe.extend(request.already_gen_mcqs)
                dedupe.extend([q["question"] for q in all_data if isinstance(q, dict) and "question" in q])

                remaining_needed = No - returned

                # Clone request with an updated "already_gen_mcqs" and target count
                updated_payload = request.model_dump()
                updated_payload["already_gen_mcqs"] = dedupe
                updated_payload["number_of_questions"] = remaining_needed
                updated_req = classes.QuestionRequest(**updated_payload)

                if request.question_type.lower() == "multiple_choice":
                    # Ask only for the deficit; _generate_one_batch should return PASSED items
                    batch_items, batch_tokens, batch_cnt, _ = await self._generate_one_batch(
                        updated_req, remaining_needed, co_outcomes
                    )
                elif request.question_type.lower() == "short_answer":
                    batch_items, batch_tokens, batch_cnt, _ = await self._generate_one_sa_batch(
                        updated_req, remaining_needed, co_outcomes
                    )
                elif request.question_type.lower() == "long_answer":
                    batch_items, batch_tokens, batch_cnt, _ = await self._generate_one_la_batch(
                        updated_req, remaining_needed, co_outcomes
                    )
                else:
                    print(f"Unknown question_type {request.question_type}; supported: MCQ, SAQ")
                    return [], {}, 0

                # Accumulate accepted items and tokens
                if batch_items:
                    all_data.extend(batch_items)
                if batch_tokens:
                    self._merge_tokens(tokens, batch_tokens)

                returned += int(batch_cnt or 0)

                # async progress ping (non-blocking)
                try:
                    asyncio.create_task(
                        helper_functions.helpers.cal_percentage(
                            updated_req.uuid, returned, No  # reflect the real target, not the original request
                        )
                    )
                except Exception:
                    # Progress is non-critical; ignore failures
                    pass

                # note: Do NOT break on zero-progress — keep trying up to max_attempts.
                # This ensures that if 1 of 5 gets rejected, we continue trying to fill that one.

            print(f"No of Total items requested: {No}, No of passed items: {returned}, attempts used: {attempts}")
            return all_data, tokens, len(all_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error occurred in question_bank_generator: {e}")
            return [], {}, 0

    # -------------------- optional topper (non-recursive) --------------------

    async def fetch_remaining_questions(
        self,
        request: classes.QuestionRequest,
        remaining: int,
        all_data: List[Dict[str, Any]],
        total_tokens: Dict[str, int],
        total_questions: int,
        target_total: int,
        co_outcomes=None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int], int]:
        """
        Helper that calls _generate_one_batch directly (NO calls to question_bank_generator).
        """
        try:
            dedupe: List[str] = []
            if request.already_gen_mcqs:
                dedupe.extend(request.already_gen_mcqs)
            dedupe.extend([q['question'] for q in all_data if 'question' in q])

            updated = request.model_dump()
            updated["already_gen_mcqs"] = dedupe
            updated["number_of_questions"] = remaining
            new_request = classes.QuestionRequest(**updated)
            
            if request.question_type.lower() == "multiple_choice":
                items, tok, cnt, _ = await self._generate_one_batch(new_request, remaining, co_outcomes)
            elif request.question_type.lower() == "short_answer":
                items, tok, cnt, _ = await self._generate_one_sa_batch(new_request, remaining, co_outcomes)
            elif request.question_type.lower() == "long_answer":
                items, tok, cnt, _ = await self._generate_one_la_batch(new_request, remaining, co_outcomes)

            to_add = min(cnt, target_total - total_questions)

            self._merge_tokens(total_tokens, tok)
            return items[:to_add], tok, to_add

        except Exception as e:
            print(f"Error while fetching remaining questions: {e}")
            return [], {}, 0

    # -------------------- organizer --------------------

    async def question_bank_organizer(self, table_name, request: classes.QuestionRequest, chunk_size: int = 2):
        """
        Generate MCQs with minimal token cost and avoid duplication by fixed ordering and bounded top-up.
        """
        try:
            await db.user_request_log(request)
            co_outcomes = await db.get_course_outcomes_list(request.course_id)
            total_need = int(request.number_of_questions)
            topics = list(request.topic_name)
            n_topics = len(topics)

            if total_need <= 0 or n_topics == 0:
                return [], {}, 0, []

            # Fast path: one chapter and too many questions => split internally
            if len(request.topic_name) == 1 and request.number_of_questions > self.max_questions_per_call:
                passed_items, tokens, count = await self.split_and_generate_questions(
                    request, request.number_of_questions, co_outcomes
                )
                if table_name is not None:
                    result_report = await db.add_mcq_data(request, passed_items, table_name)
                else:
                    result_report = []
                print("✅ Final Question Count:", len(passed_items))
                await db.token_update_fc(request, tokens, "gemini-2.5-flash-preview-05-20")
                return passed_items, tokens, count, result_report

            # ---- 1) Distribute across topics ----
            per_topic = [total_need // n_topics] * n_topics
            for i in range(total_need % n_topics):
                per_topic[i] += 1

            # Build batches such that each request ≤ max_questions_per_call
            batches, current, current_q = [], [], 0
            for idx, topic in enumerate(topics):
                q_needed = per_topic[idx]
                if current_q + q_needed > self.max_questions_per_call and current:
                    batches.append(current)
                    current, current_q = [], 0
                current.append((idx, topic, q_needed))
                current_q += q_needed
            if current:
                batches.append(current)

            base = request.model_dump()
            base.pop("topic_name", None)
            base.pop("number_of_questions", None)

            async def run_batch(batch):
                idxs = [it[0] for it in batch]
                batch_topics = [it[1] for it in batch]
                q_in_batch = sum(it[2] for it in batch)

                topic_req = classes.QuestionRequest(**base, topic_name=list(batch_topics), number_of_questions=q_in_batch)
                # Use split (which internally uses the non-recursive generator)
                return await self.split_and_generate_questions(topic_req, q_in_batch, co_outcomes)

            # ---- 2) Run batches concurrently ----
            results = await asyncio.gather(*[run_batch(b) for b in batches], return_exceptions=True)

            all_data: List[Dict[str, Any]] = []
            token_totals = {'total_input_tokens': 0, 'total_output_tokens': 0, 'total_tokens': 0}
            returned = 0
            retry_reqs: List[classes.QuestionRequest] = []

            for i, res in enumerate(results):
                if isinstance(res, Exception) or res is None:
                    # reconstruct request for retry
                    idxs = [t[0] for t in batches[i]]
                    batch_topics = [t[1] for t in batches[i]]
                    q_in_batch = sum(t[2] for t in batches[i])
                    topic_req = classes.QuestionRequest(**base, topic_name=list(batch_topics), number_of_questions=q_in_batch)
                    retry_reqs.append(topic_req)
                    continue

                batch_items, batch_tokens, batch_cnt = res
                all_data.extend(batch_items)
                self._merge_tokens(token_totals, batch_tokens)
                returned += batch_cnt

            # ---- 3) Retry failed batches once ----
            if retry_reqs:
                retry_results = await asyncio.gather(
                    *[self.split_and_generate_questions(rq, rq.number_of_questions, co_outcomes) for rq in retry_reqs],
                    return_exceptions=True
                )
                for res in retry_results:
                    if isinstance(res, Exception) or res is None:
                        continue
                    batch_items, batch_tokens, batch_cnt = res
                    all_data.extend(batch_items)
                    self._merge_tokens(token_totals, batch_tokens)
                    returned += batch_cnt

            # ---- 4) Top-up if short (bounded) ----
            max_topup_attempts = 5
            topup_attempts = 0
            while returned < total_need and topup_attempts < max_topup_attempts:
                topup_attempts += 1
                remaining = total_need - returned
                more_items, more_tokens, more_cnt = await self.fetch_remaining_questions(
                    request, remaining, all_data, token_totals, returned, total_need, co_outcomes
                )
                all_data.extend(more_items)
                returned += more_cnt
                if more_cnt == 0:
                    break

            if table_name is not None:
                result_report = await db.add_mcq_data(request, all_data, table_name)
            else:
                result_report = []
            print("✅ Final Question Count:", len(all_data))
            await db.token_update_fc(request, token_totals, "gemini-2.5-flash-preview-05-20")
            return all_data, token_totals, len(all_data), result_report

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[cs_question_bank_generator] error: {e}")
            return [], {}, 0, []

    # -------------------- splitter (uses main generator; no recursion cycles) --------------------

    async def split_and_generate_questions(self, request: classes.QuestionRequest, No: int, co_outcomes=None):
        """
        Split into batches of at most self.max_questions_per_call,
        each batch calling the non-recursive generator.
        """
        try:
            batch_size = self.max_questions_per_call
            total_passed: List[Dict[str, Any]] = []
            total_tokens = {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}

            total_required = int(No)
            batch_num = 1

            while len(total_passed) < total_required:
                remaining_needed = total_required - len(total_passed)
                current_batch = min(batch_size, remaining_needed)

                print(f"Starting Topic: {request.topic_name} | Batch {batch_num}: Need {remaining_needed}, asking {current_batch}, with question type: '{request.question_type}'")

                # Keep dedupe updated across batches
                dedupe = (request.already_gen_mcqs or []) + [q['question'] for q in total_passed if 'question' in q]
                updated = request.model_dump()
                updated["already_gen_mcqs"] = dedupe
                updated["number_of_questions"] = current_batch
                updated_req = classes.QuestionRequest(**updated)

                batch_items, tokens, count = await self.question_bank_generator(updated_req, current_batch, co_outcomes=co_outcomes)

                total_passed.extend(batch_items)
                self._merge_tokens(total_tokens, tokens)

                print(f"Topic: {len(updated_req.topic_name)} | Batch {batch_num} done. Got {count} valid. Total so far: {len(total_passed)}")
                batch_num += 1

                if count == 0:
                    # No progress — stop splitting to avoid spinning
                    break

            print(f"All batches done. Total passed: {len(total_passed)}")
            return total_passed, total_tokens, len(total_passed)

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"Error in split_and_generate_questions: {e}")
            return [], {}, 0

    # -------------------- chapter_check (parse single object safely) --------------------

    async def chapter_check(self, question, old_chapter, chapter_name_list, subject_id=None, program_id=None):
        try:
            self.llm = self.get_llm_by_model(model_id=1)
            generation_response = await self.llm.ainvoke(
                prompts.chapter_check_template.format(
                    question=question,
                    old_chapter=old_chapter,
                    chapter_name_list=chapter_name_list
                )
            )
            generation_text = self._ensure_text(generation_response.content)
            generation_text = self._strip_code_fence(generation_text)
            # small trims; expect a single JSON object
            obj = json.loads(generation_text)
            chapter_name = obj["chapter_name"]
            sub_id, cha_id = await db.get_chapters(chapter_name=chapter_name, retry_id=1, subject_id=subject_id, program_id=program_id)
            return sub_id, cha_id
        except Exception:
            print("Error in chapter_check")
            return None, None

    # -------------------- (unchanged) pre_question_bank_organizer --------------------

    async def pre_question_bank_organizer(self, request: classes.TopicQuestionrequest):
        try:
            report_new = []
            current_unique_id = str(uuid.uuid4())

            total_questions: list = []
            total_questions_count = 0
            total_tokens = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
            }

            # Concurrency throttle
            semaphore = asyncio.Semaphore(10)
            #chapter_and_topic = [{'chapter_name': 'Introduction to Java and OOP Concepts', 'topics': ['Introduction: Review of Object-Oriented concepts', 'Java buzzwords (Platform independence, Portability, Threads)', 'JVM architecture', 'Java Program structure', 'Java main method', 'Java Console output(System.out)', 'simple java program', 'Data types', 'Variables', 'type conversion and casting', 'Java Console input: Buffered input', 'operators', 'control statements', 'Static Data', 'Static Method', 'String and String Buffer Classes']}, {'chapter_name': 'Classes, Objects, Inheritance, Packages, and Interfaces', 'topics': ['Java user defined Classes and Objects', 'Arrays', 'constructors', 'Inheritance: Basic concepts', 'Types of inheritance', 'Member access rules', 'Usage of this and Super key word', 'Method Overloading', 'Method overriding', 'Abstract classes', 'Dynamic method dispatch', 'Usage of final keyword', 'Packages: Definition', 'Access Protection', 'Importing Packages', 'Interfaces: Definition', 'Implementation', 'Extending Interfaces']}]
            chapter_and_topic = await db.get_chapter_and_topic(program_id=request.program_id, subject_id=request.subject_id) 
            if not chapter_and_topic: 
                return [], {}, 0

            print(f"Chapter and topic fetched: {len(chapter_and_topic)} chapters found.")

            async def limited_question_task(req: classes.QuestionRequest):
                async with semaphore:
                    return await self.question_bank_organizer(
                        table_name=classes.MCQData,
                        request=req,
                    )
            
            # Iterate chapters → topics
            for chapter_data in chapter_and_topic:
                chapter_name = chapter_data["chapter_name"]

                tasks = []
                task_info = []  # align 1:1 with tasks for logging/context

                for topic_name in chapter_data["topics"]:
                    # Build per-topic request
                    new_request = classes.QuestionRequest(
                        user_id=4,
                        uuid="default_uuid",
                        course_id=request.course_id,
                        program_id=request.program_id,
                        program_name=request.program_name,
                        subject_id=request.subject_id,
                        subject_name=[request.subject_name],
                        chapter_name=[chapter_name],
                        topic_name=[topic_name],
                        question_type="multiple_choice",
                        # keep your distributions (adjust types here if your model expects int)
                        cognitive_level={
                                "remembering": 16.66,
                                "understanding": 16.66,
                                "applying": 16.66,
                                "analyzing": 16.66,
                                "evaluating": 16.66,
                                "creating": 16.66
                            },
                        difficulty={"easy": 33.33, "medium": 33.33, "hard": 33.33},
                        number_of_questions=request.number_of_questions,
                        model=1,
                        stream=1,
                    )

                    tasks.append(limited_question_task(new_request))
                    task_info.append({"topic": topic_name, "chapter": chapter_name})

                # Run all topic tasks for this chapter concurrently
                if tasks:
                    responses = await asyncio.gather(*tasks, return_exceptions=True)

                    # Process results
                    for info, response in zip(task_info, responses):
                        topic_name = info["topic"]
                        chapter_name = info["chapter"]

                        if isinstance(response, Exception):
                            print(f"Error generating for {chapter_name} → {topic_name}: {response}")
                            continue

                        # Expected: (result, gen_tokens, total_questions_generated, db_report)
                        result, gen_tokens, total_questions_generated, db_report = response

                        if result:
                            total_questions.extend(result)

                        if gen_tokens:
                            total_tokens["total_input_tokens"] += gen_tokens.get("total_input_tokens", 0)
                            total_tokens["total_output_tokens"] += gen_tokens.get("total_output_tokens", 0)
                            total_tokens["total_tokens"] += gen_tokens.get("total_tokens", 0)

                        if db_report:
                            report_new.append(db_report)

                        if total_questions_generated:
                            total_questions_count += total_questions_generated

            # Final summary in report
            report_new.append({"total_questions_count": total_questions_count})

            # Attribute usage to the outer request (not a stale inner new_request)
            await db.token_update_fc(
                new_request,
                total_tokens,
                "gemini-2.5-flash-preview-05-20",
                "pre_gen_question_bank",
            )

            return total_questions, total_tokens, report_new

        except Exception as e:
            print(f"Error in pre_question_bank_organizer: {e}")
            return [], {}, []

question_banks = question_bank()

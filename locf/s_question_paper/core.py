# --- START OF FILE core.py --- (with corrections)

import os, base64, asyncio, boto3, requests, logging, re, uuid, json, traceback
# The 'mistralai' imports are unused in the provided code.
# If you don't plan to use Mistral, it's best to remove them.
# from mistralai import Mistral
# from mistralai.extra import response_format_from_pydantic_model
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from PyPDF2 import PdfReader
from typing import List, Optional, Literal, Dict, Any, Tuple
from dotenv import load_dotenv
from io import BytesIO
from locf.s_question_paper import prompts, classes, db, parser_helper
from locf.s_question_paper.helper_function import ocr_helper_function, llm_helper_function, qllm_helper_function

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

# NOTE: The Mistral client is initialized but never used in the class logic.
# Consider removing if it's not needed.
# client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
# print(f"Mistral client initialized successfully.")

# Initialize boto3 client
s3 = boto3.client("s3",
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)

AWS_S3_REGION= os.getenv("AWS_S3_REGION")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
GOOGLE_API_KEY= os.getenv('GOOGLE_API_KEY')

class doc_ocr:
    def __init__(self):
        self.batch_size = 5
        self.bucket_name = AWS_S3_BUCKET_NAME
        # Using a more recent and stable model is often better.
        # "gemini-1.5-flash-latest" is a good, fast choice.
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            api_key=GOOGLE_API_KEY
        )
        self.json_parser = JsonOutputParser()

    async def ocr_process(self, request: classes.QuestionPaperRequest) -> tuple[List[Dict[str, Any]], List[str], Any, Any]:
        """
        Orchestrates the entire streamlined image tagging process.
        """
        batches = ocr_helper_function.get_page_batches(request.pdf_url)
        if not batches:
            return [], [], None, None

        all_final_tags = []
        base_s3_url = f"https://{self.bucket_name}.s3.{AWS_S3_REGION}.amazonaws.com"

        for i, batch in enumerate(batches, 1):
            print(f"\n--- Processing Batch {i}/{len(batches)} (Pages: {batch}) ---")

            pdf_response = ocr_helper_function.perform_basic_ocr(request.pdf_url, batch)
            if not pdf_response or not any(p.images for p in pdf_response.pages):
                print(f"No images found in batch {i}. Skipping.")
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

    async def model_llm(self, qp_md: str, qp_list: List[int], messages_content: List) -> List[Dict[str, Any]]:
        #prompt_template = PromptTemplate.from_template(prompts.question_prompt)
        # prompt_template = ChatPromptTemplate.from_messages([("system", prompts.question_prompt), MessagesPlaceholder(variable_name="human_messages")])
        # chain = prompt_template | self.llm
        # generation_response = await chain.ainvoke({"question_paper_text": qp_md,"question_list": qp_list, "human_messages": messages_content})
        # gen_content = generation_response.content
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompts.question_prompt),
            MessagesPlaceholder("human_messages"),
        ])

        msgs = prompt_template.format_messages(
            question_paper_text=qp_md,
            question_list=qp_list,
            human_messages=messages_content,
        )

        generation_response = await self.llm.ainvoke(msgs)
        gen_content = generation_response.content

        #print(f"Raw Question tokens: {generation_response.usage_metadata}")

        parser = JsonOutputParser()
        parsed_json = []
        try:
            parsed_json = parser.parse(gen_content)
        except Exception as e:
            logging.warning(f"Failed to parse JSON with LangChain parser. Falling back.")
            gen_text = qllm_helper_function._ensure_text(gen_content)
            parsed_json = parser_helper.json_helpers.parse_json(gen_text)
        
        gen_usage = qllm_helper_function._extract_tokens(generation_response)

        tokens = {
            "total_input_tokens":  gen_usage["total_input_tokens"],
            "total_output_tokens": gen_usage["total_output_tokens"],
            "total_tokens":        gen_usage["total_tokens"],
        }
        #print(f"Tokens Usage {tokens}")

        return parsed_json, tokens

    def strip_urls_from_output(self, objs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        url_re = re.compile(r"https?://\S+")
        for obj in objs:
            for k in ("student_answer_text", "question_text", "actual_answer", "feedback"):
                if k in obj and isinstance(obj.get(k), str):
                    obj[k] = url_re.sub("[image omitted]", obj[k])
        return objs

    def to_int(self, v: Any) -> Optional[int]:
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return None
        
    def _merge_tokens(self, tot: Dict[str, int], add: Dict[str, int]) -> None:
        if not add:
            return
        tot["total_input_tokens"] = tot.get("total_input_tokens", 0) + add.get("total_input_tokens", 0)
        tot["total_output_tokens"] = tot.get("total_output_tokens", 0) + add.get("total_output_tokens", 0)
        tot["total_tokens"] = tot.get("total_tokens", 0) + add.get("total_tokens", 0)
    
    # --- MODIFIED FUNCTION ---
    async def generation_logic(self, qcount: int, json_data: List[Dict], qp_md: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        if qcount <= 0:
            logging.warning("qcount is 0 or less, skipping generation logic.")
            return [], {}
        
        messages_content = llm_helper_function.build_user_message_dict(urls=json_data)

        gen_question_list = []
        final_response = []
        total_attempts = 0
        max_attempts = 7
        llm_batch_size = 10
        
        # Initialize a dictionary to hold the aggregated token counts
        total_tokens: Dict[str, int] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

        while (
            total_attempts < max_attempts and
            len(gen_question_list) < qcount
        ):
            total_attempts += 1
            re_target_list = [i for i in range(1, qcount + 1) if i not in gen_question_list]

            if not re_target_list:
                break

            logging.info(f"Attempt {total_attempts}/{max_attempts}: Targeting questions {re_target_list}")

            tasks = []
            question_chunks = [
                re_target_list[i : i + llm_batch_size]
                for i in range(0, len(re_target_list), llm_batch_size)
            ]

            for chunk in question_chunks:
                tasks.append(self.model_llm(qp_md, chunk, messages_content))

            logging.info(f"Sending {len(tasks)} parallel requests to the LLM.")
            responses_from_gather = await asyncio.gather(*tasks, return_exceptions=True)

            # --- START OF CORRECTION ---
            # Process the results by unpacking the (parsed_json, tokens) tuple
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
            # --- END OF CORRECTION ---

            resp = self.strip_urls_from_output(all_responses_json)

            valid_ques = [
                row for row in resp
                if self.to_int(row.get("question_number")) in re_target_list
            ]

            valid_ques = qllm_helper_function.prepare_question_content(json_data, valid_ques)
            final_response.extend(valid_ques)

            newly_generated_q_numbers = {
                self.to_int(item.get("question_number"))
                for item in valid_ques
                if self.to_int(item.get("question_number")) is not None
            }
            gen_question_list.extend(list(newly_generated_q_numbers))
            gen_question_list = sorted(list(set(gen_question_list)))

            logging.info(f"Attempt {total_attempts}: Graded questions so far: {gen_question_list}")

        # Deduplication and final check (remains the same)
        seen = set()
        deduped = []
        for row in final_response:
            qno = self.to_int(row.get("question_number"))
            if qno is not None and qno not in seen:
                deduped.append(row)
                seen.add(qno)
        final_response = deduped

        expected = set(range(1, qcount + 1))
        got = {self.to_int(r.get("question_number")) for r in final_response}
        missing = sorted(list(expected - got))
        if missing:
            logging.warning(f"Incomplete grading. Missing questions: {missing}")
        else:
            missing=[]
            
        # Return both the final questions and the total tokens
        return final_response, total_tokens, missing

    # --- CORRECTED: question_scheme to receive and use token data ---
    async def question_scheme(self, request: classes.QuestionPaperRequest) -> List[Dict[str, Any]]:
        try:
            json_data, image_list, gen_response, md_results = await self.ocr_process(request)            
            qp_md, qcount = await qllm_helper_function.question_preparation(gen_response, md_results)
            
            if not isinstance(qcount, int) or qcount <= 0:
                logging.error(f"Invalid question count received: {qcount}. Cannot proceed.")
                return []

            # --- START OF CORRECTION ---
            # Unpack the tuple returned by generation_logic
            final_response, total_tokens, miss_ques = await self.generation_logic(qcount, json_data, qp_md)
            
            # Now you can use the total_tokens dictionary
            #logging.info(f"Total token usage for generation: {total_tokens}")
            # Example: You could add this to your database call
            # await db.update_token_usage(ques_id, total_tokens)
            # --- END OF CORRECTION ---

            asc_sorted = sorted(final_response, key=lambda x: self.to_int(x.get("question_number")) or float('inf'))
            ques_id = await db.add_question_paper_data(request, json_data, image_list, gen_response, md_results, miss_ques)
            await db.add_ques_answer_data(request, asc_sorted, ques_id)
            await db.token_update_fc(request, total_tokens, "gemini-2.0-flash")
            return asc_sorted, total_tokens

        except (requests.exceptions.RequestException, boto3.exceptions.Boto3Error) as e:
            logging.error(f"A network or cloud service error occurred: {e}")
            raise RuntimeError(f"Failed to process document due to a service error: {e}") from e
        except Exception as e:
            logging.error(f"An unexpected error occurred in question_scheme: {e}")
            logging.error(traceback.format_exc())
            raise

ocr_instance = doc_ocr()
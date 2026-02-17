from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import asyncio,os, time,re,constants,json,ast
from dotenv import load_dotenv
from cs_qbanks import cs_classes, cs_prompts, helper_functions
from ocr_qbank import prompts, ocr, classes, db_connect
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate,ChatPromptTemplate
from collections import defaultdict
from tutor_bots import chat
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage,AIMessage

load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

#question_dummy_list = [{'question_no': '34', 'question': 'Gaseous exchange in woody plants occurs through', 'options': ['Stomata – Hydathodes', 'Hydathodes – Cuticle', 'Lenticels – Stomata', 'Cuticle']}, {'question_no': '55', 'question': 'Select the incorrect match.', 'options': ['Vasopressin – Stimulates reabsorption of water and electrolytes by DCT', 'Melatonin – Influences menstrual cycle', 'MSH – Regulates pigmentation of the skin', 'Somatostatin – Stimulates the release of growth hormone from pituitary']}, {'question_no': '109', 'question': 'The coefficient of apparent expansion of a liquid is C when heated in a copper vessel and it is S when heated in a silver vessel. If A is the coefficient of linear expansion of copper, then that of silver is:', 'options': ['C+S-3A/3', 'C+3A-S/3', 'S+3A-C/3', 'C+S+3A/3']}, {'question_no': '110', 'question': 'The volume of liquid at 10°C is 50 cc. Then its volume at 100°C (γR for liquid = 7 × 10^-4/°C) is', 'options': ['53.15 cm³', '55.15 cm³', '5.315 cm³', '5.515 cm³']}, {'question_no': '111', 'question': 'If γA of liquid is 5/8 of γR of liquid. αg of vessel is', 'options': ['γR/8', 'γR/12', 'γR/24', 'γR/36']}, {'question_no': '112', 'question': 'γA of liquid is (7/8) of γR of liquid. αg of vessel is', 'options': ['γR/8', 'γR/12', 'γR/24', 'γR/36']}, {'question_no': '113', 'question': 'If 2g hydrogen gas is contained in a vessel of volume of 3m³ at 27°C, then the pressure of the gas is', 'options': ['8.314 Pa', '83.14 Pa', '415.7 Pa', '831.4 Pa']}, {'question_no': '114', 'question': 'If the volume of air at 0°C and 10 atmospheric pressure is 10 litre, its volume, in litre, at normal temperature and pressure would be', 'options': ['1', '10', '100', '1000']}, {'question_no': '115', 'question': 'Three rods of same length, same cross-sectional area & same material are joined as shown in figure. The temperatures of left & right side are 0°C and 60°C. The temperature θ of junction of three rods are:', 'options': ['60°C', '40°C', '100°C', '70°C']}, {'question_no': '116', 'question': 'Three slabs of thicknesses x1, x2 and x3 and coefficients of thermal conductivity K1, K2 and K3 are placed parallel to each other in contact. In steady state the combination behaves as a single slab of material of conductivity K, given by: (Cross section areas are same)', 'options': ['x1+x2+x3/K = K1/x1 + K2/x2 + K3/x3', 'K/(x1+x2+x3) = x1/K1 + x2/K2 + x3/K3', 'K(1/x1 + 1/x2 + 1/x3) = K1x1 + K2x2 + K3x3', 'x1/K1 + x2/K2 + x3/K3 = (x1+x2+x3)/K']}, {'question_no': '118', 'question': 'Three identical thermal conductors are connected as shown. Consider no heat lost due to radiation, the temperature of the junction in °C is', 'options': ['60', '61', '62', '63']}, {'question_no': '119', 'question': 'Two metallic rods of equal length and cross-section but thermal conductivities K1 and K2 are welded together end to end. The resulting thermal conductivity of this resulting rod will be', 'options': ['K1K2/(K1+K2)', 'K1 + K2', '2K1K2/(K1+K2)', '(K1+K2)/2']}, {'question_no': '120', 'question': 'In a steady state, the temperatures at the end A and B of 20 cm long rod AB are 100°C and 0°C. The temperature of a point 9 cm from A is', 'options': ['45°C', '55°C', '5°C', '65°C']}, {'question_no': '122', 'question': 'A cup of coffee cools from 90°C to 80°C in 5 minutes, when the room temperature is 20°C. The time taken by a similar cup of coffee to cool from 80°C to 60°C at a room temperature same at 20°C is:', 'options': ['13 min', '12 min', '11 min', '5 min']}, {'question_no': '123', 'question': 'A cup of coffee cools from 90°C to 80°C in t minutes when the room temperature is 20°C. The time taken by the similar cup of coffee to cool from 80°C to 60°C at the same room temperature is:', 'options': ['13/5 t', '10/13 t', '13/10 t', '5/13 t']}, {'question_no': '124', 'question': 'The temperature of a body in air falls from 40°C to 24°C in 4 minutes. The temperature of the air is 16°C. The temperature of the body in the next 4 minutes will be:', 'options': ['14/3°C', '28/3°C', '56/3°C', '42/3°C']}, {'question_no': '125', 'question': 'A body take 4 min to cool from 100°C to 70°C. To cool from 70°C to 40°C it will take (room temperature is 15°C)', 'options': ['7 min', '6 min', '5 min', '4 min']}]
class refine_questions:
    def __init__(self):
        self.max_questions_per_call =7
        self.thinking_tokens=250
        self.model_flash2= "gemini-2.0-flash-001"
        self.model_flash25= "gemini-2.5-flash-preview-05-20"
        self.model_pro_25= "gemini-2.5-pro-preview-05-06"
        self.model_o4_mini = "o4-mini"
        self.llm_o4_mini = ChatOpenAI(model=self.model_o4_mini)
        self.llm_flash2=ChatGoogleGenerativeAI(model=self.model_flash2)  
        self.llm_flash25=ChatGoogleGenerativeAI(model=self.model_flash25, thinking_budget=0) 
        self.llm_flasht25=ChatGoogleGenerativeAI(model=self.model_flash25, thinking_budget=self.thinking_tokens)
        self.llm_pro_25=ChatGoogleGenerativeAI(model=self.model_pro_25)
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
    async def question_refined(self, question_list):
        try:
            No= len(question_list)
            start_time = time.time()
            self.llm = self.get_llm_by_model(model_id=2)
            json_question= json.dumps(question_list, indent=2)
            prompt_input = prompts.question_refine_prompt.format(question_list= json_question, topic_name_list= classes.topic_name_list)
            generation_response = await self.llm.ainvoke(prompt_input)
            #print(f"Generation Response: {generation_response.content}")
            #print(f"Time taken for generation: {time.time() - start_time}")
            start_time2 = time.time()
            #print(generation_response.usage_metadata)
            if isinstance(generation_response.content, list):
                print(f"it is in list with len {len(generation_response.content)}")
                generation_text = generation_response.content[-1]
            else:
                generation_text = generation_response.content
            #print(f"Generation text: {generation_text}")
            cleaned_data = helper_functions.json_helpers.parse_json(generation_text, mode="ocr")
            latex_data= self.latex_helper(cleaned_data)
            cln_output = helper_functions.helpers.check_options(latex_data)
            passed_list = self.map_questions(cln_output, question_list)
            passed_items = await self.key_function(passed_list)
            print(f"No of Total Text items queried: {No}, No of passed items: {len(passed_items)}")
            tokens = generation_response.usage_metadata
            return passed_items, tokens, len(passed_list)

        except Exception as e:
            print(f"Error occurred in question refined: {e}")
            return [], {}, 0
        
    def convert_div_to_frac_in_latex(self, text: str) -> str:
        def replace_div_in_math(match):
            content = match.group(1).strip()

            content = re.sub(
                r'([^\s{}]+)\s*/\s*([^\s{}]+)',
                lambda m: f"\\frac{{{m.group(1)}}}{{{m.group(2)}}}",
                content
            )

            return f"${content}$"
        modified_text = re.sub(r'\$(.+?)\$', replace_div_in_math, text)
        return modified_text
      
    def latex_helper(self, all_data):
        cleaned_data = []
        for item in all_data:
            try:
                # Apply LaTeX cleaning only where needed
                item['question'] = self.convert_div_to_frac_in_latex(item.get('question', ''))
                item['correct_answer'] = self.convert_div_to_frac_in_latex(item.get('correct_answer', ''))
                item['explanation'] = self.convert_div_to_frac_in_latex(item.get('explanation', ''))

                # Convert each option individually
                item['options'] = [
                    self.convert_div_to_frac_in_latex(opt) for opt in item.get('options', [])
                ]

            except Exception as e:
                print(f"Error processing item {item.get('q_id', 'unknown')}: {e}")
                # Even if there's an error, include the original item
            finally:
                cleaned_data.append(item)

        return cleaned_data
        
    def input_msg(self, message: str = None, urls: list[str] = None):
        """Format a multimodal input message with optional text and one or more image URLs"""
        try:
            if message and urls:
                content = [{"type": "text", "text": message}]
                for url in urls:
                    content.append({"type": "image_url", "image_url": {"url": url}})
                messages = [HumanMessage(content=content)]
            elif message:
                messages = [HumanMessage(content=message)]
            elif urls:
                content = [{"type": "text", "text": "Look at the images below:"}]
                for url in urls:
                    content.append({"type": "image_url", "image_url": {"url": url}})
                messages = [HumanMessage(content=content)]
            else:
                print("Format Error: Both message and image URLs are missing.")
                return None, None
            return messages, message
        except Exception as e:
            print(f"Error in input_msg formatting: {e}")
            return None, None
        
    async def image_model_generate(self, question_list):
        try:
            No= len(question_list)
            self.llm = self.get_llm_by_model(model_id=2)
            question_text = str(question_list)
            number = question_list[0]["question_no"]
            mes_result = f"This image belongs to question_no: {number}"
            image_fields = ["q_image", "option_1_image", "option_2_image", "option_3_image", "option_4_image"]
            image_urls_list = [question_list[0][f] for f in image_fields if f in question_list[0]]
            if not image_urls_list:
                raise ValueError("No image URLs found in question data.")
            image_urls = [f"https://neetguide.s3.ap-south-1.amazonaws.com/ocr/question_images/{img}" for img in image_urls_list]
            messages, _ = self.input_msg(mes_result, image_urls)
            prompt = ChatPromptTemplate.from_messages([("system", prompts.question_refine_prompt),MessagesPlaceholder(variable_name="messages")])
            formatted_prompt = prompt.invoke({"messages": messages, "question_list": question_text, "topic_name_list": classes.topic_name_list})
            generation_response = await self.llm.ainvoke(formatted_prompt)
            generation_text = generation_response.content
            cleaned_data = helper_functions.json_helpers.parse_json(generation_text, mode="ocr")
            latex_data= self.latex_helper(cleaned_data)
            cln_output = helper_functions.helpers.check_options(latex_data)
            passed_list = self.map_questions(cln_output, question_list)
            passed_items = await self.key_function(passed_list)
            print(f"No of Total Image items queried: {No}, No of passed items: {len(passed_items)}")
            tokens = generation_response.usage_metadata
            return passed_items, tokens, len(passed_list)
        
        except Exception as e:
            print(f"Error occurred in image_model_generate: {e}")
            import traceback
            traceback.print_exc()
            return [], {}, 0

    async def topic_check(self, question, old_topic, topic_name_list):
        try:
            start_time = time.time()
            self.llm = self.get_llm_by_model(model_id=1)
            generation_response = await self.llm.ainvoke(prompts.topic_check_template.format(question= question, old_topic=old_topic, topic_name_list=topic_name_list))    
            print(f"Time taken for generation: {time.time() - start_time}")
            #print(generation_response.usage_metadata)
            if isinstance(generation_response.content, list):
                print(f"it is in list with len {len(generation_response.content)}")
                generation_text = generation_response.content[-1]
            else:
                generation_text = generation_response.content
            cleaned_data = helper_functions.json_helpers.parse_json(generation_text)
            topic_name= cleaned_data["topic_name"]
            topic_id, subject_id, chapter_id = await db_connect.fetch_topic_details(topic_name, question, topic_list= classes.topic_name_list, retry_id=1)
            return topic_id, subject_id, chapter_id
        except:
            print("Error in topic_check")
            return None, None, None
   
    async def key_function(self, passed_qc):
        topic_cache = {}
        try:
            passed_items = []
            for entry in passed_qc:
                try:
                    topic_name = entry['topic_name']
                    if topic_name in topic_cache:
                        topic_id, subject_id, chapter_id = topic_cache[topic_name]
                    else:
                        topic_id, subject_id, chapter_id = await db_connect.fetch_topic_details(topic_name, entry['question'], topic_list= classes.topic_name_list, retry_id=0)
                        if topic_id is None:
                            print(f"Skipping question due to unresolved topic '{topic_name}'")
                            continue
                        topic_cache[topic_name] = (topic_id, subject_id, chapter_id)
                        
                    question = {'q_id': entry['question_no'],
                                'question': entry['question'],
                                'q_image': entry.get('q_image', None),
                                'explanation': entry['explanation'],
                                'correct_answer': entry['correct_answer'],
                                'options': entry['options'],
                                'subject_name': entry['subject_name'],
                                'topic_name': entry['topic_name'],
                                'question_type': classes.question_types[entry["question_type"]],
                                'estimated_time': entry['estimated_time'],
                                'concepts': entry['concepts'],
                                'QC': 'pass',
                                'correct_option': entry['correct_option'],
                                't_id': topic_id,
                                's_id': subject_id,
                                'c_id': chapter_id,
                                'difficulty': classes.difficulty_level[entry['difficulty'].lower()],
                                'cognitive_level': classes.cognitive_levels[entry['cognitive_level'].lower()],
                                'stream': 1,
                                'model': classes.model_dict[1],
                                'option_1_image': entry.get("option_1_image", None),
                                'option_2_image': entry.get("option_2_image", None),
                                'option_3_image': entry.get("option_3_image", None),
                                'option_4_image': entry.get("option_4_image", None)}
                    passed_items.append(question)
                except Exception as e:
                    print(f"Error in (key_function) preparing question: {entry}. Error: {e}")
                    continue

            return passed_items
        except Exception as e:
            print(f"An error occurred in Key Function: {e}")
            raise 

    async def process_batch(self, batch):
        passed_items, tokens, no_of_ques = await self.question_refined(question_list=batch)
        return passed_items, tokens, no_of_ques

    async def image_process_batch(self, batch):
        passed_items, tokens, no_of_ques = await self.image_model_generate(question_list=batch)
        return passed_items, tokens, no_of_ques
    # Function to split into batches
    def split_into_batches(self, questions, batch_size=10):
        return [questions[i:i + batch_size] for i in range(0, len(questions), batch_size)]

    # Main async function to process all batches in parallel
    async def process_all_batches(self, questions, batch_size=10, question_type="text"):
        try:
            batches = self.split_into_batches(questions, batch_size)
            if question_type == "image":
                tasks = [self.image_process_batch(batch) for batch in batches]
            else:
                tasks = [self.process_batch(batch) for batch in batches]
            results = await asyncio.gather(*tasks)

            # Unpack results: combine from each batch
            all_passed_items = []
            total_tokens = {"input_tokens": 0,"output_tokens": 0,"total_tokens": 0}
            total_ques = 0

            for passed_items, tokens, no_of_ques in results:
                all_passed_items.extend(passed_items)
                if tokens:
                    total_tokens["input_tokens"] += tokens.get("input_tokens", 0)
                    total_tokens["output_tokens"] += tokens.get("output_tokens", 0)
                    total_tokens["total_tokens"] += tokens.get("total_tokens", 0)
                total_ques += no_of_ques
            return all_passed_items, total_tokens, total_ques
        except Exception as e:
            print(f"An error occurred while processing batches: {e}")
            return [], {}, 0
        
    def map_questions(self, model_outputs, original_questions):
        """Maps model outputs to the original questions based on question_no."""
        try:
            merged_questions = []

            for model_output in model_outputs:
                match = next((q for q in original_questions if q["question_no"] == model_output["q_id"]), None)
                if match:
                    merged_question = {
                        "question_no": match["question_no"],
                        "question": model_output.get("question"),
                        "q_image": match.get("q_image", None),
                        "options": model_output.get("options"),
                        "correct_answer": model_output.get("correct_answer"),
                        "explanation": model_output.get("explanation"),
                        "subject_name": model_output.get("subject_name"),
                        "topic_name": model_output.get("topic_name"),
                        "cognitive_level": model_output.get("cognitive_level"),
                        "difficulty": model_output.get("difficulty"),
                        "question_type": model_output.get("question_type"),
                        "estimated_time": model_output.get("estimated_time"),
                        "concepts": model_output.get("concepts"),
                        "correct_option": model_output.get("correct_option"),
                        "option_1_image": match.get("option_1_image", None),
                        "option_2_image": match.get("option_2_image", None),
                        "option_3_image": match.get("option_3_image", None),
                        "option_4_image": match.get("option_4_image", None),
                    }
                    merged_questions.append(merged_question)
            return merged_questions
        except Exception as e:
            print(f"Error mapping questions: {e}")
            return []
    
    async def assigner_function(self, request: classes.RefineMCQs):
        """ Main function to process questions in batches and return refined questions. Handles both image and text questions, runs in parallel, and supports empty inputs."""
        try:
            all_image_questions, all_text_questions = await ocr.ocr.ocr_process(request.file_path, request.uuid)
            #all_image_questions, all_text_questions = [], question_dummy_list
            print(f"Total image questions: {len(all_image_questions)}, Total text questions: {len(all_text_questions)}")
            #print(all_text_questions)
            tasks = []
            if all_text_questions:
                tasks.append(self.process_all_batches(all_text_questions, self.max_questions_per_call, question_type="text"))
            else:
                tasks.append(asyncio.sleep(0, result=([], {}, 0)))

            if all_image_questions:
                tasks.append(self.process_all_batches(all_image_questions, 1, question_type="image"))
            else:
                tasks.append(asyncio.sleep(0, result=([], {}, 0)))
            (text_items, text_tokens, text_total), (image_items, image_tokens, image_total) = await asyncio.gather(*tasks)
            all_passed_items = text_items + image_items
            total_tokens = {**text_tokens, **image_tokens}
            total_ques = text_total + image_total
            all_passed_items.sort(key=lambda x: int(x.get("q_id", 0)))
            await db_connect.add_mcq_data(request, all_passed_items, classes.RefineDataStore)

            return all_passed_items, total_tokens, total_ques

        except Exception as e:
            print(f"An error occurred in assigner_function: {e}")
            import traceback
            traceback.print_exc()
            return [], {}, 0

refine_function = refine_questions()

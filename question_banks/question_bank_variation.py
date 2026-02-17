from langchain_google_genai import ChatGoogleGenerativeAI
from question_banks.question_bank_helpers import format_json,parse_json,calculate_total_tokens
import json,time,asyncio,os,re
import concurrent.futures
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from question_banks.question_explanation import question_explanation_generator
import constants
from question_banks import prompts_variational
from question_banks.db2 import add_varied_mcq
load_dotenv()

os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"]=os.getenv('OpenAI_API_KEY')
os.environ["GOOGLE_API_KEY"]=os.getenv('GOOGLE_API_KEY')

async def question_bank_generator(selected_subject:str,selected_input:str,difficulty:str,No:int,mcq:str):
    try:
        generation_template=prompts_variational.normal_generation_template
        qc_template=prompts_variational.normal_qc_template
        generation_llm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview")
        qc_llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview")
        print(generation_llm)
        #A block of mass 2 kg is placed on a rough horizontal surface with coefficient of static friction μs = 0.5 and coefficient of kinetic friction μk = 0.4. If a horizontal force F is applied to the block, which gradually increases from 0 N, at what value of F will the block experience maximum static friction force?  a.0 N  b. 9.8 N c. 19.6 N  d.4.9 N   correct answer: 9.8 N"
        generation_response=await generation_llm.ainvoke(generation_template.format(No=No,mcq=mcq))
        agent_reply=generation_response.content
        QC_response=await qc_llm.ainvoke(qc_template.format(mcq=agent_reply))
        QC_agent_reply=QC_response.content
        output = QC_agent_reply[constants.json_slice]
        tokens=calculate_total_tokens(generation_response.usage_metadata, QC_response.usage_metadata)
        print(generation_response.usage_metadata),
        print(QC_response.usage_metadata)
        tokens=calculate_total_tokens(generation_response.usage_metadata, QC_response.usage_metadata)
        print(tokens)
        output=format_json(output)
        #output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\\\\\', output)

        output = output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        #output = output.encode().decode('unicode_escape')  # Decodes escaped characters
        data = parse_json(output)
        data=await merge_explanations(data)
        # Extracting all entries where QC is 'pass'
        print(data)
        passed_items = data  
        failed_items = [item for item in data if item['QC'] == 'fail']
        print(f"No of Total items queried: {No},No of passed items: {len(passed_items)}, No of failed items: {len(failed_items)},Failed items: {failed_items}")
        # Printing the extracted item
        return passed_items,tokens,len(passed_items)
    except Exception as e:
        print(f"Error occurred: {e}")
        print(f"Output: {output}")

    


async def bulk_question_bank_generator_variation(selected_subject:str,selected_chapter:str,selected_input:str, difficulty:str, No:int,year:str,question_id:str,mcq:str):
    try:

        max_questions_per_call = 40
        calls = (No + max_questions_per_call - 1) // max_questions_per_call  # Calculate how many calls are needed

        # Initialize total_tokens as a dictionary, not an int
        total_tokens = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_tokens': 0
        }

        all_data = []
        total_questions = 0
        failed_tasks = []

        # Create tasks for each batch of questions
        tasks = [
            question_bank_generator(selected_subject,selected_input, difficulty, min(max_questions_per_call, No - i * max_questions_per_call),mcq)
            for i in range(calls)
        ]
        # Run all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and store failed tasks
        for i, result in enumerate(results):
            if isinstance(result, Exception):  # If task raised an exception
                print(f"Task {i + 1} failed.")
                failed_tasks.append(i)  # Store the index of the failed task
            elif result is None:
                print(f"Task {i + 1} returned None.")
                failed_tasks.append(i)
            else:
                passed_items, tokens, question_count = result
                all_data.extend(passed_items)
                if tokens:
                    total_tokens['total_input_tokens'] += tokens.get("input_tokens", 0)
                    total_tokens['total_output_tokens'] += tokens.get("output_tokens", 0)
                    total_tokens['total_tokens'] += tokens.get("total_tokens", 0)
                total_questions += question_count

        # # Retry failed tasks
        # if failed_tasks:
        #     print(f"Retrying {len(failed_tasks)} failed tasks...")
        #     retry_tasks = [
        #         question_bank_generator(selected_subject,selected_input, difficulty, min(max_questions_per_call, No - i * max_questions_per_call),mcq)
        #         for i in failed_tasks
        #     ]

        #     retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

        #     # Process retry results
        #     for result in retry_results:
        #         if isinstance(result, Exception):
        #             print(f"Retry failed.")
        #         elif result is None:
        #             print(f"Retry returned None.")
        #         else:
        #             passed_items, tokens, question_count = result
        #             all_data.extend(passed_items)
        #             if tokens:
        #                 total_tokens['total_input_tokens'] += tokens.get("input_tokens", 0)
        #                 total_tokens['total_output_tokens'] += tokens.get("output_tokens", 0)
        #                 total_tokens['total_tokens'] += tokens.get("total_tokens", 0)
        #             total_questions += question_count

        # # Check if the total number of questions received is less than requested
        # while total_questions < No:
        #     remaining_questions = No - total_questions
        #     print(f"Fetching {remaining_questions} more questions...")

        #     # Call the fetch_remaining_questions function to get the remaining questions
        #     more_data, more_tokens, more_questions = await fetch_remaining_questions(
        #        selected_subject,selected_input, difficulty, remaining_questions, all_data, total_tokens, total_questions, No,mcq  # Pass target total
        #     )
            
        #     # Add the new data to the total data
        #     all_data = more_data
        #     total_tokens['total_input_tokens'] += more_tokens.get("input_tokens", 0)
        #     total_tokens['total_output_tokens'] += more_tokens.get("output_tokens", 0)
        #     total_tokens['total_tokens'] = more_tokens.get("total_tokens", 0)
        #     total_questions = more_questions
        #print(all_data)
        add_varied_mcq(all_data,selected_subject,selected_chapter,selected_input, difficulty,year,question_id)
        return all_data, total_tokens

    except Exception as e:
        print(f"Error occurred: {e}")
        return [], 0, 0




    

async def fetch_remaining_questions(selected_subject,selected_input, difficulty, remaining, all_data, total_tokens, total_questions, target_total,mcq):
    try:
        print(f"Debug: Starting fetch_remaining_questions for chapter: {selected_input}, difficulty: {difficulty}, remaining: {remaining}")
        
        # Call the process_mcq_call function to get more questions
        additional_result = await question_bank_generator(selected_subject,selected_input, difficulty, remaining,mcq)
        # Log the received result to inspect the structure
        print(f"Debug: Type of additional_result: {type(additional_result)}")
        
        # Check if the result is valid and in the expected format (tuple)
        if isinstance(additional_result, tuple):
            print(f"Debug: additional_result is a tuple with length {len(additional_result)}")
            
            # Unpack the tuple
            if len(additional_result) == 3:
                additional_data, additional_tokens, additional_count = additional_result
                
                # Debug each unpacked value
                print(f"Debug: Type additional_data: {type(additional_data)}")
                print(f"Debug: additional_tokens: {additional_tokens}, Type: {type(additional_tokens)}")
                print(f"Debug: additional_count: {additional_count}, Type: {type(additional_count)}")
                
                # Check how many questions we can still add without exceeding the target
                questions_to_add = min(additional_count, target_total - total_questions)
                
                # Extend the all_data list with the exact number of questions needed
                if isinstance(additional_data, list):
                    all_data.extend(additional_data[:questions_to_add])  # Add only up to the required number
                    print(f"Debug: Extended all_data with additional_data. Total all_data length: {len(all_data)}")
                else:
                    print(f"Warning: additional_data is not a list. It is: {type(additional_data)}")
                
                # Update the total questions count
                total_questions += questions_to_add
                print(f"Debug: Updated total_questions: {total_questions}")
                
                # Update the total tokens if additional_tokens is valid
                if isinstance(additional_tokens, dict):
                    total_tokens['total_input_tokens'] += additional_tokens.get("input_tokens", 0)
                    total_tokens['total_output_tokens'] += additional_tokens.get("output_tokens", 0)
                    total_tokens['total_tokens'] += additional_tokens.get("total_tokens", 0)
                    print(f"Debug: Updated total_tokens: {total_tokens}")
                else:
                    print(f"Warning: additional_tokens is not a dictionary. It is: {type(additional_tokens)}")
                
                return all_data, total_tokens, total_questions
            else:
                print(f"Error: Tuple length is not 3, received length: {len(additional_result)}")
                return all_data, total_tokens, total_questions
        
        else:
            print(f"Error: Received invalid result format from process_mcq_call. Expected tuple, got {type(additional_result)}")
            return all_data, total_tokens, total_questions
        
    except Exception as e:
        print(f"Error occurred while fetching remaining questions: {e}")
        return all_data, total_tokens, total_questions
    


async def merge_explanations(data:list):
    try:
        #formatted_data = [{"question_id": idx + 1,"question": item['question'],"correct_answer": item['correct_answer']}for idx, item in enumerate(data)]
        formatted_data =[{"question_id": idx + 1,"question": item['question'],"correct_answer": f"{['A', 'B', 'C', 'D'][item['options'].index(item['correct_answer'])]}. {item['correct_answer']}","options": {label: option for label, option in zip(['A', 'B', 'C', 'D'], item['options'])}} for idx, item in enumerate(data)]
        data_ans=await question_explanation_generator(formatted_data)
        for idx, item in enumerate(data):
            try:
                # Check if `data_ans[idx]` is a dict and has an explanation
                if isinstance(data_ans[idx], dict):
                    explanation = data_ans[idx].get('explanation')
                    if explanation:  # Ensure explanation is not None or empty
                        item['explanation'] = explanation
                    else:
                        item['explanation'] = 'No explanation provided.'
                elif isinstance(data_ans[idx], list) and data_ans[idx]:  # Non-empty list
                
                    # Use the explanation from the first element if it's a dict
                    first_element = data_ans[idx][0]
                    if isinstance(first_element, dict) and 'explanation' in first_element:
                        item['explanation'] = first_element.get('explanation', 'No explanation provided.')
                    else:
                        item['explanation'] = 'No explanation provided.'
                else:
                    print("Invalid structure or empty")
                    item['explanation'] = 'No explanation provided.'

            except Exception as e:
                error_message = str(e)
                print(f"Error processing index {idx}: {error_message}")
                item['explanation'] = f"Error in explanation retrieval: {error_message}"
        return data
    except Exception as e:
        print(f"Error occurred: {e}")

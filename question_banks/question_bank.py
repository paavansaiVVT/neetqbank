from langchain_google_genai import ChatGoogleGenerativeAI
from question_banks.question_bank_helpers import format_json,parse_json,format_results,calculate_total_tokens,clean_json_data
import json,time,asyncio,os,re
import concurrent.futures
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
import constants
from question_banks import prompts
from question_banks.db import add_mcq_data
load_dotenv()

os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"]=os.getenv('OpenAI_API_KEY')
os.environ["GOOGLE_API_KEY"]=os.getenv('GOOGLE_API_KEY')


def extract_content(response_content):
    """Extract string content from LangChain response, handling both string and list formats."""
    if isinstance(response_content, str):
        return response_content
    elif isinstance(response_content, list):
        # LangChain 1.x may return list of content blocks
        text_parts = []
        for part in response_content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and 'text' in part:
                text_parts.append(part['text'])
            elif hasattr(part, 'text'):
                text_parts.append(part.text)
        return '\n'.join(text_parts)
    else:
        return str(response_content)


async def question_bank_generator(selected_subject,selected_input,difficulty,No):
    try:
        generation_template=prompts.normal_generation_template
        qc_template=prompts.normal_qc_template
        generation_llm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview")
        qc_llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview")
        print(generation_llm)
        generation_response=await generation_llm.ainvoke(generation_template.format(topic=selected_input, difficulty=difficulty,No=No))
        agent_reply=extract_content(generation_response.content)
        QC_response=await qc_llm.ainvoke(qc_template.format(mcq=agent_reply))
        QC_agent_reply=extract_content(QC_response.content)
        output = QC_agent_reply[constants.json_slice]
        tokens=calculate_total_tokens(generation_response.usage_metadata, QC_response.usage_metadata)
        print(tokens)
        output=format_json(output)
        #output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        data = parse_json(output)
        print(data)
        # Extracting all entries where QC is 'pass'
        passed_items = data  #[item for item in data if item['QC'] == 'pass']
        failed_items = [item for item in data if item['QC'] == 'fail']
        print(f"No of Total items queried: {No},No of passed items: {len(passed_items)}, No of failed items: {len(failed_items)},Failed items: {failed_items}")
        # Printing the extracted item
        return passed_items,tokens,len(passed_items)
    except Exception as e:
        print(f"Error occurred: {e}")
        print(f"Output: {output}")

    


async def bulk_question_bank_generator(selected_subject,selected_chapter,selected_input, difficulty, No):
    try:
        No = int(No)
        #difficulty = int(difficulty)
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
            question_bank_generator(selected_subject,selected_input, difficulty, min(max_questions_per_call, No - i * max_questions_per_call))
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

        # Retry failed tasks
        if failed_tasks:
            print(f"Retrying {len(failed_tasks)} failed tasks...")
            retry_tasks = [
                question_bank_generator(selected_subject,selected_input, difficulty, min(max_questions_per_call, No - i * max_questions_per_call))
                for i in failed_tasks
            ]

            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

            # Process retry results
            for result in retry_results:
                if isinstance(result, Exception):
                    print(f"Retry failed.")
                elif result is None:
                    print(f"Retry returned None.")
                else:
                    passed_items, tokens, question_count = result
                    all_data.extend(passed_items)
                    if tokens:
                        total_tokens['total_input_tokens'] += tokens.get("input_tokens", 0)
                        total_tokens['total_output_tokens'] += tokens.get("output_tokens", 0)
                        total_tokens['total_tokens'] += tokens.get("total_tokens", 0)
                    total_questions += question_count

        # Check if the total number of questions received is less than requested
        while total_questions < No:
            remaining_questions = No - total_questions
            print(f"Fetching {remaining_questions} more questions...")

            # Call the fetch_remaining_questions function to get the remaining questions
            more_data, more_tokens, more_questions = await fetch_remaining_questions(
               selected_subject,selected_input, difficulty, remaining_questions, all_data, total_tokens, total_questions, No  # Pass target total
            )
            
            # Add the new data to the total data
            all_data = more_data
            total_tokens['total_input_tokens'] += more_tokens.get("input_tokens", 0)
            total_tokens['total_output_tokens'] += more_tokens.get("output_tokens", 0)
            total_tokens['total_tokens'] = more_tokens.get("total_tokens", 0)
            total_questions = more_questions
        #print(all_data)
        add_mcq_data(all_data,selected_subject,selected_chapter,selected_input, difficulty)
        return all_data, total_tokens

    except Exception as e:
        print(f"Error occurred: {e}") 
        return all_data, total_tokens  # Return collected data even on error




    

async def fetch_remaining_questions(selected_subject,selected_input, difficulty, remaining, all_data, total_tokens, total_questions, target_total):
    try:
        print(f"Debug: Starting fetch_remaining_questions for chapter: {selected_input}, difficulty: {difficulty}, remaining: {remaining}")
        
        # Call the process_mcq_call function to get more questions
        additional_result = await question_bank_generator(selected_subject,selected_input, difficulty, remaining)
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
    


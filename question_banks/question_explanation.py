from langchain_google_genai import ChatGoogleGenerativeAI
from question_banks.question_bank_helpers import format_json,parse_json,format_results,calculate_total_tokens,clean_json_data
import json,time,asyncio,os,re
import concurrent.futures
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
import constants
from question_banks import prompts_variational
from question_banks.db2 import add_varied_mcq,update_answer_desc,update_tagging_data,update_qc,update_options_and_exp,update_tagging_topall
from question_banks.classes import QuestionBankRequest,options_parser,result_parser,explanation_parser,question_type_parser
from langchain_openai.chat_models.base import BaseChatOpenAI


load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"]=os.getenv('OpenAI_API_KEY')
os.environ["GOOGLE_API_KEY"]=os.getenv('GOOGLE_API_KEY')
os.environ["GROQ_API_KEY"]=os.getenv('Grok_API_KEY')

GEMINI_3_FLASH = "gemini-3-flash-preview"
GEMINI_3_PRO = "gemini-3-pro-preview"

async def question_explanation_generator(mcq,api_call=None):
    " generats only explanation for generated question"
    try:
        llm = ChatGoogleGenerativeAI(model=GEMINI_3_FLASH)
        #llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro")
        #llm = ChatTogether(together_api_key="e486570214210036f677982cd9b9602ce30ed7159a6dc212aad8162e250e24cb",model="deepseek-ai/DeepSeek-V3",)
        #llm = BaseChatOpenAI(model='deepseek-reasoner',openai_api_key="sk-51d7f9b1b2d341278cda94d0fa7b6450", openai_api_base='https://api.deepseek.com',max_tokens=6024)
        #llm = ChatOpenAI(model="gpt-4o",stream_usage=True) 
        #llm = ChatAnthropic(model="claude-3-5-sonnet-20240620",max_tokens=4096)
        #llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp",api_key=os.getenv('GOOGLE_API_KEY_2'))
        response=await llm.ainvoke(prompts_variational.explanation_prompt.format(mcqs=mcq))
        output=response.content
        tokens=response.usage_metadata
        print(tokens)
        # output = output[constants.json_slice]
        # output=format_json(output)
        output = output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        #data=explanation_parser.invoke(output)[0]
        try:
           data=explanation_parser.invoke(output)[0]
        except Exception as e:
           data=explanation_parser.invoke(output)
        print(len(data))
        if api_call is not None:
            asyncio.create_task(update_answer_desc(data))
        # Printing the extracted item
        return data
    except Exception as e:
        print(f"Error occurred in question_explanation_generator: {e}")
        print(f"Output: {output}")


async def question_tagger(request:QuestionBankRequest):
    "Taggs Already generated Questions From top wall question bank"
    try:
        llm = ChatGoogleGenerativeAI(model=GEMINI_3_FLASH)
        mcq=format_mcq(request,explanation="not_required")
        response=await llm.ainvoke(prompts_variational.tagging_prompt.format(mcqs=mcq))
        output=response.content
        output = output[constants.json_slice]
        tokens=response.usage_metadata
        output=format_json(output)
        output = output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        data = parse_json(output)
        update_tagging_data(request,data)
        # Printing the extracted item
        return data
    except Exception as e:
        print(f"Error occurred: {e}")
        print(f"Output: {output}")


async def question_tagger_topall(request:QuestionBankRequest):
    "Taggs Already generated Questions From top wall question bank for Adaptive agent"
    try:
        llm = ChatGoogleGenerativeAI(model=GEMINI_3_FLASH)
        mcq=format_mcq(request,explanation="not_required")
        response=await llm.ainvoke(prompts_variational.tagging_prompt_topall.format(mcqs=mcq))
        data=question_type_parser.invoke(response.content)
        tokens=response.usage_metadata
        asyncio.create_task(update_tagging_topall(request, data))
        # Printing the extracted item
        return data
    except Exception as e:
        print(f"Error occurred: {e}")
        print(f"Output: {data}")


async def questions_QC(request:QuestionBankRequest):
    "QC the Mcqs from DB"
    try:
       
        llm = ChatGoogleGenerativeAI(model=GEMINI_3_PRO,temperature=0.0)
        #llm = BaseChatOpenAI(model='deepseek-reasoner',openai_api_key="sk-51d7f9b1b2d341278cda94d0fa7b6450", openai_api_base='https://api.deepseek.com',max_tokens=1024)
        #llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",temperature=0.2)
        mcq=format_mcq(request,explanation="required")
        response=await llm.ainvoke(prompts_variational.evaluation_prompt.format(mcqs=mcq))
        output=response.content
        tokens=response.usage_metadata
        output = output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        data=result_parser.invoke(output)[0]
        # Trigger the update_qc function without waiting for its completion
        asyncio.create_task(update_qc(request, data))
        # Printing the extracted items
        return data
    except Exception as e:
        print(f"Error occurred: {e}")
        print(f"Output: {output}")

    
def format_mcq(request,explanation) -> str:
    try:
        "Formats MCQ for Proving in Prompt for question_tagger Agent"
        correct_option_map = {1: request.option_a,2: request.option_b,3: request.option_c,4: request.option_d}
        correct_option_text = correct_option_map.get(request.correct_opt, "Invalid option")
        if explanation=="not_required":
            mcq=f"""question: {request.question}\n ,Options  A. {request.option_a} B. {request.option_b} C. {request.option_c} D. {request.option_d},\n Correct Answer: {correct_option_text}) """
        elif explanation=="required":    
            mcq=f"""question: {request.question},\n Explanation: {request.explanation}\n ,Options  A. {request.option_a} B. {request.option_b} C. {request.option_c} D. {request.option_d} ,\n Correct Answer: {correct_option_text}) """
        else:
            print("Error in explanation formatting")
        return mcq
    except Exception as e:
        print(f"Error occurred in formating mcq: {e}")
    

async def questions_choices_regenerate(request:QuestionBankRequest):
    "Regenerate options for for question"
    try:
        llm = ChatGoogleGenerativeAI(model=GEMINI_3_PRO)
        #llm = ChatTogether(together_api_key="e486570214210036f677982cd9b9602ce30ed7159a6dc212aad8162e250e24cb",model="deepseek-ai/DeepSeek-V3",)
        #llm = BaseChatOpenAI(model='deepseek-reasoner',openai_api_key="sk-51d7f9b1b2d341278cda94d0fa7b6450", openai_api_base='https://api.deepseek.com',max_tokens=6024)
        response=await llm.ainvoke(prompts_variational.options_regenerate_prompt.format(question=request.question))
        tokens=response.usage_metadata
        output=response.content
        # output = output[constants.json_slice]
        # output=format_json(output)
        output = output.replace("\t", " ")
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', output)
        #data=options_parser.invoke(output)[0]
        try:
            data=options_parser.invoke(output)[0]
        except Exception as e:
            data=options_parser.invoke(output)
        mcq=format_mcq_choices(request.question, data["options"],data["correct_answer"])
        explanation=await question_explanation_generator(mcq)
        # Trigger the update_qc function without waiting for its completion
        asyncio.create_task(update_options_and_exp(request,data["options"],data["correct_answer"],explanation))
        # Printing the extracted items
        return data,explanation
    except Exception as e:
        print(f"Error occurred in questions_choices_regenerate: {e}")
        print(f"Output: {data}")


def format_mcq_choices(question, options, correct_answer):
    # Map options to A, B, C, D
    option_mapping = {f"option_{chr(97 + i)}": option for i, option in enumerate(options)}
    # Identify the correct option text
    correct_option_text = correct_answer
    # Generate the desired MCQ format
    mcq = f"""question: {question}\nOptions: A. {option_mapping['option_a']} B. {option_mapping['option_b']} C. {option_mapping['option_c']} D. {option_mapping['option_d']},\nCorrect Answer: {correct_option_text})"""
    return mcq



from langchain_google_genai import ChatGoogleGenerativeAI
from question_banks.question_bank_helpers import format_json,parse_json,format_results,calculate_total_tokens,clean_json_data
import asyncio,os, time
from dotenv import load_dotenv
import constants, json
from cs_qbanks import cs_prompts
from cs_qbanks import cs_db_connect, cs_classes
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

class question_refine:
    def __init__(self):
        self.model_name = "gemini-1.5-pro"
        self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        self.parser= JsonOutputParser()
        self.prompt = PromptTemplate.from_template(cs_prompts.question_impr_prompt)
        self.chain = self.prompt | self.llm 

    async def question_improvement_generator(self,request: cs_classes.ImprovedQuestionReq):
        try:
            question_details_dict = await cs_db_connect.question_det(request.question_id, request.user_query, self.model_name)
            question_details_json = json.dumps(question_details_dict)
            generation_response = await self.chain.ainvoke({"subject":question_details_dict.get("subject_name"), "question_details":question_details_json, "user_query":request.user_query})
            output=self.parser.invoke(generation_response.content)
            tokens=generation_response.usage_metadata
            await cs_db_connect.update_mcq_data(request, question_details_dict, output)
            print(f"Question improvement completed for ID: {request.question_id}")
            return output, tokens
        except Exception as e:
            print(f"Error occurred in question improvement: {e}")
            return None, None
        

question_refiner = question_refine()
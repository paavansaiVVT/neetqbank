from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from locf.data_extraction import prompts
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv
from locf.data_extraction.db import all_data_dump
from locf.data_extraction import helpers 
import os,requests,logging

logging.basicConfig(level=logging.DEBUG)

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')


class get_justification:
    def __init__(self):
        self.model_name= "gemini-2.0-flash-001"
        self.prompt =ChatPromptTemplate.from_template(prompts.justification_prompt)
        self.llm=ChatGoogleGenerativeAI(model=self.model_name) 
        self.parser = JsonOutputParser()
        self.chain = self.prompt | self.llm | self.parser
   
    def get_program_outcomes(self,program_id):    
        try:
            url = f"https://locf.vvtsolutions.in/api/program-outcomes/program/{program_id}"
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad status
            data = response.json()
            result = {}
            for item in data:
                code = item.get("code")
                description = item.get("description")
                if code and description:
                    result[code] = description

            return result
        except requests.RequestException as e:
            print(f"Error fetching program outcomes: {e}")
            return {}

        
    async def gen_justification(self,program_id,data):
        """Generate justifications for course outcomes."""
        try:
            co=[]
            for x in data["course_outcomes"] :
                entry={x["CO"]:x["description"]}
                co.append(entry)
            pos=self.get_program_outcomes(program_id)
            merged_mapping=self.merger(data)
            commons_items,core_items=helpers.saggreagate(merged_mapping)
            response=await self.chain.ainvoke({"mappings":core_items ,"pos":pos,"co":co})
            result=self.map_justification(response,core_items)
            return result,commons_items
        except Exception as e:
            print(f"Error in generating justification: {e}")
            return None
        
    def map_justification(self,response,maps):
        try:
            final_mapped_output = {}
            for co_entry in response:
                for co, po_justifications in co_entry.items():
                    final_mapped_output[co] = {}
                    for po, justification in po_justifications.items():
                        score = maps.get(co, {}).get(po, 0)
                        final_mapped_output[co][po] = {
                            "strength": score,
                            "justification": justification
                        }
            return final_mapped_output
        except Exception as e:
            print(f"Error in mapping justification: {e}")
            return None
        
    def merger(self,data):
        try:
                output = data.get("mapping_with_programme_specific_outcomes", {})
                if "Weightage" in output:
                    output["TOTAL"] = output.pop("Weightage")
                if "Weighted percentage of Course Contribution toPos" in output:
                    output["AVERAGE"] = output.pop("Weighted percentage of Course Contribution toPos")
                if "weighted_percentage_of_course_contribution_to_pos" in output:
                    output["AVERAGE"] = output.pop("weighted_percentage_of_course_contribution_to_pos")
                # Merge both mappings
                merged_mapping = {
                    **data.get("mapping_with_programme_outcomes", {}),
                    **output
                }
                return merged_mapping
        except Exception as e:
            print(f"Error in data merger: {e}")
        
        


get_justifications=get_justification()
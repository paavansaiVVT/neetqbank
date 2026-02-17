from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from locf.data_extraction import prompts
from langchain_community.document_loaders import PyPDFLoader
from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from dotenv import load_dotenv
from locf.data_extraction.db import all_data_dump
from locf.data_extraction import helpers
from locf.data_extraction.classes import file_request
from locf.data_extraction.justify import get_justifications
import os,logging, json, re
from uuid import uuid4

logging.basicConfig(level=logging.DEBUG)

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')


class LOCF:
    def __init__(self):
        self.model_name= "gemini-2.5-flash"
        #self.model_name = "gemini-2.0-flash-001"
        self.prompt =ChatPromptTemplate.from_template(prompts.prompt)
        self.llm=ChatGoogleGenerativeAI(model=self.model_name) 
        self.parser = JsonOutputParser()
        self.chain = self.prompt | self.llm | self.parser

    async def language_process(self, request:file_request):
        """Process the content for the language."""
        request.uuid = str(uuid4())
        pro_id = [6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
        prefix_id = ['ACA', 'BM', 'AF', 'GE', 'CA', 'HO', 'CSE', 'CHE', 'BAD', 'NFS', 'CAI', 'CDS', 'CS', 'PHY', 'AE']
        content = []
        for i in range(len(pro_id)):
            request.program_id = pro_id[i]
            request.file_name = "200L3K" + prefix_id[i]
            output = await self.extract_content(request)
            if output:
                content.append(output)
            else:
                raise Exception("Failed to extract content")

        return content

    def load_pdf(self, file_path):
        """Load PDF files from a directory."""
        try:
            loader = PyMuPDF4LLMLoader(file_path)
            docs = loader.load()
            docs_content = []
            for doc in docs:
                docs_content.append(doc.page_content)
            return docs_content
        except Exception as e:
            print(f"Error in loading PDF: {e}")
            return None
        
    async def extract_content(self,request:file_request):
        """Extract content from the loaded documents."""
        try:
            logging.info(f"Request getting started...")
            if request.markdown:
                content = request.markdown
            else:
                content = helpers.answer_sheet_extraction(request.file_path,prompts.extraction_prompt)
                # content =self.load_pdf(request.file_path)
            if content:
                logging.info(f"Content extracted successfully...")
                co_po_maps=None
                output =await self.chain.ainvoke({"content":content,"output_json":prompts.output_json})

                # json_string = json.dumps(output)
                # cleaned_data = re.sub(r'[\x00-\x1F\x7F]', '', json_string)
                # parsed_data = json.loads(cleaned_data)
                if output.get("mapping_with_programme_outcomes"):
                    output = helpers.cal_total_and_average(output)
                    co_po_maps=await get_justifications.gen_justification(request.program_id,output)
                result=await all_data_dump(request,output,co_po_maps)
                return output
            else:
                raise Exception("Failed to load PDF content")
        except Exception as e:
            raise Exception(f"Error extracting content : Invalid json output")

data_extract=LOCF()

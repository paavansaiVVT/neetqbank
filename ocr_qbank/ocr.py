# Import required libraries
from pathlib import Path
from mistralai import Mistral,DocumentURLChunk, ImageURLChunk, TextChunk
from mistralai.extra import response_format_from_pydantic_model
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from PyPDF2 import PdfReader
from typing import List
from dotenv import load_dotenv
from ocr_qbank import prompts
import os,base64,asyncio, boto3,requests
from io import BytesIO

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')
client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
print(f"Mistral client initialized successfully with key {client}.")
# Initialize boto3 client

s3 = boto3.client("s3",
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)
class QuestionItem(BaseModel):
    question_no: str = Field(..., description="The question no")
    question: str = Field(..., description="The question stem")
    options: List[str] = Field(..., description="List of options for the question")
class Document(BaseModel):
    questions: List[QuestionItem] = Field(..., description="List of questions with options")


class doc_ocr:
    def __init__(self):
        self.prompt = PromptTemplate.from_template(prompts.prompt)
        self.model_name = "gemini-2.0-flash-001"
        self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        self.parser = JsonOutputParser()
        self.chain = self.prompt | self.llm | self.parser
        self.s3_folder = "ocr/question_images"
        self.bucket_name="neetguide"

    def mistral_ocr(self,file_url,batch):
        """
        Function to perform OCR on a PDF document using Mistral's OCR service.
        It uploads the PDF file, processes it, and returns the OCR results.
        """
        try:
            # Process PDF with OCR, including embedded images
            pdf_response = client.ocr.process(
                document={
                "type": "document_url",
                "document_url": file_url},
                model="mistral-ocr-latest",
                pages=batch,
                document_annotation_format=response_format_from_pydantic_model(Document),
                include_image_base64=True)
            questions = self.parser.invoke(pdf_response.document_annotation)
            print(f"Batch {batch}")
            return pdf_response,questions
        except Exception as e:
            print(f"Error processing PDF with Mistral OCR: {str(e)}")
            return [], []
        
    def get_page_batches(self,pdf_url: str, batch_size=8):
        try:
            # Fetch the PDF content from the URL
            response = requests.get(pdf_url)
            response.raise_for_status()
            # Load PDF into PyPDF2 reader from memory
            pdf_file = BytesIO(response.content)
            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)
            page_numbers = list(range(total_pages))  # 0-indexed
            # Create batches of given size
            batches = [page_numbers[i:i + batch_size] for i in range(0, len(page_numbers), batch_size)]
            return batches
        except Exception as e:
            print(f"Error reading PDF from URL: {str(e)}")
            return None
    
    def save_images(self, pdf_response, session_id: str,batch_no):
        try:
            for page in pdf_response.pages:
                for img in page.images:
                    base64_str = img.image_base64.split(",")[1] if "," in img.image_base64 else img.image_base64
                    image_bytes = base64.b64decode(base64_str)
                    # Create a unique file name
                    file_name = f"{session_id}-{batch_no}-{img.id}"
                    s3_key = f"{self.s3_folder.rstrip('/')}/{file_name}"
                    try:
                        # Upload to S3
                        response=s3.put_object(Bucket=self.bucket_name, Key=s3_key, Body=image_bytes, ContentType="image/jpeg")
                    except Exception as e:
                        print(f"Error uploading {file_name} to S3: {str(e)}")
            print(f"Images uploaded successfully to S3 bucket '{self.bucket_name}' under folder '{self.s3_folder}'")
            return True
        except Exception as e:
            print(f"Error saving images: {str(e)}")
            return False
    
    async def image_tag(self,pdf_response):
        try:
            text=[]
            for x in pdf_response.pages:
                  if x.images:
                    text.append(x.markdown)
            if text:
                response=await self.chain.ainvoke({"question_text":text})
                print(f"Image tagging response from model: {response}")
                return response
            else:
                print("No image in PDF pages for image tagging.")
                return []
        except Exception as e:
            print(f"Error in image tagging: {str(e)}")
            return []
    
    def map_images(self, image_tags, questions,session_id, batch_no):
        image_questions = []
        text_questions = []
        try:
            for x in image_tags:
                for q in questions["questions"]:
                    if float(x["q_no"]) == float(q["question_no"]):
                        file_name = f"{session_id}-{batch_no}-{x['image_name']}"
                        if x['image_of'] == 'question':
                            q["q_image"] =file_name
                        elif x['image_of'] in ['(i)', 'i', 'a', '1', 1]:
                            q["option_1_image"] =file_name
                        elif x['image_of'] in ['(ii)', 'ii', 'b', '2', 2]:
                            q["option_2_image"] =file_name
                        elif x['image_of'] in ['(iii)', 'iii', 'c', '3', 3]:
                            q["option_3_image"] =file_name
                        elif x['image_of'] in ['(iv)', 'iv', 'd', '4', 4]:
                            q["option_4_image"] =file_name
            for q in questions["questions"]:
                if "q_image" in q or any(k in q for k in ["option_1_image", "option_2_image", "option_3_image", "option_4_image"]):
                    image_questions.append(q)
                else:
                    text_questions.append(q)
        except Exception as e:
            print(f"Error mapping images: {str(e)}")

        return image_questions, text_questions
    
    async def ocr_process(self, file_url: str, session_id: str):
        try:                                                                                                                                                                                                
            batches = self.get_page_batches(file_url)
            async def process_single_batch(batch,batch_no):
                pdf_response, questions = self.mistral_ocr(file_url, batch)  # Keep as sync if needed
                image_tags = await self.image_tag(pdf_response)
                print(image_tags)
                if image_tags:
                    self.save_images(pdf_response, session_id,batch_no)  # If this is sync, it's okay
                    image_qs, text_qs = self.map_images(image_tags, questions,session_id,batch_no)
                    return image_qs, text_qs
                else:
                    print(f"No image tags found for batch {batch_no}")
                    return [],questions["questions"]
            # build your tasks, passing both batch and its number
            tasks = [process_single_batch(batch, batch_no)for batch_no, batch in enumerate(batches, start=1)]
            print("Executing tasks")
            results = await asyncio.gather(*tasks)
            all_image_questions = []
            all_text_questions = []
            for image_qs, text_qs in results:
                all_image_questions.extend(image_qs)
                all_text_questions.extend(text_qs)
            return all_image_questions, all_text_questions
        except Exception as e:
            print(f"Error during OCR process: {str(e)}")
            return [], []
        

ocr =doc_ocr()
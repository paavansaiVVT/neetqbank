from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
import asyncio,os, time,re,constants,json,ast, requests
from dotenv import load_dotenv
from cs_qbanks import cs_prompts
from cs_qbanks import cs_db_connect, cs_classes
from langchain_core.output_parsers import JsonOutputParser
from collections import defaultdict
from cs_qbanks.helper_functions import helpers,json_helpers
from tutor_bots import chat
load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

class ComplaintAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash-001"):
        self.webhook_url = os.getenv("GOHIGHLEVEL_WEBHOOK_URL")
        self.model = ChatGoogleGenerativeAI(model=model_name, temperature=0.2)
        self.parser = JsonOutputParser()
        self.prompt = ChatPromptTemplate.from_messages([("system", cs_prompts.complaint_template),MessagesPlaceholder(variable_name="messages")])

    async def generate_complaint(self, request_data: cs_classes.ComplaintRequest):
        """Generate a complaint based on the request data."""
        messages, _ = chat.input_msg(request_data.description, request_data.ss_url)
        prompt = self.prompt.format_messages(messages=messages)
        response = await self.model.ainvoke(prompt)
        generation_text = response.content
        print(f"Generated complaint text: {generation_text}")
        response_data= self.parse_json(generation_text, request_data)
        self.ghl_store_complaint(response_data)
        return response_data

    def parse_json(self, request: cs_classes.ComplaintRequest, generation_text: str):
        """Parse the JSON output from the generation text."""
        cleaned_output = re.sub(r'[\x00-\x1F]+', '', generation_text)
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', cleaned_output)
        try:
            gen_output = self.parser.invoke(output)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            gen_output = json_helpers.parse_cleaner_def(output)
        gen_output["user_name"]= request.user_name
        gen_output["user_id"]= request.user_id
        gen_output["complaint_id"]= request.complaint_id
        gen_output["ss_url"]= request.ss_url
        gen_output["user_report"]= request.description
        gen_output["user_email"]= request.user_email
        gen_output["user_phone"]= request.user_phone
        return gen_output
    
    def ghl_store_complaint(self, response_data):
        """Store the complaint data in the GoHighLevel."""
        if isinstance(response_data, list):
            response_data = response_data[0]

        # Send to GoHighLevel
        try:
            res = requests.post(self.webhook_url, json=response_data)
            if res.status_code == 200:
                print("✅ Sent to GoHighLevel webhook successfully.")
            else:
                print(f"❌ Webhook failed: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Error sending to webhook: {e}")
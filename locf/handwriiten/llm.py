import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from locf.handwriiten import prompts

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

class NEETPaperEvaluator:
    def __init__(self, model_name: str = "gemini-2.0-flash-001"):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.1)
        self.parser = JsonOutputParser()
        self.prompt = prompts.prompt

    async def evaluate(self, question_paper_text: str, student_answers_text: str):
        """
        Evaluate the student answers against the question paper using Gemini 2.0 Flash.
        Returns a list of JSON objects as per the required schema.
        """
        # Compose the input for the LLM
        input_text = f"""
{self.prompt}
Question Paper:
{question_paper_text}

Student Answers:
{student_answers_text}
"""
        response = await self.llm.ainvoke(input_text)
        output = response.content
        # Try to parse the output as JSON
        try:
            result = self.parser.invoke(output)
        except Exception:
            # Fallback: try to extract JSON from text
            import re, json
            json_blocks = re.findall(r'\{[\s\S]*?\}', output)
            result = [json.loads(block) for block in json_blocks]
        return result

evaluator = NEETPaperEvaluator()

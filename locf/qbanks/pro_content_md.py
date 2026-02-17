from langchain_pymupdf4llm import PyMuPDF4LLMLoader
import re, os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage,AIMessage
from locf.qbanks import classes, db, prompts as pdf_prompts

load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')

class file_content:
    def __init__(self, model_name: str = "gemini-2.5-flash-preview-05-20"):
        self.model = ChatGoogleGenerativeAI(model=model_name, temperature=0.1)
        self.parser = JsonOutputParser()
        self.prompt = ChatPromptTemplate.from_messages([("system", pdf_prompts.pdf_data_extraction_prompt),MessagesPlaceholder(variable_name="messages")])

    async def generate_md_format(self, request_data: classes.pro_file_request):
        """Generate a complaint based on the request data."""
        try:
            print(f"Generating markdown format for program ID: {request_data.program_id}")
            load_content = self.load_file_content(request_data)
            print(f"Content loaded Successfully...")
            messages= [HumanMessage(content=load_content)]
            prompt = self.prompt.format_messages(messages=messages)
            response = await self.model.ainvoke(prompt)
            generation_text = response.content
            print(f"Generated markdown content: {generation_text}")
            sliced_content = self.slice_content(generation_text)
            pro_id = await db.get_program_content(program_id=request_data.program_id, content=generation_text, clean_content=sliced_content)
            return pro_id
        except Exception as e:
            print(f"Error generating markdown format: {e}")
            return None
             
    def load_file_content(self, request: classes.pro_file_request):
        """Load file content from a given file url."""
        loader = PyMuPDF4LLMLoader(request.file_url)
        docs = loader.load()
        paragraphs = "\n\n".join([doc.page_content for doc in docs])
        # Begin processing on `paragraphs`
        text = paragraphs

        # Remove headers
        text = re.sub(r'\|Part\|Course<br>Code\|Title of the Course\|Credits\|Hours\|Marks\|Marks\|Marks\|\s*\n?', '', text)
        
        # Clean up columns like Col1 to Col10
        text = re.sub(r'\bCol(?:10|[1-9])\b', '', text)

        # Clean up commas and spaces
        text = re.sub(r'\s*,\s*', ', ', text)
        text = re.sub(r',\s*,', ',', text)
        text = text.strip(', ')

        # Apply both line-based cleaners
        lines = text.splitlines()
        lines = [self.remove_extra_total(line) for line in lines]
        #lines = [self.clean_table_row(line) for line in lines]
        raw_text = "\n".join(lines)
        cleaned_text = self.clean_markdown(raw_text)
        
        return cleaned_text 
        
    def remove_extra_total(self, line):
        parts = line.split('TOTAL')
        if len(parts) > 1:
            return parts[0] + 'TOTAL' + ''.join(part.replace('TOTAL', '') for part in parts[1:])
        return line

    def clean_table_row(self, row):
        if row.startswith("|") and row.endswith("|"):
            # Skip separator rows (like |---|---|---|...)
            row_no_pipe = row.replace("|", "").strip()
            if all(char == "-" for char in row_no_pipe):
                return row

            cells = row.strip().split("|")[1:-1]
            seen = set()
            cleaned = []

            for cell in cells:
                cell_clean = cell.strip()
                # Keep duplicates if numeric
                if not cell_clean.isdigit() and cell_clean in seen:
                    cleaned.append("")  # remove duplicate text
                else:
                    cleaned.append(cell)
                    seen.add(cell_clean)

            # Fill empty cells with '----'
            filled = ["----" if not c.strip() else c for c in cleaned]
            return "|" + "|".join(filled) + "|"
        return row

    
    def clean_markdown(self, raw_markdown: str):
        lines = raw_markdown.splitlines()
        cleaned_lines = []
        seen_table_rows = set()

        for line in lines:
            original_line = line.strip()

            # Fix broken bold/italic like *** text** → ***text***
            original_line = re.sub(r'\*{3}\s*(.*?)\s*\*{2}', r'***\1***', original_line)

            # Fix normal bold formatting: ** text ** → **text**
            original_line = re.sub(r'\*\*\s*(.*?)\s*\*\*', r'**\1**', original_line)

            # Remove <br> tags and replace with space
            original_line = original_line.replace('<br>', ' ')

            # Remove standalone numbers (like 1, 2, 3) between sections
            if re.fullmatch(r'\d+', original_line):
                continue

            # Normalize excessive whitespace
            original_line = re.sub(r'\s{2,}', ' ', original_line)

            cleaned_lines.append(original_line)

        return '\n'.join(cleaned_lines)
    
    def slice_content(self, data):
        first_split = "first year"
        second_split = "**po1"
        third_split = "curriculum and syllabus for"

        data_lower = data.lower()

        try:
            result = {
                "intro": "",
                "po_section": "",
                "course_structure": "",
                "combined_output": "",
                "debug_log": []
            }

            if first_split in data_lower and second_split in data_lower:
                result["debug_log"].append("Both 'First Year' and '**PO1' found.")

                # Get actual index in original data
                idx_first = data_lower.index(first_split)
                idx_po1 = data_lower.index(second_split)

                # Capture full course structure and PO section
                result["course_structure"] = "# COURSE STRUCTURE\n\n### FIRST YEAR" + data[idx_first + len(first_split):]
                result["po_section"] = data[idx_po1:idx_first]

                if third_split in data_lower:
                    idx_curriculum = data_lower.index(third_split)
                    result["intro"] = data[idx_curriculum + len(third_split):idx_po1]
                    result["debug_log"].append("Intro extracted from 'Curriculum and Syllabus for' to '**PO1'.")
                else:
                    result["debug_log"].append("'Curriculum and Syllabus for' not found.")

            elif first_split in data_lower:
                result["debug_log"].append("Only 'First Year' found.")
                idx_first = data_lower.index(first_split)
                result["course_structure"] = "# COURSE STRUCTURE\n\n### FIRST YEAR" + data[idx_first + len(first_split):]

            elif second_split in data_lower:
                result["debug_log"].append("Only '**PO1' found.")
                idx_po1 = data_lower.index(second_split)
                result["po_section"] = data[idx_po1:]

            elif third_split in data_lower:
                result["debug_log"].append("Only 'Curriculum and Syllabus for' found.")
                idx_curriculum = data_lower.index(third_split)
                result["intro"] = data[idx_curriculum + len(third_split):]

            else:
                raise ValueError("None of the expected split keywords were found in the content.")

            # Final output: intro + course_structure
            result["combined_output"] = (
                result["intro"].strip() + "\n\n" + result["course_structure"].strip()
            ).strip()

            return result

        except Exception as e:
            raise ValueError("Error slicing markdown content: " + str(e))


program_content = file_content()
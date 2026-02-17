from langchain_core.output_parsers import JsonOutputParser
from cs_qbanks import cs_classes,cs_db_connect
import json,re, constants

class parse_json():
    """A class to parse JSON output from generation text, clean it, and return a list of valid JSON objects."""
    def __init__(self):
        self.parser = JsonOutputParser()
        self.fields = ['question', 'explanation']
    
    def parse_json(self, generation_text: str,mode="non-ocr"):
        """Parses the JSON output from the generation text, cleans it, and returns a list of valid JSON objects."""
        cleaned_output = re.sub(r'[\x00-\x1F]+', '', generation_text)
        output = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', cleaned_output)
        try:
            gen_output = self.parser.invoke(output)
        except:
            print("Error parsing JSON, trying to escape inner quotes")
            try:
                result = self.escape_json_inner_quotes(output)
                gen_output = self.parser.invoke(result)
            except:
                result = self.escape_json_inner_quotes(output)
                gen_output = self.parse_cleaner_def(result)
                print(len(gen_output), "objects found after cleanup")
        if mode=="non-ocr":        
            cleaned_data = [q for q in gen_output if all(key in q for key in cs_classes.required_items)]
            return cleaned_data
        else:
            return gen_output

    def parse_cleaner_def(self, raw_string:str):
        """Parses a raw string containing multiple JSON objects, cleans it one by one,and returns a list of valid JSON objects."""
        raw_strings=self.clean_markdown(raw_string)
        # Step 2: Split at each new JSON object using `"q_id"` as marker
        parts = re.split(r'(?=\{\s*"q_id"\s*:)', raw_strings)
        # Step 3: Parse each part individually
        json_obj=[]
        for i, part in enumerate(parts, 1):
            part = part.strip().rstrip(',')  # clean commas and spaces
            try:
                obj = json.loads(part)
                json_obj.append(obj)
            except json.JSONDecodeError as e:
                print(f"part:{part}, error {e}")
                continue
        return json_obj
    
    def clean_markdown(self, json_string:str):
        """Cleans the json markdown code blocks."""
        # Updated regex to match content between ```json and ending ```
        _json_markdown_re = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
        match = _json_markdown_re.search(json_string.strip())
        # Extract only the content inside the code block
        json_str = json_string if match is None else match.group(1)
        json_str=json_str.strip()
        return json_str[1:-1]
    
    def escape_json_inner_quotes(self, json_str:str, fields=None):
        """ Escapes unescaped double quotes within specified JSON fields to keep the JSON valid. """
        if fields is None:
            fields = self.fields
        s = json_str
        for field in fields:
            start_search = 0
            pattern = f'"{field}"'
            while True:
                idx = s.find(pattern, start_search)
                if idx == -1:
                    break
                colon = s.find(':', idx)
                if colon == -1:
                    break
                start_quote = s.find('"', colon + 1)
                if start_quote == -1:
                    break
                i = start_quote + 1
                end_quote = None
                while i < len(s):
                    if s[i] == '"':
                        j = i + 1
                        while j < len(s) and s[j].isspace():
                            j += 1
                        if j < len(s) and s[j] in {',', '}'}:
                            end_quote = i
                            break
                    i += 1
                if end_quote is None:
                    break
                content = s[start_quote+1:end_quote]
                escaped_content = content.replace('"', r'\"')
                s = s[:start_quote+1] + escaped_content + s[end_quote:]
                start_search = end_quote + 1 + len(escaped_content) - len(content)
        return s
    
class HelperFunctions():
    """A class containing helper functions for processing data."""
    def __init__(self):
        self.percentage_weightage=90

    def check_options(self, all_data):
        """Checks if the 'correct_answer' is present in 'options' and assigns the correct option number."""
        cleaned_data = []
        for item in all_data:
            try:
                correct_answer = item['correct_answer']
                if correct_answer in item['options']:
                    correct_opt = item['options'].index(correct_answer) + 1
                    item['correct_option'] = correct_opt
                    cleaned_data.append(item)
                else:
                    print(f"⚠️ Skipping: question ID: {item.get('q_id')} Correct answer '{correct_answer}' not found in options {item.get('options')}")
                    continue
            except Exception as e:
                print(f"❌ Error processing item: {e}")
        return cleaned_data
    
    def calculate_total_tokens(self, generation_tokens:dict, QC_tokens:dict):
        try:
            total_tokens = {
                'total_input_tokens': generation_tokens['input_tokens'] + QC_tokens['input_tokens'],
                'total_output_tokens': generation_tokens['output_tokens'] + QC_tokens['output_tokens'],
                'total_tokens': generation_tokens['total_tokens'] + QC_tokens['total_tokens']
            }
            return total_tokens
        except Exception as e:
            print(f"Error occurred at calculate_total_tokens: {e}")
            total_tokens = {'total_input_tokens': 0,'total_output_tokens': 0,'total_tokens': 0}
            return total_tokens
        
    def merge_data(self,gen_output, qc_output):
        # Normalize keys in qc_output as strings for flexible matching
        qc_dict = {str(item['q_id']): item for item in qc_output}

        merged_data = []
        for item in gen_output:
            q_id_str = str(item['q_id'])  # Ensure string key for comparison
            if q_id_str in qc_dict:
                item.update(qc_dict[q_id_str])  # Merge QC info
            merged_data.append(item)

        return merged_data   

    async def cal_percentage(self, uuid, passed:int, total:int):
        try:
            if total == 0:
                return 0
            percentage = (passed / total) * self.percentage_weightage
            #print(f"Percentage calculated: {percentage}%")
            await cs_db_connect.update_progress(uuid, percentage)
            return round(percentage, 2)
        except Exception as e:
            print(f"Error calculating percentage: {e}")
            return 0     

    async def key_function(self, request: cs_classes.QuestionRequest, passed_qc):
        topic_cache = {}
        try:
            passed_items = []
            for entry in passed_qc:
                try:
                    topic_name = entry['topic_name']
                    if topic_name in topic_cache:
                        topic_id, subject_id, chapter_id = topic_cache[topic_name]
                    else:
                        topic_id, subject_id, chapter_id = await cs_db_connect.fetch_topic_details(topic_name, entry['question'], request.topic_name, retry_id=0)
                        if topic_id is None:
                            cs_db_connect.logger.warning(f"Skipping question due to unresolved topic '{topic_name}'")
                            continue
                        topic_cache[topic_name] = (topic_id, subject_id, chapter_id)

                    question = {'q_id': entry['q_id'],
                                'question': entry['question'],
                                'explanation': entry['explanation'],
                                'correct_answer': entry['correct_answer'],
                                'options': entry['options'],
                                'topic_name': entry['topic_name'],
                                'question_type': constants.question_types[entry["question_type"]],
                                'estimated_time': entry['estimated_time'],
                                'concepts': entry['concepts'],
                                'QC': entry['QC'],
                                'correct_option': entry['correct_option'],
                                't_id': topic_id,
                                's_id': subject_id,
                                'c_id': chapter_id,
                                'difficulty': constants.difficulty_level[request.difficulty.lower()],
                                'cognitive_level': constants.cognitive_levels[request.cognitive_level.lower()],
                                'stream': constants.stream_dict[request.stream.lower()],
                                'model': constants.model_dict[request.model]}
                    passed_items.append(question)
                except Exception as e:
                    print(f"Error in (key_function) preparing question: {entry}. Error: {e}")
                    continue

            return passed_items
        except Exception as e:
            print(f"An error occurred in Key Function: {e}")
            raise  
        
# Initialize the helper functions and JSON parser
helpers=HelperFunctions()
json_helpers=parse_json()
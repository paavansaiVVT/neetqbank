import re,logging,json


def format_json(string):
  """ Cuts a text at end of string untill }   So that valid json format can be obtained"""
  print("formating_json")
  try:
    # Handle case where LangChain 1.x returns a list directly
    if isinstance(string, list):
        import json
        return json.dumps(string)
    
    # Handle case where string is not actually a string
    if not isinstance(string, str):
        import json
        return json.dumps(string)
    
    string = re.sub(r',\s*(\]|\})', r'\1', string)

    # Find the last occurrence of '}'
    last_brace_index = string.rfind('}')

    # Slice the string to keep everything up to and including the last '}'
    if last_brace_index != -1:
        string = string[:last_brace_index + 1]

    string=fix_missing_commas(string)


    string= string + "]"
    return string
  except Exception as e:
        logging.error(f"Error Formating json: {e}")
        return None

  
def fix_missing_commas(json_string):
    """ Add missing commas in between json elements"""
    try:
        # Add a comma before each new entry (line) that starts with a '{' and is not preceded by a comma or bracket
        fixed_string = re.sub(r'(?<=[^,\[{])\n\s*{', ',\n{', json_string)
        return fixed_string
    except Exception as e:
        logging.error(f"Error fix_missing_commas: {e}")
        return json_string
    
def format_results(results):
    try:
        # Combine all data and tokens from the parallel calls
        all_data = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens_sum = 0
        total_questions = 0

        for result in results:
            data, tokens, count = result
            print(tokens)
            if data:
                all_data.extend(data)  # Combine all data into all_data list

            total_questions += count
            # Instead of adding specific token values, collect all tokens
            # Accumulate tokens from each call
            # Check if 'tokens' is a list or a single dictionary
            total_input_tokens += tokens.get("input_tokens", 0)
            total_output_tokens += tokens.get("output_tokens", 0)
            total_tokens_sum += tokens.get("total_tokens", 0)

        
        # Create dictionary to send to API
        total_tokens = {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens_sum }
        return all_data,total_tokens,total_questions
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
    

# Add generation_tokens and QC_tokens
def calculate_total_tokens(generation_tokens, QC_tokens):
    try:
        total_tokens = {
            'input_tokens': generation_tokens['input_tokens'] + QC_tokens['input_tokens'],
            'output_tokens': generation_tokens['output_tokens'] + QC_tokens['output_tokens'],
            'total_tokens': generation_tokens['total_tokens'] + QC_tokens['total_tokens']
        }
        return total_tokens
    except Exception as e:
        print(f"Error occurred at calculate_total_tokens: {e}")
        total_tokens = {'total_input_tokens': 0,'total_output_tokens': 0,'total_tokens': 0}
        return total_tokens


def remove_extra_commas(json_string):
    """
    Removes extra commas (,,) from a JSON string.

    Args:
        json_string (str): The JSON string with potential extra commas.

    Returns:
        str: A corrected JSON string without extra commas.
    """
    try:
        # Replace occurrences of double commas with a single comma
        while ',,' in json_string:
            json_string = json_string.replace(',,', ',')
        
        return json_string

    except json.JSONDecodeError as e:
        return f"Invalid JSON format: {e}"


def clean_json_data(raw_data):
    """
    Cleans raw JSON-like string data to fix common errors such as trailing commas,
    multiple commas, and invalid escape sequences.
    """
    try:
        # Remove all instances of ",," with ","
        cleaned_data = re.sub(r",\s*,", ",", raw_data)

        # Remove any trailing commas before closing braces/brackets
        cleaned_data = re.sub(r",\s*([\}\]])", r"\\1", cleaned_data)

        cleaned_data = raw_data.replace('\\"', "**")
        return cleaned_data
    except Exception as e:
        logging.error(f"Error during cleaning JSON data: {e}")
        raise
    

def parse_json(output: str) -> dict:
    """
    Parses the JSON output and applies cleaning if necessary.
    Raises an error if parsing fails after cleaning.
    """
    try:
        # Attempt to parse JSON
        return json.loads(output, strict=False)
    except json.JSONDecodeError as e:
        logging.warning(f"Initial JSON parsing failed: {e}")
        logging.debug(f"Attempting to clean JSON output: {output}")

        # Attempt cleaning
        try:
            cleaned_output = clean_json_data(output)
            return json.loads(cleaned_output, strict=False)
        except json.JSONDecodeError as clean_err:
            logging.error(f"Failed to parse JSON after cleaning: {clean_err}")
            logging.debug(f"Final output after cleaning attempt: {cleaned_output}")
            raise ValueError("Failed to parse JSON even after cleaning") from clean_err



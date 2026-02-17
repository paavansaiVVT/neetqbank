import re,logging
from langchain_core.messages import AIMessage
 
# Cleane the Retrived context
def clean_context(data):
    try:
        # Replace unwanted characters
        cleaned_entry = data.replace("\n", " ").replace("\\n", " ").replace("\\", "").replace("\'", "").replace("*", "")

        # Remove non-ASCII characters
        cleaned_entry = re.sub(r'[^\x00-\x7F]+', '', cleaned_entry)
        
        # Append the cleaned entry to the list
        cleaned_data = []
        cleaned_data.append(cleaned_entry)
        
        return cleaned_data
    except Exception as e:
        logging.error(f"Error clean_context : {e}")
        return None
    

# Replace newline characters with an empty string
def clean_history(history):
    try:
        cleaned_history = re.sub(r'content=\\\"', 'content="', history)
        cleaned_history = re.sub(r'content=\\\'', 'content=\'', cleaned_history)
        cleaned_history = re.sub(r'\\\"', '"', history)
        return cleaned_history
    except Exception as e:
        logging.error(f"Error clean history: {e}")
        return None


def clean_solution(result):
    try:
        result = re.sub(r'(?<=\s|\()(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?=\s|\))', r'**\1**', result)
        if "**Options**" in result or "**Options:**" in result:
            # Enhanced regex pattern to handle all variations of solution markers
            result = re.sub(r'<<\s*solution\s*>>.*?<<\s*/?\s*solution\s*>>', '', result, flags=re.DOTALL)
            result = re.sub(r'<>.*?<>', '', result, flags=re.DOTALL)
            result = re.sub(r'\n\s*\n', '\n', result)  # Replace multiple newlines with a single newline
        else:
            # Only clean markers if no options are present
            result = re.sub(r'<<\s*solution\s*>>', '', result)
            result = re.sub(r'<<\s*/?\s*solution\s*>>', '', result)
            result = result.replace("<>", "")
            result = result.strip()  # Remove leading and trailing whitespace        
    except re.error as e:
        print(f"Regex error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return result

def image_format(respnse):
  # Regular expression to find image URLs
  pattern = r'Image:\s*(https?://\S+\.(?:png|jpg|jpeg|gif))'
  # Replace matched image links with <img> tag
  formatted_response = re.sub(pattern, r'![Image:](\1)', respnse)
  return formatted_response


def process_image_links_in_history(history):
    """
    Process the second-to-last message in history. If it contains any image URLs 
    from the qbank domain, split the content into text and image parts, converting 
    the URLs into the dictionary format while preserving the original text.
    """
    try:# Ensure there are at least two messages in history
        if len(history) >= 2:
            # Access the second-to-last message (index -2)
            msg = history[-1]
            # Check if the message has a 'content' attribute that is a string
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                # Pattern with capturing group to keep the URLs in the split result
                pattern = r'(https?://qbank\.csprep\.in/HTML/img/[^ \n]+)'
                parts = re.split(pattern, msg.content)
                new_content = []
                for part in parts:
                    if re.fullmatch(pattern, part):
                        # Convert URL part to dictionary format
                        new_content.append({"type": "image_url", "image_url": {"url": part}})
                    elif part.strip():
                        # Preserve non-empty text parts as text dictionaries
                        new_content.append({"type": "text", "text": part.strip()})
                # Update the message content without losing the original text
                msg.content = new_content
                # Put the updated message back into history
                history[-1] = msg
        return history
    except Exception as e:
        logging.error(f"Error processing image links in history: {e}")
        return history
    

def reorder_answer_description(data):
   """Reorder the Answer_Description to appear before Option_A in the dictionary"""
   try:   
      for item in data:
          question_data = item["Question"]
          # Extract Answer_Description if present
          answer_description = question_data.pop("Answer_Description", None)
          # Reconstruct the dictionary with Answer_Description placed before Option_A
          reordered_question = {}
          for key, value in question_data.items():
              if key == "Difficulty":  # Place Answer_Description after Difficulty
                  reordered_question[key] = value
                  if answer_description:
                      reordered_question["Answer_Description"] = answer_description
              else:
                  reordered_question[key] = value
          item["Question"] = reordered_question  # Update the dictionary
      return data
   except Exception as e:
        print(f"Error occurred in reorder_answer_description: {e}")
        return data
   
def clean_retrived_data(response):
  """Clean the extracted data by removing unwanted characters and non-ASCII characters"""
  try:
    cleaned_response = []
    extracted_data = [{"Question": doc.metadata,"category_path": doc.page_content}for doc, _ in response]
    for item in extracted_data:
        cleaned_question = {key: value for key, value in item["Question"].items() if value not in ["#", None] } # Remove `#` and `None` values
        cleaned_response.append({"Question": cleaned_question, "category_path": item["category_path"]})
        cleaned_response=reorder_answer_description(cleaned_response)
    return cleaned_response
  except Exception as e:
        print(f"Error occurred in clean_data: {e}")
        return response

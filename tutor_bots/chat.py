from langchain_core.messages import HumanMessage,AIMessage
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from tutor_bots.text_processing_functions import clean_history
import logging
import constants
from langchain_core.rate_limiters import InMemoryRateLimiter

# Initialize the rate limiter
rate_limiter = InMemoryRateLimiter(requests_per_second=constants.REQUESTS_PER_SECOND,check_every_n_seconds=constants.CHECK_EVERY_N_SECONDS,max_bucket_size=constants.MAX_BUCKET_SIZE)

  
def input_msg(message:str=None,url:str=None,history:list=None):
    """Format a Multimodel input message to the Gemini AI models according to inputs"""
    try:
        if message and history and url:
            print("message,history and URL")
            messages=message
            messages = HumanMessage(
            content=[{"type": "text",
                    "text": message,
                },  # You can optionally provide text parts
                {"type": "image_url", "image_url": {"url": url}},])
            history.append(messages)
            messages=history
        elif  message and url:
            print("message and URL")
            messages = HumanMessage(
            content=[{"type": "text",
                      "text": message,},{"type": "image_url", "image_url": {"url": url}},])
            messages=[messages]
        elif url and history:
            print("history and URL")
            messages = HumanMessage(
            content=[{"type": "image_url", "image_url": {"url": url}},])
            history.append(messages)
            messages=history
        elif message and history:
            print("history and message")
            message=HumanMessage(content=message)
            history.append(message)
            messages=history
        elif message:
            print("only message")
            messages= [HumanMessage(content=message)]
        elif url:
            print('only url')
            messages =[HumanMessage(
            content=[{"type": "text", "text": "look at user image"}, {"type": "image_url", "image_url": {"url": url}},])]
            message = [message.content for message in messages]        
        else:    
            messages=None
            print("Formart Error")
        return messages,message
    except Exception as e:
        logging.error(f"Error input message formatting: {e}")
        return None,None
    

def get_history(history:list,output:str,messages:HumanMessage):
    """Update the conversation history with the latest message"""
    try:
        if history is not None:
            history.append(AIMessage(content=output))
        elif history is None:
            history = messages+[AIMessage(content=output)]
        else:
            print(f"Error updating history: {e}")
        return(history)
    except Exception as e:
        logging.error(f"Error  updating history: {e}")
        return None
    

def generate_chat_title(messages):
    "Generate Chat title  using LDA"
    # Step 1: Vectorize the text data
    vectorizer = CountVectorizer(stop_words='english', max_features=1000)
    X = vectorizer.fit_transform(messages)

    # Step 2: Apply Latent Dirichlet Allocation for topic modeling
    lda = LatentDirichletAllocation(n_components=1, random_state=42)
    lda.fit(X)

    # Step 3: Extract the most representative words for each topic
    feature_names = vectorizer.get_feature_names_out()
    topics = []
    for topic_idx, topic in enumerate(lda.components_):
        top_words_idx = topic.argsort()[:-4:-1]
        topic_words = [feature_names[i] for i in top_words_idx]
        topics.append(topic_words)

    title = " | ".join([" ".join(topic) for topic in topics])

    return title


def history_logic(history):
    """clean excaped characters from history and convert to list"""
    if history is not None:
            try:
                history=clean_history(history)
                history = eval(history)
            except (SyntaxError, NameError):
                print("error in history_logic : history format invalid")
                history = None
    else:
        history = None
    return history



def extract_tokens(cb):
    "Extract token usage information from the callback handler."
    try:
        return {"input_tokens": cb.prompt_tokens,"output_tokens": cb.completion_tokens,"total_tokens": cb.total_tokens,"total_cost": cb.total_cost,}
    except Exception as e:
        print(f"Error extracting tokens: {e}")
        return None  
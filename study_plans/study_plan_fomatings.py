import logging,re
from study_plans.studyplan_data import topic_url_mapping
import pandas as pd
# Function to process results
class ResultProcessor:
    def __init__(self):
        """ Initializes the combined data structure and token count. """
        self.combined_data = {'study_plan': []}
        self.combined_tokens = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}

    def process_result(self, data, tokens):
        """ Processes each result by appending study plans and adding token counts. """
        if data and 'study_plan' in data:
            self.combined_data['study_plan'].extend(data['study_plan'])
        
        if tokens:
            self.combined_tokens['input_tokens'] += tokens.get('input_tokens', 0)
            self.combined_tokens['output_tokens'] += tokens.get('output_tokens', 0)
            self.combined_tokens['total_tokens'] += tokens.get('total_tokens', 0)

    def process_results(self, results):
        """ Loops through results and processes each. """
        try:
            for idx, (data, tokens) in enumerate(results):
                self.process_result(data, tokens)
            return self.combined_data, self.combined_tokens
        except Exception as e:
            logging.error(f"Error processing results: {e}")
            return None, None


def process_and_fix_data(raw_data):
    try:
        """
        Processes the given raw data, resolves duplicate 'day' entries by re-indexing them,
        and ensures that each day is unique and sequential.
        
        Parameters:
        raw_data (list): List of dictionaries representing the data with possible duplicate day entries.
        
        Returns:
        dict: A JSON-like dictionary with corrected data structure.
        """
        # Resolving duplicate day entries by re-indexing them
        unique_data = {}
        for entry in raw_data:
            day = entry['day']
            while day in unique_data:
                day += 1  # Increment the day until a unique value is found
            unique_data[day] = entry

        # Sorting the data by day to ensure it is in the correct order
        sorted_data = sorted(unique_data.items(), key=lambda x: x[0])
        final_data = [{"day": day, "chapterName": item['chapterName'], "topics": item['topics']} for day, item in sorted_data]

        # Returning the final data in JSON format
        return {"data": final_data}
    except Exception as e:
        logging.error(f"Error processing results: {e}")
        return None, None


def mapper(all_to_data):
  try:
    # Sample bot-generated data
    bot_generated_data =all_to_data["study_plan"]

    # Initialize an empty list to store the mapped data
    mapped_data = []
    # Iterate over the bot-generated data to map topics with their URLs
    for day in bot_generated_data:
        day_number = day['day']
        chapter_name = day['chapter']
        #chapter_name = day['chapters']["name"]
        topics_list = []
        for topic in day['topics']:
            # Find the matching topic URL from the data
            match = topic_url_mapping[(topic_url_mapping['Chapter Name'] == chapter_name) & (topic_url_mapping['Topic Name'].str.strip().str.lower() == topic.strip().lower())]            
            if not match.empty:
                topic_url = match['Topic Short URL'].values[0]
            else:
                topic_url = ""  # URL not found in the data
            
            topics_list.append({
                'topic': topic,
                'topicUrl': topic_url
            })
        mapped_data.append({
            'day': day_number,
            'chapterName': chapter_name,
            'topics': topics_list})
    return mapped_data
  except Exception as e:
        logging.error(f"Error mapping with respTopics URL: {e}")
        return None
  

def format_json(string):
  """ Cuts a text at end of string untill }   So that valid json format can be obtained"""
  print("formating_json")
  try:
    string = re.sub(r',\s*(\]|\})', r'\1', string)

    # Find the last occurrence of '}'
    last_brace_index = string.rfind('}')

    # Slice the string to keep everything up to and including the last '}'
    if last_brace_index != -1:
        string = string[:last_brace_index + 1]

    string=fix_missing_commas(string)
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


def adjust_days_based_on_level(base_days, level):
    """
    Adjust total study days based on the student's expertise level.
    """
    if level == "Beginner":
        return base_days + 3  # Increase days for beginners
    elif level == "Expert":
        return max(1, base_days - 3)  # Decrease days for experts but ensure at least 1 day
    else:  # Intermediate
        return base_days

def distribute_study_days_with_scores(subjects, total_days, level,subject_scores):
    """
    Distribute total study days among chapters based on their weightage, student's subject scores, and expertise level.

    Parameters:
    subjects (dict): Dictionary with subjects as keys, and a list of dictionaries with chapter names, weightages, and topics.
    total_days (int): Total number of study days.
    subject_scores (dict): Dictionary with subject names as keys and student scores as values.
    level (dict): Dictionary with subject names as keys and expertise level as values.

    Returns:
    dict: A dictionary with subjects as keys and chapter-wise allocated days as values.
    """
    try:
        subject_max_score = 100  # Assuming scores are normalized to 100
        normalized_scores = {subject: (score / subject_max_score) * 100 for subject, score in subject_scores.items()}

        study_plan = {}

        # Distribute study days among subjects
        for subject, chapter_list in subjects.items():
            if subject not in subject_scores:
                print(f"Warning: No scores found for subject {subject}")
                continue

            # Adjust the base total_days per subject based on expertise level
            subject_total_days = adjust_days_based_on_level(total_days, level.get(subject, "Intermediate"))

            # Calculate adjusted weightages based on the student's score
            score_factor = (100 - normalized_scores.get(subject, 50)) / 100  # Inverse of score percentage
            adjusted_weightages = []
            chapters = []

            for chapter_data in chapter_list:
                chapter = chapter_data['chapter']
                weightage = chapter_data['weightage']
                topics = chapter_data.get('topics', [])  # Handle topics if needed
                adjusted_weight = weightage * score_factor
                chapters.append((chapter, topics, weightage))  # Include weightage properly
                adjusted_weightages.append(adjusted_weight)

            if not adjusted_weightages:
                print(f"Error: No valid weightages found for subject {subject}, skipping")
                continue

            total_adjusted_weightage = sum(adjusted_weightages)

            # Allocate total days for the subject and distribute proportionally
            days_for_chapters_rounded = [max(1, round((w / total_adjusted_weightage) * subject_total_days)) for w in adjusted_weightages]

            # Recalculate total allocated days after rounding
            allocated_days_sum = sum(days_for_chapters_rounded)
            difference = subject_total_days - allocated_days_sum

            # Adjust for rounding mismatch
            for i in range(abs(difference)):
                if difference > 0:
                    days_for_chapters_rounded[i % len(days_for_chapters_rounded)] += 1
                elif difference < 0 and days_for_chapters_rounded[i % len(days_for_chapters_rounded)] > 1:
                    days_for_chapters_rounded[i % len(days_for_chapters_rounded)] -= 1

            # Sort chapters in descending order based on weightage
            sorted_chapters = sorted(zip(chapters, days_for_chapters_rounded), key=lambda x: x[0][2], reverse=True)

            # Store the results in the study plan
            study_plan[subject] = []
            for (chapter, topics, weightage), days in sorted_chapters:
                study_plan[subject].append({
                    'Chapter': chapter,
                    'Allocated Days': days,
                    'Weightage': weightage,
                    'Topics': topics
                })

        return study_plan

    except Exception as e:
        logging.error(f"Error Distributing Days based on score and level: {e}")
        return None
    


import logging

def adaptive_mapper(all_to_data, topic_url_mapping):
    try:
        # Extract study plan data
        bot_generated_data = all_to_data["study_plan"]
        mapped_data = []

        # Iterate over the study plan
        for day in bot_generated_data:
            day_number = day['day']
            chapters = day['chapter']  # Can be a list in the second format
            
            if isinstance(chapters, list):  # If chapter is a list (backlog + current topics)
                for chapter in chapters:
                    chapter_name = chapter["name"]
                    topics_list = []
                    
                    for topic in chapter["topics"]:
                        # Match topic with URL
                        match = topic_url_mapping[
                            (topic_url_mapping['Chapter Name'] == chapter_name) &
                            (topic_url_mapping['Topic Name'].str.strip().str.lower() == topic.strip().lower())
                        ]
                        
                        topic_url = match['Topic Short URL'].values[0] if not match.empty else ""

                        topics_list.append({
                            'topic': topic,
                            'topicUrl': topic_url
                        })

                    mapped_data.append({
                        'day': day_number,
                        'chapterName': chapter_name,
                        'topics': topics_list
                    })
                    
            else:  # If chapter is a single string (first format)
                chapter_name = chapters
                topics_list = []
                
                for topic in day['topics']:
                    match = topic_url_mapping[
                        (topic_url_mapping['Chapter Name'] == chapter_name) &
                        (topic_url_mapping['Topic Name'].str.strip().str.lower() == topic.strip().lower())
                    ]
                    
                    topic_url = match['Topic Short URL'].values[0] if not match.empty else ""

                    topics_list.append({
                        'topic': topic,
                        'topicUrl': topic_url
                    })
                
                mapped_data.append({
                    'day': day_number,
                    'chapterName': chapter_name,
                    'topics': topics_list
                })

        return mapped_data

    except Exception as e:
        logging.error(f"Error mapping with respTopics URL: {e}")
        return None

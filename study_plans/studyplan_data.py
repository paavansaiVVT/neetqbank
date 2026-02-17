import pandas as pd

# Replace 'path_to_your_file.xlsx' with the actual path to your Excel file
#file_path = r"C:\Users\Dell\Downloads\NEET All Subjects, Chpaters and Topics.xlsx"
file_path = 'https://neetguide.s3.ap-south-1.amazonaws.com/bot_prompts/study_plan_data/NEET+All+Subjects%2C+Chpaters+and+Topics.xlsx'

data = pd.read_excel(file_path)

# Cleaning the column names to remove any leading or trailing spaces
data.columns = data.columns.str.strip()
unique_chapters = data["Chapter Name"].unique()

#Extract Topics ulrs data for mapping
topic_url_mapping = data[['Chapter Name', 'Topic Name', 'Topic Short URL']]

# # Extracting unique topics for each subject from the cleaned data and removing duplicate topic names
# biology_topics_unique = data[data['Subject Name'] == "Biology"][['Chapter Name', 'Topic Name']].drop_duplicates(subset=['Topic Name'])
# chemistry_topics_unique = data[data['Subject Name'] == "Chemistry"][['Chapter Name', 'Topic Name']].drop_duplicates(subset=['Topic Name'])
# physics_topics_unique = data[data['Subject Name'] == "Physics"][['Chapter Name', 'Topic Name']].drop_duplicates(subset=['Topic Name'])

# # Convert these unique topics DataFrames to JSON format
# biology_topics_unique_json = biology_topics_unique.to_json(orient='records', indent=4)
# chemistry_topics_unique_json = chemistry_topics_unique.to_json(orient='records', indent=4)
# physics_topics_unique_json = physics_topics_unique.to_json(orient='records', indent=4)
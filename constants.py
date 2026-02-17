# API Version
RELEASE_DATE="15-04-2025"
RELEASE_VERSION="V-01.1"


# InMemoryRateLimiter for gemini-2.0-flash-001
REQUESTS_PER_SECOND = 23
CHECK_EVERY_N_SECONDS =25
MAX_BUCKET_SIZE = 100

# GoogleSerperAPIWrapper parameters
K=3   # Number of search results to fetch
GL="IN"  # Country code for Google search results

# Redis cache parameters
TTL=3600  # Time to live for cache in seconds
# Json Cutter
json_slice = slice(7, -3)


# Database forgien key constants
difficulty_level={"easy":1,
                  "medium":2,
                  "hard":3,
                  "veryhard":4}

cognitive_levels = {
    "remembering": 1,    
    "understanding": 2,
    "applying": 3,
    "application":3,
    "analyzing": 4,
    "evaluating": 5,
    "creating": 6       
}     
  
question_types = {
    "direct_concept_based": 1,
    "direct": 1,
    "assertion_reason": 2,
    "numerical_problem": 3,
    "diagram_Based_Question": 4,
    "multiple_correct_answer": 5,
    "matching_type": 6,
    "comprehension_type": 7,
    "case_study_based": 8,
    "statement_based": 9,
    "True_false type": 10,
    "single_correct_answer":11
}

status={
    "pass":0,
    "fail":1
}

# counseling rounds constants
rounds_dict = {
    "None": 0,
    "Round 1": 1,
    "Round 2": 2,
    "Round 3": 3,
    "Mop_Up": 4,
    "Stray": 5,
    "Stray Round 1": 6,
    "Stray Round 2": 7,
    "Special Stray": 8,
    "Mop_Up 2": 9,
    "Stray Round 3": 10,
    "Round 4": 11,
    "Round 5": 12}


model_dict={1:"gemini-3-flash-preview",
2:"gemini-3-flash-preview",
3:"gemini-3-flash-preview",
4:"gemini-3-pro-preview",
5:"o4-mini"}

stream_dict={"neet":1, 
             "cbse":2, 
             "jee":3}

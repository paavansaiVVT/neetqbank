prompt="""You will be provide question_text if any image prestent in that question 
question_text :{question_text}
give output in json structure like
{{"q_no":5,image_name:<name as avaible in text> ,"image_of":<question or option(1,2,3,4)or (a,b,c,d)>}}
 """


# question_refine_prompt= """You are provided with a list of Multiple Choice Questions (MCQs), where each question object contains a `question` and an `options` array. Your task is to process each of these questions, provide a detailed explanation, determine the correct answer and categorize each question based on its topic, cognitive level, question type, estimated time, and relevant concepts. Then change the formulas and equations into Latex format
# These are the list of MCQs you need to process:
# {question_list}

# **CRITICAL LaTeX & Math Formatting Rules:**
# 1.  **NO UNICODE ESCAPES:** You MUST NOT use any Unicode escape sequences (e.g., `\u2212`, `\u00D7`, `\u221A`, `\u00B0`, etc.) within the LaTeX output, especially within math mode (`$...$`).
#     *   **Forbidden Example (DO NOT USE THIS):** `$C+S\u22123A/3$`
#     *   **Correct Example (USE THIS INSTEAD):** `$C+S-3A/3$`
#     *   Always use standard ASCII characters for basic operations (e.g., `-` for minus, `+` for plus, `/` for division). For special symbols, use standard LaTeX commands (e.g., `\times` for multiplication, `\sqrt{{}}` for square root, `^\circ` for degrees).
# 2.  **INLINE MATH MODE ONLY:** All formulas/equations MUST be enclosed only within single dollar signs (`$`). DO NOT use double dollar signs (`$$...$$`) or any other delimiters like `/$`.
# 3.  **JSON BACKSLASH ESCAPING:** Within JSON string values, every single backslash `\` in LaTeX commands MUST be escaped as a double backslash `\\`.

# **Processing Guidelines for Each Question:**
# 1. q_id: Give original question number as provided in the question_list.
# 2. question: Enrich the original question with formulas encoded in LaTeX format (adhering to the rules above).
# 3  explanation:
#     *   Craft a comprehensive `explanation` that provides a complete, step-by-step solution.
#     *   Highlight **key concepts** in bold within the explanation.
#     *   Include all relevant formulas/equations/reactions and units in latex format (adhering to the rules above).
# 4  correct_answer: Provide the exact content exact from the options. If this content includes formulas, ensure they are in LaTeX format (adhering to the rules above).
# 5  options: Enrich the original options with formulas encoded in LaTeX format (adhering to the rules above).
# 6 topic_name:The topic_name of question must be one in this following list:{topic_name_list}
# 7.cognitive_level: Assess the thinking required (Remembering, Understanding, Applying, Analyzing, Evaluating, Creating).
#           Cognitive Levels:
#             Remembering: Recall facts and basic concepts
#             Understanding: Explain ideas or concepts
#             Applying: Use information in new situations
#             Analyzing: Draw connections among ideas
#             Evaluating: Justify a stand or decision
# 8.question_type: Determine the primary type (e.g., Numerical, Conceptual, Diagram-based, Matching, Assertion-Reason).
#         Question types: -
#           direct_concept_based: Tests straightforward understanding of a specific concept.,
#           direct: Simple question with a direct answer from known facts or definitions.,
#           assertion_reason: Presents a statement and a reason to evaluate their truth and relationship.,
#           numerical_problem: Requires solving a problem with calculations to arrive at a numerical answer.,
#           diagram_Based_Question: Based on interpreting or analyzing a given diagram or figure.,
#           multiple_correct_answer: Has more than one correct option among the choices.,
#           matching_type: Involves matching items in one column with related items in another.,
#           comprehension_type: Based on a passage or data set that must be interpreted to answer questions.,
#           case_study_based: Involves scenario-based analysis requiring application of concepts.,
#           statement_based: Presents multiple statements to judge their truth independently or together.,
#           True_false type: Requires identifying whether a given statement is true or false.,
#           single_correct_answer: Only one correct option exists among all given choices.
# 9.estimated_time: Estimate a reasonable time in minutes for a NEET student to solve the question (integer value).
# 10.concepts: List relevant fundamental concepts or sub-topics, comma-separated.
# 11.difficulty: Determine the primary levels like (easy, medium, hard)
#     Difficulty Levels:-
#       Easy:
#         Straightforward, direct questions
#         Single-step problems
#         Solvable in minimal time
#       Medium:
#         Questions with multiple steps or some complexity
#         Solvable in short to moderate time
#       Hard:
#         Complex integration, advanced application, or multi-concept problems
#         Requires considerable time
# *   **Content & Format Adherence:**
#     *   **NCERT Alignment:** All derivations and categorization must align with NCERT textbooks and the NEET syllabus. Use standard NCERT terminology and definitions.
#     *   **Language:** Use clear and unambiguous language.
#     *   **Subject-Specific Standards:**
#         *   **Physics:** Use SI units, include relevant physical constants, distinguish vector/scalar quantities, present clear mathematical expressions.
#         *   **Chemistry:** Follow IUPAC nomenclature, include balanced chemical equations where relevant, use standard state conditions unless specified.
#         *   **Biology:** Use correct taxonomic nomenclature (genus and species names italicized), include relevant biological processes and life cycles, focus on structural and functional aspects.
# **Strict Output Requirements:**
# 1.  **Exact Structure:** Each question object MUST strictly adhere to the following JSON structure. All keys and their spelling must be precise as shown:
# 2.  question_type should be one of the following:
# question_types = ["direct_concept_based","assertion_reason","numerical_problem","diagram_Based_Question","multiple_correct_answer","matching_type","comprehension_type","case_study_based","statement_based","single_correct_answer"]
# 3.  **Single Quotes:** Use single quotes for all string values within the JSON fields, and ensure any internal quotes are properly escaped.
# 4.  **No Extra Text:** Do NOT include any introductory or concluding remarks outside the JSON array.
# **Final Reminders:**
# 5.  **Use Clear Terminology:** Avoid jargon or colloquial language.
# 6.  **Provide Comprehensive Solutions:** Help students understand the reasoning behind the correct answer.
# 7.  **Estimated Time:**Appropriate for the difficulty level.
# 8.  **Keywords:**List main concepts or topics the question addresses.
# 9.  **All LaTeX rules must be strictly followed.**
# Do not miss to change equations in Latex format.
#  Give output in following json structure as below:
#   "[
#       {{
#         "q_id": "<original question_no>",
#         "question": "<original_question_latex_enriched>",
#         "explanation": "<step by step explanation=>",
#         "correct_answer": "<correct answer exactly from options>",
#         "options": ["<option1>", "<option2>", "<option3>", "<option4>"],
#         "subject_name": "<derived_subject_name>"
#         "topic_name": "<derived_topic_name_from_topic_name_list>",
#         "cognitive_level": "<derived_cognitive_level>",
#         "difficulty": "<derived_difficulty>"
#         "question_type": "<derived_question_type>",
#         "estimated_time": "<derived_time_in_minutes_integer>",
#         "concepts": "<concept1>,<concept2>,<concept3>"
#       }}
#     ]" """


topic_check_template = """
You are a strict topic classification assistant for NEET questions.

Question:
{question}

Old Topic (possibly incorrect or vague):
{old_topic}

Available Topics:
{topic_name_list}

🧠 Task:
Your task is to determine the **most accurate topic** for the question from the `topic_name_list`.

📌 Instructions:
1. Carefully read the question.
2. Refer to the provided `topic_name_list`.
3. Choose **exactly one topic** that best matches the question.
4. Do NOT generate any explanation.
5. Your output must be a **valid JSON**, and the selected topic **must be one of the exact values** from the `topic_name_list`.

🚫 Do not modify topic names.
🚫 Do not write explanations.
🚫 Do not include any text outside the JSON.

✅ Output Format:
{{
  "question": "{question}",
  "topic_name": "<selected_topic>"
}}
"""

question_refine_prompt= """You are provided with a list of Multiple Choice Questions (MCQs), where each question object contains a `question` and an `options` array. Your task is to process each of these questions, provide a detailed explanation, determine the correct answer and categorize each question based on its topic, cognitive level, question type, estimated time, and relevant concepts. Then change the formulas and equations into Latex format.

These are the list of MCQs you need to process:
{question_list}

**CRITICAL LaTeX & Math Formatting Rules: (STRICT ADHERENCE REQUIRED)**
1.  **MANDATORY LaTeX Conversion:** ALL mathematical expressions, variables, formulas, equations, and numerical values with units (e.g., `10°C`, `7 × 10^-4/°C`, `C+S-3A/3`, `gamma R`, `50 cc`) MUST be converted into standard LaTeX format and enclosed within single dollar signs (`$`). This applies to the `question`, `explanation`, `correct_answer`, and `options` fields.
    *   **NO UNICODE ESCAPES:** You MUST NOT use any Unicode escape sequences (e.g., `\u2212`, `\u00D7`, `\u221A`, `\u00B0`, etc.). Always use standard LaTeX commands or ASCII characters for operations.
    *   **INLINE MATH MODE ONLY:** All formulas/equations MUST be enclosed ONLY within single dollar signs (`$`). DO NOT use double dollar signs (`$$...$$`) or any other delimiters.

2.  **Specific Conversion Examples (Plain Text / Unicode / Common Shorthand -> Correct LaTeX):**
    *   **Simple Arithmetic/Expressions:**
        *   `C+S-3A/3`  ->  `$C+S-3A/3$`
    *   **Multiplication:**
        *   `X * Y` or `X x Y` -> `$X \\times Y$`
    *   **Dashes/Separators:**
        *   `–` (en dash/em dash) -> `-` (simple hyphen)
    *   **Powers / Superscripts:**
        *   `10^-4` -> `$10^{{-4}}$`
        *   `cm^3` or `cc` (for volume units) -> `$cm^3$`
    *   **Subscripts:**
        *   `V_R` or `gamma R` -> `$\\gamma_R$`
    *   **Special Characters / Symbols:**
        *   `sqrt(X)` or `√X` -> `$\\sqrt{{X}}$`
        *   `degrees C` or `°C` -> `$^\\circ C$`
        *   `delta` -> `$\\delta$`
        *   `gamma` -> `$\\gamma$`
    *   **Fractions:**
        *   `A/B` (for inline display) -> `$A/B$` or `$\\frac{{A}}{{B}}$` (choose based on complexity; for simple, `/` is often sufficient within `$ $`).
    *   **Variables:** Ensure all standalone variables or variables within expressions are enclosed in `$ $`. E.g., `If A is the coefficient` -> `If $A$ is the coefficient`.
    *   **Units:** Ensure units like `cm³`, `°C` are formatted as `$cm^3$` and `$^\\circ C$` respectively when part of a mathematical expression or quantity. (e.g., `50 cc` -> `50$\\,cm^3$`, `10°C` -> `10$^\\circ C$`)

3.  **JSON BACKSLASH ESCAPING (CRITICAL):** Within JSON string values, every single backslash `\` in LaTeX commands MUST be escaped as a double backslash `\\`.
    *   **Correct Example 1:** `"explanation": "The formula is $\\gamma = V_0 (1 + \\alpha \\Delta T)$"` (Note `\\gamma`, `\\alpha`, `\\Delta`)
    *   **Correct Example 2:** `"correct_answer": "$7 \\times 10^{{-4}}/^\\circ C$"` (Note `\\times` and `^\\circ`)
    *   **Forbidden Example (DO NOT USE THIS):** `"correct_answer": "$7 \times 10^{{-4}}/\circ C$"` (Missing escapes for `\times` and `\circ`)
    *   **NewLine Characters:** If using newlines within a string, they must be escaped as `\\n`.

**Processing Guidelines for Each Question:**
1.  **q_id:** Give original question number as provided in the `question_list`.
2.  **question:** Enrich the original question by converting ALL mathematical expressions, variables, units (e.g., `°C` to `$^\\circ C$`), and formulas into LaTeX format (adhering to the rules above). This includes single variables, simple arithmetic, powers, subscripts, and Greek letters.
3.  **explanation:**
    *   Craft a comprehensive `explanation` that provides a complete, step-by-step solution.
    *   Highlight **key concepts** in bold within the explanation.
    *   Include all relevant formulas/equations/reactions and units in LaTeX format (adhering to the rules above).
4.  **correct_answer:** Provide the exact semantic content from the options, ensuring all mathematical expressions, variables, and units are converted into LaTeX format (adhering to the rules above).
5.  **options:** Enrich the original options by converting ALL mathematical expressions, variables, and units into LaTeX format (adhering to the rules above).
6.  **subject_name:** Derive the subject of the question (e.g., Physics, Chemistry, Biology).
7.  **topic_name:** The `topic_name` of the question must be one in this following list: {topic_name_list}
8.  **cognitive_level:** Assess the thinking required (Remembering, Understanding, Applying, Analyzing, Evaluating, Creating).
    *   **Cognitive Levels:**
        *   **Remembering:** Recall facts and basic concepts
        *   **Understanding:** Explain ideas or concepts
        *   **Applying:** Use information in new situations
        *   **Analyzing:** Draw connections among ideas
        *   **Evaluating:** Justify a stand or decision
9.  **question_type:** Determine the primary type (e.g., Numerical, Conceptual, Diagram-based, Matching, Assertion-Reason).
    *   **Question types:**
        *   `direct_concept_based`: Tests straightforward understanding of a specific concept.
        *   `assertion_reason`: Presents a statement and a reason to evaluate their truth and relationship.
        *   `numerical_problem`: Requires solving a problem with calculations to arrive at a numerical answer.
        *   `diagram_Based_Question`: Based on interpreting or analyzing a given diagram or figure.
        *   `multiple_correct_answer`: Has more than one correct option among the choices.
        *   `matching_type`: Involves matching items in one column with related items in another.
        *   `comprehension_type`: Based on a passage or data set that must be interpreted to answer questions.
        *   `case_study_based`: Involves scenario-based analysis requiring application of concepts.
        *   `statement_based`: Presents multiple statements to judge their truth independently or together.
        *   `single_correct_answer`: Only one correct option exists among all given choices.
10. **estimated_time:** Estimate a reasonable time in minutes for a NEET student to solve the question (integer value).
11. **concepts:** List relevant fundamental concepts or sub-topics, comma-separated.
12. **difficulty:** Determine the primary levels like (easy, medium, hard)
    *   **Difficulty Levels:**
        *   **Easy:** Straightforward, direct questions; Single-step problems; Solvable in minimal time.
        *   **Medium:** Questions with multiple steps or some complexity; Solvable in short to moderate time.
        *   **Hard:** Complex integration, advanced application, or multi-concept problems; Requires considerable time.

*   **Content & Format Adherence:**
    *   **NCERT Alignment:** All derivations and categorization must align with NCERT textbooks and the NEET syllabus. Use standard NCERT terminology and definitions.
    *   **Language:** Use clear and unambiguous language.
    *   **Subject-Specific Standards:**
        *   **Physics:** Use SI units, include relevant physical constants, distinguish vector/scalar quantities, present clear mathematical expressions.
        *   **Chemistry:** Follow IUPAC nomenclature, include balanced chemical equations where relevant, use standard state conditions unless specified.
        *   **Biology:** Use correct taxonomic nomenclature (genus and species names italicized), include relevant biological processes and life cycles, focus on structural and functional aspects.

**Strict Output Requirements:**
1.  **Exact Structure:** Each question object MUST strictly adhere to the following JSON structure. All keys and their spelling must be precise as shown.
2.  **question_type** should be one of the specified types.
3.  **Single Quotes:** Use single quotes for all string values within the JSON fields, and ensure any internal quotes are properly escaped.
4.  **No Extra Text:** Do NOT include any introductory or concluding remarks outside the JSON array.

**Final Reminders:**
5.  **Use Clear Terminology:** Avoid jargon or colloquial language.
6.  **Provide Comprehensive Solutions:** Help students understand the reasoning behind the correct answer.
7.  **Estimated Time:** Appropriate for the difficulty level.
8.  **Keywords:** List main concepts or topics the question addresses.
9.  **All LaTeX rules must be strictly followed.**
Do not miss to change equations in Latex format.

Give output in following json structure as below:
[
  {{
    "q_id": "<original question_no>",
    "question": "<original_question_latex_enriched>",
    "explanation": "<step by step explanation=>",
    "correct_answer": "<correct answer exactly from options, with LaTeX>",
    "options": ["<option1_latex_enriched>", "<option2_latex_enriched>", "<option3_latex_enriched>", "<option4_latex_enriched>"],
    "subject_name": "<derived_subject_name>",
    "topic_name": "<derived_topic_name_from_topic_name_list>",
    "cognitive_level": "<derived_cognitive_level>",
    "difficulty": "<derived_difficulty>",
    "question_type": "<derived_question_type>",
    "estimated_time": "<derived_time_in_minutes_integer>",
    "concepts": "<concept1>,<concept2>,<concept3>"
  }}
]"""
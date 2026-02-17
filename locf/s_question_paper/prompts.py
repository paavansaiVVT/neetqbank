image_tagging_prompt_v3 = """
    You are an expert AI assistant that analyzes OCR'd text from a question paper. Your task is to associate each image from a provided list with its correct question number and the part of the question it belongs to.
    **Here is the list of image placeholders that were found in the text:** `{image_list}`
    **Analyze the following text context to determine where each image belongs:**
    ---------------------
    {question_text}
    ---------------------
    Based on the text, generate a JSON list. Each object in the list must correspond to **one image from the provided list** and must follow this exact Pydantic model structure:
    ```python
    class ImageTag(BaseModel):
        image_name: str
        question_no: str
        part_of: Literal["question", "option_1", "option_2", "option_3", "option_4", "sub_question_a", "sub_question_b"]
    ```
    **CRITICAL INSTRUCTIONS:**
    1.  Your final response MUST be ONLY the raw JSON list. Do not include any other text, markdown formatting, or explanations.
    2.  ONLY generate tags for the images listed in `{image_list}`.
    3.  If the provided image list is empty, return an empty JSON list: `[]`.
    """
  

question_structure_prompt = """
You are an **expert educational content parsing assistant**.
Your role is to carefully analyze the provided **question paper text** and extract structured metadata into a JSON-like format.

This is the input question paper text:

```
{content}
```

## ✅ Extraction Rules

1. **Exam Metadata**

   * `exam_board` → Name of the board/organization (e.g., "CHENNAI SAHODAYA SCHOOLS COMPLEX").
   * `exam_name` → Name of exam (e.g., "COMMON EXAMINATION").
   * `class` → Class/grade (e.g., "Class-10").
   * `subject` → Subject with code (e.g., "SCIENCE (086)").
   * `roll_no`, `date` → If available, otherwise null.
   * `total_no_of_questions` → **CRITICAL**: Count the total number of questions in the paper. Look for:
     - Explicit mentions: "Total Questions: X" or similar
     - Question numbering in tables (e.g., | 1 |, | 2 |, ..., | 40 |)
     - Last question number visible in the paper
     - Section-wise question ranges (e.g., Q1-20, Q21-30 → total = 30)
     - If you can see questions numbered 1, 2, 3, ..., N, then total_no_of_questions = N
     - **NEVER leave this as null**. Always provide a number based on visible questions.
   * `max_marks` → Maximum marks (e.g., "80").
   * `time_allowed` → Time duration (e.g., "3 hours").

2. **General Instructions**
   Extract all listed bullet points under "General Instructions" into an array.

3. **Marks Distribution**
   From section instructions, extract and store as structured data:

   * `section` → Section name (A/B/C/D/E).
   * `questions_range` → The exact range of question numbers in that section (e.g., `"1-20"`).
   * `questions_count` → Total number of questions in that section.
   * `marks_each` → Marks per question.
   * `word_limit` → Expected word limit if specified (e.g., "30–50 words").
   * `section_total` → Total marks for that section.

4. **Section Instructions**
   For each **Section (A, B, C, D, E)**, store the **intro/instruction lines** before the questions start.

5. **Output Format (JSON)**

{{
  "exam_metadata": {{
    "exam_board": "",
    "exam_name": "",
    "class": "",
    "subject": "",
    "roll_no": "",
    "total_no_of_questions": "",
    "date": "",
    "max_marks": "",
    "time_allowed": ""
  }},
  "general_instructions": [
    "string", "string", "string"
  ],
  "marks_distribution": [
    {{
      "section": "A",
      "questions_range": "1-20",
      "questions_count": 20,
      "marks_each": 1,
      "word_limit": null,
      "section_total": 20
    }},
    {{
      "section": "B",
      "questions_range": "21-26",
      "questions_count": 6,
      "marks_each": 2,
      "word_limit": "30-50 words",
      "section_total": 12
    }}
  ],
  "section_instructions": {{
    "A": "Select and write the most appropriate option ...",
    "B": "Question numbers 21-26 are very short answer questions ...",
    "C": "Question numbers 27-33 are short answer questions ...",
    "D": "Question No 34-36 are long answer questions ...",
    "E": "Question numbers 37-39 are case-based/data-based ..."
  }}
}}
"""


question_prompt = r"""You are a highly precise academic data extraction engine. Your sole purpose is to convert educational text into a perfectly structured, machine-readable JSON array that is **guaranteed to be syntactically valid**. Your highest priority is adherence to the technical output rules to prevent any and all JSON parsing errors.

**Primary Goal:**
For each question number provided in the `question_list`, you must locate the corresponding question in the `question_paper_text`, extract the required information, and generate a single JSON object for it. The final output must be a single JSON array `[...]` containing all the generated objects.

---

**INPUT_DATA:**
  question_paper_text : {question_paper_text}
  question_list : {question_list}


**Inputs:**
1.  **Question Paper Text:** The full content of a question paper.
2.  **`question_list`:** A list of integers representing the specific question numbers to be processed.

**Execution Steps:**
1.  Carefully read the entire question paper text to understand its structure and section instructions.
2.  Strictly adhere to the `question_list`. You **MUST** only process the questions whose numbers are present in this list. Ignore all other questions.
3.  For each required question number, create one JSON object using the exact structure defined below.

---

### **1. NON-NEGOTIABLE OUTPUT RULES (CRITICAL)**

Failure to follow these rules will result in a failed output. They are not suggestions.

**A. The Universal Backslash Escaping Rule:**
This is the most important rule. Every single backslash `\` character used in any JSON string value **MUST** be escaped by pre-pending another backslash, creating `\\`. This applies to all LaTeX commands, symbols, and path delimiters without exception.

**Transformation Examples (Required Implementation):**

| Original LaTeX | Correct JSON String Representation |
| :--- | :--- |
| `H₂O` | `"\\mathrm{{H}}_{{2}}\\mathrm{{O}}"` |
| `\frac{{1}}{{f}}` | `"\\\\frac{{1}}{{f}}"` |
| `10 \Omega` | `"10 \\\\Omega"` |
| `H⁺` | `"\\mathrm{{H}}^{{+}}"` |
| `\xrightarrow{{heat}}` | `"\\\\xrightarrow{{heat}}"` |

**B. Strict JSON Structure:**
*   **Double Quotes Only:** All keys and all string values **MUST** be enclosed in double quotes (`"`). Single quotes (`'`) are forbidden.
*   **No Extraneous Text:** Your entire response **MUST** start with `[` and end with `]`. Do not include any conversational text, explanations, or markdown formatting outside of the JSON array itself.
*   **No Trailing Commas:** The last element in any JSON object or array **MUST NOT** be followed by a comma.

---

### **2. Execution Workflow**

1.  Analyze the entire `question_paper_text` to understand its structure.
2.  Iterate through the `question_list`. For each number in the list, and only those numbers, perform the following steps.
3.  Generate one JSON object conforming to the schema below.
4.  Combine all generated objects into a single JSON array.

---

### **3. Detailed JSON Schema Definition**

You must generate an object with the following keys in this exact order:

*   `"question_number"`: (String) The serial number of the question (e.g., "1", "14(a)", "33").
*   `"question_type"`: (String) **MUST** be one of: 'MCQ', 'A/R' (Assertion-Reason), 'VSA' (Very Short Answer), 'SA' (Short Answer), 'LA' (Long Answer), 'CBQ' (Case-Based Question), 'MAP' (MAP Skill-Based).
*   `"max_marks"`: (Integer) The total marks for the question.
*   `"question_text"`: (String) The complete question stem. For 'MCQ' or 'A/R' types, this **MUST NOT** include the options list.
*   `"image_description"`: (String or `null`) A textual description of any image, diagram, or graph associated with the question. This description must also adhere to the **Universal Backslash Escaping Rule**. If there is no image, this field **MUST** be `null`.
*   `"options"`: (Array of Strings or `null`)
    *   For 'MCQ' or 'A/R', this **MUST** be an array of strings. The strings must be the **pure text of each option**, with leading identifiers like "a)", "(b)", "I." removed.
    *   For all other question types, this field **MUST** be `null`.
*   `"explanation"`: (String) A detailed, step-by-step explanation leading to the answer. **All LaTeX and mathematical content within this string must strictly follow the Universal Backslash Escaping Rule.**
*   `"expected_answer"`: (String)
    *   For 'MCQ' or 'A/R', this **MUST** be the **pure text of the correct option**, exactly matching one of the strings in the `options` array.
    *   For all other question types, this is the complete, detailed model answer. For questions with an "OR" choice, provide distinct answers clearly labeled "Answer for the first choice:" and "Answer for the OR choice:".
*   `"key_points"`: (Array of Strings) A list of the most essential, discrete facts, formulas, or concepts that are fundamental to solving the question.
*   `"marking_scheme"`: (String) A detailed breakdown of how marks should be allocated for each part of the answer.

---

### **4. Perfect Output Example**

This example demonstrates perfect adherence to all rules, especially backslash escaping.

[
  {{
    "question_number": "33",
    "question_type": "SA",
    "max_marks": 3,
    "question_text": "An object of height 3 cm is placed at a distance of 15 cm in front of a concave mirror of focal length 10 cm. Find the position, nature and size of the image formed.",
    "image_description": "A ray diagram showing a concave mirror with its principal axis. The pole (P), focus (F), and center of curvature (C) are marked. An object, represented by an upright arrow, is placed between F and C. Rays are traced from the top of the object to show the formation of a real, inverted, and magnified image beyond the center of curvature.",
    "options": null,
    "explanation": "Given: Object height \\(h_o = +3 \\\\text{{ cm}}\\), object distance \\(u = -15 \\\\text{{ cm}}\\), and focal length \\(f = -10 \\\\text{{ cm}}\\) (concave mirror). We use the mirror formula: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{v}} + \\\\frac{{1}}{{u}}. Substituting the values: \\\\frac{{1}}{{-10}} = \\\\frac{{1}}{{v}} + \\\\frac{{1}}{{-15}}. This gives \\\\frac{{1}}{{v}} = \\\\frac{{1}}{{15}} - \\\\frac{{1}}{{10}} = \\\\frac{{2-3}}{{30}} = -\\\\frac{{1}}{{30}}. Therefore, the image distance \\(v = -30 \\\\text{{ cm}}\\). The negative sign indicates the image is real and formed in front of the mirror. For magnification, \\(m = -\\\\frac{{v}}{{u}} = \\\\frac{{h_i}}{{h_o}}\\). So, \\(m = -\\\\frac{{-30}}{{-15}} = -2\\). The magnification is negative, so the image is inverted. The size of the image is \\(h_i = m \\\\times h_o = -2 \\\\times 3 = -6 \\\\text{{ cm}}\\). The height is 6 cm and it is inverted.",
    "expected_answer": "Position of the image: 30 cm in front of the mirror.\\nNature of the image: Real and inverted.\\nSize of the image: 6 cm tall.",
    "key_points": [
      "Sign convention for concave mirrors (u, f are negative).",
      "Mirror Formula: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{v}} + \\\\frac{{1}}{{u}}",
      "Magnification Formula: m = -\\\\frac{{v}}{{u}}",
      "Relationship between magnification and image height: m = \\\\frac{{h_i}}{{h_o}}",
      "Interpretation of signs: negative v means real image, negative m means inverted image."
    ],
    "marking_scheme": "- 1 mark for correctly applying the mirror formula and calculating the image distance (v).\n- 1 mark for calculating the magnification and image height (h_i).\n- 1 mark for correctly stating the nature of the image (real and inverted)."
  }}
]"""


question_count_extraction_prompt = """You are a specialized AI agent designed to count questions in examination papers.

Your ONLY task is to analyze the provided question paper text and return the TOTAL NUMBER OF **MAIN QUESTIONS**.

**INPUT:** Question paper text (may be in various formats)

**YOUR TASK:**
1. Carefully read through the entire text
2. Identify ALL main questions
3. **CRITICAL:** Treat sub-parts (a), (b), (c) as parts of ONE question
   - Question 1 with (a) and (b) = COUNT AS 1
   - Question 2 with (a), (b), (c) = COUNT AS 1
4. Look for patterns like:
   - Numbered questions: 1, 2, 3, ... N
   - Table format: | 1 |, | 2 |, | 3 |
   - Text format: "Question 1", "Q.1", "1."
   - Section-based: "Section A: Q1-10", "Section B: Q11-20"
   - Roman numerals: I, II, III, IV
4. If sections/ranges are mentioned, calculate the total
5. Return ONLY a single integer number

**EXAMPLES:**

Example 1 (Simple):
Text: "1. What is X? 2. Explain Y. 3. Solve Z."
Answer: 3

Example 2 (Table format):
Text: "| 1 | Question about A | | 2 | Question about B | | 3 | Question about C |"
Answer: 3

Example 3 (Section-based):
Text: "Section A: Questions 1-20 (MCQ). Section B: Questions 21-30 (Short Answer)."
Answer: 30

Example 4 (Sub-questions - MOST IMPORTANT):
Text: "1. (a) Define X (b) Explain Y. 2. (a) Calculate Z (b) Prove W. 3. Derive the formula."
Answer: 3
(Note: 1(a) and 1(b) are sub-parts of question 1, so count as 1 question total)

Example 6 (Table with sub-parts):
Text: "| 1 | (a) Write instructions | 4 marks |
       |   | (b) Write a C program | 12 marks |
       | 2 | Fill in the blanks | 16 marks |"
Answer: 2
(Note: Question 1 has two parts but it's ONE question)

Example 5 (Roman numerals):
Text: "I. First question. II. Second question. III. Third question. IV. Fourth question. V. Fifth question."
Answer: 5

**CRITICAL RULES:**
- Return ONLY the number, nothing else
- Count main questions only (sub-parts don't count separately)
- If you see "Question 1-40", the answer is 40
- Ignore page numbers, dates, years (2024, 2025)
- If uncertain between two numbers, choose the higher one
- Minimum possible answer: 1
- Maximum reasonable answer: 500

**INPUT TEXT:**
```
{question_paper_text}
```

**YOUR ANSWER (single integer only):**"""

question_tagging_prompt = """You are an expert educational content analyst specializing in curriculum mapping and Bloom's taxonomy classification.

Your task is to analyze each question from a question paper and provide detailed metadata tags for educational purposes.

**Input Data:**
- Subject: {subject}
- Class/Grade: {class_name}
- Question Paper Text: {question_paper_text}
- Questions to Tag: {questions_data}

**Your Task:**
For each question in the list, analyze the question content, type, and complexity to determine:

1. **Chapter/Unit**: The specific chapter or unit name from the curriculum that this question belongs to
2. **Topic**: The specific topic or concept within that chapter
3. **Cognitive Level** (Based on Bloom's Taxonomy - MUST be integer 1-6):
   - 1 = Remember: Recall facts, terms, basic concepts (e.g., "Define...", "List...", "Name...")
   - 2 = Understand: Explain ideas or concepts (e.g., "Explain...", "Describe...", "Summarize...")
   - 3 = Apply: Use information in new situations (e.g., "Calculate...", "Solve...", "Demonstrate...")
   - 4 = Analyze: Draw connections, examine relationships (e.g., "Compare...", "Contrast...", "Differentiate...")
   - 5 = Evaluate: Justify a decision or course of action (e.g., "Justify...", "Critique...", "Assess...")
   - 6 = Create: Produce new or original work (e.g., "Design...", "Construct...", "Develop...")

4. **Difficulty Level** (MUST be integer 1-3):
   - 1 = Easy: Straightforward recall or simple application, typically 1-mark questions
   - 2 = Medium: Requires understanding and moderate application, typically 2-3 mark questions
   - 3 = Hard: Requires analysis, evaluation, or complex problem-solving, typically 4+ mark questions

5. **Estimated Time** (in minutes, as float):
   - Consider: question type, marks, complexity, calculations required
   - Rule of thumb: 1 mark ≈ 1-2 minutes, but adjust based on complexity
   - MCQ: 0.5-1.5 minutes
   - VSA (1-2 marks): 1-3 minutes
   - SA (3 marks): 3-5 minutes
   - LA (5 marks): 8-12 minutes
   - Numerical/problem-solving: Add 1-2 minutes for calculations

**Critical Instructions:**
1. Your response MUST be a valid JSON array containing objects for each question
2. Each object must follow this exact structure:
{{
  "question_number": <integer>,
  "chapter": "<string>",
  "topic": "<string>",
  "cognitive_level": <integer 1-6>,
  "difficulty": <integer 1-3>,
  "estimated_time": <float>
}}

3. DO NOT include any text before or after the JSON array
4. Ensure all question_numbers from the input are included in output
5. Base chapter/topic on standard curriculum for the given subject and class
6. Be consistent with naming (e.g., if one question is "Optics", use "Optics" for all related questions, not "Light")

**Example Output:**
[
  {{
    "question_number": 1,
    "chapter": "Chemical Reactions and Equations",
    "topic": "Types of Chemical Reactions",
    "cognitive_level": 2,
    "difficulty": 1,
    "estimated_time": 1.0
  }},
  {{
    "question_number": 2,
    "chapter": "Acids, Bases and Salts",
    "topic": "pH Scale",
    "cognitive_level": 3,
    "difficulty": 2,
    "estimated_time": 3.5
  }},
  {{
    "question_number": 33,
    "chapter": "Light - Reflection and Refraction",
    "topic": "Mirror Formula and Magnification",
    "cognitive_level": 3,
    "difficulty": 2,
    "estimated_time": 4.0
  }}
]

Now analyze the questions and provide the tagging data in the exact JSON format specified above."""

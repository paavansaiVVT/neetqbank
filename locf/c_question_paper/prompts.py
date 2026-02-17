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

question_prompt_v2 = r"""You are a highly precise academic data extraction engine. Your sole purpose is to convert educational text into a perfectly structured, machine-readable JSON array that is **guaranteed to be syntactically valid**. Your highest priority is adherence to the technical output rules to prevent any and all JSON parsing errors.

**Primary Goal:**
For each question number provided in the `question_list`, you must locate the corresponding question in the `question_paper_text`, extract the required information, and generate a single JSON object for it. The final output must be a single JSON array `[...]` containing all the generated objects.

**IMPORTANT: SUB-QUESTION HANDLING**
Many questions have sub-parts (e.g., Question 14 may have parts (a), (b), (c) with different marks). You MUST identify these sub-questions and structure them properly using the `sub_questions` array.

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
3.  For each required question number, identify if it has sub-parts (a, b, c, i, ii, iii, etc.).
4.  Create one JSON object using the exact structure defined below.

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
3.  Identify if the question has sub-parts (a, b, c) or (i, ii, iii) with separate marks allocated.
4.  Generate one JSON object conforming to the schema below.
5.  Combine all generated objects into a single JSON array.

---

### **3. Detailed JSON Schema Definition**

You must generate an object with the following keys in this exact order:

*   `"question_number"`: (String) The serial number of the question (e.g., "1", "14", "33").
*   `"question_type"`: (String) **MUST** be one of: 'MCQ', 'A/R' (Assertion-Reason), 'VSA' (Very Short Answer), 'SA' (Short Answer), 'LA' (Long Answer), 'CBQ' (Case-Based Question), 'MAP' (MAP Skill-Based).
*   `"max_marks"`: (Integer) The **total marks** for the entire question (sum of all sub-question marks if applicable).
*   `"has_sub_questions"`: (Boolean) `true` if the question has sub-parts (a, b, c, etc.), `false` otherwise.
*   `"question_text"`: (String) The main question stem or common context. For 'MCQ' or 'A/R' types without sub-parts, this **MUST NOT** include the options list. For questions with sub-parts, this is the common instruction or context that applies to all sub-parts.
*   `"image_description"`: (String or `null`) A textual description of any image, diagram, or graph associated with the main question. This description must also adhere to the **Universal Backslash Escaping Rule**. If there is no image, this field **MUST** be `null`.

**For questions WITHOUT sub-parts (`has_sub_questions: false`):**
*   `"options"`: (Array of Strings or `null`) For 'MCQ' or 'A/R', array of option texts. For other types, `null`.
*   `"explanation"`: (String) A detailed, step-by-step explanation leading to the answer. **All LaTeX must be properly escaped.**
*   `"expected_answer"`: (String) For MCQ/A/R: the correct option text. For others: the complete model answer.
*   `"key_points"`: (Array of Strings) Essential facts, formulas, or concepts.
*   `"marking_scheme"`: (String) Detailed mark allocation breakdown.
*   `"sub_questions"`: (null or empty array `[]`)

**For questions WITH sub-parts (`has_sub_questions: true`):**
*   `"options"`: `null`
*   `"explanation"`: `null` (explanations go in sub-questions)
*   `"expected_answer"`: `null` (answers go in sub-questions)
*   `"key_points"`: (Array of Strings) Key points applicable to the entire question or common to all sub-parts.
*   `"marking_scheme"`: (String) Overall marking scheme or "Refer to sub-questions for detailed marking."
*   `"sub_questions"`: (Array of Objects) **MUST** contain one object for each sub-part with the following structure:

**Sub-question Object Schema:**
```json
{{
  "sub_question_id": "(a)", // or "(b)", "(i)", "(ii)", "1", "2", etc.
  "sub_max_marks": 2, // marks for THIS sub-part only
  "sub_question_text": "The specific question text for this sub-part",
  "sub_image_description": "Description of image specific to this sub-part" or null,
  "sub_question_type": "MCQ" or "SA" or "VSA" or "LA" or null,
  "sub_options": ["option1", "option2", "option3", "option4"] or null,
  "sub_explanation": "Detailed step-by-step explanation for this sub-part",
  "sub_expected_answer": "The model answer for this sub-part",
  "sub_key_points": ["key point 1", "key point 2"],
  "sub_marking_scheme": "Mark allocation for this sub-part"
}}
```

---

### **4. Perfect Output Examples**

**Example 1: Question WITHOUT sub-parts (Regular MCQ)**

[
  {{
    "question_number": "5",
    "question_type": "MCQ",
    "max_marks": 1,
    "has_sub_questions": false,
    "question_text": "Which of the following is a renewable source of energy?",
    "image_description": null,
    "options": [
      "Coal",
      "Petroleum",
      "Solar energy",
      "Natural gas"
    ],
    "explanation": "Solar energy is a renewable source of energy because it is derived from the sun, which is an inexhaustible source. Coal, petroleum, and natural gas are non-renewable fossil fuels that take millions of years to form.",
    "expected_answer": "Solar energy",
    "key_points": [
      "Renewable energy sources are inexhaustible",
      "Solar energy comes from the sun",
      "Fossil fuels are non-renewable"
    ],
    "marking_scheme": "1 mark for the correct option.",
    "sub_questions": null
  }}
]

**Example 2: Question WITH sub-parts (Question with parts a, b, c)**

[
  {{
    "question_number": "14",
    "question_type": "SA",
    "max_marks": 5,
    "has_sub_questions": true,
    "question_text": "A concave mirror produces three times magnified real image of an object placed at 10 cm in front of it.",
    "image_description": "A ray diagram showing a concave mirror with an object placed in front of it and the formation of a magnified real image.",
    "options": null,
    "explanation": null,
    "expected_answer": null,
    "key_points": [
      "Mirror formula: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{v}} + \\\\frac{{1}}{{u}}",
      "Magnification formula: m = -\\\\frac{{v}}{{u}}",
      "Sign conventions for mirrors"
    ],
    "marking_scheme": "Refer to sub-questions for detailed marking.",
    "sub_questions": [
      {{
        "sub_question_id": "(a)",
        "sub_max_marks": 2,
        "sub_question_text": "Where is the image located?",
        "sub_image_description": null,
        "sub_question_type": "SA",
        "sub_options": null,
        "sub_explanation": "Given: Object distance \\(u = -10 \\\\text{{ cm}}\\), magnification \\(m = -3\\) (negative because the image is real). Using the magnification formula: \\(m = -\\\\frac{{v}}{{u}}\\). Substituting: \\(-3 = -\\\\frac{{v}}{{-10}}\\), which gives \\(v = -30 \\\\text{{ cm}}\\). The negative sign indicates the image is formed on the same side as the object (real image).",
        "sub_expected_answer": "The image is located at 30 cm in front of the mirror.",
        "sub_key_points": [
          "Magnification m = -3 for real image",
          "Formula: m = -v/u",
          "v = -30 cm"
        ],
        "sub_marking_scheme": "1 mark for using the magnification formula correctly. 1 mark for calculating the correct image distance."
      }},
      {{
        "sub_question_id": "(b)",
        "sub_max_marks": 2,
        "sub_question_text": "Calculate the focal length of the mirror.",
        "sub_image_description": null,
        "sub_question_type": "SA",
        "sub_options": null,
        "sub_explanation": "Using the mirror formula: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{v}} + \\\\frac{{1}}{{u}}. We have \\(v = -30 \\\\text{{ cm}}\\) and \\(u = -10 \\\\text{{ cm}}\\). Substituting: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{-30}} + \\\\frac{{1}}{{-10}} = \\\\frac{{-1-3}}{{30}} = \\\\frac{{-4}}{{30}} = -\\\\frac{{2}}{{15}}. Therefore, \\(f = -7.5 \\\\text{{ cm}}\\).",
        "sub_expected_answer": "The focal length of the mirror is 7.5 cm.",
        "sub_key_points": [
          "Mirror formula: 1/f = 1/v + 1/u",
          "v = -30 cm, u = -10 cm",
          "f = -7.5 cm"
        ],
        "sub_marking_scheme": "1 mark for applying the mirror formula. 1 mark for correct calculation of focal length."
      }},
      {{
        "sub_question_id": "(c)",
        "sub_max_marks": 1,
        "sub_question_text": "What is the nature of the image formed?",
        "sub_image_description": null,
        "sub_question_type": "VSA",
        "sub_options": null,
        "sub_explanation": "Since the magnification is negative (m = -3), the image is inverted. Since the image distance v is negative and real, the image is formed on the same side as the object. Therefore, the image is real, inverted, and magnified.",
        "sub_expected_answer": "The image is real, inverted, and magnified.",
        "sub_key_points": [
          "Negative magnification indicates inverted image",
          "Real image formed by concave mirror"
        ],
        "sub_marking_scheme": "1 mark for correctly stating the nature (real and inverted)."
      }}
    ]
  }}
]

**Example 3: Case-Based Question (CBQ) with sub-parts**

[
  {{
    "question_number": "38",
    "question_type": "CBQ",
    "max_marks": 4,
    "has_sub_questions": true,
    "question_text": "Read the following passage and answer the questions that follow:\\n\\nPhotosynthesis is a process used by plants and other organisms to convert light energy into chemical energy. In this process, carbon dioxide and water are converted into glucose and oxygen in the presence of chlorophyll and sunlight. The overall equation is: \\\\text{{6CO}}_{{2}} + \\\\text{{6H}}_{{2}}\\\\text{{O}} \\\\xrightarrow{{\\\\text{{sunlight, chlorophyll}}}} \\\\text{{C}}_{{6}}\\\\text{{H}}_{{12}}\\\\text{{O}}_{{6}} + \\\\text{{6O}}_{{2}}",
    "image_description": "A diagram showing the process of photosynthesis in a leaf, with labels for chloroplast, sunlight, carbon dioxide, water, glucose, and oxygen.",
    "options": null,
    "explanation": null,
    "expected_answer": null,
    "key_points": [
      "Photosynthesis equation: 6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂",
      "Requires sunlight and chlorophyll",
      "Occurs in chloroplasts"
    ],
    "marking_scheme": "Refer to sub-questions for detailed marking.",
    "sub_questions": [
      {{
        "sub_question_id": "(i)",
        "sub_max_marks": 1,
        "sub_question_text": "Name the organelle where photosynthesis takes place.",
        "sub_image_description": null,
        "sub_question_type": "VSA",
        "sub_options": null,
        "sub_explanation": "Photosynthesis takes place in chloroplasts, which are organelles found in plant cells. Chloroplasts contain chlorophyll, the green pigment that captures light energy.",
        "sub_expected_answer": "Chloroplast",
        "sub_key_points": [
          "Chloroplast is the site of photosynthesis",
          "Contains chlorophyll"
        ],
        "sub_marking_scheme": "1 mark for correct answer."
      }},
      {{
        "sub_question_id": "(ii)",
        "sub_max_marks": 1,
        "sub_question_text": "What is the role of chlorophyll in photosynthesis?",
        "sub_image_description": null,
        "sub_question_type": "VSA",
        "sub_options": null,
        "sub_explanation": "Chlorophyll is a green pigment that absorbs light energy from the sun. This light energy is then used to drive the chemical reactions of photosynthesis, converting carbon dioxide and water into glucose and oxygen.",
        "sub_expected_answer": "Chlorophyll absorbs light energy from the sun to drive the photosynthesis process.",
        "sub_key_points": [
          "Chlorophyll absorbs light energy",
          "Enables conversion of light to chemical energy"
        ],
        "sub_marking_scheme": "1 mark for mentioning absorption of light energy."
      }},
      {{
        "sub_question_id": "(iii)",
        "sub_max_marks": 2,
        "sub_question_text": "Why is photosynthesis considered an endothermic reaction?",
        "sub_image_description": null,
        "sub_question_type": "SA",
        "sub_options": null,
        "sub_explanation": "Photosynthesis is considered an endothermic reaction because it requires energy input in the form of sunlight. The reaction absorbs light energy and converts it into chemical energy stored in glucose molecules. Energy from sunlight is essential for breaking the bonds in \\\\text{{CO}}_{{2}} and \\\\text{{H}}_{{2}}\\\\text{{O}} and forming new bonds in glucose.",
        "sub_expected_answer": "Photosynthesis is endothermic because it requires energy input from sunlight to convert carbon dioxide and water into glucose. The light energy is absorbed and stored as chemical energy in glucose molecules.",
        "sub_key_points": [
          "Endothermic reactions require energy input",
          "Sunlight provides the energy",
          "Light energy is converted to chemical energy"
        ],
        "sub_marking_scheme": "1 mark for stating that it requires energy. 1 mark for explaining that sunlight provides this energy."
      }}
    ]
  }}
]

---

### **5. Special Instructions for Sub-Questions**

1.  **Identification:** Look for patterns like:
    - "14. (a) ...", "14. (b) ...", "14. (c) ..."
    - "Q.5 (i) ...", "Q.5 (ii) ...", "Q.5 (iii) ..."
    - "Question 12: 1. ...", "2. ...", "3. ..."

2.  **Mark Distribution:** Carefully note marks for each sub-part. They are usually indicated like:
    - "(a) [2 marks]" or "(a) (2)"
    - Sometimes at the start: "Question 14 [5 marks] (a) [2] (b) [2] (c) [1]"

3.  **Total Marks Calculation:** The `max_marks` at the question level **MUST** equal the sum of all `sub_max_marks`.

4.  **Common Context:** If there's a diagram, passage, or context that applies to all sub-parts, put it in the main `question_text` and `image_description`.

5.  **OR Choices:** If a question has "OR" between sub-parts, create separate sub-question objects for each option and note in `sub_question_text` which is the "OR" alternative.

6.  **Empty Fields:** If a sub-question doesn't have certain elements (e.g., no image, not MCQ), set those fields to `null`.

---

### **6. Final Checklist**

Before outputting your JSON:
- ✅ All backslashes in LaTeX are properly escaped (`\\`)
- ✅ All strings use double quotes (`"`)
- ✅ No trailing commas
- ✅ `has_sub_questions` is `true` only when there are actual sub-parts with separate marks
- ✅ Sum of `sub_max_marks` equals `max_marks` for questions with sub-parts
- ✅ Each sub-question has all required fields
- ✅ Response starts with `[` and ends with `]`
- ✅ No extra text outside the JSON array

**Now process the questions and output the perfect JSON array.**"""

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

t = """You are an expert educational content analyst specializing in curriculum mapping and Bloom's taxonomy classification.

Your task is to analyze each question from a question paper and provide detailed metadata tags for educational purposes.

**Input Data:**
- Subject: {subject}
- Class/Grade: {class_name}
- Question Paper Text: {question_paper_text}
- Questions to Tag: {questions_data}

**Your Task:**
For each questionquestion_tagging_promp in the list, analyze the question content, type, and complexity to determine:

1. **Chapter/Unit**: The specific chapter or unit name from the curriculum that this question belongs to
2. **Topic**: The specific topic or concept within that chapter
3. **Cognitive Level** (Based on Bloom's Taxonomy - MUST be EXACTLY one of these strings):
   - "Remembering": Recall facts, terms, basic concepts (e.g., "Define...", "List...", "Name...")
   - "Understanding": Explain ideas or concepts (e.g., "Explain...", "Describe...", "Summarize...")
   - "Applying": Use information in new situations (e.g., "Calculate...", "Solve...", "Demonstrate...")
   - "Analyzing": Draw connections, examine relationships (e.g., "Compare...", "Contrast...", "Differentiate...")
   - "Evaluating": Justify a decision or course of action (e.g., "Justify...", "Critique...", "Assess...")
   - "Creating": Produce new or original work (e.g., "Design...", "Construct...", "Develop...")

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
  "cognitive_level": "String (MUST be exactly one of: Remembering|Understanding|Applying|Analyzing|Evaluating|Creating)",
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
    "cognitive_level": "Understanding",
    "difficulty": 1,
    "estimated_time": 1.0
  }},
  {{
    "question_number": 2,
    "chapter": "Acids, Bases and Salts",
    "topic": "pH Scale",
    "cognitive_level": "Applying",
    "difficulty": 2,
    "estimated_time": 3.5
  }},
  {{
    "question_number": 33,
    "chapter": "Light - Reflection and Refraction",
    "topic": "Mirror Formula and Magnification",
    "cognitive_level": "Applying",
    "difficulty": 2,
    "estimated_time": 4.0
  }}
]

Now analyze the questions and provide the tagging data in the exact JSON format specified above."""

question_extraction_prompt = """You are an expert data extraction agent specializing in academic documents. Your primary task is to parse the text of an exam paper and convert all the questions into a structured JSON format.

**Primary Goal:**
Convert the provided text from an exam paper into a single, valid JSON object containing a list of questions.

**JSON Schema and Rules:**

The final output must be a JSON object with a single key, "questions", which is an array of question objects. Each question object must follow this structure:

{{
  "question_number": "String",
  "has_sub_questions": "Boolean",
  "alternative_ques": "Boolean",
  "parts": [
    {{
      "marks": "Integer | null",
      "question_type": "String",
      "text": "String",
      "course_outcome": "String | null",
      "blooms_level": "String | null",
      "image_description": "String | null",
      "options": "Array<String> | null",
      "part_label": "String | null",
      "code_snippet": "String | null"
    }}
  ]
}}

**Field Descriptions and Instructions:**

1.  **`question_number`**: (String) The number or identifier of the question (e.g., "1", "3", "4a").
2.  **`marks`**: (Integer) The total marks for the question, if specified. If not available, use `null`.
3.  **`course_outcome`**: (String) The "CO" code associated with the question (e.g., "CO4"). If not available, use `null`.
4.  **`blooms_level`**: (String) The Bloom's Taxonomy level (e.g., "L4"). If not available, use `null`.
5.  **`question_type`**: (String) **MUST** be one of: 'MCQ', 'A/R' (Assertion-Reason), 'VSA' (Very Short Answer), 'SA' (Short Answer), 'LA' (Long Answer), 'CBQ' (Case-Based Question), 'MAP' (MAP Skill-Based). Classify the question based on its content and format.
6.  **`image_description`**: (String or `null`) A textual description of any image, diagram, or graph associated with the question. Ensure any special characters like backslashes or quotes within the description are properly escaped for valid JSON. If there is no image, this field **MUST** be `null`.
7.  **`options`**: (Array of Strings or `null`)
    *   For 'MCQ' or 'A/R' question types, this **MUST** be an array of strings. The strings must be the **pure text of each option**, with leading identifiers like "a)", "(b)", "I." removed.
    *   For all other question types, this field **MUST** be `null`.
8.  **`has_sub_questions`**: (Boolean) Set to `true` if the question is explicitly divided into labeled sub-parts like (a), (b), (i), (ii), etc. that the student must answer ALL parts. Set to `false` if it is a single, undivided question.
9.  **`alternative_ques`**: (Boolean) **CRITICAL** Set to `true` if the question contains [OR] alternatives where the student chooses ONE option to answer. Set to `false` for regular questions. This is DIFFERENT from `has_sub_questions` - alternative questions have multiple options but student answers only ONE, while sub-questions require answering ALL parts.
10. **`parts`**: (Array) An array of objects, where each object represents a distinct part of the question.
    *   **Crucially, if a question has no sub-parts, it should still be an array containing a single element.**
11. **`part_label`**: (String) The label for the sub-part (e.g., "(a)", "(b)"). If the question is not divided into parts, this field must be `null`.
12. **`text`**: (String) The full, clean text of the question or sub-part.
    *   Remove any OCR artifacts like `<br>` tags or extra whitespace.
    *   Combine lines into a coherent paragraph.
13. **`code_snippet`**: (String) If the question or part includes a block of code, extract it here.
    *   Preserve the original indentation and use `\n` for newlines.
    *   If there is no code, this field must be `null`.

**Key Processing Rules:**

*   **Ignore non-question content:** Do not include the exam header (institute name, course code, instructions, etc.) or footers in the JSON output.
*   **Accuracy is paramount:** Ensure all text, numbers, and code are extracted exactly as they appear.
*   **Handle messy input:** The source text may have formatting issues. Clean it up logically.
*   **Strict JSON format:** The final output must be a single, perfectly valid JSON object that can be parsed without errors.

**CRITICAL: Handling Introductory Text and Passages**

⚠️ **DO NOT create separate parts for introductory text or passages!**

**Examples of INCORRECT handling:**

❌ **WRONG for Question 23:**
```
23. Which type of joint exists between?
a. Upper jaw and rest of skull.
b. Lower jaw and rest of skull.
```
DO NOT create:
     - Part 1 (no label, 0 marks): "Which type of joint exists between?"
- Part 2 (label "a", 1 mark): "Upper jaw and rest of skull."
- Part 3 (label "b", 1 mark): "Lower jaw and rest of skull."

✅ **CORRECT handling:**
- Part (a) with 1 mark: "Which type of joint exists between? Upper jaw and rest of skull."
- Part (b) with 1 mark: "Which type of joint exists between? Lower jaw and rest of skull."

❌ **WRONG for Passage-Based Questions:**
```
38. PASSAGE BASED QUESTIONS:
Read the following passage: [long passage]
a. Question about passage (2 marks)
b. Another question (1 mark)
```
DO NOT create:
- Part 1 (no label, null marks): The passage text
- Part 2 (label "a"): Question a
- Part 3 (label "b"): Question b

✅ **CORRECT handling:**
- Part (a) with 2 marks: "Read the passage: [passage text] Question: Why is air considered a mixture?"
- Part (b) with 1 mark: "Read the passage: [passage text] Question: Name the process in which oxygen is produced."

**Rules for Introductory Text:**
1. If a question has introductory text followed by sub-parts (a, b, c), MERGE the introductory text with each sub-part's text
2. NEVER create a part with `part_label: null` and `marks: 0` or `marks: null`
3. Every part MUST have either:
   - `part_label: null` and valid marks (for single questions)
   - `part_label: "(a)"/"(b)"` etc. and valid marks (for sub-questions)
4. Passages/context should be included in the text of each sub-part that references it

**CRITICAL: Handling OR Questions (Student Choice Questions)**

⚠️ **OR questions are where students CHOOSE ONE of multiple alternative questions to answer.**

**Example:**
```
24. Shreya dipped a bar magnet in iron filings...
    a. Which region has more filings?
    b. What are these regions called?

[OR]

It was observed that the pencil sharpener gets attracted...
Name a material that might have been used.
```

✅ **CORRECT handling for OR questions:**
```json
{
  "question_number": "24",
  "has_sub_questions": false,
  "alternative_ques": true,
  "parts": [
    {
      "part_label": null,
      "marks": 2,
      "text": "Shreya dipped a bar magnet... a. Which region...? b. What are these regions called?"
    },
    {
      "part_label": null,
      "marks": 2,
      "text": "[OR]\nIt was observed that the pencil sharpener gets attracted..."
    }
  ]
}
```

**CRITICAL Rules for OR Questions:**
1. **MUST set `alternative_ques: true`** - This is MANDATORY for marks calculation
2. **MUST set `has_sub_questions: false`** - These are alternatives, not sub-parts
3. Create separate parts for each OR alternative
4. Mark the alternative part's text with [OR] at the start
5. Both parts should have `part_label: null` (they are alternatives, not sub-parts a/b)
6. Each part should have its own marks value
7. The system will automatically split these into separate question entries (24 and 24-ORB)

**Why `alternative_ques` is CRITICAL:**
- Regular sub-questions: Student answers ALL parts (a, b, c) → Total marks = sum of all parts
- OR questions: Student answers ONLY ONE option → Total marks = marks of chosen option
- Without this flag, marks calculation will be WRONG!

**Example:**

*If the input text is:*
> 3. Which of the following is a valid C keyword? (1 Mark)
> (a) integer
> (b) float
> (c) string
> (d) main

*The output should be:*
[
    {{
      "question_number": "3",
      "has_sub_questions": false,
      "alternative_ques": false,
      "parts": [
        {{
          "marks": 1,
          "question_type": "MCQ",
          "text": "Which of the following is a valid C keyword?",
          "course_outcome": null,
          "blooms_level": null,
          "image_description": null,
          "options": ["integer","float","string","main"],
          "part_label": null,
          "code_snippet": null
        }}
      ]
    }}
]

"""

question_extraction_retry_prompt_template = """
**🔄 RETRY EXTRACTION - CRITICAL MISSING QUESTIONS**

**CRITICAL FAILURE DETECTED:**
The previous attempt failed to extract ALL required questions.

**TARGET: {total_expected} TOTAL QUESTIONS (Questions 1 through {total_expected})**
**MISSING: {missing_questions_list}**

You are performing a RETRY extraction because the previous attempt missed these questions: {missing_questions}

**ABSOLUTE PRIORITY:** 
1. Extract ALL {total_expected} questions from the document
2. Pay EXTRA attention to the missing questions: {missing_questions_list}
3. Verify EVERY question from 1 to {total_expected} is included

**Your Task:**
1. Scan the ENTIRE document from beginning to end
2. Pay SPECIAL ATTENTION to:
   - The specific missing questions: {missing_questions_list}
   - Pages where these questions should appear
   - Section boundaries where questions might have been skipped
   - Questions that span multiple pages
   - Sub-questions or parts that might have been overlooked
   - Questions in tables, diagrams, or special formatting
3. Extract ALL {total_expected} questions with emphasis on the missing ones

**CRITICAL VALIDATION CHECKLIST:**
Before returning your response, you MUST verify:
✅ TOTAL question count = {total_expected} (count them!)
✅ ALL missing questions {missing_questions_list} are now present
✅ Questions are numbered from 1 to {total_expected}
✅ Each question has complete information (number, marks, text, parts)
✅ No questions are duplicated
✅ All sub-parts are included

**FAILURE WARNING:**
If you do not extract all {total_expected} questions, the system will FAIL and need another retry.
This is CRITICAL for exam processing - every single question matters.

**Return Format:**
Return a complete JSON object with ALL {total_expected} questions.
Do NOT return only the missing questions - return the COMPLETE list including previously extracted ones.

{original_prompt}
"""

single_question_processing_prompt = r"""You are an expert educational content analyzer specializing in generating detailed explanations, expected answers, key points, and marking schemes for examination questions.

**Your Task:**
You will receive a list of questions (without sub-parts) that have already been extracted from a question paper. Your job is to enrich EACH question with:
1. Detailed explanation
2. Expected answer
3. Key points
4. Marking scheme

**Input Questions List:**
{question_list}

**Output Requirements:**

You MUST output a JSON ARRAY containing one object for EACH input question with this EXACT structure:

[
  {{
    "question_number": "String (e.g., '1', '5', '12')",
    "has_sub_questions": false,
    "parts": [
      {{
        "part_label": null,
        "marks": Integer (total marks for this question),
        "explanation": "String (detailed step-by-step explanation showing how to solve/answer)",
        "expected_answer": "String (the complete model answer)",
        "key_points": ["String", "String", "String"],
        "marking_scheme": "String (breakdown of how marks are allocated)",
        "cognitive_level": "String (MUST be exactly one of: Remembering|Understanding|Applying|Analyzing|Evaluating|Creating)",
        "difficulty": "String (Easy|Medium|Hard)",
        "estimated_time": Float (time in minutes, e.g., 2.5)
      }}
    ]
  }},
  {{
    "question_number": "String",
    "has_sub_questions": false,
    "parts": [...]
  }}
]

**Important Instructions:**

1. **Explanation Field:**
   - Provide a comprehensive, step-by-step explanation
   - Include formulas, concepts, and reasoning
   - If there are mathematical equations, use LaTeX format with proper escaping
   - Example: `"Using Newton's second law: \\\\text{{F}} = \\\\text{{ma}}"`

2. **Expected Answer Field:**
   - Provide the complete, detailed model answer
   - This is what a student should write to get full marks
   - Be specific and thorough

3. **Key Points Field:**
   - List 3-7 essential points/concepts needed to answer the question
   - Each point should be concise but complete
   - Focus on critical formulas, facts, or concepts

4. **Marking Scheme Field:**
   - Break down how marks should be allocated
   - Example: "1 mark for correct formula, 1 mark for substitution, 1 mark for final answer"
   - Be specific about what earns each mark

5. **Cognitive Level Field (Bloom's Taxonomy):**
   - Classify the question based on Bloom's Taxonomy
   - **CRITICAL: MUST be EXACTLY one of these strings (case-sensitive):** "Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"
   - **FORBIDDEN VALUES:** Do NOT use "L1", "L2", "L3", "L4", "L5", "L6", "Level 1", "Level 2", etc.
   - **Remembering:** Recall facts, terms, basic concepts (e.g., "Define...", "List...", "Name...")
   - **Understanding:** Explain ideas or concepts (e.g., "Explain...", "Describe...", "Summarize...")
   - **Applying:** Use information in new situations (e.g., "Calculate...", "Solve...", "Demonstrate...")
   - **Analyzing:** Draw connections, examine relationships (e.g., "Compare...", "Contrast...", "Differentiate...")
   - **Evaluating:** Justify a decision or course of action (e.g., "Justify...", "Critique...", "Assess...")
   - **Creating:** Produce new or original work (e.g., "Design...", "Construct...", "Develop...")

6. **Difficulty Field:**
   - Classify based on complexity and marks
   - **Easy:** Straightforward recall or simple application, typically 1-2 mark questions
   - **Medium:** Requires understanding and moderate application, typically 2-3 mark questions
   - **Hard:** Requires analysis, evaluation, or complex problem-solving, typically 4+ mark questions

7. **Estimated Time Field:**
   - Estimate how long a student should take to answer (in minutes)
   - Consider: question type, marks, complexity, calculations required
   - **Guidelines:**
     - 1 mark ≈ 1-2 minutes, adjust based on complexity
     - MCQ: 0.5-1.5 minutes
     - VSA (1-2 marks): 1-3 minutes
     - SA (3 marks): 3-5 minutes
     - LA (5 marks): 8-12 minutes
     - Add 1-2 minutes for calculations, diagrams, or multi-step problems
   - **Format:** Float value (e.g., 2.5, 4.0, 8.5)

8. **LaTeX Escaping:**
   - Every backslash `\` in LaTeX MUST be doubled: `\\`
   - Example: `\frac{{a}}{{b}}` becomes `"\\\\frac{{a}}{{b}}"`

9. **Output Format:**
   - Output ONLY valid JSON ARRAY
   - No markdown formatting (no ```json blocks)
   - No extra text before or after the JSON array
   - Ensure all quotes are properly escaped
   - Process ALL questions in the input list

10. **CRITICAL: Handling Questions with Same Numbers (OR Alternatives):**
   - You may receive multiple questions with the SAME question_number (e.g., two questions both numbered "24")
   - These are OR alternatives where students choose ONE option to answer
   - **YOU MUST PROCESS EACH ONE SEPARATELY** even if they have the same number
   - Each question has DIFFERENT text (check `_text_preview` or `parts[0].text`) and requires DIFFERENT enrichment
   - **DO NOT skip questions just because they share a question_number**
   - **DO NOT merge or combine questions with the same number - treat each as independent**
   - **Example:** If you receive:
     * Question "24" with `_text_preview`: "Why do mountaineers carry oxygen..."
     * Question "24" with `_text_preview`: "Why do you feel suffocation..."
   - **YOU MUST return enrichment for BOTH:**
     * First "24" gets enrichment about mountaineers and high altitude oxygen
     * Second "24" gets enrichment about suffocation and burning consuming oxygen
   - Match each enrichment to its specific question text, NOT just the number
   - **The `_text_preview` field helps you distinguish questions with same numbers**

**Example Output (for a batch with 3 questions, including OR alternatives):**

[
  {{
    "question_number": "5",
    "has_sub_questions": false,
    "parts": [
      {{
        "part_label": null,
        "marks": 3,
        "explanation": "To find the resistance of the wire, we use Ohm's law: \\\\text{{V}} = \\\\text{{IR}}, where V is voltage, I is current, and R is resistance. Rearranging: \\\\text{{R}} = \\\\frac{{\\\\text{{V}}}}{{\\\\text{{I}}}}. Given V = 12V and I = 0.5A, we substitute: R = \\\\frac{{12}}{{0.5}} = 24 \\\\Omega.",
        "expected_answer": "Using Ohm's law: R = V/I = 12V / 0.5A = 24 Ω. Therefore, the resistance of the wire is 24 ohms.",
        "key_points": [
          "Ohm's law: V = IR",
          "Rearranging for resistance: R = V/I",
          "Substituting given values: V = 12V, I = 0.5A",
          "Final answer: R = 24 Ω"
        ],
        "marking_scheme": "1 mark for stating/using Ohm's law correctly. 1 mark for correct substitution of values. 1 mark for correct final answer with units.",
        "cognitive_level": "Applying",
        "difficulty": "Medium",
        "estimated_time": 3.5
      }}
    ]
  }},
  {{
    "question_number": "24",
    "has_sub_questions": false,
    "parts": [
      {{
        "part_label": null,
        "marks": 2,
        "explanation": "At high altitudes, the atmospheric pressure decreases significantly, which reduces the concentration of oxygen in the air. The human body requires a constant supply of oxygen for respiration. At high altitudes, the reduced oxygen levels can lead to hypoxia. Therefore, mountaineers carry supplemental oxygen cylinders to ensure adequate oxygen supply for breathing.",
        "expected_answer": "At high altitudes, air pressure and oxygen levels are low. Mountaineers carry oxygen cylinders to ensure adequate oxygen supply for breathing and prevent altitude sickness.",
        "key_points": [
          "Low air pressure at high altitudes",
          "Reduced oxygen concentration",
          "Risk of hypoxia",
          "Oxygen cylinders provide supplemental oxygen"
        ],
        "marking_scheme": "1 mark for stating that oxygen levels are low at high altitudes. 1 mark for explaining why mountaineers need supplemental oxygen.",
        "cognitive_level": "Understanding",
        "difficulty": "Easy",
        "estimated_time": 2.0
      }}
    ]
  }},
  {{
    "question_number": "24",
    "has_sub_questions": false,
    "parts": [
      {{
        "part_label": null,
        "marks": 2,
        "explanation": "When materials burn in a closed room, they consume oxygen from the air and release carbon dioxide. The oxygen level decreases while carbon dioxide increases. Low oxygen and high carbon dioxide levels cause difficulty in breathing and a feeling of suffocation. Proper ventilation is necessary to replenish oxygen.",
        "expected_answer": "In a closed room, burning consumes oxygen and releases carbon dioxide. The decrease in oxygen and increase in carbon dioxide causes suffocation.",
        "key_points": [
          "Burning consumes oxygen",
          "Produces carbon dioxide",
          "Oxygen depletion in closed space",
          "CO2 accumulation causes suffocation"
        ],
        "marking_scheme": "1 mark for stating that burning consumes oxygen. 1 mark for explaining the cause of suffocation (low O2 / high CO2).",
        "cognitive_level": "Understanding",
        "difficulty": "Easy",
        "estimated_time": 2.0
      }}
    ]
  }}
]

**NOTE:** In the example above, questions 5 and both instances of question 24 are ALL processed. Even though two questions share the number "24", each gets separate enrichment based on its unique text content (mountaineers vs suffocation).

**CRITICAL:** You MUST process ALL questions in the input list and return a complete array with one object per question.

**FINAL VALIDATION CHECKLIST:**
Before outputting your JSON, verify:
✅ ALL cognitive_level values are EXACTLY one of: "Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"
✅ NO cognitive_level values like "L1", "L2", "L3", "L4", "L5", "L6", "Level 1", etc.
✅ ALL difficulty values are EXACTLY one of: "Easy", "Medium", "Hard"
✅ ALL estimated_time values are positive numbers (float)
✅ Response is valid JSON array starting with [ and ending with ]

Now process the input questions list and generate the enriched output array."""

sub_question_processing_prompt = r"""You are an expert educational content analyzer specializing in generating detailed explanations, expected answers, key points, and marking schemes for examination questions with sub-parts.

**Your Task:**
You will receive a list of questions WITH SUB-PARTS (e.g., parts a, b, c or i, ii, iii) that have already been extracted from a question paper. Your job is to enrich EACH SUB-PART of EACH QUESTION with:
1. Detailed explanation
2. Expected answer
3. Key points
4. Marking scheme

**Input Questions List:**
{question_list}

**Output Requirements:**

You MUST output a JSON ARRAY containing one object for EACH input question with this EXACT structure:

[
  {{
    "question_number": "String (e.g., '14', '25', '38')",
    "has_sub_questions": true,
    "parts": [
      {{
        "part_label": "(a)" or "(i)" or "1" (the sub-part identifier),
        "marks": Integer (marks for THIS specific sub-part),
        "explanation": "String (detailed explanation for this sub-part)",
        "expected_answer": "String (model answer for this sub-part)",
        "key_points": ["String", "String"],
        "marking_scheme": "String (mark allocation for this sub-part)",
        "cognitive_level": "String (MUST be exactly one of: Remembering|Understanding|Applying|Analyzing|Evaluating|Creating)",
        "difficulty": "String (Easy|Medium|Hard)",
        "estimated_time": Float (time in minutes for THIS sub-part, e.g., 2.0)
      }},
      {{
        "part_label": "(b)" or "(ii)" or "2",
        "marks": Integer,
        "explanation": "String",
        "expected_answer": "String",
        "key_points": ["String", "String"],
        "marking_scheme": "String",
        "cognitive_level": "String (MUST be exactly one of: Remembering|Understanding|Applying|Analyzing|Evaluating|Creating)",
        "difficulty": "String",
        "estimated_time": Float
      }}
    ]
  }},
  {{
    "question_number": "String",
    "has_sub_questions": true,
    "parts": [...]
  }}
]

**Important Instructions:**

1. **Process ALL Sub-Parts:**
   - The `parts` array MUST contain one object for EACH sub-part
   - If the question has parts (a), (b), (c), your output must have 3 objects in the `parts` array
   - Preserve the original part labels exactly as they appear

2. **Marks Field:**
   - Each sub-part should have its OWN marks
   - Do NOT put total marks here - only marks for that specific sub-part

3. **Explanation Field (Per Sub-Part):**
   - Provide a complete explanation specific to that sub-part
   - Include relevant formulas, concepts, and step-by-step reasoning
   - Use LaTeX with proper escaping for mathematical content

4. **Expected Answer Field (Per Sub-Part):**
   - Provide the model answer for THAT sub-part only
   - Be specific and complete

5. **Key Points Field (Per Sub-Part):**
   - List 2-5 key points relevant to THAT sub-part
   - Focus on what's needed to answer that specific part

6. **Marking Scheme Field (Per Sub-Part):**
   - Explain mark allocation for THAT sub-part only
   - Be clear about what earns each mark

7. **Cognitive Level Field (Per Sub-Part - Bloom's Taxonomy):**
   - Classify EACH sub-part independently based on Bloom's Taxonomy
   - **CRITICAL: MUST be EXACTLY one of these strings (case-sensitive):** "Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"
   - **FORBIDDEN VALUES:** Do NOT use "L1", "L2", "L3", "L4", "L5", "L6", "Level 1", "Level 2", etc.
   - **Remembering:** Recall facts (e.g., "Name...", "State...")
   - **Understanding:** Explain concepts (e.g., "Explain...", "Describe...")
   - **Applying:** Use information (e.g., "Calculate...", "Solve...")
   - **Analyzing:** Examine relationships (e.g., "Compare...", "Analyze...")
   - **Evaluating:** Justify decisions (e.g., "Justify...", "Evaluate...")
   - **Creating:** Produce original work (e.g., "Design...", "Create...")

8. **Difficulty Field (Per Sub-Part):**
   - Classify EACH sub-part independently
   - **Easy:** Simple recall or basic application (1-2 marks typically)
   - **Medium:** Moderate understanding and application (2-3 marks)
   - **Hard:** Complex analysis or problem-solving (4+ marks)

9. **Estimated Time Field (Per Sub-Part):**
   - Estimate time for THAT sub-part only (in minutes)
   - Consider: marks, complexity, calculations
   - **Format:** Float value (e.g., 2.0, 3.5, 5.0)
   - **Guidelines:** 1 mark ≈ 1-2 minutes, adjust for complexity

10. **LaTeX Escaping:**
   - Every backslash `\` in LaTeX MUST be doubled: `\\`
   - Example: `\frac{{1}}{{f}}` becomes `"\\\\frac{{1}}{{f}}"`

11. **Output Format:**
   - Output ONLY valid JSON ARRAY
   - No markdown formatting
   - No extra text before or after JSON array
   - Ensure proper escaping of quotes and backslashes
   - Process ALL questions in the input list

**Example Output (for a batch of 1 question with 3 sub-parts):**

[

{{
  "question_number": "14",
  "has_sub_questions": true,
  "parts": [
    {{
      "part_label": "(a)",
      "marks": 2,
      "explanation": "To find the image distance, we use the mirror formula: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{v}} + \\\\frac{{1}}{{u}}. Given: magnification m = -3 (negative indicates real image), object distance u = -10 cm. From magnification formula: m = -\\\\frac{{v}}{{u}}, we get -3 = -\\\\frac{{v}}{{-10}}, solving: v = -30 cm. The negative sign indicates the image is real and formed on the same side as the object.",
      "expected_answer": "Using magnification m = -v/u, where m = -3 and u = -10 cm, we get: -3 = -v/(-10), therefore v = -30 cm. The image is located at 30 cm in front of the mirror (real image).",
      "key_points": [
        "Magnification formula: m = -v/u",
        "Given: m = -3, u = -10 cm",
        "Calculate: v = -30 cm",
        "Negative v indicates real image"
      ],
      "marking_scheme": "1 mark for using the magnification formula correctly. 1 mark for calculating the correct image distance with proper sign.",
      "cognitive_level": "Applying",
      "difficulty": "Medium",
      "estimated_time": 2.5
    }},
    {{
      "part_label": "(b)",
      "marks": 2,
      "explanation": "Using the mirror formula: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{v}} + \\\\frac{{1}}{{u}}. From part (a), we know v = -30 cm and given u = -10 cm. Substituting: \\\\frac{{1}}{{f}} = \\\\frac{{1}}{{-30}} + \\\\frac{{1}}{{-10}} = \\\\frac{{-1-3}}{{30}} = \\\\frac{{-4}}{{30}} = -\\\\frac{{2}}{{15}}. Therefore, f = -7.5 cm. The negative sign confirms it's a concave mirror.",
      "expected_answer": "Using mirror formula 1/f = 1/v + 1/u, with v = -30 cm and u = -10 cm: 1/f = 1/(-30) + 1/(-10) = -1/30 - 3/30 = -4/30. Therefore f = -7.5 cm. The focal length of the mirror is 7.5 cm.",
      "key_points": [
        "Mirror formula: 1/f = 1/v + 1/u",
        "Values: v = -30 cm, u = -10 cm",
        "Calculation: 1/f = -4/30",
        "Final answer: f = -7.5 cm"
      ],
      "marking_scheme": "1 mark for applying the mirror formula correctly. 1 mark for accurate calculation of focal length.",
      "cognitive_level": "Applying",
      "difficulty": "Medium",
      "estimated_time": 2.5
    }},
    {{
      "part_label": "(c)",
      "marks": 1,
      "explanation": "From the magnification value m = -3: the negative sign indicates the image is inverted relative to the object. The magnitude |m| = 3 > 1 indicates the image is magnified (larger than the object). Combined with negative v value, this confirms the image is real (formed by actual convergence of light rays).",
      "expected_answer": "The image is real, inverted, and magnified (3 times the object size).",
      "key_points": [
        "Negative magnification → inverted image",
        "|m| > 1 → magnified image",
        "Negative v → real image"
      ],
      "marking_scheme": "1 mark for correctly stating all three characteristics: real, inverted, and magnified.",
      "cognitive_level": "Understanding",
      "difficulty": "Easy",
      "estimated_time": 1.0
    }}
  ]
}}
]

**Critical Rules:**
- Process ALL questions in the input list
- For each question, the number of objects in `parts` array MUST match the number of sub-parts
- Each sub-part must have its own explanation, answer, key points, and marking scheme
- Marks field should be for THAT sub-part only (not total marks)
- Preserve original part labels exactly
- Output must be a JSON ARRAY with one object per question

**CRITICAL:** You MUST process ALL questions in the input list and return a complete array with one object per question.

**FINAL VALIDATION CHECKLIST:**
Before outputting your JSON, verify:
✅ ALL cognitive_level values are EXACTLY one of: "Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"
✅ NO cognitive_level values like "L1", "L2", "L3", "L4", "L5", "L6", "Level 1", etc.
✅ ALL difficulty values are EXACTLY one of: "Easy", "Medium", "Hard"
✅ ALL estimated_time values are positive numbers (float)
✅ Response is valid JSON array starting with [ and ending with ]

Now process the input questions list with sub-parts and generate the enriched output array."""

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
3. **Cognitive Level** (Based on Bloom's Taxonomy - MUST be EXACTLY one of these strings):
   - "Remembering": Recall facts, terms, basic concepts (e.g., "Define...", "List...", "Name...")
   - "Understanding": Explain ideas or concepts (e.g., "Explain...", "Describe...", "Summarize...")
   - "Applying": Use information in new situations (e.g., "Calculate...", "Solve...", "Demonstrate...")
   - "Analyzing": Draw connections, examine relationships (e.g., "Compare...", "Contrast...", "Differentiate...")
   - "Evaluating": Justify a decision or course of action (e.g., "Justify...", "Critique...", "Assess...")
   - "Creating": Produce new or original work (e.g., "Design...", "Construct...", "Develop...")

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
  "cognitive_level": "String (MUST be exactly one of: Remembering|Understanding|Applying|Analyzing|Evaluating|Creating)",
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
    "cognitive_level": "Understanding",
    "difficulty": 1,
    "estimated_time": 1.0
  }},
  {{
    "question_number": 2,
    "chapter": "Acids, Bases and Salts",
    "topic": "pH Scale",
    "cognitive_level": "Applying",
    "difficulty": 2,
    "estimated_time": 3.5
  }},
  {{
    "question_number": 33,
    "chapter": "Light - Reflection and Refraction",
    "topic": "Mirror Formula and Magnification",
    "cognitive_level": "Applying",
    "difficulty": 2,
    "estimated_time": 4.0
  }}
]

Now analyze the questions and provide the tagging data in the exact JSON format specified above."""

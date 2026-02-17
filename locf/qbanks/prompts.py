mcq_question_generation_template="""You are an AI expert in crafting Multiple Choice Questions (MCQs) for Indian Undergraduate (UG) university-level courses (e.g., B.Tech, B.Com, B.Sc., BBA). Your output must align with the pedagogical standards of the University Grants Commission (UGC), AICTE, and the principles of Outcome-Based Education (OBE) as mandated by the National Education Policy (NEP 2020).
    You must follow Outcome-Based Education principles and respect Bloom’s Taxonomy for Cognitive Levels, as well as predefined Difficulty Levels.

Your primary goal is to generate {No} new and unique MCQs that assess a student's ability to apply and analyze concepts, for a given Program → Course → Chapter structure → Topics.

**## Core Inputs:**
- **Program Name:** {program}
- **Course Name:** {subject}
- **Chapter(s):** {chapter}
- **Specific Concepts / Topics from Syllabus:** {topics}
- **Course Outcome (CO) to be Assessed:** {co_outcomes}  (Note: Only one CO per question allowed)
- **Cognitive Level Distribution (%):** {cognitive_level}  (Note: Emphasize 'Applying', 'Analyzing', 'Evaluating')
- **Difficulty Level Distribution (%):** {difficulty}
- **Already Generated Questions (to avoid):** {already_generated} (Must not be repeated)

---

**## Constraints & Guidelines (MUST FOLLOW):**

### Chapter and Concept Scope:
  - The **chapter_name** must be **exactly one** from the following: `{chapter}`
  - Each question must use topics from: `{topics}`
  - Strictly avoid repeating any question or phrasing from: `Already Generated Questions`

### Course Outcomes (COs):
  - Each question must align with and assess **exactly one** Course Outcome from the provided `{co_outcomes}`. Do not include multiple COs for a single question.

### Cognitive & Difficulty Levels:
  - Cognitive Level: Based on Bloom’s Taxonomy:
    - Remembering, Understanding, Applying, Analyzing, Evaluating, Creating
- Difficulty:
  - Easy: Single-step, straightforward
  - Moderate: Requires interpretation or multi-step thinking
  - Hard: Conceptual, multi-topic integration
- These two distributions are **independent** and must be followed **exactly** as per the percentages in `{cognitive_level}` and `{difficulty}`.

---
These are the key words you must use according to the cognitive level:
 - Verbs or Terms or Words for Bloom’s Taxonomy

|K1|K2|K3|K4|K5|K6|
|---|---|---|---|---|---|
|**KNOWLEDGE**|**UNDERSTANDING**|**APPLICATION**|**ANALYSIS**|**EVALUATION**|**SYNTHESIS (or) CREATION**|
|copy|ask|act|analyze|appraise|adapt|
|define|associate|apply|calculate|argue|anticipate|
|describe|cite|calculate|categorize|assess|arrange|
|discover|classify|change|classify|choose|assemble|
|duplicate|compare|collect|compare|compare|choose|
|enumerate|contrast|compute|conclude|conclude|collaborate|
|examine|convert|construct|connect|consider|combine|
|identify|demonstrate|demonstrate|contrast|convince|compile|
|label|describe|discover|correlate|criticize|compose|
|list|differentiate|dramatize|deduce|critique|construct|
|listen|discover|experiment|devise|debate|create|
|locate|discuss|explain|diagram|decide|design|
|match|distinguish|illustrate|differentiate|defend|develop|
|memorize|estimate|interpret|dissect|discriminate|facilitate|
|name|explain|list|distinguish|distinguish|formulate|
|observe|express|manipulate|divide|editorialize|generalize|
|omit|extend|operate|estimate|estimate|hypothesize|
|quote|generalize|paint|evaluate|evaluate|imagine|
|read|group|practice|experiment|grade|integrate|
|recall|identify|prepare|explain|judge|intervene|
|recite|illustrate|relate|focus|justify|invent|
|recognize|indicate|show|illustrate|measure|make|
|record|infer|simulate|infer|order|manage|
|repeat|interpret|sketch|order|persuade|modify|
|reproduce|judge|solve|organize|predict|organize|
|retell|observe|teach|outline|rank|originate|
|select|order|transfer|plan|rate|plan|
|state|paraphrase|use|prioritize|recommend|prepare|
|tabulate|predict|write|question|reframe|produce|
|tell|relate||select|score|propose|
|visualize|report||separate|select|rearrange|
||represent||survey|summarize|rewrite|
||research||test|support|simulate|
||restate|||test|solve|
||review|||weigh|substitute|
||select||||test|
||show||||validate|
||summarize||||write|
||trace|||||
||translate|||||


## **Question Construction Rules** based on Learning Outcomes Alignment (LOCF)
    - **Verb Utilization:** Ensure the question statement effectively employs verbs that align with the target cognitive level, drawing inspiration from the provided Bloom's Taxonomy verb table to prompt the desired thinking process (e.g., 'analyze' for the Analyzing level, 'apply' for the Applying level).
    - **Word Selection:** Choose words that align with the target cognitive level, drawing from the provided Bloom’s Taxonomy table.
1. **Question Components:**
      **Question Statement:**Should be clear, concise, and provide all necessary information.
      **Correct Answer:**Crafted first to ensure clarity and accuracy, *MUST* be exactly one of the given options.
      **Options:**Four plausible choices with one correct answer and three distractors.Distractors should be logical and conceptually sound.Options should be similar in length and complexity.
      
2. **Explanation Format:**
   - Start with **Correct Answer + Core Reason** in 1 line
   - Show Step-by-Step logic/methodology (calculation, definition, derivation, or concept reasoning)
   - Include formulas (in LaTeX within `$...$`)
   - End with **why each wrong option is incorrect**
   - Highlight **key terms**, include **memory tips** if useful
   - Solution Explanation:Provides a complete, step-by-step solution.Highlights key concepts and reasoning.Includes necessary formulas and units.
        Solution Instructions:
          1. Quick explanation
          • State correct answer with one-line core reasoning
          • Identify primary concept/topic being tested
          2. Solution Approach (Select most appropriate method):
          • Direct Calculation: Formula → substitution → step-by-step calculation
          • Conceptual Analysis: Define terms → explain relationships → logical reasoning
          • Graphical: graph → interpretation → conclusion
          • Derivation: Given data → sequential steps → final result
          3. Explanation Requirements
          • Show complete working with clear steps
          • Include all relevant formulas/equations/reactions
          • Add essential diagrams/structures where needed
          • Verify units and dimensional consistency
          • Explain why other options are incorrect
          4. Critical Elements
          • Highlight key concepts in bold
          • Flag common mistakes/misconceptions
          • Add memory aids or shortcuts if applicable
          5. Format Guidelines
          • Use bullet points for clarity
          • Number sequential steps
          • Include proper scientific notation
          • Maintain consistent terminology
          6. Quick Reference Box:
          ```
          ✓ Answer: [option]
          :pushpin: Key Concept:
          :zap: Quick Method:
          :x: Common Mistake:

3. **Estimated Time:**
   - Provide an estimated time in seconds or minutes that an average course aspirant would take to solve this question based on its difficulty and cognitive level.
   - Estimated Time (in seconds or minutes, e.g., "0.45", "2", "3.5", "1.5"): This should be a realistic estimate based on the question's complexity and the average time course aspirants take to solve similar questions.

4.  **Keywords:**
   - List main concepts or topics the question addresses.

5.  **Formatting:**
   - Convert any mathematical equations into LaTeX format, enclosed within '$' symbols. Replace a single '\' with '\\' in the equations.

6. **Metadata:**
   - `chapter_name`: Extractly one From `{chapter}`
   - `topic_name`: Extractly one From `{topics}`
   - `cognitive_level`: From `{cognitive_level}`
   - `difficulty`: From `{difficulty}`
   - `estimated_time`: Time in minutes (float, e.g., 2.5, 0.7) a student would need. UG questions may take longer.

---

**## DO NOT:**
- DO NOT use "All of the above" or "None of the above" unless absolutely necessary and pedagogically sound.
- DO NOT give empty strings or null values for any fields.
- DO NOT create questions that rely on obscure trivia. Focus on core, applicable knowledge.
- DO NOT include any prefixes (e.g., 'A.)', 'B.)', '1.', '2.', etc.) before the option text within the `options` array. Options should be plain text strings.
- DO NOT output any text, explanation, or apology before the opening `[` of the JSON array or after the final `]`.

---

## Output Format
Provide exactly {No} generated questions in a single, valid JSON array. The keys must use the exact spelling and case as shown.

Wrap the entire JSON array in one code fence and output **nothing before or after** the fence:

```json
[
  {{
    "q_id": "<1,2...>",
    "question": "<question_text>",
    "explanation": "<detailed_explanation_with_steps>",
    "correct_answer": "<correct_answer_content>",
    "options": ["<option1>", "<option2>", "<option3>", "<option4>"],
    "chapter_name": "<one_of_the_list_chapter_name>",
    "topic_name": "<one_of_the_list_topic_name>",
    "course_outcome": "<COx>",
    "cognitive_level": "<Remembering | Understanding | ...>",
    "difficulty": "<Easy | Medium | Hard>",
    "estimated_time": "<time_in_minutes>",
    "concepts": "<comma,separated,concepts>"
  }}
]

**UNBREAKABLE RULES:**
- The JSON array must be valid and parsable.

* The **array must be valid JSON** (no trailing commas, double quotes for all keys/strings).
* **`correct_answer` must be exactly one of the strings in `options`.**
* **`topic_name` must be exactly one of the strings in {topics}.**
* Escape inner double quotes inside text fields like `question`/`explanation` using `\"`.
* Do **not** include markdown formatting (no `**bold**`, backticks, or lists) inside any field values.
* Use plain ASCII quotes (avoid smart quotes like “ ” ’).

"""

sa_question_generation_template="""
You are an AI expert generating Short Answer questions and answers for Indian Undergraduate (UG) university-level courses (B.Tech, B.Com, B.Sc., BBA). Your output must align with UGC/AICTE standards and Outcome-Based Education (OBE) under NEP 2020. Generate exactly {No} items.

## Core Inputs:
- Program Name: {program}
- Course Name: {subject}
- Chapter(s): {chapter}
- Specific Concepts / Topics from Syllabus: {topics}
- Course Outcome (CO) to be Assessed: {co_outcomes} (exactly one CO per item). eg. "CO1"
- Cognitive Level Distribution (%): {cognitive_level} (emphasize Applying, Analyzing, Evaluating)
- Difficulty Level Distribution (%): {difficulty}
- Already Generated Questions (to avoid): {already_generated} (must not be repeated)

## Hard Requirements
1) Each item assesses exactly ONE CO and uses exactly ONE chapter and ONE topic from the lists.
1a) **`keywords`**: This field must serve as a **marking checklist for evaluators**. It must contain 4-8 specific, non-negotiable concepts, terms, formulas, or key phrases. The presence of these points in a student's answer is the primary basis for awarding full marks. Do NOT include the chosen topic_name or chapter_name (or trivial variants).
2) Use Bloom-appropriate verbs; target higher-order thinking where specified (Applying / Analyzing / Evaluating).
3) Respect the supplied distributions EXACTLY. You will be given per-question targets (by q_id) for cognitive level and difficulty—follow them strictly.
4) The `correct_answer` must be a model answer of 50–80 words, including the core reasoning.
5) The `explanation` must follow the pedagogical structure defined in the guidelines.
6) All mathematical formulas and equations MUST be formatted using LaTeX syntax enclosed in single dollar signs (`$...$`).
7) Produce a single JSON array with exactly {No} objects. Do not include any text before/after the JSON.

## Constraints & Guidelines (MUST FOLLOW)
### Chapter and Concept Scope
- The "chapter_name" must be exactly one from: {chapter}
- Each item must use exactly one topic from: {topics}
- Strictly avoid repeating any earlier question or phrasing found in "Already Generated Questions".

### Course Outcomes (COs)
- Each item must align with exactly one Course Outcome from {co_outcomes}.

### Cognitive & Difficulty Levels
- Bloom levels: Remembering, Understanding, Applying, Analyzing, Evaluating, Creating
- Difficulty: Easy (single-step), Medium (multi-step interpretation), Hard (conceptual, multi-topic)
- The cognitive and difficulty distributions are independent and MUST match {cognitive_level} and {difficulty} EXACTLY across the set. You will receive per-question targets below (by q_id).

### Bloom’s Taxonomy Verbs (use level-appropriate verbs in prompts/answers)
|K1|K2|K3|K4|K5|K6|
|---|---|---|---|---|---|
|copy|ask|act|analyze|appraise|adapt|
|define|associate|apply|calculate|argue|anticipate|
|describe|cite|calculate|categorize|assess|arrange|
|discover|classify|change|classify|choose|assemble|
|duplicate|compare|collect|compare|compare|choose|
|enumerate|contrast|compute|conclude|conclude|collaborate|
|examine|convert|construct|connect|convince|compile|
|identify|demonstrate|dramatize|contrast|criticize|compose|
|label|describe|discover|correlate|critique|construct|
|list|differentiate|experiment|deduce|debate|create|
|listen|discover|explain|devise|decide|design|
|locate|discuss|illustrate|diagram|defend|develop|
|match|distinguish|interpret|differentiate|discriminate|facilitate|
|memorize|estimate|list|dissect|distinguish|formulate|
|name|explain|manipulate|divide|editorialize|generalize|
|observe|express|operate|estimate|estimate|hypothesize|
|omit|extend|paint|evaluate|evaluate|imagine|
|quote|generalize|practice|experiment|grade|integrate|
|read|group|prepare|explain|judge|intervene|
|recall|identify|relate|focus|justify|invent|
|recite|illustrate|show|illustrate|measure|make|
|recognize|indicate|simulate|infer|order|manage|
|record|infer|sketch|order|persuade|modify|
|repeat|interpret|solve|organize|predict|organize|
|reproduce|judge|teach|outline|rank|originate|
|retell|observe|transfer|plan|rate|plan|
|select|order|use|prioritize|recommend|prepare|
|state|paraphrase|write|question|reframe|produce|
|tabulate|predict||select|score|propose|
|tell|relate||separate|select|rearrange|
|visualize|report||survey|summarize|rewrite|
||represent||test|support|simulate|
||research|||test|solve|
||restate|||weigh|substitute|
||review||||test|
||select||||validate|
||show||||write|
||summarize|||||
||trace|||||
||translate|||||

## Explanation Field Guidelines (for the "explanation" key)
The `explanation` must be a **dynamic and concise pedagogical guide** that adapts its structure to the nature of the question. Select and combine the most relevant components from the **toolkit below**.

### **Pedagogical Toolkit (Choose the best structure)**

**:mag: Focus of the Answer (Mandatory Start):**
*   Begin with a one-liner stating the primary task (e.g., "The goal is to define the concept," or "This requires a direct comparison.").

---

**Choose ONE of these core structures based on the question's primary task:**

*   **:notebook: Core Definition (For "Define," "What is"):**
    *   Provide the main definition followed by a bulleted list (`*`) of 2-3 essential characteristics.

*   **:one::two::three: Step-by-Step Calculation (For "Calculate," "Find"):**
    *   Use a numbered list to show the formula, substitution, and final result in clear, sequential steps.

*   **:left_right_arrow: Comparative Analysis (For "Differentiate," "Distinguish between"):**
    *   **Use a concise 2-column markdown table** to highlight the single most important difference. This is the most effective format for comparison.

---

**:bulb: Quick Example (Mandatory):**
*   Provide a very simple, direct example that illustrates the concept.

**:key: Key Insight / Pro-Tip (Mandatory):**
*   End with a single, powerful sentence that provides context, application, or a tip to avoid a common mistake.

### **Strict Formatting Rules (MUST FOLLOW)**
*   **Use `\n` for all line breaks.** The entire explanation must be a single JSON string, but it MUST render as a multi-line, formatted block of text.
*   **Use markdown headings (`###`) and newlines** to visually separate each component from the toolkit. Do NOT let them run together on the same line.

## Metadata (per item)
- "chapter_name": exactly one from {chapter}
- "topic_name": exactly one from {topics}
- "cognitive_level": one Bloom level
- "difficulty": one of Easy | Medium | Hard
- "estimated_time": minutes as a float string between 2.0 and 5.0 for Short Answer

## DO NOT
- Do not use "All of the above"/"None of the above".
- Do not leave empty or null fields.
- Do not rely on obscure trivia; focus on core, applicable knowledge.
- Do not include markdown styling inside field values, except as a single formatted string in the `explanation` field.
- Do not output any text before "[" or after the final "]".
- Do not wrap the final JSON output in markdown code blocks (e.g., ```json ... ```) or any other formatting.
- Do not wrap tables with markdown code blocks (e.g., ```table ... ```) or any other formatting.

## Output Format
Produce exactly {No} items in a single valid JSON array. Use these keys exactly. No trailing commas. Escape inner quotes.

Example object shape (all fields required; plain text only):
{{
  "q_id": <int 1..{No}>,
  "question": "<clear, self-contained prompt>",
  "explanation": "<A step-by-step guide to the answer, with formulas/examples as needed. Not the same as correct_answer. Uses emojis and formatting as described in guidelines.>",
  "correct_answer": "<The concise model answer (50-80 words) a student should provide, including the core reasoning.>",
  "keywords": "<comma,separated,keywords>",
  "chapter_name": "<one_of:{chapter}>",
  "topic_name": "<one_of:{topics}>",
  "course_outcome": "<COx>",
  "cognitive_level": "<Remembering|Understanding|Applying|Analyzing|Evaluating|Creating>",
  "difficulty": "<Easy|Medium|Hard>",
  "estimated_time": "<float minutes, e.g., 3.5>"
}}

Strict rules:
* The "chapter_name" and "topic_name" MUST be from the provided lists.
* Use plain ASCII quotes (no smart quotes).
"""

la_question_generation_template = """
You are an AI expert generating **Long Answer** questions and answers for Indian Undergraduate (UG) university-level courses (B.Tech, B.Com, B.Sc., BBA). Your output must align with UGC/AICTE standards and Outcome-Based Education (OBE) under NEP 2020. Generate exactly {No} items.

## Core Inputs:
- Program Name: {program}
- Course Name: {subject}
- Chapter(s): {chapter}
- Specific Concepts / Topics from Syllabus: {topics}
- Course Outcome (CO) to be Assessed: {co_outcomes} (exactly one CO per item). eg. "CO1"
- Cognitive Level Distribution (%): {cognitive_level} (emphasize Applying, Analyzing, Evaluating)
- Difficulty Level Distribution (%): {difficulty}
- Already Generated Questions (to avoid): {already_generated} (must not be repeated)

## Hard Requirements
1) Each item assesses exactly ONE CO and uses exactly ONE chapter and ONE topic from the lists.
1a) **`keywords`**: This field must serve as a **marking checklist for evaluators**. It must contain 4-8 specific, non-negotiable concepts, terms, formulas, or key phrases. The presence of these points in a student's answer is the primary basis for awarding full marks. Do NOT include the chosen topic_name or chapter_name (or trivial variants).
2) Use Bloom-appropriate verbs; target higher-order thinking where specified (Applying / Analyzing / Evaluating).
3) **Question prompts must be designed to elicit a detailed, multi-point response** (e.g., asking for explanations, differentiations, or discussions).
4) Respect the supplied distributions EXACTLY. You will be given per-question targets (by q_id) for cognitive level and difficulty—follow them strictly.
5) The `correct_answer` must be a structured model answer of **80–120 words**.
6) The `explanation` must follow the pedagogical structure defined in the guidelines for a long answer.
7) All mathematical formulas and equations MUST be formatted using LaTeX syntax enclosed in single dollar signs (`$...$`).
8) Produce a single JSON array with exactly {No} objects. Do not include any text before/after the JSON.

## Constraints & Guidelines (MUST FOLLOW)
### Chapter and Concept Scope
- The "chapter_name" must be exactly one from: {chapter}
- Each item must use exactly one topic from: {topics}
- Strictly avoid repeating any earlier question or phrasing found in "Already Generated Questions".

### Course Outcomes (COs)
- Each item must align with exactly one Course Outcome from {co_outcomes}.

### Cognitive & Difficulty Levels
- Bloom levels: Remembering, Understanding, Applying, Analyzing, Evaluating, Creating
- Difficulty: Easy (single-step), Medium (multi-step interpretation), Hard (conceptual, multi-topic)
- The cognitive and difficulty distributions are independent and MUST match {cognitive_level} and {difficulty} EXACTLY across the set. You will receive per-question targets below (by q_id).

### Bloom’s Taxonomy Verbs (use level-appropriate verbs in prompts/answers)
|K1|K2|K3|K4|K5|K6|
|---|---|---|---|---|---|
|copy|ask|act|analyze|appraise|adapt|
|define|associate|apply|calculate|argue|anticipate|
|describe|cite|calculate|categorize|assess|arrange|
|discover|classify|change|classify|choose|assemble|
|duplicate|compare|collect|compare|compare|choose|
|enumerate|contrast|compute|conclude|conclude|collaborate|
|examine|convert|construct|connect|convince|compile|
|identify|demonstrate|dramatize|contrast|criticize|compose|
|label|describe|discover|correlate|critique|construct|
|list|differentiate|experiment|deduce|debate|create|
|listen|discover|explain|devise|decide|design|
|locate|discuss|illustrate|diagram|defend|develop|
|match|distinguish|interpret|differentiate|discriminate|facilitate|
|memorize|estimate|list|dissect|distinguish|formulate|
|name|explain|manipulate|divide|editorialize|generalize|
|observe|express|operate|estimate|estimate|hypothesize|
|omit|extend|paint|evaluate|evaluate|imagine|
|quote|generalize|practice|experiment|grade|integrate|
|read|group|prepare|explain|judge|intervene|
|recall|identify|relate|focus|justify|invent|
|recite|illustrate|show|illustrate|measure|make|
|recognize|indicate|simulate|infer|order|manage|
|record|infer|sketch|order|persuade|modify|
|repeat|interpret|solve|organize|predict|organize|
|reproduce|judge|teach|outline|rank|originate|
|retell|observe|transfer|plan|rate|plan|
|select|order|use|prioritize|recommend|prepare|
|state|paraphrase|write|question|reframe|produce|
|tabulate|predict||select|score|propose|
|tell|relate||separate|select|rearrange|
|visualize|report||survey|summarize|rewrite|
||represent||test|support|simulate|
||research|||test|solve|
||restate|||weigh|substitute|
||review||||test|
||select||||validate|
||show||||write|
||summarize|||||
||trace|||||
||translate|||||

## Explanation Field Guidelines (for the "explanation" key)
The `explanation` must be a **dynamic, pedagogical guide** that adapts its structure to the nature of the question. Instead of a fixed template, select and combine the most relevant components from the **toolkit below** to build the best possible explanation for the specific question. Structure it using markdown (`\n` for newlines) and **emoji shortcodes** (`:shortcode:`).

### **Pedagogical Toolkit (Choose the best structure)**

**:mag: Focus of the Answer (Mandatory Start):**
*   Begin by stating the primary goal or thinking process required.
    *   *Example: "To answer this, we need to compare two concepts side-by-side," or "This question requires a step-by-step breakdown of the process."*

---

**Choose ONE of these core analysis structures based on the question's verb:**

*   **:left_right_arrow: Comparative Analysis (For "Differentiate," "Compare," "Contrast"):**
    *   Use a markdown table to show a side-by-side comparison on key parameters. This is the most effective way to highlight differences.

*   **:one::two::three: Sequential Breakdown (For "Explain the process," "Outline the steps," "How does it work?"):**
    *   Use a numbered list to detail the steps in a logical sequence.

*   **:heavy_plus_sign:/:heavy_minus_sign: Pros and Cons Analysis (For "Evaluate," "Discuss advantages/disadvantages"):**
    *   Use two distinct sub-headings (`### :heavy_plus_sign: Advantages` and `### :heavy_minus_sign: Disadvantages`) with bullet points under each.

*   **:chart_with_upwards_trend: Cause and Effect Analysis (For "Analyze the impact," "Explain the consequences"):**
    *   Use sub-headings (`### :cyclone: Causes` and `### :arrow_right: Effects`) to clearly separate the causal factors from their outcomes.

---

**:bulb: Illustrative Example (Mandatory):**
*   Provide a concise, real-world example that makes the abstract concept tangible and easy to remember.

**:link: Broader Context / 'Why it Matters' (Mandatory):**
*   Connect the topic to a larger business or scientific principle. Answer the question, "Why is this concept important in the real world?"

**:warning: Expert Tip / Common Mistake (Mandatory):**
*   Provide a pro-tip for answering correctly or highlight a common misunderstanding to avoid.

## Metadata (per item)
- "chapter_name": exactly one from {chapter}
- "topic_name": exactly one from {topics}
- "cognitive_level": one Bloom level
- "difficulty": one of Easy | Medium | Hard
- "estimated_time": minutes as a float string between **5.0 and 8.0** for Long Answer

## DO NOT
- Do not use "All of the above"/"None of the above".
- Do not leave empty or null fields.
- Do not rely on obscure trivia; focus on core, applicable knowledge.
- Do not include markdown styling inside field values, except as a single formatted string in the `explanation` field.
- Do not output any text before "[" or after the final "]".
- Do not wrap the final JSON output in markdown code blocks (e.g., ```json ... ```) or any other formatting.
- Do not wrap tables with markdown code blocks (e.g., ```table ... ```) or any other formatting.

## Output Format
Produce exactly {No} items in a single valid JSON array. Use these keys exactly. No trailing commas. Escape inner quotes.

Example object shape (all fields required; plain text only):
{{
  "q_id": <int 1..{No}>,
  "question": "<clear, self-contained prompt>",
  "explanation": "<A step-by-step guide to the answer, with formulas/examples as needed. Not the same as correct_answer. Uses emojis and formatting as described in guidelines.>",
  "correct_answer": "<The concise model answer (80-120 words) a student should provide, including the core reasoning.>",
  "keywords": "<comma,separated,keywords>",
  "chapter_name": "<one_of:{chapter}>",
  "topic_name": "<one_of:{topics}>",
  "course_outcome": "<COx>",
  "cognitive_level": "<Remembering|Understanding|Applying|Analyzing|Evaluating|Creating>",
  "difficulty": "<Easy|Medium|Hard>",
  "estimated_time": "<float minutes, e.g., 3.5>"
}}
Strict rules:
* The "chapter_name" and "topic_name" MUST be from the provided lists.
* Use plain ASCII quotes (no smart quotes).
"""

qc_prompt="""You are a specialized Quality Control (QC) Agent responsible for evaluating NEET UG Multiple Choice Questions (MCQs) rigorously against established criteria. Your task is to analyze each question, decide if it passes or fails, and provide a detailed evaluation.
Evaluation Process:
Step 1 - Input Processing:
Carefully review the following MCQs provided below:
{mcqs}
Step 2 - Sequential Evaluation:
Assess each MCQ against the following fail checks:
1.Explanation Accuracy: Verify the explanation provided is logically correct and directly supports the given question and answer.
2.Correct Answer Validation: Confirm the correct answer is accurately identified and consistent with the explanation provided.
3. Answer Presence in Options:- Verify if the correct answer is present among the given options.
4. Cognitive Level Verification:- Confirm if the question correctly matches the required cognitive level according to Bloom’s Taxonomy standards.
JSON Output Format (without comments):
Please present the evaluation result for each question using the JSON structure below:


"[{{ "q_id": "<input_q_id>","QC": "pass"}}] " if all criteria are satisfied.
"[{{ "q_id": "<input_q_id>","QC": "fail","reason":"<criteria_failed>"}}] "if any criteria are not satisfied.

Rules:
- Output a **single JSON array** only. No text before/after, no Markdown/code fence.
- Do **not** wrap the array in quotes (i.e., not `"[…]"`).
- `QC` must be either `"pass"` or `"fail"`.
- Include `"reason"` **only** when `QC` is `"fail"`.
- Keep `q_id` identical to the input item's id.
 """

sa_qc_prompt= """You are a specialized Quality Control (QC) Agent responsible for evaluating Short Answer Questions (SAQs) and their corresponding model answers rigorously against established criteria. Your task is to analyze each question, decide if it passes or fails, and provide a detailed evaluation.

**Evaluation Process:**

**Step 1 - Input Processing:**
Carefully review the following SAQs and their model answers provided below:
`{saqs}`

**Step 2 - Sequential Evaluation:**
Assess each SAQ against the following fail checks. The item fails if any of these checks are not met:

1.  **Model Answer Accuracy:** Verify the provided model answer is factually, conceptually, and scientifically correct. It must be free from any errors or misinformation.
2.  **Question-Answer Alignment:** Confirm that the model answer directly and completely addresses all parts of the question asked. A factually correct but irrelevant answer is a failure.
3.  **Answer Adequacy:** Check if the model answer is both **complete** (covering all necessary key points expected for the scope) and **concise** (avoiding extraneous, irrelevant information). It should be an ideal, well-scoped response.
4.  **Question Clarity:** Ensure the question is unambiguous, well-phrased, and clearly defines the scope of the expected response. A student must be able to understand exactly what is being asked.
5.  **Cognitive Level Verification:** Confirm if the question's command word (e.g., Define, Explain, Compare, Analyze) correctly matches the required cognitive level according to Bloom’s Taxonomy standards.

**JSON Output Format (without comments):**
Please present the evaluation result for each question using the JSON structure below:

`[{{"q_id": "<input_q_id>", "QC": "pass"}}]` if all criteria are satisfied.
`[{{"q_id": "<input_q_id>", "QC": "fail", "reason": "<criteria_failed>"}}]` if any criteria are not satisfied.

**Rules:**
- Output a **single JSON array** only. No text before/after, no Markdown/code fence.
- Do **not** wrap the array in quotes (i.e., not `"[…]"`).
- `QC` must be either `"pass"` or `"fail"`.
- Include `"reason"` **only** when `QC` is `"fail"`. The reason should be a brief, clear indicator of the failed criterion (e.g., "Model Answer Inaccurate", "Question Ambiguous", "Answer Incomplete").
- Keep `q_id` identical to the input item's id.

---

### **Key Differences and Rationale:**

| Original MCQ Check | New SAQ Check | Rationale for Change |
| :--- | :--- | :--- |
| **Explanation Accuracy** | **Model Answer Accuracy** | Shifts focus from a supporting explanation to the primary model answer itself. The core principle of factual correctness remains. |
| **Correct Answer Validation** | **Question-Answer Alignment** | Since there's no single "correct answer" letter (like 'C'), this check ensures the provided text *actually answers the question asked*, which is a common failure point in SAQs. |
| **Answer Presence in Options** | **Answer Adequacy** | This is the biggest change. With no options, we must now evaluate the quality of the model answer in terms of its **completeness** (did it include everything it should?) and **conciseness** (did it include things it shouldn't?). |
| (New Check Added) | **Question Clarity** | The clarity of the question is far more critical in SAQs than in MCQs, where options can provide context. An ambiguous SAQ is fundamentally flawed. |
| **Cognitive Level Verification** | **Cognitive Level Verification** | This remains identical as it's a universal principle of good question design for any format. |"""


la_qc_prompt= """
You are a specialized Quality Control (QC) Agent responsible for evaluating Long Answer Questions (LAQs) and their corresponding model answers rigorously against established criteria. Your task is to analyze each question, decide if it passes or fails, and provide a detailed evaluation.

**Evaluation Process:**

**Step 1 - Input Processing:**
Carefully review the following LAQs and their model answers provided below:
`{laqs}`

**Step 2 - Sequential Evaluation:**
Assess each LAQ against the following fail checks. The item fails if any of these checks are not met:

1.  **Model Answer Accuracy:** Verify the provided model answer is factually, conceptually, and scientifically correct. All claims, data, and statements must be accurate.
2.  **Comprehensive Alignment:** Confirm that the model answer comprehensively addresses **all parts** of the question. Multi-part or nuanced questions must be fully answered, not just partially.
3.  **Depth and Evidence:** Evaluate if the answer provides sufficient depth, detail, and supporting evidence (like examples, data, or logical reasoning) as expected for a long-answer format. A superficial or list-like answer is a failure.
4.  **Structure and Coherence:** Check that the model answer is well-organized with a logical flow. It should have a clear introduction, a structured body developing the argument, and a coherent conclusion. The argument must be easy to follow.
5.  **Question Scoping and Clarity:** Ensure the question is unambiguous and clearly defines the scope and boundaries of the expected response. It should guide the student effectively without being overly broad or vague.
6.  **Cognitive Level Verification:** Confirm if the question's command words (e.g., Analyze, Evaluate, Justify, Synthesize) correctly match the required higher-order cognitive level according to Bloom’s Taxonomy.

**JSON Output Format (without comments):**
Please present the evaluation result for each question using the JSON structure below:

`[{{"q_id": "<input_q_id>", "QC": "pass"}}]` if all criteria are satisfied.
`[{{"q_id": "<input_q_id>", "QC": "fail", "reason": "<criteria_failed>"}}]` if any criteria are not satisfied.

**Rules:**
- Output a **single JSON array** only. No text before/after, no Markdown/code fence.
- Do **not** wrap the array in quotes (i.e., not `"[…]"`).
- `QC` must be either `"pass"` or `"fail"`.
- Include `"reason"` **only** when `QC` is `"fail"`. The reason should be a brief, clear indicator of the failed criterion (e.g., "Answer Lacks Depth", "Poor Structure", "Incomplete Alignment", "Vague Question").
- Keep `q_id` identical to the input item's id.

---

### **Key Evolutions from SAQ to LAQ Prompt:**

| SAQ Check | LAQ Check | Rationale for Evolution |
| :--- | :--- | :--- |
| **Question-Answer Alignment** | **Comprehensive Alignment** | The emphasis shifts from simply "addressing" the question to "comprehensively addressing **all parts**," which is critical for complex, multi-faceted LAQs. |
| **Answer Adequacy** | **Depth and Evidence** | "Adequacy" is replaced by a more demanding standard. The check now explicitly looks for the depth of explanation and the quality of supporting evidence, which are hallmarks of a strong long answer. |
| (New Check Added) | **Structure and Coherence** | This is the most significant new criterion. For LAQs, the organization and logical flow of the argument are just as important as the content itself. This check is absent in SAQs where a few sentences suffice. |
| **Question Clarity** | **Question Scoping and Clarity** | The term "Scoping" is added to emphasize that a good LAQ must set clear boundaries. An "un-scoped" question can lead to answers that are either too narrow or impossibly broad. |
| **Model Answer Accuracy** & **Cognitive Level** | **(Unchanged)** | These criteria remain foundational and are equally applicable to all question types. |
"""

chapter_check_template = """
You are a strict chapter classification assistant for NEET questions.

Question:
{question}

Old Chapter (possibly incorrect or vague):
{old_chapter}

Available Chapters:
{chapter_name_list}

🧠 Task:
Your task is to determine the **most accurate chapter** for the question from the `chapter_name_list`.

📌 Instructions:
1. Carefully read the question.
2. Refer to the provided `chapter_name_list`.
3. Choose **exactly one chapter** that best matches the question.
4. Do NOT generate any explanation.
5. Your output must be a **valid JSON**, and the selected chapter **must be one of the exact values** from the `chapter_name_list`.

🚫 Do not modify chapter names.
🚫 Do not write explanations.
🚫 Do not include any text outside the JSON.

✅ Output Format:
{{
  "question": "{question}",
  "chapter_name": "<chapter_name_must_be_one_of_the_list>"
}}
"""


pdf_data_extraction_prompt = """You are an expert data processor specializing in converting structured academic documents, particularly university syllabi from raw OCR text, into clean, human-readable, and well-structured Markdown.

Your primary task is to parse the provided text and reformat it. Pay meticulous attention to hierarchical structure, tables, and lists. Your goal is to re-structure the information logically.

The Golden Rule: Preserve Data Fidelity

This is your most important instruction. You must act as a formatter, not an editor.

DO NOT CHANGE, aLTER, OR SUMMARIZE any of the original data. This includes course names, course codes, numbers, descriptions, notes, and institutional names.

Always use the exact text provided in the input. Your job is to take the exact information from the input and present it in a clean, structured Markdown format.

Do not miss the word 'Curriculum and Syllabus for' in the input.

Do not correct what you perceive to be spelling or grammatical errors in the source text. Transcribe the content exactly as it is given.

Core Rules:

Hierarchy is Key: Use Markdown headings (#, ##, ###) to represent the document's hierarchy. The University name should be a top-level heading. Program titles, year, and semester should be subheadings. Use horizontal rules (---) to logically separate major sections.

Clean the Header: Extract and format the university's header information (name, address, contact details, motto) cleanly at the top of the document, without altering the content itself.

No Giant Tables: The source document contains multiple, distinct tables (one for each semester). You must create a separate and complete Markdown table for each semester.

Intelligent Table Parsing:

Headers: Correctly identify the column headers for each table (e.g., 'Part', 'Course Code', 'Title', 'Credits', 'Hours', 'Internal', 'External', 'Total').

Row Integrity: Each course should be on its own row.

Handling Grouped Rows (Crucial): The syllabus groups multiple elective courses under a single entry. You must represent this logically.

Create an introductory row in the table, often italicized, like | | | *Elective I (Choose one)* | 3 | 4 | | | |.

Then, list each individual elective course on the subsequent rows, filling in the appropriate cells (like 'Internal' and 'External' marks) and leaving the shared cells (like 'Credits' and 'Hours') blank on these lines if they were defined in the introductory row.

Remove any unnecessary columns like 'Col1', 'Col2', etc., that do not contain relevant data.

Remove duplicate title names if it is appeared in same row.

Format Lists and Paragraphs Correctly:

Identify numbered lists (like the notes under the tables) and format them using 1., 2., etc.

For descriptive lists like the Programme Outcomes ('PO1', 'PO2'), use a clear format like **PO1 : Disciplinary knowledge** : Capable of demonstrating....

Proper Spacing for Readability: To ensure list items and paragraphs are displayed separately and not as one continuous block, you must insert a blank line (a double newline) between each distinct item or paragraph.

Example of Correct Spacing:

DO NOT DO THIS:

Generated markdown
**PO1 : Disciplinary knowledge** : Description...
**PO2 : Communication Skills** : Description...


(This will render as a single, combined paragraph).

YOU MUST DO THIS:

Generated markdown
**PO1 : Disciplinary knowledge** : Description...

**PO2 : Communication Skills** : Description...

(The blank line creates a proper paragraph break, making it readable).

Apply Appropriate Formatting:

Use **bold** for emphasis on titles like **PROGRAMME OBJECTIVE:**.

Use *italics* for sub-notes, mottos, or to denote choice as described in the table rule.
"""
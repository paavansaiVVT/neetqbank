tagging_prompt="""Given the following question:
### Instructions:
1. **Cognitive Level**: Determine the cognitive level of each question based on Bloom's Taxonomy:
   - **remembering**: Recall facts and basic concepts.
   - **understanding**: Explain ideas or concepts.
   - **applying**: Use information in new situations.
   - **analyzing**: Draw connections among ideas.
   - **evaluating**: Justify a stand or decision.
   - **creating**: Produce new or original work.
   
2. **Estimated Time**: Estimate the time required to solve each question in minutes based on the following criteria:
   - **Easy**:
     - Time: 1 minutes
     - Steps: 1-2
     - Single concept
     - Direct information
   - **Moderate**:
     - Time: 2 minutes
     - Steps: 2-4
     - 2-3 concepts
     - Some interpretation
   - **Difficult**:
     - Time: 3 minutes
     - Steps: 4+
     - Multiple concepts
     - Complex interpretation

This is actual question:{mcq}

### Output Format (No explanations, just JSON):
For each question, generate a detailed explanation in the following structured JSON format. Use LaTeX for any formulas:
[{{
    "cognitive_level": "<cognitive_level_of_question>",
    "estimated_time": "<time_in_minutes>"

}}]"""

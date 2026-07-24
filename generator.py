import os
import json
import time
from llm_api import call_api
from pdf_handler import ingest_chapter, clean_json_response

def generate_questions(pdf_path, q_cnt=20):
    text = ingest_chapter(pdf_path)
    
    generate_prompt = f"""You are an expert educational assessment generator. Generate a {q_cnt} multiple-choice question bank based on the provided text.

    CRITICAL INSTRUCTIONS:
    1. Focus on testing foundational, mechanical understanding of the concepts rather than surface-level definitions.
    2. Where applicable, frame questions using familiar, everyday analogies to help the test-taker deduce the solution.
    3. You MUST return ONLY a valid JSON array of exactly {q_cnt} objects.
    4. DO NOT wrap the array in a parent dictionary. The absolute first character of your response must be '[' and the last character must be ']'.
    5. Do not include markdown formatting, conversational text, or explanations outside the JSON.
    6. Ensure exactly 4 distinct options per question.
    7. Use extremely simple, A2-level English. Write in short, direct sentences using active voice. Strictly avoid idioms, complex grammar, and unnecessary jargon. If a technical term is absolutely required by the text, explain it simply.
    8. Avoid using analogies wherever necessary.

    Expected Exact Schema:
    [
    {{
        "question": "string",
        "options": ["string", "string", "string", "string"],
        "correct_answer_index": 0,
        "explanation": "string"
    }}
    ]

    Text:
    {text}"""

    review_prompt_template = """You are a strict JSON validation and correction assistant. Review the following draft JSON quiz questions against the original text.

    Your tasks:
    1. Verify factual accuracy against the original text.
    2. Ensure exactly 4 distinct, complete options exist for each question.
    3. Ensure the 'correct_answer_index' (integer 0-3) accurately points to the right option.
    4. Ensure the 'explanation' is a complete, factually accurate sentence.
    5. Fix any truncated sentences, blank strings, or missing fields.

    CRITICAL INSTRUCTIONS: 
    - You MUST return ONLY a valid JSON array of {q_cnt} objects. 
    - DO NOT wrap the array in a parent dictionary.
    - The absolute first character of your response must be '[' and the last character must be ']'.
    - Do not include markdown formatting, conversational text, or explanations outside the JSON.

    Expected Exact Schema:
    [
      {{
        "question": "string",
        "options": ["string", "string", "string", "string"],
        "correct_answer_index": 0,
        "explanation": "string"
      }}
    ]

    Original Text:
    {text}
    
    Draft Questions:
    {draft_json}"""

    for _ in range(3):
        try:
            draft_response = call_api(generate_prompt, response_json=False)
            review_prompt = review_prompt_template.format(q_cnt=q_cnt, text=text, draft_json=draft_response)
            final_response = call_api(review_prompt, response_json=False)
            
            questions = json.loads(clean_json_response(final_response))
            
            if len(questions) != q_cnt:
                raise ValueError(f"Must have exactly {questions} questions.")
                
            return questions
        except Exception:
            continue
            
    raise RuntimeError("Failed to generate quiz after 3 attempts.")
import os
import json
import time
from llm_api import call_api
from pdf_handler import ingest_chapter, clean_json_response

def generate_questions(pdf_path, english_level="A2", q_cnt=20, difficulty="Medium"):
    text = ingest_chapter(pdf_path)
    
    generate_prompt = f"""You are an expert educational assessment generator. Generate a {q_cnt} multiple-choice question bank based on the provided text.

    CRITICAL INSTRUCTIONS:
    1. Focus on testing foundational, mechanical understanding of the concepts rather than surface-level definitions.
    2. Where applicable, frame questions using familiar, everyday analogies to help the test-taker deduce the solution.
    3. You MUST return ONLY a valid JSON array of exactly {q_cnt} objects.
    4. DO NOT wrap the array in a parent dictionary. The absolute first character of your response must be '[' and the last character must be ']'.
    5. Do not include markdown formatting, conversational text, or explanations outside the JSON.
    6. Ensure exactly 4 distinct options per question.
    7. Language Constraint: Use {english_level}-level English. Write in short, direct sentences using active voice. Strictly avoid idioms, complex grammar, and unnecessary jargon. If a technical term is required, explain it simply.
    8. Target Difficulty: {difficulty}. Adjust question depth, distractor plausibility, and complexity accordingly.
    9. Distractors (the 3 wrong options) MUST be plausible: each should relate directly to the same concept, entity, or process discussed in the text, not be an unrelated or nonsensical statement. A distractor should represent a believable misunderstanding of the text, not a random fact.
    10. Every option's length (word count) MUST be within roughly the same range as the other options in that question. Neither the correct answer nor the distractors should be consistently longer or shorter than the rest — match length regardless of which one is correct.

    Good example 1 (short options, all similar length, distractors topically relevant):
    {{
        "question": "A car receives a new feature without a shop visit. What made this possible?",
        "options": ["A new engine part", "A dealership install", "A wireless software update", "A replaced sensor"],
        "correct_answer_index": 2,
        "explanation": "Over-the-Air updates let vehicles receive new features remotely, without physical service visits."
    }}

    Bad example 1 (avoid this — correct answer is the longest and most specific, distractors are short, vague, or unrelated):
    {{
        "question": "A car receives a new feature without a shop visit. What made this possible?",
        "options": ["Better tires", "New paint", "The manufacturer's proprietary wireless Over-the-Air update system delivering the feature remotely", "A cheaper battery"],
        "correct_answer_index": 2,
        "explanation": "..."
    }}

    Good example 2 (options are all long and detailed — length alone does not signal which one is correct):
    {{
        "question": "Why do engineers separate the SDV software stack into distinct layers?",
        "options": [
            "Because each layer has its own release schedule, ownership, and level of risk that must be managed independently",
            "Because separating layers allows the exterior paint process to be scheduled on a different factory line",
            "Because government safety inspectors require every vehicle subsystem to be certified by a different regional office",
            "Because dealership technicians need each layer stored on a separate physical hard drive during servicing"
        ],
        "correct_answer_index": 0,
        "explanation": "Each layer in the SDV stack carries distinct ownership, release rhythms, and risk profiles, so clear architectural boundaries are needed for safe, independent updates."
    }}

    Bad example 2 (avoid this — distractors are short and terse while the correct answer is the only detailed one; same problem as Bad example 1, just in reverse framing):
    {{
        "question": "Why do engineers separate the SDV software stack into distinct layers?",
        "options": [
            "For paint scheduling",
            "For inspections",
            "Because each layer has its own release schedule, ownership, and level of risk that must be managed independently",
            "For hard drive storage"
        ],
        "correct_answer_index": 2,
        "explanation": "..."
    }}

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
    6. Ensure language strictly adheres to {english_level}-level English and difficulty is calibrated to {difficulty}.
    7. Check option length: rewrite any option whose word count is far longer or shorter than the other three in the same question, so no single option is identifiable by length alone.

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

    plausibility_prompt_template = """You are a distractor-plausibility auditor. You have ONE job: check whether the 3 wrong options ("distractors") in each question could be eliminated just by noticing they belong to a different topic or subsystem than the question is asking about — without needing to understand the passage at all.

    Do NOT change anything else. Do not touch question wording, the correct answer, explanations, or option length balance unless a rewritten distractor changes it.

    For each question:
    1. Identify the subsystem/topic/category the question is really about (e.g. "cloud software delivery", "vehicle safety systems", "engineering workforce").
    2. Check each distractor: does it belong to that same subsystem/topic, just factually wrong? Or does it belong to an unrelated category (e.g. paint color, tire pressure, government tariffs) that a reader could rule out on sight without reading the passage?
    3. Rewrite any distractor that fails this check so it stays within the same topic/subsystem as the question and the correct answer, while remaining factually incorrect. Keep the rewritten distractor's length close to the other three options.

    Example of the failure to fix:
    Question: "What function does the cloud layer manage in connected vehicles?"
    Bad distractors (different subsystem than the question — eliminable by topic alone): "The physical feel of the steering wheel", "The internal pressure of engine oil", "The tint level of window glass"
    Fixed distractors (same subsystem — software/data delivery — but still wrong): "The infotainment touchscreen's local display rendering", "The dealership's in-person diagnostic scan tool", "The driver's manual firmware installation via USB"

    CRITICAL INSTRUCTIONS:
    - You MUST return ONLY a valid JSON array of {q_cnt} objects.
    - DO NOT wrap the array in a parent dictionary.
    - The absolute first character of your response must be '[' and the last character must be ']'.
    - Do not include markdown formatting, conversational text, or explanations outside the JSON.
    - Preserve every 'id' field exactly as given.

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

    def validate_structure(questions, expected_cnt):
        if len(questions) != expected_cnt:
            raise ValueError(f"Must have exactly {expected_cnt} questions.")
        for q in questions:
            idx = q.get("correct_answer_index")
            if not isinstance(idx, int) or not (0 <= idx <= 3):
                raise ValueError(f"Invalid correct_answer_index: {idx}")
            if len(q.get("options", [])) != 4:
                raise ValueError("Each question must have exactly 4 options.")

    def validate_length_parity(questions):
        length_flags = 0
        for q in questions:
            options = q["options"]
            idx = q["correct_answer_index"]
            correct_len = len(options[idx].split())
            other_lens = [len(opt.split()) for i, opt in enumerate(options) if i != idx]
            avg_other_len = sum(other_lens) / len(other_lens)
            if avg_other_len > 0 and (correct_len > avg_other_len * 1.4 or correct_len < avg_other_len / 1.4):
                length_flags += 1
        if length_flags > len(questions) * 0.3:
            raise ValueError(f"Too many questions with unbalanced option length: {length_flags}")

    for _ in range(3):
        try:
            draft_response = call_api(generate_prompt, response_json=False)
            review_prompt = review_prompt_template.format(
                q_cnt=q_cnt,
                english_level=english_level,
                difficulty=difficulty,
                text=text,
                draft_json=draft_response
            )
            reviewed_response = call_api(review_prompt, response_json=False)
            reviewed_questions = json.loads(clean_json_response(reviewed_response))
            validate_structure(reviewed_questions, q_cnt)

            plausibility_prompt = plausibility_prompt_template.format(
                q_cnt=q_cnt,
                text=text,
                draft_json=json.dumps(reviewed_questions)
            )
            plausibility_response = call_api(plausibility_prompt, response_json=False)
            final_questions = json.loads(clean_json_response(plausibility_response))
            validate_structure(final_questions, q_cnt)

            # Stage 3 can rebalance option length, so re-check after it runs, not before.
            validate_length_parity(final_questions)

            return final_questions
        except Exception:
            continue

    raise RuntimeError("Failed to generate quiz after 3 attempts.")
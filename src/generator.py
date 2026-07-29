import os
import json
import time
from src.llm_api import call_api
from src.pdf_handler import ingest_chapter, clean_json_response

STYLE_GUIDE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools/quiz_style_guide.md")

def _load_style_guide(english_level, difficulty):
    with open(STYLE_GUIDE_PATH, "r", encoding="utf-8") as f:
        raw = f.read()
    return raw.format(english_level=english_level, difficulty=difficulty)

def generate_questions(pdf_path, english_level="A2", q_cnt=20, difficulty="Medium"):
    text = ingest_chapter(pdf_path)
    style_guide = _load_style_guide(english_level, difficulty)

    generate_prompt = f"""{style_guide}

## Your Task Right Now

Generate exactly {q_cnt} new multiple-choice questions from the text below. Follow every rule and example in the style guide above.

## Text

{text}"""

    review_prompt_template = """{style_guide}

## Your Task Right Now

You are reviewing draft questions against the style guide above and the original text below. Fix any violations: factual inaccuracies, incomplete or truncated fields, an incorrect `correct_answer_index`, or option-length imbalance. Do not touch distractor plausibility here — that is handled in a separate pass.

You MUST return ONLY a valid JSON object with a single `questions` key containing an array of {q_cnt} objects, matching the schema in the style guide above. Preserve every `id` field exactly as given if present.

## Original Text

{text}

## Draft Questions

{draft_json}"""

    plausibility_prompt_template = """{style_guide}

## Your Task Right Now

You are auditing ONLY distractor plausibility in the draft questions below, using the "Distractor Plausibility Checklist" in the style guide above. Do not change question wording, the correct answer, explanations, or option-length balance unless a rewritten distractor requires it.

You MUST return ONLY a valid JSON object with a single `questions` key containing an array of {q_cnt} objects, matching the schema in the style guide above. Preserve every `id` field exactly as given.

## Original Text

{text}

## Draft Questions

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
            draft_response = call_api(generate_prompt, response_json=True, temperature=0.7, enable_thinking=True)

            review_prompt = review_prompt_template.format(
                style_guide=style_guide,
                q_cnt=q_cnt,
                text=text,
                draft_json=draft_response
            )
            reviewed_response = call_api(review_prompt, response_json=True, temperature=0.2, enable_thinking=True)
            
            # Extract the 'questions' array from the parent object. If the model ignored
            # the wrapper instruction and returned a bare array instead, treat that array
            # as the questions directly rather than letting .get() fail on a list.
            reviewed_data = json.loads(clean_json_response(reviewed_response))
            if isinstance(reviewed_data, dict):
                reviewed_questions = reviewed_data.get("questions", reviewed_data)
            else:
                reviewed_questions = reviewed_data
            validate_structure(reviewed_questions, q_cnt)

            plausibility_prompt = plausibility_prompt_template.format(
                style_guide=style_guide,
                q_cnt=q_cnt,
                text=text,
                draft_json=json.dumps({"questions": reviewed_questions})
            )
            plausibility_response = call_api(plausibility_prompt, response_json=True, temperature=0.2, enable_thinking=True)
            
            # Extract the 'questions' array from the parent object. Same guard as above —
            # fall back to treating the response as the array itself if it isn't a dict.
            final_data = json.loads(clean_json_response(plausibility_response))
            if isinstance(final_data, dict):
                final_questions = final_data.get("questions", final_data)
            else:
                final_questions = final_data
            validate_structure(final_questions, q_cnt)

            # Stage 3 can rebalance option length, so re-check after it runs, not before.
            validate_length_parity(final_questions)

            return final_questions
        except Exception as e:
            print(f"[Module: generator, Attempt {_ + 1}/3] Error: {e}")
            continue

    raise RuntimeError("Failed to generate quiz after 3 attempts.")
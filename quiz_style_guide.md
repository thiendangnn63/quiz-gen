# Quiz Question Style Guide

This document defines the quality bar for every multiple-choice question in this quiz bank. It applies at every stage of the pipeline — generation, review, and plausibility auditing. Whatever stage you are performing, every question you touch must satisfy every rule below, not just the part of the task you were asked to do.

## Output Schema

Output is always a bare JSON array — never wrapped in a parent object — of objects matching this exact schema:

```json
[
  {{
    "question": "string",
    "options": ["string", "string", "string", "string"],
    "correct_answer_index": 0,
    "explanation": "string"
  }}
]
```

Formatting requirements, always:
- The absolute first character of your response must be `[` and the last character must be `]`.
- No markdown formatting, conversational text, or explanation outside the JSON itself.
- Exactly 4 distinct options per question.

## Content Rules

1. Focus on testing foundational, mechanical understanding of the concepts, not surface-level definitions.
2. Language: use {english_level}-level English. Short, direct sentences, active voice. Avoid idioms and unnecessary jargon; if a technical term is required, explain it simply.
3. Target difficulty: {difficulty}. Adjust question depth and distractor plausibility accordingly.
4. Every option's word count must be within roughly the same range as the other three options in that question. Neither the correct answer nor any distractor should be consistently longer or shorter than the rest.

## Distractor Plausibility Checklist

Every distractor (the 3 wrong options) must be indistinguishable from the correct answer in tone and specificity — a reader should not be able to spot the correct answer just because it "sounds right" while the others sound fabricated, vague, or out of place. Check every distractor against these five failure modes:

1. **Topic mismatch**: does the distractor belong to a different subsystem/topic/category than the question (e.g. paint color, tire pressure, government tariffs, next to a software question)? A reader could rule it out without reading the passage at all.
2. **Vague hedging**: does the distractor use soft, non-committal language — "somehow," "in some way," "various," "certain," "related to," "involved in" — where the correct answer is specific and confident? Hedging is a tell that the option was invented to fill a slot rather than to sound like a real claim.
3. **Lazy negation**: is the distractor just the correct answer with "not" inserted, or a flat opposite with no new content (e.g. correct: "it updates automatically," distractor: "it does not update automatically")? This reads as an obvious foil rather than a genuine misconception.
4. **Mismatched register**: does the distractor differ from the correct answer in sentence form, length, or confidence in a way that makes it stand out — a full confident sentence next to a fragment, or a specific claim next to a generic one?
5. **Generic hardware filler**: does the distractor describe a physical/manufacturing attribute of a component — its weight, cost, size, or material — instead of answering what the question actually asks? A distractor like "increases the weight of the processor" is off-topic filler when the question is about software, data, architecture, or a process, even though it sounds specific and confident. Every distractor must propose a genuine alternative answer to the question being asked, not a fact about some other property of an object the passage happens to mention.

A correct distractor must remain factually wrong, but should read as something a person who misunderstood the text might genuinely believe — same level of detail, same sentence structure, same confident tone as the correct answer.

## Worked Examples

**Good (short options, all similar length, distractors topically relevant):**
```json
{{
    "question": "A car receives a new feature without a shop visit. What made this possible?",
    "options": ["A new engine part", "A dealership install", "A wireless software update", "A replaced sensor"],
    "correct_answer_index": 2,
    "explanation": "Over-the-Air updates let vehicles receive new features remotely, without physical service visits."
}}
```

**Bad — avoid (correct answer is the longest and most specific, distractors are short, vague, or unrelated):**
```json
{{
    "question": "A car receives a new feature without a shop visit. What made this possible?",
    "options": ["Better tires", "New paint", "The manufacturer's proprietary wireless Over-the-Air update system delivering the feature remotely", "A cheaper battery"],
    "correct_answer_index": 2,
    "explanation": "..."
}}
```

**Good (options are all long and detailed — length alone does not signal which one is correct):**
```json
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
```

**Bad — avoid (distractors are short and terse while the correct answer is the only detailed one — same problem as above, reversed):**
```json
{{
    "question": "Why do engineers separate the SDV software stack into distinct layers?",
    "options": ["For paint scheduling", "For inspections", "Because each layer has its own release schedule, ownership, and level of risk that must be managed independently", "For hard drive storage"],
    "correct_answer_index": 2,
    "explanation": "..."
}}
```

**Failure mode 1 — topic mismatch:**
Question: "What function does the cloud layer manage in connected vehicles?"
Bad distractors: "The physical feel of the steering wheel", "The internal pressure of engine oil", "The tint level of window glass"
Fixed distractors (same subsystem, still wrong): "The infotainment touchscreen's local display rendering", "The dealership's in-person diagnostic scan tool", "The driver's manual firmware installation via USB"

**Failure modes 2-4 — vague hedging, lazy negation, mismatched register:**
Question: "How does the cloud layer support connected vehicles?"
Correct: "It securely delivers and monitors software updates across the vehicle fleet."
Bad: "It handles some vehicle-related data tasks in the background." (vague hedging) / "It does not deliver updates to the vehicle." (lazy negation) / "Various connectivity functions." (mismatched register — a fragment next to a full sentence)
Fixed: "It streams live diagnostic video from onboard cameras to the service center." / "It stores driver profile settings locally and never syncs them to a server." / "It manages licensing fees for in-car infotainment subscriptions."

**Failure mode 5 — generic hardware filler (a real failure from a past run):**
Question: "What is the main job of the cloud layer in an SDV?"
Correct: "To store fleet data and manage large software updates."
Bad (drifts into unrelated manufacturing facts): "To manufacture the physical sensors for each wheel", "To assemble the battery cells inside the chassis", "To calibrate the mechanical gears during assembly"
Fixed (still wrong, but each is a genuine alternative claim about what the cloud layer might do): "To store each driver's seat and mirror preferences locally on the dashboard unit", "To broadcast live diagnostic video from the car to a mobile app", "To manage in-car entertainment subscription billing"
# Quiz Question Style Guide

This document defines the quality bar for every multiple-choice question in this quiz bank. It applies at every stage of the pipeline — generation, review, and plausibility auditing. Whatever stage you are performing, every question you touch must satisfy every rule below, not just the part of the task you were asked to do.

## Output Schema

Output must be a JSON object containing a single key `"questions"` which holds an array of objects matching this exact schema:

```json
{{
  "questions": [
    {{
      "question": "string",
      "options": ["string", "string", "string", "string"],
      "correct_answer_index": 0,
      "explanation": "string"
    }}
  ]
}}
```

Formatting requirements, always:
- The absolute first character of your response must be `{{` and the last character must be `}}`.
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

A question is acceptable if at least 2 of the 3 distractors pass every check above. A single weak or imperfect distractor does not require rewriting the whole question — only rewrite a distractor if it fails a check, not the other two that already pass.

## Worked Examples

**Good (short options, all similar length, distractors topically relevant, valid rationale before options):**
```json
{{
  "questions": [
    {{
      "question": "A car receives a new feature without a shop visit. What made this possible?",
      "options": ["A new engine part", "A dealership install", "A wireless software update", "A replaced sensor"],
      "correct_answer_index": 2,
      "explanation": "Over-the-Air updates let vehicles receive new features remotely, without physical service visits."
    }}
  ]
}}
```

**Bad — avoid (correct answer is the longest and most specific, distractors are short, vague, or unrelated):**
```json
{{
  "questions": [
    {{
      "question": "A car receives a new feature without a shop visit. What made this possible?",
      "options": ["Better tires", "New paint", "The manufacturer's proprietary wireless Over-the-Air update system delivering the feature remotely", "A cheaper battery"],
      "correct_answer_index": 2,
      "explanation": "..."
    }}
  ]
}}
```

**Good (options are all long and detailed — length alone does not signal which one is correct):**
```json
{{
  "questions": [
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
  ]
}}
```

**Bad — avoid (distractors are short and terse while the correct answer is the only detailed one — same problem as above, reversed):**
```json
{{
  "questions": [
    {{
      "question": "Why do engineers separate the SDV software stack into distinct layers?",
      "options": ["For paint scheduling", "For inspections", "Because each layer has its own release schedule, ownership, and level of risk that must be managed independently", "For hard drive storage"],
      "correct_answer_index": 2,
      "explanation": "..."
    }}
  ]
}}
```

## Real Strong Examples

These are real questions from a past run that hit the quality bar. Distractors are sharp, specific, and each proposes a genuine (wrong) answer to the exact question asked — not an adjacent true fact. Match this level of rigor.

```json
{{
  "questions": [
    {{
      "question": "What does a standard API help developers do?",
      "options": [
          "Write one program that works across many different cars.",
          "Store individual driver preference profiles on local storage drives.",
          "Bypass security protocols to access restricted engine telemetry.",
          "Translate legacy database records into modern cloud network formats."
      ],
      "correct_answer_index": 0,
      "explanation": "Standard APIs give developers a clear, common way to talk to different car systems, so they can code once and share the app."
    }}
  ]
}}
```

```json
{{
  "questions": [
    {{
      "question": "What does cloud native software help companies do?",
      "options": [
          "Scale their services rapidly and handle massive user traffic.",
          "Store private user data permanently on local dashboard drives.",
          "Bypass governmental safety regulations during system software updates.",
          "Restrict network bandwidth to prioritize essential background driving functions."
      ],
      "correct_answer_index": 0,
      "explanation": "Cloud native uses internet computing rules to let software grow quickly, handle heavy traffic, and stay stable during changes."
    }}
  ]
}}
```

**Failure mode 1 — topic mismatch (App Store example):**
Question: "What is the main job of a car app store for users?"
Correct: "It gathers many tools in one place for easy user downloads."
Bad (drifts into unrelated vehicle hardware): "It monitors tire pressure and alerts the driver when inflation drops."
Fixed (still wrong, but topically relevant): "It manages the financial transactions for dealership hardware upgrades."

**Failure modes 2-4 — lazy negation (Shared Rules example):**
Question: "Why do experts say car companies should share basic software rules?"
Correct: "It lets data move easily between cars, services, and people."
Bad (lazy negation): "It restricts data exchange to prevent seamless communication between systems."
Fixed (proposes a genuine alternative motive): "It forces competitors to pay licensing fees to use public cloud infrastructure."

**Failure mode 5 — generic hardware filler (a real failure from a past run):**
Question: "What is the main job of the cloud layer in an SDV?"
Correct: "To store fleet data and manage large software updates."
Bad (drifts into unrelated manufacturing facts): "To manufacture the physical sensors for each wheel", "To assemble the battery cells inside the chassis", "To calibrate the mechanical gears during assembly"
Fixed (still wrong, but each is a genuine alternative claim about what the cloud layer might do): "To store each driver's seat and mirror preferences locally on the dashboard unit", "To broadcast live diagnostic video from the car to a mobile app", "To manage in-car entertainment subscription billing"
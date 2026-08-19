# ============================================================
# answer_test.py — EMIS OPENAI ANSWER VALIDATION TEST
# GPT-5.4 Solver + GPT-5.4 Verifier + Review Flags + Cost Tracking
# ============================================================

import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

from convert import extract_source_file, generate_exam_json_from_text

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

TEST_DOCX = Path("static/testing/chem_ss2.docx")
OUTPUT_FILE = Path("static/testing/chem_ss2_openai_answer_test.json")
FINAL_JSON_OUTPUT = Path("static/testing/chem_ss2_openai_generated_with_answers.json")

SUBJECT = "Chemistry"
CLASS_CATEGORY = "SS2"
EXPECTED_QUESTIONS = 50

# Start with 15 first. Later change to None for all 50.
TEST_LIMIT = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL_SOLVER = os.getenv("OPENAI_MODEL_SOLVER", "gpt-5.4").strip()
OPENAI_MODEL_VERIFIER = os.getenv("OPENAI_MODEL_VERIFIER", "gpt-5.4").strip()

# GPT-5.4 standard pricing from your OpenAI pricing page
INPUT_PRICE_PER_1M = 2.50
OUTPUT_PRICE_PER_1M = 15.00

client = OpenAI(api_key=OPENAI_API_KEY)

EXPECTED_ANSWERS = {
    1: "D",
    2: "D",
    3: "D",
    4: "A",
    5: "C",
    6: "A",
    7: "B",
    8: "C",
    9: "C",
    10: "D",
    11: "D",
    12: "D",
    13: "C",
    14: "A",
    15: "D",
}


# ============================================================
# HELPERS
# ============================================================

def extract_json_object(text: str) -> dict:
    text = str(text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"OpenAI did not return valid JSON:\n{text}")

    return json.loads(match.group(0))


def normalize_option(value: str) -> str:
    value = str(value or "").strip().upper()
    if value and value[0] in {"A", "B", "C", "D"}:
        return value[0]
    return ""


def safe_confidence(value: str) -> str:
    value = str(value or "").strip().lower()
    if value in {"high", "medium", "low"}:
        return value
    return "low"


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1_000_000) * INPUT_PRICE_PER_1M
    output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
    return round(input_cost + output_cost, 6)


def usage_from_response(response) -> dict:
    usage = getattr(response, "usage", None)

    if not usage:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0,
        }

    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens) or 0

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimate_cost(input_tokens, output_tokens),
    }


# ============================================================
# LOCAL RISK DETECTOR
# ============================================================

def local_suspicion_check(question: dict) -> dict:
    qid = question.get("id")
    qtext = str(question.get("question", "")).lower()
    options_text = " ".join(question.get("options", [])).lower()
    joined = f"{qtext} {options_text}"

    hard_flags = []
    soft_flags = []

    if any(x in joined for x in ["name: | class:", "for markers only", "scores obtainable"]):
        hard_flags.append("Question appears polluted with document header/table text.")

    if "ethane" in qtext and any(word in qtext for word in [
        "addition", "bromine", "polymer", "unsaturation", "decolorize", "decolourize"
    ]):
        hard_flags.append("Question mentions ethane but reaction pattern suggests ethene/unsaturation.")

    if "ethane" in qtext and "long chain" in qtext:
        hard_flags.append("Ethane does not polymerize into a long chain; likely meant ethene.")

    if "ethane" in qtext and "bromine" in qtext and "room temperature" in qtext:
        hard_flags.append("Ethane does not readily add bromine at room temperature; likely meant ethene.")

    if "ethane is produced from ethanol" in qtext:
        hard_flags.append("Dehydration of ethanol produces ethene, not ethane.")

    if "hydrogenation of butane" in qtext:
        hard_flags.append("Butane is already saturated; hydrogenation wording may be wrong.")

    soft_typo_words = [
        "dicholo",
        "dicloro",
        "halogenations",
        "isobers",
        "athyne",
        "hydrogenated of",
        "hydrogenateded",
    ]

    for word in soft_typo_words:
        if word in joined:
            soft_flags.append(f"Possible spelling typo detected: {word}")

    return {
        "id": qid,
        "hardSuspicious": bool(hard_flags),
        "softSuspicious": bool(soft_flags),
        "hardFlags": hard_flags,
        "softFlags": soft_flags,
    }


# ============================================================
# OPENAI CALL
# ============================================================

def call_openai_json(model: str, system_prompt: str, user_prompt: str) -> tuple[dict, dict]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    data = extract_json_object(content)
    usage = usage_from_response(response)

    return data, usage


# ============================================================
# SOLVER PASS
# ============================================================

def ask_openai_solver(questions: list) -> dict:
    prompt = f"""
You are solving {CLASS_CATEGORY} {SUBJECT} objective CBT questions.

Return ONLY valid JSON in this exact format:

{{
  "answers": [
    {{
      "id": 1,
      "correctOption": "A",
      "reason": "short reason",
      "confidence": "high",
      "possibleTypo": false,
      "typoNote": ""
    }}
  ]
}}

Rules:
- correctOption must be only A, B, C, or D.
- confidence must be only high, medium, or low.
- possibleTypo must be true if the question wording is chemically/scientifically wrong, ambiguous, or likely mistyped.
- If the question has a typo, choose the most likely intended school-exam answer but mark possibleTypo true.
- Do not include markdown.
- Do not include text outside JSON.
- Keep the same question IDs.

Questions:
{json.dumps(questions, indent=2, ensure_ascii=False)}
""".strip()

    data, usage = call_openai_json(
        model=OPENAI_MODEL_SOLVER,
        system_prompt=f"You are a strict {SUBJECT} exam answer solver. Return valid JSON only.",
        user_prompt=prompt,
    )

    answers = []

    for item in data.get("answers", []):
        answers.append({
            "id": int(item.get("id")),
            "correctOption": normalize_option(item.get("correctOption")),
            "reason": str(item.get("reason", "")).strip(),
            "confidence": safe_confidence(item.get("confidence")),
            "possibleTypo": bool(item.get("possibleTypo", False)),
            "typoNote": str(item.get("typoNote", "")).strip(),
        })

    return {
        "model": OPENAI_MODEL_SOLVER,
        "answers": answers,
        "usage": usage,
    }


# ============================================================
# VERIFIER PASS
# ============================================================

def ask_openai_verifier(questions: list, solver_result: dict) -> dict:
    prompt = f"""
You are verifying {CLASS_CATEGORY} {SUBJECT} objective answers for an online CBT system.

You must check:
1. Which option is academically correct.
2. Whether the question has a typo, bad wording, or contradiction.
3. Whether the answer is safe for automatic marking.
4. Whether teacher review is required.

Return ONLY valid JSON in this exact format:

{{
  "verified": [
    {{
      "id": 1,
      "verifiedOption": "A",
      "confidence": "high",
      "needsReview": false,
      "reviewReason": "",
      "typoDetected": false,
      "typoNote": "",
      "finalExplanation": "short explanation"
    }}
  ]
}}

Rules:
- verifiedOption must be A, B, C, or D.
- confidence must be high, medium, or low.
- needsReview must be true if:
  - question wording is suspicious,
  - the answer depends on an assumed typo,
  - confidence is not high,
  - there is any academic ambiguity,
  - the question contains document/header pollution,
  - the solver answer is wrong or doubtful.
- Minor spelling typo in a clearly wrong option should not require review if final answer is obvious.
- Do not include markdown.
- Do not include text outside JSON.

Questions:
{json.dumps(questions, indent=2, ensure_ascii=False)}

Solver result:
{json.dumps(solver_result, indent=2, ensure_ascii=False)}
""".strip()

    data, usage = call_openai_json(
        model=OPENAI_MODEL_VERIFIER,
        system_prompt=f"You are a strict {SUBJECT} answer verifier for a school CBT system. Return valid JSON only.",
        user_prompt=prompt,
    )

    verified = []

    for item in data.get("verified", []):
        verified.append({
            "id": int(item.get("id")),
            "verifiedOption": normalize_option(item.get("verifiedOption")),
            "confidence": safe_confidence(item.get("confidence")),
            "needsReview": bool(item.get("needsReview", True)),
            "reviewReason": str(item.get("reviewReason", "")).strip(),
            "typoDetected": bool(item.get("typoDetected", False)),
            "typoNote": str(item.get("typoNote", "")).strip(),
            "finalExplanation": str(item.get("finalExplanation", "")).strip(),
        })

    return {
        "model": OPENAI_MODEL_VERIFIER,
        "verified": verified,
        "usage": usage,
    }


# ============================================================
# FINAL CONSENSUS
# ============================================================

def build_final_report(questions: list, solver_result: dict, verifier_result: dict) -> list:
    solver_map = {
        int(item["id"]): item
        for item in solver_result.get("answers", [])
    }

    verifier_map = {
        int(item["id"]): item
        for item in verifier_result.get("verified", [])
    }

    report = []

    for question in questions:
        qid = int(question.get("id"))
        solver = solver_map.get(qid, {})
        verifier = verifier_map.get(qid, {})
        suspicion = local_suspicion_check(question)

        solver_option = normalize_option(solver.get("correctOption"))
        verifier_option = normalize_option(verifier.get("verifiedOption"))

        needs_review = False
        review_reasons = []
        warnings = []

        if not solver_option:
            needs_review = True
            review_reasons.append("Solver returned no answer.")

        if not verifier_option:
            needs_review = True
            review_reasons.append("Verifier returned no answer.")

        if solver_option and verifier_option and solver_option != verifier_option:
            needs_review = True
            review_reasons.append("Solver and verifier disagreed.")

        if safe_confidence(solver.get("confidence")) != "high":
            needs_review = True
            review_reasons.append("Solver confidence is not high.")

        if safe_confidence(verifier.get("confidence")) != "high":
            needs_review = True
            review_reasons.append("Verifier confidence is not high.")

        if suspicion["hardSuspicious"]:
            needs_review = True
            review_reasons.extend(suspicion["hardFlags"])

        if bool(solver.get("possibleTypo")) or bool(verifier.get("typoDetected")):
            needs_review = True
            review_reasons.append("Possible typo or ambiguous wording detected.")

        if verifier.get("needsReview", True):
            needs_review = True
            if verifier.get("reviewReason"):
                review_reasons.append(verifier.get("reviewReason"))

        if suspicion["softSuspicious"]:
            warnings.extend(suspicion["softFlags"])

        # IMPORTANT:
        # The final JSON should still receive the best available answer.
        # needsReview remains in the review report only, not the student JSON.
        final_option = ""

        if solver_option and verifier_option and solver_option == verifier_option:
            final_option = verifier_option
        elif verifier_option:
            final_option = verifier_option
        elif solver_option:
            final_option = solver_option

        expected = EXPECTED_ANSWERS.get(qid, "")
        expected_match = bool(expected and final_option and final_option == expected)

        report.append({
            "id": qid,
            "question": question.get("question", ""),
            "options": question.get("options", []),
            "solverOption": solver_option,
            "verifierOption": verifier_option,
            "finalOption": final_option,
            "needsReview": needs_review,
            "reviewReasons": sorted(set([r for r in review_reasons if r])),
            "warnings": sorted(set([w for w in warnings if w])),
            "expected": expected,
            "expectedMatch": expected_match,
            "solverDetails": solver,
            "verifierDetails": verifier,
        })

    return report


def apply_answers_to_exam_json(exam_json: dict, final_report: list) -> dict:
    report_map = {
        int(item["id"]): item
        for item in final_report
    }

    clean_json = {
        "subject": exam_json.get("subject", SUBJECT),
        "class": exam_json.get("class_category", CLASS_CATEGORY),
        "session": "2024/2025",
        "time_allowed_minutes": 120,
        "questions": []
    }

    for q in exam_json.get("questions", []):
        qid = int(q.get("id"))
        item = report_map.get(qid, {})

        clean_question = {
            "id": qid,
            "diagram": q.get("diagram", None),
            "question": q.get("question", ""),
            "options": q.get("options", []),
            "correctOption": item.get("finalOption", "")
        }

        clean_json["questions"].append(clean_question)

    return clean_json

# ============================================================
# MAIN
# ============================================================

def main():
    print("\n" + "=" * 70)
    print("EMIS OPENAI ANSWER TEST — CHEMISTRY SS2")
    print("=" * 70)

    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY missing in .env")
        return

    if not TEST_DOCX.exists():
        print(f"❌ File not found: {TEST_DOCX}")
        return

    print(f"✅ Solver model: {OPENAI_MODEL_SOLVER}")
    print(f"✅ Verifier model: {OPENAI_MODEL_VERIFIER}")

    print("\n[1] Extracting questions...")

    extracted = extract_source_file(
        file_path=str(TEST_DOCX),
        subject=SUBJECT,
        class_category=CLASS_CATEGORY,
        objective_only=True,
        extract_diagrams=True,
    )

    result = generate_exam_json_from_text(
        clean_text=extracted["clean_text"],
        subject=SUBJECT,
        class_category=CLASS_CATEGORY,
        expected_questions=EXPECTED_QUESTIONS,
        diagram_map=extracted.get("diagram_map", {}),
        use_llm=False,
    )

    exam_json = result["data"]
    all_questions = exam_json.get("questions", [])

    questions = all_questions[:TEST_LIMIT] if TEST_LIMIT else all_questions

    print(f"✅ Parsed questions: {len(all_questions)}")
    print(f"✅ Testing questions: {len(questions)}")

    print("\n[2] Running OpenAI solver...")

    solver_result = ask_openai_solver(questions)
    print("✅ Solver completed")
    print(f"Solver usage: {solver_result['usage']}")

    print("\n[3] Running OpenAI verifier...")

    verifier_result = ask_openai_verifier(questions, solver_result)
    print("✅ Verifier completed")
    print(f"Verifier usage: {verifier_result['usage']}")

    print("\n[4] Building final report...")

    final_report = build_final_report(
        questions=questions,
        solver_result=solver_result,
        verifier_result=verifier_result,
    )

    safe_count = 0
    review_count = 0
    expected_match_count = 0

    for item in final_report:
        status = "✅ SAFE" if not item["needsReview"] else "⚠️ REVIEW"

        if not item["needsReview"]:
            safe_count += 1

        if item["needsReview"]:
            review_count += 1

        if item.get("expectedMatch"):
            expected_match_count += 1

        print(
            f"{status} Q{item['id']}: "
            f"Solver={item['solverOption']} | "
            f"Verifier={item['verifierOption']} | "
            f"Final={item['finalOption'] or 'EMPTY'} | "
            f"Expected={item['expected'] or '-'}"
        )

        if item["needsReview"]:
            for reason in item["reviewReasons"][:3]:
                print(f"   - {reason}")

    final_exam_json = apply_answers_to_exam_json(exam_json, final_report)

    total_input_tokens = solver_result["usage"]["input_tokens"] + verifier_result["usage"]["input_tokens"]
    total_output_tokens = solver_result["usage"]["output_tokens"] + verifier_result["usage"]["output_tokens"]
    total_tokens = solver_result["usage"]["total_tokens"] + verifier_result["usage"]["total_tokens"]
    total_cost = round(
        solver_result["usage"]["estimated_cost_usd"] + verifier_result["usage"]["estimated_cost_usd"],
        6,
    )

    full_output = {
        "subject": SUBJECT,
        "class_category": CLASS_CATEGORY,
        "source_file": str(TEST_DOCX),
        "tested_questions": len(questions),
        "safe_answers": safe_count,
        "needs_review": review_count,
        "expected_match_count": expected_match_count,
        "models": {
            "solver": OPENAI_MODEL_SOLVER,
            "verifier": OPENAI_MODEL_VERIFIER,
        },
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": total_cost,
        },
        "solver_result": solver_result,
        "verifier_result": verifier_result,
        "final_report": final_report,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(full_output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    FINAL_JSON_OUTPUT.write_text(
        json.dumps(final_exam_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 70)
    print("DONE")
    print(f"Safe answers: {safe_count}")
    print(f"Needs review: {review_count}")
    print(f"Expected matches: {expected_match_count}/{len(questions)}")
    print(f"Input tokens: {total_input_tokens}")
    print(f"Output tokens: {total_output_tokens}")
    print(f"Estimated cost: ${total_cost}")
    print(f"Report saved: {OUTPUT_FILE}")
    print(f"Final JSON saved: {FINAL_JSON_OUTPUT}")
    print("=" * 70)


if __name__ == "__main__":
    main()
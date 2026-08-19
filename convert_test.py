# ============================================================
# convert_test.py — EMIS SAFE DOCX → CBT JSON TEST
# Extracts DOCX, parses questions, solves answers with multi-Groq,
# verifies answers, flags risky questions, and saves final JSON.
# ============================================================

import os
import re
import json
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
from groq import Groq

from convert import (
    extract_source_file,
    generate_exam_json_from_text,
    validate_exam_json,
)

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

TEST_DOCX = Path("static/testing/chem_ss2.docx")
OUTPUT_DIR = Path("static/testing")

TEXT_OUTPUT = OUTPUT_DIR / "chem_ss2_extracted.txt"
JSON_OUTPUT = OUTPUT_DIR / "chem_ss2_generated_safe_answers.json"
REVIEW_OUTPUT = OUTPUT_DIR / "chem_ss2_answer_review_report.json"
VALIDATION_OUTPUT = OUTPUT_DIR / "chem_ss2_validation.json"

SUBJECT = "Chemistry"
CLASS_CATEGORY = "SS2"
EXPECTED_QUESTIONS = 50

# Use all questions. Change to 15 if testing only first 15.
TEST_LIMIT = None

BATCH_SIZE = 10

# ============================================================
# GROQ KEYS / MODELS
# ============================================================

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY", "").strip(),
    os.getenv("GROQ_API_KEY2", "").strip(),
    os.getenv("GROQ_API_KEY3", "").strip(),
    os.getenv("GROQ_API_KEY4", "").strip(),
    os.getenv("GROQ_API_KEY5", "").strip(),
]

GROQ_KEYS = [key for key in GROQ_KEYS if key]

SOLVER_MODELS = [
    os.getenv("GROQ_MODEL_SOLVER_1", "llama-3.3-70b-versatile").strip(),
    os.getenv("GROQ_MODEL_SOLVER_2", "llama-3.3-70b-versatile").strip(),
    os.getenv("GROQ_MODEL_SOLVER_3", "llama-3.3-70b-versatile").strip(),
]

VERIFIER_MODEL = os.getenv("GROQ_MODEL_VERIFIER", "llama-3.3-70b-versatile").strip()


# ============================================================
# JSON HELPERS
# ============================================================

def extract_json_object(text: str) -> dict:
    text = str(text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"AI did not return JSON:\n{text}")

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


def chunk_list(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]


# ============================================================
# TYPO / RISK DETECTOR
# ============================================================

def local_suspicion_check(question: dict) -> dict:
    qid = question.get("id")
    qtext = str(question.get("question", "")).lower()
    options_text = " ".join(question.get("options", [])).lower()
    joined = f"{qtext} {options_text}"

    hard_flags = []
    soft_flags = []

    # Hard chemistry contradictions
    if "ethane" in qtext and any(word in qtext for word in [
        "addition", "bromine", "polymer", "unsaturation", "decolorize", "decolourize"
    ]):
        hard_flags.append("Question mentions ethane but reaction pattern suggests ethene/unsaturation.")

    if "ethane" in qtext and "long chain" in qtext:
        hard_flags.append("Ethane does not polymerize into a long chain under normal school chemistry context; likely meant ethene.")

    if "ethane" in qtext and "bromine" in qtext and "room temperature" in qtext:
        hard_flags.append("Ethane does not readily add bromine at room temperature; likely meant ethene.")

    if "ethane is produced from ethanol" in qtext:
        hard_flags.append("Dehydration of ethanol produces ethene, not ethane.")

    if "hydrogenation of butane" in qtext:
        hard_flags.append("Butane is already saturated; hydrogenation wording may be wrong.")

    if "benzene" in qtext and ("decolorize bromine water" in qtext or "decolourize bromine water" in qtext):
        hard_flags.append("Benzene does not normally decolourize bromine water without catalyst/light; check wording.")

    # Soft spelling typos: do not block final answer alone
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
# GROQ CALL
# ============================================================

def call_groq_json(api_key: str, model: str, system_prompt: str, user_prompt: str) -> dict:
    client = Groq(api_key=api_key)

    res = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    return extract_json_object(res.choices[0].message.content)


# ============================================================
# SOLVER
# ============================================================

def ask_solver(api_key: str, model: str, questions: list, solver_name: str) -> dict:
    prompt = f"""
You are solving {CLASS_CATEGORY} {SUBJECT} objective questions.

Return ONLY valid JSON in this exact format:

{{
  "answers": [
    {{
      "id": 1,
      "correctOption": "A",
      "reason": "short chemistry reason",
      "confidence": "high",
      "possibleTypo": false,
      "typoNote": ""
    }}
  ]
}}

Rules:
- correctOption must be only A, B, C, or D.
- confidence must be only high, medium, or low.
- possibleTypo must be true if the question wording is chemically wrong or ambiguous.
- If the question has a typo, choose the most likely intended school-exam answer.
- Do not include markdown.
- Do not include text outside JSON.
- Keep the same question IDs.

Questions:
{json.dumps(questions, indent=2, ensure_ascii=False)}
""".strip()

    result = call_groq_json(
        api_key=api_key,
        model=model,
        system_prompt=f"You are a strict {SUBJECT} exam answer solver. Return valid JSON only.",
        user_prompt=prompt,
    )

    cleaned = []

    for item in result.get("answers", []):
        cleaned.append({
            "id": int(item.get("id")),
            "correctOption": normalize_option(item.get("correctOption")),
            "reason": str(item.get("reason", "")).strip(),
            "confidence": safe_confidence(item.get("confidence")),
            "possibleTypo": bool(item.get("possibleTypo", False)),
            "typoNote": str(item.get("typoNote", "")).strip(),
            "solver": solver_name,
            "model": model,
        })

    return {
        "solver": solver_name,
        "model": model,
        "answers": cleaned,
    }


# ============================================================
# VERIFIER
# ============================================================

def ask_verifier(api_key: str, model: str, questions: list, solver_votes: list) -> dict:
    prompt = f"""
You are verifying {CLASS_CATEGORY} {SUBJECT} objective answers for a CBT exam system.

You must check:
1. Which option is academically correct.
2. Whether the question has a typo or bad wording.
3. Whether this answer is safe for automatic marking.
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
  - solvers disagree,
  - the correct answer depends on assumed typo,
  - confidence is not high,
  - there is chemistry ambiguity,
  - question wording contradicts the likely intended answer.
- Minor spelling typo in an option should NOT require review if the answer is otherwise clear.
- Do not include markdown.
- Do not include text outside JSON.

Questions:
{json.dumps(questions, indent=2, ensure_ascii=False)}

Solver votes:
{json.dumps(solver_votes, indent=2, ensure_ascii=False)}
""".strip()

    result = call_groq_json(
        api_key=api_key,
        model=model,
        system_prompt=f"You are a strict {SUBJECT} answer verifier for a school CBT system. Return valid JSON only.",
        user_prompt=prompt,
    )

    cleaned = []

    for item in result.get("verified", []):
        cleaned.append({
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
        "verifier_model": model,
        "verified": cleaned,
    }


# ============================================================
# CONSENSUS
# ============================================================

def build_consensus_report(questions: list, solver_results: list, verifier_result: dict) -> list:
    verifier_map = {
        int(item["id"]): item
        for item in verifier_result.get("verified", [])
    }

    report = []

    for question in questions:
        qid = int(question.get("id"))
        suspicion = local_suspicion_check(question)

        votes = []
        vote_details = []

        for solver_result in solver_results:
            for ans in solver_result.get("answers", []):
                if int(ans.get("id")) == qid:
                    opt = normalize_option(ans.get("correctOption"))
                    if opt:
                        votes.append(opt)
                    vote_details.append(ans)

        vote_counter = Counter(votes)
        majority_option = vote_counter.most_common(1)[0][0] if vote_counter else ""

        total_votes = len(votes)
        agreement_count = vote_counter.get(majority_option, 0)
        agreement_ratio = round(agreement_count / total_votes, 2) if total_votes else 0

        verifier = verifier_map.get(qid, {})
        verifier_option = normalize_option(verifier.get("verifiedOption"))
        verifier_confidence = safe_confidence(verifier.get("confidence"))

        all_solvers_agree = total_votes > 0 and agreement_count == total_votes
        verifier_agrees = bool(verifier_option and verifier_option == majority_option)

        solver_low_confidence = any(
            safe_confidence(v.get("confidence")) != "high"
            for v in vote_details
        )

        solver_typo_detected = any(
            bool(v.get("possibleTypo"))
            for v in vote_details
        )

        needs_review = False
        review_reasons = []
        warnings = []

        # Hard fail-safe 1: no complete solver answer
        if total_votes < min(3, len(GROQ_KEYS)):
            needs_review = True
            review_reasons.append("Not enough solver votes were returned.")

        # Hard fail-safe 2: solver disagreement
        if not all_solvers_agree:
            needs_review = True
            review_reasons.append("Solver models disagreed.")

        # Hard fail-safe 3: verifier disagreement
        if not verifier_agrees:
            needs_review = True
            review_reasons.append("Verifier disagreed with solver majority.")

        # Hard fail-safe 4: chemistry contradiction / bad wording
        if suspicion["hardSuspicious"]:
            needs_review = True
            review_reasons.extend(suspicion["hardFlags"])

        # Hard fail-safe 5: low confidence
        if solver_low_confidence or verifier_confidence != "high":
            needs_review = True
            review_reasons.append("One or more AI passes did not return high confidence.")

        # Hard fail-safe 6: AI says typo AND verifier says review
        if (solver_typo_detected or verifier.get("typoDetected")) and verifier.get("needsReview", False):
            needs_review = True
            review_reasons.append("AI detected possible typo or ambiguous wording.")

        # Hard fail-safe 7: verifier explicitly requests review
        if verifier.get("needsReview", True):
            needs_review = True
            if verifier.get("reviewReason"):
                review_reasons.append(verifier.get("reviewReason"))

        # Soft typo warnings only
        if suspicion["softSuspicious"]:
            warnings.extend(suspicion["softFlags"])

        final_option = ""

        if not needs_review and majority_option and verifier_agrees:
            final_option = majority_option

        report.append({
            "id": qid,
            "question": question.get("question", ""),
            "options": question.get("options", []),
            "solverVotes": votes,
            "voteCounts": dict(vote_counter),
            "majorityOption": majority_option,
            "agreementRatio": agreement_ratio,
            "verifierOption": verifier_option,
            "finalOption": final_option,
            "needsReview": needs_review,
            "reviewReasons": sorted(set([r for r in review_reasons if r])),
            "warnings": sorted(set([w for w in warnings if w])),
            "solverDetails": vote_details,
            "verifierDetails": verifier,
        })

    return report


# ============================================================
# APPLY SAFE ANSWERS
# ============================================================

def apply_safe_answers_to_exam_json(exam_json: dict, consensus_report: list) -> dict:
    report_map = {
        int(item["id"]): item
        for item in consensus_report
    }

    final_json = json.loads(json.dumps(exam_json, ensure_ascii=False))

    for q in final_json.get("questions", []):
        qid = int(q.get("id"))
        item = report_map.get(qid)

        if not item:
            q["correctOption"] = ""
            q["needsReview"] = True
            q["reviewReasons"] = ["No answer consensus generated."]
            q["aiMajorityOption"] = ""
            q["aiVerifierOption"] = ""
            q["aiAgreementRatio"] = 0
            q["aiWarnings"] = []
            continue

        q["correctOption"] = item.get("finalOption", "")
        q["needsReview"] = bool(item.get("needsReview", True))
        q["reviewReasons"] = item.get("reviewReasons", [])
        q["aiWarnings"] = item.get("warnings", [])
        q["aiMajorityOption"] = item.get("majorityOption", "")
        q["aiVerifierOption"] = item.get("verifierOption", "")
        q["aiAgreementRatio"] = item.get("agreementRatio", 0)

    return final_json


# ============================================================
# RUN ANSWER PIPELINE
# ============================================================

def run_answer_pipeline(questions: list) -> dict:
    solver_results_all = []
    verifier_results_all = []
    consensus_all = []

    batches = chunk_list(questions, BATCH_SIZE)

    solver_count = min(3, len(GROQ_KEYS))

    for batch_index, batch_questions in enumerate(batches, start=1):
        print(f"\n[AI] Batch {batch_index}/{len(batches)} — Questions {batch_questions[0]['id']} to {batch_questions[-1]['id']}")

        batch_solver_results = []

        for idx in range(solver_count):
            api_key = GROQ_KEYS[idx]
            model = SOLVER_MODELS[idx] if idx < len(SOLVER_MODELS) else SOLVER_MODELS[0]
            solver_name = f"solver_{idx + 1}"

            try:
                print(f" - Running {solver_name} with {model}")
                solver_result = ask_solver(
                    api_key=api_key,
                    model=model,
                    questions=batch_questions,
                    solver_name=solver_name,
                )
                batch_solver_results.append(solver_result)
                print(f"   ✅ {solver_name} completed")
            except Exception as e:
                print(f"   ❌ {solver_name} failed: {e}")

        if not batch_solver_results:
            print("   ❌ No solver result for this batch.")
            continue

        verifier_key = GROQ_KEYS[3] if len(GROQ_KEYS) >= 4 else GROQ_KEYS[-1]

        try:
            print(f" - Running verifier with {VERIFIER_MODEL}")
            verifier_result = ask_verifier(
                api_key=verifier_key,
                model=VERIFIER_MODEL,
                questions=batch_questions,
                solver_votes=batch_solver_results,
            )
            print("   ✅ Verifier completed")
        except Exception as e:
            print(f"   ❌ Verifier failed: {e}")
            verifier_result = {
                "verifier_model": VERIFIER_MODEL,
                "verified": [],
            }

        batch_consensus = build_consensus_report(
            questions=batch_questions,
            solver_results=batch_solver_results,
            verifier_result=verifier_result,
        )

        solver_results_all.extend(batch_solver_results)
        verifier_results_all.append(verifier_result)
        consensus_all.extend(batch_consensus)

    return {
        "solver_results": solver_results_all,
        "verifier_results": verifier_results_all,
        "consensus_report": consensus_all,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n" + "=" * 70)
    print("EMIS SAFE CONVERTER TEST — CHEMISTRY SS2")
    print("=" * 70)

    if not TEST_DOCX.exists():
        print(f"❌ File not found: {TEST_DOCX}")
        return

    if not GROQ_KEYS:
        print("❌ No Groq API keys found in .env")
        print("Add GROQ_API_KEY, GROQ_API_KEY2, GROQ_API_KEY3, GROQ_API_KEY4, GROQ_API_KEY5")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"✅ Groq keys available: {len(GROQ_KEYS)}")

    print("\n[1] Extracting clean text...")

    extracted = extract_source_file(
        file_path=str(TEST_DOCX),
        subject=SUBJECT,
        class_category=CLASS_CATEGORY,
        objective_only=True,
        extract_diagrams=True,
    )

    clean_text = extracted.get("clean_text", "")
    diagram_map = extracted.get("diagram_map", {})

    TEXT_OUTPUT.write_text(clean_text, encoding="utf-8")

    print(f"✅ Clean text saved: {TEXT_OUTPUT}")
    print(f"✅ Subject: {extracted.get('subject')}")
    print(f"✅ Class: {extracted.get('class_category')}")
    print(f"✅ Question estimate: {extracted.get('question_estimate')}")
    print(f"✅ Diagrams found: {extracted.get('diagram_count')}")

    print("\n[2] Generating base CBT JSON without answers...")

    result = generate_exam_json_from_text(
        clean_text=clean_text,
        subject=SUBJECT,
        class_category=CLASS_CATEGORY,
        expected_questions=EXPECTED_QUESTIONS,
        diagram_map=diagram_map,
        use_llm=False,
    )

    base_exam_json = result.get("data", {})
    all_questions = base_exam_json.get("questions", [])

    if TEST_LIMIT:
        answer_questions = all_questions[:TEST_LIMIT]
    else:
        answer_questions = all_questions

    print(f"✅ Base questions parsed: {len(all_questions)}")
    print(f"✅ Questions sent for answer validation: {len(answer_questions)}")

    print("\n[3] Running multi-Groq answer validation...")

    answer_pipeline = run_answer_pipeline(answer_questions)
    consensus_report = answer_pipeline["consensus_report"]

    final_exam_json = apply_safe_answers_to_exam_json(
        exam_json=base_exam_json,
        consensus_report=consensus_report,
    )

    validation = validate_exam_json(
        final_exam_json,
        expected_questions=EXPECTED_QUESTIONS,
    )

    safe_count = sum(
        1 for q in final_exam_json.get("questions", [])
        if q.get("correctOption") in {"A", "B", "C", "D"} and not q.get("needsReview")
    )

    review_count = sum(
        1 for q in final_exam_json.get("questions", [])
        if q.get("needsReview")
    )

    missing_answers = sum(
        1 for q in final_exam_json.get("questions", [])
        if q.get("correctOption") not in {"A", "B", "C", "D"}
    )

    print("\n[4] Saving outputs...")

    JSON_OUTPUT.write_text(
        json.dumps(final_exam_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    review_output = {
        "subject": SUBJECT,
        "class_category": CLASS_CATEGORY,
        "source_file": str(TEST_DOCX),
        "total_questions": len(all_questions),
        "answered_questions_checked": len(answer_questions),
        "safe_answers": safe_count,
        "needs_review": review_count,
        "missing_answers": missing_answers,
        "solver_models": SOLVER_MODELS,
        "verifier_model": VERIFIER_MODEL,
        "consensus_report": consensus_report,
        "solver_results": answer_pipeline["solver_results"],
        "verifier_results": answer_pipeline["verifier_results"],
    }

    REVIEW_OUTPUT.write_text(
        json.dumps(review_output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    VALIDATION_OUTPUT.write_text(
        json.dumps(validation, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"✅ Final JSON saved: {JSON_OUTPUT}")
    print(f"✅ Review report saved: {REVIEW_OUTPUT}")
    print(f"✅ Validation saved: {VALIDATION_OUTPUT}")

    print("\n[5] Summary")
    print(f"Subject: {final_exam_json.get('subject')}")
    print(f"Class: {final_exam_json.get('class_category')}")
    print(f"Questions: {len(final_exam_json.get('questions', []))}")
    print(f"Groups: {len(final_exam_json.get('groups', []))}")
    print(f"Safe answers: {safe_count}")
    print(f"Needs review: {review_count}")
    print(f"Missing answers: {missing_answers}")
    print(f"Valid structure: {validation.get('valid')}")
    print(f"Issues: {len(validation.get('issues', []))}")
    print(f"Warnings: {len(validation.get('warnings', []))}")

    if validation.get("issues"):
        print("\nIssues:")
        for issue in validation["issues"]:
            print(f" - {issue}")

    if validation.get("warnings"):
        print("\nWarnings:")
        for warning in validation["warnings"]:
            print(f" - {warning}")

    print("\n🎉 DONE")


if __name__ == "__main__":
    main()
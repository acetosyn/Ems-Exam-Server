# ============================================================
# convert_ext.py — EMIS CONVERTER EXTENSIONS
# OpenAI Answer Solver + Verifier + Review Report + Save Helpers
# Term-Aware Build for JSS1 / JSS2 / JSS3
# ============================================================

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

from modules.class_config import (
    normalize_class_level,
    normalize_subject_display,
    normalize_subject_key,
)


# ============================================================
# ENV
# ============================================================

load_dotenv()


# ============================================================
# PATHS
# ============================================================

_THIS_FILE = Path(__file__).resolve()

if (_THIS_FILE.parent / "static").exists():
    BASE_DIR = _THIS_FILE.parent
elif (_THIS_FILE.parent.parent / "static").exists():
    BASE_DIR = _THIS_FILE.parent.parent
else:
    BASE_DIR = Path.cwd()

STATIC_DIR = BASE_DIR / "static"
BASE_SUBJECTS_DIR = STATIC_DIR / "subjects"
CONVERT_DRAFTS_DIR = STATIC_DIR / "uploads" / "convert-drafts"

BASE_SUBJECTS_DIR.mkdir(parents=True, exist_ok=True)
CONVERT_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CLASS / TERM CONFIG
# ============================================================

SUPPORTED_CLASS_LEVELS = {
    "JSS1", "JSS2", "JSS3",
    "SS1", "SS2", "SS3",
}

TERM_AWARE_CLASSES = {
    "JSS1", "JSS2", "JSS3",
}

VALID_TERMS = {
    "FIRST", "SECOND", "THIRD",
}


# ============================================================
# OPENAI CONFIG
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL_SOLVER = os.getenv("OPENAI_MODEL_SOLVER", "gpt-5.4").strip()
OPENAI_MODEL_VERIFIER = os.getenv("OPENAI_MODEL_VERIFIER", "gpt-5.4").strip()

OPENAI_INPUT_PRICE_PER_1M = float(os.getenv("OPENAI_INPUT_PRICE_PER_1M", "2.50"))
OPENAI_OUTPUT_PRICE_PER_1M = float(os.getenv("OPENAI_OUTPUT_PRICE_PER_1M", "15.00"))

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============================================================
# GENERAL HELPERS
# ============================================================

def safe_slug(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "exam"


def normalize_option(value: str) -> str:
    value = str(value or "").strip().upper()
    return value[0] if value and value[0] in {"A", "B", "C", "D"} else ""


def safe_confidence(value: str) -> str:
    value = str(value or "").strip().lower()
    return value if value in {"high", "medium", "low"} else "low"


def normalize_exam_term(value: str = "") -> str:
    value = str(value or "").strip().upper()
    value = re.sub(r"[_\-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    compact = re.sub(r"[^A-Z0-9]", "", value)

    aliases = {
        "1": "FIRST", "01": "FIRST", "1ST": "FIRST", "FIRST": "FIRST",
        "FIRSTTERM": "FIRST", "1STTERM": "FIRST", "TERM1": "FIRST",

        "2": "SECOND", "02": "SECOND", "2ND": "SECOND", "SECOND": "SECOND",
        "SECONDTERM": "SECOND", "2NDTERM": "SECOND", "TERM2": "SECOND",

        "3": "THIRD", "03": "THIRD", "3RD": "THIRD", "THIRD": "THIRD",
        "THIRDTERM": "THIRD", "3RDTERM": "THIRD", "TERM3": "THIRD",
    }

    return aliases.get(compact, "")


def exam_term_label(term: str = "") -> str:
    term = normalize_exam_term(term)

    labels = {
        "FIRST": "1st Term",
        "SECOND": "2nd Term",
        "THIRD": "3rd Term",
    }

    return labels.get(term, "—")


def normalize_detected_class(value: str = "") -> str:
    raw = str(value or "").strip()

    if not raw:
        return ""

    try:
        normalized = normalize_class_level(raw)
        if normalized in SUPPORTED_CLASS_LEVELS:
            return normalized
    except Exception:
        pass

    compact = re.sub(r"[^A-Z0-9]", "", raw.upper())

    for class_name in ("JSS1", "JSS2", "JSS3"):
        if compact == class_name or compact.startswith(class_name):
            return class_name

    for class_name in ("SS1", "SS2", "SS3"):
        if compact == class_name or compact.startswith(class_name):
            return class_name

    return ""


def class_requires_term(class_category: str = "") -> bool:
    return normalize_detected_class(class_category) in TERM_AWARE_CLASSES


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


# ============================================================
# OPENAI USAGE / COST
# ============================================================

def estimate_openai_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1_000_000) * OPENAI_INPUT_PRICE_PER_1M
    output_cost = (output_tokens / 1_000_000) * OPENAI_OUTPUT_PRICE_PER_1M

    return round(input_cost + output_cost, 6)


def usage_from_openai_response(response) -> dict:
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
        "estimated_cost_usd": estimate_openai_cost(input_tokens, output_tokens),
    }


def combine_usage(*usage_items: dict) -> dict:
    input_tokens = sum(int((item or {}).get("input_tokens", 0) or 0) for item in usage_items)
    output_tokens = sum(int((item or {}).get("output_tokens", 0) or 0) for item in usage_items)
    total_tokens = sum(int((item or {}).get("total_tokens", 0) or 0) for item in usage_items)
    cost = sum(float((item or {}).get("estimated_cost_usd", 0) or 0) for item in usage_items)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(cost, 6),
    }


# ============================================================
# OPENAI JSON CALL
# ============================================================

def call_openai_json(model: str, system_prompt: str, user_prompt: str) -> Tuple[dict, dict]:
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is missing in .env")

    response = openai_client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content or ""
    data = extract_json_object(content)
    usage = usage_from_openai_response(response)

    return data, usage


# ============================================================
# LOCAL REVIEW / TYPO DETECTOR
# ============================================================

def local_answer_suspicion_check(question: dict) -> dict:
    qtext = str(question.get("question", "")).lower()
    options_text = " ".join(str(x) for x in question.get("options", [])).lower()
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
        "diagraam",
        "diaggram",
    ]

    for word in soft_typo_words:
        if word in joined:
            soft_flags.append(f"Possible spelling typo detected: {word}")

    return {
        "hardSuspicious": bool(hard_flags),
        "softSuspicious": bool(soft_flags),
        "hardFlags": hard_flags,
        "softFlags": soft_flags,
    }


# ============================================================
# OPENAI SOLVER
# ============================================================

def ask_openai_solver(subject: str, class_category: str, questions: list) -> dict:
    prompt = f"""
You are solving {class_category} {subject} objective CBT questions.

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
- possibleTypo must be true if wording is wrong, ambiguous, scientifically suspicious, or likely mistyped.
- If a question has a typo, choose the most likely intended school-exam answer but mark possibleTypo true.
- Do not include markdown.
- Do not include text outside JSON.
- Keep the same question IDs.
- Do not rewrite questions or options.

Questions:
{json.dumps(questions, indent=2, ensure_ascii=False)}
""".strip()

    data, usage = call_openai_json(
        model=OPENAI_MODEL_SOLVER,
        system_prompt=f"You are a strict {subject} school-exam answer solver. Return valid JSON only.",
        user_prompt=prompt,
    )

    answers = []

    for item in data.get("answers", []):
        try:
            qid = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        answers.append({
            "id": qid,
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
# OPENAI VERIFIER
# ============================================================

def ask_openai_verifier(
    subject: str,
    class_category: str,
    questions: list,
    solver_result: dict,
) -> dict:

    prompt = f"""
You are verifying {class_category} {subject} objective answers for an online CBT system.

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
- needsReview must be true if wording is suspicious, an answer depends on an assumed typo,
  confidence is not high, or there is academic ambiguity.
- Minor spelling mistakes in clearly wrong options do not require review if the final answer is obvious.
- Do not include markdown.
- Do not include text outside JSON.
- Keep the same question IDs.

Questions:
{json.dumps(questions, indent=2, ensure_ascii=False)}

Solver result:
{json.dumps(solver_result, indent=2, ensure_ascii=False)}
""".strip()

    data, usage = call_openai_json(
        model=OPENAI_MODEL_VERIFIER,
        system_prompt=f"You are a strict {subject} answer verifier for a school CBT system. Return valid JSON only.",
        user_prompt=prompt,
    )

    verified = []

    for item in data.get("verified", []):
        try:
            qid = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        verified.append({
            "id": qid,
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
# FINAL ANSWER REPORT
# ============================================================

def build_openai_answer_report(questions: list, solver_result: dict, verifier_result: dict) -> list:
    solver_map = {
        int(item["id"]): item
        for item in solver_result.get("answers", [])
        if item.get("id") is not None
    }

    verifier_map = {
        int(item["id"]): item
        for item in verifier_result.get("verified", [])
        if item.get("id") is not None
    }

    report = []

    for question in questions:
        try:
            qid = int(question.get("id"))
        except (TypeError, ValueError):
            continue

        solver = solver_map.get(qid, {})
        verifier = verifier_map.get(qid, {})
        suspicion = local_answer_suspicion_check(question)

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
                review_reasons.append(str(verifier.get("reviewReason")).strip())

        if suspicion["softSuspicious"]:
            warnings.extend(suspicion["softFlags"])

        final_option = ""

        if solver_option and verifier_option and solver_option == verifier_option:
            final_option = verifier_option
        elif verifier_option:
            final_option = verifier_option
        elif solver_option:
            final_option = solver_option

        report.append({
            "id": qid,
            "question": question.get("question", ""),
            "options": question.get("options", []),

            "solverOption": solver_option,
            "verifierOption": verifier_option,
            "finalOption": final_option,

            "needsReview": needs_review,
            "reviewReasons": sorted(set(reason for reason in review_reasons if reason)),
            "warnings": sorted(set(warning for warning in warnings if warning)),

            "solverDetails": solver,
            "verifierDetails": verifier,
        })

    return report


# ============================================================
# APPLY FINAL ANSWERS
# ============================================================

def apply_openai_answers(exam_json: dict, answer_report: list) -> dict:
    report_map = {
        int(item["id"]): item
        for item in answer_report
        if item.get("id") is not None
    }

    output = json.loads(json.dumps(exam_json or {}, ensure_ascii=False))

    for question in output.get("questions", []):
        try:
            qid = int(question.get("id"))
        except (TypeError, ValueError):
            continue

        item = report_map.get(qid, {})
        question["correctOption"] = normalize_option(item.get("finalOption", ""))

    return output


# ============================================================
# COMPLETE OPENAI ANSWER PIPELINE
# ============================================================

def solve_answers_with_openai(exam_json: dict, subject: str, class_category: str) -> dict:
    if not OPENAI_API_KEY:
        return {
            "json": exam_json,
            "answer_report": [],
            "solver_result": {},
            "verifier_result": {},
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0,
            },
            "needs_review": 0,
            "error": "OPENAI_API_KEY missing.",
        }

    questions = exam_json.get("questions", [])

    if not questions:
        return {
            "json": exam_json,
            "answer_report": [],
            "solver_result": {},
            "verifier_result": {},
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0,
            },
            "needs_review": 0,
            "error": "No questions supplied for OpenAI answering.",
        }

    solver_result = ask_openai_solver(subject, class_category, questions)
    verifier_result = ask_openai_verifier(subject, class_category, questions, solver_result)

    answer_report = build_openai_answer_report(
        questions=questions,
        solver_result=solver_result,
        verifier_result=verifier_result,
    )

    answered_json = apply_openai_answers(exam_json, answer_report)
    total_usage = combine_usage(solver_result.get("usage", {}), verifier_result.get("usage", {}))
    review_count = sum(1 for item in answer_report if item.get("needsReview"))

    return {
        "json": answered_json,
        "answer_report": answer_report,
        "solver_result": solver_result,
        "verifier_result": verifier_result,
        "usage": total_usage,
        "needs_review": review_count,
    }


# ============================================================
# SUBJECT FILE NAMES
# ============================================================

def subject_filename_slug(subject: str) -> str:
    subject = normalize_subject_display(subject or "General")
    key = normalize_subject_key(subject)

    aliases = {
        "ENGLISH LANGUAGE": "english",
        "ENGLISH": "english",

        "MATHEMATICS": "mathematics",
        "MATHS": "mathematics",
        "FURTHER MATHEMATICS": "further_mathematics",

        "CHEMISTRY": "chemistry",
        "PHYSICS": "physics",
        "BIOLOGY": "biology",

        "ECONOMICS": "economics",
        "GOVERNMENT": "government",
        "LITERATURE": "literature",

        "CIVIC EDUCATION": "civic",
        "CIVIC": "civic",

        "FINANCIAL ACCOUNT": "accounts",
        "FINANCIAL ACCOUNTING": "accounts",
        "ACCOUNT": "accounts",
        "ACCOUNTS": "accounts",

        "COMPUTER SCIENCE": "computer_science",
        "COMPUTER": "computer_science",

        "TECHNICAL DRAWING": "technical_drawing",
        "TECHNICAL": "technical_drawing",

        "AGRICULTURAL SCIENCE": "agricultural_science",
        "AGRICULTURE": "agricultural_science",

        "COMMERCE": "commerce",
        "MARKETING": "marketing",
        "GEOGRAPHY": "geography",

        "IRS": "irs",
        "ISLAMIC RELIGIOUS STUDIES": "irs",

        "IRK": "irk",
        "ISLAMIC RELIGIOUS KNOWLEDGE": "irk",

        "ARABIC": "arabic",
        "YORUBA": "yoruba",
        "HAUSA": "hausa",

        "POISE": "poise",
        "ISLAMIYYAH": "islamiyyah",

        "HCS": "hcs",

        "DIGITAL TECH": "digital_tech",
        "DIGITAL TECHNOLOGY": "digital_tech",

        "GARMENT MAKING": "garment_making",

        "P.H.E": "phe",
        "PHE": "phe",
    }

    return aliases.get(key, safe_slug(subject))


# ============================================================
# CLEAN STUDENT JSON
# ============================================================

def build_clean_student_json(
    data: Dict[str, Any],
    subject: str,
    class_category: str,
    session: str = "2024/2025",
    time_allowed_minutes: int = 120,
    term: str = "",
) -> Dict[str, Any]:

    data = data or {}

    subject = normalize_subject_display(subject or data.get("subject") or "General")

    class_category = normalize_detected_class(
        class_category or data.get("class_category") or data.get("class") or ""
    )

    term = normalize_exam_term(
        term
        or data.get("term")
        or data.get("exam_term")
        or data.get("academic_term")
        or ""
    )

    # SS classes intentionally do not carry term metadata.
    if not class_requires_term(class_category):
        term = ""

    exam_title = str(data.get("exam_title") or "").strip()

    # Avoid hard-coding "1st Term" when we now know the real term.
    if not exam_title:
        if term:
            exam_title = f"{exam_term_label(term)} Examination"
        else:
            exam_title = "Examination"

    final_data = {
        "school": data.get("school") or "EPITOME MODEL ISLAMIC SCHOOLS",
        "subject": subject,
        "exam_title": exam_title,
        "instructions": data.get("instructions") or "Answer all questions.",
        "time_allowed_minutes": int(data.get("time_allowed_minutes", time_allowed_minutes)),
        "class_category": class_category,
        "questions": [],
    }

    # Preserve useful session metadata if supplied.
    final_session = str(data.get("session") or session or "").strip()

    if final_session:
        final_data["session"] = final_session

    # JSS only.
    if class_requires_term(class_category) and term:
        final_data["term"] = term
        final_data["term_label"] = exam_term_label(term)

    for question in data.get("questions", []):
        try:
            qid = int(question.get("id"))
        except (TypeError, ValueError):
            continue

        options = question.get("options", [])

        if not isinstance(options, list):
            options = []

        final_data["questions"].append({
            "id": qid,
            "diagram": question.get("diagram") or None,
            "question": str(question.get("question", "")).strip(),
            "options": options,
            "correctOption": normalize_option(question.get("correctOption")),
        })

    final_data["questions"].sort(key=lambda item: item["id"])
    return final_data


# ============================================================
# SAVE EXAM JSON TO LIBRARY
# ============================================================

def save_exam_json(
    data: Dict[str, Any],
    year: str,
    subject: str = "",
    class_category: str = "",
    overwrite: bool = True,
    review_report: Optional[List[Dict[str, Any]]] = None,
    session: str = "2024/2025",
    time_allowed_minutes: int = 120,
    term: str = "",
) -> Dict[str, Any]:

    data = data or {}

    subject = normalize_subject_display(subject or data.get("subject") or "General")

    class_category = normalize_detected_class(
        class_category or data.get("class_category") or data.get("class") or ""
    )

    if not class_category:
        class_category = "UNSORTED"

    year = str(year or datetime.now().year).strip()

    detected_term = normalize_exam_term(
        term
        or data.get("term")
        or data.get("exam_term")
        or data.get("academic_term")
        or ""
    )

    # --------------------------------------------------------
    # JSS MUST HAVE A TERM
    # --------------------------------------------------------

    if class_requires_term(class_category) and not detected_term:
        raise ValueError(
            f"{class_category} is term-aware. "
            f"FIRST, SECOND or THIRD term is required before saving."
        )

    # SS classes remain flat.
    if not class_requires_term(class_category):
        detected_term = ""

    # --------------------------------------------------------
    # SAVE FOLDER
    #
    # JSS:
    # static/subjects/2026/subjects-json/JSS1/FIRST/
    #
    # SS:
    # static/subjects/2026/subjects-json/SS1/
    # --------------------------------------------------------

    folder = BASE_SUBJECTS_DIR / year / "subjects-json" / class_category

    if detected_term:
        folder = folder / detected_term

    folder.mkdir(parents=True, exist_ok=True)

    subject_slug = subject_filename_slug(subject)
    filename = f"{subject_slug}_{class_category.lower()}.json"
    out_path = folder / filename

    if out_path.exists() and not overwrite:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{subject_slug}_{class_category.lower()}_{stamp}.json"
        out_path = folder / filename

    # --------------------------------------------------------
    # BUILD CLEAN STUDENT JSON
    # --------------------------------------------------------

    final_data = build_clean_student_json(
        data=data,
        subject=subject,
        class_category=class_category,
        session=session,
        time_allowed_minutes=time_allowed_minutes,
        term=detected_term,
    )

    # Re-lock metadata before writing.
    final_data["subject"] = subject
    final_data["class_category"] = class_category

    if detected_term:
        final_data["term"] = detected_term
        final_data["term_label"] = exam_term_label(detected_term)
    else:
        final_data.pop("term", None)
        final_data.pop("term_label", None)

    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(final_data, file, indent=2, ensure_ascii=False)

    # --------------------------------------------------------
    # REVIEW REPORT
    # --------------------------------------------------------

    review_path = ""

    if review_report:
        review_folder = folder / "_review_reports"
        review_folder.mkdir(parents=True, exist_ok=True)

        review_filename = f"{subject_slug}_{class_category.lower()}_review.json"
        review_path_obj = review_folder / review_filename

        review_payload = {
            "year": year,
            "subject": subject,
            "class_category": class_category,
            "term": detected_term or None,
            "term_label": exam_term_label(detected_term) if detected_term else None,
            "question_count": len(final_data.get("questions", [])),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "report": review_report,
        }

        with open(review_path_obj, "w", encoding="utf-8") as file:
            json.dump(review_payload, file, indent=2, ensure_ascii=False)

        review_path = str(review_path_obj)

    return {
        "success": True,
        "filename": filename,
        "path": str(out_path),

        "review_path": review_path,

        "year": year,
        "subject": subject,
        "class_category": class_category,

        "term": detected_term or None,
        "term_label": exam_term_label(detected_term) if detected_term else None,

        "questions": len(final_data.get("questions", [])),
    }


# ============================================================
# TEMP DRAFT SAVE
# ============================================================

def save_convert_draft(
    student_json: Dict[str, Any],
    full_json: Dict[str, Any] = None,
    answer_report: List[Dict[str, Any]] = None,
    openai_usage: Dict[str, Any] = None,
    needs_review: int = 0,
    source_filename: str = "",
    year: str = "",
    subject: str = "",
    class_category: str = "",
    term: str = "",
) -> Dict[str, Any]:

    student_json = student_json or {}

    draft_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    subject = normalize_subject_display(subject or student_json.get("subject") or "General")

    class_category = normalize_detected_class(
        class_category or student_json.get("class_category") or student_json.get("class") or ""
    )

    year = str(year or datetime.now().year)

    detected_term = normalize_exam_term(
        term
        or student_json.get("term")
        or student_json.get("exam_term")
        or student_json.get("academic_term")
        or ""
    )

    if not class_requires_term(class_category):
        detected_term = ""

    # Keep draft student JSON metadata synchronized.
    student_json["subject"] = subject
    student_json["class_category"] = class_category

    if detected_term:
        student_json["term"] = detected_term
        student_json["term_label"] = exam_term_label(detected_term)
    else:
        student_json.pop("term", None)
        student_json.pop("term_label", None)

    draft_data = {
        "draft_id": draft_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),

        "source_filename": source_filename,

        "year": year,
        "subject": subject,
        "class_category": class_category,

        "term": detected_term or None,
        "term_label": exam_term_label(detected_term) if detected_term else None,

        "question_count": len(student_json.get("questions", [])),
        "needs_review": int(needs_review or 0),

        "openai_usage": openai_usage or {},

        "student_json": student_json,
        "full_json": full_json or {},
        "answer_report": answer_report or [],
    }

    out_path = CONVERT_DRAFTS_DIR / f"{draft_id}.json"

    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(draft_data, file, indent=2, ensure_ascii=False)

    return {
        "success": True,
        "draft_id": draft_id,
        "filename": out_path.name,
        "path": str(out_path),
        **draft_data,
    }


# ============================================================
# LIST DRAFTS
# ============================================================

def list_convert_drafts(limit: int = 20) -> List[Dict[str, Any]]:
    drafts = []

    for path in sorted(CONVERT_DRAFTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)

            drafts.append({
                "draft_id": data.get("draft_id") or path.stem,
                "created_at": data.get("created_at", ""),
                "source_filename": data.get("source_filename", ""),

                "year": data.get("year", ""),
                "subject": data.get("subject", ""),
                "class_category": data.get("class_category", ""),

                "term": data.get("term"),
                "term_label": data.get("term_label"),

                "question_count": data.get("question_count", 0),
                "needs_review": data.get("needs_review", 0),
                "openai_usage": data.get("openai_usage", {}),
            })

        except Exception as exc:
            print(f"Unable to read convert draft {path}: {exc}")
            continue

        if len(drafts) >= int(limit or 20):
            break

    return drafts


# ============================================================
# GET SINGLE DRAFT
# ============================================================

def get_convert_draft(draft_id: str) -> Dict[str, Any]:
    draft_id = safe_slug(draft_id)
    path = CONVERT_DRAFTS_DIR / f"{draft_id}.json"

    if not path.exists():
        raise FileNotFoundError("Draft not found.")

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# DELETE SINGLE DRAFT
# ============================================================

def delete_convert_draft(draft_id: str) -> Dict[str, Any]:
    draft_id = safe_slug(draft_id)
    path = CONVERT_DRAFTS_DIR / f"{draft_id}.json"

    if path.exists():
        path.unlink()

    return {
        "success": True,
        "draft_id": draft_id,
    }


# ============================================================
# CLEAR ALL DRAFTS
# ============================================================

def clear_convert_drafts() -> Dict[str, Any]:
    count = 0

    for path in CONVERT_DRAFTS_DIR.glob("*.json"):
        try:
            path.unlink()
            count += 1
        except Exception as exc:
            print(f"Unable to delete convert draft {path}: {exc}")

    return {
        "success": True,
        "deleted": count,
    }
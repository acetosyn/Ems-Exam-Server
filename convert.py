# ============================================================
# convert.py — WAEC CBT EXTRACTOR (2025 GROUPED EDITION)
# Targets JSON FORMAT of chemistry_ss3.json
# Supports:
#  • Passages (e.g. Stock Exchange in English)
#  • Grouped sections (SECTION 1, 2, etc.)
#  • Instructions + ranges (e.g. "answer 31–35")
#  • Diagrams folder extraction (for later linking)
#  • Sub/sup formatting for sciences
#  • JSON sanitizing + numeric safety
# ============================================================

import os
import re
import json
from groq import Groq
from dotenv import load_dotenv
from docx import Document

# ============================================================
# LOAD ENV / INIT CLIENT
# ============================================================
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise Exception("❌ Missing GROQ_API_KEY in .env")

client = Groq(api_key=API_KEY)

# ============================================================
# PATH CONFIG — FLASK STATIC STRUCTURE
# ============================================================
BASE_DOCX     = "static/subjects/subjects-docx"
BASE_JSON     = "static/subjects/subjects-json"
BASE_DIAGRAMS = "static/uploads/diagrams"


# ============================================================
# DETECT SUBJECT / CLASS
# ============================================================
def detect_subject(filename: str) -> str:
    n = filename.lower()
    if "math" in n:
        return "Mathematics"
    if "chem" in n:
        return "Chemistry"
    if "eng" in n:
        return "English"
    if "literature" in n:
        return "Literature"
    if "account" in n:
        return "Accounts"
    if "civic" in n:
        return "Civic"
    if "computer" in n:
        return "Computer"
    if "econom" in n:
        return "Economics"
    if "govern" in n or "govt" in n:
        return "Government"
    if "biology" in n:
        return "Biology"
    if "physic" in n:
        return "Physics"
    return "General"


def detect_class_category(filename: str) -> str:
    n = filename.lower()
    if "ss1" in n:
        return "SS1"
    if "ss2" in n:
        return "SS2"
    if "ss3" in n:
        return "SS3"
    return "GENERAL"


def detect_version(filename: str) -> str:
    m = re.search(r"(\d+)", filename)
    return m.group(1) if m else "1"


def class_from_version(v: str) -> str:
    return {"1": "SS1", "2": "SS2", "3": "SS3"}.get(v, "GENERAL")


# ============================================================
# EXPECTED QUESTION COUNT (BY PAPER)
# ============================================================
def expected_question_count(filename: str) -> int:
    """
    Default: 50
    Exceptions:
      - computer_ss1.docx → 60
      - english_ss2.docx  → 60
      - english_ss3.docx  → 80
    """
    n = filename.lower()
    if "computer_ss1" in n:
        return 60
    if "english_ss2" in n:
        return 60
    if "english_ss3" in n:
        return 80
    return 50


# ============================================================
# DOCX PARSER — TEXT + DIAGRAMS
# ============================================================
def extract_docx(path: str, diagram_out_dir: str):
    """
    Extract:
      • Paragraph text (joined with newlines)
      • Diagrams → static/uploads/diagrams/<subject_class>/
    NOTE:
      We only map diagram indexes; we are NOT yet auto-linking
      each diagram to specific questions.
    """
    doc = Document(path)
    full_text_lines = []
    diagram_map = {}

    os.makedirs(diagram_out_dir, exist_ok=True)

    # Extract text
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            full_text_lines.append(t)

    # Extract images in order
    img_index = 1
    rels = doc.part.rels
    for rel in rels:
        rel_obj = rels[rel]
        if "image" in rel_obj.target_ref:
            img_data = rel_obj.target_part.blob

            # Save as diagram_<index>.PNG to mirror your existing style
            fname = f"diagram_{img_index}.PNG"
            out_path = os.path.join(diagram_out_dir, fname)

            with open(out_path, "wb") as f:
                f.write(img_data)

            # Flask static path
            static_path = out_path.replace("static", "/static")
            diagram_map[str(img_index)] = static_path
            img_index += 1

    return "\n".join(full_text_lines), diagram_map


def clean_llm_json(raw: str) -> str:
    """
    SUPER PATCH — Converts ANY messy LLM output into valid JSON text.

    Handles:
    - Leading text before '{'
    - Trailing commentary after '}'
    - Missing quotes around keys
    - Trailing commas
    - Markdown formatting
    - Random line breaks
    - Spaces between brackets
    """

    if not raw:
        return "{}"

    raw = raw.strip()

    # Remove code fences
    raw = raw.replace("```json", "").replace("```", "")

    # Remove non-printable characters
    raw = re.sub(r"[\x00-\x1F\x7F]", "", raw)

    # Extract the FIRST JSON object found
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        raw = match.group(0)
    else:
        # If no braces, force create a shell JSON
        return "{}"

    # Remove trailing commas inside objects/arrays
    raw = re.sub(r",\s*([\]}])", r"\1", raw)

    # Fix missing quotes around keys (e.g. subject: → "subject":)
    raw = re.sub(r'(\s*)([A-Za-z0-9_]+)\s*:', r'\1"\2":', raw)

    # Remove duplicate commas
    raw = re.sub(r",\s*,", ",", raw)

    # Normalize quotes
    raw = raw.replace("“", '"').replace("”", '"')

    return raw



# ============================================================
# SUBSCRIPT / SUPERSCRIPT FORMATTER
# ============================================================
SUB_SUP_SUBJECTS = {
    "chemistry",
    "mathematics",
    "further mathematics",
    "physics",
    "biology",
}

def apply_sub_sup_formatting(text: str, subject: str = None) -> str:
    if not text or not subject:
        return text

    subj = subject.lower()
    if subj not in SUB_SUP_SUBJECTS:
        return text

    # Chemical subscripts → Al2O3 → Al<sub>2</sub>O<sub>3</sub>
    def chem_repl(m):
        elem, num = m.group(1), m.group(2)
        # avoid messing with tokens like SS1, WAEC, Q1, etc
        if elem.upper() in {"SS", "WA", "Q"}:
            return m.group(0)
        return f"{elem}<sub>{num}</sub>"

    text = re.sub(r"([A-Z][a-z]?)(\d+)", chem_repl, text)

    # Mathematical exponents → x^2 → x<sup>2</sup>
    text = re.sub(r"(\w)\^(\d+)", r"\1<sup>\2</sup>", text)

    return text

# ============================================================
# SIMPLE-MODE DETECTION
# ============================================================
def is_simple_paper(text: str, subject: str) -> bool:
    """
    Detect papers without sections, passages, or grouped instructions.
    These should use SIMPLE MODE (1 group only).

    Simple mode triggers when:
    - No 'SECTION' in text
    - No 'Use the following' / 'Use the information'
    - Subject is in the known simple list (Accounts, Civic, Govt, Economics)
    """
    subject = subject.lower()
    if subject in ["accounts", "civic", "government", "economics"]:
        return True

    t = text.lower()

    # multi-group signals
    if "section" in t:
        return False
    if "use the" in t and "answer" in t:
        return False
    if "passage" in t:
        return False

    # Default: simple
    return True




# ============================================================
# LLM CALL — SIMPLE MODE + ADVANCED MODE
# ============================================================
def ask_llm(subject: str, class_category: str, text: str, expected_questions: int) -> dict:
    """
    Dynamic LLM extraction with SIMPLE MODE fallback for subjects without
    sections, passages, diagrams, or complex grouping.
    """

    simple = is_simple_paper(text, subject)

    # ============================================================
    # SIMPLE MODE  — One clean group, no sections, no passages
    # ============================================================
    if simple:
        prompt = f"""
You are an expert WAEC MCQ extractor.

This exam is SIMPLE MODE:
- NO sections
- NO passages
- NO diagrams
- All questions belong to ONE group
- EXACTLY {expected_questions} questions

You MUST return JSON EXACTLY in this structure:

{{
  "subject": "{subject}",
  "groups": [
    {{
      "start_id": 1,
      "end_id": {expected_questions},
      "instruction": "ANSWER ALL QUESTIONS",
      "passage": "",
      "diagram": null,
      "question_ids": [{",".join(str(i) for i in range(1, expected_questions+1))}]
    }}
  ],
  "questions": [
      {{
         "id": 1,
         "question": "text",
         "options": ["A. ...","B. ...","C. ...","D. ..."],
         "correctOption": "A"
      }}
  ]
}}

RULES:
- Generate ALL questions from 1 to {expected_questions}.
- Each question MUST have EXACTLY 4 options.
- Options MUST start with "A. ", "B. ", "C. ", "D. ".
- correctOption MUST be one letter: A/B/C/D.
- RETURN ONLY VALID JSON.
- NO COMMENTARY, NO MARKDOWN.

Extract questions now:

{text}
"""

    # ============================================================
    # ADVANCED MODE — with Sections, Passages, Diagrams, Instructions
    # ============================================================
    else:
        prompt = f"""
You are an expert WAEC MCQ extractor.

This exam may include:
- Sections (SECTION 1, SECTION II)
- Shared instructions ("Use the passage to answer...")
- Passages (English comprehension)
- Diagrams

Extract a JSON for CBT with EXACT top-level keys:
"subject", "groups", "questions"

QUESTION COUNT:
- EXACTLY {expected_questions} questions
- IDs MUST be 1 to {expected_questions}

GROUPS:
- A group is created when a block of questions share:
  • a section header
  • a shared instruction
  • a shared passage
  • a shared diagram
- Each group MUST contain:
    - "start_id"
    - "end_id"
    - "instruction"
    - "passage"
    - "diagram"
    - "question_ids" (list of ids)

QUESTIONS:
- MUST include:
    - "id": number
    - "question": text
    - "options": ["A. ...", "B. ...", "C. ...", "D. ..."]
    - "correctOption": "A"/"B"/"C"/"D"

NUMBERS:
- ALL numbers must remain EXACT (1983, N50,000, 400,000 etc.)
- DO NOT normalize or alter numeric values.

FORMATTING:
- Maintain chemical/mathematical expressions.
- DO NOT wrap entire passages in each question.

RETURN ONLY VALID JSON—no markdown, no explanation.

Extract now:

{text}
"""

    # ============================================================
    # SEND TO GROQ
    # ============================================================
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    cleaned = clean_llm_json(res.choices[0].message.content)

    # PRIMARY PARSE
    try:
        return json.loads(cleaned)
    except Exception:
        # Safest fallback: wrap big numbers in quotes
        repaired = re.sub(r'(\d{4,})', r'"\1"', cleaned)
        return json.loads(repaired)



# ============================================================
# NORMALIZATION — MATCH CHEMISTRY_SS3.JSON STYLE
# ============================================================
def normalize_output(
    data: dict,
    subject: str,
    class_category: str,
    expected_questions: int,
    diagram_map: dict,
):
    # Ensure subject is correct
    data["subject"] = subject

    # ----------------------------
    # QUESTIONS
    # ----------------------------
    questions = data.get("questions") or []
    if not isinstance(questions, list):
        raise ValueError("questions must be a list")

    # Ensure each question has id
    for idx, q in enumerate(questions, start=1):
        if "id" not in q or not isinstance(q["id"], int):
            q["id"] = idx

    # Sort by id
    questions.sort(key=lambda q: q.get("id", 0))

    # If LLM returned extra questions, trim to expected
    if expected_questions and len(questions) > expected_questions:
        questions = questions[:expected_questions]

    # If fewer, we keep them but log a warning (print)
    if expected_questions and len(questions) != expected_questions:
        print(
            f"⚠️ WARNING: Expected {expected_questions} questions "
            f"but got {len(questions)}"
        )

    # Apply sub/sup formatting & normalise options
    for q in questions:
        q["question"] = apply_sub_sup_formatting(q.get("question", ""), subject)

        opts = q.get("options") or []
        fixed_opts = []

        for i, opt in enumerate(opts):
            if not isinstance(opt, str):
                opt = str(opt)

            # Strip any leading A./(a)/[A] etc
            body = re.sub(r"^[A-Da-d][\.\)\-:\s]*", "", opt).strip()
            body = apply_sub_sup_formatting(body, subject)

            letter = chr(65 + i)  # 0→A,1→B...
            fixed_opts.append(f"{letter}. {body}")

        # Ensure exactly 4 options if possible
        if len(fixed_opts) != 4:
            # pad or trim to 4
            if len(fixed_opts) > 4:
                fixed_opts = fixed_opts[:4]
            else:
                while len(fixed_opts) < 4:
                    letter = chr(65 + len(fixed_opts))
                    fixed_opts.append(f"{letter}. ---")

        q["options"] = fixed_opts

        # normalise correctOption letter
        co = q.get("correctOption") or q.get("correct_option") or q.get("answer")
        if isinstance(co, str):
            co = co.strip().upper()
            if co and co[0] in {"A", "B", "C", "D"}:
                q["correctOption"] = co[0]
            else:
                # fallback: if unknown, default to "A"
                q["correctOption"] = "A"
        else:
            q["correctOption"] = "A"

    data["questions"] = questions

    # ----------------------------
    # GROUPS
    # ----------------------------
    groups = data.get("groups") or []
    if not isinstance(groups, list):
        groups = []

    # If no groups returned, create a single default group
    if not groups and questions:
        ids = [q["id"] for q in questions]
        group = {
            "start_id": ids[0],
            "end_id": ids[-1],
            "instruction": "Choose the correct answer",
            "passage": "",
            "diagram": None,
            "question_ids": ids,
        }
        groups = [group]
    else:
        # Normalise each group
        for g in groups:
            # Instruction / passage defaults
            instr = (g.get("instruction") or "").strip()
            passage = g.get("passage") or ""
            g["instruction"] = instr
            g["passage"] = passage

            # Diagram mapping: if "1" or "2" etc, map via diagram_map
            diag_key = g.get("diagram")
            if isinstance(diag_key, str) and diag_key.strip():
                g["diagram"] = diagram_map.get(diag_key.strip(), None)
            else:
                g["diagram"] = None

            # Question IDs
            qids = g.get("question_ids")
            start_id = g.get("start_id")
            end_id = g.get("end_id")

            if not qids and isinstance(start_id, int) and isinstance(end_id, int):
                qids = list(range(start_id, end_id + 1))
            elif not qids:
                # fallback: empty
                qids = []

            g["question_ids"] = qids

            # Ensure start/end_id exist
            if not isinstance(start_id, int) and qids:
                g["start_id"] = min(qids)
            if not isinstance(end_id, int) and qids:
                g["end_id"] = max(qids)

    # Sort groups by start_id
    groups.sort(key=lambda gr: gr.get("start_id", 0))
    data["groups"] = groups

    # Class category is added in Python (top-level)
    data["class_category"] = class_category

    return data


# ============================================================
# SAVE JSON OUTPUT
# ============================================================
def save_output(subject: str, class_category: str, data: dict):
    folder = os.path.join(BASE_JSON, class_category.upper())
    os.makedirs(folder, exist_ok=True)

    safe = subject.strip().lower().replace(" ", "_")
    out_path = os.path.join(folder, f"{safe}_{class_category.lower()}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"💾 Saved → {out_path}")
    return out_path


# ============================================================
# MAIN CONVERSION
# ============================================================
def convert_exam(path: str):
    filename = os.path.basename(path)
    subject = detect_subject(filename)
    class_cat = detect_class_category(filename)
    version = detect_version(filename)

    if class_cat == "GENERAL":
        class_cat = class_from_version(version)

    expected_q = expected_question_count(filename)

    print(f"\n📘 Processing: {filename}")
    print(f"   → Subject: {subject}")
    print(f"   → Class:   {class_cat}")
    print(f"   → Expecting {expected_q} questions")

    # Extract text + diagrams
    diag_dir = os.path.join(BASE_DIAGRAMS, f"{subject.lower()}_{class_cat.lower()}")
    text, diagram_map = extract_docx(path, diag_dir)

    # LLM extraction
    print("🧠 Sending to LLM...")
    data = ask_llm(subject, class_cat, text, expected_q)

    # Normalize to chemistry_ss3.json style
    data = normalize_output(data, subject, class_cat, expected_q, diagram_map)

    return subject, class_cat, data


# ============================================================
# PROCESS ALL
# ============================================================
def process_all():
    print("\n=== 🚀 FULL CONVERSION START ===\n")

    for filename in sorted(os.listdir(BASE_DOCX)):
        if not filename.endswith(".docx"):
            continue

        path = os.path.join(BASE_DOCX, filename)
        try:
            subject, class_cat, data = convert_exam(path)
            save_output(subject, class_cat, data)
        except Exception as e:
            print(f"❌ ERROR converting {filename}: {e}")
            # continue to next file instead of break, so others still try
            continue

    print("\n🎉 DONE.\n")


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    process_all()

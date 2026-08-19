# ============================================================
# convert.py — EMIS SMART CBT CONVERTER
# DOCX/TXT → Clean Text → Rule Parser → LLM Repair → OpenAI Answers
# ============================================================

import os
import re
import json
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from dotenv import load_dotenv
from docx import Document
from werkzeug.utils import secure_filename
from groq import Groq


# ============================================================
# CLASS CONFIG
# ============================================================

from modules.class_config import (
    SUPPORTED_CLASSES,
    normalize_class_level,
    normalize_subject_display,
    normalize_subject_key,
    CLASS_SUBJECTS,
)


# ============================================================
# EXTENSIONS
# ============================================================

from convert_ext import (
    solve_answers_with_openai,
    save_exam_json,
    build_clean_student_json,
)


# ============================================================
# ENV / PATHS
# ============================================================

load_dotenv()

_THIS_FILE = Path(__file__).resolve()

# convert.py may live in the project root or inside a module folder.
# Prefer the directory that actually contains "static".
if (_THIS_FILE.parent / "static").exists():
    BASE_DIR = _THIS_FILE.parent
elif (_THIS_FILE.parent.parent / "static").exists():
    BASE_DIR = _THIS_FILE.parent.parent
else:
    BASE_DIR = Path.cwd()

STATIC_DIR = BASE_DIR / "static"

CONVERT_UPLOAD_DIR = (
    STATIC_DIR
    / "uploads"
    / "convert-documents"
)

CONVERT_TEXT_DIR = (
    STATIC_DIR
    / "uploads"
    / "convert-text"
)

BASE_DIAGRAMS = (
    STATIC_DIR
    / "uploads"
    / "diagrams"
)

BASE_SUBJECTS_DIR = (
    STATIC_DIR
    / "subjects"
)

CONVERT_UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

CONVERT_TEXT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

BASE_DIAGRAMS.mkdir(
    parents=True,
    exist_ok=True,
)

BASE_SUBJECTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# GROQ — STRUCTURED JSON REPAIR ONLY
# ============================================================

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    "",
).strip()

# IMPORTANT:
# Groq is used only for structural JSON repair in convert.py.
#
# Answer solving / verification remains inside convert_ext.py
# and uses the configured OpenAI models there.
#
# Environment variable GROQ_MODEL may override this.
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
).strip()

groq_client = (
    Groq(api_key=GROQ_API_KEY)
    if GROQ_API_KEY
    else None
)


# ============================================================
# JSON SCHEMA FOR GROQ STRUCTURED REPAIR
# ============================================================

EMIS_EXAM_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "subject",
        "class_category",
        "groups",
        "questions",
    ],
    "properties": {
        "subject": {
            "type": "string",
        },
        "class_category": {
            "type": "string",
        },
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "start_id",
                    "end_id",
                    "instruction",
                    "passage",
                    "diagram",
                    "question_ids",
                ],
                "properties": {
                    "start_id": {
                        "type": "integer",
                    },
                    "end_id": {
                        "type": "integer",
                    },
                    "instruction": {
                        "type": "string",
                    },
                    "passage": {
                        "type": "string",
                    },
                    "diagram": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "question_ids": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                        },
                    },
                },
            },
        },
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "question",
                    "options",
                    "correctOption",
                ],
                "properties": {
                    "id": {
                        "type": "integer",
                    },
                    "question": {
                        "type": "string",
                    },
                    "options": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {
                            "type": "string",
                        },
                    },
                    "correctOption": {
                        "type": "string",
                        "enum": [
                            "A",
                            "B",
                            "C",
                            "D",
                            "",
                        ],
                    },
                },
            },
        },
    },
}


# ============================================================
# DETECTION CONFIGURATION
# ============================================================

SUPPORTED_CLASS_LEVELS = {
    "JSS1",
    "JSS2",
    "JSS3",
    "SS1",
    "SS2",
    "SS3",
}

# JSS examinations are currently term-aware.
TERM_AWARE_CLASSES = {
    "JSS1",
    "JSS2",
    "JSS3",
}

VALID_TERMS = {
    "FIRST",
    "SECOND",
    "THIRD",
}


# ============================================================
# GENERAL DETECTION NORMALIZATION
# ============================================================

def normalize_detection_text(
    value: str = "",
) -> str:
    """
    Normalize filenames/document text for reliable detection.

    Examples:
        maths_jss1.docx
            -> MATHS JSS1 DOCX

        english-JSS-2.docx
            -> ENGLISH JSS 2 DOCX

        FIRST_TERM_JSS1
            -> FIRST TERM JSS1

    Dots are preserved because forms such as:
        J.S.S. 1
        S.S.S. 2
    may occur in document headings.
    """

    value = str(value or "").upper()

    # Filename/path separators should behave as spaces.
    value = re.sub(
        r"[_\-/\\]+",
        " ",
        value,
    )

    # Other common separators.
    value = re.sub(
        r"[:;,|]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def compact_detection_text(
    value: str = "",
) -> str:
    """
    Remove everything except A-Z and 0-9.

    Examples:
        maths_jss1.docx
            -> MATHSJSS1DOCX

        English-J.S.S.-2.docx
            -> ENGLISHJSS2DOCX
    """

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(value or "").upper(),
    )


def normalize_detected_class(
    value: str = "",
) -> str:
    """
    Normalize any explicit/fallback class value to one of:

        JSS1
        JSS2
        JSS3
        SS1
        SS2
        SS3

    Also accepts class-arm values such as:
        JSS1A
        JSS2B
        SS1_GOLD
        SS2_SILVER
        SS3B
    """

    raw = str(value or "").strip()

    if not raw:
        return ""

    # First use the project's central class normalizer.
    try:
        normalized = normalize_class_level(raw)

        if normalized in SUPPORTED_CLASS_LEVELS:
            return normalized
    except Exception:
        pass

    compact = compact_detection_text(raw)

    # JSS must be checked before SS.
    for class_name in (
        "JSS1",
        "JSS2",
        "JSS3",
    ):
        if compact == class_name:
            return class_name

        if compact.startswith(class_name):
            return class_name

    for class_name in (
        "SS1",
        "SS2",
        "SS3",
    ):
        if compact == class_name:
            return class_name

        if compact.startswith(class_name):
            return class_name

    return ""


# ============================================================
# CLASS DETECTION
# ============================================================

def detect_class_category(
    filename: str = "",
    text: str = "",
    fallback: str = "",
) -> str:
    """
    Detect the broad EMIS class level.

    Detection priority:

        1. Filename
        2. Document text / heading
        3. Explicit fallback

    Supported examples:

        maths_jss1.docx
        mathematics-jss1.docx
        mathematics JSS 1.docx
        english_JSS_2.docx

        JSS1
        JSS 1
        J.S.S. 1

        SS1
        SS 1
        S.S. 1
        SSS1
        S.S.S. 1

        Year 7  -> JSS1
        Year 8  -> JSS2
        Year 9  -> JSS3

        Year 10 -> SS1
        Year 11 -> SS2
        Year 12 -> SS3
    """

    # --------------------------------------------------------
    # 1. STRONG FILENAME DETECTION
    # --------------------------------------------------------

    filename_normalized = normalize_detection_text(
        filename
    )

    filename_compact = compact_detection_text(
        filename
    )

    # Compact filename detection is deliberately first.
    #
    # maths_jss1.docx
    # -> MATHSJSS1DOCX
    #
    # Therefore JSS1 is immediately obvious.
    for class_name in (
        "JSS1",
        "JSS2",
        "JSS3",
    ):
        if class_name in filename_compact:
            return class_name

    # SS only after JSS because JSS1 contains SS1.
    for class_name in (
        "SS1",
        "SS2",
        "SS3",
    ):
        if class_name in filename_compact:
            return class_name

    # --------------------------------------------------------
    # 2. NORMALIZED FILENAME PATTERNS
    # --------------------------------------------------------

    filename_patterns = [
        (
            r"(?<![A-Z0-9])"
            r"(?:JSS\s*1|J\s*\.?\s*S\s*\.?\s*S\s*\.?\s*1)"
            r"(?![A-Z0-9])",
            "JSS1",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:JSS\s*2|J\s*\.?\s*S\s*\.?\s*S\s*\.?\s*2)"
            r"(?![A-Z0-9])",
            "JSS2",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:JSS\s*3|J\s*\.?\s*S\s*\.?\s*S\s*\.?\s*3)"
            r"(?![A-Z0-9])",
            "JSS3",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:SSS?\s*1|S\s*\.?\s*S\s*\.?\s*S?\s*\.?\s*1)"
            r"(?![A-Z0-9])",
            "SS1",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:SSS?\s*2|S\s*\.?\s*S\s*\.?\s*S?\s*\.?\s*2)"
            r"(?![A-Z0-9])",
            "SS2",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:SSS?\s*3|S\s*\.?\s*S\s*\.?\s*S?\s*\.?\s*3)"
            r"(?![A-Z0-9])",
            "SS3",
        ),
    ]

    for pattern, class_name in filename_patterns:
        if re.search(
            pattern,
            filename_normalized,
            re.I,
        ):
            return class_name

    # --------------------------------------------------------
    # 3. DOCUMENT TEXT
    # --------------------------------------------------------

    document_text = normalize_detection_text(
        text[:16000]
    )

    document_patterns = [
        (
            r"(?<![A-Z0-9])"
            r"(?:JSS\s*1|J\s*\.?\s*S\s*\.?\s*S\s*\.?\s*1)"
            r"(?![A-Z0-9])"
            r"|\bYEAR\s*7\b",
            "JSS1",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:JSS\s*2|J\s*\.?\s*S\s*\.?\s*S\s*\.?\s*2)"
            r"(?![A-Z0-9])"
            r"|\bYEAR\s*8\b",
            "JSS2",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:JSS\s*3|J\s*\.?\s*S\s*\.?\s*S\s*\.?\s*3)"
            r"(?![A-Z0-9])"
            r"|\bYEAR\s*9\b",
            "JSS3",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:SSS?\s*1|S\s*\.?\s*S\s*\.?\s*S?\s*\.?\s*1)"
            r"(?![A-Z0-9])"
            r"|\bYEAR\s*10\b",
            "SS1",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:SSS?\s*2|S\s*\.?\s*S\s*\.?\s*S?\s*\.?\s*2)"
            r"(?![A-Z0-9])"
            r"|\bYEAR\s*11\b",
            "SS2",
        ),
        (
            r"(?<![A-Z0-9])"
            r"(?:SSS?\s*3|S\s*\.?\s*S\s*\.?\s*S?\s*\.?\s*3)"
            r"(?![A-Z0-9])"
            r"|\bYEAR\s*12\b",
            "SS3",
        ),
    ]

    for pattern, class_name in document_patterns:
        if re.search(
            pattern,
            document_text,
            re.I,
        ):
            return class_name

    # --------------------------------------------------------
    # 4. EXPLICIT FALLBACK
    # --------------------------------------------------------

    fallback_class = normalize_detected_class(
        fallback
    )

    if fallback_class:
        return fallback_class

    return ""


# ============================================================
# TERM NORMALIZATION
# ============================================================

def normalize_exam_term(
    value: str = "",
) -> str:
    """
    Convert different term representations to:

        FIRST
        SECOND
        THIRD

    Supported examples:

        1
        1ST
        FIRST
        FIRST TERM
        TERM 1

        2
        2ND
        SECOND
        SECOND TERM
        TERM 2

        3
        3RD
        THIRD
        THIRD TERM
        TERM 3
    """

    value = normalize_detection_text(
        value
    )

    if not value:
        return ""

    compact = compact_detection_text(
        value
    )

    aliases = {
        # First term
        "1": "FIRST",
        "01": "FIRST",
        "1ST": "FIRST",
        "FIRST": "FIRST",
        "FIRSTTERM": "FIRST",
        "1STTERM": "FIRST",
        "TERM1": "FIRST",

        # Second term
        "2": "SECOND",
        "02": "SECOND",
        "2ND": "SECOND",
        "SECOND": "SECOND",
        "SECONDTERM": "SECOND",
        "2NDTERM": "SECOND",
        "TERM2": "SECOND",

        # Third term
        "3": "THIRD",
        "03": "THIRD",
        "3RD": "THIRD",
        "THIRD": "THIRD",
        "THIRDTERM": "THIRD",
        "3RDTERM": "THIRD",
        "TERM3": "THIRD",
    }

    return aliases.get(
        compact,
        "",
    )


def exam_term_label(
    term: str = "",
) -> str:
    """
    Return teacher-friendly term label.
    """

    term = normalize_exam_term(
        term
    )

    labels = {
        "FIRST": "1st Term",
        "SECOND": "2nd Term",
        "THIRD": "3rd Term",
    }

    return labels.get(
        term,
        "—",
    )


# ============================================================
# TERM DETECTION
# ============================================================

def detect_exam_term(
    filename: str = "",
    text: str = "",
    fallback: str = "",
) -> str:
    """
    Detect examination term.

    Detection priority:

        1. Filename
        2. Document heading/text
        3. Explicit fallback

    Examples:

        maths_jss1_first_term.docx
            -> FIRST

        second_term_english.docx
            -> SECOND

        THIRD TERM EXAMINATION
            -> THIRD

        1ST TERM
            -> FIRST

        TERM 2
            -> SECOND

        TERM3
            -> THIRD
    """

    # --------------------------------------------------------
    # 1. FILENAME
    # --------------------------------------------------------

    filename_text = normalize_detection_text(
        filename
    )

    filename_compact = compact_detection_text(
        filename
    )

    compact_markers = [
        (
            "FIRST",
            (
                "FIRSTTERM",
                "1STTERM",
                "TERM1",
            ),
        ),
        (
            "SECOND",
            (
                "SECONDTERM",
                "2NDTERM",
                "TERM2",
            ),
        ),
        (
            "THIRD",
            (
                "THIRDTERM",
                "3RDTERM",
                "TERM3",
            ),
        ),
    ]

    for term, markers in compact_markers:
        if any(
            marker in filename_compact
            for marker in markers
        ):
            return term

    # Normal filename patterns.
    term_patterns = [
        (
            "FIRST",
            [
                r"(?<![A-Z0-9])FIRST\s+TERM(?![A-Z0-9])",
                r"(?<![A-Z0-9])1ST\s+TERM(?![A-Z0-9])",
                r"(?<![A-Z0-9])TERM\s*1(?![A-Z0-9])",
            ],
        ),
        (
            "SECOND",
            [
                r"(?<![A-Z0-9])SECOND\s+TERM(?![A-Z0-9])",
                r"(?<![A-Z0-9])2ND\s+TERM(?![A-Z0-9])",
                r"(?<![A-Z0-9])TERM\s*2(?![A-Z0-9])",
            ],
        ),
        (
            "THIRD",
            [
                r"(?<![A-Z0-9])THIRD\s+TERM(?![A-Z0-9])",
                r"(?<![A-Z0-9])3RD\s+TERM(?![A-Z0-9])",
                r"(?<![A-Z0-9])TERM\s*3(?![A-Z0-9])",
            ],
        ),
    ]

    for term, patterns in term_patterns:
        for pattern in patterns:
            if re.search(
                pattern,
                filename_text,
                re.I,
            ):
                return term

    # --------------------------------------------------------
    # 2. DOCUMENT TEXT
    # --------------------------------------------------------

    document_text = normalize_detection_text(
        text[:16000]
    )

    for term, patterns in term_patterns:
        for pattern in patterns:
            if re.search(
                pattern,
                document_text,
                re.I,
            ):
                return term

    # --------------------------------------------------------
    # Additional school-exam heading styles.
    # --------------------------------------------------------

    heading_patterns = [
        (
            "FIRST",
            [
                r"\bFIRST\s+TERM\s+(?:EXAM|EXAMINATION|TEST)\b",
                r"\b1ST\s+TERM\s+(?:EXAM|EXAMINATION|TEST)\b",
            ],
        ),
        (
            "SECOND",
            [
                r"\bSECOND\s+TERM\s+(?:EXAM|EXAMINATION|TEST)\b",
                r"\b2ND\s+TERM\s+(?:EXAM|EXAMINATION|TEST)\b",
            ],
        ),
        (
            "THIRD",
            [
                r"\bTHIRD\s+TERM\s+(?:EXAM|EXAMINATION|TEST)\b",
                r"\b3RD\s+TERM\s+(?:EXAM|EXAMINATION|TEST)\b",
            ],
        ),
    ]

    for term, patterns in heading_patterns:
        for pattern in patterns:
            if re.search(
                pattern,
                document_text,
                re.I,
            ):
                return term

    # --------------------------------------------------------
    # 3. EXPLICIT FALLBACK
    # --------------------------------------------------------

    fallback_term = normalize_exam_term(
        fallback
    )

    if fallback_term:
        return fallback_term

    return ""


# ============================================================
# TERM REQUIREMENT HELPER
# ============================================================

def class_requires_term(
    class_category: str = "",
) -> bool:
    """
    Return True when the detected class requires a term.

    Currently:
        JSS1
        JSS2
        JSS3
    """

    class_category = normalize_detected_class(
        class_category
    )

    return (
        class_category
        in TERM_AWARE_CLASSES
    )


# ============================================================
# COMBINED EXAM METADATA DETECTION
# ============================================================

def detect_exam_metadata(
    filename: str = "",
    text: str = "",
    class_fallback: str = "",
    subject_fallback: str = "",
    term_fallback: str = "",
) -> Dict[str, str]:
    """
    Central metadata detector used by converter routes.

    This prevents different routes from implementing class,
    subject and term detection differently.

    Returns:

        {
            "class_category": "JSS1",
            "subject": "Mathematics",
            "term": "FIRST",
            "term_label": "1st Term"
        }
    """

    detected_class = detect_class_category(
        filename=filename,
        text=text,
        fallback=class_fallback,
    )

    detected_subject = detect_subject(
        filename=filename,
        text=text,
        fallback=subject_fallback,
    )

    detected_term = detect_exam_term(
        filename=filename,
        text=text,
        fallback=term_fallback,
    )

    return {
        "class_category": detected_class,
        "subject": detected_subject,
        "term": detected_term,
        "term_label": (
            exam_term_label(detected_term)
            if detected_term
            else ""
        ),
    }


# ============================================================
# SUBJECT LIST HELPERS
# ============================================================

def all_known_subjects() -> List[str]:
    """
    Return unique normalized subjects from CLASS_SUBJECTS.
    """

    subjects = []

    for _, items in CLASS_SUBJECTS.items():
        subjects.extend(items)

    seen = set()
    output = []

    for subject in subjects:
        key = normalize_subject_key(
            subject
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(
            normalize_subject_display(
                subject
            )
        )

    return output


def is_valid_known_subject(
    value: str,
) -> bool:
    """
    Check whether a supplied subject is recognized by EMIS.
    """

    key = normalize_subject_key(
        value or ""
    )

    if not key:
        return False

    valid_subjects = {
        normalize_subject_key(subject)
        for subject in all_known_subjects()
    }

    extra_subjects = {
        "CHEMISTRY",
        "PHYSICS",
        "BIOLOGY",

        "MATHEMATICS",
        "MATHS",
        "FURTHER MATHEMATICS",
        "FURTHER MATHS",

        "ENGLISH LANGUAGE",
        "ENGLISH",

        "P.H.E",
        "PHE",
        "PHYSICAL HEALTH EDUCATION",
        "PHYSICAL AND HEALTH EDUCATION",

        "FINANCIAL ACCOUNT",
        "FINANCIAL ACCOUNTING",
        "ACCOUNTING",
        "ACCOUNTS",
        "ACCOUNT",

        "COMPUTER SCIENCE",
        "COMPUTER STUDIES",

        "CIVIC EDUCATION",
        "CIVIC",

        "AGRICULTURAL SCIENCE",
        "AGRICULTURE",

        "TECHNICAL DRAWING",

        "ECONOMICS",
        "GOVERNMENT",
        "LITERATURE",
        "LITERATURE IN ENGLISH",
        "COMMERCE",
        "MARKETING",
        "GEOGRAPHY",

        "IRS",
        "IRK",
        "ISLAMIC RELIGIOUS STUDIES",
        "ISLAMIC RELIGIOUS KNOWLEDGE",

        "ARABIC",
        "YORUBA",
        "HAUSA",

        "POISE",
        "ISLAMIYYAH",
    }

    valid_subjects.update(
        normalize_subject_key(subject)
        for subject in extra_subjects
    )

    return (
        key
        in valid_subjects
    )


# ============================================================
# SUBJECT DETECTION ALIASES
# ============================================================

SUBJECT_ALIASES = {
    # Accounts
    "FINANCIAL ACCOUNTING": "Financial Account",
    "FINANCIAL ACCOUNT": "Financial Account",
    "ACCOUNTING": "Financial Account",
    "ACCOUNTS": "Financial Account",

    # English
    "ENGLISH LANGUAGE": "English Language",
    "ENGLISH": "English Language",

    # Mathematics
    "FURTHER MATHEMATICS": "Further Mathematics",
    "FURTHER MATHS": "Further Mathematics",
    "MATHEMATICS": "Mathematics",
    "MATHS": "Mathematics",

    # Sciences
    "CHEMISTRY": "Chemistry",
    "BIOLOGY": "Biology",
    "PHYSICS": "Physics",

    # Humanities / Commercial
    "GOVERNMENT": "Government",
    "ECONOMICS": "Economics",
    "CIVIC EDUCATION": "Civic Education",
    "LITERATURE IN ENGLISH": "Literature",
    "LITERATURE": "Literature",
    "COMMERCE": "Commerce",
    "MARKETING": "Marketing",
    "GEOGRAPHY": "Geography",

    # Computing / Technical
    "COMPUTER SCIENCE": "Computer Science",
    "COMPUTER STUDIES": "Computer Science",
    "TECHNICAL DRAWING": "Technical Drawing",

    # Agriculture
    "AGRICULTURAL SCIENCE": "Agricultural Science",
    "AGRICULTURE": "Agricultural Science",

    # Religion
    "ISLAMIC RELIGIOUS STUDIES": "IRS",
    "ISLAMIC RELIGIOUS KNOWLEDGE": "IRK",
    "IRS": "IRS",
    "IRK": "IRK",

    # Languages
    "ARABIC": "Arabic",
    "YORUBA": "Yoruba",
    "HAUSA": "Hausa",

    # Common EMIS subjects
    "POISE": "Poise",
    "ISLAMIYYAH": "Islamiyyah",

    # PHE
    "PHYSICAL AND HEALTH EDUCATION": "P.H.E",
    "PHYSICAL HEALTH EDUCATION": "P.H.E",
    "P.H.E": "P.H.E",
    "PHE": "P.H.E",
}


COMPACT_SUBJECT_ALIASES = {
    "FURTHERMATHEMATICS": "Further Mathematics",
    "FURTHERMATHS": "Further Mathematics",

    "ENGLISHLANGUAGE": "English Language",
    "ENGLISH": "English Language",

    "MATHEMATICS": "Mathematics",
    "MATHS": "Mathematics",

    "FINANCIALACCOUNTING": "Financial Account",
    "FINANCIALACCOUNT": "Financial Account",
    "ACCOUNTING": "Financial Account",
    "ACCOUNTS": "Financial Account",

    "CHEMISTRY": "Chemistry",
    "BIOLOGY": "Biology",
    "PHYSICS": "Physics",

    "CIVICEDUCATION": "Civic Education",
    "CIVIC": "Civic Education",

    "COMPUTERSCIENCE": "Computer Science",
    "COMPUTERSTUDIES": "Computer Science",
    "COMPUTER": "Computer Science",

    "TECHNICALDRAWING": "Technical Drawing",
    "TECHNICAL": "Technical Drawing",

    "AGRICULTURALSCIENCE": "Agricultural Science",
    "AGRICULTURE": "Agricultural Science",

    "ECONOMICS": "Economics",
    "GOVERNMENT": "Government",
    "LITERATURE": "Literature",
    "COMMERCE": "Commerce",
    "MARKETING": "Marketing",
    "GEOGRAPHY": "Geography",

    "ARABIC": "Arabic",
    "YORUBA": "Yoruba",
    "HAUSA": "Hausa",

    "IRK": "IRK",
    "IRS": "IRS",

    "POISE": "Poise",
    "ISLAMIYYAH": "Islamiyyah",

    "PHE": "P.H.E",
}


# ============================================================
# SUBJECT DETECTION UTILITIES
# ============================================================

def _search_subject_aliases(
    text: str,
) -> str:
    """
    Search normalized text for an explicit subject name.

    Long aliases are checked first so:
        FURTHER MATHEMATICS
    wins before:
        MATHEMATICS

    and:
        ENGLISH LANGUAGE
    wins before:
        ENGLISH
    """

    if not text:
        return ""

    sorted_aliases = sorted(
        SUBJECT_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for alias, subject_name in sorted_aliases:
        pattern = (
            r"(?<![A-Z0-9])"
            + re.escape(alias).replace(
                r"\ ",
                r"\s+",
            )
            + r"(?![A-Z0-9])"
        )

        if re.search(
            pattern,
            text,
            re.I,
        ):
            return normalize_subject_display(
                subject_name
            )

    return ""


def _search_compact_subject_filename(
    filename: str,
) -> str:
    """
    Strong subject detection specifically for filenames.

    Example:
        maths_jss1.docx
            -> Mathematics
    """

    compact = compact_detection_text(
        filename
    )

    if not compact:
        return ""

    # Remove extension-like suffixes where possible.
    compact = re.sub(
        r"(DOCX|DOC|TXT)$",
        "",
        compact,
    )

    # Longest markers first.
    for marker in sorted(
        COMPACT_SUBJECT_ALIASES,
        key=len,
        reverse=True,
    ):
        if marker in compact:
            return normalize_subject_display(
                COMPACT_SUBJECT_ALIASES[
                    marker
                ]
            )

    return ""


# ============================================================
# SUBJECT CONTENT SCORING
# ============================================================

SUBJECT_CONTENT_KEYWORDS = {
    "Chemistry": [
        "CH4",
        "FE2",
        "SO4",
        "H2O",
        "CO2",
        "HCL",
        "NAOH",
        "OXIDATION",
        "REDUCTION",
        "SULPHUR",
        "SULFUR",
        "GRAPHITE",
        "HYDROGEN BOND",
        "ELECTRONEGATIVE",
        "MOLECULE",
        "COVALENT",
        "IONIC",
        "ALKANE",
        "ALKENE",
        "ALKYNE",
        "ETHENE",
        "ETHANE",
        "ACID",
        "BASE",
        "SALT",
        "ELECTROLYSIS",
        "ORGANIC",
        "TITRATION",
        "VALENCY",
        "PERIODIC",
        "COMPOUND",
        "ELEMENT",
        "ATOMIC",
        "MOLE",
        "MOLAR",
        "ISOMER",
        "CATALYST",
    ],

    "Physics": [
        "VELOCITY",
        "ACCELERATION",
        "FORCE",
        "MASS",
        "CURRENT",
        "VOLTAGE",
        "RESISTANCE",
        "LENS",
        "MIRROR",
        "WAVE",
        "FREQUENCY",
        "MOMENTUM",
        "ENERGY",
        "POWER",
        "PRESSURE",
        "ELECTRIC FIELD",
        "MAGNETIC FIELD",
    ],

    "Biology": [
        "CELL",
        "TISSUE",
        "ORGANISM",
        "PHOTOSYNTHESIS",
        "RESPIRATION",
        "GENETIC",
        "ECOSYSTEM",
        "DIGESTION",
        "ENZYME",
        "HABITAT",
        "REPRODUCTION",
        "OSMOSIS",
        "CHROMOSOME",
        "MITOSIS",
        "MEIOSIS",
    ],

    "P.H.E": [
        "FOOTBALL",
        "VOLLEYBALL",
        "ATHLETICS",
        "SPORT",
        "EXERCISE",
        "FIRST AID",
        "HYGIENE",
        "RECREATION",
        "PHYSICAL FITNESS",
    ],
}


def _score_subject_from_content(
    text: str,
) -> str:
    """
    Use subject-specific vocabulary only when an explicit
    filename/heading subject was not found.
    """

    document_text = normalize_detection_text(
        text[:20000]
    )

    if not document_text:
        return ""

    best_subject = ""
    best_score = 0

    for subject_name, words in SUBJECT_CONTENT_KEYWORDS.items():
        score = 0

        for word in words:
            normalized_word = normalize_detection_text(
                word
            )

            if normalized_word in document_text:
                score += 1

        if score > best_score:
            best_score = score
            best_subject = subject_name

    # Require at least two independent subject indicators.
    if best_score >= 2:
        return normalize_subject_display(
            best_subject
        )

    return ""


# ============================================================
# SUBJECT DETECTION
# ============================================================

def detect_subject(
    filename: str = "",
    text: str = "",
    fallback: str = "",
) -> str:
    """
    Detect the exam subject.

    Detection priority:

        1. Explicit subject in filename
        2. Compact filename detection
        3. Explicit subject in document text
        4. Subject-specific content scoring
        5. Explicit valid fallback
        6. General

    The filename is intentionally prioritized.

    Therefore:
        maths_jss1.docx

    should always resolve to:
        Mathematics

    even when the body contains vocabulary that could resemble
    another subject.
    """

    filename_text = normalize_detection_text(
        filename
    )

    document_text = normalize_detection_text(
        text[:20000]
    )

    # --------------------------------------------------------
    # 1. EXPLICIT FILENAME SUBJECT
    # --------------------------------------------------------

    detected = _search_subject_aliases(
        filename_text
    )

    if detected:
        return detected

    # --------------------------------------------------------
    # 2. COMPACT FILENAME SUBJECT
    # --------------------------------------------------------

    detected = _search_compact_subject_filename(
        filename
    )

    if detected:
        return detected

    # --------------------------------------------------------
    # 3. EXPLICIT DOCUMENT SUBJECT
    # --------------------------------------------------------

    detected = _search_subject_aliases(
        document_text
    )

    if detected:
        return detected

    # --------------------------------------------------------
    # 4. CONTENT SCORING
    # --------------------------------------------------------

    detected = _score_subject_from_content(
        document_text
    )

    if detected:
        return detected

    # --------------------------------------------------------
    # 5. EXPLICIT VALID FALLBACK
    # --------------------------------------------------------

    if (
        fallback
        and is_valid_known_subject(fallback)
    ):
        return normalize_subject_display(
            fallback
        )

    # --------------------------------------------------------
    # 6. UNKNOWN
    # --------------------------------------------------------

    return "General"


# ============================================================
# SAFE SLUG
# ============================================================

def safe_slug(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "exam"


# ============================================================
# EXPECTED QUESTION COUNT
# ============================================================

def expected_question_count(filename: str = "", subject: str = "", default: int = 50) -> int:
    """
    Default: 50

    Exceptions:
      English SS2  -> 60
      English SS3  -> 80
      Computer SS1 -> 60
    """

    combined = normalize_detection_text(f"{filename} {subject}").lower()
    compact = compact_detection_text(f"{filename} {subject}").lower()

    if "english" in combined and "ss3" in compact and "jss3" not in compact:
        return 80

    if "english" in combined and "ss2" in compact and "jss2" not in compact:
        return 60

    if "computer" in combined and "ss1" in compact and "jss1" not in compact:
        return 60

    return int(default or 50)


# ============================================================
# EXAM YEAR DETECTION
# ============================================================

def detect_exam_year(filename: str = "", text: str = "", fallback: str = "") -> str:
    """
    Examples:
      2021/2022   -> 2021
      2021-2022   -> 2021
      2021/22     -> 2021
      2021-22     -> 2021
      2021 SESSION
      SESSION 2021
    """

    joined = f"{filename} {text[:6000]} {fallback}"

    patterns = [
        r"\b(20\d{2})\s*/\s*(20\d{2})\b",
        r"\b(20\d{2})\s*-\s*(20\d{2})\b",
        r"\b(20\d{2})\s*/\s*\d{2}\b",
        r"\b(20\d{2})\s*-\s*\d{2}\b",
        r"\b(20\d{2})\s+ACADEMIC\s+SESSION\b",
        r"\bACADEMIC\s+SESSION\s+(20\d{2})\b",
        r"\b(20\d{2})\s+SESSION\b",
        r"\bSESSION\s+(20\d{2})\b",
        r"\b(20\d{2})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, joined, re.I)
        if match:
            return str(match.group(1))

    fallback = str(fallback or "").strip()

    if re.fullmatch(r"20\d{2}", fallback):
        return fallback

    return str(datetime.now().year)


# ============================================================
# STRIP ANSWER KEY BLOCKS
# ============================================================

def strip_answer_key_blocks(text: str) -> str:
    text = str(text or "")

    answer_markers = [
        r"\bANSWER\s+KEY\b",
        r"\bANSWERS\b",
        r"\bMARKING\s+SCHEME\b",
        r"\bCORRECT\s+OPTIONS\b",
        r"\bOBJECTIVE\s+ANSWERS\b",
    ]

    cut_points = []

    for marker in answer_markers:
        match = re.search(marker, text, re.I)
        if match:
            cut_points.append(match.start())

    if cut_points:
        text = text[:min(cut_points)].strip()

    answer_key_line_re = re.compile(
        r"^\s*(?:\d{1,3}\s*[\.\)]?\s*[A-Da-d]\s*){3,}$"
    )

    cleaned = []

    for line in text.splitlines():
        stripped = normalize_text_line(line)

        if answer_key_line_re.match(stripped):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


# ============================================================
# EXTRACT OBJECTIVE SECTION
# ============================================================

def extract_objective_section(text: str, expected_questions: int = 50) -> Tuple[str, List[str]]:
    warnings = []
    lines = str(text or "").splitlines()

    start_index = 0
    found_section_a = False

    # Prefer actual SECTION A.
    for index, line in enumerate(lines):
        clean = normalize_text_line(line)

        if re.search(r"^SECTION\s+A\b", clean, re.I):
            start_index = index
            found_section_a = True
            break

    # Otherwise start from first numbered question.
    if not found_section_a:
        for index, line in enumerate(lines):
            clean = normalize_text_line(line)

            if QUESTION_START_RE.match(clean):
                start_index = index
                break

    lines = lines[start_index:]

    theory_markers = [
        r"^SECTION\s+B\b",
        r"^SECTION\s+C\b",
        r"^THEORY\b",
        r"^ESSAY\b",
        r"^THEORY\s+OF\b",
        r"^PRACTICE\s+OF\b",
        r"^ANSWER\s+TWO\s+QUESTIONS\b",
        r"^ANSWER\s+THREE\s+QUESTIONS\b",
        r"^ANSWER\s+ANY\s+\w+\s+QUESTIONS\b",
    ]

    kept_lines = []

    for line in lines:
        clean = normalize_text_line(line)

        if any(re.search(marker, clean, re.I) for marker in theory_markers):
            warnings.append("Theory section was detected and removed.")
            break

        kept_lines.append(line)

    text = strip_answer_key_blocks("\n".join(kept_lines).strip())

    ids = []

    for line in text.splitlines():
        match = QUESTION_START_RE.match(normalize_text_line(line))

        if match:
            try:
                ids.append(int(match.group(1)))
            except (TypeError, ValueError):
                pass

    if ids and expected_questions and max(ids) > expected_questions:
        warnings.append(
            f"More than {expected_questions} objective question numbers were detected. "
            f"The converter will keep only the first {expected_questions}."
        )

    return text.strip(), warnings


# ============================================================
# MULTIPLE OBJECTIVE SERIES DETECTION
# ============================================================

def detect_multiple_objective_series(text: str) -> Dict[str, Any]:
    ids = []

    for line in str(text or "").splitlines():
        match = QUESTION_START_RE.match(normalize_text_line(line))

        if not match:
            continue

        try:
            ids.append(int(match.group(1)))
        except (TypeError, ValueError):
            continue

    restarts = 0
    restart_positions = []

    for index in range(1, len(ids)):
        previous_id = ids[index - 1]
        current_id = ids[index]

        if current_id == 1 and previous_id >= 20:
            restarts += 1

            restart_positions.append({
                "previous_question": previous_id,
                "restart_question": current_id,
                "position": index,
            })

    return {
        "multiple_series": restarts > 0,
        "restart_count": restarts,
        "restart_positions": restart_positions,
        "question_numbers_seen": len(ids),
        "highest_question_number": max(ids) if ids else 0,
    }


# ============================================================
# TEXT CLEANING
# ============================================================

def normalize_text_line(text: str) -> str:
    text = str(text or "")
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("￾", "").replace("–", "-").replace("—", "-")
    return re.sub(r"[ \t]+", " ", text).strip()


def is_noise_line(line: str) -> bool:
    line = normalize_text_line(line)

    if not line:
        return True

    patterns = [
        r"^EPITOME\b",
        r"^FOR SENIOR\b",
        r"^20\d{2}$",
        r"^Name\s*:",
        r"^Class\s*:",
        r"^Time Allowed\s*:",
        r"^FOR MARKERS ONLY\b",
        r"^Sections in Paper\b",
        r"^Scores Obtainable\b",
        r"^Scores Obtained\b",
        r"^SECTION A\s*[-–—]?\s*\(Objectives\)",
        r"^Do not start\b",
        r"^ANSWER ALL QUESTIONS$",
    ]

    if any(re.search(pattern, line, re.I) for pattern in patterns):
        return True

    upper = line.upper()

    if "FOR MARKERS ONLY" in upper:
        return True

    if "NAME:" in upper and "CLASS:" in upper:
        return True

    if "SCORES OBTAINABLE" in upper or "SCORES OBTAINED" in upper:
        return True

    return False


def paragraph_num_id(paragraph):
    try:
        num_pr = paragraph._p.pPr.numPr

        if num_pr is not None and num_pr.numId is not None:
            return str(num_pr.numId.val)

    except Exception:
        pass

    return None


# ============================================================
# DOCX PARSER TEXT
# ============================================================

def iter_docx_blocks(doc: Document) -> List[str]:
    lines = []
    question_counter = 0
    roman_counter = 0

    for paragraph in doc.paragraphs:
        text = normalize_text_line(paragraph.text)

        if not text or is_noise_line(text):
            continue

        num_id = paragraph_num_id(paragraph)
        style_name = (paragraph.style.name or "").lower()

        is_option_line = bool(
            re.search(r"^\s*[\(\[]?[a-dA-D][\)\].:-]\s*", text)
        )

        is_header_line = bool(
            re.search(
                r"^(EPITOME|FOR SENIOR|20\d{2}|Name:|Class:|FOR MARKERS|"
                r"Do not start|SECTION|CHEMISTRY|BIOLOGY|PHYSICS|ENGLISH)",
                text,
                re.I,
            )
        )

        # Main numbered questions.
        if num_id == "1" and "list" in style_name and not is_option_line and not is_header_line:
            question_counter += 1
            lines.append(f"{question_counter}. {text}")
            continue

        # Roman-list content.
        if num_id and num_id != "1" and "list" in style_name and not is_option_line and question_counter > 0:
            roman_labels = ["I", "II", "III", "IV", "V", "VI"]
            label = roman_labels[roman_counter % len(roman_labels)]
            roman_counter += 1
            lines.append(f"{label}. {text}")
            continue

        if is_option_line:
            roman_counter = 0

        lines.append(text)

    # Tables can contain questions/options too.
    for table in doc.tables:
        for row in table.rows:
            cells = [normalize_text_line(cell.text) for cell in row.cells]
            cells = [cell for cell in cells if cell and not is_noise_line(cell)]

            if cells:
                row_text = " | ".join(cells)

                if not is_noise_line(row_text):
                    lines.append(row_text)

    return lines


# ============================================================
# FULL DOCX TEXT FOR METADATA DETECTION
# ============================================================

def iter_docx_all_text_for_detection(doc: Document) -> List[str]:
    lines = []

    for paragraph in doc.paragraphs:
        text = normalize_text_line(paragraph.text)

        if text:
            lines.append(text)

    for table in doc.tables:
        for row in table.rows:
            cells = [normalize_text_line(cell.text) for cell in row.cells]
            cells = [cell for cell in cells if cell]

            if cells:
                lines.append(" | ".join(cells))

    # Headers may contain school/session/term/class information.
    try:
        for section in doc.sections:
            for paragraph in section.header.paragraphs:
                text = normalize_text_line(paragraph.text)

                if text:
                    lines.append(text)

            for paragraph in section.footer.paragraphs:
                text = normalize_text_line(paragraph.text)

                if text:
                    lines.append(text)

    except Exception:
        pass

    return lines


# ============================================================
# DOCX IMAGE EXTRACTION
# ============================================================

def extract_docx_images(docx_path: Path, diagram_out_dir: Path) -> Dict[str, str]:
    diagram_out_dir.mkdir(parents=True, exist_ok=True)
    diagram_map = {}

    try:
        with zipfile.ZipFile(docx_path, "r") as archive:
            media_files = sorted(
                name for name in archive.namelist()
                if name.startswith("word/media/")
            )

            for index, media in enumerate(media_files, start=1):
                ext = Path(media).suffix.lower() or ".png"
                filename = f"diagram_{index}{ext}"
                out_path = diagram_out_dir / filename

                with archive.open(media) as source, open(out_path, "wb") as destination:
                    shutil.copyfileobj(source, destination)

                relative = out_path.relative_to(STATIC_DIR)
                static_path = "/static/" + str(relative).replace("\\", "/")
                diagram_map[str(index)] = static_path

    except Exception as exc:
        print(f"Diagram extraction failed: {exc}")

    return diagram_map


# ============================================================
# THEORY STRIPPING
# ============================================================

def strip_theory_sections(text: str) -> str:
    markers = [
        r"\bSECTION\s+B\b",
        r"\bSECTION\s+C\b",
        r"\bTHEORY\b",
        r"\bANSWER\s+THREE\s+QUESTIONS\b",
        r"\bESSAY\b",
    ]

    cut_points = []

    for marker in markers:
        match = re.search(marker, text, re.I)

        if match:
            cut_points.append(match.start())

    return text[:min(cut_points)].strip() if cut_points else text.strip()


# ============================================================
# CLEAN EXTRACTED TEXT
# ============================================================

def clean_extracted_text(text: str, objective_only: bool = True, expected_questions: int = 50) -> str:
    lines = [normalize_text_line(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line and not is_noise_line(line)]

    cleaned = "\n".join(lines)

    cleaned = re.sub(r"(?i)\bsection\s+a\s*[-–—]?\s*", "SECTION A - ", cleaned)
    cleaned = re.sub(r"(?i)\banswer\s+all\s+questions\b", "ANSWER ALL QUESTIONS", cleaned)
    cleaned = re.sub(r"([a-dA-D])\)", r"(\1)", cleaned)
    cleaned = re.sub(r"\(\(\s*([a-dA-D])\)", r"(\1)", cleaned)
    cleaned = re.sub(r"\(\s*([a-dA-D])\s*\)", r"(\1)", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    if objective_only:
        cleaned, _ = extract_objective_section(cleaned, expected_questions=expected_questions)

    return cleaned.strip()


# ============================================================
# EXTRACT SOURCE FILE
# ============================================================

def extract_source_file(
    file_path: str,
    subject: str = "",
    class_category: str = "",
    term: str = "",
    year: str = "",
    objective_only: bool = True,
    extract_diagrams: bool = True,
) -> Dict[str, Any]:

    path = Path(file_path)
    filename = path.name

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    raw_text = ""
    full_raw_text = ""
    diagram_map = {}

    # Strong first-pass filename detection.
    detected_subject = detect_subject(filename=filename, fallback=subject)
    detected_class = detect_class_category(filename=filename, fallback=class_category)
    detected_term = detect_exam_term(filename=filename, fallback=term)
    detected_year = detect_exam_year(filename=filename, fallback=year)

    # --------------------------------------------------------
    # READ DOCUMENT FIRST
    # --------------------------------------------------------

    if path.suffix.lower() == ".docx":
        doc = Document(str(path))

        full_raw_text = "\n".join(iter_docx_all_text_for_detection(doc))
        raw_text = "\n".join(iter_docx_blocks(doc))

    elif path.suffix.lower() == ".txt":
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
        full_raw_text = raw_text

    else:
        raise ValueError("Unsupported file type. Upload DOCX or TXT only.")

    # --------------------------------------------------------
    # FINAL METADATA DETECTION FROM FULL DOCUMENT
    # --------------------------------------------------------

    metadata_text = f"{full_raw_text}\n{raw_text}"

    detected_class = detect_class_category(
        filename=filename,
        text=metadata_text,
        fallback=class_category or detected_class,
    )

    detected_subject = detect_subject(
        filename=filename,
        text=metadata_text,
        fallback=subject or detected_subject,
    )

    detected_year = detect_exam_year(
        filename=filename,
        text=metadata_text,
        fallback=year or detected_year,
    )

    detected_term = detect_exam_term(
        filename=filename,
        text=metadata_text,
        fallback=term or detected_term,
    )

    # SS classes are intentionally not term-aware.
    if not class_requires_term(detected_class):
        detected_term = ""

    expected = expected_question_count(
        filename=filename,
        subject=detected_subject,
        default=50,
    )

    # --------------------------------------------------------
    # DIAGRAMS
    # --------------------------------------------------------

    if path.suffix.lower() == ".docx" and extract_diagrams:
        exam_folder_name = f"{detected_subject}_{detected_class}"

        diagram_folder = (
            BASE_DIAGRAMS
            / safe_slug(detected_year)
            / safe_slug(exam_folder_name)
        )

        diagram_map = extract_docx_images(path, diagram_folder)

    # --------------------------------------------------------
    # CLEAN OBJECTIVE TEXT
    # --------------------------------------------------------

    clean_text = clean_extracted_text(
        raw_text,
        objective_only=objective_only,
        expected_questions=expected,
    )

    if objective_only:
        clean_text, objective_warnings = extract_objective_section(
            clean_text,
            expected_questions=expected,
        )
    else:
        objective_warnings = []

    # --------------------------------------------------------
    # MULTIPLE OBJECTIVE SERIES
    # --------------------------------------------------------

    series_info = detect_multiple_objective_series(clean_text)

    if series_info.get("multiple_series"):
        objective_warnings.append(
            "Multiple objective question series were detected. Please review before generating JSON."
        )

    # --------------------------------------------------------
    # FINAL SAFETY DETECTION
    # --------------------------------------------------------

    combined_text = f"{full_raw_text}\n{raw_text}\n{clean_text}"

    final_subject = detect_subject(
        filename=filename,
        text=combined_text,
        fallback=detected_subject,
    )

    final_class = detect_class_category(
        filename=filename,
        text=combined_text,
        fallback=detected_class,
    )

    final_term = detect_exam_term(
        filename=filename,
        text=combined_text,
        fallback=detected_term,
    )

    if not class_requires_term(final_class):
        final_term = ""

    detected_year = detect_exam_year(
        filename=filename,
        text=combined_text,
        fallback=detected_year,
    )

    # --------------------------------------------------------
    # SAVE CLEAN TEXT COPY
    # --------------------------------------------------------

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_name = f"{safe_slug(path.stem)}_{timestamp}.txt"
    txt_path = CONVERT_TEXT_DIR / txt_name
    txt_path.write_text(clean_text, encoding="utf-8")

    return {
        "filename": filename,
        "subject": final_subject,
        "class_category": final_class,
        "detected_year": detected_year,

        "term": final_term or None,
        "term_label": exam_term_label(final_term) if final_term else None,
        "term_required": class_requires_term(final_class),

        "expected_questions": expected,
        "clean_text": clean_text,
        "text_path": str(txt_path),

        "diagram_map": diagram_map,
        "diagram_count": len(diagram_map),

        "question_estimate": estimate_question_count(clean_text),

        "objective_warnings": objective_warnings,
        "multiple_objective_series": series_info.get("multiple_series", False),
        "series_info": series_info,
    }


# ============================================================
# RULE-BASED PARSER
# ============================================================

QUESTION_START_RE = re.compile(r"^\s*(\d{1,3})[\.\)]\s+(.+)$")
OPTION_RE = re.compile(r"^\s*[\(\[]?([a-dA-D])[\)\].:-]\s*(.+)$")
OPTION_ANYWHERE_RE = re.compile(r"\(?\s*([a-dA-D])\)\s*")


def estimate_question_count(text: str) -> int:
    ids = []

    for line in str(text or "").splitlines():
        match = QUESTION_START_RE.match(line.strip())

        if match:
            ids.append(int(match.group(1)))

    return len(set(ids))


def parse_range(text: str) -> List[int]:
    match = re.search(r"(\d{1,3})\s*[-–—]\s*(\d{1,3})", str(text or ""))

    if not match:
        return []

    start, end = int(match.group(1)), int(match.group(2))

    if start > end:
        start, end = end, start

    return list(range(start, end + 1))


# ============================================================
# GROUP DETECTION
# ============================================================

def detect_group_lines(text: str, diagram_map: Dict[str, str]) -> List[Dict[str, Any]]:
    groups = []

    for line in str(text or "").splitlines():
        line = normalize_text_line(line)

        if not line or is_noise_line(line):
            continue

        low = line.lower()

        if "use the diagram" in low or "diagram below" in low or "study the diagram" in low:
            qids = parse_range(line)

            if qids:
                groups.append({
                    "start_id": min(qids),
                    "end_id": max(qids),
                    "instruction": line,
                    "passage": "",
                    "diagram": diagram_map.get("1") if diagram_map else None,
                    "question_ids": qids,
                })

        elif "use the passage" in low or "read the passage" in low:
            qids = parse_range(line)

            if qids:
                groups.append({
                    "start_id": min(qids),
                    "end_id": max(qids),
                    "instruction": line,
                    "passage": "",
                    "diagram": None,
                    "question_ids": qids,
                })

    return groups


# ============================================================
# WRAPPED-LINE NORMALIZATION
# ============================================================

def join_wrapped_lines(lines: List[str]) -> List[str]:
    output = []

    for line in lines:
        line = normalize_text_line(line)

        if not line or is_noise_line(line):
            continue

        if QUESTION_START_RE.match(line) or OPTION_RE.match(line):
            output.append(line)
            continue

        if output and not re.match(r"^(SECTION|ANSWER|Use the|FOR MARKERS|Name:|Class:)", line, re.I):
            output[-1] = f"{output[-1]} {line}".strip()
        else:
            output.append(line)

    return output


# ============================================================
# INLINE OPTION SPLITTING
# ============================================================

def split_options_from_line(line: str) -> List[str]:
    line = str(line or "").strip()
    matches = list(OPTION_ANYWHERE_RE.finditer(line))

    if not matches:
        return []

    options = []

    for index, match in enumerate(matches):
        letter = match.group(1).upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)

        body = re.sub(r"\s+", " ", line[start:end].strip()).strip()

        if body:
            options.append(f"{letter}. {body}")

    return options


# ============================================================
# UNNUMBERED QUESTION PARSER
# ============================================================

def parse_questions_without_numbers(text: str) -> List[Dict[str, Any]]:
    lines = [normalize_text_line(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line and not is_noise_line(line)]

    questions = []
    pending_question_lines = []
    current = None
    qid = 0

    for line in lines:
        option_parts = split_options_from_line(line)

        if option_parts:
            if current is None:
                qid += 1

                current = {
                    "id": qid,
                    "question": " ".join(pending_question_lines).strip(),
                    "options": [],
                    "correctOption": "",
                }

                pending_question_lines = []

            current["options"].extend(option_parts)

            if len(current["options"]) >= 4:
                current["options"] = normalize_options(current["options"])
                questions.append(current)
                current = None

            continue

        if current is not None and len(current.get("options", [])) < 4:
            if current["options"]:
                current["options"][-1] = f"{current['options'][-1]} {line}".strip()
            continue

        pending_question_lines.append(line)

    return questions


# ============================================================
# RULE-BASED QUESTION PARSER
# ============================================================

def parse_questions_rule_based(text: str) -> List[Dict[str, Any]]:
    lines = join_wrapped_lines(str(text or "").splitlines())

    questions = []
    current = None

    has_numbered_questions = any(
        QUESTION_START_RE.match(normalize_text_line(line))
        for line in lines
    )

    if not has_numbered_questions:
        return parse_questions_without_numbers(text)

    for line in lines:
        line = normalize_text_line(line)

        if not line or is_noise_line(line):
            continue

        q_match = QUESTION_START_RE.match(line)

        if q_match:
            if current:
                questions.append(current)

            current = {
                "id": int(q_match.group(1)),
                "question": q_match.group(2).strip(),
                "options": [],
                "correctOption": "",
            }

            continue

        if not current:
            continue

        option_parts = split_options_from_line(line)

        if option_parts:
            current["options"].extend(option_parts)
            continue

        current["question"] = f"{current['question']} {line}".strip()

    if current:
        questions.append(current)

    fixed = []
    seen = set()

    for question in questions:
        qid = question.get("id")

        if qid in seen:
            continue

        seen.add(qid)
        question["options"] = normalize_options(question.get("options", []))
        fixed.append(question)

    fixed.sort(key=lambda item: item.get("id", 0))
    return fixed


# ============================================================
# FORMATTING / NORMALIZATION
# ============================================================

SUB_SUP_SUBJECTS = {
    "CHEMISTRY",
    "MATHEMATICS",
    "FURTHER MATHEMATICS",
    "PHYSICS",
    "BIOLOGY",
}


def apply_sub_sup_formatting(text: str, subject: str = "") -> str:
    if not text:
        return ""

    if normalize_subject_key(subject) not in SUB_SUP_SUBJECTS:
        return text

    def chem_repl(match):
        element, number = match.group(1), match.group(2)

        if element.upper() in {"SS", "WA", "Q"}:
            return match.group(0)

        return f"{element}<sub>{number}</sub>"

    text = re.sub(r"([A-Z][a-z]?)(\d+)", chem_repl, str(text))
    text = re.sub(r"(\w)\^(\-?\d+)", r"\1<sup>\2</sup>", text)

    return text


def normalize_options(options: List[Any]) -> List[str]:
    fixed = []

    for index, option in enumerate(options[:4]):
        letter = chr(65 + index)
        body = str(option or "").strip()
        body = re.sub(r"^[A-Da-d][\.\)\-:\s]+", "", body).strip()
        fixed.append(f"{letter}. {body}")

    while len(fixed) < 4:
        letter = chr(65 + len(fixed))
        fixed.append(f"{letter}. ---")

    return fixed[:4]


# ============================================================
# ATTACH GROUP DIAGRAMS
# ============================================================

def attach_diagrams_to_questions(
    questions: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    diagram_by_qid = {}

    for group in groups:
        diagram = group.get("diagram")

        if not diagram:
            continue

        for qid in group.get("question_ids", []):
            try:
                diagram_by_qid[int(qid)] = diagram
            except (TypeError, ValueError):
                pass

    for question in questions:
        try:
            qid = int(question.get("id"))
        except (TypeError, ValueError):
            continue

        question["diagram"] = question.get("diagram") or diagram_by_qid.get(qid) or None

    return questions


# ============================================================
# NORMALIZE FINAL OUTPUT
# ============================================================

def normalize_output(
    data: Dict[str, Any],
    subject: str,
    class_category: str,
    expected_questions: int,
    diagram_map: Dict[str, str],
    term: str = "",
) -> Dict[str, Any]:

    subject = normalize_subject_display(subject)
    class_category = normalize_class_level(class_category) or class_category
    term = normalize_exam_term(term)

    questions = data.get("questions") or []

    if not isinstance(questions, list):
        questions = []

    cleaned_questions = []

    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue

        try:
            qid = int(question.get("id"))
        except (TypeError, ValueError):
            qid = index

        question_text = apply_sub_sup_formatting(
            str(question.get("question") or "").strip(),
            subject,
        )

        options = normalize_options(question.get("options") or [])
        options = [apply_sub_sup_formatting(option, subject) for option in options]

        correct = str(
            question.get("correctOption")
            or question.get("answer")
            or ""
        ).strip().upper()

        correct = correct[0] if correct and correct[0] in {"A", "B", "C", "D"} else ""

        cleaned_questions.append({
            "id": qid,
            "diagram": question.get("diagram") or None,
            "question": question_text,
            "options": options,
            "correctOption": correct,
        })

    cleaned_questions.sort(key=lambda item: item["id"])

    if expected_questions and len(cleaned_questions) > expected_questions:
        cleaned_questions = cleaned_questions[:expected_questions]

    # --------------------------------------------------------
    # GROUPS
    # --------------------------------------------------------

    groups = data.get("groups") or []

    if not isinstance(groups, list):
        groups = []

    fixed_groups = []

    for group in groups:
        if not isinstance(group, dict):
            continue

        qids = group.get("question_ids") or []

        try:
            qids = [int(value) for value in qids]
        except (TypeError, ValueError):
            qids = []

        try:
            start_id = int(group.get("start_id"))
        except (TypeError, ValueError):
            start_id = min(qids) if qids else 1

        try:
            end_id = int(group.get("end_id"))
        except (TypeError, ValueError):
            end_id = max(qids) if qids else start_id

        if not qids:
            qids = list(range(start_id, end_id + 1))

        diagram = group.get("diagram")

        if isinstance(diagram, str):
            diagram = diagram_map.get(diagram.strip(), diagram)

        fixed_groups.append({
            "start_id": start_id,
            "end_id": end_id,
            "instruction": str(group.get("instruction") or "").strip(),
            "passage": str(group.get("passage") or "").strip(),
            "diagram": diagram or None,
            "question_ids": qids,
        })

    # Default group.
    if not fixed_groups and cleaned_questions:
        ids = [question["id"] for question in cleaned_questions]

        fixed_groups = [{
            "start_id": min(ids),
            "end_id": max(ids),
            "instruction": "ANSWER ALL QUESTIONS",
            "passage": "",
            "diagram": None,
            "question_ids": ids,
        }]

    fixed_groups.sort(key=lambda item: item.get("start_id", 0))
    cleaned_questions = attach_diagrams_to_questions(cleaned_questions, fixed_groups)

    output = {
        "subject": subject,
        "class_category": class_category,
        "groups": fixed_groups,
        "questions": cleaned_questions,
    }

    # JSS only.
    if class_requires_term(class_category) and term:
        output["term"] = term
        output["term_label"] = exam_term_label(term)

    return output


# ============================================================
# VALIDATION
# ============================================================

def validate_exam_json(data: Dict[str, Any], expected_questions: int = 0) -> Dict[str, Any]:
    issues = []
    warnings = []

    questions = data.get("questions") or []
    groups = data.get("groups") or []
    class_category = normalize_detected_class(data.get("class_category") or data.get("class") or "")
    term = normalize_exam_term(data.get("term") or "")

    if not data.get("subject"):
        issues.append("Missing subject.")

    if not class_category:
        warnings.append("Missing class category.")

    if class_requires_term(class_category) and not term:
        warnings.append(f"{class_category} requires a term.")

    if not isinstance(questions, list) or not questions:
        issues.append("No questions found.")

    if expected_questions and len(questions) != expected_questions:
        warnings.append(f"Expected {expected_questions} questions but found {len(questions)}.")

    ids = [question.get("id") for question in questions if isinstance(question, dict)]
    duplicates = sorted({qid for qid in ids if ids.count(qid) > 1})

    if duplicates:
        issues.append(f"Duplicate question IDs found: {duplicates}")

    missing_answers = 0

    for question in questions:
        if not isinstance(question, dict):
            issues.append("Invalid question object found.")
            continue

        if not question.get("question"):
            issues.append(f"Question {question.get('id')} has empty question text.")

        options = question.get("options") or []

        if len(options) != 4:
            issues.append(f"Question {question.get('id')} does not have exactly 4 options.")

        if question.get("correctOption") not in {"A", "B", "C", "D"}:
            missing_answers += 1

    if missing_answers:
        warnings.append(f"{missing_answers} question(s) have no answer key yet.")

    if not isinstance(groups, list) or not groups:
        warnings.append("No groups found. Default group will be used.")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "question_count": len(questions),
        "group_count": len(groups),
        "missing_answers": missing_answers,
    }


# ============================================================
# GROQ STRUCTURED REPAIR
# ============================================================

def build_llm_prompt(
    subject: str,
    class_category: str,
    clean_text: str,
    expected_questions: int,
    rule_questions: List[Dict[str, Any]],
    rule_groups: List[Dict[str, Any]],
) -> str:

    parser_result = {
        "groups": rule_groups,
        "questions": rule_questions,
    }

    return f"""
You are converting a school examination document into EMIS CBT JSON.

Target:
- subject: {subject}
- class_category: {class_category}
- expected_questions: {expected_questions}

Rules:
- Return ONLY a JSON object.
- Include objective questions only.
- Ignore theory and essay questions.
- Keep question IDs in correct order.
- Each question must contain exactly four options.
- Format options as "A. ...", "B. ...", "C. ...", "D. ...".
- If no answer key exists, use correctOption: "".
- Preserve passage and diagram groups.
- Do not invent missing questions.
- Do not invent answers.

Rule parser result:
{json.dumps(parser_result, ensure_ascii=False)}

Clean extracted text:
{clean_text}
""".strip()


def ask_llm_structured(
    subject: str,
    class_category: str,
    clean_text: str,
    expected_questions: int,
    rule_questions: List[Dict[str, Any]],
    rule_groups: List[Dict[str, Any]],
) -> Dict[str, Any]:

    fallback = {
        "subject": subject,
        "class_category": class_category,
        "groups": rule_groups,
        "questions": rule_questions,
    }

    if not groq_client:
        print("Groq JSON repair skipped: GROQ_API_KEY not configured.")
        return fallback

    prompt = build_llm_prompt(
        subject=subject,
        class_category=class_category,
        clean_text=clean_text,
        expected_questions=expected_questions,
        rule_questions=rule_questions,
        rule_groups=rule_groups,
    )

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict JSON extractor for CBT examination questions.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        if not content:
            print("Groq JSON repair returned empty content. Using parser fallback.")
            return fallback

        repaired = json.loads(content)

        if not isinstance(repaired, dict):
            print("Groq JSON repair returned invalid root object. Using parser fallback.")
            return fallback

        if not isinstance(repaired.get("questions"), list):
            print("Groq JSON repair returned no question list. Using parser fallback.")
            return fallback

        return repaired

    except Exception as exc:
        print(
            f"Groq JSON repair failed with model '{GROQ_MODEL}'. "
            f"Using rule parser fallback: {exc}"
        )

        return fallback


# ============================================================
# MAIN JSON GENERATION PIPELINE
# ============================================================

def generate_exam_json_from_text(
    clean_text: str,
    subject: str,
    class_category: str,
    expected_questions: int = 50,
    diagram_map: Optional[Dict[str, str]] = None,
    use_llm: bool = True,
    solve_answers: bool = True,
    term: str = "",
) -> Dict[str, Any]:

    diagram_map = diagram_map or {}

    # --------------------------------------------------------
    # SUBJECT
    # --------------------------------------------------------

    detected_subject = detect_subject("", clean_text, "")

    if detected_subject and detected_subject != "General":
        subject = detected_subject
    elif subject:
        subject = normalize_subject_display(subject)
    else:
        subject = "General"

    # --------------------------------------------------------
    # CLASS / TERM
    # --------------------------------------------------------

    class_category = normalize_class_level(class_category) or normalize_detected_class(class_category)
    term = normalize_exam_term(term)

    if not class_requires_term(class_category):
        term = ""

    # --------------------------------------------------------
    # RULE PARSER
    # --------------------------------------------------------

    rule_questions = parse_questions_rule_based(clean_text)
    rule_groups = detect_group_lines(clean_text, diagram_map)

    if not rule_groups and rule_questions:
        ids = [question["id"] for question in rule_questions]

        rule_groups = [{
            "start_id": min(ids),
            "end_id": max(ids),
            "instruction": "ANSWER ALL QUESTIONS",
            "passage": "",
            "diagram": None,
            "question_ids": ids,
        }]

    raw_data = {
        "subject": subject,
        "class_category": class_category,
        "groups": rule_groups,
        "questions": rule_questions,
    }

    # --------------------------------------------------------
    # GROQ STRUCTURAL REPAIR
    # --------------------------------------------------------

    if use_llm:
        raw_data = ask_llm_structured(
            subject=subject,
            class_category=class_category,
            clean_text=clean_text,
            expected_questions=expected_questions,
            rule_questions=rule_questions,
            rule_groups=rule_groups,
        )

    # --------------------------------------------------------
    # NORMALIZE
    # --------------------------------------------------------

    normalized = normalize_output(
        raw_data,
        subject=subject,
        class_category=class_category,
        expected_questions=expected_questions,
        diagram_map=diagram_map,
        term=term,
    )

    # Lock metadata after Groq.
    normalized["subject"] = subject
    normalized["class_category"] = class_category

    if class_requires_term(class_category) and term:
        normalized["term"] = term
        normalized["term_label"] = exam_term_label(term)

    # --------------------------------------------------------
    # OPENAI ANSWER SOLVER + VERIFIER
    # --------------------------------------------------------

    answer_data = {
        "answer_report": [],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0,
        },
        "needs_review": 0,
    }

    if solve_answers:
        try:
            answer_data = solve_answers_with_openai(
                exam_json=normalized,
                subject=subject,
                class_category=class_category,
            )

            normalized = answer_data.get("json", normalized)

            # Re-lock metadata after OpenAI.
            normalized["subject"] = subject
            normalized["class_category"] = class_category

            if class_requires_term(class_category) and term:
                normalized["term"] = term
                normalized["term_label"] = exam_term_label(term)

        except Exception as exc:
            print(f"OpenAI answer generation failed: {exc}")
            answer_data["error"] = str(exc)

    validation = validate_exam_json(
        normalized,
        expected_questions=expected_questions,
    )

    usage = answer_data.get("usage", {}) or {}

    return {
        "data": normalized,
        "subject": subject,
        "class_category": class_category,

        "term": term or None,
        "term_label": exam_term_label(term) if term else None,

        "validation": validation,
        "answer_report": answer_data.get("answer_report", []),
        "openai_usage": usage,
        "needs_review": answer_data.get("needs_review", 0),

        "stats": {
            "questions": len(normalized.get("questions", [])),
            "groups": len(normalized.get("groups", [])),
            "diagrams": len(diagram_map),
            "warnings": len(validation.get("warnings", [])),
            "issues": len(validation.get("issues", [])),
            "needs_review": answer_data.get("needs_review", 0),
            "estimated_cost_usd": usage.get("estimated_cost_usd", 0),
        },
    }


# ============================================================
# COMPLETE FILE CONVERSION PIPELINE
# ============================================================

def convert_exam_file(
    file_path: str,
    subject: str = "",
    class_category: str = "",
    term: str = "",
    year: str = "",
    expected_questions: int = 50,
    objective_only: bool = True,
    extract_diagrams: bool = True,
    use_llm: bool = True,
    solve_answers: bool = True,
) -> Dict[str, Any]:

    extracted = extract_source_file(
        file_path=file_path,
        subject=subject,
        class_category=class_category,
        term=term,
        year=year,
        objective_only=objective_only,
        extract_diagrams=extract_diagrams,
    )

    final_subject = detect_subject(
        filename=extracted["filename"],
        text=extracted["clean_text"],
        fallback=extracted.get("subject") or subject,
    )

    final_class = detect_class_category(
        filename=extracted["filename"],
        text=extracted["clean_text"],
        fallback=extracted.get("class_category") or class_category,
    )

    final_term = detect_exam_term(
        filename=extracted["filename"],
        text=extracted["clean_text"],
        fallback=extracted.get("term") or term,
    )

    if not class_requires_term(final_class):
        final_term = ""

    final_year = detect_exam_year(
        filename=extracted["filename"],
        text=extracted["clean_text"],
        fallback=extracted.get("detected_year") or year,
    )

    expected = int(
        expected_questions
        or expected_question_count(
            extracted["filename"],
            final_subject,
        )
    )

    generated = generate_exam_json_from_text(
        clean_text=extracted["clean_text"],
        subject=final_subject,
        class_category=final_class,
        expected_questions=expected,
        diagram_map=extracted["diagram_map"],
        use_llm=use_llm,
        solve_answers=solve_answers,
        term=final_term,
    )

    # --------------------------------------------------------
    # CLEAN STUDENT JSON
    # --------------------------------------------------------

    student_json = build_clean_student_json(
        data=generated["data"],
        subject=final_subject,
        class_category=final_class,
    )

    # Some existing convert_ext.py versions do not yet explicitly
    # know about "term", so enforce it after student JSON creation.
    if isinstance(student_json, dict):
        student_json["subject"] = final_subject
        student_json["class_category"] = final_class

        if class_requires_term(final_class) and final_term:
            student_json["term"] = final_term
            student_json["term_label"] = exam_term_label(final_term)
        else:
            student_json.pop("term", None)
            student_json.pop("term_label", None)

    return {
        **extracted,

        "subject": final_subject,
        "class_category": final_class,
        "detected_year": final_year,

        "term": final_term or None,
        "term_label": exam_term_label(final_term) if final_term else None,
        "term_required": class_requires_term(final_class),

        "expected_questions": expected,

        "json": generated["data"],
        "student_json": student_json,

        "validation": generated["validation"],
        "stats": generated["stats"],

        "answer_report": generated.get("answer_report", []),
        "openai_usage": generated.get("openai_usage", {}),
        "needs_review": generated.get("needs_review", 0),
    }


# ============================================================
# SAVE UPLOADED SOURCE FILE
# ============================================================

def save_uploaded_convert_file(file_storage) -> str:
    if not file_storage or not file_storage.filename:
        raise ValueError("No file uploaded.")

    filename = secure_filename(file_storage.filename)
    ext = Path(filename).suffix.lower()

    if ext not in {".docx", ".txt"}:
        raise ValueError("Only DOCX and TXT files are allowed.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = f"{safe_slug(Path(filename).stem)}_{stamp}{ext}"
    save_path = CONVERT_UPLOAD_DIR / safe_name

    file_storage.save(str(save_path))

    return str(save_path)


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert DOCX/TXT exam to EMIS CBT JSON"
    )

    parser.add_argument("file", help="Path to DOCX/TXT file")
    parser.add_argument("--subject", default="")
    parser.add_argument("--class_category", default="")
    parser.add_argument("--term", default="")
    parser.add_argument("--year", default="")
    parser.add_argument("--expected", type=int, default=50)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--no-answers", action="store_true")
    parser.add_argument("--save", action="store_true")

    args = parser.parse_args()

    result = convert_exam_file(
        file_path=args.file,
        subject=args.subject,
        class_category=args.class_category,
        term=args.term,
        year=args.year,
        expected_questions=args.expected,
        use_llm=not args.no_llm,
        solve_answers=not args.no_answers,
    )

    print("\nDetected Metadata:")
    print(
        json.dumps(
            {
                "subject": result.get("subject"),
                "class_category": result.get("class_category"),
                "year": result.get("detected_year"),
                "term": result.get("term"),
                "term_label": result.get("term_label"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nStudent JSON:")
    print(
        json.dumps(
            result["student_json"],
            indent=2,
            ensure_ascii=False,
        )
    )

    if args.save:
        # Keep compatibility with the current convert_ext.py.
        #
        # Term is already embedded inside result["json"].
        # We will make save_exam_json physically use the JSS term
        # folder when convert_ext.py is upgraded.
        saved = save_exam_json(
            data=result["json"],
            year=result.get("detected_year") or args.year or str(datetime.now().year),
            subject=result["subject"],
            class_category=result["class_category"],
            review_report=result.get("answer_report", []),
        )

        print("\nSaved:")
        print(
            json.dumps(
                saved,
                indent=2,
                ensure_ascii=False,
            )
        )
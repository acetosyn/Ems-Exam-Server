# modules/class_config.py

import re

from modules.school_structure import MAIN_SCHOOL_CLASS_LEVELS, REGULAR_CLASS_LEVELS, TAHFEEZ_CLASS_LEVELS, ISLAMIYAH_CLASS_LEVELS, ACTIVE_DATABASE_CLASSES, PENDING_DATABASE_CLASSES, SCHOOL_SECTIONS, ASSESSMENT_SCHEMES, ALL_CONFIGURED_CLASSES, class_label, get_class_metadata, get_secondary_track_subjects, get_source_subjects, normalize_school_class, school_section_for_class


# =========================================================
# CORE CLASS CONFIGURATION
# =========================================================

# students2026.csv stores the complete regular-school roster. The CBT exam stack now
# supports Primary 1–6 as well as JSS1–3 and SS1–3. Keep the exam-class sets here as
# the single source of truth so Uploads, Push, Student Portal and Results stay aligned.
STUDENT_DATABASE_CLASSES = list(ACTIVE_DATABASE_CLASSES)
PRIMARY_EXAM_CLASSES = ["PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6"]
JSS_EXAM_CLASSES = ["JSS1", "JSS2", "JSS3"]
SS_EXAM_CLASSES = ["SS1", "SS2", "SS3"]
EXAM_SUPPORTED_CLASSES = [*PRIMARY_EXAM_CLASSES, *JSS_EXAM_CLASSES, *SS_EXAM_CLASSES]
TERM_REQUIRED_EXAM_CLASSES = [*PRIMARY_EXAM_CLASSES, *JSS_EXAM_CLASSES]
TERM_OPTIONAL_EXAM_CLASSES = list(SS_EXAM_CLASSES)
SUPPORTED_CLASSES = list(EXAM_SUPPORTED_CLASSES)
ALL_CONFIGURED_REGULAR_CLASSES = list(REGULAR_CLASS_LEVELS)
PLANNED_DATABASE_CLASSES = list(PENDING_DATABASE_CLASSES)
TAHFEEZ_CLASSES = list(TAHFEEZ_CLASS_LEVELS)
ISLAMIYAH_CLASSES = list(ISLAMIYAH_CLASS_LEVELS)

# Real lower-school registers use Gold/Silver groups for Prep/Nursery and A/B arms for Primary.
# Empty future arms remain configured so missing source sheets can be added later without code changes.
CLASS_ARMS_BY_LEVEL = {
    "CRECHE": ["CRECHE"], "STARTER": ["STARTER"],
    "PRE_CLASS": ["PRE_CLASS_GOLD", "PRE_CLASS_SILVER"],
    "NURSERY1": ["NURSERY1_GOLD", "NURSERY1_SILVER"], "NURSERY2": ["NURSERY2_GOLD", "NURSERY2_SILVER"],
    "PRIMARY1": ["PRIMARY1A", "PRIMARY1B"], "PRIMARY2": ["PRIMARY2A", "PRIMARY2B"], "PRIMARY3": ["PRIMARY3A", "PRIMARY3B"],
    "PRIMARY4": ["PRIMARY4A", "PRIMARY4B"], "PRIMARY5": ["PRIMARY5A", "PRIMARY5B"], "PRIMARY6": ["PRIMARY6A", "PRIMARY6B"],
    "JSS1": ["JSS1A", "JSS1B", "JSS1C"], "JSS2": ["JSS2A", "JSS2B", "JSS2C"], "JSS3": ["JSS3A", "JSS3B", "JSS3C"],
    "SS1": ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1_B/C"], "SS2": ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2_B/C"],
    "SS3": ["SS3_GOLD", "SS3_SILVER", "SS3_B/C"],
}

# Backward-compatible alias used by older modules.
CLASS_ARMS = CLASS_ARMS_BY_LEVEL


# =========================================================
# STUDENT DATABASE
# =========================================================

STUDENT_CSV_FILE = "static/data/database/students2026.csv"
TAHFEEZ_CSV_FILE = "static/data/database/tahfeez2026.csv"
ISLAMIYAH_CSV_FILE = TAHFEEZ_CSV_FILE  # One combined Tahfeez and Islamiyyah student register.

# Backward compatibility: every class now points to the same master CSV.
STUDENT_CSV_FILES = {level: STUDENT_CSV_FILE for level in STUDENT_DATABASE_CLASSES}


# =========================================================
# APPLICATION PATHS
# =========================================================

SUBJECT_JSON_ROOT = "static/subjects"
PORTAL_ROOT = "static/portal"
RESULTS_ROOT = "RESULTS"

COMMON_FULL_SCHOOL_SUBJECTS = ["Poise", "Islamiyyah"]


# =========================================================
# SUBJECT NORMALIZATION
# =========================================================

def normalize_subject_key(subject):
    value = str(subject or "").upper().strip()
    value = value.replace(".", "").replace("&", "AND")
    value = " ".join(value.replace("_", " ").replace("-", " ").split())

    aliases = {
        "MATHS": "MATHEMATICS",
        "ENGLISH": "ENGLISH LANGUAGE",

        "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNT",
        "ACCOUNTING": "FINANCIAL ACCOUNT",
        "ACCOUNTS": "FINANCIAL ACCOUNT",
        "ACCOUNT": "FINANCIAL ACCOUNT",

        "MARKETTING": "MARKETING",

        "IRK": "IRS",
        "IRK / IRS": "IRS",
        "IRS": "IRS",

        "AGRICULTURE": "AGRICULTURAL SCIENCE",
        "AGRICULTURAL SCIENCE": "AGRICULTURAL SCIENCE",

        "COMPUTER STUDIES": "COMPUTER SCIENCE",
        "COMPUTER": "COMPUTER SCIENCE",

        "TECHNICAL": "TECHNICAL DRAWING",
        "ARABIC": "ARABIC LANGUAGE",
        "CIVIC": "CIVIC EDUCATION",

        "ISLAMIYAH": "ISLAMIYYAH",
        "ISLAMIYYA": "ISLAMIYYAH",

        "P H E": "PHE",

        # Heritage / Citizenship
        "HERITAGE AND CITIZENSHIP STUDIES": "CIT AND HER STD",
        "HERITAGE CITIZENSHIP STUDIES": "CIT AND HER STD",
        "CITIZENSHIP AND HERITAGE STUDIES": "CIT AND HER STD",
        "CIT AND HER STD": "CIT AND HER STD",
        "CIT HER STD": "CIT AND HER STD",

        # Social / Citizenship
        "SOC AND CIT STD": "SOC AND CIT STD",
        "SOCIAL AND CITIZENSHIP STUDIES": "SOC AND CIT STD",

        # Digital Technology
        "DIGITAL TECH": "DIGITAL TECH",
        "DIGITAL TECHNOLOGY": "DIGITAL TECH",

        # Horticulture
        "HORTICULTURE AND CROP PRODUCTION": "HORT AND CROP PRODUCTION",

        # Garment
        "GARMENT MAKING": "GARMENT MAKING",
    }

    canonical = aliases.get(value, value)

    # Phase 2 dynamic subject registry keeps an immutable machine key even if
    # Admin later edits the visible subject name. Registry lookup is deliberately
    # non-seeding here so importing class_config never creates/migrates files.
    try:
        from modules.subject_registry import resolve_subject_key
        return resolve_subject_key(canonical, seed_if_missing=False) or canonical
    except Exception:
        return canonical


def normalize_subject_display(subject):
    key = normalize_subject_key(subject)

    # Admin-created subjects and Admin-renamed catalogue names should retain
    # their configured visible label while the immutable subject key stays stable.
    try:
        from modules.subject_registry import get_subject
        registry_subject = get_subject(key)
        if registry_subject and (registry_subject.get("name_overridden") or registry_subject.get("source") == "admin"):
            configured_name = str(registry_subject.get("name") or "").strip()
            if configured_name: return configured_name
    except Exception:
        pass

    display = {
        "MATHEMATICS": "Mathematics",
        "ENGLISH LANGUAGE": "English Language",

        "CHEMISTRY": "Chemistry",
        "PHYSICS": "Physics",
        "BIOLOGY": "Biology",
        "TECHNICAL DRAWING": "Technical Drawing",

        "IRS": "IRK",
        "ISLAMIYYAH": "Islamiyyah",

        "COMPUTER SCIENCE": "Computer Science",
        "FURTHER MATHEMATICS": "Further Mathematics",
        "AGRICULTURAL SCIENCE": "Agricultural Science",

        "CIVIC EDUCATION": "Civic Education",
        "GEOGRAPHY": "Geography",
        "ECONOMICS": "Economics",

        "POISE": "Poise",

        "LITERATURE": "Literature",
        "GOVERNMENT": "Government",

        "HAUSA LANGUAGE": "Hausa Language",
        "YORUBA LANGUAGE": "Yoruba Language",
        "ARABIC LANGUAGE": "Arabic Language",

        "MARKETING": "Marketing",
        "COMMERCE": "Commerce",
        "FINANCIAL ACCOUNT": "Financial Account",

        "HERITAGE AND CITIZENSHIP STUDIES": "Heritage & Citizenship Studies",
        "HCS": "Heritage & Citizenship Studies",
        "CIT AND HER STD": "Cit & Her. Std",
        "SOC AND CIT STD": "Soc. & Cit. Std",

        "NATIONAL VALUE": "National Value",
        "CCA": "CCA",
        "BUSINESS STUDIES": "Business Studies",
        "HISTORY": "History",
        "BST": "BST",
        "PHE": "P.H.E",
        "PVS": "PVS",

        "HORT AND CROP PRODUCTION": "Hort & Crop Production",
        "DIGITAL TECH": "Digital Tech.",
        "DIGITAL TECHNOLOGY": "Digital Tech.",
        "INTER SCIENCE": "Inter Science",
        "GARMENT MAKING": "Garment Making",
    }

    return display.get(key, key.title())


def unique_ordered(subjects):
    seen, output = set(), []

    for subject in subjects:
        subject = str(subject or "").strip()
        if not subject: continue

        key = normalize_subject_key(subject)
        if key in seen: continue

        seen.add(key)
        output.append(normalize_subject_display(subject))

    return output


# =========================================================
# RAW SUBJECT LISTS
# =========================================================

JSS_SUBJECTS_BY_LEVEL_RAW = {
    "JSS1": get_source_subjects("JSS1"),
    "JSS2": get_source_subjects("JSS2"),
    "JSS3": get_source_subjects("JSS3"),
}



SS_OFFICIAL_SUBJECTS_BY_LEVEL_RAW = {level: get_source_subjects(level) for level in ["SS1", "SS2", "SS3"]}

# Detailed EMIS class-subject structure: GOLD/SILVER/DIAMOND use Science; B/C uses the combined Art + Commercial pool.
SS_SCIENCE_SUBJECTS_BY_LEVEL_RAW = {level: get_secondary_track_subjects(level, "SCIENCE") for level in ["SS1", "SS2", "SS3"]}
SS_ART_SUBJECTS_BY_LEVEL_RAW = {level: get_secondary_track_subjects(level, "ART_COMMERCIAL") for level in ["SS1", "SS2", "SS3"]}
SS_COMMERCIAL_SUBJECTS_BY_LEVEL_RAW = {level: get_secondary_track_subjects(level, "ART_COMMERCIAL") for level in ["SS1", "SS2", "SS3"]}



# =========================================================
# CLEANED SUBJECT LISTS
# =========================================================

JSS_SUBJECTS_BY_LEVEL = {level: unique_ordered(subjects) for level, subjects in JSS_SUBJECTS_BY_LEVEL_RAW.items()}
JSS_SUBJECTS = unique_ordered(sum(JSS_SUBJECTS_BY_LEVEL_RAW.values(), []))  # compatibility union only; class lookup uses the per-level map

SS_SCIENCE_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects) for level, subjects in SS_SCIENCE_SUBJECTS_BY_LEVEL_RAW.items()
}

SS_ART_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects) for level, subjects in SS_ART_SUBJECTS_BY_LEVEL_RAW.items()
}

SS_COMMERCIAL_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects) for level, subjects in SS_COMMERCIAL_SUBJECTS_BY_LEVEL_RAW.items()
}

SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(SS_ART_SUBJECTS_BY_LEVEL.get(level, []) + SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, []))
    for level in ["SS1", "SS2", "SS3"]
}

CLASS_SUBJECTS = {
    **{level: unique_ordered(get_source_subjects(level)) for level in ["CRECHE", "STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2", "PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6"]},
    "JSS1": JSS_SUBJECTS_BY_LEVEL["JSS1"], "JSS2": JSS_SUBJECTS_BY_LEVEL["JSS2"], "JSS3": JSS_SUBJECTS_BY_LEVEL["JSS3"],
    # Broad SS views contain every subject available to that level.
    "SS1": unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL["SS1"] + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS1"]),
    "SS2": unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL["SS2"] + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS2"]),
    "SS3": unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL["SS3"] + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS3"]),
}


# =========================================================
# CLASS NORMALIZATION
# =========================================================

def normalize_class_level(value):
    """Normalize broad regular-school class levels, including Basic 1-12 aliases and exact arms."""
    raw = str(value or "").upper().strip()
    if not raw: return ""

    # Strip a trailing lower-school arm/group before broad class normalization.
    spaced = " ".join(raw.replace("_", " ").replace("-", " ").split())
    basic_match = re.search(r"\bBASIC\s*(1[0-2]|[1-9])(?:\s*[ABC])?\b", spaced)
    if basic_match:
        number = int(basic_match.group(1))
        return {1:"PRIMARY1",2:"PRIMARY2",3:"PRIMARY3",4:"PRIMARY4",5:"PRIMARY5",6:"PRIMARY6",7:"JSS1",8:"JSS2",9:"JSS3",10:"SS1",11:"SS2",12:"SS3"}.get(number, "")

    canonical = normalize_school_class(raw)
    if canonical in STUDENT_DATABASE_CLASSES: return canonical

    compact = re.sub(r"[\s_\-/&]", "", raw)
    for level in ["CRECHE", "STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2", "PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6", "JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]:
        level_compact = re.sub(r"[\s_\-/&]", "", level)
        if compact == level_compact or compact.startswith(level_compact): return level

    # Friendly lower-school labels such as Prep Gold / Nursery 1 Silver.
    if compact.startswith("PREP") or compact.startswith("PRECLASS"): return "PRE_CLASS"
    if compact.startswith("NURSERY1"): return "NURSERY1"
    if compact.startswith("NURSERY2"): return "NURSERY2"
    return ""

def normalize_configured_class_level(value):
    """Normalize any configured EMIS class, including Tahfeez and Islamiyah parallel levels."""
    return normalize_school_class(value)


def get_configured_class_metadata(value):
    return get_class_metadata(normalize_configured_class_level(value))


def is_configured_class(value):
    return normalize_configured_class_level(value) in ALL_CONFIGURED_CLASSES


def normalize_class_arm(value, fallback_level=""):
    """Normalize the exact arm/group while preserving existing JSS/SS behavior."""
    raw = str(value or "").upper().strip() or str(fallback_level or "").upper().strip()
    if not raw: return ""
    level = normalize_class_level(raw) or normalize_class_level(fallback_level)
    if not level: return ""
    compact = re.sub(r"[\s_\-/&]", "", raw)

    if level in {"CRECHE", "STARTER"}: return level
    if level == "PRE_CLASS":
        if "GOLD" in compact: return "PRE_CLASS_GOLD"
        if "SILVER" in compact: return "PRE_CLASS_SILVER"
        return ""
    if level in {"NURSERY1", "NURSERY2"}:
        if "GOLD" in compact: return f"{level}_GOLD"
        if "SILVER" in compact: return f"{level}_SILVER"
        return ""
    if level.startswith("PRIMARY"):
        # Accept Primary 1A and Basic 1A forms.
        suffix = ""
        m = re.search(r"(?:PRIMARY\s*\d+|BASIC\s*[1-6])\s*([AB])\b", raw.replace("_", " "), re.I)
        if m: suffix = m.group(1).upper()
        elif compact.startswith(level) and compact[len(level):] in {"A", "B"}: suffix = compact[len(level):]
        return f"{level}{suffix}" if suffix else ""

    if level.startswith("JSS"):
        for arm in ["A", "B", "C"]:
            if compact == f"{level}{arm}": return f"{level}{arm}"
        return level if compact == level else ""

    if "GOLD" in compact: return f"{level}_GOLD"
    if "SILVER" in compact: return f"{level}_SILVER"
    if "DIAMOND" in compact: return f"{level}_DIAMOND"
    suffix = compact[len(level):] if compact.startswith(level) else ""
    if suffix in {"B", "BC"}: return f"{level}_B/C"
    if compact == level: return level
    return ""

def get_class_level_from_arm(class_arm):
    return normalize_class_level(class_arm)


# =========================================================
# SENIOR SCHOOL STREAM / TRACK
# =========================================================

def get_ss_stream(class_arm):
    """
    Broad SS stream:
        SCIENCE
        ART_COMMERCIAL
        GENERAL
    """

    arm = normalize_class_arm(class_arm)

    if not arm.startswith("SS"): return ""
    if arm.endswith("_B/C"): return "ART_COMMERCIAL"
    if any(label in arm for label in ["_GOLD", "_SILVER", "_DIAMOND"]): return "SCIENCE"

    return "GENERAL"


def get_ss_track(class_arm, preferred_track=""):
    """
    Exact SS track:
        SCIENCE
        ART
        COMMERCIAL
        ART_COMMERCIAL
        GENERAL
    """

    arm = normalize_class_arm(class_arm)
    preferred = str(preferred_track or "").upper().strip()

    if preferred in {"ART", "COMMERCIAL", "ART_COMMERCIAL", "SCIENCE"}: return preferred
    if not arm.startswith("SS"): return ""
    if arm.endswith("_B/C"): return "ART_COMMERCIAL"
    if any(label in arm for label in ["_GOLD", "_SILVER", "_DIAMOND"]): return "SCIENCE"

    return "GENERAL"


def get_class_arm_stream_label(class_arm):
    """Human-readable section/stream label used by student-placement UIs."""
    arm = normalize_class_arm(class_arm); level = normalize_class_level(arm)
    if not level: return ""
    if level in {"CRECHE", "STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2"}: return "Early Years"
    if level.startswith("PRIMARY"): return "Primary"
    if level.startswith("JSS"): return "Junior"
    stream = get_ss_stream(arm)
    if stream == "SCIENCE": return "Science"
    if stream == "ART_COMMERCIAL": return "Arts / Commercial"
    return "General"


def get_class_arm_metadata(class_arm):
    """Small normalized metadata object for UI labels and movement warnings."""
    arm = normalize_class_arm(class_arm); level = normalize_class_level(arm); section = school_section_for_class(level)
    return {"class_arm": arm, "class_level": level, "stream": get_ss_stream(arm) if level.startswith("SS") else section, "stream_label": get_class_arm_stream_label(arm), "section": section}




# =========================================================
# CBT TERM MODE — SHARED BY UPLOADS / PUSH / PORTAL / RESULTS
# =========================================================

def is_exam_term_required_class(value):
    level = normalize_class_level(value)
    return level in TERM_REQUIRED_EXAM_CLASSES


def is_exam_term_optional_class(value):
    level = normalize_class_level(value)
    return level in TERM_OPTIONAL_EXAM_CLASSES


def supports_exam_terms(value):
    level = normalize_class_level(value)
    return level in EXAM_SUPPORTED_CLASSES

# =========================================================
# SUBJECT LOOKUP
# =========================================================

def unique_subjects(subjects):
    return unique_ordered(subjects)


def _registry_subject_rows(class_level, track="", active_only=True):
    try:
        from modules.subject_registry import get_class_subject_rows
        return get_class_subject_rows(class_level, track=track, active_only=active_only)
    except Exception:
        return []


def _registry_manages_class(class_level):
    """True when the Phase 2 registry is present and owns this configured class.

    This distinction matters when Admin intentionally deactivates every subject
    for a class: an empty dynamic result must stay empty instead of falling back
    to the old hard-coded lists and silently re-enabling those subjects.
    """
    level = normalize_school_class(class_level)
    if not level: return False
    try:
        from modules.subject_registry import REGISTRY_FILE, REGISTRY_VERSION, read_subject_registry
        if not REGISTRY_FILE.exists(): return False
        data = read_subject_registry(seed_if_missing=False)
        return int(data.get("version") or 0) >= REGISTRY_VERSION and level in data.get("assignments", {})
    except Exception:
        return False


def _unique_subject_names(rows):
    seen, output = set(), []
    for row in rows or []:
        name = str(row.get("name") if isinstance(row, dict) else row or "").strip()
        key = str(row.get("key") if isinstance(row, dict) else normalize_subject_key(name) or "").strip()
        if not name or key in seen: continue
        seen.add(key); output.append(name)
    return output


def get_configured_subjects_for_class(class_category, preferred_track="", active_only=True):
    """Return dynamic subjects for any configured class without activating its student database."""
    level = normalize_configured_class_level(class_category)
    if not level: return []
    track = str(preferred_track or "").upper().strip() if level.startswith("SS") else ""
    rows = _registry_subject_rows(level, track=track, active_only=active_only)
    if rows or _registry_manages_class(level): return _unique_subject_names(rows)
    source = get_source_subjects(level)
    if source: return list(source)
    if level in SUPPORTED_CLASSES: return unique_ordered(CLASS_SUBJECTS.get(level, []))
    return []


def get_subjects_for_class(class_category, class_arm=None, preferred_track=""):
    """Return active subjects for any regular class stored in students2026.csv."""
    level = normalize_class_level(class_category); arm = normalize_class_arm(class_arm or class_category, level)
    if not level: return []
    track = get_ss_track(arm, preferred_track) if level.startswith("SS") else ""
    registry_rows = _registry_subject_rows(level, track=track, active_only=True)
    if registry_rows or _registry_manages_class(level): return _unique_subject_names(registry_rows)

    if level in {"CRECHE", "STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2", "PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6"}: return unique_ordered(get_source_subjects(level) or CLASS_SUBJECTS.get(level, []))
    if level.startswith("JSS"): return unique_ordered(JSS_SUBJECTS_BY_LEVEL.get(level, []))
    if track == "SCIENCE": return unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL.get(level, []))
    if track == "ART": return unique_ordered(SS_ART_SUBJECTS_BY_LEVEL.get(level, []))
    if track == "COMMERCIAL": return unique_ordered(SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, []))
    if track == "ART_COMMERCIAL": return unique_ordered(SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, []))
    return unique_ordered(CLASS_SUBJECTS.get(level, []))


# =========================================================
# SUBJECT / TARGET COMPATIBILITY
#
# Used by push.py to prevent teachers from accidentally
# assigning SS examinations to incompatible streams.
# =========================================================

def get_ss_subject_tracks(class_level, subject):
    """Return SS tracks for a subject, preferring the dynamic registry over legacy hard-coded lists."""
    level = normalize_class_level(class_level); wanted = normalize_subject_key(subject)
    if not level.startswith("SS") or not wanted: return set()

    try:
        from modules.subject_registry import get_class_subject_rows, get_subject_tracks, resolve_subject_key
        registry_key = resolve_subject_key(subject, seed_if_missing=False); all_rows = get_class_subject_rows(level, active_only=False)
        defined = next((row for row in all_rows if str(row.get("key") or "") == registry_key), None)
        if defined is not None: return set(get_subject_tracks(level, registry_key)) if defined.get("active", False) else set()
    except Exception:
        pass

    tracks = set(); science_keys = {normalize_subject_key(item) for item in SS_SCIENCE_SUBJECTS_BY_LEVEL.get(level, [])}; art_keys = {normalize_subject_key(item) for item in SS_ART_SUBJECTS_BY_LEVEL.get(level, [])}; commercial_keys = {normalize_subject_key(item) for item in SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, [])}
    if wanted in science_keys: tracks.add("SCIENCE")
    if wanted in art_keys: tracks.add("ART")
    if wanted in commercial_keys: tracks.add("COMMERCIAL")
    return tracks


def format_ss_tracks(tracks):
    """Friendly track names for push warnings/errors."""
    labels = {"SCIENCE": "Science", "ART": "Arts", "COMMERCIAL": "Commercial"}
    ordered = [track for track in ["SCIENCE", "ART", "COMMERCIAL"] if track in set(tracks or [])]
    return ", ".join(labels.get(track, track.title()) for track in ordered)


def get_subject_target_compatibility(class_level, class_arm, subject):
    """
    Determine whether a subject may be pushed to a class/arm.

    Returns:
        {
            "allowed": True/False,
            "warning": "",
            "reason": "",
            "tracks": [...]
        }

    Rules:
        Broad SS target:
            Allow push, but warn if not valid for every stream.

        Science arm:
            Reject subjects not offered to Science.

        SS_B/C:
            Allow Art/Commercial subjects.
            Warn when only one side of the combined arm should see it.
            Reject Science-only subjects.

        Student portal remains the final visibility safety filter.
    """

    level = normalize_class_level(class_level)
    arm = normalize_class_arm(class_arm or class_level, level)
    subject_key = normalize_subject_key(subject)
    subject_display = normalize_subject_display(subject)

    result = {"allowed": True, "warning": "", "reason": "", "tracks": []}

    if not level or not subject_key:
        result["allowed"] = False
        result["reason"] = "Invalid class or subject."
        return result

    # -----------------------------------------------------
    # EARLY YEARS / PRIMARY / JSS
    # -----------------------------------------------------

    if not level.startswith("SS"):
        allowed_keys = {normalize_subject_key(item) for item in get_subjects_for_class(level, arm)}
        if subject_key not in allowed_keys:
            result["allowed"] = False; result["reason"] = f"{subject_display} is not configured as a subject for {level}."
        return result

    # -----------------------------------------------------
    # SS TRACK MEMBERSHIP
    # -----------------------------------------------------

    tracks = get_ss_subject_tracks(level, subject)
    result["tracks"] = sorted(tracks)

    if not tracks:
        result["allowed"] = False
        result["reason"] = f"{subject_display} is not configured as a subject for {level}."
        return result

    # -----------------------------------------------------
    # BROAD SS CLASS
    #
    # Example:
    #   Financial Account -> SS1
    #
    # Push is allowed because the student portal will only
    # show it to students whose stream offers the subject.
    # -----------------------------------------------------

    if arm == level:
        all_tracks = {"SCIENCE", "ART", "COMMERCIAL"}

        if tracks != all_tracks:
            track_text = format_ss_tracks(tracks)
            result["warning"] = (
                f"{subject_display} is restricted to {track_text} students. "
                f"It was pushed to {level}, but only eligible students will see it."
            )

        return result

    # -----------------------------------------------------
    # SCIENCE ARM
    #
    # GOLD / SILVER / DIAMOND are Science.
    # -----------------------------------------------------

    target_track = get_ss_track(arm)

    if target_track == "SCIENCE":
        if "SCIENCE" not in tracks:
            track_text = format_ss_tracks(tracks)

            result["allowed"] = False
            result["reason"] = (
                f"{subject_display} cannot be pushed to {arm}. "
                f"{arm} is a Science arm while {subject_display} is configured for {track_text} students."
            )

        return result

    # -----------------------------------------------------
    # COMBINED ARTS / COMMERCIAL ARM
    # -----------------------------------------------------

    if target_track == "ART_COMMERCIAL":
        compatible_tracks = tracks.intersection({"ART", "COMMERCIAL"})

        # Science-only subject cannot be pushed to B/C.
        if not compatible_tracks:
            result["allowed"] = False
            result["reason"] = (
                f"{subject_display} cannot be pushed to {arm}. "
                f"{arm} is an Arts / Commercial arm while {subject_display} is a Science subject."
            )
            return result

        # Art-only subject.
        if compatible_tracks == {"ART"}:
            result["warning"] = (
                f"{subject_display} is an Arts subject. "
                f"Commercial students in {arm} will not see it."
            )

        # Commercial-only subject.
        elif compatible_tracks == {"COMMERCIAL"}:
            result["warning"] = (
                f"{subject_display} is a Commercial subject. "
                f"Arts students in {arm} will not see it."
            )

        return result

    return result


# =========================================================
# CLASS VALIDATION
# =========================================================

def is_valid_class(class_category):
    """Validate any active regular-school class stored in students2026.csv."""
    return normalize_class_level(class_category) in STUDENT_DATABASE_CLASSES


def is_valid_class_arm(class_arm):
    """
    Examples:
        JSS1A       -> True
        SS1_GOLD    -> True
        SS1B        -> True  (normalizes to SS1_B/C)
        SS3_DIAMOND -> False
    """

    arm = normalize_class_arm(class_arm)
    level = normalize_class_level(arm)

    if not level: return False
    return arm in CLASS_ARMS_BY_LEVEL.get(level, [])


# =========================================================
# STUDENT DATABASE HELPERS
# =========================================================

def get_student_csv_file(class_category=None):
    """All classes use the single authoritative student CSV."""
    return STUDENT_CSV_FILE


def get_class_arms(class_category):
    """Return configured arms for a broad class level."""
    level = normalize_class_level(class_category)
    return list(CLASS_ARMS_BY_LEVEL.get(level, [])) if level else []
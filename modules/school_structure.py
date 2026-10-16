# MODULE: School Structure — canonical EMIS school sections, operational databases, Islamiyah/Tahfeez classifications and assessment schemes

from copy import deepcopy


# ============================================================
# OPERATIONAL DATABASE ACTIVATION
# ============================================================

# students2026.csv is now the active regular-school master database for Early Years,
# Primary, JSS and SS. Tahfeez is deliberately NOT stored as the student's regular
# Class/Class_category because Tahfeez is a parallel classification linked by
# Admission_number through static/data/database/tahfeez2026.csv.
MAIN_SCHOOL_CLASS_LEVELS = [
    "CRECHE", "STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2",
    "PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6",
    "JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3",
]

TAHFEEZ_CLASS_LEVELS = ["TAHFEEZ1", "TAHFEEZ2", "TAHFEEZ3", "TAHFEEZ4", "TAHFEEZ5"]
ISLAMIYAH_BASE_LEVELS = [
    "ISLAMIYAH_STARTER", "ISLAMIYAH_PREP1", "ISLAMIYAH1", "ISLAMIYAH2", "ISLAMIYAH3",
    "ISLAMIYAH4", "ISLAMIYAH5", "ISLAMIYAH6", "ISLAMIYAH7",
]

ISLAMIYAH_ARMS_BY_LEVEL = {"ISLAMIYAH1": list("ABCD"), "ISLAMIYAH2": list("ABCDEFGH"), "ISLAMIYAH3": list("ABCDEF"), "ISLAMIYAH4": list("ABCDEF"), "ISLAMIYAH5": list("ABC"), "ISLAMIYAH6": list("AB")}
ISLAMIYAH_ROSTER_CLASSES = ["ISLAMIYAH_STARTER", "ISLAMIYAH_PREP1"] + [f"{level}{arm}" for level, arms in ISLAMIYAH_ARMS_BY_LEVEL.items() for arm in arms] + ["ISLAMIYAH7"]
ISLAMIYAH_CLASS_LEVELS = list(dict.fromkeys(ISLAMIYAH_BASE_LEVELS + ISLAMIYAH_ROSTER_CLASSES))

# Backward-compatible name used throughout the existing project. From Phase 10
# activation onward REGULAR_CLASS_LEVELS means the student's normal school class.
# Tahfeez remains separately configured and operational through its own database.
REGULAR_CLASS_LEVELS = list(MAIN_SCHOOL_CLASS_LEVELS)
ACTIVE_DATABASE_CLASSES = list(MAIN_SCHOOL_CLASS_LEVELS)
TAHFEEZ_DATABASE_CLASSES = list(TAHFEEZ_CLASS_LEVELS)
PENDING_DATABASE_CLASSES = []
ALL_CONFIGURED_CLASSES = list(MAIN_SCHOOL_CLASS_LEVELS) + list(TAHFEEZ_CLASS_LEVELS) + list(ISLAMIYAH_CLASS_LEVELS)


# ============================================================
# SCHOOL SECTIONS
# ============================================================

SCHOOL_SECTION_ORDER = ["EARLY_YEARS", "TAHFEEZ", "PRIMARY", "JUNIOR_SECONDARY", "SENIOR_SECONDARY", "ISLAMIYAH"]

SCHOOL_SECTIONS = {
    "EARLY_YEARS": {"label": "Early Years / Nursery", "short_label": "Early Years", "classes": ["CRECHE", "STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2"]},
    "TAHFEEZ": {"label": "Tahfeez", "short_label": "Tahfeez", "classes": list(TAHFEEZ_CLASS_LEVELS)},
    "PRIMARY": {"label": "Primary School", "short_label": "Primary", "classes": ["PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6"]},
    "JUNIOR_SECONDARY": {"label": "Junior Secondary School", "short_label": "JSS", "classes": ["JSS1", "JSS2", "JSS3"]},
    "SENIOR_SECONDARY": {"label": "Senior Secondary School", "short_label": "SS", "classes": ["SS1", "SS2", "SS3"]},
    "ISLAMIYAH": {"label": "Islamiyah School", "short_label": "Islamiyah", "classes": list(ISLAMIYAH_CLASS_LEVELS)},
}

CLASS_LABELS = {
    "CRECHE": "Creche", "STARTER": "Starter", "PRE_CLASS": "Prep / Pre-Class", "NURSERY1": "Nursery 1", "NURSERY2": "Nursery 2",
    "TAHFEEZ1": "Tahfeez 1", "TAHFEEZ2": "Tahfeez 2", "TAHFEEZ3": "Tahfeez 3", "TAHFEEZ4": "Tahfeez 4", "TAHFEEZ5": "Tahfeez 5",
    "PRIMARY1": "Primary 1", "PRIMARY2": "Primary 2", "PRIMARY3": "Primary 3", "PRIMARY4": "Primary 4", "PRIMARY5": "Primary 5", "PRIMARY6": "Primary 6",
    "JSS1": "JSS1", "JSS2": "JSS2", "JSS3": "JSS3", "SS1": "SS1", "SS2": "SS2", "SS3": "SS3",
    "ISLAMIYAH_STARTER": "Islamiyah Starter", "ISLAMIYAH_PREP1": "Islamiyah Prep-1",
    "ISLAMIYAH1": "Islamiyah 1", "ISLAMIYAH2": "Islamiyah 2", "ISLAMIYAH3": "Islamiyah 3", "ISLAMIYAH4": "Islamiyah 4",
    "ISLAMIYAH5": "Islamiyah 5", "ISLAMIYAH6": "Islamiyah 6", "ISLAMIYAH7": "Islamiyah 7",
}


# ============================================================
# SUBJECT STRUCTURE FROM THE PROVIDED SCHOOL DOCUMENT
# ============================================================

CLASS_LABELS.update({key: "Islamiyyah " + key.removeprefix("ISLAMIYAH") for key in ISLAMIYAH_ROSTER_CLASSES if key not in CLASS_LABELS})

EARLY_YEARS_SUBJECTS = {
    # No Creche subject list was supplied; keep it active as a roster without inventing subjects.
    "CRECHE": [],
    "STARTER": ["Letter Works", "Number Work", "Picture Reading", "Creative Art", "Free Writing Skill", "Islamiyyah"],
    "PRE_CLASS": ["Letter Works", "Number Work", "Picture Reading", "Creative Art", "Free Writing Skill", "Islamiyyah"],
    "NURSERY1": ["Letter Works", "Number Work", "Pre-Science", "Social Habits", "Creative Art", "Writing Skill", "Arabic", "I. R. S", "Islamiyyah"],
    "NURSERY2": ["Letter Works", "Number Work", "Pre-Science", "Social Habits", "Creative Art", "Writing Skill", "Arabic", "I. R. S", "Islamiyyah"],
}

TAHFEEZ_1_2_SUBJECTS = ["Letter Works", "Number Work", "Pre-Science", "Social Habits", "Creative Art", "Writing Skill", "Arabic", "Quran", "Islamiyyah"]
TAHFEEZ_3_5_SUBJECTS = ["Mathematics", "English Studies", "Basic Science", "Social and Citizenship Studies", "Hand Writing", "Arabic", "I. R. S", "Quran", "Hausa Language", "Yoruba Language", "Basic Digital Literacy", "Islamiyyah"]

TAHFEEZ_SUBJECTS = {
    "TAHFEEZ1": list(TAHFEEZ_1_2_SUBJECTS), "TAHFEEZ2": list(TAHFEEZ_1_2_SUBJECTS),
    "TAHFEEZ3": list(TAHFEEZ_3_5_SUBJECTS), "TAHFEEZ4": list(TAHFEEZ_3_5_SUBJECTS), "TAHFEEZ5": list(TAHFEEZ_3_5_SUBJECTS),
}

PRIMARY_1_3_SUBJECTS = [
    "English Studies", "Mathematics", "Hausa Language", "Yoruba Language", "Basic Science", "Physical & Health Education", "IRK",
    "Nigerian History", "Social & Citizenship Studies", "Culture & Creative Arts (CCA)", "Arabic", "Islamiyyah",
]

PRIMARY_4_6_SUBJECTS = [
    "English Studies", "Mathematics", "Hausa Language", "Yoruba Language", "Basic Science & Technology", "Physical & Health Education", "Basic Digital Literacy", "IRK",
    "Nigerian History", "Social & Citizenship Studies", "Culture & Creative Arts (CCA)", "Pre-Vocational Studies", "Arabic", "Islamiyyah",
]

PRIMARY_SUBJECTS = {
    "PRIMARY1": list(PRIMARY_1_3_SUBJECTS), "PRIMARY2": list(PRIMARY_1_3_SUBJECTS), "PRIMARY3": list(PRIMARY_1_3_SUBJECTS),
    "PRIMARY4": list(PRIMARY_4_6_SUBJECTS), "PRIMARY5": list(PRIMARY_4_6_SUBJECTS), "PRIMARY6": list(PRIMARY_4_6_SUBJECTS),
}

# Official JSS/SS subject structure from EMIS Class_Subjects.pdf / complete class-subject workbook.
# JSS1-JSS3 share one common list across A/B/C. SS subjects are stream-specific by arm.
SECONDARY_SUBJECT_SOURCE_VERSION = "2026-10-16-emis-class-subjects-pdf-xlsx"

JSS_COMMON_SUBJECTS = [
    "Mathematics", "English Language", "IRK", "Islamiyyah", "Poise", "Heritage & Citizenship Studies", "National Value", "Yoruba Language", "Hausa Language", "Arabic Language",
    "CCA", "Business Studies", "History", "BST", "P.H.E", "PVS", "Hort & Crop Production", "Digital Tech.", "Inter Science", "Garment Making",
]

SS_SCIENCE_SUBJECTS = {
    "SS1": ["Mathematics", "English Language", "Chemistry", "Physics", "Biology", "Technical Drawing", "IRK / IRS", "Computer Science", "Further Mathematics", "Agricultural Science", "Civic Education", "Geography", "Economics", "Digital Tech.", "Cit & Her. Std", "Garment Making", "Poise", "Islamiyyah"],
    "SS2": ["Mathematics", "English Language", "Chemistry", "Physics", "Biology", "Technical Drawing", "IRK / IRS", "Computer Science", "Further Mathematics", "Agricultural Science", "Civic Education", "Geography", "Economics", "Poise", "Islamiyyah"],
    "SS3": ["Mathematics", "English Language", "Chemistry", "Physics", "Biology", "Further Mathematics", "Agricultural Science", "Civic Education", "Economics", "Poise", "Islamiyyah"],
}

SS_ART_COMMERCIAL_SUBJECTS = {
    "SS1": ["Mathematics", "English Language", "Literature", "Government", "IRS", "Hausa Language", "Yoruba Language", "Arabic Language", "Civic Education", "Marketing", "Economics", "Financial Account", "Commerce", "Poise", "Islamiyyah"],
    "SS2": ["Mathematics", "English Language", "Literature", "Government", "IRS", "Hausa Language", "Yoruba Language", "Arabic Language", "Civic Education", "Marketing", "Economics", "Financial Account", "Commerce", "Poise", "Islamiyyah"],
    "SS3": ["Mathematics", "English Language", "Literature", "Government", "Hausa Language", "Yoruba Language", "Arabic Language", "Civic Education", "Marketing", "Economics", "Commerce", "Financial Account", "Poise", "Islamiyyah"],
}

def _unique_subjects(values):
    output = []; seen = set()
    for value in values:
        key = " ".join(str(value or "").upper().replace("IRK / IRS", "IRS").split())
        if key and key not in seen: seen.add(key); output.append(value)
    return output

SECONDARY_SUBJECTS = {
    "JSS1": list(JSS_COMMON_SUBJECTS), "JSS2": list(JSS_COMMON_SUBJECTS), "JSS3": list(JSS_COMMON_SUBJECTS),
    "SS1": _unique_subjects(SS_SCIENCE_SUBJECTS["SS1"] + SS_ART_COMMERCIAL_SUBJECTS["SS1"]),
    "SS2": _unique_subjects(SS_SCIENCE_SUBJECTS["SS2"] + SS_ART_COMMERCIAL_SUBJECTS["SS2"]),
    "SS3": _unique_subjects(SS_SCIENCE_SUBJECTS["SS3"] + SS_ART_COMMERCIAL_SUBJECTS["SS3"]),
}

def get_secondary_track_subjects(class_level, track=""):
    level = normalize_school_class(class_level) if "normalize_school_class" in globals() else str(class_level or "").upper().strip()
    wanted = str(track or "").upper().strip().replace("-", "_")
    if level.startswith("JSS"): return list(JSS_COMMON_SUBJECTS)
    if level not in {"SS1", "SS2", "SS3"}: return []
    if wanted == "SCIENCE": return list(SS_SCIENCE_SUBJECTS.get(level, []))
    if wanted in {"ART", "COMMERCIAL", "ART_COMMERCIAL", "ART + COMMERCIAL", "B/C", "BC"}: return list(SS_ART_COMMERCIAL_SUBJECTS.get(level, []))
    return list(SECONDARY_SUBJECTS.get(level, []))

ISLAMIYAH_SUBJECTS = {
    "ISLAMIYAH_STARTER": ["Quran", "Hadith", "Arabiyah", "Arqaam", "Huruf"],
    "ISLAMIYAH_PREP1": ["Quran", "Hadith", "Fiqh", "Tawheed", "Murtala", "Arabiyah", "Hisab", "Azkhar"],
    "ISLAMIYAH1": ["Quran", "Hadith", "Fiqh", "Tawheed", "Huruf"], "ISLAMIYAH2": ["Quran", "Hadith", "Fiqh", "Tawheed", "Huruf"], "ISLAMIYAH3": ["Quran", "Hadith", "Fiqh", "Tawheed", "Huruf"],
    "ISLAMIYAH4": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"], "ISLAMIYAH5": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"],
    "ISLAMIYAH6": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"], "ISLAMIYAH7": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"],
}

SOURCE_NOTES = {
    "TAHFEEZ3_5_ARABIC_DUPLICATE": "The supplied school subject document lists Arabic twice for Tahfeez 3-5. The canonical runtime list stores Arabic once; the source discrepancy remains recorded for confirmation.",
    "HAUSA_YORUBA_SPLIT": "The supplied school document uses Hausa/Yoruba as a combined entry in Primary and Tahfeez 3-5. EMIS stores Hausa Language and Yoruba Language separately so each pupil can take the applicable language.",
    "ISLAMIYAH_INDEPENDENT_CLASSIFICATION": "A student's regular class and Islamiyah class are independent. Example: JSS2 + Islamiyah 5. No fixed regular-class to Islamiyah-level mapping is assumed.",
    "LOWER_SCHOOL_DATABASE_ACTIVE": "Creche, Starter, Prep / Pre-Class, Nursery 1-2 and Primary 1-6 are active regular-school classes in students2026.csv together with JSS/SS.",
    "TAHFEEZ_PARALLEL_DATABASE": "Tahfeez and Islamiyyah share the combined tahfeez2026.csv register; session placements and scores retain their existing history files. A record may optionally link to students2026.csv by Admission_number, but the supplied real Tahfeez register is preserved even when no regular-school link exists.",
    "LOWER_SCHOOL_ASSESSMENT_PENDING": "Lower-school roster activation does not invent a grading/assessment structure. Nursery/Primary/Tahfeez score components and Primary grading must be approved before full CA/Report activation.",
}


# ============================================================
# ASSESSMENT SCHEMES
# ============================================================

ASSESSMENT_SCHEMES = {
    "JSS": {"label": "Junior Secondary", "status": "active", "ca_max": 60, "exam_max": 40, "total_max": 100, "fields": {"CA1": 10, "CA2": 10, "TEST1": 20, "TEST2": 20}},
    "SS": {"label": "Senior Secondary", "status": "active", "ca_max": 30, "exam_max": 70, "total_max": 100, "fields": {"ASS1": 5, "ASS2": 5, "TEST": 20}},
    "ISLAMIYAH": {"label": "Islamiyah", "status": "active", "ca_max": 30, "exam_max": 70, "total_max": 100, "fields": {"CA": 30, "EXAM": 70}},
    "LOWER_SCHOOL": {"label": "Early Years / Primary", "status": "pending_school_scheme", "ca_max": None, "exam_max": None, "total_max": 100, "fields": {}},
    "TAHFEEZ": {"label": "Tahfeez", "status": "pending_school_scheme", "ca_max": None, "exam_max": None, "total_max": 100, "fields": {}},
}


# ============================================================
# NORMALIZATION / LOOKUP
# ============================================================

_CLASS_ALIASES = {
    "CRECHE": "CRECHE", "CRÈCHE": "CRECHE", "CRECH": "CRECHE",
    "STARTER": "STARTER", "STARTERS": "STARTER",
    "PRE": "PRE_CLASS", "PREP": "PRE_CLASS", "PRECLASS": "PRE_CLASS", "PRE CLASS": "PRE_CLASS", "PREP CLASS": "PRE_CLASS", "PRE_CLASS": "PRE_CLASS", "PRE-CLASS": "PRE_CLASS",
    "NURSERY1": "NURSERY1", "NURSERY 1": "NURSERY1", "NURSERY2": "NURSERY2", "NURSERY 2": "NURSERY2",
    "PRIMARY1": "PRIMARY1", "PRIMARY 1": "PRIMARY1", "PRIMARY2": "PRIMARY2", "PRIMARY 2": "PRIMARY2", "PRIMARY3": "PRIMARY3", "PRIMARY 3": "PRIMARY3",
    "PRIMARY4": "PRIMARY4", "PRIMARY 4": "PRIMARY4", "PRIMARY5": "PRIMARY5", "PRIMARY 5": "PRIMARY5", "PRIMARY6": "PRIMARY6", "PRIMARY 6": "PRIMARY6",
    "TAHFEEZ1": "TAHFEEZ1", "TAHFEEZ 1": "TAHFEEZ1", "TAHFEEZ2": "TAHFEEZ2", "TAHFEEZ 2": "TAHFEEZ2", "TAHFEEZ3": "TAHFEEZ3", "TAHFEEZ 3": "TAHFEEZ3",
    "TAHFEEZ4": "TAHFEEZ4", "TAHFEEZ 4": "TAHFEEZ4", "TAHFEEZ5": "TAHFEEZ5", "TAHFEEZ 5": "TAHFEEZ5",
}

BASIC_CLASS_NUMBER_BY_LEVEL = {
    "PRIMARY1": 1, "PRIMARY2": 2, "PRIMARY3": 3, "PRIMARY4": 4, "PRIMARY5": 5, "PRIMARY6": 6,
    "JSS1": 7, "JSS2": 8, "JSS3": 9, "SS1": 10, "SS2": 11, "SS3": 12,
}
BASIC_LEVEL_BY_NUMBER = {number: level for level, number in BASIC_CLASS_NUMBER_BY_LEVEL.items()}
for _number, _level in BASIC_LEVEL_BY_NUMBER.items():
    _CLASS_ALIASES[f"BASIC {_number}"] = _level
    _CLASS_ALIASES[f"BASIC{_number}"] = _level

for _level in ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"] + ISLAMIYAH_CLASS_LEVELS: _CLASS_ALIASES[_level] = _level
for _number in range(1, 8): _CLASS_ALIASES[f"ISLAMIYAH {_number}"] = f"ISLAMIYAH{_number}"
_CLASS_ALIASES.update({"ISLAMIYAH STARTER": "ISLAMIYAH_STARTER", "ISLAMIYAH STARTERS": "ISLAMIYAH_STARTER", "ISLAMIYAH PREP": "ISLAMIYAH_PREP1", "ISLAMIYAH PREP1": "ISLAMIYAH_PREP1", "ISLAMIYAH PREP 1": "ISLAMIYAH_PREP1", "ISLAMIYAH PREP-1": "ISLAMIYAH_PREP1"})


def normalize_school_class(value):
    raw = " ".join(str(value or "").upper().strip().replace("_", " ").split())
    if not raw: return ""
    raw = raw.replace("ISLAMIYYAH", "ISLAMIYAH")
    compact = raw.replace(" ", "")
    return _CLASS_ALIASES.get(raw) or _CLASS_ALIASES.get(compact) or ""


def class_label(value):
    level = normalize_school_class(value)
    return CLASS_LABELS.get(level, str(value or "").strip())


def basic_class_number(value):
    return BASIC_CLASS_NUMBER_BY_LEVEL.get(normalize_school_class(value))


def traditional_class_label(value):
    return class_label(value)


def hybrid_class_label(value):
    level = normalize_school_class(value)
    number = BASIC_CLASS_NUMBER_BY_LEVEL.get(level)
    traditional = CLASS_LABELS.get(level, str(value or "").strip())
    return f"Basic {number} / {traditional}" if number else traditional


def basic_class_reference():
    return [
        {"basic": f"Basic {number}", "traditional": CLASS_LABELS.get(level, level), "class_key": level}
        for number, level in sorted(BASIC_LEVEL_BY_NUMBER.items())
    ]


def islamiyah_base_level(value):
    level = normalize_school_class(value)
    return level[:-1] if level and level[-1:] in "ABCDEFGH" and level[:-1] in ISLAMIYAH_ARMS_BY_LEVEL else level

def is_islamiyah_class(value): return normalize_school_class(value) in ISLAMIYAH_CLASS_LEVELS

def is_tahfeez_class(value): return normalize_school_class(value) in TAHFEEZ_CLASS_LEVELS

def is_regular_class(value): return normalize_school_class(value) in MAIN_SCHOOL_CLASS_LEVELS

def database_is_active_for_class(value):
    level = normalize_school_class(value)
    return level in ACTIVE_DATABASE_CLASSES or level in TAHFEEZ_DATABASE_CLASSES or level in ISLAMIYAH_CLASS_LEVELS


def database_source_for_class(value):
    level = normalize_school_class(value)
    if level in ACTIVE_DATABASE_CLASSES: return "students2026.csv"
    if level in TAHFEEZ_DATABASE_CLASSES: return "tahfeez2026.csv"
    if level in ISLAMIYAH_CLASS_LEVELS: return "tahfeez2026.csv"
    return ""


def school_section_for_class(value):
    level = normalize_school_class(value)
    for section in SCHOOL_SECTION_ORDER:
        if level in SCHOOL_SECTIONS.get(section, {}).get("classes", []): return section
    return ""


def get_school_classes(section="", include_islamiyah=True, include_tahfeez=True):
    section = str(section or "").upper().strip()
    if section and section in SCHOOL_SECTIONS: return list(SCHOOL_SECTIONS[section]["classes"])
    classes = list(MAIN_SCHOOL_CLASS_LEVELS)
    if include_tahfeez: classes.extend(TAHFEEZ_CLASS_LEVELS)
    if include_islamiyah: classes.extend(ISLAMIYAH_CLASS_LEVELS)
    return classes


def get_class_metadata(class_level):
    level = normalize_school_class(class_level)
    if not level: return {}
    section = school_section_for_class(level); section_info = SCHOOL_SECTIONS.get(section, {}); active = database_is_active_for_class(level)
    return {
        "key": level, "label": CLASS_LABELS.get(level, level), "section": section, "section_label": section_info.get("label", section.title()),
        "is_islamiyah": level in ISLAMIYAH_CLASS_LEVELS, "is_tahfeez": level in TAHFEEZ_CLASS_LEVELS, "is_regular": level in MAIN_SCHOOL_CLASS_LEVELS,
        "database_active": active, "database_status": "active" if active else "managed_separately" if level in ISLAMIYAH_CLASS_LEVELS else "pending", "database_source": database_source_for_class(level),
    }


def get_school_structure_payload(include_subjects=False):
    sections = []
    for section_key in SCHOOL_SECTION_ORDER:
        info = SCHOOL_SECTIONS[section_key]; classes = []
        for level in info.get("classes", []):
            row = get_class_metadata(level)
            if include_subjects: row["subjects"] = get_source_subjects(level)
            classes.append(row)
        sections.append({"key": section_key, "label": info.get("label", section_key.title()), "short_label": info.get("short_label", info.get("label", section_key.title())), "classes": classes})
    return sections


def get_source_subjects(class_level):
    level = normalize_school_class(class_level)
    if level in EARLY_YEARS_SUBJECTS: return list(EARLY_YEARS_SUBJECTS[level])
    if level in TAHFEEZ_SUBJECTS: return list(TAHFEEZ_SUBJECTS[level])
    if level in PRIMARY_SUBJECTS: return list(PRIMARY_SUBJECTS[level])
    if level in SECONDARY_SUBJECTS: return list(SECONDARY_SUBJECTS[level])
    if is_islamiyah_class(level): return list(ISLAMIYAH_SUBJECTS.get(islamiyah_base_level(level), []))
    return []


def get_assessment_scheme(class_level="", school="REGULAR"):
    school_key = str(school or "").upper().strip(); level = normalize_school_class(class_level) or str(class_level or "").upper().strip()
    if school_key == "ISLAMIYAH" or is_islamiyah_class(level): return deepcopy(ASSESSMENT_SCHEMES["ISLAMIYAH"])
    if school_key == "TAHFEEZ" or is_tahfeez_class(level): return deepcopy(ASSESSMENT_SCHEMES["TAHFEEZ"])
    if level.startswith("JSS"): return deepcopy(ASSESSMENT_SCHEMES["JSS"])
    if level.startswith("SS"): return deepcopy(ASSESSMENT_SCHEMES["SS"])
    if level in MAIN_SCHOOL_CLASS_LEVELS: return deepcopy(ASSESSMENT_SCHEMES["LOWER_SCHOOL"])
    return {}

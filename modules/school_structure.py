# MODULE: School Structure — canonical EMIS school sections, configured classes, Islamiyah classes and assessment schemes

from copy import deepcopy


# ============================================================
# CURRENT / FUTURE DATABASE ACTIVATION
# ============================================================

ACTIVE_DATABASE_CLASSES = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]

REGULAR_CLASS_LEVELS = [
    "STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2",
    "TAHFEEZ1", "TAHFEEZ2", "TAHFEEZ3", "TAHFEEZ4", "TAHFEEZ5",
    "PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6",
    "JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3",
]

PENDING_DATABASE_CLASSES = [level for level in REGULAR_CLASS_LEVELS if level not in ACTIVE_DATABASE_CLASSES]

ISLAMIYAH_CLASS_LEVELS = [
    "ISLAMIYAH_STARTER", "ISLAMIYAH_PREP1", "ISLAMIYAH1", "ISLAMIYAH2", "ISLAMIYAH3",
    "ISLAMIYAH4", "ISLAMIYAH5", "ISLAMIYAH6", "ISLAMIYAH7",
]

ALL_CONFIGURED_CLASSES = list(REGULAR_CLASS_LEVELS) + list(ISLAMIYAH_CLASS_LEVELS)


# ============================================================
# SCHOOL SECTIONS
# ============================================================

SCHOOL_SECTION_ORDER = ["EARLY_YEARS", "TAHFEEZ", "PRIMARY", "JUNIOR_SECONDARY", "SENIOR_SECONDARY", "ISLAMIYAH"]

SCHOOL_SECTIONS = {
    "EARLY_YEARS": {"label": "Early Years / Nursery", "short_label": "Early Years", "classes": ["STARTER", "PRE_CLASS", "NURSERY1", "NURSERY2"]},
    "TAHFEEZ": {"label": "Tahfeez", "short_label": "Tahfeez", "classes": ["TAHFEEZ1", "TAHFEEZ2", "TAHFEEZ3", "TAHFEEZ4", "TAHFEEZ5"]},
    "PRIMARY": {"label": "Primary School", "short_label": "Primary", "classes": ["PRIMARY1", "PRIMARY2", "PRIMARY3", "PRIMARY4", "PRIMARY5", "PRIMARY6"]},
    "JUNIOR_SECONDARY": {"label": "Junior Secondary School", "short_label": "JSS", "classes": ["JSS1", "JSS2", "JSS3"]},
    "SENIOR_SECONDARY": {"label": "Senior Secondary School", "short_label": "SS", "classes": ["SS1", "SS2", "SS3"]},
    "ISLAMIYAH": {"label": "Islamiyah School", "short_label": "Islamiyah", "classes": list(ISLAMIYAH_CLASS_LEVELS)},
}

CLASS_LABELS = {
    "STARTER": "Starter", "PRE_CLASS": "Pre-Class", "NURSERY1": "Nursery 1", "NURSERY2": "Nursery 2",
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

EARLY_YEARS_SUBJECTS = {
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

ISLAMIYAH_SUBJECTS = {
    "ISLAMIYAH_STARTER": ["Quran", "Hadith", "Arabiyah", "Arqaam", "Huruf"],
    "ISLAMIYAH_PREP1": ["Quran", "Hadith", "Fiqh", "Tawheed", "Murtala", "Arabiyah", "Hisab", "Azkhar"],
    "ISLAMIYAH1": ["Quran", "Hadith", "Fiqh", "Tawheed", "Huruf"], "ISLAMIYAH2": ["Quran", "Hadith", "Fiqh", "Tawheed", "Huruf"], "ISLAMIYAH3": ["Quran", "Hadith", "Fiqh", "Tawheed", "Huruf"],
    "ISLAMIYAH4": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"], "ISLAMIYAH5": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"],
    "ISLAMIYAH6": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"], "ISLAMIYAH7": ["Quran", "Hadith", "Fiqh", "Tawheed", "Sirah", "Tajweed"],
}

SOURCE_NOTES = {
    "TAHFEEZ3_5_ARABIC_DUPLICATE": "The supplied school subject document lists Arabic twice for Tahfeez 3-5. The canonical runtime list stores Arabic once; the source discrepancy remains recorded for confirmation.",
    "HAUSA_YORUBA_SPLIT": "The supplied school document uses Hausa/Yoruba as a combined entry in Primary and Tahfeez 3-5. Phase 2 stores Hausa Language and Yoruba Language separately so each pupil can take the applicable language.",
    "ISLAMIYAH_INDEPENDENT_CLASSIFICATION": "A student's regular class and Islamiyah class are independent. Example: JSS2 + Islamiyah 5. No fixed regular-class to Islamiyah-level mapping is assumed.",
    "PRIMARY_DATABASE_PENDING": "Primary/Nursery/Tahfeez student databases are not active yet. Their class/subject configuration is available before roster activation.",
}


# ============================================================
# ASSESSMENT SCHEMES
# ============================================================

ASSESSMENT_SCHEMES = {
    "JSS": {"label": "Junior Secondary", "ca_max": 60, "exam_max": 40, "total_max": 100, "fields": {"CA1": 10, "CA2": 10, "TEST1": 20, "TEST2": 20}},
    "SS": {"label": "Senior Secondary", "ca_max": 30, "exam_max": 70, "total_max": 100, "fields": {"ASS1": 5, "ASS2": 5, "TEST": 20}},
    "ISLAMIYAH": {"label": "Islamiyah", "ca_max": 30, "exam_max": 70, "total_max": 100, "fields": {"CA": 30, "EXAM": 70}},
}


# ============================================================
# NORMALIZATION / LOOKUP
# ============================================================

_CLASS_ALIASES = {
    "STARTER": "STARTER", "STARTERS": "STARTER", "PRE": "PRE_CLASS", "PRECLASS": "PRE_CLASS", "PRE CLASS": "PRE_CLASS", "PRE_CLASS": "PRE_CLASS", "PRE-CLASS": "PRE_CLASS",
    "NURSERY1": "NURSERY1", "NURSERY 1": "NURSERY1", "NURSERY2": "NURSERY2", "NURSERY 2": "NURSERY2",
    "PRIMARY1": "PRIMARY1", "PRIMARY 1": "PRIMARY1", "PRIMARY2": "PRIMARY2", "PRIMARY 2": "PRIMARY2", "PRIMARY3": "PRIMARY3", "PRIMARY 3": "PRIMARY3",
    "PRIMARY4": "PRIMARY4", "PRIMARY 4": "PRIMARY4", "PRIMARY5": "PRIMARY5", "PRIMARY 5": "PRIMARY5", "PRIMARY6": "PRIMARY6", "PRIMARY 6": "PRIMARY6",
    "TAHFEEZ1": "TAHFEEZ1", "TAHFEEZ 1": "TAHFEEZ1", "TAHFEEZ2": "TAHFEEZ2", "TAHFEEZ 2": "TAHFEEZ2", "TAHFEEZ3": "TAHFEEZ3", "TAHFEEZ 3": "TAHFEEZ3",
    "TAHFEEZ4": "TAHFEEZ4", "TAHFEEZ 4": "TAHFEEZ4", "TAHFEEZ5": "TAHFEEZ5", "TAHFEEZ 5": "TAHFEEZ5",
}

for _level in ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"] + ISLAMIYAH_CLASS_LEVELS: _CLASS_ALIASES[_level] = _level
for _number in range(1, 8): _CLASS_ALIASES[f"ISLAMIYAH {_number}"] = f"ISLAMIYAH{_number}"
_CLASS_ALIASES.update({"ISLAMIYAH STARTER": "ISLAMIYAH_STARTER", "ISLAMIYAH STARTERS": "ISLAMIYAH_STARTER", "ISLAMIYAH PREP": "ISLAMIYAH_PREP1", "ISLAMIYAH PREP1": "ISLAMIYAH_PREP1", "ISLAMIYAH PREP 1": "ISLAMIYAH_PREP1", "ISLAMIYAH PREP-1": "ISLAMIYAH_PREP1"})


def normalize_school_class(value):
    raw = " ".join(str(value or "").upper().strip().replace("_", " ").split())
    if not raw: return ""
    compact = raw.replace(" ", "")
    return _CLASS_ALIASES.get(raw) or _CLASS_ALIASES.get(compact) or ""


def class_label(value):
    level = normalize_school_class(value)
    return CLASS_LABELS.get(level, str(value or "").strip())


def is_islamiyah_class(value): return normalize_school_class(value) in ISLAMIYAH_CLASS_LEVELS

def is_regular_class(value): return normalize_school_class(value) in REGULAR_CLASS_LEVELS

def database_is_active_for_class(value): return normalize_school_class(value) in ACTIVE_DATABASE_CLASSES


def school_section_for_class(value):
    level = normalize_school_class(value)
    for section in SCHOOL_SECTION_ORDER:
        if level in SCHOOL_SECTIONS.get(section, {}).get("classes", []): return section
    return ""


def get_school_classes(section="", include_islamiyah=True):
    section = str(section or "").upper().strip()
    if section and section in SCHOOL_SECTIONS: return list(SCHOOL_SECTIONS[section]["classes"])
    classes = list(REGULAR_CLASS_LEVELS)
    if include_islamiyah: classes.extend(ISLAMIYAH_CLASS_LEVELS)
    return classes


def get_class_metadata(class_level):
    level = normalize_school_class(class_level)
    if not level: return {}
    section = school_section_for_class(level); section_info = SCHOOL_SECTIONS.get(section, {})
    return {
        "key": level, "label": CLASS_LABELS.get(level, level), "section": section, "section_label": section_info.get("label", section.title()),
        "is_islamiyah": level in ISLAMIYAH_CLASS_LEVELS, "database_active": level in ACTIVE_DATABASE_CLASSES, "database_status": "active" if level in ACTIVE_DATABASE_CLASSES else "pending",
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
    if level in ISLAMIYAH_SUBJECTS: return list(ISLAMIYAH_SUBJECTS[level])
    return []


def get_assessment_scheme(class_level="", school="REGULAR"):
    if str(school or "").upper().strip() == "ISLAMIYAH" or is_islamiyah_class(class_level): return deepcopy(ASSESSMENT_SCHEMES["ISLAMIYAH"])
    level = normalize_school_class(class_level) or str(class_level or "").upper().strip()
    if level.startswith("JSS"): return deepcopy(ASSESSMENT_SCHEMES["JSS"])
    if level.startswith("SS"): return deepcopy(ASSESSMENT_SCHEMES["SS"])
    return {}

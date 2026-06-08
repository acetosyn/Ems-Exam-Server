# modules/class_config.py

SUPPORTED_CLASSES = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]

CLASS_ARMS_BY_LEVEL = {
    "JSS1": ["JSS1A", "JSS1B", "JSS1C"],
    "JSS2": ["JSS2A", "JSS2B", "JSS2C"],
    "JSS3": ["JSS3A", "JSS3B", "JSS3C"],
    "SS1": ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1B"],
    "SS2": ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2B"],
    "SS3": ["SS3_GOLD", "SS3_SILVER", "SS3_DIAMOND", "SS3B"],
}

CLASS_ARMS = CLASS_ARMS_BY_LEVEL

STUDENT_CSV_FILES = {
    "JSS1": "static/data/JSS1_Students.csv",
    "JSS2": "static/data/JSS2_Students.csv",
    "JSS3": "static/data/JSS3_Students.csv",
    "SS1": "static/data/SS1_Students.csv",
    "SS2": "static/data/SS2_Students.csv",
    "SS3": "static/data/SS3_Students.csv",
}

SUBJECT_JSON_ROOT = "static/subjects"
PORTAL_ROOT = "static/portal"
RESULTS_ROOT = "RESULTS"

COMMON_FULL_SCHOOL_SUBJECTS = ["Poise", "Islamiyyah"]


# =========================================================
# SUBJECT NORMALIZATION HELPERS
# Must come before subject lists are rebuilt.
# =========================================================
def normalize_subject_key(subject):
    value = str(subject or "").upper().strip()
    value = value.replace(".", "")
    value = value.replace("&", "AND")
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
        "P.H.E": "PHE",

        # Heritage / Citizenship aliases
        "HERITAGE AND CITIZENSHIP STUDIES": "CIT AND HER STD",
        "HERITAGE CITIZENSHIP STUDIES": "CIT AND HER STD",
        "CITIZENSHIP AND HERITAGE STUDIES": "CIT AND HER STD",
        "CIT AND HER STD": "CIT AND HER STD",
        "CIT HER STD": "CIT AND HER STD",

        # Social & Citizenship aliases
        "SOC AND CIT STD": "SOC AND CIT STD",
        "SOCIAL AND CITIZENSHIP STUDIES": "SOC AND CIT STD",

        # Digital Technology aliases
        "DIGITAL TECH": "DIGITAL TECH",
        "DIGITAL TECHNOLOGY": "DIGITAL TECH",

        # Horticulture aliases
        "HORTICULTURE AND CROP PRODUCTION": "HORT AND CROP PRODUCTION",

        # Garment aliases
        "GARMENT MAKING": "GARMENT MAKING",
    }

    return aliases.get(value, value)


def normalize_subject_display(subject):
    key = normalize_subject_key(subject)

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

        # Heritage/Citizenship
        "HERITAGE AND CITIZENSHIP STUDIES": "Heritage & Citizenship Studies",
        "HCS": "Heritage & Citizenship Studies",
        "CIT AND HER STD": "Cit & Her. Std",

        # Social/Citizenship
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
    seen = set()
    output = []

    for subject in subjects:
        subject = str(subject or "").strip()

        if not subject:
            continue

        key = normalize_subject_key(subject)

        if key in seen:
            continue

        seen.add(key)
        output.append(normalize_subject_display(subject))

    return output


# =========================================================
# RAW SUBJECT LISTS
# =========================================================
JSS_SUBJECTS_RAW = [
    "Mathematics",
    "English Language",
    "IRK",
    "Islamiyyah",
    "Poise",
    "Heritage & Citizenship Studies",
    "National Value",
    "Yoruba Language",
    "Hausa Language",
    "Arabic Language",
    "CCA",
    "Business Studies",
    "History",
    "BST",
    "P.H.E",
    "PVS",
    "Hort & Crop Production",
    "Digital Tech.",
    "Inter Science",
    "Garment Making",
]

SS_SCIENCE_SUBJECTS_BY_LEVEL_RAW = {
    "SS1": [
        "Mathematics",
        "English Language",
        "Chemistry",
        "Physics",
        "Biology",
        "Technical Drawing",
        "IRS",
        "Computer Science",
        "Further Mathematics",
        "Agricultural Science",
        "Civic Education",
        "Geography",
        "Economics",
        "Digital Tech.",
        "Cit & Her. Std",
        "Garment Making",
        "Poise",
        "Islamiyyah",
    ],
    "SS2": [
        "Mathematics",
        "English Language",
        "Chemistry",
        "Physics",
        "Biology",
        "Technical Drawing",
        "IRS",
        "Computer Science",
        "Further Mathematics",
        "Agricultural Science",
        "Civic Education",
        "Geography",
        "Economics",
        "Poise",
        "Islamiyyah",
    ],
    "SS3": [
        "Mathematics",
        "English Language",
        "Chemistry",
        "Physics",
        "Biology",
        "Further Mathematics",
        "Agricultural Science",
        "Civic Education",
        "Economics",
        "Poise",
        "Islamiyyah",
    ],
}

SS_ART_SUBJECTS_BY_LEVEL_RAW = {
    "SS1": [
        "Mathematics",
        "English Language",
        "Literature",
        "Government",
        "IRS",
        "Hausa Language",
        "Yoruba Language",
        "Arabic Language",
        "Civic Education",
        "Marketing",
        "Poise",
        "Islamiyyah",
    ],
    "SS2": [
        "Mathematics",
        "English Language",
        "Literature",
        "Government",
        "IRS",
        "Hausa Language",
        "Yoruba Language",
        "Arabic Language",
        "Civic Education",
        "Marketing",
        "Poise",
        "Islamiyyah",
    ],
    "SS3": [
        "Mathematics",
        "English Language",
        "Literature",
        "Government",
        "Hausa Language",
        "Yoruba Language",
        "Arabic Language",
        "Civic Education",
        "Marketing",
        "Poise",
        "Islamiyyah",
    ],
}

SS_COMMERCIAL_SUBJECTS_BY_LEVEL_RAW = {
    "SS1": [
        "Mathematics",
        "English Language",
        "Economics",
        "Financial Account",
        "Civic Education",
        "Marketing",
        "Commerce",
        "Poise",
        "Islamiyyah",
    ],
    "SS2": [
        "Mathematics",
        "English Language",
        "Economics",
        "Financial Account",
        "Civic Education",
        "Marketing",
        "Commerce",
        "Poise",
        "Islamiyyah",
    ],
    "SS3": [
        "Mathematics",
        "English Language",
        "Civic Education",
        "Economics",
        "Marketing",
        "Government",
        "Commerce",
        "Financial Account",
        "Poise",
        "Islamiyyah",
    ],
}


# =========================================================
# CLEANED SUBJECT LISTS
# =========================================================
JSS_SUBJECTS = unique_ordered(JSS_SUBJECTS_RAW)

SS_SCIENCE_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects)
    for level, subjects in SS_SCIENCE_SUBJECTS_BY_LEVEL_RAW.items()
}

SS_ART_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects)
    for level, subjects in SS_ART_SUBJECTS_BY_LEVEL_RAW.items()
}

SS_COMMERCIAL_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects)
    for level, subjects in SS_COMMERCIAL_SUBJECTS_BY_LEVEL_RAW.items()
}

SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(
        SS_ART_SUBJECTS_BY_LEVEL.get(level, [])
        + SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, [])
    )
    for level in ["SS1", "SS2", "SS3"]
}

CLASS_SUBJECTS = {
    "JSS1": JSS_SUBJECTS,
    "JSS2": JSS_SUBJECTS,
    "JSS3": JSS_SUBJECTS,

    # Broad SS remains combined only for admin/general views.
    # Student portal should always pass class_arm to get the strict track list.
    "SS1": unique_ordered(
        SS_SCIENCE_SUBJECTS_BY_LEVEL["SS1"]
        + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS1"]
    ),
    "SS2": unique_ordered(
        SS_SCIENCE_SUBJECTS_BY_LEVEL["SS2"]
        + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS2"]
    ),
    "SS3": unique_ordered(
        SS_SCIENCE_SUBJECTS_BY_LEVEL["SS3"]
        + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS3"]
    ),
}


# =========================================================
# CLASS HELPERS
# =========================================================
def normalize_class_level(value):
    value = str(value or "").upper().strip()
    value = value.replace("-", "_")
    compact = value.replace(" ", "").replace("_", "")

    for level in SUPPORTED_CLASSES:
        if compact == level or compact.startswith(level):
            return level

    return ""


def normalize_class_arm(value, fallback_level=""):
    raw = str(value or "").upper().strip()
    raw = raw.replace("-", "_")
    compact = raw.replace(" ", "").replace("_", "")

    level = (
        normalize_class_level(raw)
        or normalize_class_level(compact)
        or normalize_class_level(fallback_level)
    )

    if not level:
        return ""

    if level.startswith("JSS"):
        for arm in ["A", "B", "C"]:
            if compact == f"{level}{arm}":
                return f"{level}{arm}"
        return level

    for label in ["GOLD", "SILVER", "DIAMOND"]:
        if label in compact:
            return f"{level}_{label}"

    if compact == f"{level}B":
        return f"{level}B"

    return level


def get_ss_stream(class_arm):
    arm = normalize_class_arm(class_arm)

    if not arm.startswith("SS"):
        return ""

    if arm.endswith("B"):
        return "ART_COMMERCIAL"

    if any(label in arm for label in ["GOLD", "SILVER", "DIAMOND"]):
        return "SCIENCE"

    return "GENERAL"


def get_ss_track(class_arm, preferred_track=""):
    """
    Returns exact SS track:
    SCIENCE / ART / COMMERCIAL / ART_COMMERCIAL / GENERAL
    """
    arm = normalize_class_arm(class_arm)
    preferred = str(preferred_track or "").upper().strip()

    if preferred in ["ART", "COMMERCIAL", "ART_COMMERCIAL", "SCIENCE"]:
        return preferred

    if not arm.startswith("SS"):
        return ""

    if arm.endswith("B"):
        return "ART_COMMERCIAL"

    if any(label in arm for label in ["GOLD", "SILVER", "DIAMOND"]):
        return "SCIENCE"

    return "GENERAL"


def unique_subjects(subjects):
    return unique_ordered(subjects)


def get_subjects_for_class(class_category, class_arm=None, preferred_track=""):
    level = normalize_class_level(class_category)
    arm = normalize_class_arm(class_arm or class_category, level)

    if not level:
        return []

    if level.startswith("JSS"):
        return unique_ordered(JSS_SUBJECTS)

    track = get_ss_track(arm, preferred_track)

    if track == "SCIENCE":
        return unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL.get(level, []))

    if track == "ART":
        return unique_ordered(SS_ART_SUBJECTS_BY_LEVEL.get(level, []))

    if track == "COMMERCIAL":
        return unique_ordered(SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, []))

    if track == "ART_COMMERCIAL":
        return unique_ordered(SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, []))

    return unique_ordered(CLASS_SUBJECTS.get(level, []))


def is_valid_class(class_category):
    return bool(normalize_class_level(class_category))


def is_valid_class_arm(class_arm):
    arm = normalize_class_arm(class_arm)
    level = normalize_class_level(arm)

    if not level:
        return False

    if arm == level:
        return True

    return arm in CLASS_ARMS_BY_LEVEL.get(level, [])
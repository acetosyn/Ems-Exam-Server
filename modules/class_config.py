# modules/class_config.py

# =========================================================
# CORE CLASS CONFIGURATION
# =========================================================

SUPPORTED_CLASSES = [
    "JSS1",
    "JSS2",
    "JSS3",
    "SS1",
    "SS2",
    "SS3",
]


# =========================================================
# CLASS ARMS / CATEGORIES
#
# Canonical senior B/C format:
#   SS1_B/C
#   SS2_B/C
#   SS3_B/C
#
# Old forms such as SS1B, SS1_B, SS1BC, SS1B&C, etc.
# are normalized automatically by normalize_class_arm().
# =========================================================

CLASS_ARMS_BY_LEVEL = {
    "JSS1": [
        "JSS1A",
        "JSS1B",
        "JSS1C",
    ],

    "JSS2": [
        "JSS2A",
        "JSS2B",
        "JSS2C",
    ],

    "JSS3": [
        "JSS3A",
        "JSS3B",
        "JSS3C",
    ],

    "SS1": [
        "SS1_GOLD",
        "SS1_SILVER",
        "SS1_DIAMOND",
        "SS1_B/C",
    ],

    "SS2": [
        "SS2_GOLD",
        "SS2_SILVER",
        "SS2_DIAMOND",
        "SS2_B/C",
    ],

    # Current SS3 has no Diamond arm.
    "SS3": [
        "SS3_GOLD",
        "SS3_SILVER",
        "SS3_B/C",
    ],
}


# Backward-compatible alias used elsewhere in the application.
CLASS_ARMS = CLASS_ARMS_BY_LEVEL


# =========================================================
# STUDENT DATABASE
# =========================================================

# Single authoritative student database for the whole school.
STUDENT_CSV_FILE = "static/data/database/students2026.csv"


# Backward compatibility:
# Older modules may still do:
#
#     STUDENT_CSV_FILES["JSS1"]
#
# Instead of breaking those modules immediately, every level
# now points to the same master database.
STUDENT_CSV_FILES = {
    level: STUDENT_CSV_FILE
    for level in SUPPORTED_CLASSES
}


# =========================================================
# APPLICATION PATHS
# =========================================================

SUBJECT_JSON_ROOT = "static/subjects"
PORTAL_ROOT = "static/portal"
RESULTS_ROOT = "RESULTS"

COMMON_FULL_SCHOOL_SUBJECTS = [
    "Poise",
    "Islamiyyah",
]


# =========================================================
# SUBJECT NORMALIZATION HELPERS
# Must come before subject lists are rebuilt.
# =========================================================

def normalize_subject_key(subject):
    value = str(subject or "").upper().strip()

    value = value.replace(".", "")
    value = value.replace("&", "AND")

    value = " ".join(
        value
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )

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
        "HORTICULTURE AND CROP PRODUCTION":
            "HORT AND CROP PRODUCTION",

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

        # Heritage / Citizenship
        "HERITAGE AND CITIZENSHIP STUDIES":
            "Heritage & Citizenship Studies",

        "HCS":
            "Heritage & Citizenship Studies",

        "CIT AND HER STD":
            "Cit & Her. Std",

        # Social / Citizenship
        "SOC AND CIT STD":
            "Soc. & Cit. Std",

        "NATIONAL VALUE":
            "National Value",

        "CCA":
            "CCA",

        "BUSINESS STUDIES":
            "Business Studies",

        "HISTORY":
            "History",

        "BST":
            "BST",

        "PHE":
            "P.H.E",

        "PVS":
            "PVS",

        "HORT AND CROP PRODUCTION":
            "Hort & Crop Production",

        "DIGITAL TECH":
            "Digital Tech.",

        "DIGITAL TECHNOLOGY":
            "Digital Tech.",

        "INTER SCIENCE":
            "Inter Science",

        "GARMENT MAKING":
            "Garment Making",
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
        output.append(
            normalize_subject_display(subject)
        )

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

JSS_SUBJECTS = unique_ordered(
    JSS_SUBJECTS_RAW
)


SS_SCIENCE_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects)
    for level, subjects
    in SS_SCIENCE_SUBJECTS_BY_LEVEL_RAW.items()
}


SS_ART_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects)
    for level, subjects
    in SS_ART_SUBJECTS_BY_LEVEL_RAW.items()
}


SS_COMMERCIAL_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(subjects)
    for level, subjects
    in SS_COMMERCIAL_SUBJECTS_BY_LEVEL_RAW.items()
}


SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL = {
    level: unique_ordered(
        SS_ART_SUBJECTS_BY_LEVEL.get(level, [])
        +
        SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, [])
    )
    for level in [
        "SS1",
        "SS2",
        "SS3",
    ]
}


CLASS_SUBJECTS = {
    "JSS1": JSS_SUBJECTS,
    "JSS2": JSS_SUBJECTS,
    "JSS3": JSS_SUBJECTS,

    # Broad senior-school views.
    #
    # The student portal should pass the student's actual
    # Class value to get_subjects_for_class() so that the
    # correct stream is selected.
    "SS1": unique_ordered(
        SS_SCIENCE_SUBJECTS_BY_LEVEL["SS1"]
        +
        SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS1"]
    ),

    "SS2": unique_ordered(
        SS_SCIENCE_SUBJECTS_BY_LEVEL["SS2"]
        +
        SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS2"]
    ),

    "SS3": unique_ordered(
        SS_SCIENCE_SUBJECTS_BY_LEVEL["SS3"]
        +
        SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS3"]
    ),
}


# =========================================================
# CLASS NORMALIZATION HELPERS
# =========================================================

def normalize_class_level(value):
    """
    Convert any supported class/arm value to its broad level.

    Examples:
        JSS1A       -> JSS1
        JSS2C       -> JSS2
        SS1_GOLD    -> SS1
        SS1_B/C     -> SS1
        SS2B&C      -> SS2
        SS3BC       -> SS3
    """

    value = str(value or "").upper().strip()

    if not value:
        return ""

    compact = (
        value
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
        .replace("&", "")
    )

    # Check longer/more specific prefixes first.
    for level in SUPPORTED_CLASSES:
        if compact == level:
            return level

        if compact.startswith(level):
            return level

    return ""


def normalize_class_arm(value, fallback_level=""):
    """
    Return the application's canonical class-arm representation.

    JSS:
        JSS1A
        JSS1B
        JSS1C
        JSS2A
        ...
        JSS3C

    Senior school:
        SS1_GOLD
        SS1_SILVER
        SS1_DIAMOND
        SS1_B/C

        SS2_GOLD
        SS2_SILVER
        SS2_DIAMOND
        SS2_B/C

        SS3_GOLD
        SS3_SILVER
        SS3_B/C

    Legacy B aliases accepted include:
        SS1B
        SS1_B
        SS1BC
        SS1_BC
        SS1B/C
        SS1_B/C
        SS1B&C
        SS1_B&C

    They all normalize to:
        SS1_B/C

    Same logic applies to SS2 and SS3.
    """

    raw = str(value or "").upper().strip()

    if not raw:
        raw = str(fallback_level or "").upper().strip()

    if not raw:
        return ""

    # Preserve useful semantic characters for alias detection.
    cleaned = (
        raw
        .replace("-", "_")
        .replace(" ", "")
    )

    compact = (
        cleaned
        .replace("_", "")
        .replace("/", "")
        .replace("&", "")
    )

    level = (
        normalize_class_level(raw)
        or
        normalize_class_level(fallback_level)
    )

    if not level:
        return ""

    # -----------------------------------------------------
    # JSS ARMS
    # -----------------------------------------------------
    if level.startswith("JSS"):

        for arm in ["A", "B", "C"]:
            if compact == f"{level}{arm}":
                return f"{level}{arm}"

        # Broad JSS level.
        if compact == level:
            return level

        return level

    # -----------------------------------------------------
    # SENIOR SCHOOL SCIENCE ARMS
    # -----------------------------------------------------
    if "GOLD" in compact:
        return f"{level}_GOLD"

    if "SILVER" in compact:
        return f"{level}_SILVER"

    if "DIAMOND" in compact:
        # SS3 currently has no Diamond arm.
        # Normalize the value anyway, then validation can reject it.
        return f"{level}_DIAMOND"

    # -----------------------------------------------------
    # SENIOR SCHOOL B/C ARM
    # -----------------------------------------------------
    #
    # Canonical:
    #     SS1_B/C
    #
    # Accepted aliases:
    #     SS1B
    #     SS1_B
    #     SS1BC
    #     SS1_BC
    #     SS1B/C
    #     SS1_B/C
    #     SS1B&C
    #     SS1_B&C
    #
    # Also permits old SSB-style naming when the level
    # is supplied separately as fallback_level.
    # -----------------------------------------------------

    suffix = compact[len(level):]

    if suffix in {
        "B",
        "BC",
    }:
        return f"{level}_B/C"

    # Explicit textual variations that may survive the
    # compact transformation.
    raw_no_space = (
        raw
        .replace(" ", "")
        .replace("-", "_")
    )

    bc_aliases = {
        f"{level}B",
        f"{level}_B",

        f"{level}BC",
        f"{level}_BC",

        f"{level}B/C",
        f"{level}_B/C",

        f"{level}B&C",
        f"{level}_B&C",
    }

    if raw_no_space in bc_aliases:
        return f"{level}_B/C"

    # Broad senior level.
    if compact == level:
        return level

    return level


def get_class_level_from_arm(class_arm):
    """
    Convenience helper for retrieving the broad class level
    from a normalized or unnormalized class arm.
    """

    return normalize_class_level(
        class_arm
    )


# =========================================================
# SENIOR SCHOOL STREAM HELPERS
# =========================================================

def get_ss_stream(class_arm):
    """
    Returns broad senior-school stream:

        SCIENCE
        ART_COMMERCIAL
        GENERAL
    """

    arm = normalize_class_arm(
        class_arm
    )

    if not arm.startswith("SS"):
        return ""

    if arm.endswith("_B/C"):
        return "ART_COMMERCIAL"

    if any(
        label in arm
        for label in [
            "_GOLD",
            "_SILVER",
            "_DIAMOND",
        ]
    ):
        return "SCIENCE"

    return "GENERAL"


def get_ss_track(
    class_arm,
    preferred_track="",
):
    """
    Returns exact SS track:

        SCIENCE
        ART
        COMMERCIAL
        ART_COMMERCIAL
        GENERAL
    """

    arm = normalize_class_arm(
        class_arm
    )

    preferred = (
        str(preferred_track or "")
        .upper()
        .strip()
    )

    if preferred in {
        "ART",
        "COMMERCIAL",
        "ART_COMMERCIAL",
        "SCIENCE",
    }:
        return preferred

    if not arm.startswith("SS"):
        return ""

    # B/C is the combined Arts / Commercial arm.
    if arm.endswith("_B/C"):
        return "ART_COMMERCIAL"

    # Gold / Silver / Diamond are treated as Science arms
    # under the current EMIS configuration.
    if any(
        label in arm
        for label in [
            "_GOLD",
            "_SILVER",
            "_DIAMOND",
        ]
    ):
        return "SCIENCE"

    return "GENERAL"


# =========================================================
# SUBJECT LOOKUP HELPERS
# =========================================================

def unique_subjects(subjects):
    return unique_ordered(
        subjects
    )


def get_subjects_for_class(
    class_category,
    class_arm=None,
    preferred_track="",
):
    """
    Get the appropriate subject list for a student/class.

    Examples:

        get_subjects_for_class(
            "JSS1",
            "JSS1A",
        )

        get_subjects_for_class(
            "SS1",
            "SS1_GOLD",
        )

        get_subjects_for_class(
            "SS1",
            "SS1_B/C",
        )
    """

    level = normalize_class_level(
        class_category
    )

    arm = normalize_class_arm(
        class_arm or class_category,
        level,
    )

    if not level:
        return []

    # -----------------------------------------------------
    # JUNIOR SCHOOL
    # -----------------------------------------------------
    if level.startswith("JSS"):
        return unique_ordered(
            JSS_SUBJECTS
        )

    # -----------------------------------------------------
    # SENIOR SCHOOL
    # -----------------------------------------------------
    track = get_ss_track(
        arm,
        preferred_track,
    )

    if track == "SCIENCE":
        return unique_ordered(
            SS_SCIENCE_SUBJECTS_BY_LEVEL
            .get(level, [])
        )

    if track == "ART":
        return unique_ordered(
            SS_ART_SUBJECTS_BY_LEVEL
            .get(level, [])
        )

    if track == "COMMERCIAL":
        return unique_ordered(
            SS_COMMERCIAL_SUBJECTS_BY_LEVEL
            .get(level, [])
        )

    if track == "ART_COMMERCIAL":
        return unique_ordered(
            SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL
            .get(level, [])
        )

    return unique_ordered(
        CLASS_SUBJECTS.get(
            level,
            [],
        )
    )


# =========================================================
# CLASS VALIDATION HELPERS
# =========================================================

def is_valid_class(class_category):
    """
    Validate a broad class level.

    Valid:
        JSS1
        JSS2
        JSS3
        SS1
        SS2
        SS3
    """

    level = normalize_class_level(
        class_category
    )

    return level in SUPPORTED_CLASSES


def is_valid_class_arm(class_arm):
    """
    Validate a full class arm.

    Examples:
        JSS1A       -> True
        SS1_GOLD    -> True
        SS1_B/C     -> True

        SS1B        -> True
            because it normalizes to SS1_B/C

        SS3_DIAMOND -> False
            because SS3 currently has no Diamond arm
    """

    arm = normalize_class_arm(
        class_arm
    )

    level = normalize_class_level(
        arm
    )

    if not level:
        return False

    # Allow broad class categories.
    if arm == level:
        return True

    return (
        arm
        in CLASS_ARMS_BY_LEVEL.get(
            level,
            [],
        )
    )


# =========================================================
# STUDENT DATABASE HELPERS
# =========================================================

def get_student_csv_file(
    class_category=None,
):
    """
    Return the single authoritative student CSV.

    class_category is intentionally accepted for backwards
    compatibility, but all classes now use the same master file.
    """

    return STUDENT_CSV_FILE


def get_class_arms(
    class_category,
):
    """
    Return the configured arms for a class level.

    Example:

        get_class_arms("SS1")

    Returns:
        [
            "SS1_GOLD",
            "SS1_SILVER",
            "SS1_DIAMOND",
            "SS1_B/C",
        ]
    """

    level = normalize_class_level(
        class_category
    )

    if not level:
        return []

    return list(
        CLASS_ARMS_BY_LEVEL.get(
            level,
            [],
        )
    )
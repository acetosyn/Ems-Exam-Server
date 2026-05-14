# modules/class_config.py

SUPPORTED_CLASSES = [
    "JSS1",
    "JSS2",
    "JSS3",
    "SS1",
    "SS2",
    "SS3"
]


# =========================================================
# STUDENT CSV DATABASE FILES
# =========================================================
STUDENT_CSV_FILES = {
    "JSS1": "static/data/JSS1_Students.csv",
    "JSS2": "static/data/JSS2_Students.csv",
    "JSS3": "static/data/JSS3_Students.csv",

    "SS1": "static/data/SS1_Students.csv",
    "SS2": "static/data/SS2_Students.csv",
    "SS3": "static/data/SS3_Students.csv",
}


# =========================================================
# SYSTEM ROOT FOLDERS
# =========================================================
SUBJECT_JSON_ROOT = "static/subjects"
PORTAL_ROOT = "static/portal"
RESULTS_ROOT = "RESULTS"


# =========================================================
# SUBJECTS OFFERED PER CLASS
# =========================================================
CLASS_SUBJECTS = {

    # =====================================================
    # JSS1
    # =====================================================
    "JSS1": [
        "Yoruba Language",
        "History",
        "IRK",
        "CCA",
        "Arabic Language",
        "Business Studies",
        "Mathematics",
        "English Language",
        "Poise",
        "Islamiyyah",
        "Hort & Crop Production",
        "Digital Tech.",
        "Inter Science",
        "Garment Making",
        "Soc. & Cit. Std",
        "P.H.E",
    ],

    # =====================================================
    # JSS2
    # =====================================================
    "JSS2": [
        "Yoruba Language",
        "History",
        "IRK",
        "CCA",
        "Arabic Language",
        "Business Studies",
        "Mathematics",
        "English Language",
        "BST",
        "National Value",
        "PVS",
        "Poise",
        "Islamiyyah",
    ],

    # =====================================================
    # JSS3
    # =====================================================
    "JSS3": [
        "History",
        "IRK",
        "Hausa Language",
        "CCA",
        "Arabic Language",
        "Business Studies",
        "Mathematics",
        "English Language",
        "BST",
        "National Value",
        "PVS",
        "Poise",
        "Islamiyyah",
    ],

    # =====================================================
    # SS1
    # =====================================================
    "SS1": [
        "Biology",
        "IRS",
        "Physics",
        "Geography",
        "Mathematics",
        "English Language",
        "Chemistry",
        "Poise",
        "Islamiyyah",
        "Digital Tech.",
        "Cit & Her. Std",
        "Garment Making",
    ],

    # =====================================================
    # SS2
    # =====================================================
    "SS2": [
        "Civic Education",
        "Mathematics",
        "English Language",
        "Economics",
        "Poise",
        "Islamiyyah",
        "Arabic Language",
        "IRS",
        "Commerce",
        "Financial Account",
        "Marketing",
        "Government",
    ],

    # =====================================================
    # SS3
    # =====================================================
    "SS3": [
        "Islamiyyah",
        "Poise",
        "Chemistry",
        "English Language",
        "Further Mathematics",
        "Mathematics",
        "Civic Education",
        "Physics",
        "Biology",
        "Agricultural Science",
        "Economics",
    ],
}


# =========================================================
# HELPER — GET SUBJECTS FOR A CLASS
# =========================================================
def get_subjects_for_class(class_category):
    """
    Returns subjects assigned to a class.
    Example:
        get_subjects_for_class("JSS1")
    """

    if not class_category:
        return []

    return CLASS_SUBJECTS.get(class_category.upper(), [])


# =========================================================
# HELPER — VALIDATE CLASS
# =========================================================
def is_valid_class(class_category):
    """
    Checks if class exists in supported classes.
    """

    if not class_category:
        return False

    return class_category.upper() in SUPPORTED_CLASSES
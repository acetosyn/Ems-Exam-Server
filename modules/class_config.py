# modules/class_config.py

# =========================================================
# CORE CLASS CONFIGURATION
# =========================================================

SUPPORTED_CLASSES = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]

CLASS_ARMS_BY_LEVEL = {
    "JSS1": ["JSS1A", "JSS1B", "JSS1C"],
    "JSS2": ["JSS2A", "JSS2B", "JSS2C"],
    "JSS3": ["JSS3A", "JSS3B", "JSS3C"],
    "SS1": ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1_B/C"],
    "SS2": ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2_B/C"],
    "SS3": ["SS3_GOLD", "SS3_SILVER", "SS3_B/C"],  # Current SS3 has no Diamond arm.
}

# Backward-compatible alias used by older modules.
CLASS_ARMS = CLASS_ARMS_BY_LEVEL


# =========================================================
# STUDENT DATABASE
# =========================================================

STUDENT_CSV_FILE = "static/data/database/students2026.csv"

# Backward compatibility: every class now points to the same master CSV.
STUDENT_CSV_FILES = {level: STUDENT_CSV_FILE for level in SUPPORTED_CLASSES}


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

JSS_SUBJECTS_RAW = [
    "Mathematics", "English Language", "IRK", "Islamiyyah", "Poise",
    "Heritage & Citizenship Studies", "National Value", "Yoruba Language",
    "Hausa Language", "Arabic Language", "CCA", "Business Studies", "History",
    "BST", "P.H.E", "PVS", "Hort & Crop Production", "Digital Tech.",
    "Inter Science", "Garment Making", "Soc. & Cit. Std",
]


SS_SCIENCE_SUBJECTS_BY_LEVEL_RAW = {
    "SS1": [
        "Mathematics", "English Language", "Chemistry", "Physics", "Biology",
        "Technical Drawing", "IRS", "Computer Science", "Further Mathematics",
        "Agricultural Science", "Civic Education", "Geography", "Economics",
        "Digital Tech.", "Cit & Her. Std", "Garment Making", "Poise", "Islamiyyah",
    ],

    "SS2": [
        "Mathematics", "English Language", "Chemistry", "Physics", "Biology",
        "Technical Drawing", "IRS", "Computer Science", "Further Mathematics",
        "Agricultural Science", "Civic Education", "Geography", "Economics",
        "Poise", "Islamiyyah",
    ],

    "SS3": [
        "Mathematics", "English Language", "Chemistry", "Physics", "Biology",
        "Further Mathematics", "Agricultural Science", "Civic Education",
        "Economics", "Poise", "Islamiyyah",
    ],
}


SS_ART_SUBJECTS_BY_LEVEL_RAW = {
    "SS1": [
        "Mathematics", "English Language", "Literature", "Government", "IRS",
        "Hausa Language", "Yoruba Language", "Arabic Language", "Civic Education",
        "Marketing", "Poise", "Islamiyyah",
    ],

    "SS2": [
        "Mathematics", "English Language", "Literature", "Government", "IRS",
        "Hausa Language", "Yoruba Language", "Arabic Language", "Civic Education",
        "Marketing", "Poise", "Islamiyyah",
    ],

    "SS3": [
        "Mathematics", "English Language", "Literature", "Government",
        "Hausa Language", "Yoruba Language", "Arabic Language", "Civic Education",
        "Marketing", "Poise", "Islamiyyah",
    ],
}


SS_COMMERCIAL_SUBJECTS_BY_LEVEL_RAW = {
    "SS1": [
        "Mathematics", "English Language", "Economics", "Financial Account",
        "Civic Education", "Marketing", "Commerce", "Poise", "Islamiyyah",
    ],

    "SS2": [
        "Mathematics", "English Language", "Economics", "Financial Account",
        "Civic Education", "Marketing", "Commerce", "Poise", "Islamiyyah",
    ],

    "SS3": [
        "Mathematics", "English Language", "Civic Education", "Economics",
        "Marketing", "Government", "Commerce", "Financial Account",
        "Poise", "Islamiyyah",
    ],
}


# =========================================================
# CLEANED SUBJECT LISTS
# =========================================================

JSS_SUBJECTS = unique_ordered(JSS_SUBJECTS_RAW)

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
    "JSS1": JSS_SUBJECTS,
    "JSS2": JSS_SUBJECTS,
    "JSS3": JSS_SUBJECTS,

    # Broad SS views contain every subject available to that level.
    "SS1": unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL["SS1"] + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS1"]),
    "SS2": unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL["SS2"] + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS2"]),
    "SS3": unique_ordered(SS_SCIENCE_SUBJECTS_BY_LEVEL["SS3"] + SS_ART_COMMERCIAL_SUBJECTS_BY_LEVEL["SS3"]),
}


# =========================================================
# CLASS NORMALIZATION
# =========================================================

def normalize_class_level(value):
    """
    Examples:
        JSS1A       -> JSS1
        JSS2C       -> JSS2
        SS1_GOLD    -> SS1
        SS1_B/C     -> SS1
        SS2B&C      -> SS2
        SS3BC       -> SS3
    """

    value = str(value or "").upper().strip()
    if not value: return ""

    compact = value.replace(" ", "").replace("_", "").replace("-", "").replace("/", "").replace("&", "")

    for level in SUPPORTED_CLASSES:
        if compact == level or compact.startswith(level): return level

    return ""


def normalize_class_arm(value, fallback_level=""):
    """
    Canonical senior arms:
        SS1_GOLD / SS1_SILVER / SS1_DIAMOND / SS1_B/C

    Legacy aliases such as SS1B, SS1_B, SS1BC, SS1B/C,
    SS1B&C etc. normalize to SS1_B/C.
    """

    raw = str(value or "").upper().strip() or str(fallback_level or "").upper().strip()
    if not raw: return ""

    cleaned = raw.replace("-", "_").replace(" ", "")
    compact = cleaned.replace("_", "").replace("/", "").replace("&", "")
    level = normalize_class_level(raw) or normalize_class_level(fallback_level)

    if not level: return ""

    # JSS arms.
    if level.startswith("JSS"):
        for arm in ["A", "B", "C"]:
            if compact == f"{level}{arm}": return f"{level}{arm}"
        return level

    # SS Science arms.
    if "GOLD" in compact: return f"{level}_GOLD"
    if "SILVER" in compact: return f"{level}_SILVER"
    if "DIAMOND" in compact: return f"{level}_DIAMOND"

    # SS combined Arts / Commercial B/C arm.
    suffix = compact[len(level):]
    if suffix in {"B", "BC"}: return f"{level}_B/C"

    raw_no_space = raw.replace(" ", "").replace("-", "_")
    bc_aliases = {
        f"{level}B", f"{level}_B", f"{level}BC", f"{level}_BC",
        f"{level}B/C", f"{level}_B/C", f"{level}B&C", f"{level}_B&C",
    }

    if raw_no_space in bc_aliases: return f"{level}_B/C"
    if compact == level: return level

    return level


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
    """Human-readable stream label used by promotion/student-placement UIs."""
    arm = normalize_class_arm(class_arm)
    level = normalize_class_level(arm)
    if not level: return ""
    if level.startswith("JSS"): return "Junior"
    stream = get_ss_stream(arm)
    if stream == "SCIENCE": return "Science"
    if stream == "ART_COMMERCIAL": return "Arts / Commercial"
    return "General"


def get_class_arm_metadata(class_arm):
    """Small normalized metadata object for UI labels and movement warnings."""
    arm = normalize_class_arm(class_arm)
    level = normalize_class_level(arm)
    return {
        "class_arm": arm,
        "class_level": level,
        "stream": get_ss_stream(arm) if level.startswith("SS") else "JUNIOR",
        "stream_label": get_class_arm_stream_label(arm),
    }


# =========================================================
# SUBJECT LOOKUP
# =========================================================

def unique_subjects(subjects):
    return unique_ordered(subjects)


def get_subjects_for_class(class_category, class_arm=None, preferred_track=""):
    """
    Returns subjects appropriate to the actual class arm / track.

    Examples:
        get_subjects_for_class("JSS1", "JSS1A")
        get_subjects_for_class("SS1", "SS1_GOLD")
        get_subjects_for_class("SS1", "SS1_B/C", "COMMERCIAL")
    """

    level = normalize_class_level(class_category)
    arm = normalize_class_arm(class_arm or class_category, level)

    if not level: return []
    if level.startswith("JSS"): return unique_ordered(JSS_SUBJECTS)

    track = get_ss_track(arm, preferred_track)

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
    """
    Returns the SS tracks where a subject exists.

    Examples:
        Financial Account -> {"COMMERCIAL"}
        Chemistry         -> {"SCIENCE"}
        Literature        -> {"ART"}
        Mathematics       -> {"SCIENCE", "ART", "COMMERCIAL"}
    """

    level = normalize_class_level(class_level)
    subject_key = normalize_subject_key(subject)

    if not level.startswith("SS") or not subject_key: return set()

    tracks = set()

    science_keys = {normalize_subject_key(item) for item in SS_SCIENCE_SUBJECTS_BY_LEVEL.get(level, [])}
    art_keys = {normalize_subject_key(item) for item in SS_ART_SUBJECTS_BY_LEVEL.get(level, [])}
    commercial_keys = {normalize_subject_key(item) for item in SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, [])}

    if subject_key in science_keys: tracks.add("SCIENCE")
    if subject_key in art_keys: tracks.add("ART")
    if subject_key in commercial_keys: tracks.add("COMMERCIAL")

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
    # JSS
    # -----------------------------------------------------

    if level.startswith("JSS"):
        allowed_keys = {normalize_subject_key(item) for item in JSS_SUBJECTS}

        if subject_key not in allowed_keys:
            result["allowed"] = False
            result["reason"] = f"{subject_display} is not configured as a subject for {level}."

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
    """Validate JSS1/JSS2/JSS3/SS1/SS2/SS3."""
    return normalize_class_level(class_category) in SUPPORTED_CLASSES


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
    if arm == level: return True

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
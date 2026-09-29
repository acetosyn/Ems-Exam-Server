# MODULE: Grading System — centralized EMIS grading scales

from copy import deepcopy


GRADING_SYSTEMS = {
    "REPORT_SECONDARY": {
        "label": "Current EMIS Secondary Report Grading",
        "status": "active",
        "bands": [
            {"grade": "A", "minimum": 80, "maximum": 100, "comment": "Excellent"},
            {"grade": "B", "minimum": 70, "maximum": 79.99, "comment": "Very Good"},
            {"grade": "C", "minimum": 60, "maximum": 69.99, "comment": "Good"},
            {"grade": "D", "minimum": 45, "maximum": 59.99, "comment": "Pass"},
            {"grade": "E", "minimum": 40, "maximum": 44.99, "comment": "Pass"},
            {"grade": "F", "minimum": 0, "maximum": 39.99, "comment": "Fail"},
        ],
    },
    "WAEC": {
        "label": "WAEC A1-F9 Grading",
        "status": "configured",
        "bands": [
            {"grade": "A1", "minimum": 75, "maximum": 100, "comment": "Excellent"},
            {"grade": "B2", "minimum": 70, "maximum": 74.99, "comment": "Very Good"},
            {"grade": "B3", "minimum": 65, "maximum": 69.99, "comment": "Good"},
            {"grade": "C4", "minimum": 60, "maximum": 64.99, "comment": "Credit"},
            {"grade": "C5", "minimum": 55, "maximum": 59.99, "comment": "Credit"},
            {"grade": "C6", "minimum": 50, "maximum": 54.99, "comment": "Credit"},
            {"grade": "D7", "minimum": 45, "maximum": 49.99, "comment": "Pass"},
            {"grade": "E8", "minimum": 40, "maximum": 44.99, "comment": "Pass"},
            {"grade": "F9", "minimum": 0, "maximum": 39.99, "comment": "Fail"},
        ],
    },
    "PRIMARY": {"label": "Primary Grading", "status": "pending_school_scale", "bands": []},
}


def get_grading_system(name="REPORT_SECONDARY"): return deepcopy(GRADING_SYSTEMS.get(str(name or "").upper().strip(), {}))

def get_grade_scale(name="REPORT_SECONDARY"): return [(band["grade"], band["minimum"], band["maximum"], band["comment"]) for band in get_grading_system(name).get("bands", [])]


def grade_score(score, system="REPORT_SECONDARY"):
    try: value = float(str(score).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError): return "-", "Pending"
    for grade, minimum, maximum, comment in get_grade_scale(system):
        if minimum <= value <= maximum: return grade, comment
    return "F", "Fail"


def grading_system_ready(name): return bool(get_grading_system(name).get("bands"))

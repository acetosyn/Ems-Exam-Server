# MODULE: Promotion Safeguards — deterministic warnings, scope protection, arm-aware guidance and promotion roadmap

from modules.class_config import SUPPORTED_CLASSES, get_ss_stream, get_class_arm_stream_label
from modules.student_database.student_database import (
    get_database_summary, read_master_students, normalize_admission,
    normalize_student_level, normalize_student_arm,
)

PROMOTION_PATH = {"JSS1":"JSS2", "JSS2":"JSS3", "JSS3":"SS1", "SS1":"SS2", "SS2":"SS3", "SS3":"GRADUATED"}
DEMOTION_PATH = {"JSS2":"JSS1", "JSS3":"JSS2", "SS1":"JSS3", "SS2":"SS1", "SS3":"SS2"}
PROMOTION_SEQUENCE = ["SS3", "SS2", "SS1", "JSS3", "JSS2", "JSS1"]


def clean(value): return str(value or "").strip()
def class_total(summary, level): return int((summary.get(level) or {}).get("total") or 0)


def next_action_text(level):
    destination = PROMOTION_PATH.get(level, "")
    if destination == "GRADUATED": return "Graduate current SS3 students"
    if destination: return f"Promote current {level} students to {destination}"
    return ""


def recommended_promotion_sequence(summary=None):
    summary = summary or get_database_summary(); steps = []
    for level in PROMOTION_SEQUENCE:
        destination = PROMOTION_PATH[level]; count = class_total(summary, level)
        steps.append({"source":level, "destination":destination, "count":count, "action":"graduate" if level == "SS3" else "promote", "label":f"{level} → {'Graduate Archive' if destination == 'GRADUATED' else destination}"})
    return steps


def recommended_first_action(summary=None):
    summary = summary or get_database_summary()
    for level in PROMOTION_SEQUENCE:
        if class_total(summary, level) > 0: return next_action_text(level)
    return "No active students are waiting for promotion."


def _selected_rows(source_class, selected_admissions, mode):
    wanted = {normalize_admission(x) for x in (selected_admissions or []) if normalize_admission(x)}
    rows = []
    for student in read_master_students():
        level = normalize_student_level(student.get("Class_category") or student.get("Class"))
        admission = normalize_admission(student.get("Admission_number"))
        if level != source_class: continue
        if mode == "all" or admission in wanted: rows.append(student)
    return rows


def _arm_counts(rows, level):
    counts = {}
    for student in rows:
        arm = normalize_student_arm(student.get("Class"), level)
        if arm: counts[arm] = counts.get(arm, 0) + 1
    return counts


def _destination_placements(destination_classes):
    counts = {}
    for _, arm in (destination_classes or {}).items():
        arm = clean(arm)
        if arm: counts[arm] = counts.get(arm, 0) + 1
    return counts


def _cross_stream_changes(rows, destination_classes):
    destination_classes = {normalize_admission(k): clean(v) for k, v in (destination_classes or {}).items()}
    changes = {}
    for student in rows:
        admission = normalize_admission(student.get("Admission_number")); destination_arm = destination_classes.get(admission, "")
        if not destination_arm: continue
        source_arm = clean(student.get("Class")); source_stream = get_ss_stream(source_arm); destination_stream = get_ss_stream(destination_arm)
        if not source_stream or not destination_stream or source_stream == destination_stream: continue
        source_label = get_class_arm_stream_label(source_arm); destination_label = get_class_arm_stream_label(destination_arm)
        key = f"{source_label} → {destination_label}"; changes[key] = changes.get(key, 0) + 1
    return changes


def build_guard(action, source_class, selected_admissions=None, selected_count=None, mode="selected", destination_classes=None, use_ai=False):
    action = clean(action).lower(); source_class = clean(source_class).upper(); mode = clean(mode).lower() or "selected"; summary = get_database_summary()
    source_total = class_total(summary, source_class); selected_admissions = [normalize_admission(x) for x in (selected_admissions or []) if normalize_admission(x)]
    selected_rows = _selected_rows(source_class, selected_admissions, mode)
    selected_count = source_total if mode == "all" else int(selected_count if selected_count is not None else len(selected_rows) or len(selected_admissions))
    if selected_count < 0: selected_count = 0
    destination = PROMOTION_PATH.get(source_class, "") if action in {"promote","graduate"} else DEMOTION_PATH.get(source_class, "") if action == "demote" else source_class
    destination_total = 0 if destination == "GRADUATED" else class_total(summary, destination); whole_class = bool(source_total and selected_count >= source_total)
    source_arm_counts = _arm_counts(selected_rows, source_class); destination_arm_placements = _destination_placements(destination_classes); cross_stream_changes = _cross_stream_changes(selected_rows, destination_classes)
    warnings = []

    if action == "promote":
        if whole_class:
            warnings.append({"severity":"high", "code":"WHOLE_CLASS", "title":f"Entire {source_class} class selected", "message":f"You are about to promote all {source_total} active {source_class} students to {destination}. After completion, {source_class} will be empty. There is no one-click Undo from this screen; EMIS creates a safety database backup before the move."})
        else:
            warnings.append({"severity":"info", "code":"PARTIAL_PROMOTION", "title":"Selected-student promotion", "message":f"{selected_count} of {source_total} {source_class} students are selected. Students not selected will remain in {source_class}."})
            if source_arm_counts:
                selected_text = ", ".join(f"{arm} ({count})" for arm, count in sorted(source_arm_counts.items()))
                all_arms = (summary.get(source_class) or {}).get("arms") or {}; remaining = {arm:max(0, int(count or 0) - source_arm_counts.get(arm, 0)) for arm, count in all_arms.items()}; remaining = {arm:count for arm,count in remaining.items() if count > 0}
                remain_text = ", ".join(f"{arm} ({count})" for arm, count in sorted(remaining.items())) or "none"
                warnings.append({"severity":"info", "code":"ARM_SCOPE", "title":"Promotion scope is locked to the selected students", "message":f"Selected source arm(s): {selected_text}. Students remaining in {source_class}: {remain_text}. EMIS will not move unselected arms."})
        if destination_total > 0:
            hint = "Graduate the current SS3 students first if they have completed school." if destination == "SS3" else f"Recommended sequence: {next_action_text(destination)} first, then return to {source_class}."
            warnings.append({"severity":"warning", "code":"DESTINATION_OCCUPIED", "title":f"{destination} already contains {destination_total} student(s)", "message":f"Promoting now will add these students to an already occupied {destination} class. {hint} This is guidance only; you may still continue if the move is intentional."})
        for arm, count in sorted(destination_arm_placements.items()):
            occupied = int((((summary.get(destination) or {}).get("arms") or {}).get(arm)) or 0)
            if occupied > 0: warnings.append({"severity":"info", "code":"DESTINATION_ARM_OCCUPIED", "title":f"{arm} currently has {occupied} student(s)", "message":f"This placement will add {count} selected student(s) to {arm}. Existing students are not replaced or removed."})
        if cross_stream_changes:
            text = "; ".join(f"{label}: {count}" for label, count in sorted(cross_stream_changes.items()))
            warnings.append({"severity":"warning", "code":"CROSS_STREAM", "title":"Academic stream change detected", "message":f"The selected placement includes a stream change ({text}). This is allowed, but confirm that the change is intentional before continuing."})

    elif action == "graduate":
        warnings.append({"severity":"high", "code":"GRADUATION", "title":"SS3 graduation removes students from the active school roster", "message":f"{selected_count} SS3 student(s) will be copied to the Graduate Archive and removed from active classes. Their admission numbers become available for future new students only after the graduation transaction succeeds."})
        if whole_class: warnings.append({"severity":"info", "code":"SS3_EMPTIES", "title":"SS3 will become empty", "message":"This is the recommended first step before moving SS2 students into SS3."})

    elif action == "demote":
        warnings.append({"severity":"warning", "code":"DEMOTION", "title":"Selected-student demotion", "message":f"You are moving {selected_count} selected student(s) from {source_class} back to {destination}. Whole-class demotion is intentionally not provided. Confirm the students carefully before continuing."})
        if destination_total > 0: warnings.append({"severity":"info", "code":"DEMOTION_DESTINATION_OCCUPIED", "title":f"{destination} already has {destination_total} student(s)", "message":"The selected students will be added to the existing class after confirmation."})
        if cross_stream_changes:
            text = "; ".join(f"{label}: {count}" for label, count in sorted(cross_stream_changes.items()))
            warnings.append({"severity":"warning", "code":"CROSS_STREAM", "title":"Academic stream change detected", "message":f"The selected demotion includes a stream change ({text}). This is allowed; verify each destination arm before continuing."})

    elif action == "repeat":
        warnings.append({"severity":"info", "code":"REPEAT", "title":"Students remain in the same class", "message":f"{selected_count} student(s) will remain in {source_class}. No class movement occurs."})

    result = {"action":action, "source_class":source_class, "destination_class":destination, "source_count":source_total, "selected_count":selected_count, "whole_class":whole_class, "destination_count":destination_total, "source_arm_selection":source_arm_counts, "destination_arm_placements":destination_arm_placements, "cross_stream_changes":cross_stream_changes, "warnings":warnings, "recommended_sequence":recommended_promotion_sequence(summary), "recommended_first_action":recommended_first_action(summary), "class_summary":summary, "ai":None}
    if use_ai:
        try:
            from modules.student_database.promotion_ai import explain_promotion_guard
            result["ai"] = explain_promotion_guard({"action":action, "source_class":source_class, "destination_class":destination, "source_count":source_total, "selected_count":selected_count, "whole_class":whole_class, "source_arm_selection":source_arm_counts, "destination_arm_placements":destination_arm_placements, "cross_stream_changes":cross_stream_changes, "warnings":warnings, "recommended_first_action":result["recommended_first_action"]})
        except Exception as error: result["ai"] = {"guidance":"", "provider":"Rules only", "error":str(error)}
    return result

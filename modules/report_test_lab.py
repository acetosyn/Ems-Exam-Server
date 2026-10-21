# MODULE: Report Test Lab — isolated synthetic report/cumulative verification sandbox
# PURPOSE: Test First/Second/Third Term report generation without touching production CA, exam, attendance, Islamiyyah or Academic History data.

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request, session

from modules.academic_records import normalize_academic_session, normalize_academic_term, normalize_report_class, get_report_students_for_class, get_report_subjects_for_selection
from modules.assessment_rules import get_assessment_rule
from modules.grading_system import grade_score_for_class
from modules.student_lookup import normalize_admission_number
from modules.cumulative_results import build_class_cumulative_from_records, ordinal

report_test_lab_bp = Blueprint("report_test_lab_bp", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TEST_FILE = BASE_DIR / "static" / "data" / "report_sheets" / "test_runs.json"
TEST_LOCK = threading.RLock()
TERMS = ("FIRST", "SECOND", "THIRD")
TERM_LABELS = {"FIRST": "First Term", "SECOND": "Second Term", "THIRD": "Third Term"}


def clean(value): return str(value or "").strip()
def clean_upper(value): return clean(value).upper()
def now_iso(): return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _authorized(): return clean(session.get("user_type")).lower() in {"admin", "teacher_admin"}


def _read_store():
    if not TEST_FILE.exists(): return {"runs": []}
    try:
        data = json.loads(TEST_FILE.read_text(encoding="utf-8")); return data if isinstance(data, dict) else {"runs": []}
    except Exception: return {"runs": []}


def _write_store(data):
    TEST_FILE.parent.mkdir(parents=True, exist_ok=True); temp = TEST_FILE.with_suffix(".json.tmp"); temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(TEST_FILE)


def _stable_fraction(*parts):
    digest = hashlib.sha256("|".join(clean(part) for part in parts).encode("utf-8")).hexdigest(); return int(digest[:8], 16) / 0xFFFFFFFF


def _score(maximum, *parts, floor=.52, ceiling=.94):
    maximum = float(maximum or 0); ratio = floor + (_stable_fraction(*parts) * (ceiling - floor)); value = round(maximum * ratio, 1); return int(value) if float(value).is_integer() else value


def _trial_performance_profiles(students, session_value, level, arm):
    # A class trial must look like a real class, not a room where everybody passes. About 20% are deliberately weak/failing, while the rest are spread across borderline, average and strong performance bands.
    ranked = sorted([(normalize_admission_number(student.get("admission_number")), _stable_fraction(normalize_admission_number(student.get("admission_number")), session_value, level, arm, "trial-performance-rank")) for student in students], key=lambda item: item[1]); count = len(ranked)
    if not count: return {}
    fail_count = 0 if count == 1 else (1 if count < 5 else max(1, int((count * .20) + .5))); borderline_count = max(1, int((count * .25) + .5)) if count >= 4 else 0; strong_count = max(1, int((count * .20) + .5)) if count >= 5 else 0
    profiles = {}
    for index, (admission, _) in enumerate(ranked):
        if index < fail_count: band, low, high = "fail", .24, .37
        elif index < fail_count + borderline_count: band, low, high = "borderline", .48, .60
        elif index >= max(fail_count + borderline_count, count - strong_count): band, low, high = "strong", .76, .92
        else: band, low, high = "average", .59, .75
        base = low + (_stable_fraction(admission, session_value, level, arm, "trial-performance-base") * (high - low)); profiles[admission] = {"band": band, "base_ratio": base}
    return profiles


def _profile_score(maximum, base_ratio, *parts, spread=.10):
    maximum = float(maximum or 0); jitter = (_stable_fraction(*parts, "trial-jitter") - .5) * (spread * 2); ratio = max(.08, min(.98, float(base_ratio or .5) + jitter)); value = round(maximum * ratio, 1); return int(value) if float(value).is_integer() else value


def _assessment(level):
    rule = dict(get_assessment_rule(level) or {}); fields = [dict(item) for item in (rule.get("fields") or []) if isinstance(item, dict) and item.get("key")]
    if not fields or rule.get("exam_max") in (None, ""):
        # Test Lab fallback is intentionally sandbox-only; it never changes the school's real assessment rule.
        fields = [{"key": "CA", "label": "CA", "max": 30.0}]; rule.update({"key": "TRIAL", "label": "Trial Scheme", "ca_max": 30, "exam_max": 70, "total_max": 100, "fields": fields, "entry_enabled": False, "trial_fallback": True})
    return rule


def _subject_name(value):
    if isinstance(value, dict): return clean(value.get("subject") or value.get("name") or value.get("label") or value.get("subject_name"))
    return clean(value)


def _subject_key(name): return "_".join(clean_upper(name).replace("/", " ").replace("-", " ").split())


def _attendance(admission, term):
    days_open = 60; absent = int(round(_stable_fraction(admission, term, "absent") * 5)); late = int(round(_stable_fraction(admission, term, "late") * 3)); sick = int(round(_stable_fraction(admission, term, "sick") * 2)); present = max(0, days_open - absent - sick); credit = present
    return {"days_open": days_open, "present": present, "absent": absent, "late": late, "sick": sick, "excused": 0, "unmarked": 0, "present_credit": credit, "absent_total": absent + sick, "attendance_percentage": round(credit / days_open * 100, 1)}


def _build_term_reports(students, subjects, session_value, term, level, arm, rule, performance_profiles=None):
    reports = []; performance_profiles = performance_profiles or {}
    fields = rule.get("fields") or []; exam_max = float(rule.get("exam_max") or 0); total_max = float(rule.get("total_max") or 100)
    for student in students:
        admission = normalize_admission_number(student.get("admission_number")); full_name = clean(student.get("full_name") or student.get("name")) or admission; rows = []; performance = performance_profiles.get(admission) or {"band": "average", "base_ratio": .66}; base_ratio = float(performance.get("base_ratio") or .66)
        for subject in subjects:
            name = _subject_name(subject)
            if not name: continue
            row = {"subject_key": _subject_key(name), "subject": name, "assessment_mode": clean_upper(rule.get("key") or "TRIAL"), "mode": clean_upper(rule.get("key") or "TRIAL"), "total_max": total_max, "complete": True, "has_ca": True, "has_exam": True}
            ca_total = 0.0
            for field in fields:
                key = clean(field.get("key")).lower(); maximum = float(field.get("max") or 0); value = _profile_score(maximum, base_ratio, admission, term, name, key, spread=.09); row[key] = value; ca_total += float(value)
            exam = _profile_score(exam_max, base_ratio, admission, term, name, "exam", spread=.11); total = round(ca_total + float(exam), 1); grade, comment = grade_score_for_class(total, level)
            row.update({"ca_total": round(ca_total, 1), "exam": exam, "total": total, "grade": grade, "comment": comment, "position": 0, "position_text": "--", "out_of": len(students), "lowest": None, "highest": None, "class_average": None}); rows.append(row)
        total_score = round(sum(float(row.get("total") or 0) for row in rows), 1); average = round(total_score / (len(rows) * total_max) * 100, 2) if rows and total_max else None; grade, comment = grade_score_for_class(average, level) if average is not None else ("-", "Pending")
        reports.append({"admission_number": admission, "full_name": full_name, "first_name": clean(student.get("first_name")), "last_name": clean(student.get("last_name")), "other_names": clean(student.get("other_names")), "sex": clean(student.get("sex")), "class_level": level, "class_arm": arm, "session": session_value, "term": term, "term_label": TERM_LABELS[term], "subjects": rows, "subject_count": len(rows), "total_score": total_score, "average": average, "grade": grade, "grade_comment": comment, "has_ca": True, "has_exam": True, "has_attendance": True, "attendance": _attendance(admission, term), "academic_complete": True, "subjects_complete": len(rows), "missing_ca_subjects": [], "missing_exam_subjects": [], "source_mode": "test_trial", "trial_data": True, "trial_performance_band": performance.get("band"), "assessment": rule, "assessment_mode": clean_upper(rule.get("key") or "TRIAL"), "teacher_remark": "TRIAL DATA — generated only for Report Test Lab verification.", "principal_remark": "TRIAL DATA — not part of the student's official record.", "form_teacher": "Test Lab", "promotion_status": "PENDING", "promotion_note": "Trial cumulative decision only."})

    # Class statistics and positions are calculated exactly once after every student's scores exist.
    report_averages = sorted([float(r["average"]) for r in reports if r.get("average") is not None], reverse=True)
    for report in reports:
        if report.get("average") is not None:
            position = report_averages.index(float(report["average"])) + 1; report["position"] = position; report["position_text"] = ordinal(position); report["out_of"] = len(reports)
    for subject_index in range(max((len(r.get("subjects") or []) for r in reports), default=0)):
        totals = [float(r["subjects"][subject_index]["total"]) for r in reports if len(r.get("subjects") or []) > subject_index]
        if not totals: continue
        ordered = sorted(totals, reverse=True); low, high, avg = min(totals), max(totals), round(sum(totals) / len(totals), 2)
        for report in reports:
            if len(report.get("subjects") or []) <= subject_index: continue
            row = report["subjects"][subject_index]; score = float(row["total"]); pos = ordered.index(score) + 1; row.update({"position": pos, "position_text": ordinal(pos), "out_of": len(totals), "lowest": low, "highest": high, "class_average": avg})
    class_avg = round(sum(float(r["average"]) for r in reports if r.get("average") is not None) / len(reports), 2) if reports else None
    for report in reports: report["class_average"] = class_avg
    return reports


def _history_records(term_reports):
    rows = []
    for term, reports in term_reports.items():
        for report in reports:
            admission = normalize_admission_number(report.get("admission_number")); student_key = hashlib.sha256(f"trial|{admission}|{clean(report.get('full_name')).lower()}".encode("utf-8")).hexdigest()[:20]
            rows.append({"record_id": f"trial-{term.lower()}-{student_key}", "student_key": student_key, "admission_number": admission, "full_name": report.get("full_name"), "sex": report.get("sex"), "session": report.get("session"), "term": term, "class_level": report.get("class_level"), "class_arm": report.get("class_arm"), "source_mode": "test_trial", "academic_complete": True, "subject_count": report.get("subject_count"), "subjects_complete": report.get("subject_count"), "total_score": report.get("total_score"), "maximum_score": (report.get("subject_count") or 0) * 100, "score_percentage": report.get("average"), "average": report.get("average"), "grade": report.get("grade"), "position": report.get("position"), "position_text": report.get("position_text"), "out_of": report.get("out_of"), "attendance_percentage": (report.get("attendance") or {}).get("attendance_percentage"), "report": report})
    return rows


def _attach_cumulative(third_reports, cumulative):
    by_admission = {normalize_admission_number(item.get("profile", {}).get("admission_number")): item for item in cumulative.get("students", [])}; complete = [item for item in cumulative.get("students", []) if item.get("complete") and item.get("annual_average") is not None]; annual_values = [float(item.get("annual_average")) for item in complete]; high = max(annual_values) if annual_values else None; low = min(annual_values) if annual_values else None
    for report in third_reports:
        item = by_admission.get(normalize_admission_number(report.get("admission_number")))
        if not item: continue
        terms = item.get("terms") or {}; subjects = {clean_upper(row.get("subject_key")): row for row in (item.get("subjects") or [])}
        for row in report.get("subjects") or []:
            annual = subjects.get(clean_upper(row.get("subject_key"))) or {}; row.update({"first_term_total": annual.get("first_term"), "second_term_total": annual.get("second_term"), "third_term_total": annual.get("third_term"), "cumulative_total": annual.get("annual_score"), "cumulative_average": annual.get("annual_average"), "cumulative_grade": annual.get("grade"), "cumulative_comment": annual.get("comment"), "terms_available": annual.get("terms_available", 0)})
        report.update({"first_term_average": (terms.get("FIRST") or {}).get("average"), "second_term_average": (terms.get("SECOND") or {}).get("average"), "third_term_average": (terms.get("THIRD") or {}).get("average"), "first_term_score": (terms.get("FIRST") or {}).get("score"), "second_term_score": (terms.get("SECOND") or {}).get("score"), "third_term_score": (terms.get("THIRD") or {}).get("score"), "first_term_max": (terms.get("FIRST") or {}).get("maximum"), "second_term_max": (terms.get("SECOND") or {}).get("maximum"), "third_term_max": (terms.get("THIRD") or {}).get("maximum"), "cumulative_score": item.get("annual_score"), "cumulative_max": item.get("annual_max"), "cumulative_score_percentage": item.get("annual_score_percentage"), "cumulative_average": item.get("annual_average"), "cumulative_grade": item.get("annual_grade"), "cumulative_terms_available": item.get("terms_available"), "cumulative_complete": item.get("complete"), "cumulative_attendance": item.get("attendance"), "cumulative_source_mode": "test_trial", "cumulative_class_average": cumulative.get("class_average"), "cumulative_highest_average": high, "cumulative_lowest_average": low, "cumulative_no_in_class": cumulative.get("complete_students"), "cumulative_combined_stream": cumulative.get("complete_students"), "cumulative_position": item.get("annual_position"), "cumulative_position_text": item.get("annual_position_text"), "cumulative_out_of": item.get("annual_out_of"), "promotion_status": "PROMOTED" if (item.get("annual_average") or 0) >= 45 else "REPEATED", "promotion_note": "Trial decision generated by the isolated Test Lab.", "report_variant": "cumulative", "is_cumulative_report": True, "show_promotion_decision": True})


def _summary_run(run):
    return {key: run.get(key) for key in ("run_id", "created_at", "created_by", "session", "class_level", "class_arm", "scope", "student_count", "class_context_count", "subject_count", "coverage_percentage", "class_average", "pass_count", "fail_count")}


@report_test_lab_bp.route("/api/report-sheets/test-lab/config")
def test_lab_config():
    if not _authorized(): return jsonify({"success": False, "message": "Unauthorized."}), 403
    level, arm = normalize_report_class(request.args.get("class_level") or request.args.get("level"), request.args.get("class_arm") or request.args.get("arm")); students = get_report_students_for_class(level, arm, active_only=True) if level else []; subjects = get_report_subjects_for_selection(level, arm) if level else []; rule = _assessment(level) if level else {}
    return jsonify({"success": True, "class_level": level, "class_arm": arm, "students": [{"admission_number": s.get("admission_number"), "full_name": s.get("full_name"), "class_arm": s.get("class_arm")} for s in students], "subjects": [_subject_name(s) for s in subjects if _subject_name(s)], "assessment": rule, "count": len(students), "sandbox": True})


@report_test_lab_bp.route("/api/report-sheets/test-lab/run", methods=["POST"])
def test_lab_run():
    if not _authorized(): return jsonify({"success": False, "message": "Unauthorized."}), 403
    data = request.get_json(silent=True) or {}; session_value = normalize_academic_session(data.get("session")); level, arm = normalize_report_class(data.get("class_level"), data.get("class_arm")); scope = clean(data.get("scope") or "class").lower(); class_students = get_report_students_for_class(level, arm, active_only=True); next_term = clean(data.get("next_term")); form_teacher = clean(data.get("form_teacher")) or "Test Lab"
    if not session_value or not level or not arm: return jsonify({"success": False, "message": "Select session, class level and class arm before starting a test run."}), 400
    try: next_term = datetime.strptime(next_term[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError): return jsonify({"success": False, "message": "Set a valid Next Term Begins date before starting the Test Lab. Trial sheets follow the same required setup as official reports."}), 400
    if not class_students: return jsonify({"success": False, "message": "No active students were found for this class."}), 404
    wanted = {normalize_admission_number(value) for value in (data.get("admission_numbers") or []) if normalize_admission_number(value)}
    if scope == "student":
        admission = normalize_admission_number(data.get("admission_number")); wanted = {admission} if admission else wanted
    selected_students = [student for student in class_students if not wanted or normalize_admission_number(student.get("admission_number")) in wanted]
    if not selected_students: return jsonify({"success": False, "message": "No students matched the selected Test Lab scope."}), 400
    subjects = [_subject_name(item) for item in get_report_subjects_for_selection(level, arm)]; subjects = [name for name in subjects if name]
    if not subjects: subjects = ["English Language", "Mathematics", "Basic Science", "Civic Education", "Computer Studies"]
    rule = _assessment(level); performance_profiles = _trial_performance_profiles(class_students, session_value, level, arm)
    # Always synthesize the full selected class in memory so a one-student trial still receives realistic class average, highest/lowest and position statistics. About 20% of a multi-student class are intentionally generated as genuine failing/poor-result cases. Only the requested scope is returned/stored for preview.
    class_term_reports = {term: _build_term_reports(class_students, subjects, session_value, term, level, arm, rule, performance_profiles) for term in TERMS}
    for reports in class_term_reports.values():
        for report in reports: report["form_teacher"] = form_teacher; report["next_term"] = next_term
    records = _history_records(class_term_reports); cumulative = build_class_cumulative_from_records(records, session_value, level, arm); _attach_cumulative(class_term_reports["THIRD"], cumulative)
    selected_admissions = {normalize_admission_number(student.get("admission_number")) for student in selected_students}; term_reports = {term: [report for report in reports if normalize_admission_number(report.get("admission_number")) in selected_admissions] for term, reports in class_term_reports.items()}
    cumulative_students = cumulative.get("students") or []; class_fail_count = sum(1 for item in cumulative_students if item.get("annual_average") is not None and float(item.get("annual_average") or 0) < 45); class_pass_count = sum(1 for item in cumulative_students if item.get("annual_average") is not None and float(item.get("annual_average") or 0) >= 45)
    run_id = uuid.uuid4().hex[:12]; created_by = clean(session.get("admin_username") or session.get("username") or session.get("user") or "Staff"); run = {"run_id": run_id, "created_at": now_iso(), "created_by": created_by, "session": session_value, "class_level": level, "class_arm": arm, "scope": scope, "student_count": len(selected_students), "class_context_count": len(class_students), "subject_count": len(subjects), "coverage_percentage": cumulative.get("coverage_percentage"), "class_average": cumulative.get("class_average"), "pass_count": class_pass_count, "fail_count": class_fail_count, "assessment_fallback": bool(rule.get("trial_fallback")), "term_reports": term_reports, "cumulative": cumulative}
    with TEST_LOCK:
        store = _read_store(); runs = [item for item in (store.get("runs") or []) if isinstance(item, dict)]; runs.append(run); store["runs"] = runs[-10:]; _write_store(store)
    return jsonify({"success": True, "message": f"Trial complete: {len(selected_students)} selected student(s) previewed with {len(class_students)}-student class statistics. Test distribution: {class_pass_count} pass / {class_fail_count} fail. Three terms and cumulative result generated in the isolated Test Lab.", "sandbox": True, "run": _summary_run(run), "term_counts": {term: len(rows) for term, rows in term_reports.items()}, "third_term_reports": term_reports["THIRD"], "cumulative": cumulative, "assessment": rule})


@report_test_lab_bp.route("/api/report-sheets/test-lab/runs")
def test_lab_runs():
    if not _authorized(): return jsonify({"success": False, "message": "Unauthorized."}), 403
    with TEST_LOCK: runs = [_summary_run(item) for item in reversed(_read_store().get("runs") or []) if isinstance(item, dict)]
    return jsonify({"success": True, "sandbox": True, "runs": runs, "count": len(runs)})


@report_test_lab_bp.route("/api/report-sheets/test-lab/clear", methods=["POST", "DELETE"])
def test_lab_clear():
    if not _authorized(): return jsonify({"success": False, "message": "Unauthorized."}), 403
    data = request.get_json(silent=True) or {}; run_id = clean(data.get("run_id"));
    with TEST_LOCK:
        store = _read_store(); runs = [item for item in (store.get("runs") or []) if isinstance(item, dict)]; before = len(runs); runs = [item for item in runs if clean(item.get("run_id")) != run_id] if run_id else []; store["runs"] = runs; _write_store(store)
    deleted = before - len(runs); return jsonify({"success": True, "sandbox": True, "deleted": deleted, "message": f"{deleted} isolated trial run(s) cleared. Production academic data was not touched."})

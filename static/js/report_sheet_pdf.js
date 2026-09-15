/* ======================================================================
   report_sheet_pdf.js — EMIS One-Page A4 Portrait Report Card Renderer
   Purpose: official printable parent-facing report card only.
   No backend fetching is performed here; report_sheet.js supplies data.
   ====================================================================== */

(() => {
    "use strict";

    const AFFECTIVE_LABELS = { punctuality: "Punctuality", attendance: "Attendance", reliability: "Reliability", neatness: "Neatness", politeness: "Politeness", honesty: "Honesty", relationship: "Relationship", self_control: "Self Control", attentiveness: "Attentiveness", perseverance: "Perseverance" };
    const PSYCHOMOTOR_LABELS = { handwriting: "Handwriting", games: "Games", sport: "Sport", drawing: "Drawing & Painting", crafts: "Crafts", musical_skills: "Musical Skills" };

    window.ReportSheetPDF = {
        // ============================================================
        // MAIN RENDERER
        // ============================================================

        render(report = {}, payload = {}) {
            const subjects = Array.isArray(report.subjects) ? report.subjects : [], count = subjects.length, isJss = String(report.class_level || payload.class_level || "").toUpperCase().startsWith("JSS"), isThird = String(report.term || payload.term || "").toUpperCase().includes("THIRD"), density = count >= 15 ? "report-density-ultra" : count >= 10 || isThird ? "report-density-tight" : "report-density-normal";
            return `<article class="emis-report-card generated-report-sheet ${density}" data-report-admission="${this.escape(report.admission_number || "")}" data-result-name="${this.escape(report.result_name || "")}" data-source-mode="${this.escape(report.source_mode || "auto")}">${this.header(report, payload)}${this.identity(report, payload)}${this.summaryStrip(report)}${this.subjectSection(report, subjects, isJss, isThird)}${this.insightStrip(report)}${isThird ? this.cumulativeStrip(report) : ""}${this.traitsAndAttendance(report)}${this.remarks(report, payload)}${this.footer(report)}</article>`;
        },

        // ============================================================
        // SCHOOL HEADER / REPORT TITLE
        // ============================================================

        header(report, payload) {
            const term = report.term_label || this.termLabel(report.term || payload.term), session = report.session || payload.session || "";
            return `<header class="emis-report-header"><div class="emis-report-logo"><img src="/static/images/logo.jpg" alt="Epitome Model Islamic Schools Logo"></div><div class="emis-report-school"><h1>EPITOME MODEL ISLAMIC SCHOOLS</h1><p>FOR TOTAL ACADEMIC EXCELLENCE</p><span>OFF SANI ABACHA ROAD, OLD KARU ROAD, ANGUWAR HASHIMU</span></div><div class="emis-report-document"><strong>STUDENT REPORT SHEET</strong><span>${this.escape(term)} • ${this.escape(session)} ACADEMIC SESSION</span></div></header>`;
        },

        // ============================================================
        // STUDENT IDENTITY / CONTEXT
        // ============================================================

        identity(report, payload) {
            const klass = this.classLabel(report.class_arm || report.class_level || payload.class_arm), sex = report.sex || "—", age = report.age ?? report.student?.age ?? "—", session = report.session || payload.session || "—", term = report.term_label || this.termLabel(report.term || payload.term);
            return `<section class="emis-report-identity"><div class="emis-student-primary"><span>Student Name</span><strong>${this.escape(report.full_name || "—")}</strong><small>${this.escape(report.admission_number || "—")} • ${this.escape(klass)}</small></div><div class="emis-student-facts"><p><span>Admission No.</span><strong>${this.escape(report.admission_number || "—")}</strong></p><p><span>Class</span><strong>${this.escape(klass)}</strong></p><p><span>Sex</span><strong>${this.escape(sex)}</strong></p><p><span>Age</span><strong>${this.escape(age)}</strong></p><p><span>Session</span><strong>${this.escape(session)}</strong></p><p><span>Term</span><strong>${this.escape(term)}</strong></p></div></section>`;
        },

        // ============================================================
        // PARENT-FRIENDLY SUMMARY STRIP
        // ============================================================

        summaryStrip(report) {
            const attendance = report.attendance || {}, average = this.percent(report.average), grade = report.grade || "—", position = report.position_text || report.position || "—", outOf = report.out_of || "—", attendancePct = this.percent(attendance.attendance_percentage, 1), classAverage = this.percent(report.performance_insights?.class_average ?? report.class_average, 2), totalScore = this.num(report.total_score ?? report.total_score_number ?? report.total);
            return `<section class="emis-report-summary"><article><span>Final Average</span><strong>${average}</strong><small>Total score: ${totalScore}</small></article><article><span>Final Grade</span><strong>${this.escape(grade)}</strong><small>${this.gradeMeaning(grade)}</small></article><article><span>Class Position</span><strong>${this.escape(position)} <em>/ ${this.escape(outOf)}</em></strong><small>No. in class: ${this.escape(outOf)}</small></article><article><span>Attendance</span><strong>${attendancePct}</strong><small>${this.escape(attendance.present_credit ?? attendance.present ?? 0)} present • ${this.escape(attendance.absent_total ?? attendance.absent ?? 0)} absent</small></article><article><span>Class Average</span><strong>${classAverage}</strong><small>Comparison point</small></article></section>`;
        },

        // ============================================================
        // SUBJECT PERFORMANCE TABLE
        // ============================================================

        subjectSection(report, subjects, isJss, isThird) {
            const colspan = isJss ? (isThird ? 16 : 15) : (isThird ? 15 : 14), rows = subjects.length ? subjects.map((row, index) => this.subjectRow(row, index, isJss, isThird)).join("") : `<tr class="emis-no-subject-row"><td colspan="${colspan}">No academic CA/Test or CBT scores have been recorded for this student in the selected term.</td></tr>`;
            return `<section class="emis-report-academics"><div class="emis-section-heading"><div><span>Academic Performance</span><strong>${subjects.length} Subject${subjects.length === 1 ? "" : "s"} Assessed</strong></div><small>${isJss ? "JSS: CA /60 + Exam /40" : "SS: CA /30 + Exam /70"}${isThird ? " • Annual average included" : ""}</small></div><div class="emis-report-table-wrap"><table class="emis-report-result-table ${isJss ? "jss" : "ss"}"><thead>${this.subjectHeader(isJss, isThird)}</thead><tbody>${rows}</tbody></table></div>${this.gradeLegend()}</section>`;
        },

        subjectHeader(isJss, isThird) {
            if (isJss) return `<tr><th>#</th><th class="subject-col">Subject</th><th>CA1<br><small>/10</small></th><th>CA2<br><small>/10</small></th><th>T1<br><small>/20</small></th><th>T2<br><small>/20</small></th><th>Exam<br><small>/40</small></th><th>Total<br><small>/100</small></th>${isThird ? "<th>Annual<br><small>Avg.</small></th>" : ""}<th>Grd</th><th>Pos</th><th>Out</th><th>Low</th><th>High</th><th>Avg</th><th>Comment</th></tr>`;
            return `<tr><th>#</th><th class="subject-col">Subject</th><th>1st Ass.<br><small>/5</small></th><th>2nd Ass.<br><small>/5</small></th><th>Test<br><small>/20</small></th><th>Exam<br><small>/70</small></th><th>Total<br><small>/100</small></th>${isThird ? "<th>Annual<br><small>Avg.</small></th>" : ""}<th>Grd</th><th>Pos</th><th>Out</th><th>Low</th><th>High</th><th>Avg</th><th>Comment</th></tr>`;
        },

        subjectRow(row, index, isJss, isThird) {
            const annual = row.cumulative_average !== undefined && row.cumulative_average !== null ? this.num(row.cumulative_average) : "—";
            if (isJss) return `<tr><td>${index + 1}</td><td class="subject-col">${this.escape(row.subject || "—")}</td><td>${this.score(row.ca1)}</td><td>${this.score(row.ca2)}</td><td>${this.score(row.test1)}</td><td>${this.score(row.test2)}</td><td>${this.score(row.exam)}</td><td class="total-cell">${this.score(row.total)}</td>${isThird ? `<td class="annual-cell">${annual}</td>` : ""}<td class="grade-cell">${this.escape(row.grade || "—")}</td><td>${this.escape(row.position_text || row.position || "—")}</td><td>${this.escape(row.out_of || "—")}</td><td>${this.score(row.lowest)}</td><td>${this.score(row.highest)}</td><td>${this.score(row.class_average)}</td><td class="comment-col">${this.escape(row.comment || "")}</td></tr>`;
            return `<tr><td>${index + 1}</td><td class="subject-col">${this.escape(row.subject || "—")}</td><td>${this.score(row.ass1)}</td><td>${this.score(row.ass2)}</td><td>${this.score(row.test)}</td><td>${this.score(row.exam)}</td><td class="total-cell">${this.score(row.total)}</td>${isThird ? `<td class="annual-cell">${annual}</td>` : ""}<td class="grade-cell">${this.escape(row.grade || "—")}</td><td>${this.escape(row.position_text || row.position || "—")}</td><td>${this.escape(row.out_of || "—")}</td><td>${this.score(row.lowest)}</td><td>${this.score(row.highest)}</td><td>${this.score(row.class_average)}</td><td class="comment-col">${this.escape(row.comment || "")}</td></tr>`;
        },

        gradeLegend() { return `<div class="emis-grade-legend"><strong>Grade Key</strong><span>A 80–100 • Excellent</span><span>B 70–79 • Very Good</span><span>C 60–69 • Good</span><span>D 45–59 • Pass</span><span>E 40–44 • Pass</span><span>F 0–39 • Needs Improvement</span></div>`; },

        // ============================================================
        // PERFORMANCE INSIGHTS — EXTRA PARENT FEATURES
        // ============================================================

        insightStrip(report) {
            const insights = report.performance_insights || this.calculateInsights(report), rawDiff = this.optionalNumber(insights.average_difference), diffText = rawDiff === null ? "—" : `${rawDiff > 0 ? "+" : ""}${this.num(rawDiff)}%`, diffLabel = rawDiff === null ? "Comparison pending" : rawDiff > 0 ? "Above class average" : rawDiff < 0 ? "Below class average" : "At class average";
            return `<section class="emis-report-insights"><article><span>Strongest Subject</span><strong>${this.escape(insights.strongest_subject || "—")}</strong><small>${this.percent(insights.strongest_score)}</small></article><article><span>Focus Subject</span><strong>${this.escape(insights.focus_subject || "—")}</strong><small>${this.percent(insights.focus_score)}</small></article><article><span>Compared With Class</span><strong>${diffText}</strong><small>${this.escape(diffLabel)}</small></article><article><span>Subjects Passed</span><strong>${this.escape(insights.passes ?? 0)} / ${this.escape(insights.subjects_assessed ?? report.subject_count ?? 0)}</strong><small>40% and above</small></article></section>`;
        },

        calculateInsights(report) {
            const subjects = Array.isArray(report.subjects) ? report.subjects : [], scored = subjects.filter(row => this.optionalNumber(row.total) !== null), strongest = scored.reduce((best, row) => !best || Number(row.total) > Number(best.total) ? row : best, null), focus = scored.reduce((best, row) => !best || Number(row.total) < Number(best.total) ? row : best, null), average = this.optionalNumber(report.average), classAverage = this.optionalNumber(report.class_average);
            return { strongest_subject: strongest?.subject || "", strongest_score: strongest?.total ?? null, focus_subject: focus?.subject || "", focus_score: focus?.total ?? null, average_difference: average !== null && classAverage !== null ? average - classAverage : null, subjects_assessed: subjects.length, passes: scored.filter(row => Number(row.total) >= 40).length };
        },

        // ============================================================
        // THIRD TERM CUMULATIVE SUMMARY
        // ============================================================

        cumulativeStrip(report) {
            if (report.cumulative_average === undefined || report.cumulative_average === null) return "";
            return `<section class="emis-cumulative-strip"><div><span>1st Term Average</span><strong>${this.num(report.first_term_average)}%</strong></div><div><span>2nd Term Average</span><strong>${this.num(report.second_term_average)}%</strong></div><div><span>3rd Term Average</span><strong>${this.num(report.third_term_average ?? report.average)}%</strong></div><div><span>Annual Average</span><strong>${this.num(report.cumulative_average)}%</strong></div><div><span>Annual Grade</span><strong>${this.escape(report.cumulative_grade || "—")}</strong></div><div><span>Annual Position</span><strong>${this.escape(report.cumulative_position_text || report.cumulative_position || "—")} / ${this.escape(report.cumulative_out_of || "—")}</strong></div></section>`;
        },

        // ============================================================
        // ATTENDANCE + AFFECTIVE / PSYCHOMOTOR RATINGS
        // ============================================================

        traitsAndAttendance(report) {
            const attendance = report.attendance || {}, affective = report.affective || {}, psychomotor = report.psychomotor || {};
            return `<section class="emis-development-grid"><article class="emis-development-card attendance-card"><h3><i class="fa-solid fa-calendar-check"></i> Attendance</h3><div class="emis-attendance-grid"><p><span>Days School Open</span><strong>${this.escape(attendance.days_open ?? 0)}</strong></p><p><span>Present / Credit</span><strong>${this.escape(attendance.present_credit ?? attendance.present ?? 0)}</strong></p><p><span>Absent</span><strong>${this.escape(attendance.absent_total ?? attendance.absent ?? 0)}</strong></p><p><span>Late</span><strong>${this.escape(attendance.late ?? 0)}</strong></p><p><span>Excused</span><strong>${this.escape(attendance.excused ?? 0)}</strong></p><p><span>Attendance %</span><strong>${this.num(attendance.attendance_percentage, 1)}%</strong></p></div></article><article class="emis-development-card"><h3><i class="fa-solid fa-heart"></i> Affective Traits</h3><div class="emis-trait-list">${Object.entries(AFFECTIVE_LABELS).map(([key, label]) => `<span><em>${this.escape(label)}</em><strong>${this.rating(affective[key])}</strong></span>`).join("")}</div></article><article class="emis-development-card"><h3><i class="fa-solid fa-person-running"></i> Psychomotor</h3><div class="emis-trait-list">${Object.entries(PSYCHOMOTOR_LABELS).map(([key, label]) => `<span><em>${this.escape(label)}</em><strong>${this.rating(psychomotor[key])}</strong></span>`).join("")}</div><div class="emis-rating-scale"><strong>Rating Scale</strong><span>6 Excel • 5 Excellent • 4 Good • 3 Fair • 2 Poor • 1 Not Observed</span></div></article></section>`;
        },

        // ============================================================
        // OFFICIAL REMARKS / NEXT TERM
        // ============================================================

        remarks(report, payload) {
            const formTeacher = report.form_teacher || payload.form_teacher || "—", nextTerm = report.next_term || payload.next_term || "—";
            return `<section class="emis-report-remarks"><div class="emis-remark-main"><div class="emis-remark-row"><span>Form Teacher</span><strong>${this.escape(formTeacher)}</strong></div><div class="emis-remark-row"><span>Form Teacher's Remark</span><strong>${this.escape(report.teacher_remark || "—")}</strong></div><div class="emis-remark-row"><span>Principal's Remark</span><strong>${this.escape(report.principal_remark || "—")}</strong></div><div class="emis-remark-row"><span>Next Term Begins</span><strong>${this.escape(this.dateLabel(nextTerm))}</strong></div></div><div class="emis-report-signatures"><div><span>Form Teacher</span><i></i></div><div><span>Principal</span><i></i></div></div></section>`;
        },

        // ============================================================
        // FOOTER / VERIFICATION NOTE
        // ============================================================

        footer(report) { const mode = String(report.source_mode || "auto").toLowerCase(), note = mode === "manual" ? "Generated from teacher-entered manual EMIS report records" : mode === "hybrid" ? "Generated from EMIS automated records with approved manual fallback data" : "Generated from verified EMIS CA/Test, CBT and Attendance records"; return `<footer class="emis-report-footer"><span>EMIS Academic Report • ${this.escape(report.admission_number || "")}</span><strong>${this.escape(note)}</strong></footer>`; },

        // ============================================================
        // FORMAT HELPERS
        // ============================================================

        optionalNumber(value) { if (value === "" || value === null || value === undefined) return null; const number = Number(value); return Number.isFinite(number) ? number : null; },
        score(value) { return this.optionalNumber(value) === null ? "—" : this.num(value); },
        num(value, digits = 2) { const number = this.optionalNumber(value); if (number === null) return "—"; return Number.isInteger(number) ? String(number) : number.toFixed(digits).replace(/0+$/, "").replace(/\.$/, ""); },
        percent(value, digits = 2) { const number = this.optionalNumber(value); return number === null ? "—" : `${this.num(number, digits)}%`; },
        rating(value) { if (value === "" || value === null || value === undefined) return "—"; const n = Number(value); return Number.isFinite(n) && n >= 1 && n <= 6 ? String(Math.round(n)) : "—"; },
        classLabel(value) { return String(value || "—").replace(/_/g, " "); },
        termLabel(value) { const raw = String(value || "").toUpperCase(); if (raw.includes("FIRST") || raw === "1") return "FIRST TERM"; if (raw.includes("SECOND") || raw === "2") return "SECOND TERM"; if (raw.includes("THIRD") || raw === "3") return "THIRD TERM"; return raw || "—"; },
        gradeMeaning(grade) { return { A: "Excellent", B: "Very Good", C: "Good", D: "Pass", E: "Pass", F: "Needs Improvement" }[String(grade || "").toUpperCase()] || "Overall result"; },
        dateLabel(value) { if (!value || value === "—") return "—"; const date = new Date(`${value}T00:00:00`); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }); },
        escape(value) { return String(value ?? "").replace(/[&<>'"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch])); }
    };
})();

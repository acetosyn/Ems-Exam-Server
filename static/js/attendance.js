/* ======================================================================
   attendance_ui.js — EMIS Attendance Studio
   Backend: modules/attendance_manager.py
   ====================================================================== */

(() => {
    "use strict";

    const root = document.getElementById("attendanceStudio");
    if (!root || root.dataset.backendBound === "1") return;
    root.dataset.backendBound = "1";

    const $ = id => document.getElementById(id), $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];

    const API = {
        config: "/api/attendance/config", students: "/api/attendance/students", records: "/api/attendance/records",
        save: "/api/attendance/save", holiday: "/api/attendance/holiday", history: "/api/attendance/history",
        dates: "/api/attendance/dates", summary: "/api/attendance/summary", studentSummary: "/api/attendance/student-summary",
        studentHistory: "/api/attendance/student-history", delete: "/api/attendance/delete"
    };

    const VALID_STATUSES = ["PRESENT", "ABSENT", "LATE", "SICK", "EXCUSED", "UNMARKED"];

    const STATUS_LABELS = {
        PRESENT: "Present", ABSENT: "Absent", LATE: "Late", SICK: "Sick",
        EXCUSED: "Excused", UNMARKED: "Unmarked", HOLIDAY: "Holiday"
    };

    const STATUS_ICONS = {
        PRESENT: "fa-user-check", ABSENT: "fa-user-xmark", LATE: "fa-person-running",
        SICK: "fa-kit-medical", EXCUSED: "fa-handshake-angle", UNMARKED: "fa-clock", HOLIDAY: "fa-umbrella-beach"
    };

    const FALLBACK_ARMS = {
        JSS1: ["JSS1A", "JSS1B", "JSS1C"], JSS2: ["JSS2A", "JSS2B", "JSS2C"], JSS3: ["JSS3A", "JSS3B", "JSS3C"],
        SS1: ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1_B/C"], SS2: ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2_B/C"],
        SS3: ["SS3_GOLD", "SS3_SILVER", "SS3_B/C"]
    };

    const state = {
        students: [], loaded: false, loadedSession: "", loadedTerm: "", loadedLevel: "", loadedArm: "", loadedDate: "",
        saved: false, holiday: false, savedAt: "", existingCount: 0, filter: "ALL", search: "", selected: new Set(),
        dirty: false, activeStudent: null, completionNotified: false,
        history: { records: [], daily: [], students: [], dates: [], summary: {} }, historyLoaded: false
    };

    const els = {
        session: $("sessionSelect"), term: $("termSelect"), level: $("levelSelect"), arm: $("armSelect"), date: $("attendanceDate"),
        load: $("loadStudentsBtn"), refresh: $("refreshAttendanceBtn"), search: $("attendanceSearchInput"), tbody: $("attendanceTableBody"),
        selectAll: $("selectAllStudents"), save: $("saveAttendanceBtn"), overwrite: $("overwriteExisting"), del: $("deleteCurrentAttendanceBtn"),
        allPresent: $("markAllPresentBtn"), allAbsent: $("markAllAbsentBtn"), selectedLate: $("markSelectedLateBtn"),
        selectedSick: $("markSelectedSickBtn"), selectedExcused: $("markSelectedExcusedBtn"), holiday: $("markHolidayBtn"),
        clear: $("clearMarksBtn"), summary: $("viewSummaryBtn"), classHistory: $("viewCurrentClassHistoryBtn"),
        openHistory: $("openHistoryBtn"), printRegister: $("printRegisterBtn"),

        holidayModal: $("holidayConfirmModal"), holidayReason: $("holidayReason"), cancelHoliday: $("cancelHolidayBtn"),
        confirmHoliday: $("confirmHolidayBtn"),

        studentModal: $("attendanceStudentModal"), closeStudent: $("closeStudentModal"), studentHistoryBtn: $("loadStudentHistoryBtn"),
        studentHistoryBody: $("studentHistoryTableBody"),

        historyModal: $("attendanceHistoryModal"), closeHistory: $("closeHistoryModal"), backdrop: $("attendanceModalBackdrop"),
        historyLoad: $("loadHistoryBtn"), historyReset: $("resetHistoryBtn"), historyPrint: $("printHistoryBtn"),
        historyExport: $("exportHistoryCsvBtn"),
        deleteModal: $("attendanceDeleteModal"), closeDeleteModal: $("closeDeleteAttendanceModal"), cancelDelete: $("cancelDeleteAttendanceBtn"),
        confirmDelete: $("confirmDeleteAttendanceBtn"), deleteTarget: $("deleteAttendanceTarget"),

        historySession: $("historySessionSelect"), historyTerm: $("historyTermSelect"), historyLevel: $("historyLevelSelect"),
        historyArm: $("historyArmSelect"), historyStart: $("historyStartDate"), historyEnd: $("historyEndDate"),
        historyStatus: $("historyStatusSelect"), historySearch: $("historySearchInput")
    };

    let classArms = parseClassArms();
    let pendingDelete = null;


    // ============================================================
    // BASIC HELPERS
    // ============================================================

    function parseClassArms() {
        try {
            const node = $("classArmsData"), parsed = node ? JSON.parse(node.textContent || "{}") : {};
            return parsed && typeof parsed === "object" && Object.keys(parsed).length ? parsed : FALLBACK_ARMS;
        } catch (_) { return FALLBACK_ARMS; }
    }

    function esc(value) {
        return String(value ?? "").replace(/[&<>'"]/g, ch => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
        }[ch]));
    }

    function clean(value) { return String(value ?? "").trim(); }

    function upper(value) { return clean(value).toUpperCase(); }

    function canonicalTerm(value) {
        const raw = upper(value).replace(/[_-]+/g, " ").replace(/\s+/g, " ");

        if (["FIRST", "FIRST TERM", "1", "1ST", "1ST TERM", "TERM 1"].includes(raw)) return "FIRST";
        if (["SECOND", "SECOND TERM", "2", "2ND", "2ND TERM", "TERM 2"].includes(raw)) return "SECOND";
        if (["THIRD", "THIRD TERM", "3", "3RD", "3RD TERM", "TERM 3"].includes(raw)) return "THIRD";

        return "";
    }

    function termLabel(value) {
        return { FIRST: "FIRST TERM", SECOND: "SECOND TERM", THIRD: "THIRD TERM" }[canonicalTerm(value)] || upper(value) || "—";
    }

    function todayISO() {
        const d = new Date(), offset = d.getTimezoneOffset();
        return new Date(d.getTime() - offset * 60000).toISOString().slice(0, 10);
    }

    function humanDate(value) {
        if (!value) return "—";

        const d = new Date(`${value}T00:00:00`);

        return Number.isNaN(d.getTime())
            ? value
            : d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
    }

    function humanDateTime(value) {
        if (!value) return "Not saved";

        const d = new Date(String(value).replace(" ", "T"));

        return Number.isNaN(d.getTime())
            ? value
            : d.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    }

    function armLabel(value) { return clean(value).replace(/_/g, " "); }

    function initials(name) {
        const parts = clean(name).split(/\s+/).filter(Boolean);
        return (parts[0]?.[0] || "S") + (parts[1]?.[0] || parts[0]?.[1] || "T");
    }

    function query(params) {
        const q = new URLSearchParams();

        Object.entries(params || {}).forEach(([key, value]) => {
            if (value !== undefined && value !== null && String(value) !== "") q.set(key, value);
        });

        return q.toString();
    }

    function setText(id, value) {
        const node = $(id);
        if (node) node.textContent = value ?? "";
    }


    // ============================================================
    // API
    // ============================================================

    async function api(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                ...(options.body ? { "Content-Type": "application/json" } : {}),
                ...(options.headers || {})
            },
            ...options
        });

        let data = {};

        try { data = await response.json(); }
        catch (_) { data = {}; }

        if (!response.ok) {
            const error = new Error(data.message || data.error || `Request failed (${response.status})`);
            error.status = response.status;
            error.data = data;
            throw error;
        }

        return data;
    }


    // ============================================================
    // TOAST / BUTTON / MODAL
    // ============================================================

    function toast(message, type = "info", timeout = 3800, title = "") {
        const host = $("attendanceToastHost");
        if (!host) return;

        const config = {
            success: { icon: "fa-circle-check", title: "Success" }, complete: { icon: "fa-circle-check", title: "Class Complete" },
            warning: { icon: "fa-triangle-exclamation", title: "Attention" }, error: { icon: "fa-circle-xmark", title: "Something Went Wrong" },
            info: { icon: "fa-circle-info", title: "Attendance Update" }
        };

        const current = config[type] || config.info, item = document.createElement("div");
        item.className = `attendance-toast ${type}`;
        item.innerHTML = `<div class="attendance-toast-icon"><i class="fa-solid ${current.icon}"></i></div><div class="attendance-toast-content"><strong>${esc(title || current.title)}</strong><span>${esc(message)}</span></div><button type="button" class="attendance-toast-close" aria-label="Close notification"><i class="fa-solid fa-xmark"></i></button><span class="attendance-toast-progress"></span>`;

        host.querySelectorAll(".attendance-toast").forEach(old => { old.classList.add("leaving"); setTimeout(() => old.remove(), 180); });
        host.appendChild(item);
        item.style.setProperty("--toast-duration", `${timeout}ms`);

        const dismiss = () => { if (!item.isConnected || item.classList.contains("leaving")) return; item.classList.add("leaving"); setTimeout(() => item.remove(), 220); };
        item.querySelector(".attendance-toast-close")?.addEventListener("click", dismiss);
        requestAnimationFrame(() => item.classList.add("show"));
        setTimeout(dismiss, timeout);
    }

    function setButtonLoading(button, loading, text = "") {
        if (!button) return;

        if (loading) {
            if (!button.dataset.originalHtml) button.dataset.originalHtml = button.innerHTML;

            button.disabled = true;
            button.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${esc(text || "Loading...")}`;
        } else {
            button.disabled = false;

            if (button.dataset.originalHtml) {
                button.innerHTML = button.dataset.originalHtml;
                delete button.dataset.originalHtml;
            }
        }
    }

    function toggleModal(modal, open) {
        if (!modal) return;

        modal.setAttribute("aria-hidden", open ? "false" : "true");
        modal.classList.toggle("active", open);
        modal.classList.toggle("open", open);
        modal.classList.toggle("show", open);

        if (els.backdrop) {
            const anyOpen = open || [els.holidayModal, els.studentModal, els.historyModal, els.deleteModal].some(
                item => item && item !== modal && item.getAttribute("aria-hidden") === "false"
            );

            els.backdrop.classList.toggle("active", anyOpen);
            els.backdrop.classList.toggle("show", anyOpen);
        }

        document.body.classList.toggle(
            "attendance-modal-open",
            [els.holidayModal, els.studentModal, els.historyModal].some(item => item && item.getAttribute("aria-hidden") === "false")
        );
    }

  // ============================================================
// CLOSE ALL ATTENDANCE MODALS
// ============================================================

function closeAllModals() {
    [els.holidayModal, els.studentModal, els.historyModal, els.deleteModal].forEach(modal => {
        if (!modal) return;
        modal.setAttribute("aria-hidden", "true");
        modal.classList.remove("active", "open", "show");
    });

    if (els.backdrop) els.backdrop.classList.remove("active", "show");

    document.body.classList.remove("attendance-modal-open");

    pendingDelete = null;
}

    // ============================================================
    // CLASS / CONTEXT
    // ============================================================

    function currentContext() {
        return {
            session: clean(els.session?.value), term: clean(els.term?.value), class_level: clean(els.level?.value),
            class_arm: clean(els.arm?.value), date: clean(els.date?.value)
        };
    }

    function loadedContextMatches() {
        const c = currentContext();

        return state.loaded
            && c.session === state.loadedSession
            && canonicalTerm(c.term) === canonicalTerm(state.loadedTerm)
            && c.class_level === state.loadedLevel
            && c.class_arm === state.loadedArm
            && c.date === state.loadedDate;
    }

    function armsForLevel(level) {
        let values = classArms?.[level];

        if (!Array.isArray(values) || !values.length) values = FALLBACK_ARMS[level] || [];

        return values.map(item => {
            if (typeof item === "string") return item;
            return item?.value || item?.arm || item?.class_arm || "";
        }).filter(Boolean);
    }

    function populateArmSelect(levelSelect, armSelect, preferred = "") {
        if (!armSelect) return;

        const level = clean(levelSelect?.value), arms = armsForLevel(level);

        armSelect.innerHTML = `<option value="">Select arm</option>${
            arms.map(arm => `<option value="${esc(arm)}">${esc(armLabel(arm))}</option>`).join("")
        }`;

        if (preferred && arms.includes(preferred)) armSelect.value = preferred;
    }

    function syncChips() {
        setText("chipSession", clean(els.session?.value) || "—");
        setText("chipTerm", termLabel(els.term?.value));
        setText("activeDateChip", humanDate(els.date?.value));

        if (!state.loaded || !loadedContextMatches()) {
            setText("loadedClassChip", state.loadedArm ? armLabel(state.loadedArm) : "None");

            if (!state.dirty) setText("reportReadyChip", "Waiting");
        }
    }

    function setDirty(value = true) {
        state.dirty = value;

        if (value) {
            setText("chipTimestamp", "Unsaved changes");
            setText("reportReadyChip", "Unsaved");
        } else if (state.savedAt) setText("chipTimestamp", humanDateTime(state.savedAt));
    }

    function resetLoadedState(message = "Select class and load students") {
        state.students = [];
        state.loaded = false;
        state.loadedSession = "";
        state.loadedTerm = "";
        state.loadedLevel = "";
        state.loadedArm = "";
        state.loadedDate = "";
        state.saved = false;
        state.holiday = false;
        state.savedAt = "";
        state.existingCount = 0;
        state.selected.clear();
        state.dirty = false;
        state.completionNotified = false;

        if (els.tbody) {
            els.tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="9">
                        <div class="attendance-empty-state">
                            <i class="fa-solid fa-calendar-check"></i>
                            <h3>${esc(message)}</h3>
                            <p>Select session, term, class level and class arm, then click Load Class.</p>
                        </div>
                    </td>
                </tr>
            `;
        }

        if (els.save) els.save.disabled = true;
        if (els.del) els.del.disabled = true;
        if (els.selectAll) els.selectAll.checked = false;

        ["presentCount", "absentCount", "lateCount", "sickCount", "pendingCount", "totalCount", "selectedCount"]
            .forEach(id => setText(id, "0"));

        setText("existingRecordCount", "0");
        setText("chipTimestamp", "Not saved");
        setText("reportReadyChip", "Waiting");
        setText("loadedClassChip", "None");
        setText("registerTitle", "Select class and load students");

        syncChips();
    }


    // ============================================================
    // STUDENT TABLE
    // ============================================================

    function studentByAdmission(admission) {
        const key = clean(admission).toLowerCase();
        return state.students.find(student => clean(student.admission_number).toLowerCase() === key) || null;
    }

    function statusClass(status) { return upper(status || "UNMARKED").toLowerCase(); }

    function renderStudents() {
        if (!els.tbody) return;

        if (!state.students.length) {
            els.tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="9">
                        <div class="attendance-empty-state">
                            <i class="fa-solid ${state.holiday ? "fa-umbrella-beach" : "fa-users-slash"}"></i>
                            <h3>${state.holiday ? "School Holiday" : "No students found"}</h3>
                            <p>${
                                state.holiday
                                    ? `This date is saved as a holiday${state.savedAt ? ` (${esc(humanDateTime(state.savedAt))})` : ""}. Enable overwrite if you need to replace it with normal attendance.`
                                    : "No active students were returned for this class arm."
                            }</p>
                        </div>
                    </td>
                </tr>
            `;

            updateCounters();
            return;
        }

        els.tbody.innerHTML = state.students.map((student, index) => {
            const status = upper(student.attendance_status || student.status || "UNMARKED");
            const selected = state.selected.has(clean(student.admission_number));

            return `
                <tr class="attendance-student-row status-${statusClass(status)}" data-admission="${esc(student.admission_number)}">
                    <td>
                        <input type="checkbox" class="student-select" ${selected ? "checked" : ""} aria-label="Select ${esc(student.full_name)}">
                    </td>

                    <td class="student-serial">${index + 1}</td>

                    <td>
                        <button type="button" class="student-profile-link" data-action="profile">
                            <strong>${esc(student.full_name || "Student")}</strong>
                        </button>
                    </td>

                    <td>${esc(student.admission_number || "—")}</td>
                    <td>${esc(armLabel(student.class_arm || student.class || state.loadedArm))}</td>

                    <td>
                        <select class="attendance-status-select" aria-label="Attendance status">
                            ${VALID_STATUSES.map(item => `
                                <option value="${item}" ${item === status ? "selected" : ""}>
                                    ${STATUS_LABELS[item]}
                                </option>
                            `).join("")}
                        </select>
                    </td>

                    <td>
                        <input type="text" class="attendance-reason-input" value="${esc(student.reason || "")}" placeholder="Optional reason">
                    </td>

                    <td>
                        <input type="text" class="attendance-note-input" value="${esc(student.note || "")}" placeholder="Optional note">
                    </td>

                    <td>
                        <div class="attendance-row-marks">
                            ${["PRESENT", "ABSENT", "LATE", "SICK", "EXCUSED"].map(item => `
                                <button type="button"
                                        class="attendance-mark-btn ${statusClass(item)} ${item === status ? "active" : ""}"
                                        data-action="mark"
                                        data-status="${item}"
                                        title="${STATUS_LABELS[item]}">
                                    <i class="fa-solid ${STATUS_ICONS[item]}"></i>
                                </button>
                            `).join("")}
                        </div>
                    </td>
                </tr>
            `;
        }).join("");

        applyFilters();
        updateCounters();
        updateSelectionUI();
    }

    function readRowIntoStudent(row) {
        const student = studentByAdmission(row?.dataset.admission);
        if (!student || !row) return;

        student.status = upper(row.querySelector(".attendance-status-select")?.value || "UNMARKED");
        student.attendance_status = student.status;
        student.reason = clean(row.querySelector(".attendance-reason-input")?.value);
        student.note = clean(row.querySelector(".attendance-note-input")?.value);
    }

    function setStudentStatus(student, status, checkCompletion = true) {
        if (!student || !VALID_STATUSES.includes(status)) return;

        student.status = status;
        student.attendance_status = status;

        const row = els.tbody?.querySelector(`tr[data-admission="${CSS.escape(student.admission_number)}"]`);
        if (row) {
            const select = row.querySelector(".attendance-status-select");
            if (select) select.value = status;
            row.className = `attendance-student-row status-${statusClass(status)}`;
            row.querySelectorAll(".attendance-mark-btn").forEach(button => button.classList.toggle("active", button.dataset.status === status));
        }

        if (checkCompletion) checkClassCompletion();
    }

    function checkClassCompletion() {
        if (!state.loaded || !state.students.length) return false;

        const remaining = state.students.filter(student => upper(student.attendance_status || student.status || "UNMARKED") === "UNMARKED").length;
        if (remaining > 0) { state.completionNotified = false; return false; }
        if (state.completionNotified) return true;

        state.completionNotified = true;
        toast(`All ${state.students.length} students in ${armLabel(state.loadedArm)} have now been marked. You can save the attendance register.`, "complete", 5200, "Class Fully Marked");
        return true;
    }



    function updateCounters() {
        const counts = { PRESENT: 0, ABSENT: 0, LATE: 0, SICK: 0, EXCUSED: 0, UNMARKED: 0 };

        state.students.forEach(student => {
            const status = upper(student.attendance_status || student.status || "UNMARKED");
            counts[VALID_STATUSES.includes(status) ? status : "UNMARKED"]++;
        });

        setText("presentCount", counts.PRESENT);
        setText("absentCount", counts.ABSENT);
        setText("lateCount", counts.LATE);
        setText("sickCount", counts.SICK);
        setText("pendingCount", counts.UNMARKED);
        setText("totalCount", state.students.length);
        setText("selectedCount", state.selected.size);
    }

    function updateSelectionUI() {
        setText("selectedCount", state.selected.size);

        const visible = $$("tr.attendance-student-row", els.tbody).filter(row => !row.hidden);
        const selectedVisible = visible.filter(row => row.querySelector(".student-select")?.checked);

        if (els.selectAll) {
            els.selectAll.checked = visible.length > 0 && selectedVisible.length === visible.length;
            els.selectAll.indeterminate = selectedVisible.length > 0 && selectedVisible.length < visible.length;
        }
    }

    function applyFilters() {
        const search = clean(state.search).toLowerCase();
        const filter = upper(state.filter || "ALL");

        $$("tr.attendance-student-row", els.tbody).forEach(row => {
            const student = studentByAdmission(row.dataset.admission);
            const status = upper(student?.attendance_status || student?.status || "UNMARKED");

            const haystack = `
                ${student?.full_name || ""}
                ${student?.admission_number || ""}
                ${student?.class_arm || ""}
                ${status}
                ${student?.reason || ""}
                ${student?.note || ""}
            `.toLowerCase();

            row.hidden = !(
                (filter === "ALL" || status === filter)
                && (!search || haystack.includes(search))
            );
        });

        updateSelectionUI();
    }

    function currentPayload() {
        state.students.forEach(student => {
            const row = els.tbody?.querySelector(`tr[data-admission="${CSS.escape(student.admission_number)}"]`);
            if (row) readRowIntoStudent(row);
        });

        return {
            session: state.loadedSession, term: state.loadedTerm, class_level: state.loadedLevel,
            class_arm: state.loadedArm, date: state.loadedDate, overwrite: !!els.overwrite?.checked,

            records: state.students.map(student => ({
                admission_number: student.admission_number,
                status: upper(student.attendance_status || student.status || "UNMARKED"),
                reason: clean(student.reason), note: clean(student.note)
            }))
        };
    }


    // ============================================================
    // MAIN CLASS LOAD
    // ============================================================

    function validateMainSelection() {
        const c = currentContext();

        if (!c.session) return toast("Select an academic session.", "warning"), false;
        if (!canonicalTerm(c.term)) return toast("Select a valid term.", "warning"), false;
        if (!c.class_level) return toast("Select a class level.", "warning"), false;
        if (!c.class_arm) return toast("Select a class arm.", "warning"), false;
        if (!c.date) return toast("Select an attendance date.", "warning"), false;

        return true;
    }

    async function loadClass({ quiet = false } = {}) {
        if (!validateMainSelection()) return;

        const c = currentContext();

        setButtonLoading(els.load, true, "Loading...");

        try {
            const recordsUrl = `${API.records}?${query({
                session: c.session, term: c.term, class_level: c.class_level,
                class_arm: c.class_arm, date: c.date
            })}`;

            const [records, summary, dates] = await Promise.all([
                api(recordsUrl),

                api(`${API.summary}?${query({
                    session: c.session, term: c.term,
                    class_level: c.class_level, class_arm: c.class_arm
                })}`).catch(() => ({ days_open: 0 })),

                api(`${API.dates}?${query({
                    session: c.session, term: c.term,
                    class_level: c.class_level, class_arm: c.class_arm
                })}`).catch(() => ({ count: 0, dates: [] }))
            ]);

            let students = Array.isArray(records.students) ? records.students : [];

            if (records.holiday && !students.length) {
                const roster = await api(`${API.students}?${query({
                    session: c.session, term: c.term,
                    class_level: c.class_level, class_arm: c.class_arm
                })}`).catch(() => ({ students: [] }));

                students = (roster.students || []).map(student => ({
                    ...student, status: "UNMARKED", attendance_status: "UNMARKED",
                    reason: "", note: "", saved_at: ""
                }));
            }

            state.students = students.map(student => ({
                ...student,
                status: upper(student.attendance_status || student.status || "UNMARKED"),
                attendance_status: upper(student.attendance_status || student.status || "UNMARKED"),
                reason: clean(student.reason), note: clean(student.note)
            }));

            state.loaded = true;
            state.loadedSession = c.session;
            state.loadedTerm = canonicalTerm(c.term);
            state.loadedLevel = c.class_level;
            state.loadedArm = c.class_arm;
            state.loadedDate = c.date;
            state.saved = !!records.saved;
            state.holiday = !!records.holiday;
            state.savedAt = clean(records.saved_at);

            state.existingCount = Number(
                records.existing_count
                ?? (records.saved ? (records.holiday ? 1 : state.students.length) : 0)
            );

            state.selected.clear();
            state.dirty = false;
            state.completionNotified = state.students.length > 0 && state.students.every(student => upper(student.attendance_status || student.status || "UNMARKED") !== "UNMARKED");

            renderStudents();

            setText("loadedClassChip", armLabel(state.loadedArm));
            setText("registerTitle", `${armLabel(state.loadedArm)} Attendance — ${humanDate(state.loadedDate)}`);

            setText(
                "registerSubtitle",
                state.holiday
                    ? `This date is currently saved as a school holiday${records.reason ? `: ${records.reason}` : "."}`
                    : `${state.students.length} active student${state.students.length === 1 ? "" : "s"} loaded from the EMIS roster.`
            );

            setText("chipTimestamp", state.savedAt ? humanDateTime(state.savedAt) : "Not saved");
            setText("existingRecordCount", state.existingCount);
            setText("daysOpenCount", summary.days_open ?? summary.days_school_open ?? 0);
            setText("savedRecordsCount", dates.count ?? (dates.dates || []).length ?? 0);
            setText("reportReadyChip", Number(summary.days_open ?? summary.days_school_open ?? 0) > 0 ? "Ready" : "Waiting");

            if (els.save) els.save.disabled = !state.students.length;
            if (els.del) els.del.disabled = !state.saved;
            if (els.overwrite && !state.saved) els.overwrite.checked = false;

            syncChips();

            if (!quiet) {
                if (state.holiday) toast(`Holiday record loaded for ${armLabel(state.loadedArm)} on ${humanDate(state.loadedDate)}. Enable overwrite if you need to replace it.`, "warning", 4300, "Holiday Record Loaded");
                else if (state.saved) toast(`${state.students.length} saved attendance record${state.students.length === 1 ? "" : "s"} loaded for ${armLabel(state.loadedArm)}.`, "success", 4000, "Saved Attendance Loaded");
                else toast(`${state.students.length} active student${state.students.length === 1 ? "" : "s"} loaded for ${armLabel(state.loadedArm)}.`, "success", 3600, "Class Loaded");
            }

        } catch (error) {
            resetLoadedState("Could not load attendance");
            toast(error.message || "Could not load attendance.", "error");

        } finally {
            setButtonLoading(els.load, false);
        }
    }


    // ============================================================
    // SAVE ATTENDANCE
    // ============================================================

    async function saveAttendance(forceOverwrite = false) {
        if (!state.loaded || !loadedContextMatches()) {
            return toast("Load the selected class and date before saving.", "warning");
        }

        if (!state.students.length) return toast("There are no students to save.", "warning");

        const payload = currentPayload();

        if (forceOverwrite) payload.overwrite = true;

        setButtonLoading(els.save, true, "Saving...");

        try {
            const data = await api(API.save, {
                method: "POST",
                body: JSON.stringify(payload)
            });

            state.saved = true;
            state.holiday = false;
            state.savedAt = clean(data.saved_at);
            state.existingCount = Number(data.saved_count || state.students.length);
            state.dirty = false;

            if (els.overwrite) els.overwrite.checked = false;
            if (els.del) els.del.disabled = false;

            setText("chipTimestamp", humanDateTime(state.savedAt));
            setText("existingRecordCount", state.existingCount);
            setText("reportReadyChip", "Ready");

            toast(`${state.students.length} attendance record${state.students.length === 1 ? "" : "s"} saved successfully for ${armLabel(state.loadedArm)} on ${humanDate(state.loadedDate)}.`, "success", 4600, "Attendance Saved");

            await refreshDashboardMetrics();

        } catch (error) {
            if (error.status === 409 && error.data?.requires_overwrite) {
                if (window.confirm(`${error.message}\n\nDo you want to overwrite the existing attendance for this date?`)) {
                    if (els.overwrite) els.overwrite.checked = true;

                    setButtonLoading(els.save, false);
                    return saveAttendance(true);
                }

            } else {
                toast(error.message || "Could not save attendance.", "error");
            }

        } finally {
            setButtonLoading(els.save, false);
        }
    }

    async function refreshDashboardMetrics() {
        if (!state.loaded) return;

        try {
            const [summary, dates] = await Promise.all([
                api(`${API.summary}?${query({
                    session: state.loadedSession, term: state.loadedTerm,
                    class_level: state.loadedLevel, class_arm: state.loadedArm
                })}`),

                api(`${API.dates}?${query({
                    session: state.loadedSession, term: state.loadedTerm,
                    class_level: state.loadedLevel, class_arm: state.loadedArm
                })}`)
            ]);

            setText("daysOpenCount", summary.days_open ?? summary.days_school_open ?? 0);
            setText("savedRecordsCount", dates.count ?? 0);
            setText("reportReadyChip", Number(summary.days_open ?? summary.days_school_open ?? 0) > 0 ? "Ready" : "Waiting");

        } catch (_) {
            /* Dashboard refresh is non-critical. */
        }
    }


    // ============================================================
    // BULK MARKING
    // ============================================================

    function selectedStudentsOrWarn() {
        if (!state.selected.size) {
            toast("Select at least one student first.", "warning");
            return [];
        }

        return state.students.filter(student => state.selected.has(clean(student.admission_number)));
    }

    function bulkStatus(status, mode = "selected") {
        if (!state.loaded || !state.students.length) return toast("Load a class first.", "warning");

        const targets = mode === "all" ? state.students : selectedStudentsOrWarn();

        if (!targets.length) return;

        targets.forEach(student => setStudentStatus(student, status, false));

        setDirty(true);
        updateCounters();
        applyFilters();

        const classComplete = checkClassCompletion();
        if (!classComplete) toast(`${targets.length} student${targets.length === 1 ? "" : "s"} marked ${STATUS_LABELS[status].toLowerCase()}.`, "success", 3200, "Attendance Updated");
    }

    function clearMarks() {
        if (!state.loaded || !state.students.length) return toast("Load a class first.", "warning");

        const targets = state.selected.size
            ? state.students.filter(student => state.selected.has(clean(student.admission_number)))
            : state.students;

        targets.forEach(student => {
            setStudentStatus(student, "UNMARKED", false);

            student.reason = "";
            student.note = "";

            const row = els.tbody?.querySelector(`tr[data-admission="${CSS.escape(student.admission_number)}"]`);

            if (row) {
                const reason = row.querySelector(".attendance-reason-input");
                const note = row.querySelector(".attendance-note-input");

                if (reason) reason.value = "";
                if (note) note.value = "";
            }
        });

        state.completionNotified = false;
        setDirty(true);
        updateCounters();
        applyFilters();

        toast(`${targets.length} attendance mark${targets.length === 1 ? "" : "s"} cleared.`, "info", 3200, "Marks Cleared");
    }


   // ============================================================
// DELETE ATTENDANCE
// ============================================================

function requestDeleteAttendance(payload = null, closeHistoryAfter = false) {
    const target = payload || { session: state.loadedSession, term: state.loadedTerm, class_level: state.loadedLevel, class_arm: state.loadedArm, date: state.loadedDate };

    if (!target.session || !target.term || !target.class_level || !target.class_arm || !target.date) return toast("A saved attendance date is required.", "warning");

    pendingDelete = { target, closeHistoryAfter };

    if (els.deleteTarget) els.deleteTarget.innerHTML = `<strong>${esc(armLabel(target.class_arm))}</strong><span>${esc(humanDate(target.date))}</span>`;

    toggleModal(els.deleteModal, true);
}


function cancelDeleteAttendance() {
    pendingDelete = null;
    toggleModal(els.deleteModal, false);
}


async function confirmDeleteAttendance() {
    if (!pendingDelete?.target) return toggleModal(els.deleteModal, false);

    const { target, closeHistoryAfter } = pendingDelete;

    setButtonLoading(els.confirmDelete, true, "Deleting...");

    try {
        await api(API.delete, { method: "POST", body: JSON.stringify(target) });

        const deletingCurrent = state.loaded && target.session === state.loadedSession && canonicalTerm(target.term) === canonicalTerm(state.loadedTerm) && target.class_arm === state.loadedArm && target.date === state.loadedDate;

        pendingDelete = null;
        toggleModal(els.deleteModal, false);

        toast(`Saved attendance for ${armLabel(target.class_arm)} on ${humanDate(target.date)} was deleted successfully.`, "success", 4200, "Attendance Deleted");

        if (deletingCurrent) await loadClass({ quiet: true });

        await refreshDashboardMetrics();

        if (state.historyLoaded) await loadHistory();
        if (closeHistoryAfter) toggleModal(els.historyModal, false);

    } catch (error) {
        toast(error.message || "Could not delete attendance.", "error");

    } finally {
        setButtonLoading(els.confirmDelete, false);
    }
}

    // ============================================================
    // HOLIDAY
    // ============================================================

    async function saveHoliday(forceOverwrite = false) {
        if (!validateMainSelection()) return;

        const c = currentContext();

        const payload = {
            ...c,
            overwrite: forceOverwrite || !!els.overwrite?.checked,
            reason: clean(els.holidayReason?.value) || "School Holiday"
        };

        setButtonLoading(els.confirmHoliday, true, "Saving...");

        try {
            const data = await api(API.holiday, {
                method: "POST",
                body: JSON.stringify(payload)
            });

            toggleModal(els.holidayModal, false);
            toast(`${armLabel(c.class_arm)} has been saved as a school holiday for ${humanDate(c.date)}.`, "success", 4300, "Holiday Saved");

            if (els.holidayReason) els.holidayReason.value = "";

            await loadClass({ quiet: true });

        } catch (error) {
            if (error.status === 409 && error.data?.requires_overwrite) {
                if (window.confirm(`${error.message}\n\nReplace the existing record with a holiday?`)) {
                    if (els.overwrite) els.overwrite.checked = true;

                    setButtonLoading(els.confirmHoliday, false);
                    return saveHoliday(true);
                }

            } else {
                toast(error.message || "Could not save holiday.", "error");
            }

        } finally {
            setButtonLoading(els.confirmHoliday, false);
        }
    }


    // ============================================================
    // STUDENT PROFILE
    // ============================================================

    async function openStudentProfile(student) {
        if (!student) return;

        state.activeStudent = student;

        toggleModal(els.studentModal, true);

        setText("modalStudentAvatar", initials(student.full_name).toUpperCase());
        setText("modalStudentName", student.full_name || "Student");
        setText("modalStudentAdmission", student.admission_number || "—");
        setText("modalStudentClass", armLabel(student.class_arm || state.loadedArm));

        setText(
            "modalStudentStatus",
            STATUS_LABELS[upper(student.attendance_status || student.status || "UNMARKED")] || "Unmarked"
        );

        setText("modalStudentReason", student.reason || "—");
        setText("modalStudentNote", student.note || "—");

        setText("modalStudentDaysOpen", "…");
        setText("modalStudentDaysPresent", "…");
        setText("modalStudentDaysAbsent", "…");
        setText("modalStudentPercent", "…");

        if (els.studentHistoryBody) {
            els.studentHistoryBody.innerHTML = `
                <tr>
                    <td colspan="5">Click Load Full History to view this student’s saved attendance.</td>
                </tr>
            `;
        }

        try {
            const data = await api(`${API.studentSummary}?${query({
                admission_number: student.admission_number,
                session: state.loadedSession, term: state.loadedTerm,
                class_level: state.loadedLevel, class_arm: state.loadedArm
            })}`);

            const summary = data.summary || data;

            setText("modalStudentDaysOpen", summary.days_open ?? summary.days_school_open ?? 0);
            setText("modalStudentDaysPresent", summary.days_present ?? summary.present_credit ?? summary.present ?? 0);
            setText("modalStudentDaysAbsent", summary.days_absent ?? summary.absent_total ?? summary.absent ?? 0);
            setText("modalStudentPercent", `${Number(summary.attendance_percentage || 0).toFixed(1)}%`);

        } catch (_) {
            setText("modalStudentDaysOpen", "—");
            setText("modalStudentDaysPresent", "—");
            setText("modalStudentDaysAbsent", "—");
            setText("modalStudentPercent", "—");
        }
    }

    async function loadStudentHistory() {
        const student = state.activeStudent;

        if (!student) return;

        setButtonLoading(els.studentHistoryBtn, true, "Loading...");

        try {
            const data = await api(`${API.studentHistory}?${query({
                admission_number: student.admission_number,
                session: state.loadedSession,
                term: state.loadedTerm
            })}`);

            const records = data.records || [];

            if (!els.studentHistoryBody) return;

            els.studentHistoryBody.innerHTML = records.length
                ? records.map(row => `
                    <tr>
                        <td>${esc(humanDate(row.date))}</td>
                        <td>${esc(row.day || "—")}</td>

                        <td>
                            <span class="attendance-status-badge ${statusClass(row.status)}">
                                ${esc(STATUS_LABELS[row.status] || row.status)}
                            </span>
                        </td>

                        <td>${esc(row.reason || "—")}</td>
                        <td>${esc(row.note || "—")}</td>
                    </tr>
                `).join("")
                : `<tr><td colspan="5">No saved attendance history found for this student.</td></tr>`;

            toast(records.length ? `${records.length} saved attendance record${records.length === 1 ? "" : "s"} loaded for ${student.full_name}.` : `No saved attendance history was found for ${student.full_name}.`, records.length ? "success" : "info", 3600, "Student History");

        } catch (error) {
            toast(error.message || "Could not load student history.", "error");

        } finally {
            setButtonLoading(els.studentHistoryBtn, false);
        }
    }


    // ============================================================
    // HISTORY MODAL
    // ============================================================

    function copyMainContextToHistory() {
        if (els.historySession) els.historySession.value = clean(els.session?.value);
        if (els.historyTerm) els.historyTerm.value = clean(els.term?.value);
        if (els.historyLevel) els.historyLevel.value = clean(els.level?.value);

        populateArmSelect(els.historyLevel, els.historyArm, clean(els.arm?.value));
    }

    function openHistory({ tab = "records", useCurrent = true, autoLoad = true } = {}) {
        if (useCurrent) copyMainContextToHistory();

        toggleModal(els.historyModal, true);
        switchHistoryTab(tab);

        if (autoLoad && clean(els.historyLevel?.value) && clean(els.historyArm?.value)) loadHistory();
    }

    function historyContext() {
        return {
            session: clean(els.historySession?.value), term: clean(els.historyTerm?.value),
            class_level: clean(els.historyLevel?.value), class_arm: clean(els.historyArm?.value),
            start_date: clean(els.historyStart?.value), end_date: clean(els.historyEnd?.value),
            status: clean(els.historyStatus?.value), search: clean(els.historySearch?.value)
        };
    }

    async function loadHistory() {
        const c = historyContext();

        if (!c.class_level) return toast("Select a history class level.", "warning");
        if (!c.class_arm) return toast("Select a history class arm.", "warning");

        setButtonLoading(els.historyLoad, true, "Loading...");

        try {
            const data = await api(`${API.history}?${query(c)}`);

            state.history.records = data.records || [];
            state.history.daily = data.daily_breakdown || data.daily || [];
            state.history.students = data.student_breakdown || data.students || [];
            state.history.dates = data.saved_dates || data.dates || [];
            state.history.summary = data.summary || {};
            state.historyLoaded = true;

            renderHistory();

            toast(`${state.history.records.length} saved attendance record${state.history.records.length === 1 ? "" : "s"} loaded for ${armLabel(c.class_arm)}.`, "success", 4000, "History Loaded");

        } catch (error) {
            toast(error.message || "Could not load attendance history.", "error");

        } finally {
            setButtonLoading(els.historyLoad, false);
        }
    }

    function renderHistory() {
        const summary = state.history.summary || {};

        setText("historyTotalRecords", summary.total_records ?? state.history.records.length);
        setText("historyDaysOpen", summary.days_open ?? summary.days_school_open ?? 0);
        setText("historyPresent", summary.present ?? 0);
        setText("historyAbsent", summary.absent ?? 0);
        setText("historyLate", summary.late ?? 0);
        setText("historySick", summary.sick ?? 0);
        setText("historyExcused", summary.excused ?? 0);
        setText("historyHoliday", summary.holiday ?? 0);


        // --------------------------------------------------------
        // RAW RECORDS
        // --------------------------------------------------------

        const recordsBody = $("historyRecordsBody");

        if (recordsBody) {
            recordsBody.innerHTML = state.history.records.length
                ? state.history.records.map(row => `
                    <tr>
                        <td>${esc(humanDate(row.date))}</td>
                        <td>${esc(row.day || "—")}</td>
                        <td>${esc(row.week || "—")}</td>
                        <td>${esc(row.full_name || (row.status === "HOLIDAY" ? "School Holiday" : "—"))}</td>
                        <td>${esc(row.admission_number || "—")}</td>
                        <td>${esc(armLabel(row.class_arm || row.class || ""))}</td>

                        <td>
                            <span class="attendance-status-badge ${statusClass(row.status)}">
                                ${esc(STATUS_LABELS[row.status] || row.status)}
                            </span>
                        </td>

                        <td>${esc(row.reason || "—")}</td>
                        <td>${esc(row.note || "—")}</td>
                        <td>${esc(humanDateTime(row.saved_at))}</td>
                    </tr>
                `).join("")
                : `<tr><td colspan="10">No attendance records match the selected filters.</td></tr>`;
        }


        // --------------------------------------------------------
        // DAILY BREAKDOWN
        // --------------------------------------------------------

        const dailyBody = $("historyDailyBody");

        if (dailyBody) {
            dailyBody.innerHTML = state.history.daily.length
                ? state.history.daily.map(row => `
                    <tr>
                        <td>${esc(humanDate(row.date))}</td>
                        <td>${esc(row.day || "—")}</td>
                        <td>${esc(row.month || "—")}</td>
                        <td>${esc(row.week || "—")}</td>
                        <td>${esc(row.records ?? row.total ?? 0)}</td>
                        <td>${esc(row.present || 0)}</td>
                        <td>${esc(row.absent || 0)}</td>
                        <td>${esc(row.late || 0)}</td>
                        <td>${esc(row.sick || 0)}</td>
                        <td>${row.holiday ? "Yes" : "No"}</td>
                    </tr>
                `).join("")
                : `<tr><td colspan="10">No daily breakdown available.</td></tr>`;
        }


        // --------------------------------------------------------
        // STUDENT SUMMARY
        // --------------------------------------------------------

        const studentsBody = $("historyStudentsBody");

        if (studentsBody) {
            studentsBody.innerHTML = state.history.students.length
                ? state.history.students.map(row => `
                    <tr>
                        <td>${esc(row.full_name || "—")}</td>
                        <td>${esc(row.admission_number || "—")}</td>
                        <td>${esc(armLabel(row.class_arm || row.class || ""))}</td>
                        <td>${esc(row.days_open ?? row.days_school_open ?? 0)}</td>
                        <td>${esc(row.days_present ?? row.present_credit ?? row.present ?? 0)}</td>
                        <td>${esc(row.days_absent ?? row.absent_total ?? row.absent ?? 0)}</td>
                        <td>${esc(row.days_late ?? row.late ?? 0)}</td>
                        <td>${esc(row.days_sick ?? row.sick ?? 0)}</td>
                        <td>${esc(row.attendance_score ?? row.present_credit ?? 0)}</td>
                        <td>${Number(row.attendance_percentage || 0).toFixed(1)}%</td>
                    </tr>
                `).join("")
                : `<tr><td colspan="10">No student summary available.</td></tr>`;
        }


        // --------------------------------------------------------
        // SAVED DATES
        // --------------------------------------------------------

        const datesBody = $("historyDatesBody");

        if (datesBody) {
            datesBody.innerHTML = state.history.dates.length
                ? state.history.dates.map(row => `
                    <tr>
                        <td>${esc(humanDate(row.date))}</td>
                        <td>${esc(row.day || "—")}</td>
                        <td>${esc(row.month || "—")}</td>
                        <td>${esc(row.week || "—")}</td>
                        <td>${esc(row.records ?? row.total ?? 0)}</td>
                        <td>${esc(row.present || 0)}</td>
                        <td>${esc(row.absent || 0)}</td>
                        <td>${esc(row.late || 0)}</td>
                        <td>${esc(row.sick || 0)}</td>

                        <td>
                            <div class="history-row-actions">
                                <button type="button"
                                        class="attendance-icon-btn load-date"
                                        data-date="${esc(row.date)}"
                                        title="Load date">
                                    <i class="fa-solid fa-folder-open"></i>
                                </button>

                                <button type="button"
                                        class="attendance-icon-btn delete-date"
                                        data-date="${esc(row.date)}"
                                        title="Delete date">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `).join("")
                : `<tr><td colspan="10">No saved dates available.</td></tr>`;
        }
    }

    function switchHistoryTab(tab) {
        $$(".history-tab").forEach(button => {
            button.classList.toggle("active", button.dataset.historyTab === tab);
        });

        const map = {
            records: "historyRecordsPanel",
            daily: "historyDailyPanel",
            students: "historyStudentsPanel",
            dates: "historyDatesPanel"
        };

        Object.entries(map).forEach(([key, id]) => {
            $(id)?.classList.toggle("active", key === tab);
        });
    }

    function resetHistoryFilters() {
        if (els.historySession) els.historySession.value = clean(els.session?.value) || "";
        if (els.historyTerm) els.historyTerm.value = clean(els.term?.value) || "";
        if (els.historyLevel) els.historyLevel.value = clean(els.level?.value) || "";

        populateArmSelect(els.historyLevel, els.historyArm, clean(els.arm?.value));

        if (els.historyStart) els.historyStart.value = "";
        if (els.historyEnd) els.historyEnd.value = "";
        if (els.historyStatus) els.historyStatus.value = "";
        if (els.historySearch) els.historySearch.value = "";

        state.history = { records: [], daily: [], students: [], dates: [], summary: {} };
        state.historyLoaded = false;

        renderHistory();
        toast("History filters have been reset.", "info", 2800, "Filters Reset");
    }


    // ============================================================
    // HISTORY CSV EXPORT
    // ============================================================

    function exportHistoryCsv() {
        const rows = state.history.records;

        if (!rows.length) return toast("Load attendance history before exporting.", "warning");

        const headers = [
            "Date", "Day", "Week", "Session", "Term", "Class", "Admission Number",
            "Student", "Status", "Reason", "Note", "Saved At", "Record Type"
        ];

        const csvRows = [
            headers,

            ...rows.map(row => [
                row.date, row.day, row.week, row.session, row.term_label || row.term,
                row.class_arm || row.class, row.admission_number, row.full_name,
                row.status, row.reason, row.note, row.saved_at, row.record_type
            ])
        ];

        const text = csvRows
            .map(row => row.map(value => `"${String(value ?? "").replace(/"/g, '""')}"`).join(","))
            .join("\r\n");

        const blob = new Blob(["\ufeff" + text], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = `attendance_${clean(els.historyArm?.value) || "history"}_${Date.now()}.csv`;

        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(url);
        toast(`${rows.length} attendance record${rows.length === 1 ? "" : "s"} exported successfully.`, "success", 3600, "History Exported");
    }


    // ============================================================
    // LOAD SAVED HISTORY DATE
    // ============================================================

    async function loadSavedDateFromHistory(dateValue) {
        const h = historyContext();

        if (!h.session || !h.term) {
            return toast("Select a specific session and term before loading a saved date into the register.", "warning");
        }

        if (els.session) els.session.value = h.session;
        if (els.term) els.term.value = h.term;
        if (els.level) els.level.value = h.class_level;

        populateArmSelect(els.level, els.arm, h.class_arm);

        if (els.date) els.date.value = dateValue;

        toggleModal(els.historyModal, false);

        await loadClass();
    }


    // ============================================================
    // ACADEMIC CONFIG
    // ============================================================

    async function initAcademicConfig() {
        try {
            const data = await api(API.config);
            const academic = data.academic || {};

            const sessionValue = clean(academic.academic_session || academic.session);
            const termValue = canonicalTerm(academic.term);

            if (
                sessionValue
                && els.session
                && [...els.session.options].some(option => option.value === sessionValue)
            ) {
                els.session.value = sessionValue;
            }

            if (termValue && els.term) {
                const option = [...els.term.options].find(item => canonicalTerm(item.value) === termValue);

                if (option) els.term.value = option.value;
            }

        } catch (_) {
            /* Existing HTML defaults remain active. */
        }

        syncChips();
    }


    // ============================================================
    // EVENT BINDINGS
    // ============================================================

    function bindEvents() {

        // --------------------------------------------------------
        // MAIN FILTERS
        // --------------------------------------------------------

        els.level?.addEventListener("change", () => {
            populateArmSelect(els.level, els.arm);
            resetLoadedState();
            syncChips();
        });

        els.arm?.addEventListener("change", () => {
            if (state.loaded) resetLoadedState();
            syncChips();
        });

        els.session?.addEventListener("change", () => {
            if (state.loaded) resetLoadedState();
            syncChips();
        });

        els.term?.addEventListener("change", () => {
            if (state.loaded) resetLoadedState();
            syncChips();
        });

        els.date?.addEventListener("change", () => {
            if (state.loaded) resetLoadedState();
            syncChips();
        });


        // --------------------------------------------------------
        // LOAD / SAVE / DELETE
        // --------------------------------------------------------

        els.load?.addEventListener("click", () => loadClass());
        els.refresh?.addEventListener("click", () => loadClass());
        els.save?.addEventListener("click", () => saveAttendance());
        els.del?.addEventListener("click", () => requestDeleteAttendance());
        // --------------------------------------------------------
        // DELETE ATTENDANCE CONFIRMATION MODAL
        // --------------------------------------------------------

        els.closeDeleteModal?.addEventListener("click", cancelDeleteAttendance);
        els.cancelDelete?.addEventListener("click", cancelDeleteAttendance);
        els.confirmDelete?.addEventListener("click", confirmDeleteAttendance);


        // --------------------------------------------------------
        // SEARCH / FILTER
        // --------------------------------------------------------

        els.search?.addEventListener("input", event => {
            state.search = event.target.value;
            applyFilters();
        });

        $$(".filter-pill").forEach(button => {
            button.addEventListener("click", () => {
                state.filter = button.dataset.filter || "ALL";

                $$(".filter-pill").forEach(item => {
                    item.classList.toggle("active", item === button);
                });

                applyFilters();
            });
        });


        // --------------------------------------------------------
        // SELECT ALL
        // --------------------------------------------------------

        els.selectAll?.addEventListener("change", () => {
            $$("tr.attendance-student-row", els.tbody)
                .filter(row => !row.hidden)
                .forEach(row => {
                    const checkbox = row.querySelector(".student-select");

                    if (checkbox) checkbox.checked = els.selectAll.checked;

                    const admission = row.dataset.admission;

                    if (els.selectAll.checked) state.selected.add(admission);
                    else state.selected.delete(admission);
                });

            updateSelectionUI();
        });


        // --------------------------------------------------------
        // TABLE CHANGE
        // --------------------------------------------------------

        els.tbody?.addEventListener("change", event => {
            const row = event.target.closest("tr[data-admission]");

            if (!row) return;

            if (event.target.matches(".student-select")) {
                if (event.target.checked) state.selected.add(row.dataset.admission);
                else state.selected.delete(row.dataset.admission);

                updateSelectionUI();
                return;
            }

            if (event.target.matches(".attendance-status-select")) {
                const student = studentByAdmission(row.dataset.admission);

                setStudentStatus(student, upper(event.target.value));
                setDirty(true);
                updateCounters();
                applyFilters();
            }
        });


        // --------------------------------------------------------
        // REASON / NOTE
        // --------------------------------------------------------

        els.tbody?.addEventListener("input", event => {
            const row = event.target.closest("tr[data-admission]");

            if (
                !row
                || !(
                    event.target.matches(".attendance-reason-input")
                    || event.target.matches(".attendance-note-input")
                )
            ) return;

            readRowIntoStudent(row);
            setDirty(true);
        });


        // --------------------------------------------------------
        // STUDENT PROFILE / MARK BUTTONS
        // --------------------------------------------------------

        els.tbody?.addEventListener("click", event => {
            const row = event.target.closest("tr[data-admission]");

            if (!row) return;

            const student = studentByAdmission(row.dataset.admission);

            if (event.target.closest('[data-action="profile"]')) {
                openStudentProfile(student);
                return;
            }

            const mark = event.target.closest('[data-action="mark"]');

            if (mark) {
                setStudentStatus(student, mark.dataset.status);
                setDirty(true);
                updateCounters();
                applyFilters();
            }
        });


        // --------------------------------------------------------
        // QUICK MARKING
        // --------------------------------------------------------

        els.allPresent?.addEventListener("click", () => bulkStatus("PRESENT", "all"));
        els.allAbsent?.addEventListener("click", () => bulkStatus("ABSENT", "all"));
        els.selectedLate?.addEventListener("click", () => bulkStatus("LATE"));
        els.selectedSick?.addEventListener("click", () => bulkStatus("SICK"));
        els.selectedExcused?.addEventListener("click", () => bulkStatus("EXCUSED"));
        els.clear?.addEventListener("click", clearMarks);


        // --------------------------------------------------------
        // HOLIDAY
        // --------------------------------------------------------

        els.holiday?.addEventListener("click", () => {
            if (!validateMainSelection()) return;

            toggleModal(els.holidayModal, true);
            els.holidayReason?.focus();
        });

        els.cancelHoliday?.addEventListener("click", () => toggleModal(els.holidayModal, false));
        els.confirmHoliday?.addEventListener("click", () => saveHoliday());


        // --------------------------------------------------------
        // SUMMARY / HISTORY
        // --------------------------------------------------------

        els.summary?.addEventListener("click", () => {
            openHistory({ tab: "students", useCurrent: true, autoLoad: true });
        });

        els.classHistory?.addEventListener("click", () => {
            openHistory({ tab: "records", useCurrent: true, autoLoad: true });
        });

        els.openHistory?.addEventListener("click", () => {
            openHistory({
                tab: "records",
                useCurrent: true,
                autoLoad: !!clean(els.arm?.value)
            });
        });


        // --------------------------------------------------------
        // PRINT
        // --------------------------------------------------------

        els.printRegister?.addEventListener("click", () => window.print());


        // --------------------------------------------------------
        // STUDENT MODAL
        // --------------------------------------------------------

        els.closeStudent?.addEventListener("click", () => toggleModal(els.studentModal, false));
        els.studentHistoryBtn?.addEventListener("click", loadStudentHistory);


        // --------------------------------------------------------
        // HISTORY MODAL
        // --------------------------------------------------------

        els.closeHistory?.addEventListener("click", () => toggleModal(els.historyModal, false));

        els.historyLevel?.addEventListener("change", () => {
            populateArmSelect(els.historyLevel, els.historyArm);
        });

        els.historyLoad?.addEventListener("click", loadHistory);
        els.historyReset?.addEventListener("click", resetHistoryFilters);
        els.historyPrint?.addEventListener("click", () => window.print());
        els.historyExport?.addEventListener("click", exportHistoryCsv);

        $$(".history-tab").forEach(button => {
            button.addEventListener("click", () => {
                switchHistoryTab(button.dataset.historyTab);
            });
        });


        // --------------------------------------------------------
        // SAVED DATE ACTIONS
        // --------------------------------------------------------

        $("historyDatesBody")?.addEventListener("click", event => {
            const load = event.target.closest(".load-date");
            const del = event.target.closest(".delete-date");

            if (load) {
                loadSavedDateFromHistory(load.dataset.date);
                return;
            }

            if (del) {
                const h = historyContext();

                if (!h.session || !h.term) return toast("Select a specific session and term before deleting a saved date.", "warning");

                requestDeleteAttendance({ session: h.session, term: h.term, class_level: h.class_level, class_arm: h.class_arm, date: del.dataset.date });
            }
        });


        // --------------------------------------------------------
        // MODAL BACKDROP / ESC
        // --------------------------------------------------------

        els.backdrop?.addEventListener("click", closeAllModals);

        document.addEventListener("keydown", event => {
            if (event.key === "Escape") closeAllModals();
        });


        // --------------------------------------------------------
        // UNSAVED WARNING
        // --------------------------------------------------------

        window.addEventListener("beforeunload", event => {
            if (!state.dirty) return;

            event.preventDefault();
            event.returnValue = "";
        });
    }


    // ============================================================
    // INITIALIZE
    // ============================================================

    async function init() {
        const now = new Date();
        const dateValue = todayISO();

        if (els.date && !els.date.value) els.date.value = dateValue;

        setText("todayDayLabel", now.toLocaleDateString(undefined, { weekday: "long" }));
        setText("todayDateLabel", now.toLocaleDateString(undefined, { day: "2-digit", month: "long", year: "numeric" }));

        populateArmSelect(els.level, els.arm);
        populateArmSelect(els.historyLevel, els.historyArm);

        bindEvents();

        await initAcademicConfig();

        syncChips();
    }

    init();

})();
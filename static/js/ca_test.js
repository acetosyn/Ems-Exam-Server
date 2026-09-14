/* ======================================================================
   ca_test.js — EMIS CA/Test Entry Studio
   Backend: modules/ca_test_manager.py
   Upgrade: partial-score save awareness + report partial-data compatibility
   ====================================================================== */

(() => {
    "use strict";

    const root = document.getElementById("caPage");
    if (!root || root.dataset.backendBound === "1") return;

    root.dataset.backendBound = "1";
    root.dataset.stage = "backend";

    const $ = id => document.getElementById(id), $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];

    const API = {
        config: "/api/ca-tests/config", students: "/api/ca-tests/students", records: "/api/ca-tests/records",
        save: "/api/ca-tests/save", history: "/api/ca-tests/history", delete: "/api/ca-tests/delete",
        reportPreview: "/api/report-sheets/preview"
    };

    const FALLBACK_ARMS = {
        JSS1: ["JSS1A", "JSS1B", "JSS1C"], JSS2: ["JSS2A", "JSS2B", "JSS2C"], JSS3: ["JSS3A", "JSS3B", "JSS3C"],
        SS1: ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1_B/C"], SS2: ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2_B/C"],
        SS3: ["SS3_GOLD", "SS3_SILVER", "SS3_B/C"]
    };

    const FIELD_CONFIG = {
        JSS: [
            { key: "ca1", label: "CA1", max: 10 },
            { key: "ca2", label: "CA2", max: 10 },
            { key: "test1", label: "TEST1", max: 20 },
            { key: "test2", label: "TEST2", max: 20 }
        ],

        SS: [
            { key: "ass1", label: "1ST ASS.", max: 5 },
            { key: "ass2", label: "2ND ASS.", max: 5 },
            { key: "test", label: "TEST", max: 20 }
        ]
    };

    const MAX_TOTAL = { JSS: 60, SS: 30 };
    const AUDIT_KEY = "emis_ca_audit_v1";

    const state = {
        students: [], loaded: false, loadedSession: "", loadedTerm: "", loadedLevel: "", loadedArm: "", loadedSubject: "",
        mode: "", fields: [], dirty: false, search: "", highlightComplete: false, editingAdmission: "",
        savedHistory: [], selectedSavedSubject: "", savedPreviewStudents: []
    };

    const els = {
        session: $("caSession"), term: $("caTerm"), level: $("caClassLevel"), arm: $("caClassArm"), subject: $("caSubject"),
        load: $("loadCAStudentsBtn"), search: $("caSearchInput"), tbody: $("caTableBody"), thead: $("caTableHead"),
        tableSubtext: $("caTableSubtext"), legend: $("caScoreLegend"), saveMessage: $("caSaveMessage"),

        fillZeros: $("fillZerosBtn"), bulk: $("openBulkModalBtn"), exportVisible: $("exportCAVisibleBtn"), clear: $("clearCAScoresBtn"),
        previewMerge: $("previewReportMergeBtn"), openSave: $("openSaveConfirmBtn"), save: $("saveCAScoresBtn"),

        loadSaved: $("loadSavedRecordsBtn"), editSaved: $("editSavedModeBtn"), deleteSubject: $("deleteSubjectRecordsBtn"),
        downloadTemplate: $("downloadTemplateBtn"), openImport: $("openImportModalBtn"), openAudit: $("openAuditModalBtn"),
        openStructure: $("openStructureModalBtn"),

        studentModal: $("caStudentModal"), modalStudentName: $("modalStudentName"), modalStudentMeta: $("modalStudentMeta"),
        modalScoreGrid: $("modalScoreGrid"), modalTotal: $("modalStudentTotal"), modalTotalHint: $("modalStudentTotalHint"),
        applyStudent: $("applyStudentScoresBtn"),

        bulkModal: $("caBulkModal"), bulkZero: $("bulkFillZeroFromModal"), bulkComplete: $("bulkMarkCompleteModal"),
        bulkClear: $("bulkClearVisibleModal"),

        savedModal: $("caSavedRecordsModal"), savedBody: $("savedRecordsTableBody"), savedPreview: $("savedRecordPreviewPanel"),
        reloadSaved: $("reloadSelectedSavedRecordBtn"), deleteSaved: $("deleteSelectedSavedRecordBtn"),

        importModal: $("caImportModal"), importFile: $("caImportFile"), processImport: $("processImportBtn"),
        auditModal: $("caAuditModal"), auditList: $("caAuditList"), structureModal: $("caStructureModal"),
        saveModal: $("caSaveConfirmModal")
    };

    let classArms = parseClassArms();


    // ============================================================
    // BASIC HELPERS
    // ============================================================

    function parseClassArms() {
        try {
            const node = $("caClassArmsConfig"), parsed = node ? JSON.parse(node.textContent || "{}") : {};
            return parsed && typeof parsed === "object" && Object.keys(parsed).length ? parsed : FALLBACK_ARMS;
        } catch (_) { return FALLBACK_ARMS; }
    }

    function clean(value) { return String(value ?? "").trim(); }

    function upper(value) { return clean(value).toUpperCase(); }

    function esc(value) {
        return String(value ?? "").replace(/[&<>'"]/g, ch => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
        }[ch]));
    }

    function canonicalTerm(value) {
        const raw = upper(value).replace(/[_-]+/g, " ").replace(/\s+/g, " ");

        if (["FIRST", "FIRST TERM", "1", "1ST", "1ST TERM"].includes(raw)) return "FIRST";
        if (["SECOND", "SECOND TERM", "2", "2ND", "2ND TERM"].includes(raw)) return "SECOND";
        if (["THIRD", "THIRD TERM", "3", "3RD", "3RD TERM"].includes(raw)) return "THIRD";

        return "";
    }

    function termLabel(value) {
        return { FIRST: "FIRST TERM", SECOND: "SECOND TERM", THIRD: "THIRD TERM" }[canonicalTerm(value)] || upper(value) || "—";
    }

    function armLabel(value) { return clean(value).replace(/_/g, " "); }

    function query(params = {}) {
        const q = new URLSearchParams();

        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null && String(value) !== "") q.set(key, value);
        });

        return q.toString();
    }

    function setText(id, value) {
        const node = $(id);
        if (node) node.textContent = value ?? "";
    }

    function normalizeAdmission(value) { return upper(value).replace(/[^A-Z0-9]/g, ""); }

    function scoreNumber(value) {
        if (value === null || value === undefined || clean(value) === "") return null;

        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function formatScore(value) {
        const number = scoreNumber(value);
        if (number === null) return "";
        return Number.isInteger(number) ? String(number) : String(Number(number.toFixed(2)));
    }

    function humanDateTime(value) {
        if (!value) return "—";

        const d = new Date(String(value).replace(" ", "T"));

        return Number.isNaN(d.getTime())
            ? value
            : d.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    }

    function currentContext() {
        return {
            session: clean(els.session?.value), term: clean(els.term?.value), class_level: clean(els.level?.value),
            class_arm: clean(els.arm?.value), subject: clean(els.subject?.value)
        };
    }

    function loadedContextMatches() {
        const c = currentContext();

        return state.loaded
            && c.session === state.loadedSession
            && canonicalTerm(c.term) === canonicalTerm(state.loadedTerm)
            && c.class_level === state.loadedLevel
            && c.class_arm === state.loadedArm
            && c.subject === state.loadedSubject;
    }


    // ============================================================
    // API HELPER
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
    // TOAST / BUTTON / MODAL HELPERS
    // ============================================================

// ============================================================
// CA / TEST TEACHER NOTIFICATION
// ============================================================

function toast(message, type = "info", timeout = 4200, title = "") {
    let host = $("caToastHost");

    if (!host) {
        host = document.createElement("div");
        host.id = "caToastHost";
        host.className = "ca-toast-host";
        root.appendChild(host);
    }

    const config = {
        success: { icon: "fa-circle-check", title: "Success" },
        loaded: { icon: "fa-cloud-arrow-down", title: "Scores Loaded" },
        saved: { icon: "fa-floppy-disk", title: "Scores Saved" },
        warning: { icon: "fa-triangle-exclamation", title: "Attention" },
        error: { icon: "fa-circle-xmark", title: "Something Went Wrong" },
        info: { icon: "fa-circle-info", title: "CA/Test Update" }
    };

    const current = config[type] || config.info, item = document.createElement("div");

    item.className = `ca-toast ${type}`;
    item.style.setProperty("--toast-duration", `${timeout}ms`);

    item.innerHTML = `
        <div class="ca-toast-icon"><i class="fa-solid ${current.icon}"></i></div>

        <div class="ca-toast-content">
            <strong>${esc(title || current.title)}</strong>
            <span>${esc(message)}</span>
        </div>

        <button type="button" class="ca-toast-close" aria-label="Close notification">
            <i class="fa-solid fa-xmark"></i>
        </button>

        <span class="ca-toast-progress"></span>
    `;

    host.querySelectorAll(".ca-toast").forEach(old => {
        old.classList.add("leaving");
        setTimeout(() => old.remove(), 180);
    });

    host.appendChild(item);

    const dismiss = () => {
        if (!item.isConnected || item.classList.contains("leaving")) return;
        item.classList.add("leaving");
        setTimeout(() => item.remove(), 220);
    };

    item.querySelector(".ca-toast-close")?.addEventListener("click", dismiss);

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

    function openModal(modal) {
        if (!modal) return;

        modal.setAttribute("aria-hidden", "false");
        modal.classList.add("active", "open", "show", "is-open");
        document.body.classList.add("ca-modal-open");
    }

    function closeModal(modal) {
        if (!modal) return;

        modal.setAttribute("aria-hidden", "true");
        modal.classList.remove("active", "open", "show", "is-open");

        if (!$$(".ca-modal").some(item => item.getAttribute("aria-hidden") === "false")) document.body.classList.remove("ca-modal-open");
    }

    function closeAllModals() {
        $$(".ca-modal").forEach(closeModal);
        document.body.classList.remove("ca-modal-open");
    }


    // ============================================================
    // CLASS ARM CONFIGURATION
    // ============================================================

    function armsForLevel(level) {
        let values = classArms?.[level];

        if (!Array.isArray(values) || !values.length) values = FALLBACK_ARMS[level] || [];

        return values.map(item => {
            if (typeof item === "string") return item;
            return item?.value || item?.arm || item?.class_arm || "";
        }).filter(Boolean);
    }

    function populateClassArms(preferred = "") {
        if (!els.arm) return;

        const level = clean(els.level?.value);
        const arms = armsForLevel(level);

        if (!level) {
            els.arm.innerHTML = `<option value="">Select class level first</option>`;
            els.arm.disabled = true;
            return;
        }

        els.arm.innerHTML = `<option value="">Select class arm</option>${arms.map(arm => `<option value="${esc(arm)}">${esc(armLabel(arm))}</option>`).join("")}`;
        els.arm.disabled = false;

        if (preferred && arms.includes(preferred)) els.arm.value = preferred;
    }


    // ============================================================
    // ASSESSMENT MODE / STRUCTURE
    // ============================================================

    function modeForLevel(level) { return upper(level).startsWith("JSS") ? "JSS" : upper(level).startsWith("SS") ? "SS" : ""; }

    function fieldsForMode(mode = state.mode) { return FIELD_CONFIG[mode] || []; }

    function maxTotal(mode = state.mode) { return MAX_TOTAL[mode] || 0; }

    function updateStructure(mode = "") {
        mode = mode || modeForLevel(els.level?.value);

        $("jssModeCard")?.classList.toggle("active", mode === "JSS");
        $("ssModeCard")?.classList.toggle("active", mode === "SS");

        if (mode === "JSS") {
            setText("caStructureLabel", "JSS — CA /60");
            setText("caStructureHint", "CA1 /10 + CA2 /10 + TEST1 /20 + TEST2 /20 • Exam /40");
        } else if (mode === "SS") {
            setText("caStructureLabel", "SS — CA /30");
            setText("caStructureHint", "1ST ASS /5 + 2ND ASS /5 + TEST /20 • Exam /70");
        } else {
            setText("caStructureLabel", "Select Class");
            setText("caStructureHint", "JSS: /60 CA + /40 Exam • SS: /30 CA + /70 Exam");
        }

        if (els.legend) {
            els.legend.innerHTML = mode
                ? fieldsForMode(mode).map(field => `<span>${esc(field.label)} /${field.max}</span>`).join("")
                : `<span>Waiting for class</span>`;
        }
    }


    // ============================================================
    // SUBJECT LOADING
    // ============================================================

    async function loadSubjectOptions(preferred = "") {
        const c = currentContext();

        if (!c.class_level || !c.class_arm) {
            if (els.subject) {
                els.subject.innerHTML = `<option value="">Select class and arm first</option>`;
                els.subject.disabled = true;
            }

            return;
        }

        if (els.subject) {
            els.subject.disabled = true;
            els.subject.innerHTML = `<option value="">Loading subjects...</option>`;
        }

        try {
            const data = await api(`${API.config}?${query({
                session: c.session, term: c.term, class_level: c.class_level, class_arm: c.class_arm
            })}`);

            state.mode = data.mode || modeForLevel(c.class_level);
            state.fields = fieldsForMode(state.mode);

            const subjects = Array.isArray(data.subjects) ? data.subjects : [];

            els.subject.innerHTML = `<option value="">Select subject</option>${subjects.map(subject => `<option value="${esc(subject)}">${esc(subject)}</option>`).join("")}`;
            els.subject.disabled = false;

            if (preferred && subjects.includes(preferred)) els.subject.value = preferred;

            updateStructure(state.mode);

        } catch (error) {
            els.subject.innerHTML = `<option value="">Could not load subjects</option>`;
            els.subject.disabled = true;

            toast(error.message || "Could not load subject list.", "error");
        }
    }


    // ============================================================
    // SCORE HELPERS
    // ============================================================

    function studentScores(student) {
        if (!student._scores) student._scores = {};
        return student._scores;
    }

    function getScore(student, field) {
        const value = studentScores(student)[field];
        return value === null || value === undefined ? "" : value;
    }

    function setScore(student, field, value) { studentScores(student)[field] = value; }

    function scoreValid(value, maximum) {
        if (clean(value) === "") return true;

        const number = scoreNumber(value);
        return number !== null && number >= 0 && number <= maximum;
    }

    function studentComplete(student) {
        return fieldsForMode().every(field => clean(getScore(student, field.key)) !== "" && scoreValid(getScore(student, field.key), field.max));
    }

    function studentHasAnyScore(student) {
        return fieldsForMode().some(field => clean(getScore(student, field.key)) !== "");
    }

    function studentTotal(student) {
        return fieldsForMode().reduce((total, field) => {
            const value = getScore(student, field.key);
            const number = scoreNumber(value);

            return total + (number !== null && number >= 0 && number <= field.max ? number : 0);
        }, 0);
    }

    function invalidFields(student) {
        return fieldsForMode().filter(field => !scoreValid(getScore(student, field.key), field.max));
    }

    function studentByAdmission(admission) {
        const key = normalizeAdmission(admission);
        return state.students.find(student => normalizeAdmission(student.admission_number) === key) || null;
    }


    // ============================================================
    // WORKSPACE RESET
    // ============================================================

    function resetWorkspace(message = "Select a class and subject to begin score entry.") {
        state.students = [];
        state.loaded = false;
        state.loadedSession = "";
        state.loadedTerm = "";
        state.loadedLevel = "";
        state.loadedArm = "";
        state.loadedSubject = "";
        state.dirty = false;
        state.search = "";
        state.highlightComplete = false;
        state.editingAdmission = "";

        if (els.tbody) {
            els.tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="ca-empty">
                        <i class="fa-solid fa-clipboard-list"></i>
                        <strong>${esc(message)}</strong>
                        <span>Select the academic filters and click Load Students.</span>
                    </td>
                </tr>
            `;
        }

        if (els.search) els.search.value = "";

        setText("loadedStudentsCount", "0");
        setText("savedRecordsCount", "0");
        setText("classAverageScore", "--");
        setText("reportReadyStatus", "Waiting");

        if (els.tableSubtext) els.tableSubtext.textContent = "Select a class and subject to begin score entry.";

        updateSaveMessage("Select a class and subject to begin score entry.", "info");

        if (els.save) {
            els.save.disabled = true;
            els.save.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save CA/Test Scores`;
        }
    }


    // ============================================================
    // TABLE HEADER
    // ============================================================

    function renderTableHeader() {
        if (!els.thead) return;

        const fields = fieldsForMode();

        els.thead.innerHTML = `
            <tr>
                <th>#</th>
                <th>Admission No</th>
                <th>Student Name</th>
                <th>Class</th>

                ${fields.map(field => `<th>${esc(field.label)}<small>/${field.max}</small></th>`).join("")}

                <th>Total<small>/${maxTotal()}</small></th>
                <th>Status</th>
                <th>Action</th>
            </tr>
        `;
    }


    // ============================================================
    // STUDENT TABLE
    // ============================================================

    function renderStudents() {
        renderTableHeader();

        if (!els.tbody) return;

        if (!state.students.length) {
            els.tbody.innerHTML = `<tr><td colspan="${fieldsForMode().length + 7}" class="ca-empty"><i class="fa-solid fa-users-slash"></i><strong>No students found</strong><span>No active students were returned for this class arm.</span></td></tr>`;
            updateStats();
            return;
        }

        els.tbody.innerHTML = state.students.map((student, index) => {
            const total = studentTotal(student), complete = studentComplete(student);

            return `
                <tr class="ca-student-row ${complete ? "complete" : "incomplete"} ${state.highlightComplete && complete ? "ca-row-highlight-complete" : ""}" data-admission="${esc(student.admission_number)}">
                    <td>${index + 1}</td>
                    <td>${esc(student.admission_number || "—")}</td>

                    <td>
                        <strong>${esc(student.full_name || "Student")}</strong>
                    </td>

                    <td>${esc(armLabel(student.class_arm || student.class || state.loadedArm))}</td>

                    ${fieldsForMode().map(field => `
                        <td>
                            <input type="number"
                                   class="ca-score-input"
                                   data-field="${field.key}"
                                   min="0"
                                   max="${field.max}"
                                   step="0.01"
                                   value="${esc(formatScore(getScore(student, field.key)))}"
                                   aria-label="${esc(field.label)} score for ${esc(student.full_name)}">
                        </td>
                    `).join("")}

                    <td>
                        <strong class="ca-row-total">${formatScore(total)}</strong>
                        <small>/${maxTotal()}</small>
                    </td>

                    <td>
                        <span class="ca-row-status ${complete ? "complete" : "incomplete"}">
                            <i class="fa-solid ${complete ? "fa-circle-check" : "fa-clock"}"></i>
                            ${complete ? "Complete" : "Incomplete"}
                        </span>
                    </td>

                    <td>
                        <button type="button" class="ca-row-action" data-action="edit" title="Quick edit">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join("");

        applySearch();
        updateStats();
    }

    function updateStudentRow(student) {
        const row = els.tbody?.querySelector(`tr[data-admission="${CSS.escape(student.admission_number)}"]`);
        if (!row) return;

        const complete = studentComplete(student);

        row.classList.toggle("complete", complete);
        row.classList.toggle("incomplete", !complete);
        row.classList.toggle("ca-row-highlight-complete", state.highlightComplete && complete);

        const total = row.querySelector(".ca-row-total");
        if (total) total.textContent = formatScore(studentTotal(student));

        const status = row.querySelector(".ca-row-status");

        if (status) {
            status.className = `ca-row-status ${complete ? "complete" : "incomplete"}`;
            status.innerHTML = `<i class="fa-solid ${complete ? "fa-circle-check" : "fa-clock"}"></i> ${complete ? "Complete" : "Incomplete"}`;
        }

        updateStats();
    }


    // ============================================================
    // LIVE STATS
    // ============================================================

    function updateStats() {
        const totals = state.students.filter(studentHasAnyScore).map(studentTotal);
        const complete = state.students.filter(studentComplete).length;
        const saved = state.students.filter(student => student.has_saved_scores).length;
        const average = totals.length ? totals.reduce((sum, value) => sum + value, 0) / totals.length : null;

        setText("loadedStudentsCount", state.students.length);
        setText("savedRecordsCount", saved);
        setText("classAverageScore", average === null ? "--" : `${formatScore(average)} / ${maxTotal()}`);

        if (!state.students.length) setText("reportReadyStatus", "Waiting");
        else if (complete === state.students.length) setText("reportReadyStatus", "CA Ready");
        else setText("reportReadyStatus", `${complete}/${state.students.length} Complete`);

        if (state.loaded) {
            const incomplete = state.students.length - complete;

            updateSaveMessage(
                incomplete
                    ? `${complete} complete • ${incomplete} incomplete • CA total /${maxTotal()}`
                    : `All ${complete} student records are complete and ready to save.`,
                incomplete ? "warning" : "success"
            );
        }
    }


    // ============================================================
    // SEARCH / VISIBILITY
    // ============================================================

    function applySearch() {
        const search = clean(state.search).toLowerCase();

        $$("tr.ca-student-row", els.tbody).forEach(row => {
            const student = studentByAdmission(row.dataset.admission);

            const haystack = `${student?.full_name || ""} ${student?.admission_number || ""} ${student?.class_arm || ""}`.toLowerCase();
            row.hidden = !!search && !haystack.includes(search);
        });
    }

    function visibleStudents() {
        return $$("tr.ca-student-row", els.tbody)
            .filter(row => !row.hidden)
            .map(row => studentByAdmission(row.dataset.admission))
            .filter(Boolean);
    }


    // ============================================================
    // SAVE MESSAGE
    // ============================================================

    function updateSaveMessage(message, type = "info") {
        if (!els.saveMessage) return;

        const icon = type === "success" ? "fa-circle-check" : type === "warning" ? "fa-triangle-exclamation" : type === "error" ? "fa-circle-xmark" : "fa-circle-info";

        els.saveMessage.className = `ca-save-message ${type}`;
        els.saveMessage.innerHTML = `<i class="fa-solid ${icon}"></i> ${esc(message)}`;
    }


    // ============================================================
    // LOAD STUDENTS
    // ============================================================

    function validateSelection() {
        const c = currentContext();

        if (!c.session) return toast("Select an academic session.", "warning"), false;
        if (!canonicalTerm(c.term)) return toast("Select a valid term.", "warning"), false;
        if (!c.class_level) return toast("Select a class level.", "warning"), false;
        if (!c.class_arm) return toast("Select a class arm.", "warning"), false;
        if (!c.subject) return toast("Select a subject.", "warning"), false;

        return true;
    }

    async function loadStudents({ quiet = false } = {}) {
        if (!validateSelection()) return;

        const c = currentContext();

        setButtonLoading(els.load, true, "Loading...");

        try {
            const data = await api(`${API.students}?${query({
                session: c.session, term: c.term, class_level: c.class_level,
                class_arm: c.class_arm, subject: c.subject
            })}`);

            state.mode = data.mode || modeForLevel(c.class_level);
            state.fields = fieldsForMode(state.mode);
            state.loaded = true;
            state.loadedSession = data.session || c.session;
            state.loadedTerm = data.term || canonicalTerm(c.term);
            state.loadedLevel = data.class_level || c.class_level;
            state.loadedArm = data.class_arm || c.class_arm;
            state.loadedSubject = data.subject || c.subject;
            state.dirty = false;
            state.highlightComplete = false;

            state.students = (data.students || []).map(student => {
                const scores = student.scores || {};
                const mapped = {};

                fieldsForMode().forEach(field => {
                    mapped[field.key] = scores[field.key] === null || scores[field.key] === undefined ? "" : scores[field.key];
                });

                return { ...student, _scores: mapped, has_saved_scores: !!student.has_saved_scores };
            });

            renderStudents();

            if (els.tableSubtext) {
                els.tableSubtext.textContent = `${state.loadedSubject} • ${armLabel(state.loadedArm)} • ${termLabel(state.loadedTerm)} • ${state.loadedSession}`;
            }

            if (els.save) {
                els.save.disabled = !state.students.length;
                els.save.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save CA/Test Scores`;
            }

            updateStructure(state.mode);


            if (!quiet) {
                const savedCount = state.students.filter(student => student.has_saved_scores).length;

                toast(
                    savedCount
                        ? `${state.students.length} students loaded for ${state.loadedSubject}. ${savedCount} student${savedCount === 1 ? "" : "s"} already have saved scores.`
                        : `${state.students.length} students loaded successfully for ${state.loadedSubject}.`,
                    "loaded", 4800, savedCount ? "Saved Scores Loaded" : "Class Loaded"
                );
            }

        } catch (error) {
            resetWorkspace("Could not load students");
            toast(error.message || "Could not load CA students.", "error");

        } finally {
            setButtonLoading(els.load, false);
        }
    }


    // ============================================================
    // DIRECT SCORE ENTRY
    // ============================================================

    function handleScoreInput(input) {
        const row = input.closest("tr[data-admission]");
        if (!row) return;

        const student = studentByAdmission(row.dataset.admission);
        const field = fieldsForMode().find(item => item.key === input.dataset.field);

        if (!student || !field) return;

        const value = clean(input.value);

        setScore(student, field.key, value);
        input.classList.toggle("invalid", !scoreValid(value, field.max));

        if (!scoreValid(value, field.max)) input.setCustomValidity(`${field.label} must be between 0 and ${field.max}.`);
        else input.setCustomValidity("");

        state.dirty = true;
        updateStudentRow(student);
    }


    // ============================================================
    // QUICK STUDENT EDIT MODAL
    // ============================================================

    function openStudentEditor(student) {
        if (!student) return;

        state.editingAdmission = student.admission_number;

        if (els.modalStudentName) els.modalStudentName.textContent = student.full_name || "Student Score Entry";
        if (els.modalStudentMeta) els.modalStudentMeta.textContent = `${student.admission_number || "—"} • ${armLabel(student.class_arm || state.loadedArm)} • ${state.loadedSubject}`;

        if (els.modalScoreGrid) {
            els.modalScoreGrid.innerHTML = fieldsForMode().map(field => `
                <div class="form-group">
                    <label class="form-label">${esc(field.label)} /${field.max}</label>
                    <input type="number"
                           class="form-input modal-score-input"
                           data-field="${field.key}"
                           min="0"
                           max="${field.max}"
                           step="0.01"
                           value="${esc(formatScore(getScore(student, field.key)))}">
                </div>
            `).join("");
        }

        updateModalTotal();
        openModal(els.studentModal);
    }

    function updateModalTotal() {
        let total = 0;

        $$(".modal-score-input", els.modalScoreGrid).forEach(input => {
            const field = fieldsForMode().find(item => item.key === input.dataset.field);
            const number = scoreNumber(input.value);

            input.classList.toggle("invalid", !scoreValid(input.value, field?.max || 0));

            if (field && number !== null && number >= 0 && number <= field.max) total += number;
        });

        if (els.modalTotal) els.modalTotal.textContent = formatScore(total);
        if (els.modalTotalHint) els.modalTotalHint.textContent = `${state.mode} CA/Test maximum = ${maxTotal()}`;
    }

    function applyStudentEditor() {
        const student = studentByAdmission(state.editingAdmission);
        if (!student) return;

        const inputs = $$(".modal-score-input", els.modalScoreGrid);
        let invalid = false;

        inputs.forEach(input => {
            const field = fieldsForMode().find(item => item.key === input.dataset.field);

            if (!field || !scoreValid(input.value, field.max)) {
                invalid = true;
                input.classList.add("invalid");
            }
        });

        if (invalid) return toast("One or more scores exceed the allowed maximum.", "error");

        inputs.forEach(input => setScore(student, input.dataset.field, clean(input.value)));

        state.dirty = true;
        closeModal(els.studentModal);
        renderStudents();

        toast(`Scores updated for ${student.full_name}.`, "success");
    }


    // ============================================================
    // BULK SCORE TOOLS
    // ============================================================

    function fillEmptyWithZero() {
        const students = visibleStudents();

        if (!students.length) return toast("No visible students to update.", "warning");

        let changed = 0;

        students.forEach(student => {
            fieldsForMode().forEach(field => {
                if (clean(getScore(student, field.key)) === "") {
                    setScore(student, field.key, 0);
                    changed++;
                }
            });
        });

        if (!changed) return toast("There are no empty score fields in the visible rows.", "info");

        state.dirty = true;
        renderStudents();

        toast(`${changed} empty score field${changed === 1 ? "" : "s"} filled with 0.`, "success");
    }

    function clearVisibleScores() {
        const students = visibleStudents();

        if (!students.length) return toast("No visible students to clear.", "warning");
        if (!window.confirm(`Clear all visible CA/Test scores for ${students.length} student${students.length === 1 ? "" : "s"}?`)) return;

        students.forEach(student => fieldsForMode().forEach(field => setScore(student, field.key, "")));

        state.dirty = true;
        renderStudents();

        toast("Visible score fields cleared.", "success");
    }

    function highlightCompleteRows() {
        state.highlightComplete = !state.highlightComplete;
        renderStudents();

        toast(state.highlightComplete ? "Complete rows highlighted." : "Complete-row highlight removed.", "info");
    }


    // ============================================================
    // SAVE CONFIRMATION
    // ============================================================

    function openSaveConfirmation() {
        if (!state.loaded || !loadedContextMatches()) return toast("Load the current class and subject before saving.", "warning");
        if (!state.students.length) return toast("There are no student records to save.", "warning");

        const invalid = state.students.flatMap(student => invalidFields(student).map(field => `${student.full_name}: ${field.label}`));

        if (invalid.length) return toast(`Fix invalid scores before saving. ${invalid[0]}`, "error");

        const complete = state.students.filter(studentComplete).length;

        setText("saveSummaryClass", armLabel(state.loadedArm));
        setText("saveSummarySubject", state.loadedSubject);
        setText("saveSummaryStudents", state.students.length);

        if (els.save) {
            els.save.disabled = false;
            els.save.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save CA/Test Scores`;
        }

        updateSaveMessage(
            complete === state.students.length
                ? `All ${complete} students have complete CA/Test scores.`
                : `${complete} complete • ${state.students.length - complete} incomplete. Incomplete records can still be saved and edited later.`,
            complete === state.students.length ? "success" : "warning"
        );

        openModal(els.saveModal);
    }


    // ============================================================
    // BUILD SAVE PAYLOAD
    // ============================================================

    function buildSavePayload(overwrite = false) {
        const enteredStudents = state.students.filter(studentHasAnyScore);

        return {
            session: state.loadedSession, term: state.loadedTerm, class_level: state.loadedLevel,
            class_arm: state.loadedArm, subject: state.loadedSubject, overwrite,
            records: enteredStudents.map(student => { const record = { admission_number: student.admission_number }; fieldsForMode().forEach(field => record[field.key] = clean(getScore(student, field.key))); return record; })
        };
    }


    // ============================================================
    // SAVE CA / TEST SCORES
    // ============================================================

    async function saveScores(forceOverwrite = false) {
        if (!state.loaded || !loadedContextMatches()) return toast("Reload the selected class and subject before saving.", "warning");

        const invalid = state.students.flatMap(student => invalidFields(student)), enteredStudents = state.students.filter(studentHasAnyScore);
        if (invalid.length) return toast("One or more scores exceed the maximum allowed mark.", "error");
        if (!enteredStudents.length) return toast("Enter at least one CA/Test score before saving. Blank students are not stored.", "warning", 4200, "No Scores Entered");

        setButtonLoading(els.save, true, "Saving...");

        try {
            const data = await api(API.save, { method: "POST", body: JSON.stringify(buildSavePayload(forceOverwrite)) });
            const savedCount = Number(data.saved_count ?? enteredStudents.length), completeCount = Number(data.complete_count ?? 0), incompleteCount = Number(data.incomplete_count ?? Math.max(0, savedCount - completeCount));

            state.students.forEach(student => student.has_saved_scores = studentHasAnyScore(student));
            state.dirty = false;
            closeModal(els.saveModal); updateStats();
            addAudit(data.overwrite ? "OVERWRITE" : "SAVE", `${savedCount} ${state.mode} CA/Test records saved for ${state.loadedSubject} — ${armLabel(state.loadedArm)}.`);
            toast(`${savedCount} ${state.mode} CA/Test record${savedCount === 1 ? "" : "s"} saved for ${state.loadedSubject} — ${armLabel(state.loadedArm)}. Blank students were ignored.`, "saved", 5200, data.overwrite ? "Scores Updated Successfully" : "Scores Saved Successfully");
            updateSaveMessage(`${savedCount} records saved • ${completeCount} complete • ${incompleteCount} incomplete • blank students ignored.`, "success");

        } catch (error) {
            if (error.status === 409 && error.data?.requires_overwrite) {
                if (window.confirm(`${error.message}\n\nDo you want to overwrite the existing saved scores for this class and subject?`)) {
                    setButtonLoading(els.save, false);
                    return saveScores(true);
                }

            } else {
                toast(error.message || "Could not save CA/Test scores.", "error");
            }

        } finally {
            setButtonLoading(els.save, false);
        }
    }


    // ============================================================
    // DELETE CURRENT SUBJECT RECORDS
    // ============================================================

    async function deleteSubjectRecords(subject = "") {
        const c = currentContext();
        subject = subject || c.subject;

        if (!c.session || !c.term || !c.class_level || !c.class_arm || !subject) return toast("Select session, term, class arm and subject first.", "warning", 4200, "Selection Required");
        if (!window.confirm(`Delete ALL saved ${subject} CA/Test records for ${armLabel(c.class_arm)} — ${termLabel(c.term)}?\n\nThis removes the whole saved subject set.`)) return false;

        setButtonLoading(els.deleteSubject, true, "Deleting...");

        try {
            const data = await api(API.delete, { method: "POST", body: JSON.stringify({ session: c.session, term: c.term, class_level: c.class_level, class_arm: c.class_arm, subject }) });

            addAudit("DELETE", `${subject} CA/Test records deleted for ${armLabel(c.class_arm)}.`);

            toast(data.message || `${subject} CA/Test records deleted for ${armLabel(c.class_arm)}.`, "success", 4800, "Saved Scores Deleted");

            if (state.loaded && state.loadedSubject === subject) await loadStudents({ quiet: true });
            if (els.savedModal?.getAttribute("aria-hidden") === "false") await loadSavedRecords({ quiet: true });

            return true;

        } catch (error) {
            toast(error.message || "Could not delete saved CA/Test records.", "error", 5200, "Delete Failed");
            return false;

        } finally {
            setButtonLoading(els.deleteSubject, false);
        }
    }


    // ============================================================
    // SAVED RECORD HISTORY
    // ============================================================

    async function loadSavedRecords(options = {}) {
        const quiet = !!options.quiet, c = currentContext();

        if (!c.session || !c.term || !c.class_level || !c.class_arm) return toast("Select session, term, class level and class arm first.", "warning", 4200, "Selection Required");

        openModal(els.savedModal);
        if (els.savedBody) els.savedBody.innerHTML = `<tr><td colspan="7"><i class="fa-solid fa-spinner fa-spin"></i> Loading saved records...</td></tr>`;

        try {
            const data = await api(`${API.history}?${query({ session: c.session, term: c.term, class_level: c.class_level, class_arm: c.class_arm })}`);

            state.savedHistory = data.records || data.subjects || [];
            state.selectedSavedSubject = "";
            state.savedPreviewStudents = [];

            renderSavedRecords();

            if (!quiet) {
                const subjectCount = state.savedHistory.length, studentCount = state.savedHistory.reduce((total, item) => total + Number(item.students || 0), 0);

                toast(
                    subjectCount
                        ? `${subjectCount} saved subject record${subjectCount === 1 ? "" : "s"} loaded for ${armLabel(c.class_arm)} — ${termLabel(c.term)}${studentCount ? ` • ${studentCount} student record${studentCount === 1 ? "" : "s"}` : ""}.`
                        : `No saved CA/Test records were found for ${armLabel(c.class_arm)} — ${termLabel(c.term)}.`,
                    subjectCount ? "loaded" : "info", 4800,
                    subjectCount ? "Saved Records Loaded" : "No Saved Records"
                );
            }

        } catch (error) {
            if (els.savedBody) els.savedBody.innerHTML = `<tr><td colspan="7">${esc(error.message || "Could not load saved records.")}</td></tr>`;
            toast(error.message || "Could not load saved CA/Test records.", "error", 5200, "Saved Records Failed");
        }
    }


    // ============================================================
    // RENDER SAVED RECORD HISTORY
    // ============================================================

    function renderSavedRecords() {
        if (!els.savedBody) return;

        const c = currentContext();

        if (!state.savedHistory.length) {
            els.savedBody.innerHTML = `<tr><td colspan="7">No saved CA/Test records found for this class and term.</td></tr>`;
            if (els.savedPreview) els.savedPreview.innerHTML = `<div class="saved-preview-empty"><i class="fa-solid fa-table-list"></i><strong>No saved records</strong><span>Save CA/Test scores first.</span></div>`;
            return;
        }

        els.savedBody.innerHTML = state.savedHistory.map((item, index) => `
            <tr data-subject="${esc(item.subject)}">
                <td><input type="radio" name="savedCASelection" value="${esc(index)}" aria-label="Select ${esc(item.subject)}"></td>
                <td>${esc(c.session)}</td><td>${esc(termLabel(c.term))}</td><td>${esc(armLabel(c.class_arm))}</td>
                <td><strong>${esc(item.subject)}</strong></td><td>${esc(item.students || 0)}</td><td>${esc(humanDateTime(item.saved_at))}</td>
            </tr>
        `).join("");
    }


    // ============================================================
    // SELECT / LOAD SAVED RECORD PREVIEW
    // ============================================================

    async function selectSavedRecord(index) {
        const item = state.savedHistory[Number(index)];
        if (!item) return;

        state.selectedSavedSubject = item.subject;

        if (els.savedPreview) els.savedPreview.innerHTML = `<div class="saved-preview-empty"><i class="fa-solid fa-spinner fa-spin"></i><strong>Loading ${esc(item.subject)}</strong><span>Please wait...</span></div>`;

        try {
            const c = currentContext();
            const data = await api(`${API.students}?${query({ session: c.session, term: c.term, class_level: c.class_level, class_arm: c.class_arm, subject: item.subject })}`);

            state.savedPreviewStudents = data.students || [];
            renderSavedPreview(item, data);

            const savedCount = state.savedPreviewStudents.filter(student => student.has_saved_scores).length;

            toast(
                savedCount
                    ? `${savedCount} saved ${item.subject} score record${savedCount === 1 ? "" : "s"} loaded for ${armLabel(c.class_arm)}.`
                    : `The saved ${item.subject} record opened, but no student score details were found.`,
                savedCount ? "loaded" : "info", 4400,
                savedCount ? "Saved Scores Loaded" : "Saved Record Opened"
            );

        } catch (error) {
            if (els.savedPreview) els.savedPreview.innerHTML = `<div class="saved-preview-empty"><i class="fa-solid fa-circle-xmark"></i><strong>Could not load saved record</strong><span>${esc(error.message || "Saved score details could not be loaded.")}</span></div>`;
            toast(error.message || `Could not load saved ${item.subject} scores.`, "error", 5200, "Saved Scores Failed");
        }
    }


    // ============================================================
    // RENDER SAVED SCORE PREVIEW
    // ============================================================

    function renderSavedPreview(item, data) {
        if (!els.savedPreview) return;

        const mode = data.mode || modeForLevel(currentContext().class_level), fields = FIELD_CONFIG[mode] || [], saved = (data.students || []).filter(student => student.has_saved_scores);

        els.savedPreview.innerHTML = `
            <div class="saved-preview-head">
                <div><strong>${esc(item.subject)}</strong><span>${saved.length} saved student record${saved.length === 1 ? "" : "s"} • ${esc(mode)} CA /${MAX_TOTAL[mode]}</span></div>
            </div>

            <div class="saved-record-table-wrap">
                <table class="saved-record-table">
                    <thead><tr><th>Admission</th><th>Student</th>${fields.map(field => `<th>${esc(field.label)}</th>`).join("")}<th>Total</th></tr></thead>
                    <tbody>
                        ${saved.length ? saved.map(student => {
                            const scores = student.scores || {};
                            return `<tr><td>${esc(student.admission_number)}</td><td>${esc(student.full_name)}</td>${fields.map(field => `<td>${esc(formatScore(scores[field.key])) || "—"}</td>`).join("")}<td><strong>${esc(formatScore(scores.ca_total))}</strong></td></tr>`;
                        }).join("") : `<tr><td colspan="${fields.length + 3}">No saved score details found.</td></tr>`}
                    </tbody>
                </table>
            </div>
        `;
    }


    // ============================================================
    // RELOAD SAVED RECORD FOR EDITING
    // ============================================================

    async function reloadSavedForEditing() {
        if (!state.selectedSavedSubject) return toast("Select a saved subject first.", "warning", 4200, "Select Saved Record");

        const subject = state.selectedSavedSubject, option = [...(els.subject?.options || [])].find(item => item.value === subject);

        if (!option) await loadSubjectOptions(subject);
        else els.subject.value = subject;

        closeModal(els.savedModal);
        addAudit("RELOAD", `${subject} saved records reopened for editing.`);

        await loadStudents();
    }


    // ============================================================
    // DELETE SELECTED SAVED RECORD
    // ============================================================

    async function deleteSelectedSavedRecord() {
        if (!state.selectedSavedSubject) return toast("Select a saved record first.", "warning", 4200, "Select Saved Record");

        const subject = state.selectedSavedSubject, deleted = await deleteSubjectRecords(subject);
        if (!deleted) return;

        state.selectedSavedSubject = "";
        state.savedPreviewStudents = [];

        if (els.savedPreview) els.savedPreview.innerHTML = `<div class="saved-preview-empty"><i class="fa-solid fa-table-list"></i><strong>No saved record selected</strong><span>Select another saved subject to preview its scores.</span></div>`;
    }


    // ============================================================
    // EDIT SAVED MODE
    // ============================================================

    async function editSavedScores() {
        if (clean(els.subject?.value)) {
            await loadStudents();
            return;
        }

        await loadSavedRecords();
    }

    // ============================================================
    // DOWNLOAD CSV TEMPLATE
    // ============================================================

    function downloadTemplate() {
        if (!state.loaded || !state.students.length) return toast("Load the class and subject before downloading a template.", "warning");

        const headers = ["Admission_number", "Student_Name", "Class", ...fieldsForMode().map(field => field.label)];

        const rows = state.students.map(student => [
            student.admission_number, student.full_name, student.class_arm || state.loadedArm,
            ...fieldsForMode().map(() => "")
        ]);

        downloadCsv(
            `CA_Template_${safeFilePart(state.loadedArm)}_${safeFilePart(state.loadedSubject)}_${safeFilePart(state.loadedTerm)}.csv`,
            [headers, ...rows]
        );

        addAudit("TEMPLATE", `${state.loadedSubject} CSV template downloaded for ${armLabel(state.loadedArm)}.`);
    }


    // ============================================================
    // EXPORT VISIBLE SCORES
    // ============================================================

    function exportVisibleScores() {
        if (!state.loaded) return toast("Load CA/Test records first.", "warning");

        const students = visibleStudents();

        if (!students.length) return toast("There are no visible student rows to export.", "warning");

        const headers = ["Admission_number", "Student_Name", "Class", ...fieldsForMode().map(field => field.label), "CA_Total", "Status"];

        const rows = students.map(student => [
            student.admission_number, student.full_name, student.class_arm || state.loadedArm,
            ...fieldsForMode().map(field => getScore(student, field.key)),
            studentTotal(student), studentComplete(student) ? "COMPLETE" : "INCOMPLETE"
        ]);

        downloadCsv(
            `CA_${safeFilePart(state.loadedArm)}_${safeFilePart(state.loadedSubject)}_${safeFilePart(state.loadedTerm)}.csv`,
            [headers, ...rows]
        );

        addAudit("EXPORT", `${students.length} visible ${state.loadedSubject} records exported.`);
    }

    function downloadCsv(filename, rows) {
        const content = rows.map(row => row.map(value => `"${String(value ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
        const blob = new Blob(["\ufeff" + content], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = filename;

        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(url);
    }

    function safeFilePart(value) {
        return clean(value).replace(/[\/\\:*?"<>|]+/g, "-").replace(/\s+/g, "_") || "CA";
    }


    // ============================================================
    // CSV PARSER
    // ============================================================

    function parseCsv(text) {
        const rows = [];
        let row = [], cell = "", quoted = false;

        for (let i = 0; i < text.length; i++) {
            const char = text[i], next = text[i + 1];

            if (char === '"' && quoted && next === '"') {
                cell += '"';
                i++;
                continue;
            }

            if (char === '"') {
                quoted = !quoted;
                continue;
            }

            if (char === "," && !quoted) {
                row.push(cell);
                cell = "";
                continue;
            }

            if ((char === "\n" || char === "\r") && !quoted) {
                if (char === "\r" && next === "\n") i++;

                row.push(cell);

                if (row.some(value => clean(value) !== "")) rows.push(row);

                row = [];
                cell = "";
                continue;
            }

            cell += char;
        }

        row.push(cell);

        if (row.some(value => clean(value) !== "")) rows.push(row);

        return rows;
    }

    function normalizeHeader(value) { return upper(value).replace(/[^A-Z0-9]/g, ""); }


    // ============================================================
    // IMPORT CSV
    // ============================================================

    async function processImport() {
        if (!state.loaded || !loadedContextMatches()) return toast("Load the class and subject before importing scores.", "warning");

        const file = els.importFile?.files?.[0];

        if (!file) return toast("Select a CSV file first.", "warning");

        setButtonLoading(els.processImport, true, "Importing...");

        try {
            const rows = parseCsv(await file.text());

            if (rows.length < 2) throw new Error("The CSV file contains no student score rows.");

            const headers = rows[0].map(normalizeHeader);

            const admissionIndex = headers.findIndex(value => ["ADMISSIONNUMBER", "ADMISSIONNO", "ADMISSION", "STUDENTID", "ID"].includes(value));

            if (admissionIndex < 0) throw new Error("CSV must contain an Admission_number or Admission No column.");

            const fieldIndexes = {};

            fieldsForMode().forEach(field => {
                const candidates = [normalizeHeader(field.key), normalizeHeader(field.label)];
                fieldIndexes[field.key] = headers.findIndex(value => candidates.includes(value));
            });

            let matched = 0, changed = 0, invalid = 0;

            rows.slice(1).forEach(row => {
                const admission = row[admissionIndex];
                const student = studentByAdmission(admission);

                if (!student) return;

                matched++;

                fieldsForMode().forEach(field => {
                    const index = fieldIndexes[field.key];

                    if (index < 0) return;

                    const raw = clean(row[index]);

                    if (raw === "") return;

                    if (!scoreValid(raw, field.max)) {
                        invalid++;
                        return;
                    }

                    setScore(student, field.key, raw);
                    changed++;
                });
            });

            if (!matched) throw new Error("No admission numbers in the CSV matched the loaded class roster.");

            state.dirty = changed > 0 || state.dirty;

            renderStudents();
            closeModal(els.importModal);

            addAudit("IMPORT", `${changed} score field(s) imported from ${file.name}.`);

            toast(
                invalid
                    ? `${changed} scores imported. ${invalid} invalid value${invalid === 1 ? "" : "s"} skipped.`
                    : `${changed} score field${changed === 1 ? "" : "s"} imported successfully.`,
                invalid ? "warning" : "success"
            );

        } catch (error) {
            toast(error.message || "Could not import the CSV file.", "error");

        } finally {
            setButtonLoading(els.processImport, false);
        }
    }


    // ============================================================
    // REPORT-SHEET MERGE PREVIEW
    // ============================================================

    async function previewReportMerge() {
        if (!state.loaded || !loadedContextMatches()) return toast("Load the current class and subject first.", "warning");

        setButtonLoading(els.previewMerge, true, "Checking...");

        try {
            const data = await api(API.reportPreview, {
                method: "POST",
                body: JSON.stringify({
                    session: state.loadedSession, term: state.loadedTerm,
                    class_level: state.loadedLevel, class_arm: state.loadedArm
                })
            });

            const generated = data.reports?.length || data.summary?.generated || 0, complete = Number(data.summary?.complete_reports || 0), partial = Number(data.summary?.partial_reports ?? Math.max(0, generated - complete));

            if (generated) {
                updateSaveMessage(`${generated} report sheet${generated === 1 ? "" : "s"} can be prepared • ${complete} academically complete • ${partial} partial/pending.`, partial ? "warning" : "success");
                toast(`${generated} report sheet${generated === 1 ? "" : "s"} available. Missing exam/CA fields will remain blank until those records exist.`, partial ? "warning" : "success", 4600, "Report Merge Checked");
            } else {
                updateSaveMessage("No report data is available for this class selection yet.", "warning");
                toast("No report data is available yet for this class selection.", "warning");
            }

        } catch (error) {
            toast(error.message || "Could not preview report-sheet merge.", "error");

        } finally {
            setButtonLoading(els.previewMerge, false);
        }
    }


    // ============================================================
    // LOCAL AUDIT LOG
    // ============================================================

    function readAudit() {
        try {
            const value = JSON.parse(localStorage.getItem(AUDIT_KEY) || "[]");
            return Array.isArray(value) ? value : [];
        } catch (_) { return []; }
    }

    function writeAudit(rows) {
        try { localStorage.setItem(AUDIT_KEY, JSON.stringify(rows.slice(0, 100))); }
        catch (_) {}
    }

    function addAudit(action, message) {
        const c = currentContext();

        const rows = readAudit();

        rows.unshift({
            action, message, timestamp: new Date().toISOString(),
            session: c.session, term: canonicalTerm(c.term),
            class_arm: c.class_arm, subject: c.subject
        });

        writeAudit(rows);
    }

    function renderAudit() {
        if (!els.auditList) return;

        const rows = readAudit();

        els.auditList.innerHTML = rows.length
            ? rows.map(item => `
                <article>
                    <i class="fa-solid ${
                        item.action === "DELETE" ? "fa-trash"
                        : item.action === "SAVE" || item.action === "OVERWRITE" ? "fa-floppy-disk"
                        : item.action === "IMPORT" ? "fa-file-import"
                        : "fa-circle-info"
                    }"></i>

                    <div>
                        <strong>${esc(item.action)} — ${esc(item.subject || "CA/Test")}</strong>
                        <span>${esc(item.message)}</span>
                        <small>${esc(humanDateTime(item.timestamp))} • ${esc(armLabel(item.class_arm))} • ${esc(termLabel(item.term))}</small>
                    </div>
                </article>
            `).join("")
            : `<article><i class="fa-solid fa-circle-info"></i><div><strong>No activity yet</strong><span>CA actions from this browser will appear here.</span></div></article>`;
    }


    // ============================================================
    // ACADEMIC SETTINGS
    // ============================================================

    async function loadAcademicDefaults() {
        try {
            const data = await api(API.config);
            const sessionValue = clean(data.session);
            const termValue = canonicalTerm(data.term);

            if (sessionValue && els.session && [...els.session.options].some(option => option.value === sessionValue)) els.session.value = sessionValue;

            if (termValue && els.term) {
                const option = [...els.term.options].find(item => canonicalTerm(item.value) === termValue);
                if (option) els.term.value = option.value;
            }

        } catch (_) {
            /* Existing HTML defaults remain active. */
        }
    }


    // ============================================================
    // FILTER CHANGE HANDLING
    // ============================================================

    function resetAfterFilterChange() {
        resetWorkspace();
        updateStructure(modeForLevel(els.level?.value));
    }


    // ============================================================
    // EVENT BINDINGS — FILTERS
    // ============================================================

    function bindFilterEvents() {
        els.level?.addEventListener("change", async () => {
            populateClassArms();

            if (els.subject) {
                els.subject.innerHTML = `<option value="">Select class and arm first</option>`;
                els.subject.disabled = true;
            }

            resetAfterFilterChange();
            updateStructure(modeForLevel(els.level.value));
        });

        els.arm?.addEventListener("change", async () => {
            resetAfterFilterChange();

            if (els.arm.value) await loadSubjectOptions();
        });

        els.subject?.addEventListener("change", resetAfterFilterChange);

        els.session?.addEventListener("change", () => {
            resetAfterFilterChange();
            if (els.arm?.value) loadSubjectOptions(els.subject?.value);
        });

        els.term?.addEventListener("change", () => {
            resetAfterFilterChange();
            if (els.arm?.value) loadSubjectOptions(els.subject?.value);
        });
    }


    // ============================================================
    // EVENT BINDINGS — SCORE TABLE
    // ============================================================

    function bindTableEvents() {
        els.search?.addEventListener("input", event => {
            state.search = event.target.value;
            applySearch();
        });

        els.tbody?.addEventListener("input", event => {
            if (event.target.matches(".ca-score-input")) handleScoreInput(event.target);
        });

        els.tbody?.addEventListener("click", event => {
            const button = event.target.closest('[data-action="edit"]');
            if (!button) return;

            const row = button.closest("tr[data-admission]");
            if (!row) return;

            openStudentEditor(studentByAdmission(row.dataset.admission));
        });
    }


    // ============================================================
    // EVENT BINDINGS — MODALS
    // ============================================================

    function bindModalEvents() {
        document.addEventListener("click", event => {
            const closer = event.target.closest("[data-close-modal]");
            if (!closer) return;

            closeModal($(closer.dataset.closeModal));
        });

        $$(".ca-modal").forEach(modal => {
            modal.addEventListener("click", event => {
                if (event.target === modal) closeModal(modal);
            });
        });

        document.addEventListener("keydown", event => {
            if (event.key === "Escape") closeAllModals();
        });

        els.openStructure?.addEventListener("click", () => openModal(els.structureModal));
        els.bulk?.addEventListener("click", () => openModal(els.bulkModal));
        els.openImport?.addEventListener("click", () => openModal(els.importModal));

        els.openAudit?.addEventListener("click", () => {
            renderAudit();
            openModal(els.auditModal);
        });

        els.applyStudent?.addEventListener("click", applyStudentEditor);
        els.modalScoreGrid?.addEventListener("input", updateModalTotal);

        els.openSave?.addEventListener("click", openSaveConfirmation);
        els.save?.addEventListener("click", () => saveScores());
    }


    // ============================================================
    // EVENT BINDINGS — BULK TOOLS
    // ============================================================

    function bindBulkEvents() {
        els.fillZeros?.addEventListener("click", fillEmptyWithZero);

        els.bulkZero?.addEventListener("click", () => {
            fillEmptyWithZero();
            closeModal(els.bulkModal);
        });

        els.bulkComplete?.addEventListener("click", () => {
            highlightCompleteRows();
            closeModal(els.bulkModal);
        });

        els.clear?.addEventListener("click", clearVisibleScores);

        els.bulkClear?.addEventListener("click", () => {
            clearVisibleScores();
            closeModal(els.bulkModal);
        });
    }


    // ============================================================
    // EVENT BINDINGS — SAVED RECORDS
    // ============================================================

    function bindSavedRecordEvents() {
        els.loadSaved?.addEventListener("click", loadSavedRecords);
        els.editSaved?.addEventListener("click", editSavedScores);
        els.deleteSubject?.addEventListener("click", () => deleteSubjectRecords());

        els.savedBody?.addEventListener("change", event => {
            if (!event.target.matches('input[name="savedCASelection"]')) return;
            selectSavedRecord(event.target.value);
        });

        els.reloadSaved?.addEventListener("click", reloadSavedForEditing);
        els.deleteSaved?.addEventListener("click", deleteSelectedSavedRecord);
    }


    // ============================================================
    // EVENT BINDINGS — IMPORT / EXPORT / REPORT
    // ============================================================

    function bindUtilityEvents() {
        els.downloadTemplate?.addEventListener("click", downloadTemplate);
        els.exportVisible?.addEventListener("click", exportVisibleScores);
        els.processImport?.addEventListener("click", processImport);
        els.previewMerge?.addEventListener("click", previewReportMerge);
    }


    // ============================================================
    // EVENT BINDINGS — LOAD STUDENTS
    // ============================================================

    function bindLoadEvents() {
        els.load?.addEventListener("click", () => loadStudents());
    }


    // ============================================================
    // UNSAVED CHANGES WARNING
    // ============================================================

    function bindUnsavedWarning() {
        window.addEventListener("beforeunload", event => {
            if (!state.dirty) return;

            event.preventDefault();
            event.returnValue = "";
        });
    }


    // ============================================================
    // INITIALIZE PAGE
    // ============================================================

    async function init() {
        populateClassArms();
        updateStructure("");

        bindFilterEvents();
        bindTableEvents();
        bindModalEvents();
        bindBulkEvents();
        bindSavedRecordEvents();
        bindUtilityEvents();
        bindLoadEvents();
        bindUnsavedWarning();

        await loadAcademicDefaults();

        updateSaveMessage("Select class, subject and term to begin CA/Test score entry.", "info");
    }

    init();

})();
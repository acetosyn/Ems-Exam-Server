// static/js/admin_results.js
// ============================================================
// EMIS ADMIN RESULTS — OBJECTIVE + ESSAY / THEORY MANAGEMENT
// Term-aware JSS • Flat SS • Student roster essay entry
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  // ==========================================================
  // 1. DOM HELPERS
  // ==========================================================

  const $ = (id) => document.getElementById(id);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const els = {
    yearSelector: $("yearSelector"), classSelector: $("classSelector"), classArmSelector: $("classArmSelector"), termSelector: $("termSelector"),
    termFilterGroup: $("termFilterGroup"), termRequirementBadge: $("termRequirementBadge"), subjectSelector: $("subjectSelector"),
    statusFilter: $("statusFilter"), sessionSelector: $("sessionSelector"), globalSearch: $("globalSearch"), clearSearchBtn: $("clearSearchBtn"),

    reloadTableBtn: $("reloadTableBtn"), clearFiltersBtn: $("clearFiltersBtn"), resultsTable: $("resultsTable"), resultsBody: $("resultsBody"),
    selectAllRows: $("selectAllRows"), selectedCountBadge: $("selectedCountBadge"), tableSubtitle: $("tableSubtitle"),
    paginationInfo: $("paginationInfo"), pagination: $("pagination"), rowsPerPage: $("rowsPerPage"),
    columnToggleBtn: $("columnToggleBtn"), columnMenu: $("columnMenu"), resetColumnsBtn: $("resetColumnsBtn"), toggleCompactBtn: $("toggleCompactBtn"),
    activeFilterChips: $("activeFilterChips"), filteredResultCount: $("filteredResultCount"),

    deleteSelectedBtn: $("deleteSelectedBtn"), printSelectedBtn: $("printSelectedBtn"),
    exportAllExcelBtn: $("exportAllExcelBtn"), exportCsvBtn: $("exportCsvBtn"), printAllPdfBtn: $("printAllPdfBtn"),

    essayScoresBtn: $("essayScoresBtn"), openEssayScoresBtn: $("openEssayScoresBtn"),

    deleteModal: $("deleteModal"), cancelDeleteBtn: $("cancelDeleteBtn"), confirmDeleteBtn: $("confirmDeleteBtn"),

    summaryOverlay: $("summaryOverlay"), adminPrintSummary: $("adminPrintSummary"), summaryCloseBtn: $("summaryCloseBtn"),
    summaryCloseFooterBtn: $("summaryCloseFooterBtn"), summaryPrintBtn: $("summaryPrintBtn"), summaryPrintFooterBtn: $("summaryPrintFooterBtn"),
    summaryTermRow: $("summaryTermRow"),

    statTotalResults: $("statTotalResults"), statPassRate: $("statPassRate"), statAvgScore: $("statAvgScore"), statSubjects: $("statSubjects"),
    avgTimeTaken: $("avgTimeTaken"), topPerformerName: $("topPerformerName"), topPerformerMeta: $("topPerformerMeta"),
    highestScore: $("highestScore"), lowestScore: $("lowestScore"),

    essayScoreModal: $("essayScoreModal"), essayScoreBackdrop: $("essayScoreBackdrop"), essayScoreCloseBtn: $("essayScoreCloseBtn"),
    cancelEssayScoresBtn: $("cancelEssayScoresBtn"), saveEssayScoresBtn: $("saveEssayScoresBtn"), clearEssayChangesBtn: $("clearEssayChangesBtn"),

    essayAvailabilityBadge: $("essayAvailabilityBadge"), essayContextYear: $("essayContextYear"), essayContextClass: $("essayContextClass"),
    essayContextTermWrap: $("essayContextTermWrap"), essayContextTerm: $("essayContextTerm"), essayContextSubject: $("essayContextSubject"),
    essayObjectiveMax: $("essayObjectiveMax"), essayMaximumScore: $("essayMaximumScore"), essayHeaderMax: $("essayHeaderMax"),

    essayStudentSearch: $("essayStudentSearch"), clearEssaySearchBtn: $("clearEssaySearchBtn"), essayPendingOnly: $("essayPendingOnly"),
    essayStudentCount: $("essayStudentCount"), essayScoreBody: $("essayScoreBody"), essayUnsavedCount: $("essayUnsavedCount")
  };


  // ==========================================================
  // 2. CONSTANTS / STATE
  // ==========================================================

  const DEFAULT_TERMS = ["FIRST", "SECOND", "THIRD"];
  const TERM_LABELS = { FIRST: "1st Term", SECOND: "2nd Term", THIRD: "3rd Term" };

  const COLUMN_ORDER = [
    "select", "student", "admission", "year", "class", "term", "subject",
    "objective", "essay", "total", "status", "time", "date", "actions"
  ];

  const state = {
    allResults: [], filteredResults: [], selectedKeys: new Set(),
    currentPage: 1, rowsPerPage: Number(els.rowsPerPage?.value || 20),
    sortKey: "date", sortDirection: "desc", statusView: "all", compact: false,
    currentSummaryRow: null, pendingDeleteRows: null, visibleColumns: new Set(COLUMN_ORDER),
    loadToken: 0, loading: false,

    essay: {
      year: "", classLevel: "", term: "", subject: "", arm: "all",
      objectiveMax: 60, essayMax: 40, totalMax: 100, available: true,
      students: [], filteredStudents: [], changes: new Map(), originalScores: new Map(),
      search: "", pendingOnly: false, loading: false
    }
  };


  // ==========================================================
  // 3. GENERAL HELPERS
  // ==========================================================

  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  function normalizeText(value) { return String(value ?? "").trim().toLowerCase(); }
  function normalizeUpper(value) { return String(value ?? "").trim().toUpperCase(); }
  function formatClassLabel(value) { return String(value || "").replaceAll("_", " ").replace(/\s+/g, " ").trim().toUpperCase(); }
  function formatSubject(value) { return String(value || "").replaceAll("_", " ").replace(/\s+/g, " ").trim().toUpperCase(); }
  function isJssClass(value) { return normalizeUpper(value).startsWith("JSS"); }
  function isSsClass(value) { return normalizeUpper(value).startsWith("SS"); }

  function parseNumber(value, fallback = 0) {
    const number = Number.parseFloat(String(value ?? "").replace("%", "").trim());
    return Number.isFinite(number) ? number : fallback;
  }

  function parseNullableNumber(value) {
    if (value === null || value === undefined || String(value).trim() === "") return null;
    const number = Number.parseFloat(String(value).replace("%", "").trim());
    return Number.isFinite(number) ? number : null;
  }

  function roundScore(value, decimals = 2) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    const factor = 10 ** decimals;
    return Math.round((number + Number.EPSILON) * factor) / factor;
  }

  function scoreText(value, decimals = 2) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
    const number = roundScore(Number(value), decimals);
    return Number.isInteger(number) ? String(number) : String(number).replace(/0+$/, "").replace(/\.$/, "");
  }

  function boolValue(value, fallback = false) {
    if (typeof value === "boolean") return value;
    if (value === 1 || value === "1") return true;
    if (value === 0 || value === "0") return false;

    const raw = normalizeText(value);
    if (["true", "yes", "y", "available", "present"].includes(raw)) return true;
    if (["false", "no", "n", "none", "absent", "not available"].includes(raw)) return false;

    return fallback;
  }

  function compareValues(a, b) {
    if (typeof a === "number" && typeof b === "number") return a - b;
    return String(a ?? "").localeCompare(String(b ?? ""), undefined, { numeric: true, sensitivity: "base" });
  }

  function debounce(fn, wait = 220) {
    let timer = null;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); };
  }

  function safeSetText(idOrElement, value) {
    const element = typeof idOrElement === "string" ? $(idOrElement) : idOrElement;
    if (element) element.textContent = value ?? "";
  }

  function normalizeTerm(value) {
    const raw = normalizeUpper(value).replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ");

    const aliases = {
      FIRST: "FIRST", "FIRST TERM": "FIRST", "TERM 1": "FIRST", "TERM ONE": "FIRST", "1": "FIRST", "1ST": "FIRST", "1ST TERM": "FIRST",
      SECOND: "SECOND", "SECOND TERM": "SECOND", "TERM 2": "SECOND", "TERM TWO": "SECOND", "2": "SECOND", "2ND": "SECOND", "2ND TERM": "SECOND",
      THIRD: "THIRD", "THIRD TERM": "THIRD", "TERM 3": "THIRD", "TERM THREE": "THIRD", "3": "THIRD", "3RD": "THIRD", "3RD TERM": "THIRD"
    };

    return aliases[raw] || "";
  }

  function termLabel(value) { return TERM_LABELS[normalizeTerm(value)] || ""; }


  // ==========================================================
  // 4. TOAST
  // ==========================================================

  function showToast(message, type = "info") {
    let stack = document.querySelector(".ar-toast-stack");

    if (!stack) {
      stack = document.createElement("div");
      stack.className = "ar-toast-stack";

      Object.assign(stack.style, {
        position: "fixed", right: "20px", bottom: "20px", zIndex: "10050",
        display: "grid", gap: "8px", maxWidth: "390px"
      });

      document.body.appendChild(stack);
    }

    const palette = {
      success: ["#166534", "#ecfdf3", "#bbf7d0"],
      error: ["#991b1b", "#fff1f2", "#fecdd3"],
      warning: ["#92400e", "#fffbeb", "#fde68a"],
      info: ["#115e59", "#f0fdfa", "#99f6e4"]
    };

    const [color, background, border] = palette[type] || palette.info;
    const toast = document.createElement("div");

    toast.textContent = message;

    Object.assign(toast.style, {
      padding: "11px 13px", border: `1px solid ${border}`, borderRadius: "10px",
      color, background, boxShadow: "0 10px 28px rgba(15,23,42,.14)",
      fontSize: "14px", fontWeight: "700", lineHeight: "1.4",
      opacity: "0", transform: "translateY(8px)", transition: "opacity .18s ease, transform .18s ease"
    });

    stack.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateY(0)";
    });

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      setTimeout(() => toast.remove(), 220);
    }, 3400);
  }


  // ==========================================================
  // 5. FETCH
  // ==========================================================

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {})
      },
      ...options
    });

    let data = {};

    try { data = await response.json(); }
    catch { data = {}; }

    if (!response.ok) throw new Error(data.error || data.message || `Request failed (${response.status})`);

    return data;
  }


  // ==========================================================
  // 6. DOWNLOAD HELPERS
  // ==========================================================

  function downloadBlob(content, mime, filename) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    link.remove();

    setTimeout(() => URL.revokeObjectURL(url), 700);
  }

  function exportFilename(extension) {
    const year = selectedYear() || "all-years";
    const cls = selectedClass() || "all-classes";
    const term = selectedTerm() || "all-terms";
    const date = new Date().toISOString().slice(0, 10);

    return `emis_results_${year}_${cls}_${term}_${date}.${extension}`.replaceAll(" ", "_").toLowerCase();
  }


  // ==========================================================
  // 7. RESULT FIELD HELPERS
  // ==========================================================

  function getStudentName(row) { return String(row?.["Student Name"] ?? row?.full_name ?? row?.student_name ?? row?.name ?? "Unknown Student").trim(); }
  function getAdmission(row) { return String(row?.["Admission No"] ?? row?.Admission_number ?? row?.admission_number ?? row?.student_id ?? "").trim(); }
  function getYear(row) { return String(row?.Year ?? row?.year ?? "").trim(); }

  function getClassLevel(row) {
    return String(
      row?.["Class Level"] ?? row?.["Class Category"] ?? row?.class_category ??
      row?.class_level ?? row?.Class_category ?? row?.classCategory ?? row?.Class ?? ""
    ).trim().toUpperCase();
  }

  function getClassArm(row) {
    return String(row?.["Class Arm"] ?? row?.class_arm ?? row?.classArm ?? row?.Class ?? getClassLevel(row)).trim().toUpperCase();
  }

  function getClass(row) { return getClassArm(row) || getClassLevel(row); }
  function getClassCategory(row) { return getClassLevel(row); }

  function getTerm(row) { return normalizeTerm(row?.Term ?? row?.term ?? row?.["Term Label"] ?? row?.term_label); }
  function getTermLabel(row) { return row?.["Term Label"] ?? row?.term_label ?? termLabel(getTerm(row)); }

  function getSubject(row) { return String(row?.Subject ?? row?.subject ?? row?.["Subject Folder"] ?? row?.subject_folder ?? "").trim(); }
  function getSubjectFolder(row) { return String(row?.["Subject Folder"] ?? row?.subject_folder ?? row?.Subject ?? row?.subject ?? "").trim(); }

  function getCorrect(row) { return parseNumber(row?.Correct ?? row?.correct ?? row?.correct_answers ?? 0); }
  function getQuestionTotal(row) { return parseNumber(row?.Total ?? row?.total ?? row?.total_questions ?? row?.question_count ?? 0); }

  function getObjectivePercentage(row) {
    const explicit = parseNullableNumber(
      row?.objective_percentage ?? row?.objective_percent ?? row?.["Objective Percentage"] ??
      row?.["Score (%)"] ?? row?.["Score Number"] ?? row?.score_percentage ?? row?.percentage ?? row?.score
    );

    if (explicit !== null) return roundScore(explicit);

    const correct = getCorrect(row);
    const total = getQuestionTotal(row);

    return total > 0 ? roundScore((correct / total) * 100) : 0;
  }

  function getEssayAvailable(row) {
    const explicit = row?.essay_available ?? row?.has_essay ?? row?.hasEssay ?? row?.essay_present ?? row?.theory_present;

    if (explicit !== undefined && explicit !== null && explicit !== "") return boolValue(explicit);

    const essayScore = parseNullableNumber(row?.essay_score ?? row?.theory_score ?? row?.["Essay Score"] ?? row?.["Theory Score"]);
    const essayMax = parseNullableNumber(row?.essay_max ?? row?.theory_max ?? row?.["Essay Max"]);

    return essayScore !== null || (essayMax !== null && essayMax > 0);
  }

  function getObjectiveMax(row) {
    const explicit = parseNullableNumber(row?.objective_max ?? row?.objective_weight ?? row?.["Objective Max"]);
    if (explicit !== null && explicit > 0) return explicit;

    return getEssayAvailable(row) ? 60 : 100;
  }

  function getEssayMax(row) {
    const explicit = parseNullableNumber(row?.essay_max ?? row?.theory_max ?? row?.essay_weight ?? row?.["Essay Max"]);
    if (explicit !== null && explicit >= 0) return explicit;

    return getEssayAvailable(row) ? 40 : 0;
  }

  function getObjectiveScore(row) {
    const explicit = parseNullableNumber(
      row?.objective_score ?? row?.objective_mark ?? row?.["Objective Score"] ?? row?.["Objective Mark"]
    );

    if (explicit !== null) return roundScore(explicit);

    const objectiveMax = getObjectiveMax(row);
    const correct = getCorrect(row);
    const totalQuestions = getQuestionTotal(row);

    if (totalQuestions > 0) return roundScore((correct / totalQuestions) * objectiveMax);

    return roundScore((getObjectivePercentage(row) / 100) * objectiveMax);
  }

  function getEssayScore(row) {
    const score = parseNullableNumber(
      row?.essay_score ?? row?.theory_score ?? row?.["Essay Score"] ?? row?.["Theory Score"]
    );

    return score === null ? null : roundScore(score);
  }

  function getFinalScore(row) {
    const explicit = parseNullableNumber(
      row?.final_score ?? row?.combined_score ?? row?.total_score ??
      row?.["Final Score"] ?? row?.["Combined Score"]
    );

    if (explicit !== null) return roundScore(explicit);

    const objective = getObjectiveScore(row);

    if (!getEssayAvailable(row)) return roundScore(objective);

    const essay = getEssayScore(row);
    if (essay === null) return null;

    return roundScore(objective + essay);
  }

  function getScore(row) {
    const finalScore = getFinalScore(row);
    if (finalScore !== null) return finalScore;

    return getObjectivePercentage(row);
  }

  function getResultState(row) {
    const hasObjective = getQuestionTotal(row) > 0 || parseNullableNumber(row?.objective_score ?? row?.["Score (%)"] ?? row?.score) !== null;
    const essayAvailable = getEssayAvailable(row);
    const essayScore = getEssayScore(row);

    if (!essayAvailable) return hasObjective ? "COMPLETE" : "PENDING";
    if (hasObjective && essayScore !== null) return "COMPLETE";
    if (hasObjective && essayScore === null) return "AWAITING ESSAY";
    if (!hasObjective && essayScore !== null) return "AWAITING OBJECTIVE";

    return "PENDING";
  }

  function getStatus(row) {
    const resultState = getResultState(row);
    const finalScore = getFinalScore(row);

    if (resultState !== "COMPLETE" || finalScore === null) return "PENDING";

    const explicit = normalizeUpper(row?.final_status ?? row?.Status ?? row?.status);

    if (explicit === "PASS" || explicit === "FAIL") {
      if (row?.final_status !== undefined || !getEssayAvailable(row)) return explicit;
    }

    return finalScore >= 50 ? "PASS" : "FAIL";
  }

  function getTime(row) { return row?.["Time Taken"] ?? row?.time_taken ?? row?.timeTaken ?? ""; }
  function getSubmittedAt(row) { return row?.["Submitted At"] ?? row?.submitted_at ?? row?.submittedAt ?? ""; }

  function getSession(row) {
    return String(row?.Session ?? row?.session ?? row?.["Academic Session"] ?? row?.academic_session ?? "").trim();
  }

  function getStableKey(row) {
    return [
      getYear(row), getClassLevel(row), getClassArm(row), getTerm(row), getSubjectFolder(row),
      getAdmission(row), getStudentName(row), getSubmittedAt(row)
    ].join("::").toUpperCase();
  }


  // ==========================================================
  // 8. SCORE DISPLAY HELPERS
  // ==========================================================

  function objectiveDisplay(row) {
    const score = getObjectiveScore(row);
    const max = getObjectiveMax(row);
    const correct = getCorrect(row);
    const total = getQuestionTotal(row);

    return {
      score, max, text: `${scoreText(score)} / ${scoreText(max)}`,
      raw: total > 0 ? `${scoreText(correct)} / ${scoreText(total)} questions` : `${scoreText(getObjectivePercentage(row))}% CBT`
    };
  }

  function essayDisplay(row) {
    if (!getEssayAvailable(row)) return { available: false, score: null, max: 0, text: "N/A", state: "No Essay" };

    const score = getEssayScore(row);
    const max = getEssayMax(row);

    return {
      available: true, score, max,
      text: score === null ? "Pending" : `${scoreText(score)} / ${scoreText(max)}`,
      state: score === null ? "Not Entered" : "Entered"
    };
  }

  function totalDisplay(row) {
    const score = getFinalScore(row);
    const stateValue = getResultState(row);

    return {
      score,
      text: score === null ? "Pending" : `${scoreText(score)} / 100`,
      state: stateValue
    };
  }


  // ==========================================================
  // 9. TIME HELPERS
  // ==========================================================

  function getTimeSeconds(row) {
    const value = getTime(row);

    if (typeof value === "number" && Number.isFinite(value)) return value;

    const raw = String(value || "").trim().toLowerCase();

    if (!raw) return NaN;
    if (/^\d+(\.\d+)?$/.test(raw)) return Number.parseFloat(raw);

    const hms = raw.match(/(?:(\d+)\s*h(?:our)?s?)?\s*(?:(\d+)\s*m(?:in(?:ute)?)?s?)?\s*(?:(\d+)\s*s(?:ec(?:ond)?)?s?)?/);

    if (hms && (hms[1] || hms[2] || hms[3])) return Number(hms[1] || 0) * 3600 + Number(hms[2] || 0) * 60 + Number(hms[3] || 0);

    const colon = raw.split(":").map(Number);

    if (colon.every(Number.isFinite)) {
      if (colon.length === 3) return colon[0] * 3600 + colon[1] * 60 + colon[2];
      if (colon.length === 2) return colon[0] * 60 + colon[1];
    }

    const numeric = Number.parseFloat(raw);

    return Number.isFinite(numeric) ? numeric : NaN;
  }

  function formatSeconds(totalSeconds) {
    if (!Number.isFinite(totalSeconds)) return "—";

    const seconds = Math.max(0, Math.round(totalSeconds));

    if (seconds < 60) return `${seconds} sec`;

    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;

    if (minutes < 60) return remaining ? `${minutes}m ${remaining}s` : `${minutes} min`;

    const hours = Math.floor(minutes / 60);

    return `${hours}h ${minutes % 60}m`;
  }


  // ==========================================================
  // 10. TABLE STATES
  // ==========================================================

  function setLoading(message = "Loading examination results") {
    if (!els.resultsBody) return;

    els.resultsBody.innerHTML = `
      <tr>
        <td colspan="14" class="table-placeholder">
          <span class="table-placeholder-icon"><i class="fa-solid fa-spinner fa-spin"></i></span>
          <strong>${escapeHtml(message)}</strong>
          <span>Please wait while EMIS reads the result repository.</span>
        </td>
      </tr>
    `;

    if (els.tableSubtitle) els.tableSubtitle.textContent = "Reading examination records...";
  }

  function setEmpty(message = "No results found", subtext = "No examination result matches the current filters.") {
    if (!els.resultsBody) return;

    els.resultsBody.innerHTML = `
      <tr>
        <td colspan="14" class="table-placeholder">
          <span class="table-placeholder-icon"><i class="fa-solid fa-folder-open"></i></span>
          <strong>${escapeHtml(message)}</strong>
          <span>${escapeHtml(subtext)}</span>
        </td>
      </tr>
    `;
  }


  // ==========================================================
  // 11. CURRENT FILTER VALUES
  // ==========================================================

  function selectedYear() { return els.yearSelector?.value || "all"; }
  function selectedClass() { return els.classSelector?.value || "all"; }
  function selectedTerm() { return els.termSelector?.value || "all"; }
  function selectedSubject() { return els.subjectSelector?.value || "all"; }


  // ==========================================================
  // 12. TERM UI
  // ==========================================================

  function updateTermUi() {
    if (!els.termSelector || !els.termFilterGroup) return;

    const cls = selectedClass();

    if (cls === "all") {
      els.termFilterGroup.hidden = false;
      els.termSelector.disabled = false;

      if (els.termRequirementBadge) {
        els.termRequirementBadge.textContent = "JSS";
        els.termRequirementBadge.title = "Term applies to JSS results";
      }

      return;
    }

    if (isJssClass(cls)) {
      els.termFilterGroup.hidden = false;
      els.termSelector.disabled = false;

      if (els.termRequirementBadge) {
        els.termRequirementBadge.textContent = "Required";
        els.termRequirementBadge.title = "JSS results are stored by term";
      }

      return;
    }

    els.termFilterGroup.hidden = true;
    els.termSelector.value = "all";
    els.termSelector.disabled = true;

    if (els.termRequirementBadge) {
      els.termRequirementBadge.textContent = "N/A";
      els.termRequirementBadge.title = "SS results are not term based";
    }
  }


  // ==========================================================
  // 13. TERM OPTIONS
  // ==========================================================

  function populateTermOptions(terms, preserve = true) {
    if (!els.termSelector) return;

    const previous = preserve ? els.termSelector.value : "all";
    const normalized = [...new Set((terms || []).map(normalizeTerm).filter(Boolean))];
    const ordered = DEFAULT_TERMS.filter((term) => normalized.includes(term));
    const values = ordered.length ? ordered : DEFAULT_TERMS;

    els.termSelector.innerHTML = `<option value="all">All Terms</option>`;

    values.forEach((term) => {
      const option = document.createElement("option");

      option.value = term;
      option.textContent = TERM_LABELS[term] || term;

      els.termSelector.appendChild(option);
    });

    const exists = [...els.termSelector.options].some((option) => option.value === previous);

    els.termSelector.value = exists ? previous : "all";
  }

  async function loadAvailableTerms() {
    updateTermUi();

    const year = selectedYear();
    const cls = selectedClass();

    if (!isJssClass(cls) || year === "all") {
      populateTermOptions(DEFAULT_TERMS);
      return;
    }

    try {
      const data = await fetchJson(`/api/results/terms?year=${encodeURIComponent(year)}&class=${encodeURIComponent(cls)}`);
      populateTermOptions(Array.isArray(data.terms) ? data.terms : DEFAULT_TERMS);
    } catch (error) {
      console.error("TERM LOAD ERROR:", error);
      populateTermOptions(DEFAULT_TERMS);
    }
  }


  // ==========================================================
  // 14. SUBJECT OPTIONS
  // ==========================================================

  function populateSubjectOptions(subjects, preserve = true) {
    if (!els.subjectSelector) return;

    const previous = preserve ? els.subjectSelector.value : "all";

    const uniqueSubjects = [...new Set(
      (subjects || []).map(String).map((value) => value.trim()).filter(Boolean)
    )].sort((a, b) => formatSubject(a).localeCompare(formatSubject(b)));

    els.subjectSelector.innerHTML = `<option value="all">All Subjects</option>`;

    uniqueSubjects.forEach((subject) => {
      const option = document.createElement("option");

      option.value = subject;
      option.textContent = formatSubject(subject);

      els.subjectSelector.appendChild(option);
    });

    const match = [...els.subjectSelector.options].find((option) => normalizeText(option.value) === normalizeText(previous));

    els.subjectSelector.value = match ? match.value : "all";
  }

  async function loadSubjectsFromApi() {
    if (!els.subjectSelector) return false;

    const year = selectedYear();
    const cls = selectedClass();
    const term = selectedTerm();

    if (year === "all" || cls === "all") return false;
    if (isJssClass(cls) && term === "all") return false;

    const params = new URLSearchParams({ year, class: cls });

    if (isJssClass(cls)) params.set("term", term);

    try {
      const data = await fetchJson(`/api/results/subjects?${params.toString()}`);

      populateSubjectOptions(Array.isArray(data.subjects) ? data.subjects : []);

      return true;
    } catch (error) {
      console.error("SUBJECT LOAD ERROR:", error);
      return false;
    }
  }

  function rebuildSubjectsFromLoadedResults() {
    const subjects = state.allResults.map((row) => getSubjectFolder(row) || getSubject(row)).filter(Boolean);
    populateSubjectOptions(subjects);
  }


  // ==========================================================
  // 15. CLASS ARMS
  // ==========================================================

  function rebuildClassArms() {
    if (!els.classArmSelector) return;

    const current = els.classArmSelector.value || "all";
    const cls = selectedClass();

    const arms = [...new Set(
      state.allResults
        .filter((row) => cls === "all" || getClassLevel(row) === cls || getClass(row) === cls)
        .map(getClassArm)
        .filter(Boolean)
    )].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

    els.classArmSelector.innerHTML = `<option value="all">All Arms</option>`;

    arms.forEach((arm) => {
      const option = document.createElement("option");

      option.value = arm;
      option.textContent = formatClassLabel(arm);

      els.classArmSelector.appendChild(option);
    });

    const exists = [...els.classArmSelector.options].some((option) => option.value === current);

    els.classArmSelector.value = exists ? current : "all";
  }


  // ==========================================================
  // 16. SESSION OPTIONS
  // ==========================================================

  function rebuildSessions() {
    if (!els.sessionSelector) return;

    const current = els.sessionSelector.value || "all";

    const sessions = [...new Set(
      state.allResults.map(getSession).filter(Boolean)
    )].sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));

    els.sessionSelector.innerHTML = `<option value="all">All Sessions</option>`;

    sessions.forEach((session) => {
      const option = document.createElement("option");

      option.value = session;
      option.textContent = session;

      els.sessionSelector.appendChild(option);
    });

    const exists = [...els.sessionSelector.options].some((option) => option.value === current);

    els.sessionSelector.value = exists ? current : "all";

    const field = els.sessionSelector.closest(".session-filter");

    if (field) field.hidden = sessions.length === 0;
  }


  // ==========================================================
  // 17. SERVER RESULTS QUERY
  // ==========================================================

  function buildResultsUrl() {
    const year = selectedYear();
    const cls = selectedClass();
    const term = selectedTerm();
    const subject = selectedSubject();

    const params = new URLSearchParams({ year, class: cls, subject });

    if (cls === "all") params.set("term", term);
    else if (isJssClass(cls)) params.set("term", term);
    else params.set("term", "all");

    return `/api/results/all?${params.toString()}`;
  }


  // ==========================================================
  // 18. LOAD RESULTS
  // ==========================================================

  async function loadAllResults({ silent = false } = {}) {
    const token = ++state.loadToken;

    state.loading = true;
    state.selectedKeys.clear();

    updateSelectionUi();

    if (!silent) setLoading("Loading examination results");

    try {
      const data = await fetchJson(buildResultsUrl());

      if (token !== state.loadToken) return;

      state.allResults = Array.isArray(data.results) ? data.results : [];

      rebuildClassArms();
      rebuildSessions();

      const subjectLoadedFromApi = await loadSubjectsFromApi();

      if (!subjectLoadedFromApi) rebuildSubjectsFromLoadedResults();

      applyFilters({ resetPage: true });

      if (!silent) showToast(`${state.allResults.length} result(s) loaded.`, "success");

    } catch (error) {
      if (token !== state.loadToken) return;

      console.error("RESULT LOAD ERROR:", error);

      state.allResults = [];
      state.filteredResults = [];

      updateStats([]);
      renderActiveFilters();

      setEmpty("Could not load results", error.message || "Please check the results API and try again.");

      if (els.pagination) els.pagination.innerHTML = "";
      if (els.paginationInfo) els.paginationInfo.textContent = "Showing 0 results";
      if (els.filteredResultCount) els.filteredResultCount.textContent = "0 records";

      if (!silent) showToast(error.message || "Could not load results.", "error");

    } finally {
      if (token === state.loadToken) state.loading = false;
    }
  }


  // ==========================================================
  // 19. CLIENT FILTERS
  // ==========================================================

  function applyFilters({ resetPage = true } = {}) {
    const arm = normalizeUpper(els.classArmSelector?.value || "all");
    const session = normalizeText(els.sessionSelector?.value || "all");
    const status = normalizeUpper(els.statusFilter?.value || "");
    const quickStatus = normalizeUpper(state.statusView === "all" ? "" : state.statusView);
    const query = normalizeText(els.globalSearch?.value || "");

    state.filteredResults = state.allResults.filter((row) => {
      const rowArm = getClassArm(row);
      const rowSession = normalizeText(getSession(row));
      const rowStatus = getStatus(row);

      const searchable = normalizeText([
        getStudentName(row), getAdmission(row), getYear(row), getClassLevel(row), getClassArm(row),
        getTerm(row), getTermLabel(row), getSubject(row), getSubjectFolder(row),
        getObjectiveScore(row), getEssayScore(row), getFinalScore(row),
        rowStatus, getResultState(row), getTime(row), getSubmittedAt(row), getSession(row)
      ].join(" "));

      const armOk = arm === "ALL" || rowArm === arm;
      const sessionOk = session === "all" || rowSession === session;
      const statusOk = !status || rowStatus === status;
      const quickStatusOk = !quickStatus || rowStatus === quickStatus;
      const searchOk = !query || searchable.includes(query);

      return armOk && sessionOk && statusOk && quickStatusOk && searchOk;
    });

    sortFilteredResults();

    if (resetPage) state.currentPage = 1;

    const loadedKeys = new Set(state.allResults.map(getStableKey));

    state.selectedKeys = new Set([...state.selectedKeys].filter((key) => loadedKeys.has(key)));

    renderTable();
    updateStats(state.filteredResults);
    renderActiveFilters();
    updateSelectionUi();
  }


  // ==========================================================
  // 20. SORTING
  // ==========================================================

  function sortValue(row, key) {
    switch (key) {
      case "student": return getStudentName(row);
      case "admission": return getAdmission(row);
      case "year": return parseNumber(getYear(row));
      case "class": return getClass(row);
      case "term": return DEFAULT_TERMS.indexOf(getTerm(row));
      case "subject": return formatSubject(getSubject(row));

      case "objective": return getObjectiveScore(row);
      case "essay": return getEssayScore(row) ?? -1;
      case "total": return getFinalScore(row) ?? -1;

      case "status": return getStatus(row);
      case "time": return getTimeSeconds(row);

      case "date": {
        const timestamp = Date.parse(getSubmittedAt(row));
        return Number.isFinite(timestamp) ? timestamp : getSubmittedAt(row);
      }

      default: return "";
    }
  }

  function sortFilteredResults() {
    const direction = state.sortDirection === "asc" ? 1 : -1;

    state.filteredResults.sort((rowA, rowB) => {
      const result = compareValues(sortValue(rowA, state.sortKey), sortValue(rowB, state.sortKey));

      if (result !== 0) return result * direction;

      return getStudentName(rowA).localeCompare(getStudentName(rowB));
    });
  }

  function setSort(key) {
    if (!key) return;

    if (state.sortKey === key) state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
    else {
      state.sortKey = key;
      state.sortDirection = ["date", "objective", "essay", "total"].includes(key) ? "desc" : "asc";
    }

    sortFilteredResults();

    state.currentPage = 1;

    renderTable();
    updateSortIcons();
  }

  function updateSortIcons() {
    $$(".results-table th.sortable").forEach((th) => {
      const icon = th.querySelector("i");

      if (!icon) return;

      const active = th.dataset.sort === state.sortKey;

      icon.className = active
        ? `fa-solid ${state.sortDirection === "asc" ? "fa-sort-up" : "fa-sort-down"}`
        : "fa-solid fa-sort";

      th.setAttribute("aria-sort", active ? (state.sortDirection === "asc" ? "ascending" : "descending") : "none");
    });
  }


  // ==========================================================
  // 21. PAGINATION
  // ==========================================================

  function totalPages() {
    return Math.max(1, Math.ceil(state.filteredResults.length / state.rowsPerPage));
  }

  function pageSlice() {
    const pages = totalPages();

    state.currentPage = Math.min(Math.max(1, state.currentPage), pages);

    const start = (state.currentPage - 1) * state.rowsPerPage;
    const end = Math.min(start + state.rowsPerPage, state.filteredResults.length);

    return { start, end, rows: state.filteredResults.slice(start, end) };
  }

  function renderPagination() {
    if (!els.pagination) return;

    const pages = totalPages();

    els.pagination.innerHTML = "";

    if (!state.filteredResults.length || pages <= 1) return;

    const makeButton = (label, page, options = {}) => {
      const button = document.createElement("button");

      button.type = "button";
      button.className = options.active ? "active" : "";
      button.innerHTML = label;
      button.disabled = Boolean(options.disabled);

      button.setAttribute("aria-label", options.ariaLabel || `Page ${page}`);

      button.addEventListener("click", () => {
        state.currentPage = page;

        renderTable();

        document.querySelector(".results-table-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });

      return button;
    };

    els.pagination.appendChild(
      makeButton('<i class="fa-solid fa-chevron-left"></i>', Math.max(1, state.currentPage - 1), {
        disabled: state.currentPage === 1,
        ariaLabel: "Previous page"
      })
    );

    const candidates = new Set([
      1, pages,
      state.currentPage - 2, state.currentPage - 1,
      state.currentPage,
      state.currentPage + 1, state.currentPage + 2
    ]);

    const pageNumbers = [...candidates].filter((page) => page >= 1 && page <= pages).sort((a, b) => a - b);

    let previous = 0;

    pageNumbers.forEach((page) => {
      if (previous && page - previous > 1) {
        const ellipsis = document.createElement("span");

        ellipsis.textContent = "…";
        ellipsis.style.padding = "0 4px";
        ellipsis.style.color = "#667085";

        els.pagination.appendChild(ellipsis);
      }

      els.pagination.appendChild(
        makeButton(String(page), page, {
          active: page === state.currentPage,
          ariaLabel: `Go to page ${page}`
        })
      );

      previous = page;
    });

    els.pagination.appendChild(
      makeButton('<i class="fa-solid fa-chevron-right"></i>', Math.min(pages, state.currentPage + 1), {
        disabled: state.currentPage === pages,
        ariaLabel: "Next page"
      })
    );
  }


  // ==========================================================
  // 22. CURRENT VIEW DESCRIPTION
  // ==========================================================

  function describeCurrentView() {
    const parts = [];

    if (selectedYear() !== "all") parts.push(selectedYear());
    if (selectedClass() !== "all") parts.push(selectedClass());

    if ((selectedClass() === "all" || isJssClass(selectedClass())) && selectedTerm() !== "all") parts.push(termLabel(selectedTerm()));
    if (selectedSubject() !== "all") parts.push(formatSubject(selectedSubject()));

    return parts.length
      ? `Showing ${parts.join(" • ")} examination results.`
      : "Showing all available examination results.";
  }


  // ==========================================================
  // 23. STATUS HTML
  // ==========================================================

  function resultStatusHtml(row) {
    const status = getStatus(row);
    const resultState = getResultState(row);

    if (status === "PASS") {
      return `<span class="status-pass"><i class="fa-solid fa-check"></i> PASS</span>`;
    }

    if (status === "FAIL") {
      return `<span class="status-fail"><i class="fa-solid fa-xmark"></i> FAIL</span>`;
    }

    let label = "Pending";

    if (resultState === "AWAITING ESSAY") label = "Awaiting Essay";
    if (resultState === "AWAITING OBJECTIVE") label = "Awaiting Objective";

    return `<span class="status-pending"><i class="fa-solid fa-clock"></i> ${escapeHtml(label)}</span>`;
  }


  // ==========================================================
  // 24. TABLE RENDERING
  // ==========================================================

  function renderTable() {
    if (!els.resultsBody) return;

    if (!state.filteredResults.length) {
      setEmpty();

      if (els.pagination) els.pagination.innerHTML = "";
      if (els.paginationInfo) els.paginationInfo.textContent = "Showing 0 results";
      if (els.tableSubtitle) els.tableSubtitle.textContent = "No result matches the current view.";
      if (els.filteredResultCount) els.filteredResultCount.textContent = "0 records";

      updateSelectionUi();
      updateSortIcons();
      applyColumnVisibility();

      return;
    }

    const { start, end, rows } = pageSlice();

    els.resultsBody.innerHTML = rows.map((row, pageIndex) => {
      const absoluteIndex = start + pageIndex;
      const key = getStableKey(row);

      const name = getStudentName(row);
      const admission = getAdmission(row);
      const year = getYear(row);
      const classArm = getClass(row);
      const term = getTerm(row);
      const subject = formatSubject(getSubject(row));

      const objective = objectiveDisplay(row);
      const essay = essayDisplay(row);
      const total = totalDisplay(row);

      const time = getTime(row);
      const date = getSubmittedAt(row);
      const checked = state.selectedKeys.has(key);

      return `
        <tr data-result-key="${escapeHtml(key)}" data-result-index="${absoluteIndex}">
          <td class="select-col" data-column-name="select">
            <input type="checkbox" class="row-check" data-key="${escapeHtml(key)}" aria-label="Select ${escapeHtml(name)}" ${checked ? "checked" : ""}>
          </td>

          <td data-column-name="student">
            <div class="student-cell">
              <span class="student-name">${escapeHtml(name)}</span>
              <span class="student-meta">${escapeHtml(admission || "No admission number")}</span>
            </div>
          </td>

          <td data-column-name="admission">${escapeHtml(admission || "—")}</td>
          <td data-column-name="year">${escapeHtml(year || "—")}</td>

          <td data-column-name="class">
            <span class="class-badge">${escapeHtml(formatClassLabel(classArm) || "—")}</span>
          </td>

          <td class="term-column" data-column-name="term">
            ${term ? `<span class="term-badge">${escapeHtml(termLabel(term))}</span>` : `<span aria-label="Not applicable">—</span>`}
          </td>

          <td data-column-name="subject"><strong>${escapeHtml(subject || "—")}</strong></td>

          <td class="score-cell objective-score-cell" data-column-name="objective">
            <strong>${escapeHtml(objective.text)}</strong>
            <span class="student-meta">${escapeHtml(objective.raw)}</span>
          </td>

          <td class="score-cell essay-score-cell" data-column-name="essay">
            ${
              !essay.available
                ? `<span class="score-na">N/A</span><span class="student-meta">No essay</span>`
                : essay.score === null
                  ? `<span class="score-pending">Pending</span><span class="student-meta">Out of ${escapeHtml(essay.max)}</span>`
                  : `<strong>${escapeHtml(essay.text)}</strong><span class="student-meta">Teacher scored</span>`
            }
          </td>

          <td class="score-cell final-score-cell" data-column-name="total">
            ${
              total.score === null
                ? `<span class="score-pending">Pending</span><span class="student-meta">${escapeHtml(total.state.replaceAll("_", " "))}</span>`
                : `<strong>${escapeHtml(total.text)}</strong><span class="student-meta">Final score</span>`
            }
          </td>

          <td data-column-name="status">${resultStatusHtml(row)}</td>

          <td data-column-name="time">${escapeHtml(time || "—")}</td>
          <td data-column-name="date">${escapeHtml(date || "—")}</td>

          <td class="actions-col" data-column-name="actions">
            <div class="row-action-group">
              <button class="view-btn view-result-btn" type="button" data-index="${absoluteIndex}" title="View result">
                <i class="fa-solid fa-eye"></i> View
              </button>

              <button class="delete-btn delete-row-btn" type="button" data-index="${absoluteIndex}" title="Delete result" aria-label="Delete result for ${escapeHtml(name)}">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    if (els.tableSubtitle) els.tableSubtitle.textContent = describeCurrentView();
    if (els.paginationInfo) els.paginationInfo.textContent = `Showing ${start + 1}–${end} of ${state.filteredResults.length} result(s)`;
    if (els.filteredResultCount) els.filteredResultCount.textContent = `${state.filteredResults.length} record${state.filteredResults.length === 1 ? "" : "s"}`;

    bindRenderedRowEvents();
    renderPagination();
    updateSelectionUi();
    updateSortIcons();
    applyColumnVisibility();

    if (state.compact) els.resultsTable?.classList.add("compact");
  }


  // ==========================================================
  // 25. TABLE ROW EVENTS
  // ==========================================================

  function bindRenderedRowEvents() {
    $$(".row-check").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const key = checkbox.dataset.key;

        if (!key) return;

        if (checkbox.checked) state.selectedKeys.add(key);
        else state.selectedKeys.delete(key);

        updateSelectionUi();
      });
    });

    $$(".view-result-btn").forEach((button) => {
      button.addEventListener("click", () => {
        const row = state.filteredResults[Number(button.dataset.index)];

        if (row) openSummary(row);
      });
    });

    $$(".delete-row-btn").forEach((button) => {
      button.addEventListener("click", () => {
        const row = state.filteredResults[Number(button.dataset.index)];

        if (!row) return;

        state.pendingDeleteRows = [row];

        openDeleteModal([row]);
      });
    });

    $$("#resultsBody tr[data-result-index]").forEach((rowElement) => {
      rowElement.addEventListener("dblclick", (event) => {
        if (event.target.closest("button, input, a")) return;

        const row = state.filteredResults[Number(rowElement.dataset.resultIndex)];

        if (row) openSummary(row);
      });
    });
  }


  // ==========================================================
  // 26. SELECTION
  // ==========================================================

  function currentPageRows() { return pageSlice().rows; }

  function updateSelectionUi() {
    const count = state.selectedKeys.size;

    if (els.selectedCountBadge) els.selectedCountBadge.textContent = `${count} selected`;
    if (els.deleteSelectedBtn) els.deleteSelectedBtn.disabled = count === 0;
    if (els.printSelectedBtn) els.printSelectedBtn.disabled = count === 0;

    if (els.selectAllRows) {
      const rows = currentPageRows();
      const selectedOnPage = rows.filter((row) => state.selectedKeys.has(getStableKey(row))).length;

      els.selectAllRows.checked = rows.length > 0 && selectedOnPage === rows.length;
      els.selectAllRows.indeterminate = selectedOnPage > 0 && selectedOnPage < rows.length;
    }
  }

  function getSelectedRecords() {
    return state.allResults.filter((row) => state.selectedKeys.has(getStableKey(row)));
  }

  function toggleSelectCurrentPage(checked) {
    currentPageRows().forEach((row) => {
      const key = getStableKey(row);

      if (checked) state.selectedKeys.add(key);
      else state.selectedKeys.delete(key);
    });

    renderTable();
  }


  // ==========================================================
  // 27. ACTIVE FILTER CHIPS
  // ==========================================================

  function renderActiveFilters() {
    if (!els.activeFilterChips) return;

    const chips = [];

    if (selectedYear() !== "all") chips.push(["Year", selectedYear()]);
    if (selectedClass() !== "all") chips.push(["Class", selectedClass()]);

    const arm = els.classArmSelector?.value || "all";

    if (arm !== "all") chips.push(["Arm", formatClassLabel(arm)]);

   if ((selectedClass() === "all" || isJssClass(selectedClass())) && selectedTerm() !== "all") chips.push(["Term", termLabel(selectedTerm())]);
    if (selectedSubject() !== "all") chips.push(["Subject", formatSubject(selectedSubject())]);

    const status = els.statusFilter?.value || "";

    if (status) chips.push(["Status", status]);
    if (state.statusView !== "all") chips.push(["Quick View", state.statusView]);

    const session = els.sessionSelector?.value || "all";

    if (session !== "all") chips.push(["Session", session]);

    const query = els.globalSearch?.value?.trim();

    if (query) chips.push(["Search", query]);

    if (!chips.length) {
      els.activeFilterChips.innerHTML = `<span class="filter-chip">All Results</span>`;
      return;
    }

    els.activeFilterChips.innerHTML = chips
      .map(([label, value]) => `<span class="filter-chip">${escapeHtml(label)}: ${escapeHtml(value)}</span>`)
      .join("");
  }


  // ==========================================================
  // 28. STATISTICS
  // ==========================================================

  function updateStats(rows) {
    const completed = rows.filter((row) => getFinalScore(row) !== null);
    const scores = completed.map(getFinalScore).filter((score) => Number.isFinite(score));

    const total = rows.length;
    const passCount = completed.filter((row) => getStatus(row) === "PASS").length;
    const passRate = completed.length ? Math.round((passCount / completed.length) * 100) : 0;
    const averageScore = scores.length ? roundScore(scores.reduce((sum, score) => sum + score, 0) / scores.length, 1) : 0;

    const subjects = new Set(
      rows.map((row) => normalizeText(getSubjectFolder(row) || getSubject(row))).filter(Boolean)
    );

    safeSetText(els.statTotalResults, total);
    safeSetText(els.statPassRate, `${scoreText(passRate)}%`);
    safeSetText(els.statAvgScore, `${scoreText(averageScore)}%`);
    safeSetText(els.statSubjects, subjects.size);

    const validTimes = rows.map(getTimeSeconds).filter(Number.isFinite);
    const averageTime = validTimes.length ? validTimes.reduce((sum, value) => sum + value, 0) / validTimes.length : NaN;

    safeSetText(els.avgTimeTaken, formatSeconds(averageTime));

    if (!scores.length) {
      safeSetText(els.topPerformerName, "—");
      safeSetText(els.topPerformerMeta, "No completed result data");
      safeSetText(els.highestScore, "0%");
      safeSetText(els.lowestScore, "0%");
      return;
    }

    const ranked = [...completed].sort((a, b) => {
      const scoreDiff = (getFinalScore(b) ?? -1) - (getFinalScore(a) ?? -1);

      if (scoreDiff !== 0) return scoreDiff;

      const timeA = getTimeSeconds(a);
      const timeB = getTimeSeconds(b);

      if (Number.isFinite(timeA) && Number.isFinite(timeB)) return timeA - timeB;

      return getStudentName(a).localeCompare(getStudentName(b));
    });

    const top = ranked[0];

    const topMeta = [
      getClass(top),
      getTerm(top) ? termLabel(getTerm(top)) : "",
      formatSubject(getSubject(top)),
      `${scoreText(getFinalScore(top))}%`
    ].filter(Boolean).join(" • ");

    safeSetText(els.topPerformerName, getStudentName(top));
    safeSetText(els.topPerformerMeta, topMeta);
    safeSetText(els.highestScore, `${scoreText(Math.max(...scores))}%`);
    safeSetText(els.lowestScore, `${scoreText(Math.min(...scores))}%`);
  }


  // ==========================================================
  // 29. COLUMN VISIBILITY
  // ==========================================================

  function applyColumnVisibility() {
    COLUMN_ORDER.forEach((columnName) => {
      const visible = state.visibleColumns.has(columnName);

      $$(`[data-column-name="${columnName}"]`).forEach((cell) => {
        cell.style.display = visible ? "" : "none";
      });
    });
  }

  function syncColumnCheckboxes() {
    $$("#columnMenu input[data-column]").forEach((checkbox) => {
      checkbox.checked = state.visibleColumns.has(checkbox.dataset.column);
    });
  }

  function setColumnVisible(column, visible) {
    if (!column) return;

    if (visible) state.visibleColumns.add(column);
    else state.visibleColumns.delete(column);

    state.visibleColumns.add("select");
    state.visibleColumns.add("actions");

    applyColumnVisibility();
  }

  function resetColumns() {
    state.visibleColumns = new Set(COLUMN_ORDER);

    syncColumnCheckboxes();
    applyColumnVisibility();
  }


  // ==========================================================
  // 30. DELETE MODAL
  // ==========================================================

  function openDeleteModal(rows = null) {
    const records = rows || getSelectedRecords();

    if (!records.length) {
      showToast("Select at least one result to delete.", "warning");
      return;
    }

    state.pendingDeleteRows = records;

    const title = $("deleteModalTitle");

    if (title) title.textContent = records.length === 1 ? "Delete this result?" : `Delete ${records.length} selected results?`;

    els.deleteModal?.classList.remove("hidden");

    document.body.style.overflow = "hidden";
  }

  function closeDeleteModal() {
    els.deleteModal?.classList.add("hidden");

    state.pendingDeleteRows = null;

    if (
      !els.adminPrintSummary?.classList.contains("show") &&
      els.essayScoreModal?.classList.contains("hidden")
    ) {
      document.body.style.overflow = "";
    }
  }


  // ==========================================================
  // 31. DELETE PAYLOAD
  // ==========================================================

  function buildDeletePayload(rows) {
    return rows.map((row) => ({
      ...row,
      Year: getYear(row),
      "Class Level": getClassLevel(row),
      "Class Arm": getClassArm(row),
      Class: getClass(row),
      "Class Category": getClassCategory(row),
      Term: getTerm(row),
      Subject: getSubject(row),
      "Subject Folder": getSubjectFolder(row),
      "Student Name": getStudentName(row),
      "Admission No": getAdmission(row)
    }));
  }

  async function confirmDelete() {
    const records = state.pendingDeleteRows?.length ? state.pendingDeleteRows : getSelectedRecords();

    if (!records.length) {
      showToast("No result is selected.", "warning");
      closeDeleteModal();
      return;
    }

    const button = els.confirmDeleteBtn;
    const text = button?.querySelector(".btn-text");
    const spinner = button?.querySelector(".btn-spinner");

    if (button) button.disabled = true;

    text?.classList.add("hidden");
    spinner?.classList.remove("hidden");

    try {
      const data = await fetchJson("/api/results/delete", {
        method: "POST",
        body: JSON.stringify({ delete_items: buildDeletePayload(records) })
      });

      const deleted = Number(data.deleted ?? records.length);

      showToast(
        data.message
          ? `${data.message}${Number.isFinite(deleted) ? ` (${deleted})` : ""}`
          : `${deleted} result(s) deleted.`,
        "success"
      );

      closeDeleteModal();

      state.selectedKeys.clear();

      await loadAllResults({ silent: true });

    } catch (error) {
      console.error("DELETE ERROR:", error);
      showToast(error.message || "Could not delete the selected result(s).", "error");

    } finally {
      if (button) button.disabled = false;

      text?.classList.remove("hidden");
      spinner?.classList.add("hidden");
    }
  }


  // ==========================================================
  // 32. RESULT DETAILS MODAL
  // ==========================================================

  function setSummaryStatus(status) {
    const badge = $("ap_status");

    if (!badge) return;

    badge.textContent = status || "—";

    if (status === "PASS") badge.style.background = "#15803d";
    else if (status === "FAIL") badge.style.background = "#c62828";
    else badge.style.background = "#b7791f";
  }

  function openSummary(row) {
    if (!row) return;

    state.currentSummaryRow = row;

    const objective = objectiveDisplay(row);
    const essay = essayDisplay(row);
    const total = totalDisplay(row);

    const totalQuestions = getQuestionTotal(row);
    const correct = getCorrect(row);
    const accuracy = totalQuestions ? roundScore((correct / totalQuestions) * 100, 1) : getObjectivePercentage(row);

    safeSetText("ap_studentName", getStudentName(row) || "—");
    safeSetText("ap_studentID", getAdmission(row) || "—");
    safeSetText("ap_studentNameMirror", getStudentName(row) || "—");
    safeSetText("ap_studentIDMirror", getAdmission(row) || "—");

    safeSetText("ap_year", getYear(row) || "—");
    safeSetText("ap_studentClass", getClass(row) || "—");
    safeSetText("ap_studentCategory", getClassCategory(row) || "—");
    safeSetText("ap_term", getTerm(row) ? termLabel(getTerm(row)) : "Not Applicable");

    safeSetText("ap_subject", formatSubject(getSubject(row)) || "—");

    safeSetText("ap_objectiveScore", objective.text);
    safeSetText("ap_objectiveRaw", objective.raw);

    safeSetText("ap_essayScore", essay.available ? essay.text : "N/A");
    safeSetText("ap_essayState", essay.available ? essay.state : "No essay section");

    safeSetText("ap_finalScore", total.text);

    // Existing hidden compatibility fields.
    safeSetText("ap_percent", total.score === null ? "Pending" : `${scoreText(total.score)}%`);
    safeSetText("ap_rawScore", `${scoreText(correct)} / ${scoreText(totalQuestions)}`);
    safeSetText("ap_accuracy", `${scoreText(accuracy)}%`);

    safeSetText("ap_correct", scoreText(correct));
    safeSetText("ap_total", scoreText(totalQuestions));
    safeSetText("ap_time", getTime(row) || "—");
    safeSetText("ap_date", getSubmittedAt(row) || "—");

    setSummaryStatus(getStatus(row));

    if (els.summaryTermRow) els.summaryTermRow.hidden = !isJssClass(getClassLevel(row)) && !getTerm(row);

    els.summaryOverlay?.classList.add("show", "active");
    els.adminPrintSummary?.classList.add("show", "active");

    document.body.style.overflow = "hidden";

    setTimeout(() => els.summaryCloseBtn?.focus(), 50);
  }

  function closeSummary() {
    els.summaryOverlay?.classList.remove("show", "active");
    els.adminPrintSummary?.classList.remove("show", "active");

    state.currentSummaryRow = null;

    if (
      els.deleteModal?.classList.contains("hidden") &&
      els.essayScoreModal?.classList.contains("hidden")
    ) {
      document.body.style.overflow = "";
    }
  }

  function printCurrentSummary() {
    if (!state.currentSummaryRow) {
      showToast("Open a result before printing.", "warning");
      return;
    }

    window.print();
  }

// ==========================================================
// 33. ESSAY MODAL CONTEXT
// ==========================================================

function validateEssayContext() {
  let year = selectedYear();
  let classLevel = selectedClass();
  let subject = selectedSubject();
  let term = selectedTerm();
  let arm = els.classArmSelector?.value || "all";

  // ----------------------------------------------------------
  // AUTO-DETECT FROM CURRENT VISIBLE RESULTS
  // ----------------------------------------------------------

  const visibleRows = Array.isArray(state.filteredResults) ? state.filteredResults : [];

  const years = [...new Set(visibleRows.map(getYear).filter(Boolean))];
  const classes = [...new Set(visibleRows.map(getClassLevel).filter(Boolean))];
  const subjects = [...new Set(visibleRows.map((row) => getSubjectFolder(row) || getSubject(row)).filter(Boolean))];
  const terms = [...new Set(visibleRows.map(getTerm).filter(Boolean))];
  const arms = [...new Set(visibleRows.map(getClassArm).filter(Boolean))];

  if (year === "all" && years.length === 1) year = years[0];
  if (classLevel === "all" && classes.length === 1) classLevel = classes[0];
  if (subject === "all" && subjects.length === 1) subject = subjects[0];
  if (term === "all" && terms.length === 1) term = terms[0];
  if (arm === "all" && arms.length === 1) arm = arms[0];

  // ----------------------------------------------------------
  // VALIDATION
  // ----------------------------------------------------------

  if (!year || year === "all") {
    return {
      ok: false,
      message: years.length > 1
        ? "More than one examination year is currently displayed. Please narrow the results to one year before entering essay scores."
        : "No examination year could be detected from the current results."
    };
  }

  if (!classLevel || classLevel === "all") {
    return {
      ok: false,
      message: classes.length > 1
        ? "More than one class is currently displayed. Please narrow the results to one class before entering essay scores."
        : "No class could be detected from the current results."
    };
  }

  if (!subject || subject === "all") {
    return {
      ok: false,
      message: subjects.length > 1
        ? "More than one subject is currently displayed. Please narrow the results to one subject before entering essay scores."
        : "No subject could be detected from the current results."
    };
  }

  if (isJssClass(classLevel) && (!term || term === "all")) {
    return {
      ok: false,
      message: terms.length > 1
        ? `More than one term is currently displayed for ${classLevel}. Please narrow the results to one term before entering essay scores.`
        : `No term could be detected for ${classLevel}.`
    };
  }

  return {
    ok: true,
    year,
    classLevel,
    term: isJssClass(classLevel) ? term : "",
    subject,
    arm
  };
}

function resetEssayState() {
  state.essay.students = [];
  state.essay.filteredStudents = [];
  state.essay.changes = new Map();
  state.essay.originalScores = new Map();
  state.essay.search = "";
  state.essay.pendingOnly = false;

  if (els.essayStudentSearch) els.essayStudentSearch.value = "";
  if (els.essayPendingOnly) els.essayPendingOnly.checked = false;

  updateEssayUnsavedCount();
}

function setEssayContextUi() {
  const essay = state.essay;

  safeSetText(els.essayContextYear, essay.year || "—");
  safeSetText(els.essayContextClass, essay.classLevel || "—");
  safeSetText(els.essayContextTerm, essay.term ? termLabel(essay.term) : "Not Applicable");
  safeSetText(els.essayContextSubject, formatSubject(essay.subject) || "—");

  if (els.essayContextTermWrap) els.essayContextTermWrap.classList.toggle("hidden", !essay.term);

  safeSetText(els.essayObjectiveMax, scoreText(essay.objectiveMax));
  safeSetText(els.essayMaximumScore, scoreText(essay.essayMax));
  safeSetText(els.essayHeaderMax, scoreText(essay.essayMax));

  if (els.essayAvailabilityBadge) {
    els.essayAvailabilityBadge.classList.toggle("available", essay.available);
    els.essayAvailabilityBadge.classList.toggle("unavailable", !essay.available);

    els.essayAvailabilityBadge.innerHTML = essay.available
      ? `<i class="fa-solid fa-circle-check"></i> Essay Available`
      : `<i class="fa-solid fa-circle-xmark"></i> No Essay`;
  }
}


// ==========================================================
// 34. ESSAY API URL
// ==========================================================

function buildEssayUrl() {
  const params = new URLSearchParams({
    year: state.essay.year,
    class: state.essay.classLevel,
    subject: state.essay.subject
  });

  if (state.essay.term) params.set("term", state.essay.term);
  if (state.essay.arm && state.essay.arm !== "all") params.set("arm", state.essay.arm);

  return `/api/results/essay?${params.toString()}`;
}


// ==========================================================
// 35. ESSAY STUDENT NORMALIZATION
// ==========================================================

function normalizeEssayStudent(student) {
  const admission = String(
    student?.admission_number ??
    student?.Admission_number ??
    student?.["Admission No"] ??
    student?.student_id ??
    ""
  ).trim();

  const firstName = String(student?.first_name ?? student?.First_name ?? "").trim();
  const lastName = String(student?.last_name ?? student?.Last_name ?? "").trim();
  const otherNames = String(student?.other_names ?? student?.Other_names ?? "").trim();

  const suppliedName = String(
    student?.student_name ??
    student?.full_name ??
    student?.["Student Name"] ??
    student?.name ??
    ""
  ).trim();

  const name = suppliedName || [lastName, firstName, otherNames].filter(Boolean).join(" ");

  const classArm = String(
    student?.class_arm ??
    student?.Class ??
    student?.class_name ??
    student?.student_class ??
    state.essay.classLevel
  ).trim().toUpperCase();

  const objectiveCorrect = parseNullableNumber(
    student?.objective_correct ??
    student?.correct ??
    student?.Correct
  );

  const objectiveTotal = parseNullableNumber(
    student?.objective_total ??
    student?.total_questions ??
    student?.Total
  );

  let objectiveScore = parseNullableNumber(
    student?.objective_score ??
    student?.objective_mark ??
    student?.["Objective Score"] ??
    student?.["Objective Mark"]
  );

  if (objectiveScore === null && objectiveCorrect !== null && objectiveTotal !== null && objectiveTotal > 0) {
    objectiveScore = roundScore((objectiveCorrect / objectiveTotal) * state.essay.objectiveMax);
  }

  const essayScore = parseNullableNumber(
    student?.essay_score ??
    student?.theory_score ??
    student?.["Essay Score"] ??
    student?.["Theory Score"]
  );

  const hasObjective = boolValue(
    student?.has_objective,
    objectiveScore !== null || (objectiveCorrect !== null && objectiveTotal !== null && objectiveTotal > 0)
  );

  return {
    ...student,
    admission_number: admission,
    student_name: name || admission || "Unknown Student",
    class_arm: classArm,
    objective_score: objectiveScore,
    objective_correct: objectiveCorrect,
    objective_total: objectiveTotal,
    essay_score: essayScore === null ? null : roundScore(essayScore),
    has_objective: hasObjective,
    essay_saved: boolValue(student?.essay_saved, essayScore !== null)
  };
}

function essayStudentKey(student) {
  return normalizeUpper(student.admission_number || student.student_name);
}


  // ==========================================================
  // 36. OPEN / CLOSE ESSAY MODAL
  // ==========================================================

  async function openEssayScoreManager() {
    const context = validateEssayContext();

    if (!context.ok) {
      showToast(context.message, "warning");
      return;
    }

    resetEssayState();

    state.essay.year = context.year;
    state.essay.classLevel = context.classLevel;
    state.essay.term = context.term;
    state.essay.subject = context.subject;
    state.essay.arm = context.arm;
    state.essay.objectiveMax = 60;
    state.essay.essayMax = 40;
    state.essay.totalMax = 100;
    state.essay.available = true;

    setEssayContextUi();

    els.essayScoreModal?.classList.remove("hidden");
    document.body.style.overflow = "hidden";

    await loadEssayStudents();
  }

  function closeEssayScoreManager(force = false) {
    if (!force && state.essay.changes.size > 0) {
      const confirmed = window.confirm(
        `${state.essay.changes.size} essay score change(s) have not been saved.\n\nClose without saving?`
      );

      if (!confirmed) return;
    }

    els.essayScoreModal?.classList.add("hidden");

    resetEssayState();

    if (
      !els.adminPrintSummary?.classList.contains("show") &&
      els.deleteModal?.classList.contains("hidden")
    ) {
      document.body.style.overflow = "";
    }
  }


  // ==========================================================
  // 37. ESSAY MODAL STATES
  // ==========================================================

  function setEssayLoading() {
    if (!els.essayScoreBody) return;

    els.essayScoreBody.innerHTML = `
      <tr>
        <td colspan="8" class="essay-score-placeholder">
          <span class="essay-placeholder-icon"><i class="fa-solid fa-spinner fa-spin"></i></span>
          <strong>Loading class register</strong>
          <span>Reading students and existing essay scores...</span>
        </td>
      </tr>
    `;
  }

  function setEssayEmpty(title = "No students found", message = "No students were found for this class.") {
    if (!els.essayScoreBody) return;

    els.essayScoreBody.innerHTML = `
      <tr>
        <td colspan="8" class="essay-score-placeholder">
          <span class="essay-placeholder-icon"><i class="fa-solid fa-user-slash"></i></span>
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(message)}</span>
        </td>
      </tr>
    `;
  }

  function setEssayError(message) {
    if (!els.essayScoreBody) return;

    els.essayScoreBody.innerHTML = `
      <tr>
        <td colspan="8" class="essay-score-placeholder">
          <span class="essay-placeholder-icon"><i class="fa-solid fa-triangle-exclamation"></i></span>
          <strong>Could not load essay scores</strong>
          <span>${escapeHtml(message)}</span>
        </td>
      </tr>
    `;
  }


  // ==========================================================
  // 38. LOAD ESSAY STUDENTS
  // ==========================================================

  async function loadEssayStudents() {
    state.essay.loading = true;

    setEssayLoading();

    try {
      const data = await fetchJson(buildEssayUrl());

      state.essay.objectiveMax = parseNumber(data.objective_max ?? data.objective_weight, 60);
      state.essay.essayMax = parseNumber(data.essay_max ?? data.essay_weight, 40);
      state.essay.totalMax = parseNumber(data.total_max, 100);

      if (state.essay.objectiveMax <= 0) state.essay.objectiveMax = 60;
      if (state.essay.essayMax < 0) state.essay.essayMax = 40;

      state.essay.available = data.essay_available === undefined
        ? true
        : boolValue(data.essay_available, true);

      const records = Array.isArray(data.students)
        ? data.students
        : Array.isArray(data.results)
          ? data.results
          : [];

      state.essay.students = records.map(normalizeEssayStudent);

      state.essay.originalScores.clear();

      state.essay.students.forEach((student) => {
        state.essay.originalScores.set(essayStudentKey(student), student.essay_score);
      });

      setEssayContextUi();
      filterEssayStudents();

      if (!state.essay.available) {
        showToast("This examination has no essay / theory section.", "warning");
      }

    } catch (error) {
      console.error("ESSAY SCORE LOAD ERROR:", error);

      state.essay.students = [];
      state.essay.filteredStudents = [];

      setEssayError(
        error.message ||
        "The essay result backend is not connected yet."
      );

      /*
       * During development, objective-result students can still be
       * displayed as a fallback. The final essay_results.py endpoint
       * will replace this with the complete class database roster.
       */
      const fallback = buildEssayFallbackFromLoadedResults();

      if (fallback.length) {
        state.essay.students = fallback;
        filterEssayStudents();

        showToast(
          "Essay API is not connected yet. Showing students with existing objective results only.",
          "warning"
        );
      } else {
        showToast(error.message || "Could not load class register.", "error");
      }

    } finally {
      state.essay.loading = false;
    }
  }

  function buildEssayFallbackFromLoadedResults() {
    const seen = new Set();
    const records = [];

    state.allResults.forEach((row) => {
      if (String(getYear(row)) !== String(state.essay.year)) return;
      if (getClassLevel(row) !== state.essay.classLevel) return;

      if (state.essay.term && getTerm(row) !== state.essay.term) return;

      const subjectMatches =
        normalizeText(getSubject(row)) === normalizeText(state.essay.subject) ||
        normalizeText(getSubjectFolder(row)) === normalizeText(state.essay.subject);

      if (!subjectMatches) return;

      if (state.essay.arm !== "all" && normalizeUpper(getClassArm(row)) !== normalizeUpper(state.essay.arm)) return;

      const admission = getAdmission(row);
      const key = normalizeUpper(admission || getStudentName(row));

      if (seen.has(key)) return;

      seen.add(key);

      records.push(normalizeEssayStudent({
        admission_number: admission,
        student_name: getStudentName(row),
        class_arm: getClassArm(row),
        objective_score: getObjectiveScore(row),
        objective_correct: getCorrect(row),
        objective_total: getQuestionTotal(row),
        has_objective: true,
        essay_score: getEssayScore(row)
      }));
    });

    return records;
  }


  // ==========================================================
  // 39. ESSAY STUDENT FILTER
  // ==========================================================

  function filterEssayStudents() {
    const search = normalizeText(els.essayStudentSearch?.value || "");
    const pendingOnly = Boolean(els.essayPendingOnly?.checked);

    state.essay.search = search;
    state.essay.pendingOnly = pendingOnly;

    state.essay.filteredStudents = state.essay.students.filter((student) => {
      const key = essayStudentKey(student);
      const currentScore = state.essay.changes.has(key)
        ? state.essay.changes.get(key)
        : student.essay_score;

      const searchable = normalizeText([
        student.student_name,
        student.admission_number,
        student.class_arm
      ].join(" "));

      const searchOk = !search || searchable.includes(search);
      const pendingOk = !pendingOnly || currentScore === null || currentScore === undefined || currentScore === "";

      return searchOk && pendingOk;
    });

    renderEssayStudents();
  }


  // ==========================================================
  // 40. ESSAY RESULT CALCULATION
  // ==========================================================

  function calculateEssayStudentTotal(student, essayScore) {
    if (!student.has_objective || student.objective_score === null) return null;
    if (essayScore === null || essayScore === undefined || essayScore === "") return null;

    return roundScore(Number(student.objective_score) + Number(essayScore));
  }

  function essayStudentStatus(student, essayScore) {
    const hasObjective = Boolean(student.has_objective && student.objective_score !== null);
    const hasEssay = essayScore !== null && essayScore !== undefined && essayScore !== "";

    if (hasObjective && hasEssay) return "COMPLETE";
    if (hasObjective && !hasEssay) return "AWAITING ESSAY";
    if (!hasObjective && hasEssay) return "AWAITING OBJECTIVE";

    return "PENDING";
  }


  // ==========================================================
  // 41. RENDER ESSAY STUDENTS
  // ==========================================================

  function renderEssayStudents() {
    if (!els.essayScoreBody) return;

    const students = state.essay.filteredStudents;

    safeSetText(els.essayStudentCount, students.length);

    if (!students.length) {
      setEssayEmpty(
        state.essay.students.length ? "No matching students" : "No students found",
        state.essay.students.length
          ? "Try changing the search or pending filter."
          : "No student records were returned for this class."
      );

      return;
    }

    els.essayScoreBody.innerHTML = students.map((student, index) => {
      const key = essayStudentKey(student);

      const essayScore = state.essay.changes.has(key)
        ? state.essay.changes.get(key)
        : student.essay_score;

      const total = calculateEssayStudentTotal(student, essayScore);
      const status = essayStudentStatus(student, essayScore);

      const objectiveHtml = student.has_objective && student.objective_score !== null
        ? `
          <strong>${escapeHtml(scoreText(student.objective_score))} / ${escapeHtml(scoreText(state.essay.objectiveMax))}</strong>
          <span class="essay-cell-meta">${
            student.objective_total
              ? `${escapeHtml(scoreText(student.objective_correct))} / ${escapeHtml(scoreText(student.objective_total))} questions`
              : "Objective available"
          }</span>
        `
        : `
          <span class="essay-pending-value">Pending</span>
          <span class="essay-cell-meta">CBT not submitted</span>
        `;

      const totalHtml = total !== null
        ? `
          <strong>${escapeHtml(scoreText(total))} / 100</strong>
          <span class="essay-cell-meta">${total >= 50 ? "Pass" : "Fail"}</span>
        `
        : `
          <span class="essay-pending-value">Pending</span>
          <span class="essay-cell-meta">${
            status === "AWAITING OBJECTIVE"
              ? "Awaiting objective"
              : status === "AWAITING ESSAY"
                ? "Awaiting essay"
                : "Incomplete"
          }</span>
        `;

      let statusLabel = "Pending";
      let statusClass = "pending";

      if (status === "COMPLETE") {
        statusLabel = "Complete";
        statusClass = "complete";
      } else if (status === "AWAITING ESSAY") {
        statusLabel = "Essay Pending";
        statusClass = "essay-pending";
      } else if (status === "AWAITING OBJECTIVE") {
        statusLabel = "OBJ Pending";
        statusClass = "objective-pending";
      }

      return `
        <tr data-essay-key="${escapeHtml(key)}">
          <td class="essay-number-col">${index + 1}</td>

          <td>
            <div class="essay-student-cell">
              <span class="essay-student-avatar">${escapeHtml((student.student_name || "?").charAt(0).toUpperCase())}</span>
              <div>
                <strong>${escapeHtml(student.student_name)}</strong>
                <span>${escapeHtml(student.admission_number || "No admission number")}</span>
              </div>
            </div>
          </td>

          <td>${escapeHtml(student.admission_number || "—")}</td>
          <td><span class="class-badge">${escapeHtml(formatClassLabel(student.class_arm) || "—")}</span></td>

          <td class="essay-objective-cell">${objectiveHtml}</td>

          <td class="essay-entry-cell">
            ${
              state.essay.available
                ? `
                  <div class="essay-input-wrap">
                    <input
                      class="essay-score-input"
                      type="number"
                      inputmode="decimal"
                      step="0.25"
                      min="0"
                      max="${escapeHtml(state.essay.essayMax)}"
                      data-key="${escapeHtml(key)}"
                      value="${essayScore === null || essayScore === undefined ? "" : escapeHtml(scoreText(essayScore))}"
                      placeholder="—"
                      aria-label="Essay score for ${escapeHtml(student.student_name)}"
                    >
                    <span>/ ${escapeHtml(scoreText(state.essay.essayMax))}</span>
                  </div>
                `
                : `<span class="score-na">N/A</span>`
            }
          </td>

          <td class="essay-total-cell">${totalHtml}</td>

          <td>
            <span class="essay-row-status ${escapeHtml(statusClass)}">
              ${escapeHtml(statusLabel)}
            </span>
          </td>
        </tr>
      `;
    }).join("");

    bindEssayInputs();
  }


  // ==========================================================
  // 42. ESSAY INPUT EVENTS
  // ==========================================================

  function bindEssayInputs() {
    $$(".essay-score-input", els.essayScoreBody).forEach((input) => {
      input.addEventListener("input", () => handleEssayInput(input));

      input.addEventListener("blur", () => {
        if (!input.value.trim()) return;

        const value = Number.parseFloat(input.value);

        if (Number.isFinite(value)) input.value = scoreText(roundScore(value));
      });
    });
  }

  function handleEssayInput(input) {
    const key = normalizeUpper(input.dataset.key || "");

    if (!key) return;

    const raw = input.value.trim();
    const student = state.essay.students.find((item) => essayStudentKey(item) === key);

    if (!student) return;

    let value = null;

    if (raw !== "") {
      value = Number.parseFloat(raw);

      if (!Number.isFinite(value)) {
        input.classList.add("invalid");
        return;
      }

      if (value < 0 || value > state.essay.essayMax) {
        input.classList.add("invalid");
        showToast(`Essay score must be between 0 and ${scoreText(state.essay.essayMax)}.`, "warning");
        return;
      }

      value = roundScore(value);
    }

    input.classList.remove("invalid");

    const original = state.essay.originalScores.get(key) ?? null;

    if (
      (original === null && value === null) ||
      (original !== null && value !== null && Number(original) === Number(value))
    ) {
      state.essay.changes.delete(key);
    } else {
      state.essay.changes.set(key, value);
    }

    updateEssayUnsavedCount();

    /*
     * Re-render so combined total and row state update immediately.
     * Keep focus on the edited student afterwards.
     */
    renderEssayStudents();

    const newInput = $(`.essay-score-input[data-key="${CSS.escape(key)}"]`);

    if (newInput) {
      newInput.focus();
      try { newInput.setSelectionRange(newInput.value.length, newInput.value.length); } catch {}
    }
  }

  function updateEssayUnsavedCount() {
    safeSetText(els.essayUnsavedCount, state.essay.changes.size);

    if (els.saveEssayScoresBtn) els.saveEssayScoresBtn.disabled = state.essay.changes.size === 0 || !state.essay.available;
  }


  // ==========================================================
  // 43. RESET ESSAY CHANGES
  // ==========================================================

  function resetEssayChanges() {
    if (!state.essay.changes.size) {
      showToast("There are no unsaved essay score changes.", "info");
      return;
    }

    state.essay.changes.clear();

    renderEssayStudents();
    updateEssayUnsavedCount();

    showToast("Unsaved essay score changes were reset.", "success");
  }


  // ==========================================================
  // 44. SAVE ESSAY SCORES
  // ==========================================================

  async function saveEssayScores() {
    if (!state.essay.available) {
      showToast("This examination does not contain an essay section.", "warning");
      return;
    }

    if (!state.essay.changes.size) {
      showToast("No essay score changes to save.", "info");
      return;
    }

    const scores = [];

    for (const [key, score] of state.essay.changes.entries()) {
      const student = state.essay.students.find((item) => essayStudentKey(item) === key);

      if (!student) continue;

      if (score !== null && (Number(score) < 0 || Number(score) > state.essay.essayMax)) {
        showToast(
          `${student.student_name}: score must be between 0 and ${scoreText(state.essay.essayMax)}.`,
          "error"
        );
        return;
      }

      scores.push({
        admission_number: student.admission_number,
        student_name: student.student_name,
        class_arm: student.class_arm,
        score
      });
    }

    if (!scores.length) return;

    const payload = {
      year: state.essay.year,
      class: state.essay.classLevel,
      class_level: state.essay.classLevel,
      arm: state.essay.arm === "all" ? "" : state.essay.arm,
      term: state.essay.term,
      subject: state.essay.subject,

      objective_max: state.essay.objectiveMax,
      essay_max: state.essay.essayMax,
      total_max: state.essay.totalMax,

      scores
    };

    const button = els.saveEssayScoresBtn;
    const text = button?.querySelector(".btn-text");
    const spinner = button?.querySelector(".btn-spinner");

    if (button) button.disabled = true;

    text?.classList.add("hidden");
    spinner?.classList.remove("hidden");

    try {
      const data = await fetchJson("/api/results/essay/save", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      const savedCount = Number(data.saved_count ?? data.updated ?? scores.length);

      showToast(`${savedCount} essay score${savedCount === 1 ? "" : "s"} saved successfully.`, "success");

      state.essay.changes.clear();

      await loadEssayStudents();
      await loadAllResults({ silent: true });

      window.dispatchEvent(new CustomEvent("emis:essay-scores-changed", {
        detail: {
          year: state.essay.year,
          class: state.essay.classLevel,
          term: state.essay.term,
          subject: state.essay.subject
        }
      }));

    } catch (error) {
      console.error("ESSAY SAVE ERROR:", error);

      showToast(
        error.message || "Could not save essay scores. The essay backend may not be connected yet.",
        "error"
      );

    } finally {
      if (button) button.disabled = state.essay.changes.size === 0;

      text?.classList.remove("hidden");
      spinner?.classList.add("hidden");
    }
  }


  // ==========================================================
  // 45. ESSAY SEARCH / FILTER EVENTS
  // ==========================================================

  const filterEssaySearch = debounce(() => filterEssayStudents(), 120);

  els.essayStudentSearch?.addEventListener("input", filterEssaySearch);

  els.clearEssaySearchBtn?.addEventListener("click", () => {
    if (!els.essayStudentSearch) return;

    els.essayStudentSearch.value = "";
    els.essayStudentSearch.focus();

    filterEssayStudents();
  });

  els.essayPendingOnly?.addEventListener("change", filterEssayStudents);


  // ==========================================================
  // 46. ESSAY MODAL EVENTS
  // ==========================================================

  els.essayScoresBtn?.addEventListener("click", openEssayScoreManager);
  els.openEssayScoresBtn?.addEventListener("click", openEssayScoreManager);

  els.essayScoreCloseBtn?.addEventListener("click", () => closeEssayScoreManager());
  els.cancelEssayScoresBtn?.addEventListener("click", () => closeEssayScoreManager());
  els.essayScoreBackdrop?.addEventListener("click", () => closeEssayScoreManager());

  els.clearEssayChangesBtn?.addEventListener("click", resetEssayChanges);
  els.saveEssayScoresBtn?.addEventListener("click", saveEssayScores);


  // ==========================================================
  // 47. PRINT SELECTED
  // ==========================================================

  function printSelected() {
    const records = getSelectedRecords();

    if (!records.length) {
      showToast("Select at least one result to print.", "warning");
      return;
    }

    if (records.length === 1) {
      openSummary(records[0]);

      setTimeout(() => window.print(), 250);

      return;
    }

    printResultList(records, "Selected Examination Results");
  }

  function printAllFiltered() {
    if (!state.filteredResults.length) {
      showToast("No results are available to print.", "warning");
      return;
    }

    printResultList(state.filteredResults, "EMIS Examination Results");
  }


  // ==========================================================
  // 48. RESULT LIST PRINT
  // ==========================================================

  function printResultList(records, title) {
    const popup = window.open("", "_blank");

    if (!popup) {
      showToast("Your browser blocked the print window. Allow pop-ups and try again.", "warning");
      return;
    }

    const includeTerm = records.some((row) => Boolean(getTerm(row)));

    const rows = records.map((row, index) => {
      const objective = objectiveDisplay(row);
      const essay = essayDisplay(row);
      const total = totalDisplay(row);

      return `
        <tr>
          <td>${index + 1}</td>
          <td>${escapeHtml(getStudentName(row))}</td>
          <td>${escapeHtml(getAdmission(row))}</td>
          <td>${escapeHtml(getYear(row))}</td>
          <td>${escapeHtml(getClass(row))}</td>
          ${includeTerm ? `<td>${escapeHtml(getTerm(row) ? termLabel(getTerm(row)) : "—")}</td>` : ""}
          <td>${escapeHtml(formatSubject(getSubject(row)))}</td>
          <td>${escapeHtml(objective.text)}</td>
          <td>${escapeHtml(essay.text)}</td>
          <td>${escapeHtml(total.text)}</td>
          <td>${escapeHtml(getStatus(row))}</td>
          <td>${escapeHtml(getTime(row) || "—")}</td>
          <td>${escapeHtml(getSubmittedAt(row) || "—")}</td>
        </tr>
      `;
    }).join("");

    popup.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <title>${escapeHtml(title)}</title>

          <style>
            * { box-sizing: border-box; }

            body { margin: 0; padding: 24px; font-family: Arial, sans-serif; color: #17202a; }

            .print-head { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 3px solid #0f766e; }

            h1 { margin: 0; font-size: 22px; }

            p { margin: 5px 0 0; color: #667085; font-size: 12px; }

            table { width: 100%; border-collapse: collapse; font-size: 9.5px; }

            th { padding: 8px; color: #fff; background: #334155; text-align: left; }

            td { padding: 7px; border: 1px solid #d9e0e7; }

            tr:nth-child(even) td { background: #f8fafc; }

            @page { size: landscape; margin: 10mm; }
          </style>
        </head>

        <body>
          <div class="print-head">
            <h1>${escapeHtml(title)}</h1>
            <p>${records.length} result(s) • Generated ${escapeHtml(new Date().toLocaleString())}</p>
          </div>

          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Student</th>
                <th>Admission</th>
                <th>Year</th>
                <th>Class</th>
                ${includeTerm ? "<th>Term</th>" : ""}
                <th>Subject</th>
                <th>Objective</th>
                <th>Essay</th>
                <th>Total</th>
                <th>Status</th>
                <th>Time</th>
                <th>Date</th>
              </tr>
            </thead>

            <tbody>${rows}</tbody>
          </table>
        </body>
      </html>
    `);

    popup.document.close();
    popup.focus();

    setTimeout(() => popup.print(), 300);
  }


  // ==========================================================
  // 49. EXPORT DATA
  // ==========================================================

  function exportRows() { return state.filteredResults; }

  function exportColumns() {
    return [
      ["Student Name", getStudentName],
      ["Admission No", getAdmission],
      ["Year", getYear],
      ["Class Level", getClassLevel],
      ["Class Arm", getClassArm],
      ["Term", (row) => getTerm(row) ? termLabel(getTerm(row)) : ""],
      ["Subject", (row) => formatSubject(getSubject(row))],

      ["Objective Score", (row) => getObjectiveScore(row)],
      ["Objective Max", (row) => getObjectiveMax(row)],
      ["Objective Correct", getCorrect],
      ["Objective Questions", getQuestionTotal],

      ["Essay Score", (row) => getEssayScore(row) ?? ""],
      ["Essay Max", (row) => getEssayAvailable(row) ? getEssayMax(row) : ""],

      ["Final Score", (row) => getFinalScore(row) ?? ""],
      ["Final Max", () => 100],

      ["Status", getStatus],
      ["Result State", getResultState],
      ["Time Taken", getTime],
      ["Submitted At", getSubmittedAt],
      ["Session", getSession]
    ];
  }


  // ==========================================================
  // 50. CSV EXPORT
  // ==========================================================

  function exportCsv() {
    const records = exportRows();

    if (!records.length) {
      showToast("No results are available to export.", "warning");
      return;
    }

    const columns = exportColumns();

    const escapeCsv = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;

    const csv = [
      columns.map(([heading]) => escapeCsv(heading)).join(","),
      ...records.map((row) => columns.map(([, getter]) => escapeCsv(getter(row))).join(","))
    ].join("\r\n");

    downloadBlob("\ufeff" + csv, "text/csv;charset=utf-8;", exportFilename("csv"));

    showToast("CSV exported successfully.", "success");
  }


  // ==========================================================
  // 51. PROFESSIONAL EXCEL EXPORT
  // ==========================================================

  async function exportExcelCompatible() {
    const records = exportRows();

    if (!records.length) {
      showToast("No results are available to export.", "warning");
      return;
    }

    const button = els.exportAllExcelBtn;
    const originalHtml = button?.innerHTML || "";

    try {
      if (button) {
        button.disabled = true;
        button.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>Preparing...</span>`;
      }

      const normalizedRecords = records.map((row) => ({
        ...row,

        "Student Name": getStudentName(row),
        "Admission No": getAdmission(row),
        Year: getYear(row),

        "Class Level": getClassLevel(row),
        "Class Arm": getClassArm(row),

        Term: getTerm(row) ? termLabel(getTerm(row)) : "",
        Subject: formatSubject(getSubject(row)),

        "Objective Score": getObjectiveScore(row),
        "Objective Max": getObjectiveMax(row),

        "Essay Score": getEssayScore(row),
        "Essay Max": getEssayAvailable(row) ? getEssayMax(row) : null,

        "Final Score": getFinalScore(row),
        "Final Max": 100,

        "Score (%)": getFinalScore(row) ?? getObjectivePercentage(row),

        Correct: getCorrect(row),
        Total: getQuestionTotal(row),

        Status: getStatus(row),
        "Result State": getResultState(row),

        "Time Taken": getTime(row),
        "Submitted At": getSubmittedAt(row),
        Session: getSession(row)
      }));

      const exportData = {
        results: normalizedRecords,

        filters: {
          year: selectedYear() === "all" ? "All Years" : selectedYear(),
          class: selectedClass() === "all" ? "All Classes" : selectedClass(),
          term: selectedTerm() === "all" ? "All Terms" : termLabel(selectedTerm()),
          subject: selectedSubject() === "all" ? "All Subjects" : formatSubject(selectedSubject()),

          class_arm: (els.classArmSelector?.value || "all") === "all"
            ? "All Arms"
            : formatClassLabel(els.classArmSelector?.value || ""),

          session: (els.sessionSelector?.value || "all") === "all"
            ? "All Sessions"
            : els.sessionSelector?.value || "All Sessions",

          status: els.statusFilter?.value || (state.statusView !== "all" ? state.statusView : "All Status")
        }
      };

      const response = await fetch("/api/results/export/excel", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",

        headers: {
          "Content-Type": "application/json",
          Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        },

        body: JSON.stringify(exportData)
      });

      if (!response.ok) {
        let errorMessage = `Export failed (${response.status})`;

        try {
          const errorData = await response.json();
          errorMessage = errorData.error || errorData.message || errorMessage;
        } catch {}

        throw new Error(errorMessage);
      }

      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";

      const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);

      const filename = filenameMatch?.[1] || exportFilename("xlsx");

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = filename;

      document.body.appendChild(link);
      link.click();
      link.remove();

      setTimeout(() => URL.revokeObjectURL(url), 1000);

      showToast(`Professional Excel report exported — ${records.length} result(s).`, "success");

    } catch (error) {
      console.error("EXCEL EXPORT ERROR:", error);

      showToast(error.message || "Could not generate the Excel report.", "error");

    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = originalHtml;
      }
    }
  }


  // ==========================================================
  // 52. RESET FILTERS
  // ==========================================================

  async function clearFilters() {
    if (els.yearSelector) els.yearSelector.value = "all";
    if (els.classSelector) els.classSelector.value = "all";
    if (els.classArmSelector) els.classArmSelector.value = "all";

    if (els.termSelector) {
      els.termSelector.disabled = false;
      els.termSelector.value = "all";
    }

    if (els.subjectSelector) els.subjectSelector.value = "all";
    if (els.statusFilter) els.statusFilter.value = "";
    if (els.sessionSelector) els.sessionSelector.value = "all";
    if (els.globalSearch) els.globalSearch.value = "";

    state.statusView = "all";
    state.currentPage = 1;
    state.sortKey = "date";
    state.sortDirection = "desc";
    state.selectedKeys.clear();

    populateTermOptions(DEFAULT_TERMS, false);

    updateTermUi();
    syncClassPills();
    syncStatusTabs();

    await loadAllResults();
  }


  // ==========================================================
  // 53. CLASS PILLS
  // ==========================================================

  function syncClassPills() {
    const cls = selectedClass();

    $$(".class-pill").forEach((pill) => {
      pill.classList.toggle("active", (pill.dataset.class || "all") === cls);
    });
  }


  // ==========================================================
  // 54. STATUS TABS
  // ==========================================================

  function syncStatusTabs() {
    $$(".view-tab[data-status-view]").forEach((tab) => {
      tab.classList.toggle("active", (tab.dataset.statusView || "all") === state.statusView);
    });
  }


  // ==========================================================
  // 55. COLUMN MENU
  // ==========================================================

  function closeColumnMenu() {
    els.columnMenu?.classList.add("hidden");
    els.columnToggleBtn?.setAttribute("aria-expanded", "false");
  }

  function toggleColumnMenu() {
    if (!els.columnMenu) return;

    const opening = els.columnMenu.classList.contains("hidden");

    els.columnMenu.classList.toggle("hidden", !opening);
    els.columnToggleBtn?.setAttribute("aria-expanded", String(opening));

    if (opening) syncColumnCheckboxes();
  }


  // ==========================================================
  // 56. FILTER CHANGE HANDLERS
  // ==========================================================

  async function handleYearChange() {
    state.currentPage = 1;
    state.selectedKeys.clear();

    if (els.classArmSelector) els.classArmSelector.value = "all";
    if (els.subjectSelector) els.subjectSelector.value = "all";

    await loadAvailableTerms();
    await loadAllResults();
  }

  async function handleClassChange() {
    state.currentPage = 1;
    state.selectedKeys.clear();

    syncClassPills();
    updateTermUi();

    if (els.classArmSelector) els.classArmSelector.value = "all";
    if (els.subjectSelector) els.subjectSelector.value = "all";

    await loadAvailableTerms();
    await loadAllResults();
  }

  async function handleTermChange() {
    state.currentPage = 1;
    state.selectedKeys.clear();

    if (els.subjectSelector) els.subjectSelector.value = "all";

    await loadAllResults();
  }

  async function handleSubjectChange() {
    state.currentPage = 1;
    state.selectedKeys.clear();

    await loadAllResults();
  }


  // ==========================================================
  // 57. MAIN FILTER EVENTS
  // ==========================================================

  els.reloadTableBtn?.addEventListener("click", () => loadAllResults());
  els.clearFiltersBtn?.addEventListener("click", clearFilters);

  els.yearSelector?.addEventListener("change", handleYearChange);
  els.classSelector?.addEventListener("change", handleClassChange);
  els.termSelector?.addEventListener("change", handleTermChange);
  els.subjectSelector?.addEventListener("change", handleSubjectChange);

  els.classArmSelector?.addEventListener("change", () => applyFilters());
  els.sessionSelector?.addEventListener("change", () => applyFilters());

  els.statusFilter?.addEventListener("change", () => {
    state.statusView = "all";

    syncStatusTabs();
    applyFilters();
  });


  // ==========================================================
  // 58. SEARCH
  // ==========================================================

  const applySearch = debounce(() => applyFilters(), 180);

  els.globalSearch?.addEventListener("input", applySearch);

  els.clearSearchBtn?.addEventListener("click", () => {
    if (!els.globalSearch) return;

    els.globalSearch.value = "";
    els.globalSearch.focus();

    applyFilters();
  });


  // ==========================================================
  // 59. CLASS QUICK BUTTONS
  // ==========================================================

  $$(".class-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      if (!els.classSelector) return;

      els.classSelector.value = pill.dataset.class || "all";

      handleClassChange();
    });
  });


  // ==========================================================
  // 60. QUICK PASS / FAIL TABS
  // ==========================================================

  $$(".view-tab[data-status-view]").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.statusView = tab.dataset.statusView || "all";

      if (els.statusFilter) els.statusFilter.value = "";

      syncStatusTabs();
      applyFilters();
    });
  });


  // ==========================================================
  // 61. SORT EVENTS
  // ==========================================================

  $$(".results-table th.sortable").forEach((th) => {
    th.querySelector("button")?.addEventListener("click", () => setSort(th.dataset.sort));
  });


  // ==========================================================
  // 62. ROWS PER PAGE
  // ==========================================================

  els.rowsPerPage?.addEventListener("change", () => {
    const value = Number(els.rowsPerPage.value);

    state.rowsPerPage = [10, 20, 50, 100].includes(value) ? value : 20;
    state.currentPage = 1;

    renderTable();
  });


  // ==========================================================
  // 63. SELECT ALL CURRENT PAGE
  // ==========================================================

  els.selectAllRows?.addEventListener("change", () => {
    toggleSelectCurrentPage(els.selectAllRows.checked);
  });


  // ==========================================================
  // 64. COLUMN MANAGER EVENTS
  // ==========================================================

  els.columnToggleBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleColumnMenu();
  });

  els.columnMenu?.addEventListener("click", (event) => event.stopPropagation());

  $$("#columnMenu input[data-column]").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      setColumnVisible(checkbox.dataset.column, checkbox.checked);
    });
  });

  els.resetColumnsBtn?.addEventListener("click", resetColumns);

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".column-manager")) closeColumnMenu();
  });


  // ==========================================================
  // 65. COMPACT TABLE
  // ==========================================================

  els.toggleCompactBtn?.addEventListener("click", () => {
    state.compact = !state.compact;

    els.resultsTable?.classList.toggle("compact", state.compact);

    if (els.toggleCompactBtn) {
      els.toggleCompactBtn.innerHTML = state.compact
        ? '<i class="fa-solid fa-expand"></i><span>Comfortable</span>'
        : '<i class="fa-solid fa-compress"></i><span>Compact</span>';
    }
  });


  // ==========================================================
  // 66. DELETE EVENTS
  // ==========================================================

  els.deleteSelectedBtn?.addEventListener("click", () => openDeleteModal());
  els.cancelDeleteBtn?.addEventListener("click", closeDeleteModal);
  els.confirmDeleteBtn?.addEventListener("click", confirmDelete);

  els.deleteModal?.addEventListener("click", (event) => {
    if (event.target === els.deleteModal) closeDeleteModal();
  });


  // ==========================================================
  // 67. PRINT / EXPORT EVENTS
  // ==========================================================

  els.printSelectedBtn?.addEventListener("click", printSelected);
  els.printAllPdfBtn?.addEventListener("click", printAllFiltered);
  els.exportCsvBtn?.addEventListener("click", exportCsv);
  els.exportAllExcelBtn?.addEventListener("click", exportExcelCompatible);


  // ==========================================================
  // 68. SUMMARY EVENTS
  // ==========================================================

  els.summaryCloseBtn?.addEventListener("click", closeSummary);
  els.summaryCloseFooterBtn?.addEventListener("click", closeSummary);
  els.summaryOverlay?.addEventListener("click", closeSummary);

  els.summaryPrintBtn?.addEventListener("click", printCurrentSummary);
  els.summaryPrintFooterBtn?.addEventListener("click", printCurrentSummary);


  // ==========================================================
  // 69. KEYBOARD SHORTCUTS
  // ==========================================================

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      if (!els.essayScoreModal?.classList.contains("hidden")) return;

      event.preventDefault();

      els.globalSearch?.focus();
      els.globalSearch?.select();

      return;
    }

    if (event.key !== "Escape") return;

    if (els.essayScoreModal && !els.essayScoreModal.classList.contains("hidden")) {
      closeEssayScoreManager();
      return;
    }

    if (els.adminPrintSummary?.classList.contains("show")) {
      closeSummary();
      return;
    }

    if (els.deleteModal && !els.deleteModal.classList.contains("hidden")) {
      closeDeleteModal();
      return;
    }

    closeColumnMenu();
  });


  // ==========================================================
  // 70. EXTERNAL REFRESH HOOKS
  // ==========================================================

  window.loadAllResults = loadAllResults;
  window.refreshAdminResults = loadAllResults;
  window.openEssayScoreManager = openEssayScoreManager;

  window.addEventListener("emis:result-submitted", () => loadAllResults({ silent: true }));
  window.addEventListener("emis:results-changed", () => loadAllResults({ silent: true }));
  window.addEventListener("emis:essay-scores-changed", () => loadAllResults({ silent: true }));


  // ==========================================================
  // 71. INITIALIZE
  // ==========================================================

  async function init() {
    populateTermOptions(DEFAULT_TERMS, false);

    updateTermUi();
    syncClassPills();
    syncStatusTabs();
    syncColumnCheckboxes();
    updateSelectionUi();
    updateSortIcons();
    updateEssayUnsavedCount();

    await loadAvailableTerms();
    await loadAllResults();
  }

  init();
});
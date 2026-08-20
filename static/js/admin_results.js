// static/js/admin_results.js
// ============================================================
// EMIS ADMIN RESULTS — TERM-AWARE RESULTS MANAGEMENT
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
    paginationInfo: $("paginationInfo"), pagination: $("pagination"), rowsPerPage: $("rowsPerPage"), columnToggleBtn: $("columnToggleBtn"),
    columnMenu: $("columnMenu"), resetColumnsBtn: $("resetColumnsBtn"), toggleCompactBtn: $("toggleCompactBtn"),
    activeFilterChips: $("activeFilterChips"), filteredResultCount: $("filteredResultCount"),

    deleteSelectedBtn: $("deleteSelectedBtn"), printSelectedBtn: $("printSelectedBtn"), exportAllExcelBtn: $("exportAllExcelBtn"),
    exportCsvBtn: $("exportCsvBtn"), printAllPdfBtn: $("printAllPdfBtn"),

    deleteModal: $("deleteModal"), cancelDeleteBtn: $("cancelDeleteBtn"), confirmDeleteBtn: $("confirmDeleteBtn"),

    summaryOverlay: $("summaryOverlay"), adminPrintSummary: $("adminPrintSummary"), summaryCloseBtn: $("summaryCloseBtn"),
    summaryCloseFooterBtn: $("summaryCloseFooterBtn"), summaryPrintBtn: $("summaryPrintBtn"), summaryPrintFooterBtn: $("summaryPrintFooterBtn"),
    summaryTermRow: $("summaryTermRow"),

    statTotalResults: $("statTotalResults"), statPassRate: $("statPassRate"), statAvgScore: $("statAvgScore"), statSubjects: $("statSubjects"),
    avgTimeTaken: $("avgTimeTaken"), topPerformerName: $("topPerformerName"), topPerformerMeta: $("topPerformerMeta"),
    highestScore: $("highestScore"), lowestScore: $("lowestScore")
  };


  // ==========================================================
  // 2. CONSTANTS / STATE
  // ==========================================================

  const DEFAULT_TERMS = ["FIRST", "SECOND", "THIRD"];
  const TERM_LABELS = { FIRST: "1st Term", SECOND: "2nd Term", THIRD: "3rd Term" };
  const COLUMN_ORDER = ["select", "student", "admission", "year", "class", "term", "subject", "score", "status", "time", "date", "actions"];

  const state = {
    allResults: [], filteredResults: [], selectedKeys: new Set(), currentPage: 1,
    rowsPerPage: Number(els.rowsPerPage?.value || 20), sortKey: "date", sortDirection: "desc",
    statusView: "all", compact: false, currentSummaryRow: null, pendingDeleteRows: null,
    visibleColumns: new Set(COLUMN_ORDER), loadToken: 0, loading: false
  };


  // ==========================================================
  // 3. GENERAL HELPERS
  // ==========================================================

  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  function normalizeText(value) { return String(value ?? "").trim().toLowerCase(); }
  function normalizeUpper(value) { return String(value ?? "").trim().toUpperCase(); }

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
  function formatSubject(value) { return String(value || "").replaceAll("_", " ").replace(/\s+/g, " ").trim().toUpperCase(); }
  function formatClassLabel(value) { return String(value || "").replaceAll("_", " ").trim().toUpperCase(); }
  function isJssClass(value) { return normalizeUpper(value).startsWith("JSS"); }
  function isSsClass(value) { return normalizeUpper(value).startsWith("SS"); }

  function parseNumber(value, fallback = 0) {
    const number = Number.parseFloat(String(value ?? "").replace("%", "").trim());
    return Number.isFinite(number) ? number : fallback;
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


  // ==========================================================
  // 4. TOAST
  // ==========================================================

  function showToast(message, type = "info") {
    let stack = document.querySelector(".ar-toast-stack");

    if (!stack) {
      stack = document.createElement("div");
      stack.className = "ar-toast-stack";
      Object.assign(stack.style, {
        position: "fixed", right: "20px", bottom: "20px", zIndex: "10050", display: "grid",
        gap: "8px", maxWidth: "370px"
      });
      document.body.appendChild(stack);
    }

    const palette = {
      success: ["#166534", "#ecfdf3", "#bbf7d0"], error: ["#991b1b", "#fff1f2", "#fecdd3"],
      warning: ["#92400e", "#fffbeb", "#fde68a"], info: ["#115e59", "#f0fdfa", "#99f6e4"]
    };

    const [color, background, border] = palette[type] || palette.info;
    const toast = document.createElement("div");
    toast.textContent = message;

    Object.assign(toast.style, {
      padding: "11px 13px", border: `1px solid ${border}`, borderRadius: "10px", color, background,
      boxShadow: "0 10px 28px rgba(15,23,42,.14)", fontSize: "14px", fontWeight: "700",
      lineHeight: "1.4", opacity: "0", transform: "translateY(8px)",
      transition: "opacity .18s ease, transform .18s ease"
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
    }, 3200);
  }


  // ==========================================================
  // 5. FETCH
  // ==========================================================

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
      ...options
    });

    let data = {};
    try { data = await response.json(); } catch { data = {}; }

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

    setTimeout(() => URL.revokeObjectURL(url), 500);
  }

  function exportFilename(extension) {
    const year = els.yearSelector?.value || "all-years";
    const cls = els.classSelector?.value || "all-classes";
    const term = els.termSelector?.value || "all-terms";
    const date = new Date().toISOString().slice(0, 10);

    return `emis_results_${year}_${cls}_${term}_${date}.${extension}`.replaceAll(" ", "_").toLowerCase();
  }


  // ==========================================================
  // 7. RESULT FIELD HELPERS
  // ==========================================================

  function getScore(row) { return parseNumber(row?.["Score (%)"] ?? row?.["Score Number"] ?? row?.score ?? 0); }

  function getStatus(row) {
    const explicit = normalizeUpper(row?.Status ?? row?.status);
    if (explicit === "PASS" || explicit === "FAIL") return explicit;
    return getScore(row) >= 50 ? "PASS" : "FAIL";
  }

  function getStudentName(row) { return String(row?.["Student Name"] ?? row?.full_name ?? row?.student_name ?? "Unknown Student").trim(); }
  function getAdmission(row) { return String(row?.["Admission No"] ?? row?.admission_number ?? row?.student_id ?? "").trim(); }
  function getYear(row) { return String(row?.Year ?? row?.year ?? "").trim(); }

  function getClassLevel(row) {
    return String(row?.["Class Level"] ?? row?.["Class Category"] ?? row?.class_category ?? row?.class_level ?? row?.Class ?? "").trim().toUpperCase();
  }

  function getClassArm(row) {
    return String(row?.["Class Arm"] ?? row?.class_arm ?? row?.Class ?? getClassLevel(row)).trim().toUpperCase();
  }

  function getClass(row) { return getClassArm(row) || getClassLevel(row); }
  function getClassCategory(row) { return getClassLevel(row); }
  function getTerm(row) { return normalizeTerm(row?.Term ?? row?.term ?? row?.["Term Label"]); }
  function getTermLabel(row) { return row?.["Term Label"] || termLabel(getTerm(row)); }
  function getSubject(row) { return String(row?.Subject ?? row?.subject ?? row?.["Subject Folder"] ?? "").trim(); }
  function getSubjectFolder(row) { return String(row?.["Subject Folder"] ?? row?.subject_folder ?? row?.Subject ?? row?.subject ?? "").trim(); }
  function getCorrect(row) { return row?.Correct ?? row?.correct ?? 0; }
  function getTotal(row) { return row?.Total ?? row?.total ?? 0; }
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
  // 8. TIME HELPERS
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
  // 9. TABLE STATES
  // ==========================================================

  function setLoading(message = "Loading examination results") {
    if (!els.resultsBody) return;

    els.resultsBody.innerHTML = `
      <tr>
        <td colspan="12" class="table-placeholder">
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
        <td colspan="12" class="table-placeholder">
          <span class="table-placeholder-icon"><i class="fa-solid fa-folder-open"></i></span>
          <strong>${escapeHtml(message)}</strong>
          <span>${escapeHtml(subtext)}</span>
        </td>
      </tr>
    `;
  }


  // ==========================================================
  // 10. CURRENT FILTER VALUES
  // ==========================================================

  function selectedYear() { return els.yearSelector?.value || "all"; }
  function selectedClass() { return els.classSelector?.value || "all"; }
  function selectedTerm() { return els.termSelector?.value || "all"; }
  function selectedSubject() { return els.subjectSelector?.value || "all"; }


  // ==========================================================
  // 11. TERM UI
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
  // 12. TERM OPTIONS
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

    if (!isJssClass(cls)) {
      populateTermOptions(DEFAULT_TERMS);
      return;
    }

    if (year === "all") {
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
  // 13. SUBJECT OPTIONS
  // ==========================================================

  function populateSubjectOptions(subjects, preserve = true) {
    if (!els.subjectSelector) return;

    const previous = preserve ? els.subjectSelector.value : "all";

    const uniqueSubjects = [...new Set((subjects || []).map(String).map((value) => value.trim()).filter(Boolean))]
      .sort((a, b) => formatSubject(a).localeCompare(formatSubject(b)));

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
  // 14. CLASS ARMS
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
  // 15. SESSION OPTIONS
  // ==========================================================

  function rebuildSessions() {
    if (!els.sessionSelector) return;

    const current = els.sessionSelector.value || "all";
    const sessions = [...new Set(state.allResults.map(getSession).filter(Boolean))]
      .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));

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
  // 16. SERVER RESULTS QUERY
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
  // 17. LOAD RESULTS
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
  // 18. CLIENT FILTERS
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
        getTerm(row), getTermLabel(row), getSubject(row), getSubjectFolder(row), getScore(row),
        getStatus(row), getTime(row), getSubmittedAt(row), getSession(row)
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
  // 19. SORTING
  // ==========================================================

  function sortValue(row, key) {
    switch (key) {
      case "student": return getStudentName(row);
      case "admission": return getAdmission(row);
      case "year": return parseNumber(getYear(row));
      case "class": return getClass(row);
      case "term": return DEFAULT_TERMS.indexOf(getTerm(row));
      case "subject": return formatSubject(getSubject(row));
      case "score": return getScore(row);
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
      state.sortDirection = key === "date" || key === "score" ? "desc" : "asc";
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

      icon.className = active ? `fa-solid ${state.sortDirection === "asc" ? "fa-sort-up" : "fa-sort-down"}` : "fa-solid fa-sort";
      th.setAttribute("aria-sort", active ? (state.sortDirection === "asc" ? "ascending" : "descending") : "none");
    });
  }


  // ==========================================================
  // 20. PAGINATION
  // ==========================================================

  function totalPages() { return Math.max(1, Math.ceil(state.filteredResults.length / state.rowsPerPage)); }

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

    els.pagination.appendChild(makeButton(
      '<i class="fa-solid fa-chevron-left"></i>',
      Math.max(1, state.currentPage - 1),
      { disabled: state.currentPage === 1, ariaLabel: "Previous page" }
    ));

    const candidates = new Set([1, pages, state.currentPage - 2, state.currentPage - 1, state.currentPage, state.currentPage + 1, state.currentPage + 2]);

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

      els.pagination.appendChild(makeButton(String(page), page, { active: page === state.currentPage, ariaLabel: `Go to page ${page}` }));
      previous = page;
    });

    els.pagination.appendChild(makeButton(
      '<i class="fa-solid fa-chevron-right"></i>',
      Math.min(pages, state.currentPage + 1),
      { disabled: state.currentPage === pages, ariaLabel: "Next page" }
    ));
  }


  // ==========================================================
  // 21. TABLE VIEW DESCRIPTION
  // ==========================================================

  function describeCurrentView() {
    const parts = [];

    if (selectedYear() !== "all") parts.push(selectedYear());
    if (selectedClass() !== "all") parts.push(selectedClass());

    if ((selectedClass() === "all" || isJssClass(selectedClass())) && selectedTerm() !== "all") parts.push(termLabel(selectedTerm()));
    if (selectedSubject() !== "all") parts.push(formatSubject(selectedSubject()));

    return parts.length ? `Showing ${parts.join(" • ")} examination results.` : "Showing all available examination results.";
  }


  // ==========================================================
  // 22. TABLE RENDERING
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
      const score = getScore(row);
      const correct = getCorrect(row);
      const total = getTotal(row);
      const status = getStatus(row);
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

          <td class="score-cell" data-column-name="score">
            ${escapeHtml(Number.isInteger(score) ? score : score.toFixed(1))}%
            <span class="student-meta">${escapeHtml(correct)} / ${escapeHtml(total)}</span>
          </td>

          <td data-column-name="status">
            <span class="${status === "PASS" ? "status-pass" : "status-fail"}">
              <i class="fa-solid ${status === "PASS" ? "fa-check" : "fa-xmark"}"></i>
              ${escapeHtml(status)}
            </span>
          </td>

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
  // 23. TABLE ROW EVENTS
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
  // 24. SELECTION
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
  // 25. ACTIVE FILTER CHIPS
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

    els.activeFilterChips.innerHTML = chips.map(([label, value]) => `<span class="filter-chip">${escapeHtml(label)}: ${escapeHtml(value)}</span>`).join("");
  }


  // ==========================================================
  // 26. STATISTICS
  // ==========================================================

  function updateStats(rows) {
    const total = rows.length;
    const scores = rows.map(getScore);
    const passCount = rows.filter((row) => getStatus(row) === "PASS").length;
    const passRate = total ? Math.round((passCount / total) * 100) : 0;
    const averageScore = total ? Math.round(scores.reduce((sum, score) => sum + score, 0) / total) : 0;

    const subjects = new Set(rows.map((row) => normalizeText(getSubjectFolder(row) || getSubject(row))).filter(Boolean));

    safeSetText(els.statTotalResults, total);
    safeSetText(els.statPassRate, `${passRate}%`);
    safeSetText(els.statAvgScore, `${averageScore}%`);
    safeSetText(els.statSubjects, subjects.size);

    const validTimes = rows.map(getTimeSeconds).filter(Number.isFinite);
    const averageTime = validTimes.length ? validTimes.reduce((sum, value) => sum + value, 0) / validTimes.length : NaN;

    safeSetText(els.avgTimeTaken, formatSeconds(averageTime));

    if (!total) {
      safeSetText(els.topPerformerName, "—");
      safeSetText(els.topPerformerMeta, "No result data");
      safeSetText(els.highestScore, "0%");
      safeSetText(els.lowestScore, "0%");
      return;
    }

    const ranked = [...rows].sort((a, b) => {
      const scoreDiff = getScore(b) - getScore(a);
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
      `${getScore(top)}%`
    ].filter(Boolean).join(" • ");

    safeSetText(els.topPerformerName, getStudentName(top));
    safeSetText(els.topPerformerMeta, topMeta);
    safeSetText(els.highestScore, `${Math.max(...scores)}%`);
    safeSetText(els.lowestScore, `${Math.min(...scores)}%`);
  }


  // ==========================================================
  // 27. COLUMN VISIBILITY
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
  // 28. DELETE MODAL
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

    if (!els.adminPrintSummary?.classList.contains("show")) document.body.style.overflow = "";
  }


  // ==========================================================
  // 29. TERM-AWARE DELETE PAYLOAD
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
        data.message ? `${data.message}${Number.isFinite(deleted) ? ` (${deleted})` : ""}` : `${deleted} result(s) deleted.`,
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
  // 30. RESULT DETAILS MODAL
  // ==========================================================

  function setSummaryStatus(status) {
    const badge = $("ap_status");
    if (!badge) return;

    badge.textContent = status || "—";
    badge.style.background = status === "PASS" ? "#15803d" : status === "FAIL" ? "#c62828" : "#0f766e";
  }

  function openSummary(row) {
    if (!row) return;

    state.currentSummaryRow = row;

    const total = Number(getTotal(row)) || 0;
    const correct = Number(getCorrect(row)) || 0;
    const accuracy = total ? Math.round((correct / total) * 100) : Math.round(getScore(row));

    safeSetText("ap_studentName", getStudentName(row) || "—");
    safeSetText("ap_studentID", getAdmission(row) || "—");
    safeSetText("ap_studentNameMirror", getStudentName(row) || "—");
    safeSetText("ap_studentIDMirror", getAdmission(row) || "—");

    safeSetText("ap_year", getYear(row) || "—");
    safeSetText("ap_studentClass", getClass(row) || "—");
    safeSetText("ap_studentCategory", getClassCategory(row) || "—");
    safeSetText("ap_term", getTerm(row) ? termLabel(getTerm(row)) : "Not Applicable");

    safeSetText("ap_subject", formatSubject(getSubject(row)) || "—");
    safeSetText("ap_percent", `${getScore(row)}%`);
    safeSetText("ap_rawScore", `${correct} / ${total}`);
    safeSetText("ap_correct", correct);
    safeSetText("ap_total", total);
    safeSetText("ap_accuracy", `${accuracy}%`);
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

    if (els.deleteModal?.classList.contains("hidden")) document.body.style.overflow = "";
  }

  function printCurrentSummary() {
    if (!state.currentSummaryRow) {
      showToast("Open a result before printing.", "warning");
      return;
    }

    window.print();
  }


  // ==========================================================
  // 31. PRINT SELECTED
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
  // 32. RESULT LIST PRINT
  // ==========================================================

  function printResultList(records, title) {
    const popup = window.open("", "_blank");

    if (!popup) {
      showToast("Your browser blocked the print window. Allow pop-ups and try again.", "warning");
      return;
    }

    const includeTerm = records.some((row) => Boolean(getTerm(row)));

    const rows = records.map((row, index) => `
      <tr>
        <td>${index + 1}</td>
        <td>${escapeHtml(getStudentName(row))}</td>
        <td>${escapeHtml(getAdmission(row))}</td>
        <td>${escapeHtml(getYear(row))}</td>
        <td>${escapeHtml(getClass(row))}</td>
        ${includeTerm ? `<td>${escapeHtml(getTerm(row) ? termLabel(getTerm(row)) : "—")}</td>` : ""}
        <td>${escapeHtml(formatSubject(getSubject(row)))}</td>
        <td>${escapeHtml(getCorrect(row))}/${escapeHtml(getTotal(row))}</td>
        <td>${escapeHtml(getScore(row))}%</td>
        <td>${escapeHtml(getStatus(row))}</td>
        <td>${escapeHtml(getTime(row) || "—")}</td>
        <td>${escapeHtml(getSubmittedAt(row) || "—")}</td>
      </tr>
    `).join("");

    popup.document.write(`
      <!DOCTYPE html>

      <html>
        <head>
          <meta charset="UTF-8">
          <title>${escapeHtml(title)}</title>

          <style>
            * { box-sizing: border-box; }

            body {
              margin: 0;
              padding: 24px;
              font-family: Arial, sans-serif;
              color: #17202a;
            }

            .print-head {
              margin-bottom: 16px;
              padding-bottom: 12px;
              border-bottom: 3px solid #0f766e;
            }

            h1 {
              margin: 0;
              font-size: 22px;
            }

            p {
              margin: 5px 0 0;
              color: #667085;
              font-size: 12px;
            }

            table {
              width: 100%;
              border-collapse: collapse;
              font-size: 10px;
            }

            th {
              padding: 8px;
              color: #fff;
              background: #334155;
              text-align: left;
            }

            td {
              padding: 7px;
              border: 1px solid #d9e0e7;
            }

            tr:nth-child(even) td {
              background: #f8fafc;
            }

            @page {
              size: landscape;
              margin: 12mm;
            }
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
                <th>Raw</th>
                <th>Score</th>
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
  // 33. EXPORT DATA
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
      ["Score (%)", getScore],
      ["Correct", getCorrect],
      ["Total", getTotal],
      ["Status", getStatus],
      ["Time Taken", getTime],
      ["Submitted At", getSubmittedAt],
      ["Session", getSession]
    ];
  }


  // ==========================================================
  // 34. CSV EXPORT
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
  // 35. PROFESSIONAL EXCEL EXPORT
  // Real .xlsx workbook generated by backend / OpenPyXL
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

      const exportData = {
        results: records,

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

          status: els.statusFilter?.value
            || (state.statusView !== "all" ? state.statusView : "All Status")
        }
      };

      console.log("[admin_results] Generating professional Excel workbook:", {
        results: records.length,
        filters: exportData.filters
      });

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
        const errorData = await response.json().catch(() => ({}));

        throw new Error(
          errorData.error ||
          errorData.message ||
          `Excel export failed (${response.status})`
        );
      }

      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";

      let filename = exportFilename("xlsx");

      const utfFilename = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const normalFilename = disposition.match(/filename="?([^";]+)"?/i);

      if (utfFilename?.[1]) filename = decodeURIComponent(utfFilename[1]);
      else if (normalFilename?.[1]) filename = normalFilename[1];

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = filename;

      document.body.appendChild(link);
      link.click();
      link.remove();

      setTimeout(() => URL.revokeObjectURL(url), 1000);

      showToast(`Professional Excel report exported — ${records.length} result(s).`, "success");

      console.log("[admin_results] Excel workbook downloaded:", filename);

    } catch (error) {
      console.error("EXCEL EXPORT ERROR:", error);

      showToast(
        error.message ||
        "Could not generate the Excel report.",
        "error"
      );

    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = originalHtml;
      }
    }
  }

  // ==========================================================
  // 36. RESET FILTERS
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
  // 37. CLASS PILLS
  // ==========================================================

  function syncClassPills() {
    const cls = selectedClass();

    $$(".class-pill").forEach((pill) => {
      pill.classList.toggle("active", (pill.dataset.class || "all") === cls);
    });
  }


  // ==========================================================
  // 38. STATUS TABS
  // ==========================================================

  function syncStatusTabs() {
    $$(".view-tab[data-status-view]").forEach((tab) => {
      tab.classList.toggle("active", (tab.dataset.statusView || "all") === state.statusView);
    });
  }


  // ==========================================================
  // 39. COLUMN MENU
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
  // 40. YEAR CHANGE
  // ==========================================================

  async function handleYearChange() {
    state.currentPage = 1;
    state.selectedKeys.clear();

    if (els.classArmSelector) els.classArmSelector.value = "all";
    if (els.subjectSelector) els.subjectSelector.value = "all";

    await loadAvailableTerms();
    await loadAllResults();
  }


  // ==========================================================
  // 41. CLASS CHANGE
  // ==========================================================

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


  // ==========================================================
  // 42. TERM CHANGE
  // ==========================================================

  async function handleTermChange() {
    state.currentPage = 1;
    state.selectedKeys.clear();

    if (els.subjectSelector) els.subjectSelector.value = "all";

    await loadAllResults();
  }


  // ==========================================================
  // 43. SUBJECT CHANGE
  // ==========================================================

  async function handleSubjectChange() {
    state.currentPage = 1;
    state.selectedKeys.clear();

    await loadAllResults();
  }


  // ==========================================================
  // 44. MAIN FILTER EVENTS
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
  // 45. SEARCH
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
  // 46. CLASS QUICK BUTTONS
  // ==========================================================

  $$(".class-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      if (!els.classSelector) return;

      els.classSelector.value = pill.dataset.class || "all";

      handleClassChange();
    });
  });


  // ==========================================================
  // 47. QUICK PASS / FAIL TABS
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
  // 48. SORT EVENTS
  // ==========================================================

  $$(".results-table th.sortable").forEach((th) => {
    th.querySelector("button")?.addEventListener("click", () => setSort(th.dataset.sort));
  });


  // ==========================================================
  // 49. ROWS PER PAGE
  // ==========================================================

  els.rowsPerPage?.addEventListener("change", () => {
    const value = Number(els.rowsPerPage.value);

    state.rowsPerPage = [10, 20, 50, 100].includes(value) ? value : 20;
    state.currentPage = 1;

    renderTable();
  });


  // ==========================================================
  // 50. SELECT ALL CURRENT PAGE
  // ==========================================================

  els.selectAllRows?.addEventListener("change", () => {
    toggleSelectCurrentPage(els.selectAllRows.checked);
  });


  // ==========================================================
  // 51. COLUMN MANAGER EVENTS
  // ==========================================================

  els.columnToggleBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleColumnMenu();
  });

  els.columnMenu?.addEventListener("click", (event) => event.stopPropagation());

  $$("#columnMenu input[data-column]").forEach((checkbox) => {
    checkbox.addEventListener("change", () => setColumnVisible(checkbox.dataset.column, checkbox.checked));
  });

  els.resetColumnsBtn?.addEventListener("click", resetColumns);

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".column-manager")) closeColumnMenu();
  });


  // ==========================================================
  // 52. COMPACT TABLE
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
  // 53. DELETE EVENTS
  // ==========================================================

  els.deleteSelectedBtn?.addEventListener("click", () => openDeleteModal());
  els.cancelDeleteBtn?.addEventListener("click", closeDeleteModal);
  els.confirmDeleteBtn?.addEventListener("click", confirmDelete);

  els.deleteModal?.addEventListener("click", (event) => {
    if (event.target === els.deleteModal) closeDeleteModal();
  });


  // ==========================================================
  // 54. PRINT / EXPORT EVENTS
  // ==========================================================

  els.printSelectedBtn?.addEventListener("click", printSelected);
  els.printAllPdfBtn?.addEventListener("click", printAllFiltered);
  els.exportCsvBtn?.addEventListener("click", exportCsv);
  els.exportAllExcelBtn?.addEventListener("click", exportExcelCompatible);


  // ==========================================================
  // 55. SUMMARY EVENTS
  // ==========================================================

  els.summaryCloseBtn?.addEventListener("click", closeSummary);
  els.summaryCloseFooterBtn?.addEventListener("click", closeSummary);
  els.summaryOverlay?.addEventListener("click", closeSummary);

  els.summaryPrintBtn?.addEventListener("click", printCurrentSummary);
  els.summaryPrintFooterBtn?.addEventListener("click", printCurrentSummary);


  // ==========================================================
  // 56. KEYBOARD SHORTCUTS
  // ==========================================================

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();

      els.globalSearch?.focus();
      els.globalSearch?.select();

      return;
    }

    if (event.key !== "Escape") return;

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
  // 57. EXTERNAL REFRESH HOOKS
  // ==========================================================

  window.loadAllResults = loadAllResults;
  window.refreshAdminResults = loadAllResults;

  window.addEventListener("emis:result-submitted", () => loadAllResults({ silent: true }));
  window.addEventListener("emis:results-changed", () => loadAllResults({ silent: true }));


  // ==========================================================
  // 58. INITIALIZE
  // ==========================================================

  async function init() {
    populateTermOptions(DEFAULT_TERMS, false);

    updateTermUi();
    syncClassPills();
    syncStatusTabs();
    syncColumnCheckboxes();
    updateSelectionUi();
    updateSortIcons();

    await loadAvailableTerms();
    await loadAllResults();
  }

  init();
});
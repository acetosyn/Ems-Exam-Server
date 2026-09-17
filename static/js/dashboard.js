/* ======================================================================
   EMIS ADMIN DASHBOARD — LIVE CONTROL CENTER V1
   Uses existing EMIS APIs only. No backend changes required.

   LIVE SOURCES:
     • /api/academic-settings
     • /api/promotion/summary + /api/promotion/students
     • /api/results/all
     • /api/notifications/fetch + /api/notifications/stream
     • /api/attendance/history
     • /api/ca-tests/history
     • /api/report-sheets/saved
     • /api/sync/status
     • /api/promotion/logs
   ====================================================================== */

(() => {
  "use strict";

  const root = document.getElementById("emisDashboard");
  if (!root || root.dataset.liveBound === "1") return;
  root.dataset.liveBound = "1";

  const $ = id => document.getElementById(id), $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
  const TERM_LABELS = { FIRST: "First Term", SECOND: "Second Term", THIRD: "Third Term" };
  const CLASS_ARMS = {
    JSS1: ["JSS1A", "JSS1B", "JSS1C"], JSS2: ["JSS2A", "JSS2B", "JSS2C"], JSS3: ["JSS3A", "JSS3B", "JSS3C"],
    SS1: ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1_B/C"], SS2: ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2_B/C"], SS3: ["SS3_GOLD", "SS3_SILVER", "SS3_B/C"]
  };
  const CLASS_LEVELS = Object.keys(CLASS_ARMS), TOTAL_CLASS_ARMS = Object.values(CLASS_ARMS).reduce((sum, arms) => sum + arms.length, 0);
  const QUICK_REFRESH_MS = 30000, DEEP_REFRESH_MS = 60000, NOTIFICATION_POLL_MS = 8000, MAX_ACTIVITY = 18;

  const state = {
    academic: { year: "", session: "", term: "" }, results: null, attendance: null, ca: null, reports: null, sync: null,
    notifications: [], derivedActivity: [], systemLogs: [], activeExamMap: new Map(), seenSequences: new Set(), lastNotificationSequence: 0,
    activityMode: "live", initialNotificationLoad: true, initialDeepScan: true, autoRefresh: true, refreshing: false, lastRefreshAt: null,
    notificationStream: null, streamReconnectTimer: null, quickTimer: null, deepTimer: null, notificationTimer: null
  };

  const els = {
    refresh: $("refreshDashboard"), autoRefresh: $("autoRefreshToggle"), connectionPill: $("connectionPill"), connectionText: $("connectionText"),
    activePeriod: $("activeAcademicPeriod"), activeYear: $("activeAcademicYear"), activeSession: $("activeAcademicSession"), activeTerm: $("activeAcademicTerm"), academicState: $("academicPeriodState"),
    totalStudents: $("statTotalStudents"), studentsMeta: $("statStudentsMeta"), totalResults: $("statTotalResults"), pending: $("statPending"), activeExams: $("statActiveExams"), activeExamsMeta: $("statActiveExamsMeta"),
    average: $("statAvg"), avgMeta: $("statAvgMeta"), attendanceToday: $("statAttendanceToday"), attendanceMeta: $("statAttendanceMeta"), caCompletion: $("statCACompletion"), caMeta: $("statCAMeta"),
    pulsePass: $("resultPulsePassRate"), pulseSubjects: $("resultPulseSubjects"), pulsePending: $("resultPulsePending"), sparkline: $("resultSparkline"), sparkMeta: $("resultSparkMeta"),
    activityFeed: $("liveActivityFeed"), activityCount: $("liveActivityCount"), systemPulseState: $("systemPulseState"), smartAlerts: $("smartAlerts"), smartAlertCount: $("smartAlertCount"),
    moduleSearch: $("moduleSearch"), moduleSearchEmpty: $("moduleSearchEmpty"), lastRefresh: $("lastRefreshText"), toastHost: $("dashboardToastHost")
  };

  function clean(value) { return String(value ?? "").trim(); }
  function upper(value) { return clean(value).toUpperCase(); }
  function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" }[ch])); }
  function number(value, fallback = 0) { const parsed = Number.parseFloat(String(value ?? "").replace(/,/g, "").replace("%", "").trim()); return Number.isFinite(parsed) ? parsed : fallback; }
  function nullableNumber(value) { if (value === null || value === undefined || clean(value) === "") return null; const parsed = Number.parseFloat(String(value).replace(/,/g, "").replace("%", "").trim()); return Number.isFinite(parsed) ? parsed : null; }
  function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }
  function normalizeTerm(value) {
    const raw = upper(value).replace(/[_-]+/g, " ").replace(/\s+/g, " ");
    if (["FIRST", "FIRST TERM", "1", "1ST", "1ST TERM", "TERM 1"].includes(raw)) return "FIRST";
    if (["SECOND", "SECOND TERM", "2", "2ND", "2ND TERM", "TERM 2"].includes(raw)) return "SECOND";
    if (["THIRD", "THIRD TERM", "3", "3RD", "3RD TERM", "TERM 3"].includes(raw)) return "THIRD";
    return "";
  }
  function query(params = {}) { const q = new URLSearchParams(); Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== null && clean(value) !== "") q.set(key, value); }); return q.toString(); }
  function todayISO() { const d = new Date(), offset = d.getTimezoneOffset(); return new Date(d.getTime() - offset * 60000).toISOString().slice(0, 10); }
  function formatNumber(value) { const n = Number(value); return Number.isFinite(n) ? n.toLocaleString() : "0"; }
  function formatPercent(value, digits = 1) { const n = Number(value); return Number.isFinite(n) ? `${n.toFixed(digits).replace(/\.0$/, "")}%` : "—"; }
  function formatClass(value) { return clean(value).replaceAll("_", " "); }
  function timeAgo(value) {
    if (!value) return "Just now";
    const date = value instanceof Date ? value : new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return clean(value) || "Just now";
    const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    if (seconds < 45) return "Just now"; if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`; if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`; return `${Math.floor(seconds / 86400)}d ago`;
  }
  function safeTimestamp(value) { const d = new Date(String(value || "").replace(" ", "T")); return Number.isNaN(d.getTime()) ? 0 : d.getTime(); }
  function setText(element, value) { if (element) element.textContent = value ?? ""; }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, { credentials:"same-origin", cache:"no-store", ...options, headers:{ Accept:"application/json", ...(options.body ? { "Content-Type":"application/json" } : {}), ...(options.headers || {}) } });
    let data = {}; try { data = await response.json(); } catch (_) { data = {}; }
    if (response.status === 401 || response.status === 403) { const error = new Error(data.message || data.error || "Your staff session has expired."); error.sessionExpired = true; throw error; }
    if (!response.ok) throw new Error(data.message || data.error || `Request failed (${response.status})`);
    return data;
  }

  async function mapLimit(items, limit, worker) {
    const output = new Array(items.length); let index = 0;
    async function runner() { while (index < items.length) { const current = index++; try { output[current] = await worker(items[current], current); } catch (error) { output[current] = { __error: error }; } } }
    await Promise.all(Array.from({ length:Math.min(limit, items.length) }, runner)); return output;
  }

  function showToast(title, message, type = "info", timeout = 5200) {
    if (!els.toastHost) return;
    const icons = { success:"fa-circle-check", warning:"fa-triangle-exclamation", danger:"fa-circle-xmark", info:"fa-bell" }, toast = document.createElement("article");
    toast.className = `dashboard-toast ${type}`;
    toast.innerHTML = `<span class="toast-icon"><i class="fa-solid ${icons[type] || icons.info}"></i></span><div class="toast-copy"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p></div><button class="toast-close" type="button" aria-label="Dismiss"><i class="fa-solid fa-xmark"></i></button>`;
    els.toastHost.prepend(toast); while (els.toastHost.children.length > 3) els.toastHost.lastElementChild?.remove();
    const close = () => { if (!toast.isConnected) return; toast.classList.add("leaving"); setTimeout(() => toast.remove(), 220); };
    toast.querySelector(".toast-close")?.addEventListener("click", close); requestAnimationFrame(() => toast.classList.add("show")); setTimeout(close, timeout);
  }

  function deriveAcademicSource(payload) { return payload?.settings || payload?.academic || payload?.context || payload || {}; }
  function academicFromSource(source = {}) {
    let session = clean(source.academic_session || source.session || source.current_session || source.active_session), year = clean(source.result_year || source.year || source.active_year || source.current_year), term = normalizeTerm(source.term || source.current_term || source.active_term);
    if (!year && /^\d{4}\/\d{4}$/.test(session)) year = session.slice(0, 4);
    if (!session && /^\d{4}$/.test(year)) session = `${year}/${Number(year) + 1}`;
    return { year, session, term };
  }

  async function loadAcademicContext() {
    let academic = { year:"", session:"", term:"" };
    try { academic = academicFromSource(deriveAcademicSource(await fetchJson("/api/academic-settings"))); } catch (_) {}
    if (!academic.session || !academic.term) {
      try { const config = await fetchJson("/api/attendance/config"); academic = { ...academic, ...Object.fromEntries(Object.entries(academicFromSource(config.academic || config)).filter(([,v]) => v)) }; } catch (_) {}
    }
    const globalContext = window.EMIS_ACADEMIC_CONTEXT || window.EMISAcademicContext || window.emisAcademicContext;
    if (globalContext) { const fallback = academicFromSource(globalContext); academic = { year:academic.year || fallback.year, session:academic.session || fallback.session, term:academic.term || fallback.term }; }
    state.academic = academic; renderAcademicContext(); return academic;
  }

  function renderAcademicContext() {
    const { year, session, term } = state.academic, label = [session, TERM_LABELS[term]].filter(Boolean).join(" • ") || "Academic period not configured";
    setText(els.activePeriod, label); setText(els.activeYear, year || "—"); setText(els.activeSession, session || "—"); setText(els.activeTerm, TERM_LABELS[term] || "—"); setText(els.academicState, session && term ? "Active" : "Needs Setup");
    if (els.academicState) els.academicState.classList.toggle("warning", !(session && term));
  }

  function extractStudentTotal(payload) {
    const direct = [payload?.total_students, payload?.active_students, payload?.count, payload?.summary?.total_students, payload?.summary?.active_students].map(v => Number(v)).find(Number.isFinite);
    if (Number.isFinite(direct)) return direct;
    const summary = payload?.summary; if (!summary || typeof summary !== "object") return null;
    let total = 0, found = false;
    CLASS_LEVELS.forEach(level => { const item = summary[level]; if (typeof item === "number" && Number.isFinite(item)) { total += item; found = true; return; } if (!item || typeof item !== "object") return; const candidate = [item.total_students, item.active_students, item.students, item.count, item.total, item.active].map(v => Number(v)).find(Number.isFinite); if (Number.isFinite(candidate)) { total += candidate; found = true; } });
    return found ? total : null;
  }

  async function loadStudentStats() {
    let total = null;
    try { total = extractStudentTotal(await fetchJson("/api/promotion/summary")); } catch (_) {}
    if (total === null) {
      const rows = await mapLimit(CLASS_LEVELS, 3, async level => fetchJson(`/api/promotion/students?${query({ class:level })}`));
      total = rows.reduce((sum, item) => sum + (item && !item.__error ? Number(item.count ?? item.students?.length ?? 0) : 0), 0);
    }
    setText(els.totalStudents, formatNumber(total)); setText(els.studentsMeta, "Active master roster"); return total;
  }

  function resultStudent(row) { return clean(row?.["Student Name"] ?? row?.full_name ?? row?.student_name ?? row?.name ?? "Student"); }
  function resultAdmission(row) { return clean(row?.["Admission No"] ?? row?.Admission_number ?? row?.admission_number ?? row?.student_id); }
  function resultSubject(row) { return clean(row?.Subject ?? row?.subject ?? row?.["Subject Folder"] ?? row?.subject_folder); }
  function resultSubmittedAt(row) { return row?.["Submitted At"] ?? row?.submitted_at ?? row?.submittedAt ?? ""; }
  function resultEssayAvailable(row) {
    const explicit = row?.essay_available ?? row?.has_essay ?? row?.hasEssay ?? row?.essay_present ?? row?.theory_present;
    if (explicit !== undefined && explicit !== null && explicit !== "") return [true,1,"1","true","yes","available","present"].includes(typeof explicit === "string" ? explicit.toLowerCase() : explicit);
    return nullableNumber(row?.essay_score ?? row?.theory_score ?? row?.["Essay Score"] ?? row?.["Theory Score"]) !== null || nullableNumber(row?.essay_max ?? row?.theory_max ?? row?.["Essay Max"]) !== null;
  }
  function resultFinalScore(row) {
    const explicit = nullableNumber(row?.final_score ?? row?.combined_score ?? row?.total_score ?? row?.["Final Score"] ?? row?.["Combined Score"]); if (explicit !== null) return explicit;
    const correct = nullableNumber(row?.Correct ?? row?.correct ?? row?.correct_answers), totalQuestions = nullableNumber(row?.Total ?? row?.total ?? row?.total_questions ?? row?.question_count), percentage = nullableNumber(row?.["Score (%)"] ?? row?.["Score Number"] ?? row?.score_percentage ?? row?.percentage ?? row?.score);
    const essayAvailable = resultEssayAvailable(row), objectiveMax = nullableNumber(row?.objective_max ?? row?.objective_weight ?? row?.["Objective Max"]) ?? (essayAvailable ? 60 : 100);
    let objective = nullableNumber(row?.objective_score ?? row?.objective_mark ?? row?.["Objective Score"] ?? row?.["Objective Mark"]);
    if (objective === null && totalQuestions && totalQuestions > 0 && correct !== null) objective = (correct / totalQuestions) * objectiveMax;
    if (objective === null && percentage !== null) objective = (percentage / 100) * objectiveMax;
    if (objective === null) return null; if (!essayAvailable) return objective;
    const essay = nullableNumber(row?.essay_score ?? row?.theory_score ?? row?.["Essay Score"] ?? row?.["Theory Score"]); return essay === null ? null : objective + essay;
  }
  function resultPending(row) { return resultFinalScore(row) === null; }

  async function loadResultStats({ notifyChanges = true } = {}) {
    const { year, term } = state.academic, params = { year:year || "all", class:"all", subject:"all", term:term || "all" }, payload = await fetchJson(`/api/results/all?${query(params)}`);
    const rows = Array.isArray(payload?.results) ? payload.results : Array.isArray(payload) ? payload : [], completed = rows.map(row => ({ row, score:resultFinalScore(row) })).filter(item => item.score !== null), total = rows.length, pending = rows.filter(resultPending).length;
    const average = completed.length ? completed.reduce((sum, item) => sum + item.score, 0) / completed.length : 0, passed = completed.filter(item => item.score >= 50).length, passRate = completed.length ? (passed / completed.length) * 100 : 0, subjects = new Set(rows.map(resultSubject).filter(Boolean));
    const recent = completed.slice().sort((a,b) => safeTimestamp(resultSubmittedAt(b.row)) - safeTimestamp(resultSubmittedAt(a.row))).slice(0, 12);
    const previousTotal = state.results?.total ?? null; state.results = { total, pending, average, passed, passRate, subjects:subjects.size, recent, rows };
    setText(els.totalResults, formatNumber(total)); setText(els.pending, formatNumber(pending)); setText(els.average, completed.length ? formatPercent(average) : "—"); setText(els.avgMeta, `${formatPercent(passRate)} pass rate`);
    setText(els.pulsePass, completed.length ? formatPercent(passRate) : "—"); setText(els.pulseSubjects, formatNumber(subjects.size)); setText(els.pulsePending, formatNumber(pending)); renderSparkline(recent);
    setHealth("Results", total ? "Live" : "Waiting", total ? `${formatNumber(total)} records • ${formatNumber(pending)} pending` : "No records for active period", total ? (pending ? "warning" : "success") : "neutral");
    if (notifyChanges && previousTotal !== null && total > previousTotal) addDerivedActivity({ type:"result", title:"New results detected", message:`${total - previousTotal} new result record${total - previousTotal === 1 ? "" : "s"} added to the active academic period.`, tone:"success" }, true);
    return state.results;
  }

  function renderSparkline(recent) {
    if (!els.sparkline) return;
    if (!recent.length) { els.sparkline.innerHTML = `<span class="spark-placeholder">No completed results yet</span>`; setText(els.sparkMeta, "Waiting for completed scores"); return; }
    els.sparkline.innerHTML = recent.slice().reverse().map(item => { const level = Math.max(5, Math.min(100, Math.round(clamp(item.score, 0, 100) / 5) * 5)); return `<span class="spark-bar spark-${String(level).padStart(3, "0")}" title="${escapeHtml(resultStudent(item.row))}: ${Math.round(item.score * 10) / 10}%"></span>`; }).join("");
    setText(els.sparkMeta, `${recent.length} recent result${recent.length === 1 ? "" : "s"}`);
  }

  function allClassTargets() { return Object.entries(CLASS_ARMS).flatMap(([level, arms]) => arms.map(arm => ({ level, arm }))); }

  async function loadAttendanceStats({ notifyChanges = true } = {}) {
    const { session, term } = state.academic; if (!session || !term) return null;
    const date = todayISO(), results = await mapLimit(allClassTargets(), 4, async item => fetchJson(`/api/attendance/history?${query({ session, term, class_level:item.level, class_arm:item.arm, start_date:date, end_date:date })}`));
    let markedClasses = 0, studentRecords = 0, present = 0, absent = 0, late = 0, sick = 0, excused = 0, unmarked = 0, holidays = 0;
    results.forEach(data => { if (!data || data.__error) return; const daily = Array.isArray(data.daily) ? data.daily : Array.isArray(data.daily_breakdown) ? data.daily_breakdown : [], today = daily.find(item => clean(item.date) === date) || daily[0]; if (!today && !(data.count > 0)) return; markedClasses++; if (!today) { studentRecords += Number(data.count || 0); return; } studentRecords += Number(today.records ?? today.total ?? 0); present += Number(today.present || 0); absent += Number(today.absent || 0); late += Number(today.late || 0); sick += Number(today.sick || 0); excused += Number(today.excused || 0); unmarked += Number(today.unmarked || 0); holidays += Number(today.holiday || 0); });
    const denominator = present + absent + late + sick + excused + unmarked, rate = denominator ? ((present + late + excused) / denominator) * 100 : 0, previous = state.attendance?.markedClasses ?? null;
    state.attendance = { markedClasses, studentRecords, present, absent, late, sick, excused, unmarked, holidays, rate, totalClasses:TOTAL_CLASS_ARMS };
    setText(els.attendanceToday, `${markedClasses}/${TOTAL_CLASS_ARMS}`); setText(els.attendanceMeta, `${formatNumber(studentRecords)} records${denominator ? ` • ${formatPercent(rate)} credit` : ""}`);
    setHealth("Attendance", markedClasses ? (markedClasses >= TOTAL_CLASS_ARMS ? "Complete" : "Live") : "Waiting", `${markedClasses}/${TOTAL_CLASS_ARMS} class registers today`, markedClasses >= TOTAL_CLASS_ARMS ? "success" : markedClasses ? "warning" : "neutral");
    if (notifyChanges && previous !== null && markedClasses > previous) addDerivedActivity({ type:"attendance", title:"Attendance register updated", message:`${markedClasses - previous} additional class register${markedClasses - previous === 1 ? "" : "s"} detected for today.`, tone:"success" }, true);
    return state.attendance;
  }

  async function loadCAStats({ notifyChanges = true } = {}) {
    const { session, term } = state.academic; if (!session || !term) return null;
    const results = await mapLimit(allClassTargets(), 4, async item => fetchJson(`/api/ca-tests/history?${query({ session, term, class_level:item.level, class_arm:item.arm })}`));
    let subjectRegisters = 0, students = 0, complete = 0, incomplete = 0, latest = "";
    results.forEach(data => { if (!data || data.__error) return; const records = Array.isArray(data.records) ? data.records : Array.isArray(data.subjects) ? data.subjects : []; subjectRegisters += records.length; records.forEach(item => { students += Number(item.students || 0); complete += Number(item.complete || 0); incomplete += Number(item.incomplete || 0); if (safeTimestamp(item.saved_at) > safeTimestamp(latest)) latest = item.saved_at; }); });
    const denominator = complete + incomplete, completion = denominator ? (complete / denominator) * 100 : 0, previousComplete = state.ca?.complete ?? null;
    state.ca = { subjectRegisters, students, complete, incomplete, completion, latest };
    setText(els.caCompletion, denominator ? formatPercent(completion) : "—"); setText(els.caMeta, `${formatNumber(complete)} complete • ${formatNumber(incomplete)} incomplete`);
    setHealth("CA", subjectRegisters ? (incomplete ? "In Progress" : "Ready") : "Waiting", subjectRegisters ? `${subjectRegisters} subject register${subjectRegisters === 1 ? "" : "s"} saved` : "No CA/Test records yet", subjectRegisters ? (incomplete ? "warning" : "success") : "neutral");
    if (notifyChanges && previousComplete !== null && complete > previousComplete) addDerivedActivity({ type:"ca", title:"CA/Test scores updated", message:`${complete - previousComplete} additional complete student assessment record${complete - previousComplete === 1 ? "" : "s"} detected.`, tone:"success" }, true);
    return state.ca;
  }

  async function loadReportStats({ notifyChanges = true } = {}) {
    const { session, term } = state.academic; if (!session || !term) return null;
    const payload = await fetchJson(`/api/report-sheets/saved?${query({ session, term })}`), reports = Array.isArray(payload.reports) ? payload.reports : [], count = Number(payload.count ?? reports.length ?? 0), previous = state.reports?.count ?? null;
    state.reports = { count, reports };
    setHealth("Reports", count ? "Ready" : "Waiting", count ? `${formatNumber(count)} saved report${count === 1 ? "" : "s"}` : "No saved reports for active period", count ? "success" : "neutral");
    if (notifyChanges && previous !== null && count > previous) addDerivedActivity({ type:"report", title:"Report sheets generated", message:`${count - previous} new saved report sheet${count - previous === 1 ? "" : "s"} detected.`, tone:"success" }, true);
    return state.reports;
  }

  async function loadSyncStatus({ notifyChanges = true } = {}) {
    const payload = await fetchJson("/api/sync/status"), failed = Number(payload.failed || 0), pending = Number(payload.pending || 0), synced = Number(payload.synced || 0), received = Number(payload.received || 0), role = payload.sender_enabled ? "Sender" : payload.receiver_enabled ? "Receiver" : "Disabled", previousFailed = state.sync?.failed ?? null;
    state.sync = { ...payload, failed, pending, synced, received, role };
    const status = failed ? "Attention" : pending ? "Syncing" : (payload.sender_enabled || payload.receiver_enabled) ? "Healthy" : "Disabled", tone = failed ? "danger" : pending ? "warning" : (payload.sender_enabled || payload.receiver_enabled) ? "success" : "neutral";
    const details = payload.sender_enabled ? `${pending} pending • ${synced} synced` : payload.receiver_enabled ? `${received} received • Cloud receiver` : "Synchronization disabled";
    setHealth("Sync", status, details, tone);
    if (notifyChanges && previousFailed !== null && failed > previousFailed) addDerivedActivity({ type:"sync", title:"Sync requires attention", message:`${failed} synchronization event${failed === 1 ? "" : "s"} currently failed.`, tone:"danger" }, true);
    return state.sync;
  }

  function healthElements(name) {
    const map = { Attendance:[$("pulseAttendance"),$("pulseAttendanceMeta")], CA:[$("pulseCA"),$("pulseCAMeta")], Results:[$("pulseResults"),$("pulseResultsMeta")], Reports:[$("pulseReports"),$("pulseReportsMeta")], Sync:[$("pulseSync"),$("pulseSyncMeta")] }; return map[name] || [];
  }
  function setHealth(name, label, meta, tone = "neutral") {
    const [status, detail] = healthElements(name); if (status) { status.textContent = label; status.className = `health-status ${tone}`; } if (detail) detail.textContent = meta;
  }

  function updateOverallHealth() {
    const tones = []; if (state.sync?.failed) tones.push("danger"); if (state.ca?.incomplete || (state.attendance?.markedClasses > 0 && state.attendance?.markedClasses < TOTAL_CLASS_ARMS) || state.results?.pending || state.sync?.pending) tones.push("warning");
    const tone = tones.includes("danger") ? "danger" : tones.includes("warning") ? "warning" : "success", label = tone === "danger" ? "Attention" : tone === "warning" ? "Monitoring" : "Healthy";
    if (els.systemPulseState) { els.systemPulseState.textContent = label; els.systemPulseState.className = `health-badge ${tone}`; }
  }

  function buildSmartAlerts() {
    const alerts = [];
    if (!navigator.onLine) alerts.push({ tone:"danger", icon:"fa-wifi", title:"Browser is offline", message:"Live cloud updates will resume when connectivity returns." });
    if (state.sync?.failed) alerts.push({ tone:"danger", icon:"fa-cloud-exclamation", title:"Synchronization failures", message:`${state.sync.failed} sync event${state.sync.failed === 1 ? "" : "s"} need attention.` });
    else if (state.sync?.pending) alerts.push({ tone:"warning", icon:"fa-cloud-arrow-up", title:"Synchronization in progress", message:`${state.sync.pending} event${state.sync.pending === 1 ? "" : "s"} waiting to sync.` });
    if (state.results?.pending) alerts.push({ tone:"warning", icon:"fa-pen-to-square", title:"Incomplete examination results", message:`${state.results.pending} result${state.results.pending === 1 ? " is" : "s are"} awaiting completion/essay scores.` });
    if (state.ca?.incomplete) alerts.push({ tone:"warning", icon:"fa-clipboard-question", title:"Incomplete CA/Test entries", message:`${state.ca.incomplete} student assessment record${state.ca.incomplete === 1 ? " is" : "s are"} incomplete.` });
    if (state.attendance && state.attendance.markedClasses < TOTAL_CLASS_ARMS) alerts.push({ tone:"info", icon:"fa-calendar-day", title:"Attendance coverage today", message:`${state.attendance.markedClasses}/${TOTAL_CLASS_ARMS} class registers currently have attendance activity.` });
    if (state.reports && !state.reports.count) alerts.push({ tone:"info", icon:"fa-file-circle-exclamation", title:"No saved report sheets yet", message:"No report snapshots are saved for the active academic period." });
    renderSmartAlerts(alerts.slice(0, 5)); updateOverallHealth();
  }

  function renderSmartAlerts(alerts) {
    setText(els.smartAlertCount, alerts.length);
    if (!els.smartAlerts) return;
    if (!alerts.length) { els.smartAlerts.innerHTML = `<div class="mini-empty"><i class="fa-solid fa-shield-check"></i> No critical alerts.</div>`; return; }
    els.smartAlerts.innerHTML = alerts.map(item => `<div class="smart-alert ${item.tone === "danger" || item.tone === "warning" ? item.tone : ""}"><i class="fa-solid ${item.icon}"></i><div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.message)}</span></div></div>`).join("");
  }

  function activityKey(item) { return clean(item.sequence || item.id || `${item.type}|${item.title}|${item.message}|${item.time}`); }
  function eventType(item) { return clean(item.event_type || item.type || item.kind).toLowerCase(); }
  function notificationTitle(item) {
    const type = eventType(item), student = clean(item.student_name || item.name || item.full_name || item.payload?.student_name || item.payload?.name);
    if (type === "exam_start") return student ? `${student} started an exam` : "Examination started";
    if (type === "exam_end") return student ? `${student} submitted an exam` : "Examination submitted";
    if (type === "timeout") return student ? `${student}'s exam timed out` : "Examination timed out";
    return clean(item.title || item.message || "Live EMIS activity");
  }
  function notificationMessage(item) {
    if (clean(item.message)) return clean(item.message);
    const subject = clean(item.subject || item.payload?.subject), admission = clean(item.admission_number || item.admission || item.payload?.admission_number || item.payload?.admission);
    return [subject && `Subject: ${formatClass(subject)}`, admission && `Admission: ${admission}`].filter(Boolean).join(" • ") || "New activity received from the EMIS server.";
  }
  function notificationMeta(item) {
    const source = item.payload && typeof item.payload === "object" ? { ...item, ...item.payload } : item;
    return [clean(source.class_arm || source.class || source.class_level), clean(source.subject), normalizeTerm(source.term) ? TERM_LABELS[normalizeTerm(source.term)] : "", clean(source.score) !== "" ? `Score ${clean(source.score)}` : ""].filter(Boolean).slice(0, 3);
  }
  function notificationTime(item) { return item.created_at_iso || item.created_at_text || item.timestamp || item.time || item.submitted_at || new Date().toISOString(); }
  function notificationTone(item) { const type = eventType(item); return type === "exam_end" ? "success" : type === "timeout" ? "warning" : type === "exam_start" ? "info" : item.tone || "info"; }
  function notificationIcon(item) { const type = eventType(item); return type === "exam_start" ? "fa-play" : type === "exam_end" ? "fa-circle-check" : type === "timeout" ? "fa-clock" : "fa-bell"; }

  function examSessionKey(item) {
    const source = item.payload && typeof item.payload === "object" ? { ...item, ...item.payload } : item, admission = clean(source.admission_number || source.admission || source.student_id), subject = upper(source.subject || source.exam_subject || "EXAM");
    return `${admission || clean(source.student_name || source.name)}::${subject}`;
  }
  function applyExamEvent(item) {
    const type = eventType(item), key = examSessionKey(item); if (!key || key === "::EXAM") return;
    if (type === "exam_start") state.activeExamMap.set(key, item); else if (["exam_end", "timeout"].includes(type)) state.activeExamMap.delete(key);
  }
  function renderActiveExamStat() { const count = state.activeExamMap.size; setText(els.activeExams, formatNumber(count)); setText(els.activeExamsMeta, count ? `${count} student session${count === 1 ? "" : "s"} currently active` : "No active student exam detected"); }

  function ingestNotification(item, { announce = false } = {}) {
    const sequence = Number(item?.sequence || 0); if (sequence && state.seenSequences.has(sequence)) return false;
    if (sequence) { state.seenSequences.add(sequence); state.lastNotificationSequence = Math.max(state.lastNotificationSequence, sequence); }
    state.notifications.push(item); if (state.notifications.length > 80) state.notifications = state.notifications.slice(-80); applyExamEvent(item); renderActiveExamStat();
    if (announce) { const type = notificationTone(item); showToast(notificationTitle(item), notificationMessage(item), type); if (["exam_end", "timeout"].includes(eventType(item))) setTimeout(() => loadResultStats({ notifyChanges:true }).then(() => { buildSmartAlerts(); renderActivity(); }).catch(() => {}), 900); }
    return true;
  }

  async function pollNotifications({ initial = false } = {}) {
    try {
      const since = initial ? 0 : state.lastNotificationSequence, payload = await fetchJson(`/api/notifications/fetch?${query({ since_sequence:since })}`), notifications = Array.isArray(payload.notifications) ? payload.notifications.slice().sort((a,b) => Number(a.sequence || 0) - Number(b.sequence || 0)) : [];
      notifications.forEach(item => ingestNotification(item, { announce:!initial })); if (initial && payload.latest_sequence) state.lastNotificationSequence = Math.max(state.lastNotificationSequence, Number(payload.latest_sequence || 0));
      state.initialNotificationLoad = false; renderActivity();
    } catch (error) { if (error.sessionExpired) return; console.warn("[EMIS Dashboard] notification polling:", error.message); }
  }

  function connectNotificationStream() {
    if (!("EventSource" in window) || state.notificationStream) return;
    try {
      const source = new EventSource(`/api/notifications/stream?${query({ since_sequence:state.lastNotificationSequence })}`); state.notificationStream = source;
      source.addEventListener("notification", event => { try { const item = JSON.parse(event.data || "{}"); if (ingestNotification(item, { announce:true })) renderActivity(); } catch (_) {} });
      source.addEventListener("connected", () => {});
      source.onerror = () => { try { source.close(); } catch (_) {} state.notificationStream = null; clearTimeout(state.streamReconnectTimer); state.streamReconnectTimer = setTimeout(connectNotificationStream, 6000); };
    } catch (_) { state.notificationStream = null; }
  }

  function addDerivedActivity(item, announce = false) {
    const event = { ...item, id:`derived-${Date.now()}-${Math.random().toString(16).slice(2)}`, time:new Date().toISOString() }; state.derivedActivity.push(event); if (state.derivedActivity.length > 40) state.derivedActivity = state.derivedActivity.slice(-40); if (announce && !state.initialDeepScan) showToast(item.title, item.message, item.tone || "info"); renderActivity();
  }

  function activityItems() {
    const notificationItems = state.notifications.map(item => ({ id:`n-${activityKey(item)}`, title:notificationTitle(item), message:notificationMessage(item), meta:notificationMeta(item), time:notificationTime(item), tone:notificationTone(item), icon:notificationIcon(item) }));
    const derived = state.derivedActivity.map(item => ({ id:item.id, title:item.title, message:item.message, meta:item.meta || [], time:item.time, tone:item.tone || "info", icon:item.type === "attendance" ? "fa-calendar-check" : item.type === "ca" ? "fa-clipboard-check" : item.type === "report" ? "fa-file-lines" : item.type === "sync" ? "fa-cloud-arrow-up" : "fa-chart-line" }));
    return [...notificationItems, ...derived].sort((a,b) => safeTimestamp(b.time) - safeTimestamp(a.time)).slice(0, MAX_ACTIVITY);
  }

  function logItems() {
    return state.systemLogs.slice(0, MAX_ACTIVITY).map((log, index) => {
      const title = clean(log.action || log.Action || log.event || log.type || log.status || "System activity"), message = clean(log.message || log.Message || log.note || log.Note || log.details || log.description || log.student || "EMIS administrative activity recorded."), time = log.timestamp || log.Timestamp || log.saved_at || log.Saved_at || log.date || log.Date || "";
      return { id:`log-${index}-${time}`, title:title.replaceAll("_", " "), message, meta:[clean(log.class || log.Class || log.from_class), clean(log.to_class || log.destination)].filter(Boolean), time, tone:"info", icon:"fa-clock-rotate-left" };
    });
  }

  function renderActivity() {
    if (!els.activityFeed) return; const items = state.activityMode === "system" ? logItems() : activityItems(); setText(els.activityCount, items.length);
    if (!items.length) { els.activityFeed.innerHTML = `<div class="dash-empty-state"><i class="fa-regular fa-bell"></i><strong>${state.activityMode === "system" ? "No recent system log" : "Waiting for activity"}</strong><span>${state.activityMode === "system" ? "Promotion and database activity will appear here when available." : "Exam starts, submissions and module changes will appear here."}</span></div>`; return; }
    els.activityFeed.innerHTML = items.map(item => `<article class="activity-item"><span class="activity-icon ${item.tone}"><i class="fa-solid ${item.icon}"></i></span><div class="activity-copy"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.message)}</p>${item.meta?.length ? `<div class="activity-meta">${item.meta.map(meta => `<span>${escapeHtml(meta)}</span>`).join("")}</div>` : ""}</div><span class="activity-time">${escapeHtml(timeAgo(item.time))}</span></article>`).join("");
  }

  async function loadSystemLogs() { try { const payload = await fetchJson("/api/promotion/logs?limit=20"); state.systemLogs = Array.isArray(payload.logs) ? payload.logs : []; if (state.activityMode === "system") renderActivity(); } catch (_) { state.systemLogs = []; } }

  async function quickRefresh({ manual = false } = {}) {
    if (state.refreshing) return; state.refreshing = true; if (els.refresh) els.refresh.classList.add("loading");
    try {
      await loadAcademicContext();
      const tasks = [loadStudentStats(), loadResultStats({ notifyChanges:!manual }), loadSyncStatus({ notifyChanges:!manual }), loadSystemLogs()];
      await Promise.allSettled(tasks); buildSmartAlerts(); renderActivity(); markRefreshed();
      if (manual) showToast("Dashboard refreshed", "Live EMIS statistics have been updated.", "success", 3000);
    } catch (error) { console.warn("[EMIS Dashboard] quick refresh:", error); if (manual) showToast("Refresh incomplete", error.message || "Some live data could not be refreshed.", "warning"); }
    finally { state.refreshing = false; if (els.refresh) els.refresh.classList.remove("loading"); }
  }

  async function deepRefresh({ manual = false } = {}) {
    if (!state.academic.session || !state.academic.term) await loadAcademicContext();
    const tasks = [loadAttendanceStats({ notifyChanges:!manual }), loadCAStats({ notifyChanges:!manual }), loadReportStats({ notifyChanges:!manual })];
    await Promise.allSettled(tasks); buildSmartAlerts(); state.initialDeepScan = false; renderActivity(); markRefreshed();
  }

  function markRefreshed() { state.lastRefreshAt = new Date(); updateRefreshLabel(); }
  function updateRefreshLabel() { if (!els.lastRefresh) return; els.lastRefresh.innerHTML = `<i class="fa-regular fa-clock"></i> ${state.lastRefreshAt ? `Updated ${escapeHtml(timeAgo(state.lastRefreshAt))}` : "Waiting for first refresh…"}`; }

  function updateNetworkState() {
    const online = navigator.onLine; if (els.connectionPill) els.connectionPill.className = `connection-pill ${online ? "online" : "offline"}`; setText(els.connectionText, online ? "Connected • Live updates enabled" : "Offline • Showing last known data"); buildSmartAlerts();
    if (online && state.autoRefresh && !document.hidden) { quickRefresh().catch(() => {}); deepRefresh().catch(() => {}); connectNotificationStream(); }
  }

  function scheduleTimers() {
    clearInterval(state.quickTimer); clearInterval(state.deepTimer); clearInterval(state.notificationTimer);
    state.quickTimer = setInterval(() => { if (state.autoRefresh && !document.hidden && navigator.onLine) quickRefresh().catch(() => {}); }, QUICK_REFRESH_MS);
    state.deepTimer = setInterval(() => { if (state.autoRefresh && !document.hidden && navigator.onLine) deepRefresh().catch(() => {}); }, DEEP_REFRESH_MS);
    state.notificationTimer = setInterval(() => { if (navigator.onLine && !document.hidden) pollNotifications().catch(() => {}); }, NOTIFICATION_POLL_MS);
  }

  function toggleAutoRefresh() {
    state.autoRefresh = !state.autoRefresh; try { localStorage.setItem("emis_dashboard_auto_refresh", state.autoRefresh ? "1" : "0"); } catch (_) {}
    if (els.autoRefresh) { els.autoRefresh.classList.toggle("paused", !state.autoRefresh); els.autoRefresh.setAttribute("aria-pressed", state.autoRefresh ? "true" : "false"); els.autoRefresh.querySelector("span").textContent = state.autoRefresh ? "Auto Refresh" : "Auto Paused"; }
    showToast(state.autoRefresh ? "Auto refresh enabled" : "Auto refresh paused", state.autoRefresh ? "Dashboard data will continue updating automatically." : "Use Refresh Now whenever you want the latest module data.", "info", 3200);
    if (state.autoRefresh) { quickRefresh().catch(() => {}); deepRefresh().catch(() => {}); }
  }

  function bindModuleSearch() {
    if (!els.moduleSearch) return;
    els.moduleSearch.addEventListener("input", () => { const needle = clean(els.moduleSearch.value).toLowerCase(); let visible = 0; $$(".module-link", $("moduleLinkGrid")).forEach(link => { const match = !needle || clean(link.dataset.moduleName).toLowerCase().includes(needle) || clean(link.textContent).toLowerCase().includes(needle); link.hidden = !match; if (match) visible++; }); if (els.moduleSearchEmpty) els.moduleSearchEmpty.hidden = visible > 0; });
    document.addEventListener("keydown", event => { const tag = document.activeElement?.tagName?.toLowerCase(); if (event.key === "/" && !["input","textarea","select"].includes(tag)) { event.preventDefault(); els.moduleSearch.focus(); } if (event.key === "Escape" && document.activeElement === els.moduleSearch) { els.moduleSearch.value = ""; els.moduleSearch.dispatchEvent(new Event("input")); els.moduleSearch.blur(); } });
  }

  function bindActivityTabs() {
    $$("[data-activity-tab]", root).forEach(button => button.addEventListener("click", () => { state.activityMode = button.dataset.activityTab || "live"; $$("[data-activity-tab]", root).forEach(item => { const active = item === button; item.classList.toggle("active", active); item.setAttribute("aria-selected", active ? "true" : "false"); }); renderActivity(); }));
  }

  function restorePreferences() { try { state.autoRefresh = localStorage.getItem("emis_dashboard_auto_refresh") !== "0"; } catch (_) { state.autoRefresh = true; } if (els.autoRefresh && !state.autoRefresh) { els.autoRefresh.classList.add("paused"); els.autoRefresh.setAttribute("aria-pressed", "false"); els.autoRefresh.querySelector("span").textContent = "Auto Paused"; } }

  async function initialize() {
    restorePreferences(); bindModuleSearch(); bindActivityTabs(); updateNetworkState(); scheduleTimers();
    els.refresh?.addEventListener("click", async () => { await quickRefresh({ manual:true }); await deepRefresh({ manual:true }); });
    els.autoRefresh?.addEventListener("click", toggleAutoRefresh);
    window.addEventListener("online", updateNetworkState); window.addEventListener("offline", updateNetworkState);
    document.addEventListener("visibilitychange", () => { if (!document.hidden && state.autoRefresh) { quickRefresh().catch(() => {}); deepRefresh().catch(() => {}); pollNotifications().catch(() => {}); } });
    window.addEventListener("emis:result-submitted", () => quickRefresh().catch(() => {})); window.addEventListener("emis:results-changed", () => quickRefresh().catch(() => {})); window.addEventListener("emis:essay-scores-changed", () => quickRefresh().catch(() => {}));
    setInterval(updateRefreshLabel, 30000);

    await loadAcademicContext();
    await Promise.allSettled([loadStudentStats(), loadResultStats({ notifyChanges:false }), loadSyncStatus({ notifyChanges:false }), loadSystemLogs(), pollNotifications({ initial:true })]);
    renderActivity(); connectNotificationStream(); await deepRefresh({ manual:true }); state.initialDeepScan = false; buildSmartAlerts(); markRefreshed();
  }

  initialize().catch(error => { console.error("[EMIS Dashboard] initialization failed:", error); showToast("Dashboard initialization", error.message || "Some live dashboard data could not be loaded.", "warning", 6000); });
})();

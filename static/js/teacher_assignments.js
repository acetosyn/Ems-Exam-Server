/* ==========================================================
   EMIS PHASE 3 — Teacher Assignment Manager
   ----------------------------------------------------------
   Admin: Teacher -> Session -> Class/Arm -> Subject assignment
   Teacher: read-only personal teaching-load summary
========================================================== */

(() => {
  "use strict";

  const root = document.querySelector(".teacher-phase3");
  if (!root) return;

  const role = String(root.dataset.staffRole || "").trim().toLowerCase();
  const $ = id => document.getElementById(id);
  const state = { config: null, teachers: [], selectedTeacherId: "", draftAssignments: [], savedSignature: "", session: "", loading: false };

  const escapeHTML = value => String(value ?? "").replace(/[&<>'"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
  const clean = value => String(value ?? "").trim();
  const canonicalSession = value => { const m = clean(value).match(/^(\d{4})\s*[\/-]\s*(\d{4})$/); return m ? `${m[1]}/${m[2]}` : clean(value); };
  const assignmentKey = row => [row.class_level || "", row.class_arm || "", row.subject_key || ""].map(v => clean(v).toUpperCase()).join("|");
  const draftSignature = rows => [...rows].map(assignmentKey).sort().join("||");

  function notify(message, type = "info") {
    const el = $("teacherAssignmentNotice");
    if (!el) return;
    el.className = `teacher-assignment-notice ${type}`; el.innerHTML = `<i class="fa-solid ${type === "success" ? "fa-circle-check" : type === "error" ? "fa-circle-exclamation" : "fa-circle-info"}"></i><span>${escapeHTML(message)}</span>`;
    clearTimeout(notify.timer); notify.timer = setTimeout(() => el.classList.add("hidden"), 4500);
  }

  async function api(url, options = {}) {
    const response = await fetch(url, { cache: "no-store", headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    let data = {}; try { data = await response.json(); } catch (_) {}
    if (!response.ok || data.success === false) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  }

  function classMeta(classLevel) {
    for (const section of state.config?.sections || []) {
      const found = (section.classes || []).find(item => item.key === classLevel);
      if (found) return { ...found, section_key: section.key, section_label: section.label };
    }
    return null;
  }

  function subjectMeta(classLevel, subjectKey) {
    const meta = classMeta(classLevel); return (meta?.subjects || []).find(item => clean(item.key).toUpperCase() === clean(subjectKey).toUpperCase()) || null;
  }

  function inferredTrack(arm) {
    const value = clean(arm).toUpperCase();
    if (!value) return "";
    if (value.endsWith("_B/C")) return "ART_COMMERCIAL";
    if (["_GOLD", "_SILVER", "_DIAMOND"].some(token => value.includes(token))) return "SCIENCE";
    return "GENERAL";
  }

  function subjectCompatible(subject, arm) {
    const tracks = (subject?.tracks || []).map(value => clean(value).toUpperCase());
    if (!arm || !tracks.length) return true;
    const track = inferredTrack(arm);
    if (!track || track === "GENERAL") return true;
    if (track === "ART_COMMERCIAL") return tracks.includes("ART") || tracks.includes("COMMERCIAL");
    return tracks.includes(track);
  }

  function assignmentDisplay(row) {
    const meta = classMeta(row.class_level) || {}; const subject = subjectMeta(row.class_level, row.subject_key) || {};
    return {
      section: row.section_label || meta.section_label || row.school_section || "School",
      classLabel: row.class_label || meta.label || row.class_level,
      armLabel: row.class_arm ? row.class_arm.replaceAll("_", " ") : "All applicable arms",
      subjectName: row.subject_name || subject.name || row.subject_key,
    };
  }

  function setDirty() {
    const dirty = draftSignature(state.draftAssignments) !== state.savedSignature; const el = $("taDirtyState");
    if (el) { el.classList.toggle("dirty", dirty); el.innerHTML = dirty ? '<i class="fa-solid fa-pen"></i> Unsaved assignment changes' : '<i class="fa-solid fa-circle-check"></i> No unsaved changes'; }
    const save = $("taSaveAssignments"); if (save) save.disabled = !state.selectedTeacherId || state.loading || !dirty;
  }

  function updateAdminStats(stats = {}) {
    if ($("taTotalTeachers")) $("taTotalTeachers").textContent = stats.teacher_count ?? "0";
    if ($("taActiveTeachers")) $("taActiveTeachers").textContent = stats.active_teacher_count ?? "0";
    if ($("taTeachersAssigned")) $("taTeachersAssigned").textContent = stats.teachers_assigned ?? "0";
    if ($("taAssignmentCount")) $("taAssignmentCount").textContent = stats.assignment_count ?? "0";
    if ($("taSessionStat")) $("taSessionStat").textContent = stats.academic_session || state.session || "Current session";
  }

  function teacherInitial(teacher) {
    const source = clean(teacher?.full_name) || clean(teacher?.teacher_id) || "T";
    return source.charAt(0).toUpperCase();
  }

  function renderTeacherList() {
    const container = $("taTeacherList"); if (!container) return;
    const query = clean($("taTeacherSearch")?.value).toLowerCase(); const filter = $("taTeacherStatusFilter")?.value || "all";
    const filtered = state.teachers.filter(teacher => {
      const haystack = `${teacher.teacher_id || ""} ${teacher.full_name || ""}`.toLowerCase(); if (query && !haystack.includes(query)) return false;
      const status = clean(teacher.status || "active").toLowerCase(); const assigned = Number(teacher.assignment_count || 0) > 0;
      if (filter === "active" && status !== "active") return false; if (filter === "inactive" && status !== "inactive") return false;
      if (filter === "assigned" && !assigned) return false; if (filter === "unassigned" && assigned) return false; return true;
    });
    if ($("taTeacherCountBadge")) $("taTeacherCountBadge").textContent = filtered.length;
    if (!filtered.length) { container.innerHTML = '<div class="teacher-empty-state"><i class="fa-solid fa-user-slash"></i><p>No teachers match this filter.</p></div>'; return; }

    container.innerHTML = filtered.map(teacher => {
      const active = teacher.teacher_id === state.selectedTeacherId; const status = clean(teacher.status || "active").toLowerCase(); const name = clean(teacher.full_name) || "Name not added";
      return `<button type="button" class="teacher-directory-item ${active ? "selected" : ""}" data-teacher-id="${escapeHTML(teacher.teacher_id)}">
        <span class="teacher-avatar small">${escapeHTML(teacherInitial(teacher))}</span>
        <span class="teacher-directory-copy"><strong>${escapeHTML(name)}</strong><small>${escapeHTML(teacher.teacher_id)} · ${Number(teacher.assignment_count || 0)} assignment${Number(teacher.assignment_count || 0) === 1 ? "" : "s"}</small></span>
        <span class="teacher-mini-status ${status}">${escapeHTML(status)}</span>
      </button>`;
    }).join("");

    container.querySelectorAll("[data-teacher-id]").forEach(button => button.addEventListener("click", () => selectTeacher(button.dataset.teacherId)));
  }

  function populateSectionSelect() {
    const select = $("taSectionSelect"); if (!select) return;
    select.innerHTML = '<option value="">Select section</option>' + (state.config?.sections || []).map(section => `<option value="${escapeHTML(section.key)}">${escapeHTML(section.label)}</option>`).join("");
  }

  function populateClassSelect() {
    const sectionKey = $("taSectionSelect")?.value || ""; const select = $("taClassSelect"); if (!select) return;
    const section = (state.config?.sections || []).find(item => item.key === sectionKey); const classes = section?.classes || [];
    select.disabled = !classes.length; select.innerHTML = '<option value="">Select class</option>' + classes.map(item => `<option value="${escapeHTML(item.key)}">${escapeHTML(item.label)}</option>`).join("");
    populateArmAndSubject();
  }

  function populateArmAndSubject() {
    const level = $("taClassSelect")?.value || ""; const meta = classMeta(level); const armSelect = $("taArmSelect"); const subjectSelect = $("taSubjectSelect"); const hint = $("taArmHint");
    if (armSelect) {
      const arms = meta?.arms || []; armSelect.disabled = !meta; armSelect.innerHTML = '<option value="">All applicable arms</option>' + arms.map(arm => `<option value="${escapeHTML(arm)}">${escapeHTML(arm.replaceAll("_", " "))}</option>`).join("");
      if (hint) hint.textContent = !meta ? "Choose a class first." : arms.length ? "Leave as All applicable arms to assign across compatible arms." : "This class currently has no separate arm configuration.";
    }
    populateSubjectSelect();
  }

  function populateSubjectSelect() {
    const level = $("taClassSelect")?.value || ""; const arm = $("taArmSelect")?.value || ""; const meta = classMeta(level); const select = $("taSubjectSelect"); if (!select) return;
    const subjects = (meta?.subjects || []).filter(subject => subjectCompatible(subject, arm));
    select.disabled = !meta || !subjects.length; select.innerHTML = `<option value="">${meta && !subjects.length ? "No active subjects available" : "Select subject"}</option>` + subjects.map(subject => `<option value="${escapeHTML(subject.key)}">${escapeHTML(subject.name)}</option>`).join("");
    updateAddButton();
  }

  function updateAddButton() {
    const button = $("taAddAssignment"); if (!button) return;
    button.disabled = !state.selectedTeacherId || !$("taClassSelect")?.value || !$("taSubjectSelect")?.value;
  }

  function addDraftAssignment() {
    const level = $("taClassSelect")?.value || ""; const arm = $("taArmSelect")?.value || ""; const subjectKey = $("taSubjectSelect")?.value || ""; const meta = classMeta(level); const subject = subjectMeta(level, subjectKey);
    if (!level || !subjectKey || !meta || !subject) return;
    const row = { school_section: meta.section_key, class_level: level, class_arm: arm, subject_key: subject.key, section_label: meta.section_label, class_label: meta.label, subject_name: subject.name };
    if (state.draftAssignments.some(item => assignmentKey(item) === assignmentKey(row))) { notify("That class and subject assignment has already been added.", "info"); return; }
    state.draftAssignments.push(row); renderAssignmentList(); setDirty();
  }

  function removeDraftAssignment(key) {
    state.draftAssignments = state.draftAssignments.filter(row => assignmentKey(row) !== key); renderAssignmentList(); setDirty();
  }

  function renderAssignmentList() {
    const container = $("taAssignmentList"); if (!container) return;
    if ($("taDraftCount")) $("taDraftCount").textContent = state.draftAssignments.length;
    if (!state.draftAssignments.length) { container.innerHTML = '<div class="teacher-empty-state compact"><i class="fa-solid fa-book-open"></i><p>No teaching assignments for this session yet.</p><small>Use the builder above to add the first class and subject.</small></div>'; return; }
    const sorted = [...state.draftAssignments].sort((a, b) => `${a.school_section}|${a.class_level}|${a.class_arm}|${a.subject_key}`.localeCompare(`${b.school_section}|${b.class_level}|${b.class_arm}|${b.subject_key}`));
    container.innerHTML = sorted.map(row => { const display = assignmentDisplay(row); return `<div class="teacher-assignment-row">
      <span class="teacher-assignment-subject-icon"><i class="fa-solid fa-book"></i></span>
      <span class="teacher-assignment-main"><strong>${escapeHTML(display.subjectName)}</strong><small>${escapeHTML(display.section)}</small></span>
      <span class="teacher-assignment-class"><strong>${escapeHTML(display.classLabel)}</strong><small>${escapeHTML(display.armLabel)}</small></span>
      <button type="button" class="teacher-remove-assignment" data-assignment-key="${escapeHTML(assignmentKey(row))}" title="Remove assignment"><i class="fa-solid fa-xmark"></i></button>
    </div>`; }).join("");
    container.querySelectorAll("[data-assignment-key]").forEach(button => button.addEventListener("click", () => removeDraftAssignment(button.dataset.assignmentKey)));
  }

  function renderSelectedTeacher(teacher) {
    $("taEmptyEditor")?.classList.add("hidden"); $("taEditor")?.classList.remove("hidden"); const name = clean(teacher.full_name) || teacher.teacher_id; const status = clean(teacher.status || "active").toLowerCase();
    if ($("taTeacherAvatar")) $("taTeacherAvatar").textContent = teacherInitial(teacher); if ($("taTeacherTitle")) $("taTeacherTitle").textContent = name; if ($("taTeacherIdText")) $("taTeacherIdText").textContent = teacher.teacher_id;
    if ($("taFullName")) $("taFullName").value = clean(teacher.full_name); if ($("taTeacherStatus")) $("taTeacherStatus").value = status;
    const pill = $("taTeacherStatusPill"); if (pill) { pill.className = `teacher-status-pill ${status}`; pill.textContent = status.charAt(0).toUpperCase() + status.slice(1); }
  }

  async function selectTeacher(teacherId) {
    if (!teacherId || state.loading) return;
    if (draftSignature(state.draftAssignments) !== state.savedSignature && state.selectedTeacherId && !window.confirm("You have unsaved assignment changes. Discard them and open another teacher?")) return;
    state.loading = true; state.selectedTeacherId = teacherId; renderTeacherList();
    try {
      const sessionValue = canonicalSession($("taAcademicSession")?.value || state.session); const data = await api(`/api/teacher-assignments/teachers/${encodeURIComponent(teacherId)}?academic_session=${encodeURIComponent(sessionValue)}`);
      state.session = data.academic_session; if ($("taAcademicSession")) $("taAcademicSession").value = data.academic_session; state.draftAssignments = data.assignments || []; state.savedSignature = draftSignature(state.draftAssignments); renderSelectedTeacher(data.teacher); renderAssignmentList(); setDirty();
    } catch (error) { notify(error.message, "error"); }
    finally { state.loading = false; setDirty(); }
  }

  async function reloadTeacherDirectory(keepSelected = true) {
    const sessionValue = canonicalSession($("taAcademicSession")?.value || state.session); const data = await api(`/api/teacher-assignments/teachers?academic_session=${encodeURIComponent(sessionValue)}`);
    state.session = data.academic_session; state.teachers = data.teachers || []; updateAdminStats(data.stats || {}); renderTeacherList();
    if (keepSelected && state.selectedTeacherId && state.teachers.some(item => item.teacher_id === state.selectedTeacherId)) return;
    if (state.teachers.length) await selectTeacher(state.teachers[0].teacher_id);
  }

  async function saveProfile() {
    if (!state.selectedTeacherId) return;
    const button = $("taSaveProfile"); if (button) button.disabled = true;
    try {
      const data = await api(`/api/teacher-assignments/teachers/${encodeURIComponent(state.selectedTeacherId)}`, { method: "PATCH", body: JSON.stringify({ full_name: $("taFullName")?.value || "", status: $("taTeacherStatus")?.value || "active" }) });
      renderSelectedTeacher(data.teacher); await reloadTeacherDirectory(true); notify("Teacher profile updated.", "success");
    } catch (error) { notify(error.message, "error"); }
    finally { if (button) button.disabled = false; }
  }

  async function saveAssignments() {
    if (!state.selectedTeacherId) return;
    const sessionValue = canonicalSession($("taAcademicSession")?.value || state.session); const button = $("taSaveAssignments"); state.loading = true; if (button) button.disabled = true;
    try {
      const payload = { academic_session: sessionValue, assignments: state.draftAssignments.map(row => ({ class_level: row.class_level, class_arm: row.class_arm || "", subject_key: row.subject_key })) };
      const data = await api(`/api/teacher-assignments/teachers/${encodeURIComponent(state.selectedTeacherId)}/assignments`, { method: "PUT", body: JSON.stringify(payload) });
      state.session = data.academic_session; state.draftAssignments = data.assignments || []; state.savedSignature = draftSignature(state.draftAssignments); if ($("taAcademicSession")) $("taAcademicSession").value = data.academic_session; renderAssignmentList(); updateAdminStats(data.stats || {}); await reloadTeacherDirectory(true); notify("Teacher assignments saved successfully.", "success");
    } catch (error) { notify(error.message, "error"); }
    finally { state.loading = false; setDirty(); }
  }

  async function changeSession() {
    const value = canonicalSession($("taAcademicSession")?.value || ""); if (!/^\d{4}\/\d{4}$/.test(value)) { notify("Enter the academic session as YYYY/YYYY, for example 2026/2027.", "error"); return; }
    const [a, b] = value.split("/").map(Number); if (b !== a + 1) { notify("The academic session end year must be exactly one year after the start year.", "error"); return; }
    if (draftSignature(state.draftAssignments) !== state.savedSignature && !window.confirm("Change session and discard unsaved assignment changes?")) { $("taAcademicSession").value = state.session; return; }
    state.session = value; await reloadTeacherDirectory(false);
  }

  async function initAdmin() {
    try {
      const data = await api("/api/teacher-assignments/config"); state.config = data; state.session = data.academic_session; state.teachers = data.teachers || []; if ($("taAcademicSession")) $("taAcademicSession").value = state.session;
      populateSectionSelect(); updateAdminStats(data.stats || {}); renderTeacherList();
      $("taTeacherSearch")?.addEventListener("input", renderTeacherList); $("taTeacherStatusFilter")?.addEventListener("change", renderTeacherList); $("taSectionSelect")?.addEventListener("change", populateClassSelect); $("taClassSelect")?.addEventListener("change", populateArmAndSubject); $("taArmSelect")?.addEventListener("change", populateSubjectSelect); $("taSubjectSelect")?.addEventListener("change", updateAddButton);
      $("taAddAssignment")?.addEventListener("click", addDraftAssignment); $("taSaveProfile")?.addEventListener("click", saveProfile); $("taSaveAssignments")?.addEventListener("click", saveAssignments); $("taAcademicSession")?.addEventListener("change", changeSession);
      if (state.teachers.length) await selectTeacher(state.teachers[0].teacher_id);
    } catch (error) { notify(error.message, "error"); const list = $("taTeacherList"); if (list) list.innerHTML = `<div class="teacher-empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>${escapeHTML(error.message)}</p></div>`; }
  }

  function renderMyAssignments(data) {
    const teacher = data.teacher || {}; if ($("myTeacherName")) $("myTeacherName").textContent = clean(teacher.full_name) || "Your Assignments"; if ($("myTeacherSession")) $("myTeacherSession").textContent = `${data.academic_session || "Current session"} academic session`; if ($("myTeacherId")) $("myTeacherId").textContent = teacher.teacher_id || $("myTeacherId").textContent;
    if ($("myAssignmentCount")) $("myAssignmentCount").textContent = data.assignment_count ?? 0; if ($("myClassCount")) $("myClassCount").textContent = data.class_count ?? 0; if ($("mySubjectCount")) $("mySubjectCount").textContent = data.subject_count ?? 0;
    const container = $("myAssignmentList"); if (!container) return; const rows = data.assignments || [];
    if (!rows.length) { container.innerHTML = '<div class="teacher-empty-state compact"><i class="fa-solid fa-circle-info"></i><p>No teaching assignments have been assigned to your account for this academic session yet.</p><small>Please contact the Admin if you believe an assignment is missing.</small></div>'; return; }
    container.innerHTML = rows.map(row => { const display = assignmentDisplay(row); return `<article class="teacher-self-assignment"><span class="teacher-assignment-subject-icon"><i class="fa-solid fa-book-open"></i></span><div><small>${escapeHTML(display.section)}</small><strong>${escapeHTML(display.subjectName)}</strong><span>${escapeHTML(display.classLabel)} · ${escapeHTML(display.armLabel)}</span></div></article>`; }).join("");
  }

  async function initTeacher() {
    try { const data = await api("/api/teacher-assignments/config"); state.config = data; state.session = data.academic_session; renderMyAssignments({ ...data, assignment_count: (data.assignments || []).length, class_count: new Set((data.assignments || []).map(row => `${row.class_level}|${row.class_arm}`)).size, subject_count: new Set((data.assignments || []).map(row => row.subject_key)).size }); }
    catch (error) { notify(error.message, "error"); }
  }

  document.addEventListener("DOMContentLoaded", () => {});
  if (role === "admin") initAdmin(); else if (role === "teacher") initTeacher();
})();

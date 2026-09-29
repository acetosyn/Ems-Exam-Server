/* ======================================================================
   subjects.js — EMIS Phase 2 Dynamic Subject Manager
   ====================================================================== */

(() => {
    "use strict";

    const $ = id => document.getElementById(id);
    const state = { config: null, subjects: [], filtered: [], editingId: "", loading: false };
    const clean = value => String(value ?? "").trim();
    const escapeHtml = value => clean(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);

    async function api(url, options = {}) {
        const response = await fetch(url, { cache: "no-store", credentials: "same-origin", headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) }, ...options });
        let data = {}; try { data = await response.json(); } catch (_) { data = {}; }
        if (!response.ok || data.success === false) throw new Error(data.error || data.message || `Request failed (${response.status})`);
        return data;
    }

    function formatDateTime(value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? clean(value) || "—" : date.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    function setText(id, value) { const node = $(id); if (node) node.textContent = value ?? ""; }

    function showToast(message, type = "info", timeout = 3800) {
        const host = $("subjectToastHost"); if (!host) return;
        const icon = type === "success" ? "fa-circle-check" : type === "error" ? "fa-circle-exclamation" : "fa-circle-info";
        const toast = document.createElement("div"); toast.className = `subject-toast ${type}`; toast.innerHTML = `<i class="fa-solid ${icon}"></i><span>${escapeHtml(message)}</span>`; host.appendChild(toast);
        window.setTimeout(() => toast.remove(), timeout);
    }

    function renderStats(stats = {}) {
        setText("statTotalSubjects", stats.total_subjects ?? "—"); setText("statActiveSubjects", stats.active_subjects ?? "—"); setText("statInactiveSubjects", `${stats.inactive_subjects ?? 0} inactive`);
        setText("statAssignments", stats.active_assignments ?? "—"); setText("statSections", stats.school_sections ?? "—"); setText("registryVersion", `v${stats.registry_version ?? 2}`); setText("registryClasses", stats.configured_classes ?? "—");
        setText("registryHeadline", `${stats.active_subjects ?? 0} active subjects across ${stats.configured_classes ?? 0} configured classes`); setText("registryUpdated", stats.updated_at ? `Updated ${formatDateTime(stats.updated_at)}` : "Local academic configuration");
        const badge = $("registryState"); if (badge) badge.textContent = "READY";
    }

    function populateFilters() {
        const sectionFilter = $("sectionFilter"), classFilter = $("classFilter"); if (!state.config || !sectionFilter || !classFilter) return;
        const currentSection = sectionFilter.value, currentClass = classFilter.value;
        sectionFilter.innerHTML = `<option value="">All Sections</option>${state.config.sections.map(section => `<option value="${escapeHtml(section.key)}">${escapeHtml(section.label)}</option>`).join("")}`;
        if ([...sectionFilter.options].some(option => option.value === currentSection)) sectionFilter.value = currentSection;
        const visibleSections = currentSection ? state.config.sections.filter(section => section.key === currentSection) : state.config.sections;
        const classes = visibleSections.flatMap(section => section.classes.map(item => ({ ...item, sectionLabel: section.label })));
        classFilter.innerHTML = `<option value="">All Classes</option>${classes.map(item => `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)}${item.database_status === "pending" ? " • Pending DB" : ""}</option>`).join("")}`;
        if ([...classFilter.options].some(option => option.value === currentClass)) classFilter.value = currentClass; else classFilter.value = "";
    }

    function buildAssignmentGroups() {
        const host = $("classAssignmentGroups"); if (!host || !state.config) return;
        host.innerHTML = state.config.sections.map(section => {
            const classes = section.classes.map(item => {
                const tracks = item.supports_tracks ? `<div class="track-options" data-track-group="${escapeHtml(item.key)}">${state.config.tracks.map(track => `<label class="track-option"><input type="checkbox" class="track-checkbox" data-class="${escapeHtml(item.key)}" value="${escapeHtml(track.key)}" checked><span>${escapeHtml(track.label)}</span></label>`).join("")}</div>` : "";
                return `<div class="assignment-class-row"><div class="assignment-class-main"><input type="checkbox" class="assignment-checkbox class-assignment-checkbox" data-class="${escapeHtml(item.key)}"><span class="assignment-class-label">${escapeHtml(item.label)}</span><span class="db-chip ${escapeHtml(item.database_status)}">${item.database_status === "active" ? "DB Active" : "DB Pending"}</span></div>${tracks}</div>`;
            }).join("");
            return `<section class="assignment-section" data-section="${escapeHtml(section.key)}"><div class="assignment-section-head"><strong>${escapeHtml(section.label)}</strong><span>${section.classes.length} class${section.classes.length === 1 ? "" : "es"}</span></div><div class="assignment-class-list">${classes}</div></section>`;
        }).join("");
        host.querySelectorAll(".class-assignment-checkbox").forEach(box => box.addEventListener("change", () => syncTrackVisibility(box.dataset.class)));
        state.config.sections.flatMap(section => section.classes).filter(item => item.supports_tracks).forEach(item => syncTrackVisibility(item.key));
    }

    function syncTrackVisibility(classKey) {
        const classBox = document.querySelector(`.class-assignment-checkbox[data-class="${CSS.escape(classKey)}"]`), group = document.querySelector(`[data-track-group="${CSS.escape(classKey)}"]`); if (!group) return;
        group.style.display = classBox?.checked ? "flex" : "none"; group.querySelectorAll("input").forEach(input => { input.disabled = !classBox?.checked; });
    }

    function resetAssignmentSelections() {
        document.querySelectorAll(".class-assignment-checkbox").forEach(box => { box.checked = false; syncTrackVisibility(box.dataset.class); });
        document.querySelectorAll(".track-checkbox").forEach(box => { box.checked = true; });
    }

    function fillAssignments(assignments = []) {
        resetAssignmentSelections();
        assignments.forEach(item => {
            const classKey = clean(item.class_level), classBox = document.querySelector(`.class-assignment-checkbox[data-class="${CSS.escape(classKey)}"]`); if (!classBox) return;
            classBox.checked = true; syncTrackVisibility(classKey);
            const tracks = Array.isArray(item.tracks) ? item.tracks.map(value => clean(value).toUpperCase()) : [];
            if (classKey.startsWith("SS") && tracks.length) document.querySelectorAll(`.track-checkbox[data-class="${CSS.escape(classKey)}"]`).forEach(box => { box.checked = tracks.includes(clean(box.value).toUpperCase()); });
        });
    }

    function collectAssignments() {
        const assignments = [];
        document.querySelectorAll(".class-assignment-checkbox:checked").forEach(box => {
            const classLevel = clean(box.dataset.class), tracks = classLevel.startsWith("SS") ? [...document.querySelectorAll(`.track-checkbox[data-class="${CSS.escape(classLevel)}"]:checked`)].map(input => clean(input.value)) : [];
            if (classLevel.startsWith("SS") && !tracks.length) throw new Error(`${classLevel} must have at least one stream selected.`);
            assignments.push({ class_level: classLevel, tracks });
        });
        return assignments;
    }

    function subjectSections(subject) {
        const seen = new Set(), output = [];
        (subject.assignments || []).forEach(item => { if (!item.section || seen.has(item.section)) return; seen.add(item.section); output.push(item.section_label || item.section); });
        return output;
    }

    function filterSubjects() {
        const query = clean($("subjectSearch")?.value).toLowerCase(), section = clean($("sectionFilter")?.value), classLevel = clean($("classFilter")?.value), status = clean($("statusFilter")?.value || "all");
        state.filtered = state.subjects.filter(subject => {
            if (status === "active" && !subject.active) return false; if (status === "inactive" && subject.active) return false;
            if (section && !(subject.assignments || []).some(item => item.section === section)) return false;
            if (classLevel && !(subject.assignments || []).some(item => item.class_level === classLevel)) return false;
            if (!query) return true;
            const haystack = [subject.name, subject.key, ...(subject.aliases || []), ...(subject.assignments || []).flatMap(item => [item.class_label, item.section_label, item.display_name])].join(" ").toLowerCase();
            return haystack.includes(query);
        });
        renderSubjectTable();
    }

    function renderSubjectTable() {
        const body = $("subjectTableBody"), empty = $("subjectEmptyState"); if (!body) return;
        setText("catalogCount", `${state.filtered.length} subject${state.filtered.length === 1 ? "" : "s"}`);
        if (!state.filtered.length) { body.innerHTML = ""; if (empty) empty.hidden = false; return; }
        if (empty) empty.hidden = true;
        body.innerHTML = state.filtered.map(subject => {
            const assignments = subject.assignments || [], classChips = assignments.slice(0, 4).map(item => `<span class="class-chip" title="${escapeHtml(item.section_label || "")}">${escapeHtml(item.class_label || item.class_level)}</span>`).join("") + (assignments.length > 4 ? `<span class="class-chip more-chip">+${assignments.length - 4}</span>` : "");
            const sections = subjectSections(subject), sectionChips = sections.slice(0, 3).map(label => `<span class="section-chip">${escapeHtml(label)}</span>`).join("") + (sections.length > 3 ? `<span class="section-chip more-chip">+${sections.length - 3}</span>` : "");
            return `<tr data-subject-id="${escapeHtml(subject.id)}"><td class="subject-name-cell"><strong>${escapeHtml(subject.name)}</strong><code>${escapeHtml(subject.key)}</code></td><td><span class="subject-status-badge ${subject.active ? "active" : "inactive"}"><i class="fa-solid fa-circle"></i>${subject.active ? "Active" : "Inactive"}</span></td><td><div class="chip-stack">${classChips || `<span class="class-chip more-chip">Unassigned</span>`}</div></td><td><div class="chip-stack">${sectionChips || `<span class="section-chip more-chip">—</span>`}</div></td><td class="subject-action-col"><button class="subject-edit-btn" type="button" data-edit-subject="${escapeHtml(subject.id)}"><i class="fa-solid fa-pen"></i> Edit</button></td></tr>`;
        }).join("");
        body.querySelectorAll("[data-edit-subject]").forEach(button => button.addEventListener("click", () => editSubject(button.dataset.editSubject)));
        body.querySelectorAll("tr[data-subject-id]").forEach(row => row.addEventListener("dblclick", () => editSubject(row.dataset.subjectId)));
    }

    function resetEditor(subject = null) {
        state.editingId = subject?.id || ""; if ($("editingSubjectId")) $("editingSubjectId").value = state.editingId; if ($("subjectName")) $("subjectName").value = subject?.name || ""; if ($("subjectActive")) $("subjectActive").checked = subject ? !!subject.active : true;
        setText("editorKicker", subject ? "Edit subject" : "New subject"); setText("editorTitle", subject ? `Edit ${subject.name}` : "Subject Editor");
        const identity = $("subjectIdentityBox"); if (identity) identity.hidden = !subject; setText("subjectStableKey", subject?.key || "—"); fillAssignments(subject?.assignments || []);
        const saveButton = $("saveSubjectBtn"); if (saveButton) saveButton.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> ${subject ? "Save Changes" : "Save Subject"}`;
    }

    function editSubject(subjectId) {
        const subject = state.subjects.find(item => item.id === subjectId); if (!subject) return;
        resetEditor(subject); $("subjectEditorPanel")?.scrollIntoView({ behavior: "smooth", block: "start" }); window.setTimeout(() => $("subjectName")?.focus(), 250);
    }

    function setEditorLoading(loading) {
        state.loading = loading; const button = $("saveSubjectBtn"); if (!button) return; button.disabled = loading;
        if (loading) button.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Saving…`;
        else { const editing = !!state.editingId; button.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> ${editing ? "Save Changes" : "Save Subject"}`; }
    }

    async function saveSubject(event) {
        event.preventDefault(); if (state.loading) return;
        const name = clean($("subjectName")?.value); if (!name) return showToast("Enter a subject name.", "error");
        let assignments = []; try { assignments = collectAssignments(); } catch (error) { return showToast(error.message, "error"); }
        const payload = { name, active: !!$("subjectActive")?.checked, assignments };
        setEditorLoading(true);
        try {
            const editingId = state.editingId, data = await api(editingId ? `/api/subject-manager/subjects/${encodeURIComponent(editingId)}` : "/api/subject-manager/subjects", { method: editingId ? "PUT" : "POST", body: JSON.stringify(payload) });
            showToast(data.message || (editingId ? "Subject updated." : "Subject created."), "success"); await loadRegistry({ preserveEditorId: data.subject?.id || editingId });
        } catch (error) { console.error("SUBJECT SAVE ERROR:", error); showToast(error.message || "Unable to save subject.", "error", 5200); }
        finally { setEditorLoading(false); }
    }

    function selectAllClasses(selected) {
        document.querySelectorAll(".class-assignment-checkbox").forEach(box => { box.checked = selected; syncTrackVisibility(box.dataset.class); });
        if (selected) document.querySelectorAll(".track-checkbox").forEach(box => { box.checked = true; });
    }

    async function loadRegistry({ preserveEditorId = "" } = {}) {
        const refreshButton = $("refreshSubjectsBtn"); if (refreshButton) refreshButton.classList.add("is-loading");
        try {
            const data = await api("/api/subject-manager/config"); state.config = { sections: data.sections || [], tracks: data.tracks || [] }; state.subjects = data.subjects || [];
            renderStats(data.stats || {}); populateFilters(); buildAssignmentGroups(); filterSubjects();
            const wantedId = preserveEditorId || state.editingId, selected = wantedId ? state.subjects.find(item => item.id === wantedId) : null; resetEditor(selected || null);
        } catch (error) {
            console.error("SUBJECT REGISTRY LOAD ERROR:", error); showToast(error.message || "Could not load the subject registry.", "error", 5200); if ($("registryState")) $("registryState").textContent = "ERROR";
            const body = $("subjectTableBody"); if (body) body.innerHTML = `<tr><td colspan="5" class="subject-loading-cell"><i class="fa-solid fa-triangle-exclamation"></i> Subject registry could not be loaded.</td></tr>`;
        } finally { if (refreshButton) refreshButton.classList.remove("is-loading"); }
    }

    function bindEvents() {
        $("subjectEditorForm")?.addEventListener("submit", saveSubject); $("newSubjectBtn")?.addEventListener("click", () => { resetEditor(null); $("subjectEditorPanel")?.scrollIntoView({ behavior: "smooth", block: "start" }); window.setTimeout(() => $("subjectName")?.focus(), 220); });
        $("clearEditorBtn")?.addEventListener("click", () => resetEditor(null)); $("cancelEditBtn")?.addEventListener("click", () => resetEditor(null)); $("selectAllClassesBtn")?.addEventListener("click", () => selectAllClasses(true)); $("clearAllClassesBtn")?.addEventListener("click", () => selectAllClasses(false));
        $("subjectSearch")?.addEventListener("input", filterSubjects); $("statusFilter")?.addEventListener("change", filterSubjects); $("classFilter")?.addEventListener("change", filterSubjects);
        $("sectionFilter")?.addEventListener("change", () => { populateFilters(); filterSubjects(); }); $("refreshSubjectsBtn")?.addEventListener("click", () => loadRegistry({ preserveEditorId: state.editingId }));
    }

    async function init() { bindEvents(); await loadRegistry(); }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true }); else init();
})();

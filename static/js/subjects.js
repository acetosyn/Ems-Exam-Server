/* ======================================================================
   subjects.js — EMIS Phase 2 Dynamic Subject Manager
   ====================================================================== */

(() => {
    "use strict";

    const $ = id => document.getElementById(id);
    const state = { config: null, subjects: [], filtered: [], editingId: "", loading: false, viewMode: localStorage.getItem("emisSubjectView") === "table" ? "table" : "grid", classSubjectGroups: [], classViewerKey: "" };
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

    function openEditorDrawer() { const panel=$("subjectEditorPanel"), overlay=$("subjectEditorOverlay"); if (!panel) return; if (overlay) { overlay.hidden=false; requestAnimationFrame(()=>overlay.classList.add("open")); } panel.classList.add("is-open"); panel.setAttribute("aria-hidden","false"); document.body.classList.add("subject-editor-open"); }
    function closeEditorDrawer() { const panel=$("subjectEditorPanel"), overlay=$("subjectEditorOverlay"); panel?.classList.remove("is-open"); panel?.setAttribute("aria-hidden","true"); overlay?.classList.remove("open"); document.body.classList.remove("subject-editor-open"); if (overlay) window.setTimeout(()=>{ if(!overlay.classList.contains("open")) overlay.hidden=true; },210); }

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


    function classSubjectGroups() {
        if (!state.config) return [];
        const groups = [];
        const activeSubjects = state.subjects.filter(subject => subject.active !== false);
        const classSubjects = (classKey, track = "") => activeSubjects.flatMap(subject => {
            const assignment = (subject.assignments || []).find(item => item.class_level === classKey); if (!assignment) return [];
            const tracks = (assignment.tracks || []).map(value => clean(value).toUpperCase());
            if (track === "SCIENCE" && !tracks.includes("SCIENCE")) return [];
            if (track === "ART_COMMERCIAL" && !tracks.some(value => value === "ART" || value === "COMMERCIAL")) return [];
            return [{ id: subject.id, key: subject.key, name: assignment.display_name || subject.name, catalogName: subject.name }];
        }).sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));

        state.config.sections.forEach(section => (section.classes || []).forEach(item => {
            const classKey = clean(item.key), classLabel = clean(item.label || item.key), sectionLabel = clean(section.label || section.key);
            if (item.supports_tracks) {
                const scienceArm = classKey === "SS3" ? "GOLD / SILVER" : "GOLD / SILVER / DIAMOND";
                const scienceSubjects = classSubjects(classKey, "SCIENCE"), artSubjects = classSubjects(classKey, "ART_COMMERCIAL");
                if (scienceSubjects.length) groups.push({ key: `${classKey}::SCIENCE`, classKey, classLabel: `${classLabel} • Science`, shortLabel: `${classLabel} Science`, sectionKey: section.key, sectionLabel, stream: "Science", armLabel: scienceArm, subjects: scienceSubjects });
                if (artSubjects.length) groups.push({ key: `${classKey}::ART_COMMERCIAL`, classKey, classLabel: `${classLabel} • Art + Commercial`, shortLabel: `${classLabel} B/C`, sectionKey: section.key, sectionLabel, stream: "Art + Commercial", armLabel: "B / C", subjects: artSubjects });
            } else {
                const subjects = classSubjects(classKey); if (!subjects.length) return;
                const armLabel = /^JSS[123]$/.test(classKey) ? "A / B / C" : "";
                groups.push({ key: classKey, classKey, classLabel, shortLabel: classLabel, sectionKey: section.key, sectionLabel, stream: "", armLabel, subjects });
            }
        }));
        return groups;
    }

    function renderClassSubjectViewerClassList(query = "") {
        const host = $("classSubjectViewerClassList"); if (!host) return;
        const needle = clean(query).toLowerCase(), groups = state.classSubjectGroups.filter(group => !needle || [group.classLabel, group.sectionLabel, group.stream, group.armLabel, ...group.subjects.map(subject => subject.name)].join(" ").toLowerCase().includes(needle));
        setText("classSubjectViewerCount", `${groups.length} class view${groups.length === 1 ? "" : "s"}`);
        if (!groups.length) { host.innerHTML = `<div class="class-subject-classlist-empty"><i class="fa-solid fa-magnifying-glass"></i><strong>No matching class</strong><span>Try a class, section or subject name.</span></div>`; return; }
        const bySection = groups.reduce((map, group) => { (map[group.sectionLabel] ||= []).push(group); return map; }, {});
        host.innerHTML = Object.entries(bySection).map(([sectionLabel, items]) => `<section class="class-subject-section-group"><h4>${escapeHtml(sectionLabel)}</h4>${items.map(group => `<button type="button" class="class-subject-class-btn ${group.key === state.classViewerKey ? "active" : ""}" data-class-subject-key="${escapeHtml(group.key)}"><span><strong>${escapeHtml(group.shortLabel)}</strong><small>${escapeHtml(group.armLabel || group.stream || "Class subject list")}</small></span><b>${group.subjects.length}</b></button>`).join("")}</section>`).join("");
        host.querySelectorAll("[data-class-subject-key]").forEach(button => button.addEventListener("click", () => selectClassSubjectGroup(button.dataset.classSubjectKey)));
    }

    function selectClassSubjectGroup(groupKey) {
        const group = state.classSubjectGroups.find(item => item.key === groupKey); if (!group) return;
        state.classViewerKey = group.key; renderClassSubjectViewerClassList($("classSubjectViewerSearch")?.value || "");
        setText("classSubjectViewerSection", group.sectionLabel); setText("classSubjectViewerClassName", group.classLabel); setText("classSubjectViewerSubjectCount", `${group.subjects.length} subject${group.subjects.length === 1 ? "" : "s"}`);
        const details = [group.armLabel ? `Class arms: ${group.armLabel}` : "", group.stream ? `${group.stream} offering` : "Complete active class offering", "Synced across EMIS"].filter(Boolean).join(" • "); setText("classSubjectViewerMeta", details);
        const list = $("classSubjectViewerList"); if (list) list.innerHTML = group.subjects.length ? group.subjects.map((subject, index) => `<article class="class-subject-item"><span class="class-subject-number">${index + 1}</span><div><strong>${escapeHtml(subject.name)}</strong>${subject.catalogName && subject.catalogName !== subject.name ? `<small>Catalogue: ${escapeHtml(subject.catalogName)}</small>` : `<small>${escapeHtml(subject.key)}</small>`}</div><span class="class-subject-live"><i class="fa-solid fa-circle-check"></i> Live</span></article>`).join("") : `<div class="class-subject-empty"><i class="fa-solid fa-book-open-reader"></i><strong>No active subjects</strong><span>This class currently has no active subject assignments.</span></div>`;
        const index = state.classSubjectGroups.findIndex(item => item.key === group.key), prev = $("classSubjectViewerPrev"), next = $("classSubjectViewerNext"); if (prev) prev.disabled = index <= 0; if (next) next.disabled = index < 0 || index >= state.classSubjectGroups.length - 1;
    }

    function openClassSubjectViewer() {
        state.classSubjectGroups = classSubjectGroups(); if (!state.classSubjectGroups.length) return showToast("No active class subject offerings are available yet.", "info");
        const selectedClass = clean($("classFilter")?.value), selectedMatch = selectedClass ? state.classSubjectGroups.find(group => group.classKey === selectedClass) : null;
        state.classViewerKey = selectedMatch?.key || state.classViewerKey || state.classSubjectGroups[0].key;
        const overlay = $("classSubjectViewerOverlay"), modal = $("classSubjectViewerModal"); if (!modal) return;
        if (overlay) { overlay.hidden = false; requestAnimationFrame(() => overlay.classList.add("open")); } modal.classList.add("open"); modal.setAttribute("aria-hidden", "false"); document.body.classList.add("class-subject-viewer-open");
        if ($("classSubjectViewerSearch")) $("classSubjectViewerSearch").value = ""; renderClassSubjectViewerClassList(); selectClassSubjectGroup(state.classViewerKey); window.setTimeout(() => $("classSubjectViewerSearch")?.focus(), 120);
    }

    function closeClassSubjectViewer() {
        const overlay = $("classSubjectViewerOverlay"), modal = $("classSubjectViewerModal"); modal?.classList.remove("open"); modal?.setAttribute("aria-hidden", "true"); overlay?.classList.remove("open"); document.body.classList.remove("class-subject-viewer-open"); if (overlay) window.setTimeout(() => { if (!overlay.classList.contains("open")) overlay.hidden = true; }, 180);
    }

    function moveClassSubjectViewer(step) {
        const index = state.classSubjectGroups.findIndex(item => item.key === state.classViewerKey), nextIndex = Math.max(0, Math.min(state.classSubjectGroups.length - 1, index + step)); if (nextIndex !== index) selectClassSubjectGroup(state.classSubjectGroups[nextIndex].key);
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

    function subjectAccent(subject) {
        const labels = subjectSections(subject).join(" ").toLowerCase();
        if (labels.includes("islamiyah")) return "islamiyah"; if (labels.includes("tahfeez")) return "tahfeez"; if (labels.includes("senior")) return "senior"; if (labels.includes("junior")) return "junior"; if (labels.includes("primary")) return "primary"; if (labels.includes("early")) return "early"; return "general";
    }

    function bindSubjectActions(host) {
        if (!host) return;
        host.querySelectorAll("[data-edit-subject]").forEach(button => button.addEventListener("click", () => editSubject(button.dataset.editSubject)));
        host.querySelectorAll("[data-archive-subject]").forEach(button => button.addEventListener("click", () => archiveSubject(button.dataset.archiveSubject)));
        host.querySelectorAll("[data-subject-id]").forEach(node => node.addEventListener("dblclick", event => { if (!event.target.closest("button")) editSubject(node.dataset.subjectId); }));
    }

    function renderSubjectTable() {
        const body = $("subjectTableBody"), grid = $("subjectCatalogGrid"), empty = $("subjectEmptyState"); if (!body || !grid) return;
        setText("catalogCount", `${state.filtered.length} subject${state.filtered.length === 1 ? "" : "s"}`);
        if (!state.filtered.length) { body.innerHTML = ""; grid.innerHTML = ""; if (empty) empty.hidden = false; applySubjectView(); return; }
        if (empty) empty.hidden = true;
        const selectedClass = clean($("classFilter")?.value);
        const compactData = state.filtered.map(subject => {
            const assignments = subject.assignments || [], selectedAssignment = selectedClass ? assignments.find(item => item.class_level === selectedClass) : null, displayName = selectedAssignment?.display_name || subject.name, sections = subjectSections(subject), classChips = assignments.slice(0, 5).map(item => `<span class="class-chip" title="${escapeHtml(item.section_label || "")}">${escapeHtml(item.class_label || item.class_level)}</span>`).join("") + (assignments.length > 5 ? `<span class="class-chip more-chip">+${assignments.length - 5}</span>` : ""), sectionChips = sections.slice(0, 3).map(label => `<span class="section-chip">${escapeHtml(label)}</span>`).join("") + (sections.length > 3 ? `<span class="section-chip more-chip">+${sections.length - 3}</span>` : "");
            return { subject, displayName, assignments, sections, classChips, sectionChips, accent: subjectAccent(subject) };
        });
        body.innerHTML = compactData.map(({subject,displayName,classChips,sectionChips}) => `<tr data-subject-id="${escapeHtml(subject.id)}"><td class="subject-name-cell"><strong>${escapeHtml(displayName)}</strong><code>${escapeHtml(subject.key)}</code></td><td><span class="subject-status-badge ${subject.active ? "active" : "inactive"}"><i class="fa-solid fa-circle"></i>${subject.active ? "Active" : "Archived"}</span></td><td><div class="chip-stack">${classChips || `<span class="class-chip more-chip">Unassigned</span>`}</div></td><td><div class="chip-stack">${sectionChips || `<span class="section-chip more-chip">—</span>`}</div></td><td class="subject-action-col"><div class="subject-row-actions"><button class="subject-edit-btn" type="button" data-edit-subject="${escapeHtml(subject.id)}"><i class="fa-solid fa-pen"></i> Edit</button>${subject.active ? `<button class="subject-archive-btn" type="button" data-archive-subject="${escapeHtml(subject.id)}" title="Archive subject"><i class="fa-solid fa-box-archive"></i> Delete</button>` : ""}</div></td></tr>`).join("");
        grid.innerHTML = compactData.map(({subject,displayName,assignments,sections,classChips,sectionChips,accent}) => `<article class="subject-catalog-card accent-${accent} ${subject.active ? "is-active" : "is-archived"}" data-subject-id="${escapeHtml(subject.id)}"><header class="subject-card-head"><span class="subject-card-icon"><i class="fa-solid fa-book-open"></i></span><div class="subject-card-title"><strong>${escapeHtml(displayName)}</strong><code>${escapeHtml(subject.key)}</code></div><span class="subject-status-badge ${subject.active ? "active" : "inactive"}"><i class="fa-solid fa-circle"></i>${subject.active ? "Active" : "Archived"}</span></header><div class="subject-card-metrics"><span><small>Classes</small><b>${assignments.length}</b></span><span><small>Sections</small><b>${sections.length}</b></span><span><small>Coverage</small><b>${assignments.length ? "Live" : "None"}</b></span></div><div class="subject-card-block"><div class="subject-card-label"><span>Class Coverage</span><em>${assignments.length ? `${assignments.length} assigned` : "Not assigned"}</em></div><div class="chip-stack">${classChips || `<span class="class-chip more-chip">Unassigned</span>`}</div></div><div class="subject-card-block section-block"><div class="subject-card-label"><span>School Sections</span><em>${sections.length || 0}</em></div><div class="chip-stack">${sectionChips || `<span class="section-chip more-chip">No section</span>`}</div></div><footer class="subject-card-footer"><span class="subject-sync-ready"><i class="fa-solid fa-arrows-rotate"></i>${assignments.length ? "Synced across EMIS" : "Awaiting class assignment"}</span><div class="subject-row-actions"><button class="subject-edit-btn" type="button" data-edit-subject="${escapeHtml(subject.id)}"><i class="fa-solid fa-pen"></i> Edit</button>${subject.active ? `<button class="subject-archive-btn" type="button" data-archive-subject="${escapeHtml(subject.id)}"><i class="fa-solid fa-box-archive"></i> Delete</button>` : ""}</div></footer></article>`).join("");
        bindSubjectActions(body); bindSubjectActions(grid); applySubjectView();
    }

    function setSubjectView(mode) { state.viewMode = mode === "table" ? "table" : "grid"; localStorage.setItem("emisSubjectView", state.viewMode); applySubjectView(); }
    function applySubjectView() {
        const grid=$("subjectCatalogGrid"), table=$("subjectTableView"), gridBtn=$("subjectGridViewBtn"), tableBtn=$("subjectTableViewBtn"); if (!grid || !table) return;
        const isTable=state.viewMode === "table"; grid.hidden=isTable; table.hidden=!isTable; gridBtn?.classList.toggle("active",!isTable); tableBtn?.classList.toggle("active",isTable); gridBtn?.setAttribute("aria-pressed",String(!isTable)); tableBtn?.setAttribute("aria-pressed",String(isTable));
    }

    function resetEditor(subject = null) {
        state.editingId = subject?.id || ""; if ($("editingSubjectId")) $("editingSubjectId").value = state.editingId; if ($("subjectName")) $("subjectName").value = subject?.name || ""; if ($("subjectActive")) $("subjectActive").checked = subject ? !!subject.active : true;
        setText("editorKicker", subject ? "Edit subject" : "New subject"); setText("editorTitle", subject ? `Edit ${subject.name}` : "Subject Editor");
        const identity = $("subjectIdentityBox"); if (identity) identity.hidden = !subject; setText("subjectStableKey", subject?.key || "—"); fillAssignments(subject?.assignments || []);
        const saveButton = $("saveSubjectBtn"); if (saveButton) saveButton.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> ${subject ? "Save Changes" : "Save Subject"}`; const archiveButton=$("archiveSubjectBtn"); if (archiveButton) archiveButton.hidden=!subject || !subject.active;
    }

    function editSubject(subjectId) {
        const subject = state.subjects.find(item => item.id === subjectId); if (!subject) return;
        resetEditor(subject); openEditorDrawer(); window.setTimeout(() => $("subjectName")?.focus(), 180);
    }

    async function archiveSubject(subjectId = state.editingId) {
        const subject = state.subjects.find(item => item.id === subjectId); if (!subject) return;
        if (!window.confirm(`Delete ${subject.name} from the active subject catalogue?\n\nThis removes it from all current class offerings, uploads/push validation and portal subject lists, but keeps historical results safe.`)) return;
        try { const data = await api(`/api/subject-manager/subjects/${encodeURIComponent(subjectId)}`, { method: "DELETE" }); showToast(data.message || "Subject archived.", "success", 5200); closeEditorDrawer(); state.editingId=""; await loadRegistry(); }
        catch (error) { console.error("SUBJECT ARCHIVE ERROR:", error); showToast(error.message || "Unable to archive subject.", "error", 5200); }
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
        $("subjectEditorForm")?.addEventListener("submit", saveSubject); $("newSubjectBtn")?.addEventListener("click", () => { resetEditor(null); openEditorDrawer(); window.setTimeout(() => $("subjectName")?.focus(), 160); });
        $("clearEditorBtn")?.addEventListener("click", closeEditorDrawer); $("cancelEditBtn")?.addEventListener("click", closeEditorDrawer); $("subjectEditorOverlay")?.addEventListener("click", closeEditorDrawer); $("archiveSubjectBtn")?.addEventListener("click", () => archiveSubject()); document.addEventListener("keydown", event => { if (event.key !== "Escape") return; if ($("classSubjectViewerModal")?.classList.contains("open")) return closeClassSubjectViewer(); if ($("subjectEditorPanel")?.classList.contains("is-open")) closeEditorDrawer(); }); $("selectAllClassesBtn")?.addEventListener("click", () => selectAllClasses(true)); $("clearAllClassesBtn")?.addEventListener("click", () => selectAllClasses(false));
        $("subjectSearch")?.addEventListener("input", filterSubjects); $("statusFilter")?.addEventListener("change", filterSubjects); $("classFilter")?.addEventListener("change", filterSubjects);
        $("sectionFilter")?.addEventListener("change", () => { populateFilters(); filterSubjects(); }); $("refreshSubjectsBtn")?.addEventListener("click", () => loadRegistry({ preserveEditorId: state.editingId })); $("subjectGridViewBtn")?.addEventListener("click", () => setSubjectView("grid")); $("subjectTableViewBtn")?.addEventListener("click", () => setSubjectView("table"));
        $("viewClassSubjectsBtn")?.addEventListener("click", openClassSubjectViewer); $("closeClassSubjectViewerBtn")?.addEventListener("click", closeClassSubjectViewer); $("classSubjectViewerOverlay")?.addEventListener("click", closeClassSubjectViewer); $("classSubjectViewerSearch")?.addEventListener("input", event => renderClassSubjectViewerClassList(event.target.value)); $("classSubjectViewerPrev")?.addEventListener("click", () => moveClassSubjectViewer(-1)); $("classSubjectViewerNext")?.addEventListener("click", () => moveClassSubjectViewer(1));
    }

    async function init() { bindEvents(); await loadRegistry(); }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true }); else init();
})();

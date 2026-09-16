// MODULE: Promotion Manager Frontend — Promotion, repetition, SS3 graduation and graduate archive

document.addEventListener("DOMContentLoaded", () => {

    // =========================================================
    // REQUIRE STUDENT DATABASE MODULE
    // =========================================================
    const DB = window.EMISStudentDB;

    if (!DB) {
        console.error("Promotion Manager: student_database.js must be loaded before promotion.js.");
        return;
    }


    // =========================================================
    // SHARED HELPERS
    // =========================================================
    const $ = (id) => document.getElementById(id);

    const {
        state,
        api,
        CLASS_ARMS,
        selectedStudents,
        clearSelection,
        loadSummary,
        loadStudents,
        loadLogs,
        openStudentDetails,
        openConfirmation,
        forceCloseConfirmation,
        showModal,
        hideModal,
        showToast,
        fullName,
        displayClass,
        normalizeAdmission,
        normalize,
        escapeHtml
    } = DB;


    // =========================================================
    // PROMOTION PATH
    // =========================================================
    const NEXT_CLASS = { JSS1:"JSS2", JSS2:"JSS3", JSS3:"SS1", SS1:"SS2", SS2:"SS3", SS3:"GRADUATED" };
    const PREVIOUS_CLASS = { JSS2:"JSS1", JSS3:"JSS2", SS1:"JSS3", SS2:"SS1", SS3:"SS2" };


    // =========================================================
    // DOM ELEMENTS
    // =========================================================
    const els = {

        // PROMOTION ACTIONS
        promoteSelectedBtn: $("promoteSelectedBtn"), promoteAllClassBtn: $("promoteAllClassBtn"), demoteSelectedBtn: $("demoteSelectedBtn"), repeatSelectedBtn: $("repeatSelectedBtn"),
        roadmap: $("promotionRoadmap"), roadmapHint: $("promotionRoadmapHint"),

        // DESTINATION ARM
        destinationArmOverlay: $("destinationArmOverlay"),
        destinationArmModal: $("destinationArmModal"),
        destinationArmTitle: $("destinationArmTitle"),
        destinationArmDescription: $("destinationArmDescription"),
        destinationArmSelector: $("destinationArmSelector"),
        destinationStudentSummary: $("destinationStudentSummary"),
        destinationScopeBanner: $("destinationScopeBanner"),
        destinationPlacementGroups: $("destinationPlacementGroups"),
        applyDestinationArmBtn: $("applyDestinationArmBtn"),
        resetDestinationPlacementBtn: $("resetDestinationPlacementBtn"),
        cancelDestinationArmBtn: $("cancelDestinationArmBtn"),
        confirmDestinationArmBtn: $("confirmDestinationArmBtn"),
        formClassCategory: $("formClassCategory"), formClass: $("formClass"), studentArmTrackLabel: $("studentArmTrackLabel"),

        // PREVIEW
        previewOverlay: $("previewOverlay"),
        previewModal: $("previewModal"),
        previewModalTitle: $("previewModalTitle"),
        closePreviewBtn: $("closePreviewBtn"),
        cancelPreviewBtn: $("cancelPreviewBtn"),
        previewAction: $("previewAction"),
        previewSourceClass: $("previewSourceClass"),
        previewDestinationClass: $("previewDestinationClass"),
        previewStudentCount: $("previewStudentCount"), previewWarnings: $("previewWarnings"), previewAiGuide: $("previewAiGuide"), previewAiGuideBtn: $("previewAiGuideBtn"),
        previewBody: $("previewBody"), confirmPreviewApplyBtn: $("confirmPreviewApplyBtn"),

        // GRADUATES
        viewGraduatesBtn: $("viewGraduatesBtn"),
        graduatesOverlay: $("graduatesOverlay"),
        graduatesModal: $("graduatesModal"),
        closeGraduatesBtn: $("closeGraduatesBtn"),
        graduateSearch: $("graduateSearch"),
        graduateYearFilter: $("graduateYearFilter"),
        graduatesBody: $("graduatesBody"),
        graduatesCount: $("graduatesCount"),
        graduatesPagination: $("graduatesPagination"),
        clearGraduateArchiveBtn: $("clearGraduateArchiveBtn"),
        graduateClearPanel: $("graduateClearPanel"),
        graduateClearTitle: $("graduateClearTitle"),
        graduateClearMessage: $("graduateClearMessage"),
        graduateClearConfirmInput: $("graduateClearConfirmInput"),
        cancelGraduateClearBtn: $("cancelGraduateClearBtn"),
        confirmGraduateClearBtn: $("confirmGraduateClearBtn")
    };


    // =========================================================
    // LOCAL STATE
    // =========================================================
    const promotionState = {
        destinationContext: null, pendingPreview: null, pendingGuard: null,
        graduates: [],
        graduatePage: 1,
        graduateRowsPerPage: 15,
        graduateClearBusy: false
    };


    // =========================================================
    // INITIALIZE
    // =========================================================
    init();

    function init() { bindEvents(); renderRoadmap(state.summary || {}); updateWholeClassButton(); bindArmLabelEnhancements(); }


    // =========================================================
    // EVENTS
    // =========================================================
    function bindEvents() {

        // PROMOTION / REPETITION
        els.promoteSelectedBtn?.addEventListener("click", startPromotionAction);
        els.promoteAllClassBtn?.addEventListener("click", startWholeClassPromotion);
        els.demoteSelectedBtn?.addEventListener("click", startDemotionAction);
        els.repeatSelectedBtn?.addEventListener("click", startRepeatAction);
        document.addEventListener("emis:summary-loaded", event => renderRoadmap(event.detail?.summary || state.summary || {}));
        document.addEventListener("emis:class-changed", updateWholeClassButton);
        document.addEventListener("emis:selection-changed", updateWholeClassButton);
        $("classArmSelector")?.addEventListener("change", updateWholeClassButton);

        // DESTINATION ARM
        els.cancelDestinationArmBtn?.addEventListener("click", closeDestinationArmModal);
        els.destinationArmOverlay?.addEventListener("click", closeDestinationArmModal);
        els.confirmDestinationArmBtn?.addEventListener("click", confirmDestinationArm);
        els.applyDestinationArmBtn?.addEventListener("click", applyDestinationToAllListed);
        els.resetDestinationPlacementBtn?.addEventListener("click", resetDestinationSmartDefaults);

        // PREVIEW
        els.closePreviewBtn?.addEventListener("click", closePreview);
        els.cancelPreviewBtn?.addEventListener("click", closePreview);
        els.previewOverlay?.addEventListener("click", closePreview);
        els.confirmPreviewApplyBtn?.addEventListener("click", previewContinue);
        els.previewAiGuideBtn?.addEventListener("click", loadAiGuideForPreview);

        // GRADUATES
        els.viewGraduatesBtn?.addEventListener("click", openGraduates);
        els.closeGraduatesBtn?.addEventListener("click", closeGraduates);
        els.graduatesOverlay?.addEventListener("click", closeGraduates);

        els.graduateSearch?.addEventListener("input", () => {
            promotionState.graduatePage = 1;
            renderGraduates();
        });

        els.graduateYearFilter?.addEventListener("change", () => {
            promotionState.graduatePage = 1;
            closeGraduateClearPanel();
            renderGraduates();
        });
        els.clearGraduateArchiveBtn?.addEventListener("click", openGraduateClearPanel);
        els.cancelGraduateClearBtn?.addEventListener("click", closeGraduateClearPanel);
        els.graduateClearConfirmInput?.addEventListener("input", updateGraduateClearConfirmation);
        els.graduateClearConfirmInput?.addEventListener("keydown", event => {
            if (event.key === "Enter" && String(els.graduateClearConfirmInput?.value || "").trim().toUpperCase() === "DELETE") applyGraduateArchiveClear();
        });
        els.confirmGraduateClearBtn?.addEventListener("click", applyGraduateArchiveClear);

        // ESCAPE
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") return;

            closeDestinationArmModal();
            closePreview();
            closeGraduates();
        });
    }


    // =========================================================
    // PROMOTION / WHOLE-CLASS / DEMOTION START
    // =========================================================
    function startPromotionAction() { const students = selectedStudents(); if (!students.length) return showToast("Select at least one student first.", "warning"); beginPromotion(students, "selected"); }

    function startWholeClassPromotion() {
        const armFilter = $("classArmSelector")?.value || "all";
        if (armFilter !== "all") {
            const students = (Array.isArray(state.students) ? state.students : []).filter(student => student.Class === armFilter);
            if (!students.length) return showToast(`No active students are currently in ${displayClass(armFilter)}.`, "warning");
            return beginPromotion([...students], "selected");
        }
        const students = Array.isArray(state.students) ? [...state.students] : [];
        if (!students.length) return showToast(`No active students are currently in ${state.currentClass}.`, "warning");
        beginPromotion(students, "all");
    }

    function beginPromotion(students, mode = "selected") {
        if (state.currentClass === "SS3") return openActionPreview({ type:"graduate", action:"Graduate", source:"SS3", destination:"Graduate Archive", students:[...students], destinationClasses:{}, mode });
        const destination = NEXT_CLASS[state.currentClass];
        if (!destination) return showToast("No promotion destination is configured for this class.", "error");
        openDestinationArmModal([...students], destination, [...students], { type:"promote", action:"Promote", mode });
    }

    function startDemotionAction() {
        const students = selectedStudents(), destination = PREVIOUS_CLASS[state.currentClass];
        if (!students.length) return showToast("Select the student(s) you want to demote first.", "warning");
        if (!destination) return showToast(`${state.currentClass} is the lowest class and cannot be demoted.`, "warning");
        openDestinationArmModal([...students], destination, [...students], { type:"demote", action:"Demote", mode:"selected" });
    }

    function updateWholeClassButton() {
        if (!els.promoteAllClassBtn) return;
        const isSS3 = state.currentClass === "SS3", armFilter = $("classArmSelector")?.value || "all", armScoped = armFilter !== "all";
        if (armScoped) {
            els.promoteAllClassBtn.innerHTML = isSS3 ? `<i class="fa-solid fa-graduation-cap"></i><span>Graduate ${escapeHtml(displayClass(armFilter))} Arm</span>` : `<i class="fa-solid fa-people-arrow-up"></i><span>Promote ${escapeHtml(displayClass(armFilter))} Arm</span>`;
            els.promoteAllClassBtn.title = `Only students in ${displayClass(armFilter)} will be processed. Other ${state.currentClass} arms remain unchanged.`;
        } else {
            els.promoteAllClassBtn.innerHTML = isSS3 ? `<i class="fa-solid fa-graduation-cap"></i><span>Graduate Entire SS3</span>` : `<i class="fa-solid fa-people-arrow-up"></i><span>Promote Entire Class</span>`;
            els.promoteAllClassBtn.title = `Process every active student in ${state.currentClass}.`;
        }
        if (els.demoteSelectedBtn) els.demoteSelectedBtn.disabled = state.currentClass === "JSS1" || !selectedStudents().length;
    }

    // =========================================================
    // FLEXIBLE DESTINATION PLACEMENT
    // =========================================================
    function armStreamMeta(arm) {
        const value = String(arm || "").toUpperCase();
        if (!value) return { key:"", label:"Unassigned", className:"general" };
        if (!value.startsWith("SS")) return { key:"JUNIOR", label:"Junior", className:"junior" };
        if (value.endsWith("_B/C")) return { key:"ART_COMMERCIAL", label:"Arts / Commercial", className:"arts-commercial" };
        if (["_GOLD","_SILVER","_DIAMOND"].some(tag => value.includes(tag))) return { key:"SCIENCE", label:"Science", className:"science" };
        return { key:"GENERAL", label:"General", className:"general" };
    }

    function destinationArmOptions(destination, selected = "", includeBlank = true) {
        const arms = CLASS_ARMS[destination] || [], counts = state.summary?.[destination]?.arms || {};
        const blank = includeBlank ? `<option value="">Choose destination arm</option>` : "";
        return blank + arms.map(arm => { const meta = armStreamMeta(arm), occupied = Number(counts?.[arm] || 0); return `<option value="${escapeHtml(arm)}" ${arm === selected ? "selected" : ""}>${escapeHtml(displayClass(arm))} — ${escapeHtml(meta.label)}${occupied ? ` • ${occupied} current` : ""}</option>`; }).join("");
    }

    function smartPlacementForStudent(student, destination) {
        return automaticDestinationArm(student, destination) || "";
    }

    function openDestinationArmModal(allStudents, destination, affectedStudents, operation = { type:"promote", action:"Promote", mode:"selected" }) {
        const unique = [], seen = new Set();
        (allStudents || []).forEach(student => { const admission = normalizeAdmission(student?.Admission_number); if (admission && !seen.has(admission)) { seen.add(admission); unique.push(student); } });
        if (!unique.length) return showToast("No students are available for placement.", "warning");

        const context = { allStudents:unique, affectedStudents:unique, source:state.currentClass, destination, type:operation.type || "promote", action:operation.action || "Promote", mode:operation.mode || "selected", placements:{} };
        unique.forEach(student => { context.placements[normalizeAdmission(student.Admission_number)] = smartPlacementForStudent(student, destination); });
        promotionState.destinationContext = context;

        if (els.destinationArmTitle) els.destinationArmTitle.textContent = `${context.source} → ${destination}`;
        if (els.destinationArmDescription) els.destinationArmDescription.textContent = contextTextForDestination(context.source, destination, unique.length, context.type);
        if (els.destinationArmSelector) els.destinationArmSelector.innerHTML = destinationArmOptions(destination);
        renderDestinationScope(context); renderPlacementGroups(context); refreshPlacementSummary(context); showModal(els.destinationArmModal, els.destinationArmOverlay);
    }

    function contextTextForDestination(source, destination, count, type) {
        if (type === "demote") return `Choose the exact ${destination} arm for each of the ${count} selected student(s). Stream changes are allowed and will be highlighted before confirmation.`;
        if (source === "JSS3") return `Choose the SS1 arm for the ${count} listed student(s). Only these listed students will move; other JSS3 arms remain untouched.`;
        return `Review the destination arm for each of the ${count} listed student(s). Smart defaults preserve a compatible arm where possible, but you can change any student to another valid arm.`;
    }

    function renderDestinationScope(context) {
        if (!els.destinationScopeBanner) return;
        const groups = groupStudentsBySourceArm(context.allStudents), armText = Object.entries(groups).map(([arm, students]) => `${displayClass(arm)} (${students.length})`).join(", ");
        const whole = context.mode === "all";
        els.destinationScopeBanner.classList.toggle("whole-class", whole);
        els.destinationScopeBanner.innerHTML = `<i class="fa-solid ${whole ? "fa-triangle-exclamation" : "fa-shield-halved"}"></i><div><strong>${whole ? `Entire ${context.source} class scope` : "Selected-student scope locked"}</strong><span>${whole ? `All ${context.allStudents.length} active ${context.source} students are listed. Review every source arm before continuing.` : `Only ${context.allStudents.length} selected student(s) will move: ${escapeHtml(armText)}. Unselected students and arms remain in ${context.source}.`}</span></div>`;
    }

    function groupStudentsBySourceArm(students) {
        return (students || []).reduce((groups, student) => { const arm = student.Class || student.Class_category || "Unknown"; (groups[arm] ||= []).push(student); return groups; }, {});
    }

    function renderPlacementGroups(context) {
        if (!els.destinationPlacementGroups) return;
        const groups = groupStudentsBySourceArm(context.allStudents);
        els.destinationPlacementGroups.innerHTML = Object.entries(groups).map(([sourceArm, students]) => {
            const sourceMeta = armStreamMeta(sourceArm), common = commonPlacement(students, context), sourceLabel = displayClass(sourceArm);
            return `<section class="placement-group" data-source-arm="${escapeHtml(sourceArm)}"><div class="placement-group-head"><div class="placement-group-title"><strong>${escapeHtml(sourceLabel)}</strong><span><span class="stream-chip ${sourceMeta.className}">${escapeHtml(sourceMeta.label)}</span>${students.length} student${students.length === 1 ? "" : "s"}</span></div><select class="placement-group-select" data-placement-group="${escapeHtml(sourceArm)}" aria-label="Destination for ${escapeHtml(sourceLabel)} group">${destinationArmOptions(context.destination, common)}</select><button class="pm-btn pm-btn-secondary placement-group-apply" type="button" data-apply-placement-group="${escapeHtml(sourceArm)}"><i class="fa-solid fa-layer-group"></i><span>Apply to Group</span></button></div><div class="placement-student-list">${students.map(student => placementStudentRow(student, context)).join("")}</div></section>`;
        }).join("");

        els.destinationPlacementGroups.querySelectorAll("[data-apply-placement-group]").forEach(button => button.addEventListener("click", () => applyDestinationToGroup(button.dataset.applyPlacementGroup || "")));
        els.destinationPlacementGroups.querySelectorAll(".placement-student-select").forEach(select => select.addEventListener("change", () => { const admission = normalizeAdmission(select.dataset.admission); if (!admission || !promotionState.destinationContext) return; promotionState.destinationContext.placements[admission] = select.value || ""; refreshPlacementSummary(promotionState.destinationContext); }));
    }

    function placementStudentRow(student, context) {
        const admission = normalizeAdmission(student.Admission_number), sourceArm = student.Class || student.Class_category || "", sourceMeta = armStreamMeta(sourceArm), selected = context.placements[admission] || "";
        return `<div class="placement-student-row" data-placement-row="${escapeHtml(admission)}"><div class="placement-student-copy"><strong>${escapeHtml(fullName(student))}</strong><span>${escapeHtml(student.Admission_number)} • ${escapeHtml(displayClass(sourceArm))}<span class="stream-chip ${sourceMeta.className}">${escapeHtml(sourceMeta.label)}</span></span></div><div class="placement-student-select-wrap"><select class="placement-student-select" data-admission="${escapeHtml(admission)}" aria-label="Destination for ${escapeHtml(fullName(student))}">${destinationArmOptions(context.destination, selected)}</select><div class="placement-change-note" data-placement-note="${escapeHtml(admission)}"></div></div></div>`;
    }

    function commonPlacement(students, context) {
        const values = [...new Set(students.map(student => context.placements[normalizeAdmission(student.Admission_number)] || ""))];
        return values.length === 1 ? values[0] : "";
    }

    function applyDestinationToAllListed() {
        const context = promotionState.destinationContext, arm = els.destinationArmSelector?.value || "";
        if (!context) return; if (!arm) return showToast("Choose a destination arm to apply.", "warning");
        context.allStudents.forEach(student => { context.placements[normalizeAdmission(student.Admission_number)] = arm; });
        renderPlacementGroups(context); refreshPlacementSummary(context);
    }

    function applyDestinationToGroup(sourceArm) {
        const context = promotionState.destinationContext; if (!context) return;
        const group = els.destinationPlacementGroups?.querySelector(`.placement-group[data-source-arm="${cssEscape(sourceArm)}"]`), select = group?.querySelector(".placement-group-select"), arm = select?.value || "";
        if (!arm) return showToast(`Choose a destination for ${displayClass(sourceArm)} first.`, "warning");
        context.allStudents.filter(student => (student.Class || student.Class_category || "") === sourceArm).forEach(student => { context.placements[normalizeAdmission(student.Admission_number)] = arm; });
        renderPlacementGroups(context); refreshPlacementSummary(context);
    }

    function resetDestinationSmartDefaults() {
        const context = promotionState.destinationContext; if (!context) return;
        context.allStudents.forEach(student => { context.placements[normalizeAdmission(student.Admission_number)] = smartPlacementForStudent(student, context.destination); });
        if (els.destinationArmSelector) els.destinationArmSelector.value = "";
        renderPlacementGroups(context); refreshPlacementSummary(context); showToast("Smart placement defaults restored.", "info");
    }

    function refreshPlacementSummary(context) {
        if (!context) return;
        const counts = {}, cross = {}, unassigned = [];
        context.allStudents.forEach(student => {
            const admission = normalizeAdmission(student.Admission_number), destinationArm = context.placements[admission] || "";
            if (!destinationArm) { unassigned.push(student); return; }
            counts[destinationArm] = (counts[destinationArm] || 0) + 1;
            const sourceMeta = armStreamMeta(student.Class), destinationMeta = armStreamMeta(destinationArm);
            if (sourceMeta.key && destinationMeta.key && sourceMeta.key !== "JUNIOR" && destinationMeta.key !== "JUNIOR" && sourceMeta.key !== destinationMeta.key) cross[`${sourceMeta.label} → ${destinationMeta.label}`] = (cross[`${sourceMeta.label} → ${destinationMeta.label}`] || 0) + 1;
            const row = els.destinationPlacementGroups?.querySelector(`[data-placement-row="${cssEscape(admission)}"]`), note = row?.querySelector(`[data-placement-note="${cssEscape(admission)}"]`), isCross = sourceMeta.key && destinationMeta.key && sourceMeta.key !== "JUNIOR" && destinationMeta.key !== "JUNIOR" && sourceMeta.key !== destinationMeta.key;
            row?.classList.toggle("cross-stream", !!isCross); if (note) note.textContent = isCross ? `Track change: ${sourceMeta.label} → ${destinationMeta.label}` : "";
        });
        els.destinationPlacementGroups?.querySelectorAll(".placement-group").forEach(group => { const sourceArm = group.dataset.sourceArm || "", students = context.allStudents.filter(student => (student.Class || student.Class_category || "") === sourceArm), common = commonPlacement(students, context), select = group.querySelector(".placement-group-select"); if (select) select.value = common; });
        if (els.destinationStudentSummary) {
            const pills = Object.entries(counts).map(([arm,count]) => `<span class="placement-summary-pill">${escapeHtml(displayClass(arm))}: ${count}</span>`).join("");
            const crossPills = Object.entries(cross).map(([label,count]) => `<span class="placement-summary-pill warning">${escapeHtml(label)}: ${count}</span>`).join("");
            els.destinationStudentSummary.innerHTML = `<div class="placement-summary-grid"><strong>${context.allStudents.length - unassigned.length}/${context.allStudents.length} assigned</strong>${pills}${crossPills}${unassigned.length ? `<span class="placement-summary-pill warning">${unassigned.length} need placement</span>` : ""}</div>`;
        }
        if (els.confirmDestinationArmBtn) { els.confirmDestinationArmBtn.disabled = unassigned.length > 0; els.confirmDestinationArmBtn.title = unassigned.length ? `${unassigned.length} student(s) still need a destination arm.` : "Review this placement"; }
    }

    function closeDestinationArmModal() { promotionState.destinationContext = null; hideModal(els.destinationArmModal, els.destinationArmOverlay); }

    function confirmDestinationArm() {
        const context = promotionState.destinationContext; if (!context) return;
        const destinationClasses = {}, missing = [];
        context.allStudents.forEach(student => { const admission = normalizeAdmission(student.Admission_number), arm = context.placements[admission] || ""; if (!arm) missing.push(student); else destinationClasses[student.Admission_number] = arm; });
        if (missing.length) return showToast(`${missing.length} student(s) still need a destination arm.`, "warning");
        hideModal(els.destinationArmModal, els.destinationArmOverlay); promotionState.destinationContext = null;
        openActionPreview({ type:context.type || "promote", action:context.action || "Promote", source:context.source, destination:context.destination, students:context.allStudents, destinationClasses, mode:context.mode || "selected" });
    }

    function cssEscape(value) { return window.CSS?.escape ? window.CSS.escape(String(value || "")) : String(value || "").replace(/["\\]/g, "\\$&"); }

    function bindArmLabelEnhancements() {
        const decorate = () => { decorateArmSelect($("classArmSelector")); decorateArmSelect(els.formClass); updateStudentArmTrackPreview(); decorateStudentTableStreams(); };
        els.formClassCategory?.addEventListener("change", () => setTimeout(decorate, 0)); els.formClass?.addEventListener("change", updateStudentArmTrackPreview);
        document.addEventListener("emis:class-changed", () => setTimeout(decorate, 0)); document.addEventListener("emis:summary-loaded", () => setTimeout(decorate, 0));
        if (els.formClass) new MutationObserver(() => { decorateArmSelect(els.formClass); updateStudentArmTrackPreview(); }).observe(els.formClass, { childList:true });
        const studentsBody = $("studentsBody"); if (studentsBody) new MutationObserver(decorateStudentTableStreams).observe(studentsBody, { childList:true, subtree:true });
        setTimeout(decorate, 0);
    }

    function decorateArmSelect(select) {
        if (!select) return;
        [...select.options].forEach(option => { const value = option.value || ""; if (!value || value === "all" || value.startsWith("AUTO")) return; const meta = armStreamMeta(value); if (value.startsWith("SS")) { const label = `${displayClass(value)} — ${meta.label}`; if (option.textContent !== label) option.textContent = label; } });
        if (select === els.formClass && els.formClassCategory?.value?.startsWith("SS")) {
            const hasScience = [...select.options].some(option => option.value === "AUTO_SCIENCE"), hasArts = [...select.options].some(option => option.value === "AUTO_ART_COMMERCIAL");
            if (!hasScience) select.add(new Option("Automatic / Balanced — Science", "AUTO_SCIENCE"), Math.min(1, select.options.length));
            if (!hasArts) select.add(new Option("Automatic — Arts / Commercial", "AUTO_ART_COMMERCIAL"), Math.min(2, select.options.length));
        }
    }

    function decorateStudentTableStreams() {
        const body = $("studentsBody"); if (!body || !Array.isArray(state.students)) return;
        body.querySelectorAll("tr").forEach(row => {
            const admission = normalizeAdmission(row.querySelector(".student-check")?.dataset.admission); if (!admission) return;
            const student = state.students.find(item => normalizeAdmission(item.Admission_number) === admission), cell = row.querySelector('[data-column-name="class"]'); if (!student || !cell) return;
            const meta = armStreamMeta(student.Class), isSS = String(student.Class || "").startsWith("SS"); let badge = cell.querySelector(".student-table-stream");
            if (!isSS) { if (badge) badge.remove(); return; }
            if (!badge) { cell.insertAdjacentHTML("beforeend", `<span class="student-table-stream ${meta.className}">${escapeHtml(meta.label)}</span>`); return; }
            const wantedClass = `student-table-stream ${meta.className}`; if (badge.className !== wantedClass) badge.className = wantedClass; if (badge.textContent !== meta.label) badge.textContent = meta.label;
        });
    }


    function updateStudentArmTrackPreview() {
        if (!els.studentArmTrackLabel) return;
        const value = els.formClass?.value || "", level = els.formClassCategory?.value || "";
        let meta = armStreamMeta(value), text = "Select an SS arm to see its stream label.";
        if (value === "AUTO_SCIENCE") meta = { className:"science", label:"Science" }, text = "Automatic placement will balance this student among available Science arms.";
        else if (value === "AUTO_ART_COMMERCIAL") meta = { className:"arts-commercial", label:"Arts / Commercial" }, text = "Automatic placement will use the combined Arts / Commercial arm.";
        else if (value) text = `${displayClass(value)} is labelled ${meta.label}.`;
        else if (level.startsWith("SS")) text = "Automatic Assignment may choose any SS arm. Pick a stream-specific automatic option or exact arm when the student's stream is known.";
        else if (level.startsWith("JSS")) meta = { className:"junior", label:"Junior" }, text = "JSS placement uses A, B or C; there is no senior-school stream label yet.";
        els.studentArmTrackLabel.className = `arm-track-preview ${meta.className || "muted"}`; els.studentArmTrackLabel.innerHTML = `<i class="fa-solid fa-tag"></i><span>${escapeHtml(text)}</span>`;
    }


    // =========================================================
    // REPETITION
    // =========================================================
    function startRepeatAction() {
        const students = selectedStudents();

        if (!students.length) {
            showToast("Select at least one student first.", "warning");
            return;
        }

        openActionPreview({
            type: "repeat",
            action: "Repeat",
            source: state.currentClass,
            destination: state.currentClass,
            students, destinationClasses: {}, mode:"selected"
        });
    }


    // =========================================================
    // ACTION PREVIEW
    // =========================================================
    async function openActionPreview(context) {
        promotionState.pendingPreview = context; promotionState.pendingGuard = null;
        if (els.previewModalTitle) els.previewModalTitle.textContent = `${context.action} Preview`;
        if (els.previewAction) els.previewAction.textContent = context.action;
        if (els.previewSourceClass) els.previewSourceClass.textContent = context.source;
        if (els.previewDestinationClass) els.previewDestinationClass.textContent = context.destination;
        if (els.previewStudentCount) els.previewStudentCount.textContent = context.students.length;
        if (els.previewAiGuide) { els.previewAiGuide.classList.add("hidden"); els.previewAiGuide.textContent = ""; }
        if (els.previewWarnings) els.previewWarnings.innerHTML = `<div class="promotion-guard-loading"><i class="fa-solid fa-spinner fa-spin"></i><span>Checking class movement safeguards...</span></div>`;
        if (els.previewBody) {
            const previewRows = context.students.slice(0, 120);
            els.previewBody.innerHTML = previewRows.map(student => {
                const explicitDestination = context.destinationClasses?.[student.Admission_number];
                const destinationText = context.type === "repeat" ? displayClass(student.Class) : context.type === "graduate" ? "Graduate Archive" : explicitDestination ? displayClass(explicitDestination) : getAutomaticDestinationLabel(student, context.destination);
                return `<div class="action-preview-item"><div><strong>${escapeHtml(fullName(student))}</strong><span>${escapeHtml(student.Admission_number)}</span></div><span>${escapeHtml(displayClass(student.Class))}<i class="fa-solid fa-arrow-right"></i>${escapeHtml(destinationText)}</span></div>`;
            }).join("") + (context.students.length > previewRows.length ? `<div class="preview-more-count">+ ${context.students.length - previewRows.length} more student(s)</div>` : "");
        }
        showModal(els.previewModal, els.previewOverlay);
        try { const guard = await requestPromotionGuard(context, false); if (promotionState.pendingPreview !== context) return; promotionState.pendingGuard = guard; renderGuardWarnings(guard); }
        catch (error) { if (els.previewWarnings) els.previewWarnings.innerHTML = `<div class="promotion-guard-card warning"><i class="fa-solid fa-triangle-exclamation"></i><div><strong>Safeguard check unavailable</strong><span>${escapeHtml(error.message)}</span></div></div>`; }
    }

    async function requestPromotionGuard(context, useAi = false) {
        const action = context.type === "graduate" ? "graduate" : context.type;
        return api("/api/promotion/guard", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ action, class_category:context.source, mode:context.mode || "selected", admissions:(context.mode === "all" ? [] : context.students.map(student => student.Admission_number)), destination_classes:context.destinationClasses || {}, use_ai:useAi }) });
    }

    function renderGuardWarnings(guard) {
        if (!els.previewWarnings) return; const warnings = Array.isArray(guard?.warnings) ? guard.warnings : [];
        els.previewWarnings.innerHTML = warnings.map(item => `<div class="promotion-guard-card ${escapeHtml(item.severity || "info")}"><i class="fa-solid ${item.severity === "high" ? "fa-circle-exclamation" : item.severity === "warning" ? "fa-triangle-exclamation" : "fa-circle-info"}"></i><div><strong>${escapeHtml(item.title || "Promotion guidance")}</strong><span>${escapeHtml(item.message || "")}</span></div></div>`).join("") || `<div class="promotion-guard-card info"><i class="fa-solid fa-shield-halved"></i><div><strong>Safeguard check complete</strong><span>No special warning is required for this move.</span></div></div>`;
        if (guard?.recommended_first_action) els.previewWarnings.insertAdjacentHTML("beforeend", `<div class="promotion-sequence-hint"><i class="fa-solid fa-route"></i><span><strong>Recommended yearly order:</strong> ${escapeHtml(guard.recommended_first_action)}</span></div>`);
    }

    async function loadAiGuideForPreview() {
        const context = promotionState.pendingPreview; if (!context || !els.previewAiGuideBtn) return;
        const original = els.previewAiGuideBtn.innerHTML; els.previewAiGuideBtn.disabled = true; els.previewAiGuideBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Asking AI...`;
        try { const guard = await requestPromotionGuard(context, true), text = guard?.ai?.guidance || "AI guidance was unavailable, but the deterministic safeguards above remain authoritative."; if (els.previewAiGuide) { els.previewAiGuide.classList.remove("hidden"); els.previewAiGuide.innerHTML = `<strong><i class="fa-solid fa-wand-magic-sparkles"></i> AI Guide</strong><span>${escapeHtml(text)}</span><small>${escapeHtml(guard?.ai?.provider || "Rules only")}${guard?.ai?.model ? ` • ${escapeHtml(guard.ai.model)}` : ""}</small>`; } }
        catch (error) { showToast(error.message, "warning"); }
        finally { els.previewAiGuideBtn.disabled = false; els.previewAiGuideBtn.innerHTML = original; }
    }

    function renderRoadmap(summary = {}) {
        if (!els.roadmap) return; const steps = [{source:"SS3",destination:"Graduated"},{source:"SS2",destination:"SS3"},{source:"SS1",destination:"SS2"},{source:"JSS3",destination:"SS1"},{source:"JSS2",destination:"JSS3"},{source:"JSS1",destination:"JSS2"}];
        const first = steps.find(step => Number(summary?.[step.source]?.total || 0) > 0)?.source || "";
        els.roadmap.innerHTML = steps.map(step => { const count = Number(summary?.[step.source]?.total || 0), active = step.source === first; return `<div class="roadmap-step ${active ? "recommended" : ""}"><span>${escapeHtml(step.source)}</span><i class="fa-solid fa-arrow-right"></i><strong>${escapeHtml(step.destination)}</strong><small>${count} student${count === 1 ? "" : "s"}</small></div>`; }).join("");
        if (els.roadmapHint) els.roadmapHint.textContent = first ? `Recommended starting point: ${first === "SS3" ? "Graduate SS3 first" : `process ${first} before moving the class below into it`}. This is guidance, not a block.` : "No active class is waiting for promotion.";
    }


    function automaticDestinationArm(student, destination) {
        const source = student.Class_category || "";
        const sourceArm = student.Class || "";

        if (source.startsWith("JSS") && destination.startsWith("JSS")) {
            const suffix = sourceArm.replace(source, "");
            const candidate = `${destination}${suffix}`;

            return CLASS_ARMS[destination]?.includes(candidate)
                ? candidate
                : "";
        }

        if (source.startsWith("SS") && destination.startsWith("SS")) {
            const suffix = sourceArm.replace(source, "");
            const candidate = `${destination}${suffix}`;

            return CLASS_ARMS[destination]?.includes(candidate)
                ? candidate
                : "";
        }

        return "";
    }


    function getAutomaticDestinationLabel(student, destination) {
        if (!destination || destination === "GRADUATED") return "Graduate Archive";

        const destinationArm = automaticDestinationArm(student, destination);

        return destinationArm
            ? displayClass(destinationArm)
            : destination;
    }


    function closePreview() { promotionState.pendingPreview = null; promotionState.pendingGuard = null; hideModal(els.previewModal, els.previewOverlay); }


    // =========================================================
    // PREVIEW CONTINUE
    // =========================================================
    function previewContinue() {
        const context = promotionState.pendingPreview;

        if (!context) return;

        hideModal(els.previewModal, els.previewOverlay);
        promotionState.pendingPreview = null;

        // PROMOTION
        if (context.type === "promote") {
            openConfirmation({
                label: "Confirm Promotion",
                title: `Promote ${context.students.length} student${context.students.length === 1 ? "" : "s"}?`,
                text: context.mode === "all" ? `All active ${context.source} students will move to ${context.destination}. ${context.source} will be empty after a successful full-class promotion. A safety backup is created before the database is changed.` : `${context.source} students will move to ${context.destination}. Students not selected remain in ${context.source}. The live CSV and Excel databases will be synchronized automatically.`,
                students: context.students,
                type: "primary",
                action: () => applyPromotion(context)
            });

            return;
        }

        // DEMOTION
        if (context.type === "demote") {
            openConfirmation({ label:"Confirm Demotion", title:`Demote ${context.students.length} student${context.students.length === 1 ? "" : "s"}?`, text:`The selected student${context.students.length === 1 ? "" : "s"} will move from ${context.source} back to ${context.destination}. A database safety backup is created automatically.`, students:context.students, type:"warning", action:() => applyDemotion(context) });
            return;
        }

        // REPETITION
        if (context.type === "repeat") {
            openConfirmation({
                label: "Confirm Repetition",
                title: `Repeat ${context.students.length} student${context.students.length === 1 ? "" : "s"}?`,
                text: `The selected student${context.students.length === 1 ? "" : "s"} will remain in ${context.source}.`,
                students: context.students,
                type: "warning",
                action: () => applyRepeat(context)
            });

            return;
        }

        // GRADUATION
        if (context.type === "graduate") {
            openConfirmation({
                label: "Confirm Graduation",
                title: `Graduate ${context.students.length} SS3 student${context.students.length === 1 ? "" : "s"}?`,
                text: context.mode === "all" ? "All active SS3 students will be archived and removed from the active school database. SS3 will be empty after success, and released admission numbers can be reused for future new students." : "The selected student(s) will be archived, removed from the active database, and their admission numbers released for future new students.",
                students: context.students,
                type: "graduate",
                action: () => applyGraduation(context)
            });
        }
    }


    // =========================================================
    // APPLY PROMOTION
    // =========================================================
    async function applyPromotion(context) {
        try {
            const data = await api("/api/promotion/promote", {
                method: "POST",
                headers: { "Content-Type": "application/json" },

                body: JSON.stringify({
                    class_category: context.source,
                    mode: context.mode || "selected",
                    confirm_entire_class: context.mode === "all",
                    admissions: context.students.map((student) => student.Admission_number),
                    destination_classes: context.destinationClasses || {}
                })
            });

            forceCloseConfirmation();

            showToast(data.message, "success");
            clearSelection(false);

            await Promise.allSettled([
                loadSummary(),
                loadStudents(),
                loadLogs()
            ]);

            document.dispatchEvent(new CustomEvent("emis:promotion-completed", {
                detail: data
            }));

        } catch (error) {
            showToast(error.message, "error");
        }
    }


    // =========================================================
    // APPLY DEMOTION
    // =========================================================
    async function applyDemotion(context) {
        try {
            const data = await api("/api/promotion/demote", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ class_category: context.source, mode: "selected", admissions: context.students.map(student => student.Admission_number), destination_classes: context.destinationClasses || {} })
            });
            forceCloseConfirmation(); showToast(data.message, "success"); clearSelection(false);
            await Promise.allSettled([loadSummary(), loadStudents(), loadLogs()]);
            document.dispatchEvent(new CustomEvent("emis:demotion-completed", { detail: data }));
        } catch (error) { showToast(error.message, "error"); }
    }


    // =========================================================
    // APPLY REPETITION
    // =========================================================
    async function applyRepeat(context) {
        try {
            const data = await api("/api/promotion/repeat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },

                body: JSON.stringify({
                    class_category: context.source,
                    admissions: context.students.map((student) => student.Admission_number),
                    note: "Student retained in current class"
                })
            });

            forceCloseConfirmation();

            showToast(data.message, "success");
            clearSelection(false);

            await Promise.allSettled([
                loadStudents(),
                loadLogs()
            ]);

            document.dispatchEvent(new CustomEvent("emis:repetition-completed", {
                detail: data
            }));

        } catch (error) {
            showToast(error.message, "error");
        }
    }


    // =========================================================
    // APPLY GRADUATION
    // =========================================================
    async function applyGraduation(context) {
        try {
            const data = await api("/api/promotion/graduate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },

                body: JSON.stringify({
                    class_category: "SS3",
                    mode: context.mode || "selected",
                    confirm_entire_class: context.mode === "all",
                    admissions: context.students.map((student) => student.Admission_number)
                })
            });

            forceCloseConfirmation();

            let message = data.message || "Graduation completed successfully.";

            if (Array.isArray(data.released_admission_numbers) && data.released_admission_numbers.length) {
                message += ` Released admission number${data.released_admission_numbers.length === 1 ? "" : "s"}: ${data.released_admission_numbers.join(", ")}.`;
            }

            showToast(message, "success");
            clearSelection(false);

            await Promise.allSettled([
                loadSummary(),
                loadStudents(),
                loadLogs()
            ]);

            document.dispatchEvent(new CustomEvent("emis:graduation-completed", {
                detail: data
            }));

        } catch (error) {
            showToast(error.message, "error");
        }
    }


    // =========================================================
    // GRADUATE ARCHIVE
    // =========================================================
    async function openGraduates() {
        showModal(els.graduatesModal, els.graduatesOverlay);
        closeGraduateClearPanel();
        await loadGraduatesArchive(false);
    }


    async function loadGraduatesArchive(preserveYear = true) {
        const preferredYear = preserveYear ? (els.graduateYearFilter?.value || "all") : "all";
        if (els.graduatesBody) els.graduatesBody.innerHTML = loadingGraduateRow();

        try {
            const data = await api("/api/promotion/graduates");
            promotionState.graduates = Array.isArray(data.graduates) ? data.graduates : [];
            promotionState.graduatePage = 1;
            populateGraduateYears(data.summary || {}, preferredYear);
            renderGraduates();
        } catch (error) {
            promotionState.graduates = [];
            updateGraduateClearButton();

            if (els.graduatesBody) {
                els.graduatesBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="table-placeholder">
                            <strong>Could not load graduates</strong>
                            <span>${escapeHtml(error.message)}</span>
                        </td>
                    </tr>
                `;
            }
        }
    }


    function closeGraduates() {
        closeGraduateClearPanel();
        hideModal(els.graduatesModal, els.graduatesOverlay);
    }


    function populateGraduateYears(summary, preferredYear = "all") {
        if (!els.graduateYearFilter) return;

        const years = Object.keys(summary.years || {}).sort((a, b) => Number(b) - Number(a));
        els.graduateYearFilter.innerHTML = `
            <option value="all">All Years</option>
            ${years.map((year) => `<option value="${escapeHtml(year)}">${escapeHtml(year)}</option>`).join("")}
        `;

        els.graduateYearFilter.value = years.includes(String(preferredYear)) ? String(preferredYear) : "all";
    }


    function getFilteredGraduates() {
        const query = normalize(els.graduateSearch?.value);
        const year = els.graduateYearFilter?.value || "all";

        return promotionState.graduates.filter((graduate) => {
            if (year !== "all" && String(graduate.Graduation_year || "") !== year) return false;
            if (!query) return true;

            return normalize([
                graduate.Admission_number,
                graduate.Last_name,
                graduate.First_name,
                graduate.Other_names,
                graduate.Class,
                graduate.Academic_session,
                graduate.Graduation_year
            ].join(" ")).includes(query);
        });
    }


    function getGraduateClearTargets() {
        const year = els.graduateYearFilter?.value || "all";
        if (year === "all") return [...promotionState.graduates];
        return promotionState.graduates.filter(graduate => String(graduate.Graduation_year || "") === year);
    }


    function updateGraduateClearButton() {
        if (!els.clearGraduateArchiveBtn) return;
        const year = els.graduateYearFilter?.value || "all";
        const targets = getGraduateClearTargets();
        els.clearGraduateArchiveBtn.disabled = promotionState.graduateClearBusy || !targets.length;
        els.clearGraduateArchiveBtn.innerHTML = year === "all"
            ? `<i class="fa-solid fa-trash-can"></i><span>Clear Archive</span>`
            : `<i class="fa-solid fa-trash-can"></i><span>Clear ${escapeHtml(year)}</span>`;
        els.clearGraduateArchiveBtn.title = !targets.length
            ? "There are no archived graduates in this scope."
            : year === "all"
                ? `Clear all ${targets.length} archived graduate record(s). A backup will be created first.`
                : `Clear all ${targets.length} archived graduate record(s) from ${year}. A backup will be created first.`;
    }


    function openGraduateClearPanel() {
        const targets = getGraduateClearTargets();
        const year = els.graduateYearFilter?.value || "all";
        if (!targets.length) return showToast("There are no archived graduates to clear in this scope.", "warning");

        const scopeName = year === "all" ? "the entire Graduate Archive" : `the ${year} Graduate Archive`;
        if (els.graduateClearTitle) els.graduateClearTitle.textContent = year === "all" ? "Clear Entire Graduate Archive?" : `Clear ${year} Graduate Archive?`;
        if (els.graduateClearMessage) els.graduateClearMessage.textContent = `You are about to remove ${targets.length} archived graduate record${targets.length === 1 ? "" : "s"} from ${scopeName}. Search text does not limit this action. Students will NOT return to SS3, and admission numbers will NOT be released again or otherwise changed.`;
        if (els.graduateClearConfirmInput) els.graduateClearConfirmInput.value = "";
        if (els.confirmGraduateClearBtn) els.confirmGraduateClearBtn.disabled = true;
        els.graduateClearPanel?.classList.remove("hidden");
        setTimeout(() => els.graduateClearConfirmInput?.focus(), 50);
    }


    function closeGraduateClearPanel() {
        if (promotionState.graduateClearBusy) return;
        els.graduateClearPanel?.classList.add("hidden");
        if (els.graduateClearConfirmInput) els.graduateClearConfirmInput.value = "";
        if (els.confirmGraduateClearBtn) els.confirmGraduateClearBtn.disabled = true;
    }


    function updateGraduateClearConfirmation() {
        if (!els.confirmGraduateClearBtn) return;
        const confirmed = String(els.graduateClearConfirmInput?.value || "").trim().toUpperCase() === "DELETE";
        els.confirmGraduateClearBtn.disabled = promotionState.graduateClearBusy || !confirmed;
    }


    async function applyGraduateArchiveClear() {
        if (promotionState.graduateClearBusy) return;

        const confirmation = String(els.graduateClearConfirmInput?.value || "").trim().toUpperCase();
        if (confirmation !== "DELETE") return showToast("Type DELETE exactly to confirm this archive clear.", "warning");

        const year = els.graduateYearFilter?.value || "all";
        const targets = getGraduateClearTargets();
        if (!targets.length) return showToast("There are no archived graduates to clear in this scope.", "warning");

        promotionState.graduateClearBusy = true;
        updateGraduateClearButton();
        if (els.confirmGraduateClearBtn) {
            els.confirmGraduateClearBtn.disabled = true;
            els.confirmGraduateClearBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>Creating backup...</span>`;
        }
        if (els.cancelGraduateClearBtn) els.cancelGraduateClearBtn.disabled = true;

        try {
            const data = await api("/api/promotion/graduates/clear", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ scope: year === "all" ? "all" : "year", year: year === "all" ? "" : year, confirmation })
            });

            showToast(data.message || "Graduate archive cleared successfully.", "success");
            els.graduateClearPanel?.classList.add("hidden");
            if (els.graduateSearch) els.graduateSearch.value = "";
            await Promise.allSettled([loadGraduatesArchive(false), loadLogs()]);
            document.dispatchEvent(new CustomEvent("emis:graduate-archive-cleared", { detail: data }));
        } catch (error) {
            showToast(error.message, "error");
        } finally {
            promotionState.graduateClearBusy = false;
            if (els.cancelGraduateClearBtn) els.cancelGraduateClearBtn.disabled = false;
            if (els.confirmGraduateClearBtn) els.confirmGraduateClearBtn.innerHTML = `<i class="fa-solid fa-trash-can"></i><span>Clear Graduate Archive</span>`;
            updateGraduateClearConfirmation();
            updateGraduateClearButton();
        }
    }


    function renderGraduates() {
        if (!els.graduatesBody) return;

        const filtered = getFilteredGraduates();
        const totalPages = Math.max(1, Math.ceil(filtered.length / promotionState.graduateRowsPerPage));

        promotionState.graduatePage = Math.min(promotionState.graduatePage, totalPages);

        const start = (promotionState.graduatePage - 1) * promotionState.graduateRowsPerPage;
        const pageRows = filtered.slice(start, start + promotionState.graduateRowsPerPage);

        if (!pageRows.length) {
            els.graduatesBody.innerHTML = `
                <tr>
                    <td colspan="6" class="table-placeholder">
                        <span class="table-placeholder-icon"><i class="fa-solid fa-graduation-cap"></i></span>
                        <strong>No graduates found</strong>
                        <span>No archived graduate matches this search.</span>
                    </td>
                </tr>
            `;

        } else {
            els.graduatesBody.innerHTML = pageRows.map((graduate) => `
                <tr>
                    <td>
                        <strong>${escapeHtml(fullName(graduate))}</strong>
                        <span>${escapeHtml(graduate.Academic_session || "")}</span>
                    </td>

                    <td>${escapeHtml(graduate.Admission_number || "—")}</td>
                    <td>${escapeHtml(displayClass(graduate.Class || "—"))}</td>
                    <td>${escapeHtml(graduate.Sex || "—")}</td>
                    <td>${escapeHtml(graduate.Graduation_date || "—")}</td>

                    <td>
                        <button class="row-action-btn graduate-view-btn" data-admission="${escapeHtml(graduate.Admission_number)}" type="button" title="View graduate">
                            <i class="fa-solid fa-eye"></i>
                        </button>
                    </td>
                </tr>
            `).join("");

            document.querySelectorAll(".graduate-view-btn").forEach((button) => {
                button.addEventListener("click", () => {
                    const graduate = promotionState.graduates.find((item) => normalizeAdmission(item.Admission_number) === normalizeAdmission(button.dataset.admission));

                    if (graduate) {
                        closeGraduates();
                        openStudentDetails(graduate);
                    }
                });
            });
        }

        if (els.graduatesCount) els.graduatesCount.textContent = `${filtered.length} graduate${filtered.length === 1 ? "" : "s"}`;
        updateGraduateClearButton();
        renderGraduatePagination(filtered.length, totalPages);
    }


    function renderGraduatePagination(totalRows, totalPages) {
        if (!els.graduatesPagination) return;

        if (!totalRows || totalPages <= 1) {
            els.graduatesPagination.innerHTML = "";
            return;
        }

        els.graduatesPagination.innerHTML = `
            <button type="button" data-graduate-page="${promotionState.graduatePage - 1}" ${promotionState.graduatePage <= 1 ? "disabled" : ""}>
                <i class="fa-solid fa-chevron-left"></i>
            </button>

            <span>${promotionState.graduatePage} / ${totalPages}</span>

            <button type="button" data-graduate-page="${promotionState.graduatePage + 1}" ${promotionState.graduatePage >= totalPages ? "disabled" : ""}>
                <i class="fa-solid fa-chevron-right"></i>
            </button>
        `;

        els.graduatesPagination.querySelectorAll("button[data-graduate-page]").forEach((button) => {
            button.addEventListener("click", () => {
                const page = Number(button.dataset.graduatePage);

                if (page < 1 || page > totalPages) return;

                promotionState.graduatePage = page;
                renderGraduates();
            });
        });
    }


    function loadingGraduateRow() {
        return `
            <tr>
                <td colspan="6" class="table-placeholder">
                    <span class="table-placeholder-icon"><i class="fa-solid fa-spinner fa-spin"></i></span>
                    <strong>Loading graduation archive</strong>
                    <span>Please wait...</span>
                </td>
            </tr>
        `;
    }


    // =========================================================
    // PUBLIC PROMOTION API
    // =========================================================
    window.EMISPromotion = {
        NEXT_CLASS,
        state: promotionState,

        startPromotionAction,
        startWholeClassPromotion,
        startDemotionAction,
        startRepeatAction,
        openGraduates
    };

});
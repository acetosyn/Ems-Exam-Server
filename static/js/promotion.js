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
    const NEXT_CLASS = {
        JSS1: "JSS2",
        JSS2: "JSS3",
        JSS3: "SS1",
        SS1: "SS2",
        SS2: "SS3",
        SS3: "GRADUATED"
    };


    // =========================================================
    // DOM ELEMENTS
    // =========================================================
    const els = {

        // PROMOTION ACTIONS
        promoteSelectedBtn: $("promoteSelectedBtn"),
        repeatSelectedBtn: $("repeatSelectedBtn"),

        // DESTINATION ARM
        destinationArmOverlay: $("destinationArmOverlay"),
        destinationArmModal: $("destinationArmModal"),
        destinationArmTitle: $("destinationArmTitle"),
        destinationArmDescription: $("destinationArmDescription"),
        destinationArmSelector: $("destinationArmSelector"),
        destinationStudentSummary: $("destinationStudentSummary"),
        cancelDestinationArmBtn: $("cancelDestinationArmBtn"),
        confirmDestinationArmBtn: $("confirmDestinationArmBtn"),

        // PREVIEW
        previewOverlay: $("previewOverlay"),
        previewModal: $("previewModal"),
        previewModalTitle: $("previewModalTitle"),
        closePreviewBtn: $("closePreviewBtn"),
        cancelPreviewBtn: $("cancelPreviewBtn"),
        previewAction: $("previewAction"),
        previewSourceClass: $("previewSourceClass"),
        previewDestinationClass: $("previewDestinationClass"),
        previewStudentCount: $("previewStudentCount"),
        previewBody: $("previewBody"),
        confirmPreviewApplyBtn: $("confirmPreviewApplyBtn"),

        // GRADUATES
        viewGraduatesBtn: $("viewGraduatesBtn"),
        graduatesOverlay: $("graduatesOverlay"),
        graduatesModal: $("graduatesModal"),
        closeGraduatesBtn: $("closeGraduatesBtn"),
        graduateSearch: $("graduateSearch"),
        graduateYearFilter: $("graduateYearFilter"),
        graduatesBody: $("graduatesBody"),
        graduatesCount: $("graduatesCount"),
        graduatesPagination: $("graduatesPagination")
    };


    // =========================================================
    // LOCAL STATE
    // =========================================================
    const promotionState = {
        destinationContext: null,
        pendingPreview: null,

        graduates: [],
        graduatePage: 1,
        graduateRowsPerPage: 15
    };


    // =========================================================
    // INITIALIZE
    // =========================================================
    init();

    function init() {
        bindEvents();
    }


    // =========================================================
    // EVENTS
    // =========================================================
    function bindEvents() {

        // PROMOTION / REPETITION
        els.promoteSelectedBtn?.addEventListener("click", startPromotionAction);
        els.repeatSelectedBtn?.addEventListener("click", startRepeatAction);

        // DESTINATION ARM
        els.cancelDestinationArmBtn?.addEventListener("click", closeDestinationArmModal);
        els.destinationArmOverlay?.addEventListener("click", closeDestinationArmModal);
        els.confirmDestinationArmBtn?.addEventListener("click", confirmDestinationArm);

        // PREVIEW
        els.closePreviewBtn?.addEventListener("click", closePreview);
        els.cancelPreviewBtn?.addEventListener("click", closePreview);
        els.previewOverlay?.addEventListener("click", closePreview);
        els.confirmPreviewApplyBtn?.addEventListener("click", previewContinue);

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
            renderGraduates();
        });

        // ESCAPE
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") return;

            closeDestinationArmModal();
            closePreview();
            closeGraduates();
        });
    }


    // =========================================================
    // PROMOTION START
    // =========================================================
    function startPromotionAction() {
        const students = selectedStudents();

        if (!students.length) {
            showToast("Select at least one student first.", "warning");
            return;
        }

        // -----------------------------------------------------
        // SS3 → GRADUATION
        // -----------------------------------------------------
        if (state.currentClass === "SS3") {
            openActionPreview({
                type: "graduate",
                action: "Graduate",
                source: "SS3",
                destination: "Graduate Archive",
                students,
                destinationClasses: {}
            });

            return;
        }

        const destination = NEXT_CLASS[state.currentClass];

        if (!destination) {
            showToast("No promotion destination is configured for this class.", "error");
            return;
        }

        // -----------------------------------------------------
        // JSS3 → SS1
        //
        // SS1 stream / arm must be selected manually.
        // -----------------------------------------------------
        if (state.currentClass === "JSS3") {
            openDestinationArmModal(students, destination, students);
            return;
        }

        // -----------------------------------------------------
        // SS2 → SS3
        //
        // If an SS2 arm has no compatible SS3 destination,
        // request manual placement.
        // -----------------------------------------------------
        if (state.currentClass === "SS2") {
            const needsPlacement = students.filter((student) => {
                const expectedDestination = automaticDestinationArm(student, destination);
                return !expectedDestination;
            });

            if (needsPlacement.length) {
                openDestinationArmModal(students, destination, needsPlacement);
                return;
            }
        }

        // -----------------------------------------------------
        // NORMAL AUTOMATIC PROMOTION
        // -----------------------------------------------------
        openActionPreview({
            type: "promote",
            action: "Promote",
            source: state.currentClass,
            destination,
            students,
            destinationClasses: {}
        });
    }


    // =========================================================
    // DESTINATION ARM
    // =========================================================
    function openDestinationArmModal(allStudents, destination, affectedStudents) {
        const arms = CLASS_ARMS[destination] || [];

        promotionState.destinationContext = {
            allStudents,
            affectedStudents,
            source: state.currentClass,
            destination
        };

        if (els.destinationArmTitle) els.destinationArmTitle.textContent = `${state.currentClass} → ${destination}`;

        if (els.destinationArmDescription) {
            els.destinationArmDescription.textContent = state.currentClass === "JSS3"
                ? `Select the ${destination} arm these ${allStudents.length} student(s) should enter.`
                : `${affectedStudents.length} selected student(s) cannot be mapped automatically. Select their ${destination} destination arm.`;
        }

        if (els.destinationStudentSummary) {
            els.destinationStudentSummary.textContent = `${affectedStudents.length} student${affectedStudents.length === 1 ? "" : "s"} require destination placement`;
        }

        if (els.destinationArmSelector) {
            els.destinationArmSelector.innerHTML = `
                <option value="">Select destination arm</option>
                ${arms.map((arm) => `<option value="${escapeHtml(arm)}">${escapeHtml(displayClass(arm))}</option>`).join("")}
            `;
        }

        showModal(els.destinationArmModal, els.destinationArmOverlay);
    }


    function closeDestinationArmModal() {
        promotionState.destinationContext = null;
        hideModal(els.destinationArmModal, els.destinationArmOverlay);
    }


    function confirmDestinationArm() {
        const context = promotionState.destinationContext;
        const selectedArm = els.destinationArmSelector?.value || "";

        if (!context) return;

        if (!selectedArm) {
            showToast("Select a destination class arm.", "warning");
            return;
        }

        const destinationClasses = {};

        context.affectedStudents.forEach((student) => {
            destinationClasses[student.Admission_number] = selectedArm;
        });

        hideModal(els.destinationArmModal, els.destinationArmOverlay);

        promotionState.destinationContext = null;

        openActionPreview({
            type: "promote",
            action: "Promote",
            source: context.source,
            destination: context.destination,
            students: context.allStudents,
            destinationClasses
        });
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
            students,
            destinationClasses: {}
        });
    }


    // =========================================================
    // ACTION PREVIEW
    // =========================================================
    function openActionPreview(context) {
        promotionState.pendingPreview = context;

        if (els.previewModalTitle) els.previewModalTitle.textContent = `${context.action} Preview`;
        if (els.previewAction) els.previewAction.textContent = context.action;
        if (els.previewSourceClass) els.previewSourceClass.textContent = context.source;
        if (els.previewDestinationClass) els.previewDestinationClass.textContent = context.destination;
        if (els.previewStudentCount) els.previewStudentCount.textContent = context.students.length;

        if (els.previewBody) {
            els.previewBody.innerHTML = context.students.map((student) => {
                const explicitDestination = context.destinationClasses?.[student.Admission_number];

                const destinationText = context.type === "repeat"
                    ? displayClass(student.Class)
                    : context.type === "graduate"
                        ? "Graduate Archive"
                        : explicitDestination
                            ? displayClass(explicitDestination)
                            : getAutomaticDestinationLabel(student, context.destination);

                return `
                    <div class="action-preview-item">
                        <div>
                            <strong>${escapeHtml(fullName(student))}</strong>
                            <span>${escapeHtml(student.Admission_number)}</span>
                        </div>

                        <span>
                            ${escapeHtml(displayClass(student.Class))}
                            <i class="fa-solid fa-arrow-right"></i>
                            ${escapeHtml(destinationText)}
                        </span>
                    </div>
                `;
            }).join("");
        }

        showModal(els.previewModal, els.previewOverlay);
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


    function closePreview() {
        promotionState.pendingPreview = null;
        hideModal(els.previewModal, els.previewOverlay);
    }


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
                text: `${context.source} students will move to ${context.destination}. The live CSV and Excel databases will be synchronized automatically.`,
                students: context.students,
                type: "primary",
                action: () => applyPromotion(context)
            });

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
                text: "The selected student(s) will be archived, removed from the active database, and their admission numbers released for future new students.",
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

        if (els.graduatesBody) els.graduatesBody.innerHTML = loadingGraduateRow();

        try {
            const data = await api("/api/promotion/graduates");

            promotionState.graduates = Array.isArray(data.graduates) ? data.graduates : [];
            promotionState.graduatePage = 1;

            populateGraduateYears(data.summary || {});
            renderGraduates();

        } catch (error) {
            promotionState.graduates = [];

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
        hideModal(els.graduatesModal, els.graduatesOverlay);
    }


    function populateGraduateYears(summary) {
        if (!els.graduateYearFilter) return;

        const years = Object.keys(summary.years || {}).sort((a, b) => Number(b) - Number(a));

        els.graduateYearFilter.innerHTML = `
            <option value="all">All Years</option>
            ${years.map((year) => `<option value="${escapeHtml(year)}">${escapeHtml(year)}</option>`).join("")}
        `;
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
        startRepeatAction,
        openGraduates
    };

});
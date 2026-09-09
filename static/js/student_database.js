// MODULE: Student Database Frontend — Active student records, admission workflow, CRUD, backup, export, table controls and shared Promotion Manager utilities

document.addEventListener("DOMContentLoaded", () => {

    // =========================================================
    // CONSTANTS
    // =========================================================
    const $ = (id) => document.getElementById(id);

    const VALID_CLASSES = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"];

    const CLASS_ARMS = {
        JSS1: ["JSS1A", "JSS1B", "JSS1C"],
        JSS2: ["JSS2A", "JSS2B", "JSS2C"],
        JSS3: ["JSS3A", "JSS3B", "JSS3C"],
        SS1: ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1_B/C"],
        SS2: ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2_B/C"],
        SS3: ["SS3_GOLD", "SS3_SILVER", "SS3_B/C"]
    };


    // =========================================================
    // DOM ELEMENTS
    // =========================================================
    const els = {

        // SUMMARY
        summaryGrid: $("summaryGrid"),
        summaryJSS1: $("summaryJSS1"),
        summaryJSS2: $("summaryJSS2"),
        summaryJSS3: $("summaryJSS3"),
        summarySS1: $("summarySS1"),
        summarySS2: $("summarySS2"),
        summarySS3: $("summarySS3"),

        // FILTERS
        classPills: $("classPills"),
        classSelector: $("classSelector"),
        classArmSelector: $("classArmSelector"),
        sortStudents: $("sortStudents"),
        studentSearch: $("studentSearch"),
        clearSearchBtn: $("clearSearchBtn"),
        activeFilterChips: $("activeFilterChips"),
        filteredStudentCount: $("filteredStudentCount"),

        // STUDENT TABLE
        studentTableTitle: $("studentTableTitle"),
        tableSubtitle: $("tableSubtitle"),
        studentsTable: $("studentsTable"),
        studentsBody: $("studentsBody"),
        masterCheck: $("masterCheck"),
        rowsPerPage: $("rowsPerPage"),
        paginationInfo: $("paginationInfo"),
        pagination: $("pagination"),

        // SELECTION
        selectedCountBadge: $("selectedCountBadge"),
        promoteSelectedBtn: $("promoteSelectedBtn"),
        promoteButtonIcon: $("promoteButtonIcon"),
        promoteButtonText: $("promoteButtonText"),
        repeatSelectedBtn: $("repeatSelectedBtn"),
        clearSelectionBtn: $("clearSelectionBtn"),
        deleteSelectedBtn: $("deleteSelectedBtn"),

        // PAGE ACTIONS
        openAddStudentBtn: $("openAddStudentBtn"),
        refreshBtn: $("refreshBtn"),
        backupNowBtn: $("backupNowBtn"),
        exportClassBtn: $("exportClassBtn"),
        exportClassCsvBtn: $("exportClassCsvBtn"),

        // TABLE TOOLS
        columnToggleBtn: $("columnToggleBtn"),
        columnMenu: $("columnMenu"),
        resetColumnsBtn: $("resetColumnsBtn"),
        toggleCompactBtn: $("toggleCompactBtn"),

        // LOGS
        logsList: $("logsList"),

        // STUDENT DETAILS
        studentDetailsOverlay: $("studentDetailsOverlay"),
        studentDetailsModal: $("studentDetailsModal"),
        closeStudentDetailsBtn: $("closeStudentDetailsBtn"),
        closeDetailsActionBtn: $("closeDetailsActionBtn"),
        editFromDetailsBtn: $("editFromDetailsBtn"),
        detailsStudentName: $("detailsStudentName"),
        detailsStudentAdmission: $("detailsStudentAdmission"),
        detailsClassBadge: $("detailsClassBadge"),
        detailsAdmissionNumber: $("detailsAdmissionNumber"),
        detailsLastName: $("detailsLastName"),
        detailsFirstName: $("detailsFirstName"),
        detailsOtherNames: $("detailsOtherNames"),
        detailsSex: $("detailsSex"),
        detailsPhone: $("detailsPhone"),
        detailsClass: $("detailsClass"),
        detailsCategory: $("detailsCategory"),

        // ADD / EDIT STUDENT
        studentFormOverlay: $("studentFormOverlay"),
        studentFormModal: $("studentFormModal"),
        studentFormTitle: $("studentFormTitle"),
        closeStudentFormBtn: $("closeStudentFormBtn"),
        cancelStudentFormBtn: $("cancelStudentFormBtn"),
        studentRecordForm: $("studentRecordForm"),
        editingAdmission: $("editingAdmission"),
        formAdmission: $("formAdmission"),
        formLastName: $("formLastName"),
        formFirstName: $("formFirstName"),
        formOtherNames: $("formOtherNames"),
        formPhone: $("formPhone"),
        formSex: $("formSex"),
        formClassCategory: $("formClassCategory"),
        formClass: $("formClass"),
        saveStudentBtn: $("saveStudentBtn"),

        // OPTIONAL VOICE ENTRY
        startVoiceEntryBtn: $("startVoiceEntryBtn"),
        voiceButtonText: $("voiceButtonText"),
        voiceStatus: $("voiceStatus"),
        voiceStatusText: $("voiceStatusText"),

        // SHARED CONFIRMATION
        confirmModal: $("confirmModal"),
        confirmModalIcon: $("confirmModalIcon"),
        confirmModalLabel: $("confirmModalLabel"),
        confirmModalTitle: $("confirmModalTitle"),
        confirmText: $("confirmText"),
        confirmStudentList: $("confirmStudentList"),
        cancelConfirmBtn: $("cancelConfirmBtn"),
        confirmActionBtn: $("confirmActionBtn"),

        // TOASTS
        toastRoot: $("toastRoot")
    };


    // =========================================================
    // STATE
    // =========================================================
    const state = {
        currentClass: "JSS1",
        students: [],
        selected: new Set(),

        page: 1,
        rowsPerPage: 20,

        sortKey: "name",
        sortDirection: "asc",

        currentStudent: null,

        visibleColumns: new Set(["student", "admission", "sex", "class", "category", "phone"]),
        compact: false,

        recognition: null,
        listening: false,

        pendingAction: null,

        summary: {},
        admissionSummary: {}
    };


    // =========================================================
    // INITIALIZATION
    // =========================================================
    init();

    function init() {
        bindEvents();

        updateClassUI("JSS1");
        updateClassArmFilter();
        updateActionButtons();
        applyColumnVisibility();

        refreshAll();
    }


    // =========================================================
    // EVENT BINDINGS
    // =========================================================
    function bindEvents() {

        // GENERAL PAGE ACTIONS
        els.refreshBtn?.addEventListener("click", refreshAll);
        els.openAddStudentBtn?.addEventListener("click", () => openStudentForm());
        els.backupNowBtn?.addEventListener("click", backupDatabase);
        els.exportClassBtn?.addEventListener("click", () => exportCurrentClass("xlsx"));
        els.exportClassCsvBtn?.addEventListener("click", () => exportCurrentClass("csv"));

        // CLASS SELECTOR
        els.classSelector?.addEventListener("change", () => changeClass(els.classSelector.value));

        // CLASS PILLS
        document.querySelectorAll(".class-pill[data-class]").forEach((button) => {
            button.addEventListener("click", () => changeClass(button.dataset.class));
        });

        // CLASS SUMMARY CARDS
        document.querySelectorAll(".class-summary-card[data-class]").forEach((card) => {
            card.addEventListener("click", () => changeClass(card.dataset.class));

            card.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    changeClass(card.dataset.class);
                }
            });
        });

        // CLASS ARM FILTER
        els.classArmSelector?.addEventListener("change", () => {
            state.page = 1;
            clearSelection(false);
            renderStudents();
        });

        // SORT
        els.sortStudents?.addEventListener("change", () => {
            state.sortKey = els.sortStudents.value;
            state.sortDirection = "asc";
            state.page = 1;
            renderStudents();
        });

        // SEARCH
        els.studentSearch?.addEventListener("input", () => {
            state.page = 1;
            renderStudents();
        });

        els.clearSearchBtn?.addEventListener("click", () => {
            if (!els.studentSearch) return;

            els.studentSearch.value = "";
            state.page = 1;

            renderStudents();
            els.studentSearch.focus();
        });

        // ROWS PER PAGE
        els.rowsPerPage?.addEventListener("change", () => {
            state.rowsPerPage = Number(els.rowsPerPage.value || 20);
            state.page = 1;
            renderStudents();
        });

        // TABLE SORTING
        document.querySelectorAll("#studentsTable th.sortable").forEach((header) => {
            header.addEventListener("click", () => {
                const key = header.dataset.sort;

                if (state.sortKey === key) {
                    state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
                } else {
                    state.sortKey = key;
                    state.sortDirection = "asc";
                }

                if (els.sortStudents && ["name", "admission", "class", "sex"].includes(key)) els.sortStudents.value = key;

                state.page = 1;
                renderStudents();
            });
        });

        // MASTER CHECKBOX
        els.masterCheck?.addEventListener("change", () => {
            if (els.masterCheck.checked) selectVisiblePage();
            else deselectVisiblePage();
        });

        // CLEAR SELECTION
        els.clearSelectionBtn?.addEventListener("click", () => clearSelection());

        // DELETE
        els.deleteSelectedBtn?.addEventListener("click", startDeleteAction);

        // STUDENT DETAILS
        els.closeStudentDetailsBtn?.addEventListener("click", closeStudentDetails);
        els.closeDetailsActionBtn?.addEventListener("click", closeStudentDetails);
        els.studentDetailsOverlay?.addEventListener("click", closeStudentDetails);

        els.editFromDetailsBtn?.addEventListener("click", () => {
            if (!state.currentStudent) return;

            const student = state.currentStudent;

            closeStudentDetails();
            openStudentForm(student);
        });

        // ADD / EDIT STUDENT
        els.closeStudentFormBtn?.addEventListener("click", closeStudentForm);
        els.cancelStudentFormBtn?.addEventListener("click", closeStudentForm);
        els.studentFormOverlay?.addEventListener("click", closeStudentForm);
        els.studentRecordForm?.addEventListener("submit", saveStudentRecord);

        els.formClassCategory?.addEventListener("change", () => {
            populateFormClassArms(els.formClassCategory.value);
        });

        // VOICE ENTRY
        els.startVoiceEntryBtn?.addEventListener("click", toggleVoiceEntry);

        // SHARED CONFIRMATION
        els.cancelConfirmBtn?.addEventListener("click", closeConfirmation);
        els.confirmActionBtn?.addEventListener("click", runPendingAction);

        els.confirmModal?.addEventListener("click", (event) => {
            if (event.target === els.confirmModal) closeConfirmation();
        });

        // COLUMN MANAGER
        els.columnToggleBtn?.addEventListener("click", toggleColumnMenu);
        els.resetColumnsBtn?.addEventListener("click", resetColumns);

        els.columnMenu?.querySelectorAll('input[type="checkbox"][data-column]').forEach((checkbox) => {
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) state.visibleColumns.add(checkbox.dataset.column);
                else state.visibleColumns.delete(checkbox.dataset.column);

                applyColumnVisibility();
            });
        });

        // COMPACT TABLE
        els.toggleCompactBtn?.addEventListener("click", toggleCompactMode);

        // OUTSIDE COLUMN MENU
        document.addEventListener("click", (event) => {
            if (!els.columnMenu || !els.columnToggleBtn) return;

            if (!els.columnMenu.contains(event.target) && !els.columnToggleBtn.contains(event.target)) closeColumnMenu();
        });

        // ESCAPE
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") return;

            closeStudentDetails();
            closeStudentForm();
            closeColumnMenu();

            if (!confirmationIsLoading()) closeConfirmation();
        });
    }


    // =========================================================
    // API
    // =========================================================
    async function api(url, options = {}) {
        const response = await fetch(url, options);
        const contentType = response.headers.get("content-type") || "";

        const data = contentType.includes("application/json")
            ? await response.json().catch(() => ({}))
            : {};

        if (!response.ok || data.success === false) throw new Error(data.message || `Request failed with status ${response.status}.`);

        return data;
    }


    // =========================================================
    // REFRESH
    // =========================================================
    async function refreshAll() {
        await Promise.allSettled([
            loadSummary(),
            loadStudents(),
            loadLogs()
        ]);

        dispatch("emis:database-refreshed", {});
    }


    // =========================================================
    // SUMMARY
    // =========================================================
    async function loadSummary() {
        try {
            const data = await api("/api/promotion/summary");

            state.summary = data.summary || {};
            state.admissionSummary = data.admission_numbers || {};

            VALID_CLASSES.forEach((className) => {
                const element = $(`summary${className}`);
                if (element) element.textContent = state.summary[className]?.total ?? 0;
            });

            updateAdmissionPreview();

            dispatch("emis:summary-loaded", {
                summary: state.summary,
                admissionNumbers: state.admissionSummary
            });

            return data;

        } catch (error) {
            showToast(`Summary could not be loaded: ${error.message}`, "error");
            throw error;
        }
    }


    function updateAdmissionPreview() {
        if (!els.formAdmission) return;

        const editing = Boolean(normalizeAdmission(els.editingAdmission?.value));

        if (editing) return;

        const next = state.admissionSummary?.next_admission_number || "";
        const source = state.admissionSummary?.next_admission_source || "";

        els.formAdmission.value = "";

        if (next) {
            els.formAdmission.placeholder = source === "recycled"
                ? `${next} available — assigned when saved`
                : `${next} expected — assigned when saved`;
        } else {
            els.formAdmission.placeholder = "Automatically assigned when saved";
        }
    }


    // =========================================================
    // CLASS
    // =========================================================
    function changeClass(className) {
        if (!VALID_CLASSES.includes(className)) return;

        state.currentClass = className;
        state.page = 1;

        clearSelection(false);
        updateClassUI(className);
        updateClassArmFilter();

        dispatch("emis:class-changed", {
            className
        });

        loadStudents();
    }


    function updateClassUI(className) {
        state.currentClass = className;

        if (els.classSelector) els.classSelector.value = className;

        document.querySelectorAll(".class-pill[data-class]").forEach((button) => {
            button.classList.toggle("active", button.dataset.class === className);
        });

        document.querySelectorAll(".class-summary-card[data-class]").forEach((card) => {
            card.classList.toggle("active", card.dataset.class === className);
        });

        if (els.studentTableTitle) els.studentTableTitle.textContent = `${className} Students`;
        if (els.tableSubtitle) els.tableSubtitle.textContent = `Live student records for ${className}.`;
    }


    function updateClassArmFilter() {
        if (!els.classArmSelector) return;

        const arms = CLASS_ARMS[state.currentClass] || [];

        els.classArmSelector.innerHTML = `
            <option value="all">All Arms</option>
            ${arms.map((arm) => `<option value="${escapeHtml(arm)}">${escapeHtml(displayClass(arm))}</option>`).join("")}
        `;

        els.classArmSelector.value = "all";
    }


    // =========================================================
    // LOAD STUDENTS
    // =========================================================
    async function loadStudents() {
        const className = state.currentClass;

        if (els.tableSubtitle) els.tableSubtitle.textContent = `Loading ${className} student records...`;
        if (els.studentsBody) els.studentsBody.innerHTML = loadingRow("Loading student database", "Please wait...");

        try {
            const data = await api(`/api/promotion/students?class=${encodeURIComponent(className)}`);

            if (className !== state.currentClass) return data;

            state.students = Array.isArray(data.students) ? data.students : [];
            state.selected.clear();
            state.page = 1;

            renderStudents();
            updateActionButtons();

            if (els.tableSubtitle) {
                els.tableSubtitle.textContent = `${state.students.length} active student record${state.students.length === 1 ? "" : "s"} in ${className}.`;
            }

            dispatch("emis:students-loaded", {
                className,
                students: state.students
            });

            dispatchSelectionChanged();

            return data;

        } catch (error) {
            state.students = [];
            state.selected.clear();

            if (els.studentsBody) els.studentsBody.innerHTML = errorRow("Could not load students", error.message);

            updateActionButtons();
            updatePaginationInfo(0, 0, 0);

            if (els.tableSubtitle) els.tableSubtitle.textContent = `Unable to load ${className} records.`;

            dispatchSelectionChanged();

            throw error;
        }
    }


    // =========================================================
    // FILTER / SORT
    // =========================================================
    function getFilteredStudents() {
        const query = normalize(els.studentSearch?.value);
        const arm = els.classArmSelector?.value || "all";

        const list = state.students.filter((student) => {
            if (arm !== "all" && student.Class !== arm) return false;
            if (!query) return true;

            return normalize([
                student.Admission_number,
                student.Last_name,
                student.First_name,
                student.Other_names,
                student.Phone,
                student.Sex,
                student.Class,
                student.Class_category
            ].join(" ")).includes(query);
        });

        list.sort(compareStudents);

        if (state.sortDirection === "desc") list.reverse();

        return list;
    }


    function compareStudents(a, b) {
        const key = state.sortKey || "name";

        if (key === "admission") return admissionNumberValue(a.Admission_number) - admissionNumberValue(b.Admission_number);
        if (key === "class") return normalize(a.Class).localeCompare(normalize(b.Class));
        if (key === "category") return normalize(a.Class_category).localeCompare(normalize(b.Class_category));
        if (key === "sex") return normalize(a.Sex).localeCompare(normalize(b.Sex));

        return normalize(`${a.Last_name} ${a.First_name} ${a.Other_names}`).localeCompare(normalize(`${b.Last_name} ${b.First_name} ${b.Other_names}`));
    }


    function admissionNumberValue(value) {
        const match = String(value || "").toLowerCase().match(/^std(\d+)$/);
        return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
    }


    // =========================================================
    // RENDER STUDENTS
    // =========================================================
    function renderStudents() {
        if (!els.studentsBody) return;

        const filtered = getFilteredStudents();
        const totalPages = Math.max(1, Math.ceil(filtered.length / state.rowsPerPage));

        state.page = Math.min(state.page, totalPages);

        const start = (state.page - 1) * state.rowsPerPage;
        const pageRows = filtered.slice(start, start + state.rowsPerPage);

        if (!pageRows.length) {
            els.studentsBody.innerHTML = emptyRow("No students found", "No student matches the current class, arm or search.");
        } else {
            els.studentsBody.innerHTML = pageRows.map(studentRow).join("");
            bindStudentRows();
        }

        renderPagination(filtered.length, totalPages);
        updateFilters(filtered.length);
        updateMasterCheckbox(pageRows);
        updateActionButtons();
        applyColumnVisibility();
    }


    function studentRow(student) {
        const admission = student.Admission_number || "";
        const key = normalizeAdmission(admission);
        const name = fullName(student);

        return `
            <tr class="${state.selected.has(key) ? "is-selected" : ""}">
                <td class="select-col" data-column-name="select">
                    <input type="checkbox" class="student-check" data-admission="${escapeHtml(admission)}" ${state.selected.has(key) ? "checked" : ""} aria-label="Select ${escapeHtml(name)}">
                </td>

                <td data-column-name="student">
                    <div class="student-name">${escapeHtml(name || "Unknown Student")}</div>
                    <div class="student-sub">${escapeHtml(admission)}</div>
                </td>

                <td data-column-name="admission">
                    <span class="admission-number">${escapeHtml(admission || "—")}</span>
                </td>

                <td data-column-name="sex">${escapeHtml(student.Sex || "—")}</td>

                <td data-column-name="class">
                    <span class="student-class-cell">${escapeHtml(displayClass(student.Class || "—"))}</span>
                </td>

                <td data-column-name="category">${escapeHtml(student.Class_category || "—")}</td>
                <td data-column-name="phone">${escapeHtml(student.Phone || "—")}</td>

                <td class="actions-col">
                    <div class="row-actions">
                        <button class="row-action-btn view-student" data-admission="${escapeHtml(admission)}" type="button" title="View student">
                            <i class="fa-solid fa-eye"></i>
                        </button>

                        <button class="row-action-btn edit-student" data-admission="${escapeHtml(admission)}" type="button" title="Edit student">
                            <i class="fa-solid fa-pen"></i>
                        </button>

                        <button class="row-action-btn danger delete-student" data-admission="${escapeHtml(admission)}" type="button" title="Delete student">
                            <i class="fa-solid fa-user-minus"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }


    function bindStudentRows() {
        document.querySelectorAll(".student-check").forEach((checkbox) => {
            checkbox.addEventListener("change", () => {
                const admission = normalizeAdmission(checkbox.dataset.admission);

                if (checkbox.checked) state.selected.add(admission);
                else state.selected.delete(admission);

                renderStudents();
                dispatchSelectionChanged();
            });
        });

        document.querySelectorAll(".view-student").forEach((button) => {
            button.addEventListener("click", () => {
                const student = findStudent(button.dataset.admission);
                if (student) openStudentDetails(student);
            });
        });

        document.querySelectorAll(".edit-student").forEach((button) => {
            button.addEventListener("click", () => {
                const student = findStudent(button.dataset.admission);
                if (student) openStudentForm(student);
            });
        });

        document.querySelectorAll(".delete-student").forEach((button) => {
            button.addEventListener("click", () => {
                const admission = normalizeAdmission(button.dataset.admission);

                state.selected.clear();
                state.selected.add(admission);

                renderStudents();
                dispatchSelectionChanged();
                startDeleteAction();
            });
        });
    }


    // =========================================================
    // SELECTION
    // =========================================================
    function getCurrentPageRows() {
        const filtered = getFilteredStudents();
        const start = (state.page - 1) * state.rowsPerPage;

        return filtered.slice(start, start + state.rowsPerPage);
    }


    function selectVisiblePage() {
        getCurrentPageRows().forEach((student) => state.selected.add(normalizeAdmission(student.Admission_number)));

        renderStudents();
        dispatchSelectionChanged();
    }


    function deselectVisiblePage() {
        getCurrentPageRows().forEach((student) => state.selected.delete(normalizeAdmission(student.Admission_number)));

        renderStudents();
        dispatchSelectionChanged();
    }


    function clearSelection(render = true) {
        state.selected.clear();

        if (els.masterCheck) {
            els.masterCheck.checked = false;
            els.masterCheck.indeterminate = false;
        }

        updateActionButtons();

        if (render) renderStudents();

        dispatchSelectionChanged();
    }


    function updateMasterCheckbox(pageRows) {
        if (!els.masterCheck) return;

        const admissions = pageRows.map((student) => normalizeAdmission(student.Admission_number)).filter(Boolean);
        const selectedCount = admissions.filter((admission) => state.selected.has(admission)).length;

        els.masterCheck.checked = admissions.length > 0 && selectedCount === admissions.length;
        els.masterCheck.indeterminate = selectedCount > 0 && selectedCount < admissions.length;
    }


    function selectedStudents() {
        return state.students.filter((student) => state.selected.has(normalizeAdmission(student.Admission_number)));
    }


    function updateActionButtons() {
        const disabled = state.selected.size === 0;

        if (els.selectedCountBadge) els.selectedCountBadge.textContent = `${state.selected.size} selected`;
        if (els.promoteSelectedBtn) els.promoteSelectedBtn.disabled = disabled;
        if (els.repeatSelectedBtn) els.repeatSelectedBtn.disabled = disabled;
        if (els.clearSelectionBtn) els.clearSelectionBtn.disabled = disabled;
        if (els.deleteSelectedBtn) els.deleteSelectedBtn.disabled = disabled;

        updatePromotionButton();
    }


    function updatePromotionButton() {
        if (!els.promoteButtonText || !els.promoteButtonIcon) return;

        if (state.currentClass === "SS3") {
            els.promoteButtonText.textContent = "Graduate";
            els.promoteButtonIcon.className = "fa-solid fa-graduation-cap";
        } else {
            els.promoteButtonText.textContent = "Promote";
            els.promoteButtonIcon.className = "fa-solid fa-arrow-up";
        }
    }


    function dispatchSelectionChanged() {
        dispatch("emis:selection-changed", {
            selected: selectedStudents(),
            count: state.selected.size,
            currentClass: state.currentClass
        });
    }


    // =========================================================
    // FILTER DISPLAY
    // =========================================================
    function updateFilters(filteredCount) {
        const arm = els.classArmSelector?.value || "all";
        const query = els.studentSearch?.value?.trim() || "";

        const chips = [
            `<span class="filter-chip">${escapeHtml(state.currentClass)}</span>`,
            `<span class="filter-chip">${escapeHtml(arm === "all" ? "All Arms" : displayClass(arm))}</span>`
        ];

        if (query) chips.push(`<span class="filter-chip">Search: ${escapeHtml(query)}</span>`);

        if (els.activeFilterChips) els.activeFilterChips.innerHTML = chips.join("");
        if (els.filteredStudentCount) els.filteredStudentCount.textContent = `${filteredCount} student${filteredCount === 1 ? "" : "s"}`;
    }


    // =========================================================
    // PAGINATION
    // =========================================================
    function renderPagination(totalRows, totalPages) {
        if (!els.pagination) return;

        if (!totalRows) {
            els.pagination.innerHTML = "";
            updatePaginationInfo(0, 0, 0);
            return;
        }

        const buttons = [];

        buttons.push(`
            <button type="button" data-page="${state.page - 1}" ${state.page <= 1 ? "disabled" : ""}>
                <i class="fa-solid fa-chevron-left"></i>
            </button>
        `);

        paginationPages(totalPages, state.page).forEach((page) => {
            if (page === "...") {
                buttons.push(`<span class="pagination-ellipsis">…</span>`);
            } else {
                buttons.push(`<button type="button" data-page="${page}" class="${page === state.page ? "active" : ""}">${page}</button>`);
            }
        });

        buttons.push(`
            <button type="button" data-page="${state.page + 1}" ${state.page >= totalPages ? "disabled" : ""}>
                <i class="fa-solid fa-chevron-right"></i>
            </button>
        `);

        els.pagination.innerHTML = buttons.join("");

        els.pagination.querySelectorAll("button[data-page]").forEach((button) => {
            button.addEventListener("click", () => {
                const page = Number(button.dataset.page);

                if (page < 1 || page > totalPages || page === state.page) return;

                state.page = page;
                renderStudents();
            });
        });

        const start = (state.page - 1) * state.rowsPerPage + 1;
        const end = Math.min(state.page * state.rowsPerPage, totalRows);

        updatePaginationInfo(start, end, totalRows);
    }


    function paginationPages(totalPages, currentPage) {
        if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);

        const pages = [1];

        if (currentPage > 4) pages.push("...");

        const start = Math.max(2, currentPage - 1);
        const end = Math.min(totalPages - 1, currentPage + 1);

        for (let page = start; page <= end; page += 1) pages.push(page);

        if (currentPage < totalPages - 3) pages.push("...");

        pages.push(totalPages);

        return pages;
    }


    function updatePaginationInfo(start, end, total) {
        if (!els.paginationInfo) return;

        els.paginationInfo.textContent = total
            ? `Showing ${start}–${end} of ${total} students`
            : "Showing 0 students";
    }


    // =========================================================
    // DELETE STUDENT
    // =========================================================
    function startDeleteAction() {
        const students = selectedStudents();

        if (!students.length) {
            showToast("Select at least one student first.", "warning");
            return;
        }

        openConfirmation({
            label: "Delete Student Record",
            title: students.length === 1 ? "Delete this student?" : `Delete ${students.length} students?`,
            text: "The selected student record(s) will be removed from the active school database. Their admission numbers will not be recycled.",
            students,
            type: "danger",
            action: deleteSelectedStudents
        });
    }


    async function deleteSelectedStudents() {
        try {
            const admissions = selectedStudents().map((student) => student.Admission_number);

            const data = await api("/api/promotion/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    class_category: state.currentClass,
                    admissions
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

        } catch (error) {
            showToast(error.message, "error");
        }
    }


    // =========================================================
    // STUDENT DETAILS
    // =========================================================
    function openStudentDetails(student) {
        state.currentStudent = student;

        if (els.detailsStudentName) els.detailsStudentName.textContent = fullName(student) || "Unknown Student";
        if (els.detailsStudentAdmission) els.detailsStudentAdmission.textContent = student.Admission_number || "—";
        if (els.detailsClassBadge) els.detailsClassBadge.textContent = displayClass(student.Class || "—");
        if (els.detailsAdmissionNumber) els.detailsAdmissionNumber.textContent = student.Admission_number || "—";
        if (els.detailsLastName) els.detailsLastName.textContent = student.Last_name || "—";
        if (els.detailsFirstName) els.detailsFirstName.textContent = student.First_name || "—";
        if (els.detailsOtherNames) els.detailsOtherNames.textContent = student.Other_names || "—";
        if (els.detailsSex) els.detailsSex.textContent = student.Sex || "—";
        if (els.detailsPhone) els.detailsPhone.textContent = student.Phone || "—";
        if (els.detailsClass) els.detailsClass.textContent = displayClass(student.Class || "—");
        if (els.detailsCategory) els.detailsCategory.textContent = student.Class_category || "—";

        showModal(els.studentDetailsModal, els.studentDetailsOverlay);
    }


    function closeStudentDetails() {
        hideModal(els.studentDetailsModal, els.studentDetailsOverlay);
        state.currentStudent = null;
    }


    // =========================================================
    // ADD / EDIT STUDENT
    // =========================================================
    function openStudentForm(student = null) {
        if (!els.studentFormModal || !els.studentRecordForm) {
            console.error("Student Database: Add/Edit Student modal was not found.");
            showToast("The Add Student form could not be opened.", "error");
            return;
        }

        els.studentRecordForm.reset();

        stopVoiceEntry();
        hideVoiceStatus();

        if (student) {
            if (els.studentFormTitle) els.studentFormTitle.textContent = "Edit Student";
            if (els.editingAdmission) els.editingAdmission.value = student.Admission_number || "";
            if (els.formAdmission) {
                els.formAdmission.value = student.Admission_number || "";
                els.formAdmission.placeholder = "";
            }

            if (els.formLastName) els.formLastName.value = student.Last_name || "";
            if (els.formFirstName) els.formFirstName.value = student.First_name || "";
            if (els.formOtherNames) els.formOtherNames.value = student.Other_names || "";
            if (els.formPhone) els.formPhone.value = student.Phone || "";
            if (els.formSex) els.formSex.value = normalizeSexValue(student.Sex);

            const classCategory = student.Class_category || state.currentClass || "JSS1";

            if (els.formClassCategory) els.formClassCategory.value = classCategory;

            populateFormClassArms(classCategory, student.Class || "");

            if (els.saveStudentBtn) {
                els.saveStudentBtn.innerHTML = `
                    <i class="fa-solid fa-floppy-disk"></i>
                    <span>Save Changes</span>
                `;
            }

        } else {
            if (els.studentFormTitle) els.studentFormTitle.textContent = "Add Student";
            if (els.editingAdmission) els.editingAdmission.value = "";
            if (els.formAdmission) els.formAdmission.value = "";

            const defaultClass = VALID_CLASSES.includes(state.currentClass) ? state.currentClass : "JSS1";

            if (els.formClassCategory) els.formClassCategory.value = defaultClass;

            populateFormClassArms(defaultClass);
            updateAdmissionPreview();

            if (els.saveStudentBtn) {
                els.saveStudentBtn.innerHTML = `
                    <i class="fa-solid fa-user-plus"></i>
                    <span>Add Student</span>
                `;
            }
        }

        showModal(els.studentFormModal, els.studentFormOverlay);

        window.requestAnimationFrame(() => els.formLastName?.focus());
    }


    function closeStudentForm() {
        stopVoiceEntry();
        hideModal(els.studentFormModal, els.studentFormOverlay);
    }


    // =========================================================
    // CLASS ARM OPTIONS
    // =========================================================
    function populateFormClassArms(classCategory, selectedArm = "") {
        if (!els.formClass) return;

        const arms = CLASS_ARMS[classCategory] || [];

        if (!classCategory || !arms.length) {
            els.formClass.innerHTML = `<option value="">Select class first</option>`;
            els.formClass.disabled = true;
            return;
        }

        els.formClass.disabled = false;

        els.formClass.innerHTML = `
            <option value="">Automatic Assignment</option>
            ${arms.map((arm) => `<option value="${escapeHtml(arm)}">${escapeHtml(displayClass(arm))}</option>`).join("")}
        `;

        els.formClass.value = selectedArm && arms.includes(selectedArm) ? selectedArm : "";
    }


    // =========================================================
    // SAVE STUDENT
    // =========================================================
    async function saveStudentRecord(event) {
        event.preventDefault();

        const editingAdmission = normalizeAdmission(els.editingAdmission?.value);

        const student = {
            Last_name: els.formLastName?.value.trim() || "",
            First_name: els.formFirstName?.value.trim() || "",
            Other_names: els.formOtherNames?.value.trim() || "",
            Phone: els.formPhone?.value.trim() || "",
            Sex: els.formSex?.value || "",
            Class_category: els.formClassCategory?.value || "",
            Class: els.formClass?.value || ""
        };

        if (!student.Last_name) {
            showToast("Enter the student's last name.", "warning");
            els.formLastName?.focus();
            return;
        }

        if (!student.First_name) {
            showToast("Enter the student's first name.", "warning");
            els.formFirstName?.focus();
            return;
        }

        if (!student.Sex) {
            showToast("Select the student's sex.", "warning");
            els.formSex?.focus();
            return;
        }

        if (!student.Class_category) {
            showToast("Select the student's class.", "warning");
            els.formClassCategory?.focus();
            return;
        }

        if (!VALID_CLASSES.includes(student.Class_category)) {
            showToast("The selected class is invalid.", "error");
            return;
        }

        if (editingAdmission) student.Admission_number = editingAdmission;

        setSaveStudentLoading(true);

        try {
            const data = await api("/api/promotion/student/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    original_admission: editingAdmission,
                    student
                })
            });

            closeStudentForm();

            const savedStudent = data.student || {};
            const savedClass = savedStudent.Class_category || student.Class_category;
            const admission = data.admission_number || savedStudent.Admission_number || editingAdmission;
            const classArm = data.class_arm || savedStudent.Class || "";
            const armSource = data.arm_source || "";
            const admissionSource = data.admission_source || "";

            state.currentClass = savedClass;

            updateClassUI(savedClass);
            updateClassArmFilter();

            let message = data.message || "Student saved successfully.";

            if (!editingAdmission && admission) {
                if (admissionSource === "recycled") message += ` Recycled admission number ${admission} was assigned.`;
                else if (admissionSource === "new") message += ` New admission number ${admission} was assigned.`;

                if (armSource === "automatic" && classArm) message += ` Automatically placed in ${displayClass(classArm)}.`;
            }

            showToast(message, "success");

            dispatch("emis:student-saved", {
                student: savedStudent,
                admissionNumber: admission,
                admissionSource,
                classArm,
                armSource,
                editing: Boolean(editingAdmission)
            });

            await Promise.allSettled([
                loadSummary(),
                loadStudents(),
                loadLogs()
            ]);

        } catch (error) {
            console.error("Student save failed:", error);
            showToast(error.message || "Student could not be saved.", "error");

        } finally {
            setSaveStudentLoading(false);
        }
    }


    function setSaveStudentLoading(loading) {
        if (!els.saveStudentBtn) return;

        els.saveStudentBtn.disabled = Boolean(loading);

        const editing = Boolean(normalizeAdmission(els.editingAdmission?.value));

        if (loading) {
            els.saveStudentBtn.innerHTML = `
                <i class="fa-solid fa-spinner fa-spin"></i>
                <span>${editing ? "Saving..." : "Adding..."}</span>
            `;

            return;
        }

        els.saveStudentBtn.innerHTML = editing
            ? `<i class="fa-solid fa-floppy-disk"></i><span>Save Changes</span>`
            : `<i class="fa-solid fa-user-plus"></i><span>Add Student</span>`;
    }


    // =========================================================
    // BACKUP
    // =========================================================
    async function backupDatabase() {
        if (els.backupNowBtn) els.backupNowBtn.disabled = true;

        try {
            const data = await api("/api/promotion/backup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    reason: "manual_promotion_manager_backup"
                })
            });

            showToast(data.message, "success");
            await loadLogs();

        } catch (error) {
            showToast(error.message, "error");

        } finally {
            if (els.backupNowBtn) els.backupNowBtn.disabled = false;
        }
    }


    // =========================================================
    // EXPORT
    // =========================================================
    function exportCurrentClass(format) {
        const arm = els.classArmSelector?.value || "all";

        const params = new URLSearchParams({
            class: state.currentClass,
            format
        });

        if (arm !== "all") params.set("arm", arm);

        window.location.href = `/api/promotion/export?${params.toString()}`;
    }


    // =========================================================
    // LOGS
    // =========================================================
    async function loadLogs() {
        if (!els.logsList) return;

        try {
            const data = await api("/api/promotion/logs?limit=30");
            renderLogs(data.logs || []);

            return data;

        } catch (error) {
            els.logsList.innerHTML = `
                <div class="activity-empty">
                    <span class="empty-activity-icon"><i class="fa-solid fa-triangle-exclamation"></i></span>
                    <strong>Could not load activity</strong>
                    <span>${escapeHtml(error.message)}</span>
                </div>
            `;

            throw error;
        }
    }


    function renderLogs(logs) {
        if (!els.logsList) return;

        if (!logs.length) {
            els.logsList.innerHTML = `
                <div class="activity-empty">
                    <span class="empty-activity-icon"><i class="fa-solid fa-clock"></i></span>
                    <strong>No database activity yet</strong>
                    <span>Additions, promotions, repetitions, graduations and deletions will appear here.</span>
                </div>
            `;

            return;
        }

        els.logsList.innerHTML = logs.map((log) => {
            const icon = logIcon(log.Action);

            return `
                <article class="promotion-log-item">
                    <span class="promotion-log-icon"><i class="${icon}"></i></span>

                    <div class="promotion-log-copy">
                        <strong>${escapeHtml(formatAction(log.Action))}</strong>

                        <span>
                            ${escapeHtml(log.From || "—")} → ${escapeHtml(log.To || "—")}
                            • ${escapeHtml(log.Count || "0")} student${String(log.Count) === "1" ? "" : "s"}
                        </span>

                        ${log.Note ? `<p>${escapeHtml(log.Note)}</p>` : ""}
                    </div>

                    <div class="promotion-log-meta">
                        <strong>${escapeHtml(log.Admin || "Admin")}</strong>
                        <span>${escapeHtml(log.Timestamp || "")}</span>
                    </div>
                </article>
            `;
        }).join("");
    }


    function logIcon(action) {
        const value = normalize(action);

        if (value.includes("graduate")) return "fa-solid fa-graduation-cap";
        if (value.includes("promote")) return "fa-solid fa-arrow-up";
        if (value.includes("repeat")) return "fa-solid fa-rotate-left";
        if (value.includes("delete")) return "fa-solid fa-user-minus";
        if (value.includes("add")) return "fa-solid fa-user-plus";
        if (value.includes("edit")) return "fa-solid fa-pen";
        if (value.includes("backup")) return "fa-solid fa-database";

        return "fa-solid fa-clock-rotate-left";
    }


    // =========================================================
    // GENERIC CONFIRMATION
    // =========================================================
    function openConfirmation({ label, title, text, students = [], type = "primary", action }) {
        state.pendingAction = action;

        if (els.confirmModalLabel) els.confirmModalLabel.textContent = label;
        if (els.confirmModalTitle) els.confirmModalTitle.textContent = title;
        if (els.confirmText) els.confirmText.textContent = text;

        if (els.confirmModalIcon) {
            if (type === "danger") els.confirmModalIcon.innerHTML = `<i class="fa-solid fa-user-minus"></i>`;
            else if (type === "graduate") els.confirmModalIcon.innerHTML = `<i class="fa-solid fa-graduation-cap"></i>`;
            else if (type === "warning") els.confirmModalIcon.innerHTML = `<i class="fa-solid fa-rotate-left"></i>`;
            else els.confirmModalIcon.innerHTML = `<i class="fa-solid fa-arrow-up"></i>`;
        }

        if (els.confirmStudentList) {
            if (students.length) {
                els.confirmStudentList.classList.remove("hidden");

                els.confirmStudentList.innerHTML = students.slice(0, 8).map((student) => `
                    <div>
                        <strong>${escapeHtml(fullName(student))}</strong>
                        <span>${escapeHtml(student.Admission_number)} • ${escapeHtml(displayClass(student.Class))}</span>
                    </div>
                `).join("");

                if (students.length > 8) {
                    els.confirmStudentList.insertAdjacentHTML("beforeend", `
                        <div>
                            <strong>+${students.length - 8} more</strong>
                            <span>Additional selected students</span>
                        </div>
                    `);
                }

            } else {
                els.confirmStudentList.classList.add("hidden");
                els.confirmStudentList.innerHTML = "";
            }
        }

        els.confirmModal?.classList.remove("hidden");
    }


    function closeConfirmation() {
        if (!els.confirmModal || confirmationIsLoading()) return;

        els.confirmModal.classList.add("hidden");
        state.pendingAction = null;
    }


    function forceCloseConfirmation() {
        els.confirmModal?.classList.add("hidden");
        state.pendingAction = null;
    }


    async function runPendingAction() {
        if (typeof state.pendingAction !== "function") return;

        const action = state.pendingAction;

        setConfirmationLoading(true);

        try {
            await action();
        } finally {
            setConfirmationLoading(false);
        }
    }


    function setConfirmationLoading(loading) {
        const text = els.confirmActionBtn?.querySelector(".btn-text");
        const spinner = els.confirmActionBtn?.querySelector(".btn-spinner");

        if (els.confirmActionBtn) els.confirmActionBtn.disabled = loading;
        if (text) text.classList.toggle("hidden", loading);
        if (spinner) spinner.classList.toggle("hidden", !loading);
        if (loading && spinner) spinner.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
    }


    function confirmationIsLoading() {
        return Boolean(els.confirmActionBtn?.disabled);
    }


    // =========================================================
    // COLUMN MANAGER
    // =========================================================
    function toggleColumnMenu() {
        if (!els.columnMenu) return;

        const opening = els.columnMenu.classList.contains("hidden");

        els.columnMenu.classList.toggle("hidden", !opening);
        els.columnToggleBtn?.setAttribute("aria-expanded", opening ? "true" : "false");
    }


    function closeColumnMenu() {
        els.columnMenu?.classList.add("hidden");
        els.columnToggleBtn?.setAttribute("aria-expanded", "false");
    }


    function resetColumns() {
        state.visibleColumns = new Set(["student", "admission", "sex", "class", "category", "phone"]);

        els.columnMenu?.querySelectorAll('input[type="checkbox"][data-column]').forEach((checkbox) => {
            checkbox.checked = true;
        });

        applyColumnVisibility();
    }


    function applyColumnVisibility() {
        if (!els.studentsTable) return;

        ["student", "admission", "sex", "class", "category", "phone"].forEach((column) => {
            const visible = state.visibleColumns.has(column);

            els.studentsTable.querySelectorAll(`[data-column-name="${cssEscape(column)}"]`).forEach((cell) => {
                cell.classList.toggle("column-hidden", !visible);
            });
        });
    }


    // =========================================================
    // COMPACT TABLE
    // =========================================================
    function toggleCompactMode() {
        state.compact = !state.compact;

        els.studentsTable?.classList.toggle("compact", state.compact);
        els.toggleCompactBtn?.classList.toggle("active", state.compact);

        if (els.toggleCompactBtn) {
            els.toggleCompactBtn.innerHTML = state.compact
                ? `<i class="fa-solid fa-expand"></i><span>Normal</span>`
                : `<i class="fa-solid fa-compress"></i><span>Compact</span>`;
        }
    }


    // =========================================================
    // VOICE ENTRY
    // =========================================================
    function toggleVoiceEntry() {
        if (!els.startVoiceEntryBtn) return;

        if (state.listening) {
            stopVoiceEntry();
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            showToast("Voice entry is not supported by this browser. Chrome or Edge is recommended.", "warning");
            return;
        }

        const recognition = new SpeechRecognition();

        recognition.lang = "en-NG";
        recognition.continuous = false;
        recognition.interimResults = true;

        recognition.onstart = () => {
            state.listening = true;
            state.recognition = recognition;

            els.startVoiceEntryBtn?.classList.add("listening");

            if (els.voiceButtonText) els.voiceButtonText.textContent = "Stop Voice";
            if (els.voiceStatus) els.voiceStatus.classList.remove("hidden");
            if (els.voiceStatusText) els.voiceStatusText.textContent = "Listening... Speak the student's details.";
        };

        recognition.onresult = (event) => {
            let transcript = "";

            for (let index = event.resultIndex; index < event.results.length; index += 1) transcript += `${event.results[index][0].transcript} `;

            transcript = transcript.trim();

            if (els.voiceStatusText) els.voiceStatusText.textContent = transcript || "Listening...";

            const finalResult = Array.from(event.results).some((result) => result.isFinal);

            if (finalResult && transcript) applyVoiceTranscript(transcript);
        };

        recognition.onerror = (event) => {
            showToast(voiceErrorMessage(event.error), "warning");
            stopVoiceEntry();
        };

        recognition.onend = () => {
            state.listening = false;
            state.recognition = null;

            els.startVoiceEntryBtn?.classList.remove("listening");

            if (els.voiceButtonText) els.voiceButtonText.textContent = "Start Voice";

            if (els.voiceStatus && !els.voiceStatus.classList.contains("hidden")) setTimeout(hideVoiceStatus, 2500);
        };

        recognition.start();
    }


    function stopVoiceEntry() {
        if (state.recognition) {
            try {
                state.recognition.stop();
            } catch (_) {}
        }

        state.listening = false;
        state.recognition = null;

        els.startVoiceEntryBtn?.classList.remove("listening");

        if (els.voiceButtonText) els.voiceButtonText.textContent = "Start Voice";
    }


    function hideVoiceStatus() {
        els.voiceStatus?.classList.add("hidden");
    }


    function applyVoiceTranscript(transcript) {
        const text = String(transcript || "").trim();
        const normalizedText = ` ${text.replace(/[,:;]/g, " ")} `;

        const lastName = extractSpeechField(normalizedText, ["last name", "surname"], ["first name", "other names", "middle name", "phone", "sex", "gender", "class category", "class arm", "class"]);
        const firstName = extractSpeechField(normalizedText, ["first name"], ["last name", "surname", "other names", "middle name", "phone", "sex", "gender", "class category", "class arm", "class"]);
        const otherNames = extractSpeechField(normalizedText, ["other names", "middle name"], ["last name", "surname", "first name", "phone", "sex", "gender", "class category", "class arm", "class"]);
        const phone = extractSpeechField(normalizedText, ["phone number", "phone"], ["last name", "surname", "first name", "other names", "middle name", "sex", "gender", "class category", "class arm", "class"]);
        const sex = extractSpeechField(normalizedText, ["sex", "gender"], ["last name", "surname", "first name", "other names", "middle name", "phone", "class category", "class arm", "class"]);

        const classCategory = detectSpokenClassCategory(text);
        const classArm = detectSpokenClassArm(text, classCategory);

        if (lastName && els.formLastName) els.formLastName.value = titleCase(lastName);
        if (firstName && els.formFirstName) els.formFirstName.value = titleCase(firstName);
        if (otherNames && els.formOtherNames) els.formOtherNames.value = titleCase(otherNames);
        if (phone && els.formPhone) els.formPhone.value = normalizeSpokenPhone(phone);

        if (sex && els.formSex) {
            const sexValue = normalizeSexValue(sex);
            if (sexValue) els.formSex.value = sexValue;
        }

        if (classCategory && VALID_CLASSES.includes(classCategory)) {
            if (els.formClassCategory) els.formClassCategory.value = classCategory;
            populateFormClassArms(classCategory, classArm);
        }

        if (els.voiceStatus) els.voiceStatus.classList.remove("hidden");
        if (els.voiceStatusText) els.voiceStatusText.textContent = "Voice details captured. Review the fields carefully before saving.";

        showToast("Voice details captured. Please review spelling before saving.", "success");
    }


    function extractSpeechField(text, markers, stopMarkers) {
        const lower = text.toLowerCase();

        for (const marker of markers) {
            const start = lower.indexOf(` ${marker} `);

            if (start === -1) continue;

            const valueStart = start + marker.length + 2;
            let end = text.length;

            stopMarkers.forEach((stop) => {
                const position = lower.indexOf(` ${stop} `, valueStart);
                if (position !== -1 && position < end) end = position;
            });

            return text.slice(valueStart, end).trim();
        }

        return "";
    }


    function detectSpokenClassCategory(text) {
        const value = normalize(text).replace(/\s+/g, "");

        for (const className of VALID_CLASSES) {
            if (value.includes(className.toLowerCase())) return className;
        }

        return "";
    }


    function detectSpokenClassArm(text, classCategory) {
        if (!classCategory) return "";

        const value = normalize(text).replace(/\s+/g, "").replace(/and/g, "/");

        for (const arm of CLASS_ARMS[classCategory] || []) {
            const normalizedArm = normalize(arm).replace(/[_\s]/g, "");
            if (value.includes(normalizedArm)) return arm;
        }

        if (classCategory.startsWith("JSS")) {
            if (/\barm\s*a\b/i.test(text) || new RegExp(`${classCategory}\\s*a`, "i").test(text)) return `${classCategory}A`;
            if (/\barm\s*b\b/i.test(text) || new RegExp(`${classCategory}\\s*b`, "i").test(text)) return `${classCategory}B`;
            if (/\barm\s*c\b/i.test(text) || new RegExp(`${classCategory}\\s*c`, "i").test(text)) return `${classCategory}C`;
        }

        if (/gold/i.test(text)) return `${classCategory}_GOLD`;
        if (/silver/i.test(text)) return `${classCategory}_SILVER`;

        if (/diamond/i.test(text) && CLASS_ARMS[classCategory]?.includes(`${classCategory}_DIAMOND`)) return `${classCategory}_DIAMOND`;

        if (/\bb\s*(\/|and|&)\s*c\b/i.test(text) && CLASS_ARMS[classCategory]?.includes(`${classCategory}_B/C`)) return `${classCategory}_B/C`;

        return "";
    }


    function voiceErrorMessage(error) {
        if (error === "not-allowed") return "Microphone permission was denied.";
        if (error === "no-speech") return "No speech was detected.";
        if (error === "audio-capture") return "No microphone could be accessed.";

        return "Voice entry could not capture the student's details.";
    }


    // =========================================================
    // LOOKUP
    // =========================================================
    function findStudent(admission) {
        const key = normalizeAdmission(admission);

        return state.students.find((student) => normalizeAdmission(student.Admission_number) === key);
    }


    // =========================================================
    // MODALS
    // =========================================================
    function showModal(modal, overlay) {
        if (!modal) return;

        if (overlay) {
            overlay.classList.add("open");
            overlay.setAttribute("aria-hidden", "false");
        }

        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");

        document.body.classList.add("pm-modal-open");
    }


    function hideModal(modal, overlay) {
        if (modal) {
            modal.classList.remove("open");
            modal.setAttribute("aria-hidden", "true");
        }

        if (overlay) {
            overlay.classList.remove("open");
            overlay.setAttribute("aria-hidden", "true");
        }

        const anotherModalOpen = document.querySelector([
            ".student-details-modal.open",
            ".student-form-modal.open",
            ".pm-dialog-modal.open",
            ".action-preview-modal.open",
            ".graduates-modal.open"
        ].join(", "));

        if (!anotherModalOpen && els.confirmModal?.classList.contains("hidden")) document.body.classList.remove("pm-modal-open");
    }


    // =========================================================
    // HELPERS
    // =========================================================
    function fullName(student) {
        return [student?.Last_name, student?.First_name, student?.Other_names].filter(Boolean).join(" ").trim();
    }


    function displayClass(value) {
        return String(value || "").replaceAll("_", " ");
    }


    function normalizeAdmission(value) {
        return String(value || "").trim().toLowerCase();
    }


    function normalize(value) {
        return String(value || "").trim().toLowerCase();
    }


    function normalizeSexValue(value) {
        const sex = normalize(value);

        if (sex === "male" || sex === "m") return "Male";
        if (sex === "female" || sex === "f") return "Female";

        return "";
    }


    function normalizeSpokenPhone(value) {
        const replacements = {
            zero: "0", oh: "0", one: "1", two: "2", three: "3", four: "4",
            five: "5", six: "6", seven: "7", eight: "8", nine: "9"
        };

        return String(value || "").toLowerCase().split(/\s+/).map((part) => replacements[part] ?? part).join("").replace(/[^\d+]/g, "");
    }


    function titleCase(value) {
        return String(value || "").trim().toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
    }


    function formatAction(value) {
        return String(value || "ACTION").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
    }


    function cssEscape(value) {
        if (window.CSS?.escape) return window.CSS.escape(value);
        return String(value).replace(/["\\]/g, "\\$&");
    }


    function dispatch(name, detail = {}) {
        document.dispatchEvent(new CustomEvent(name, { detail }));
    }


    // =========================================================
    // TABLE PLACEHOLDERS
    // =========================================================
    function loadingRow(title, message) {
        return `
            <tr>
                <td colspan="8" class="table-placeholder">
                    <span class="table-placeholder-icon"><i class="fa-solid fa-spinner fa-spin"></i></span>
                    <strong>${escapeHtml(title)}</strong>
                    <span>${escapeHtml(message)}</span>
                </td>
            </tr>
        `;
    }


    function emptyRow(title, message) {
        return `
            <tr>
                <td colspan="8" class="table-placeholder">
                    <span class="table-placeholder-icon"><i class="fa-solid fa-users-slash"></i></span>
                    <strong>${escapeHtml(title)}</strong>
                    <span>${escapeHtml(message)}</span>
                </td>
            </tr>
        `;
    }


    function errorRow(title, message) {
        return `
            <tr>
                <td colspan="8" class="table-placeholder">
                    <span class="table-placeholder-icon"><i class="fa-solid fa-triangle-exclamation"></i></span>
                    <strong>${escapeHtml(title)}</strong>
                    <span>${escapeHtml(message)}</span>
                </td>
            </tr>
        `;
    }


    // =========================================================
    // TOASTS
    // =========================================================
    function showToast(message, type = "info") {
        if (!els.toastRoot) return;

        const toast = document.createElement("div");

        toast.className = `toast ${type}`;

        toast.innerHTML = `
            <span class="toast-icon"><i class="${toastIcon(type)}"></i></span>
            <span>${escapeHtml(message)}</span>
        `;

        els.toastRoot.appendChild(toast);

        requestAnimationFrame(() => toast.classList.add("show"));

        setTimeout(() => {
            toast.classList.remove("show");
            setTimeout(() => toast.remove(), 250);
        }, 3800);
    }


    function toastIcon(type) {
        if (type === "success") return "fa-solid fa-circle-check";
        if (type === "error") return "fa-solid fa-circle-exclamation";
        if (type === "warning") return "fa-solid fa-triangle-exclamation";

        return "fa-solid fa-circle-info";
    }


    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }


    // =========================================================
    // PUBLIC API FOR promotion.js
    // =========================================================
    window.EMISStudentDB = {
        VALID_CLASSES,
        CLASS_ARMS,
        state,

        api,
        refreshAll,
        loadSummary,
        loadStudents,
        loadLogs,

        changeClass,
        updateClassUI,
        updateClassArmFilter,

        selectedStudents,
        clearSelection,
        updateActionButtons,

        openStudentDetails,

        openConfirmation,
        closeConfirmation,
        forceCloseConfirmation,

        showModal,
        hideModal,
        showToast,

        fullName,
        displayClass,
        normalizeAdmission,
        normalize,
        escapeHtml
    };


    // =========================================================
    // READY EVENT
    // =========================================================
    dispatch("emis:student-database-ready", {
        api: window.EMISStudentDB
    });

});
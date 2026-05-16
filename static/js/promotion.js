// static/js/promotion.js
// EMIS Promotion Manager v4 — fixed loading + upgraded table manager

document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);

  const VALID_CLASSES = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3", "GRADUATED", "LEFT"];

  const els = {
    summaryGrid: $("summaryGrid"),
    fromClass: $("fromClass"),
    toClass: $("toClass"),
    destinationArm: $("destinationArm"),
    promotionMode: $("promotionMode"),
    statusFilter: $("statusFilter"),
    armFilter: $("armFilter"),
    pageSize: $("pageSize"),
    sortStudents: $("sortStudents"),

    refreshBtn: $("refreshBtn"),
    loadStudentsBtn: $("loadStudentsBtn"),
    selectAllBtn: $("selectAllBtn"),
    clearSelectionBtn: $("clearSelectionBtn"),
    previewPromotionBtn: $("previewPromotionBtn"),
    promoteBtn: $("promoteBtn"),
    deleteSelectedBtn: $("deleteSelectedBtn"),

    openAddStudentBtn: $("openAddStudentBtn"),
    openBulkEditBtn: $("openBulkEditBtn"),
    exportClassBtn: $("exportClassBtn"),
    backupNowBtn: $("backupNowBtn"),
    viewGraduatedBtn: $("viewGraduatedBtn"),
    viewLeftBtn: $("viewLeftBtn"),

    studentsBody: $("studentsBody"),
    studentSearch: $("studentSearch"),
    selectedBadge: $("selectedBadge"),
    tableStatusBadge: $("tableStatusBadge"),
    recordCountText: $("recordCountText"),
    currentViewText: $("currentViewText"),
    masterCheck: $("masterCheck"),
    prevPageBtn: $("prevPageBtn"),
    nextPageBtn: $("nextPageBtn"),
    pageInfo: $("pageInfo"),

    importForm: $("importForm"),
    csvFile: $("csvFile"),
    fileName: $("fileName"),

    logsList: $("logsList"),
    selectedPreviewList: $("selectedPreviewList"),

    confirmModal: $("confirmModal"),
    confirmText: $("confirmText"),
    cancelConfirmBtn: $("cancelConfirmBtn"),
    confirmActionBtn: $("confirmActionBtn"),

    previewModal: $("previewModal"),
    previewBody: $("previewBody"),
    closePreviewBtn: $("closePreviewBtn"),
    cancelPreviewBtn: $("cancelPreviewBtn"),
    confirmPreviewApplyBtn: $("confirmPreviewApplyBtn"),

    studentDetailsModal: $("studentDetailsModal"),
    studentDetailsBody: $("studentDetailsBody"),
    closeStudentDetailsBtn: $("closeStudentDetailsBtn"),
    closeDetailsActionBtn: $("closeDetailsActionBtn"),
    editFromDetailsBtn: $("editFromDetailsBtn"),

    studentFormModal: $("studentFormModal"),
    studentRecordForm: $("studentRecordForm"),
    studentFormTitle: $("studentFormTitle"),
    closeStudentFormBtn: $("closeStudentFormBtn"),
    cancelStudentFormBtn: $("cancelStudentFormBtn"),
    editingAdmission: $("editingAdmission"),
    formAdmission: $("formAdmission"),
    formLastName: $("formLastName"),
    formFirstName: $("formFirstName"),
    formOtherNames: $("formOtherNames"),
    formPhone: $("formPhone"),
    formClass: $("formClass"),
    formClassCategory: $("formClassCategory"),
    formStatus: $("formStatus")
  };

  const nextMap = {
    JSS1: "JSS2",
    JSS2: "JSS3",
    JSS3: "SS1",
    SS1: "SS2",
    SS2: "SS3",
    SS3: "GRADUATED"
  };

  let students = [];
  let selected = new Set();
  let currentPage = 1;
  let currentStudent = null;
  let pendingAction = null;

  init();

  function init() {
    forceDefaultClass();
    setDefaultDestination();
    bindEvents();
    refreshAll();
  }

  function forceDefaultClass() {
    if (els.fromClass && !els.fromClass.value) els.fromClass.value = "JSS1";
    if (els.toClass && !els.toClass.value) els.toClass.value = nextMap[els.fromClass.value] || "JSS2";
    if ($("targetClass") && !$("targetClass").value) $("targetClass").value = "JSS1";
  }

  function bindEvents() {
    els.refreshBtn?.addEventListener("click", () => refreshAll());
    els.loadStudentsBtn?.addEventListener("click", () => loadStudents());

    els.fromClass?.addEventListener("change", () => {
      if (!els.fromClass.value) els.fromClass.value = "JSS1";
      setDefaultDestination();
      clearSelection(false);
      loadStudents();
    });

    els.toClass?.addEventListener("change", () => {
      if (!els.toClass.value) setDefaultDestination();
    });

    [els.statusFilter, els.armFilter, els.pageSize, els.sortStudents].forEach((el) => {
      el?.addEventListener("change", () => {
        currentPage = 1;
        renderStudents();
      });
    });

    els.studentSearch?.addEventListener("input", () => {
      currentPage = 1;
      renderStudents();
    });

    els.selectAllBtn?.addEventListener("click", () => selectAllVisible());
    els.clearSelectionBtn?.addEventListener("click", () => clearSelection());
    els.previewPromotionBtn?.addEventListener("click", () => openPreview());
    els.promoteBtn?.addEventListener("click", () => openPromotionConfirm());
    els.deleteSelectedBtn?.addEventListener("click", () => openDeleteConfirm());

    els.masterCheck?.addEventListener("change", () => {
      els.masterCheck.checked ? selectAllVisible() : clearSelection();
    });

    els.prevPageBtn?.addEventListener("click", () => {
      currentPage = Math.max(1, currentPage - 1);
      renderStudents();
    });

    els.nextPageBtn?.addEventListener("click", () => {
      currentPage += 1;
      renderStudents();
    });

    els.openAddStudentBtn?.addEventListener("click", () => openStudentForm());
    els.openBulkEditBtn?.addEventListener("click", () => openBulkEdit());
    els.exportClassBtn?.addEventListener("click", () => exportCurrentClass());
    els.backupNowBtn?.addEventListener("click", () => backupCurrentClass());
    els.viewGraduatedBtn?.addEventListener("click", () => loadSpecialClass("GRADUATED"));
    els.viewLeftBtn?.addEventListener("click", () => loadSpecialClass("LEFT"));

    els.cancelConfirmBtn?.addEventListener("click", () => closeConfirm());
    els.confirmActionBtn?.addEventListener("click", () => runPendingAction());

    els.confirmModal?.addEventListener("click", (event) => {
      if (event.target === els.confirmModal) closeConfirm();
    });

    els.closePreviewBtn?.addEventListener("click", () => closePreview());
    els.cancelPreviewBtn?.addEventListener("click", () => closePreview());
    els.confirmPreviewApplyBtn?.addEventListener("click", () => {
      closePreview();
      openPromotionConfirm();
    });

    els.closeStudentDetailsBtn?.addEventListener("click", () => closeStudentDetails());
    els.closeDetailsActionBtn?.addEventListener("click", () => closeStudentDetails());
    els.editFromDetailsBtn?.addEventListener("click", () => {
      if (currentStudent) {
        closeStudentDetails();
        openStudentForm(currentStudent);
      }
    });

    els.closeStudentFormBtn?.addEventListener("click", () => closeStudentForm());
    els.cancelStudentFormBtn?.addEventListener("click", () => closeStudentForm());
    els.studentRecordForm?.addEventListener("submit", saveStudentRecord);

    els.csvFile?.addEventListener("change", () => {
      const file = els.csvFile.files?.[0];
      els.fileName.textContent = file ? file.name : "No file selected";
    });

    els.importForm?.addEventListener("submit", handleImport);
  }

  function setDefaultDestination() {
    if (!els.fromClass || !els.toClass) return;
    els.toClass.value = nextMap[els.fromClass.value] || "JSS2";
  }

  async function refreshAll() {
    await loadSummary();
    await loadStudents();
    await loadLogs();
  }

  async function api(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));

    if (!response.ok || data.success === false) {
      throw new Error(data.message || "Request failed.");
    }

    return data;
  }

  async function loadSummary() {
    try {
      const data = await api("/api/promotion/summary");
      renderSummary(data.summary || {});
    } catch (error) {
      els.summaryGrid.innerHTML = `
        <article class="summary-card loading-card">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>${escapeHtml(error.message)}</span>
        </article>
      `;
    }
  }

  function renderSummary(summary) {
    const order = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3", "GRADUATED", "LEFT"];

    els.summaryGrid.innerHTML = order.map((cls) => {
      const item = summary[cls] || { total: 0, active: 0 };

      return `
        <article class="summary-card" data-class="${cls}">
          <span>${escapeHtml(cls)}</span>
          <strong>${item.total || 0}</strong>
          <span>${["GRADUATED", "LEFT"].includes(cls) ? "Records" : `Active: ${item.active || 0}`}</span>
        </article>
      `;
    }).join("");

    document.querySelectorAll(".summary-card[data-class]").forEach((card) => {
      card.addEventListener("click", () => loadSpecialClass(card.dataset.class));
    });
  }

  async function loadSpecialClass(cls) {
    if (!VALID_CLASSES.includes(cls)) cls = "JSS1";

    if (["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"].includes(cls) && els.fromClass) {
      els.fromClass.value = cls;
      setDefaultDestination();
    }

    selected.clear();
    currentPage = 1;
    await loadStudents(cls);
  }

  function resolveClass(value) {
    if (typeof value === "string" && VALID_CLASSES.includes(value)) return value;

    const selectedClass = els.fromClass?.value || "JSS1";

    if (VALID_CLASSES.includes(selectedClass)) return selectedClass;

    return "JSS1";
  }

  async function loadStudents(forcedClass = "") {
    const cls = resolveClass(forcedClass);

    setTableStatus("Loading...");
    els.studentsBody.innerHTML = skeletonRows();

    try {
      const data = await api(`/api/promotion/students?class=${encodeURIComponent(cls)}`);

      students = Array.isArray(data.students) ? data.students : [];
      selected.clear();
      currentPage = 1;

      renderStudents();
      updateSelectedBadge();
      updateSelectedPreview();
      setTableStatus(`${students.length} loaded`);
    } catch (error) {
      students = [];
      els.studentsBody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-cell">
            <i class="fa-solid fa-triangle-exclamation"></i>
            <strong>Could not load students</strong>
            <span>${escapeHtml(error.message)}</span>
          </td>
        </tr>
      `;
      setTableStatus("Error");
      updateTableInfo(0, 0);
    }
  }

  function getFilteredStudents() {
    const query = normalize(els.studentSearch?.value || "");
    const status = normalize(els.statusFilter?.value || "");
    const arm = normalize(els.armFilter?.value || "");
    const sort = els.sortStudents?.value || "name";

    const list = students.filter((student) => {
      const studentStatus = normalize(student.Status || "ACTIVE");
      const studentClass = normalize(student.Class || "");

      const text = normalize([
        student.Admission_number,
        student.Last_name,
        student.First_name,
        student.Other_names,
        student.Phone,
        student.Class,
        student.Class_category,
        student.Status || "ACTIVE"
      ].join(" "));

      const statusOk = !status || studentStatus === status;
      const armOk = !arm || studentClass.endsWith(arm);
      const searchOk = !query || text.includes(query);

      return statusOk && armOk && searchOk;
    });

    list.sort((a, b) => sortValue(a, sort).localeCompare(sortValue(b, sort)));

    return list;
  }

  function sortValue(student, sort) {
    if (sort === "admission") return normalize(student.Admission_number);
    if (sort === "class") return normalize(student.Class);
    if (sort === "status") return normalize(student.Status || "ACTIVE");

    return normalize(`${student.Last_name} ${student.First_name} ${student.Other_names}`);
  }

  function renderStudents() {
    const filtered = getFilteredStudents();
    const pageSize = Number(els.pageSize?.value || 25);
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));

    currentPage = Math.min(currentPage, totalPages);

    const start = (currentPage - 1) * pageSize;
    const pageRows = filtered.slice(start, start + pageSize);

    updateTableInfo(filtered.length, students.length);

    if (!pageRows.length) {
      els.studentsBody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-cell">
            <i class="fa-solid fa-folder-open"></i>
            <strong>No students found</strong>
            <span>No student matches your current view.</span>
          </td>
        </tr>
      `;
      updatePagination(totalPages);
      return;
    }

    els.studentsBody.innerHTML = pageRows.map((student) => studentRow(student)).join("");

    bindStudentRows();
    updatePagination(totalPages);
    updateSelectedPreview();
  }

  function studentRow(student) {
    const admission = student.Admission_number || "";
    const key = admission.toLowerCase();
    const fullName = [student.Last_name, student.First_name, student.Other_names].filter(Boolean).join(" ");
    const status = student.Status || "ACTIVE";

    return `
      <tr class="${selected.has(key) ? "is-selected" : ""}">
        <td>
          <input
            type="checkbox"
            class="student-check"
            data-admission="${escapeHtml(admission)}"
            ${selected.has(key) ? "checked" : ""}
          >
        </td>

        <td>
          <div class="student-name">${escapeHtml(fullName || "Unknown Student")}</div>
          <div class="student-sub">${escapeHtml(student.Last_name || "")} ${escapeHtml(student.First_name || "")}</div>
        </td>

        <td>${escapeHtml(admission || "—")}</td>
        <td>${escapeHtml(student.Class || "—")}</td>
        <td><span class="status-pill ${escapeHtml(status.toLowerCase())}">${escapeHtml(status)}</span></td>
        <td>${escapeHtml(student.Phone || "—")}</td>

        <td>
          <div class="row-actions">
            <button class="row-action-btn view-student" data-admission="${escapeHtml(admission)}" title="View">
              <i class="fa-solid fa-eye"></i>
            </button>

            <button class="row-action-btn edit-student" data-admission="${escapeHtml(admission)}" title="Edit">
              <i class="fa-solid fa-pen"></i>
            </button>

            <button class="row-action-btn danger delete-student" data-admission="${escapeHtml(admission)}" title="Delete">
              <i class="fa-solid fa-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }

  function bindStudentRows() {
    document.querySelectorAll(".student-check").forEach((box) => {
      box.addEventListener("change", () => {
        const key = String(box.dataset.admission || "").toLowerCase();

        if (box.checked) selected.add(key);
        else selected.delete(key);

        updateSelectedBadge();
        updateSelectedPreview();
        renderStudents();
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
        selected.clear();
        selected.add(String(button.dataset.admission || "").toLowerCase());
        updateSelectedBadge();
        openDeleteConfirm();
      });
    });
  }

  function findStudent(admission) {
    const key = String(admission || "").toLowerCase();
    return students.find((student) => String(student.Admission_number || "").toLowerCase() === key);
  }

  function selectAllVisible() {
    getFilteredStudents().forEach((student) => {
      if (student.Admission_number) selected.add(String(student.Admission_number).toLowerCase());
    });

    updateSelectedBadge();
    updateSelectedPreview();
    renderStudents();
  }

  function clearSelection(shouldRender = true) {
    selected.clear();

    if (els.masterCheck) els.masterCheck.checked = false;

    updateSelectedBadge();
    updateSelectedPreview();

    if (shouldRender) renderStudents();
  }

  function updateSelectedBadge() {
    if (els.selectedBadge) els.selectedBadge.textContent = `${selected.size} selected`;
  }

  function updateSelectedPreview() {
    if (!els.selectedPreviewList) return;

    const selectedRows = students.filter((student) =>
      selected.has(String(student.Admission_number || "").toLowerCase())
    );

    if (!selectedRows.length) {
      els.selectedPreviewList.innerHTML = `
        <div class="log-empty">
          <i class="fa-solid fa-user-check"></i>
          No selected student yet.
        </div>
      `;
      return;
    }

    const visible = selectedRows.slice(0, 8);

    els.selectedPreviewList.innerHTML = visible.map((student) => `
      <div class="selected-preview-item">
        <strong>${escapeHtml([student.Last_name, student.First_name, student.Other_names].filter(Boolean).join(" "))}</strong>
        <p>${escapeHtml(student.Admission_number)} • ${escapeHtml(student.Class)}</p>
        <span>${escapeHtml(student.Status || "ACTIVE")}</span>
      </div>
    `).join("") + (
      selectedRows.length > 8
        ? `<div class="log-empty">+${selectedRows.length - 8} more selected</div>`
        : ""
    );
  }

  function updatePagination(totalPages) {
    if (els.pageInfo) els.pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;

    if (els.prevPageBtn) els.prevPageBtn.disabled = currentPage <= 1;
    if (els.nextPageBtn) els.nextPageBtn.disabled = currentPage >= totalPages;
  }

  function updateTableInfo(filtered, total) {
    if (els.recordCountText) {
      els.recordCountText.innerHTML = `<i class="fa-solid fa-list"></i> ${filtered} of ${total} records`;
    }

    if (els.currentViewText) {
      els.currentViewText.innerHTML = `<i class="fa-solid fa-filter"></i> ${filterLabel()}`;
    }
  }

  function filterLabel() {
    const parts = [];

    if (els.studentSearch?.value) parts.push("Search");
    if (els.statusFilter?.value) parts.push(els.statusFilter.value);
    if (els.armFilter?.value) parts.push(`Arm ${els.armFilter.value}`);

    return parts.length ? parts.join(" • ") : "No active filter";
  }

  function setTableStatus(text) {
    if (els.tableStatusBadge) els.tableStatusBadge.textContent = text;
  }

  function openPreview() {
    const rows = selectedRows();

    if (!rows.length && els.promotionMode.value !== "all") {
      showToast("Please select at least one student.", "warning");
      return;
    }

    const count = els.promotionMode.value === "all" ? students.length : rows.length;

    els.previewBody.innerHTML = `
      <div class="pm-details-grid">
        <div class="pm-detail-item"><span>From</span><strong>${escapeHtml(els.fromClass.value)}</strong></div>
        <div class="pm-detail-item"><span>To</span><strong>${escapeHtml(els.toClass.value)}</strong></div>
        <div class="pm-detail-item"><span>Mode</span><strong>${escapeHtml(els.promotionMode.value)}</strong></div>
        <div class="pm-detail-item"><span>Students</span><strong>${count}</strong></div>
      </div>
    `;

    els.previewModal?.classList.remove("hidden");
  }

  function closePreview() {
    els.previewModal?.classList.add("hidden");
  }

  function selectedRows() {
    return students.filter((student) =>
      selected.has(String(student.Admission_number || "").toLowerCase())
    );
  }

  function openPromotionConfirm() {
    const mode = els.promotionMode.value;
    const count = mode === "all" ? students.length : selected.size;

    if (!els.fromClass.value || !els.toClass.value) {
      showToast("Please choose source and destination class.", "warning");
      return;
    }

    if (!students.length) {
      showToast("No students loaded.", "warning");
      return;
    }

    if (mode !== "all" && !selected.size) {
      showToast("Please select at least one student.", "warning");
      return;
    }

    els.confirmText.textContent =
      `Move ${count} student(s) from ${els.fromClass.value} to ${els.toClass.value}? A backup will be created first.`;

    pendingAction = applyPromotion;
    els.confirmModal.classList.remove("hidden");
  }

  function openDeleteConfirm() {
    if (!selected.size) {
      showToast("Please select student(s) to delete.", "warning");
      return;
    }

    els.confirmText.textContent =
      `Delete ${selected.size} selected student record(s)? A backup will be created first.`;

    pendingAction = deleteSelectedStudents;
    els.confirmModal.classList.remove("hidden");
  }

  function closeConfirm() {
    els.confirmModal.classList.add("hidden");
    pendingAction = null;
  }

  async function runPendingAction() {
    if (typeof pendingAction === "function") await pendingAction();
  }

  async function applyPromotion() {
    setConfirmLoading(true);

    try {
      const data = await api("/api/promotion/promote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_class: els.fromClass.value,
          to_class: els.toClass.value,
          mode: els.promotionMode.value,
          destination_arm: els.destinationArm.value.trim(),
          admissions: Array.from(selected),
          note: "Promotion Manager action"
        })
      });

      showToast(data.message, "success");
      closeConfirm();
      await refreshAll();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setConfirmLoading(false);
    }
  }

  async function deleteSelectedStudents() {
    setConfirmLoading(true);

    try {
      const data = await api("/api/promotion/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          class_category: els.fromClass.value,
          admissions: Array.from(selected)
        })
      });

      showToast(data.message, "success");
      closeConfirm();
      await refreshAll();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setConfirmLoading(false);
    }
  }

  function setConfirmLoading(loading) {
    els.confirmActionBtn.disabled = loading;
    els.confirmActionBtn.textContent = loading ? "Processing..." : "Yes, Continue";
  }

  function openStudentDetails(student) {
    currentStudent = student;

    els.studentDetailsBody.innerHTML = `
      <div class="pm-details-grid">
        <div class="pm-detail-item"><span>Admission</span><strong>${escapeHtml(student.Admission_number)}</strong></div>
        <div class="pm-detail-item"><span>Full Name</span><strong>${escapeHtml([student.Last_name, student.First_name, student.Other_names].filter(Boolean).join(" "))}</strong></div>
        <div class="pm-detail-item"><span>Class</span><strong>${escapeHtml(student.Class)}</strong></div>
        <div class="pm-detail-item"><span>Category</span><strong>${escapeHtml(student.Class_category)}</strong></div>
        <div class="pm-detail-item"><span>Status</span><strong>${escapeHtml(student.Status || "ACTIVE")}</strong></div>
        <div class="pm-detail-item"><span>Phone</span><strong>${escapeHtml(student.Phone || "—")}</strong></div>
      </div>
    `;

    els.studentDetailsModal.classList.remove("hidden");
  }

  function closeStudentDetails() {
    els.studentDetailsModal.classList.add("hidden");
    currentStudent = null;
  }

  function openStudentForm(student = null) {
    els.studentRecordForm.reset();

    if (student) {
      els.studentFormTitle.textContent = "Edit Student";
      els.editingAdmission.value = student.Admission_number || "";
      els.formAdmission.value = student.Admission_number || "";
      els.formLastName.value = student.Last_name || "";
      els.formFirstName.value = student.First_name || "";
      els.formOtherNames.value = student.Other_names || "";
      els.formPhone.value = student.Phone || "";
      els.formClass.value = student.Class || "";
      els.formClassCategory.value = student.Class_category || els.fromClass.value || "JSS1";
      els.formStatus.value = student.Status || "ACTIVE";
    } else {
      els.studentFormTitle.textContent = "Add Student";
      els.editingAdmission.value = "";
      els.formClassCategory.value = els.fromClass.value || "JSS1";
      els.formClass.value = `${els.formClassCategory.value}A`;
      els.formStatus.value = "ACTIVE";
    }

    els.studentFormModal.classList.remove("hidden");
  }

  function closeStudentForm() {
    els.studentFormModal.classList.add("hidden");
  }

  async function saveStudentRecord(event) {
    event.preventDefault();

    try {
      const payload = {
        original_admission: els.editingAdmission.value,
        student: {
          Admission_number: els.formAdmission.value.trim(),
          Last_name: els.formLastName.value.trim(),
          First_name: els.formFirstName.value.trim(),
          Other_names: els.formOtherNames.value.trim(),
          Phone: els.formPhone.value.trim(),
          Class: els.formClass.value.trim(),
          Class_category: els.formClassCategory.value,
          Status: els.formStatus.value
        }
      };

      const data = await api("/api/promotion/student/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      showToast(data.message, "success");
      closeStudentForm();

      if (els.fromClass) els.fromClass.value = payload.student.Class_category;

      await refreshAll();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  function openBulkEdit() {
    if (!selected.size) {
      showToast("Select students first before bulk edit.", "warning");
      return;
    }

    showToast("Bulk edit ready. Use the destination/mode controls to move selected records.", "info");
  }

  function exportCurrentClass() {
    const cls = resolveClass();
    window.location.href = `/api/promotion/export?class=${encodeURIComponent(cls)}`;
  }

  async function backupCurrentClass() {
    try {
      const data = await api("/api/promotion/backup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ class_category: resolveClass() })
      });

      showToast(data.message, "success");
      await loadLogs();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  async function handleImport(event) {
    event.preventDefault();

    if (!els.csvFile.files?.length) {
      showToast("Please choose a CSV file.", "warning");
      return;
    }

    const formData = new FormData(els.importForm);

    try {
      const data = await api("/api/promotion/import", {
        method: "POST",
        body: formData
      });

      showToast(data.message, "success");
      els.importForm.reset();
      els.fileName.textContent = "No file selected";
      await refreshAll();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  async function loadLogs() {
    try {
      const data = await api("/api/promotion/logs");
      renderLogs(data.logs || []);
    } catch (error) {
      els.logsList.innerHTML = `<div class="log-empty">${escapeHtml(error.message)}</div>`;
    }
  }

  function renderLogs(logs) {
    if (!logs.length) {
      els.logsList.innerHTML = `
        <div class="log-empty">
          <i class="fa-solid fa-clock"></i>
          No promotion action yet.
        </div>
      `;
      return;
    }

    els.logsList.innerHTML = logs.map((log) => `
      <div class="log-item">
        <strong>${escapeHtml(log.Action || "ACTION")}</strong>
        <p>${escapeHtml(log.From || "—")} → ${escapeHtml(log.To || "—")} • ${escapeHtml(log.Count || "0")} student(s)</p>
        <span>${escapeHtml(log.Timestamp || "")} by ${escapeHtml(log.Admin || "Admin")}</span>
      </div>
    `).join("");
  }

  function skeletonRows() {
    return Array.from({ length: 6 }).map(() => `
      <tr>
        <td colspan="7"><div class="table-skeleton"></div></td>
      </tr>
    `).join("");
  }

  function showToast(message, type = "info") {
    const root = document.getElementById("toastRoot");
    const toast = document.createElement("div");

    toast.className = `toast ${type}`;
    toast.textContent = message;

    root.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px) scale(0.96)";
      setTimeout(() => toast.remove(), 250);
    }, 3600);
  }

  function normalize(value) {
    return String(value || "").toLowerCase().trim();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
});
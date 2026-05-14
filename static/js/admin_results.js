// static/js/admin_results.js

document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);

  const yearSelector = $("yearSelector");
  const classSelector = $("classSelector");
  const subjectSelector = $("subjectSelector");
  const statusFilter = $("statusFilter");
  const globalSearch = $("globalSearch");

  const reloadTableBtn = $("reloadTableBtn");
  const clearFiltersBtn = $("clearFiltersBtn");
  const deleteSelectedBtn = $("deleteSelectedBtn");
  const printSelectedBtn = $("printSelectedBtn");
  const exportAllExcelBtn = $("exportAllExcelBtn");
  const exportCsvBtn = $("exportCsvBtn");
  const printAllPdfBtn = $("printAllPdfBtn");
  const toggleCompactBtn = $("toggleCompactBtn");

  const resultsTable = $("resultsTable");
  const resultsBody = $("resultsBody");
  const selectAllRows = $("selectAllRows");
  const selectedCountBadge = $("selectedCountBadge");
  const tableSubtitle = $("tableSubtitle");
  const paginationInfo = $("paginationInfo");
  const pagination = $("pagination");

  const deleteModal = $("deleteModal");
  const cancelDeleteBtn = $("cancelDeleteBtn");
  const confirmDeleteBtn = $("confirmDeleteBtn");

  const summaryOverlay = $("summaryOverlay");
  const adminPrintSummary = $("adminPrintSummary");
  const summaryCloseBtn = $("summaryCloseBtn");

  let allResults = [];
  let filteredResults = [];
  let selectedKeys = new Set();
  let currentPage = 1;
  const rowsPerPage = 15;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function normalizeText(value) {
    return String(value ?? "").toLowerCase().trim();
  }

  function formatSubject(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .toUpperCase();
  }

  function getScore(row) {
    const raw = row["Score (%)"] ?? row["Score Number"] ?? row.score ?? 0;
    const clean = String(raw).replace("%", "").trim();
    const score = Number.parseFloat(clean);
    return Number.isFinite(score) ? score : 0;
  }

  function getStatus(row) {
    const status = String(row.Status ?? row.status ?? "").toUpperCase().trim();

    if (status === "PASS" || status === "FAIL") {
      return status;
    }

    return getScore(row) >= 50 ? "PASS" : "FAIL";
  }

  function getStudentName(row) {
    return row["Student Name"] || row.full_name || "Unknown Student";
  }

  function getAdmission(row) {
    return row["Admission No"] || row.admission_number || row.student_id || "";
  }

  function getYear(row) {
    return row.Year || row.year || "";
  }

  function getClass(row) {
    return row.Class || row["Class Category"] || row.class_category || row.class_name || "";
  }

  function getClassCategory(row) {
    return row["Class Category"] || row.Class || row.class_category || row.class_name || "";
  }

  function getSubject(row) {
    return row.Subject || row["Subject Folder"] || row.subject || "";
  }

  function getSubjectFolder(row) {
    return row["Subject Folder"] || row.Subject || row.subject || "";
  }

  function getCorrect(row) {
    return row.Correct ?? row.correct ?? 0;
  }

  function getTotal(row) {
    return row.Total ?? row.total ?? 0;
  }

  function getTime(row) {
    return row["Time Taken"] ?? row.time_taken ?? row.timeTaken ?? "";
  }

  function getSubmittedAt(row) {
    return row["Submitted At"] ?? row.submitted_at ?? row.submittedAt ?? "";
  }

  function getStableKey(row) {
    return [
      getYear(row),
      getClassCategory(row),
      getSubjectFolder(row),
      getAdmission(row),
      getStudentName(row),
      getSubmittedAt(row)
    ].join("::").toUpperCase();
  }

  function initials(name) {
    const parts = String(name || "").split(" ").filter(Boolean);

    if (!parts.length) return "?";

    return parts.slice(0, 2).map((p) => p[0]).join("").toUpperCase();
  }

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add("show"), 30);

    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 350);
    }, 3200);
  }

  function setLoading(message = "Loading results...") {
    resultsBody.innerHTML = `
      <tr>
        <td colspan="11" class="table-placeholder">
          <i class="fa-solid fa-spinner fa-spin"></i>
          <strong>${escapeHtml(message)}</strong>
          <span>Please wait while EMIS scans all result files.</span>
        </td>
      </tr>
    `;
  }

  function setEmpty(message = "No results found", sub = "No student result matches the current view.") {
    resultsBody.innerHTML = `
      <tr>
        <td colspan="11" class="table-placeholder">
          <i class="fa-solid fa-folder-open"></i>
          <strong>${escapeHtml(message)}</strong>
          <span>${escapeHtml(sub)}</span>
        </td>
      </tr>
    `;
  }

  async function loadAllResults() {
    setLoading("Loading all written exam results");

    selectedKeys.clear();
    updateSelectedBadge();

    const year = yearSelector?.value || "all";
    const cls = classSelector?.value || "all";

    const url = `/api/results/all?year=${encodeURIComponent(year)}&class=${encodeURIComponent(cls)}&subject=all`;

    try {
      const res = await fetch(url, {
        headers: {
          Accept: "application/json"
        }
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Could not load results");
      }

      allResults = Array.isArray(data.results) ? data.results : [];

      buildSubjectDropdown();
      applyFilters();

      showToast(`${allResults.length} result(s) loaded successfully.`, "success");
    } catch (error) {
      console.error(error);
      allResults = [];
      filteredResults = [];

      setEmpty("Could not load results", error.message || "Please check your backend route.");
      updateStats([]);
      renderCharts([]);

      showToast(error.message || "Failed to load results.", "error");
    }
  }

  function buildSubjectDropdown() {
    if (!subjectSelector) return;

    const currentValue = subjectSelector.value || "all";

    const subjects = Array.from(
      new Set(
        allResults
          .map((row) => getSubjectFolder(row))
          .filter(Boolean)
      )
    ).sort();

    subjectSelector.innerHTML = `<option value="all">All Subjects</option>`;

    subjects.forEach((subject) => {
      const option = document.createElement("option");
      option.value = subject;
      option.textContent = formatSubject(subject);
      subjectSelector.appendChild(option);
    });

    const exists = [...subjectSelector.options].some((option) => option.value === currentValue);
    subjectSelector.value = exists ? currentValue : "all";
  }

  function applyFilters() {
    const year = normalizeText(yearSelector?.value || "all");
    const cls = normalizeText(classSelector?.value || "all");
    const subject = normalizeText(subjectSelector?.value || "all");
    const status = normalizeText(statusFilter?.value || "");
    const query = normalizeText(globalSearch?.value || "");

    filteredResults = allResults.filter((row) => {
      const rowYear = normalizeText(getYear(row));
      const rowClass = normalizeText(getClass(row));
      const rowClassCategory = normalizeText(getClassCategory(row));
      const rowSubject = normalizeText(getSubject(row));
      const rowSubjectFolder = normalizeText(getSubjectFolder(row));
      const rowStatus = normalizeText(getStatus(row));

      const searchableText = normalizeText([
        getStudentName(row),
        getAdmission(row),
        getYear(row),
        getClass(row),
        getClassCategory(row),
        getSubject(row),
        getSubjectFolder(row),
        getScore(row),
        getStatus(row),
        getTime(row),
        getSubmittedAt(row)
      ].join(" "));

      const yearOk = year === "all" || rowYear === year;
      const classOk = cls === "all" || rowClass === cls || rowClassCategory === cls;
      const subjectOk = subject === "all" || rowSubject === subject || rowSubjectFolder === subject;
      const statusOk = !status || rowStatus === status;
      const searchOk = !query || searchableText.includes(query);

      return yearOk && classOk && subjectOk && statusOk && searchOk;
    });

    currentPage = 1;
    selectedKeys.clear();
    updateSelectedBadge();

    renderTable();
    updateStats(filteredResults);
    renderCharts(filteredResults);
  }

  function renderTable() {
    if (!filteredResults.length) {
      setEmpty();
      pagination.innerHTML = "";
      paginationInfo.textContent = "Showing 0 results";
      tableSubtitle.textContent = "No result matches your current filters.";
      return;
    }

    const totalPages = Math.ceil(filteredResults.length / rowsPerPage);
    currentPage = Math.min(currentPage, totalPages);

    const start = (currentPage - 1) * rowsPerPage;
    const end = start + rowsPerPage;
    const pageRows = filteredResults.slice(start, end);

    resultsBody.innerHTML = pageRows.map((row, pageIndex) => {
      const absoluteIndex = start + pageIndex;
      const key = getStableKey(row);

      const name = getStudentName(row);
      const admission = getAdmission(row);
      const year = getYear(row);
      const cls = getClass(row);
      const subject = formatSubject(getSubject(row));
      const score = getScore(row);
      const correct = getCorrect(row);
      const total = getTotal(row);
      const status = getStatus(row);
      const time = getTime(row);
      const date = getSubmittedAt(row);

      return `
        <tr>
          <td>
            <input type="checkbox" class="row-check" data-key="${escapeHtml(key)}" ${selectedKeys.has(key) ? "checked" : ""}>
          </td>

          <td>
            <div class="student-cell">
              <div class="student-avatar">${escapeHtml(initials(name))}</div>
              <div>
                <span class="student-name">${escapeHtml(name)}</span>
                <span class="student-sub">${escapeHtml(admission || "No admission no")}</span>
              </div>
            </div>
          </td>

          <td><span class="badge-soft">${escapeHtml(admission || "—")}</span></td>
          <td><span class="badge-soft">${escapeHtml(year || "—")}</span></td>
          <td><span class="badge-soft">${escapeHtml(cls || "—")}</span></td>
          <td>${escapeHtml(subject || "—")}</td>

          <td>
            <div class="score-badges">
              <span class="badge-percent">${score}%</span>
              <span class="badge-raw">${escapeHtml(correct)}/${escapeHtml(total)}</span>
              ${score >= 80 ? `<span class="badge-excellence"><i class="fa-solid fa-star"></i> Excellent</span>` : ""}
            </div>
          </td>

          <td>
            <span class="status-pill ${status === "PASS" ? "status-pass" : "status-fail"}">
              <i class="fa-solid ${status === "PASS" ? "fa-check" : "fa-xmark"}"></i>
              ${escapeHtml(status)}
            </span>
          </td>

          <td>${escapeHtml(time || "—")}</td>
          <td>${escapeHtml(date || "—")}</td>

          <td>
            <button class="btn btn-light tiny view-result-btn" data-index="${absoluteIndex}">
              <i class="fa-solid fa-eye"></i> View
            </button>
          </td>
        </tr>
      `;
    }).join("");

    tableSubtitle.textContent = "Showing results across JSS1–SS3 and SS1–SS3.";
    paginationInfo.textContent = `Showing ${start + 1}-${Math.min(end, filteredResults.length)} of ${filteredResults.length} result(s)`;

    renderPagination(totalPages);
    bindRowEvents();
  }

  function renderPagination(totalPages) {
    pagination.innerHTML = "";

    if (totalPages <= 1) return;

    const prev = document.createElement("button");
    prev.className = "page-btn";
    prev.innerHTML = "&laquo;";
    prev.disabled = currentPage === 1;
    prev.addEventListener("click", () => {
      if (currentPage > 1) {
        currentPage--;
        renderTable();
      }
    });
    pagination.appendChild(prev);

    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || Math.abs(i - currentPage) <= 2) {
        const btn = document.createElement("button");
        btn.className = `page-btn ${i === currentPage ? "active" : ""}`;
        btn.textContent = i;
        btn.addEventListener("click", () => {
          currentPage = i;
          renderTable();
        });
        pagination.appendChild(btn);
      }
    }

    const next = document.createElement("button");
    next.className = "page-btn";
    next.innerHTML = "&raquo;";
    next.disabled = currentPage === totalPages;
    next.addEventListener("click", () => {
      if (currentPage < totalPages) {
        currentPage++;
        renderTable();
      }
    });
    pagination.appendChild(next);
  }

  function bindRowEvents() {
    document.querySelectorAll(".row-check").forEach((box) => {
      box.addEventListener("change", () => {
        const key = box.dataset.key;

        if (box.checked) {
          selectedKeys.add(key);
        } else {
          selectedKeys.delete(key);
        }

        updateSelectedBadge();
      });
    });

    document.querySelectorAll(".view-result-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const index = Number(btn.dataset.index);
        const row = filteredResults[index];

        if (row) openSummary(row);
      });
    });
  }

  function updateStats(rows) {
    const total = rows.length;
    const scores = rows.map(getScore);
    const passCount = rows.filter((row) => getStatus(row) === "PASS").length;
    const passRate = total ? Math.round((passCount / total) * 100) : 0;
    const avgScore = total ? Math.round(scores.reduce((sum, score) => sum + score, 0) / total) : 0;
    const subjects = new Set(rows.map((row) => getSubject(row)).filter(Boolean));

    $("statTotalResults").textContent = total;
    $("statPassRate").textContent = `${passRate}%`;
    $("statAvgScore").textContent = `${avgScore}%`;
    $("statSubjects").textContent = subjects.size;

    if (!total) {
      $("topPerformerName").textContent = "—";
      $("topPerformerMeta").textContent = "No data loaded";
      $("highestScore").textContent = "0%";
      $("lowestScore").textContent = "0%";
      $("avgTimeTaken").textContent = "—";
      return;
    }

    const sorted = [...rows].sort((a, b) => getScore(b) - getScore(a));
    const top = sorted[0];

    $("topPerformerName").textContent = getStudentName(top);
    $("topPerformerMeta").textContent = `${getClass(top)} • ${formatSubject(getSubject(top))} • ${getScore(top)}%`;
    $("highestScore").textContent = `${Math.max(...scores)}%`;
    $("lowestScore").textContent = `${Math.min(...scores)}%`;

    const times = rows
      .map((row) => Number.parseFloat(getTime(row)))
      .filter((value) => Number.isFinite(value));

    $("avgTimeTaken").textContent = times.length
      ? `${Math.round(times.reduce((sum, value) => sum + value, 0) / times.length)} sec`
      : "—";
  }

  function renderCharts(rows) {
    const scoreBars = $("scoreBars");
    const passFailDonut = $("passFailDonut");
    const donutText = $("donutText");

    if (!rows.length) {
      scoreBars.innerHTML = `<p class="chart-empty">Load results to view score distribution.</p>`;
      passFailDonut.style.setProperty("--pass", 0);
      donutText.textContent = "0%";
      return;
    }

    const bands = [
      { label: "80 - 100", min: 80, max: 100 },
      { label: "70 - 79", min: 70, max: 79 },
      { label: "60 - 69", min: 60, max: 69 },
      { label: "50 - 59", min: 50, max: 59 },
      { label: "0 - 49", min: 0, max: 49 }
    ];

    const counts = bands.map((band) => rows.filter((row) => {
      const score = getScore(row);
      return score >= band.min && score <= band.max;
    }).length);

    const maxCount = Math.max(...counts, 1);

    scoreBars.innerHTML = bands.map((band, index) => {
      const count = counts[index];
      const width = Math.round((count / maxCount) * 100);

      return `
        <div class="score-bar-row">
          <span>${band.label}%</span>
          <div class="score-track">
            <div class="score-fill" style="width:${width}%"></div>
          </div>
          <strong>${count}</strong>
        </div>
      `;
    }).join("");

    const passCount = rows.filter((row) => getStatus(row) === "PASS").length;
    const passRate = Math.round((passCount / rows.length) * 100);

    passFailDonut.style.setProperty("--pass", passRate);
    donutText.textContent = `${passRate}%`;
  }

  function updateSelectedBadge() {
    selectedCountBadge.textContent = `${selectedKeys.size} selected`;

    if (selectAllRows) {
      selectAllRows.checked = false;
    }
  }

  function getSelectedRecords() {
    return filteredResults.filter((row) => selectedKeys.has(getStableKey(row)));
  }

  if (selectAllRows) {
    selectAllRows.addEventListener("change", () => {
      const start = (currentPage - 1) * rowsPerPage;
      const end = start + rowsPerPage;
      const pageRows = filteredResults.slice(start, end);

      pageRows.forEach((row) => {
        const key = getStableKey(row);

        if (selectAllRows.checked) {
          selectedKeys.add(key);
        } else {
          selectedKeys.delete(key);
        }
      });

      updateSelectedBadge();
      renderTable();
    });
  }

  function openDeleteModal() {
    if (!selectedKeys.size) {
      showToast("Please select at least one result to delete.", "warning");
      return;
    }

    deleteModal.classList.remove("hidden");
  }

  function closeDeleteModal() {
    deleteModal.classList.add("hidden");
  }

  async function confirmDelete() {
    const records = getSelectedRecords();

    if (!records.length) {
      showToast("No selected record found.", "warning");
      closeDeleteModal();
      return;
    }

    confirmDeleteBtn.classList.add("loading");
    confirmDeleteBtn.querySelector(".btn-text")?.classList.add("hidden");
    confirmDeleteBtn.querySelector(".btn-spinner")?.classList.remove("hidden");

    try {
      const res = await fetch("/api/results/delete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json"
        },
        body: JSON.stringify({
          delete_items: records
        })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Delete failed");
      }

      showToast(data.message || "Selected results deleted.", "success");
      closeDeleteModal();
      await loadAllResults();
    } catch (error) {
      console.error(error);
      showToast(error.message || "Could not delete selected results.", "error");
    } finally {
      confirmDeleteBtn.classList.remove("loading");
      confirmDeleteBtn.querySelector(".btn-text")?.classList.remove("hidden");
      confirmDeleteBtn.querySelector(".btn-spinner")?.classList.add("hidden");
    }
  }

function openSummary(row) {
  if (!row) return;

  // Fill data
  $("ap_studentName").textContent = getStudentName(row) || "—";
  $("ap_studentID").textContent = getAdmission(row) || "—";
  $("ap_year").textContent = getYear(row) || "—";
  $("ap_studentClass").textContent = getClass(row) || "—";
  $("ap_studentCategory").textContent = getClassCategory(row) || "—";
  $("ap_subject").textContent = formatSubject(getSubject(row)) || "—";

  $("ap_percent").textContent = `${getScore(row) || 0}%`;
  $("ap_rawScore").textContent = `${getCorrect(row) || 0} / ${getTotal(row) || 0}`;
  $("ap_correct").textContent = getCorrect(row) || 0;
  $("ap_total").textContent = getTotal(row) || 0;

  const total = Number(getTotal(row)) || 0;
  const correct = Number(getCorrect(row)) || 0;
  const accuracy = total ? Math.round((correct / total) * 100) : (getScore(row) || 0);

  $("ap_accuracy").textContent = `${accuracy}%`;
  $("ap_time").textContent = getTime(row) || "—";
  $("ap_status").textContent = getStatus(row) || "—";
  $("ap_date").textContent = getSubmittedAt(row) || "—";

  // Show modal properly
  summaryOverlay.classList.remove("hidden");
  summaryOverlay.style.display = "block";

  adminPrintSummary.classList.add("show-summary");
}


function closeSummary() {
  summaryOverlay.classList.add("hidden");
  summaryOverlay.style.display = "none";

  adminPrintSummary.classList.remove("show-summary");
}




  function printSelected() {
    const records = getSelectedRecords();

    if (!records.length) {
      showToast("Please select one result to print.", "warning");
      return;
    }

    openSummary(records[0]);
    setTimeout(() => window.print(), 250);
  }

  function printAll() {
    if (!filteredResults.length) {
      showToast("No results available to print.", "warning");
      return;
    }

    const win = window.open("", "_blank");

    const rows = filteredResults.map((row, index) => `
      <tr>
        <td>${index + 1}</td>
        <td>${escapeHtml(getStudentName(row))}</td>
        <td>${escapeHtml(getAdmission(row))}</td>
        <td>${escapeHtml(getYear(row))}</td>
        <td>${escapeHtml(getClass(row))}</td>
        <td>${escapeHtml(formatSubject(getSubject(row)))}</td>
        <td>${getScore(row)}%</td>
        <td>${escapeHtml(getStatus(row))}</td>
        <td>${escapeHtml(getSubmittedAt(row))}</td>
      </tr>
    `).join("");

    win.document.write(`
      <html>
      <head>
        <title>EMIS Results Printout</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 24px; color: #102033; }
          h1 { margin: 0 0 6px; }
          p { margin: 0 0 20px; color: #63748a; }
          table { width: 100%; border-collapse: collapse; font-size: 12px; }
          th, td { border: 1px solid #dce7f5; padding: 8px; text-align: left; }
          th { background: #eef4ff; }
        </style>
      </head>
      <body>
        <h1>EMIS Exam Results</h1>
        <p>Total Results: ${filteredResults.length}</p>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Student</th>
              <th>Admission</th>
              <th>Year</th>
              <th>Class</th>
              <th>Subject</th>
              <th>Score</th>
              <th>Status</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </body>
      </html>
    `);

    win.document.close();
    win.focus();
    win.print();
  }

  function exportCsv() {
    if (!filteredResults.length) {
      showToast("No results available to export.", "warning");
      return;
    }

    const headers = [
      "Student Name",
      "Admission No",
      "Year",
      "Class",
      "Subject",
      "Score (%)",
      "Correct",
      "Total",
      "Status",
      "Time Taken",
      "Submitted At"
    ];

    const rows = filteredResults.map((row) => [
      getStudentName(row),
      getAdmission(row),
      getYear(row),
      getClass(row),
      formatSubject(getSubject(row)),
      `${getScore(row)}%`,
      getCorrect(row),
      getTotal(row),
      getStatus(row),
      getTime(row),
      getSubmittedAt(row)
    ]);

    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
      .join("\n");

    const blob = new Blob([csv], {
      type: "text/csv;charset=utf-8;"
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = `emis_results_${Date.now()}.csv`;
    a.click();

    URL.revokeObjectURL(url);

    showToast("CSV exported successfully.", "success");
  }

  function exportExcelFallback() {
    exportCsv();
    showToast("Excel export downloaded as CSV. Open it with Microsoft Excel.", "info");
  }

  function clearFilters() {
    if (yearSelector) yearSelector.value = "all";
    if (classSelector) classSelector.value = "all";
    if (subjectSelector) subjectSelector.value = "all";
    if (statusFilter) statusFilter.value = "";
    if (globalSearch) globalSearch.value = "";

    document.querySelectorAll(".class-pill").forEach((pill) => {
      pill.classList.toggle("active", pill.dataset.class === "all");
    });

    loadAllResults();
  }

  reloadTableBtn?.addEventListener("click", loadAllResults);
  clearFiltersBtn?.addEventListener("click", clearFilters);

  yearSelector?.addEventListener("change", loadAllResults);
  classSelector?.addEventListener("change", loadAllResults);
  subjectSelector?.addEventListener("change", applyFilters);
  statusFilter?.addEventListener("change", applyFilters);
  globalSearch?.addEventListener("input", applyFilters);

  document.querySelectorAll(".class-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".class-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");

      if (classSelector) {
        classSelector.value = pill.dataset.class || "all";
      }

      loadAllResults();
    });
  });

  deleteSelectedBtn?.addEventListener("click", openDeleteModal);
  cancelDeleteBtn?.addEventListener("click", closeDeleteModal);
  confirmDeleteBtn?.addEventListener("click", confirmDelete);

  printSelectedBtn?.addEventListener("click", printSelected);
  printAllPdfBtn?.addEventListener("click", printAll);

  exportCsvBtn?.addEventListener("click", exportCsv);
  exportAllExcelBtn?.addEventListener("click", exportExcelFallback);

  toggleCompactBtn?.addEventListener("click", () => {
    resultsTable?.classList.toggle("compact");
  });

  summaryCloseBtn?.addEventListener("click", closeSummary);
  summaryOverlay?.addEventListener("click", closeSummary);


window.loadAllResults = loadAllResults;

window.addEventListener("emis:result-submitted", () => {
  loadAllResults();
});


  loadAllResults();
});
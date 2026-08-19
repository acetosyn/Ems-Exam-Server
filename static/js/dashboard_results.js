/* ===========================================================
   dashboard_results.js
   EMIS Admin Results & Credentials
   2026 Student Database Upgrade
=========================================================== */

document.addEventListener("DOMContentLoaded", () => {
  // =========================================================
  // ELEMENTS
  // =========================================================

  const ids = [
    "viewCredsBtn", "refreshCredsBtn", "exportCredsBtn", "clearCredsBtn",
    "viewResultsBtn", "refreshResultsBtn", "exportResultsBtn", "clearResultsBtn",
    "resultsModal", "resultsModalBody", "closeResultsModal", "refreshResultsModal",
    "credentialsModal", "credsModalBody", "closeCredsModal", "refreshCredsModal",
    "exportCredsModal", "exportResultsModal",

    // New admin.html result filters / summary
    "resultFilterYear", "resultFilterClassLevel", "resultFilterClassArm",
    "resultFilterSex", "resultFilterStream", "resultFilterStatus",
    "resultFilterSubject", "resultSearchStudent", "clearResultFilters",
    "resultsSubmittedTotal", "resultsPassedTotal", "resultsFailedTotal",
    "resultsAverageScore", "exportFilteredResultsBtn",

    // Existing full-page results table
    "resultsTableBody"
  ];

  const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));

  const credsWrapper = byId("credentialsWrapper");
  const resultsWrapper = byId("resultsWrapper");

  let allResults = [];
  let filteredResults = [];
  let autoRefreshInterval = null;


  // =========================================================
  // GLOBAL RESULT DETAIL MODAL
  // =========================================================

  const viewModal = document.createElement("div");
  viewModal.id = "viewModal";
  viewModal.className = "view-modal hidden";

  viewModal.innerHTML = `
    <div class="view-modal-content">
      <button id="closeViewModal" class="view-close" type="button">&times;</button>

      <h3 class="text-lg font-semibold mb-3 border-b pb-1">
        Exam Result Details
      </h3>

      <div id="viewModalBody" class="text-sm space-y-2 max-h-[70vh] overflow-y-auto"></div>
    </div>
  `;

  document.body.appendChild(viewModal);

  const viewModalBody = viewModal.querySelector("#viewModalBody");
  const closeViewModal = viewModal.querySelector("#closeViewModal");

  closeViewModal?.addEventListener("click", () => viewModal.classList.add("hidden"));

  viewModal.addEventListener("click", event => {
    if (event.target === viewModal) viewModal.classList.add("hidden");
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") viewModal.classList.add("hidden");
  });


  // =========================================================
  // HELPERS
  // =========================================================

  function byId(id) {
    return document.getElementById(id);
  }

  function clean(value) {
    return String(value ?? "").trim();
  }

  function upper(value) {
    return clean(value).toUpperCase();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function numberValue(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function resultAdmission(result) {
    return clean(result.admission_number || result.student_id || result.id);
  }

  function resultName(result) {
    return clean(result.full_name || result.fullname || result.student_name || result.name);
  }

  function resultSex(result) {
    const value = upper(result.sex || result.gender);

    if (value === "MALE") return "M";
    if (value === "FEMALE") return "F";

    return value;
  }

  function resultClassLevel(result) {
    return upper(result.class_level || result.class_category);
  }

  function resultClassArm(result) {
    return upper(result.class_arm || result.class || result.class_name || resultClassLevel(result));
  }

  function resultStream(result) {
    const stream = upper(result.stream || result.ss_stream);

    if (stream === "ART_COMMERCIAL") return "ART_COMMERCIAL";
    if (stream === "SCIENCE") return "SCIENCE";
    if (stream === "GENERAL") return "GENERAL";

    return stream;
  }

  function resultStatus(result) {
    const status = upper(result.result_status || result.status);

    if (status === "PASS" || status === "PASSED") return "PASS";
    if (status === "FAIL" || status === "FAILED") return "FAIL";

    return numberValue(result.score) >= 50 ? "PASS" : "FAIL";
  }

  function formatStream(stream) {
    stream = upper(stream);

    if (stream === "ART_COMMERCIAL") return "Art + Commercial";
    if (stream === "SCIENCE") return "Science";
    if (stream === "GENERAL") return "General";

    return stream || "—";
  }

  function formatSex(sex) {
    sex = upper(sex);

    if (sex === "M") return "Male";
    if (sex === "F") return "Female";

    return "—";
  }

  function formatTimeTaken(value) {
    if (value === null || value === undefined || value === "") return "—";

    const raw = clean(value);

    // Preserve already formatted times such as 32:18.
    if (raw.includes(":")) return raw;

    const seconds = Math.max(0, numberValue(value));

    if (!seconds) return "0s";

    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;

    if (!mins) return `${secs}s`;

    return `${mins}m ${String(secs).padStart(2, "0")}s`;
  }

  function formatDate(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return clean(value);

    return date.toLocaleString();
  }

  function subjectValue(result) {
    return upper(result.subject);
  }


  // =========================================================
  // TOASTS
  // =========================================================

  function showToast(message, type = "info") {
    const toast = document.createElement("div");

    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add("visible"), 50);
    setTimeout(() => toast.remove(), 4000);
  }


  // =========================================================
  // SKELETON
  // =========================================================

  function skeletonLoader(rows = 4, cols = 8) {
    let html = "<table class='modern-table w-full'><tbody>";

    for (let row = 0; row < rows; row++) {
      html += "<tr>";

      for (let col = 0; col < cols; col++) {
        html += "<td><div class='skeleton'></div></td>";
      }

      html += "</tr>";
    }

    return `${html}</tbody></table>`;
  }


  // =========================================================
  // CREDENTIALS
  // =========================================================

  async function fetchCredentials(target = credsWrapper) {
    if (!target) return;

    target.innerHTML = skeletonLoader(3, 2);

    try {
      const response = await fetch("/view_credentials", {
        headers: { Accept: "application/json" },
        credentials: "same-origin"
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const payload = await response.json();
      const credentials = payload.credentials || [];

      if (!credentials.length) {
        target.innerHTML = "<p class='muted'>No credentials found.</p>";
        return;
      }

      target.innerHTML = `
        <div class="table-actions">
          <input id="searchCreds" class="form-input w-1/3 mb-2" placeholder="Search credentials...">
        </div>

        <table class="modern-table sortable w-full">
          <thead>
            <tr>
              <th>Username / Admission</th>
              <th>Password</th>
            </tr>
          </thead>

          <tbody>
            ${credentials.map(row => `
              <tr>
                <td>${escapeHtml(row.username || row.admission_number || "")}</td>
                <td>${escapeHtml(row.password || "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;

      enableSearch("searchCreds", target);
      enableSort(target);

      showToast("Credentials loaded", "success");

    } catch (error) {
      console.error("Credential fetch failed:", error);
      target.innerHTML = "<p class='error'>Failed to load credentials.</p>";
      showToast("Failed to load credentials", "error");
    }
  }


  // =========================================================
  // FETCH RESULTS
  // =========================================================

  async function fetchResults(target = resultsWrapper, silent = false) {
    if (target && !silent) target.innerHTML = skeletonLoader(4, 10);

    try {
      const response = await fetch("/api/exam/results", {
        headers: { Accept: "application/json" },
        credentials: "same-origin"
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const payload = await response.json();

      const results = Array.isArray(payload.results)
        ? payload.results
        : Array.isArray(payload.data)
          ? payload.data
          : [];

      results.sort((a, b) => {
        const aTime = new Date(a.submitted_at || 0).getTime();
        const bTime = new Date(b.submitted_at || 0).getTime();

        return bTime - aTime;
      });

      allResults = results;
      filteredResults = applyAdminFilterData(allResults);

      if (target) {
        if (!results.length) {
          target.innerHTML = "<p class='muted'>No exam results yet.</p>";
        } else {
          renderResultsTable(filteredResults, target);
        }
      }

      renderMainResultsTable(filteredResults);
      updateSummary(filteredResults);

      if (!silent) showToast("Results loaded", "success");

      return results;

    } catch (error) {
      console.error("Result fetch failed:", error);

      allResults = [];
      filteredResults = [];

      if (target) target.innerHTML = "<p class='error'>Failed to load results.</p>";

      renderMainResultsTable([]);
      updateSummary([]);

      if (!silent) showToast("Failed to load results", "error");

      return [];
    }
  }


  // =========================================================
  // MODAL / WRAPPER RESULTS TABLE
  // =========================================================

  function renderResultsTable(data, target = resultsWrapper) {
    if (!target) return;

    const subjects = [...new Set(data.map(subjectValue).filter(Boolean))].sort();

    target.innerHTML = `
      <div class="flex flex-wrap gap-2 mb-2 items-center">

        <input
          type="text"
          id="searchResults"
          class="form-input"
          placeholder="Search admission no., name, class or subject..."
        >

        <select id="filterSubject" class="form-input w-auto">
          <option value="all">All Subjects</option>
          ${subjects.map(subject => `
            <option value="${escapeHtml(subject)}">${escapeHtml(subject)}</option>
          `).join("")}
        </select>

        <select id="filterStatus" class="form-input w-auto">
          <option value="all">All Status</option>
          <option value="PASS">Passed</option>
          <option value="FAIL">Failed</option>
        </select>

        <button id="toggleAutoRefresh" class="btn-outline" type="button">
          <i class="fa-solid fa-rotate"></i>
          Auto Refresh
        </button>

      </div>

      <div class="muted mb-2">
        Showing ${data.length} result(s)
      </div>

      <div class="table-wrap">
        <table class="modern-table sortable w-full">
          <thead>
            <tr>
              <th>Admission No.</th>
              <th>Student</th>
              <th>Sex</th>
              <th>Class</th>
              <th>Arm</th>
              <th>Stream</th>
              <th>Subject</th>
              <th>Score</th>
              <th>Status</th>
              <th>Submitted</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            ${data.map(result => resultRowHtml(result, true)).join("")}
          </tbody>
        </table>
      </div>
    `;

    enableSort(target);

    byId("searchResults")?.addEventListener("input", applyModalFilters);
    byId("filterSubject")?.addEventListener("change", applyModalFilters);
    byId("filterStatus")?.addEventListener("change", applyModalFilters);
    byId("toggleAutoRefresh")?.addEventListener("click", toggleAutoRefresh);

    bindResultActionButtons(target);
  }


  // =========================================================
  // ADMIN.HTML 14-COLUMN TABLE
  // =========================================================

  function renderMainResultsTable(data) {
    if (!el.resultsTableBody) return;

    if (!data.length) {
      el.resultsTableBody.innerHTML = `
        <tr>
          <td colspan="14" class="empty-cell">No results available.</td>
        </tr>
      `;
      return;
    }

    el.resultsTableBody.innerHTML = data.map(result => {
      const admission = resultAdmission(result);
      const status = resultStatus(result);
      const sex = resultSex(result);
      const stream = resultStream(result);

      return `
        <tr data-admission="${escapeHtml(admission)}">

          <td>
            <strong>${escapeHtml(admission || "—")}</strong>
          </td>

          <td>${escapeHtml(resultName(result) || "—")}</td>

          <td>
            <span class="student-sex-badge ${sex === "M" ? "male" : sex === "F" ? "female" : ""}">
              ${escapeHtml(sex || "—")}
            </span>
          </td>

          <td>${escapeHtml(resultClassLevel(result) || "—")}</td>

          <td>
            <span class="class-arm-badge ${resultClassArm(result).includes("B/C") ? "bc" : ""}">
              ${escapeHtml(resultClassArm(result) || "—")}
            </span>
          </td>

          <td>
            <span class="result-stream ${streamClass(stream)}">
              ${escapeHtml(formatStream(stream))}
            </span>
          </td>

          <td>${escapeHtml(subjectValue(result) || "—")}</td>

          <td>
            <strong>${numberValue(result.score)}%</strong>
          </td>

          <td>${numberValue(result.correct)}</td>

          <td>${numberValue(result.total)}</td>

          <td>
            <span class="result-status ${status === "PASS" ? "pass" : "fail"}">
              ${status}
            </span>
          </td>

          <td>${escapeHtml(formatTimeTaken(result.time_taken))}</td>

          <td>${escapeHtml(formatDate(result.submitted_at))}</td>

          <td>
            <button
              type="button"
              class="btn-outline btn-sm viewResult"
              data-admission="${escapeHtml(admission)}"
              data-subject="${escapeHtml(subjectValue(result))}"
            >
              View
            </button>
          </td>

        </tr>
      `;
    }).join("");

    bindResultActionButtons(el.resultsTableBody);
  }


  // =========================================================
  // RESULT ROW FOR MODAL TABLE
  // =========================================================

  function resultRowHtml(result, includeDelete = false) {
    const admission = resultAdmission(result);
    const status = resultStatus(result);
    const sex = resultSex(result);
    const stream = resultStream(result);

    return `
      <tr>
        <td>${escapeHtml(admission || "—")}</td>
        <td>${escapeHtml(resultName(result) || "—")}</td>
        <td>${escapeHtml(sex || "—")}</td>
        <td>${escapeHtml(resultClassLevel(result) || "—")}</td>
        <td>${escapeHtml(resultClassArm(result) || "—")}</td>
        <td>${escapeHtml(formatStream(stream))}</td>
        <td>${escapeHtml(subjectValue(result) || "—")}</td>

        <td>
          ${numberValue(result.correct)}/${numberValue(result.total)}
          (${numberValue(result.score)}%)
        </td>

        <td>
          <span class="result-status ${status === "PASS" ? "pass" : "fail"}">
            ${status}
          </span>
        </td>

        <td>${escapeHtml(formatDate(result.submitted_at))}</td>

        <td>
          <button
            class="btn-outline btn-sm viewResult"
            type="button"
            data-admission="${escapeHtml(admission)}"
            data-subject="${escapeHtml(subjectValue(result))}"
          >
            View
          </button>

          ${includeDelete ? `
            <button
              class="btn-danger btn-sm deleteResult"
              type="button"
              data-admission="${escapeHtml(admission)}"
              data-subject="${escapeHtml(subjectValue(result))}"
              data-year="${escapeHtml(clean(result.year))}"
            >
              Delete
            </button>
          ` : ""}
        </td>
      </tr>
    `;
  }


  // =========================================================
  // STREAM CSS CLASS
  // =========================================================

  function streamClass(stream) {
    stream = upper(stream);

    if (stream === "SCIENCE") return "science";
    if (stream === "ART_COMMERCIAL") return "art-commercial";

    return "general";
  }


  // =========================================================
  // RESULT DETAIL MODAL
  // =========================================================

  function showResultDetails(admissionNumber, subject = "") {
    const admission = clean(admissionNumber).toLowerCase();
    const wantedSubject = upper(subject);

    const result = allResults.find(item => {
      const sameAdmission = resultAdmission(item).toLowerCase() === admission;
      const sameSubject = !wantedSubject || subjectValue(item) === wantedSubject;

      return sameAdmission && sameSubject;
    });

    if (!result) {
      showToast("Result not found", "error");
      return;
    }

    const status = resultStatus(result);

    viewModalBody.innerHTML = `
      <div><strong>Admission Number:</strong> ${escapeHtml(resultAdmission(result))}</div>
      <div><strong>Student Name:</strong> ${escapeHtml(resultName(result))}</div>
      <div><strong>Sex:</strong> ${escapeHtml(formatSex(resultSex(result)))}</div>

      <hr>

      <div><strong>Class Level:</strong> ${escapeHtml(resultClassLevel(result))}</div>
      <div><strong>Class Arm:</strong> ${escapeHtml(resultClassArm(result))}</div>
      <div><strong>Stream:</strong> ${escapeHtml(formatStream(resultStream(result)))}</div>

      <hr>

      <div><strong>Subject:</strong> ${escapeHtml(subjectValue(result))}</div>
      <div><strong>Score:</strong> ${numberValue(result.score)}%</div>
      <div><strong>Correct:</strong> ${numberValue(result.correct)}</div>
      <div><strong>Incorrect:</strong> ${numberValue(result.incorrect)}</div>
      <div><strong>Total:</strong> ${numberValue(result.total)}</div>
      <div><strong>Answered:</strong> ${numberValue(result.answered)}</div>
      <div><strong>Skipped:</strong> ${numberValue(result.skipped)}</div>
      <div><strong>Flagged:</strong> ${numberValue(result.flagged)}</div>
      <div><strong>Tab Switches:</strong> ${numberValue(result.tabSwitches ?? result.tab_switches)}</div>

      <hr>

      <div><strong>Result:</strong> ${status}</div>
      <div><strong>Submission Status:</strong> ${escapeHtml(result.submission_status || "COMPLETED")}</div>
      <div><strong>Time Taken:</strong> ${escapeHtml(formatTimeTaken(result.time_taken))}</div>
      <div><strong>Academic Session:</strong> ${escapeHtml(result.academic_session || "—")}</div>
      <div><strong>Term:</strong> ${escapeHtml(result.term || "—")}</div>
      <div><strong>Exam Year:</strong> ${escapeHtml(result.year || "—")}</div>
      <div><strong>Date Written:</strong> ${escapeHtml(result.date_written || "—")}</div>
      <div><strong>Submitted:</strong> ${escapeHtml(formatDate(result.submitted_at))}</div>
    `;

    viewModal.classList.remove("hidden");
  }


  // =========================================================
  // RESULT ACTION BUTTONS
  // =========================================================

  function bindResultActionButtons(container) {
    if (!container) return;

    container.querySelectorAll(".viewResult").forEach(button => {
      button.addEventListener("click", () => {
        showResultDetails(button.dataset.admission, button.dataset.subject);
      });
    });

    container.querySelectorAll(".deleteResult").forEach(button => {
      button.addEventListener("click", () => {
        deleteResult({
          admission_number: button.dataset.admission,
          subject: button.dataset.subject,
          year: button.dataset.year
        });
      });
    });
  }


  // =========================================================
  // ADMIN.HTML FILTERS
  // =========================================================

  function getAdminFilters() {
    return {
      year: clean(el.resultFilterYear?.value),
      classLevel: upper(el.resultFilterClassLevel?.value),
      classArm: upper(el.resultFilterClassArm?.value),
      sex: upper(el.resultFilterSex?.value),
      stream: upper(el.resultFilterStream?.value),
      status: upper(el.resultFilterStatus?.value),
      subject: upper(el.resultFilterSubject?.value),
      search: clean(el.resultSearchStudent?.value).toLowerCase()
    };
  }

  function applyAdminFilterData(source) {
    const filters = getAdminFilters();

    return source.filter(result => {
      const admission = resultAdmission(result).toLowerCase();
      const name = resultName(result).toLowerCase();
      const subject = subjectValue(result);

      const searchHaystack = [
        admission,
        name,
        subject.toLowerCase(),
        resultClassLevel(result).toLowerCase(),
        resultClassArm(result).toLowerCase()
      ].join(" ");

      if (filters.year && clean(result.year) !== filters.year) return false;
      if (filters.classLevel && resultClassLevel(result) !== filters.classLevel) return false;
      if (filters.classArm && resultClassArm(result) !== filters.classArm) return false;
      if (filters.sex && resultSex(result) !== filters.sex) return false;
      if (filters.stream && resultStream(result) !== filters.stream) return false;
      if (filters.status && resultStatus(result) !== filters.status) return false;

      if (filters.subject && !subject.includes(filters.subject)) return false;
      if (filters.search && !searchHaystack.includes(filters.search)) return false;

      return true;
    });
  }

  function applyAdminFilters() {
    filteredResults = applyAdminFilterData(allResults);

    renderMainResultsTable(filteredResults);
    updateSummary(filteredResults);
  }

  function clearAdminFilters() {
    [
      el.resultFilterYear,
      el.resultFilterClassLevel,
      el.resultFilterClassArm,
      el.resultFilterSex,
      el.resultFilterStream,
      el.resultFilterStatus,
      el.resultFilterSubject,
      el.resultSearchStudent
    ].forEach(input => {
      if (input) input.value = "";
    });

    applyAdminFilters();
  }


  // =========================================================
  // OLD MODAL FILTERS
  // =========================================================

  function applyModalFilters() {
    const search = clean(byId("searchResults")?.value).toLowerCase();
    const subject = upper(byId("filterSubject")?.value);
    const status = upper(byId("filterStatus")?.value);

    const filtered = allResults.filter(result => {
      const haystack = [
        resultAdmission(result),
        resultName(result),
        resultClassLevel(result),
        resultClassArm(result),
        resultStream(result),
        subjectValue(result)
      ].join(" ").toLowerCase();

      const searchMatch = !search || haystack.includes(search);
      const subjectMatch = !subject || subject === "ALL" || subjectValue(result) === subject;
      const statusMatch = !status || status === "ALL" || resultStatus(result) === status;

      return searchMatch && subjectMatch && statusMatch;
    });

    renderResultsTable(filtered, resultsWrapper);
  }


  // =========================================================
  // RESULT SUMMARY
  // =========================================================

  function updateSummary(results) {
    const total = results.length;

    const passed = results.filter(result => resultStatus(result) === "PASS").length;
    const failed = results.filter(result => resultStatus(result) === "FAIL").length;

    const average = total
      ? results.reduce((sum, result) => sum + numberValue(result.score), 0) / total
      : 0;

    if (el.resultsSubmittedTotal) el.resultsSubmittedTotal.textContent = String(total);
    if (el.resultsPassedTotal) el.resultsPassedTotal.textContent = String(passed);
    if (el.resultsFailedTotal) el.resultsFailedTotal.textContent = String(failed);

    if (el.resultsAverageScore) {
      el.resultsAverageScore.textContent = total ? `${average.toFixed(1)}%` : "--";
    }

    // Also update original dashboard average if available.
    const statAvg = byId("statAvg");
    if (statAvg) statAvg.textContent = total ? `${average.toFixed(1)}%` : "--";

    const autoAverage = byId("autoAverage");
    if (autoAverage) autoAverage.textContent = total ? `${average.toFixed(1)}%` : "--";

    const autoPassRate = byId("autoPassRate");

    if (autoPassRate) {
      const passRate = total ? (passed / total) * 100 : 0;
      autoPassRate.textContent = total ? `${passRate.toFixed(1)}%` : "--";
    }
  }


  // =========================================================
  // DELETE RESULT
  // =========================================================

  async function deleteResult(resultIdentity) {
    const admission = resultIdentity.admission_number;
    const subject = resultIdentity.subject;

    if (!admission) return;

    const label = subject ? `${admission} — ${subject}` : admission;

    if (!confirm(`Delete result for ${label}? This action is permanent.`)) return;

    try {
      const response = await fetch("/delete_result", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",

        body: JSON.stringify({
          admission_number: admission,
          student_id: admission,
          subject,
          year: resultIdentity.year
        })
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok || payload.success === false) {
        throw new Error(payload.message || `HTTP ${response.status}`);
      }

      showToast(payload.message || "Result deleted", "success");
      await fetchResults(resultsWrapper, true);

    } catch (error) {
      console.error("Delete result failed:", error);
      showToast(error.message || "Error deleting result", "error");
    }
  }


  // =========================================================
  // AUTO REFRESH
  // =========================================================

  function toggleAutoRefresh() {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;

      showToast("Auto-refresh stopped", "info");
      return;
    }

    autoRefreshInterval = setInterval(() => {
      fetchResults(resultsWrapper, true);
    }, 30000);

    showToast("Auto-refresh enabled every 30 seconds", "success");
  }


  // =========================================================
  // EXPORT FILTERED RESULTS
  // =========================================================

  function exportFilteredResults() {
    if (!filteredResults.length) {
      showToast("No filtered results to export", "info");
      return;
    }

    const headers = [
      "Admission_number",
      "Full_name",
      "Sex",
      "Class_level",
      "Class_arm",
      "Stream",
      "Subject",
      "Score",
      "Correct",
      "Total",
      "Result_status",
      "Time_taken",
      "Submitted_at"
    ];

    const rows = filteredResults.map(result => [
      resultAdmission(result),
      resultName(result),
      resultSex(result),
      resultClassLevel(result),
      resultClassArm(result),
      resultStream(result),
      subjectValue(result),
      numberValue(result.score),
      numberValue(result.correct),
      numberValue(result.total),
      resultStatus(result),
      result.time_taken ?? "",
      result.submitted_at ?? ""
    ]);

    const csv = [headers, ...rows]
      .map(row => row.map(csvValue).join(","))
      .join("\n");

    const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = `EMIS_Filtered_Results_${new Date().toISOString().slice(0, 10)}.csv`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);

    showToast(`${filteredResults.length} result(s) exported`, "success");
  }

  function csvValue(value) {
    const text = String(value ?? "");

    if (/[",\n]/.test(text)) {
      return `"${text.replaceAll('"', '""')}"`;
    }

    return text;
  }


  // =========================================================
  // GENERIC SEARCH
  // =========================================================

  function enableSearch(id, container) {
    const input = byId(id);

    if (!input || !container) return;

    input.addEventListener("input", event => {
      const term = event.target.value.toLowerCase();

      container.querySelectorAll("tbody tr").forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(term) ? "" : "none";
      });
    });
  }


  // =========================================================
  // SORTING
  // =========================================================

  function enableSort(container) {
    if (!container) return;

    container.querySelectorAll("th").forEach(header => {
      header.addEventListener("click", () => {
        const table = header.closest("table");
        const tbody = table?.querySelector("tbody");

        if (!table || !tbody) return;

        const index = Array.from(header.parentNode.children).indexOf(header);
        const rows = Array.from(tbody.querySelectorAll("tr"));

        const ascending = header.classList.toggle("asc");

        rows.sort((rowA, rowB) => {
          const a = rowA.children[index]?.innerText?.trim() || "";
          const b = rowB.children[index]?.innerText?.trim() || "";

          const aNum = Number(a.replace(/[%/,]/g, ""));
          const bNum = Number(b.replace(/[%/,]/g, ""));

          if (Number.isFinite(aNum) && Number.isFinite(bNum)) {
            return ascending ? aNum - bNum : bNum - aNum;
          }

          return ascending
            ? a.localeCompare(b, undefined, { numeric: true })
            : b.localeCompare(a, undefined, { numeric: true });
        });

        rows.forEach(row => tbody.appendChild(row));
      });
    });
  }


  // =========================================================
  // NEW ADMIN FILTER EVENTS
  // =========================================================

  [
    el.resultFilterYear,
    el.resultFilterClassLevel,
    el.resultFilterClassArm,
    el.resultFilterSex,
    el.resultFilterStream,
    el.resultFilterStatus
  ].forEach(input => {
    input?.addEventListener("change", applyAdminFilters);
  });

  el.resultFilterSubject?.addEventListener("input", applyAdminFilters);
  el.resultSearchStudent?.addEventListener("input", applyAdminFilters);
  el.clearResultFilters?.addEventListener("click", clearAdminFilters);
  el.exportFilteredResultsBtn?.addEventListener("click", exportFilteredResults);


  // =========================================================
  // ORIGINAL BUTTON EVENTS
  // =========================================================

  el.viewResultsBtn?.addEventListener("click", async () => {
    if (!el.resultsModal || !el.resultsModalBody) return;

    el.resultsModal.style.display = "flex";
    await fetchResults(el.resultsModalBody);
  });

  el.closeResultsModal?.addEventListener("click", () => {
    if (el.resultsModal) el.resultsModal.style.display = "none";
  });

  el.refreshResultsModal?.addEventListener("click", () => {
    if (el.resultsModalBody) fetchResults(el.resultsModalBody);
  });

  el.refreshResultsBtn?.addEventListener("click", () => fetchResults(resultsWrapper));
  el.refreshCredsBtn?.addEventListener("click", () => fetchCredentials(credsWrapper));

  el.viewCredsBtn?.addEventListener("click", async () => {
    if (!el.credentialsModal || !el.credsModalBody) return;

    el.credentialsModal.style.display = "flex";
    await fetchCredentials(el.credsModalBody);
  });

  el.closeCredsModal?.addEventListener("click", () => {
    if (el.credentialsModal) el.credentialsModal.style.display = "none";
  });

  el.refreshCredsModal?.addEventListener("click", () => {
    if (el.credsModalBody) fetchCredentials(el.credsModalBody);
  });


  // =========================================================
  // INITIAL LOAD
  // =========================================================

  fetchResults(resultsWrapper);
});
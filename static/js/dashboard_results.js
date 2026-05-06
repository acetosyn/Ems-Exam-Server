/* ===========================================================
   dashboard_results.js — Admin Results & Credentials Panel
   Architect Build v12 (Dual Modal Fix + Z-Stack Stable)
   =========================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const ids = [
    "viewCredsBtn", "refreshCredsBtn", "exportCredsBtn", "clearCredsBtn",
    "viewResultsBtn", "refreshResultsBtn", "exportResultsBtn", "clearResultsBtn",
    "resultsModal", "resultsModalBody", "closeResultsModal", "refreshResultsModal",
    "credentialsModal", "credsModalBody", "closeCredsModal", "refreshCredsModal",
    "exportCredsModal", "exportResultsModal"
  ];
  const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));

  const credsWrapper = byId("credentialsWrapper");
  const resultsWrapper = byId("resultsWrapper");
  let allResults = [];
  let autoRefreshInterval = null;

  // ===========================================================
  // Global View Modal (Independent Top Layer)
  // ===========================================================
  const viewModal = document.createElement("div");
  viewModal.id = "viewModal";
  viewModal.className = "view-modal hidden";
  viewModal.innerHTML = `
    <div class="view-modal-content">
      <button id="closeViewModal" class="view-close">&times;</button>
      <h3 class="text-lg font-semibold mb-3 border-b pb-1">Exam Result Details</h3>
      <div id="viewModalBody" class="text-sm space-y-2 max-h-[70vh] overflow-y-auto"></div>
    </div>`;
  document.body.appendChild(viewModal);

  const closeViewModal = viewModal.querySelector("#closeViewModal");
  closeViewModal.addEventListener("click", () => viewModal.classList.add("hidden"));

  // ===========================================================
  // Toast System
  // ===========================================================
  function showToast(msg, type = "info") {
    const t = document.createElement("div");
    t.className = `toast toast-${type}`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.classList.add("visible"), 50);
    setTimeout(() => t.remove(), 4000);
  }

  // ===========================================================
  // Skeleton Loader
  // ===========================================================
  function skeletonLoader(rows = 3, cols = 5) {
    let s = "<table class='modern-table w-full'><tbody>";
    for (let i = 0; i < rows; i++) {
      s += "<tr>";
      for (let j = 0; j < cols; j++) s += "<td><div class='skeleton'></div></td>";
      s += "</tr>";
    }
    return s + "</tbody></table>";
  }

  // ===========================================================
  // Fetch Credentials
  // ===========================================================
  async function fetchCredentials(target = credsWrapper) {
    target.innerHTML = skeletonLoader(3, 2);
    try {
      const res = await fetch("/view_credentials");
      const data = (await res.json()).credentials || [];
      if (!data.length) {
        target.innerHTML = "<p class='muted'>⚠️ No credentials found.</p>";
        return;
      }
      target.innerHTML = `
        <div class="table-actions">
          <input id="searchCreds" class="form-input w-1/3 mb-2" placeholder="Search username..." />
        </div>
        <table class="modern-table sortable w-full">
          <thead><tr><th>Username</th><th>Password</th></tr></thead>
          <tbody>${data.map(r => `<tr><td>${r.username}</td><td>${r.password}</td></tr>`).join("")}</tbody>
        </table>`;
      enableSearch("searchCreds", target);
      enableSort(target);
      showToast("✅ Credentials loaded", "success");
    } catch {
      target.innerHTML = `<p class='error'>❌ Failed to load credentials.</p>`;
      showToast("Failed to load credentials", "error");
    }
  }

  // ===========================================================
  // Fetch Results
  // ===========================================================
  async function fetchResults(target = resultsWrapper) {
    target.innerHTML = skeletonLoader(4, 8);
    try {
      const res = await fetch("/api/exam/results");
      const data = (await res.json()).results || [];
      if (!data.length) {
        target.innerHTML = "<p class='muted'>⚠️ No exam results yet.</p>";
        return;
      }
      data.sort((a, b) => new Date(b.submitted_at) - new Date(a.submitted_at));
      allResults = data;
      renderResultsTable(data, target);
      showToast("✅ Results loaded", "success");
    } catch {
      target.innerHTML = `<p class='error'>❌ Failed to load results.</p>`;
      showToast("Failed to load results", "error");
    }
  }

  // ===========================================================
  // Render Results Table
  // ===========================================================
  function renderResultsTable(data, target = resultsWrapper) {
    const subjects = [...new Set(data.map(r => r.subject || ""))].filter(Boolean);
    const subjectOptions = subjects.map(s => `<option value="${s}">${s}</option>`).join("");

    target.innerHTML = `
      <div class="flex flex-wrap gap-2 mb-2 items-center">
        <input type="text" id="searchResults" class="form-input" placeholder="Search name, email, or subject..." />
        <select id="filterSubject" class="form-input w-auto">
          <option value="all">All Subjects</option>${subjectOptions}
        </select>
        <select id="filterStatus" class="form-input w-auto">
          <option value="all">All Status</option>
          <option value="passed">Passed</option>
          <option value="failed">Failed</option>
        </select>
        <button id="toggleAutoRefresh" class="btn-outline">⟳ Auto Refresh</button>
      </div>

      <div class="muted mb-2">Showing ${data.length} result(s)</div>

      <table class="modern-table sortable w-full">
        <thead>
          <tr>
            <th>Username</th><th>Full Name</th><th>Email</th>
            <th>Subject</th><th>Score</th><th>Time</th><th>Status</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${data.map(r => {
            const passed = Number(r.score) >= 50;
            const status = passed ? "Passed" : "Failed";
            const scoreDisplay = `${r.correct || 0}/${r.total || 0} (${r.score}%)`;
            return `
              <tr>
                <td>${r.username}</td>
                <td>${r.fullname || ""}</td>
                <td>${r.email || ""}</td>
                <td>${r.subject || ""}</td>
                <td>${scoreDisplay}</td>
                <td>${r.time_taken || "0"}s</td>
                <td class="${passed ? "text-green-600" : "text-red-600"}">${status}</td>
                <td>
                  <button class="btn-outline btn-sm viewResult" data-username="${r.username}">View</button>
                  <button class="btn-danger btn-sm deleteResult" data-username="${r.username}">Delete</button>
                </td>
              </tr>`;
          }).join("")}
        </tbody>
      </table>`;

    enableSort(target);
    byId("searchResults").addEventListener("input", applyFilters);
    byId("filterSubject").addEventListener("change", applyFilters);
    byId("filterStatus").addEventListener("change", applyFilters);
    byId("toggleAutoRefresh").addEventListener("click", toggleAutoRefresh);

    target.querySelectorAll(".deleteResult").forEach(btn =>
      btn.addEventListener("click", () => deleteResult(btn.dataset.username))
    );

    target.querySelectorAll(".viewResult").forEach(btn =>
      btn.addEventListener("click", () => showResultDetails(btn.dataset.username))
    );
  }

  // ===========================================================
  // View Individual Modal (Top Layer)
  // ===========================================================
  function showResultDetails(username) {
    const r = allResults.find(x => x.username === username);
    if (!r) return showToast("Result not found", "error");

    const status = r.score >= 50 ? "Passed ✅" : "Failed ❌";
    viewModal.querySelector("#viewModalBody").innerHTML = `
      <div><strong>Username:</strong> ${r.username}</div>
      <div><strong>Full Name:</strong> ${r.fullname}</div>
      <div><strong>Email:</strong> ${r.email}</div>
      <div><strong>Subject:</strong> ${r.subject}</div>
      <div><strong>Score:</strong> ${r.correct}/${r.total} (${r.score}%)</div>
      <div><strong>Answered:</strong> ${r.answered}</div>
      <div><strong>Time Taken:</strong> ${r.time_taken}s</div>
      <div><strong>Status:</strong> ${status}</div>
      <div><strong>Submitted:</strong> ${new Date(r.submitted_at).toLocaleString()}</div>
    `;
    viewModal.classList.remove("hidden");
  }

  // ===========================================================
  // Filters / Delete / Auto Refresh
  // ===========================================================
  function applyFilters() {
    const term = byId("searchResults").value.toLowerCase();
    const subject = byId("filterSubject").value;
    const statusFilter = byId("filterStatus").value;

    const filtered = allResults.filter(r => {
      const matchSearch = Object.values(r).join(" ").toLowerCase().includes(term);
      const matchSubject = subject === "all" || (r.subject || "").toLowerCase() === subject.toLowerCase();
      const passed = Number(r.score) >= 50;
      const matchStatus = statusFilter === "all" ||
        (statusFilter === "passed" && passed) ||
        (statusFilter === "failed" && !passed);
      return matchSearch && matchSubject && matchStatus;
    });

    renderResultsTable(filtered);
  }

  async function deleteResult(username) {
    if (!confirm(`Delete result for ${username}? This action is permanent.`)) return;
    try {
      const res = await fetch("/delete_result", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username })
      });
      const data = await res.json();
      showToast(data.message || "Deleted", data.success ? "success" : "error");
      if (data.success) fetchResults();
    } catch {
      showToast("Error deleting result", "error");
    }
  }

  function toggleAutoRefresh() {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
      showToast("⏹ Auto-refresh stopped", "info");
      return;
    }
    autoRefreshInterval = setInterval(fetchResults, 30000);
    showToast("⟳ Auto-refresh every 30s", "success");
  }

  // ===========================================================
  // Utility Functions
  // ===========================================================
  function enableSearch(id, container) {
    const input = byId(id);
    if (!input) return;
    input.addEventListener("input", e => {
      const term = e.target.value.toLowerCase();
      container.querySelectorAll("tbody tr").forEach(tr => {
        tr.style.display = tr.innerText.toLowerCase().includes(term) ? "" : "none";
      });
    });
  }

  function enableSort(container) {
    container.querySelectorAll("th").forEach(th => {
      th.addEventListener("click", () => {
        const table = th.closest("table");
        const idx = Array.from(th.parentNode.children).indexOf(th);
        const rows = Array.from(table.querySelectorAll("tbody tr"));
        const asc = th.classList.toggle("asc");
        rows.sort((a, b) => {
          const x = a.children[idx].innerText.toLowerCase();
          const y = b.children[idx].innerText.toLowerCase();
          return asc ? x.localeCompare(y) : y.localeCompare(x);
        });
        rows.forEach(r => table.querySelector("tbody").appendChild(r));
      });
    });
  }

  function byId(id) { return document.getElementById(id); }

  // ===========================================================
  // Event Bindings
  // ===========================================================
  el.viewResultsBtn?.addEventListener("click", () => {
    el.resultsModal.style.display = "flex";
    fetchResults(el.resultsModalBody);
  });
  el.closeResultsModal?.addEventListener("click", () => el.resultsModal.style.display = "none");

  // Init
  fetchResults();
});

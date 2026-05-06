/* ============================================================================
   EMIS ID MANAGEMENT — FULL SYSTEM (v8.0 Stable)
   ----------------------------------------------------------
   Students:
   ✔ Load SS_Students.csv
   ✔ Modal viewer + search

   Teachers:
   ✔ Load teacher IDs from backend
   ✔ Generate (one/multiple)
   ✔ View all teacher IDs
   ✔ Suspend/Delete (future)
   ✔ CSV Export
============================================================================ */

document.addEventListener("DOMContentLoaded", async () => {

  /* -------------------------------------------------------
     ELEMENT REFERENCES — STUDENTS
  ------------------------------------------------------- */
  const studentIdModal = document.getElementById("studentIdModal");
  const closeStudentIdModal = document.getElementById("closeStudentIdModal");
  const studentSearchInput = document.getElementById("studentSearchInput");
  const studentList = document.getElementById("studentList");
  const viewStudentIdsBtn = document.getElementById("viewStudentIdsBtn");

  /* -------------------------------------------------------
     ELEMENT REFERENCES — TEACHERS
  ------------------------------------------------------- */
  const teacherTableBody = document.getElementById("teacherTableBody");

  const viewTeacherIdsBtn = document.getElementById("viewTeacherIdsBtn");
  const viewTeacherIdsTile = document.getElementById("viewTeacherIds");

  // NEW ENTRY POINT → Purple "Generate IDs" tile
  const openTeacherGenerator = document.getElementById("openTeacherGenerator");

  // Header button
  const generateTeacherBtn = document.getElementById("generateTeacherBtn");

  // Modals
  const teacherIdModal = document.getElementById("teacherIdModal");
  const closeTeacherIdModal = document.getElementById("closeTeacherIdModal");
  const teacherIdResults = document.getElementById("teacherIdResults");
  const downloadTeacherCSV = document.getElementById("downloadTeacherCSV");
  const refreshTeacherList = document.getElementById("refreshTeacherList");

  const teacherOptionsModal = document.getElementById("teacherOptionsModal");
  const closeTeacherOptionsModal = document.getElementById("closeTeacherOptionsModal");
  const generateOneTeacherBtn = document.getElementById("generateOneTeacherBtn");
  const openGenerateMultipleBtn = document.getElementById("openGenerateMultipleBtn");

  const generateTeacherModal = document.getElementById("generateTeacherModal");
  const closeGenerateModal = document.getElementById("closeGenerateModal");
  const cancelGenerateBtn = document.getElementById("cancelGenerateBtn");
  const generateTeacherForm = document.getElementById("generateTeacherForm");

  const totalTeachers = document.getElementById("totalTeachers");
  const lastGenerated = document.getElementById("lastGenerated");
  const lastSync = document.getElementById("lastSync");

  /* -------------------------------------------------------
     DATA STORAGE
  ------------------------------------------------------- */
  let STUDENTS = [];
  let TEACHERS = [];

  /* -------------------------------------------------------
     CSV PARSER FOR STUDENTS
  ------------------------------------------------------- */
  function parseCSV(csvText) {
    const lines = csvText.trim().split("\n");
    const headers = lines[0].split(",");

    return lines.slice(1).map(line => {
      const cols = line.split(",");
      const obj = {};
      headers.forEach((h, i) => {
        obj[h.trim()] = cols[i] ? cols[i].trim() : "";
      });
      return obj;
    });
  }

  async function loadCSVStudents() {
    try {
      const res = await fetch("/static/ids/SS_Students.csv");
      const text = await res.text();
      STUDENTS = parseCSV(text);
      document.getElementById("totalStudents").textContent = STUDENTS.length;
    } catch (err) {
      console.error("❌ Failed to load student CSV:", err);
    }
  }

  /* -------------------------------------------------------
     LOGIN NORMALIZATION
  ------------------------------------------------------- */
  function normalizeLogin(name) {
    return name.replace(/\s+/g, "").toLowerCase();
  }

  /* -------------------------------------------------------
     RENDER STUDENTS
  ------------------------------------------------------- */
  function buildStudentCard(st) {
    const fullName = [st.First_name, st.Other_names, st.Last_name].filter(Boolean).join(" ");
    return `
      <div class="student-card">
        <div class="avatar">${(st.First_name || "?")[0].toUpperCase()}</div>

        <div class="ml-3">
          <h4>${fullName}</h4>
          <p class="detail-line"><strong>ID:</strong> ${st.Admission_number}</p>
          <p class="detail-line"><strong>Class:</strong> ${st.Class} (${st.Class_category})</p>
          <p class="detail-line"><strong>Phone:</strong> ${st.Phone || "—"}</p>
          <p class="login-hint">
            Login: <span class="login-format">${st.First_name}</span> →
            <span class="normalized">${normalizeLogin(st.First_name || "")}</span>
          </p>
        </div>
      </div>
    `;
  }

  function renderStudents(list) {
    studentList.innerHTML = "";
    if (!list.length) {
      studentList.innerHTML = `<div class="student-empty">No matching students found.</div>`;
      return;
    }
    list.forEach(st => {
      const card = document.createElement("div");
      card.innerHTML = buildStudentCard(st);
      studentList.appendChild(card.firstElementChild);
    });
  }

  /* -------------------------------------------------------
     STUDENT MODAL LOGIC
  ------------------------------------------------------- */
  function openStudentModal() {
    studentIdModal.classList.remove("hidden");
    studentSearchInput.value = "";
    renderStudents(STUDENTS);
  }

  closeStudentIdModal.addEventListener("click", () =>
    studentIdModal.classList.add("hidden")
  );

  studentSearchInput.addEventListener("input", e => {
    const term = e.target.value.toLowerCase();
    renderStudents(
      STUDENTS.filter(st =>
        Object.values(st).join(" ").toLowerCase().includes(term)
      )
    );
  });

  if (viewStudentIdsBtn) viewStudentIdsBtn.addEventListener("click", openStudentModal);

  document.querySelectorAll("[data-action='students']").forEach(tile =>
    tile.addEventListener("click", openStudentModal)
  );

  /* -------------------------------------------------------
     TEACHER DATA LOADING
  ------------------------------------------------------- */
  async function loadTeachers() {
    try {
      const res = await fetch("/generate_teacher_ids");
      const data = await res.json();
      TEACHERS = data.teachers || [];

      totalTeachers.textContent = TEACHERS.length;
      renderTeacherTable();
      lastSync.textContent = new Date().toLocaleString();
    } catch (err) {
      console.error("❌ Failed to load teachers:", err);
    }
  }

    /* -------------------------------------------------------
      RENDER TEACHER TABLE
  ------------------------------------------------------- */

  function renderTeacherTable() {
    teacherTableBody.innerHTML = "";

    TEACHERS.forEach(t => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${t.teacher_id}</td>
        <td>${t.password}</td>
        <td>${t.status || "Active"}</td>
        <td>${new Date(t.created_at).toLocaleDateString()}</td>
        <td>
          <button class="action-btn action-suspend" data-id="${t.id}">
            <i class="fa-solid fa-ban"></i>
          </button>
          <button class="action-btn action-delete" data-id="${t.id}">
            <i class="fa-solid fa-trash"></i>
          </button>
        </td>
      `;
      teacherTableBody.appendChild(tr);
    });
  }


  /* -------------------------------------------------------
     OPEN TEACHER OPTIONS MODAL (ALL ENTRY POINTS)
  ------------------------------------------------------- */
  function openTeacherOptions() {
    teacherOptionsModal.classList.remove("hidden");
  }

  if (generateTeacherBtn) generateTeacherBtn.addEventListener("click", openTeacherOptions);
  if (openTeacherGenerator) openTeacherGenerator.addEventListener("click", openTeacherOptions);
  if (viewTeacherIdsTile) viewTeacherIdsTile.addEventListener("click", openTeacherOptions);

  if (closeTeacherOptionsModal) {
    closeTeacherOptionsModal.addEventListener("click", () =>
      teacherOptionsModal.classList.add("hidden")
    );
  }

  /* -------------------------------------------------------
     GENERATE ONE TEACHER ID
  ------------------------------------------------------- */
  generateOneTeacherBtn.addEventListener("click", async () => {
    try {
      const fd = new FormData();
      fd.append("count", 1);

      const res = await fetch("/generate_teacher_ids", { method: "POST", body: fd });
      const data = await res.json();

      TEACHERS = data.teachers;
      renderTeacherTable();
      lastGenerated.textContent = new Date().toLocaleString();

      teacherOptionsModal.classList.add("hidden");
      showTeacherIdModal(data.generated);
    } catch (err) {
      console.error("❌ Single teacher gen failed:", err);
    }
  });

  /* -------------------------------------------------------
     GENERATE MULTIPLE TEACHERS
  ------------------------------------------------------- */
  openGenerateMultipleBtn.addEventListener("click", () => {
    teacherOptionsModal.classList.add("hidden");
    generateTeacherModal.classList.remove("hidden");
  });

  closeGenerateModal.addEventListener("click", () =>
    generateTeacherModal.classList.add("hidden")
  );

  cancelGenerateBtn.addEventListener("click", () =>
    generateTeacherModal.classList.add("hidden")
  );

  generateTeacherForm.addEventListener("submit", async e => {
    e.preventDefault();

    const n = parseInt(document.getElementById("numTeachers").value);
    if (!n || n < 1) return alert("Enter valid count");

    try {
      const fd = new FormData();
      fd.append("count", n);

      const res = await fetch("/generate_teacher_ids", { method: "POST", body: fd });
      const data = await res.json();

      TEACHERS = data.teachers;
      renderTeacherTable();

      lastGenerated.textContent = new Date().toLocaleString();
      generateTeacherModal.classList.add("hidden");

      showTeacherIdModal(data.generated);
    } catch (err) {
      console.error("❌ Multiple teacher gen failed:", err);
    }
  });

  /* -------------------------------------------------------
     VIEW TEACHER ID LIST
  ------------------------------------------------------- */
  viewTeacherIdsBtn.addEventListener("click", () => {
    showTeacherIdModal(TEACHERS);
  });

  closeTeacherIdModal.addEventListener("click", () =>
    teacherIdModal.classList.add("hidden")
  );

  refreshTeacherList.addEventListener("click", async () => {
    await loadTeachers();
    alert("🔄 Refreshed!");
  });

  downloadTeacherCSV.addEventListener("click", () => {
    window.location.href = "/export_teacher_ids";
  });


  /* -------------------------------------------------------
      SHOW TEACHER ID MODAL 
  ------------------------------------------------------- */
  function showTeacherIdModal(list) {
    teacherIdResults.innerHTML = "";

    if (!list.length) {
      teacherIdResults.innerHTML = `
        <p class="text-center text-gray-500">No teacher IDs found</p>
      `;
    } else {
      list.forEach(tc => {
        const div = document.createElement("div");
        div.className = "p-2 bg-white rounded-lg shadow flex justify-between text-sm";
        div.innerHTML = `
          <span><b>${tc.teacher_id}</b> — ${tc.password}</span>
          <span class="text-xs text-gray-500">${tc.status || "Active"}</span>
        `;
        teacherIdResults.appendChild(div);
      });
    }

    teacherIdModal.classList.remove("hidden");
  }

  /* -------------------------------------------------------
     INITIAL LOAD
  ------------------------------------------------------- */
  await loadCSVStudents();
  await loadTeachers();


  /* -------------------------------------------------------
     DELETE TEACHER ID — Custom Modal
  ------------------------------------------------------- */

  let deleteTargetId = null;

  const deleteConfirmModal = document.getElementById("deleteConfirmModal");
  const confirmDeleteBtn = document.getElementById("confirmDelete");
  const cancelDeleteBtn = document.getElementById("cancelDelete");
  const closeDeleteConfirm = document.getElementById("closeDeleteConfirm");

  // Open modal when clicking delete icon
  teacherTableBody.addEventListener("click", (e) => {
    const btn = e.target.closest(".action-delete");
    if (!btn) return;

    deleteTargetId = btn.dataset.id;
    deleteConfirmModal.classList.remove("hidden");
  });

  // Close modal
  function closeDeleteModal() {
    deleteConfirmModal.classList.add("hidden");
    deleteTargetId = null;
  }

  cancelDeleteBtn.addEventListener("click", closeDeleteModal);
  closeDeleteConfirm.addEventListener("click", closeDeleteModal);

  // Confirm delete
  confirmDeleteBtn.addEventListener("click", async () => {
    if (!deleteTargetId) return;

    try {
      const res = await fetch(`/delete_teacher_id/${deleteTargetId}`, {
        method: "DELETE"
      });

      const data = await res.json();

      if (data.success) {
        // Remove from list instantly
        TEACHERS = TEACHERS.filter(t => t.id != deleteTargetId);

        // Re-render table immediately
        renderTeacherTable();
      } else {
        alert("Failed to delete: " + (data.error || "Unknown error"));
      }
    } catch (err) {
      console.error("❌ Delete failed:", err);
    }

    closeDeleteModal();
  });

});   // ✅ FINAL CLOSING BRACKET FOR DOMContentLoaded



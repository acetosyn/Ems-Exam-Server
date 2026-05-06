// =====================================================================================
// EMIS STUDENTS.JS — FINAL 2025/2026
// STATIC SUBJECT DROPDOWN + OPTIONAL PUSHED SUBJECT PREVIEW
// -------------------------------------------------------------------------------------
// Behaviour:
//  • Dropdown always shows 13 official subjects (from HTML template)
//  • NO validation before entering exam_dashboard
//  • Student ALWAYS goes to exam_dashboard
//  • exam_dashboard decides if exam exists or not
//  • Available Exams card STILL shows pushed subjects only
// =====================================================================================

document.addEventListener("DOMContentLoaded", () => {

  const subjectsBtn         = document.getElementById("openSubjectsBtn");
  const subjectsCard        = document.getElementById("availableSubjectsCard");
  const subjectsList        = document.getElementById("availableSubjectsList");
  const viewSubjectsBtn     = document.getElementById("viewSubjectsBtn");

  const examModal           = document.getElementById("examModal");
  const openExamPortalBtn   = document.getElementById("openExamPortal");
  const closeExamModalBtn   = document.getElementById("closeExamModal");

  const subjectDropdown     = document.getElementById("subjectDropdown");
  const startExamBtn        = document.getElementById("startExamBtn");

  const footerYear          = document.getElementById("year");
  const currentYear         = new Date().getFullYear();

  let pushedSubjects = [];

  // ------------------------------------------------------------
  // Fetch pushed subjects (only for preview card UI)
  // ------------------------------------------------------------
  async function fetchPushedSubjects() {
    try {
      const res = await fetch(`/api/student/subjects?year=${currentYear}`);
      const data = await res.json();
      pushedSubjects = data.subjects || [];
    } catch (err) {
      console.error("❌ Error fetching pushed subjects:", err);
      pushedSubjects = [];
    }
  }

  // ------------------------------------------------------------
  // Available Exams Card
  // ------------------------------------------------------------
  async function loadSubjectsCard() {
    await fetchPushedSubjects();

    subjectsList.innerHTML = "";

    if (!pushedSubjects.length) {
      subjectsList.innerHTML = `<li class="empty">No subjects pushed yet.</li>`;
    } else {
      pushedSubjects.forEach(sub => {
        const li = document.createElement("li");
        li.innerHTML = `<i class="fa-solid fa-book"></i> ${sub}`;
        subjectsList.appendChild(li);
      });
    }

    subjectsCard.classList.add("show");
  }

  subjectsBtn?.addEventListener("click", loadSubjectsCard);
  viewSubjectsBtn?.addEventListener("click", loadSubjectsCard);

  // ------------------------------------------------------------
  // Open / Close Exam Modal — NO validation
  // ------------------------------------------------------------
  openExamPortalBtn?.addEventListener("click", () => {
    examModal.classList.add("show");
  });

  closeExamModalBtn?.addEventListener("click", () => {
    examModal.classList.remove("show");
  });

  examModal?.addEventListener("click", (e) => {
    if (e.target === examModal) examModal.classList.remove("show");
  });

  // ------------------------------------------------------------
  // Enable start button only when subject selected
  // (NO validation against pushed subjects)
  // ------------------------------------------------------------
  subjectDropdown?.addEventListener("change", () => {
    startExamBtn.disabled = !subjectDropdown.value.trim();
  });

  // ------------------------------------------------------------
  // Move to exam_dashboard (backend decides if exam available)
  // ------------------------------------------------------------
  startExamBtn?.addEventListener("click", () => {
    const subject = subjectDropdown.value.trim();
    if (!subject) return;
    window.location.href = `/exam_dashboard?subject=${encodeURIComponent(subject)}`;
  });

  if (footerYear) footerYear.textContent = currentYear;
});

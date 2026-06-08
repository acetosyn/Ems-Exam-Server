// static/js/student-exams.js

document.addEventListener("DOMContentLoaded", () => {
  const subjectDropdown = document.getElementById("subjectDropdown");
  const startBtn = document.getElementById("startExamBtn");

  function syncStartButton() {
    if (!subjectDropdown || !startBtn) return;
    startBtn.disabled = !subjectDropdown.value.trim();
  }

  syncStartButton();

  subjectDropdown?.addEventListener("change", syncStartButton);
});
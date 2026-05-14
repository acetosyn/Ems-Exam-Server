// static/js/student-exams.js

document.addEventListener("DOMContentLoaded", () => {
  const subjectDropdown = document.getElementById("subjectDropdown");
  const startBtn = document.getElementById("startExamBtn");

  if (subjectDropdown && startBtn) {
    startBtn.disabled = !subjectDropdown.value.trim();

    subjectDropdown.addEventListener("change", () => {
      startBtn.disabled = !subjectDropdown.value.trim();
    });
  }
});
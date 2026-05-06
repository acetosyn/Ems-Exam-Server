// =============================================================
// EMIS ADMIN DASHBOARD — dashboard.js
// Handles: Refresh, Command Palette trigger, stat placeholders
// (Backend integrations will populate these later)
// =============================================================
document.addEventListener("DOMContentLoaded", () => {
  const refreshBtn = document.getElementById("refreshDashboard");
  const cmdPaletteBtn = document.getElementById("cmdPaletteBtn");

  // Simple pulse feedback on refresh click
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      refreshBtn.classList.add("animate-pulse");
      setTimeout(() => refreshBtn.classList.remove("animate-pulse"), 800);
    });
  }

  // Placeholder for future command palette
  if (cmdPaletteBtn) {
    cmdPaletteBtn.addEventListener("click", () => {
      console.log("🧠 Command Palette triggered (coming soon)");
    });
  }

  // Placeholder live stats (will be populated later)
  const stats = {
    students: document.getElementById("statTotalStudents"),
    exams: document.getElementById("statActiveExams"),
    pending: document.getElementById("statPending"),
    avg: document.getElementById("statAvg"),
  };

  // Initialize baseline view
  Object.values(stats).forEach(el => el && (el.textContent = "--"));
});

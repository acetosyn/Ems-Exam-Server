/* ==========================================================
   privileges.js — EMIS Role Access UI Guard v2.0
   ----------------------------------------------------------
   Teacher sidebar access:
   • Teachers
   • Students (existing teacher route)
   • Results
   • Attendance
   • CA Tests

   Report Sheets, IDs, Promotion, Settings, Admin Dashboard
   and other Admin-only sections remain restricted.
========================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const sidebarRole = document.querySelector(".sidebar-role");
  if (!sidebarRole) return;

  const userType = sidebarRole.textContent.trim().toLowerCase();
  if (userType !== "teacher") return;

  const allowedSections = new Set([
    "teachers",
    "students",
    "results",
    "attendance",
    "ca tests",
    "ca test"
  ]);

  const normalizeLabel = (value) => String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
  const navLinks = document.querySelectorAll(".sidebar-menu a");

  navLinks.forEach(link => {
    const text = normalizeLabel(link.textContent);
    const allowed = allowedSections.has(text);

    link.classList.toggle("restricted", !allowed);
    link.style.opacity = allowed ? "" : "0.5";
    link.style.pointerEvents = "auto";

    if (allowed) return;

    link.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      showAccessMessage(`Access Restricted — Teacher accounts cannot access "${text.toUpperCase()}".`);
    });
  });
});


function showAccessMessage(message) {
  let box = document.getElementById("accessRestrictionNotice");

  if (!box) {
    box = document.createElement("div");
    box.id = "accessRestrictionNotice";
    box.style.position = "fixed";
    box.style.top = "20px";
    box.style.right = "20px";
    box.style.maxWidth = "420px";
    box.style.padding = "14px 18px";
    box.style.background = "#e11d48";
    box.style.color = "#fff";
    box.style.fontWeight = "700";
    box.style.fontFamily = "Inter, sans-serif";
    box.style.borderRadius = "10px";
    box.style.boxShadow = "0 4px 15px rgba(0,0,0,0.2)";
    box.style.zIndex = "99999";
    box.style.transition = "all 0.3s ease";
    document.body.appendChild(box);
  }

  box.textContent = message;
  box.style.opacity = "1";
  box.style.transform = "translateY(0)";

  clearTimeout(window.__emisAccessNoticeTimer);
  window.__emisAccessNoticeTimer = setTimeout(() => {
    box.style.opacity = "0";
    box.style.transform = "translateY(-10px)";
  }, 3200);
}

/* ==========================================================
   privileges.js — Access Restriction Logic for Roles (v1.0)
   ----------------------------------------------------------
   - Restricts teacher accounts to limited sections
   - Works after login across all dashboards
   - Compatible with your current sidebar + layout
========================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const sidebarRole = document.querySelector(".sidebar-role");
  if (!sidebarRole) return; // stop if sidebar not loaded

  const userType = sidebarRole.textContent.trim().toLowerCase();

  // ======================================================
  // 1️⃣ Only Teachers are restricted
  // ======================================================
  if (userType === "teacher") {
    // Allowed sidebar items for teacher
    const allowedSections = [
      "teachers",
      "students",
      "past questions",
      "mock exam",
      "results"
    ];

    const navLinks = document.querySelectorAll(".sidebar-menu a");

    navLinks.forEach(link => {
      const text = link.textContent.trim().toLowerCase();

      // If not in the allowed list → restrict
      if (!allowedSections.includes(text)) {
        link.classList.add("restricted");
        link.style.opacity = "0.5";
        link.style.pointerEvents = "auto";
        link.addEventListener("click", e => {
          e.preventDefault();
          showAccessMessage(`Access Restricted — You don’t have permission to access "${text.toUpperCase()}".`);
        });
      }
    });
  }
});


// ==========================================================
// 🔔 Popup / Toast-like Flash Message for Access Block
// ==========================================================
function showAccessMessage(message) {
  let box = document.getElementById("accessRestrictionNotice");
  if (!box) {
    box = document.createElement("div");
    box.id = "accessRestrictionNotice";
    box.style.position = "fixed";
    box.style.top = "20px";
    box.style.right = "20px";
    box.style.padding = "14px 18px";
    box.style.background = "#e11d48";
    box.style.color = "#fff";
    box.style.fontWeight = "600";
    box.style.fontFamily = "Inter, sans-serif";
    box.style.borderRadius = "10px";
    box.style.boxShadow = "0 4px 15px rgba(0,0,0,0.2)";
    box.style.zIndex = "2000";
    box.style.transition = "all 0.4s ease";
    document.body.appendChild(box);
  }
  box.textContent = message;
  box.style.opacity = "1";
  box.style.transform = "translateY(0)";

  // fade out after 3s
  setTimeout(() => {
    box.style.opacity = "0";
    box.style.transform = "translateY(-10px)";
  }, 3000);
}

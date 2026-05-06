// =============================================================
// EMIS Admin Login Script — Optimized v4
// Handles: Password toggle, Validation, Overlay, Toast, Typewriter
// =============================================================
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("adminLoginForm");
  const overlay = document.getElementById("loadingOverlay");

  // =========================================================
  // PASSWORD TOGGLE
  // =========================================================
  document.querySelectorAll(".toggle-password").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const input = document.getElementById(targetId);
      if (!input) return;

      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      btn.innerHTML = isHidden
        ? '<i class="fas fa-eye-slash"></i>'
        : '<i class="fas fa-eye"></i>';
    });
  });

  // =========================================================
  // FORM SUBMIT HANDLER
  // =========================================================
  if (form) {
    form.addEventListener("submit", (e) => {
      const inputs = form.querySelectorAll("input[required]");
      let valid = true;

      inputs.forEach((input) => {
        if (!input.value.trim()) valid = false;
      });

      if (!valid) {
        e.preventDefault();
        showToast("⚠️ Please fill in all fields", "error");
        return;
      }

      // Show loading overlay after successful validation
      if (overlay) overlay.classList.remove("hidden");
    });
  }

  // =========================================================
  // TYPEWRITER EFFECT
  // =========================================================
  const el = document.getElementById("typewriter");
  if (el) {
    const messages = [
      "Welcome to EMIS Exam Portal",
      "Login below to access your dashboard",
      "Powered by Epiconsult Tech Division"
    ];

    let msgIndex = 0;
    let charIndex = 0;
    let deleting = false;

    const textSpan = document.createElement("span");
    const cursor = document.createElement("span");
    cursor.className = "typewriter-cursor";
    cursor.textContent = "|";
    el.innerHTML = "";
    el.appendChild(textSpan);
    el.appendChild(cursor);

    const type = () => {
      const message = messages[msgIndex];
      if (!deleting) {
        textSpan.textContent = message.substring(0, charIndex++);
        if (charIndex > message.length) {
          deleting = true;
          setTimeout(type, 1000);
          return;
        }
      } else {
        textSpan.textContent = message.substring(0, charIndex--);
        if (charIndex === 0) {
          deleting = false;
          msgIndex = (msgIndex + 1) % messages.length;
        }
      }
      setTimeout(type, deleting ? 40 : 70);
    };

    type();
  }
});

// =============================================================
// TOAST NOTIFICATION SYSTEM
// =============================================================
function showToast(message, type = "info") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  // Animate toast fade out
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}

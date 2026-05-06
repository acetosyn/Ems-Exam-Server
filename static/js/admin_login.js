// =============================================================
// EMIS Admin Login Script — v8 (Live Submit + Rolling Circle Loader)
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
// FORM SUBMIT HANDLER (Live POST + Smooth Loader + Inline Errors)
// =========================================================
if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Prevent double submissions
    if (form.classList.contains("submitting")) return;
    form.classList.add("submitting");

    // Validate inputs
    const inputs = form.querySelectorAll("input[required]");
    let valid = true;
    inputs.forEach((input) => {
      if (!input.value.trim()) valid = false;
    });

    if (!valid) {
      showToast("⚠️ Please fill in all fields", "error");
      form.classList.remove("submitting");
      return;
    }

    // ✅ Show loader overlay + button spinner
    overlay.classList.remove("hidden");
    const loginBtn = document.querySelector("#loginButton");
    const btnText = loginBtn.querySelector(".btn-text");
    const btnLoader = loginBtn.querySelector(".btn-loader");

    btnText.textContent = "Authenticating...";
    btnLoader.classList.remove("hidden");

    // Remove any previous inline error box
    document.querySelectorAll(".error-box").forEach(el => el.remove());

    try {
      const formData = new FormData(form);
      const response = await fetch("/admin_login", {
        method: "POST",
        body: formData,
      });

      // ✅ Redirect if login success (Admin or Teacher)
      if (response.redirected) {
        showToast("✅ Login successful! Redirecting...", "success");
        window.location.href = response.url;
        return;
      }

      // 🔍 Parse returned HTML (error cases)
      const html = await response.text();

      // Detect backend error messages
      let errorMessage = "⚠️ Login failed. Please try again.";
      if (html.includes("Invalid") || html.includes("❌")) {
        errorMessage = "❌ Invalid username or password";
      }

      // ✅ Create and inject visible error box above form
      const errorBox = document.createElement("div");
      errorBox.className =
        "error-box bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4 animate-fadeIn";
      errorBox.innerHTML = `<strong class='font-semibold'>Login Failed:</strong> ${errorMessage}`;
      form.parentNode.insertBefore(errorBox, form);

      showToast(errorMessage, "error");
    } catch (err) {
      console.error("Login error:", err);

      // Inject network error box
      const errorBox = document.createElement("div");
      errorBox.className =
        "error-box bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4 animate-fadeIn";
      errorBox.innerHTML =
        "<strong class='font-semibold'>Connection Error:</strong> 🚫 Please check your network.";
      form.parentNode.insertBefore(errorBox, form);

      showToast("🚫 Network error. Please check your connection.", "error");
    } finally {
      // ✅ Hide loader if not redirected
      setTimeout(() => {
        if (!overlay.classList.contains("hidden")) {
          overlay.classList.add("hidden");
          btnLoader.classList.add("hidden");
          btnText.textContent = "🔑 Login to Dashboard";
          form.classList.remove("submitting");
        }
      }, 800);
    }
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
      "Empowering academic excellence with technology"
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

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}

// user_login.js — Candidate Login interactions with subject selection

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("userLoginForm");
  const overlay = document.getElementById("loadingOverlay");
  const passwordToggle = document.querySelector(".toggle-password");
  const passwordInput = document.getElementById("password");
  const loginBtn = document.querySelector(".login-btn");
  const btnText = loginBtn.querySelector(".btn-text");
  const btnSpinner = loginBtn.querySelector(".loading-spinner");
  const subjectSelect = document.getElementById("subject"); // new subject dropdown

  // Toggle password visibility
  if (passwordToggle) {
    passwordToggle.addEventListener("click", () => {
      const type = passwordInput.getAttribute("type") === "password" ? "text" : "password";
      passwordInput.setAttribute("type", type);
      passwordToggle.textContent = type === "password" ? "👁️" : "🙈";
    });
  }

  // Form submit
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    let valid = true;
    form.querySelectorAll("input, select").forEach(el => {
      if (!el.value) {
        el.style.borderColor = "red";
        valid = false;
      } else {
        el.style.borderColor = "#cbd5e1";
      }
    });

    if (!valid) {
      alert("⚠️ Please fill in all required fields (including subject)");
      return;
    }

    // Show spinner
    btnText.classList.add("hidden");
    btnSpinner.classList.remove("hidden");
    overlay.classList.remove("hidden");

    // Save subject choice in sessionStorage (optional: helpful for front-end display)
    if (subjectSelect) {
      sessionStorage.setItem("chosenSubject", subjectSelect.value);
    }

    // Simulate login delay
    setTimeout(() => {
      form.submit(); // continue to backend
    }, 1200);
  });
});

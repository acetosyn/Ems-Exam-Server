// =============================================================
// EMIS ADMIN LOGIN SCRIPT — Modern Upgrade
// Features:
// 1. Password visibility toggle
// 2. Remember username locally
// 3. Smart form validation
// 4. Caps Lock warning
// 5. Password strength detector
// 6. Orbit-style loader class handling
// 7. Toast notifications
// 8. Double-submit prevention
// 9. Keyboard shortcuts
// 10. Network-safe async login
// =============================================================

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("adminLoginForm");
  const overlay = document.getElementById("loadingOverlay");
  const loginBtn = document.getElementById("loginButton");
  const usernameInput = document.getElementById("admin-username");
  const passwordInput = document.getElementById("admin-password");
  const rememberInput = document.querySelector('input[name="remember"]');

  initPasswordToggle();
  initRememberUsername();
  initInputEffects();
  initCapsLockWarning();
  initPasswordStrength();
  initKeyboardShortcuts();
  initLoginSubmit();

  // =========================================================
  // PASSWORD TOGGLE
  // =========================================================
  function initPasswordToggle() {
    document.querySelectorAll(".toggle-password").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.dataset.target;
        const input = document.getElementById(targetId);
        const icon = btn.querySelector("i");

        if (!input || !icon) return;

        const isHidden = input.type === "password";
        input.type = isHidden ? "text" : "password";

        icon.classList.toggle("fa-eye", !isHidden);
        icon.classList.toggle("fa-eye-slash", isHidden);

        btn.setAttribute(
          "aria-label",
          isHidden ? "Hide password" : "Show password"
        );

        input.focus();
        showMiniHint(btn, isHidden ? "Visible" : "Hidden");
      });
    });
  }

  // =========================================================
  // REMEMBER USERNAME
  // =========================================================
  function initRememberUsername() {
    if (!usernameInput || !rememberInput) return;

    const savedUsername = localStorage.getItem("emis_admin_username");

    if (savedUsername) {
      usernameInput.value = savedUsername;
      rememberInput.checked = true;

      if (passwordInput) {
        passwordInput.focus();
      }
    }

    rememberInput.addEventListener("change", () => {
      if (!rememberInput.checked) {
        localStorage.removeItem("emis_admin_username");
      }
    });
  }

  // =========================================================
  // INPUT UI EFFECTS
  // =========================================================
  function initInputEffects() {
    const inputs = document.querySelectorAll(".input-box input");

    inputs.forEach((input) => {
      markFilled(input);

      input.addEventListener("input", () => {
        markFilled(input);
        clearFieldError(input);
      });

      input.addEventListener("focus", () => {
        input.closest(".input-box")?.classList.add("is-focused");
      });

      input.addEventListener("blur", () => {
        input.closest(".input-box")?.classList.remove("is-focused");
        markFilled(input);
      });
    });
  }

  function markFilled(input) {
    const box = input.closest(".input-box");
    if (!box) return;

    if (input.value.trim()) {
      box.classList.add("has-value");
    } else {
      box.classList.remove("has-value");
    }
  }

  // =========================================================
  // CAPS LOCK WARNING
  // =========================================================
  function initCapsLockWarning() {
    if (!passwordInput) return;

    let warning = document.getElementById("capsLockWarning");

    if (!warning) {
      warning = document.createElement("div");
      warning.id = "capsLockWarning";
      warning.className = "caps-warning hidden";
      warning.innerHTML =
        '<i class="fa-solid fa-triangle-exclamation"></i> Caps Lock is on';
      passwordInput.closest(".form-group")?.appendChild(warning);
    }

    passwordInput.addEventListener("keyup", (event) => {
      const isCaps = event.getModifierState && event.getModifierState("CapsLock");
      warning.classList.toggle("hidden", !isCaps);
    });

    passwordInput.addEventListener("blur", () => {
      warning.classList.add("hidden");
    });
  }

  // =========================================================
  // PASSWORD STRENGTH DETECTOR
  // =========================================================
  function initPasswordStrength() {
    if (!passwordInput) return;

    let meter = document.getElementById("passwordStrength");

    if (!meter) {
      meter = document.createElement("div");
      meter.id = "passwordStrength";
      meter.className = "password-strength hidden";
      meter.innerHTML = `
        <div class="strength-track">
          <span class="strength-fill"></span>
        </div>
        <small class="strength-text">Password strength</small>
      `;

      passwordInput.closest(".form-group")?.appendChild(meter);
    }

    passwordInput.addEventListener("input", () => {
      const value = passwordInput.value;
      const score = getPasswordScore(value);

      updatePasswordMeter(meter, score, value.length);
    });
  }

  function getPasswordScore(value) {
    let score = 0;

    if (value.length >= 6) score++;
    if (value.length >= 10) score++;
    if (/[A-Z]/.test(value)) score++;
    if (/[0-9]/.test(value)) score++;
    if (/[^A-Za-z0-9]/.test(value)) score++;

    return Math.min(score, 5);
  }

  function updatePasswordMeter(meter, score, length) {
    const fill = meter.querySelector(".strength-fill");
    const text = meter.querySelector(".strength-text");

    if (!fill || !text) return;

    if (!length) {
      meter.classList.add("hidden");
      fill.style.width = "0%";
      text.textContent = "Password strength";
      return;
    }

    meter.classList.remove("hidden");

    const widthMap = ["12%", "25%", "45%", "65%", "82%", "100%"];
    const labelMap = ["Very weak", "Weak", "Fair", "Good", "Strong", "Excellent"];
    const classMap = ["very-weak", "weak", "fair", "good", "strong", "excellent"];

    meter.classList.remove(
      "very-weak",
      "weak",
      "fair",
      "good",
      "strong",
      "excellent"
    );

    meter.classList.add(classMap[score]);
    fill.style.width = widthMap[score];
    text.textContent = labelMap[score];
  }

  // =========================================================
  // KEYBOARD SHORTCUTS
  // =========================================================
  function initKeyboardShortcuts() {
    document.addEventListener("keydown", (event) => {
      const key = event.key.toLowerCase();

      if (event.altKey && key === "u" && usernameInput) {
        event.preventDefault();
        usernameInput.focus();
      }

      if (event.altKey && key === "p" && passwordInput) {
        event.preventDefault();
        passwordInput.focus();
      }

      if (event.key === "Escape") {
        hideOverlay();
        closeToasts();
      }
    });
  }

  // =========================================================
  // FORM SUBMIT
  // =========================================================
  function initLoginSubmit() {
    if (!form) return;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      if (form.classList.contains("submitting")) return;

      removeInlineError();

      const validation = validateForm();

      if (!validation.valid) {
        showInlineError(validation.message);
        showToast(validation.message, "error");
        shakeCard();
        return;
      }

      rememberUsernameIfNeeded();
      setSubmitting(true);

      try {
        const formData = new FormData(form);
        const actionUrl = form.getAttribute("action") || window.location.href;

        const response = await fetch(actionUrl, {
          method: "POST",
          body: formData,
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "XMLHttpRequest"
          }
        });

        if (response.redirected) {
          showToast("Login successful. Redirecting...", "success");
          window.location.href = response.url;
          return;
        }

        const html = await response.text();
        const errorMessage = extractLoginError(html);

        showInlineError(errorMessage);
        showToast(errorMessage, "error");
        shakeCard();
      } catch (error) {
        console.error("Login error:", error);

        const message =
          "Connection error. Please check your network and try again.";

        showInlineError(message);
        showToast(message, "error");
        shakeCard();
      } finally {
        setTimeout(() => {
          if (!window.location.href.includes("dashboard")) {
            setSubmitting(false);
          }
        }, 700);
      }
    });
  }

  // =========================================================
  // VALIDATION
  // =========================================================
  function validateForm() {
    const username = usernameInput?.value.trim() || "";
    const password = passwordInput?.value.trim() || "";

    clearAllFieldErrors();

    if (!username && !password) {
      markFieldError(usernameInput);
      markFieldError(passwordInput);
      return {
        valid: false,
        message: "Please enter your username and password."
      };
    }

    if (!username) {
      markFieldError(usernameInput);
      usernameInput?.focus();
      return {
        valid: false,
        message: "Please enter your username or ID."
      };
    }

    if (!password) {
      markFieldError(passwordInput);
      passwordInput?.focus();
      return {
        valid: false,
        message: "Please enter your password."
      };
    }

    if (password.length < 3) {
      markFieldError(passwordInput);
      passwordInput?.focus();
      return {
        valid: false,
        message: "Password is too short."
      };
    }

    return {
      valid: true,
      message: ""
    };
  }

  function markFieldError(input) {
    input?.closest(".input-box")?.classList.add("has-error");
  }

  function clearFieldError(input) {
    input?.closest(".input-box")?.classList.remove("has-error");
  }

  function clearAllFieldErrors() {
    document.querySelectorAll(".input-box.has-error").forEach((box) => {
      box.classList.remove("has-error");
    });
  }

  // =========================================================
  // SUBMITTING STATE
  // =========================================================
  function setSubmitting(isSubmitting) {
    const btnText = loginBtn?.querySelector(".btn-text");
    const btnLoader = loginBtn?.querySelector(".btn-loader");

    form?.classList.toggle("submitting", isSubmitting);
    loginBtn?.classList.toggle("is-loading", isSubmitting);

    if (loginBtn) {
      loginBtn.disabled = isSubmitting;
    }

    if (isSubmitting) {
      showOverlay();

      if (btnText) {
        btnText.innerHTML =
          '<i class="fa-solid fa-shield-halved"></i> Authenticating...';
      }

      btnLoader?.classList.remove("hidden");
    } else {
      hideOverlay();

      if (btnText) {
        btnText.innerHTML =
          '<i class="fa-solid fa-right-to-bracket"></i> Login to Dashboard';
      }

      btnLoader?.classList.add("hidden");
    }
  }

  function showOverlay() {
    overlay?.classList.remove("hidden");
    overlay?.classList.add("is-visible");
    document.body.classList.add("login-busy");
  }

  function hideOverlay() {
    overlay?.classList.add("hidden");
    overlay?.classList.remove("is-visible");
    document.body.classList.remove("login-busy");
  }

  // =========================================================
  // ERROR HANDLING
  // =========================================================
  function extractLoginError(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    const errorBox = doc.querySelector(".error-box");
    const text = errorBox?.textContent?.trim();

    if (text) {
      return text.replace(/\s+/g, " ");
    }

    if (/invalid/i.test(html)) {
      return "Invalid username or password.";
    }

    if (/failed/i.test(html)) {
      return "Login failed. Please confirm your details.";
    }

    return "Login failed. Please try again.";
  }

  function showInlineError(message) {
    removeInlineError();

    const errorBox = document.createElement("div");
    errorBox.className = "error-box js-error-box";
    errorBox.innerHTML = `
      <i class="fa-solid fa-triangle-exclamation"></i>
      <div>
        <strong>Login Failed</strong>
        <span>${escapeHtml(message)}</span>
      </div>
    `;

    form?.parentNode?.insertBefore(errorBox, form);
  }

  function removeInlineError() {
    document.querySelectorAll(".js-error-box").forEach((box) => box.remove());
  }

  function shakeCard() {
    const card = document.querySelector(".auth-card");

    if (!card) return;

    card.classList.remove("shake-card");
    void card.offsetWidth;
    card.classList.add("shake-card");
  }

  // =========================================================
  // REMEMBER USERNAME SAVE
  // =========================================================
  function rememberUsernameIfNeeded() {
    if (!usernameInput || !rememberInput) return;

    if (rememberInput.checked) {
      localStorage.setItem("emis_admin_username", usernameInput.value.trim());
    } else {
      localStorage.removeItem("emis_admin_username");
    }
  }

  // =========================================================
  // MINI HINT
  // =========================================================
  function showMiniHint(target, message) {
    if (!target) return;

    const oldHint = document.querySelector(".mini-hint");
    oldHint?.remove();

    const hint = document.createElement("span");
    hint.className = "mini-hint";
    hint.textContent = message;

    document.body.appendChild(hint);

    const rect = target.getBoundingClientRect();

    hint.style.left = `${rect.left + rect.width / 2}px`;
    hint.style.top = `${rect.top - 8}px`;

    setTimeout(() => {
      hint.remove();
    }, 900);
  }

  // =========================================================
  // TOAST SYSTEM
  // =========================================================
  function showToast(message, type = "info") {
    let container = document.querySelector(".toast-container");

    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;

    const icon = getToastIcon(type);

    toast.innerHTML = `
      <i class="${icon}"></i>
      <span>${escapeHtml(message)}</span>
      <button type="button" aria-label="Close notification">
        <i class="fa-solid fa-xmark"></i>
      </button>
    `;

    const closeBtn = toast.querySelector("button");

    closeBtn?.addEventListener("click", () => {
      removeToast(toast);
    });

    container.appendChild(toast);

    setTimeout(() => {
      removeToast(toast);
    }, 4200);
  }

  function getToastIcon(type) {
    if (type === "success") return "fa-solid fa-circle-check";
    if (type === "error") return "fa-solid fa-triangle-exclamation";
    if (type === "warning") return "fa-solid fa-circle-exclamation";
    return "fa-solid fa-circle-info";
  }

  function removeToast(toast) {
    if (!toast) return;

    toast.classList.add("is-leaving");

    setTimeout(() => {
      toast.remove();
    }, 250);
  }

  function closeToasts() {
    document.querySelectorAll(".toast").forEach((toast) => removeToast(toast));
  }

  // =========================================================
  // HELPERS
  // =========================================================
  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
});
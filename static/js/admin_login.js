// =============================================================
// EMIS ADMIN LOGIN SCRIPT — Stable Native Submit Version
// Fixes double-click login issue
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
  initLoginSubmit();

  function initPasswordToggle() {
    document.querySelectorAll(".toggle-password").forEach((btn) => {
      btn.addEventListener("click", () => {
        const input = document.getElementById(btn.dataset.target);
        const icon = btn.querySelector("i");
        if (!input || !icon) return;

        const show = input.type === "password";
        input.type = show ? "text" : "password";

        icon.classList.toggle("fa-eye", !show);
        icon.classList.toggle("fa-eye-slash", show);

        input.focus();
      });
    });
  }

  function initRememberUsername() {
    if (!usernameInput || !rememberInput) return;

    const savedUsername = localStorage.getItem("emis_admin_username");

    if (savedUsername) {
      usernameInput.value = savedUsername;
      rememberInput.checked = true;
      passwordInput?.focus();
    }

    rememberInput.addEventListener("change", () => {
      if (!rememberInput.checked) {
        localStorage.removeItem("emis_admin_username");
      }
    });
  }

  function initInputEffects() {
    document.querySelectorAll(".input-box input").forEach((input) => {
      updateInputState(input);

      input.addEventListener("input", () => {
        updateInputState(input);
        clearFieldError(input);
      });

      input.addEventListener("focus", () => {
        input.closest(".input-box")?.classList.add("is-focused");
      });

      input.addEventListener("blur", () => {
        input.closest(".input-box")?.classList.remove("is-focused");
        updateInputState(input);
      });
    });
  }

  function updateInputState(input) {
    const box = input.closest(".input-box");
    if (!box) return;

    box.classList.toggle("has-value", !!input.value.trim());
  }

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
      const isCaps =
        event.getModifierState && event.getModifierState("CapsLock");

      warning.classList.toggle("hidden", !isCaps);
    });

    passwordInput.addEventListener("blur", () => {
      warning.classList.add("hidden");
    });
  }

  function initLoginSubmit() {
    if (!form) return;

    form.addEventListener("submit", (event) => {
      removeInlineError();
      clearAllFieldErrors();

      const username = usernameInput?.value.trim() || "";
      const password = passwordInput?.value.trim() || "";

      if (!username || !password) {
        event.preventDefault();

        if (!username) markFieldError(usernameInput);
        if (!password) markFieldError(passwordInput);

        showInlineError("Please enter your username and password.");
        shakeCard();

        if (!username) usernameInput?.focus();
        else passwordInput?.focus();

        return;
      }

      if (rememberInput?.checked) {
        localStorage.setItem("emis_admin_username", username);
      } else {
        localStorage.removeItem("emis_admin_username");
      }

      setSubmitting(true);

      /*
        Important:
        Do NOT use fetch here.
        Let the browser submit normally so Flask redirect works first time.
      */
    });
  }

  function setSubmitting(isSubmitting) {
    const btnText = loginBtn?.querySelector(".btn-text");
    const btnLoader = loginBtn?.querySelector(".btn-loader");

    form?.classList.toggle("submitting", isSubmitting);
    loginBtn?.classList.toggle("is-loading", isSubmitting);

    if (loginBtn) {
      loginBtn.disabled = isSubmitting;
    }

    if (isSubmitting) {
      overlay?.classList.remove("hidden");
      overlay?.classList.add("is-visible");
      document.body.classList.add("login-busy");

      if (btnText) {
        btnText.innerHTML =
          '<i class="fa-solid fa-shield-halved"></i> Signing in...';
      }

      btnLoader?.classList.remove("hidden");
    }
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

  function showInlineError(message) {
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

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
});
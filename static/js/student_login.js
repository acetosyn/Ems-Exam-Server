// =============================================================
// EMIS STUDENT LOGIN SCRIPT — Clean Student Version
// =============================================================

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("studentLoginForm");
  const loginBtn = document.getElementById("studentLoginButton");
  const btnText = loginBtn?.querySelector(".btn-text");
  const btnLoader = loginBtn?.querySelector(".btn-loader");
  const overlay = document.getElementById("loadingOverlay");

  const loginNameInput = document.getElementById("login_name");
  const admissionInput = document.getElementById("admission_number");
  const rememberInput = document.getElementById("rememberStudent");

  initRememberStudent();
  initInputEffects();
  initKeyboardShortcuts();
  initSubmit();

  function normalizeLoginText(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }

  function cleanAdmission(value) {
    return String(value || "")
      .trim()
      .replace(/\s+/g, "")
      .toLowerCase();
  }

  function initRememberStudent() {
    if (!loginNameInput || !admissionInput || !rememberInput) return;

    const savedName = localStorage.getItem("emis_student_login_name") || "";
    const savedAdmission = localStorage.getItem("emis_student_admission") || "";

    if (savedName || savedAdmission) {
      loginNameInput.value = savedName;
      admissionInput.value = savedAdmission;
      rememberInput.checked = true;
    }

    rememberInput.addEventListener("change", () => {
      if (!rememberInput.checked) {
        localStorage.removeItem("emis_student_login_name");
        localStorage.removeItem("emis_student_admission");
      }
    });
  }

  function initInputEffects() {
    document.querySelectorAll(".input-box input").forEach((input) => {
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

    loginNameInput?.addEventListener("input", () => {
      loginNameInput.value = loginNameInput.value
        .replace(/[0-9]/g, "")
        .replace(/\s{2,}/g, " ");
    });

    admissionInput?.addEventListener("input", () => {
      admissionInput.value = cleanAdmission(admissionInput.value);
    });
  }

  function markFilled(input) {
    const box = input.closest(".input-box");
    if (!box) return;

    box.classList.toggle("has-value", Boolean(input.value.trim()));
  }

  function initKeyboardShortcuts() {
    document.addEventListener("keydown", (event) => {
      const key = event.key.toLowerCase();

      if (event.altKey && key === "n") {
        event.preventDefault();
        loginNameInput?.focus();
      }

      if (event.altKey && key === "a") {
        event.preventDefault();
        admissionInput?.focus();
      }

      if (event.key === "Escape") {
        hideOverlay();
        closeToasts();
      }
    });
  }

  function initSubmit() {
    if (!form || !loginBtn) return;

    form.addEventListener("submit", (event) => {
      if (form.classList.contains("submitting")) {
        event.preventDefault();
        return;
      }

      removeInlineError();

      const validation = validateForm();

      if (!validation.valid) {
        event.preventDefault();
        showInlineError(validation.message);
        showToast(validation.message, "error");
        shakeCard();
        return;
      }

      admissionInput.value = cleanAdmission(admissionInput.value);
      loginNameInput.value = loginNameInput.value.trim();

      saveRememberedDetails();
      setSubmitting(true);

      // Do not prevent default. Flask should handle the real login.
    });
  }

  function validateForm() {
    const loginName = loginNameInput?.value.trim() || "";
    const admission = admissionInput?.value.trim() || "";

    const cleanName = normalizeLoginText(loginName);
    const cleanAdm = normalizeLoginText(admission);

    clearAllFieldErrors();

    if (!loginName && !admission) {
      markFieldError(loginNameInput);
      markFieldError(admissionInput);
      return {
        valid: false,
        message: "Please enter your name and admission number."
      };
    }

    if (!loginName) {
      markFieldError(loginNameInput);
      loginNameInput?.focus();
      return {
        valid: false,
        message: "Please enter your first name or surname."
      };
    }

    if (cleanName.length < 2) {
      markFieldError(loginNameInput);
      loginNameInput?.focus();
      return {
        valid: false,
        message: "Name is too short."
      };
    }

    if (!admission) {
      markFieldError(admissionInput);
      admissionInput?.focus();
      return {
        valid: false,
        message: "Please enter your admission number."
      };
    }

    if (cleanAdm.length < 3) {
      markFieldError(admissionInput);
      admissionInput?.focus();
      return {
        valid: false,
        message: "Admission number is too short."
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

  function saveRememberedDetails() {
    if (!rememberInput?.checked) {
      localStorage.removeItem("emis_student_login_name");
      localStorage.removeItem("emis_student_admission");
      return;
    }

    localStorage.setItem("emis_student_login_name", loginNameInput.value.trim());
    localStorage.setItem("emis_student_admission", cleanAdmission(admissionInput.value));
  }

  function setSubmitting(isSubmitting) {
    form.classList.toggle("submitting", isSubmitting);
    loginBtn.disabled = isSubmitting;
    loginBtn.classList.toggle("is-loading", isSubmitting);

    if (isSubmitting) {
      showOverlay();
      document.body.classList.add("student-busy");

      if (btnText) {
        btnText.innerHTML =
          '<i class="fa-solid fa-shield-halved"></i> Checking details...';
      }

      btnLoader?.classList.remove("hidden");
    } else {
      hideOverlay();
      document.body.classList.remove("student-busy");

      if (btnText) {
        btnText.innerHTML =
          '<i class="fa-solid fa-right-to-bracket"></i> Login to Exam Portal';
      }

      btnLoader?.classList.add("hidden");
    }
  }

  function showOverlay() {
    overlay?.classList.remove("hidden");
  }

  function hideOverlay() {
    overlay?.classList.add("hidden");
  }

  function showInlineError(message) {
    removeInlineError();

    const errorBox = document.createElement("div");
    errorBox.className = "error-banner js-error-banner";
    errorBox.innerHTML = `
      <i class="fa-solid fa-triangle-exclamation"></i>
      <div>
        <strong>Login Error</strong>
        <span>${escapeHtml(message)}</span>
      </div>
    `;

    form?.parentNode?.insertBefore(errorBox, form);
  }

  function removeInlineError() {
    document.querySelectorAll(".js-error-banner").forEach((box) => box.remove());
  }

  function shakeCard() {
    const card = document.querySelector(".student-card");
    if (!card) return;

    card.classList.remove("shake-card");
    void card.offsetWidth;
    card.classList.add("shake-card");
  }

  function showToast(message, type = "info") {
    let container = document.querySelector(".toast-container");

    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <i class="${getToastIcon(type)}"></i>
      <span>${escapeHtml(message)}</span>
      <button type="button" aria-label="Close notification">
        <i class="fa-solid fa-xmark"></i>
      </button>
    `;

    toast.querySelector("button")?.addEventListener("click", () => {
      removeToast(toast);
    });

    container.appendChild(toast);

    setTimeout(() => removeToast(toast), 4200);
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
    setTimeout(() => toast.remove(), 250);
  }

  function closeToasts() {
    document.querySelectorAll(".toast").forEach((toast) => removeToast(toast));
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
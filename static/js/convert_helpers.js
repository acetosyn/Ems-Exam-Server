/* ============================================================
   EMIS CONVERTER HELPERS — convert_helpers.js
============================================================ */

window.EmisConvertTools = (() => {
  function q(selector, scope = document) {
    return scope.querySelector(selector);
  }

  function qa(selector, scope = document) {
    return [...scope.querySelectorAll(selector)];
  }

  function text(el, value) {
    if (el) el.textContent = value;
  }

  function safeJSONParse(value, fallback = null) {
    try {
      return JSON.parse(value);
    } catch {
      return fallback;
    }
  }

  function prettyJSON(data) {
    return JSON.stringify(data || {}, null, 2);
  }

  function flash(message, type = "success") {
    let box = document.getElementById("flashMessage");

    if (!box) {
      box = document.createElement("div");
      box.id = "flashMessage";
      box.className = "flash-message";
      document.body.appendChild(box);
    }

    box.textContent = message;
    box.className = `flash-message ${type} show`;

    setTimeout(() => {
      box.classList.remove("show");
    }, 3200);
  }

  function addLog(logBody, message, type = "success") {
    if (!logBody) return;

    const placeholder = logBody.querySelector(".log-placeholder");
    if (placeholder) placeholder.remove();

    const item = document.createElement("div");
    item.className = `log-item ${type}`;
    item.innerHTML = `
      <strong>${new Date().toLocaleTimeString()}</strong>
      <span>${message}</span>
    `;

    logBody.prepend(item);
  }

  function setBusy(button, busy, busyText = "Processing...") {
    if (!button) return;

    if (busy) {
      button.dataset.oldHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner"></span> ${busyText}`;
    } else {
      button.disabled = false;
      if (button.dataset.oldHtml) {
        button.innerHTML = button.dataset.oldHtml;
      }
    }
  }

  function setProgress(progressWrap, bar, label, percent, message) {
    if (!progressWrap || !bar || !label) return;

    progressWrap.classList.remove("hidden");
    bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    label.textContent = message || "Processing...";

    if (percent >= 100) {
      setTimeout(() => progressWrap.classList.add("hidden"), 900);
    }
  }

  async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      headers: {
        "X-Requested-With": "fetch",
        ...(options.headers || {}),
      },
      ...options,
    });

    let payload = null;

    try {
      payload = await response.json();
    } catch {
      payload = { error: await response.text() };
    }

    if (!response.ok) {
      throw new Error(payload?.error || payload?.message || `Request failed (${response.status})`);
    }

    return payload;
  }

  function downloadText(filename, content, mime = "text/plain") {
    const blob = new Blob([content || ""], { type: `${mime};charset=utf-8` });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "download.txt";
    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);
  }

  async function copyText(content) {
    if (!content) return false;

    try {
      await navigator.clipboard.writeText(content);
      return true;
    } catch {
      const ta = document.createElement("textarea");
      ta.value = content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      return true;
    }
  }

  function openModal(modal) {
    if (modal) modal.classList.remove("hidden");
  }

  function closeModal(modal) {
    if (modal) modal.classList.add("hidden");
  }

  function bindModalClose(scope = document) {
    qa("[data-close]", scope).forEach((btn) => {
      if (btn.__emisModalBound__) return;
      btn.__emisModalBound__ = true;

      btn.addEventListener("click", () => {
        const modal = btn.closest(".modal");
        closeModal(modal);
      });
    });
  }

  function estimateQuestions(cleanText) {
    const ids = new Set();

    String(cleanText || "").split(/\n+/).forEach((line) => {
      const m = line.trim().match(/^(\d{1,3})[\.\)]\s+/);
      if (m) ids.add(Number(m[1]));
    });

    return ids.size;
  }

  function estimateOptions(cleanText) {
    let count = 0;

    String(cleanText || "").split(/\n+/).forEach((line) => {
      if (/^\s*[\(\[]?[a-dA-D][\)\].:-]\s+/.test(line.trim())) {
        count++;
      }
    });

    return count;
  }

  function validateExamJSON(data, expectedCount = 0) {
    const issues = [];
    const warnings = [];

    if (!data || typeof data !== "object") {
      return {
        valid: false,
        issues: ["Invalid JSON object."],
        warnings: [],
        question_count: 0,
        group_count: 0,
        missing_answers: 0,
      };
    }

    const questions = Array.isArray(data.questions) ? data.questions : [];

    if (!data.subject) issues.push("Missing subject.");
    if (!data.class_category) warnings.push("Missing class category.");
    if (!questions.length) issues.push("No questions found.");

    if (expectedCount && questions.length !== Number(expectedCount)) {
      warnings.push(`Expected ${expectedCount} questions but found ${questions.length}.`);
    }

    let missingAnswers = 0;

    questions.forEach((q) => {
      if (!q.question) {
        issues.push(`Question ${q.id || "?"} has empty question text.`);
      }

      if (!Array.isArray(q.options) || q.options.length !== 4) {
        issues.push(`Question ${q.id || "?"} does not have exactly 4 options.`);
      }

      if (!["A", "B", "C", "D"].includes(q.correctOption)) {
        missingAnswers++;
      }
    });

    if (missingAnswers) {
      warnings.push(`${missingAnswers} question(s) have no answer key yet.`);
    }

    return {
      valid: issues.length === 0,
      issues,
      warnings,
      question_count: questions.length,
      group_count: 0,
      missing_answers: missingAnswers,
    };
  }

  function filenameBase(name) {
    return String(name || "exam")
      .replace(/\.[^/.]+$/, "")
      .replace(/[^\w\-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "")
      .toLowerCase();
  }

  return {
    q,
    qa,
    text,
    flash,
    addLog,
    setBusy,
    setProgress,
    fetchJSON,
    downloadText,
    copyText,
    openModal,
    closeModal,
    bindModalClose,
    safeJSONParse,
    prettyJSON,
    estimateQuestions,
    estimateOptions,
    validateExamJSON,
    filenameBase,
  };
})();
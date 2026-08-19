/* ============================================================
   EMIS CONVERTER EXTENSIONS — convert_ext.js
   Handles:
   - OpenAI answer solving UI
   - Answer review report
   - OpenAI usage/cost display
   - Student JSON preview helpers
   - Save payload shaping
============================================================ */

window.EmisConvertExt = (() => {
  function normalizeOption(value) {
    value = String(value || "").trim().toUpperCase();
    return ["A", "B", "C", "D"].includes(value[0]) ? value[0] : "";
  }

  function getAnswerReport(payload = {}) {
    return payload.answer_report || payload.answerReport || [];
  }

  function getUsage(payload = {}) {
    return payload.openai_usage || payload.openaiUsage || payload.usage || {};
  }

  function getNeedsReview(payload = {}) {
    return Number(payload.needs_review || payload.needsReview || 0);
  }

  function getStudentJSON(payload = {}) {
    return payload.student_json || payload.studentJson || null;
  }

  function summarizeOpenAI(payload = {}) {
    const usage = getUsage(payload);
    const needsReview = getNeedsReview(payload);

    return {
      inputTokens: Number(usage.input_tokens || 0),
      outputTokens: Number(usage.output_tokens || 0),
      totalTokens: Number(usage.total_tokens || 0),
      cost: Number(usage.estimated_cost_usd || 0),
      needsReview,
    };
  }

  function renderUsage(els, payload = {}) {
    const T = window.EmisConvertTools;
    const summary = summarizeOpenAI(payload);

    T.text(els.aiInputTokens, summary.inputTokens.toLocaleString());
    T.text(els.aiOutputTokens, summary.outputTokens.toLocaleString());
    T.text(els.aiTotalTokens, summary.totalTokens.toLocaleString());
    T.text(els.aiCost, `$${summary.cost.toFixed(6)}`);
    T.text(els.aiReviewCount, summary.needsReview.toLocaleString());

    if (els.aiStatusBadge) {
      els.aiStatusBadge.classList.remove("success", "warn", "error", "muted");

      if (!summary.totalTokens) {
        els.aiStatusBadge.classList.add("muted");
        els.aiStatusBadge.textContent = "Not Used";
      } else if (summary.needsReview > 0) {
        els.aiStatusBadge.classList.add("warn");
        els.aiStatusBadge.textContent = "Review Needed";
      } else {
        els.aiStatusBadge.classList.add("success");
        els.aiStatusBadge.textContent = "Answered";
      }
    }
  }

  function renderAnswerReport(els, report = []) {
    const T = window.EmisConvertTools;

    if (!els.answerReviewBody) return;

    if (!Array.isArray(report) || !report.length) {
      els.answerReviewBody.innerHTML = `
        <div class="empty-review">
          <i class="fa-solid fa-circle-info"></i>
          <p>No OpenAI answer review report yet.</p>
        </div>
      `;
      return;
    }

    const needsReview = report.filter((item) => item.needsReview);
    const clean = report.filter((item) => !item.needsReview);

    T.text(els.answerReportTotal, report.length);
    T.text(els.answerReportClean, clean.length);
    T.text(els.answerReportReview, needsReview.length);

    els.answerReviewBody.innerHTML = report.map((item) => {
      const finalOption = normalizeOption(item.finalOption);
      const solverOption = normalizeOption(item.solverOption);
      const verifierOption = normalizeOption(item.verifierOption);

      const reasons = Array.isArray(item.reviewReasons) ? item.reviewReasons : [];
      const warnings = Array.isArray(item.warnings) ? item.warnings : [];

      return `
        <article class="answer-review-item ${item.needsReview ? "needs-review" : "ok"}">
          <div class="answer-review-head">
            <strong>Question ${item.id}</strong>
            <span class="${item.needsReview ? "warn" : "success"}">
              ${item.needsReview ? "Needs Review" : "OK"}
            </span>
          </div>

          <p class="answer-question">${escapeHTML(item.question || "")}</p>

          <div class="answer-options">
            ${(item.options || []).map((opt) => `
              <span class="${String(opt).startsWith(finalOption + ".") ? "selected" : ""}">
                ${escapeHTML(opt)}
              </span>
            `).join("")}
          </div>

          <div class="answer-mini-grid">
            <span>Solver: <b>${solverOption || "—"}</b></span>
            <span>Verifier: <b>${verifierOption || "—"}</b></span>
            <span>Final: <b>${finalOption || "—"}</b></span>
          </div>

          ${reasons.length ? `
            <div class="answer-reasons">
              <strong>Review Reason</strong>
              <ul>${reasons.map((r) => `<li>${escapeHTML(r)}</li>`).join("")}</ul>
            </div>
          ` : ""}

          ${warnings.length ? `
            <div class="answer-warnings">
              <strong>Warnings</strong>
              <ul>${warnings.map((w) => `<li>${escapeHTML(w)}</li>`).join("")}</ul>
            </div>
          ` : ""}
        </article>
      `;
    }).join("");
  }

  function renderStudentJSON(els, studentJSON) {
    const T = window.EmisConvertTools;

    if (els.studentJsonPreview) {
      els.studentJsonPreview.textContent = studentJSON
        ? T.prettyJSON(studentJSON)
        : "No clean student JSON generated yet.";
    }

    if (els.studentJsonModalBody) {
      els.studentJsonModalBody.textContent = studentJSON
        ? T.prettyJSON(studentJSON)
        : "No clean student JSON generated yet.";
    }
  }

  function buildGeneratePayload(els, state) {
    return {
      clean_text: els.cleanText?.value?.trim() || "",
      subject: els.subject?.value || "",
      class_category: els.classCategory?.value || "",
      expected_questions: Number(els.expectedCount?.value || 50),
      diagram_map: state.diagramMap || {},
      use_llm: els.strictJson?.checked ? true : false,
      solve_answers: true, // Always attempt to solve answers when generating
    };
  }

  function buildSavePayload(els, state) {
    return {
      year: els.year?.value || new Date().getFullYear(),
      subject: els.subject?.value || state.generatedJSON?.subject || "",
      class_category:
        els.classCategory?.value ||
        state.generatedJSON?.class_category ||
        state.generatedJSON?.class ||
        "",
      json: state.generatedJSON,
      student_json: state.studentJSON || null,
      answer_report: state.answerReport || [],
      openai_usage: state.openaiUsage || {},
      needs_review: state.needsReview || 0,
      overwrite: true,
    };
  }

  function escapeHTML(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  return {
    getAnswerReport,
    getUsage,
    getNeedsReview,
    getStudentJSON,
    summarizeOpenAI,
    renderUsage,
    renderAnswerReport,
    renderStudentJSON,
    buildGeneratePayload,
    buildSavePayload,
  };
})();
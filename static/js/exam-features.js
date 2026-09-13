/* ============================================================================
   exam-features.js — EMIS CBT EXPERIENCE LAYER v2.2

   Enhances:
     • Attractive correct / incorrect answer feedback
     • Answered / flagged / current navigation states
     • Smart Section A → Section B navigation
     • Modern submit review
     • Smooth question transitions
     • Lightweight exam notifications
     • Accessibility
     • Reduced-motion support

   IMPORTANT:
     exam-core.js owns exam data, scoring, timer and submission.
     exam-realtime.js owns examination security.
============================================================================ */

(() => {
  if (window.__EMIS_EXAM_FEATURES_V22__) return;
  window.__EMIS_EXAM_FEATURES_V22__ = true;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;

  const featureState = {
    started: false,
    submitModalOpen: false,
    sectionToastShown: false,
    toastCounter: 0,
    observerScheduled: false
  };


  /* ==========================================================
     STYLES
  ========================================================== */

  function injectFeatureStyles() {
    if ($("#emisExamFeaturesStyles")) return;

    const style = document.createElement("style");
    style.id = "emisExamFeaturesStyles";

    style.textContent = `
      /* ========================================================
         CORRECT / INCORRECT FLASH
      ======================================================== */

      .eflash {
        position:absolute;
        top:12px;
        right:14px;
        z-index:40;
        width:46px;
        height:46px;
        display:grid;
        place-items:center;
        padding:0;
        border:2px solid rgba(255,255,255,.82);
        border-radius:50%;
        color:#fff;
        pointer-events:none;
        opacity:0;
        transform:scale(.55) rotate(-8deg);
        box-shadow:0 10px 28px rgba(15,23,42,.18);
      }

      .eflash i {
        font-size:1.12rem;
        font-weight:900;
      }

      .eflash::after {
        content:"";
        position:absolute;
        inset:-6px;
        border:2px solid currentColor;
        border-radius:50%;
        opacity:0;
        transform:scale(.7);
      }

      .eflash.ok {
        background:linear-gradient(145deg,#2acb72,#138447);
        box-shadow:0 10px 26px rgba(22,163,74,.28);
      }

      .eflash.bad {
        background:linear-gradient(145deg,#ef5662,#c72435);
        box-shadow:0 10px 26px rgba(220,38,38,.26);
      }

      .eflash.show {
        opacity:1;
        animation:efMarkPop .58s cubic-bezier(.15,.9,.25,1) forwards;
      }

      .eflash.show::after {
        animation:efMarkRing .58s ease-out forwards;
      }

      #questionContent.ef-answer-pulse {
        animation:efAnswerPulse .32s ease;
      }

      @keyframes efMarkPop {
        0% { opacity:0; transform:scale(.45) rotate(-12deg); }
        42% { opacity:1; transform:scale(1.16) rotate(3deg); }
        68% { transform:scale(.94) rotate(0); }
        100% { opacity:1; transform:scale(1) rotate(0); }
      }

      @keyframes efMarkRing {
        0% { opacity:.5; transform:scale(.65); }
        100% { opacity:0; transform:scale(1.45); }
      }

      @keyframes efAnswerPulse {
        0% { transform:scale(1); }
        50% { transform:scale(1.003); }
        100% { transform:scale(1); }
      }


      /* ========================================================
         QUESTION NAVIGATION
      ======================================================== */

      .question-nav-btn {
        position:relative;
      }

      .question-nav-btn .dot {
        position:absolute;
        top:5px;
        right:5px;
        width:7px;
        height:7px;
        border-radius:50%;
        background:#16a34a;
        box-shadow:0 0 0 2px #fff;
        pointer-events:none;
      }

      .question-nav-btn.ef-flagged {
        box-shadow:inset 0 0 0 2px #d79008;
      }

      .question-nav-btn.ef-flagged::after {
        content:"";
        position:absolute;
        top:5px;
        left:5px;
        width:6px;
        height:6px;
        border-radius:50%;
        background:#d79008;
        box-shadow:0 0 0 2px #fff;
        pointer-events:none;
      }

      .question-nav-btn.ef-current {
        transform:translateY(-1px);
      }


      /* ========================================================
         SECTION B CTA
      ======================================================== */

      #nextBtn.ef-section-ready {
        position:relative;
        overflow:hidden;
        isolation:isolate;
        box-shadow:0 7px 20px rgba(20,122,112,.17);
      }

      #nextBtn.ef-section-ready::before {
        content:"";
        position:absolute;
        inset:0;
        z-index:-1;
        background:linear-gradient(110deg,transparent 15%,rgba(255,255,255,.25) 45%,transparent 75%);
        transform:translateX(-120%);
        animation:efCTAshine 2.8s ease-in-out infinite;
      }

      #nextBtn .ef-next-meta {
        margin-left:5px;
        padding:2px 6px;
        border-radius:999px;
        background:rgba(255,255,255,.17);
        font-size:.57rem;
        font-weight:900;
        letter-spacing:.045em;
        text-transform:uppercase;
      }

      @keyframes efCTAshine {
        0%,58% { transform:translateX(-120%); }
        82%,100% { transform:translateX(140%); }
      }


      /* ========================================================
         QUESTION TRANSITION
      ======================================================== */

      #questionContent .qa-slide.ef-question-enter,
      #questionContent.ef-question-enter {
        animation:efQuestionEnter .24s cubic-bezier(.2,.75,.3,1);
      }

      @keyframes efQuestionEnter {
        from { opacity:.25; transform:translateX(15px); }
        to { opacity:1; transform:translateX(0); }
      }


      /* ========================================================
         LIGHTWEIGHT FEATURE TOAST
      ======================================================== */

      .ef-toast-stack {
        position:fixed;
        left:50%;
        bottom:24px;
        z-index:99990;
        display:grid;
        gap:8px;
        width:min(430px,calc(100vw - 28px));
        transform:translateX(-50%);
        pointer-events:none;
      }

      .ef-toast {
        display:grid;
        grid-template-columns:35px minmax(0,1fr) 25px;
        align-items:center;
        gap:9px;
        width:100%;
        padding:9px 11px;
        background:rgba(255,255,255,.98);
        border:1px solid #dce6ee;
        border-radius:13px;
        box-shadow:0 12px 30px rgba(25,43,60,.16);
        backdrop-filter:blur(10px);
        pointer-events:auto;
        opacity:0;
        transform:translateY(10px) scale(.985);
        animation:efToastIn .23s ease forwards;
      }

      .ef-toast-icon {
        width:34px;
        height:34px;
        display:grid;
        place-items:center;
        border-radius:10px;
        font-size:.8rem;
      }

      .ef-toast-content {
        min-width:0;
      }

      .ef-toast-content strong {
        display:block;
        margin-bottom:1px;
        color:#182435;
        font-size:.77rem;
        font-weight:900;
      }

      .ef-toast-content span {
        display:block;
        color:#647386;
        font-size:.68rem;
        font-weight:600;
        line-height:1.4;
      }

      .ef-toast-close {
        width:24px;
        height:24px;
        display:grid;
        place-items:center;
        padding:0;
        color:#8995a3;
        background:transparent;
        border:0;
        border-radius:7px;
        cursor:pointer;
      }

      .ef-toast-close:hover {
        color:#223047;
        background:#eef2f6;
      }

      .ef-toast.info .ef-toast-icon { color:#176b9c; background:#e5f3fc; }
      .ef-toast.success .ef-toast-icon { color:#14704c; background:#e3f7ed; }
      .ef-toast.warning .ef-toast-icon { color:#9a6500; background:#fff2ce; }
      .ef-toast.danger .ef-toast-icon { color:#b72c3a; background:#ffe5e8; }

      .ef-toast.is-leaving {
        animation:efToastOut .2s ease forwards;
      }

      @keyframes efToastIn {
        to { opacity:1; transform:translateY(0) scale(1); }
      }

      @keyframes efToastOut {
        to { opacity:0; transform:translateY(7px) scale(.985); }
      }


      /* ========================================================
         SUBMIT REVIEW MODAL
      ======================================================== */

      .ef-submit-overlay {
        position:fixed;
        inset:0;
        z-index:99995;
        display:grid;
        place-items:center;
        padding:18px;
        background:rgba(15,23,42,.58);
        backdrop-filter:blur(6px);
        animation:efFadeIn .2s ease;
      }

      .ef-submit-card {
        width:min(610px,96vw);
        max-height:90vh;
        overflow:auto;
        background:#fff;
        border:1px solid rgba(255,255,255,.7);
        border-radius:22px;
        box-shadow:0 26px 75px rgba(15,23,42,.3);
        animation:efModalIn .27s cubic-bezier(.2,.8,.2,1);
      }

      .ef-submit-head {
        display:flex;
        align-items:center;
        gap:13px;
        padding:18px 20px 14px;
        border-bottom:1px solid #e8edf3;
      }

      .ef-submit-icon {
        width:44px;
        height:44px;
        flex:0 0 auto;
        display:grid;
        place-items:center;
        color:#0f766e;
        background:#e5f7f4;
        border-radius:14px;
        font-size:1rem;
      }

      .ef-submit-title {
        flex:1;
        min-width:0;
      }

      .ef-submit-title small {
        display:block;
        margin-bottom:2px;
        color:#768395;
        font-size:.61rem;
        font-weight:900;
        letter-spacing:.08em;
        text-transform:uppercase;
      }

      .ef-submit-title h3 {
        margin:0;
        color:#172033;
        font-size:1.12rem;
        font-weight:900;
      }

      .ef-submit-x {
        width:34px;
        height:34px;
        display:grid;
        place-items:center;
        padding:0;
        color:#758294;
        background:#f3f6f9;
        border:0;
        border-radius:10px;
        cursor:pointer;
      }

      .ef-submit-body {
        padding:17px 20px 19px;
      }

      .ef-submit-lead {
        margin:0 0 14px;
        color:#566579;
        font-size:.82rem;
        font-weight:560;
        line-height:1.55;
      }

      .ef-submit-stats {
        display:grid;
        grid-template-columns:repeat(4,1fr);
        gap:8px;
        margin-bottom:13px;
      }

      .ef-submit-stat {
        padding:11px 8px;
        text-align:center;
        background:#f7f9fc;
        border:1px solid #e2e9f0;
        border-radius:13px;
      }

      .ef-submit-stat strong {
        display:block;
        color:#172033;
        font-size:1.04rem;
        font-weight:900;
      }

      .ef-submit-stat span {
        display:block;
        margin-top:2px;
        color:#758295;
        font-size:.6rem;
        font-weight:750;
      }

      .ef-submit-stat.good { background:#eefaf4; border-color:#cceada; }
      .ef-submit-stat.good strong { color:#18704c; }

      .ef-submit-stat.warn { background:#fff8e8; border-color:#f0ddb0; }
      .ef-submit-stat.warn strong { color:#9a6500; }

      .ef-submit-stat.flag { background:#fff6e8; border-color:#efd8a7; }
      .ef-submit-stat.flag strong { color:#a36a00; }

      .ef-submit-alert,
      .ef-submit-note {
        display:flex;
        align-items:flex-start;
        gap:9px;
        margin-top:9px;
        padding:10px 11px;
        border-radius:12px;
        font-size:.72rem;
        font-weight:620;
        line-height:1.45;
      }

      .ef-submit-alert {
        color:#825600;
        background:#fff7e1;
        border:1px solid #efd9a4;
      }

      .ef-submit-note {
        color:#315d75;
        background:#edf7fc;
        border:1px solid #cfe6f1;
      }

      .ef-submit-actions {
        display:flex;
        justify-content:flex-end;
        gap:9px;
        padding:13px 20px 18px;
        border-top:1px solid #edf1f5;
      }

      .ef-review-btn,
      .ef-final-submit-btn {
        min-height:39px;
        padding:0 15px;
        border-radius:11px;
        font-size:.75rem;
        font-weight:820;
        cursor:pointer;
      }

      .ef-review-btn {
        color:#344256;
        background:#f4f6f9;
        border:1px solid #d8e0e8;
      }

      .ef-final-submit-btn {
        color:#fff;
        background:#c93746;
        border:1px solid #c93746;
        box-shadow:0 7px 18px rgba(201,55,70,.18);
      }

      .ef-final-submit-btn:disabled {
        opacity:.65;
        cursor:not-allowed;
      }

      @keyframes efFadeIn {
        from { opacity:0; }
        to { opacity:1; }
      }

      @keyframes efModalIn {
        from { opacity:0; transform:translateY(12px) scale(.975); }
        to { opacity:1; transform:translateY(0) scale(1); }
      }

      @media (max-width:700px) {
        .eflash { top:8px; right:8px; width:42px; height:42px; }
        .ef-submit-stats { grid-template-columns:repeat(2,1fr); }
        .ef-submit-card { border-radius:18px; }
        .ef-submit-head { padding:15px; }
        .ef-submit-body { padding:14px 15px 16px; }
        .ef-submit-actions { padding:12px 15px 15px; }
        .ef-toast-stack { bottom:15px; }
      }

      @media (prefers-reduced-motion:reduce) {
        .eflash,
        .eflash::after,
        .ef-toast,
        .ef-submit-overlay,
        .ef-submit-card,
        #questionContent,
        #questionContent .qa-slide,
        #nextBtn.ef-section-ready::before {
          animation:none !important;
          transition:none !important;
        }
      }
    `;

    document.head.appendChild(style);
  }


  /* ==========================================================
     HELPERS
  ========================================================== */

  function getRealQuestionIndices() {
    return Array.isArray(window.realQuestionIndices) ? window.realQuestionIndices : [];
  }


  function getExamStats() {
    const realIndices = getRealQuestionIndices();
    const total = realIndices.length;
    const answered = realIndices.filter((index) => Boolean(window.userAnswers?.[index])).length;
    const flagged = realIndices.filter((index) => window.flaggedQuestions?.has?.(index)).length;
    const unanswered = Math.max(0, total - answered);

    return { total, answered, unanswered, flagged };
  }


  function formatFeatureTime(seconds) {
    const safe = Math.max(0, Number(seconds) || 0);
    const hours = Math.floor(safe / 3600);
    const minutes = Math.floor((safe % 3600) / 60);
    const secs = Math.floor(safe % 60);

    return hours > 0
      ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
      : `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }


  function resolveCorrectIndex(question) {
    const direct = Number(question?.correctIndex);

    if (Number.isInteger(direct) && direct >= 0) return direct;

    const option = String(question?.correctOption || "").trim().toUpperCase();

    if (/^[A-Z]$/.test(option)) return option.charCodeAt(0) - 65;

    return -1;
  }


  /* ==========================================================
     FEATURE TOAST
  ========================================================== */

  function getToastStack() {
    let stack = $("#emisFeatureToastStack");

    if (!stack) {
      stack = document.createElement("div");
      stack.id = "emisFeatureToastStack";
      stack.className = "ef-toast-stack";
      stack.setAttribute("aria-live", "polite");
      stack.setAttribute("aria-atomic", "false");
      document.body.appendChild(stack);
    }

    return stack;
  }


  function showFeatureToast(title, message = "", type = "info", duration = 3200) {
    const normalizedType = ["info", "success", "warning", "danger"].includes(type) ? type : "info";
    const icons = { info: "fa-circle-info", success: "fa-circle-check", warning: "fa-triangle-exclamation", danger: "fa-circle-exclamation" };
    const stack = getToastStack();

    const toast = document.createElement("div");
    toast.className = `ef-toast ${normalizedType}`;
    toast.dataset.toastId = String(++featureState.toastCounter);

    toast.innerHTML = `
      <div class="ef-toast-icon"><i class="fa-solid ${icons[normalizedType]}"></i></div>
      <div class="ef-toast-content"><strong></strong><span></span></div>
      <button type="button" class="ef-toast-close" aria-label="Dismiss"><i class="fa-solid fa-xmark"></i></button>
    `;

    toast.querySelector("strong").textContent = String(title || "Exam");
    toast.querySelector(".ef-toast-content span").textContent = String(message || "");

    const close = toast.querySelector(".ef-toast-close");

    stack.appendChild(toast);

    while (stack.children.length > 3) stack.firstElementChild?.remove();

    let removed = false;

    const dismiss = () => {
      if (removed) return;
      removed = true;
      toast.classList.add("is-leaving");
      setTimeout(() => toast.remove(), 220);
    };

    close?.addEventListener("click", dismiss);

    if (duration > 0) setTimeout(dismiss, duration);

    return toast;
  }

  window.examFeatureToast = showFeatureToast;


  /* ==========================================================
     BEAUTIFUL ✓ / ✕ ANSWER FEEDBACK
  ========================================================== */

  function showAnswerFeedback(selectedIndex) {
    const host = $("#questionContent");
    const question = window.examData?.questions?.[window.currentQuestionIndex];

    if (!host || !question) return;

    const correctIndex = resolveCorrectIndex(question);
    const selected = Number(selectedIndex);

    if (correctIndex < 0 || !Number.isFinite(selected)) return;

    const correct = selected === correctIndex;

    host.style.position = "relative";

    let mark = host.querySelector(".eflash");

    if (!mark) {
      mark = document.createElement("div");
      mark.className = "eflash";
      mark.setAttribute("aria-live", "polite");
      host.appendChild(mark);
    }

    mark.className = `eflash ${correct ? "ok" : "bad"}`;
    mark.innerHTML = correct ? `<i class="fa-solid fa-check"></i>` : `<i class="fa-solid fa-xmark"></i>`;
    mark.setAttribute("aria-label", correct ? "Correct answer" : "Incorrect answer");

    mark.classList.remove("show");
    host.classList.remove("ef-answer-pulse");

    requestAnimationFrame(() => {
      mark.classList.add("show");
      host.classList.add("ef-answer-pulse");
    });

    clearTimeout(mark.__efHideTimer);
    clearTimeout(host.__efPulseTimer);

    mark.__efHideTimer = setTimeout(() => mark.classList.remove("show"), 580);
    host.__efPulseTimer = setTimeout(() => host.classList.remove("ef-answer-pulse"), 350);
  }


  /* ==========================================================
     QUESTION NAVIGATION STATES
  ========================================================== */

  function syncQuestionNavigation() {
    const realIndices = getRealQuestionIndices();

    $$(".question-nav-btn").forEach((button) => {
      const trueIndex = Number(button.dataset.qIndex);
      const position = realIndices.indexOf(trueIndex);
      const answered = Boolean(window.userAnswers?.[trueIndex]);
      const flagged = Boolean(window.flaggedQuestions?.has?.(trueIndex));
      const current = trueIndex === Number(window.currentQuestionIndex);

      button.classList.toggle("ef-answered", answered);
      button.classList.toggle("ef-flagged", flagged);
      button.classList.toggle("ef-current", current);

      let dot = button.querySelector(".dot");

      if (answered && !dot) {
        dot = document.createElement("span");
        dot.className = "dot";
        dot.setAttribute("aria-hidden", "true");
        button.appendChild(dot);
      } else if (!answered && dot) {
        dot.remove();
      }

      const states = [answered ? "answered" : "not answered"];
      if (flagged) states.push("flagged");
      if (current) states.push("current");

      const number = position >= 0 ? position + 1 : button.textContent.trim();

      button.setAttribute("aria-label", `Question ${number}, ${states.join(", ")}`);
      button.title = `Question ${number} • ${states.join(" • ")}`;
    });

    syncProgressAccessibility();
  }


  /* ==========================================================
     ACCESSIBLE PROGRESS
  ========================================================== */

  function syncProgressAccessibility() {
    const stats = getExamStats();
    const progressBar = $("#progressBar");
    const progressText = $("#progressText");

    if (progressBar) {
      progressBar.setAttribute("role", "progressbar");
      progressBar.setAttribute("aria-valuemin", "0");
      progressBar.setAttribute("aria-valuemax", String(stats.total));
      progressBar.setAttribute("aria-valuenow", String(stats.answered));
      progressBar.setAttribute("aria-valuetext", `${stats.answered} of ${stats.total} questions answered`);
    }

    if (progressText) progressText.title = `${stats.answered} answered • ${stats.unanswered} remaining • ${stats.flagged} flagged`;
  }


  /* ==========================================================
     SMART CTA
  ========================================================== */

  function syncCTA() {
    const next = $("#nextBtn");

    if (!next || !window.examData || window.examSection === "essay") return;

    const realIndices = getRealQuestionIndices();

    if (!realIndices.length) return;

    const lastRealIndex = realIndices[realIndices.length - 1];
    const lastObjective = Number(window.currentQuestionIndex) === Number(lastRealIndex);
    const essayCount = Array.isArray(window.essayData?.questions) ? window.essayData.questions.length : 0;

    next.classList.remove("ef-section-ready");

    if (!lastObjective) {
      next.innerHTML = `Next <i class="fa-solid fa-arrow-right"></i>`;
      next.onclick = typeof window.nextQuestion === "function" ? window.nextQuestion : null;
      return;
    }

    next.classList.add("ef-section-ready");

    if (essayCount > 0) {
      next.innerHTML = `Section B <span class="ef-next-meta">Theory</span> <i class="fa-solid fa-arrow-right"></i>`;
      next.onclick = typeof window.openEssaySection === "function" ? window.openEssaySection : null;
      return;
    }

    next.innerHTML = `Review & Submit <i class="fa-solid fa-clipboard-check"></i>`;
    next.onclick = () => window.openSubmitConfirm?.();
  }


  /* ==========================================================
     QUESTION TRANSITION
  ========================================================== */

  function animateCurrentQuestion() {
    if (reducedMotion()) return;

    const host = $("#questionContent .qa-slide") || $("#questionContent");

    if (!host) return;

    host.classList.remove("ef-question-enter");

    void host.offsetWidth;

    host.classList.add("ef-question-enter");

    clearTimeout(host.__efTransitionTimer);

    host.__efTransitionTimer = setTimeout(() => host.classList.remove("ef-question-enter"), 290);
  }


  /* ==========================================================
     SUBMIT REVIEW MODAL
  ========================================================== */

  function openSubmitConfirm() {
    if (featureState.submitModalOpen || window.__examFinished) return;

    const stats = getExamStats();
    const remainingTime = formatFeatureTime(window.timeRemaining);
    const essayCount = Array.isArray(window.essayData?.questions) ? window.essayData.questions.length : 0;
    const previousFocus = document.activeElement;

    $("#efSubmitModal")?.remove();

    const overlay = document.createElement("div");

    overlay.id = "efSubmitModal";
    overlay.className = "ef-submit-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "efSubmitTitle");

    overlay.innerHTML = `
      <div class="ef-submit-card">
        <div class="ef-submit-head">
          <div class="ef-submit-icon"><i class="fa-solid fa-clipboard-check"></i></div>

          <div class="ef-submit-title">
            <small>Final Review</small>
            <h3 id="efSubmitTitle">Submit Examination?</h3>
          </div>

          <button type="button" class="ef-submit-x" id="efSubmitClose" aria-label="Close"><i class="fa-solid fa-xmark"></i></button>
        </div>

        <div class="ef-submit-body">
          <p class="ef-submit-lead">Review your examination status before final submission. Once submitted, the examination will end.</p>

          <div class="ef-submit-stats">
            <div class="ef-submit-stat good"><strong>${stats.answered}</strong><span>Answered</span></div>
            <div class="ef-submit-stat ${stats.unanswered ? "warn" : "good"}"><strong>${stats.unanswered}</strong><span>Unanswered</span></div>
            <div class="ef-submit-stat ${stats.flagged ? "flag" : ""}"><strong>${stats.flagged}</strong><span>Flagged</span></div>
            <div class="ef-submit-stat"><strong>${remainingTime}</strong><span>Time Left</span></div>
          </div>

          ${
            stats.unanswered > 0
              ? `<div class="ef-submit-alert"><i class="fa-solid fa-triangle-exclamation"></i><span><strong>${stats.unanswered} question${stats.unanswered === 1 ? "" : "s"} unanswered.</strong> Unanswered objective questions will receive no mark.</span></div>`
              : `<div class="ef-submit-alert" style="color:#176747;background:#edf9f3;border-color:#cce8d8;"><i class="fa-solid fa-circle-check"></i><span>All objective questions have been answered.</span></div>`
          }

          ${
            stats.flagged > 0
              ? `<div class="ef-submit-alert"><i class="fa-solid fa-flag"></i><span>You still have <strong>${stats.flagged} flagged question${stats.flagged === 1 ? "" : "s"}</strong> marked for review.</span></div>`
              : ""
          }

          ${
            essayCount > 0
              ? `<div class="ef-submit-note"><i class="fa-solid fa-pen-to-square"></i><span>Section B contains <strong>${essayCount} theory question${essayCount === 1 ? "" : "s"}</strong>. Ensure your theory answers are written clearly in the physical answer booklet before submitting.</span></div>`
              : ""
          }
        </div>

        <div class="ef-submit-actions">
          <button type="button" class="ef-review-btn" id="efContinueReview"><i class="fa-solid fa-arrow-left"></i> Keep Reviewing</button>
          <button type="button" class="ef-final-submit-btn" id="efFinalSubmit"><i class="fa-solid fa-paper-plane"></i> Submit Exam</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    featureState.submitModalOpen = true;

    const closeBtn = $("#efSubmitClose", overlay);
    const reviewBtn = $("#efContinueReview", overlay);
    const submitBtn = $("#efFinalSubmit", overlay);

    const closeModal = () => {
      if (!featureState.submitModalOpen) return;

      featureState.submitModalOpen = false;
      overlay.remove();
      document.removeEventListener("keydown", handleKeydown);

      if (previousFocus?.focus) setTimeout(() => previousFocus.focus(), 0);
    };

    const handleKeydown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeModal();
      }
    };

    closeBtn?.addEventListener("click", closeModal);
    reviewBtn?.addEventListener("click", closeModal);

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeModal();
    });

    document.addEventListener("keydown", handleKeydown);

    submitBtn?.addEventListener("click", async () => {
      if (typeof window.submitExam !== "function") {
        showFeatureToast("Submission unavailable", "The examination submission function could not be found.", "danger", 4500);
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Submitting...`;

      await window.submitExam(false);

      if (!window.__examFinished) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Submit Exam`;
      }
    });

    setTimeout(() => reviewBtn?.focus(), 30);
  }

  window.openSubmitConfirm = openSubmitConfirm;


  /* ==========================================================
     PATCH ANSWER SELECTION
  ========================================================== */

  function patchSelectOption() {
    if (window.__EMIS_FEATURES_SELECT_PATCHED__) return true;

    const original = window.selectOption;

    if (typeof original !== "function") return false;

    window.selectOption = function (...args) {
      const selectedIndex = args[0];
      const result = original.apply(this, args);

      showAnswerFeedback(selectedIndex);

      setTimeout(() => {
        syncQuestionNavigation();
        syncCTA();
      }, 0);

      return result;
    };

    window.__EMIS_FEATURES_SELECT_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH QUESTION LOAD
  ========================================================== */

  function patchLoadQuestion() {
    if (window.__EMIS_FEATURES_LOAD_PATCHED__) return true;

    const original = window.loadQuestion;

    if (typeof original !== "function") return false;

    window.loadQuestion = function (...args) {
      const result = original.apply(this, args);

      requestAnimationFrame(() => {
        animateCurrentQuestion();
        syncQuestionNavigation();
        syncCTA();
      });

      return result;
    };

    window.__EMIS_FEATURES_LOAD_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH QUESTION NAVIGATION
  ========================================================== */

  function patchQuestionNavigation() {
    if (window.__EMIS_FEATURES_QNAV_PATCHED__) return true;

    const original = window.updateQuestionNavigation;

    if (typeof original !== "function") return false;

    window.updateQuestionNavigation = function (...args) {
      const result = original.apply(this, args);
      syncQuestionNavigation();
      return result;
    };

    window.__EMIS_FEATURES_QNAV_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH NAV BUTTONS
  ========================================================== */

  function patchNavigationButtons() {
    if (window.__EMIS_FEATURES_NAVBTN_PATCHED__) return true;

    const original = window.updateNavigationButtons;

    if (typeof original !== "function") return false;

    window.updateNavigationButtons = function (...args) {
      const result = original.apply(this, args);
      syncCTA();
      return result;
    };

    window.__EMIS_FEATURES_NAVBTN_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH PROGRESS
  ========================================================== */

  function patchProgress() {
    if (window.__EMIS_FEATURES_PROGRESS_PATCHED__) return true;

    const original = window.updateProgress;

    if (typeof original !== "function") return false;

    window.updateProgress = function (...args) {
      const result = original.apply(this, args);
      syncProgressAccessibility();
      return result;
    };

    window.__EMIS_FEATURES_PROGRESS_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH FLAG UI
  ========================================================== */

  function patchFlagUI() {
    if (window.__EMIS_FEATURES_FLAG_PATCHED__) return true;

    const original = window.updateFlagUI;

    if (typeof original !== "function") return false;

    window.updateFlagUI = function (...args) {
      const result = original.apply(this, args);
      setTimeout(syncQuestionNavigation, 0);
      return result;
    };

    window.__EMIS_FEATURES_FLAG_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH SECTION B
  ========================================================== */

  function patchEssaySection() {
    if (window.__EMIS_FEATURES_ESSAY_PATCHED__) return true;

    const original = window.openEssaySection;

    if (typeof original !== "function") return false;

    window.openEssaySection = function (...args) {
      const result = original.apply(this, args);

      if (!featureState.sectionToastShown) {
        featureState.sectionToastShown = true;

        showFeatureToast(
          "Section B • Theory",
          "Write all theory answers clearly in the physical answer booklet provided.",
          "info",
          4200
        );
      }

      return result;
    };

    window.__EMIS_FEATURES_ESSAY_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH START EXAM
     Global flag prevents wrapper conflicts with exam-realtime.
  ========================================================== */

  function patchStartExam() {
    if (window.__EMIS_FEATURES_START_PATCHED__) return true;

    const original = window.startExam;

    if (typeof original !== "function") return false;

    window.startExam = async function (...args) {
      const result = await original.apply(this, args);

      if (window.examData && !featureState.started && !window.__examFinished) {
        featureState.started = true;

        setTimeout(() => {
          showFeatureToast(
            "Examination Started",
            "Use Previous / Next or the question numbers to navigate your examination.",
            "success",
            3900
          );
        }, 400);

        syncQuestionNavigation();
        syncCTA();
        syncProgressAccessibility();
      }

      return result;
    };

    window.__EMIS_FEATURES_START_PATCHED__ = true;

    return true;
  }


  /* ==========================================================
     PATCH CORE
  ========================================================== */

  function patchCoreHooks() {
    patchSelectOption();
    patchLoadQuestion();
    patchQuestionNavigation();
    patchNavigationButtons();
    patchProgress();
    patchFlagUI();
    patchEssaySection();
    patchStartExam();
  }


  /* ==========================================================
     LIGHTWEIGHT LIVE UI OBSERVER
  ========================================================== */

  function startUISyncObserver() {
    const examInterface = $("#examInterface") || document.body;

    if (examInterface.__emisFeatureObserver) return;

    const observer = new MutationObserver((mutations) => {
      const relevant = mutations.some((mutation) => mutation.type === "childList" && mutation.addedNodes.length);

      if (!relevant || featureState.observerScheduled) return;

      featureState.observerScheduled = true;

      requestAnimationFrame(() => {
        featureState.observerScheduled = false;
        syncQuestionNavigation();
        syncCTA();
      });
    });

    observer.observe(examInterface, { childList: true, subtree: true });

    examInterface.__emisFeatureObserver = observer;
  }


  /* ==========================================================
     BOOT
  ========================================================== */

  function bootExamFeatures() {
    injectFeatureStyles();
    patchCoreHooks();
    startUISyncObserver();

    let attempts = 0;

    const waitForCore = () => {
      attempts++;

      patchCoreHooks();

      if (window.examData) {
        syncQuestionNavigation();
        syncCTA();
        syncProgressAccessibility();
      }

      if (attempts < 60 && (
        typeof window.selectOption !== "function" ||
        typeof window.loadQuestion !== "function" ||
        typeof window.startExam !== "function"
      )) {
        setTimeout(waitForCore, 130);
      }
    };

    waitForCore();

    console.log("%c[exam-features] EXPERIENCE LAYER v2.2 READY ✓", "color:#0f766e;font-weight:900");
  }


  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bootExamFeatures, { once: true });
  else bootExamFeatures();

})();
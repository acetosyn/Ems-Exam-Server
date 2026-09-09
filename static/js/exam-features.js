/* ============================================================================
   EMIS EXAM — FEATURES MODULE
   Compatible with:
   • Section A Objective
   • Section B Theory
   • exam-core.js
   • exam-realtime.js
============================================================================ */

(function () {
  if (!window) return;

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));


  /* -------------------------------------------------------------------------
     1. ✔ / ✖ FLASH PILL
  ------------------------------------------------------------------------- */

  function enableFlashPill() {
    const originalSelect = window.selectOption;

    if (typeof originalSelect !== "function") return;

    window.selectOption = function (idx) {
      const q = window.examData?.questions?.[window.currentQuestionIndex];
      const host = $("#questionContent");

      if (q && host) {
        const correct = q.correctIndex;
        const ok = idx === correct;

        let pill = host.querySelector(".eflash");

        if (!pill) {
          pill = document.createElement("div");
          pill.className = "eflash";
          host.style.position = "relative";
          host.appendChild(pill);
        }

        pill.className = "eflash " + (ok ? "ok" : "bad");
        pill.textContent = ok ? "✔" : "✖";

        requestAnimationFrame(() => pill.classList.add("show"));
        setTimeout(() => pill.classList.remove("show"), 600);
      }

      return originalSelect.apply(this, arguments);
    };
  }


  /* -------------------------------------------------------------------------
     2. STYLES
  ------------------------------------------------------------------------- */

  const style = document.createElement("style");

  style.textContent = `
    .eflash {
      position:absolute;
      top:-10px;
      right:-10px;
      padding:8px 10px;
      border-radius:50%;
      font-weight:800;
      color:#fff;
      opacity:0;
      scale:.9;
      transition:all .22s ease;
      z-index:20;
      box-shadow:0 8px 22px rgba(0,0,0,.25);
    }

    .eflash.ok { background:#16a34a; }
    .eflash.bad { background:#dc2626; }
    .eflash.show { opacity:1; scale:1; }

    .question-nav-btn .dot {
      position:absolute;
      top:6px;
      right:6px;
      width:8px;
      height:8px;
      border-radius:50%;
      background:#16a34a;
      box-shadow:0 0 0 2px #fff;
    }

    #nextBtn.pulse {
      animation:pulseBtn .8s ease-in-out 2;
    }

    @keyframes pulseBtn {
      0% { transform:scale(1); }
      50% { transform:scale(1.06); }
      100% { transform:scale(1); }
    }

    .qa-slide {
      will-change:transform,opacity;
    }

    .slide-enter {
      opacity:0;
      transform:translateX(26px);
    }

    .slide-enter-active {
      transition:all .25s ease;
      opacity:1;
      transform:translateX(0);
    }

    .slide-exit {
      opacity:1;
      transform:translateX(0);
    }

    .slide-exit-active {
      transition:all .25s ease;
      opacity:0;
      transform:translateX(-26px);
    }
  `;

  document.head.appendChild(style);


  /* -------------------------------------------------------------------------
     3. CTA SYNC
     IMPORTANT:
     The core engine owns final-question navigation.

     Last objective:
       Section B →

     Section B:
       final submission is handled by essaySubmitBtn / endExam()
  ------------------------------------------------------------------------- */

  function syncCTA() {
    const next = $("#nextBtn");

    if (!next || !window.examData) return;

    // Section B has its own controls.
    if (window.examSection === "essay") return;

    const realIndices = Array.isArray(window.realQuestionIndices)
      ? window.realQuestionIndices
      : [];

    if (!realIndices.length) return;

    const lastRealIndex = realIndices[realIndices.length - 1];
    const isLastObjective = window.currentQuestionIndex === lastRealIndex;

    if (isLastObjective) {
      next.innerHTML = `Section B <i class="fa-solid fa-arrow-right"></i>`;
      next.onclick = window.openEssaySection;
      next.classList.add("pulse");
    } else {
      next.innerHTML = `Next <i class="fa-solid fa-arrow-right"></i>`;
      next.onclick = window.nextQuestion;
      next.classList.remove("pulse");
    }
  }


  /* -------------------------------------------------------------------------
     4. ANSWERED DOTS
  ------------------------------------------------------------------------- */

  function decorateAnsweredDots() {
    $$(".question-nav-btn").forEach((btn) => {
      const trueIndex = Number(btn.dataset.qIndex);
      const answered = Boolean(window.userAnswers?.[trueIndex]);

      if (answered) {
        btn.style.position = "relative";

        if (!btn.querySelector(".dot")) {
          const dot = document.createElement("span");
          dot.className = "dot";
          btn.appendChild(dot);
        }

      } else {
        const dot = btn.querySelector(".dot");
        if (dot) dot.remove();
      }
    });
  }


  /* -------------------------------------------------------------------------
     5. OPTIONAL SUBMIT CONFIRMATION
     Used only when explicitly called elsewhere.
  ------------------------------------------------------------------------- */

  function openSubmitConfirm() {
    const realIndices = window.realQuestionIndices || [];
    const total = realIndices.length;
    const answered = realIndices.filter((i) => window.userAnswers[i]).length;
    const unanswered = total - answered;

    const wrap = document.createElement("div");

    wrap.style.cssText = `
      position:fixed;
      inset:0;
      background:rgba(0,0,0,.55);
      display:grid;
      place-items:center;
      z-index:99999;
    `;

    wrap.innerHTML = `
      <div style="
        background:#fff;
        padding:20px;
        border-radius:14px;
        max-width:560px;
        width:92%;
        box-shadow:0 14px 34px rgba(0,0,0,.35);
      ">
        <h3 style="
          margin:0 0 10px;
          font-size:1.25rem;
          font-weight:800;
          color:#1e3a8a;
        ">
          Submit Exam?
        </h3>

        <p>You answered <b>${answered}</b> of <b>${total}</b>.</p>

        ${
          unanswered > 0
            ? `
              <p style="
                background:#fef3c7;
                padding:10px;
                border-radius:10px;
                border:1px solid #fde68a;
                color:#b45309;
              ">
                ${unanswered} unanswered will be marked incorrect.
              </p>
            `
            : `
              <p style="
                background:#dcfce7;
                padding:10px;
                border-radius:10px;
                border:1px solid #bbf7d0;
                color:#166534;
              ">
                All objective questions answered ✔
              </p>
            `
        }

        <div style="
          display:flex;
          justify-content:flex-end;
          gap:10px;
          margin-top:16px;
        ">
          <button id="cxl" style="
            padding:10px 16px;
            background:#f1f5f9;
            border-radius:10px;
            border:1px solid #cbd5e1;
            cursor:pointer;
            font-weight:600;
          ">
            Review
          </button>

          <button id="ok" style="
            padding:10px 16px;
            background:#dc2626;
            border-radius:10px;
            border:none;
            color:#fff;
            cursor:pointer;
            font-weight:600;
          ">
            Submit
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(wrap);

    const cxlBtn = wrap.querySelector("#cxl");
    const okBtn = wrap.querySelector("#ok");

    cxlBtn.onclick = () => wrap.remove();

    okBtn.onclick = () => {
      wrap.remove();
      window.submitExam(false);
    };
  }

  window.openSubmitConfirm = openSubmitConfirm;


  /* -------------------------------------------------------------------------
     6. PATCH CORE HOOKS
  ------------------------------------------------------------------------- */

  function patchCoreHooks() {
    const originalLoad = window.loadQuestion;

    if (typeof originalLoad === "function") {
      window.loadQuestion = function () {
        const result = originalLoad.apply(this, arguments);

        syncCTA();
        decorateAnsweredDots();

        return result;
      };
    }

    const originalNav = window.updateNavigationButtons;

    if (typeof originalNav === "function") {
      window.updateNavigationButtons = function () {
        const result = originalNav.apply(this, arguments);

        // Preserve Section B behaviour from exam-core.js.
        syncCTA();

        return result;
      };
    }
  }


  /* -------------------------------------------------------------------------
     7. SLIDE TRANSITIONS
  ------------------------------------------------------------------------- */

  (function enableSlideTransitions() {
    let lastNode = null;

    document.addEventListener("question:willChange", () => {
      const host = $("#questionContent .qa-slide");

      if (host) {
        lastNode = host.cloneNode(true);
        host.parentElement.insertBefore(lastNode, host);
      }
    });

    document.addEventListener("question:didChange", () => {
      const host = $("#questionContent .qa-slide");

      if (host) {
        host.classList.add("slide-enter");

        requestAnimationFrame(() => {
          host.classList.add("slide-enter-active");
        });

        setTimeout(() => {
          host.classList.remove("slide-enter", "slide-enter-active");
        }, 300);
      }

      if (lastNode) {
        lastNode.classList.add("slide-exit");

        requestAnimationFrame(() => {
          lastNode.classList.add("slide-exit-active");
        });

        setTimeout(() => {
          lastNode.remove();
          lastNode = null;
        }, 300);
      }
    });
  })();


  /* -------------------------------------------------------------------------
     8. START EXAM PATCH
  ------------------------------------------------------------------------- */

  function patchStartExam() {
    const originalStart = window.startExam;

    if (typeof originalStart !== "function") return;

    window.startExam = async function () {
      const result = await originalStart.apply(this, arguments);

      if (typeof toast === "function") {
        setTimeout(() => {
          toast("Tip: Use ← → keys to navigate", "info", 2400);
        }, 300);
      }

      return result;
    };
  }


  /* -------------------------------------------------------------------------
     9. BOOT
  ------------------------------------------------------------------------- */

  document.addEventListener("DOMContentLoaded", () => {
    enableFlashPill();
    patchCoreHooks();
    patchStartExam();

    const boot = () => {
      if (window.examData) {
        syncCTA();
        decorateAnsweredDots();
      } else {
        setTimeout(boot, 150);
      }
    };

    boot();
  });

})();
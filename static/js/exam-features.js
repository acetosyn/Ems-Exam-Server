/* ============================================================================
   EMIS EXAM — FEATURES MODULE (2025 LITE VERSION)
   Essential UI upgrades only:
   ✓ ✔ / ✖ flash pill
   ✓ Next → / Submit auto-sync
   ✓ Answered dots
   ✓ Submit confirmation modal
   ✓ Clean slide transitions
   Fully compatible with exam-core.js + strict anti-cheat.
============================================================================ */

(function () {
  if (!window) return;

  const $  = (s,r=document)=>r.querySelector(s);
  const $$ = (s,r=document)=>Array.from(r.querySelectorAll(s));


  /* -------------------------------------------------------------------------
     1. ✔ / ✖ FLASH PILL (Correct / Wrong)
  ------------------------------------------------------------------------- */
  function enableFlashPill() {
    const originalSelect = window.selectOption;

    window.selectOption = function (idx) {
      const q = window.examData?.questions?.[window.currentQuestionIndex];
      const host = $("#questionContent");

      if (q && host) {
        const correct = q.correctIndex;
        const ok = (idx === correct);

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
     Inject required minimal styles
  ------------------------------------------------------------------------- */
  const style = document.createElement("style");
  style.textContent = `
    .eflash {
      position:absolute; top:-10px; right:-10px;
      padding:8px 10px; border-radius:50%; font-weight:800; color:#fff;
      opacity:0; scale:.9; transition:all .22s ease; z-index:20;
      box-shadow:0 8px 22px rgba(0,0,0,.25);
    }
    .eflash.ok { background:#16a34a }
    .eflash.bad { background:#dc2626 }
    .eflash.show { opacity:1; scale:1 }

    .question-nav-btn .dot {
      position:absolute; top:6px; right:6px;
      width:8px; height:8px; border-radius:50%;
      background:#16a34a; box-shadow:0 0 0 2px #fff;
    }

    #nextBtn.pulse { animation:pulseBtn .8s ease-in-out 2 }
    @keyframes pulseBtn {
      0%{transform:scale(1)}
      50%{transform:scale(1.06)}
      100%{transform:scale(1)}
    }

    .qa-slide{will-change:transform,opacity}
    .slide-enter{opacity:0;transform:translateX(26px)}
    .slide-enter-active{transition:all .25s ease; opacity:1;transform:translateX(0)}
    .slide-exit{opacity:1;transform:translateX(0)}
    .slide-exit-active{transition:all .25s ease; opacity:0;transform:translateX(-26px)}
  `;
  document.head.appendChild(style);



  /* -------------------------------------------------------------------------
     2. Sync Next → / Submit CTA button
  ------------------------------------------------------------------------- */
  function syncCTA() {
    const next = $("#nextBtn");
    if (!next || !window.examData) return;

    const last = (window.currentQuestionIndex === window.examData.questions.length - 1);

    next.textContent = last ? "Submit" : "Next →";
    next.onclick     = last ? openSubmitConfirm : window.nextQuestion;

    if (last) next.classList.add("pulse");
    else next.classList.remove("pulse");
  }


  /* -------------------------------------------------------------------------
     3. Show green "answered" dot on answered questions
  ------------------------------------------------------------------------- */
  function decorateAnsweredDots() {
    $$(".question-nav-btn").forEach((btn, idx) => {
      const q = window.examData?.questions?.[idx];
      const qid = q?.id ?? idx;

      const answered = !!window.userAnswers[qid];

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
     4. Submit Confirmation Modal (Enhanced UX: Hover + Pointer)
  ------------------------------------------------------------------------- */
function openSubmitConfirm() {

  // ✔ Use REAL question indices (ignores instructions)
  const realIndices = window.realQuestionIndices || [];
  const total = realIndices.length;

  // ✔ Count answered correctly
  const answered = realIndices.filter(i => window.userAnswers[i]).length;

  // ✔ Correct unanswered count
  const unanswered = total - answered;

  const wrap = document.createElement("div");
  wrap.style.cssText = `
    position:fixed; inset:0; background:rgba(0,0,0,.55);
    display:grid; place-items:center; z-index:99999;
  `;

  wrap.innerHTML = `
    <div style="background:#fff; padding:20px; border-radius:14px;
         max-width:560px; width:92%; box-shadow:0 14px 34px rgba(0,0,0,.35);
         animation:fadeIn .25s ease-out">
      <h3 style="margin:0 0 10px; font-size:1.25rem; font-weight:800; color:#1e3a8a">
        Submit Exam?
      </h3>

      <p>You answered <b>${answered}</b> of <b>${total}</b>.</p>

      ${
        unanswered > 0
        ? `<p style="background:#fef3c7; padding:10px; border-radius:10px;
                      border:1px solid #fde68a; color:#b45309">
             ${unanswered} unanswered will be marked incorrect.
           </p>`
        : `<p style="background:#dcfce7; padding:10px; border-radius:10px;
                      border:1px solid #bbf7d0; color:#166534">
             All questions answered ✔
           </p>`
      }

      <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:16px">

        <!-- REVIEW BTN -->
        <button id="cxl" style="
            padding:10px 16px; background:#f1f5f9; border-radius:10px;
            border:1px solid #cbd5e1; cursor:pointer;
            transition: all .2s ease; font-weight:600;">
          Review
        </button>

        <!-- SUBMIT BTN -->
        <button id="ok" style="
            padding:10px 16px; background:#dc2626; border-radius:10px;
            color:#fff; cursor:pointer;
            transition: all .2s ease; font-weight:600;">
          Submit
        </button>

      </div>
    </div>
  `;

  document.body.appendChild(wrap);

  // HOVER EFFECTS (unchanged)
  const cxlBtn = wrap.querySelector("#cxl");
  const okBtn  = wrap.querySelector("#ok");

  cxlBtn.onmouseover = () => {
    cxlBtn.style.background = "#e2e8f0";
    cxlBtn.style.transform = "scale(1.05)";
  };
  cxlBtn.onmouseout = () => {
    cxlBtn.style.background = "#f1f5f9";
    cxlBtn.style.transform = "scale(1)";
  };

  okBtn.onmouseover = () => {
    okBtn.style.filter = "brightness(1.2)";
    okBtn.style.transform = "scale(1.05)";
  };
  okBtn.onmouseout = () => {
    okBtn.style.filter = "none";
    okBtn.style.transform = "scale(1)";
  };

  // CLICK HANDLERS
  cxlBtn.onclick = () => wrap.remove();
  okBtn.onclick  = () => { wrap.remove(); window.submitExam(false); };
}


  /* -------------------------------------------------------------------------
     5. Patch loadQuestion & navigation buttons
  ------------------------------------------------------------------------- */
  function patchCoreHooks() {
    const origLoad = window.loadQuestion;
    window.loadQuestion = function () {
      const r = origLoad.apply(this, arguments);
      syncCTA();
      decorateAnsweredDots();
      return r;
    };

    const origNav = window.updateNavigationButtons;
    window.updateNavigationButtons = function () {
      const r = origNav.apply(this, arguments);
      syncCTA();
      return r;
    };
  }



  /* -------------------------------------------------------------------------
     6. Slide Transitions
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
        requestAnimationFrame(() =>
          host.classList.add("slide-enter-active")
        );
        setTimeout(() =>
          host.classList.remove("slide-enter", "slide-enter-active"),
          300
        );
      }

      if (lastNode) {
        lastNode.classList.add("slide-exit");
        requestAnimationFrame(() =>
          lastNode.classList.add("slide-exit-active")
        );
        setTimeout(() => { lastNode.remove(); lastNode = null; }, 300);
      }
    });
  })();



  /* -------------------------------------------------------------------------
     7. Start exam → show tip
  ------------------------------------------------------------------------- */
  function patchStartExam() {
    const orig = window.startExam;
    window.startExam = async function () {
      const r = await orig.apply(this, arguments);

      // small tip
      setTimeout(() =>
        toast("Tip: Use ← → keys to navigate", "info", 2400),
      300);

      return r;
    };
  }


  /* -------------------------------------------------------------------------
     BOOT
  ------------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    enableFlashPill();
    patchCoreHooks();
    patchStartExam();

    // Wait for examData, then sync buttons & dots
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

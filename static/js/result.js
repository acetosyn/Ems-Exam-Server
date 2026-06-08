/* ============================================================
   EMIS RESULT ENGINE — result.js
   ------------------------------------------------------------
   Student-side completion confirmation only.

   Includes:
   - Live clock
   - Theme toggle
   - Completion info
   - One-time party celebration rain
===============================================================*/

document.addEventListener("DOMContentLoaded", () => {
  initLiveClock();
  initThemeToggle();
  injectCompletionInfo();
  setupBackButton();
  overrideBackNavigation();

  setTimeout(() => {
    startSubmissionCelebration();
  }, 450);
});

/* ------------------------------------------------------------
   1. Live Clock
-------------------------------------------------------------*/
function initLiveClock() {
  const clock = document.getElementById("liveClock");
  if (!clock) return;

  function updateClock() {
    const now = new Date();

    clock.textContent = now.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  }

  updateClock();
  setInterval(updateClock, 1000);
}

/* ------------------------------------------------------------
   2. Theme Toggle
-------------------------------------------------------------*/
function initThemeToggle() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;

  const savedTheme = localStorage.getItem("emis_result_theme");

  if (savedTheme === "dark") {
    document.body.classList.add("dark-mode");
    btn.innerHTML = `<i class="fa-solid fa-sun"></i>`;
  }

  btn.addEventListener("click", () => {
    document.body.classList.toggle("dark-mode");

    const isDark = document.body.classList.contains("dark-mode");

    localStorage.setItem("emis_result_theme", isDark ? "dark" : "light");

    btn.innerHTML = isDark
      ? `<i class="fa-solid fa-sun"></i>`
      : `<i class="fa-solid fa-moon"></i>`;
  });
}

/* ------------------------------------------------------------
   3. Completion Info
-------------------------------------------------------------*/
function injectCompletionInfo() {
  const result = window.resultData || {};
  const student = window.studentData || {};

  const subject = cleanText(result.subject || result.Subject || "your exam");
  const studentName = cleanText(student.full_name || student.name || "Student");
  const admissionNo = cleanText(
    student.admission_number ||
    student.admission_no ||
    student.student_id ||
    "--"
  );

  const className = cleanText(
    student.class_name ||
    student.class ||
    result.class_name ||
    result.Class ||
    "--"
  );

  const classCategory = cleanText(
    student.class_category ||
    result.class_category ||
    result["Class Category"] ||
    "--"
  );

  const submittedAt = formatDateTime(
    result.submitted_at ||
    result.submittedAt ||
    result["Submitted At"]
  );

  setText("studentName", studentName);
  setText("studentID", admissionNo);
  setText("studentClass", className);
  setText("studentCategory", classCategory);
  setText("studentSysID", student.id || admissionNo);

  setText("subjectName", subject);
  setText("examStatus", "Completed");
  setText("completionDate", submittedAt);

  const wrapper = document.querySelector(".result-wrapper");
  if (wrapper) {
    wrapper.dataset.subject = subject;
  }
}

/* ------------------------------------------------------------
   4. Back Button
-------------------------------------------------------------*/
function setupBackButton() {
  const btn = document.getElementById("backToDashboardBtn");
  if (!btn) return;

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    window.location.href = "/back_to_exam_dashboard";
  });
}

/* ------------------------------------------------------------
   5. Disable Browser Back To Exam Page
-------------------------------------------------------------*/
function overrideBackNavigation() {
  try {
    history.pushState(null, "", window.location.href);

    window.onpopstate = () => {
      window.location.href = "/back_to_exam_dashboard";
    };
  } catch (error) {
    console.warn("Back navigation override unavailable:", error);
  }
}

/* ------------------------------------------------------------
   6. One-Time Submission Celebration
-------------------------------------------------------------*/
function startSubmissionCelebration() {
  const oldLayer = document.getElementById("submissionCelebrationLayer");
  if (oldLayer) oldLayer.remove();

  const layer = document.createElement("div");
  layer.id = "submissionCelebrationLayer";
  layer.className = "submission-celebration-layer";
  document.body.appendChild(layer);

  injectCelebrationStyles();

  const emojis = ["🎈", "🎉", "🎊", "⭐", "✨", "🏆", "💫"];
  const colors = ["#2563eb", "#8b5cf6", "#06b6d4", "#22c55e", "#f59e0b", "#ef4444", "#ec4899"];

  for (let i = 0; i < 55; i++) {
    const item = document.createElement("div");
    const isEmoji = Math.random() > 0.45;

    item.className = isEmoji ? "party-emoji" : "party-confetti";

    if (isEmoji) {
      item.textContent = emojis[Math.floor(Math.random() * emojis.length)];
    } else {
      item.style.background = colors[Math.floor(Math.random() * colors.length)];
      item.style.borderRadius = Math.random() > 0.5 ? "999px" : "4px";
    }

    item.style.left = Math.random() * 100 + "vw";
    item.style.animationDelay = Math.random() * 0.9 + "s";
    item.style.animationDuration = 3.5 + Math.random() * 3.2 + "s";
    item.style.transform = `rotate(${Math.random() * 360}deg)`;
    item.style.setProperty("--drift", `${Math.random() * 180 - 90}px`);
    item.style.setProperty("--spin", `${Math.random() * 720 - 360}deg`);

    layer.appendChild(item);
  }

  for (let i = 0; i < 10; i++) {
    const balloon = document.createElement("div");
    balloon.className = "party-balloon";
    balloon.style.left = Math.random() * 100 + "vw";
    balloon.style.animationDelay = Math.random() * 1.2 + "s";
    balloon.style.animationDuration = 6 + Math.random() * 2 + "s";
    balloon.style.background = colors[Math.floor(Math.random() * colors.length)];
    balloon.style.setProperty("--drift", `${Math.random() * 140 - 70}px`);

    layer.appendChild(balloon);
  }

  setTimeout(() => {
    layer.remove();
  }, 8500);
}

/* ------------------------------------------------------------
   7. Inject Celebration CSS From JS
-------------------------------------------------------------*/
function injectCelebrationStyles() {
  if (document.getElementById("submissionCelebrationStyles")) return;

  const style = document.createElement("style");
  style.id = "submissionCelebrationStyles";

  style.textContent = `
    .submission-celebration-layer {
      position: fixed;
      inset: 0;
      overflow: hidden;
      pointer-events: none;
      z-index: 99999;
    }

    .party-emoji,
    .party-confetti,
    .party-balloon {
      position: absolute;
      top: -60px;
      will-change: transform, opacity;
    }

    .party-emoji {
      font-size: clamp(1.3rem, 2.4vw, 2.5rem);
      filter: drop-shadow(0 8px 12px rgba(15, 23, 42, 0.18));
      animation: partyRain linear forwards;
    }

    .party-confetti {
      width: 12px;
      height: 18px;
      opacity: 0.95;
      box-shadow: 0 6px 14px rgba(15, 23, 42, 0.16);
      animation: partyRain linear forwards;
    }

    .party-balloon {
      width: 34px;
      height: 44px;
      border-radius: 50% 50% 45% 45%;
      opacity: 0.92;
      box-shadow:
        inset -8px -10px 14px rgba(15, 23, 42, 0.16),
        inset 6px 7px 10px rgba(255, 255, 255, 0.35),
        0 14px 26px rgba(15, 23, 42, 0.18);
      animation: balloonRain ease-in forwards;
    }

    .party-balloon::before {
      content: "";
      position: absolute;
      left: 50%;
      bottom: -7px;
      transform: translateX(-50%);
      width: 0;
      height: 0;
      border-left: 5px solid transparent;
      border-right: 5px solid transparent;
      border-top: 8px solid currentColor;
      color: inherit;
    }

    .party-balloon::after {
      content: "";
      position: absolute;
      left: 50%;
      bottom: -42px;
      width: 1px;
      height: 38px;
      background: rgba(15, 23, 42, 0.25);
      transform: translateX(-50%);
    }

    @keyframes partyRain {
      0% {
        transform: translate3d(0, -80px, 0) rotate(0deg) scale(0.85);
        opacity: 0;
      }

      8% {
        opacity: 1;
      }

      100% {
        transform: translate3d(var(--drift), 115vh, 0) rotate(var(--spin)) scale(1);
        opacity: 0;
      }
    }

    @keyframes balloonRain {
      0% {
        transform: translate3d(0, -90px, 0) rotate(-8deg);
        opacity: 0;
      }

      12% {
        opacity: 1;
      }

      100% {
        transform: translate3d(var(--drift), 118vh, 0) rotate(10deg);
        opacity: 0;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .submission-celebration-layer {
        display: none !important;
      }
    }
  `;

  document.head.appendChild(style);
}

/* ------------------------------------------------------------
   Utilities
-------------------------------------------------------------*/
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value || "--";
}

function cleanText(value) {
  return String(value || "").trim();
}

function formatDateTime(value) {
  if (!value) return "Submitted";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
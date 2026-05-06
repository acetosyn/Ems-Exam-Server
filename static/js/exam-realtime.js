/* ======================================================================
   EMIS EXAM — STRICT ANTICHEAT (2025 VERSION v4 — FINAL & STABLE)
   • No double triggers
   • First violation = warning
   • Second = immediate termination
   • Protected from startup blur glitches
   ====================================================================== */

(function () {

  console.log("%c[exam-realtime] STRICT MODE v4 loaded", "color:#38bdf8;font-weight:bold");

  // -------------------------------------------------------------
  // INTERNAL STATE (always fresh)
  // -------------------------------------------------------------
  window.__ANTI_CHEAT_ACTIVE = false; 
  window.__ANTICHEAT_READY   = false; 
  window.__TAB_STRIKES       = 0;
  window.__DEVTOOLS_STRIKES  = 0;
  window.__OFFLINE_SINCE     = null;


// -------------------------------------------------------------
// FLASH MESSAGE — 5 minutes warning, safe, no auto-blur strikes
// -------------------------------------------------------------
function temporarilyPauseAnticheat() {
    window.__ANTICHEAT_READY = false;
    setTimeout(() => {
        window.__ANTICHEAT_READY = true;
    }, 450);  // prevents instant 2nd strike
}

function flash(msg, type = "warning") {
    const el = document.createElement("div");

    // Prevent flash() itself from causing blur → 2nd strike
    if (type === "warning") temporarilyPauseAnticheat();

    const icon = type === "danger" ? "❌"
              : type === "success" ? "✔️"
              : "⚠️";

    const bg = type === "danger" ? "#dc2626"
             : type === "success" ? "#16a34a"
             : "#facc15";

    const textColor = type === "warning" ? "#0f172a" : "#fff";

    Object.assign(el.style, {
        position: "fixed",
        top: "22px",
        right: "22px",
        padding: "16px 26px",
        borderRadius: "12px",
        zIndex: 999999,
        color: textColor,
        fontWeight: "800",
        fontSize: "1.05rem",
        background: bg,
        boxShadow: "0 4px 20px rgba(0,0,0,.35)",
        opacity: "0",
        transition: "opacity .35s ease"
    });

    el.textContent = `${icon}  ${msg}`;

    document.body.appendChild(el);
    requestAnimationFrame(() => (el.style.opacity = "1"));

    // 5 minutes for warning, 2.4s for danger
    const duration = type === "warning" ? 300000 : 2400;

    setTimeout(() => {
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 400);
    }, duration);
}


// -------------------------------------------------------------
// VIOLATION HANDLER (Improved messaging)
// -------------------------------------------------------------
function strike(reason = "") {
  if (!window.__ANTI_CHEAT_ACTIVE || !window.__ANTICHEAT_READY || window.__examFinished)
    return;

  window.__TAB_STRIKES++;

  // FIRST OFFENSE
  if (window.__TAB_STRIKES === 1) {
    flash("⚠️ Warning: You switched tab or left the exam page. Do NOT do this again.", "warning");
    return;
  }

  // SECOND OFFENSE
  if (window.__TAB_STRIKES >= 2) {
    flash("❌ Exam terminated for violating instructions.", "danger");
    setTimeout(() => window.submitExam(true), 650);
  }
}


  // -------------------------------------------------------------
  // 1. VISIBILITY — Switching Tabs
  // -------------------------------------------------------------
  document.addEventListener("visibilitychange", () => {
    if (!window.__ANTI_CHEAT_ACTIVE) return;
    if (!window.__ANTICHEAT_READY) return;
    if (document.hidden) strike("tab switch");
  });


  // -------------------------------------------------------------
  // 2. BLUR — Minimizing or switching apps
  // -------------------------------------------------------------
  window.addEventListener("blur", () => {
    if (!window.__ANTI_CHEAT_ACTIVE) return;
    if (!window.__ANTICHEAT_READY) return;
    strike("blur/minimize");
  });


  // -------------------------------------------------------------
  // 3. Keyboard Restrictions
  // -------------------------------------------------------------
  document.addEventListener("keydown", (e) => {
    if (!window.__ANTI_CHEAT_ACTIVE) return;

    const k = e.key.toLowerCase();

    // block new tab, navigation etc
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      return false;
    }

    // block devtools attempts
    if (k === "f12" || (e.ctrlKey && e.shiftKey)) {
      e.preventDefault();
      return false;
    }

    // block backspace navigation
    if (
      k === "backspace" &&
      !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
    ) {
      e.preventDefault();
      return false;
    }
  });


  // -------------------------------------------------------------
  // 4. DEVTOOLS DETECTION
  // -------------------------------------------------------------
  setInterval(() => {
    if (!window.__ANTI_CHEAT_ACTIVE) return;

    const suspicious =
      window.outerWidth - window.innerWidth > 160 ||
      window.outerHeight - window.innerHeight > 160;

    if (suspicious) {
      window.__DEVTOOLS_STRIKES++;

      if (window.__DEVTOOLS_STRIKES === 1) {
        flash("⚠️ DevTools detected. Close immediately!", "warning");
      } else {
        flash("❌ DevTools opened again — exam ended!", "danger");
        setTimeout(() => submitExam(true), 650);
      }
    }

  }, 900);


  // -------------------------------------------------------------
  // 5. NETWORK STRICT MODE
  // -------------------------------------------------------------
  window.addEventListener("offline", () => {
    if (!window.__ANTI_CHEAT_ACTIVE) return;
    window.__OFFLINE_SINCE = Date.now();
    flash("⚠️ You are offline. Reconnect within 30s!", "warning");
  });

  window.addEventListener("online", () => {
    window.__OFFLINE_SINCE = null;
  });

  setInterval(() => {
    if (!window.__ANTI_CHEAT_ACTIVE) return;
    if (window.__OFFLINE_SINCE && Date.now() - window.__OFFLINE_SINCE > 30000) {
      flash("❌ Offline too long — exam ending!", "danger");
      submitExam(true);
    }
  }, 2500);


  // -------------------------------------------------------------
  // 6. BLOCK PAGE UNLOAD
  // -------------------------------------------------------------
  window.addEventListener("beforeunload", (e) => {
    if (window.__ANTI_CHEAT_ACTIVE && !window.__examFinished) {
      e.preventDefault();
      e.returnValue = "";
    }
  });


  // -------------------------------------------------------------
  // 7. Hook startExam
  // -------------------------------------------------------------
  const REAL_startExam = window.startExam;

  window.startExam = async function () {
    await REAL_startExam();

    // Prevent blur from animations
    window.__ANTICHEAT_READY = false;

    // Enable anti-cheat fully after UI is stable
    setTimeout(() => {
      window.__ANTI_CHEAT_ACTIVE = true;
      window.__ANTICHEAT_READY = true;

      console.log(
        "%c[exam-realtime] STRICT ANTICHEAT ACTIVATED ✓",
        "color:lime;font-weight:bold"
      );

      // reset counters fresh
      window.__TAB_STRIKES = 0;
      window.__DEVTOOLS_STRIKES = 0;
      window.__OFFLINE_SINCE = null;

    }, 900);
  };

})();

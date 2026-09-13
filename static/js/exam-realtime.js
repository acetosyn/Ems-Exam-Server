/* =================================================================================================
   exam-realtime.js — EMIS STRICT EXAM SECURITY v6.0

   SECURITY:
   • Security activation does NOT depend on localhost/server loading speed
   • Persistent watchdog activates security as soon as the real exam is ready
   • First tab/window/minimize/focus loss = warning
   • Second tab/window/minimize/focus loss = automatic termination
   • visibilitychange + blur + focus watchdog deduplicated into ONE offence
   • Right-click blocked
   • Ctrl / Cmd shortcuts blocked
   • F12 blocked
   • Copy / Cut / Paste blocked
   • Dragging blocked
   • Text selection blocked while exam is active
   • Browser print output protected
   • Backspace browser navigation blocked
   • Offline > 30 seconds = automatic termination
   • Network state continuously verified
   • beforeunload protection
   • Self-healing activation if another script changes startExam wrapping/order
   • DevTools heuristic intentionally DISABLED to prevent false positives

   OWNERSHIP:
   exam-core.js     = questions, scoring, timer, submission
   exam-features.js = examination UI / experience
   exam-realtime.js = live examination security
================================================================================================= */

(() => {
  if (window.__EMIS_REALTIME_V60__) return;
  window.__EMIS_REALTIME_V60__ = true;

  console.log("%c[exam-realtime] STRICT SECURITY v6.0 loaded ✓", "color:#0f766e;font-weight:900;font-size:13px");

  /* ==============================================================================================
     CONFIG
  ============================================================================================== */

  const CONFIG = {
    startupGraceMs: 700,
    watchdogMs: 300,
    focusCheckMs: 650,
    focusDedupeMs: 1400,
    warningPauseMs: 500,
    offlineLimitMs: 30000,
    networkCheckMs: 1000,
    warningDurationMs: 9000,
    dangerDurationMs: 7000,
    infoDurationMs: 4200,
    successDurationMs: 4500,

    /* Deliberately false. Browser DevTools size heuristics caused false warnings. */
    devtoolsDetectionEnabled: false
  };

  /* ==============================================================================================
     GLOBAL SECURITY STATE
  ============================================================================================== */

  window.__ANTI_CHEAT_ACTIVE = false;
  window.__ANTICHEAT_READY = false;
  window.__TAB_STRIKES = 0;
  window.__DEVTOOLS_STRIKES = 0;
  window.__OFFLINE_SINCE = null;
  window.__examSecurityTerminating = false;
  window.__examTerminationReason = null;

  const state = {
    startRequested: false,
    activating: false,
    activatedAt: 0,
    lastFocusViolationAt: 0,
    offline15Shown: false,
    offline5Shown: false,
    watchdogTimer: null,
    focusTimer: null,
    networkTimer: null
  };

  /* ==============================================================================================
     SECURITY UI
  ============================================================================================== */

  function injectSecurityStyles() {
    if (document.getElementById("emisSecurityStyles")) return;

    const style = document.createElement("style");
    style.id = "emisSecurityStyles";

    style.textContent = `
      .emis-security-stack{position:fixed;top:88px;left:50%;z-index:999999;display:grid;gap:12px;width:min(620px,calc(100vw - 34px));transform:translateX(-50%);pointer-events:none}
      .emis-security-flash{position:relative;display:grid;grid-template-columns:64px minmax(0,1fr);align-items:center;gap:16px;width:100%;min-height:92px;padding:16px 20px 16px 18px;overflow:hidden;background:rgba(255,255,255,.99);border:1px solid #d9e2e9;border-radius:19px;box-shadow:0 20px 55px rgba(18,32,47,.22),0 4px 13px rgba(18,32,47,.08);backdrop-filter:blur(14px);opacity:0;transform:translateY(-16px) scale(.965);animation:emisSecurityIn .34s cubic-bezier(.2,.82,.25,1) forwards}
      .emis-security-flash::before{content:"";position:absolute;inset:0 auto 0 0;width:7px;border-radius:19px 0 0 19px}
      .emis-security-icon{position:relative;width:60px;height:60px;display:grid;place-items:center;flex:0 0 auto;border-radius:18px;font-size:1.5rem;box-shadow:inset 0 0 0 1px rgba(255,255,255,.48)}
      .emis-security-icon::after{content:"";position:absolute;inset:-6px;border:2px solid currentColor;border-radius:21px;opacity:.12;pointer-events:none}
      .emis-security-icon i{position:relative;z-index:2}
      .emis-security-copy{min-width:0}
      .emis-security-copy strong{display:block;margin:0 0 6px;color:#182334;font-size:1.08rem;font-weight:950;line-height:1.2;letter-spacing:-.012em}
      .emis-security-copy span{display:block;max-width:510px;color:#4f6073;font-size:.94rem;font-weight:650;line-height:1.55}
      .emis-security-progress{position:absolute;left:7px;right:0;bottom:0;height:4px;opacity:.28;transform-origin:left center;animation:emisSecurityProgress linear forwards}

      .emis-security-flash.warning{background:linear-gradient(105deg,#fff5d6 0%,#fffaf0 32%,#fff 100%);border-color:#e9ca78;box-shadow:0 20px 55px rgba(174,111,0,.18),0 4px 13px rgba(18,32,47,.07)}
      .emis-security-flash.warning::before,.emis-security-flash.warning .emis-security-progress{background:#db8e08}
      .emis-security-flash.warning .emis-security-icon{color:#915d00;background:linear-gradient(145deg,#fff1bc,#ffdd7c)}
      .emis-security-flash.warning .emis-security-copy strong{color:#855600}
      .emis-security-flash.warning .emis-security-icon i{animation:emisWarningPulse 1.05s ease-in-out 4}

      .emis-security-flash.danger{background:linear-gradient(105deg,#ffebee 0%,#fff7f8 32%,#fff 100%);border-color:#e7b5bc;box-shadow:0 21px 58px rgba(194,38,54,.21),0 4px 13px rgba(18,32,47,.08)}
      .emis-security-flash.danger::before,.emis-security-flash.danger .emis-security-progress{background:#cf3143}
      .emis-security-flash.danger .emis-security-icon{color:#ae2031;background:linear-gradient(145deg,#ffdce1,#ffbdc6)}
      .emis-security-flash.danger .emis-security-copy strong{color:#a51f30}
      .emis-security-flash.danger .emis-security-icon i{animation:emisDangerShake .55s ease 3}

      .emis-security-flash.success{background:linear-gradient(105deg,#eaf9f1 0%,#f8fdfb 32%,#fff 100%);border-color:#b9dfca;box-shadow:0 19px 50px rgba(25,130,79,.16),0 4px 12px rgba(18,32,47,.07)}
      .emis-security-flash.success::before,.emis-security-flash.success .emis-security-progress{background:#208653}
      .emis-security-flash.success .emis-security-icon{color:#176b46;background:linear-gradient(145deg,#d9f3e5,#bce7cf)}
      .emis-security-flash.success .emis-security-copy strong{color:#176b46}
      .emis-security-flash.success .emis-security-icon i{animation:emisSuccessPop .5s ease}

      .emis-security-flash.info{background:linear-gradient(105deg,#eaf5fb 0%,#f8fcfe 32%,#fff 100%);border-color:#bad7e5;box-shadow:0 19px 50px rgba(38,116,157,.15),0 4px 12px rgba(18,32,47,.07)}
      .emis-security-flash.info::before,.emis-security-flash.info .emis-security-progress{background:#2879a5}
      .emis-security-flash.info .emis-security-icon{color:#226a91;background:linear-gradient(145deg,#d9edf7,#beddea)}
      .emis-security-flash.info .emis-security-copy strong{color:#205f82}

      body.emis-exam-secured,body.emis-exam-secured *{-webkit-user-select:none!important;user-select:none!important;-webkit-touch-callout:none!important}
      body.emis-exam-secured input,body.emis-exam-secured textarea{user-select:text!important;-webkit-user-select:text!important}

      .emis-security-flash.is-leaving{animation:emisSecurityOut .25s ease forwards}
      @keyframes emisSecurityIn{0%{opacity:0;transform:translateY(-16px) scale(.965)}72%{opacity:1;transform:translateY(2px) scale(1.008)}100%{opacity:1;transform:translateY(0) scale(1)}}
      @keyframes emisSecurityOut{0%{opacity:1;transform:translateY(0) scale(1)}100%{opacity:0;transform:translateY(-10px) scale(.985)}}
      @keyframes emisSecurityProgress{from{transform:scaleX(1)}to{transform:scaleX(0)}}
      @keyframes emisWarningPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.19)}}
      @keyframes emisDangerShake{0%,100%{transform:translateX(0)}20%{transform:translateX(-4px)}40%{transform:translateX(4px)}60%{transform:translateX(-3px)}80%{transform:translateX(3px)}}
      @keyframes emisSuccessPop{0%{transform:scale(.7)}65%{transform:scale(1.18)}100%{transform:scale(1)}}

      @media print{
        body.emis-exam-secured *{visibility:hidden!important}
        body.emis-exam-secured::before{content:"Printing is disabled during the examination.";visibility:visible!important;position:fixed;inset:0;display:grid;place-items:center;font:700 24px Arial,sans-serif;color:#222;background:#fff}
      }

      @media(max-width:700px){
        .emis-security-stack{top:72px;width:calc(100vw - 20px)}
        .emis-security-flash{grid-template-columns:54px minmax(0,1fr);gap:12px;min-height:82px;padding:13px 14px 13px 15px;border-radius:16px}
        .emis-security-flash::before{width:6px}.emis-security-icon{width:52px;height:52px;border-radius:15px;font-size:1.25rem}
        .emis-security-copy strong{margin-bottom:4px;font-size:.96rem}.emis-security-copy span{font-size:.84rem;line-height:1.48}
        .emis-security-progress{left:6px;height:3px}
      }

      @media(max-width:420px){
        .emis-security-stack{top:66px;width:calc(100vw - 14px)}
        .emis-security-flash{grid-template-columns:48px minmax(0,1fr);gap:10px;min-height:76px;padding:12px}
        .emis-security-icon{width:46px;height:46px;font-size:1.1rem}
        .emis-security-copy strong{font-size:.9rem}.emis-security-copy span{font-size:.79rem}
      }

      @media(prefers-reduced-motion:reduce){.emis-security-flash,.emis-security-progress,.emis-security-icon i{animation:none!important;transition:none!important}}
    `;

    document.head.appendChild(style);
  }

  function getSecurityStack() {
    let stack = document.getElementById("emisSecurityStack");
    if (!stack) {
      stack = document.createElement("div");
      stack.id = "emisSecurityStack";
      stack.className = "emis-security-stack";
      stack.setAttribute("aria-live", "assertive");
      stack.setAttribute("aria-atomic", "false");
      document.body.appendChild(stack);
    }
    return stack;
  }

  function flash(message, type = "warning", title = "", duration = null) {
    const normalizedType = ["warning","danger","success","info"].includes(type) ? type : "info";
    const titles = { warning:"Exam Warning", danger:"Exam Security", success:"Connection Restored", info:"Exam Protected" };
    const icons = { warning:"fa-triangle-exclamation", danger:"fa-shield-halved", success:"fa-circle-check", info:"fa-shield-halved" };
    const defaultDuration = normalizedType === "warning" ? CONFIG.warningDurationMs : normalizedType === "danger" ? CONFIG.dangerDurationMs : normalizedType === "success" ? CONFIG.successDurationMs : CONFIG.infoDurationMs;
    const visibleFor = Number(duration) > 0 ? Number(duration) : defaultDuration;
    const stack = getSecurityStack();
    const notice = document.createElement("div");

    notice.className = `emis-security-flash ${normalizedType}`;
    notice.setAttribute("role", normalizedType === "danger" || normalizedType === "warning" ? "alert" : "status");
    notice.innerHTML = `<div class="emis-security-icon"><i class="fa-solid ${icons[normalizedType]}"></i></div><div class="emis-security-copy"><strong></strong><span></span></div><div class="emis-security-progress"></div>`;
    notice.querySelector("strong").textContent = title || titles[normalizedType];
    notice.querySelector("span").textContent = String(message || "");

    const progress = notice.querySelector(".emis-security-progress");
    if (progress) progress.style.animationDuration = `${visibleFor}ms`;

    stack.appendChild(notice);
    while (stack.children.length > 2) stack.firstElementChild?.remove();

    setTimeout(() => {
      if (!notice.isConnected) return;
      notice.classList.add("is-leaving");
      setTimeout(() => notice.remove(), 270);
    }, visibleFor);

    return notice;
  }

  window.examSecurityFlash = flash;

  /* ==============================================================================================
     SECURITY STATE HELPERS
  ============================================================================================== */

  function securityEngaged() {
    return window.__ANTI_CHEAT_ACTIVE === true && !window.__examFinished && !window.__examSecurityTerminating;
  }

  function securityActive() {
    return securityEngaged() && window.__ANTICHEAT_READY === true;
  }

  function examInterfaceVisible() {
    const examInterface = document.getElementById("examInterface");
    if (document.body.classList.contains("exam-started")) return true;
    if (!examInterface) return false;
    if (examInterface.classList.contains("hidden")) return false;
    return getComputedStyle(examInterface).display !== "none";
  }

  function examDataReady() {
    return Boolean(window.examData && Array.isArray(window.realQuestionIndices) && window.realQuestionIndices.length > 0);
  }

  function examReadyForSecurity() {
    return !window.__examFinished && !window.__examSecurityTerminating && examInterfaceVisible() && examDataReady();
  }

  function temporarilyPauseAnticheat(duration = CONFIG.warningPauseMs) {
    if (!securityEngaged()) return;
    window.__ANTICHEAT_READY = false;

    setTimeout(() => {
      if (window.__ANTI_CHEAT_ACTIVE && !window.__examFinished && !window.__examSecurityTerminating) window.__ANTICHEAT_READY = true;
    }, Math.max(150, Number(duration) || CONFIG.warningPauseMs));
  }

  window.temporarilyPauseAnticheat = temporarilyPauseAnticheat;

  function emitSecurityEvent(type, detail = {}) {
    document.dispatchEvent(new CustomEvent("exam:security", { detail:{ type, timestamp:new Date().toISOString(), ...detail } }));
  }

  function resetSecurityState() {
    window.__TAB_STRIKES = 0;
    window.__DEVTOOLS_STRIKES = 0;
    window.__OFFLINE_SINCE = null;
    window.__examSecurityTerminating = false;
    window.__examTerminationReason = null;

    state.lastFocusViolationAt = 0;
    state.offline15Shown = false;
    state.offline5Shown = false;
  }

  /* ==============================================================================================
     TERMINATION
  ============================================================================================== */

  function terminateExam(reason = "security_violation", message = "Exam terminated for violating examination instructions.") {
    if (window.__examFinished || window.__examSecurityTerminating) return;

    window.__examSecurityTerminating = true;
    window.__examTerminationReason = reason;
    window.__ANTICHEAT_READY = false;

    emitSecurityEvent("terminated", { reason, tabStrikes:window.__TAB_STRIKES });
    flash(message, "danger", "Examination Terminated", CONFIG.dangerDurationMs);

    console.error("[exam-realtime] EXAM TERMINATED:", { reason, tabStrikes:window.__TAB_STRIKES });

    setTimeout(() => {
      if (typeof window.submitExam === "function") window.submitExam(true);
      else console.error("[exam-realtime] submitExam() not found.");
    }, 750);
  }

  window.terminateExamForSecurity = terminateExam;

  /* ==============================================================================================
     TAB / WINDOW / MINIMIZE / FOCUS VIOLATIONS
  ============================================================================================== */

  function strike(reason = "left_exam_page") {
    if (!securityActive()) return;

    const now = Date.now();
    if (now - state.lastFocusViolationAt < CONFIG.focusDedupeMs) return;

    state.lastFocusViolationAt = now;
    window.__TAB_STRIKES++;

    emitSecurityEvent("focus_violation", { reason, strike:window.__TAB_STRIKES });
    console.warn(`[exam-realtime] Focus violation ${window.__TAB_STRIKES}: ${reason}`);

    if (window.__TAB_STRIKES === 1) {
      temporarilyPauseAnticheat();

      flash(
        "You switched tab, minimized the browser, opened another window or left the examination page. This is your first and only warning. Leaving the exam again will terminate your examination automatically.",
        "warning",
        "⚠ First Warning • 1 of 2",
        CONFIG.warningDurationMs
      );

      return;
    }

    terminateExam("repeated_focus_violation", "You left the examination page again after receiving your first warning. Your examination has now been terminated.");
  }

  document.addEventListener("visibilitychange", () => {
    if (securityActive() && document.hidden) strike("tab_switch_or_hidden_page");
  }, true);

  window.addEventListener("blur", () => {
    if (securityActive()) strike("browser_window_focus_lost");
  }, true);

  /* A second line of defence for browsers that inconsistently emit blur/visibilitychange. */
  function checkFocusIntegrity() {
    if (!securityActive()) return;
    if (document.hidden) { strike("focus_watchdog_hidden"); return; }
    if (typeof document.hasFocus === "function" && !document.hasFocus()) strike("focus_watchdog_window_lost");
  }

  /* ==============================================================================================
     KEYBOARD SECURITY
  ============================================================================================== */

  document.addEventListener("keydown", event => {
    if (!securityEngaged()) return;

    const key = String(event.key || "").toLowerCase();
    const ctrlOrMeta = event.ctrlKey || event.metaKey;

    if (key === "f12") {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      flash("Developer tools are disabled during the examination.", "warning", "Restricted Action", 4000);
      return false;
    }

    if (ctrlOrMeta) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      flash("Keyboard shortcuts are disabled while your examination is active.", "warning", "Restricted Shortcut", 3500);
      return false;
    }

    if (event.altKey && ["arrowleft","arrowright","home"].includes(key)) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      flash("Browser navigation shortcuts are disabled during the examination.", "warning", "Restricted Shortcut", 3500);
      return false;
    }

    if (key === "backspace" && !["INPUT","TEXTAREA"].includes(String(document.activeElement?.tagName || "").toUpperCase())) {
      event.preventDefault();
      event.stopPropagation();
      return false;
    }

    if (key === "printscreen") {
      event.preventDefault();
      flash("Screenshots are prohibited during the examination.", "warning", "Restricted Action", 4000);
      return false;
    }
  }, true);

  /* ==============================================================================================
     RIGHT CLICK / COPY / CUT / PASTE / DRAG / SELECTION
  ============================================================================================== */

  document.addEventListener("contextmenu", event => {
    if (!securityEngaged()) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    flash("Right-click is disabled while an examination is active.", "info", "Exam Protected", 3300);
    return false;
  }, true);

  ["copy","cut","paste"].forEach(eventName => {
    document.addEventListener(eventName, event => {
      if (!securityEngaged()) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      flash("Copying, cutting and pasting are disabled during the examination.", "warning", "Restricted Action", 3500);
      return false;
    }, true);
  });

  document.addEventListener("dragstart", event => {
    if (!securityEngaged()) return;
    event.preventDefault();
    event.stopPropagation();
    return false;
  }, true);

  document.addEventListener("selectstart", event => {
    if (!securityEngaged()) return;

    const tag = String(event.target?.tagName || "").toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA") return;

    event.preventDefault();
    return false;
  }, true);

  /* ==============================================================================================
     PRINT PROTECTION
  ============================================================================================== */

  window.addEventListener("beforeprint", () => {
    if (!securityEngaged()) return;
    emitSecurityEvent("print_attempt");
    flash("Printing examination content is disabled.", "warning", "Restricted Action", 4000);
  });

  /* ==============================================================================================
     DEVTOOLS
     Automatic heuristics intentionally disabled because browser dimensions caused false positives.
     F12 and Ctrl/Cmd shortcuts remain blocked above.
  ============================================================================================== */

  function devtoolsLooksOpen() {
    if (!CONFIG.devtoolsDetectionEnabled) return false;
    return false;
  }

  /* Retained as a compatibility function in case other EMIS scripts reference it. */
  window.emisDevtoolsLooksOpen = devtoolsLooksOpen;

  /* ==============================================================================================
     NETWORK SECURITY
  ============================================================================================== */

  function resetNetworkState() {
    window.__OFFLINE_SINCE = null;
    state.offline15Shown = false;
    state.offline5Shown = false;
  }

  function registerOffline() {
    if (!securityEngaged() || window.__OFFLINE_SINCE) return;

    window.__OFFLINE_SINCE = Date.now();
    state.offline15Shown = false;
    state.offline5Shown = false;

    emitSecurityEvent("offline");
    flash(
      "Internet connection lost. Reconnect within 30 seconds. Your examination remains open temporarily but will be terminated if the connection is not restored.",
      "warning",
      "⚠ Internet Connection Lost",
      7500
    );
  }

  function registerOnline() {
    const wasOffline = Boolean(window.__OFFLINE_SINCE);
    resetNetworkState();

    if (!securityEngaged() || !wasOffline) return;

    emitSecurityEvent("online");
    flash("Your internet connection has been restored successfully. You may continue your examination.", "success", "Connection Restored", CONFIG.successDurationMs);
  }

  window.addEventListener("offline", registerOffline);
  window.addEventListener("online", registerOnline);

  function checkNetworkGrace() {
    if (!securityEngaged()) return;

    /* navigator.onLine is checked continuously in case browser online/offline events are missed. */
    if (!navigator.onLine && !window.__OFFLINE_SINCE) registerOffline();
    if (navigator.onLine && window.__OFFLINE_SINCE) { registerOnline(); return; }
    if (!window.__OFFLINE_SINCE) return;

    const elapsed = Date.now() - window.__OFFLINE_SINCE;
    const remaining = Math.max(0, Math.ceil((CONFIG.offlineLimitMs - elapsed) / 1000));

    if (remaining <= 15 && remaining > 5 && !state.offline15Shown) {
      state.offline15Shown = true;
      flash(`${remaining} seconds remain to restore your internet connection.`, "warning", "Still Offline", 5000);
    }

    if (remaining <= 5 && remaining > 0 && !state.offline5Shown) {
      state.offline5Shown = true;
      flash("Reconnect immediately. Your examination is about to be terminated.", "danger", "Connection Critical", 5000);
    }

    if (elapsed >= CONFIG.offlineLimitMs) terminateExam("network_timeout", "Your examination remained offline for more than 30 seconds and has been terminated.");
  }

  /* ==============================================================================================
     PAGE EXIT PROTECTION
  ============================================================================================== */

  window.addEventListener("beforeunload", event => {
    if (!securityEngaged()) return;
    event.preventDefault();
    event.returnValue = "";
    return "";
  });

  /* ==============================================================================================
     SECURITY ACTIVATION
  ============================================================================================== */

  function activateSecurity(source = "runtime") {
    if (window.__examFinished || window.__examSecurityTerminating || window.__ANTI_CHEAT_ACTIVE || state.activating) return false;
    if (!examReadyForSecurity()) return false;

    state.activating = true;
    resetSecurityState();

    window.__ANTI_CHEAT_ACTIVE = true;
    window.__ANTICHEAT_READY = false;
    document.body.classList.add("emis-exam-secured");

    console.log(`[exam-realtime] Security initializing via ${source}...`);

    setTimeout(() => {
      state.activating = false;

      if (window.__examFinished || window.__examSecurityTerminating || !examInterfaceVisible() || !examDataReady()) {
        window.__ANTI_CHEAT_ACTIVE = false;
        window.__ANTICHEAT_READY = false;
        document.body.classList.remove("emis-exam-secured");
        return;
      }

      window.__ANTI_CHEAT_ACTIVE = true;
      window.__ANTICHEAT_READY = true;
      state.activatedAt = Date.now();

      if (!navigator.onLine) window.__OFFLINE_SINCE = Date.now();

      emitSecurityEvent("activated", { source });

      flash(
        "Security monitoring is active. Remain on this examination page until you submit your exam.",
        "info",
        "Exam Security Active",
        CONFIG.infoDurationMs
      );

      console.log("%c[exam-realtime] STRICT ANTICHEAT ACTIVATED ✓", "color:#16a34a;font-weight:900;font-size:13px");
      console.log("[exam-realtime] Security state:", {
        active:window.__ANTI_CHEAT_ACTIVE,
        ready:window.__ANTICHEAT_READY,
        tabStrikes:window.__TAB_STRIKES,
        online:navigator.onLine,
        source
      });
    }, CONFIG.startupGraceMs);

    return true;
  }

  window.activateExamSecurity = activateSecurity;

  /*
   * IMPORTANT:
   * This is what removes the localhost-vs-deployed-server timing problem.
   * It keeps checking until the exam interface AND exam data are genuinely ready.
   */
  function ensureSecurityActive(source = "security-watchdog") {
    if (window.__examFinished || window.__examSecurityTerminating) return;

    if (securityEngaged()) {
      document.body.classList.add("emis-exam-secured");
      return;
    }

    if (examReadyForSecurity()) activateSecurity(source);
  }

  /* ==============================================================================================
     STARTEXAM WRAPPER
  ============================================================================================== */

  function patchStartExam() {
    if (window.__EMIS_REALTIME_START_PATCHED__) return true;

    const originalStart = window.startExam;
    if (typeof originalStart !== "function") return false;

    window.startExam = async function (...args) {
      state.startRequested = true;

      let result;
      try {
        result = await originalStart.apply(this, args);
      } finally {
        ensureSecurityActive("startExam-wrapper");

        /* Continue checking because production data may arrive after startExam resolves. */
        setTimeout(() => ensureSecurityActive("startExam-700ms"), 700);
        setTimeout(() => ensureSecurityActive("startExam-1500ms"), 1500);
        setTimeout(() => ensureSecurityActive("startExam-3000ms"), 3000);
      }

      return result;
    };

    window.__EMIS_REALTIME_START_PATCHED__ = true;
    console.log("[exam-realtime] startExam security wrapper attached ✓");
    return true;
  }

  /* ==============================================================================================
     START BUTTON FALLBACK
  ============================================================================================== */

  function installStartButtonFallback() {
    const startBtn = document.getElementById("startExamBtn");
    if (!startBtn || startBtn.__emisRealtimeFallback) return;

    startBtn.__emisRealtimeFallback = true;

    startBtn.addEventListener("click", () => {
      state.startRequested = true;

      setTimeout(() => ensureSecurityActive("start-button-500ms"), 500);
      setTimeout(() => ensureSecurityActive("start-button-1200ms"), 1200);
      setTimeout(() => ensureSecurityActive("start-button-2500ms"), 2500);
      setTimeout(() => ensureSecurityActive("start-button-5000ms"), 5000);
    }, true);
  }

  /* ==============================================================================================
     WATCHDOGS
  ============================================================================================== */

  function startWatchers() {
    if (!state.watchdogTimer) state.watchdogTimer = setInterval(() => ensureSecurityActive("persistent-watchdog"), CONFIG.watchdogMs);
    if (!state.focusTimer) state.focusTimer = setInterval(checkFocusIntegrity, CONFIG.focusCheckMs);
    if (!state.networkTimer) state.networkTimer = setInterval(checkNetworkGrace, CONFIG.networkCheckMs);
  }

  /* ==============================================================================================
     DIAGNOSTIC STATUS
  ============================================================================================== */

  window.getExamSecurityStatus = () => ({
    version:"6.0",
    active:window.__ANTI_CHEAT_ACTIVE,
    ready:window.__ANTICHEAT_READY,
    examFinished:Boolean(window.__examFinished),
    terminating:window.__examSecurityTerminating,
    terminationReason:window.__examTerminationReason,
    tabStrikes:window.__TAB_STRIKES,
    examInterfaceVisible:examInterfaceVisible(),
    examDataReady:examDataReady(),
    questionCount:Array.isArray(window.realQuestionIndices) ? window.realQuestionIndices.length : 0,
    browserFocused:typeof document.hasFocus === "function" ? document.hasFocus() : null,
    pageHidden:document.hidden,
    online:navigator.onLine,
    offlineSince:window.__OFFLINE_SINCE,
    activatedAt:state.activatedAt || null,
    devtoolsAutomaticDetection:CONFIG.devtoolsDetectionEnabled
  });

  /* ==============================================================================================
     BOOT
  ============================================================================================== */

  function bootRealtimeSecurity() {
    injectSecurityStyles();
    installStartButtonFallback();
    startWatchers();

    let attempts = 0;

    const attachCore = () => {
      attempts++;

      patchStartExam();
      installStartButtonFallback();
      ensureSecurityActive("boot");

      if (typeof window.startExam !== "function" && attempts < 100) {
        setTimeout(attachCore, 100);
        return;
      }

      /*
       * Keep several delayed checks because production hosting, mobile networks and browser cache
       * can make exam-core/data initialization much slower than localhost.
       */
      setTimeout(() => ensureSecurityActive("boot-1s"), 1000);
      setTimeout(() => ensureSecurityActive("boot-2s"), 2000);
      setTimeout(() => ensureSecurityActive("boot-4s"), 4000);
      setTimeout(() => ensureSecurityActive("boot-8s"), 8000);
    };

    attachCore();

    console.log("%c[exam-realtime] SECURITY WATCHDOGS READY ✓", "color:#2879a5;font-weight:800");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bootRealtimeSecurity, { once:true });
  else bootRealtimeSecurity();

})();
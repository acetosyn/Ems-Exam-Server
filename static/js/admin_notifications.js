/* static/js/admin_notifications.js */
/* ============================================================
   EMIS ADMIN REAL-TIME NOTIFICATION ENGINE v2.1

   CORE:
   - SSE primary + polling reconciliation
   - Exact backend sequence / FIFO order
   - Same-student lifecycle supersession only
   - Different students NEVER jump the FIFO queue
   - 15 reminder appearances per event
   - Hover pauses notification
   - Hidden-tab unread counter
   - JSS + SS term-aware
   - SS General / Legacy aware
   - Completed / Timeout / Terminated aware
   - Admin result table refresh on result activity
   - 20-minute staff-session backend compatible
============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  console.log("%c[admin_notifications] EMIS REAL-TIME ENGINE v2.1 STARTED ✓", "color:#0f766e;font-weight:900;");

  const $ = (id) => document.getElementById(id);

  /* ============================================================
     DOM
  ============================================================ */

  const host = $("liveNotificationHost"), card = $("liveNotificationCard"), icon = $("liveNotificationIcon"),
        typeLabel = $("liveNotificationType"), title = $("liveNotificationTitle"), message = $("liveNotificationMessage"),
        timeLabel = $("liveNotificationTime"), meta = $("liveNotificationMeta"), closeBtn = $("liveNotificationClose");

  if (!host || !card) {
    console.warn("[admin_notifications] Live notification HTML not found.");
    return;
  }

  /* ============================================================
     CONFIG
  ============================================================ */

  const CONFIG = {
    pollInterval: 7000,
    flashInterval: 7000,
    displayDuration: 4800,
    exitDuration: 500,
    betweenEventsDelay: 700,

    repeatCount: 15,
    maxQueue: 500,
    maxKnownKeys: 3000,
    bootstrapMaxAge: 45000,

    sseReconnectMin: 2000,
    sseReconnectMax: 30000,

    resultRefreshCooldown: 3000
  };

  /* ============================================================
     STATE
  ============================================================ */

  let pendingQueue = [], knownKeys = new Set(), knownKeyOrder = [];
  let currentNotification = null, currentNotificationKey = "", currentRepeatCount = 0, currentAppearanceStartedAt = 0;
  let lastSequence = 0, unreadWhileHidden = 0, reconnectAttempts = 0, droppedQueueItems = 0;

  let eventSource = null, pollTimer = null, hideTimer = null, repeatTimer = null, nextTimer = null, reconnectTimer = null;

  let isShowing = false, isPolling = false, isHovered = false, pendingFinishAfterHover = false,
      sseConnected = false, refreshCooldown = false, sessionExpired = false;

  const originalDocumentTitle = document.title;

  /* ============================================================
     HELPERS
  ============================================================ */

  function safeText(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  function text(value) { return String(value ?? "").trim(); }
  function upper(value) { return text(value).toUpperCase(); }

  function normalizeTerm(value) {
    const raw = upper(value).replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ");

    if (["FIRST", "FIRST TERM", "TERM 1", "TERM ONE", "1", "1ST", "1ST TERM"].includes(raw)) return "FIRST";
    if (["SECOND", "SECOND TERM", "TERM 2", "TERM TWO", "2", "2ND", "2ND TERM"].includes(raw)) return "SECOND";
    if (["THIRD", "THIRD TERM", "TERM 3", "TERM THREE", "3", "3RD", "3RD TERM"].includes(raw)) return "THIRD";

    return "";
  }

  function termLabel(value) {
    return { FIRST: "1st Term", SECOND: "2nd Term", THIRD: "3rd Term" }[normalizeTerm(value)] || "";
  }

  function formatSubject(value) {
    return text(value).replaceAll("_", " ").replace(/\s+/g, " ").toUpperCase();
  }

  function getPayload(notif) {
    return notif?.payload && typeof notif.payload === "object" ? notif.payload : {};
  }

  function getSequence(notif) {
    const sequence = Number(notif?.sequence || 0);
    return Number.isFinite(sequence) ? sequence : 0;
  }

  function getAdmission(payload) {
    return payload.admission_number || payload.admission_no || payload["Admission No"] || payload.admission || payload.student_id || "";
  }

  function getStudentName(payload) {
    return payload.student_name || payload.full_name || payload["Student Name"] || payload.student || payload.name || "Student";
  }

  function getSubject(payload) {
    return payload.subject || payload.subject_folder || payload.Subject || payload["Subject Folder"] || "";
  }

  function getYear(payload) {
    return payload.year || payload.Year || payload.exam_year || "";
  }

  function getClass(payload) {
    return payload.class_arm || payload["Class Arm"] || payload.class_name || payload.class_level ||
           payload.class_category || payload["Class Category"] || payload.class || payload.Class || "";
  }

  function getClassLevel(payload) {
    const raw = upper(payload.class_level || payload.class_category || payload["Class Category"] || payload.class || "");
    const match = raw.match(/^(JSS[123]|SS[123])/);
    return match ? match[1] : "";
  }

  function isSsPayload(payload) {
    return getClassLevel(payload).startsWith("SS");
  }

  function getTerm(payload) {
    return normalizeTerm(payload.term || payload.Term || payload.term_name || payload["Term Label"] || "");
  }

  function getDisplayTerm(payload) {
    const term = getTerm(payload);
    if (term) return termLabel(term);

    return isSsPayload(payload) ? "General / Legacy" : "";
  }

  function getScore(payload) {
    const value = payload.score ?? payload["Score (%)"] ?? payload.score_percentage ?? payload.final_score ?? "";
    return text(value).replace("%", "");
  }

  function getResultStatus(payload) {
    return upper(payload.result_status || payload.final_status || payload["Final Status"] || payload.Status || "");
  }

  function getSubmissionStatus(payload) {
    return upper(payload.submission_status || payload.exam_status || payload.status || "");
  }

  function getTerminationReason(payload) {
    return text(payload.termination_reason || payload.security_reason || payload.violation_reason || "");
  }

  function friendlyTerminationReason(reason) {
    const value = text(reason).toLowerCase();

    if (value === "repeated_focus_violation") return "Repeated tab switching or leaving the exam page";
    if (value === "repeated_devtools_violation") return "Repeated developer-tools violation";
    if (value === "network_timeout") return "Internet connection remained unavailable for too long";

    return text(reason).replaceAll("_", " ");
  }

  /* ============================================================
     EVENT TYPE
  ============================================================ */

  function getEventType(notif) {
    const payload = getPayload(notif);
    const rawType = text(notif?.type).toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
    const submissionStatus = getSubmissionStatus(payload).toLowerCase();

    if (["login", "student_login"].includes(rawType)) return "login";
    if (["exam_start", "exam_started", "start_exam"].includes(rawType)) return "exam_start";

    if (["terminated", "exam_terminated", "security_terminated"].includes(rawType)) return "terminated";
    if (["timeout", "exam_timeout", "exam_timed_out"].includes(rawType)) return "timeout";

    if (["exam_end", "exam_submit", "exam_submitted", "exam_submission", "submit_exam"].includes(rawType)) {
      if (["terminated", "security_violation", "disqualified"].includes(submissionStatus)) return "terminated";
      if (["timeout", "timed_out", "timed out"].includes(submissionStatus)) return "timeout";
      return "exam_end";
    }

    if (["result_pending", "pending_result", "result_processing"].includes(rawType)) return "result_pending";
    if (["result_available", "result_ready", "result_generated", "result_published"].includes(rawType)) return "result_available";

    return rawType || "notification";
  }

  /* ============================================================
     IDENTIFIERS / DEDUPLICATION
  ============================================================ */

  function getNotificationKey(notif) {
    if (notif?.id !== undefined && notif?.id !== null && text(notif.id)) return String(notif.id);

    const payload = getPayload(notif);

    return [
      getEventType(notif),
      upper(getAdmission(payload)) || "UNKNOWN",
      upper(getSubject(payload)),
      String(getYear(payload) || ""),
      getTerm(payload),
      getSequence(notif),
      notif?.timestamp || ""
    ].join(":");
  }

  function getStudentKey(notif) {
    const payload = getPayload(notif);
    return upper(getAdmission(payload)) || upper(getStudentName(payload)) || "UNKNOWN-STUDENT";
  }

  function rememberKey(key) {
    if (!key || knownKeys.has(key)) return false;

    knownKeys.add(key);
    knownKeyOrder.push(key);

    while (knownKeyOrder.length > CONFIG.maxKnownKeys) {
      const oldKey = knownKeyOrder.shift();
      if (oldKey) knownKeys.delete(oldKey);
    }

    return true;
  }

  /* ============================================================
     SAME-STUDENT LIFECYCLE SUPERSESSION
  ============================================================ */

  function canSupersede(oldNotif, newNotif) {
    if (!oldNotif || !newNotif || getStudentKey(oldNotif) !== getStudentKey(newNotif)) return false;

    const oldType = getEventType(oldNotif), newType = getEventType(newNotif);

    if (newType === "exam_start" && oldType === "login") return true;
    if (newType === "result_pending" && ["login", "exam_start"].includes(oldType)) return true;
    if (["exam_end", "timeout", "terminated"].includes(newType) && ["login", "exam_start", "result_pending"].includes(oldType)) return true;

    /* Exam Submitted / Timeout / Terminated must be displayed before Result Available. */
    if (newType === "result_available" && ["exam_end", "timeout", "terminated"].includes(oldType)) return false;

    return false;
  }

  /* ============================================================
     TIME
  ============================================================ */

  function eventNumericTime(notif) {
    const created = Number(notif?.created_at || 0);

    if (Number.isFinite(created) && created > 0) return created > 100000000000 ? created : created * 1000;

    const parsed = Date.parse(notif?.timestamp || "");
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function relativeTime(notif) {
    const createdMs = eventNumericTime(notif);

    if (!createdMs) return notif?.timestamp || "";

    const seconds = Math.max(0, Math.floor((Date.now() - createdMs) / 1000));

    if (seconds < 10) return "Just now";
    if (seconds < 60) return `${seconds}s ago`;

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;

    return `${Math.floor(hours / 24)}d ago`;
  }

  /* ============================================================
     CONNECTION / QUEUE / TAB TITLE
  ============================================================ */

  function setConnectionState(state) {
    host.dataset.connection = state;
    card.dataset.connection = state;

    window.dispatchEvent(new CustomEvent("emis:notification-connection", {
      detail: { state, connected: state === "connected", reconnectAttempts, sessionExpired }
    }));
  }

  function updateQueueState() {
    const total = pendingQueue.length + (currentNotification ? 1 : 0);

    host.dataset.queueCount = String(total);
    host.dataset.queuePressure = total >= 50 ? "high" : total >= 15 ? "medium" : "normal";

    window.dispatchEvent(new CustomEvent("emis:notification-queue", {
      detail: { pending: pendingQueue.length, current: Boolean(currentNotification), total, dropped: droppedQueueItems }
    }));
  }

  function updateDocumentTitle() {
    document.title = unreadWhileHidden > 0 ? `(${unreadWhileHidden}) ${originalDocumentTitle}` : originalDocumentTitle;
  }

  function registerHiddenActivity() {
    if (!document.hidden) return;

    unreadWhileHidden++;
    updateDocumentTitle();
  }

  function clearHiddenActivity() {
    unreadWhileHidden = 0;
    updateDocumentTitle();
  }

  /* ============================================================
     PRESENTATION
  ============================================================ */

  function getPresentation(notif) {
    const payload = getPayload(notif), type = getEventType(notif);
    const student = getStudentName(payload), subject = formatSubject(getSubject(payload));
    const score = getScore(payload), resultStatus = getResultStatus(payload);
    const terminationReason = friendlyTerminationReason(getTerminationReason(payload));

    if (type === "login") {
      return { type, visualType: "login", label: "Student Login", icon: "fa-user-check", title: `${student} logged in`, message: notif.message || "Student successfully accessed the CBT examination portal." };
    }

    if (type === "exam_start") {
      return { type, visualType: "exam_start", label: "Exam Started", icon: "fa-file-pen", title: `${student} started ${subject || "an examination"}`, message: notif.message || "The student's examination session is now in progress." };
    }

    if (type === "result_pending") {
      return { type, visualType: "result_pending", label: "Processing Result", icon: "fa-hourglass-half", title: `${student}'s result is processing`, message: notif.message || "The submitted examination result is currently being processed." };
    }

    if (type === "exam_end") {
      return { type, visualType: "exam_end", label: "Exam Submitted", icon: "fa-flag-checkered", title: `${student} submitted ${subject || "an examination"}`, message: notif.message || "The examination was completed and submitted successfully." };
    }

    if (type === "timeout") {
      return { type, visualType: "timeout", label: "Time Expired", icon: "fa-clock", title: `${student}'s examination timed out`, message: notif.message || "The examination was submitted automatically when the allocated time expired." };
    }

    if (type === "terminated") {
      const reasonText = terminationReason ? ` Reason: ${terminationReason}.` : "";

      /* Reuse timeout/danger visual styling already present in admin_results.css. */
      return { type, visualType: "timeout", label: "Exam Terminated", icon: "fa-shield-halved", title: `${student}'s examination was terminated`, message: notif.message || `The examination ended because of a security violation.${reasonText}` };
    }

    if (type === "result_available") {
      const scoreText = score ? ` Score: ${score}%.` : "";
      const statusText = resultStatus ? ` Result: ${resultStatus}.` : "";

      return { type, visualType: "result_available", label: "Result Available", icon: "fa-circle-check", title: `${student}'s result is available`, message: notif.message || `A new examination result is now available.${scoreText}${statusText}` };
    }

    return { type: "notification", visualType: "notification", label: "Live Activity", icon: "fa-bell", title: student, message: notif.message || payload.message || "New examination activity received." };
  }

  /* ============================================================
     META CHIPS
  ============================================================ */

  function buildMeta(notif) {
    const payload = getPayload(notif), values = [];
    const admission = getAdmission(payload), cls = getClass(payload), displayTerm = getDisplayTerm(payload);
    const subject = getSubject(payload), year = getYear(payload), type = getEventType(notif);

    if (admission) values.push(admission);
    if (cls) values.push(upper(cls));
    if (displayTerm) values.push(displayTerm);
    if (subject) values.push(formatSubject(subject));
    if (year) values.push(String(year));

    if (type === "terminated" && getTerminationReason(payload)) values.push("SECURITY VIOLATION");
    if (type === "timeout") values.push("TIMEOUT");

    return values.slice(0, 6);
  }

  /* ============================================================
     RESULTS REFRESH
  ============================================================ */

  function triggerResultsRefresh(notif) {
    const type = getEventType(notif);

    if (!["exam_end", "timeout", "terminated", "result_available"].includes(type) || refreshCooldown) return;

    refreshCooldown = true;
    setTimeout(() => { refreshCooldown = false; }, CONFIG.resultRefreshCooldown);

    if (typeof window.refreshAdminResults === "function") {
      try { return window.refreshAdminResults({ silent: true }); }
      catch (error) { console.warn("[admin_notifications] refreshAdminResults failed:", error); }
    }

    if (typeof window.loadAllResults === "function") {
      try { return window.loadAllResults({ silent: true }); }
      catch (error) { console.warn("[admin_notifications] loadAllResults failed:", error); }
    }

    window.dispatchEvent(new CustomEvent("emis:result-submitted", { detail: notif }));
  }

  /* ============================================================
     FIFO QUEUE
  ============================================================ */

  function sortQueue() {
    pendingQueue.sort((a, b) => {
      const sequenceA = getSequence(a), sequenceB = getSequence(b);

      if (sequenceA && sequenceB && sequenceA !== sequenceB) return sequenceA - sequenceB;

      return eventNumericTime(a) - eventNumericTime(b);
    });
  }

  function removeSupersededPendingEvents(notif) {
    pendingQueue = pendingQueue.filter((queued) => !canSupersede(queued, notif));
  }

  function addNotification(notif, fromLive = false, bootstrap = false) {
    if (!notif || !notif.type || sessionExpired) return false;

    const key = getNotificationKey(notif);

    if (!rememberKey(key)) return false;

    const sequence = getSequence(notif);
    if (sequence > lastSequence) lastSequence = sequence;

    if (bootstrap) {
      const created = eventNumericTime(notif), age = created ? Date.now() - created : Infinity;

      /* Remember old bootstrap notifications, but do not replay them. */
      if (!Number.isFinite(age) || age > CONFIG.bootstrapMaxAge) return true;
    }

    registerHiddenActivity();
    removeSupersededPendingEvents(notif);

    /*
     * IMPORTANT:
     * Only a newer lifecycle stage for the SAME STUDENT may
     * interrupt the current card.
     *
     * Another student's notification must wait in FIFO order.
     */
    const shouldPreemptCurrent = Boolean(fromLive && currentNotification && canSupersede(currentNotification, notif));

    if (shouldPreemptCurrent) {
      pendingQueue.unshift(notif);

      if (fromLive) triggerResultsRefresh(notif);

      updateQueueState();
      preemptCurrentNotification();

      return true;
    }

    pendingQueue.push(notif);

    if (pendingQueue.length > CONFIG.maxQueue) {
      const overflow = pendingQueue.length - CONFIG.maxQueue;

      pendingQueue.splice(0, overflow);
      droppedQueueItems += overflow;

      console.warn(`[admin_notifications] Queue overflow: ${overflow} old event(s) dropped.`);
    }

    sortQueue();

    if (fromLive) triggerResultsRefresh(notif);

    updateQueueState();

    if (!isShowing && !currentNotification) showNextNotification();

    return true;
  }

  /* ============================================================
     SHOW NOTIFICATION
  ============================================================ */

  function showNotification(notif, isRepeat = false) {
    if (!notif || sessionExpired) return;

    clearTimeout(hideTimer);
    clearTimeout(repeatTimer);
    clearTimeout(nextTimer);

    const presentation = getPresentation(notif), chips = buildMeta(notif);

    currentNotification = notif;
    currentNotificationKey = getNotificationKey(notif);

    if (!isRepeat) currentRepeatCount = 1;

    currentAppearanceStartedAt = Date.now();
    pendingFinishAfterHover = false;
    isShowing = true;

    card.dataset.type = presentation.visualType || presentation.type;
    card.dataset.eventType = presentation.type;
    card.dataset.repeat = String(currentRepeatCount);
    card.dataset.repeatTotal = String(CONFIG.repeatCount);

    if (icon) icon.innerHTML = `<i class="fa-solid ${safeText(presentation.icon)}"></i>`;
    if (typeLabel) typeLabel.textContent = presentation.label;
    if (title) title.textContent = presentation.title;
    if (message) message.textContent = presentation.message;
    if (timeLabel) timeLabel.textContent = relativeTime(notif);
    if (meta) meta.innerHTML = chips.map((value) => `<span>${safeText(value)}</span>`).join("");

    card.classList.remove("is-visible", "is-leaving");
    void card.offsetWidth;
    card.classList.add("is-visible");

    updateQueueState();

    console.log(`[admin_notifications] Showing ${currentRepeatCount}/${CONFIG.repeatCount}:`, presentation.type, currentNotificationKey);

    hideTimer = setTimeout(() => {
      if (isHovered) {
        pendingFinishAfterHover = true;
        return;
      }

      finishAppearance();

    }, CONFIG.displayDuration);
  }

  /* ============================================================
     FINISH APPEARANCE
  ============================================================ */

  function finishAppearance() {
    clearTimeout(hideTimer);

    if (!currentNotification || !isShowing) return;

    if (isHovered) {
      pendingFinishAfterHover = true;
      return;
    }

    pendingFinishAfterHover = false;

    card.classList.remove("is-visible");
    card.classList.add("is-leaving");

    setTimeout(() => {
      card.classList.remove("is-leaving");
      isShowing = false;

      if (currentRepeatCount < CONFIG.repeatCount) {
        currentRepeatCount++;

        const elapsed = Date.now() - currentAppearanceStartedAt;
        const wait = Math.max(250, CONFIG.flashInterval - elapsed);

        repeatTimer = setTimeout(() => {
          if (currentNotification && !sessionExpired) showNotification(currentNotification, true);
        }, wait);

        return;
      }

      currentNotification = null;
      currentNotificationKey = "";
      currentRepeatCount = 0;
      currentAppearanceStartedAt = 0;

      updateQueueState();

      nextTimer = setTimeout(showNextNotification, CONFIG.betweenEventsDelay);

    }, CONFIG.exitDuration);
  }

  /* ============================================================
     NEXT EVENT
  ============================================================ */

  function showNextNotification() {
    if (sessionExpired || isShowing || currentNotification) return;

    sortQueue();

    const next = pendingQueue.shift();

    if (!next) {
      card.classList.remove("is-visible", "is-leaving");

      currentNotification = null;
      currentNotificationKey = "";
      currentRepeatCount = 0;

      updateQueueState();
      return;
    }

    updateQueueState();
    showNotification(next, false);
  }

  /* ============================================================
     SAME-STUDENT PREEMPTION
  ============================================================ */

  function preemptCurrentNotification() {
    clearTimeout(hideTimer);
    clearTimeout(repeatTimer);
    clearTimeout(nextTimer);

    if (!currentNotification) {
      isShowing = false;
      showNextNotification();
      return;
    }

    card.classList.remove("is-visible");
    card.classList.add("is-leaving");

    setTimeout(() => {
      card.classList.remove("is-leaving");

      currentNotification = null;
      currentNotificationKey = "";
      currentRepeatCount = 0;
      currentAppearanceStartedAt = 0;
      isShowing = false;

      updateQueueState();
      showNextNotification();

    }, CONFIG.exitDuration);
  }

  /* ============================================================
     HOVER PAUSE
  ============================================================ */

  card.addEventListener("mouseenter", () => {
    isHovered = true;
    card.dataset.paused = "true";
  });

  card.addEventListener("mouseleave", () => {
    isHovered = false;
    card.dataset.paused = "false";

    if (pendingFinishAfterHover) finishAppearance();
  });

  /* ============================================================
     STAFF SESSION EXPIRED
  ============================================================ */

  function handleSessionExpired() {
    if (sessionExpired) return;

    sessionExpired = true;
    sseConnected = false;

    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }

    clearTimeout(hideTimer);
    clearTimeout(repeatTimer);
    clearTimeout(nextTimer);
    clearTimeout(reconnectTimer);

    closeEventStream();

    pendingQueue = [];
    currentNotification = null;
    currentNotificationKey = "";
    currentRepeatCount = 0;
    isShowing = true;

    setConnectionState("expired");
    updateQueueState();

    card.dataset.type = "timeout";
    card.dataset.eventType = "session_expired";
    card.dataset.repeat = "1";
    card.dataset.repeatTotal = "1";

    if (icon) icon.innerHTML = `<i class="fa-solid fa-lock"></i>`;
    if (typeLabel) typeLabel.textContent = "Session Ended";
    if (title) title.textContent = "Admin session expired";
    if (message) message.textContent = "Your staff session is no longer active. Please sign in again to continue receiving live examination results.";
    if (timeLabel) timeLabel.textContent = "Login required";
    if (meta) meta.innerHTML = `<span>SESSION EXPIRED</span>`;

    card.classList.remove("is-leaving");
    void card.offsetWidth;
    card.classList.add("is-visible");

    console.warn("[admin_notifications] Staff session expired. Notification engine stopped.");

    window.dispatchEvent(new CustomEvent("emis:staff-session-expired"));
  }

  /* ============================================================
     FETCH
  ============================================================ */

  async function fetchNotifications(initial = false) {
    if (isPolling || sessionExpired) return;

    isPolling = true;

    try {
      const url = initial || !lastSequence
        ? "/api/notifications/fetch"
        : `/api/notifications/fetch?since_sequence=${encodeURIComponent(lastSequence)}`;

      const response = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" }
      });

      if (response.status === 401 || response.status === 403) {
        handleSessionExpired();
        return;
      }

      if (!response.ok) {
        console.warn("[admin_notifications] Notification fetch failed:", response.status);
        return;
      }

      const data = await response.json();

      if (data.error) {
        console.warn("[admin_notifications] Notification server error:", data.error);
        return;
      }

      const notifications = Array.isArray(data.notifications) ? data.notifications : [];

      notifications.sort((a, b) => {
        const sequenceDifference = getSequence(a) - getSequence(b);
        return sequenceDifference || eventNumericTime(a) - eventNumericTime(b);
      });

      notifications.forEach((notif) => addNotification(notif, !initial, initial));

      const serverLatest = Number(data.latest_sequence || 0);
      if (serverLatest > lastSequence) lastSequence = serverLatest;

      updateQueueState();

    } catch (error) {
      if (!sessionExpired) console.error("[admin_notifications] Fetch failed:", error);

    } finally {
      isPolling = false;
    }
  }

  /* ============================================================
     SSE
  ============================================================ */

  function closeEventStream() {
    if (!eventSource) return;

    eventSource.close();
    eventSource = null;
    sseConnected = false;
  }

  function scheduleSseReconnect() {
    if (sessionExpired || !navigator.onLine) return;

    clearTimeout(reconnectTimer);
    reconnectAttempts++;

    const delay = Math.min(CONFIG.sseReconnectMax, CONFIG.sseReconnectMin * Math.pow(2, Math.min(reconnectAttempts - 1, 4)));

    setConnectionState("reconnecting");

    reconnectTimer = setTimeout(() => {
      if (!document.hidden && !sessionExpired) startEventStream();
    }, delay);

    console.warn(`[admin_notifications] SSE reconnect scheduled in ${delay}ms.`);
  }

  function startEventStream() {
    if (!window.EventSource || eventSource || sessionExpired || !navigator.onLine) return;

    clearTimeout(reconnectTimer);
    setConnectionState("connecting");

    try {
      eventSource = new EventSource(`/api/notifications/stream?since_sequence=${encodeURIComponent(lastSequence)}`);

      eventSource.addEventListener("connected", () => {
        sseConnected = true;
        reconnectAttempts = 0;
        setConnectionState("connected");

        console.log("[admin_notifications] SSE connected.");
      });

      eventSource.addEventListener("notification", (event) => {
        try {
          const notif = JSON.parse(event.data);
          addNotification(notif, true, false);

        } catch (error) {
          console.error("[admin_notifications] Invalid SSE payload:", error);
        }
      });

      eventSource.onopen = () => {
        sseConnected = true;
        reconnectAttempts = 0;
        setConnectionState("connected");
      };

      eventSource.onerror = () => {
        if (sessionExpired) return;

        sseConnected = false;
        closeEventStream();

        /*
         * Poll once before reconnecting. If staff authentication
         * has genuinely expired, fetchNotifications() will detect
         * the 401/403 and stop the reconnect loop cleanly.
         */
        fetchNotifications(false).finally(() => {
          if (!sessionExpired) scheduleSseReconnect();
        });
      };

    } catch (error) {
      console.error("[admin_notifications] Could not start SSE:", error);

      closeEventStream();
      scheduleSseReconnect();
    }
  }

  /* ============================================================
     POLLING RECONCILIATION
  ============================================================ */

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(() => {
      /*
       * Visible Admin Results page keeps the staff session active.
       * Hidden tabs do not continually extend inactivity.
       */
      if (!document.hidden && !sessionExpired) fetchNotifications(false);
    }, CONFIG.pollInterval);
  }

  /* ============================================================
     MANUAL CLOSE
  ============================================================ */

  closeBtn?.addEventListener("click", () => {
    if (sessionExpired) {
      window.location.href = "/admin_login";
      return;
    }

    clearTimeout(hideTimer);
    clearTimeout(repeatTimer);
    clearTimeout(nextTimer);

    if (!currentNotification) return;

    card.classList.remove("is-visible");
    card.classList.add("is-leaving");

    setTimeout(() => {
      card.classList.remove("is-leaving");

      currentNotification = null;
      currentNotificationKey = "";
      currentRepeatCount = 0;
      currentAppearanceStartedAt = 0;

      isShowing = false;
      isHovered = false;
      pendingFinishAfterHover = false;

      updateQueueState();
      showNextNotification();

    }, CONFIG.exitDuration);
  });

  /* ============================================================
     TAB VISIBILITY
  ============================================================ */

  document.addEventListener("visibilitychange", () => {
    if (document.hidden || sessionExpired) return;

    clearHiddenActivity();

    /*
     * Returning within the 20-minute staff-session window refreshes
     * the session and reconciles anything missed while hidden.
     */
    fetchNotifications(false);

    if (!eventSource) startEventStream();
    if (!isShowing && !currentNotification && pendingQueue.length) showNextNotification();
  });

  /* ============================================================
     ONLINE / OFFLINE
  ============================================================ */

  window.addEventListener("online", () => {
    if (sessionExpired) return;

    setConnectionState("connecting");

    fetchNotifications(false);
    if (!eventSource) startEventStream();
  });

  window.addEventListener("offline", () => {
    if (sessionExpired) return;

    setConnectionState("offline");
    closeEventStream();
  });

  /* ============================================================
     RESULT SUBMISSION EVENT
  ============================================================ */

  window.addEventListener("emis:result-submitted", () => {
    if (!sessionExpired) fetchNotifications(false);
  });

  /* ============================================================
     CLEANUP
  ============================================================ */

  window.addEventListener("beforeunload", () => {
    if (pollTimer) clearInterval(pollTimer);

    clearTimeout(hideTimer);
    clearTimeout(repeatTimer);
    clearTimeout(nextTimer);
    clearTimeout(reconnectTimer);

    closeEventStream();

    document.title = originalDocumentTitle;
  });

  /* ============================================================
     GLOBAL DIAGNOSTIC API
  ============================================================ */

  window.EmisAdminNotifications = {
    refresh: () => fetchNotifications(false),
    push: (notification) => addNotification(notification, true, false),
    showNext: showNextNotification,

    queueLength: () => pendingQueue.length,

    state: () => ({
      pending: pendingQueue.length,
      current: currentNotification,
      currentType: currentNotification ? getEventType(currentNotification) : null,

      repeat: currentRepeatCount,
      repeatTotal: CONFIG.repeatCount,

      lastSequence,
      sseConnected,
      reconnectAttempts,

      unreadWhileHidden,
      droppedQueueItems,
      knownNotifications: knownKeys.size,

      sessionExpired,
      connection: host.dataset.connection || ""
    }),

    reconnect: () => {
      if (sessionExpired) return false;

      closeEventStream();
      reconnectAttempts = 0;

      fetchNotifications(false);
      startEventStream();

      return true;
    },

    clear: () => {
      pendingQueue = [];
      knownKeys.clear();
      knownKeyOrder = [];

      currentNotification = null;
      currentNotificationKey = "";
      currentRepeatCount = 0;
      currentAppearanceStartedAt = 0;

      clearTimeout(hideTimer);
      clearTimeout(repeatTimer);
      clearTimeout(nextTimer);

      isShowing = false;
      isHovered = false;
      pendingFinishAfterHover = false;

      card.classList.remove("is-visible", "is-leaving");

      clearHiddenActivity();
      updateQueueState();
    }
  };

  /* ============================================================
     INITIALIZE
  ============================================================ */

  async function initNotifications() {
    setConnectionState(navigator.onLine ? "connecting" : "offline");
    updateQueueState();

    await fetchNotifications(true);

    if (sessionExpired) return;

    if (navigator.onLine) startEventStream();

    startPolling();

    if (!isShowing && !currentNotification && pendingQueue.length) showNextNotification();

    console.log(`[admin_notifications] READY ✓ Queue=${pendingQueue.length} Repeat=${CONFIG.repeatCount}x TermMode=JSS+SS.`);
  }

  initNotifications();
});
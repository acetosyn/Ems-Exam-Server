/* static/js/admin_notifications.js */
/* ============================================================
   EMIS ADMIN PREMIUM REAL-TIME NOTIFICATION ENGINE

   CORE RULES
   ------------------------------------------------------------
   - One notification card at a time
   - Exact backend sequence / FIFO ordering
   - Different students = first come, first served
   - Same student = controlled lifecycle supersession
   - Login -> Exam Start -> Processing -> Submit -> Result
   - Every event appears 15 times
   - Approx. 7 seconds between appearance START times
   - SSE primary transport
   - Polling reconciliation fallback

   IMPORTANT SUBMISSION RULE
   ------------------------------------------------------------
   - Login may be superseded by Exam Start
   - Exam Start may be superseded by Submit
   - Result Pending may be superseded by Submit
   - Result Available MUST NOT suppress Exam Submitted
   - Exam Submitted gets all 15 appearances first
   - Result Available then gets its own 15 appearances

   PREMIUM FEATURES
   ------------------------------------------------------------
   1. 15x notification reminder
   2. Hover-to-pause while teacher is reading
   3. Browser-tab unread activity counter
   4. SSE connection-health tracking
   5. Queue-pressure / queue-count tracking
   6. Stale bootstrap-event protection
   7. Exponential SSE reconnect
   8. Exact backend sequence ordering
   9. Controlled same-student lifecycle preemption
   10. Diagnostics API via window.EmisAdminNotifications
============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  console.log("%c[admin_notifications.js] EMIS Premium FIFO Notification Engine Started", "color:#0f766e;font-weight:bold;");

  const $ = (id) => document.getElementById(id);

  /* ============================================================
     DOM
  ============================================================ */

  const host = $("liveNotificationHost");
  const card = $("liveNotificationCard");
  const icon = $("liveNotificationIcon");
  const typeLabel = $("liveNotificationType");
  const title = $("liveNotificationTitle");
  const message = $("liveNotificationMessage");
  const time = $("liveNotificationTime");
  const meta = $("liveNotificationMeta");
  const closeBtn = $("liveNotificationClose");

  if (!host || !card) {
    console.warn("[admin_notifications] Floating notification HTML was not found.");
    return;
  }

  /* ============================================================
     CONFIG
  ============================================================ */

  const POLL_INTERVAL = 7000;
  const FLASH_INTERVAL = 7000;
  const DISPLAY_DURATION = 4800;
  const EXIT_DURATION = 500;
  const BETWEEN_EVENTS_DELAY = 700;

  const REPEAT_COUNT = 15;
  const MAX_QUEUE = 500;
  const BOOTSTRAP_MAX_AGE = 45000;

  const SSE_RECONNECT_MIN = 2000;
  const SSE_RECONNECT_MAX = 30000;

  /* ============================================================
     STATE
  ============================================================ */

  let pendingQueue = [];
  let knownKeys = new Set();

  let currentNotification = null;
  let currentNotificationKey = "";
  let currentRepeatCount = 0;
  let currentAppearanceStartedAt = 0;

  let lastSequence = 0;
  let unreadWhileHidden = 0;

  let eventSource = null;
  let pollTimer = null;
  let hideTimer = null;
  let repeatTimer = null;
  let nextTimer = null;
  let reconnectTimer = null;

  let isShowing = false;
  let isPolling = false;
  let isHovered = false;
  let pendingFinishAfterHover = false;
  let sseConnected = false;
  let refreshCooldown = false;

  let reconnectAttempts = 0;
  let droppedQueueItems = 0;

  const originalDocumentTitle = document.title;

  /* ============================================================
     BASIC HELPERS
  ============================================================ */

  function safeText(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }

  function upper(value) { return String(value ?? "").trim().toUpperCase(); }

  function normalizeTerm(value) {
    const raw = upper(value).replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ");

    if (["FIRST", "FIRST TERM", "TERM 1", "TERM ONE", "1", "1ST", "1ST TERM"].includes(raw)) return "FIRST";
    if (["SECOND", "SECOND TERM", "TERM 2", "TERM TWO", "2", "2ND", "2ND TERM"].includes(raw)) return "SECOND";
    if (["THIRD", "THIRD TERM", "TERM 3", "TERM THREE", "3", "3RD", "3RD TERM"].includes(raw)) return "THIRD";

    return "";
  }

  function termLabel(value) {
    const term = normalizeTerm(value);

    if (term === "FIRST") return "1st Term";
    if (term === "SECOND") return "2nd Term";
    if (term === "THIRD") return "3rd Term";

    return "";
  }

  function formatSubject(value) { return String(value ?? "").replaceAll("_", " ").replace(/\s+/g, " ").trim().toUpperCase(); }

  function getPayload(notif) { return notif?.payload && typeof notif.payload === "object" ? notif.payload : {}; }

  function getSequence(notif) {
    const sequence = Number(notif?.sequence || 0);
    return Number.isFinite(sequence) ? sequence : 0;
  }

  /* ============================================================
     PAYLOAD HELPERS
  ============================================================ */

  function getAdmission(payload) { return payload.admission_number || payload.admission_no || payload["Admission No"] || payload.admission || payload.student_id || ""; }

  function getStudentName(payload) { return payload.student_name || payload.full_name || payload["Student Name"] || payload.student || payload.name || "Student"; }

  function getSubject(payload) { return payload.subject || payload.subject_folder || payload.Subject || payload["Subject Folder"] || ""; }

  function getYear(payload) { return payload.year || payload.Year || payload.exam_year || ""; }

  function getClass(payload) { return payload.class_arm || payload["Class Arm"] || payload.class_name || payload.class_category || payload["Class Category"] || payload.class || payload.Class || ""; }

  function getTerm(payload) { return normalizeTerm(payload.term || payload.Term || payload.term_name || payload["Term Label"] || ""); }

  function getScore(payload) {
    const value = payload.score ?? payload["Score (%)"] ?? payload.score_percentage ?? "";
    return String(value ?? "").replace("%", "").trim();
  }

  function getStatus(payload) { return upper(payload.status || payload.Status || payload.result_status || ""); }

  /* ============================================================
     EVENT TYPE
  ============================================================ */

  function getEventType(notif) {
    const payload = getPayload(notif);
    const rawType = String(notif?.type || "").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
    const status = String(payload.status || payload.result_status || "").trim().toLowerCase();

    if (["login", "student_login"].includes(rawType)) return "login";
    if (["exam_start", "exam_started", "start_exam"].includes(rawType)) return "exam_start";

    if (["exam_end", "exam_submit", "exam_submitted", "exam_submission", "submit_exam"].includes(rawType)) {
      if (["timeout", "timed_out"].includes(status)) return "timeout";
      return "exam_end";
    }

    if (["timeout", "exam_timeout", "exam_timed_out"].includes(rawType)) return "timeout";
    if (["result_pending", "pending_result", "result_processing"].includes(rawType)) return "result_pending";
    if (["result_available", "result_ready", "result_generated", "result_published"].includes(rawType)) return "result_available";

    return rawType || "notification";
  }

  /* ============================================================
     LIFECYCLE STAGE
  ============================================================ */

  function eventStage(notif) {
    const type = getEventType(notif);

    if (type === "login") return 10;
    if (type === "exam_start") return 20;
    if (type === "result_pending") return 30;
    if (type === "exam_end" || type === "timeout") return 40;
    if (type === "result_available") return 50;

    return 5;
  }

  /* ============================================================
     IDENTIFIERS
  ============================================================ */

  function getNotificationKey(notif) {
    if (notif?.id !== undefined && notif?.id !== null && String(notif.id).trim()) return String(notif.id);

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
    const admission = upper(getAdmission(payload));

    if (admission) return admission;

    return upper(getStudentName(payload)) || "UNKNOWN-STUDENT";
  }

  /* ============================================================
     CONTROLLED SUPERSESSION RULES
  ============================================================ */

  function canSupersede(oldNotif, newNotif) {
    if (!oldNotif || !newNotif) return false;
    if (getStudentKey(oldNotif) !== getStudentKey(newNotif)) return false;

    const oldType = getEventType(oldNotif);
    const newType = getEventType(newNotif);

    if (newType === "exam_start" && oldType === "login") return true;

    if (newType === "result_pending" && ["login", "exam_start"].includes(oldType)) return true;

    if (["exam_end", "timeout"].includes(newType) && ["login", "exam_start", "result_pending"].includes(oldType)) return true;

    if (newType === "result_available" && ["exam_end", "timeout"].includes(oldType)) return false;

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
     CONNECTION HEALTH
  ============================================================ */

  function setConnectionState(state) {
    host.dataset.connection = state;
    card.dataset.connection = state;

    window.dispatchEvent(new CustomEvent("emis:notification-connection", {
      detail: { state, connected: state === "connected", reconnectAttempts }
    }));
  }

  /* ============================================================
     QUEUE PRESSURE
  ============================================================ */

  function updateQueueState() {
    const queueLength = pendingQueue.length + (currentNotification ? 1 : 0);

    host.dataset.queueCount = String(queueLength);
    host.dataset.queuePressure = queueLength >= 50 ? "high" : queueLength >= 15 ? "medium" : "normal";

    window.dispatchEvent(new CustomEvent("emis:notification-queue", {
      detail: { pending: pendingQueue.length, current: Boolean(currentNotification), total: queueLength, dropped: droppedQueueItems }
    }));
  }

  /* ============================================================
     TAB TITLE UNREAD
  ============================================================ */

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
    const payload = getPayload(notif);
    const type = getEventType(notif);

    const student = getStudentName(payload);
    const subject = formatSubject(getSubject(payload));
    const score = getScore(payload);
    const status = getStatus(payload);

    if (type === "login") return { type, label: "Student Login", icon: "fa-user-check", title: `${student} logged in`, message: notif.message || "Student successfully accessed the CBT examination portal." };

    if (type === "exam_start") return { type, label: "Exam Started", icon: "fa-file-pen", title: `${student} started ${subject || "an examination"}`, message: notif.message || "The student's examination session is now in progress." };

    if (type === "result_pending") return { type, label: "Processing Result", icon: "fa-hourglass-half", title: `${student}'s result is processing`, message: notif.message || "The submitted examination result is currently being processed." };

    if (type === "exam_end") return { type, label: "Exam Submitted", icon: "fa-flag-checkered", title: `${student} submitted ${subject || "an examination"}`, message: notif.message || "The examination was successfully completed and submitted." };

    if (type === "timeout") return { type, label: "Exam Timeout", icon: "fa-clock", title: `${student}'s examination ended`, message: notif.message || "The examination ended because the allocated time expired." };

    if (type === "result_available") {
      const scoreText = score ? ` Score: ${score}%.` : "";
      const statusText = status ? ` Status: ${status}.` : "";

      return { type, label: "Result Available", icon: "fa-circle-check", title: `${student}'s result is available`, message: notif.message || `A new examination result is now available.${scoreText}${statusText}` };
    }

    return { type: "notification", label: "Live Activity", icon: "fa-bell", title: student, message: notif.message || payload.message || "New examination activity received." };
  }

  /* ============================================================
     META
  ============================================================ */

  function buildMeta(notif) {
    const payload = getPayload(notif);
    const values = [];

    const admission = getAdmission(payload);
    const cls = getClass(payload);
    const term = getTerm(payload);
    const subject = getSubject(payload);
    const year = getYear(payload);

    if (admission) values.push(admission);
    if (cls) values.push(upper(cls));
    if (term) values.push(termLabel(term));
    if (subject) values.push(formatSubject(subject));
    if (year) values.push(String(year));

    return values.slice(0, 5);
  }

  /* ============================================================
     RESULTS REFRESH
  ============================================================ */

  function triggerResultsRefresh(notif) {
    const type = getEventType(notif);

    if (!["exam_end", "timeout", "result_available"].includes(type)) return;
    if (refreshCooldown) return;

    refreshCooldown = true;

    setTimeout(() => { refreshCooldown = false; }, 3000);

    if (typeof window.refreshAdminResults === "function") return window.refreshAdminResults({ silent: true });
    if (typeof window.loadAllResults === "function") return window.loadAllResults({ silent: true });

    window.dispatchEvent(new CustomEvent("emis:result-submitted", { detail: notif }));
  }

  /* ============================================================
     FIFO SORT
  ============================================================ */

  function sortQueue() {
    pendingQueue.sort((a, b) => {
      const sequenceA = getSequence(a);
      const sequenceB = getSequence(b);

      if (sequenceA && sequenceB && sequenceA !== sequenceB) return sequenceA - sequenceB;

      return eventNumericTime(a) - eventNumericTime(b);
    });
  }

  /* ============================================================
     REMOVE ONLY TRULY OBSOLETE EVENTS
  ============================================================ */

  function removeSupersededPendingEvents(notif) {
    pendingQueue = pendingQueue.filter((queued) => !canSupersede(queued, notif));
  }

  /* ============================================================
     ADD EVENT
  ============================================================ */

  function addNotification(notif, fromLive = false, bootstrap = false) {
    if (!notif || !notif.type) return false;

    const key = getNotificationKey(notif);

    if (knownKeys.has(key)) return false;

    knownKeys.add(key);

    const sequence = getSequence(notif);

    if (sequence > lastSequence) lastSequence = sequence;

    if (bootstrap) {
      const created = eventNumericTime(notif);
      const age = created ? Date.now() - created : Infinity;

      if (!Number.isFinite(age) || age > BOOTSTRAP_MAX_AGE) return true;
    }

    registerHiddenActivity();
    removeSupersededPendingEvents(notif);

    const shouldPreemptCurrent = Boolean(
  fromLive &&
  currentNotification &&
  (
    getStudentKey(currentNotification) !== getStudentKey(notif) ||
    canSupersede(currentNotification, notif)
  )
);

    if (shouldPreemptCurrent) {
      pendingQueue.unshift(notif);

      if (fromLive) triggerResultsRefresh(notif);

      updateQueueState();
      preemptCurrentNotification();

      return true;
    }
    pendingQueue.push(notif);

    if (pendingQueue.length > MAX_QUEUE) {
      const overflow = pendingQueue.length - MAX_QUEUE;

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
     SHOW CARD
  ============================================================ */

  function showNotification(notif, isRepeat = false) {
    if (!notif) return;

    clearTimeout(hideTimer);
    clearTimeout(repeatTimer);
    clearTimeout(nextTimer);

    const presentation = getPresentation(notif);
    const chips = buildMeta(notif);

    currentNotification = notif;
    currentNotificationKey = getNotificationKey(notif);

    if (!isRepeat) currentRepeatCount = 1;

    currentAppearanceStartedAt = Date.now();
    pendingFinishAfterHover = false;
    isShowing = true;

    card.dataset.type = presentation.type;
    card.dataset.repeat = String(currentRepeatCount);
    card.dataset.repeatTotal = String(REPEAT_COUNT);

    if (icon) icon.innerHTML = `<i class="fa-solid ${safeText(presentation.icon)}"></i>`;
    if (typeLabel) typeLabel.textContent = presentation.label;
    if (title) title.textContent = presentation.title;
    if (message) message.textContent = presentation.message;
    if (time) time.textContent = relativeTime(notif);
    if (meta) meta.innerHTML = chips.map((value) => `<span>${safeText(value)}</span>`).join("");

    card.classList.remove("is-visible", "is-leaving");

    void card.offsetWidth;

    card.classList.add("is-visible");

    updateQueueState();

    console.log(`[admin_notifications] Showing ${currentRepeatCount}/${REPEAT_COUNT}:`, presentation.type, currentNotificationKey);

    hideTimer = setTimeout(() => {
      if (isHovered) {
        pendingFinishAfterHover = true;
        return;
      }

      finishAppearance();
    }, DISPLAY_DURATION);
  }

  /* ============================================================
     FINISH ONE APPEARANCE
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

      if (currentRepeatCount < REPEAT_COUNT) {
        currentRepeatCount++;

        const elapsedSinceAppearanceStart = Date.now() - currentAppearanceStartedAt;
        const waitForNextAppearance = Math.max(250, FLASH_INTERVAL - elapsedSinceAppearanceStart);

        repeatTimer = setTimeout(() => {
          if (!currentNotification) return;

          showNotification(currentNotification, true);
        }, waitForNextAppearance);

        return;
      }

      currentNotification = null;
      currentNotificationKey = "";
      currentRepeatCount = 0;
      currentAppearanceStartedAt = 0;

      updateQueueState();

      nextTimer = setTimeout(() => showNextNotification(), BETWEEN_EVENTS_DELAY);

    }, EXIT_DURATION);
  }

  /* ============================================================
     NEXT FIFO EVENT
  ============================================================ */

  function showNextNotification() {
    if (isShowing || currentNotification) return;

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
     PREEMPT CURRENT EVENT
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

    }, EXIT_DURATION);
  }

  /* ============================================================
     HOVER TO PAUSE
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
     FETCH
  ============================================================ */

  async function fetchNotifications(initial = false) {
    if (isPolling) return;

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
      console.error("[admin_notifications] Fetch failed:", error);

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
    clearTimeout(reconnectTimer);

    reconnectAttempts++;

    const delay = Math.min(
      SSE_RECONNECT_MAX,
      SSE_RECONNECT_MIN * Math.pow(2, Math.min(reconnectAttempts - 1, 4))
    );

    setConnectionState("reconnecting");

    reconnectTimer = setTimeout(() => {
      if (!document.hidden) startEventStream();
    }, delay);

    console.warn(`[admin_notifications] SSE reconnect scheduled in ${delay}ms.`);
  }

  function startEventStream() {
    if (!window.EventSource || eventSource) return;

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
        sseConnected = false;

        closeEventStream();
        scheduleSseReconnect();
      };

    } catch (error) {
      console.error("[admin_notifications] Could not start SSE:", error);

      closeEventStream();
      scheduleSseReconnect();
    }
  }

  /* ============================================================
     POLLING FALLBACK
  ============================================================ */

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(() => {
      if (!document.hidden) fetchNotifications(false);
    }, POLL_INTERVAL);
  }

  /* ============================================================
     MANUAL CLOSE
  ============================================================ */

  closeBtn?.addEventListener("click", () => {
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

    }, EXIT_DURATION);
  });

  /* ============================================================
     TAB VISIBILITY
  ============================================================ */

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;

    clearHiddenActivity();

    fetchNotifications(false);

    if (!eventSource) startEventStream();

    if (!isShowing && !currentNotification && pendingQueue.length) showNextNotification();
  });

  /* ============================================================
     ONLINE / OFFLINE
  ============================================================ */

  window.addEventListener("online", () => {
    setConnectionState("connecting");

    fetchNotifications(false);

    if (!eventSource) startEventStream();
  });

  window.addEventListener("offline", () => {
    setConnectionState("offline");
    closeEventStream();
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
     GLOBAL API
  ============================================================ */

  window.EmisAdminNotifications = {
    refresh: () => fetchNotifications(false),

    push: (notification) => addNotification(notification, true, false),

    showNext: () => showNextNotification(),

    queueLength: () => pendingQueue.length,

    state: () => ({
      pending: pendingQueue.length,
      current: currentNotification,
      currentType: currentNotification ? getEventType(currentNotification) : null,
      repeat: currentRepeatCount,
      repeatTotal: REPEAT_COUNT,
      lastSequence,
      sseConnected,
      reconnectAttempts,
      unreadWhileHidden,
      droppedQueueItems
    }),

    reconnect: () => {
      closeEventStream();
      reconnectAttempts = 0;
      startEventStream();
    },

    clear: () => {
      pendingQueue = [];
      knownKeys.clear();

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

    if (navigator.onLine) startEventStream();

    startPolling();

    if (!isShowing && !currentNotification && pendingQueue.length) showNextNotification();

    console.log(`[admin_notifications] Premium FIFO engine ready. Queue: ${pendingQueue.length}, repeat: ${REPEAT_COUNT}x.`);
  }

  initNotifications();
});
/* static/js/admin_notifications.js */
/* ============================================================
   EMIS ADMIN FLOATING REAL-TIME NOTIFICATION ENGINE

   Features:
   - Uses Server-Sent Events when available
   - Falls back to polling automatically
   - Poll reconciliation every 7 seconds
   - Sliding notification card every 7 seconds
   - No activity = no card displayed
   - Handles login, exam start, submission, timeout
   - Ready for result_pending / result_available events
   - Deduplicates repeated events
   - Keeps latest event per student/activity
   - Refreshes Admin Results when exam/result activity changes
   - Supports JSS term metadata
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  console.log("%c[admin_notifications.js] EMIS Floating Live Notifications Engine Started", "color:#0f766e;font-weight:bold;");

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
  const ROTATION_INTERVAL = 7000;
  const DISPLAY_DURATION = 5600;
  const EXIT_DURATION = 550;
  const MAX_NOTIFICATIONS = 60;

  let allNotifications = [];
  let notificationQueue = [];
  let knownNotificationKeys = new Set();
  let dismissedKeys = new Set();

  let lastEventTime = 0;
  let currentNotification = null;
  let currentNotificationKey = "";

  let eventSource = null;
  let pollTimer = null;
  let rotationTimer = null;
  let hideTimer = null;

  let isShowing = false;
  let isPolling = false;
  let sseConnected = false;
  let refreshCooldown = false;


  /* ============================================================
     BASIC HELPERS
     ============================================================ */

  function safeText(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

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


  /* ============================================================
     PAYLOAD HELPERS
     ============================================================ */

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
    return payload.class_arm || payload["Class Arm"] || payload.class_name || payload.class_category || payload["Class Category"] || payload.class || payload.Class || "";
  }

  function getClassLevel(payload) {
    return payload.class_level || payload["Class Level"] || payload.class_category || payload["Class Category"] || payload.class || payload.Class || "";
  }

  function getTerm(payload) {
    return normalizeTerm(payload.term || payload.Term || payload.term_name || payload["Term Label"] || "");
  }

  function getScore(payload) {
    const value = payload.score ?? payload["Score (%)"] ?? payload.score_percentage ?? "";
    return String(value ?? "").replace("%", "").trim();
  }

  function getStatus(payload) {
    return upper(payload.status || payload.Status || payload.result_status || "");
  }


  /* ============================================================
     EVENT TYPE NORMALIZATION
     ============================================================ */

  function getEventType(notif) {
    const payload = getPayload(notif);
    const rawType = String(notif?.type || "").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
    const status = String(payload.status || payload.result_status || "").trim().toLowerCase();

    if (rawType === "login" || rawType === "student_login") return "login";

    if (["exam_start", "exam_started", "start_exam"].includes(rawType)) return "exam_start";

    if (["exam_end", "exam_submit", "exam_submitted", "exam_submission", "submit_exam"].includes(rawType)) {
      if (status === "timeout" || status === "timed_out") return "timeout";
      return "exam_end";
    }

    if (["timeout", "exam_timeout", "exam_timed_out"].includes(rawType)) return "timeout";

    if (["result_pending", "pending_result", "result_processing"].includes(rawType)) return "result_pending";

    if (["result_available", "result_ready", "result_generated", "result_published"].includes(rawType)) return "result_available";

    return rawType || "notification";
  }


  /* ============================================================
     EVENT IDENTIFIERS
     ============================================================ */

  function getNotificationKey(notif) {
    if (notif?.id !== undefined && notif?.id !== null && String(notif.id).trim()) return String(notif.id);

    const payload = getPayload(notif);
    const type = getEventType(notif);
    const admission = upper(getAdmission(payload)) || "UNKNOWN";
    const subject = upper(getSubject(payload));
    const year = String(getYear(payload) || "");
    const term = getTerm(payload);
    const timestamp = notif?.timestamp || payload.timestamp || notif?.created_at || "";

    return `${type}:${admission}:${subject}:${year}:${term}:${timestamp}`;
  }

  function getDedupeKey(notif) {
    const payload = getPayload(notif);
    const type = getEventType(notif);
    const admission = upper(getAdmission(payload)) || "UNKNOWN";
    const subject = upper(getSubject(payload));
    const year = String(getYear(payload) || "");
    const term = getTerm(payload);

    if (type === "login") return `login:${admission}`;
    if (type === "exam_start") return `exam_start:${admission}:${subject}:${year}:${term}`;
    if (type === "exam_end") return `exam_end:${admission}:${subject}:${year}:${term}`;
    if (type === "timeout") return `timeout:${admission}:${subject}:${year}:${term}`;
    if (type === "result_pending") return `result_pending:${admission}:${subject}:${year}:${term}`;
    if (type === "result_available") return `result_available:${admission}:${subject}:${year}:${term}`;

    return getNotificationKey(notif);
  }


  /* ============================================================
     EVENT TIME
     ============================================================ */

  function eventNumericTime(notif) {
    const created = Number(notif?.created_at || 0);
    if (Number.isFinite(created) && created > 0) return created;

    const parsed = Date.parse(notif?.timestamp || "");
    if (Number.isFinite(parsed)) return Math.floor(parsed / 1000);

    return 0;
  }

  function relativeTime(notif) {
    const created = eventNumericTime(notif);

    if (created > 0) {
      const createdMs = created > 100000000000 ? created : created * 1000;
      const seconds = Math.max(0, Math.floor((Date.now() - createdMs) / 1000));

      if (seconds < 10) return "Just now";
      if (seconds < 60) return `${seconds}s ago`;

      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;

      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}h ago`;

      const days = Math.floor(hours / 24);
      if (days < 7) return `${days}d ago`;
    }

    return notif?.timestamp || "";
  }


  /* ============================================================
     CARD PRESENTATION
     ============================================================ */

  function getPresentation(notif) {
    const payload = getPayload(notif);
    const type = getEventType(notif);

    const student = getStudentName(payload);
    const subject = formatSubject(getSubject(payload));
    const score = getScore(payload);
    const status = getStatus(payload);

    if (type === "login") {
      return {
        type: "login",
        label: "Student Login",
        icon: "fa-user-check",
        title: `${student} logged in`,
        message: notif.message || "Student successfully accessed the CBT examination portal."
      };
    }

    if (type === "exam_start") {
      return {
        type: "exam_start",
        label: "Exam Started",
        icon: "fa-file-pen",
        title: `${student} started ${subject || "an examination"}`,
        message: notif.message || "A new examination session is currently in progress."
      };
    }

    if (type === "exam_end") {
      return {
        type: "exam_end",
        label: "Exam Submitted",
        icon: "fa-flag-checkered",
        title: `${student} submitted ${subject || "an examination"}`,
        message: notif.message || "The examination was successfully completed and submitted."
      };
    }

    if (type === "timeout") {
      return {
        type: "timeout",
        label: "Exam Timeout",
        icon: "fa-clock",
        title: `${student}'s examination ended`,
        message: notif.message || "The examination session ended because the allocated time expired."
      };
    }

    if (type === "result_pending") {
      return {
        type: "result_pending",
        label: "Result Pending",
        icon: "fa-hourglass-half",
        title: `${student}'s result is pending`,
        message: notif.message || "The examination result is currently awaiting processing."
      };
    }

    if (type === "result_available") {
      const scoreText = score ? ` Score: ${score}%.` : "";
      const statusText = status ? ` Status: ${status}.` : "";

      return {
        type: "result_available",
        label: "Result Available",
        icon: "fa-circle-check",
        title: `${student}'s result is available`,
        message: notif.message || `A new examination result is now available.${scoreText}${statusText}`
      };
    }

    return {
      type: "notification",
      label: "Live Activity",
      icon: "fa-bell",
      title: student,
      message: notif.message || payload.message || "New examination activity received."
    };
  }


  /* ============================================================
     CARD META CHIPS
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
    setTimeout(() => { refreshCooldown = false; }, 3500);

    if (typeof window.refreshAdminResults === "function") {
      window.refreshAdminResults({ silent: true });
      return;
    }

    if (typeof window.loadAllResults === "function") {
      window.loadAllResults({ silent: true });
      return;
    }

    window.dispatchEvent(new CustomEvent("emis:result-submitted", { detail: notif }));
  }


  /* ============================================================
     ADD / UPDATE NOTIFICATION
     ============================================================ */

  function addNotification(notif, fromLive = false) {
    if (!notif || !notif.type) return false;

    const uniqueKey = getNotificationKey(notif);

    if (knownNotificationKeys.has(uniqueKey)) return false;

    knownNotificationKeys.add(uniqueKey);
    allNotifications.push(notif);

    const created = eventNumericTime(notif);
    if (created > lastEventTime) lastEventTime = created;

    if (allNotifications.length > 500) allNotifications = allNotifications.slice(-500);

    rebuildNotificationQueue();

    if (fromLive) {
      triggerResultsRefresh(notif);

      if (!isShowing) showNextNotification();
    }

    return true;
  }


  /* ============================================================
     BUILD DEDUPED ROTATION QUEUE
     ============================================================ */

  function rebuildNotificationQueue() {
    const latestMap = new Map();

    [...allNotifications]
      .sort((a, b) => eventNumericTime(a) - eventNumericTime(b))
      .forEach((notif) => latestMap.set(getDedupeKey(notif), notif));

    notificationQueue = [...latestMap.values()]
      .sort((a, b) => eventNumericTime(b) - eventNumericTime(a))
      .filter((notif) => !dismissedKeys.has(getNotificationKey(notif)))
      .slice(0, MAX_NOTIFICATIONS);
  }


  /* ============================================================
     FIND NEXT CARD
     ============================================================ */

  function getNextNotification() {
    rebuildNotificationQueue();

    if (!notificationQueue.length) return null;

    if (!currentNotificationKey) return notificationQueue[0];

    const currentIndex = notificationQueue.findIndex((notif) => getNotificationKey(notif) === currentNotificationKey);

    if (currentIndex < 0) return notificationQueue[0];

    const nextIndex = (currentIndex + 1) % notificationQueue.length;

    return notificationQueue[nextIndex];
  }


  /* ============================================================
     SHOW NOTIFICATION CARD
     ============================================================ */

  function showNotification(notif) {
    if (!notif) {
      hideNotification(true);
      return;
    }

    clearTimeout(hideTimer);

    const presentation = getPresentation(notif);
    const chips = buildMeta(notif);
    const key = getNotificationKey(notif);

    currentNotification = notif;
    currentNotificationKey = key;
    isShowing = true;

    card.dataset.type = presentation.type;

    if (icon) icon.innerHTML = `<i class="fa-solid ${safeText(presentation.icon)}"></i>`;
    if (typeLabel) typeLabel.textContent = presentation.label;
    if (title) title.textContent = presentation.title;
    if (message) message.textContent = presentation.message;
    if (time) time.textContent = relativeTime(notif);

    if (meta) meta.innerHTML = chips.map((value) => `<span>${safeText(value)}</span>`).join("");

    card.classList.remove("is-visible", "is-leaving");

    void card.offsetWidth;

    card.classList.add("is-visible");

    hideTimer = setTimeout(() => hideNotification(false), DISPLAY_DURATION);
  }


  /* ============================================================
     HIDE NOTIFICATION CARD
     ============================================================ */

  function hideNotification(immediate = false) {
    clearTimeout(hideTimer);

    if (!isShowing && !card.classList.contains("is-visible")) return;

    if (immediate) {
      card.classList.remove("is-visible", "is-leaving");
      isShowing = false;
      return;
    }

    card.classList.remove("is-visible");
    card.classList.add("is-leaving");

    setTimeout(() => {
      card.classList.remove("is-leaving");
      isShowing = false;
    }, EXIT_DURATION);
  }


  /* ============================================================
     ROTATE NOTIFICATION
     ============================================================ */

  function showNextNotification() {
    const next = getNextNotification();

    if (!next) {
      hideNotification(true);
      currentNotification = null;
      currentNotificationKey = "";
      return;
    }

    if (isShowing) {
      hideNotification(false);

      setTimeout(() => showNotification(next), EXIT_DURATION + 100);

      return;
    }

    showNotification(next);
  }


  /* ============================================================
     FETCH NOTIFICATIONS
     ============================================================ */

  async function fetchNotifications(initial = false) {
    if (isPolling) return;

    isPolling = true;

    try {
      const url = initial || !lastEventTime ? "/api/notifications/fetch" : `/api/notifications/fetch?since=${encodeURIComponent(lastEventTime)}`;

      const res = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" }
      });

      if (!res.ok) {
        console.warn("[admin_notifications] Notification fetch failed:", res.status);
        return;
      }

      const data = await res.json();

      if (data.error) {
        console.warn("[admin_notifications] Server notification error:", data.error);
        return;
      }

      const notifications = Array.isArray(data.notifications) ? data.notifications : [];
      let addedCount = 0;

      notifications.forEach((notif) => {
        if (addNotification(notif, !initial)) addedCount++;
      });

      rebuildNotificationQueue();

      if (initial && notificationQueue.length && !isShowing) showNextNotification();
      if (!notificationQueue.length) hideNotification(true);

      if (!initial && addedCount > 0) console.log(`[admin_notifications] ${addedCount} new notification(s) received.`);

    } catch (error) {
      console.error("[admin_notifications] Fetch failed:", error);

    } finally {
      isPolling = false;
    }
  }


  /* ============================================================
     SERVER-SENT EVENTS
     ============================================================ */

  function closeEventStream() {
    if (!eventSource) return;

    eventSource.close();
    eventSource = null;
    sseConnected = false;
  }

  function startEventStream() {
    if (!window.EventSource) {
      console.warn("[admin_notifications] EventSource unsupported. Polling mode enabled.");
      return;
    }

    if (eventSource) return;

    try {
      eventSource = new EventSource("/api/notifications/stream");

      eventSource.addEventListener("connected", () => {
        sseConnected = true;
        console.log("[admin_notifications] SSE connected.");
      });

      eventSource.addEventListener("notification", (event) => {
        try {
          const notif = JSON.parse(event.data);
          addNotification(notif, true);

        } catch (error) {
          console.error("[admin_notifications] Invalid SSE notification:", error);
        }
      });

      eventSource.onopen = () => {
        sseConnected = true;
      };

      eventSource.onerror = () => {
        if (sseConnected) console.warn("[admin_notifications] SSE connection lost. Polling will continue.");

        sseConnected = false;
        closeEventStream();

        setTimeout(() => {
          if (!document.hidden) startEventStream();
        }, 10000);
      };

    } catch (error) {
      console.error("[admin_notifications] Could not start SSE:", error);
      closeEventStream();
    }
  }


  /* ============================================================
     POLLING
     ============================================================ */

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(() => {
      if (!document.hidden) fetchNotifications(false);
    }, POLL_INTERVAL);
  }


  /* ============================================================
     CARD ROTATION
     ============================================================ */

  function startRotation() {
    if (rotationTimer) clearInterval(rotationTimer);

    rotationTimer = setInterval(() => {
      if (document.hidden) return;
      if (!notificationQueue.length) return;

      showNextNotification();
    }, ROTATION_INTERVAL);
  }


  /* ============================================================
     MANUAL DISMISS
     ============================================================ */

  closeBtn?.addEventListener("click", () => {
    if (currentNotificationKey) dismissedKeys.add(currentNotificationKey);

    hideNotification(false);

    setTimeout(() => {
      currentNotification = null;
      currentNotificationKey = "";

      rebuildNotificationQueue();

      if (notificationQueue.length) showNextNotification();
    }, EXIT_DURATION + 150);
  });


  /* ============================================================
     VISIBILITY
     ============================================================ */

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;

    fetchNotifications(false);

    if (!eventSource) startEventStream();

    if (notificationQueue.length && !isShowing) showNextNotification();
  });


  /* ============================================================
     PAGE CLEANUP
     ============================================================ */

  window.addEventListener("beforeunload", () => {
    if (pollTimer) clearInterval(pollTimer);
    if (rotationTimer) clearInterval(rotationTimer);
    if (hideTimer) clearTimeout(hideTimer);

    closeEventStream();
  });


  /* ============================================================
     OPTIONAL GLOBAL API
     Useful if another script wants to create an admin notice.
     ============================================================ */

  window.EmisAdminNotifications = {
    refresh: () => fetchNotifications(false),

    push: (notification) => addNotification(notification, true),

    showNext: () => showNextNotification(),

    clear: () => {
      allNotifications = [];
      notificationQueue = [];
      knownNotificationKeys.clear();
      dismissedKeys.clear();

      currentNotification = null;
      currentNotificationKey = "";

      hideNotification(true);
    }
  };


  /* ============================================================
     INITIALIZE
     ============================================================ */

  async function initNotifications() {
    await fetchNotifications(true);

    startEventStream();
    startPolling();
    startRotation();

    console.log(`[admin_notifications] Ready with ${notificationQueue.length} active notification(s).`);
  }

  initNotifications();
});
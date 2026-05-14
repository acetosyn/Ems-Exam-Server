/* static/js/admin_notifications.js */

console.log(
  "%c[admin_notifications.js] EMIS Live Notifications Engine Started",
  "color:#fbbf24;font-weight:bold;"
);

const loginList = document.getElementById("loginNotifList");
const examList = document.getElementById("examNotifList");

const MAX_LOGIN_ITEMS = 30;
const MAX_EXAM_ITEMS = 50;

let allNotifications = [];
let seenKeys = new Set();
let lastEventTime = 0;
let pollTimer = null;
let eventSource = null;
let refreshCooldown = false;

function safeText(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getPayload(notif) {
  return notif && notif.payload ? notif.payload : {};
}

function getAdmission(payload) {
  return (
    payload.admission_number ||
    payload.admission_no ||
    payload.admission ||
    payload.student_id ||
    "???"
  );
}

function getStudentName(payload) {
  return (
    payload.student_name ||
    payload.full_name ||
    payload.student ||
    "Unknown Student"
  );
}

function getSubject(payload) {
  return String(payload.subject || "").toUpperCase();
}

function getYear(payload) {
  return payload.year || "";
}

function getClass(payload) {
  return payload.class_category || payload.class_name || payload.class || "";
}

function getNotificationKey(notif) {
  const payload = getPayload(notif);
  const adm = getAdmission(payload);
  const subject = getSubject(payload);
  const year = getYear(payload);
  const type = notif.type || "notification";

  if (notif.id) {
    return notif.id;
  }

  return `${type}:${adm}:${subject}:${year}:${notif.timestamp || ""}`;
}

function getDedupeKey(notif) {
  const payload = getPayload(notif);
  const adm = getAdmission(payload);
  const subject = getSubject(payload);
  const year = getYear(payload);

  if (notif.type === "login") {
    return `login:${adm}`;
  }

  if (notif.type === "exam_start") {
    return `exam_start:${adm}:${subject}:${year}`;
  }

  if (notif.type === "exam_end") {
    return `exam_end:${adm}:${subject}:${year}`;
  }

  return getNotificationKey(notif);
}

function getIconClass(type, payload) {
  if (type === "login") return "fa-user-check";
  if (type === "exam_start") return "fa-hourglass-start";

  if (type === "exam_end") {
    const status = String(payload.status || "").toLowerCase();
    return status === "timeout" ? "fa-hourglass-end" : "fa-flag-checkered";
  }

  return "fa-bell";
}

function renderEmptyState(listElement, mode) {
  if (!listElement) return;

  listElement.innerHTML = `
    <li class="emis-notif-empty">
      <i class="fa-solid fa-bell-slash"></i>
      <p>${mode === "login" ? "No logins yet" : "No exam activity yet"}</p>
      <small>${mode === "login"
        ? "Student login activity will appear here in real-time."
        : "Exam start and submission actions will show here in real-time."}</small>
    </li>
  `;
}

function createNotifItem(notif, isNew = false) {
  const payload = getPayload(notif);
  const studentName = getStudentName(payload);
  const adm = getAdmission(payload);
  const subject = getSubject(payload);
  const cls = getClass(payload);
  const year = getYear(payload);
  const iconClass = getIconClass(notif.type, payload);

  const li = document.createElement("li");
  li.className = `emis-notif-item ${isNew ? "is-new" : ""}`;

  let metaLine = [];

  if (adm && adm !== "???") metaLine.push(adm);
  if (subject) metaLine.push(subject);
  if (cls) metaLine.push(cls);
  if (year) metaLine.push(year);

  li.innerHTML = `
    <div class="notif-icon">
      <i class="fa-solid ${iconClass}"></i>
    </div>
    <div class="notif-main">
      <strong>${safeText(studentName)}</strong>
      <span class="notif-sub">${safeText(notif.message || "")}</span>
      <span class="notif-meta">
        ${safeText(metaLine.join(" • "))}${metaLine.length ? " • " : ""}${safeText(notif.timestamp || "")}
      </span>
    </div>
  `;

  if (isNew) {
    setTimeout(() => li.classList.remove("is-new"), 2500);
  }

  return li;
}

function buildQueues() {
  const loginMap = new Map();
  const examMap = new Map();

  allNotifications.forEach((notif) => {
    if (!notif || !notif.type) return;

    const key = getDedupeKey(notif);

    if (notif.type === "login") {
      loginMap.set(key, notif);
    }

    if (notif.type === "exam_start" || notif.type === "exam_end") {
      examMap.set(key, notif);
    }
  });

  const sortLatest = (a, b) => {
    const at = Number(a.created_at || 0);
    const bt = Number(b.created_at || 0);

    if (at || bt) return bt - at;

    return String(b.timestamp || "").localeCompare(String(a.timestamp || ""));
  };

  return {
    loginArray: Array.from(loginMap.values()).sort(sortLatest).slice(0, MAX_LOGIN_ITEMS),
    examArray: Array.from(examMap.values()).sort(sortLatest).slice(0, MAX_EXAM_ITEMS)
  };
}

function renderNotifications(newKeys = new Set()) {
  const { loginArray, examArray } = buildQueues();

  if (!loginArray.length) {
    renderEmptyState(loginList, "login");
  } else if (loginList) {
    loginList.innerHTML = "";
    loginArray.forEach((notif) => {
      const key = getNotificationKey(notif);
      loginList.appendChild(createNotifItem(notif, newKeys.has(key)));
    });
  }

  if (!examArray.length) {
    renderEmptyState(examList, "exam");
  } else if (examList) {
    examList.innerHTML = "";
    examArray.forEach((notif) => {
      const key = getNotificationKey(notif);
      examList.appendChild(createNotifItem(notif, newKeys.has(key)));
    });
  }
}

function triggerResultsRefresh(notif) {
  if (!notif || notif.type !== "exam_end") return;

  if (refreshCooldown) return;

  refreshCooldown = true;

  setTimeout(() => {
    refreshCooldown = false;
  }, 4000);

  if (typeof window.loadAllResults === "function") {
    window.loadAllResults();
    return;
  }

  window.dispatchEvent(new CustomEvent("emis:result-submitted", {
    detail: notif
  }));
}

function addNotification(notif, fromLive = false) {
  if (!notif || !notif.type) return;

  const key = getNotificationKey(notif);

  if (seenKeys.has(key)) return;

  seenKeys.add(key);
  allNotifications.push(notif);

  if (Number(notif.created_at || 0) > lastEventTime) {
    lastEventTime = Number(notif.created_at);
  }

  if (allNotifications.length > 500) {
    allNotifications = allNotifications.slice(-500);
  }

  renderNotifications(fromLive ? new Set([key]) : new Set());

  if (fromLive) {
    triggerResultsRefresh(notif);
  }
}

async function fetchNotifications(initial = false) {
  try {
    const url = initial
      ? "/api/notifications/fetch"
      : `/api/notifications/fetch?since=${encodeURIComponent(lastEventTime)}`;

    const res = await fetch(url, {
      headers: {
        Accept: "application/json"
      }
    });

    if (!res.ok) {
      console.warn("[notifications] fetch failed:", res.status);
      return;
    }

    const data = await res.json();

    if (data.error) {
      console.warn("[notifications] server error:", data.error);
      return;
    }

    const list = Array.isArray(data.notifications) ? data.notifications : [];
    const newKeys = new Set();

    list.forEach((notif) => {
      const key = getNotificationKey(notif);

      if (!seenKeys.has(key)) {
        seenKeys.add(key);
        newKeys.add(key);
        allNotifications.push(notif);
      }

      if (Number(notif.created_at || 0) > lastEventTime) {
        lastEventTime = Number(notif.created_at);
      }
    });

    if (allNotifications.length > 500) {
      allNotifications = allNotifications.slice(-500);
    }

    renderNotifications(initial ? new Set() : newKeys);

    if (!initial && list.some((n) => n.type === "exam_end")) {
      triggerResultsRefresh({ type: "exam_end" });
    }
  } catch (err) {
    console.error("[notifications] fetch failed:", err);
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(() => {
    fetchNotifications(false);
  }, 3000);
}

function startEventStream() {
  if (!window.EventSource) {
    startPolling();
    return;
  }

  try {
    eventSource = new EventSource("/api/notifications/stream");

    eventSource.addEventListener("connected", () => {
      console.log("[notifications] SSE connected");
    });

    eventSource.addEventListener("notification", (event) => {
      try {
        const notif = JSON.parse(event.data);
        addNotification(notif, true);
      } catch (err) {
        console.error("[notifications] bad SSE payload:", err);
      }
    });

    eventSource.onerror = () => {
      console.warn("[notifications] SSE disconnected. Falling back to polling.");

      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      startPolling();
    };
  } catch (err) {
    console.error("[notifications] SSE failed:", err);
    startPolling();
  }
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    fetchNotifications(false);
  }
});

fetchNotifications(true).then(() => {
  startEventStream();
  startPolling();
});
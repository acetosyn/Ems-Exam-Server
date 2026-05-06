/* ============================================================================
   EMIS ADMIN LIVE NOTIFICATIONS ENGINE (2025 · PREMIUM QUEUE VERSION)
   - Polls server for login + exam activity every 7 seconds
   - Dedupes repeated events (latest login / start / submit only)
   - Supports high volume (hundreds+ of students)
   - Triggers "is-new" class for slide-in / glow animations
   - Uses dynamic icons for login / start / submit / timeout
============================================================================ */

console.log(
  "%c[admin_notifications.js] Live Notifications Queue Engine Ready",
  "color:#fbbf24;font-weight:bold;"
);

// DOM targets
const loginList = document.getElementById("loginNotifList");
const examList  = document.getElementById("examNotifList");

// How many items we *visually* keep
const MAX_LOGIN_ITEMS = 30;
const MAX_EXAM_ITEMS  = 40;

// To detect "new" items between polls
let prevLoginKeys = new Set();
let prevExamKeys  = new Set();

/* ----------------------------------------------------------------------------
   Helpers: Empty placeholders
---------------------------------------------------------------------------- */
function renderEmptyState(listElement, mode) {
  if (!listElement) return;

  const li = document.createElement("li");
  li.className = "emis-notif-empty";

  if (mode === "login") {
    li.innerHTML = `
      <i class="fa-solid fa-bell-slash"></i>
      <p>No logins yet</p>
      <span>Student login activity will appear here in real-time.</span>
    `;
  } else {
    li.innerHTML = `
      <i class="fa-solid fa-bell-slash"></i>
      <p>No exam activity yet</p>
      <span>Exam start and submission actions will show here in real-time.</span>
    `;
  }

  listElement.innerHTML = "";
  listElement.appendChild(li);
}

/* ----------------------------------------------------------------------------
   Helper: Build a stable unique key per notification so we can dedupe

   - LOGIN        key: "login:ADM"
   - EXAM START   key: "start:ADM:SUBJECT:YEAR"
   - EXAM END     key: "end:ADM:SUBJECT:YEAR"
---------------------------------------------------------------------------- */
function getNotificationKey(notif) {
  const payload = notif.payload || {};
  const adm     = payload.admission_number || payload.admission || "???";
  const subject = (payload.subject || "").toUpperCase();
  const year    = payload.year || "";

  if (notif.type === "login") {
    return `login:${adm}`;
  }
  if (notif.type === "exam_start") {
    return `start:${adm}:${subject}:${year}`;
  }
  if (notif.type === "exam_end") {
    return `end:${adm}:${subject}:${year}`;
  }

  // Fallback (should rarely be used)
  return `${notif.type}:${adm}:${subject}:${year}:${notif.timestamp || ""}`;
}

/* ----------------------------------------------------------------------------
   Helper: Decide icon based on notification type and status
---------------------------------------------------------------------------- */
function getIconHTML(notif) {
  if (notif.type === "login") {
    return `<i class="fa-solid fa-user-check notif-icon"></i>`;
  }

  if (notif.type === "exam_start") {
    return `<i class="fa-solid fa-hourglass-start notif-icon"></i>`;
  }

  if (notif.type === "exam_end") {
    const status = (notif.payload && notif.payload.status) || "";
    if (status === "timeout") {
      return `<i class="fa-solid fa-hourglass-end notif-icon"></i>`;
    }
    return `<i class="fa-solid fa-flag-checkered notif-icon"></i>`;
  }

  // Default fallback
  return `<i class="fa-solid fa-bell notif-icon"></i>`;
}

/* ----------------------------------------------------------------------------
   Create a notification list item from backend object
   notif = { type, message, payload, timestamp, __key }
---------------------------------------------------------------------------- */
function makeNotifItem(notif) {
  const li = document.createElement("li");
  li.className = "emis-notif-item";

  const payload = notif.payload || {};
  const studentName =
    payload.student_name ||
    payload.student ||
    "Unknown Student";

  const actionText = notif.message || "";
  const timestamp  = notif.timestamp || "";

  const iconHTML = getIconHTML(notif);

  li.innerHTML = `
    ${iconHTML}
    <div class="notif-main">
      <strong>${studentName}</strong>
      <span class="notif-sub">${actionText}</span>
      <span class="notif-meta">${timestamp}</span>
    </div>
  `;

  return li;
}

/* ----------------------------------------------------------------------------
   Build deduped queues for login + exam from raw notifications array

   - The backend queue is chronological (oldest → newest)
   - We iterate in order and simply overwrite the map entry for a given key.
   - This means the map stores ONLY the most recent event for each key.
---------------------------------------------------------------------------- */
function buildQueues(rawList) {
  const loginMap = new Map();
  const examMap  = new Map();

  for (const notif of rawList) {
    if (!notif || !notif.type) continue;

    const key = getNotificationKey(notif);
    notif.__key = key;

    if (notif.type === "login") {
      loginMap.set(key, notif);
    } else if (notif.type === "exam_start" || notif.type === "exam_end") {
      examMap.set(key, notif);
    }
  }

  let loginArray = Array.from(loginMap.values());
  let examArray  = Array.from(examMap.values());

  // Sort by timestamp DESC (newest first)
  loginArray.sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
  examArray.sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));

  // Hard cap visible items
  loginArray = loginArray.slice(0, MAX_LOGIN_ITEMS);
  examArray  = examArray.slice(0, MAX_EXAM_ITEMS);

  return { loginArray, examArray };
}

/* ----------------------------------------------------------------------------
   Render a list (login or exam) with "new" animations
---------------------------------------------------------------------------- */
function renderList(listEl, items, mode, prevKeySet) {
  if (!listEl) return;

  // If no items → show empty state
  if (!items.length) {
    renderEmptyState(listEl, mode);
    return;
  }

  // Clear current content
  listEl.innerHTML = "";

  items.forEach((notif) => {
    const li = makeNotifItem(notif);

    // Slide-in animation ONLY for truly new keys
    if (!prevKeySet.has(notif.__key)) {
      li.classList.add("is-new");
      // remove the animation class after a while so it can re-apply if needed
      setTimeout(() => li.classList.remove("is-new"), 2200);
    }

    listEl.appendChild(li);
  });
}

/* ----------------------------------------------------------------------------
   MAIN POLL FUNCTION — HIGH VOLUME SAFE

   - Fetches full queue from backend
   - Dedupe per student / exam
   - Only keeps recent unique events
   - Renders login & exam lists with animations
---------------------------------------------------------------------------- */
async function pollNotifications() {
  try {
    const res = await fetch("/api/notifications/fetch", {
      headers: { "Accept": "application/json" }
    });

    if (!res.ok) {
      console.warn("[notifications] fetch failed with status", res.status);
      return;
    }

    const data = await res.json();

    if (data.error) {
      console.warn("[notifications] server error:", data.error);
      return;
    }

    const all = Array.isArray(data.notifications) ? data.notifications : [];

    // Build deduped queues
    const { loginArray, examArray } = buildQueues(all);

    // Current key sets for diffing
    const currentLoginKeys = new Set(loginArray.map(n => n.__key));
    const currentExamKeys  = new Set(examArray.map(n => n.__key));

    // Render lists (with "is-new" where needed)
    renderList(loginList, loginArray, "login", prevLoginKeys);
    renderList(examList,  examArray,  "exam",  prevExamKeys);

    // Save for next poll
    prevLoginKeys = currentLoginKeys;
    prevExamKeys  = currentExamKeys;

  } catch (err) {
    console.error("[notifications] fetch failed", err);
  }
}

/* ----------------------------------------------------------------------------
   Start polling every 7 seconds
---------------------------------------------------------------------------- */
setInterval(pollNotifications, 7000);

// First load immediately
pollNotifications();

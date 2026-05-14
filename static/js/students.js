// static/js/students.js

document.addEventListener("DOMContentLoaded", () => {
  const subjectsBtn = document.getElementById("openSubjectsBtn");
  const subjectsBtnAlt = document.getElementById("openSubjectsBtnAlt");
  const subjectsCard = document.getElementById("availableSubjectsCard");
  const subjectsList = document.getElementById("availableSubjectsList");
  const viewSubjectsBtn = document.getElementById("viewSubjectsBtn");

  const examModal = document.getElementById("examModal");
  const openExamPortalBtn = document.getElementById("openExamPortal");
  const openExamPortalAlt = document.getElementById("openExamPortalAlt");
  const closeExamModalBtn = document.getElementById("closeExamModal");
  const closeExamModalTop = document.getElementById("closeExamModalTop");

  const subjectDropdown = document.getElementById("subjectDropdown");
  const startExamBtn = document.getElementById("startExamBtn");
  const refreshSubjectsBtn = document.getElementById("refreshSubjectsBtn");

  const liveClock = document.getElementById("liveClock");
  const footerYear = document.getElementById("year");

  let pushedSubjects = [];

  function openExamModal() {
    examModal?.classList.add("show");
  }

  function closeExamModal() {
    examModal?.classList.remove("show");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function padTime(value) {
    return String(value).padStart(2, "0");
  }

  function getGreeting(hour) {
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  }

  function createAdvancedClock() {
    if (!liveClock) return null;

    liveClock.innerHTML = `
      <span class="clock-widget">
        <span class="clock-time">
          <span class="clock-hour" id="clockHour">--</span>
          <span class="clock-separator">:</span>
          <span class="clock-minute" id="clockMinute">--</span>
          <span class="clock-separator">:</span>
          <span class="clock-second" id="clockSecond">--</span>
          <span class="clock-ampm" id="clockAmpm">--</span>
        </span>
        <span class="clock-date" id="clockDate">---</span>
      </span>
    `;

    return {
      hour: document.getElementById("clockHour"),
      minute: document.getElementById("clockMinute"),
      second: document.getElementById("clockSecond"),
      ampm: document.getElementById("clockAmpm"),
      date: document.getElementById("clockDate"),
      widget: liveClock.querySelector(".clock-widget")
    };
  }

  function updateAdvancedClock(clockParts) {
    if (!clockParts) return;

    const now = new Date();

    const hours24 = now.getHours();
    const hours12 = hours24 % 12 || 12;
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();
    const ampm = hours24 >= 12 ? "PM" : "AM";

    const day = now.toLocaleDateString([], { weekday: "short" });
    const date = now.toLocaleDateString([], {
      month: "short",
      day: "numeric"
    });

    const greeting = getGreeting(hours24);

    clockParts.hour.textContent = padTime(hours12);
    clockParts.minute.textContent = padTime(minutes);
    clockParts.second.textContent = padTime(seconds);
    clockParts.ampm.textContent = ampm;
    clockParts.date.textContent = `${day}, ${date}`;
    clockParts.widget.title = `${greeting} • ${day}, ${date}`;
  }

  function startAdvancedClock() {
    const clockParts = createAdvancedClock();

    updateAdvancedClock(clockParts);
    setInterval(() => updateAdvancedClock(clockParts), 1000);
  }

  async function fetchPushedSubjects() {
    try {
      const res = await fetch("/api/get_pushed_subjects");
      const data = await res.json();

      pushedSubjects = (data.subjects || [])
        .map((item) => {
          if (typeof item === "string") return item;
          return item.subject || "";
        })
        .filter(Boolean);

    } catch (err) {
      console.error("Error fetching pushed subjects:", err);
      pushedSubjects = [];
    }
  }

  async function loadSubjectsCard() {
    await fetchPushedSubjects();

    if (!subjectsList) return;

    subjectsList.innerHTML = "";

    if (!pushedSubjects.length) {
      subjectsList.innerHTML = `<li class="empty">No subjects pushed yet.</li>`;
    } else {
      pushedSubjects.forEach((sub) => {
        const li = document.createElement("li");
        li.innerHTML = `<i class="fa-solid fa-book"></i> ${escapeHtml(sub)}`;
        subjectsList.appendChild(li);
      });
    }

    subjectsCard?.classList.add("show");
  }

  subjectsBtn?.addEventListener("click", loadSubjectsCard);
  subjectsBtnAlt?.addEventListener("click", loadSubjectsCard);
  viewSubjectsBtn?.addEventListener("click", loadSubjectsCard);

  openExamPortalBtn?.addEventListener("click", openExamModal);
  openExamPortalAlt?.addEventListener("click", openExamModal);

  closeExamModalBtn?.addEventListener("click", closeExamModal);
  closeExamModalTop?.addEventListener("click", closeExamModal);

  examModal?.addEventListener("click", (e) => {
    if (e.target === examModal) {
      closeExamModal();
    }
  });

  subjectDropdown?.addEventListener("change", () => {
    startExamBtn.disabled = !subjectDropdown.value.trim();
  });

  refreshSubjectsBtn?.addEventListener("click", async () => {
    await loadSubjectsCard();
  });

  startExamBtn?.addEventListener("click", () => {
    const subject = subjectDropdown.value.trim();
    if (!subject) return;

    window.location.href = `/exam_dashboard?subject=${encodeURIComponent(subject)}`;
  });

  startAdvancedClock();

  if (footerYear) {
    footerYear.textContent = new Date().getFullYear();
  }
});
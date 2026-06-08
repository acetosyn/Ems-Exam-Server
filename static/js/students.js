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
  const availableSubjectsCount = document.getElementById("availableSubjectsCount");

  const metaYear = document.querySelector('meta[name="exam-year"]');
  const metaClassArm = document.querySelector('meta[name="student-class-arm"]');
  const metaClassLevel = document.querySelector('meta[name="student-class-level"]');
  const metaStream = document.querySelector('meta[name="student-stream"]');

  let pushedSubjects = [];

  function openExamModal() {
    examModal?.classList.add("show");
    refreshSubjects();
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

    const day = now.toLocaleDateString([], { weekday: "short" });
    const date = now.toLocaleDateString([], {
      month: "short",
      day: "numeric"
    });

    clockParts.hour.textContent = padTime(hours12);
    clockParts.minute.textContent = padTime(now.getMinutes());
    clockParts.second.textContent = padTime(now.getSeconds());
    clockParts.ampm.textContent = hours24 >= 12 ? "PM" : "AM";
    clockParts.date.textContent = `${day}, ${date}`;
    clockParts.widget.title = `${getGreeting(hours24)} • ${day}, ${date}`;
  }

  function startAdvancedClock() {
    const clockParts = createAdvancedClock();
    updateAdvancedClock(clockParts);
    setInterval(() => updateAdvancedClock(clockParts), 1000);
  }

  function getExamYearQuery() {
    const year = metaYear?.content?.trim();
    return year ? `?year=${encodeURIComponent(year)}` : "";
  }

function normalizeSubjectItem(item) {
  let subject = "";

  if (typeof item === "string") {
    subject = item;
  } else if (item && typeof item === "object") {
    subject = item.subject || item.name || item.title || "";
  }

  subject = String(subject || "").trim();

  subject = subject
    .replace(/[_-]/g, " ")
    .replace(/\b(JSS1|JSS2|JSS3|SS1|SS2|SS3)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  return subject.toUpperCase();
}



  function updateSubjectDropdown() {
    if (!subjectDropdown) return;

    const currentValue = subjectDropdown.value;
    subjectDropdown.innerHTML = `<option value="">-- Select Subject --</option>`;

    pushedSubjects.forEach((subject) => {
      const upperSubject = String(subject || "").toUpperCase();
      const option = document.createElement("option");
      option.value = upperSubject;
      option.textContent = upperSubject;
      subjectDropdown.appendChild(option);
    });

    if (currentValue) {
      subjectDropdown.value = currentValue;
    }

    if (!subjectDropdown.value && startExamBtn) {
      startExamBtn.disabled = true;
    }
  }

  function renderSubjectsList() {
    if (!subjectsList) return;

    subjectsList.innerHTML = "";

    if (!pushedSubjects.length) {
      subjectsList.innerHTML = `<li class="empty">No subjects available yet.</li>`;
      return;
    }

    pushedSubjects.forEach((sub) => {
      const li = document.createElement("li");
      li.innerHTML = `<i class="fa-solid fa-book"></i> ${escapeHtml(String(sub).toUpperCase())}`;
      subjectsList.appendChild(li);
    });
  }

  async function fetchPushedSubjects() {
    try {
      const res = await fetch(`/api/student/subjects${getExamYearQuery()}`);

      if (!res.ok) {
        throw new Error(`Subject API failed: ${res.status}`);
      }

      const data = await res.json();

      const seen = new Set();

      pushedSubjects = (data.subjects || [])
        .map(normalizeSubjectItem)
        .filter(Boolean)
        .filter((subject) => {
          const key = subject.toLowerCase();
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });

      if (availableSubjectsCount) {
        availableSubjectsCount.textContent = pushedSubjects.length;
      }

      if (data.class_arm && metaClassArm) {
        metaClassArm.content = data.class_arm;
      }

      if (data.class_level && metaClassLevel) {
        metaClassLevel.content = data.class_level;
      }

      if (data.stream && metaStream) {
        metaStream.content = data.stream;
      }

    } catch (err) {
      console.error("Error fetching student subjects:", err);
      pushedSubjects = [];
    }
  }
  

  async function refreshSubjects() {
    await fetchPushedSubjects();
    renderSubjectsList();
    updateSubjectDropdown();
  }

  async function loadSubjectsCard() {
    await refreshSubjects();
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
    if (startExamBtn) {
      startExamBtn.disabled = !subjectDropdown.value.trim();
    }
  });

  refreshSubjectsBtn?.addEventListener("click", loadSubjectsCard);

  startExamBtn?.addEventListener("click", () => {
    const subject = subjectDropdown?.value?.trim();

    if (!subject) return;

    const year = metaYear?.content?.trim();
    const params = new URLSearchParams();
    params.set("subject", subject);

    if (year) {
      params.set("year", year);
    }

    window.location.href = `/exam_dashboard?${params.toString()}`;
  });

  startAdvancedClock();

  if (footerYear) {
    footerYear.textContent = new Date().getFullYear();
  }

  refreshSubjects();
});
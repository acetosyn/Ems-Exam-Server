// hour-glass.js — Current date/time + countdown timer

let totalExamSeconds = 60 * 60;
let remainingSeconds = totalExamSeconds;
let timerInterval = null;
let clockInterval = null;

function padTime(value) {
  return String(value).padStart(2, "0");
}

function getOrdinalSuffix(day) {
  if (day > 3 && day < 21) return "th";

  switch (day % 10) {
    case 1:
      return "st";
    case 2:
      return "nd";
    case 3:
      return "rd";
    default:
      return "th";
  }
}

function formatFullDate(date) {
  const weekday = date.toLocaleDateString([], { weekday: "long" });
  const month = date.toLocaleDateString([], { month: "long" });
  const day = date.getDate();
  const year = date.getFullYear();

  return `${weekday}, ${day}${getOrdinalSuffix(day)} ${month} ${year}`;
}

function formatCurrentTime(date) {
  let hours = date.getHours();
  const minutes = date.getMinutes();
  const seconds = date.getSeconds();
  const ampm = hours >= 12 ? "PM" : "AM";

  hours = hours % 12 || 12;

  return `${padTime(hours)}:${padTime(minutes)}:${padTime(seconds)} ${ampm}`;
}

function updateCurrentDateTime() {
  const dateEl = document.getElementById("examCurrentDate");
  const timeEl = document.getElementById("examCurrentTime");

  if (!dateEl && !timeEl) return;

  const now = new Date();

  if (dateEl) {
    dateEl.textContent = formatFullDate(now);
  }

  if (timeEl) {
    timeEl.textContent = formatCurrentTime(now);
  }
}

function startCurrentDateTimeClock() {
  updateCurrentDateTime();

  clearInterval(clockInterval);
  clockInterval = setInterval(updateCurrentDateTime, 1000);
}

function startTimer(durationSeconds) {
  if (isNaN(durationSeconds) || durationSeconds <= 0) {
    console.error("Invalid timer duration:", durationSeconds);
    return;
  }

  totalExamSeconds = durationSeconds;
  remainingSeconds = durationSeconds;

  const timerDisplay = document.getElementById("timerDisplay");
  updateTimerDisplay(timerDisplay, remainingSeconds);

  clearInterval(timerInterval);

  timerInterval = setInterval(() => {
    remainingSeconds--;

    updateTimerDisplay(timerDisplay, remainingSeconds);

    if (remainingSeconds <= 0) {
      clearInterval(timerInterval);

      if (typeof endExam === "function") {
        endExam();
      } else if (typeof submitExam === "function") {
        submitExam(false);
      } else {
        console.error("No endExam() or submitExam() function found.");
      }
    }
  }, 1000);
}

function updateTimerDisplay(displayEl, seconds) {
  if (!displayEl) return;

  const safeSeconds = Math.max(0, seconds);
  const hours = Math.floor(safeSeconds / 3600);
  const mins = Math.floor((safeSeconds % 3600) / 60);
  const secs = safeSeconds % 60;

  if (hours > 0) {
    displayEl.textContent = `${padTime(hours)}:${padTime(mins)}:${padTime(secs)}`;
  } else {
    displayEl.textContent = `${padTime(mins)}:${padTime(secs)}`;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  startCurrentDateTimeClock();

  const startBtn = document.getElementById("startExamBtn");

  if (startBtn) {
    startBtn.addEventListener("click", () => {
      startTimer(60 * 60);
    });
  }

  const examAlreadyStarted = document.body.classList.contains("exam-started");
  const timerDisplay = document.getElementById("timerDisplay");

  if (examAlreadyStarted && timerDisplay && timerDisplay.textContent.trim() === "00:00") {
    updateTimerDisplay(timerDisplay, remainingSeconds);
  }
});
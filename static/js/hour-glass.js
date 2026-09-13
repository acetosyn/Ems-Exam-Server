// ======================================================
// hour-glass.js — EMIS CURRENT DATE / TIME DISPLAY
//
// IMPORTANT:
// Examination countdown is owned exclusively by exam-core.js.
// This file must NOT create, reset or submit the exam timer.
// ======================================================

(() => {
  let clockInterval = null;

  const padTime = (value) => String(value).padStart(2, "0");

  function getOrdinalSuffix(day) {
    if (day > 3 && day < 21) return "th";

    switch (day % 10) {
      case 1: return "st";
      case 2: return "nd";
      case 3: return "rd";
      default: return "th";
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

    if (dateEl) dateEl.textContent = formatFullDate(now);
    if (timeEl) timeEl.textContent = formatCurrentTime(now);
  }

  function startCurrentDateTimeClock() {
    updateCurrentDateTime();

    if (clockInterval) clearInterval(clockInterval);

    clockInterval = setInterval(updateCurrentDateTime, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startCurrentDateTimeClock);
  } else {
    startCurrentDateTimeClock();
  }
})();
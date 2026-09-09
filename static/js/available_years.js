/* ==========================================================
   EMIS — AVAILABLE EXAM YEARS
   Dynamic year badges + synchronized year selectors
========================================================== */

(() => {
  if (window.__EMIS_AVAILABLE_YEARS__) return;
  window.__EMIS_AVAILABLE_YEARS__ = true;

  const ENDPOINT = "/api/available-years";

  function safeJsonParse(text) {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  }

  function getYearSelectors() {
    return [
      document.getElementById("yearSelectorUploads"),
      document.getElementById("pushYearSelector"),
      document.getElementById("subjectsModalYear")
    ].filter(Boolean);
  }

  function ensureYearOption(select, year) {
    if (!select || !year) return;

    const yearValue = String(year);
    const exists = [...select.options].some((option) => String(option.value) === yearValue);

    if (exists) return;

    const option = document.createElement("option");
    option.value = yearValue;
    option.textContent = yearValue;
    select.appendChild(option);
  }

  function setSelectValue(select, year) {
    if (!select || !year) return false;

    const yearValue = String(year);

    ensureYearOption(select, yearValue);

    // Do not fire another change event if this selector
    // is already using the requested year.
    if (String(select.value) === yearValue) return false;

    select.value = yearValue;
    select.dispatchEvent(new Event("change", { bubbles: true }));

    return true;
  }

  function autoSelectYear(year) {
    if (!year) return;

    let changed = false;

    getYearSelectors().forEach((select) => {
      if (setSelectValue(select, year)) changed = true;
    });

    if (changed && typeof flashMessage === "function") flashMessage(`Selected exam year ${year}`, "success");
  }

  function setActiveBadge(container, year) {
    if (!container) return;

    container.querySelectorAll(".year-badge").forEach((badge) => {
      badge.classList.toggle("active", String(badge.dataset.year) === String(year));
    });
  }

  function renderYears(container, years) {
    container.innerHTML = "";

    years.forEach((year) => {
      const badge = document.createElement("button");

      badge.type = "button";
      badge.className = "year-badge";
      badge.dataset.year = String(year);
      badge.textContent = year;
      badge.title = `Load ${year} JSON exams`;

      badge.addEventListener("click", () => {
        autoSelectYear(year);
        setActiveBadge(container, year);
      });

      container.appendChild(badge);
    });
  }

  async function loadAvailableYears() {
    const container = document.getElementById("availableYearsList");

    if (!container) return;

    container.innerHTML = `<span class="year-loading">Loading…</span>`;

    try {
      const url = `${ENDPOINT}?_ts=${Date.now()}`;

      const res = await fetch(url, {
        method: "GET",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Cache-Control": "no-cache",
          Pragma: "no-cache"
        }
      });

      const text = await res.text();

      if (text.trim().startsWith("<")) {
        console.error("Expected JSON, got HTML:", text);
        container.innerHTML = `<span class="year-error">Route / auth error</span>`;
        return;
      }

      const data = safeJsonParse(text);

      if (!res.ok || !data) {
        container.innerHTML = `<span class="year-error">Failed to load</span>`;
        return;
      }

      const years = Array.isArray(data.years)
        ? [...new Set(data.years.map(Number).filter(Boolean))].sort((a, b) => b - a)
        : [];

      if (!years.length) {
        container.innerHTML = `<span class="year-empty">No available years</span>`;
        return;
      }

      renderYears(container, years);

      const currentYear = document.getElementById("yearSelectorUploads")?.value;

      if (currentYear) setActiveBadge(container, currentYear);

      window.EmisAvailableYears = {
        years,
        latest: years[0],
        reload: loadAvailableYears,
        select: autoSelectYear
      };

    } catch (error) {
      console.error("Failed to load available years:", error);
      container.innerHTML = `<span class="year-error">Failed to load</span>`;
    }
  }

  function waitForContainer(retries = 80) {
    const container = document.getElementById("availableYearsList");

    if (container) {
      loadAvailableYears();
      return;
    }

    if (retries <= 0) return;

    setTimeout(() => waitForContainer(retries - 1), 100);
  }

  waitForContainer();
})();
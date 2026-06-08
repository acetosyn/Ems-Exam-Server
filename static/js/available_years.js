/* ==========================================================
   EMIS — Available WAEC Years
   Dynamic year badges + auto-select support
========================================================== */

(function () {
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
      document.getElementById("subjectsModalYear"),
    ].filter(Boolean);
  }

  function setSelectValue(select, year) {
    if (!select || !year) return;

    const exists = [...select.options].some((opt) => String(opt.value) === String(year));

    if (!exists) {
      const opt = document.createElement("option");
      opt.value = year;
      opt.textContent = year;
      select.appendChild(opt);
    }

    select.value = year;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function autoSelectYear(year) {
    getYearSelectors().forEach((select) => setSelectValue(select, year));

    if (typeof flashMessage === "function") {
      flashMessage(`Selected exam year ${year}`, "success");
    }
  }

  function renderYears(container, years) {
    container.innerHTML = "";

    years.forEach((year) => {
      const badge = document.createElement("button");
      badge.type = "button";
      badge.className = "year-badge";
      badge.textContent = year;
      badge.title = `Load ${year} JSON exams`;

      badge.addEventListener("click", () => {
        autoSelectYear(year);

        container.querySelectorAll(".year-badge").forEach((b) => {
          b.classList.remove("active");
        });

        badge.classList.add("active");
      });

      container.appendChild(badge);
    });
  }

  async function loadAvailableYears() {
    const container = document.getElementById("availableYearsList");
    if (!container) return;

    container.innerHTML = `<span class="year-loading">Loading…</span>`;

    try {
      const res = await fetch(ENDPOINT, {
        headers: { Accept: "application/json" },
        cache: "no-store",
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
        ? data.years.map(Number).filter(Boolean).sort((a, b) => b - a)
        : [];

      if (!years.length) {
        container.innerHTML = `<span class="year-empty">No available years</span>`;
        return;
      }

      renderYears(container, years);

      window.EmisAvailableYears = {
        years,
        latest: years[0],
        reload: loadAvailableYears,
        select: autoSelectYear,
      };

    } catch (err) {
      console.error("Failed to load available years", err);
      container.innerHTML = `<span class="year-error">Failed to load</span>`;
    }
  }

  function waitForContainer(retries = 80) {
    const el = document.getElementById("availableYearsList");

    if (el) {
      loadAvailableYears();
      return;
    }

    if (retries <= 0) return;

    setTimeout(() => waitForContainer(retries - 1), 100);
  }

  waitForContainer();
})();
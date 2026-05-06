/* ==========================================================
   EMIS — Available WAEC Years (Header Card)
   Source: GET /api/available-years
========================================================== */

(function () {
  if (window.__EMIS_AVAILABLE_YEARS__) return;
  window.__EMIS_AVAILABLE_YEARS__ = true;

  async function loadAvailableYears() {
    const container = document.getElementById("availableYearsList");
    if (!container) return;

    container.innerHTML = `<span class="year-loading">Loading…</span>`;

    try {
      // ✅ CORRECT ENDPOINT (matches app.py)
      const res = await fetch("/api/available-years");

      // Defensive check — prevents HTML → JSON crash
      const text = await res.text();
      if (text.startsWith("<")) {
        console.error("Expected JSON, got HTML:", text);
        container.innerHTML =
          `<span class="year-error">Route / auth error</span>`;
        return;
      }

      const data = JSON.parse(text);

      container.innerHTML = "";

      if (!data.years || data.years.length === 0) {
        container.innerHTML =
          `<span class="year-empty">No available years</span>`;
        return;
      }

      data.years.forEach((year) => {
        const badge = document.createElement("span");
        badge.className = "year-badge";
        badge.textContent = year;

        // 🔮 Optional future enhancement:
        // badge.onclick = () => autoSelectYear(year);

        container.appendChild(badge);
      });
    } catch (err) {
      console.error("Failed to load available years", err);
      container.innerHTML =
        `<span class="year-error">Failed to load</span>`;
    }
  }

  /*
    Because uploads.html is dynamically injected
    (inside teachers.html), we retry once the element appears.
  */
  function waitForContainer() {
    const el = document.getElementById("availableYearsList");
    if (el) {
      loadAvailableYears();
    } else {
      setTimeout(waitForContainer, 100);
    }
  }

  waitForContainer();
})();

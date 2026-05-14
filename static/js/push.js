/* ======================================================================
   EMIS PUSH — JSS1–SS3 PORTAL PUSH SYSTEM
   Supports:
     ✓ JSS1 / JSS2 / JSS3 / SS1 / SS2 / SS3
     ✓ Per-class active years
     ✓ Push selected files
     ✓ Push all filtered files
     ✓ Clear by class or ALL
====================================================================== */

(() => {
  if (window.__EMIS_PUSH_BOUND__) return;
  window.__EMIS_PUSH_BOUND__ = true;

  window.EmisPush = {
    selectedClass: null,

    supportedClasses: ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"],

    normalizeClass(cls) {
      return String(cls || "").toUpperCase().trim();
    },

    init() {
      const btnPush = document.querySelector("#pushSelectedToPortal");
      const btnClear = document.querySelector("#clearPortalSubjects");
      const btnPushAll = document.querySelector("#btnPushAllSubjects");

      const modalPush = document.querySelector("#pushClassModal");
      const modalClear = document.querySelector("#clearPortalModal");

      const confirmPush = document.querySelector("#btnConfirmPush");
      const pushYearSel = document.querySelector("#pushYearSelector");

      const logBody = document.querySelector("#portalLogBody");
      const activeYearLabel = document.getElementById("activeYearLabel");

      if (!btnPush || !modalPush || !confirmPush || !pushYearSel) return;

      const pushClassBtns = modalPush.querySelectorAll(".class-btn");
      const clearClassBtns = modalClear?.querySelectorAll(".clear-btn");

      const log = (msg, type = "info") => {
        if (!logBody) return;

        const placeholder = logBody.querySelector(".log-placeholder");
        if (placeholder) logBody.innerHTML = "";

        const p = document.createElement("p");

        if (type === "success") {
          p.innerHTML = `<span class="lg-success">✔</span> ${msg}`;
        } else if (type === "error") {
          p.innerHTML = `<span class="lg-error">✖</span> ${msg}`;
        } else {
          p.innerHTML = `<span class="lg-info">•</span> ${msg}`;
        }

        logBody.appendChild(p);
        logBody.scrollTop = logBody.scrollHeight;
      };

      const logSuccess = (msg) => log(msg, "success");
      const logError = (msg) => log(msg, "error");
      const logInfo = (msg) => log(msg, "info");

      const showMessage = (msg, type = "success") => {
        if (typeof flashMessage === "function") {
          flashMessage(msg, type);
        } else {
          console[type === "error" ? "error" : "log"](msg);
        }
      };

      const updatePushCount = () => {
        if (window.EmisUploads?.updatePushCount) {
          window.EmisUploads.updatePushCount();
          return;
        }

        const el = document.getElementById("pushCount");
        if (el && window.EmisUploads?.selectedFiles) {
          el.textContent = window.EmisUploads.selectedFiles.size;
        }
      };

      const updateActiveYearLabel = (year, classActiveYears = null) => {
        if (!activeYearLabel) return;

        if (!year || year === "Select Year") {
          activeYearLabel.textContent = "Active Year: —";
          activeYearLabel.classList.add("year-empty");
        } else {
          activeYearLabel.textContent = `Latest Active Year: ${year}`;
          activeYearLabel.classList.remove("year-empty");
        }

        if (classActiveYears && typeof classActiveYears === "object") {
          const parts = Object.entries(classActiveYears)
            .map(([cls, yr]) => `${cls}: ${yr}`)
            .join(" • ");

          if (parts) {
            activeYearLabel.title = parts;
          }
        }

        activeYearLabel.classList.remove("year-pulse");
        void activeYearLabel.offsetWidth;
        activeYearLabel.classList.add("year-pulse");
      };

      const autoFetchLatestYear = async () => {
        try {
          const res = await fetch("/api/push_latest_year");
          const data = await res.json();

          const latest = data?.year || data?.latest_year || "";
          const classActiveYears = data?.class_active_years || {};

          updateActiveYearLabel(latest, classActiveYears);

          if (!pushYearSel.value || pushYearSel.value === "Select Year") {
            if (latest) pushYearSel.value = latest;
          }

        } catch (err) {
          console.warn("Year sync error:", err);
        }
      };

      autoFetchLatestYear();

      pushYearSel.onchange = () => {
        updateActiveYearLabel(pushYearSel.value);
      };

      const resetPushModal = () => {
        this.selectedClass = null;

        confirmPush.disabled = true;
        confirmPush.classList.add("disabled");

        const chosen = modalPush.querySelector("#chosenPushClass");
        if (chosen) {
          chosen.textContent = "";
          chosen.classList.add("hidden");
        }
      };

      const closePushModal = () => {
        modalPush.classList.add("hidden");
        resetPushModal();
      };

      const closeClearModal = () => {
        modalClear?.classList.add("hidden");
      };

      modalPush.querySelectorAll('[data-close="true"]').forEach((el) => {
        el.onclick = closePushModal;
      });

      modalClear?.querySelectorAll('[data-close="true"]').forEach((el) => {
        el.onclick = closeClearModal;
      });

      btnPush.onclick = () => {
        const year = pushYearSel.value;

        if (!year || year === "Select Year") {
          showMessage("Select a year first.", "error");
          return;
        }

        if (!window.EmisUploads?.selectedFiles?.size) {
          showMessage("No files selected.", "error");
          return;
        }

        modalPush.classList.remove("hidden");
      };

      pushClassBtns.forEach((btn) => {
        btn.onclick = () => {
          const cls = this.normalizeClass(btn.dataset.class);

          if (!this.supportedClasses.includes(cls)) {
            showMessage("Invalid class selected.", "error");
            return;
          }

          this.selectedClass = cls;

          confirmPush.disabled = false;
          confirmPush.classList.remove("disabled");

          const chosen = modalPush.querySelector("#chosenPushClass");
          if (chosen) {
            chosen.textContent = `Selected Class: ${this.selectedClass}`;
            chosen.classList.remove("hidden");
          }
        };
      });

      confirmPush.onclick = async () => {
        const cls = this.normalizeClass(this.selectedClass);
        const files = [...(window.EmisUploads?.selectedFiles || [])];

        if (!cls || !this.supportedClasses.includes(cls)) {
          showMessage("Select a valid class.", "error");
          return;
        }

        if (!files.length) {
          showMessage("No files selected.", "error");
          return;
        }

        closePushModal();

        try {
          logInfo(`Pushing ${files.length} file(s) to ${cls}...`);

          const res = await fetch("/api/push", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              files,
              class_category: cls
            }),
          });

          const out = await res.json();

          if (!res.ok || !out.success) {
            throw new Error(out.error || "Push failed");
          }

          const count = out.subjects_pushed?.length || 0;

          showMessage(`Pushed ${count} subject(s) to ${cls}.`, "success");
          logSuccess(`Pushed ${count} subject(s) → ${cls}`);

          if (window.EmisUploads?.selectedFiles) {
            window.EmisUploads.selectedFiles.clear();
          }

          updatePushCount();

          updateActiveYearLabel(
            out.latest_year || out.active_year || "",
            out.class_active_years || null
          );

        } catch (err) {
          console.error("Push error:", err);
          showMessage("Push failed.", "error");
          logError(err.message || "Push failed.");
        }
      };

      btnClear.onclick = () => {
        const year = pushYearSel.value;

        if (!year || year === "Select Year") {
          showMessage("Select a year first.", "error");
          return;
        }

        modalClear?.classList.remove("hidden");
      };

      clearClassBtns?.forEach((btn) => {
        btn.onclick = async () => {
          const clsRaw = this.normalizeClass(btn.dataset.class);
          const cls = clsRaw === "ALL" ? "ALL" : clsRaw;
          const year = pushYearSel.value;

          if (!year || year === "Select Year") {
            showMessage("Select a year first.", "error");
            return;
          }

          if (cls !== "ALL" && !this.supportedClasses.includes(cls)) {
            showMessage("Invalid class selected.", "error");
            return;
          }

          closeClearModal();

          try {
            logInfo(`Clearing ${year} / ${cls}...`);

            const res = await fetch("/api/clear", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                year,
                class_category: cls
              }),
            });

            const out = await res.json();

            if (!res.ok || !out.success) {
              throw new Error(out.error || "Clear failed");
            }

            showMessage(`Cleared: ${out.cleared}`, "success");
            logSuccess(`Cleared ${out.cleared}`);

            updateActiveYearLabel(
              out.latest_year || "",
              out.class_active_years || null
            );

          } catch (err) {
            console.error("Clear error:", err);
            showMessage("Clear failed.", "error");
            logError(err.message || "Clear failed.");
          }
        };
      });

      if (btnPushAll) {
        btnPushAll.onclick = () => {
          const year = pushYearSel.value;

          if (!year || year === "Select Year") {
            showMessage("Select a year first.", "error");
            return;
          }

          if (!window.EmisUploads?.convertedItems?.length) {
            showMessage("No subjects found for this year.", "error");
            return;
          }

          let items = window.EmisUploads.convertedItems;

          if (
            window.EmisUploads.activeClass &&
            window.EmisUploads.activeClass !== "ALL"
          ) {
            items = items.filter((it) => {
              return this.normalizeClass(it.class_category) === window.EmisUploads.activeClass;
            });
          }

          if (!items.length) {
            showMessage("No subjects found for the selected class.", "error");
            return;
          }

          window.EmisUploads.selectedFiles.clear();

          items.forEach((it) => {
            window.EmisUploads.selectedFiles.add(`${year}:${it.filename}`);
          });

          updatePushCount();

          modalPush.classList.remove("hidden");
          showMessage("Select a class to push selected subject(s).", "info");
          logInfo(`Queued ${items.length} file(s) from ${year}.`);
        };
      }
    },
  };

  const autoInitPush = () => {
    const wrap = document.querySelector(".uploads-wrapper");
    if (!wrap || wrap.__push_initialized__) return;

    wrap.__push_initialized__ = true;
    window.EmisPush.init();
  };

  if (["complete", "interactive"].includes(document.readyState)) {
    autoInitPush();
  } else {
    document.addEventListener("DOMContentLoaded", autoInitPush);
  }

  new MutationObserver(autoInitPush).observe(document.body, {
    childList: true,
    subtree: true
  });
})();
/* ======================================================================
   EMIS PUSH — push.js (v14 ULTRA OPTIMIZED — Architect Edition 2025)
   FEATURES:
     ✓ Premium Active Year Sync (auto-fetch)
     ✓ Intelligent Logs (info/success/error)
     ✓ No-subjects-pushed detection
     ✓ Automatic HUD refresh
     ✓ Safer modal handling
     ✓ Full compatibility with push.py FINAL
====================================================================== */

(() => {
  window.EmisPush = {
    selectedClass: null,

    /* ==========================================================
       INIT
    ========================================================== */
    init() {
      const btnPush     = document.querySelector("#pushSelectedToPortal");
      const btnClear    = document.querySelector("#clearPortalSubjects");
      const btnPushAll  = document.querySelector("#btnPushAllSubjects");
      const modalPush   = document.querySelector("#pushClassModal");
      const modalClear  = document.querySelector("#clearPortalModal");
      const confirmPush = document.querySelector("#btnConfirmPush");
      const pushYearSel = document.querySelector("#pushYearSelector");
      const logBody     = document.querySelector("#portalLogBody");
      const activeYearLabel = document.getElementById("activeYearLabel");

      if (!btnPush || !modalPush || !confirmPush || !pushYearSel) return;

      const pushClassBtns  = modalPush.querySelectorAll(".class-btn");
      const clearClassBtns = modalClear?.querySelectorAll(".clear-btn");

      /* ==========================================================
         LOG SYSTEM (v14)
      ========================================================== */
      const log = (msg, type = "info") => {
        if (!logBody) return;
        const placeholder = logBody.querySelector(".log-placeholder");
        if (placeholder) logBody.innerHTML = "";

        const p = document.createElement("p");

        if (type === "success") p.innerHTML = `<span class="lg-success">✔</span> ${msg}`;
        else if (type === "error") p.innerHTML = `<span class="lg-error">✖</span> ${msg}`;
        else p.innerHTML = `<span class="lg-info">•</span> ${msg}`;

        logBody.appendChild(p);
        logBody.scrollTop = logBody.scrollHeight;
      };

      const logInfo = (msg) => log(msg, "info");
      const logSuccess = (msg) => log(msg, "success");
      const logError = (msg) => log(msg, "error");

      /* ==========================================================
         UI: UPDATE ACTIVE YEAR LABEL
      ========================================================== */
      const updateActiveYearLabel = (year) => {
        if (!activeYearLabel) return;

        if (!year || year === "Select Year") {
          activeYearLabel.textContent = "Active Year: —";
          activeYearLabel.classList.add("year-empty");
        } else {
          activeYearLabel.textContent = `Active Year: ${year}`;
          activeYearLabel.classList.remove("year-empty");
        }

        activeYearLabel.classList.remove("year-pulse");
        void activeYearLabel.offsetWidth;
        activeYearLabel.classList.add("year-pulse");
      };

      /* ==========================================================
         AUTO-FETCH TRUE LATEST YEAR FROM BACKEND (v14 NEW!)
      ========================================================== */
      const autoFetchLatestYear = async () => {
        try {
          const res = await fetch("/api/push_latest_year");
          const data = await res.json();

          const latest = data?.year || "";

          updateActiveYearLabel(latest);

          // Auto-set dropdown if empty
          if (!pushYearSel.value || pushYearSel.value === "Select Year") {
            if (latest) pushYearSel.value = latest;
          }

        } catch (err) {
          console.warn("Year sync error:", err);
        }
      };

      autoFetchLatestYear();

      /* ==========================================================
         YEAR DROPDOWN CHANGE
      ========================================================== */
      pushYearSel.onchange = () => {
        updateActiveYearLabel(pushYearSel.value);
      };

      /* ==========================================================
         RESET MODALS
      ========================================================== */
      const resetPushModal = () => {
        this.selectedClass = null;
        confirmPush.disabled = true;
        confirmPush.classList.add("disabled");

        const chosen = modalPush.querySelector("#chosenPushClass");
        chosen.textContent = "";
        chosen.classList.add("hidden");
      };

      const closePushModal = () => {
        modalPush.classList.add("hidden");
        resetPushModal();
      };

      const closeClearModal = () => modalClear?.classList.add("hidden");

      modalPush.querySelectorAll('[data-close="true"]').forEach((el) => {
        el.onclick = closePushModal;
      });
      modalClear?.querySelectorAll('[data-close="true"]').forEach((el) => {
        el.onclick = closeClearModal;
      });

      /* ==========================================================
         OPEN PUSH MODAL
      ========================================================== */
      btnPush.onclick = () => {
        const year = pushYearSel.value;
        if (!year || year === "Select Year") {
          flashMessage("Select a year first.", "error");
          return;
        }
        if (!EmisUploads.selectedFiles.size) {
          flashMessage("No files selected.", "error");
          return;
        }
        modalPush.classList.remove("hidden");
      };

      /* ==========================================================
         SELECT CLASS
      ========================================================== */
      pushClassBtns.forEach((btn) => {
        btn.onclick = () => {
          this.selectedClass = btn.dataset.class;
          confirmPush.disabled = false;
          confirmPush.classList.remove("disabled");

          const chosen = modalPush.querySelector("#chosenPushClass");
          chosen.textContent = `Selected Class: ${this.selectedClass}`;
          chosen.classList.remove("hidden");
        };
      });

      /* ==========================================================
         CONFIRM PUSH
      ========================================================== */
      confirmPush.onclick = async () => {
        const cls = this.selectedClass;
        const files = [...EmisUploads.selectedFiles];

        closePushModal();

        const res = await fetch("/api/push", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ files, class_category: cls }),
        });

        const out = await res.json();

        if (!out.success) {
          flashMessage("Push failed", "error");
          logError("Push failed — backend returned unsuccessful response.");
          return;
        }

        flashMessage(`Pushed ${out.subjects_pushed.length} subject(s) to ${cls}.`);
        logSuccess(`Pushed ${out.subjects_pushed.length} → ${cls}`);

        EmisUploads.selectedFiles.clear();
        if (window.updatePushCount) updatePushCount();

        updateActiveYearLabel(out.latest_year);
      };

      /* ==========================================================
         OPEN CLEAR MODAL
      ========================================================== */
      btnClear.onclick = () => {
        const year = pushYearSel.value;
        if (!year || year === "Select Year") {
          flashMessage("Select a year first.", "error");
          return;
        }
        modalClear.classList.remove("hidden");
      };

      /* ==========================================================
         CLEAR SUBJECTS (YEAR + CLASS + ALL)
      ========================================================== */
      clearClassBtns?.forEach((btn) => {
        btn.onclick = async () => {
          const cls  = btn.dataset.class;
          const year = pushYearSel.value;

          closeClearModal();

          const res = await fetch("/api/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ year, class_category: cls }),
          });

          const out = await res.json();

          if (out.success) {
            flashMessage(`Cleared: ${out.cleared}`, "success");
            logSuccess(`Cleared ${out.cleared}`);
            updateActiveYearLabel(out.latest_year || "");
          } else {
            flashMessage("Clear failed.", "error");
            logError(`Clear failed: ${out.error}`);
          }
        };
      });

      /* ==========================================================
         PUSH ALL SUBJECTS
      ========================================================== */
      if (btnPushAll) {
        btnPushAll.onclick = () => {
          const year = pushYearSel.value;

          if (!year || year === "Select Year") {
            flashMessage("Select a year first.", "error");
            return;
          }

          if (!EmisUploads.convertedItems.length) {
            flashMessage("No subjects found for this year.", "error");
            return;
          }

          modalPush.classList.remove("hidden");
          flashMessage("Select a class to push ALL subjects.", "info");

          EmisUploads.selectedFiles.clear();
          EmisUploads.convertedItems.forEach((it) => {
            EmisUploads.selectedFiles.add(`${year}:${it.filename}`);
          });

          if (window.updatePushCount) updatePushCount();
        };
      }
    },
  };
})();

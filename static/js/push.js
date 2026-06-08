/* ======================================================================
   EMIS PUSH — YEAR + CLASS ARM PORTAL PUSH SYSTEM
   Fixed for right-side Push Target panel
====================================================================== */

(() => {
  if (window.__EMIS_PUSH_BOUND__) return;
  window.__EMIS_PUSH_BOUND__ = true;

  window.EmisPush = {
    supportedClasses: ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"],

    classArms: {
      JSS1: ["JSS1A", "JSS1B", "JSS1C"],
      JSS2: ["JSS2A", "JSS2B", "JSS2C"],
      JSS3: ["JSS3A", "JSS3B", "JSS3C"],
      SS1: ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1B"],
      SS2: ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2B"],
      SS3: ["SS3_GOLD", "SS3_SILVER", "SS3_DIAMOND", "SS3B"],
    },

    normalize(value) {
      return String(value || "").toUpperCase().trim().replaceAll("-", "_");
    },

    normalizeClassLevel(value) {
      const compact = this.normalize(value).replaceAll("_", "").replaceAll(" ", "");

      for (const cls of this.supportedClasses) {
        if (compact === cls || compact.startsWith(cls)) return cls;
      }

      return "";
    },

    normalizeClassArm(value, fallbackLevel = "") {
      const raw = this.normalize(value);
      const compact = raw.replaceAll("_", "").replaceAll(" ", "");
      const level = this.normalizeClassLevel(raw) || this.normalizeClassLevel(fallbackLevel);

      if (!level) return "";

      if (level.startsWith("JSS")) {
        for (const arm of ["A", "B", "C"]) {
          if (compact === `${level}${arm}`) return `${level}${arm}`;
        }
        return level;
      }

      for (const label of ["GOLD", "SILVER", "DIAMOND"]) {
        if (compact.includes(label)) return `${level}_${label}`;
      }

      if (compact === `${level}B`) return `${level}B`;

      return level;
    },

    isValidTarget(classLevel, classArm) {
      if (!classLevel || !classArm) return false;
      if (!this.supportedClasses.includes(classLevel)) return false;
      if (classArm === classLevel) return true;
      return (this.classArms[classLevel] || []).includes(classArm);
    },

    showPushConfirm({ year, classArm, count }) {
  return new Promise((resolve) => {
    const modal = document.querySelector("#pushConfirmModal");
    const text = document.querySelector("#pushConfirmText");
    const yearEl = document.querySelector("#pushConfirmYear");
    const targetEl = document.querySelector("#pushConfirmTarget");
    const countEl = document.querySelector("#pushConfirmCount");
    const cancelBtn = document.querySelector("#cancelPushConfirm");
    const acceptBtn = document.querySelector("#acceptPushConfirm");
    const backdrop = modal?.querySelector(".push-confirm-backdrop");

    if (!modal) {
      resolve(confirm(`Push ${count} subject(s) to ${classArm}?`));
      return;
    }

    if (text) text.textContent = `You are about to publish selected exam JSON files to ${classArm}.`;
    if (yearEl) yearEl.textContent = `Year: ${year}`;
    if (targetEl) targetEl.textContent = `Target: ${classArm}`;
    if (countEl) countEl.textContent = `Subjects: ${count}`;

    modal.classList.remove("hidden");

    const close = (answer) => {
      modal.classList.add("hidden");

      cancelBtn?.removeEventListener("click", onCancel);
      acceptBtn?.removeEventListener("click", onAccept);
      backdrop?.removeEventListener("click", onCancel);

      resolve(answer);
    };

    const onCancel = () => close(false);
    const onAccept = () => close(true);

    cancelBtn?.addEventListener("click", onCancel);
    acceptBtn?.addEventListener("click", onAccept);
    backdrop?.addEventListener("click", onCancel);
  });
},

    init() {
      const btnPush = document.querySelector("#pushSelectedToPortal");
      const btnClear = document.querySelector("#clearPortalSubjects");
      const btnPushAll = document.querySelector("#btnPushAllSubjects");

      const pushYearSel = document.querySelector("#pushYearSelector");
      const pushClassLevel = document.querySelector("#pushClassLevel");
      const pushClassArm = document.querySelector("#pushClassArm");

      const logBody = document.querySelector("#portalLogBody");
      const activeYearLabel = document.querySelector("#activeYearLabel");

      if (!btnPush || !pushYearSel || !pushClassLevel || !pushClassArm) return;

      const showMessage = (msg, type = "success") => {
        if (typeof flashMessage === "function") {
          flashMessage(msg, type);
        } else {
          alert(msg);
        }
      };

      const log = (msg, type = "info") => {
        if (!logBody) return;

        const placeholder = logBody.querySelector(".log-placeholder");
        if (placeholder) logBody.innerHTML = "";

        const p = document.createElement("p");
        p.className = `push-log ${type}`;
        p.innerHTML = msg;
        logBody.appendChild(p);
        logBody.scrollTop = logBody.scrollHeight;
      };

      const updatePushCount = () => {
        const count = window.EmisUploads?.selectedFiles?.size || 0;

        const pushCount = document.querySelector("#pushCount");
        const pushCountSide = document.querySelector("#pushCountSide");

        if (pushCount) pushCount.textContent = count;
        if (pushCountSide) pushCountSide.textContent = count;

        if (window.EmisUploads?.updatePushCount) {
          window.EmisUploads.updatePushCount();
        }
      };

      const buildArmOptions = (classLevel) => {
        if (!classLevel) {
          pushClassArm.innerHTML = `<option value="">Select class first</option>`;
          return;
        }

        const arms = this.classArms[classLevel] || [];

        pushClassArm.innerHTML = `
          <option value="">Select Arm / Group</option>
          <option value="${classLevel}">${classLevel} — Whole Class Level</option>
          ${arms.map((arm) => `<option value="${arm}">${arm}</option>`).join("")}
        `;
      };

      const updateActiveYearLabel = (year, activeMap = null) => {
        if (!activeYearLabel) return;

        if (!year) {
          activeYearLabel.textContent = "Active Year: —";
        } else {
          activeYearLabel.textContent = `Active Year: ${year}`;
        }

        if (activeMap && typeof activeMap === "object") {
          activeYearLabel.title = Object.entries(activeMap)
            .map(([target, yr]) => `${target}: ${yr}`)
            .join(" • ");
        }
      };

      const fetchLatestYear = async () => {
        try {
          const res = await fetch("/api/push_latest_year");
          const data = await res.json();

          updateActiveYearLabel(
            data.latest_year || data.year || "",
            data.class_active_years || {}
          );
        } catch (err) {
          console.warn("Latest year fetch failed:", err);
        }
      };

      pushClassLevel.addEventListener("change", () => {
        const level = this.normalizeClassLevel(pushClassLevel.value);
        buildArmOptions(level);
      });

      btnPush.addEventListener("click", async () => {
        const year = pushYearSel.value;
        const classLevel = this.normalizeClassLevel(pushClassLevel.value);
        const classArm = this.normalizeClassArm(pushClassArm.value, classLevel);
        const files = [...(window.EmisUploads?.selectedFiles || [])];

        if (!year || year === "Select Year") {
          showMessage("Select a year first.", "error");
          return;
        }

        if (!this.isValidTarget(classLevel, classArm)) {
          showMessage("Select class level and class arm/group.", "error");
          return;
        }

        if (!files.length) {
          showMessage("No JSON file selected.", "error");
          return;
        }

      const confirmed = await this.showPushConfirm({
        year,
        classArm,
        count: files.length
      });

        if (!confirmed) return;

        try {
          btnPush.disabled = true;
          btnPush.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Pushing...`;

          log(`Pushing ${files.length} file(s) to ${classArm}...`);

          const res = await fetch("/api/push", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              files,
              class_level: classLevel,
              class_category: classLevel,
              class_arm: classArm,
              target_arm: classArm
            }),
          });

          const out = await res.json();

          if (!res.ok || !out.success) {
            throw new Error(out.error || "Push failed");
          }

          const count = out.subjects_pushed?.length || 0;
          const failed = out.failed?.length || 0;

          showMessage(`Pushed ${count} subject(s) to ${classArm}.`, "success");
          log(`✅ Pushed ${count} subject(s) to ${classArm}.`, "success");

          if (failed) {
            log(`⚠️ ${failed} file(s) failed. Check backend console.`, "error");
          }

          if (window.EmisUploads?.selectedFiles) {
            window.EmisUploads.selectedFiles.clear();
          }

          document.querySelectorAll(".row-select").forEach((box) => {
            box.checked = false;
          });

          updatePushCount();

          updateActiveYearLabel(
            out.active_year || out.latest_year || year,
            out.class_active_years || {}
          );

        } catch (err) {
          console.error("Push error:", err);
          showMessage(err.message || "Push failed.", "error");
          log(`❌ ${err.message || "Push failed."}`, "error");
        } finally {
          btnPush.disabled = false;
          btnPush.innerHTML = `<i class="fa-solid fa-cloud-arrow-right"></i> Push Selected to Target`;
        }
      });

      btnClear?.addEventListener("click", async () => {
        const year = pushYearSel.value;
        const classLevel = this.normalizeClassLevel(pushClassLevel.value);
        const classArm = this.normalizeClassArm(pushClassArm.value, classLevel);

        if (!year || year === "Select Year") {
          showMessage("Select a year first.", "error");
          return;
        }

        if (!this.isValidTarget(classLevel, classArm)) {
          showMessage("Select class level and class arm/group to clear.", "error");
          return;
        }

        if (!confirm(`Clear pushed subjects for ${year} / ${classArm}?`)) return;

        try {
          btnClear.disabled = true;
          btnClear.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Clearing...`;

          const res = await fetch("/api/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              year,
              class_level: classLevel,
              class_category: classLevel,
              class_arm: classArm,
              target_arm: classArm
            }),
          });

          const out = await res.json();

          if (!res.ok || !out.success) {
            throw new Error(out.error || "Clear failed");
          }

          showMessage(`Cleared ${classArm}.`, "success");
          log(`🗑️ Cleared ${out.cleared}.`, "success");

          updateActiveYearLabel(
            out.latest_year || "",
            out.class_active_years || {}
          );

        } catch (err) {
          console.error("Clear error:", err);
          showMessage(err.message || "Clear failed.", "error");
          log(`❌ ${err.message || "Clear failed."}`, "error");
        } finally {
          btnClear.disabled = false;
          btnClear.innerHTML = `<i class="fa-solid fa-trash"></i> Clear Target Subjects`;
        }
      });

      if (btnPushAll) {
        btnPushAll.addEventListener("click", () => {
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

          if (window.EmisUploads.activeClass && window.EmisUploads.activeClass !== "ALL") {
            items = items.filter((it) => {
              return this.normalizeClassLevel(it.class_category) === window.EmisUploads.activeClass;
            });
          }

          window.EmisUploads.selectedFiles.clear();

          items.forEach((it) => {
            window.EmisUploads.selectedFiles.add(`${year}:${it.filename}`);
          });

          document.querySelectorAll(".row-select").forEach((box) => {
            box.checked = true;
          });

          updatePushCount();
          showMessage(`${items.length} file(s) queued. Select target and push.`, "success");
        });
      }

      const currentLevel = this.normalizeClassLevel(pushClassLevel.value);
      if (currentLevel) buildArmOptions(currentLevel);

      fetchLatestYear();
      updatePushCount();
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
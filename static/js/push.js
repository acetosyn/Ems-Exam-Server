/* ======================================================================
   EMIS CBT — PORTAL PUSH CONTROLLER

   Supports:
     • Broad class targets
     • Exact class-arm targets
     • JSS1 / JSS2 / JSS3 — strict FIRST / SECOND / THIRD
     • SS1 / SS2 / SS3 — hybrid GENERAL + FIRST / SECOND / THIRD
     • SS selected-term pushes with General/root source fallback
     • Historical JSON source year -> independent Current / Active target year
     • Current / Active target years 2025-2040
     • Multi-select batch push — one, many or complete subject set
     • One-click Push All Subjects for the selected class / term target
     • Year-aware JSON selection
     • Term / mode-aware confirmation
     • Term-aware clear operations
     • Active year / active term status
     • Backward compatibility with existing portal API
====================================================================== */

(() => {
  if (window.__EMIS_PUSH_BOUND__) return;
  window.__EMIS_PUSH_BOUND__ = true;

  window.EmisPush = {

    /* ==========================================================
       CONFIGURATION
    ========================================================== */

    supportedClasses: ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"],
    termAwareClasses: ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"],
    termRequiredClasses: ["JSS1", "JSS2", "JSS3"],
    optionalTermClasses: ["SS1", "SS2", "SS3"],
    validTerms: ["FIRST", "SECOND", "THIRD"],
    targetYearMin: 2025,
    targetYearMax: 2040,

    classArms: {
      JSS1: ["JSS1A", "JSS1B", "JSS1C"],
      JSS2: ["JSS2A", "JSS2B", "JSS2C"],
      JSS3: ["JSS3A", "JSS3B", "JSS3C"],

      SS1: ["SS1_GOLD", "SS1_SILVER", "SS1_DIAMOND", "SS1_B/C"],
      SS2: ["SS2_GOLD", "SS2_SILVER", "SS2_DIAMOND", "SS2_B/C"],

      // SS3 currently has no Diamond arm.
      SS3: ["SS3_GOLD", "SS3_SILVER", "SS3_B/C"]
    },


    /* ==========================================================
       NORMALIZATION
    ========================================================== */

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

    const compact = raw
      .replaceAll("_", "")
      .replaceAll(" ", "")
      .replaceAll("/", "")
      .replaceAll("&", "");

    const level = this.normalizeClassLevel(raw) || this.normalizeClassLevel(fallbackLevel);

    if (!level) return "";

    /* JSS */
    if (level.startsWith("JSS")) {
      for (const arm of ["A", "B", "C"]) {
        if (compact === `${level}${arm}`) return `${level}${arm}`;
      }

      return level;
    }

    /* SS Science arms */
    for (const label of ["GOLD", "SILVER", "DIAMOND"]) {
      if (compact.includes(label)) return `${level}_${label}`;
    }

    /* SS combined Arts / Commercial aliases */
    const suffix = compact.slice(level.length);

    if (suffix === "B" || suffix === "BC") return `${level}_B/C`;

    return level;
  },


    normalizeTerm(value) {
      const raw = String(value || "").trim().toUpperCase();

      const aliases = {
        "1": "FIRST", "01": "FIRST", "1ST": "FIRST", "FIRST": "FIRST", "FIRST TERM": "FIRST", "1ST TERM": "FIRST", "TERM 1": "FIRST", "TERM1": "FIRST",
        "2": "SECOND", "02": "SECOND", "2ND": "SECOND", "SECOND": "SECOND", "SECOND TERM": "SECOND", "2ND TERM": "SECOND", "TERM 2": "SECOND", "TERM2": "SECOND",
        "3": "THIRD", "03": "THIRD", "3RD": "THIRD", "THIRD": "THIRD", "THIRD TERM": "THIRD", "3RD TERM": "THIRD", "TERM 3": "THIRD", "TERM3": "THIRD"
      };

      return aliases[raw] || null;
    },

    termLabel(term) {
      const raw = String(term || "").trim().toUpperCase();

      if (raw === "GENERAL") return "General / Root";

      const normalized = this.normalizeTerm(term);
      const labels = { FIRST: "1st Term", SECOND: "2nd Term", THIRD: "3rd Term" };

      return labels[normalized] || "—";
    },

    isTermAwareClass(classLevel) {
      return this.termAwareClasses.includes(this.normalizeClassLevel(classLevel));
    },

    isTermRequiredClass(classLevel) {
      return this.termRequiredClasses.includes(this.normalizeClassLevel(classLevel));
    },

    isOptionalTermClass(classLevel) {
      return this.optionalTermClasses.includes(this.normalizeClassLevel(classLevel));
    },

    isValidTarget(classLevel, classArm) {
      if (!classLevel || !classArm || !this.supportedClasses.includes(classLevel)) return false;
      if (classArm === classLevel) return true;

      return (this.classArms[classLevel] || []).includes(classArm);
    },


    /* ==========================================================
       SELECTED FILE HELPERS
    ========================================================== */

    getSelectedItems() {
      if (window.EmisUploads?.getSelectedItems) return window.EmisUploads.getSelectedItems();

      const selected = [...(window.EmisUploads?.selectedFiles || [])];

      return selected.map((entry) => {
        const raw = String(entry || "");

        if (raw.includes("|")) {
          const [year, classCategory, rawTerm, ...filenameParts] = raw.split("|");

          return { year, filename: filenameParts.join("|"), class_category: classCategory, term: rawTerm === "NONE" ? null : rawTerm };
        }

        const [year, ...filenameParts] = raw.split(":");

        return { year, filename: filenameParts.join(":"), class_category: "", term: null };
      });
    },

    getItemClass(item) {
      if (window.EmisUploads?.getItemClass) return window.EmisUploads.getItemClass(item);

      return this.normalizeClassLevel(item?.class_category || item?.class_level || item?.class);
    },

    getItemTerm(item) {
      if (window.EmisUploads?.getItemTerm) return window.EmisUploads.getItemTerm(item);

      return this.normalizeTerm(item?.term || item?.exam_term || item?.academic_term || item?.term_name);
    },

    getPushFileEntries(items) {
      return [...new Set(items.map((item) => `${item.year}:${item.filename}`))];
    },


    /* ==========================================================
       PUSH CONFIRMATION
    ========================================================== */

    showPushConfirm({ targetYear, sourceYear = "", classLevel, classArm, term = null, mode = "", count }) {
      return new Promise((resolve) => {
        const modal = document.querySelector("#pushConfirmModal"), text = document.querySelector("#pushConfirmText"), yearEl = document.querySelector("#pushConfirmYear"), targetEl = document.querySelector("#pushConfirmTarget"), termEl = document.querySelector("#pushConfirmTerm"), countEl = document.querySelector("#pushConfirmCount"), cancelBtn = document.querySelector("#cancelPushConfirm"), acceptBtn = document.querySelector("#acceptPushConfirm"), backdrop = modal?.querySelector(".push-confirm-backdrop");
        const generalMode = this.isOptionalTermClass(classLevel) && String(mode || "").toUpperCase() === "GENERAL", modeLabel = term ? this.termLabel(term) : generalMode ? "General / Root" : "", targetText = modeLabel ? `${classArm} • ${modeLabel}` : classArm, sourceText = sourceYear ? ` from JSON ${sourceYear}` : "";

        if (!modal) { resolve(confirm(`Push ${count} subject(s)${sourceText} to ${targetYear} • ${targetText}?`)); return; }

        if (text) text.textContent = `You are about to publish ${count} selected exam file(s)${sourceText} to ${targetText}.`;
        if (yearEl) yearEl.textContent = `Current / Active Year: ${targetYear}`;
        if (targetEl) targetEl.textContent = `Target: ${classArm}`;

        if (termEl) {
          if (modeLabel) { termEl.textContent = `Term / Mode: ${modeLabel}`; termEl.classList.remove("hidden"); }
          else termEl.classList.add("hidden");
        }

        if (countEl) countEl.textContent = `Subjects: ${count}`;
        modal.classList.remove("hidden");

        const close = (answer) => { modal.classList.add("hidden"); cancelBtn?.removeEventListener("click", onCancel); acceptBtn?.removeEventListener("click", onAccept); backdrop?.removeEventListener("click", onCancel); resolve(answer); };
        const onCancel = () => close(false), onAccept = () => close(true);
        cancelBtn?.addEventListener("click", onCancel); acceptBtn?.addEventListener("click", onAccept); backdrop?.addEventListener("click", onCancel);
      });
    },

    /* ==========================================================
       INITIALIZATION
    ========================================================== */

    init() {
      const root = document.querySelector(".uploads-wrapper");

      if (!root) return;


      /* ========================================================
         MAIN PUSH PANEL / STATUS / CLEAR MODAL
      ======================================================== */

      const btnPush = root.querySelector("#pushSelectedToPortal");
      const btnClear = root.querySelector("#clearPortalSubjects");
      const btnPushAll = root.querySelector("#btnPushAllSubjects");

      const pushYearSel = root.querySelector("#pushYearSelector");
      const pushClassLevel = root.querySelector("#pushClassLevel");
      const pushClassArm = root.querySelector("#pushClassArm");
      const pushTermField = root.querySelector("#pushTermField");
      const pushTermSelector = root.querySelector("#pushTermSelector");

      const activeYearLabel = root.querySelector("#activeYearLabel");
      const activeTargetLabel = root.querySelector("#activeTargetLabel");
      const activeTermLabelWrap = root.querySelector("#activeTermLabelWrap");
      const activeTermLabel = root.querySelector("#activeTermLabel");
      const statTargetArm = root.querySelector("#statTargetArm");

      const logBody = root.querySelector("#portalLogBody");

      const clearModal = root.querySelector("#clearPortalModal");
      const clearClassLevel = root.querySelector("#clearClassLevel");
      const clearClassArm = root.querySelector("#clearClassArm");
      const clearTermField = root.querySelector("#clearTermField");
      const clearTermSelector = root.querySelector("#clearTermSelector");
      const confirmClearTarget = root.querySelector("#confirmClearTarget");
      const confirmClearAllTargets = root.querySelector("#confirmClearAllTargets");


      if (!btnPush || !pushYearSel || !pushClassLevel || !pushClassArm) return;

      /* ========================================================
         CURRENT / ACTIVE TARGET YEAR — 2025 TO 2040
      ======================================================== */

      const buildPushTargetYears = () => {
        const previous = String(pushYearSel.value || "").trim(), current = new Date().getFullYear();
        pushYearSel.innerHTML = "";

        for (let year = this.targetYearMin; year <= this.targetYearMax; year++) pushYearSel.add(new Option(String(year), String(year)));

        const previousValid = Number(previous) >= this.targetYearMin && Number(previous) <= this.targetYearMax;
        const currentValid = current >= this.targetYearMin && current <= this.targetYearMax;
        pushYearSel.value = previousValid ? previous : currentValid ? String(current) : String(this.targetYearMin);
        pushYearSel.setAttribute("aria-label", "Current / Active Year");
        pushYearSel.title = `Current / Active examination year (${this.targetYearMin}-${this.targetYearMax})`;

        const explicitLabel = root.querySelector('label[for="pushYearSelector"]');
        if (explicitLabel) explicitLabel.textContent = "Current / Active Year";
      };

      buildPushTargetYears();


      /* ========================================================
         PUSH NOTICE / LOG / PUSH COUNT
      ======================================================== */

      const noticeStack = root.querySelector("#pushNoticeStack");

      const showPushNotice = ({ type = "info", title = "", message = "", details = [], duration = 6500 } = {}) => {
        const normalizedType = type === "warn" ? "warning" : ["success", "warning", "error", "info"].includes(type) ? type : "info";

        const titles = {
          success: "Push Successful",
          warning: "Check Student Visibility",
          error: "Subject Not Pushed",
          info: "Portal Information"
        };

        const icons = {
          success: "fa-circle-check",
          warning: "fa-triangle-exclamation",
          error: "fa-circle-xmark",
          info: "fa-circle-info"
        };

        const badges = {
          success: "PUBLISHED",
          warning: "CHECK TARGET",
          error: "BLOCKED",
          info: "INFO"
        };

        /* Fallback if notification container is unavailable. */
        if (!noticeStack) {
          const fallback = [title || titles[normalizedType], message, ...(Array.isArray(details) ? details : [])].filter(Boolean).join("\n");

          if (typeof flashMessage === "function") flashMessage(fallback, normalizedType === "warning" ? "warn" : normalizedType);
          else alert(fallback);

          return null;
        }

        const notice = document.createElement("article");
        notice.className = `push-notice push-notice-${normalizedType}`;
        notice.setAttribute("role", normalizedType === "error" ? "alert" : "status");

        const iconWrap = document.createElement("div");
        iconWrap.className = "push-notice-icon";

        const icon = document.createElement("i");
        icon.className = `fa-solid ${icons[normalizedType]}`;
        iconWrap.appendChild(icon);

        const content = document.createElement("div");
        content.className = "push-notice-content";

        const heading = document.createElement("div");
        heading.className = "push-notice-heading";

        const headingText = document.createElement("strong");
        headingText.textContent = title || titles[normalizedType];

        const badge = document.createElement("span");
        badge.className = "push-notice-badge";
        badge.textContent = badges[normalizedType];

        heading.append(headingText, badge);
        content.appendChild(heading);

        if (message) {
          const paragraph = document.createElement("p");
          paragraph.className = "push-notice-message";
          paragraph.textContent = message;
          content.appendChild(paragraph);
        }

        const cleanDetails = (Array.isArray(details) ? details : []).map((item) => String(item || "").trim()).filter(Boolean).slice(0, 5);

        if (cleanDetails.length) {
          const detailBox = document.createElement("div");
          detailBox.className = "push-notice-details";

          cleanDetails.forEach((detail) => {
            const row = document.createElement("div");
            row.className = "push-notice-detail";

            const bullet = document.createElement("i");
            bullet.className = normalizedType === "warning" ? "fa-solid fa-circle-exclamation" : normalizedType === "error" ? "fa-solid fa-ban" : "fa-solid fa-check";

            const text = document.createElement("span");
            text.textContent = detail;

            row.append(bullet, text);
            detailBox.appendChild(row);
          });

          content.appendChild(detailBox);
        }

        const closeBtn = document.createElement("button");
        closeBtn.type = "button";
        closeBtn.className = "push-notice-close";
        closeBtn.setAttribute("aria-label", "Dismiss notification");
        closeBtn.innerHTML = `<i class="fa-solid fa-xmark"></i>`;

        const progress = document.createElement("div");
        progress.className = "push-notice-progress";

        if (duration > 0) progress.style.animationDuration = `${duration}ms`;
        else progress.hidden = true;

        notice.append(iconWrap, content, closeBtn, progress);
        noticeStack.appendChild(notice);

        /* Keep the notification area compact. */
        while (noticeStack.children.length > 4) noticeStack.firstElementChild?.remove();

        let removed = false;

        const dismiss = () => {
          if (removed) return;
          removed = true;
          notice.classList.add("is-leaving");
          setTimeout(() => notice.remove(), 280);
        };

        closeBtn.addEventListener("click", dismiss);
        if (duration > 0) setTimeout(dismiss, duration);

        return notice;
      };

      const showMessage = (message, type = "success") => {
        showPushNotice({
          type: type === "warn" ? "warning" : type,
          message,
          duration: type === "error" ? 8000 : 5500
        });
      };

      const log = (message, type = "info") => {
        if (!logBody) return;

        const placeholder = logBody.querySelector(".log-placeholder");
        if (placeholder) logBody.innerHTML = "";

        const entry = document.createElement("div");
        entry.className = type === "success" ? "log-item success" : type === "error" ? "log-item error" : type === "warn" ? "log-item warn" : "log-item";

        const time = document.createElement("strong");
        time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

        const text = document.createElement("span");
        text.textContent = message;

        entry.append(time, text);
        logBody.appendChild(entry);
        logBody.scrollTop = logBody.scrollHeight;
      };

      const updatePushCount = () => {
        const count = window.EmisUploads?.selectedFiles?.size || 0;
        const pushCount = root.querySelector("#pushCount");
        const pushCountSide = root.querySelector("#pushCountSide");

        if (pushCount) pushCount.textContent = count;
        if (pushCountSide) pushCountSide.textContent = count;
        if (window.EmisUploads?.updatePushCount) window.EmisUploads.updatePushCount();
      };


      /* ========================================================
         CLASS ARM OPTIONS
      ======================================================== */

      const buildArmOptions = (selectElement, classLevel) => {
        if (!selectElement) return;

        if (!classLevel) {
          selectElement.innerHTML = `<option value="" disabled selected>Select class first</option>`;
          return;
        }

        const arms = this.classArms[classLevel] || [];

        selectElement.innerHTML = `
          <option value="" selected>Select Arm / Group</option>
          <option value="${classLevel}">${classLevel} — Whole Class</option>
          ${arms.map((arm) => `<option value="${arm}">${arm}</option>`).join("")}
        `;
      };


      /* ========================================================
         TERM UI — JSS REQUIRED / SS OPTIONAL
      ======================================================== */

      const updatePushTermUI = () => {
        const classLevel = this.normalizeClassLevel(pushClassLevel.value);
        const termAware = this.isTermAwareClass(classLevel);
        const termRequired = this.isTermRequiredClass(classLevel);
        const optionalTerm = this.isOptionalTermClass(classLevel);
        const generalOption = root.querySelector("#pushGeneralTermOption");

        if (pushTermField) pushTermField.classList.toggle("hidden", !termAware);
        if (generalOption) generalOption.hidden = !optionalTerm;

        if (!termAware && pushTermSelector) pushTermSelector.value = "";
        if (termRequired && pushTermSelector?.value === "GENERAL") pushTermSelector.value = "";

        /* Preserve legacy SS behaviour by defaulting SS to General / Root. */
        if (optionalTerm && pushTermSelector && !pushTermSelector.value) pushTermSelector.value = "GENERAL";

        updateTargetPreview();
      };

      const updateClearTermUI = () => {
        if (!clearClassLevel) return;

        const classLevel = this.normalizeClassLevel(clearClassLevel.value);
        const termAware = this.isTermAwareClass(classLevel);
        const termRequired = this.isTermRequiredClass(classLevel);
        const optionalTerm = this.isOptionalTermClass(classLevel);
        const entireOption = root.querySelector("#clearEntireTargetOption");

        if (clearTermField) clearTermField.classList.toggle("hidden", !termAware);
        if (entireOption) entireOption.hidden = !optionalTerm;

        if (!termAware && clearTermSelector) clearTermSelector.value = "";
        if (termRequired && clearTermSelector?.value === "ALL") clearTermSelector.value = "";
      };


      /* ========================================================
         TARGET PREVIEW
      ======================================================== */

      const updateTargetPreview = () => {
        const targetYear = pushYearSel.value, classLevel = this.normalizeClassLevel(pushClassLevel.value), classArm = this.normalizeClassArm(pushClassArm.value, classLevel), rawMode = String(pushTermSelector?.value || "").trim().toUpperCase(), term = this.normalizeTerm(rawMode);
        const generalMode = this.isOptionalTermClass(classLevel) && rawMode === "GENERAL", modeLabel = term ? this.termLabel(term) : generalMode ? "General / Root" : "";

        if (activeYearLabel) activeYearLabel.textContent = targetYear || "—";
        if (activeTargetLabel) activeTargetLabel.textContent = classArm || classLevel || "—";
        if (statTargetArm) statTargetArm.textContent = classArm || classLevel || "—";
        if (activeTermLabelWrap) activeTermLabelWrap.classList.toggle("hidden", !modeLabel);
        if (activeTermLabel) activeTermLabel.textContent = modeLabel || "—";
      };


      /* ========================================================
         ACTIVE PORTAL STATUS
      ======================================================== */

      const updateServerActiveStatus = (latestYear, activeYears = {}, activeTerms = {}) => {
        if (activeYearLabel && !pushYearSel.value) activeYearLabel.textContent = latestYear || "—";

        if (activeYearLabel) {
          const yearTitles = Object.entries(activeYears || {}).map(([target, year]) => {
            const classLevel = this.normalizeClassLevel(target);
            const hasTermState = Object.prototype.hasOwnProperty.call(activeTerms || {}, target);
            const term = activeTerms?.[target];

            if (term) return `${target}: ${year} / ${this.termLabel(term)}`;
            if (hasTermState && this.isOptionalTermClass(classLevel)) return `${target}: ${year} / General`;

            return `${target}: ${year}`;
          }).join(" • ");

          activeYearLabel.title = yearTitles;
        }
      };

      const fetchLatestState = async () => {
        try {
          const response = await fetch("/api/push_latest_year");
          const data = await response.json();

          if (!response.ok) return;

          updateServerActiveStatus(data.latest_year || data.year || "", data.class_active_years || {}, data.class_active_terms || {});
        } catch (error) {
          console.warn("Latest portal state fetch failed:", error);
        }
      };


      /* ========================================================
         AUTO SYNC PUSH PANEL FROM CURRENT SELECTION
      ======================================================== */

      const syncTargetFromSelection = () => {
        const selectedItems = this.getSelectedItems(); if (!selectedItems.length) return;
        const classes = [...new Set(selectedItems.map((item) => this.getItemClass(item)).filter(Boolean))];

        /* Historical JSON source year must NEVER overwrite Current / Active Target Year. */
        if (classes.length === 1) {
          const classLevel = classes[0];

          if ([...pushClassLevel.options].some((option) => option.value === classLevel)) {
            const previousLevel = this.normalizeClassLevel(pushClassLevel.value), previousArm = this.normalizeClassArm(pushClassArm.value, previousLevel || classLevel);
            pushClassLevel.value = classLevel;

            if (previousLevel !== classLevel || !pushClassArm.options.length) {
              buildArmOptions(pushClassArm, classLevel);
              const armStillExists = [...pushClassArm.options].some((option) => option.value === previousArm);
              if (previousArm && armStillExists) pushClassArm.value = previousArm;
            }

            updatePushTermUI();

            const itemTerms = [...new Set(selectedItems.map((item) => this.getItemTerm(item)).filter(Boolean))], hasGeneralItems = selectedItems.some((item) => !this.getItemTerm(item));
            if (this.isTermRequiredClass(classLevel) && pushTermSelector) pushTermSelector.value = itemTerms.length === 1 && !hasGeneralItems ? itemTerms[0] : "";

            if (this.isOptionalTermClass(classLevel) && pushTermSelector) {
              if (itemTerms.length === 0) pushTermSelector.value = "GENERAL";
              else if (itemTerms.length === 1) pushTermSelector.value = itemTerms[0];
              else pushTermSelector.value = "";
            }
          }
        }

        updateTargetPreview();
      };


      /* ========================================================
         VALIDATE CURRENT PUSH SELECTION
      ======================================================== */

      const validatePushSelection = (targetYear, classLevel, term, mode, items) => {
        if (!items.length) return { valid: false, message: "No JSON file selected." };
        if (items.some((item) => !item?.filename)) return { valid: false, message: "One or more selected files are invalid." };

        const targetYearNumber = Number(targetYear), sourceYears = [...new Set(items.map((item) => String(item.year || "").trim()).filter(Boolean))];
        if (!Number.isInteger(targetYearNumber) || targetYearNumber < this.targetYearMin || targetYearNumber > this.targetYearMax) return { valid: false, message: `Current / Active Year must be between ${this.targetYearMin} and ${this.targetYearMax}.` };
        if (sourceYears.length > 1) return { valid: false, message: "Selected files contain different JSON source years. Push one source year at a time." };

        const classes = [...new Set(items.map((item) => this.getItemClass(item)).filter(Boolean))];
        if (classes.length > 1) return { valid: false, message: "Selected files contain different classes. Push one class at a time." };
        if (classes.length === 1 && classes[0] !== classLevel) return { valid: false, message: `Selected files are for ${classes[0]}, not ${classLevel}.` };

        const rawMode = String(mode || "").trim().toUpperCase(), itemTerms = [...new Set(items.map((item) => this.getItemTerm(item)).filter(Boolean))], missingTerms = items.some((item) => !this.getItemTerm(item));

        /* JSS = strict selected term. */
        if (this.isTermRequiredClass(classLevel)) {
          if (!term) return { valid: false, message: `Select a term for ${classLevel}.` };
          if (itemTerms.length > 1) return { valid: false, message: "Selected JSS files contain different terms. Push one term at a time." };
          if (missingTerms) return { valid: false, message: "One or more JSS files have no term assigned. Please fix the JSON metadata first." };
          if (itemTerms.length === 1 && itemTerms[0] !== term) return { valid: false, message: `Selected files are ${this.termLabel(itemTerms[0])}, but target is ${this.termLabel(term)}.` };
          return { valid: true, sourceYear: sourceYears[0] || "" };
        }

        /* SS = General/root or one selected term. */
        if (this.isOptionalTermClass(classLevel)) {
          if (!rawMode) return { valid: false, message: `Select General / Root or a term for ${classLevel}.` };

          if (rawMode === "GENERAL") {
            if (itemTerms.length) return { valid: false, message: "General / Root push can only contain General SS files. Choose the matching term to push term-specific files." };
            return { valid: true, sourceYear: sourceYears[0] || "" };
          }

          if (!term) return { valid: false, message: `Select General / Root or a valid term for ${classLevel}.` };
          const wrongTerms = itemTerms.filter((itemTerm) => itemTerm !== term);
          if (wrongTerms.length) return { valid: false, message: `Selected SS files include ${wrongTerms.map((itemTerm) => this.termLabel(itemTerm)).join(", ")}, but target is ${this.termLabel(term)}.` };

          return { valid: true, sourceYear: sourceYears[0] || "" };
        }

        return { valid: true, sourceYear: sourceYears[0] || "" };
      };


      /* ========================================================
         MAIN CLASS / TARGET SELECTORS
      ======================================================== */

      pushClassLevel.addEventListener("change", () => {
        const classLevel = this.normalizeClassLevel(pushClassLevel.value);

        buildArmOptions(pushClassArm, classLevel);

        if (pushTermSelector) pushTermSelector.value = "";

        updatePushTermUI();
        updateTargetPreview();
      });

      pushClassArm.addEventListener("change", updateTargetPreview);
      pushYearSel.addEventListener("change", updateTargetPreview);
      pushTermSelector?.addEventListener("change", updateTargetPreview);


      /* ========================================================
         BATCH PUSH ENGINE — ONE, MANY OR ALL SUBJECTS
      ======================================================== */

      const getTargetContext = () => {
        const targetYear = String(pushYearSel.value || "").trim(), classLevel = this.normalizeClassLevel(pushClassLevel.value), classArm = this.normalizeClassArm(pushClassArm.value, classLevel);
        const rawTermMode = String(pushTermSelector?.value || "").trim().toUpperCase(), term = this.isTermAwareClass(classLevel) && rawTermMode !== "GENERAL" ? this.normalizeTerm(rawTermMode) : null;
        return { targetYear, classLevel, classArm, rawTermMode, term };
      };

      const formatPushFailures = (items) => (Array.isArray(items) ? items : []).slice(0, 8).map((item) => {
        const subject = String(item?.subject || "").trim(), reason = String(item?.reason || "This subject could not be pushed.").trim();
        return subject && !reason.toLowerCase().startsWith(subject.toLowerCase()) ? `${subject}: ${reason}` : reason;
      }).filter(Boolean);

      const clearPushedQueue = () => {
        if (window.EmisUploads?.clearSelection) window.EmisUploads.clearSelection();
        else if (window.EmisUploads?.selectedFiles) window.EmisUploads.selectedFiles.clear();

        root.querySelectorAll(".row-select").forEach((checkbox) => { checkbox.checked = false; });
        const checkAll = root.querySelector("#checkAllUploads");
        if (checkAll) { checkAll.checked = false; checkAll.indeterminate = false; }
        updatePushCount();
      };

      const selectBatchItemsInQueue = (items) => {
        const uploads = window.EmisUploads;
        if (!uploads?.selectedFiles) return;

        uploads.selectedFiles.clear();
        items.forEach((item) => {
          if (uploads.makeSelectionKey) uploads.selectedFiles.add(uploads.makeSelectionKey(item));
          else uploads.selectedFiles.add(`${item.year}|${this.getItemClass(item)}|${this.getItemTerm(item) || "NONE"}|${item.filename}`);
        });

        root.querySelectorAll(".upload-row").forEach((row) => {
          const checkbox = row.querySelector(".row-select"); if (!checkbox) return;
          const year = row.dataset.year, filename = row.dataset.filename, cls = this.normalizeClassLevel(row.dataset.class), term = this.normalizeTerm(row.dataset.term) || "NONE";
          checkbox.checked = uploads.selectedFiles.has(`${year}|${cls}|${term}|${filename}`);
        });

        const checkAll = root.querySelector("#checkAllUploads"), renderedChecks = [...root.querySelectorAll(".upload-row .row-select")];
        if (checkAll && renderedChecks.length) {
          const checkedCount = renderedChecks.filter((checkbox) => checkbox.checked).length;
          checkAll.checked = checkedCount === renderedChecks.length; checkAll.indeterminate = checkedCount > 0 && checkedCount < renderedChecks.length;
        }

        updatePushCount();
      };

      const collectAllSubjectsForTarget = (classLevel, term, rawTermMode) => {
        const uploads = window.EmisUploads;
        if (!uploads?.convertedItems?.length || !classLevel) return [];

        let items = uploads.convertedItems.filter((item) => this.getItemClass(item) === classLevel);
        if (uploads.activeYear) items = items.filter((item) => String(item.year || "") === String(uploads.activeYear));

        if (this.isTermRequiredClass(classLevel)) {
          if (!term) return [];
          items = items.filter((item) => this.getItemTerm(item) === term);

        } else if (this.isOptionalTermClass(classLevel)) {
          if (rawTermMode === "GENERAL") {
            items = items.filter((item) => !this.getItemTerm(item));

          } else if (term) {
            const specificKeys = new Set(items.filter((item) => this.getItemTerm(item) === term).map((item) => `${item.year}|${this.getItemClass(item)}|${item.filename}`));
            items = items.filter((item) => {
              const itemTerm = this.getItemTerm(item);
              if (itemTerm === term) return true;
              if (itemTerm) return false;
              return !specificKeys.has(`${item.year}|${this.getItemClass(item)}|${item.filename}`);
            });
          }
        }

        const unique = new Map();
        items.forEach((item) => { const key = `${item.year}|${this.getItemClass(item)}|${this.getItemTerm(item) || "NONE"}|${item.filename}`; if (!unique.has(key)) unique.set(key, item); });
        return [...unique.values()];
      };

      const executeBatchPush = async (items, triggerButton = btnPush, { clearQueue = true, actionLabel = "Push Selected" } = {}) => {
        const { targetYear, classLevel, classArm, rawTermMode, term } = getTargetContext();
        items = Array.isArray(items) ? items.filter(Boolean) : [];

        if (!items.length) return showMessage("Select at least one JSON subject to push.", "error");
        if (!targetYear) return showMessage("Select a Current / Active Year first.", "error");
        if (!this.isValidTarget(classLevel, classArm)) return showMessage("Select class level and class arm/group.", "error");

        const validation = validatePushSelection(targetYear, classLevel, term, rawTermMode, items);
        if (!validation.valid) return showMessage(validation.message, "error");

        const files = this.getPushFileEntries(items), sourceYear = validation.sourceYear || "";
        if (!files.length) return showMessage("No valid JSON subjects were found in the selected batch.", "error");

        const confirmed = await this.showPushConfirm({ targetYear, sourceYear, classLevel, classArm, term, mode: rawTermMode, count: files.length });
        if (!confirmed) return;

        const originalHtml = triggerButton?.innerHTML || "", generalMode = this.isOptionalTermClass(classLevel) && rawTermMode === "GENERAL";
        const targetText = term ? `${classArm} / ${this.termLabel(term)}` : generalMode ? `${classArm} / General` : classArm, pushedTargetLabel = term ? `${classArm} • ${this.termLabel(term)}` : generalMode ? `${classArm} • General / Root` : classArm;

        try {
          if (triggerButton) { triggerButton.disabled = true; triggerButton.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Pushing ${files.length}...`; }
          if (btnPush && btnPush !== triggerButton) btnPush.disabled = true;
          if (btnPushAll && btnPushAll !== triggerButton) btnPushAll.disabled = true;

          log(`Batch push started — ${files.length} subject(s)${sourceYear ? ` from JSON ${sourceYear}` : ""} → active year ${targetYear} • ${targetText}.`);

          const response = await fetch("/api/push", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ files, target_year: targetYear, year: targetYear, class_level: classLevel, class_category: classLevel, class_arm: classArm, target_arm: classArm, term, batch: true })
          });

          let output = {};
          try { output = await response.json(); } catch { output = {}; }

          const failures = Array.isArray(output.failed) ? output.failed : [], warnings = Array.isArray(output.warnings) ? output.warnings : [];
          const pushedCount = Number(output.subject_count ?? output.subjects_pushed?.length ?? 0) || 0, failedCount = Number(output.failed_count ?? failures.length ?? 0) || 0, warningCount = Number(output.warning_count ?? warnings.length ?? 0) || 0;

          if (!response.ok) throw new Error(output.error || failures[0]?.reason || "Batch push request failed.");

          if (!output.success || !pushedCount) {
            const blockedDetails = formatPushFailures(failures);
            showPushNotice({ type: "error", title: `${failedCount || files.length} Subject${(failedCount || files.length) === 1 ? "" : "s"} Not Pushed`, message: `Nothing was published to ${targetYear} • ${pushedTargetLabel}.`, details: blockedDetails, duration: 12000 });
            blockedDetails.forEach((reason) => log(reason, "error")); return;
          }

          showPushNotice({ type: failedCount ? "warning" : "success", title: failedCount ? "Batch Push Partially Completed" : pushedCount === 1 ? "Push Successful" : "Batch Push Successful", message: `${pushedCount} of ${files.length} selected subject${files.length === 1 ? "" : "s"} published${sourceYear ? ` from JSON ${sourceYear}` : ""} to active year ${targetYear} • ${pushedTargetLabel}.`, duration: failedCount ? 10000 : 6500 });
          log(`Batch completed — ${pushedCount}/${files.length} subject(s) published to active year ${targetYear} • ${pushedTargetLabel}.`, failedCount ? "warn" : "success");

          if (warningCount) {
            const warningDetails = warnings.slice(0, 8).map((item) => String(item?.message || item?.warning || "").trim()).filter(Boolean);
            showPushNotice({ type: "warning", title: `${warningCount} Visibility Warning${warningCount === 1 ? "" : "s"}`, message: "The compatible subjects were published, but some may not be available to every student in this target.", details: warningDetails, duration: 12000 });
            warningDetails.forEach((warning) => log(warning, "warn"));
          }

          if (failedCount) {
            const failureDetails = formatPushFailures(failures);
            showPushNotice({ type: "error", title: `${failedCount} Subject${failedCount === 1 ? "" : "s"} Skipped`, message: `${pushedCount} compatible subject${pushedCount === 1 ? "" : "s"} were still published successfully.`, details: failureDetails, duration: 12000 });
            failureDetails.forEach((reason) => log(reason, "warn"));
          }

          if (clearQueue) clearPushedQueue();
          updateServerActiveStatus(output.active_year || output.target_year || output.latest_year || targetYear, output.class_active_years || {}, output.class_active_terms || {});
          updateTargetPreview(); root.querySelector("#refreshPortalMap")?.click();

        } catch (error) {
          console.error("Batch push error:", error);
          showPushNotice({ type: "error", title: "Batch Push Failed", message: error.message || "The portal batch push could not be completed.", duration: 10000 });
          log(error.message || "Batch push failed.", "error");

        } finally {
          if (triggerButton) { triggerButton.disabled = false; triggerButton.innerHTML = originalHtml || `<i class="fa-solid fa-cloud-arrow-up"></i> ${actionLabel}`; }
          if (btnPush) btnPush.disabled = false;
          if (btnPushAll) btnPushAll.disabled = false;
        }
      };


      /* ========================================================
         PUSH SELECTED — MULTI-SELECT BATCH
      ======================================================== */

      btnPush.addEventListener("click", async () => {
        syncTargetFromSelection();
        const selectedItems = this.getSelectedItems();
        await executeBatchPush(selectedItems, btnPush, { clearQueue: true, actionLabel: "Push Selected" });
      });


      /* ========================================================
         OPEN CLEAR TARGET MODAL
      ======================================================== */

      btnClear?.addEventListener("click", () => {
        const pushLevel = this.normalizeClassLevel(pushClassLevel.value);
        const pushArm = this.normalizeClassArm(pushClassArm.value, pushLevel);
        const pushTerm = this.normalizeTerm(pushTermSelector?.value);

        if (clearClassLevel && pushLevel) {
          clearClassLevel.value = pushLevel;
          buildArmOptions(clearClassArm, pushLevel);

          if (clearClassArm && pushArm) clearClassArm.value = pushArm;
        }


        /*
         * Important:
         * General push must NOT automatically choose "Entire SS Target".
         * Entire target removes General + FIRST + SECOND + THIRD.
         */

        if (clearTermSelector) clearTermSelector.value = "";

        updateClearTermUI();


        /* A real selected term may safely be copied into the clear modal. */

        if (clearTermSelector && pushTerm && this.isTermAwareClass(pushLevel)) clearTermSelector.value = pushTerm;


        if (clearModal) {
          clearModal.classList.remove("hidden");

        } else {
          const fallbackScope = this.isOptionalTermClass(pushLevel) ? "ALL" : pushTerm;

          clearSelectedTarget(pushYearSel.value, pushLevel, pushArm, fallbackScope);
        }
      });


      /* ========================================================
         CLEAR MODAL CLASS CHANGE
      ======================================================== */

      clearClassLevel?.addEventListener("change", () => {
        const classLevel = this.normalizeClassLevel(clearClassLevel.value);

        buildArmOptions(clearClassArm, classLevel);

        if (clearTermSelector) clearTermSelector.value = "";

        updateClearTermUI();
      });


      /* ========================================================
         CLEAR TARGET FUNCTION
      ======================================================== */

      const clearSelectedTarget = async (year, classLevel, classArm, scope) => {
        year = String(year || "").trim();
        classLevel = this.normalizeClassLevel(classLevel);
        classArm = this.normalizeClassArm(classArm, classLevel);

        const rawScope = String(scope || "").trim().toUpperCase();
        const clearEntireSS = this.isOptionalTermClass(classLevel) && rawScope === "ALL";
        const term = clearEntireSS ? null : this.normalizeTerm(rawScope);


        if (!year) {
          showMessage("Select a Current / Active Year first.", "error");
          return;
        }

        if (!this.isValidTarget(classLevel, classArm)) {
          showMessage("Select class level and class arm/group to clear.", "error");
          return;
        }


        /* JSS always requires a selected term. */

        if (this.isTermRequiredClass(classLevel) && !term) {
          showMessage(`Select a term for ${classLevel}.`, "error");
          return;
        }


        /* SS requires explicit Entire Target OR a selected term. */

        if (this.isOptionalTermClass(classLevel) && !clearEntireSS && !term) {
          showMessage(`Select Entire SS Target or a specific term for ${classLevel}.`, "error");
          return;
        }


        const targetText = term ? `${year} / ${classArm} / ${this.termLabel(term)}` : `${year} / ${classArm} / ENTIRE TARGET`;

        const warning = clearEntireSS
          ? `Clear the ENTIRE SS target ${year} / ${classArm}?\n\nThis removes General and all term folders for this target.`
          : `Clear pushed subjects for ${targetText}?`;

        if (!confirm(warning)) return;


        try {
          if (confirmClearTarget) {
            confirmClearTarget.disabled = true;
            confirmClearTarget.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Clearing...`;
          }


          const response = await fetch("/api/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              year,
              class_level: classLevel,
              class_category: classLevel,
              class_arm: classArm,
              target_arm: classArm,
              term
            })
          });


          const output = await response.json();

          if (!response.ok || !output.success) throw new Error(output.error || "Clear failed");


          showMessage(term ? `${classArm} • ${this.termLabel(term)} cleared.` : `${classArm} entire target cleared.`, "success");
          log(`Cleared ${output.cleared}.`, "success");

          clearModal?.classList.add("hidden");

          updateServerActiveStatus(output.latest_year || "", output.class_active_years || {}, output.class_active_terms || {});
          root.querySelector("#refreshPortalMap")?.click();


        } catch (error) {
          console.error("Clear target error:", error);

          showMessage(error.message || "Clear failed.", "error");
          log(error.message || "Clear failed.", "error");


        } finally {
          if (confirmClearTarget) {
            confirmClearTarget.disabled = false;
            confirmClearTarget.innerHTML = `<i class="fa-solid fa-trash-can"></i> Clear Target`;
          }
        }
      };


      /* ========================================================
         CONFIRM CLEAR TARGET
      ======================================================== */

      confirmClearTarget?.addEventListener("click", async () => {
        const year = pushYearSel.value;
        const classLevel = this.normalizeClassLevel(clearClassLevel?.value);
        const classArm = this.normalizeClassArm(clearClassArm?.value, classLevel);

        /*
         * Keep ALL intact.
         * normalizeTerm("ALL") -> null, which would lose the distinction
         * between "nothing selected" and "Entire SS Target".
         */
        const clearScope = String(clearTermSelector?.value || "").trim().toUpperCase();

        await clearSelectedTarget(year, classLevel, classArm, clearScope);
      });


      /* ========================================================
         CLEAR ALL PORTAL TARGETS
      ======================================================== */

      confirmClearAllTargets?.addEventListener("click", async () => {
        const confirmed = confirm("Clear ALL portal targets and all pushed subjects?\n\nThis affects every year, class and class arm.");

        if (!confirmed) return;


        try {
          confirmClearAllTargets.disabled = true;
          confirmClearAllTargets.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Clearing...`;


          const response = await fetch("/api/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ year: "ALL", class_level: "ALL", class_category: "ALL", class_arm: "ALL", target_arm: "ALL" })
          });


          const output = await response.json();

          if (!response.ok || !output.success) throw new Error(output.error || "Clear all failed");


          showMessage("All portal targets cleared.", "success");
          log("All portal assignments cleared.", "success");

          clearModal?.classList.add("hidden");

          updateServerActiveStatus("", {}, {});
          root.querySelector("#refreshPortalMap")?.click();


        } catch (error) {
          console.error("Clear all error:", error);

          showMessage(error.message || "Could not clear portal.", "error");
          log(error.message || "Could not clear portal.", "error");


        } finally {
          confirmClearAllTargets.disabled = false;
          confirmClearAllTargets.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Clear Everything`;
        }
      });


      /* ========================================================
         PUSH ALL SUBJECTS — ONE CLICK BATCH
         Uses the loaded JSON source year + selected target class/term.
      ======================================================== */

      btnPushAll?.addEventListener("click", async () => {
        const uploads = window.EmisUploads;
        if (!uploads?.convertedItems?.length) return showMessage("No subjects found in the JSON library.", "error");

        let { classLevel, rawTermMode, term } = getTargetContext();

        /* If Push Target class is blank, use the active Repository class when it is one exact class. */
        if (!classLevel && uploads.activeClass && uploads.activeClass !== "ALL") {
          classLevel = this.normalizeClassLevel(uploads.activeClass);
          if (classLevel && [...pushClassLevel.options].some((option) => option.value === classLevel)) {
            pushClassLevel.value = classLevel; buildArmOptions(pushClassArm, classLevel); updatePushTermUI();
            rawTermMode = String(pushTermSelector?.value || "").trim().toUpperCase();
            term = this.isTermAwareClass(classLevel) && rawTermMode !== "GENERAL" ? this.normalizeTerm(rawTermMode) : null;
          }
        }

        if (!classLevel) return showMessage("Select one class in Push Target before using Push All Subjects.", "error");
        if (this.isTermRequiredClass(classLevel) && !term) return showMessage(`Select a term for ${classLevel} before pushing all subjects.`, "error");
        if (this.isOptionalTermClass(classLevel) && !rawTermMode) return showMessage(`Select General / Root or a term for ${classLevel} before pushing all subjects.`, "error");

        const items = collectAllSubjectsForTarget(classLevel, term, rawTermMode);
        if (!items.length) return showMessage(`No ${classLevel} subjects were found for the selected term/mode in this JSON year.`, "error");

        selectBatchItemsInQueue(items);
        await executeBatchPush(items, btnPushAll, { clearQueue: true, actionLabel: "Push All Subjects" });
      });


      /* ========================================================
         OBSERVE QUEUE CHANGES
         Keeps target selectors synced after table selections.
      ======================================================== */

      root.addEventListener("change", (event) => {
        if (event.target.matches(".row-select, #checkAllUploads")) {
          setTimeout(() => {
            updatePushCount();
            syncTargetFromSelection();
          }, 0);
        }
      });


      root.querySelector("#selectAllVisible")?.addEventListener("click", () => {
        setTimeout(() => {
          updatePushCount();
          syncTargetFromSelection();
        }, 0);
      });


      root.querySelector("#clearQueue")?.addEventListener("click", () => {
        setTimeout(updatePushCount, 0);
      });


      /* ========================================================
         INITIAL STATE
      ======================================================== */

      const currentLevel = this.normalizeClassLevel(pushClassLevel.value);

      if (currentLevel) buildArmOptions(pushClassArm, currentLevel);

      updatePushTermUI();
      updateClearTermUI();
      updateTargetPreview();
      updatePushCount();
      fetchLatestState();
    }
  };


  /* ==========================================================
     AUTO INITIALIZATION
  ========================================================== */

  const autoInitPush = () => {
    const wrapper = document.querySelector(".uploads-wrapper");

    if (!wrapper || wrapper.__push_initialized__) return;

    wrapper.__push_initialized__ = true;

    window.EmisPush.init();
  };


  if (document.readyState === "complete" || document.readyState === "interactive") autoInitPush();
  else document.addEventListener("DOMContentLoaded", autoInitPush);


  /* ==========================================================
     DYNAMIC / SPA PAGE SUPPORT
  ========================================================== */

  new MutationObserver(autoInitPush).observe(document.body, { childList: true, subtree: true });

})();
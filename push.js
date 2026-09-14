/* ======================================================================
   EMIS CBT — PORTAL PUSH CONTROLLER

   Supports:
     • Broad class targets
     • Exact class-arm targets
     • JSS1 / JSS2 / JSS3 — strict FIRST / SECOND / THIRD
     • SS1 / SS2 / SS3 — hybrid GENERAL + FIRST / SECOND / THIRD
     • SS selected-term pushes with General/root source fallback
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

    showPushConfirm({ year, classLevel, classArm, term = null, mode = "", count }) {
      return new Promise((resolve) => {
        const modal = document.querySelector("#pushConfirmModal");
        const text = document.querySelector("#pushConfirmText");
        const yearEl = document.querySelector("#pushConfirmYear");
        const targetEl = document.querySelector("#pushConfirmTarget");
        const termEl = document.querySelector("#pushConfirmTerm");
        const countEl = document.querySelector("#pushConfirmCount");
        const cancelBtn = document.querySelector("#cancelPushConfirm");
        const acceptBtn = document.querySelector("#acceptPushConfirm");
        const backdrop = modal?.querySelector(".push-confirm-backdrop");

        const generalMode = this.isOptionalTermClass(classLevel) && String(mode || "").toUpperCase() === "GENERAL";
        const modeLabel = term ? this.termLabel(term) : generalMode ? "General / Root" : "";
        const targetText = modeLabel ? `${classArm} • ${modeLabel}` : classArm;

        if (!modal) {
          resolve(confirm(`Push ${count} subject(s) to ${targetText}?`));
          return;
        }

        if (text) text.textContent = `You are about to publish ${count} selected exam file(s) to ${targetText}.`;
        if (yearEl) yearEl.textContent = `Year: ${year}`;
        if (targetEl) targetEl.textContent = `Target: ${classArm}`;

        if (termEl) {
          if (modeLabel) {
            termEl.textContent = `Term / Mode: ${modeLabel}`;
            termEl.classList.remove("hidden");
          } else {
            termEl.classList.add("hidden");
          }
        }

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
        const year = pushYearSel.value;
        const classLevel = this.normalizeClassLevel(pushClassLevel.value);
        const classArm = this.normalizeClassArm(pushClassArm.value, classLevel);
        const rawMode = String(pushTermSelector?.value || "").trim().toUpperCase();
        const term = this.normalizeTerm(rawMode);
        const generalMode = this.isOptionalTermClass(classLevel) && rawMode === "GENERAL";
        const modeLabel = term ? this.termLabel(term) : generalMode ? "General / Root" : "";

        if (activeYearLabel) activeYearLabel.textContent = year || "—";
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
        const selectedItems = this.getSelectedItems();

        if (!selectedItems.length) return;

        const years = [...new Set(selectedItems.map((item) => String(item.year || "")).filter(Boolean))];
        const classes = [...new Set(selectedItems.map((item) => this.getItemClass(item)).filter(Boolean))];

        /* Year */
        if (years.length === 1) {
          const year = years[0];
          if ([...pushYearSel.options].some((option) => option.value === year)) pushYearSel.value = year;
        }

        /* Class */
        if (classes.length === 1) {
          const classLevel = classes[0];

          if ([...pushClassLevel.options].some((option) => option.value === classLevel)) {
            const previousLevel = this.normalizeClassLevel(pushClassLevel.value);
            const previousArm = this.normalizeClassArm(pushClassArm.value, previousLevel || classLevel);

            pushClassLevel.value = classLevel;

            /*
             * Do not rebuild when the class has not changed.
             * Rebuilding would wipe the teacher's selected target arm.
             */
            if (previousLevel !== classLevel || !pushClassArm.options.length) {
              buildArmOptions(pushClassArm, classLevel);

              const armStillExists = [...pushClassArm.options].some((option) => option.value === previousArm);
              if (previousArm && armStillExists) pushClassArm.value = previousArm;
            }

            updatePushTermUI();

            const itemTerms = [...new Set(selectedItems.map((item) => this.getItemTerm(item)).filter(Boolean))];
            const hasGeneralItems = selectedItems.some((item) => !this.getItemTerm(item));

            /* JSS = one strict term. */
            if (this.isTermRequiredClass(classLevel) && pushTermSelector) {
              pushTermSelector.value = itemTerms.length === 1 && !hasGeneralItems ? itemTerms[0] : "";
            }

            /*
             * SS:
             * root only             -> GENERAL
             * FIRST + root fallback -> FIRST
             * multiple real terms   -> blank / invalid
             */
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

      const validatePushSelection = (year, classLevel, term, mode, items) => {
        if (!items.length) return { valid: false, message: "No JSON file selected." };
        if (items.some((item) => !item?.filename)) return { valid: false, message: "One or more selected files are invalid." };

        /* Year */
        const years = [...new Set(items.map((item) => String(item.year || "")))];

        if (years.length > 1) return { valid: false, message: "Selected files contain different exam years. Push one year at a time." };
        if (years.length === 1 && years[0] && String(year) !== years[0]) return { valid: false, message: `Selected files belong to ${years[0]}, but Push Year is ${year}.` };

        /* Class */
        const classes = [...new Set(items.map((item) => this.getItemClass(item)).filter(Boolean))];

        if (classes.length > 1) return { valid: false, message: "Selected files contain different classes. Push one class at a time." };
        if (classes.length === 1 && classes[0] !== classLevel) return { valid: false, message: `Selected files are for ${classes[0]}, not ${classLevel}.` };

        const rawMode = String(mode || "").trim().toUpperCase();
        const itemTerms = [...new Set(items.map((item) => this.getItemTerm(item)).filter(Boolean))];
        const missingTerms = items.some((item) => !this.getItemTerm(item));

        /* ====================================================
           JSS = STRICT TERM
        ==================================================== */

        if (this.isTermRequiredClass(classLevel)) {
          if (!term) return { valid: false, message: `Select a term for ${classLevel}.` };
          if (itemTerms.length > 1) return { valid: false, message: "Selected JSS files contain different terms. Push one term at a time." };
          if (missingTerms) return { valid: false, message: "One or more JSS files have no term assigned. Please fix the JSON metadata first." };
          if (itemTerms.length === 1 && itemTerms[0] !== term) return { valid: false, message: `Selected files are ${this.termLabel(itemTerms[0])}, but target is ${this.termLabel(term)}.` };

          return { valid: true };
        }

        /* ====================================================
           SS = HYBRID GENERAL / TERM
        ==================================================== */

        if (this.isOptionalTermClass(classLevel)) {
          if (!rawMode) return { valid: false, message: `Select General / Root or a term for ${classLevel}.` };

          /* GENERAL ROOT PUSH */
          if (rawMode === "GENERAL") {
            if (itemTerms.length) return { valid: false, message: "General / Root push can only contain General SS files. Choose the matching term to push term-specific files." };

            return { valid: true };
          }

          /* TERM PUSH */
          if (!term) return { valid: false, message: `Select General / Root or a valid term for ${classLevel}.` };

          /*
           * Selected SS term may contain:
           *   selected-term JSONs
           *   + root/general JSON fallbacks.
           *
           * Another real term is never allowed.
           */
          const wrongTerms = itemTerms.filter((itemTerm) => itemTerm !== term);

          if (wrongTerms.length) {
            const labels = wrongTerms.map((itemTerm) => this.termLabel(itemTerm)).join(", ");
            return { valid: false, message: `Selected SS files include ${labels}, but target is ${this.termLabel(term)}.` };
          }

          return { valid: true };
        }

        return { valid: true };
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
         PUSH SELECTED
      ======================================================== */

      btnPush.addEventListener("click", async () => {
        syncTargetFromSelection();

        const year = String(pushYearSel.value || "").trim();
        const classLevel = this.normalizeClassLevel(pushClassLevel.value);
        const classArm = this.normalizeClassArm(pushClassArm.value, classLevel);
        const rawTermMode = String(pushTermSelector?.value || "").trim().toUpperCase();
        const term = this.isTermAwareClass(classLevel) && rawTermMode !== "GENERAL" ? this.normalizeTerm(rawTermMode) : null;
        const selectedItems = this.getSelectedItems();

        /* -----------------------------------------------------
           BASIC TARGET / SELECTION VALIDATION
        ----------------------------------------------------- */

        if (!year) return showMessage("Select a year first.", "error");
        if (!this.isValidTarget(classLevel, classArm)) return showMessage("Select class level and class arm/group.", "error");

        const validation = validatePushSelection(year, classLevel, term, rawTermMode, selectedItems);
        if (!validation.valid) return showMessage(validation.message, "error");

        const files = this.getPushFileEntries(selectedItems);

        /* -----------------------------------------------------
           CONFIRMATION
        ----------------------------------------------------- */

        const confirmed = await this.showPushConfirm({ year, classLevel, classArm, term, mode: rawTermMode, count: files.length });
        if (!confirmed) return;

        /* -----------------------------------------------------
           PUSH REQUEST
        ----------------------------------------------------- */

        try {
          btnPush.disabled = true;
          btnPush.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Pushing...`;

          const generalMode = this.isOptionalTermClass(classLevel) && rawTermMode === "GENERAL";
          const targetText = term ? `${classArm} / ${this.termLabel(term)}` : generalMode ? `${classArm} / General` : classArm;
          const pushedTargetLabel = term ? `${classArm} • ${this.termLabel(term)}` : generalMode ? `${classArm} • General / Root` : classArm;

          log(`Pushing ${files.length} file(s) to ${targetText}...`);

          const response = await fetch("/api/push", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ files, year, class_level: classLevel, class_category: classLevel, class_arm: classArm, target_arm: classArm, term })
          });

          let output = {};
          try { output = await response.json(); } catch { output = {}; }

          const failures = Array.isArray(output.failed) ? output.failed : [];
          const warnings = Array.isArray(output.warnings) ? output.warnings : [];
          const pushedCount = Number(output.subject_count ?? output.subjects_pushed?.length ?? 0) || 0;
          const failedCount = Number(output.failed_count ?? failures.length ?? 0) || 0;
          const warningCount = Number(output.warning_count ?? warnings.length ?? 0) || 0;

          const formatFailures = (items) => items.slice(0, 5).map((item) => {
            const subject = String(item?.subject || "").trim();
            const reason = String(item?.reason || "This subject could not be pushed.").trim();
            return subject && !reason.toLowerCase().startsWith(subject.toLowerCase()) ? `${subject}: ${reason}` : reason;
          }).filter(Boolean);

          /* ---------------------------------------------------
             SERVER ERROR
          --------------------------------------------------- */

          if (!response.ok) throw new Error(output.error || failures[0]?.reason || "Push request failed.");

          /* ---------------------------------------------------
             EVERYTHING BLOCKED

             Selection remains so teacher can simply change
             the class arm/group and push again.
          --------------------------------------------------- */

          if (!output.success || !pushedCount) {
            const blockedDetails = formatFailures(failures);

            showPushNotice({
              type: "error",
              title: failedCount === 1 ? "Subject Not Pushed" : `${failedCount || files.length} Subjects Not Pushed`,
              message: `Nothing was published to ${pushedTargetLabel}. Change the target arm/group and try again.`,
              details: blockedDetails,
              duration: 11000
            });

            blockedDetails.forEach((reason) => log(reason, "error"));
            return;
          }

          /* ---------------------------------------------------
             SUCCESS
          --------------------------------------------------- */

          showPushNotice({
            type: "success",
            title: pushedCount === 1 ? "Push Successful" : "Push Completed",
            message: `${pushedCount} subject${pushedCount === 1 ? "" : "s"} published to ${pushedTargetLabel}.`,
            duration: 6000
          });

          log(`Pushed ${pushedCount} subject(s) to ${pushedTargetLabel}.`, "success");

          /* ---------------------------------------------------
             STREAM / STUDENT VISIBILITY WARNINGS
          --------------------------------------------------- */

          if (warningCount) {
            const warningDetails = warnings.slice(0, 5).map((item) => String(item?.message || item?.warning || "").trim()).filter(Boolean);

            showPushNotice({
              type: "warning",
              title: warningCount === 1 ? "Check Student Visibility" : `${warningCount} Visibility Warnings`,
              message: warningCount === 1
                ? "The push succeeded, but this subject is not available to every student in the selected target."
                : "The push succeeded, but some subjects are not available to every student in the selected target.",
              details: warningDetails,
              duration: 11000
            });

            warningDetails.forEach((warning) => log(warning, "warn"));
          }

          /* ---------------------------------------------------
             PARTIAL FAILURE

             Compatible subjects push successfully while
             incompatible subjects are skipped.
          --------------------------------------------------- */

          if (failedCount) {
            const failureDetails = formatFailures(failures);

            showPushNotice({
              type: "error",
              title: `${failedCount} ${failedCount === 1 ? "Subject" : "Subjects"} Skipped`,
              message: pushedCount === 1 ? "1 compatible subject was published successfully." : `${pushedCount} compatible subjects were published successfully.`,
              details: failureDetails,
              duration: 11000
            });

            failureDetails.forEach((reason) => log(reason, "warn"));
          }

          /* ---------------------------------------------------
             CLEAR SUCCESSFUL QUEUE
          --------------------------------------------------- */

          if (window.EmisUploads?.clearSelection) window.EmisUploads.clearSelection();
          else if (window.EmisUploads?.selectedFiles) window.EmisUploads.selectedFiles.clear();

          root.querySelectorAll(".row-select").forEach((checkbox) => { checkbox.checked = false; });

          const checkAll = root.querySelector("#checkAllUploads");
          if (checkAll) { checkAll.checked = false; checkAll.indeterminate = false; }

          updatePushCount();

          /* ---------------------------------------------------
             UPDATE ACTIVE PORTAL STATE
          --------------------------------------------------- */

          updateServerActiveStatus(
            output.active_year || output.latest_year || year,
            output.class_active_years || {},
            output.class_active_terms || {}
          );

          updateTargetPreview();
          root.querySelector("#refreshPortalMap")?.click();

        } catch (error) {
          console.error("Push error:", error);

          showPushNotice({
            type: "error",
            title: "Push Failed",
            message: error.message || "The portal push could not be completed.",
            duration: 9000
          });

          log(error.message || "Push failed.", "error");

        } finally {
          btnPush.disabled = false;
          btnPush.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Push Selected`;
        }
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
          showMessage("Select a year first.", "error");
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
         SELECT / QUEUE ALL VISIBLE SUBJECTS
      ======================================================== */

      btnPushAll?.addEventListener("click", () => {
        const uploads = window.EmisUploads;

        if (!uploads?.convertedItems?.length) {
          showMessage("No subjects found in the library.", "error");
          return;
        }


        let items = [...uploads.convertedItems];


        /* Current class filter */

        if (uploads.activeClass && uploads.activeClass !== "ALL") {
          items = items.filter((item) => this.getItemClass(item) === uploads.activeClass);
        }


        /* ====================================================
           CURRENT TERM FILTER — JSS + HYBRID SS
        ==================================================== */

        if (uploads.activeClass && this.isTermAwareClass(uploads.activeClass) && uploads.activeTerm && uploads.activeTerm !== "ALL") {

          /* SS GENERAL */

          if (uploads.activeTerm === "GENERAL") {
            items = items.filter((item) => !this.getItemTerm(item));


          /* FIRST / SECOND / THIRD */

          } else {
            const wantedTerm = this.normalizeTerm(uploads.activeTerm);


            /* JSS exact term only */

            if (this.isTermRequiredClass(uploads.activeClass)) {
              items = items.filter((item) => this.getItemTerm(item) === wantedTerm);


            /* SS selected term + General fallback */

            } else {
              const specificKeys = new Set(
                items
                  .filter((item) => this.getItemTerm(item) === wantedTerm)
                  .map((item) => `${item.year}|${this.getItemClass(item)}|${item.filename}`)
              );

              items = items.filter((item) => {
                const itemTerm = this.getItemTerm(item);

                if (itemTerm === wantedTerm) return true;
                if (itemTerm) return false;

                return !specificKeys.has(`${item.year}|${this.getItemClass(item)}|${item.filename}`);
              });
            }
          }
        }


        /* Current subject filter */

        if (uploads.activeSubject && uploads.activeSubject !== "ALL") {
          const wantedSubject = String(uploads.activeSubject).toLowerCase().trim();

          items = items.filter((item) => String(item.subject || "").toLowerCase().trim() === wantedSubject);
        }


        if (!items.length) {
          showMessage("No visible subjects to queue.", "error");
          return;
        }


        uploads.selectedFiles.clear();


        items.forEach((item) => {
          if (uploads.makeSelectionKey) {
            uploads.selectedFiles.add(uploads.makeSelectionKey(item));

          } else {
            const year = item.year;
            const cls = this.getItemClass(item);
            const term = this.getItemTerm(item) || "NONE";

            uploads.selectedFiles.add(`${year}|${cls}|${term}|${item.filename}`);
          }
        });


        root.querySelectorAll(".upload-row").forEach((row) => {
          const checkbox = row.querySelector(".row-select");

          if (!checkbox) return;

          const year = row.dataset.year;
          const filename = row.dataset.filename;
          const cls = this.normalizeClassLevel(row.dataset.class);
          const term = this.normalizeTerm(row.dataset.term) || "NONE";
          const key = `${year}|${cls}|${term}|${filename}`;

          checkbox.checked = uploads.selectedFiles.has(key);
        });


        updatePushCount();
        syncTargetFromSelection();

        showMessage(`${items.length} file(s) queued. Select target arm and push.`, "success");
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
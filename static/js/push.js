/* ======================================================================
   EMIS CBT — PORTAL PUSH CONTROLLER

   Supports:
     • Broad class targets
     • Exact class-arm targets
     • JSS1 / JSS2 / JSS3 term-aware routing
     • SS1 / SS2 / SS3 non-term routing
     • Year-aware JSON selection
     • Term-aware push confirmation
     • Term-aware clear operations
     • Active year / term status
     • Backward compatibility with existing portal API
====================================================================== */

(() => {
  if (window.__EMIS_PUSH_BOUND__) return;
  window.__EMIS_PUSH_BOUND__ = true;


  window.EmisPush = {

    /* ==========================================================
       CONFIGURATION
    ========================================================== */

    supportedClasses: [
      "JSS1",
      "JSS2",
      "JSS3",
      "SS1",
      "SS2",
      "SS3"
    ],

    termAwareClasses: [
      "JSS1",
      "JSS2",
      "JSS3"
    ],

    validTerms: [
      "FIRST",
      "SECOND",
      "THIRD"
    ],

    classArms: {
      JSS1: ["JSS1A", "JSS1B", "JSS1C"],
      JSS2: ["JSS2A", "JSS2B", "JSS2C"],
      JSS3: ["JSS3A", "JSS3B", "JSS3C"],

      SS1: [
        "SS1_GOLD",
        "SS1_SILVER",
        "SS1_DIAMOND",
        "SS1B"
      ],

      SS2: [
        "SS2_GOLD",
        "SS2_SILVER",
        "SS2_DIAMOND",
        "SS2B"
      ],

      SS3: [
        "SS3_GOLD",
        "SS3_SILVER",
        "SS3_DIAMOND",
        "SS3B"
      ]
    },


    /* ==========================================================
       NORMALIZATION
    ========================================================== */

    normalize(value) {
      return String(value || "")
        .toUpperCase()
        .trim()
        .replaceAll("-", "_");
    },


    normalizeClassLevel(value) {
      const compact = this.normalize(value)
        .replaceAll("_", "")
        .replaceAll(" ", "");

      for (const cls of this.supportedClasses) {
        if (compact === cls || compact.startsWith(cls)) {
          return cls;
        }
      }

      return "";
    },


    normalizeClassArm(value, fallbackLevel = "") {
      const raw = this.normalize(value);

      const compact = raw
        .replaceAll("_", "")
        .replaceAll(" ", "");

      const level = (
        this.normalizeClassLevel(raw)
        || this.normalizeClassLevel(fallbackLevel)
      );

      if (!level) return "";

      /* JSS */
      if (level.startsWith("JSS")) {
        for (const arm of ["A", "B", "C"]) {
          if (compact === `${level}${arm}`) {
            return `${level}${arm}`;
          }
        }

        return level;
      }

      /* SS Streams */
      for (const label of ["GOLD", "SILVER", "DIAMOND"]) {
        if (compact.includes(label)) {
          return `${level}_${label}`;
        }
      }

      /* Arts / Commercial combined class */
      if (compact === `${level}B`) {
        return `${level}B`;
      }

      return level;
    },


    normalizeTerm(value) {
      const raw = String(value || "")
        .trim()
        .toUpperCase();

      const aliases = {
        "1": "FIRST",
        "1ST": "FIRST",
        "FIRST": "FIRST",
        "FIRST TERM": "FIRST",
        "1ST TERM": "FIRST",
        "TERM 1": "FIRST",
        "TERM1": "FIRST",

        "2": "SECOND",
        "2ND": "SECOND",
        "SECOND": "SECOND",
        "SECOND TERM": "SECOND",
        "2ND TERM": "SECOND",
        "TERM 2": "SECOND",
        "TERM2": "SECOND",

        "3": "THIRD",
        "3RD": "THIRD",
        "THIRD": "THIRD",
        "THIRD TERM": "THIRD",
        "3RD TERM": "THIRD",
        "TERM 3": "THIRD",
        "TERM3": "THIRD"
      };

      return aliases[raw] || null;
    },


    termLabel(term) {
      const normalized = this.normalizeTerm(term);

      const labels = {
        FIRST: "1st Term",
        SECOND: "2nd Term",
        THIRD: "3rd Term"
      };

      return labels[normalized] || "—";
    },


    isTermAwareClass(classLevel) {
      return this.termAwareClasses.includes(
        this.normalizeClassLevel(classLevel)
      );
    },


    isValidTarget(classLevel, classArm) {
      if (!classLevel || !classArm) return false;
      if (!this.supportedClasses.includes(classLevel)) return false;

      if (classArm === classLevel) {
        return true;
      }

      return (this.classArms[classLevel] || [])
        .includes(classArm);
    },


    /* ==========================================================
       SELECTED FILE HELPERS
    ========================================================== */

    getSelectedItems() {
      if (window.EmisUploads?.getSelectedItems) {
        return window.EmisUploads.getSelectedItems();
      }

      /*
         Backward compatibility with old queue:
         YEAR:FILENAME
      */
      const selected = [
        ...(window.EmisUploads?.selectedFiles || [])
      ];

      return selected.map((entry) => {
        const raw = String(entry || "");

        if (raw.includes("|")) {
          const [
            year,
            classCategory,
            rawTerm,
            ...filenameParts
          ] = raw.split("|");

          return {
            year,
            filename: filenameParts.join("|"),
            class_category: classCategory,
            term: rawTerm === "NONE" ? null : rawTerm
          };
        }

        const [year, ...filenameParts] = raw.split(":");

        return {
          year,
          filename: filenameParts.join(":"),
          class_category: "",
          term: null
        };
      });
    },


    getItemClass(item) {
      if (window.EmisUploads?.getItemClass) {
        return window.EmisUploads.getItemClass(item);
      }

      return this.normalizeClassLevel(
        item?.class_category
        || item?.class_level
        || item?.class
      );
    },


    getItemTerm(item) {
      if (window.EmisUploads?.getItemTerm) {
        return window.EmisUploads.getItemTerm(item);
      }

      return this.normalizeTerm(
        item?.term
        || item?.exam_term
        || item?.academic_term
      );
    },


    getPushFileEntries(items) {
      return items.map((item) => {
        return `${item.year}:${item.filename}`;
      });
    },


    /* ==========================================================
       PUSH CONFIRMATION
    ========================================================== */

    showPushConfirm({ year, classArm, term = null, count }) {
      return new Promise((resolve) => {
        const modal = document.querySelector("#pushConfirmModal");
        const text = document.querySelector("#pushConfirmText");

        const yearEl = document.querySelector("#pushConfirmYear");
        const targetEl = document.querySelector("#pushConfirmTarget");
        const termEl = document.querySelector("#pushConfirmTerm");
        const countEl = document.querySelector("#pushConfirmCount");

        const cancelBtn = document.querySelector("#cancelPushConfirm");
        const acceptBtn = document.querySelector("#acceptPushConfirm");

        const backdrop = modal?.querySelector(
          ".push-confirm-backdrop"
        );

        const targetText = term
          ? `${classArm} • ${this.termLabel(term)}`
          : classArm;

        if (!modal) {
          resolve(
            confirm(
              `Push ${count} subject(s) to ${targetText}?`
            )
          );

          return;
        }

        if (text) {
          text.textContent = (
            `You are about to publish ${count} selected `
            + `exam file(s) to ${targetText}.`
          );
        }

        if (yearEl) {
          yearEl.textContent = `Year: ${year}`;
        }

        if (targetEl) {
          targetEl.textContent = `Target: ${classArm}`;
        }

        if (termEl) {
          if (term) {
            termEl.textContent = `Term: ${this.termLabel(term)}`;
            termEl.classList.remove("hidden");
          } else {
            termEl.classList.add("hidden");
          }
        }

        if (countEl) {
          countEl.textContent = `Subjects: ${count}`;
        }

        modal.classList.remove("hidden");


        const close = (answer) => {
          modal.classList.add("hidden");

          cancelBtn?.removeEventListener(
            "click",
            onCancel
          );

          acceptBtn?.removeEventListener(
            "click",
            onAccept
          );

          backdrop?.removeEventListener(
            "click",
            onCancel
          );

          resolve(answer);
        };


        const onCancel = () => close(false);
        const onAccept = () => close(true);

        cancelBtn?.addEventListener(
          "click",
          onCancel
        );

        acceptBtn?.addEventListener(
          "click",
          onAccept
        );

        backdrop?.addEventListener(
          "click",
          onCancel
        );
      });
    },


    /* ==========================================================
       INITIALIZATION
    ========================================================== */

    init() {
      const root = document.querySelector(
        ".uploads-wrapper"
      );

      if (!root) return;


      /* ========================================================
         MAIN PUSH PANEL
      ======================================================== */

      const btnPush = root.querySelector(
        "#pushSelectedToPortal"
      );

      const btnClear = root.querySelector(
        "#clearPortalSubjects"
      );

      const btnPushAll = root.querySelector(
        "#btnPushAllSubjects"
      );

      const pushYearSel = root.querySelector(
        "#pushYearSelector"
      );

      const pushClassLevel = root.querySelector(
        "#pushClassLevel"
      );

      const pushClassArm = root.querySelector(
        "#pushClassArm"
      );

      const pushTermField = root.querySelector(
        "#pushTermField"
      );

      const pushTermSelector = root.querySelector(
        "#pushTermSelector"
      );


      /* ========================================================
         STATUS LABELS
      ======================================================== */

      const activeYearLabel = root.querySelector(
        "#activeYearLabel"
      );

      const activeTargetLabel = root.querySelector(
        "#activeTargetLabel"
      );

      const activeTermLabelWrap = root.querySelector(
        "#activeTermLabelWrap"
      );

      const activeTermLabel = root.querySelector(
        "#activeTermLabel"
      );

      const statTargetArm = root.querySelector(
        "#statTargetArm"
      );


      /* ========================================================
         ACTIVITY LOG
      ======================================================== */

      const logBody = root.querySelector(
        "#portalLogBody"
      );


      /* ========================================================
         CLEAR MODAL
      ======================================================== */

      const clearModal = root.querySelector(
        "#clearPortalModal"
      );

      const clearClassLevel = root.querySelector(
        "#clearClassLevel"
      );

      const clearClassArm = root.querySelector(
        "#clearClassArm"
      );

      const clearTermField = root.querySelector(
        "#clearTermField"
      );

      const clearTermSelector = root.querySelector(
        "#clearTermSelector"
      );

      const confirmClearTarget = root.querySelector(
        "#confirmClearTarget"
      );

      const confirmClearAllTargets = root.querySelector(
        "#confirmClearAllTargets"
      );


      if (
        !btnPush
        || !pushYearSel
        || !pushClassLevel
        || !pushClassArm
      ) {
        return;
      }


      /* ========================================================
         MESSAGE
      ======================================================== */

      const showMessage = (message, type = "success") => {
        if (typeof flashMessage === "function") {
          flashMessage(message, type);
        } else {
          alert(message);
        }
      };


      /* ========================================================
         LOG
      ======================================================== */

      const log = (message, type = "info") => {
        if (!logBody) return;

        const placeholder = logBody.querySelector(
          ".log-placeholder"
        );

        if (placeholder) {
          logBody.innerHTML = "";
        }

        const entry = document.createElement("div");

        entry.className = (
          type === "success"
            ? "log-item success"
            : type === "error"
              ? "log-item error"
              : type === "warn"
                ? "log-item warn"
                : "log-item"
        );

        const time = new Date().toLocaleTimeString(
          [],
          {
            hour: "2-digit",
            minute: "2-digit"
          }
        );

        entry.innerHTML = `
          <strong>${time}</strong>
          <span>${message}</span>
        `;

        logBody.appendChild(entry);
        logBody.scrollTop = logBody.scrollHeight;
      };


      /* ========================================================
         PUSH COUNT
      ======================================================== */

      const updatePushCount = () => {
        const count = (
          window.EmisUploads?.selectedFiles?.size
          || 0
        );

        const pushCount = root.querySelector(
          "#pushCount"
        );

        const pushCountSide = root.querySelector(
          "#pushCountSide"
        );

        if (pushCount) {
          pushCount.textContent = count;
        }

        if (pushCountSide) {
          pushCountSide.textContent = count;
        }

        if (window.EmisUploads?.updatePushCount) {
          window.EmisUploads.updatePushCount();
        }
      };


      /* ========================================================
         CLASS ARM OPTIONS
      ======================================================== */

      const buildArmOptions = (
        selectElement,
        classLevel
      ) => {
        if (!selectElement) return;

        if (!classLevel) {
          selectElement.innerHTML = `
            <option value="" disabled selected>
              Select class first
            </option>
          `;

          return;
        }

        const arms = this.classArms[classLevel] || [];

        selectElement.innerHTML = `
          <option value="" selected>
            Select Arm / Group
          </option>

          <option value="${classLevel}">
            ${classLevel} — Whole Class
          </option>

          ${arms
            .map((arm) => `
              <option value="${arm}">
                ${arm}
              </option>
            `)
            .join("")}
        `;
      };


      /* ========================================================
         TERM UI
      ======================================================== */

      const updatePushTermUI = () => {
        const classLevel = this.normalizeClassLevel(
          pushClassLevel.value
        );

        const termAware = this.isTermAwareClass(
          classLevel
        );

        if (pushTermField) {
          pushTermField.classList.toggle(
            "hidden",
            !termAware
          );
        }

        if (!termAware && pushTermSelector) {
          pushTermSelector.value = "";
        }

        updateTargetPreview();
      };


      const updateClearTermUI = () => {
        if (!clearClassLevel) return;

        const classLevel = this.normalizeClassLevel(
          clearClassLevel.value
        );

        const termAware = this.isTermAwareClass(
          classLevel
        );

        if (clearTermField) {
          clearTermField.classList.toggle(
            "hidden",
            !termAware
          );
        }

        if (!termAware && clearTermSelector) {
          clearTermSelector.value = "";
        }
      };


      /* ========================================================
         TARGET PREVIEW
      ======================================================== */

      const updateTargetPreview = () => {
        const year = pushYearSel.value;

        const classLevel = this.normalizeClassLevel(
          pushClassLevel.value
        );

        const classArm = this.normalizeClassArm(
          pushClassArm.value,
          classLevel
        );

        const term = this.normalizeTerm(
          pushTermSelector?.value
        );

        if (activeYearLabel) {
          activeYearLabel.textContent = year || "—";
        }

        if (activeTargetLabel) {
          activeTargetLabel.textContent = (
            classArm
            || classLevel
            || "—"
          );
        }

        if (statTargetArm) {
          statTargetArm.textContent = (
            classArm
            || classLevel
            || "—"
          );
        }

        if (activeTermLabelWrap) {
          const showTerm = (
            this.isTermAwareClass(classLevel)
            && term
          );

          activeTermLabelWrap.classList.toggle(
            "hidden",
            !showTerm
          );
        }

        if (activeTermLabel) {
          activeTermLabel.textContent = term
            ? this.termLabel(term)
            : "—";
        }
      };


      /* ========================================================
         ACTIVE PORTAL STATUS
      ======================================================== */

      const updateServerActiveStatus = (
        latestYear,
        activeYears = {},
        activeTerms = {}
      ) => {
        if (activeYearLabel && !pushYearSel.value) {
          activeYearLabel.textContent = (
            latestYear
            || "—"
          );
        }

        if (activeYearLabel) {
          const yearTitles = Object.entries(
            activeYears || {}
          )
            .map(([target, year]) => {
              const term = activeTerms?.[target];

              return term
                ? `${target}: ${year} / ${this.termLabel(term)}`
                : `${target}: ${year}`;
            })
            .join(" • ");

          activeYearLabel.title = yearTitles;
        }
      };


      const fetchLatestState = async () => {
        try {
          const response = await fetch(
            "/api/push_latest_year"
          );

          const data = await response.json();

          if (!response.ok) {
            return;
          }

          updateServerActiveStatus(
            data.latest_year || data.year || "",
            data.class_active_years || {},
            data.class_active_terms || {}
          );

        } catch (error) {
          console.warn(
            "Latest portal state fetch failed:",
            error
          );
        }
      };


      /* ========================================================
         AUTO SYNC PUSH PANEL FROM CURRENT SELECTION
      ======================================================== */

      const syncTargetFromSelection = () => {
        const selectedItems = this.getSelectedItems();

        if (!selectedItems.length) {
          return;
        }

        const years = [
          ...new Set(
            selectedItems
              .map((item) => String(item.year || ""))
              .filter(Boolean)
          )
        ];

        const classes = [
          ...new Set(
            selectedItems
              .map((item) => this.getItemClass(item))
              .filter(Boolean)
          )
        ];

        const terms = [
          ...new Set(
            selectedItems
              .map((item) => this.getItemTerm(item))
              .filter(Boolean)
          )
        ];


        /* Year */
        if (years.length === 1) {
          const year = years[0];

          const optionExists = [
            ...pushYearSel.options
          ].some(
            (option) => option.value === year
          );

          if (optionExists) {
            pushYearSel.value = year;
          }
        }


/* Class */
if (classes.length === 1) {
  const classLevel = classes[0];

  const optionExists = [...pushClassLevel.options]
    .some((option) => option.value === classLevel);

  if (optionExists) {
    const previousLevel = this.normalizeClassLevel(pushClassLevel.value);
    const previousArm = this.normalizeClassArm(
      pushClassArm.value,
      previousLevel || classLevel
    );

    pushClassLevel.value = classLevel;

    /*
     * Do not rebuild the arm dropdown when the selected
     * class is already the same class.
     *
     * Rebuilding here was wiping out JSS1A / JSS1B / JSS1C
     * immediately before the push request.
     */
    if (previousLevel !== classLevel || !pushClassArm.options.length) {
      buildArmOptions(pushClassArm, classLevel);

      const armStillExists = [...pushClassArm.options]
        .some((option) => option.value === previousArm);

      if (previousArm && armStillExists) {
        pushClassArm.value = previousArm;
      }
    }

    updatePushTermUI();
  }
}


        /* JSS Term */
        if (
          classes.length === 1
          && this.isTermAwareClass(classes[0])
          && terms.length === 1
          && pushTermSelector
        ) {
          pushTermSelector.value = terms[0];
        }

        updateTargetPreview();
      };


      /* ========================================================
         VALIDATE CURRENT PUSH SELECTION
      ======================================================== */

      const validatePushSelection = (
        year,
        classLevel,
        term,
        items
      ) => {
        if (!items.length) {
          return {
            valid: false,
            message: "No JSON file selected."
          };
        }


        /* ----------------------------------------------------
           Ensure all selected files have metadata
        ---------------------------------------------------- */

        const missingFilename = items.some(
          (item) => !item?.filename
        );

        if (missingFilename) {
          return {
            valid: false,
            message: "One or more selected files are invalid."
          };
        }


        /* ----------------------------------------------------
           Year
        ---------------------------------------------------- */

        const years = [
          ...new Set(
            items.map(
              (item) => String(item.year || "")
            )
          )
        ];

        if (years.length > 1) {
          return {
            valid: false,
            message: (
              "Selected files contain different exam years. "
              + "Push one year at a time."
            )
          };
        }

        if (
          years.length === 1
          && years[0]
          && String(year) !== years[0]
        ) {
          return {
            valid: false,
            message: (
              `Selected files belong to ${years[0]}, `
              + `but Push Year is ${year}.`
            )
          };
        }


        /* ----------------------------------------------------
           Class
        ---------------------------------------------------- */

        const classes = [
          ...new Set(
            items
              .map((item) => this.getItemClass(item))
              .filter(Boolean)
          )
        ];

        if (classes.length > 1) {
          return {
            valid: false,
            message: (
              "Selected files contain different classes. "
              + "Push one class at a time."
            )
          };
        }

        if (
          classes.length === 1
          && classes[0] !== classLevel
        ) {
          return {
            valid: false,
            message: (
              `Selected files are for ${classes[0]}, `
              + `not ${classLevel}.`
            )
          };
        }


        /* ----------------------------------------------------
           JSS Term
        ---------------------------------------------------- */

        if (this.isTermAwareClass(classLevel)) {
          if (!term) {
            return {
              valid: false,
              message: `Select a term for ${classLevel}.`
            };
          }

          const terms = [
            ...new Set(
              items
                .map((item) => this.getItemTerm(item))
                .filter(Boolean)
            )
          ];

          if (terms.length > 1) {
            return {
              valid: false,
              message: (
                "Selected JSS files contain different terms. "
                + "Push one term at a time."
              )
            };
          }

          const missingTerms = items.some(
            (item) => !this.getItemTerm(item)
          );

          if (missingTerms) {
            return {
              valid: false,
              message: (
                "One or more JSS files have no term assigned. "
                + "Please fix the JSON metadata first."
              )
            };
          }

          if (
            terms.length === 1
            && terms[0] !== term
          ) {
            return {
              valid: false,
              message: (
                `Selected files are ${this.termLabel(terms[0])}, `
                + `but target is ${this.termLabel(term)}.`
              )
            };
          }
        }

        return {
          valid: true
        };
      };


      /* ========================================================
         MAIN CLASS SELECT
      ======================================================== */

      pushClassLevel.addEventListener(
        "change",
        () => {
          const classLevel = this.normalizeClassLevel(
            pushClassLevel.value
          );

          buildArmOptions(
            pushClassArm,
            classLevel
          );

          updatePushTermUI();
          updateTargetPreview();
        }
      );


      pushClassArm.addEventListener(
        "change",
        updateTargetPreview
      );


      pushYearSel.addEventListener(
        "change",
        updateTargetPreview
      );


      pushTermSelector?.addEventListener(
        "change",
        updateTargetPreview
      );


      /* ========================================================
         PUSH SELECTED
      ======================================================== */

      btnPush.addEventListener(
        "click",
        async () => {
          syncTargetFromSelection();

          const year = String(
            pushYearSel.value || ""
          ).trim();

          const classLevel = this.normalizeClassLevel(
            pushClassLevel.value
          );

          const classArm = this.normalizeClassArm(
            pushClassArm.value,
            classLevel
          );

          const term = this.isTermAwareClass(classLevel)
            ? this.normalizeTerm(
                pushTermSelector?.value
              )
            : null;

          const selectedItems = this.getSelectedItems();


          /* --------------------------------------------------
             Basic target validation
          -------------------------------------------------- */

          if (!year) {
            showMessage(
              "Select a year first.",
              "error"
            );

            return;
          }

          if (!this.isValidTarget(
            classLevel,
            classArm
          )) {
            showMessage(
              "Select class level and class arm/group.",
              "error"
            );

            return;
          }


          /* --------------------------------------------------
             Selection validation
          -------------------------------------------------- */

          const validation = validatePushSelection(
            year,
            classLevel,
            term,
            selectedItems
          );

          if (!validation.valid) {
            showMessage(
              validation.message,
              "error"
            );

            return;
          }


          const files = this.getPushFileEntries(
            selectedItems
          );


          /* --------------------------------------------------
             Confirmation
          -------------------------------------------------- */

          const confirmed = await this.showPushConfirm({
            year,
            classArm,
            term,
            count: files.length
          });

          if (!confirmed) {
            return;
          }


          /* --------------------------------------------------
             Push request
          -------------------------------------------------- */

          try {
            btnPush.disabled = true;

            btnPush.innerHTML = `
              <i class="fa-solid fa-spinner fa-spin"></i>
              Pushing...
            `;

            const targetText = term
              ? `${classArm} / ${this.termLabel(term)}`
              : classArm;

            log(
              `Pushing ${files.length} file(s) to ${targetText}...`
            );


            const response = await fetch(
              "/api/push",
              {
                method: "POST",

                headers: {
                  "Content-Type": "application/json"
                },

                body: JSON.stringify({
                  files,

                  year,

                  class_level: classLevel,
                  class_category: classLevel,

                  class_arm: classArm,
                  target_arm: classArm,

                  term
                })
              }
            );


            const output = await response.json();


            if (!response.ok || !output.success) {
              throw new Error(
                output.error
                || "Push failed"
              );
            }


            const pushedCount = (
              output.subject_count
              ?? output.subjects_pushed?.length
              ?? 0
            );

            const failedCount = (
              output.failed_count
              ?? output.failed?.length
              ?? 0
            );


            /* ------------------------------------------------
               Success
            ------------------------------------------------ */

            showMessage(
              term
                ? (
                    `Pushed ${pushedCount} subject(s) to `
                    + `${classArm} • ${this.termLabel(term)}.`
                  )
                : (
                    `Pushed ${pushedCount} subject(s) `
                    + `to ${classArm}.`
                  ),
              "success"
            );


            log(
              term
                ? (
                    `Pushed ${pushedCount} subject(s) to `
                    + `${classArm} • ${this.termLabel(term)}.`
                  )
                : (
                    `Pushed ${pushedCount} subject(s) `
                    + `to ${classArm}.`
                  ),
              "success"
            );


            /* ------------------------------------------------
               Failed files
            ------------------------------------------------ */

            if (failedCount) {
              const reasons = (
                output.failed || []
              )
                .slice(0, 3)
                .map((item) => item.reason)
                .filter(Boolean)
                .join(" • ");

              log(
                `${failedCount} file(s) failed.${reasons ? ` ${reasons}` : ""}`,
                "warn"
              );
            }


            /* ------------------------------------------------
               Clear selection
            ------------------------------------------------ */

            if (window.EmisUploads?.clearSelection) {
              window.EmisUploads.clearSelection();

            } else if (
              window.EmisUploads?.selectedFiles
            ) {
              window.EmisUploads.selectedFiles.clear();
            }


            root.querySelectorAll(
              ".row-select"
            ).forEach((checkbox) => {
              checkbox.checked = false;
            });


            const checkAll = root.querySelector(
              "#checkAllUploads"
            );

            if (checkAll) {
              checkAll.checked = false;
              checkAll.indeterminate = false;
            }


            updatePushCount();


            /* ------------------------------------------------
               Update active status
            ------------------------------------------------ */

            updateServerActiveStatus(
              output.active_year
              || output.latest_year
              || year,

              output.class_active_years
              || {},

              output.class_active_terms
              || {}
            );


            updateTargetPreview();


            /* Portal map refresh hook */
            root.querySelector(
              "#refreshPortalMap"
            )?.click();


          } catch (error) {
            console.error(
              "Push error:",
              error
            );

            showMessage(
              error.message
              || "Push failed.",
              "error"
            );

            log(
              error.message
              || "Push failed.",
              "error"
            );

          } finally {
            btnPush.disabled = false;

            btnPush.innerHTML = `
              <i class="fa-solid fa-cloud-arrow-up"></i>
              Push Selected
            `;
          }
        }
      );


      /* ========================================================
         OPEN CLEAR TARGET MODAL
      ======================================================== */

      btnClear?.addEventListener(
        "click",
        () => {
          const pushLevel = this.normalizeClassLevel(
            pushClassLevel.value
          );

          const pushArm = this.normalizeClassArm(
            pushClassArm.value,
            pushLevel
          );

          const pushTerm = this.normalizeTerm(
            pushTermSelector?.value
          );


          if (clearClassLevel && pushLevel) {
            clearClassLevel.value = pushLevel;

            buildArmOptions(
              clearClassArm,
              pushLevel
            );

            if (clearClassArm && pushArm) {
              clearClassArm.value = pushArm;
            }
          }


          updateClearTermUI();


          if (
            clearTermSelector
            && pushTerm
            && this.isTermAwareClass(pushLevel)
          ) {
            clearTermSelector.value = pushTerm;
          }


          if (clearModal) {
            clearModal.classList.remove(
              "hidden"
            );

          } else {
            /*
               Backward-compatible fallback.
            */
            clearSelectedTarget(
              pushYearSel.value,
              pushLevel,
              pushArm,
              pushTerm
            );
          }
        }
      );


      /* ========================================================
         CLEAR MODAL CLASS CHANGE
      ======================================================== */

      clearClassLevel?.addEventListener(
        "change",
        () => {
          const classLevel = this.normalizeClassLevel(
            clearClassLevel.value
          );

          buildArmOptions(
            clearClassArm,
            classLevel
          );

          updateClearTermUI();
        }
      );


      /* ========================================================
         CLEAR TARGET FUNCTION
      ======================================================== */

      const clearSelectedTarget = async (
        year,
        classLevel,
        classArm,
        term
      ) => {
        year = String(year || "").trim();

        classLevel = this.normalizeClassLevel(
          classLevel
        );

        classArm = this.normalizeClassArm(
          classArm,
          classLevel
        );

        term = this.isTermAwareClass(classLevel)
          ? this.normalizeTerm(term)
          : null;


        if (!year) {
          showMessage(
            "Select a year first.",
            "error"
          );

          return;
        }


        if (!this.isValidTarget(
          classLevel,
          classArm
        )) {
          showMessage(
            "Select class level and class arm/group to clear.",
            "error"
          );

          return;
        }


        if (
          this.isTermAwareClass(classLevel)
          && !term
        ) {
          showMessage(
            `Select a term for ${classLevel}.`,
            "error"
          );

          return;
        }


        const targetText = term
          ? `${year} / ${classArm} / ${this.termLabel(term)}`
          : `${year} / ${classArm}`;


        if (!confirm(
          `Clear pushed subjects for ${targetText}?`
        )) {
          return;
        }


        try {
          if (confirmClearTarget) {
            confirmClearTarget.disabled = true;

            confirmClearTarget.innerHTML = `
              <i class="fa-solid fa-spinner fa-spin"></i>
              Clearing...
            `;
          }


          const response = await fetch(
            "/api/clear",
            {
              method: "POST",

              headers: {
                "Content-Type": "application/json"
              },

              body: JSON.stringify({
                year,

                class_level: classLevel,
                class_category: classLevel,

                class_arm: classArm,
                target_arm: classArm,

                term
              })
            }
          );


          const output = await response.json();


          if (!response.ok || !output.success) {
            throw new Error(
              output.error
              || "Clear failed"
            );
          }


          showMessage(
            term
              ? (
                  `${classArm} • ${this.termLabel(term)} cleared.`
                )
              : `${classArm} cleared.`,
            "success"
          );


          log(
            `Cleared ${output.cleared}.`,
            "success"
          );


          clearModal?.classList.add(
            "hidden"
          );


          updateServerActiveStatus(
            output.latest_year || "",
            output.class_active_years || {},
            output.class_active_terms || {}
          );


          root.querySelector(
            "#refreshPortalMap"
          )?.click();


        } catch (error) {
          console.error(
            "Clear target error:",
            error
          );

          showMessage(
            error.message
            || "Clear failed.",
            "error"
          );

          log(
            error.message
            || "Clear failed.",
            "error"
          );

        } finally {
          if (confirmClearTarget) {
            confirmClearTarget.disabled = false;

            confirmClearTarget.innerHTML = `
              <i class="fa-solid fa-trash-can"></i>
              Clear Target
            `;
          }
        }
      };


      /* ========================================================
         CONFIRM CLEAR TARGET
      ======================================================== */

      confirmClearTarget?.addEventListener(
        "click",
        async () => {
          const year = pushYearSel.value;

          const classLevel = this.normalizeClassLevel(
            clearClassLevel?.value
          );

          const classArm = this.normalizeClassArm(
            clearClassArm?.value,
            classLevel
          );

          const term = this.normalizeTerm(
            clearTermSelector?.value
          );

          await clearSelectedTarget(
            year,
            classLevel,
            classArm,
            term
          );
        }
      );


      /* ========================================================
         CLEAR ALL PORTAL TARGETS
      ======================================================== */

      confirmClearAllTargets?.addEventListener(
        "click",
        async () => {
          const confirmed = confirm(
            "Clear ALL portal targets and all pushed subjects?\n\n"
            + "This affects every year, class and class arm."
          );

          if (!confirmed) {
            return;
          }


          try {
            confirmClearAllTargets.disabled = true;

            confirmClearAllTargets.innerHTML = `
              <i class="fa-solid fa-spinner fa-spin"></i>
              Clearing...
            `;


            const response = await fetch(
              "/api/clear",
              {
                method: "POST",

                headers: {
                  "Content-Type": "application/json"
                },

                body: JSON.stringify({
                  year: "ALL",
                  class_level: "ALL",
                  class_category: "ALL",
                  class_arm: "ALL",
                  target_arm: "ALL"
                })
              }
            );


            const output = await response.json();


            if (!response.ok || !output.success) {
              throw new Error(
                output.error
                || "Clear all failed"
              );
            }


            showMessage(
              "All portal targets cleared.",
              "success"
            );


            log(
              "All portal assignments cleared.",
              "success"
            );


            clearModal?.classList.add(
              "hidden"
            );


            updateServerActiveStatus(
              "",
              {},
              {}
            );


            root.querySelector(
              "#refreshPortalMap"
            )?.click();


          } catch (error) {
            console.error(
              "Clear all error:",
              error
            );

            showMessage(
              error.message
              || "Could not clear portal.",
              "error"
            );

            log(
              error.message
              || "Could not clear portal.",
              "error"
            );

          } finally {
            confirmClearAllTargets.disabled = false;

            confirmClearAllTargets.innerHTML = `
              <i class="fa-solid fa-triangle-exclamation"></i>
              Clear Everything
            `;
          }
        }
      );


      /* ========================================================
         SELECT / QUEUE ALL VISIBLE SUBJECTS
      ======================================================== */

      btnPushAll?.addEventListener(
        "click",
        () => {
          const uploads = window.EmisUploads;

          if (!uploads?.convertedItems?.length) {
            showMessage(
              "No subjects found in the library.",
              "error"
            );

            return;
          }


          let items = [
            ...uploads.convertedItems
          ];


          /* Current class filter */
          if (
            uploads.activeClass
            && uploads.activeClass !== "ALL"
          ) {
            items = items.filter((item) => {
              return this.getItemClass(item)
                === uploads.activeClass;
            });
          }


          /* Current JSS term filter */
          if (
            uploads.activeClass
            && this.isTermAwareClass(
              uploads.activeClass
            )
            && uploads.activeTerm
            && uploads.activeTerm !== "ALL"
          ) {
            items = items.filter((item) => {
              return this.getItemTerm(item)
                === uploads.activeTerm;
            });
          }


          /* Current subject filter */
          if (
            uploads.activeSubject
            && uploads.activeSubject !== "ALL"
          ) {
            const wantedSubject = String(
              uploads.activeSubject
            )
              .toLowerCase()
              .trim();

            items = items.filter((item) => {
              const subject = String(
                item.subject || ""
              )
                .toLowerCase()
                .trim();

              return subject === wantedSubject;
            });
          }


          if (!items.length) {
            showMessage(
              "No visible subjects to queue.",
              "error"
            );

            return;
          }


          uploads.selectedFiles.clear();


          items.forEach((item) => {
            if (uploads.makeSelectionKey) {
              uploads.selectedFiles.add(
                uploads.makeSelectionKey(item)
              );

            } else {
              const year = item.year;
              const cls = this.getItemClass(item);
              const term = this.getItemTerm(item) || "NONE";

              uploads.selectedFiles.add(
                `${year}|${cls}|${term}|${item.filename}`
              );
            }
          });


          root.querySelectorAll(
            ".upload-row"
          ).forEach((row) => {
            const checkbox = row.querySelector(
              ".row-select"
            );

            if (!checkbox) return;

            const year = row.dataset.year;
            const filename = row.dataset.filename;

            const cls = this.normalizeClassLevel(
              row.dataset.class
            );

            const term = (
              this.normalizeTerm(row.dataset.term)
              || "NONE"
            );

            const key = (
              `${year}|${cls}|${term}|${filename}`
            );

            checkbox.checked = (
              uploads.selectedFiles.has(key)
            );
          });


          updatePushCount();
          syncTargetFromSelection();


          showMessage(
            `${items.length} file(s) queued. Select target arm and push.`,
            "success"
          );
        }
      );


      /* ========================================================
         OBSERVE QUEUE CHANGES
         Keeps target selectors synced after table selections.
      ======================================================== */

      root.addEventListener(
        "change",
        (event) => {
          if (
            event.target.matches(
              ".row-select, #checkAllUploads"
            )
          ) {
            setTimeout(() => {
              updatePushCount();
              syncTargetFromSelection();
            }, 0);
          }
        }
      );


      root.querySelector(
        "#selectAllVisible"
      )?.addEventListener(
        "click",
        () => {
          setTimeout(() => {
            updatePushCount();
            syncTargetFromSelection();
          }, 0);
        }
      );


      root.querySelector(
        "#clearQueue"
      )?.addEventListener(
        "click",
        () => {
          setTimeout(
            updatePushCount,
            0
          );
        }
      );


      /* ========================================================
         INITIAL STATE
      ======================================================== */

      const currentLevel = this.normalizeClassLevel(
        pushClassLevel.value
      );

      if (currentLevel) {
        buildArmOptions(
          pushClassArm,
          currentLevel
        );
      }


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
    const wrapper = document.querySelector(
      ".uploads-wrapper"
    );

    if (
      !wrapper
      || wrapper.__push_initialized__
    ) {
      return;
    }

    wrapper.__push_initialized__ = true;

    window.EmisPush.init();
  };


  if (
    document.readyState === "complete"
    || document.readyState === "interactive"
  ) {
    autoInitPush();

  } else {
    document.addEventListener(
      "DOMContentLoaded",
      autoInitPush
    );
  }


  /* ==========================================================
     DYNAMIC / SPA PAGE SUPPORT
  ========================================================== */

  new MutationObserver(
    autoInitPush
  ).observe(
    document.body,
    {
      childList: true,
      subtree: true
    }
  );

})();
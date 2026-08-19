/* ==========================================================
   EMIS CBT — UPLOADS / PAST QUESTION LIBRARY

   Supports:
     • JSS1 / JSS2 / JSS3 — Term Aware
     • SS1 / SS2 / SS3 — Non-Term Aware
     • Year filtering
     • Class filtering
     • Term filtering
     • Subject filtering
     • Search
     • JSON preview
     • JSON delete
     • Push queue selection
========================================================== */


/* ==========================================================
   GLOBAL FLASH MESSAGE
========================================================== */

function flashMessage(text, type = "success") {
  let fm = document.getElementById("flashMessage");

  if (!fm) {
    fm = document.createElement("div");
    fm.id = "flashMessage";
    fm.className = "flash-message";
    document.body.appendChild(fm);
  }

  fm.textContent = text;
  fm.className = `flash-message ${type} show`;

  clearTimeout(window.__emisUploadFlashTimer);

  window.__emisUploadFlashTimer = setTimeout(() => {
    fm.classList.remove("show");
  }, 3000);
}


/* ==========================================================
   MAIN UPLOAD LIBRARY CONTROLLER
========================================================== */

(() => {
  if (window.__EMIS_UPLOADS_BOUND__) return;
  window.__EMIS_UPLOADS_BOUND__ = true;

  window.EmisUploads = {

    /* ======================================================
       STATE
    ====================================================== */

    activeYear: null,
    activeClass: "ALL",
    activeTerm: "ALL",
    activeSubject: "ALL",

    convertedItems: [],
    selectedFiles: new Set(),

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


    /* ======================================================
       NORMALIZERS
    ====================================================== */

    normalizeClass(value) {
      return String(value || "").toUpperCase().trim();
    },

    normalizeTerm(value) {
      const raw = String(value || "").trim().toUpperCase();

      const aliases = {
        "1": "FIRST",
        "1ST": "FIRST",
        "FIRST": "FIRST",
        "FIRST TERM": "FIRST",
        "TERM 1": "FIRST",
        "TERM1": "FIRST",

        "2": "SECOND",
        "2ND": "SECOND",
        "SECOND": "SECOND",
        "SECOND TERM": "SECOND",
        "TERM 2": "SECOND",
        "TERM2": "SECOND",

        "3": "THIRD",
        "3RD": "THIRD",
        "THIRD": "THIRD",
        "THIRD TERM": "THIRD",
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

    normalizeSubject(value) {
      return String(value || "")
        .toLowerCase()
        .replaceAll("_", " ")
        .replaceAll("-", " ")
        .replace(/\s+/g, " ")
        .trim();
    },

    isTermAwareClass(value) {
      return this.termAwareClasses.includes(
        this.normalizeClass(value)
      );
    },


    /* ======================================================
       ITEM / QUEUE HELPERS
    ====================================================== */

    getItemClass(item) {
      return this.normalizeClass(
        item?.class_category
        || item?.class_level
        || item?.class
        || ""
      );
    },

    getItemTerm(item) {
      const cls = this.getItemClass(item);

      if (!this.isTermAwareClass(cls)) {
        return null;
      }

      return this.normalizeTerm(
        item?.term
        || item?.exam_term
        || item?.academic_term
      );
    },

    getSubjectLabel(item) {
      const subject = String(item?.subject || "").trim();

      if (subject) {
        return subject;
      }

      const filename = String(item?.filename || "")
        .replace(/\.json$/i, "")
        .replace(/_(jss1|jss2|jss3|ss1|ss2|ss3)$/i, "")
        .replaceAll("_", " ")
        .replaceAll("-", " ")
        .replace(/\s+/g, " ")
        .trim();

      return filename || "Unknown";
    },

    makeSelectionKey(item) {
      const year = String(item?.year || this.activeYear || "");
      const cls = this.getItemClass(item) || "UNKNOWN";
      const term = this.getItemTerm(item) || "NONE";
      const filename = String(item?.filename || "");

      return `${year}|${cls}|${term}|${filename}`;
    },

    parseSelectionKey(key) {
      const [year, classCategory, rawTerm, ...filenameParts] = String(key || "").split("|");

      return {
        year,
        class_category: classCategory,
        term: rawTerm === "NONE" ? null : rawTerm,
        filename: filenameParts.join("|")
      };
    },

    getMeta(filename, year, classCategory = null, term = null) {
      const wantedClass = classCategory
        ? this.normalizeClass(classCategory)
        : null;

      const wantedTerm = term
        ? this.normalizeTerm(term)
        : null;

      return this.convertedItems.find((item) => {
        if (String(item.filename) !== String(filename)) return false;
        if (String(item.year) !== String(year)) return false;

        if (wantedClass && this.getItemClass(item) !== wantedClass) {
          return false;
        }

        if (wantedTerm && this.getItemTerm(item) !== wantedTerm) {
          return false;
        }

        return true;
      });
    },

    getSelectedItems() {
      return [...this.selectedFiles]
        .map((key) => {
          const selected = this.parseSelectionKey(key);

          return this.getMeta(
            selected.filename,
            selected.year,
            selected.class_category,
            selected.term
          ) || selected;
        })
        .filter(Boolean);
    },

    getSelectedPushEntries() {
      return this.getSelectedItems().map((item) => ({
        year: String(item.year || ""),
        filename: String(item.filename || ""),
        class_category: this.getItemClass(item),
        term: this.getItemTerm(item)
      }));
    },

    clearSelection() {
      this.selectedFiles.clear();
      this.updatePushCount();
    },


    /* ======================================================
       PUSH COUNT
    ====================================================== */

    updatePushCount() {
      const count = this.selectedFiles.size;

      [
        "pushCount",
        "pushCountSide",
        "statSelected",
        "statSelectedFiles"
      ].forEach((id) => {
        const el = document.getElementById(id);

        if (el) {
          el.textContent = count;
        }
      });

      const summary = document.getElementById("librarySelectionSummary");

      if (summary) {
        summary.textContent = `${count} selected`;
      }
    },


    /* ======================================================
       INITIALIZATION
    ====================================================== */

    initOnce(container = document) {
      const root = container.querySelector(".uploads-wrapper");

      if (!root || root.__initialized__) {
        return;
      }

      root.__initialized__ = true;


      /* ====================================================
         DOM REFERENCES
      ==================================================== */

      const yearSelector = root.querySelector("#yearSelectorUploads");

      const classPills = root.querySelectorAll(".class-pill");
      const termPills = root.querySelectorAll(".term-pill");

      const termFilterBar = root.querySelector("#termFilterBar");

      const tableBody = root.querySelector("#uploadedTable");

      const searchBox = root.querySelector("#searchUploads");
      const clearSearchBtn = root.querySelector("#clearUploadSearch");

      const subjectFilter = root.querySelector("#subjectFilterUploads");

      const refreshBtn = root.querySelector("#refreshUploads");
      const checkAllUploads = root.querySelector("#checkAllUploads");

      const selectAllVisibleBtn = root.querySelector("#selectAllVisible");
      const clearQueueBtn = root.querySelector("#clearQueue");

      const activeYearLabel = root.querySelector("#activeYearLabel");

      const statSelectedYear = root.querySelector("#statSelectedYear");
      const statLoadedFiles = root.querySelector("#statLoadedFiles");

      const libraryResultCount = root.querySelector("#libraryResultCount");
      const activeClassIndicator = root.querySelector("#activeClassIndicator");
      const activeTermIndicator = root.querySelector("#activeTermIndicator");

      if (!yearSelector || !tableBody) {
        return;
      }


      /* ====================================================
         LOCAL HELPERS
      ==================================================== */

      const escapeHtml = (value) => {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      };


      const setActiveYearLabel = (year) => {
        if (!activeYearLabel) return;

        activeYearLabel.textContent = year || "—";
      };


      const updateStats = () => {
        if (statSelectedYear) {
          statSelectedYear.textContent = this.activeYear || "—";
        }

        if (statLoadedFiles) {
          statLoadedFiles.textContent = Array.isArray(this.convertedItems)
            ? this.convertedItems.length
            : 0;
        }

        this.updatePushCount();
      };


      const setLoadingState = (loading) => {
        if (!refreshBtn) return;

        refreshBtn.disabled = loading;

        refreshBtn.innerHTML = loading
          ? `<span class="spinner"></span>`
          : `<i class="fa-solid fa-rotate"></i>`;
      };


      const renderEmpty = (title, subtitle = "") => {
        tableBody.innerHTML = `
          <tr>
            <td colspan="8" class="empty">
              <div class="table-empty-state">
                <span class="table-empty-icon">
                  <i class="fa-solid fa-folder-open"></i>
                </span>

                <strong>${escapeHtml(title)}</strong>

                ${subtitle
                  ? `<small>${escapeHtml(subtitle)}</small>`
                  : ""}
              </div>
            </td>
          </tr>
        `;

        if (checkAllUploads) {
          checkAllUploads.checked = false;
          checkAllUploads.indeterminate = false;
        }

        if (libraryResultCount) {
          libraryResultCount.textContent = "0 files";
        }
      };


      /* ====================================================
         TERM UI
      ==================================================== */

      const resetTermFilter = () => {
        this.activeTerm = "ALL";

        termPills.forEach((pill) => {
          pill.classList.toggle(
            "active",
            String(pill.dataset.term || "").toUpperCase() === "ALL"
          );
        });
      };


      const updateTermVisibility = () => {
        const termAware = this.isTermAwareClass(this.activeClass);

        if (termFilterBar) {
          termFilterBar.classList.toggle("hidden", !termAware);
        }

        if (activeTermIndicator) {
          activeTermIndicator.classList.toggle("hidden", !termAware);

          if (termAware) {
            activeTermIndicator.textContent = this.activeTerm === "ALL"
              ? "All Terms"
              : this.termLabel(this.activeTerm);
          }
        }

        if (!termAware) {
          resetTermFilter();
        }
      };


      const updateActiveIndicators = () => {
        if (activeClassIndicator) {
          activeClassIndicator.textContent = this.activeClass === "ALL"
            ? "All Classes"
            : this.activeClass;
        }

        if (activeTermIndicator) {
          if (this.isTermAwareClass(this.activeClass)) {
            activeTermIndicator.classList.remove("hidden");

            activeTermIndicator.textContent = this.activeTerm === "ALL"
              ? "All Terms"
              : this.termLabel(this.activeTerm);

          } else {
            activeTermIndicator.classList.add("hidden");
          }
        }
      };


      /* ====================================================
         SUBJECT FILTER
      ==================================================== */

      const populateSubjectFilter = () => {
        if (!subjectFilter) return;

        const current = subjectFilter.value || "ALL";

        let sourceRows = Array.isArray(this.convertedItems)
          ? [...this.convertedItems]
          : [];

        if (this.activeClass !== "ALL") {
          sourceRows = sourceRows.filter(
            (item) => this.getItemClass(item) === this.activeClass
          );
        }

        if (
          this.activeClass !== "ALL"
          && this.isTermAwareClass(this.activeClass)
          && this.activeTerm !== "ALL"
        ) {
          sourceRows = sourceRows.filter(
            (item) => this.getItemTerm(item) === this.activeTerm
          );
        }

        const subjects = [
          ...new Set(
            sourceRows
              .map((item) => this.getSubjectLabel(item))
              .filter(Boolean)
          )
        ].sort((a, b) => a.localeCompare(b));

        subjectFilter.innerHTML = `
          <option value="ALL">All Subjects</option>
          ${subjects
            .map((subject) => `
              <option value="${escapeHtml(subject)}">
                ${escapeHtml(subject)}
              </option>
            `)
            .join("")}
        `;

        const stillExists = [...subjectFilter.options]
          .some((option) => option.value === current);

        subjectFilter.value = stillExists ? current : "ALL";
        this.activeSubject = subjectFilter.value;
      };


      /* ====================================================
         FILTERING
      ==================================================== */

      const getFilteredRows = () => {
        let rows = Array.isArray(this.convertedItems)
          ? [...this.convertedItems]
          : [];

        /* Class */
        if (this.activeClass !== "ALL") {
          rows = rows.filter(
            (item) => this.getItemClass(item) === this.activeClass
          );
        }

        /* Term */
        if (
          this.activeClass !== "ALL"
          && this.isTermAwareClass(this.activeClass)
          && this.activeTerm !== "ALL"
        ) {
          rows = rows.filter(
            (item) => this.getItemTerm(item) === this.activeTerm
          );
        }

        /* Subject */
        const selectedSubject = subjectFilter?.value
          || this.activeSubject
          || "ALL";

        if (selectedSubject !== "ALL") {
          rows = rows.filter((item) => {
            return this.normalizeSubject(
              this.getSubjectLabel(item)
            ) === this.normalizeSubject(selectedSubject);
          });
        }

        /* Search */
        const query = String(searchBox?.value || "")
          .toLowerCase()
          .trim();

        if (query) {
          rows = rows.filter((item) => {
            const filename = String(item.filename || "").toLowerCase();
            const subject = this.getSubjectLabel(item).toLowerCase();
            const cls = this.getItemClass(item).toLowerCase();
            const term = this.termLabel(this.getItemTerm(item)).toLowerCase();

            return (
              filename.includes(query)
              || subject.includes(query)
              || cls.includes(query)
              || term.includes(query)
            );
          });
        }

        return rows;
      };


      /* ====================================================
         CHECK ALL STATE
      ==================================================== */

      const syncCheckAll = () => {
        if (!checkAllUploads) return;

        const rows = getFilteredRows();

        if (!rows.length) {
          checkAllUploads.checked = false;
          checkAllUploads.indeterminate = false;
          return;
        }

        const selectedVisible = rows.filter((item) => {
          return this.selectedFiles.has(
            this.makeSelectionKey(item)
          );
        }).length;

        checkAllUploads.checked = selectedVisible === rows.length;

        checkAllUploads.indeterminate = (
          selectedVisible > 0
          && selectedVisible < rows.length
        );
      };


      /* ====================================================
         TABLE RENDER
      ==================================================== */

      const renderTable = () => {
        updateTermVisibility();
        updateActiveIndicators();

        if (!this.activeYear) {
          renderEmpty(
            "Select an exam year",
            "Question files will appear here."
          );

          updateStats();
          return;
        }

        const rows = getFilteredRows();

        if (libraryResultCount) {
          libraryResultCount.textContent = `${rows.length} ${rows.length === 1 ? "file" : "files"}`;
        }

        if (!rows.length) {
          let description = `No files found for ${this.activeYear}.`;

          if (this.activeClass !== "ALL") {
            description = `No ${this.activeClass} files found for ${this.activeYear}.`;
          }

          if (
            this.activeClass !== "ALL"
            && this.isTermAwareClass(this.activeClass)
            && this.activeTerm !== "ALL"
          ) {
            description = (
              `No ${this.activeClass} ${this.termLabel(this.activeTerm)} `
              + `files found for ${this.activeYear}.`
            );
          }

          renderEmpty("Nothing found", description);
          updateStats();
          return;
        }

        tableBody.innerHTML = rows
          .map((item) => {
            const yearRaw = item.year || this.activeYear;
            const classRaw = this.getItemClass(item);
            const termRaw = this.getItemTerm(item);

            const year = escapeHtml(yearRaw);
            const filename = escapeHtml(item.filename || "");
            const subject = escapeHtml(this.getSubjectLabel(item));
            const classCategory = escapeHtml(classRaw || "—");
            const term = escapeHtml(this.termLabel(termRaw));
            const questions = escapeHtml(item.questions ?? 0);
            const statusRaw = String(item.status || "OK");
            const status = escapeHtml(statusRaw);

            const size = Number(item.size ?? item.size_kb ?? 0);
            const legacy = Boolean(item.legacy);

            const key = this.makeSelectionKey(item);
            const selected = this.selectedFiles.has(key);

            const termMeta = termRaw
              ? ` • ${escapeHtml(this.termLabel(termRaw))}`
              : "";

            const sizeMeta = Number.isFinite(size) && size > 0
              ? ` • ${escapeHtml(size)} KB`
              : "";

            let statusClass = "status-ok";

            if (statusRaw === "TERM_REQUIRED") {
              statusClass = "status-pill term-required";
            }

            return `
              <tr class="upload-row"
                  data-year="${year}"
                  data-filename="${filename}"
                  data-class="${classCategory}"
                  data-term="${escapeHtml(termRaw || "")}">

                <td class="check-column">
                  <input
                    type="checkbox"
                    class="row-select"
                    aria-label="Select ${filename}"
                    ${selected ? "checked" : ""}
                  >
                </td>

                <td class="file-cell" data-clickable="true">
                  <div class="file-main">
                    <span class="file-name">${filename}</span>

                    <span class="file-meta">
                      ${classCategory}${termMeta} • ${questions} questions${sizeMeta}
                      ${legacy ? " • Legacy" : ""}
                    </span>
                  </div>
                </td>

                <td>${subject}</td>

                <td>
                  <span class="summary-chip">
                    ${classCategory}
                  </span>
                </td>

                <td class="term-column">
                  ${termRaw
                    ? `<span class="summary-chip term-chip">${term}</span>`
                    : `<span class="file-meta">—</span>`}
                </td>

                <td class="center">${questions}</td>

                <td>
                  <span class="${statusClass}">
                    ${status === "TERM_REQUIRED" ? "Term Required" : status}
                  </span>
                </td>

                <td class="actions-column">
                  <div class="table-row-actions">

                    <button
                      class="mini-icon-button preview-btn"
                      type="button"
                      title="Preview JSON"
                      aria-label="Preview ${filename}"
                    >
                      <i class="fa-solid fa-eye"></i>
                    </button>

                    <button
                      class="mini-icon-button delete-btn"
                      type="button"
                      title="Delete JSON"
                      aria-label="Delete ${filename}"
                    >
                      <i class="fa-solid fa-trash-can"></i>
                    </button>

                  </div>
                </td>

              </tr>
            `;
          })
          .join("");

        syncCheckAll();
        updateStats();
      };


      /* ====================================================
         LOAD YEAR
      ==================================================== */

      const loadYearFiles = async (year, refreshing = false) => {
        if (!year || year === "Select Year") {
          return;
        }

        if (refreshing) {
          setLoadingState(true);
        }

        tableBody.innerHTML = `
          <tr>
            <td colspan="8" class="empty">
              <div class="table-empty-state">
                <span class="spinner"></span>
                <strong>Loading library...</strong>
              </div>
            </td>
          </tr>
        `;

        try {
          const response = await fetch(
            `/api/uploads/${encodeURIComponent(year)}`
          );

          const data = await response.json();

          if (!response.ok) {
            throw new Error(
              data.error || "Failed to load JSON files"
            );
          }

          this.convertedItems = Array.isArray(data.uploads)
            ? data.uploads
            : [];

          this.selectedFiles.clear();

          populateSubjectFilter();
          renderTable();
          this.updatePushCount();

        } catch (error) {
          console.error("Upload library error:", error);

          this.convertedItems = [];
          this.selectedFiles.clear();

          populateSubjectFilter();

          renderEmpty(
            "Could not load library",
            "Please refresh and try again."
          );

          flashMessage(
            error.message || "Could not load JSON library.",
            "error"
          );

        } finally {
          if (refreshing) {
            setTimeout(() => {
              setLoadingState(false);
            }, 250);
          }

          updateStats();
        }
      };


      /* ====================================================
         PREVIEW JSON
      ==================================================== */

      const previewFile = async (row) => {
        const year = row.dataset.year;
        const filename = row.dataset.filename;
        const classCategory = this.normalizeClass(row.dataset.class);
        const term = this.normalizeTerm(row.dataset.term);

        if (!year || !filename || !classCategory) {
          throw new Error("Missing preview information.");
        }

        if (
          this.isTermAwareClass(classCategory)
          && !term
        ) {
          throw new Error(
            `${classCategory} file has no term assigned.`
          );
        }

        const params = new URLSearchParams({
          class: classCategory
        });

        if (term) {
          params.set("term", term);
        }

        const response = await fetch(
          `/api/uploads/${encodeURIComponent(year)}/${encodeURIComponent(filename)}?${params.toString()}`
        );

        const output = await response.json();

        if (!response.ok) {
          throw new Error(
            output.error || "Could not preview file"
          );
        }

        const content = output;
        const meta = this.getMeta(
          filename,
          year,
          classCategory,
          term
        );

        /* Mini preview card */
        if (window.ConvertUI?.setPreviewCard) {
          window.ConvertUI.setPreviewCard(
            filename,
            meta,
            content
          );

        } else {
          const previewSubject = root.querySelector("#previewSubjectPill");
          const previewVersion = root.querySelector("#previewVersionPill");
          const previewQuestions = root.querySelector("#previewQuestionCountPill");
          const previewBody = root.querySelector("#latestPreviewBody");

          if (previewSubject) {
            previewSubject.textContent = this.getSubjectLabel(meta || content);
          }

          if (previewVersion) {
            previewVersion.textContent = term
              ? this.termLabel(term)
              : classCategory;
          }

          if (previewQuestions) {
            const qCount = Array.isArray(content?.questions)
              ? content.questions.length
              : Number(meta?.questions || 0);

            previewQuestions.textContent = `${qCount} Questions`;
          }

          if (previewBody) {
            previewBody.innerHTML = `
              <pre style="white-space:pre-wrap;margin:0;">${escapeHtml(
                JSON.stringify(content, null, 2)
              )}</pre>
            `;
          }
        }

        /* Full JSON modal */
        if (window.ConvertUI?.openJsonModal) {
          const titleParts = [
            year,
            classCategory
          ];

          if (term) {
            titleParts.push(this.termLabel(term));
          }

          titleParts.push(filename);

          window.ConvertUI.openJsonModal(
            `Preview • ${titleParts.join(" • ")}`,
            JSON.stringify(content, null, 2)
          );

          return;
        }

        const modal = root.querySelector("#jsonPreviewModal");
        const title = root.querySelector("#jsonPreviewTitle");
        const body = root.querySelector("#jsonPreviewBody");

        const titleParts = [
          year,
          classCategory
        ];

        if (term) {
          titleParts.push(this.termLabel(term));
        }

        titleParts.push(filename);

        if (title) {
          title.textContent = `Preview • ${titleParts.join(" • ")}`;
        }

        if (body) {
          body.textContent = JSON.stringify(content, null, 2);
        }

        if (modal) {
          modal.classList.remove("hidden");
        }
      };


      /* ====================================================
         DELETE JSON
      ==================================================== */

      const deleteFile = async (row) => {
        const year = row.dataset.year;
        const filename = row.dataset.filename;
        const classCategory = this.normalizeClass(row.dataset.class);
        const term = this.normalizeTerm(row.dataset.term);

        if (!year || !filename || !classCategory) {
          throw new Error("Missing delete information.");
        }

        if (
          this.isTermAwareClass(classCategory)
          && !term
        ) {
          throw new Error(
            `${classCategory} file has no term assigned.`
          );
        }

        const label = term
          ? `${classCategory} • ${this.termLabel(term)}`
          : classCategory;

        const confirmed = window.confirm(
          `Delete "${filename}" from ${year} • ${label}?\n\nThis cannot be undone.`
        );

        if (!confirmed) {
          return false;
        }

        const params = new URLSearchParams({
          class: classCategory
        });

        if (term) {
          params.set("term", term);
        }

        const response = await fetch(
          `/api/uploads/${encodeURIComponent(year)}/delete/${encodeURIComponent(filename)}?${params.toString()}`,
          {
            method: "DELETE"
          }
        );

        const output = await response.json();

        if (!response.ok) {
          throw new Error(
            output.error || "Could not delete file"
          );
        }

        const meta = this.getMeta(
          filename,
          year,
          classCategory,
          term
        );

        if (meta) {
          this.selectedFiles.delete(
            this.makeSelectionKey(meta)
          );
        }

        this.convertedItems = this.convertedItems.filter((item) => {
          return !(
            String(item.year) === String(year)
            && String(item.filename) === String(filename)
            && this.getItemClass(item) === classCategory
            && this.getItemTerm(item) === term
          );
        });

        populateSubjectFilter();
        renderTable();
        this.updatePushCount();

        flashMessage(
          `${filename} deleted successfully.`,
          "success"
        );

        return true;
      };


      /* ====================================================
         YEAR SELECTOR
      ==================================================== */

      yearSelector.addEventListener("change", () => {
        this.activeYear = yearSelector.value;

        setActiveYearLabel(this.activeYear);

        this.selectedFiles.clear();

        loadYearFiles(
          this.activeYear
        );
      });


      /* ====================================================
         CLASS FILTER
      ==================================================== */

      classPills.forEach((pill) => {
        pill.addEventListener("click", () => {
          classPills.forEach((item) => {
            item.classList.remove("active");
          });

          pill.classList.add("active");

          this.activeClass = this.normalizeClass(
            pill.dataset.class || "ALL"
          );

          resetTermFilter();
          updateTermVisibility();
          populateSubjectFilter();
          renderTable();
        });
      });


      /* ====================================================
         TERM FILTER
      ==================================================== */

      termPills.forEach((pill) => {
        pill.addEventListener("click", () => {
          if (!this.isTermAwareClass(this.activeClass)) {
            return;
          }

          termPills.forEach((item) => {
            item.classList.remove("active");
          });

          pill.classList.add("active");

          const rawTerm = String(
            pill.dataset.term || "ALL"
          ).toUpperCase();

          this.activeTerm = rawTerm === "ALL"
            ? "ALL"
            : this.normalizeTerm(rawTerm) || "ALL";

          populateSubjectFilter();
          renderTable();
        });
      });


      /* ====================================================
         SUBJECT FILTER
      ==================================================== */

      subjectFilter?.addEventListener("change", () => {
        this.activeSubject = subjectFilter.value || "ALL";
        renderTable();
      });


      /* ====================================================
         SEARCH
      ==================================================== */

      searchBox?.addEventListener("input", () => {
        const hasValue = Boolean(
          String(searchBox.value || "").trim()
        );

        clearSearchBtn?.classList.toggle(
          "hidden",
          !hasValue
        );

        renderTable();
      });


      clearSearchBtn?.addEventListener("click", () => {
        if (!searchBox) return;

        searchBox.value = "";
        clearSearchBtn.classList.add("hidden");

        searchBox.focus();
        renderTable();
      });


      /* ====================================================
         REFRESH
      ==================================================== */

      refreshBtn?.addEventListener("click", () => {
        if (!this.activeYear) {
          flashMessage(
            "Select an exam year first.",
            "error"
          );

          return;
        }

        loadYearFiles(
          this.activeYear,
          true
        );
      });


      /* ====================================================
         SELECT ALL VISIBLE
      ==================================================== */

      selectAllVisibleBtn?.addEventListener("click", () => {
        const rows = getFilteredRows();

        if (!rows.length) {
          flashMessage(
            "No visible files to select.",
            "error"
          );

          return;
        }

        rows.forEach((item) => {
          this.selectedFiles.add(
            this.makeSelectionKey(item)
          );
        });

        renderTable();
        this.updatePushCount();

        flashMessage(
          `${rows.length} visible file(s) selected.`,
          "success"
        );
      });


      /* ====================================================
         CLEAR QUEUE
      ==================================================== */

      clearQueueBtn?.addEventListener("click", () => {
        this.selectedFiles.clear();

        renderTable();
        this.updatePushCount();

        flashMessage(
          "Push queue cleared.",
          "success"
        );
      });


      /* ====================================================
         TABLE HEADER CHECKBOX
      ==================================================== */

      checkAllUploads?.addEventListener("change", () => {
        const rows = getFilteredRows();

        rows.forEach((item) => {
          const key = this.makeSelectionKey(item);

          if (checkAllUploads.checked) {
            this.selectedFiles.add(key);
          } else {
            this.selectedFiles.delete(key);
          }
        });

        renderTable();
        this.updatePushCount();
      });


      /* ====================================================
         TABLE EVENTS
      ==================================================== */

      tableBody.addEventListener("click", async (event) => {
        const row = event.target.closest("tr.upload-row");

        if (!row) {
          return;
        }

        const year = row.dataset.year;
        const filename = row.dataset.filename;
        const classCategory = this.normalizeClass(
          row.dataset.class
        );

        const term = this.normalizeTerm(
          row.dataset.term
        );

        const meta = this.getMeta(
          filename,
          year,
          classCategory,
          term
        );

        const key = meta
          ? this.makeSelectionKey(meta)
          : `${year}|${classCategory}|${term || "NONE"}|${filename}`;


        /* --------------------------------------------------
           Checkbox
        -------------------------------------------------- */

        if (event.target.classList.contains("row-select")) {
          if (event.target.checked) {
            this.selectedFiles.add(key);
          } else {
            this.selectedFiles.delete(key);
          }

          syncCheckAll();
          this.updatePushCount();
          return;
        }


        /* --------------------------------------------------
           Preview
        -------------------------------------------------- */

        if (event.target.closest(".preview-btn")) {
          try {
            await previewFile(row);

          } catch (error) {
            console.error(
              "Preview error:",
              error
            );

            flashMessage(
              error.message || "Could not preview file.",
              "error"
            );
          }

          return;
        }


        /* --------------------------------------------------
           Delete
        -------------------------------------------------- */

        if (event.target.closest(".delete-btn")) {
          try {
            await deleteFile(row);

          } catch (error) {
            console.error(
              "Delete error:",
              error
            );

            flashMessage(
              error.message || "Could not delete file.",
              "error"
            );
          }
        }
      });


      /* ====================================================
         MODAL CLOSE BUTTONS
      ==================================================== */

      root.querySelectorAll('[data-close="true"]').forEach((element) => {
        element.addEventListener("click", () => {
          const modal = element.closest(".modal");

          if (modal) {
            modal.classList.add("hidden");
          }
        });
      });


      /* ====================================================
         INITIAL STATE
      ==================================================== */

      resetTermFilter();
      updateTermVisibility();
      updateActiveIndicators();

      populateSubjectFilter();
      this.updatePushCount();
      updateStats();
      renderTable();
    }
  };


  /* ========================================================
     AUTO INITIALIZER
  ======================================================== */

  const autoInit = () => {
    const wrapper = document.querySelector(".uploads-wrapper");

    if (wrapper) {
      window.EmisUploads.initOnce(document);
    }
  };


  if (
    document.readyState === "complete"
    || document.readyState === "interactive"
  ) {
    autoInit();

  } else {
    document.addEventListener(
      "DOMContentLoaded",
      autoInit
    );
  }


  /* ========================================================
     SPA / DYNAMIC PAGE SUPPORT
  ======================================================== */

  new MutationObserver(autoInit).observe(
    document.body,
    {
      childList: true,
      subtree: true
    }
  );

})();





/* ==========================================================
   PATCH — STEP 1 DOCX FILE PICKER
   Restores:
     • One File
     • Multiple Files
     • Drag & Drop
     • Selected file list
     • Clear files
========================================================== */

(() => {
  if (window.__EMIS_DOCX_PICKER_BOUND__) return;
  window.__EMIS_DOCX_PICKER_BOUND__ = true;

  let selectedDocxFiles = [];

  function initDocxPicker() {
    const root = document.querySelector(".uploads-wrapper");
    if (!root || root.__docx_picker_initialized__) return;

    const chooseSingle = root.querySelector("#chooseSingle");
    const chooseMulti = root.querySelector("#chooseMulti");

    const inputSingle = root.querySelector("#uploadInputSingle");
    const inputMulti = root.querySelector("#uploadInputMulti");

    const dropZone = root.querySelector("#uploadDropZone");

    const fileList = root.querySelector("#fileList");
    const selectedCount = root.querySelector("#selectedCount");
    const noSelectedFiles = root.querySelector("#noSelectedFiles");

    const clearUploads = root.querySelector("#clearUploads");

    if (
      !chooseSingle ||
      !chooseMulti ||
      !inputSingle ||
      !inputMulti ||
      !dropZone
    ) {
      return;
    }

    root.__docx_picker_initialized__ = true;


    /* ------------------------------------------------------
       EXPOSE SELECTED DOCX FILES
       Other conversion scripts can use this.
    ------------------------------------------------------ */

    window.EmisDocxUpload = {
      get files() {
        return selectedDocxFiles;
      },

      clear() {
        selectedDocxFiles = [];
        renderFiles();
      }
    };


    /* ------------------------------------------------------
       HELPERS
    ------------------------------------------------------ */

    function isDocx(file) {
      return String(file?.name || "")
        .toLowerCase()
        .endsWith(".docx");
    }


    function formatSize(bytes) {
      const size = Number(bytes || 0);

      if (size < 1024) {
        return `${size} B`;
      }

      if (size < 1024 * 1024) {
        return `${(size / 1024).toFixed(1)} KB`;
      }

      return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    }


    function fileKey(file) {
      return `${file.name}|${file.size}|${file.lastModified}`;
    }


    function addFiles(files, replace = false) {
      const incoming = [...files].filter(isDocx);

      if (!incoming.length) {
        if (typeof flashMessage === "function") {
          flashMessage("Please select DOCX files only.", "error");
        }

        return;
      }

      if (replace) {
        selectedDocxFiles = [];
      }

      const existing = new Set(
        selectedDocxFiles.map(fileKey)
      );

      incoming.forEach((file) => {
        const key = fileKey(file);

        if (!existing.has(key)) {
          selectedDocxFiles.push(file);
          existing.add(key);
        }
      });

      renderFiles();
    }


    function removeFile(index) {
      selectedDocxFiles.splice(index, 1);
      renderFiles();
    }


    function renderFiles() {
      const count = selectedDocxFiles.length;

      if (selectedCount) {
        selectedCount.textContent = count;
      }

      if (noSelectedFiles) {
        noSelectedFiles.classList.toggle(
          "hidden",
          count > 0
        );
      }

      if (!fileList) return;

      if (!count) {
        fileList.innerHTML = "";
        return;
      }

      fileList.innerHTML = selectedDocxFiles
        .map((file, index) => `
          <li class="selected-docx-item">
            <div class="selected-docx-info">
              <i class="fa-solid fa-file-word"></i>

              <div>
                <strong title="${file.name}">
                  ${file.name}
                </strong>

                <small>
                  ${formatSize(file.size)}
                </small>
              </div>
            </div>

            <button
              type="button"
              class="remove-docx-file"
              data-index="${index}"
              title="Remove file"
            >
              <i class="fa-solid fa-xmark"></i>
            </button>
          </li>
        `)
        .join("");
    }


    /* ------------------------------------------------------
       ONE FILE
    ------------------------------------------------------ */

    chooseSingle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();

      inputSingle.value = "";
      inputSingle.click();
    });


    inputSingle.addEventListener("change", () => {
      if (!inputSingle.files?.length) return;

      addFiles(
        inputSingle.files,
        true
      );
    });


    /* ------------------------------------------------------
       MULTIPLE FILES
    ------------------------------------------------------ */

    chooseMulti.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();

      inputMulti.value = "";
      inputMulti.click();
    });


    inputMulti.addEventListener("change", () => {
      if (!inputMulti.files?.length) return;

      addFiles(
        inputMulti.files,
        false
      );
    });


    /* ------------------------------------------------------
       DRAG & DROP
    ------------------------------------------------------ */

    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();

        dropZone.classList.add("drag-over");
      });
    });


    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();

        dropZone.classList.remove("drag-over");
      });
    });


    dropZone.addEventListener("drop", (event) => {
      const files = event.dataTransfer?.files;

      if (!files?.length) return;

      addFiles(
        files,
        false
      );
    });


    /* ------------------------------------------------------
       REMOVE SINGLE FILE
    ------------------------------------------------------ */

    fileList?.addEventListener("click", (event) => {
      const button = event.target.closest(
        ".remove-docx-file"
      );

      if (!button) return;

      event.preventDefault();
      event.stopPropagation();

      const index = Number(
        button.dataset.index
      );

      if (!Number.isInteger(index)) return;

      removeFile(index);
    });


    /* ------------------------------------------------------
       CLEAR ALL
    ------------------------------------------------------ */

    clearUploads?.addEventListener("click", (event) => {
      event.preventDefault();

      selectedDocxFiles = [];

      inputSingle.value = "";
      inputMulti.value = "";

      renderFiles();

      if (typeof flashMessage === "function") {
        flashMessage(
          "Selected DOCX files cleared.",
          "success"
        );
      }
    });


    /* ------------------------------------------------------
       INITIAL STATE
    ------------------------------------------------------ */

    renderFiles();
  }


  if (
    document.readyState === "complete" ||
    document.readyState === "interactive"
  ) {
    initDocxPicker();

  } else {
    document.addEventListener(
      "DOMContentLoaded",
      initDocxPicker
    );
  }


  new MutationObserver(
    initDocxPicker
  ).observe(
    document.body,
    {
      childList: true,
      subtree: true
    }
  );

})();
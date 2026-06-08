/* ==========================================================
   EMIS UPLOADS — YEAR + CLASS + SUBJECT FILTER BROWSER
   Supports:
     • JSS1 / JSS2 / JSS3
     • SS1 / SS2 / SS3
     • ALL
     • Dynamic subject dropdown filter
========================================================== */

function flashMessage(text, type = "success") {
  const fm = document.getElementById("flashMessage");
  if (!fm) return;

  fm.textContent = text;
  fm.className = `flash-message ${type} show`;

  setTimeout(() => {
    fm.classList.remove("show");
  }, 3000);
}

(() => {
  if (window.__EMIS_UPLOADS_BOUND__) return;
  window.__EMIS_UPLOADS_BOUND__ = true;

  window.EmisUploads = {
    activeYear: null,
    activeClass: "ALL",
    activeSubject: "ALL",
    convertedItems: [],
    selectedFiles: new Set(),

    supportedClasses: ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"],

    normalizeClass(cls) {
      return String(cls || "").toUpperCase().trim();
    },

    normalizeSubject(value) {
      return String(value || "")
        .toLowerCase()
        .replaceAll("_", " ")
        .replaceAll("-", " ")
        .replace(/\s+/g, " ")
        .trim();
    },

    getMeta(fname, year) {
      return this.convertedItems.find(
        (i) =>
          i.filename === fname &&
          String(i.year) === String(year)
      );
    },

    updatePushCount() {
      const count = this.selectedFiles.size;

      ["pushCount", "pushCountSide", "statSelected", "statSelectedFiles"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.textContent = count;
      });
    },

    initOnce(container = document) {
      const root = container.querySelector(".uploads-wrapper");
      if (!root || root.__initialized__) return;

      root.__initialized__ = true;

      const yearSelector = root.querySelector("#yearSelectorUploads");
      const classPills = root.querySelectorAll(".class-pill");
      const tableBody = root.querySelector("#uploadedTable");
      const searchBox = root.querySelector("#searchUploads");
      const subjectFilter = root.querySelector("#subjectFilterUploads");
      const refreshBtn = root.querySelector("#refreshUploads");
      const checkAllUploads = root.querySelector("#checkAllUploads");
      const selectAllVisibleBtn = root.querySelector("#selectAllVisible");
      const clearQueueBtn = root.querySelector("#clearQueue");
      const activeYearLabel = document.getElementById("activeYearLabel");

      const statSelectedYear = root.querySelector("#statSelectedYear");
      const statLoadedFiles = root.querySelector("#statLoadedFiles");

      if (!yearSelector || !tableBody) return;

      const setActiveYearLabel = (year) => {
        if (!activeYearLabel) return;

        if (!year || year === "Select Year") {
          activeYearLabel.textContent = "Active Year: —";
        } else {
          activeYearLabel.textContent = `Active Year: ${year}`;
        }
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

        if (loading) {
          refreshBtn.disabled = true;
          refreshBtn.innerHTML = `<span class="spinner"></span>`;
        } else {
          refreshBtn.disabled = false;
          refreshBtn.innerHTML = `<i class="fa-solid fa-rotate"></i> Refresh`;
        }
      };

      const escapeHtml = (value) => {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      };

      const renderEmpty = (message) => {
        tableBody.innerHTML = `
          <tr>
            <td colspan="9" class="empty">${escapeHtml(message)}</td>
          </tr>
        `;

        if (checkAllUploads) checkAllUploads.checked = false;
      };

      const getSubjectLabel = (item) => {
        const subject = String(item.subject || "").trim();

        if (subject) return subject;

        const filename = String(item.filename || "")
          .replace(".json", "")
          .replace(/_(jss1|jss2|jss3|ss1|ss2|ss3)$/i, "")
          .replaceAll("_", " ")
          .replaceAll("-", " ")
          .replace(/\s+/g, " ")
          .trim();

        return filename || "Unknown";
      };

      const populateSubjectFilter = () => {
        if (!subjectFilter) return;

        const current = subjectFilter.value || "ALL";

        const subjects = [...new Set(
          (this.convertedItems || [])
            .map((item) => getSubjectLabel(item))
            .filter(Boolean)
        )].sort((a, b) => a.localeCompare(b));

        subjectFilter.innerHTML = `
          <option value="ALL">All Subjects</option>
          ${subjects.map((subject) => `
            <option value="${escapeHtml(subject)}">${escapeHtml(subject)}</option>
          `).join("")}
        `;

        const stillExists = [...subjectFilter.options].some((opt) => opt.value === current);
        subjectFilter.value = stillExists ? current : "ALL";
        this.activeSubject = subjectFilter.value;
      };

      const getFilteredRows = () => {
        let rows = Array.isArray(this.convertedItems)
          ? [...this.convertedItems]
          : [];

        if (this.activeClass !== "ALL") {
          rows = rows.filter((item) => {
            const cls = this.normalizeClass(item.class_category || item.class_level);
            return cls === this.activeClass;
          });
        }

        const selectedSubject = subjectFilter?.value || this.activeSubject || "ALL";

        if (selectedSubject !== "ALL") {
          rows = rows.filter((item) => {
            return this.normalizeSubject(getSubjectLabel(item)) === this.normalizeSubject(selectedSubject);
          });
        }

        const q = String(searchBox?.value || "").toLowerCase().trim();

        if (q) {
          rows = rows.filter((item) => {
            const filename = String(item.filename || "").toLowerCase();
            const subject = getSubjectLabel(item).toLowerCase();
            const cls = String(item.class_category || item.class_level || "").toLowerCase();

            return (
              filename.includes(q) ||
              subject.includes(q) ||
              cls.includes(q)
            );
          });
        }

        return rows;
      };

      const syncCheckAll = () => {
        if (!checkAllUploads) return;

        const rows = getFilteredRows();

        if (!rows.length) {
          checkAllUploads.checked = false;
          checkAllUploads.indeterminate = false;
          return;
        }

        const selectedVisible = rows.filter((item) => {
          const key = `${item.year || this.activeYear}:${item.filename}`;
          return this.selectedFiles.has(key);
        }).length;

        checkAllUploads.checked = selectedVisible === rows.length;
        checkAllUploads.indeterminate = selectedVisible > 0 && selectedVisible < rows.length;
      };

      const renderTable = () => {
        if (!this.activeYear) {
          renderEmpty("Select a year to load JSON files");
          updateStats();
          return;
        }

        const rows = getFilteredRows();

        if (!rows.length) {
          const classText = this.activeClass === "ALL" ? "" : `${this.activeClass} `;
          const subjectText =
            (subjectFilter?.value && subjectFilter.value !== "ALL")
              ? `${subjectFilter.value} `
              : "";

          renderEmpty(`No ${subjectText}${classText}files found for ${this.activeYear}.`);
          updateStats();
          return;
        }

        tableBody.innerHTML = rows
          .map((item) => {
            const year = escapeHtml(item.year || this.activeYear);
            const filename = escapeHtml(item.filename || "");
            const subject = escapeHtml(getSubjectLabel(item));
            const classCategory = escapeHtml(item.class_category || item.class_level || "—");
            const version = escapeHtml(item.version || "—");
            const questions = escapeHtml(item.questions || 0);
            const sizeKb = escapeHtml(item.size_kb || "—");
            const status = escapeHtml(item.status || "OK");

            const key = `${item.year || this.activeYear}:${item.filename}`;

            return `
              <tr class="upload-row"
                  data-year="${year}"
                  data-filename="${filename}"
                  data-class="${classCategory}">

                <td>
                  <input type="checkbox" class="row-select"
                    ${this.selectedFiles.has(key) ? "checked" : ""}>
                </td>

                <td class="file-cell" data-clickable="true">
                  <div class="file-main">
                    <span class="file-name">${filename}</span>
                    <span class="file-meta">
                      ${subject} • ${classCategory} • ${questions} questions
                    </span>
                  </div>
                </td>

                <td>${subject}</td>
                <td>${classCategory}</td>
                <td>${version}</td>
                <td class="center">${questions}</td>
                <td class="center">${sizeKb} KB</td>
                <td><span class="status-pill">${status}</span></td>

                <td>
                  <button class="btn-secondary tiny preview-btn" type="button">
                    <i class="fa-solid fa-eye"></i>
                    Preview
                  </button>
                </td>
              </tr>
            `;
          })
          .join("");

        syncCheckAll();
        updateStats();
      };

      const loadYearFiles = async (year, refreshing = false) => {
        if (!year || year === "Select Year") return;

        if (refreshing) setLoadingState(true);

        tableBody.innerHTML = `
          <tr>
            <td colspan="9" class="empty">
              <span class="spinner"></span>
              Loading JSON files...
            </td>
          </tr>
        `;

        try {
          const res = await fetch(`/api/uploads/${encodeURIComponent(year)}`);
          const data = await res.json();

          if (!res.ok) {
            throw new Error(data.error || "Failed to load JSON files");
          }

          this.convertedItems = data.uploads || [];
          this.selectedFiles.clear();

          populateSubjectFilter();
          renderTable();
          this.updatePushCount();

        } catch (err) {
          console.error("Upload list error:", err);
          this.convertedItems = [];
          populateSubjectFilter();
          renderEmpty("Failed to load JSON list.");
        }

        if (refreshing) {
          setTimeout(() => setLoadingState(false), 300);
        }

        updateStats();
      };

      yearSelector.onchange = () => {
        this.activeYear = yearSelector.value;
        setActiveYearLabel(this.activeYear);
        loadYearFiles(this.activeYear);
      };

      classPills.forEach((pill) => {
        pill.onclick = () => {
          classPills.forEach((p) => p.classList.remove("active"));
          pill.classList.add("active");

          this.activeClass = this.normalizeClass(pill.dataset.class || "ALL");
          renderTable();
        };
      });

      subjectFilter?.addEventListener("change", () => {
        this.activeSubject = subjectFilter.value || "ALL";
        renderTable();
      });

      searchBox?.addEventListener("input", renderTable);

      refreshBtn?.addEventListener("click", () => {
        if (this.activeYear) {
          loadYearFiles(this.activeYear, true);
        }
      });

      selectAllVisibleBtn?.addEventListener("click", () => {
        const rows = getFilteredRows();

        if (!rows.length) {
          flashMessage("No visible files to select.", "error");
          return;
        }

        rows.forEach((item) => {
          const key = `${item.year || this.activeYear}:${item.filename}`;
          this.selectedFiles.add(key);
        });

        renderTable();
        this.updatePushCount();
        flashMessage(`${rows.length} visible file(s) selected.`, "success");
      });

      clearQueueBtn?.addEventListener("click", () => {
        this.selectedFiles.clear();
        renderTable();
        this.updatePushCount();
        flashMessage("Push queue cleared.", "success");
      });

      checkAllUploads?.addEventListener("change", () => {
        const rows = getFilteredRows();

        rows.forEach((item) => {
          const key = `${item.year || this.activeYear}:${item.filename}`;

          if (checkAllUploads.checked) {
            this.selectedFiles.add(key);
          } else {
            this.selectedFiles.delete(key);
          }
        });

        renderTable();
        this.updatePushCount();
      });

      tableBody.onclick = async (e) => {
        const row = e.target.closest("tr.upload-row");
        if (!row) return;

        const year = row.dataset.year;
        const filename = row.dataset.filename;
        const key = `${year}:${filename}`;

        if (e.target.classList.contains("row-select")) {
          if (e.target.checked) {
            this.selectedFiles.add(key);
          } else {
            this.selectedFiles.delete(key);
          }

          syncCheckAll();
          this.updatePushCount();
          return;
        }

        if (e.target.closest(".preview-btn")) {
          try {
            const meta = this.getMeta(filename, year);
            const cls = this.normalizeClass(meta?.class_category || meta?.class_level || row.dataset.class);

            if (!cls) {
              throw new Error("Missing class category for preview");
            }

            const res = await fetch(
              `/api/uploads/${encodeURIComponent(cls)}/${encodeURIComponent(filename)}`
            );

            const out = await res.json();

            if (!res.ok) {
              throw new Error(out.error || "Could not preview file");
            }

            const content = out.content
              ? JSON.parse(out.content)
              : out;

            if (window.ConvertUI?.setPreviewCard) {
              window.ConvertUI.setPreviewCard(filename, meta, content);
            }

            if (window.ConvertUI?.openJsonModal) {
              window.ConvertUI.openJsonModal(
                `Preview • ${year} • ${cls} • ${filename}`,
                JSON.stringify(content, null, 2)
              );
            } else {
              const title = document.getElementById("jsonPreviewTitle");
              const body = document.getElementById("jsonPreviewBody");
              const modal = document.getElementById("jsonPreviewModal");

              if (title) title.innerHTML = `<i class="fa-solid fa-code"></i> Preview • ${year} • ${cls} • ${filename}`;
              if (body) body.textContent = JSON.stringify(content, null, 2);
              if (modal) modal.classList.remove("hidden");
            }

          } catch (err) {
            console.error("Preview error:", err);
            flashMessage("Could not preview file.", "error");
          }
        }
      };

      root.querySelectorAll('[data-close="true"]').forEach((el) => {
        el.addEventListener("click", () => {
          const modal = el.closest(".modal");
          if (modal) modal.classList.add("hidden");
        });
      });

      populateSubjectFilter();
      this.updatePushCount();
      updateStats();
    }
  };

  const autoInit = () => {
    const wrap = document.querySelector(".uploads-wrapper");
    if (wrap) window.EmisUploads.initOnce(document);
  };

  if (["complete", "interactive"].includes(document.readyState)) {
    autoInit();
  } else {
    document.addEventListener("DOMContentLoaded", autoInit);
  }

  new MutationObserver(autoInit).observe(document.body, {
    childList: true,
    subtree: true
  });
})();
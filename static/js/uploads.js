/* ==========================================================
   EMIS UPLOADS — YEAR + CLASS PILL FILTER BROWSER
   Supports:
     • JSS1 / JSS2 / JSS3
     • SS1 / SS2 / SS3
     • ALL
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
    convertedItems: [],
    selectedFiles: new Set(),

    supportedClasses: ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"],

    normalizeClass(cls) {
      return String(cls || "").toUpperCase().trim();
    },

    getMeta(fname, year) {
      return this.convertedItems.find(
        (i) =>
          i.filename === fname &&
          String(i.year) === String(year)
      );
    },

    updatePushCount() {
      const el = document.getElementById("pushCount");
      if (el) el.textContent = this.selectedFiles.size;
    },

    initOnce(container = document) {
      const root = container.querySelector(".uploads-wrapper");
      if (!root || root.__initialized__) return;

      root.__initialized__ = true;

      const yearSelector = root.querySelector("#yearSelectorUploads");
      const classPills = root.querySelectorAll(".class-pill");
      const tableBody = root.querySelector("#uploadedTable");
      const searchBox = root.querySelector("#searchUploads");
      const refreshBtn = root.querySelector("#refreshUploads");
      const activeYearLabel = document.getElementById("activeYearLabel");

      if (!yearSelector || !tableBody) return;

      const setActiveYearLabel = (year) => {
        if (!activeYearLabel) return;

        if (!year || year === "Select Year") {
          activeYearLabel.textContent = "Active Year: —";
        } else {
          activeYearLabel.textContent = `Active Year: ${year}`;
        }
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
            <td colspan="8" class="empty">${escapeHtml(message)}</td>
          </tr>
        `;
      };

      const renderTable = () => {
        if (!this.activeYear) {
          renderEmpty("Select a year to load JSON files");
          return;
        }

        let rows = Array.isArray(this.convertedItems)
          ? [...this.convertedItems]
          : [];

        if (this.activeClass !== "ALL") {
          rows = rows.filter((item) => {
            const cls = this.normalizeClass(item.class_category);
            return cls === this.activeClass;
          });
        }

        const q = String(searchBox?.value || "").toLowerCase().trim();

        if (q) {
          rows = rows.filter((item) => {
            const filename = String(item.filename || "").toLowerCase();
            const subject = String(item.subject || "").toLowerCase();
            const cls = String(item.class_category || "").toLowerCase();

            return (
              filename.includes(q) ||
              subject.includes(q) ||
              cls.includes(q)
            );
          });
        }

        if (!rows.length) {
          const classText =
            this.activeClass === "ALL"
              ? ""
              : `${this.activeClass} `;

          renderEmpty(`No ${classText}files found for ${this.activeYear}.`);
          return;
        }

        tableBody.innerHTML = rows
          .map((item) => {
            const year = escapeHtml(item.year || this.activeYear);
            const filename = escapeHtml(item.filename || "");
            const subject = escapeHtml(item.subject || "Unknown");
            const classCategory = escapeHtml(item.class_category || "—");
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
                <td>${status}</td>

                <td>
                  <button class="btn-secondary tiny preview-btn" type="button">
                    Preview
                  </button>
                </td>
              </tr>
            `;
          })
          .join("");
      };

      const loadYearFiles = async (year, refreshing = false) => {
        if (!year || year === "Select Year") return;

        if (refreshing) setLoadingState(true);

        try {
          const res = await fetch(`/api/uploads/${encodeURIComponent(year)}`);
          const data = await res.json();

          if (!res.ok) {
            throw new Error(data.error || "Failed to load JSON files");
          }

          this.convertedItems = data.uploads || [];
          renderTable();

        } catch (err) {
          console.error("Upload list error:", err);
          renderEmpty("Failed to load JSON list.");
        }

        if (refreshing) {
          setTimeout(() => setLoadingState(false), 300);
        }
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

      refreshBtn?.addEventListener("click", () => {
        if (this.activeYear) {
          loadYearFiles(this.activeYear, true);
        }
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

          this.updatePushCount();
          return;
        }

        if (e.target.classList.contains("preview-btn")) {
          try {
            const meta = this.getMeta(filename, year);
            const cls = this.normalizeClass(meta?.class_category || row.dataset.class);

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
              alert(JSON.stringify(content, null, 2));
            }

          } catch (err) {
            console.error("Preview error:", err);
            alert("Could not preview file.");
          }
        }
      };

      searchBox?.addEventListener("input", renderTable);

      this.updatePushCount();
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
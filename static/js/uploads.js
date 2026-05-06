/* ==========================================================
   EMIS UPLOADS — YEAR + CLASS PILL FILTER BROWSER (v23 FINAL)
   Handles:
     • Load JSON files by YEAR
     • Filter by CLASS (SS1 / SS2 / SS3 / ALL via pills)
     • Search
     • Preview JSON
     • Select files for push
========================================================== */

function flashMessage(text, type = "success") {
  const fm = document.getElementById("flashMessage");
  if (!fm) return;
  fm.textContent = text;
  fm.className = `flash-message ${type} show`;
  setTimeout(() => fm.classList.remove("show"), 3000);
}

(() => {
  if (window.__EMIS_UPLOADS_BOUND__) return;
  window.__EMIS_UPLOADS_BOUND__ = true;

  window.EmisUploads = {
    activeYear: null,
    activeClass: "ALL", // NEW (SS1 / SS2 / SS3 / ALL)
    convertedItems: [],
    selectedFiles: new Set(),

    /* Get item meta by filename + year */
    getMeta(fname, year) {
      return this.convertedItems.find(
        (i) => i.filename === fname && String(i.year) === String(year)
      );
    },

    initOnce(container = document) {
      const root = container.querySelector(".uploads-wrapper");
      if (!root || root.__initialized__) return;
      root.__initialized__ = true;

      /* ELEMENTS */
      const yearSelector = root.querySelector("#yearSelectorUploads");
      const classPills = root.querySelectorAll(".class-pill"); // NEW pill UI
      const tableBody = root.querySelector("#uploadedTable");
      const searchBox = root.querySelector("#searchUploads");
      const refreshBtn = root.querySelector("#refreshUploads");

 /* ---------------------------------------------
   YEAR SELECTOR → Load year JSONs
---------------------------------------------- */
yearSelector.onchange = () => {
  this.activeYear = yearSelector.value;

  // ⭐ UPDATE ACTIVE YEAR LABEL (NEW)
  const activeYearLabel = document.getElementById("activeYearLabel");
  if (activeYearLabel) {
    activeYearLabel.textContent = 
      this.activeYear && this.activeYear !== "Select Year"
        ? `Active Year: ${this.activeYear}`
        : "Active Year: —";
  }

  loadYearFiles(this.activeYear);
};

      /* ---------------------------------------------
         CLASS PILL SELECTOR → Filter table
      ---------------------------------------------- */
      classPills.forEach((pill) => {
        pill.onclick = () => {
          classPills.forEach((p) => p.classList.remove("active"));
          pill.classList.add("active");

          this.activeClass = pill.dataset.class;
          renderTable();
        };
      });

      /* ---------------------------------------------
         REFRESH YEAR LIST
      ---------------------------------------------- */
      refreshBtn.onclick = () => {
        if (this.activeYear) loadYearFiles(this.activeYear, true);
      };

      /* ---------------------------------------------
         LOAD JSON LIST FOR A YEAR
      ---------------------------------------------- */
      async function loadYearFiles(year, refreshing = false) {
        if (!year) return;

        if (refreshing) {
          refreshBtn.disabled = true;
          refreshBtn.innerHTML = `<span class="spinner"></span>`;
        }

        try {
          const res = await fetch(`/api/uploads/${year}`);
          const data = await res.json();

          EmisUploads.convertedItems = data.uploads || [];
          renderTable();
        } catch (err) {
          console.error(err);
          tableBody.innerHTML = `
            <tr><td colspan="8" class="empty">Failed to load JSON list.</td></tr>`;
        }

        if (refreshing) {
          setTimeout(() => {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = `<i class="fa-solid fa-rotate"></i>`;
          }, 300);
        }
      }

      /* ---------------------------------------------
         RENDER TABLE — filtered by YEAR + CLASS pill
      ---------------------------------------------- */
      function renderTable() {
        if (!EmisUploads.activeYear) {
          tableBody.innerHTML = `
            <tr><td colspan="8" class="empty">Select a year to load JSON files</td></tr>`;
          return;
        }

        let rows = EmisUploads.convertedItems;

        /* APPLY CLASS FILTER */
        if (EmisUploads.activeClass !== "ALL") {
          rows = rows.filter(
            (i) => i.class_category.toUpperCase() === EmisUploads.activeClass
          );
        }

        if (!rows.length) {
          tableBody.innerHTML = `
            <tr><td colspan="8" class="empty">
              No ${EmisUploads.activeClass === "ALL" ? "" : EmisUploads.activeClass + " "}
              files found for ${EmisUploads.activeYear}.
            </td></tr>`;
          return;
        }

        tableBody.innerHTML = rows
          .map((item) => {
            const key = `${item.year}:${item.filename}`;
            return `
              <tr class="upload-row"
                  data-year="${item.year}"
                  data-filename="${item.filename}"
                  data-class="${item.class_category}">

                <td>
                  <input type="checkbox" class="row-select"
                    ${EmisUploads.selectedFiles.has(key) ? "checked" : ""}>
                </td>

                <td class="file-cell" data-clickable="true">
                  <div class="file-main">
                    <span class="file-name">${item.filename}</span>
                    <span class="file-meta">
                      ${item.subject} • ${item.class_category} • ${item.questions} questions
                    </span>
                  </div>
                </td>

                <td>${item.subject}</td>
                <td>${item.class_category}</td>
                <td>${item.version || "—"}</td>
                <td class="center">${item.questions}</td>
                <td class="center">${item.size_kb || "—"} KB</td>
                <td>${item.status || "OK"}</td>

                <td>
                  <button class="btn-secondary tiny preview-btn">Preview</button>
                </td>
              </tr>`;
          })
          .join("");
      }

      /* ---------------------------------------------
         ROW EVENTS: select + preview
      ---------------------------------------------- */
      tableBody.onclick = async (e) => {
        const row = e.target.closest("tr.upload-row");
        if (!row) return;

        const year = row.dataset.year;
        const fname = row.dataset.filename;
        const key = `${year}:${fname}`;

        /* Checkbox → SELECT */
        if (e.target.classList.contains("row-select")) {
          if (e.target.checked) EmisUploads.selectedFiles.add(key);
          else EmisUploads.selectedFiles.delete(key);
          updatePushCount();
          return;
        }

        /* Preview button */
        if (e.target.classList.contains("preview-btn")) {
          try {
            const res = await fetch(`/api/uploads/${year}/${fname}`);
            const json = await res.json();
            const meta = EmisUploads.getMeta(fname, year);

            ConvertUI.setPreviewCard(fname, meta, json);
            ConvertUI.openJsonModal(
              `Preview • ${year} • ${fname}`,
              JSON.stringify(json, null, 2)
            );
          } catch (err) {
            alert("Could not preview file.");
          }
        }
      };

      /* ---------------------------------------------
         SEARCH FILTER — by filename
      ---------------------------------------------- */
      searchBox.oninput = () => {
        const q = searchBox.value.toLowerCase();
        const rows = tableBody.querySelectorAll("tr.upload-row");

        rows.forEach((r) => {
          const name = r.dataset.filename.toLowerCase();
          r.style.display = name.includes(q) ? "" : "none";
        });
      };

      /* ---------------------------------------------
         UPDATE PUSH COUNT
      ---------------------------------------------- */
      function updatePushCount() {
        const el = document.getElementById("pushCount");
        if (el) el.textContent = EmisUploads.selectedFiles.size;
      }
    }
  };

  /* AUTO INIT HOOK */
  const autoInit = () => {
    const wrap = document.querySelector(".uploads-wrapper");
    if (wrap) window.EmisUploads.initOnce(document);
  };

  if (["complete", "interactive"].includes(document.readyState)) autoInit();
  else document.addEventListener("DOMContentLoaded", autoInit);

  new MutationObserver(autoInit).observe(document.body, {
    childList: true,
    subtree: true
  });
})();

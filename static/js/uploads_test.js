/* ==========================================================
   EMIS UPLOADS — uploads.js (v13, overwrite-aware)
   Handles:
     • Uploading files → /api/upload
     • Overwrite detection (status: "exists")
     • Overwrite / Skip modal actions
     • Staging files
     • Rendering table
     • Selection queue
     • Push-to-portal
     • Logs
     • Rolling loader for Convert
     • Refresh button with spinner
     • Full JSON preview
   ========================================================== */

/* ==========================================================
   FLASH MESSAGE
========================================================== */
function flashMessage(text, type = "success") {
  const fm = document.getElementById("flashMessage");
  if (!fm) return;
  fm.textContent = text;
  fm.className = `flash-message ${type} show`;
  setTimeout(() => fm.classList.remove("show"), 3000);
}

/* ==========================================================
   GLOBAL OVERWRITE CONFIRM MODAL
========================================================== */
function showOverwriteModal(item, onOverwrite, onSkip) {
  let modal = document.getElementById("overwriteModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "overwriteModal";
    modal.className = "overwrite-modal";
    modal.innerHTML = `
      <div class="ov-content">
        <h3>Subject Already Converted</h3>
        <p>
          <strong>${item.subject}</strong> (${item.class_category}) already exists.<br>
          Do you want to overwrite it with this new DOCX?
        </p>
        <div class="ov-buttons">
          <button id="ovOverwrite" class="btn-danger">Overwrite</button>
          <button id="ovSkip" class="btn-secondary">Skip</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const css = document.createElement("style");
    css.textContent = `
      .overwrite-modal {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,.55);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
      }
      .ov-content {
        background: #fff;
        padding: 1.4rem;
        width: 360px;
        border-radius: 10px;
        text-align: center;
      }
      .ov-buttons {
        margin-top: 1rem;
        display: flex;
        gap: 1rem;
        justify-content: center;
      }
      .btn-danger {
        background: #dc2626;
        color: #fff;
        padding: .5rem 1rem;
        border-radius: 6px;
      }
      .btn-secondary {
        padding: .5rem 1rem;
        background: #e5e7eb;
        border-radius: 6px;
      }
    `;
    document.head.appendChild(css);
  }

  modal.style.display = "flex";

  document.getElementById("ovOverwrite").onclick = () => {
    modal.style.display = "none";
    onOverwrite();
  };

  document.getElementById("ovSkip").onclick = () => {
    modal.style.display = "none";
    onSkip();
  };
}

/* ==========================================================
   MODULE WRAPPER
========================================================== */
(() => {
  if (window.__EMIS_UPLOADS_BOUND__) return;
  window.__EMIS_UPLOADS_BOUND__ = true;

  window.EmisUploads = {
    selectedFiles: new Set(),
    convertedItems: [],

    getMeta(fname) {
      return this.convertedItems.find((i) => i.filename === fname);
    },

    queueFromPreview(fname) {
      this.selectedFiles.add(fname);
      updatePushCount();
    },

    initOnce(container = document) {
      const root = container.querySelector(".uploads-wrapper");
      if (!root || root.__initialized__) return;
      root.__initialized__ = true;

      /* ELEMENT REFERENCES */
      const dropZone = root.querySelector("#uploadDropZone");
      const inputSingle = root.querySelector("#uploadInputSingle");
      const inputMulti = root.querySelector("#uploadInputMulti");
      const chooseSingle = root.querySelector("#chooseSingle");
      const chooseMulti = root.querySelector("#chooseMulti");
      const fileList = root.querySelector("#fileList");
      const selectedCountBadge = root.querySelector("#selectedCount");
      const startUpload = root.querySelector("#startUpload");
      const clearUploads = root.querySelector("#clearUploads");

      const uploadProgress = root.querySelector("#uploadProgress");
      const uploadProgressBar = root.querySelector("#uploadProgressBar");
      const uploadProgressLabel = root.querySelector("#uploadProgressLabel");

      const tableBody = root.querySelector("#uploadedTable");
      const searchBox = root.querySelector("#searchUploads");
      const refreshBtn = root.querySelector("#refreshUploads");

      const pushSelectedBtn = root.querySelector("#pushSelectedToPortal");
      const clearQueueBtn = root.querySelector("#clearQueue");
      const pushCountEl = root.querySelector("#pushCount");

      const btnViewSubjects = root.querySelector("#btnViewSubjects");
      const portalLogBody = root.querySelector("#portalLogBody");
      const clearPortalLogBtn = root.querySelector("#clearPortalLog");

      let stagedFiles = [];

      /* ==========================================================
         UTILITIES
      ========================================================== */
      const niceKB = (bytes) => Math.round((bytes / 1024) * 10) / 10;

      const showProgress = (on, label = "Converting…") => {
        uploadProgress.classList.toggle("hidden", !on);
        uploadProgressLabel.textContent = label;
      };

      const setProgress = (val) => {
        uploadProgressBar.style.width = `${val}%`;
      };

      const updateSelectedCountBadge = () => {
        selectedCountBadge.textContent = `${stagedFiles.length} selected`;
      };

      const updatePushCount = () => {
        pushCountEl.textContent = EmisUploads.selectedFiles.size;
        clearQueueBtn.classList.toggle("hidden", EmisUploads.selectedFiles.size === 0);
      };

      const logPortal = (msg) => {
        const placeholder = portalLogBody.querySelector(".log-placeholder");
        if (placeholder) portalLogBody.innerHTML = "";
        const p = document.createElement("p");
        p.textContent = msg;
        portalLogBody.appendChild(p);
        portalLogBody.scrollTop = portalLogBody.scrollHeight;
      };

      /* ==========================================================
         RENDER STAGED LIST
      ========================================================== */
      const renderStagedList = () => {
        fileList.innerHTML = "";
        if (!stagedFiles.length) {
          fileList.innerHTML = `<li class="empty">No files selected</li>`;
        } else {
          stagedFiles.forEach((f) => {
            fileList.innerHTML += `
              <li>
                <i class="fa-solid fa-file"></i>
                <span class="file-name">${f.name}</span>
                <span class="file-size">${niceKB(f.size)} KB</span>
              </li>`;
          });
        }
        updateSelectedCountBadge();
      };

      /* CLICK → INPUT */
      chooseSingle.onclick = () => inputSingle.click();
      chooseMulti.onclick = () => inputMulti.click();

      inputSingle.onchange = (e) => {
        stagedFiles = [...e.target.files];
        renderStagedList();
      };
      inputMulti.onchange = (e) => {
        stagedFiles = [...e.target.files];
        renderStagedList();
      };

      /* DRAG/DROP */
      dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
      };
      dropZone.ondragleave = () => dropZone.classList.remove("drag-over");
      dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        stagedFiles = [...e.dataTransfer.files];
        renderStagedList();
      };

      clearUploads.onclick = () => {
        stagedFiles = [];
        renderStagedList();
      };

      /* ==========================================================
         ROLLING LOADER (Convert button)
      ========================================================== */
      const normalBtnHTML = startUpload.innerHTML;

      const showLoadingButton = (msg = "Please wait… Converting") => {
        startUpload.disabled = true;
        startUpload.innerHTML = `<span class="spinner"></span>${msg}`;
        startUpload.classList.add("loading");
      };

      const hideLoadingButton = () => {
        startUpload.disabled = false;
        startUpload.innerHTML = normalBtnHTML;
        startUpload.classList.remove("loading");
      };

      const cssSpinner = document.createElement("style");
      cssSpinner.textContent = `
        .spinner {
          width: 18px;
          height: 18px;
          border: 3px solid #fff;
          border-top-color: transparent;
          border-radius: 50%;
          display: inline-block;
          margin-right: 8px;
          animation: spin .65s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        button.loading { opacity: .7; pointer-events: none; }
      `;
      document.head.appendChild(cssSpinner);

      /* ==========================================================
         START UPLOAD (with overwrite support)
      ========================================================== */
      startUpload.onclick = async () => {
        if (!stagedFiles.length) {
          alert("Please select files.");
          return;
        }

        try {
          showLoadingButton();
          showProgress(true);
          setProgress(25);

          const fd = new FormData();
          stagedFiles.forEach((f) => fd.append("file", f));

          const res = await fetch("/api/upload", { method: "POST", body: fd });
          setProgress(55);

          if (!res.ok) throw new Error("Upload failed");

          const payload = await res.json();
          setProgress(85);

          /* HANDLE "exists" CASE */
          const existsItems = payload.converted.filter((i) => i.status === "exists");

          if (existsItems.length) {
            hideLoadingButton();
            showProgress(false);

            const item = existsItems[0];

            showOverwriteModal(
              item,
              async () => {
                // overwrite
                const fd2 = new FormData();
                stagedFiles.forEach((f) => fd2.append("file", f));
                fd2.append("overwrite", "true");

                showLoadingButton("Overwriting…");
                await fetch("/api/upload", { method: "POST", body: fd2 });
                await fetchConverted();
                hideLoadingButton();
                flashMessage("Subject overwritten.", "success");
              },
              () => {
                flashMessage("Skipped — existing subject untouched.", "error");
              }
            );

            return;
          }

          /* NORMAL SUCCESS PATH */
          if (payload?.converted?.length) {
            const last = payload.converted[payload.converted.length - 1];
            const jname = last.json_filename;

            try {
              const jres = await fetch(`/api/uploads/${jname}`);
              const jdata = await jres.json();
              ConvertUI.setPreviewCard(jname, last, jdata);
            } catch (err) {
              console.warn("Preview failed:", err);
            }
          }

          await fetchConverted();
          stagedFiles = [];
          renderStagedList();
          logPortal("✅ Conversion completed.");
          setProgress(100);
        } catch (err) {
          alert(err.message);
        } finally {
          setTimeout(() => showProgress(false), 300);
          setProgress(0);
          hideLoadingButton();
        }
      };

      /* ==========================================================
         FETCH + REFRESH BUTTON
      ========================================================== */
      async function fetchConverted(showRefreshState = false) {
        try {
          if (showRefreshState) {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = `<span class="spinner"></span>Refreshing…`;
          }

          const res = await fetch("/api/uploads");
          const data = await res.json();
          EmisUploads.convertedItems = data.uploads || data;

          renderTable();
          updatePushCount();

          if (showRefreshState) {
            setTimeout(() => {
              refreshBtn.disabled = false;
              refreshBtn.innerHTML = `<i class="fa-solid fa-rotate-right"></i>`;
            }, 400);
          }
        } catch {
          tableBody.innerHTML =
            `<tr><td colspan="4" class="empty">Failed to load uploads</td></tr>`;
        }
      }

      refreshBtn.onclick = () => fetchConverted(true);

      /* ==========================================================
         RENDER TABLE
      ========================================================== */
      function renderTable() {
        tableBody.innerHTML = "";

        if (!EmisUploads.convertedItems.length) {
          tableBody.innerHTML = `<tr><td colspan="4" class="empty">No converted exams yet.</td></tr>`;
          return;
        }

        tableBody.innerHTML = EmisUploads.convertedItems
          .map(
            (item) => `
              <tr class="upload-row" data-filename="${item.filename}">
                <td><input type="checkbox" class="row-select"
                  ${EmisUploads.selectedFiles.has(item.filename) ? "checked" : ""}></td>

                <td class="file-cell" data-clickable="true">
                  <div class="file-main">
                    <span class="file-name">${item.filename}</span>
                    <span class="file-meta">${item.subject} • ${item.class_category} • ${item.questions} questions</span>
                  </div>
                </td>

                <td>${item.subject}</td>
                <td class="center">${item.questions}</td>
              </tr>`
          )
          .join("");
      }

      /* ==========================================================
         PREVIEW (Full JSON)
      ========================================================== */
      tableBody.onclick = async (e) => {
        const row = e.target.closest("tr.upload-row");
        if (!row) return;

        const fname = row.dataset.filename;

        // Checkbox toggle
        if (e.target.classList.contains("row-select")) {
          if (e.target.checked) EmisUploads.selectedFiles.add(fname);
          else EmisUploads.selectedFiles.delete(fname);
          updatePushCount();
          return;
        }

        if (e.target.closest("[data-clickable='true']")) {
          try {
            const res = await fetch(`/api/uploads/${fname}`);
            const data = await res.json();
            const meta = EmisUploads.getMeta(fname);

            ConvertUI.setPreviewCard(fname, meta, data);

            ConvertUI.openJsonModal(
              `Full Preview: ${fname}`,
              JSON.stringify(data, null, 2)
            );
          } catch (err) {
            alert("Preview error: " + err.message);
          }
        }
      };

      /* SEARCH */
      searchBox.oninput = () => {
        const q = searchBox.value.toLowerCase();
        const rows = tableBody.querySelectorAll("tr.upload-row");

        rows.forEach((r) => {
          const name = r.dataset.filename.toLowerCase();
          r.style.display = name.includes(q) ? "" : "none";
        });
      };

      /* PUSH SELECTED */
      pushSelectedBtn.onclick = async () => {
        if (!EmisUploads.selectedFiles.size) {
          flashMessage("No files selected.", "error");
          return;
        }

        const list = [...EmisUploads.selectedFiles];

        try {
          const res = await fetch("/push_to_portal", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ files: list }),
          });

          const out = await res.json();

          flashMessage(`${out.copied_files.length} file(s) pushed.`, "success");
          logPortal(`🚀 Pushed ${out.copied_files.length} file(s).`);

          EmisUploads.selectedFiles.clear();
          updatePushCount();
          renderTable();
        } catch (err) {
          flashMessage("Push failed", "error");
        }
      };

      clearQueueBtn.onclick = () => {
        EmisUploads.selectedFiles.clear();
        updatePushCount();
        renderTable();
        logPortal("Queue cleared");
      };

      btnViewSubjects.onclick = () =>
        ConvertUI.openSubjectsModal(EmisUploads.convertedItems);

      clearPortalLogBtn.onclick = () => {
        portalLogBody.innerHTML = `<p class="log-placeholder">No portal actions yet.</p>`;
      };

      /* INIT */
      renderStagedList();
      fetchConverted();
    },
  };

  /* AUTO-INIT */
  const autoInit = () => {
    const wrap = document.querySelector(".uploads-wrapper");
    if (wrap) window.EmisUploads.initOnce(document);
  };

  if (["complete", "interactive"].includes(document.readyState)) autoInit();
  else document.addEventListener("DOMContentLoaded", autoInit);

  new MutationObserver(autoInit).observe(document.body, {
    childList: true,
    subtree: true,
  });
})();

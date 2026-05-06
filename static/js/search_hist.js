/* search_hist.js — Dynamic History + Search for /uploads
   - Loads all documents on entering Uploads panel (or on page load)
   - Debounced search by partial name
   - Renders responsive cards with lazy PDF preview + open/copy
*/

(() => {
  if (window.__SEARCH_HIST_INIT__) return;
  window.__SEARCH_HIST_INIT__ = true;

  const ready = (cb) =>
    document.readyState !== "loading"
      ? cb()
      : document.addEventListener("DOMContentLoaded", cb);

  // Tiny toast
  function toast(msg, type = "info") {
    const el = document.createElement("div");
    el.className =
      "fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg text-sm text-white z-50 " +
      (type === "error"
        ? "bg-red-600"
        : type === "success"
        ? "bg-green-600"
        : "bg-gray-800");
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2600);
  }

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "";
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.min(
      Math.floor(Math.log(bytes) / Math.log(1024)),
      sizes.length - 1
    );
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  }

  // Debounce
  function debounce(fn, ms = 300) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  // Render
  function renderList(container, list) {
    if (!container) return;
    if (!list || list.length === 0) {
      container.innerHTML = `<div class="doc-empty">No documents found.</div>`;
      return;
    }
    const html = list
      .map((doc) => {
        const ext = (doc.ext || "").toLowerCase();
        const icon =
          ext === "pdf"
            ? "📕"
            : ext === "doc" || ext === "docx"
            ? "📄"
            : ext === "xls" || ext === "xlsx"
            ? "📊"
            : "📁";
        const size = formatBytes(doc.size);
        const dt = doc.mtime_str || "";
        const href = doc.url; // served by /uploads/<filename>

        // Lazy preview (button → iframe only when clicked)
        const preview =
          ext === "pdf"
            ? `<div class="doc-preview">
                 <button class="preview-btn" data-url="${href}">Preview</button>
                 <div class="preview-frame hidden"></div>
               </div>`
            : `<div class="doc-preview skel"></div>`;

        return `
        <div class="doc-card" data-name="${doc.name.toLowerCase()}">
          <div class="doc-hdr">
            <span class="doc-ico">${icon}</span>
            <div class="doc-name" title="${doc.name}">${doc.name}</div>
          </div>
          <div class="doc-meta">
            <span>${ext.toUpperCase()}</span>
            <span>•</span>
            <span>${size}</span>
            ${dt ? `<span>•</span><span>${dt}</span>` : ""}
          </div>
          ${preview}
          <div class="doc-actions">
            <a class="open-btn" href="${href}" target="_blank" rel="noopener">Open</a>
            <button class="copy-btn" data-url="${href}">Copy Link</button>
          </div>
        </div>`;
      })
      .join("");
    container.innerHTML = html;

    // Copy buttons
    container.querySelectorAll(".copy-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(btn.dataset.url);
          toast("Link copied", "success");
        } catch (e) {
          toast("Failed to copy", "error");
        }
      });
    });

    // Lazy preview buttons
    container.querySelectorAll(".preview-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const wrap = btn.closest(".doc-preview");
        const frameWrap = wrap.querySelector(".preview-frame");
        if (frameWrap.classList.contains("hidden")) {
          frameWrap.innerHTML = `<iframe src="${btn.dataset.url}#toolbar=0&navpanes=0&scrollbar=0" class="w-full h-40 border rounded"></iframe>`;
          frameWrap.classList.remove("hidden");
          btn.textContent = "Hide Preview";
        } else {
          frameWrap.innerHTML = "";
          frameWrap.classList.add("hidden");
          btn.textContent = "Preview";
        }
      });
    });
  }

  // Fetch
  async function fetchDocs(q = "") {
    const url = q ? `/documents?q=${encodeURIComponent(q)}` : `/documents`;
    const res = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
    if (!res.ok) throw new Error("Load failed");
    const data = await res.json();
    return data.documents || [];
  }

  // Load + bind
  ready(() => {
    const docList = document.getElementById("docList");
    const input = document.getElementById("docSearch");
    const searchBtn = document.getElementById("searchDocBtn");
    const clearBtn = document.getElementById("clearHistoryBtn");
    const uploadsPanel = document.getElementById("panel-uploads");

    if (!docList) return;

    // Load when Uploads panel becomes active (and on first load)
    async function loadAll() {
      try {
        const docs = await fetchDocs("");
        renderList(docList, docs);
      } catch (e) {
        console.error(e);
        renderList(docList, []);
        toast("Could not load documents", "error");
      }
    }

    // Observe route activation
    const observer = new MutationObserver((muts) => {
      muts.forEach((m) => {
        if (m.type === "attributes" && m.attributeName === "class") {
          if (uploadsPanel.classList.contains("is-active")) {
            loadAll();
          }
        }
      });
    });
    if (uploadsPanel) observer.observe(uploadsPanel, { attributes: true });

    // Also load once on boot (in case Uploads is default)
    if (uploadsPanel && uploadsPanel.classList.contains("is-active")) {
      loadAll();
    }

    // Debounced type search
    const doSearch = debounce(async () => {
      const q = (input?.value || "").trim();
      try {
        const docs = await fetchDocs(q);
        renderList(docList, docs);
      } catch (e) {
        renderList(docList, []);
      }
    }, 350);

    if (input) input.addEventListener("input", doSearch);
    if (searchBtn) searchBtn.addEventListener("click", () => doSearch());

    // ✅ Clear button only clears front-end, not reload
    if (clearBtn)
      clearBtn.addEventListener("click", () => {
        if (input) input.value = "";
        docList.innerHTML = `
        <div class="doc-empty">
          History cleared. <button id="reloadHistoryBtn" class="modern-btn modern-btn-secondary ml-2">Reload</button>
        </div>`;
        // bind reload button
        const reloadBtn = document.getElementById("reloadHistoryBtn");
        if (reloadBtn) reloadBtn.addEventListener("click", loadAll);
      });

    // Listen for uploads and refresh automatically
    window.addEventListener("documents:refresh", loadAll);
  });
})();

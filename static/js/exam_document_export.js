/* ==========================================================
   EMIS EXAM SERVER — TEACHER COPY
   PDF PREVIEW / PDF DOWNLOAD / DOCX DOWNLOAD
   + SELECTED EXAM VIEW / QUICK DOWNLOAD
========================================================== */

(() => {
  if (window.__EMIS_TEACHER_COPY_BOUND__) return;
  window.__EMIS_TEACHER_COPY_BOUND__ = true;

  const $ = (id) => document.getElementById(id);
  let currentPreviewObjectUrl = null;


  /* ======================================================
     NORMALIZERS / LABELS
  ====================================================== */

  const normalizeTerm = (value) => {
    const raw = String(value || "").trim().toUpperCase();

    const map = {
      "1": "FIRST", "01": "FIRST", "1ST": "FIRST", "FIRST": "FIRST", "FIRST TERM": "FIRST",
      "2": "SECOND", "02": "SECOND", "2ND": "SECOND", "SECOND": "SECOND", "SECOND TERM": "SECOND",
      "3": "THIRD", "03": "THIRD", "3RD": "THIRD", "THIRD": "THIRD", "THIRD TERM": "THIRD"
    };

    return map[raw] || null;
  };

  const termLabel = (value) => ({ FIRST: "1st Term", SECOND: "2nd Term", THIRD: "3rd Term" }[normalizeTerm(value)] || "General");

  const prettyFilename = (filename) => String(filename || "")
    .replace(/\.json$/i, "").replaceAll("_", " ").replaceAll("-", " ")
    .replace(/\s+/g, " ").trim().replace(/\b\w/g, (char) => char.toUpperCase());


  /* ======================================================
     URL BUILDER
  ====================================================== */

  const buildTeacherCopyUrl = ({ year, filename, classCategory, term, format, disposition = "attachment" }) => {
    const params = new URLSearchParams({ class: classCategory, format, disposition, _ts: Date.now().toString() });
    if (term) params.set("term", term);

    return `/api/uploads/${encodeURIComponent(year)}/${encodeURIComponent(filename)}/teacher-copy?${params.toString()}`;
  };


const buildTeacherPreviewUrl = ({ year, filename, classCategory, term }) => {
  const params = new URLSearchParams({
    class: classCategory,
    _ts: Date.now().toString()
  });

  if (term) params.set("term", term);

  return `/api/uploads/${encodeURIComponent(year)}/${encodeURIComponent(filename)}/teacher-copy/preview?${params.toString()}`;
};

  /* ======================================================
     UI STATE
  ====================================================== */

  const setLoading = (loading, text = "Preparing teacher copy...") => {
    const loader = $("teacherCopyLoader");
    const loaderText = $("teacherCopyLoaderText");
    const frame = $("teacherCopyFrame");

    if (loaderText) loaderText.textContent = text;
    loader?.classList.toggle("hidden", !loading);
    frame?.classList.toggle("loading", loading);
  };

  const setButtonsDisabled = (disabled) => {
    ["downloadTeacherDocx", "downloadTeacherPdf"].forEach((id) => {
      const button = $(id);
      if (button) button.disabled = disabled;
    });
  };

  const clearPreviewObjectUrl = () => {
    if (!currentPreviewObjectUrl) return;

    URL.revokeObjectURL(currentPreviewObjectUrl);
    currentPreviewObjectUrl = null;
  };

/* ======================================================
   FETCH + DISPLAY PDF PREVIEW
   Preview comes as Base64 JSON so download managers
   cannot intercept the PDF request.
====================================================== */

async function loadPdfPreview(previewUrl) {
  const frame = $("teacherCopyFrame");

  if (!frame) throw new Error("PDF preview frame is unavailable.");

  clearPreviewObjectUrl();
  setLoading(true, "Preparing teacher copy...");
  setButtonsDisabled(true);

  const response = await fetch(previewUrl, {
    method: "GET",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Cache-Control": "no-cache",
      Pragma: "no-cache"
    }
  });

  let output;

  try {
    output = await response.json();
  } catch (_) {
    throw new Error("Invalid preview response received from the server.");
  }

  if (!response.ok || !output?.success) {
    throw new Error(output?.error || "Unable to generate PDF preview.");
  }

  const encoded = String(output.pdf_base64 || "");

  if (!encoded) {
    throw new Error("The generated PDF preview contains no data.");
  }

  let binary;

  try {
    binary = atob(encoded);
  } catch (_) {
    throw new Error("The generated PDF preview could not be decoded.");
  }

  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }

  const pdfBlob = new Blob([bytes], { type: "application/pdf" });

  if (!pdfBlob.size) {
    throw new Error("The generated PDF preview is empty.");
  }

  currentPreviewObjectUrl = URL.createObjectURL(pdfBlob);

  frame.onload = () => {
    setLoading(false);
    setButtonsDisabled(false);
  };

  frame.onerror = () => {
    setLoading(false);
    setButtonsDisabled(false);
    window.flashMessage?.("The PDF was generated but could not be displayed.", "error");
  };

  frame.src = currentPreviewObjectUrl;

  /* Chrome PDF viewer fallback */
  setTimeout(() => {
    setLoading(false);
    setButtonsDisabled(false);
  }, 900);
}

/* ======================================================
   OPEN TEACHER COPY
====================================================== */

async function openTeacherCopy(row) {
  if (!row) return;

  const year = String(row.dataset.year || "").trim();
  const filename = String(row.dataset.filename || "").trim();
  const classCategory = String(row.dataset.class || "").trim().toUpperCase();
  const term = normalizeTerm(row.dataset.term);

  if (!year || !filename || !classCategory) {
    window.flashMessage?.("Unable to determine the exam file details.", "error");
    return;
  }

  const modal = $("teacherCopyModal");
  const frame = $("teacherCopyFrame");
  const title = $("teacherCopyTitle");
  const meta = $("teacherCopyMeta");
  const pdfBtn = $("downloadTeacherPdf");
  const docxBtn = $("downloadTeacherDocx");

  if (!modal || !frame) {
    window.flashMessage?.("Teacher Copy interface is unavailable.", "error");
    return;
  }

  const previewUrl = buildTeacherPreviewUrl({ year, filename, classCategory, term });
  const pdfUrl = buildTeacherCopyUrl({ year, filename, classCategory, term, format: "pdf", disposition: "attachment" });
  const docxUrl = buildTeacherCopyUrl({ year, filename, classCategory, term, format: "docx", disposition: "attachment" });

  if (title) title.textContent = prettyFilename(filename);
  if (meta) meta.textContent = `${classCategory} • ${term ? termLabel(term) : "General"} • ${year}`;

  if (pdfBtn) pdfBtn.onclick = () => window.location.href = pdfUrl;
  if (docxBtn) docxBtn.onclick = () => window.location.href = docxUrl;

  frame.src = "about:blank";
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");

  try {
    await loadPdfPreview(previewUrl);
  } catch (error) {
    console.error("[Teacher Copy] Preview error:", error);
    setLoading(false);
    setButtonsDisabled(false);
    window.flashMessage?.(error.message || "Could not load the teacher-copy PDF.", "error");
  }
}

  /* ======================================================
     OPEN SELECTED EXAM PDF
  ====================================================== */

  function viewSelectedExamPdf() {
    const uploads = window.EmisUploads;

    if (!uploads || typeof uploads.getSelectedItems !== "function") {
      window.flashMessage?.("Upload selection data is unavailable.", "error");
      return;
    }

    const selected = uploads.getSelectedItems();

    if (selected.length !== 1) {
      window.flashMessage?.("Select one exam to view its PDF.", "error");
      return;
    }

    const item = selected[0];
    const year = String(item.year || "").trim();
    const filename = String(item.filename || "").trim();

    const classCategory = typeof uploads.getItemClass === "function"
      ? uploads.getItemClass(item)
      : String(item.class_category || item.class_level || item.class || "").trim().toUpperCase();

    const term = typeof uploads.getItemTerm === "function"
      ? uploads.getItemTerm(item)
      : normalizeTerm(item.term);

    if (!year || !filename || !classCategory) {
      window.flashMessage?.("Unable to determine the selected exam details.", "error");
      return;
    }

    const fakeRow = document.createElement("tr");

    fakeRow.className = "upload-row";
    fakeRow.dataset.year = year;
    fakeRow.dataset.filename = filename;
    fakeRow.dataset.class = classCategory;
    fakeRow.dataset.term = term || "";

    openTeacherCopy(fakeRow);
  }


  /* ======================================================
     CLOSE TEACHER COPY
  ====================================================== */

  function closeTeacherCopy() {
    const modal = $("teacherCopyModal");
    const frame = $("teacherCopyFrame");

    modal?.classList.add("hidden");
    document.body.classList.remove("modal-open");

    if (frame) {
      frame.onload = null;
      frame.onerror = null;
      frame.src = "about:blank";
      frame.classList.remove("loading");
    }

    clearPreviewObjectUrl();
    setLoading(false);
    setButtonsDisabled(false);
  }


  /* ======================================================
     SELECTED EXAM ACTION BUTTONS
  ====================================================== */

  function updateSelectedExamPdfButton() {
    const viewBtn = $("selectedExamViewBtn");
    const viewLabel = $("selectedExamViewLabel");
    const pdfBtn = $("selectedExamPdfBtn");
    const pdfLabel = $("selectedExamPdfLabel");
    const uploads = window.EmisUploads;

    if (!uploads || !viewBtn || !pdfBtn) return;

    const selected = typeof uploads.getSelectedItems === "function" ? uploads.getSelectedItems() : [];
    const count = selected.length;

    if (!count) {
      viewBtn.classList.add("hidden");
      pdfBtn.classList.add("hidden");

      viewBtn.disabled = false;
      pdfBtn.disabled = false;

      if (viewLabel) viewLabel.textContent = "View PDF";
      if (pdfLabel) pdfLabel.textContent = "Download PDF";

      return;
    }

    viewBtn.classList.remove("hidden");
    pdfBtn.classList.remove("hidden");

    if (count === 1) {
      viewBtn.disabled = false;
      pdfBtn.disabled = false;

      if (viewLabel) viewLabel.textContent = "View PDF";
      if (pdfLabel) pdfLabel.textContent = "Download PDF";

      return;
    }

    viewBtn.disabled = true;
    pdfBtn.disabled = true;

    if (viewLabel) viewLabel.textContent = `${count} Selected`;
    if (pdfLabel) pdfLabel.textContent = "Download PDF";
  }


  /* ======================================================
     DOWNLOAD SELECTED EXAM PDF
  ====================================================== */

  function downloadSelectedExamPdf() {
    const uploads = window.EmisUploads;

    if (!uploads || typeof uploads.getSelectedItems !== "function") {
      window.flashMessage?.("Upload selection data is unavailable.", "error");
      return;
    }

    const selected = uploads.getSelectedItems();

    if (selected.length !== 1) {
      window.flashMessage?.("Select one exam to download its PDF.", "error");
      return;
    }

    const item = selected[0];
    const year = String(item.year || "").trim();
    const filename = String(item.filename || "").trim();

    const classCategory = typeof uploads.getItemClass === "function"
      ? uploads.getItemClass(item)
      : String(item.class_category || item.class_level || item.class || "").trim().toUpperCase();

    const term = typeof uploads.getItemTerm === "function"
      ? uploads.getItemTerm(item)
      : normalizeTerm(item.term);

    if (!year || !filename || !classCategory) {
      window.flashMessage?.("Unable to determine the selected exam details.", "error");
      return;
    }

    const url = buildTeacherCopyUrl({ year, filename, classCategory, term, format: "pdf", disposition: "attachment" });

    window.location.href = url;
  }


  /* ======================================================
     MAIN CLICK EVENTS
  ====================================================== */

  document.addEventListener("click", (event) => {
    const teacherBtn = event.target.closest(".teacher-copy-btn");

    if (teacherBtn) {
      event.preventDefault();
      event.stopPropagation();

      const row = teacherBtn.closest("tr.upload-row");
      if (!row) return;

      openTeacherCopy(row);
      return;
    }

    if (event.target.closest("[data-teacher-copy-close]")) {
      event.preventDefault();
      closeTeacherCopy();
      return;
    }

    if (event.target.closest("#selectedExamViewBtn")) {
      event.preventDefault();
      viewSelectedExamPdf();
      return;
    }

    if (event.target.closest("#selectedExamPdfBtn")) {
      event.preventDefault();
      downloadSelectedExamPdf();
    }
  });


  /* ======================================================
     SELECTION EVENTS
  ====================================================== */

  document.addEventListener("change", (event) => {
    if (event.target.matches(".row-select, #checkAllUploads")) {
      setTimeout(updateSelectedExamPdfButton, 0);
    }
  });

  document.addEventListener("click", (event) => {
    if (event.target.closest("#selectAllVisible, #clearQueue")) {
      setTimeout(updateSelectedExamPdfButton, 0);
    }
  });


  /* ======================================================
     CUSTOM SELECTION EVENT
  ====================================================== */

  document.addEventListener("emis:upload-selection-changed", updateSelectedExamPdfButton);


  /* ======================================================
     ESCAPE
  ====================================================== */

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;

    const modal = $("teacherCopyModal");

    if (modal && !modal.classList.contains("hidden")) {
      closeTeacherCopy();
    }
  });


  /* ======================================================
     INITIAL SYNC
  ====================================================== */

  const initializeSelectedPdfButton = () => setTimeout(updateSelectedExamPdfButton, 0);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSelectedPdfButton);
  } else {
    initializeSelectedPdfButton();
  }

})();
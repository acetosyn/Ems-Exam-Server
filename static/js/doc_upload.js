/* doc_upload.js — Admin Document Upload (modernized)
   Handles choose/clear, preview, drag-drop, progress, and upload
*/

(() => {
  if (window.__DOC_UPLOAD_INIT__) return;
  window.__DOC_UPLOAD_INIT__ = true;

  const ready = (cb) =>
    document.readyState !== "loading"
      ? cb()
      : document.addEventListener("DOMContentLoaded", cb);

  // --- Tiny toast feedback ---
  function showToast(msg, type = "info") {
    const toast = document.createElement("div");
    toast.className =
      "fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg text-sm text-white z-50 " +
      (type === "error"
        ? "bg-red-600"
        : type === "success"
        ? "bg-green-600"
        : "bg-gray-800");
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  // --- Init Upload Logic ---
  ready(() => {
    const input = document.getElementById("fileID");
    const chooseBtn = document.getElementById("chooseFileBtn");
    const clearBtn = document.getElementById("clearFileBtn");
    const uploadBtn = document.getElementById("uploadBtn");
    const fileChosen = document.getElementById("fileChosen");
    const previewCard = document.getElementById("filePreviewCard");
    const previewFileName = document.getElementById("previewFileName");
    const previewFileType = document.getElementById("previewFileType");
    const previewFrame = document.getElementById("previewFrame");
    const uploadSummary = document.getElementById("uploadSummary");
    const uploadStatus = document.getElementById("uploadStatus");
    const dropBox = document.querySelector(".drop_box");
    const progressWrap = document.getElementById("uploadProgress");
    const progressBar = progressWrap ? progressWrap.querySelector(".progress-bar") : null;

    if (!input || !chooseBtn || !clearBtn || !uploadBtn) {
      console.warn("[doc_upload] Missing required DOM elements");
      return;
    }

    // File type whitelist
    const ALLOWED_TYPES = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "application/vnd.ms-excel",
    ];

    // --- Open file chooser ---
    chooseBtn.addEventListener("click", (e) => {
      e.preventDefault();
      input.click();
    });

    // --- Clear file selection ---
    clearBtn.addEventListener("click", (e) => {
      e.preventDefault();
      resetUI();
      showToast("File cleared", "info");
    });

    // --- Handle file selection ---
    input.addEventListener("change", () => {
      handleFile(input.files[0]);
    });

    // --- Drag and Drop support ---
    if (dropBox) {
      ["dragenter", "dragover"].forEach((evt) =>
        dropBox.addEventListener(evt, (e) => {
          e.preventDefault();
          dropBox.classList.add("dragover");
        })
      );
      ["dragleave", "drop"].forEach((evt) =>
        dropBox.addEventListener(evt, (e) => {
          e.preventDefault();
          dropBox.classList.remove("dragover");
        })
      );
      dropBox.addEventListener("drop", (e) => {
        const file = e.dataTransfer.files[0];
        if (file) {
          input.files = e.dataTransfer.files;
          handleFile(file);
        }
      });
    }

    function handleFile(file) {
      if (!file) {
        resetUI();
        return;
      }

      const fileName = file.name;
      const fileType = file.type || "unknown";

      // Validate type
      if (
        !ALLOWED_TYPES.includes(file.type) &&
        !/\.(pdf|docx?|xlsx?)$/i.test(fileName)
      ) {
        resetUI();
        showToast("Invalid file type. Only PDF, Word, Excel allowed.", "error");
        return;
      }

      // Basic info
      fileChosen.textContent = `Selected: ${fileName}`;
      fileChosen.classList.remove("hidden");

      previewFileName.textContent = fileName;
      previewFileType.textContent = `Type: ${fileType}`;
      previewCard.classList.remove("hidden");
      clearBtn.classList.remove("hidden");

      previewFrame.src = "";
      previewFrame.classList.add("hidden");

      // PDF inline preview
      if (file.type === "application/pdf") {
        const reader = new FileReader();
        reader.onload = (e) => {
          previewFrame.src = e.target.result;
          previewFrame.classList.remove("hidden");
        };
        reader.readAsDataURL(file);
      }

      // Upload summary card
      let summaryHTML = `
        <div class="border rounded-lg p-3 bg-gray-50 shadow-sm">
          <p class="font-medium text-navy">${fileName}</p>
          <p class="text-xs text-gray-500">${fileType}</p>
      `;

      if (file.type === "application/pdf") {
        summaryHTML += `<iframe class="w-full h-32 border rounded mt-2" src="${URL.createObjectURL(
          file
        )}"></iframe>`;
      } else if (/\.docx?$/i.test(fileName)) {
        summaryHTML += `<div class="mt-2 text-sm text-blue-600">📄 Word document selected</div>`;
      } else if (/\.xlsx?$/i.test(fileName)) {
        summaryHTML += `<div class="mt-2 text-sm text-green-600">📊 Excel spreadsheet selected</div>`;
      } else {
        summaryHTML += `<div class="mt-2 text-sm text-gray-600">📎 Preview not available</div>`;
      }

      summaryHTML += `</div>`;
      if (uploadSummary) uploadSummary.innerHTML = summaryHTML;

      showToast("File selected", "success");
    }

    // --- Upload file to backend ---
    uploadBtn.addEventListener("click", async () => {
      if (!input.files || input.files.length === 0) {
        showToast("No file selected", "error");
        return;
      }

      const file = input.files[0];
      const formData = new FormData();
      formData.append("file", file);

      uploadStatus.textContent = "Uploading...";
      uploadStatus.classList.remove("text-green-600", "text-red-600");
      uploadStatus.classList.add("text-gray-600");

      if (progressWrap && progressBar) {
        progressWrap.classList.remove("hidden");
        progressBar.style.width = "0%";
      }

      try {
        const res = await fetch("/upload_document", {
          method: "POST",
          body: formData,
        });

        // Simulate progress animation
        if (progressBar) {
          let percent = 0;
          const interval = setInterval(() => {
            percent += 15;
            if (percent > 100) {
              percent = 100;
              clearInterval(interval);
            }
            progressBar.style.width = percent + "%";
          }, 200);
        }

        const data = await res.json();
        if (res.ok && data.filename) {
          uploadStatus.textContent = "✅ Upload successful: " + data.filename;
          uploadStatus.classList.remove("text-gray-600", "text-red-600");
          uploadStatus.classList.add("text-green-600");
          showToast("File uploaded successfully", "success");
        } else {
          throw new Error(data.error || "Upload failed");
        }
      } catch (err) {
        console.error("[doc_upload] Upload error:", err);
        uploadStatus.textContent = "❌ Upload failed: " + err.message;
        uploadStatus.classList.remove("text-gray-600", "text-green-600");
        uploadStatus.classList.add("text-red-600");
        showToast("Upload failed: " + err.message, "error");
      } finally {
        if (progressWrap) setTimeout(() => progressWrap.classList.add("hidden"), 1200);
      }
    });

    function resetUI() {
      input.value = "";
      fileChosen.textContent = "";
      fileChosen.classList.add("hidden");
      previewCard.classList.add("hidden");
      clearBtn.classList.add("hidden");
      previewFrame.src = "";
      previewFrame.classList.add("hidden");
      if (uploadSummary) uploadSummary.innerHTML = "";
      if (uploadStatus) uploadStatus.textContent = "";
      if (progressWrap && progressBar) {
        progressBar.style.width = "0%";
        progressWrap.classList.add("hidden");
      }
    }

    console.log("[doc_upload] Upload initialized");
  });
})();

/* ==========================================================
   EMIS CONVERSION UI CONTROLLER — convert.js  (v2, updated)
   Matches NEW convert.py structure:
     • No version field
     • class_category used instead
     • ID always present
   ========================================================== */

window.ConvertUI = (() => {

  /* ------------------------------------------------------
     DOM REFERENCES
  ------------------------------------------------------ */
  const modalRoot        = document.body;

  const jsonPreviewModal = document.getElementById("jsonPreviewModal");
  const jsonPreviewTitle = document.getElementById("jsonPreviewTitle");
  const jsonPreviewBody  = document.getElementById("jsonPreviewBody");
  const modalFooterPush  = document.getElementById("modalPushToPortal");

  const subjectsModal      = document.getElementById("subjectsModal");
  const subjectsCards      = document.getElementById("subjectsCardsContainer");
  const subjectsEmptyState = document.getElementById("subjectsEmptyState");

  const previewSubjectPill       = document.getElementById("previewSubjectPill");
  const previewVersionPill       = document.getElementById("previewVersionPill");   // ← will show class instead
  const previewQuestionCountPill = document.getElementById("previewQuestionCountPill");
  const latestPreviewBody        = document.getElementById("latestPreviewBody");

  /* Preview state */
  let latestPreview = {
    filename: null,
    subject: null,
    class_category: null,
    questions: 0,
    data: null,
  };

  /* ==========================================================
     JSON PREVIEW MODAL
  ========================================================== */
  const openJsonModal = (title, content) => {
    jsonPreviewTitle.textContent = title;
    jsonPreviewBody.textContent  = content;
    jsonPreviewModal.classList.remove("hidden");
    modalRoot.classList.add("overflow-hidden");
  };

  const closeJsonModal = () => {
    jsonPreviewModal.classList.add("hidden");
    modalRoot.classList.remove("overflow-hidden");
    jsonPreviewBody.textContent = "";
  };

  jsonPreviewModal?.addEventListener("click", (e) => {
    if (e.target.dataset.close === "true" || e.target.classList.contains("modal-backdrop")) {
      closeJsonModal();
    }
  });

  if (modalFooterPush) {
    modalFooterPush.addEventListener("click", () => {
      if (latestPreview.filename && window.EmisUploads?.queueFromPreview) {
        window.EmisUploads.queueFromPreview(latestPreview.filename);
      }
      closeJsonModal();
    });
  }


  /* ==========================================================
     PREVIEW CARD — UPDATED FOR convert.py
  ========================================================== */
  const setPreviewCard = (filename, meta, data) => {
    latestPreview = {
      filename,
      subject: meta?.subject || data?.subject || "—",
      class_category: meta?.class_category || data?.class_category || "—",
      questions: meta?.questions || (data?.questions?.length ?? 0),
      data,
    };

    previewSubjectPill.textContent = `Subject: ${latestPreview.subject}`;

    // 🔥 No version — show CLASS CATEGORY instead
    previewVersionPill.textContent = `Class: ${latestPreview.class_category}`;

    previewQuestionCountPill.textContent = `Questions: ${latestPreview.questions}`;

    if (!data) {
      latestPreviewBody.innerHTML =
        `<p class="preview-placeholder">Upload & convert to see JSON preview.</p>`;
    } else {
      const snippet = data.questions ? data.questions.slice(0, 3) : data;
      latestPreviewBody.textContent = JSON.stringify(snippet, null, 2);
    }
  };


  /* ==========================================================
     SUBJECTS MODAL — UPDATED
  ========================================================== */
  const openSubjectsModal = (convertedItems) => {
    renderSubjects(convertedItems);
    subjectsModal.classList.remove("hidden");
    modalRoot.classList.add("overflow-hidden");
  };

  const closeSubjectsModal = () => {
    subjectsModal.classList.add("hidden");
    modalRoot.classList.remove("overflow-hidden");
  };

  subjectsModal?.addEventListener("click", (e) => {
    if (e.target.dataset.close === "true" || e.target.classList.contains("modal-backdrop")) {
      closeSubjectsModal();
    }
  });

  const renderSubjects = (items) => {
    subjectsCards.innerHTML = "";

    if (!items.length) {
      subjectsEmptyState.classList.remove("hidden");
      return;
    }
    subjectsEmptyState.classList.add("hidden");

    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "subject-card";
      card.dataset.filename = item.filename;

      card.innerHTML = `
        <header>
          <span class="subject-name">${item.subject}</span>
          <span class="subject-version-pill">Class ${item.class_category}</span>
        </header>

        <p class="subject-filename">${item.filename}</p>
        <p class="subject-meta">${item.questions} question(s)</p>

        <div class="subject-actions">
          <button class="btn-primary tiny act-push-one">
            <i class="fa-solid fa-cloud-arrow-up"></i> Queue for Push
          </button>

          <button class="btn-secondary tiny act-preview-one">
            <i class="fa-solid fa-eye"></i> Preview JSON
          </button>
        </div>
      `;

      subjectsCards.appendChild(card);
    });
  };

  subjectsCards?.addEventListener("click", async (e) => {
    const card = e.target.closest(".subject-card");
    if (!card) return;

    const fname = card.dataset.filename;

    if (e.target.closest(".act-push-one")) {
      window.EmisUploads?.queueFromPreview?.(fname);
      return;
    }

    if (e.target.closest(".act-preview-one")) {
      try {
        const res = await fetch(`/api/uploads/${encodeURIComponent(fname)}`);
        const data = await res.json();
        const meta = window.EmisUploads?.getMeta(fname);

        setPreviewCard(fname, meta, data);

        const snippet = data.questions ? data.questions.slice(0, 5) : data;
        openJsonModal(`Preview: ${fname}`, JSON.stringify(snippet, null, 2));
      } catch (err) {
        alert(`Preview failed: ${err.message}`);
      }
    }
  });


  /* ------------------------------------------------------
     PUBLIC API
  ------------------------------------------------------ */
  return {
    setPreviewCard,
    openJsonModal,
    closeJsonModal,
    openSubjectsModal,
    latestPreview: () => latestPreview
  };
})();

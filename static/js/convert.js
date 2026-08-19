/* ============================================================
   EMIS SMART CONVERTER — convert.js
   Upgraded Dual-Workspace Build

   Supports:
   - Full Converter page (.convert-wrapper)
   - Upload page quick conversion (#startUpload)
   - One DOCX conversion
   - Multiple DOCX batch conversion
   - DOCX/TXT extraction
   - Backend subject/class/year detection
   - JSS term metadata support
   - OpenAI answer solving + verification
   - Temporary drafts
   - Save to JSON Exam Library
   - Upload page automatic library refresh

   APIs:
   /convert/api/extract
   /convert/api/generate-json
   /convert/api/save-json
   /convert/api/drafts

   Flow:
   DOCX/TXT
      ↓
   Extract Clean Text
      ↓
   Generate CBT JSON + Answers
      ↓
   Validate / Draft
      ↓
   Save Exam Library
============================================================ */

window.EmisConvert = (() => {

  /* ==========================================================
     API ENDPOINTS
  ========================================================== */

  const API = {
    extract: "/convert/api/extract",
    generate: "/convert/api/generate-json",
    save: "/convert/api/save-json",
    drafts: "/convert/api/drafts",
  };


  /* ==========================================================
     CONFIGURATION
  ========================================================== */

  const TERM_AWARE_CLASSES = ["JSS1", "JSS2", "JSS3"];

  let state = getFreshState();


  /* ==========================================================
     STATE
  ========================================================== */

  function getFreshState() {
    return {
      file: null,
      cleanText: "",
      generatedJSON: null,
      studentJSON: null,
      fullJSON: null,
      validation: null,

      diagramMap: {},
      diagramCount: 0,

      detectedYear: "",
      detectedTerm: "",

      objectiveWarnings: [],
      multipleObjectiveSeries: false,
      seriesInfo: {},

      answerReport: [],
      openaiUsage: {},
      needsReview: 0,

      rawPayload: null,
      draft: null,
    };
  }


  /* ==========================================================
     BASIC NORMALIZERS
  ========================================================== */

  function normalizeClass(value) {
    const raw = String(value || "")
      .toUpperCase()
      .replaceAll("-", "_")
      .replace(/\s+/g, "")
      .trim();

    for (const cls of ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]) {
      if (raw === cls || raw.startsWith(cls)) return cls;
    }

    return "";
  }


  function isTermAwareClass(value) {
    return TERM_AWARE_CLASSES.includes(normalizeClass(value));
  }


  function normalizeTerm(value) {
    const raw = String(value || "").trim().toUpperCase();

    if (!raw) return null;

    const aliases = {
      "1": "FIRST",
      "01": "FIRST",
      "1ST": "FIRST",
      "FIRST": "FIRST",
      "FIRST TERM": "FIRST",
      "1ST TERM": "FIRST",
      "TERM 1": "FIRST",
      "TERM1": "FIRST",

      "2": "SECOND",
      "02": "SECOND",
      "2ND": "SECOND",
      "SECOND": "SECOND",
      "SECOND TERM": "SECOND",
      "2ND TERM": "SECOND",
      "TERM 2": "SECOND",
      "TERM2": "SECOND",

      "3": "THIRD",
      "03": "THIRD",
      "3RD": "THIRD",
      "THIRD": "THIRD",
      "THIRD TERM": "THIRD",
      "3RD TERM": "THIRD",
      "TERM 3": "THIRD",
      "TERM3": "THIRD",
    };

    return aliases[raw] || null;
  }


  function termLabel(term) {
    const value = normalizeTerm(term);

    return {
      FIRST: "1st Term",
      SECOND: "2nd Term",
      THIRD: "3rd Term",
    }[value] || "—";
  }


  /* ==========================================================
     INITIALIZE FULL CONVERTER PAGE
  ========================================================== */

  function initOnce(root = document) {
    const T = window.EmisConvertTools;
    const X = window.EmisConvertExt;

    if (!T) {
      console.error(
        "EmisConvertTools missing. Load convert_helpers.js before convert.js"
      );
      return;
    }

    const wrap = T.q(".convert-wrapper", root);

    if (!wrap || wrap.__initialized__) return;

    wrap.__initialized__ = true;

    const els = getElements(wrap);

    T.bindModalClose(wrap);

    bindUpload(els, T);
    bindActions(els, T, X);
    bindModals(els, T, X);
    bindViewPills(els, T);

    refreshAllUI(els, T, X);
    loadDrafts(els, T, X);

    T.addLog(
      els.logBody,
      "Converter workspace opened.",
      "success"
    );
  }


  /* ==========================================================
     CONVERTER PAGE DOM ELEMENTS
  ========================================================== */

  function getElements(wrap) {
    const T = window.EmisConvertTools;

    return {
      wrap,

      dropZone: T.q("#convertDropZone", wrap),
      fileInput: T.q("#convertFileInput", wrap),
      chooseFile: T.q("#chooseConvertFile", wrap),
      clearFile: T.q("#clearConvertFile", wrap),

      selectedFile: T.q("#convertSelectedFile", wrap),
      questionCount: T.q("#convertQuestionCount", wrap),
      diagramCount: T.q("#convertDiagramCount", wrap),
      validationStatus: T.q("#convertValidationStatus", wrap),

      fileBadge: T.q("#convertFileBadge", wrap),
      fileList: T.q("#convertFileList", wrap),

      year: T.q("#convertYear", wrap),
      classCategory: T.q("#convertClass", wrap),
      subject: T.q("#convertSubject", wrap),
      expectedCount: T.q("#convertExpectedCount", wrap),

      term:
        T.q("#convertTerm", wrap) ||
        T.q("#examTerm", wrap),

      objectiveOnly: T.q("#objectiveOnlyMode", wrap),
      extractDiagrams: T.q("#extractDiagramsMode", wrap),
      strictJson: T.q("#strictJsonMode", wrap),

      extractBtn: T.q("#extractConvertText", wrap),
      generateBtn: T.q("#generateConvertJson", wrap),
      saveBtn: T.q("#saveConvertJson", wrap),

      progress: T.q("#convertProgress", wrap),
      progressBar: T.q("#convertProgressBar", wrap),
      progressLabel: T.q("#convertProgressLabel", wrap),

      cleanText: T.q("#cleanTextPreview", wrap),
      copyCleanText: T.q("#copyCleanText", wrap),
      downloadCleanText: T.q("#downloadCleanText", wrap),
      clearCleanText: T.q("#clearCleanText", wrap),
      searchCleanText: T.q("#searchCleanText", wrap),

      detectedQuestionMeta: T.q("#detectedQuestionMeta", wrap),
      detectedOptionMeta: T.q("#detectedOptionMeta", wrap),
      detectedGroupMeta: T.q("#detectedGroupMeta", wrap),
      detectedWarningMeta: T.q("#detectedWarningMeta", wrap),

      jsonPreview: T.q("#convertJsonPreview", wrap),
      jsonModalBody: T.q("#convertJsonModalBody", wrap),

      studentJsonPreview: T.q("#studentJsonPreview", wrap),
      studentJsonModalBody: T.q("#studentJsonModalBody", wrap),

      jsonSubjectMeta: T.q("#jsonSubjectMeta", wrap),
      jsonClassMeta: T.q("#jsonClassMeta", wrap),
      jsonCountMeta: T.q("#jsonCountMeta", wrap),

      validationMainText: T.q("#validationMainText", wrap),
      validationSubText: T.q("#validationSubText", wrap),

      validateBtn: T.q("#validateConvertJson", wrap),
      copyJSON: T.q("#copyConvertJson", wrap),
      downloadJSON: T.q("#downloadConvertJson", wrap),

      copyStudentJSON: T.q("#copyStudentJson", wrap),
      downloadStudentJSON: T.q("#downloadStudentJson", wrap),

      checkQuestionCount: T.q("#checkQuestionCount", wrap),
      checkOptions: T.q("#checkOptions", wrap),
      checkAnswers: T.q("#checkAnswers", wrap),
      checkGroups: T.q("#checkGroups", wrap),
      checkOpenAI: T.q("#checkOpenAI", wrap),

      rerunChecks: T.q("#rerunConvertChecks", wrap),

      aiStatusBadge: T.q("#aiStatusBadge", wrap),
      aiInputTokens: T.q("#aiInputTokens", wrap),
      aiOutputTokens: T.q("#aiOutputTokens", wrap),
      aiTotalTokens: T.q("#aiTotalTokens", wrap),
      aiCost: T.q("#aiCost", wrap),
      aiReviewCount: T.q("#aiReviewCount", wrap),

      answerReportTotal: T.q("#answerReportTotal", wrap),
      answerReportClean: T.q("#answerReportClean", wrap),
      answerReportReview: T.q("#answerReportReview", wrap),
      answerReviewBody: T.q("#answerReviewBody", wrap),

      logBody: T.q("#convertLogBody", wrap),
      clearLog: T.q("#clearConvertLog", wrap),

      guideBtn: T.q("#btnOpenConvertGuide", wrap),
      resetBtn: T.q("#btnResetConvertPage", wrap),

      guideModal: T.q("#convertGuideModal", wrap),
      jsonModal: T.q("#convertJsonModal", wrap),
      studentJsonModal: T.q("#studentJsonModal", wrap),

      openJsonModal: T.q("#openConvertJsonModal", wrap),
      openStudentJsonModal: T.q("#openStudentJsonModal", wrap),

      saveTargetModal: T.q("#convertSaveTargetModal", wrap),
      saveTargetYear: T.q("#saveTargetYear", wrap),
      saveTargetClass: T.q("#saveTargetClass", wrap),
      saveTargetSubject: T.q("#saveTargetSubject", wrap),

      saveTargetTerm:
        T.q("#saveTargetTerm", wrap) ||
        T.q("#convertSaveTargetTerm", wrap),

      saveTargetOverwrite: T.q("#saveTargetOverwrite", wrap),
      saveTargetPathPreview: T.q("#saveTargetPathPreview", wrap),
      confirmSaveTargetBtn: T.q("#confirmSaveTargetBtn", wrap),

      draftsBody: T.q("#convertDraftsBody", wrap),
      refreshDraftsBtn: T.q("#refreshConvertDrafts", wrap),
      clearDraftsBtn: T.q("#clearConvertDrafts", wrap),

      pipelineSteps: T.qa(".convert-pipeline-steps span", wrap),
      viewPills: T.qa("[data-convert-view]", wrap),
    };
  }


  /* ==========================================================
     FULL CONVERTER FILE EVENTS
  ========================================================== */

  function bindUpload(els, T) {
    els.chooseFile?.addEventListener(
      "click",
      () => els.fileInput?.click()
    );

    els.fileInput?.addEventListener("change", () => {
      const file = els.fileInput.files?.[0];

      if (file) setSelectedFile(file, els, T);
    });

    els.clearFile?.addEventListener("click", () => {
      state = getFreshState();

      if (els.fileInput) {
        els.fileInput.value = "";
      }

      refreshAllUI(
        els,
        T,
        window.EmisConvertExt
      );

      T.addLog(
        els.logBody,
        "Selected document cleared.",
        "warn"
      );
    });

    ["dragenter", "dragover"].forEach((eventName) => {
      els.dropZone?.addEventListener(eventName, (event) => {
        event.preventDefault();
        els.dropZone.classList.add("drag-over");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      els.dropZone?.addEventListener(eventName, (event) => {
        event.preventDefault();
        els.dropZone.classList.remove("drag-over");
      });
    });

    els.dropZone?.addEventListener("drop", (event) => {
      const file = event.dataTransfer.files?.[0];

      if (file) {
        setSelectedFile(file, els, T);
      }
    });
  }


  /* ==========================================================
     FULL CONVERTER ACTIONS
  ========================================================== */

  function bindActions(els, T, X) {
    els.extractBtn?.addEventListener(
      "click",
      () => extractCleanText(els, T, X)
    );

    els.generateBtn?.addEventListener(
      "click",
      () => generateJSON(els, T, X)
    );

    els.saveBtn?.addEventListener(
      "click",
      () => openSaveTargetModal(els, T)
    );

    els.confirmSaveTargetBtn?.addEventListener(
      "click",
      () => saveJSON(els, T, X)
    );


    ["change", "input"].forEach((eventName) => {
      els.saveTargetYear?.addEventListener(
        eventName,
        () => updateSaveTargetPathPreview(els, T)
      );

      els.saveTargetClass?.addEventListener(
        eventName,
        () => updateSaveTargetPathPreview(els, T)
      );

      els.saveTargetSubject?.addEventListener(
        eventName,
        () => updateSaveTargetPathPreview(els, T)
      );

      els.saveTargetTerm?.addEventListener(
        eventName,
        () => updateSaveTargetPathPreview(els, T)
      );
    });


    els.cleanText?.addEventListener("input", () => {
      state.cleanText = els.cleanText.value;
      updateDetectedStats(els, T);
    });


    els.copyCleanText?.addEventListener("click", async () => {
      await T.copyText(
        els.cleanText?.value || ""
      );

      T.flash(
        "Clean text copied.",
        "success"
      );
    });


    els.downloadCleanText?.addEventListener("click", () => {
      const name =
        `${T.filenameBase(state.file?.name || "clean_text")}.txt`;

      T.downloadText(
        name,
        els.cleanText?.value || "",
        "text/plain"
      );
    });


    els.clearCleanText?.addEventListener("click", () => {
      state.cleanText = "";

      if (els.cleanText) {
        els.cleanText.value = "";
      }

      updateDetectedStats(els, T);

      T.addLog(
        els.logBody,
        "Clean text cleared.",
        "warn"
      );
    });


    els.validateBtn?.addEventListener("click", () => {
      runValidation(els, T);

      T.flash(
        "JSON check completed.",
        "success"
      );
    });


    els.copyJSON?.addEventListener("click", async () => {
      await T.copyText(
        T.prettyJSON(state.generatedJSON)
      );

      T.flash(
        "JSON copied.",
        "success"
      );
    });


    els.downloadJSON?.addEventListener("click", () => {
      const subject =
        state.generatedJSON?.subject ||
        els.subject?.value ||
        "exam";

      const cls =
        state.generatedJSON?.class_category ||
        state.generatedJSON?.class ||
        els.classCategory?.value ||
        "class";

      const name =
        `${T.filenameBase(subject)}_${String(cls).toLowerCase()}.json`;

      T.downloadText(
        name,
        T.prettyJSON(state.generatedJSON),
        "application/json"
      );
    });


    els.copyStudentJSON?.addEventListener("click", async () => {
      await T.copyText(
        T.prettyJSON(
          state.studentJSON ||
          state.generatedJSON
        )
      );

      T.flash(
        "Student JSON copied.",
        "success"
      );
    });


    els.downloadStudentJSON?.addEventListener("click", () => {
      const data =
        state.studentJSON ||
        state.generatedJSON;

      const subject =
        data?.subject ||
        els.subject?.value ||
        "exam";

      const cls =
        data?.class ||
        data?.class_category ||
        els.classCategory?.value ||
        "class";

      const name =
        `${T.filenameBase(subject)}_${String(cls).toLowerCase()}_student.json`;

      T.downloadText(
        name,
        T.prettyJSON(data),
        "application/json"
      );
    });


    els.rerunChecks?.addEventListener("click", () => {
      runValidation(els, T);
      renderExtendedUI(els, T, X);

      T.addLog(
        els.logBody,
        "Quality checks re-run.",
        "success"
      );
    });


    els.clearLog?.addEventListener("click", () => {
      if (!els.logBody) return;

      els.logBody.innerHTML =
        `<p class="log-placeholder">No conversion actions yet.</p>`;
    });


    els.resetBtn?.addEventListener(
      "click",
      () => resetWorkspace(els, T, X)
    );


    els.searchCleanText?.addEventListener(
      "input",
      () => searchCleanText(els)
    );


    els.refreshDraftsBtn?.addEventListener(
      "click",
      () => loadDrafts(els, T, X)
    );


    els.clearDraftsBtn?.addEventListener("click", async () => {
      if (
        !confirm(
          "Clear all temporary converted JSON drafts?"
        )
      ) {
        return;
      }

      try {
        await T.fetchJSON(
          `${API.drafts}/clear`,
          {
            method: "DELETE"
          }
        );

        T.flash(
          "All temporary drafts cleared.",
          "success"
        );

        T.addLog(
          els.logBody,
          "All temporary converted JSON drafts were cleared.",
          "warn"
        );

        loadDrafts(els, T, X);

      } catch (error) {
        T.flash(
          error.message ||
          "Failed to clear drafts.",
          "error"
        );
      }
    });
  }


  /* ==========================================================
     MODAL EVENTS
  ========================================================== */

  function bindModals(els, T, X) {
    els.guideBtn?.addEventListener(
      "click",
      () => T.openModal(els.guideModal)
    );

    els.openJsonModal?.addEventListener("click", () => {
      if (els.jsonModalBody) {
        els.jsonModalBody.textContent =
          T.prettyJSON(state.generatedJSON);
      }

      T.openModal(els.jsonModal);
    });

    els.openStudentJsonModal?.addEventListener("click", () => {
      if (X && els.studentJsonModal) {
        X.renderStudentJSON(
          els,
          state.studentJSON ||
          state.generatedJSON
        );

        T.openModal(
          els.studentJsonModal
        );
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;

      T.closeModal(els.guideModal);
      T.closeModal(els.jsonModal);
      T.closeModal(els.studentJsonModal);
      T.closeModal(els.saveTargetModal);
    });
  }


  /* ==========================================================
     VIEW PILLS
  ========================================================== */

  function bindViewPills(els, T) {
    els.viewPills.forEach((pill) => {
      pill.addEventListener("click", () => {
        els.viewPills.forEach(
          (item) => item.classList.remove("active")
        );

        pill.classList.add("active");

        const view =
          pill.dataset.convertView;

        if (view === "text" && els.cleanText) {
          els.cleanText.value =
            state.cleanText || "";
        }

        if (view === "questions") {
          showQuestionsView(els, T);
        }

        if (view === "diagrams") {
          showDiagramsView(els);
        }

        if (view === "issues") {
          showIssuesView(els, T);
        }
      });
    });
  }


  /* ==========================================================
     FILE SELECTION
  ========================================================== */

  function setSelectedFile(file, els, T) {
    const allowed = [".docx", ".txt"];
    const lower = file.name.toLowerCase();

    if (
      !allowed.some(
        (extension) => lower.endsWith(extension)
      )
    ) {
      T.flash(
        "Only DOCX or TXT files are allowed.",
        "error"
      );

      return;
    }

    state = getFreshState();
    state.file = file;

    refreshAllUI(
      els,
      T,
      window.EmisConvertExt
    );

    setPipeline(
      els,
      0
    );

    T.flash(
      "Document selected.",
      "success"
    );

    T.addLog(
      els.logBody,
      `Selected ${file.name}.`,
      "success"
    );
  }


  /* ==========================================================
     EXTRACT CLEAN TEXT — FULL CONVERTER PAGE
  ========================================================== */

  async function extractCleanText(els, T, X) {
    if (!state.file) {
      T.flash(
        "Please choose a DOCX or TXT file first.",
        "warn"
      );

      return;
    }

    T.setBusy(
      els.extractBtn,
      true,
      "Extracting..."
    );

    T.setProgress(
      els.progress,
      els.progressBar,
      els.progressLabel,
      25,
      "Uploading document..."
    );

    setPipeline(
      els,
      1
    );

    try {
      const payload =
        await extractFile(
          state.file,
          {
            subject: els.subject?.value || "",
            class_category: els.classCategory?.value || "",
            expected_questions: els.expectedCount?.value || "50",
            objective_only: els.objectiveOnly?.checked !== false,
            extract_diagrams: els.extractDiagrams?.checked !== false,
            year: els.year?.value || "",
            term: els.term?.value || "",
          }
        );


      state.cleanText =
        payload.clean_text ||
        payload.text ||
        "";

      state.diagramMap =
        payload.diagram_map ||
        {};

      state.diagramCount =
        payload.diagram_count ||
        Object.keys(state.diagramMap).length ||
        0;

      state.detectedYear =
        payload.detected_year ||
        payload.year ||
        "";

      state.detectedTerm =
        normalizeTerm(
          payload.term ||
          payload.exam_term ||
          payload.academic_term
        ) || "";

      state.objectiveWarnings =
        payload.objective_warnings ||
        [];

      state.multipleObjectiveSeries =
        Boolean(
          payload.multiple_objective_series
        );

      state.seriesInfo =
        payload.series_info ||
        {};


      const detectedSubject =
        payload.subject || "";

      const detectedClass =
        payload.class_category ||
        payload.class_level ||
        "";


      if (
        detectedSubject &&
        detectedSubject !== "General" &&
        els.subject
      ) {
        els.subject.value =
          detectedSubject;
      }


      if (
        detectedClass &&
        els.classCategory
      ) {
        els.classCategory.value =
          detectedClass;
      }


      if (
        state.detectedTerm &&
        els.term
      ) {
        els.term.value =
          state.detectedTerm;
      }


      if (
        payload.expected_questions &&
        els.expectedCount
      ) {
        els.expectedCount.value =
          payload.expected_questions;
      }


      if (
        state.detectedYear &&
        els.year
      ) {
        const detectedYear =
          String(state.detectedYear);

        const hasOption =
          [...els.year.options].some(
            (option) =>
              option.value === detectedYear
          );

        if (hasOption) {
          els.year.value =
            detectedYear;
        }
      }


      if (els.cleanText) {
        els.cleanText.value =
          state.cleanText;
      }


      T.setProgress(
        els.progress,
        els.progressBar,
        els.progressLabel,
        100,
        "Clean text extracted."
      );


      T.flash(
        state.objectiveWarnings.length
          ? "Clean text extracted, but please review the warning(s)."
          : "Clean text extracted successfully.",
        state.objectiveWarnings.length
          ? "warn"
          : "success"
      );


      T.addLog(
        els.logBody,
        "Clean text extraction completed.",
        "success"
      );


      if (state.detectedYear) {
        T.addLog(
          els.logBody,
          `Detected exam year: ${state.detectedYear}.`,
          "success"
        );
      }


      if (
        detectedSubject &&
        detectedSubject !== "General"
      ) {
        T.addLog(
          els.logBody,
          `Detected subject: ${detectedSubject}.`,
          "success"
        );
      }


      if (detectedClass) {
        T.addLog(
          els.logBody,
          `Detected class: ${detectedClass}.`,
          "success"
        );
      }


      if (state.detectedTerm) {
        T.addLog(
          els.logBody,
          `Detected term: ${termLabel(state.detectedTerm)}.`,
          "success"
        );
      }


      state.objectiveWarnings.forEach(
        (warning) => {
          T.addLog(
            els.logBody,
            warning,
            "warn"
          );
        }
      );


      updateDetectedStats(
        els,
        T
      );

      refreshAllUI(
        els,
        T,
        X
      );

    } catch (error) {
      T.flash(
        error.message ||
        "Extraction failed.",
        "error"
      );

      T.addLog(
        els.logBody,
        error.message ||
        "Extraction failed.",
        "error"
      );

      T.setProgress(
        els.progress,
        els.progressBar,
        els.progressLabel,
        100,
        "Extraction failed."
      );

    } finally {
      T.setBusy(
        els.extractBtn,
        false
      );
    }
  }


  /* ==========================================================
     LOW-LEVEL FILE EXTRACTION
  ========================================================== */

  async function extractFile(file, options = {}) {
    const T = window.EmisConvertTools;

    if (!T) {
      throw new Error(
        "Converter helper library is unavailable."
      );
    }

    if (!(file instanceof File)) {
      throw new Error(
        "Invalid document supplied."
      );
    }

    const lower =
      String(file.name || "")
        .toLowerCase();

    if (
      !lower.endsWith(".docx") &&
      !lower.endsWith(".txt")
    ) {
      throw new Error(
        `Unsupported file: ${file.name}`
      );
    }


    const form =
      new FormData();

    form.append(
      "file",
      file
    );

    form.append(
      "subject",
      options.subject || ""
    );

    form.append(
      "class_category",
      options.class_category || ""
    );

    form.append(
      "expected_questions",
      String(
        options.expected_questions ||
        50
      )
    );

    form.append(
      "objective_only",
      options.objective_only === false
        ? "0"
        : "1"
    );

    form.append(
      "extract_diagrams",
      options.extract_diagrams === false
        ? "0"
        : "1"
    );


    if (options.year) {
      form.append(
        "year",
        options.year
      );
    }


    if (options.term) {
      form.append(
        "term",
        options.term
      );
    }


    return await T.fetchJSON(
      API.extract,
      {
        method: "POST",
        body: form,
      }
    );
  }


  /* ==========================================================
     GENERATE CBT JSON — FULL CONVERTER PAGE
  ========================================================== */

  async function generateJSON(els, T, X) {
    const clean =
      els.cleanText?.value.trim() ||
      "";

    if (!clean) {
      T.flash(
        "Extract or paste clean text first.",
        "warn"
      );

      return;
    }


    T.setBusy(
      els.generateBtn,
      true,
      "Generating..."
    );

    T.setProgress(
      els.progress,
      els.progressBar,
      els.progressLabel,
      35,
      "Generating CBT JSON..."
    );

    setPipeline(
      els,
      2
    );


    try {
      const body = {
        clean_text: clean,

        subject:
          els.subject?.value ||
          "",

        class_category:
          els.classCategory?.value ||
          "",

        expected_questions:
          Number(
            els.expectedCount?.value ||
            50
          ),

        diagram_map:
          state.diagramMap ||
          {},

        use_llm:
          els.strictJson?.checked
            ? true
            : false,

        solve_answers: true,

        year:
          els.year?.value ||
          state.detectedYear ||
          "",

        term:
          normalizeTerm(
            els.term?.value ||
            state.detectedTerm
          ) || null,

        source_filename:
          state.file?.name ||
          "",
      };


      const payload =
        await generateFromCleanText(
          body
        );


      applyGeneratedPayload(
        payload,
        body
      );


      const backendSubject =
        payload.subject ||
        state.generatedJSON?.subject ||
        state.studentJSON?.subject ||
        body.subject ||
        "";


      const backendClass =
        payload.class_category ||
        state.generatedJSON?.class_category ||
        state.generatedJSON?.class ||
        state.studentJSON?.class_category ||
        state.studentJSON?.class ||
        body.class_category ||
        "";


      const backendTerm =
        normalizeTerm(
          payload.term ||
          state.generatedJSON?.term ||
          state.studentJSON?.term ||
          body.term
        );


      if (
        backendSubject &&
        els.subject
      ) {
        els.subject.value =
          backendSubject;
      }


      if (
        backendClass &&
        els.classCategory
      ) {
        els.classCategory.value =
          backendClass;
      }


      if (
        backendTerm &&
        els.term
      ) {
        els.term.value =
          backendTerm;
      }


      if (state.generatedJSON) {
        if (backendSubject) {
          state.generatedJSON.subject =
            backendSubject;
        }

        if (backendClass) {
          state.generatedJSON.class_category =
            backendClass;
        }

        if (
          backendTerm &&
          isTermAwareClass(backendClass)
        ) {
          state.generatedJSON.term =
            backendTerm;

          state.generatedJSON.term_label =
            termLabel(backendTerm);
        }
      }


      if (state.studentJSON) {
        if (backendSubject) {
          state.studentJSON.subject =
            backendSubject;
        }

        if (backendClass) {
          state.studentJSON.class_category =
            backendClass;
        }

        if (
          backendTerm &&
          isTermAwareClass(backendClass)
        ) {
          state.studentJSON.term =
            backendTerm;

          state.studentJSON.term_label =
            termLabel(backendTerm);
        }
      }


      state.detectedTerm =
        backendTerm ||
        state.detectedTerm ||
        "";


      state.validation =
        payload.validation ||
        T.validateExamJSON(
          state.generatedJSON,
          body.expected_questions
        );


      T.setProgress(
        els.progress,
        els.progressBar,
        els.progressLabel,
        100,
        "JSON generated."
      );


      T.flash(
        state.needsReview
          ? `CBT JSON generated. ${state.needsReview} answer(s) may need review.`
          : "CBT JSON generated successfully.",
        state.needsReview
          ? "warn"
          : "success"
      );


      T.addLog(
        els.logBody,
        state.needsReview
          ? `Generated CBT JSON with ${state.needsReview} review flag(s).`
          : "Generated CBT JSON successfully.",
        state.needsReview
          ? "warn"
          : "success"
      );


      if (backendSubject) {
        T.addLog(
          els.logBody,
          `Detected subject: ${backendSubject}.`,
          "success"
        );
      }


      if (backendClass) {
        T.addLog(
          els.logBody,
          `Detected class: ${backendClass}.`,
          "success"
        );
      }


      if (
        backendTerm &&
        isTermAwareClass(backendClass)
      ) {
        T.addLog(
          els.logBody,
          `Detected term: ${termLabel(backendTerm)}.`,
          "success"
        );
      }


      if (state.draft?.draft_id) {
        T.addLog(
          els.logBody,
          `Temporary draft saved: ${
            state.draft.subject ||
            backendSubject ||
            "Subject"
          } ${
            state.draft.class_category ||
            backendClass ||
            ""
          }.`,
          "success"
        );
      }


      if (!backendClass) {
        T.addLog(
          els.logBody,
          "Class was not detected. Please select the class before saving.",
          "warn"
        );

        T.flash(
          "Class was not detected. Please select the class before saving.",
          "warn"
        );
      }


      if (
        isTermAwareClass(backendClass) &&
        !backendTerm
      ) {
        T.addLog(
          els.logBody,
          `${backendClass} requires a term before saving.`,
          "warn"
        );
      }


      setPipeline(
        els,
        3
      );

      renderJSON(
        els,
        T
      );

      runValidation(
        els,
        T
      );

      renderExtendedUI(
        els,
        T,
        X
      );

      refreshAllUI(
        els,
        T,
        X
      );

      loadDrafts(
        els,
        T,
        X
      );

    } catch (error) {
      T.flash(
        error.message ||
        "JSON generation failed.",
        "error"
      );

      T.addLog(
        els.logBody,
        error.message ||
        "JSON generation failed.",
        "error"
      );

      T.setProgress(
        els.progress,
        els.progressBar,
        els.progressLabel,
        100,
        "Generation failed."
      );

    } finally {
      T.setBusy(
        els.generateBtn,
        false
      );
    }
  }


  /* ==========================================================
     GENERATE FROM CLEAN TEXT — REUSABLE
  ========================================================== */

  async function generateFromCleanText(body) {
    const T =
      window.EmisConvertTools;

    if (!T) {
      throw new Error(
        "Converter helper library is unavailable."
      );
    }


    return await T.fetchJSON(
      API.generate,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify(body),
      }
    );
  }


  /* ==========================================================
     APPLY GENERATED API RESPONSE TO STATE
  ========================================================== */

  function applyGeneratedPayload(payload, body = {}) {
    state.rawPayload =
      payload;

    state.fullJSON =
      payload.full_json ||
      null;

    state.draft =
      payload.draft ||
      null;


    state.generatedJSON =
      payload.student_json ||
      payload.json ||
      payload.data ||
      payload.exam ||
      payload;


    state.studentJSON =
      payload.student_json ||
      payload.json ||
      null;


    state.answerReport =
      payload.answer_report ||
      [];


    state.openaiUsage =
      payload.openai_usage ||
      payload.usage ||
      {};


    state.needsReview =
      Number(
        payload.needs_review ||
        0
      );


    state.detectedTerm =
      normalizeTerm(
        payload.term ||
        state.generatedJSON?.term ||
        body.term
      ) ||
      state.detectedTerm ||
      "";
  }


  /* ==========================================================
     SAVE TARGET MODAL
  ========================================================== */

  function openSaveTargetModal(els, T) {
    if (!state.generatedJSON) {
      T.flash(
        "Generate JSON first or load a draft first.",
        "warn"
      );

      return;
    }


    buildSaveYearOptions(
      els
    );


    const detectedClass =
      els.classCategory?.value ||
      state.generatedJSON?.class_category ||
      state.generatedJSON?.class ||
      "";


    const detectedSubject =
      els.subject?.value ||
      state.generatedJSON?.subject ||
      "";


    const detectedTerm =
      normalizeTerm(
        els.term?.value ||
        state.generatedJSON?.term ||
        state.detectedTerm
      );


    if (els.saveTargetYear) {
      els.saveTargetYear.value =
        els.year?.value ||
        state.detectedYear ||
        String(
          new Date().getFullYear()
        );
    }


    if (els.saveTargetClass) {
      els.saveTargetClass.value =
        detectedClass;
    }


    if (els.saveTargetSubject) {
      els.saveTargetSubject.value =
        detectedSubject;
    }


    if (
      els.saveTargetTerm &&
      detectedTerm
    ) {
      els.saveTargetTerm.value =
        detectedTerm;
    }


    updateSaveTargetPathPreview(
      els,
      T
    );

    T.openModal(
      els.saveTargetModal
    );
  }


  function buildSaveYearOptions(els) {
    if (
      !els.saveTargetYear ||
      els.saveTargetYear.options.length
    ) {
      return;
    }


    const sourceOptions =
      [...(els.year?.options || [])];


    if (sourceOptions.length) {
      sourceOptions.forEach((source) => {
        const option =
          document.createElement(
            "option"
          );

        option.value =
          source.value;

        option.textContent =
          source.textContent;

        els.saveTargetYear.appendChild(
          option
        );
      });

      return;
    }


    const currentYear =
      new Date().getFullYear();


    for (
      let year = currentYear;
      year >= 2013;
      year--
    ) {
      const option =
        document.createElement(
          "option"
        );

      option.value =
        String(year);

      option.textContent =
        String(year);

      els.saveTargetYear.appendChild(
        option
      );
    }
  }


  function updateSaveTargetPathPreview(els, T) {
    const year =
      els.saveTargetYear?.value ||
      "YEAR";

    const cls =
      els.saveTargetClass?.value ||
      "CLASS";

    const subject =
      els.saveTargetSubject?.value ||
      "subject";

    const term =
      normalizeTerm(
        els.saveTargetTerm?.value ||
        els.term?.value ||
        state.generatedJSON?.term ||
        state.detectedTerm
      );


    const filename =
      `${T.filenameBase(subject)}_${String(cls).toLowerCase()}.json`;


    let path =
      `static/subjects/${year}/subjects-json/${cls}`;


    if (
      isTermAwareClass(cls) &&
      term
    ) {
      path +=
        `/${term}`;
    }


    path +=
      `/${filename}`;


    T.text(
      els.saveTargetPathPreview,
      path
    );
  }


  /* ==========================================================
     SAVE JSON — FULL CONVERTER PAGE
  ========================================================== */

  async function saveJSON(els, T, X) {
    if (!state.generatedJSON) {
      T.flash(
        "Generate JSON first or load a draft first.",
        "warn"
      );

      return;
    }


    const finalClass =
      els.saveTargetClass?.value ||
      els.classCategory?.value ||
      state.generatedJSON.class_category ||
      "";


    const finalSubject =
      els.saveTargetSubject?.value ||
      els.subject?.value ||
      state.generatedJSON.subject ||
      "";


    const finalYear =
      els.saveTargetYear?.value ||
      els.year?.value ||
      state.detectedYear ||
      new Date().getFullYear();


    const finalTerm =
      normalizeTerm(
        els.saveTargetTerm?.value ||
        els.term?.value ||
        state.generatedJSON?.term ||
        state.detectedTerm
      );


    if (!finalClass) {
      T.flash(
        "Please select the class folder before saving.",
        "warn"
      );

      T.addLog(
        els.logBody,
        "Save stopped: class folder was not selected.",
        "warn"
      );

      return;
    }


    if (!finalSubject) {
      T.flash(
        "Please enter the subject before saving.",
        "warn"
      );

      T.addLog(
        els.logBody,
        "Save stopped: subject was not provided.",
        "warn"
      );

      return;
    }


    if (
      isTermAwareClass(finalClass) &&
      !finalTerm
    ) {
      T.flash(
        `${normalizeClass(finalClass)} requires a term before saving.`,
        "warn"
      );

      T.addLog(
        els.logBody,
        `Save stopped: ${normalizeClass(finalClass)} term is missing.`,
        "warn"
      );

      return;
    }


    enforceExamMetadata(
      state.generatedJSON,
      finalSubject,
      finalClass,
      finalTerm
    );


    if (state.studentJSON) {
      enforceExamMetadata(
        state.studentJSON,
        finalSubject,
        finalClass,
        finalTerm
      );
    }


    T.setBusy(
      els.saveBtn,
      true,
      "Saving..."
    );

    T.setBusy(
      els.confirmSaveTargetBtn,
      true,
      "Saving..."
    );

    T.setProgress(
      els.progress,
      els.progressBar,
      els.progressLabel,
      50,
      "Saving JSON to library..."
    );

    setPipeline(
      els,
      4
    );


    try {
      const payload =
        await saveGeneratedExam({
          year: finalYear,
          detected_year:
            state.detectedYear || "",

          subject: finalSubject,
          class_category: finalClass,
          term: finalTerm,

          json:
            state.generatedJSON,

          student_json:
            state.studentJSON ||
            null,

          full_json:
            state.fullJSON ||
            null,

          answer_report:
            state.answerReport ||
            [],

          openai_usage:
            state.openaiUsage ||
            {},

          needs_review:
            state.needsReview ||
            0,

          source_filename:
            state.file?.name ||
            "",

          overwrite:
            els.saveTargetOverwrite?.value !== "0",
        });


      T.setProgress(
        els.progress,
        els.progressBar,
        els.progressLabel,
        100,
        "JSON saved."
      );


      T.flash(
        `Saved ${payload.filename || "JSON file"} successfully.`,
        "success"
      );


      T.addLog(
        els.logBody,
        `Saved JSON to library: ${payload.filename || "completed"}.`,
        "success"
      );


      if (payload.year) {
        T.addLog(
          els.logBody,
          `Saved year: ${payload.year}.`,
          "success"
        );
      }


      if (payload.class_category) {
        T.addLog(
          els.logBody,
          `Saved class: ${payload.class_category}.`,
          "success"
        );
      }


      if (payload.term) {
        T.addLog(
          els.logBody,
          `Saved term: ${termLabel(payload.term)}.`,
          "success"
        );
      }


      if (payload.path) {
        T.addLog(
          els.logBody,
          `Saved path: ${payload.path}`,
          "success"
        );
      }


      if (payload.review_path) {
        T.addLog(
          els.logBody,
          "Answer review report also saved.",
          "success"
        );
      }


      T.closeModal(
        els.saveTargetModal
      );

      renderJSON(
        els,
        T
      );

      runValidation(
        els,
        T
      );

      renderExtendedUI(
        els,
        T,
        X
      );

      loadDrafts(
        els,
        T,
        X
      );

    } catch (error) {
      T.flash(
        error.message ||
        "Save failed.",
        "error"
      );

      T.addLog(
        els.logBody,
        error.message ||
        "Save failed.",
        "error"
      );

      T.setProgress(
        els.progress,
        els.progressBar,
        els.progressLabel,
        100,
        "Save failed."
      );

    } finally {
      T.setBusy(
        els.saveBtn,
        false
      );

      T.setBusy(
        els.confirmSaveTargetBtn,
        false
      );
    }
  }


  /* ==========================================================
     SAVE GENERATED EXAM — REUSABLE
  ========================================================== */

  async function saveGeneratedExam(body) {
    const T =
      window.EmisConvertTools;

    if (!T) {
      throw new Error(
        "Converter helper library is unavailable."
      );
    }


    return await T.fetchJSON(
      API.save,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify(body),
      }
    );
  }


  /* ==========================================================
     ENFORCE FINAL JSON METADATA
  ========================================================== */

  function enforceExamMetadata(
    data,
    subject,
    classCategory,
    term = null
  ) {
    if (
      !data ||
      typeof data !== "object"
    ) {
      return;
    }


    data.subject =
      subject;

    data.class_category =
      classCategory;


    if (
      isTermAwareClass(classCategory)
    ) {
      const normalized =
        normalizeTerm(term);

      if (normalized) {
        data.term =
          normalized;

        data.term_label =
          termLabel(normalized);
      }

    } else {
      delete data.term;
      delete data.term_label;
    }
  }


  /* ==========================================================
     REUSABLE QUICK CONVERSION
     Used directly by uploads.html
  ========================================================== */

  async function convertFileToLibrary(file, options = {}) {
    const T =
      window.EmisConvertTools;

    if (!T) {
      throw new Error(
        "EmisConvertTools is unavailable."
      );
    }


    if (!(file instanceof File)) {
      throw new Error(
        "A valid DOCX file was not supplied."
      );
    }


    const filename =
      String(
        file.name ||
        ""
      );


    const lower =
      filename.toLowerCase();


    if (
      !lower.endsWith(".docx") &&
      !lower.endsWith(".txt")
    ) {
      throw new Error(
        `Unsupported file: ${filename}`
      );
    }


    const requestedYear =
      String(
        options.year ||
        ""
      ).trim();


    const requestedClass =
      String(
        options.class_category ||
        options.classCategory ||
        ""
      ).trim();


    const requestedSubject =
      String(
        options.subject ||
        ""
      ).trim();


    const requestedTerm =
      normalizeTerm(
        options.term
      );


    const expectedQuestions =
      Number(
        options.expected_questions ||
        options.expectedQuestions ||
        50
      );


    const objectiveOnly =
      options.objective_only !== false;


    const extractDiagrams =
      options.extract_diagrams !== false;


    const useLLM =
      options.use_llm !== false;


    const solveAnswers =
      options.solve_answers !== false;


    const overwrite =
      options.overwrite !== false;


    const onProgress =
      typeof options.onProgress === "function"
        ? options.onProgress
        : () => {};


    /* --------------------------------------------------------
       STEP 1 — EXTRACT
    -------------------------------------------------------- */

    onProgress({
      stage: "extract",
      percent: 15,
      message: `Reading ${filename}...`,
    });


    const extracted =
      await extractFile(
        file,
        {
          year:
            requestedYear,

          subject:
            requestedSubject,

          class_category:
            requestedClass,

          term:
            requestedTerm,

          expected_questions:
            expectedQuestions,

          objective_only:
            objectiveOnly,

          extract_diagrams:
            extractDiagrams,
        }
      );


    const cleanText =
      String(
        extracted.clean_text ||
        extracted.text ||
        ""
      ).trim();


    if (!cleanText) {
      throw new Error(
        `No readable exam text was extracted from ${filename}.`
      );
    }


    /* --------------------------------------------------------
       DETECT EXTRACTION METADATA
    -------------------------------------------------------- */

    const extractedSubject =
      String(
        extracted.subject ||
        requestedSubject ||
        ""
      ).trim();


    const extractedClass =
      String(
        extracted.class_category ||
        extracted.class_level ||
        extracted.class ||
        requestedClass ||
        ""
      ).trim();


    const extractedYear =
      String(
        extracted.detected_year ||
        extracted.year ||
        requestedYear ||
        ""
      ).trim();


    const extractedTerm =
      normalizeTerm(
        extracted.term ||
        extracted.exam_term ||
        extracted.academic_term ||
        requestedTerm
      );


    const diagramMap =
      extracted.diagram_map ||
      {};


    /* --------------------------------------------------------
       STEP 2 — GENERATE + SOLVE ANSWERS
    -------------------------------------------------------- */

    onProgress({
      stage: "generate",
      percent: 45,
      message: `Generating CBT JSON for ${filename}...`,
    });


    const generateBody = {
      clean_text:
        cleanText,

      subject:
        extractedSubject,

      class_category:
        extractedClass,

      expected_questions:
        Number(
          extracted.expected_questions ||
          expectedQuestions
        ),

      diagram_map:
        diagramMap,

      use_llm:
        useLLM,

      solve_answers:
        solveAnswers,

      year:
        extractedYear,

      detected_year:
        extractedYear,

      term:
        extractedTerm,

      source_filename:
        filename,
    };


    const generated =
      await generateFromCleanText(
        generateBody
      );


    const generatedJSON =
      generated.student_json ||
      generated.json ||
      generated.data ||
      generated.exam ||
      (
        Array.isArray(generated.questions)
          ? generated
          : null
      );


    if (
      !generatedJSON ||
      typeof generatedJSON !== "object"
    ) {
      throw new Error(
        `JSON generation failed for ${filename}.`
      );
    }


    const studentJSON =
      generated.student_json ||
      generated.json ||
      generatedJSON;


    /* --------------------------------------------------------
       FINAL METADATA
    -------------------------------------------------------- */

    const finalSubject =
      String(
        generated.subject ||
        generatedJSON.subject ||
        extractedSubject ||
        ""
      ).trim();


    const finalClass =
      String(
        generated.class_category ||
        generatedJSON.class_category ||
        generatedJSON.class ||
        extractedClass ||
        ""
      ).trim();


    const finalYear =
      String(
        requestedYear ||
        generated.year ||
        generated.detected_year ||
        extractedYear ||
        generated.draft?.year ||
        ""
      ).trim();


    const finalTerm =
      normalizeTerm(
        generated.term ||
        generated.exam_term ||
        generatedJSON.term ||
        generatedJSON.exam_term ||
        extractedTerm
      );


    if (!finalYear) {
      throw new Error(
        `Exam year could not be detected for ${filename}. Select a year before converting.`
      );
    }


    if (!finalClass) {
      throw new Error(
        `Class could not be detected for ${filename}.`
      );
    }


    if (!finalSubject) {
      throw new Error(
        `Subject could not be detected for ${filename}.`
      );
    }


    if (
      isTermAwareClass(finalClass) &&
      !finalTerm
    ) {
      throw new Error(
        `${normalizeClass(finalClass)} term could not be detected for ${filename}.`
      );
    }


    enforceExamMetadata(
      generatedJSON,
      finalSubject,
      finalClass,
      finalTerm
    );


    if (
      studentJSON &&
      typeof studentJSON === "object"
    ) {
      enforceExamMetadata(
        studentJSON,
        finalSubject,
        finalClass,
        finalTerm
      );
    }


    /* --------------------------------------------------------
       STEP 3 — SAVE
    -------------------------------------------------------- */

    onProgress({
      stage: "save",
      percent: 80,
      message: `Saving ${finalSubject}...`,
    });


    const saveBody = {
      year:
        finalYear,

      detected_year:
        generated.detected_year ||
        extracted.detected_year ||
        finalYear,

      subject:
        finalSubject,

      class_category:
        finalClass,

      term:
        finalTerm,

      json:
        generatedJSON,

      student_json:
        studentJSON,

      full_json:
        generated.full_json ||
        null,

      answer_report:
        generated.answer_report ||
        [],

      openai_usage:
        generated.openai_usage ||
        generated.usage ||
        {},

      needs_review:
        Number(
          generated.needs_review ||
          0
        ),

      source_filename:
        filename,

      overwrite,
    };


    const saved =
      await saveGeneratedExam(
        saveBody
      );


    onProgress({
      stage: "complete",
      percent: 100,
      message: `${finalSubject} converted successfully.`,
    });


    return {
      success: true,

      source_filename:
        filename,

      filename:
        saved.filename ||
        generated.filename ||
        "",

      year:
        String(
          saved.year ||
          finalYear
        ),

      subject:
        saved.subject ||
        finalSubject,

      class_category:
        saved.class_category ||
        finalClass,

      term:
        normalizeTerm(
          saved.term ||
          finalTerm
        ),

      term_label:
        saved.term_label ||
        (
          finalTerm
            ? termLabel(finalTerm)
            : "—"
        ),

      questions:
        Array.isArray(
          generatedJSON.questions
        )
          ? generatedJSON.questions.length
          : 0,

      needs_review:
        Number(
          generated.needs_review ||
          0
        ),

      openai_usage:
        generated.openai_usage ||
        generated.usage ||
        {},

      generated_json:
        generatedJSON,

      student_json:
        studentJSON,

      extracted,
      generated,
      saved,
    };
  }


  /* ==========================================================
     UPLOAD PAGE QUICK-CONVERT BRIDGE
     Directly connects #startUpload to converter engine.
  ========================================================== */

  function initUploadBridge(root = document) {
    const uploadsRoot =
      root.querySelector(
        ".uploads-wrapper"
      );

    if (!uploadsRoot) return;


    const startButton =
      uploadsRoot.querySelector(
        "#startUpload"
      );


    if (
      !startButton ||
      startButton.__emisConvertBridgeBound__
    ) {
      return;
    }


    startButton.__emisConvertBridgeBound__ =
      true;


    const progressWrap =
      uploadsRoot.querySelector(
        "#uploadProgress"
      );

    const progressBar =
      uploadsRoot.querySelector(
        "#uploadProgressBar"
      );

    const progressLabel =
      uploadsRoot.querySelector(
        "#uploadProgressLabel"
      );


    const yearSelector =
      uploadsRoot.querySelector(
        "#yearSelectorUploads"
      );


    const inputSingle =
      uploadsRoot.querySelector(
        "#uploadInputSingle"
      );

    const inputMulti =
      uploadsRoot.querySelector(
        "#uploadInputMulti"
      );


    function showMessage(
      message,
      type = "success"
    ) {
      if (
        typeof window.flashMessage ===
        "function"
      ) {
        window.flashMessage(
          message,
          type
        );

        return;
      }


      if (
        window.EmisConvertTools?.flash
      ) {
        window.EmisConvertTools.flash(
          message,
          type
        );

        return;
      }


      alert(message);
    }


    function setProgress(
      percent,
      message
    ) {
      const safe =
        Math.max(
          0,
          Math.min(
            100,
            Number(percent || 0)
          )
        );


      if (progressWrap) {
        progressWrap.classList.remove(
          "hidden"
        );
      }


      if (progressBar) {
        progressBar.style.width =
          `${safe}%`;
      }


      if (progressLabel) {
        progressLabel.textContent =
          message ||
          "Processing...";
      }
    }


    function hideProgress() {
      setTimeout(
        () => {
          progressWrap?.classList.add(
            "hidden"
          );

          if (progressBar) {
            progressBar.style.width =
              "0%";
          }
        },
        1000
      );
    }


    function getUploadFiles() {
      /*
       * Primary source:
       * The DOCX picker patch in uploads.js exposes this.
       */
      const externalFiles =
        window.EmisDocxUpload?.files;


      if (
        externalFiles &&
        externalFiles.length
      ) {
        return [...externalFiles];
      }


      /*
       * Fallback for single/multiple native inputs.
       */
      const combined = [
        ...(inputSingle?.files || []),
        ...(inputMulti?.files || []),
      ];


      const unique =
        new Map();


      combined.forEach((file) => {
        const key =
          `${file.name}|${file.size}|${file.lastModified}`;

        unique.set(
          key,
          file
        );
      });


      return [
        ...unique.values()
      ];
    }


    function getSelectedYear() {
      const year =
        String(
          yearSelector?.value ||
          window.EmisUploads?.activeYear ||
          ""
        ).trim();


      if (
        !year ||
        year === "Select Year" ||
        year === "Year"
      ) {
        return "";
      }


      return year;
    }


    function setBusy(
      busy,
      message = "Converting..."
    ) {
      if (busy) {
        if (
          !startButton.dataset.originalHtml
        ) {
          startButton.dataset.originalHtml =
            startButton.innerHTML;
        }


        startButton.disabled =
          true;


        startButton.innerHTML = `
          <i class="fa-solid fa-spinner fa-spin"></i>
          ${message}
        `;

        return;
      }


      startButton.disabled =
        false;


      startButton.innerHTML =
        startButton.dataset.originalHtml ||
        `
          <i class="fa-solid fa-wand-magic-sparkles"></i>
          Convert
        `;
    }


    async function refreshLibrary(year) {
      if (!yearSelector || !year) {
        return;
      }


      const hasOption =
        [...yearSelector.options].some(
          (option) =>
            String(option.value) ===
            String(year)
        );


      if (hasOption) {
        yearSelector.value =
          String(year);
      }


      yearSelector.dispatchEvent(
        new Event(
          "change",
          {
            bubbles: true
          }
        )
      );
    }


    startButton.addEventListener(
      "click",
      async (event) => {
        event.preventDefault();
        event.stopPropagation();


        const files =
          getUploadFiles();


        if (!files.length) {
          showMessage(
            "Select at least one DOCX file first.",
            "error"
          );

          return;
        }


        const invalid =
          files.find(
            (file) =>
              !String(file.name || "")
                .toLowerCase()
                .endsWith(".docx")
          );


        if (invalid) {
          showMessage(
            "Only DOCX files can be converted from this page.",
            "error"
          );

          return;
        }


        const selectedYear =
          getSelectedYear();


        const successList = [];
        const failureList = [];


        setBusy(
          true,
          files.length > 1
            ? `Converting 1/${files.length}`
            : "Converting..."
        );


        setProgress(
          2,
          `Preparing ${files.length} document${files.length === 1 ? "" : "s"}...`
        );


        try {
          for (
            let index = 0;
            index < files.length;
            index++
          ) {
            const file =
              files[index];

            const number =
              index + 1;


            setBusy(
              true,
              files.length > 1
                ? `Converting ${number}/${files.length}`
                : "Converting..."
            );


            try {
              const result =
                await convertFileToLibrary(
                  file,
                  {
                    year:
                      selectedYear,

                    expected_questions:
                      50,

                    objective_only:
                      true,

                    extract_diagrams:
                      true,

                    use_llm:
                      true,

                    solve_answers:
                      true,

                    overwrite:
                      true,


                    onProgress(info) {
                      const filePercent =
                        Number(
                          info.percent ||
                          0
                        );


                      const before =
                        index /
                        files.length;


                      const current =
                        (
                          filePercent /
                          100
                        ) /
                        files.length;


                      const total =
                        Math.round(
                          (
                            before +
                            current
                          ) *
                          100
                        );


                      setProgress(
                        total,

                        files.length > 1
                          ? `${number}/${files.length} • ${info.message || file.name}`
                          : info.message ||
                            file.name
                      );
                    }
                  }
                );


              successList.push(
                result
              );


            } catch (error) {
              console.error(
                `Conversion failed: ${file.name}`,
                error
              );


              failureList.push({
                filename:
                  file.name,

                error:
                  error.message ||
                  "Conversion failed",
              });
            }
          }


          /* --------------------------------------------------
             RESULT
          -------------------------------------------------- */

          if (successList.length) {
            const finalYear =
              successList[
                successList.length - 1
              ]?.year ||
              selectedYear;


            setProgress(
              100,

              failureList.length
                ? `${successList.length} converted, ${failureList.length} failed.`
                : `${successList.length} converted successfully.`
            );


            showMessage(
              failureList.length
                ? `${successList.length} converted successfully; ${failureList.length} failed.`
                : `${successList.length} exam${successList.length === 1 ? "" : "s"} converted and saved successfully.`,
              failureList.length
                ? "warn"
                : "success"
            );


            await refreshLibrary(
              finalYear
            );
          }


          if (
            !successList.length &&
            failureList.length
          ) {
            setProgress(
              100,
              "Conversion failed."
            );


            showMessage(
              failureList[0].error ||
              "Conversion failed.",
              "error"
            );
          }


          if (failureList.length) {
            console.table(
              failureList
            );
          }


          /*
           * Clear source queue only when every file succeeded.
           */
          if (
            successList.length &&
            !failureList.length
          ) {
            if (
              window.EmisDocxUpload?.clear
            ) {
              window.EmisDocxUpload.clear();

            } else {
              if (inputSingle) {
                inputSingle.value = "";
              }

              if (inputMulti) {
                inputMulti.value = "";
              }
            }
          }


        } finally {
          setBusy(
            false
          );

          hideProgress();
        }
      }
    );
  }


  /* ==========================================================
     TEMPORARY DRAFTS
  ========================================================== */

  async function loadDrafts(els, T, X) {
    if (!els.draftsBody) return;


    try {
      els.draftsBody.innerHTML =
        `<p class="log-placeholder">Loading recent converted JSON drafts...</p>`;


      const payload =
        await T.fetchJSON(
          API.drafts
        );


      renderDrafts(
        els,
        T,
        X,
        payload.drafts || []
      );


    } catch (error) {
      els.draftsBody.innerHTML =
        `<p class="log-placeholder">Unable to load drafts.</p>`;


      T.addLog(
        els.logBody,
        error.message ||
        "Unable to load drafts.",
        "error"
      );
    }
  }


  function renderDrafts(els, T, X, drafts) {
    if (!els.draftsBody) return;


    if (!drafts.length) {
      els.draftsBody.innerHTML = `
        <div class="convert-empty-drafts">
          <i class="fa-solid fa-folder-open"></i>
          <strong>No saved drafts yet</strong>
          <span>Generated JSON drafts will appear here automatically after conversion.</span>
        </div>
      `;

      return;
    }


    els.draftsBody.innerHTML =
      drafts.map((draft) => {
        const cost =
          draft.openai_usage
            ?.estimated_cost_usd ||
          0;


        const term =
          normalizeTerm(
            draft.term
          );


        return `
          <article
            class="convert-draft-card"
            data-draft-id="${escapeHTML(draft.draft_id || "")}"
          >
            <div class="convert-draft-icon">
              <i class="fa-solid fa-file-code"></i>
            </div>

            <div class="convert-draft-main">
              <strong>
                ${escapeHTML(draft.subject || "Subject")}
                ${escapeHTML(draft.class_category || "")}
              </strong>

              <span>
                ${escapeHTML(draft.year || "—")}
                ${term ? ` • ${escapeHTML(termLabel(term))}` : ""}
                • ${Number(draft.question_count || 0)} questions
                • Review: ${Number(draft.needs_review || 0)}
              </span>

              <small>
                ${escapeHTML(draft.source_filename || "Converted JSON")}
                • ${escapeHTML(draft.created_at || "")}
              </small>

              <small>
                OpenAI cost: $${escapeHTML(cost)}
              </small>
            </div>

            <div class="convert-draft-actions">
              <button
                class="btn-primary small"
                data-draft-action="load"
              >
                <i class="fa-solid fa-folder-open"></i>
                Load
              </button>

              <button
                class="btn-danger small"
                data-draft-action="delete"
              >
                <i class="fa-solid fa-trash"></i>
                Delete
              </button>
            </div>
          </article>
        `;
      }).join("");


    els.draftsBody
      .querySelectorAll(
        "[data-draft-action='load']"
      )
      .forEach((button) => {
        button.addEventListener(
          "click",
          () => {
            const card =
              button.closest(
                "[data-draft-id]"
              );

            loadSingleDraft(
              card?.dataset?.draftId,
              els,
              T,
              X
            );
          }
        );
      });


    els.draftsBody
      .querySelectorAll(
        "[data-draft-action='delete']"
      )
      .forEach((button) => {
        button.addEventListener(
          "click",
          () => {
            const card =
              button.closest(
                "[data-draft-id]"
              );

            deleteSingleDraft(
              card?.dataset?.draftId,
              els,
              T,
              X
            );
          }
        );
      });
  }


  async function loadSingleDraft(
    draftId,
    els,
    T,
    X
  ) {
    if (!draftId) return;


    try {
      const payload =
        await T.fetchJSON(
          `${API.drafts}/${draftId}`
        );


      const draft =
        payload.draft ||
        {};


      state.generatedJSON =
        draft.student_json ||
        draft.json ||
        null;


      state.studentJSON =
        draft.student_json ||
        draft.json ||
        null;


      state.fullJSON =
        draft.full_json ||
        null;


      state.answerReport =
        draft.answer_report ||
        [];


      state.openaiUsage =
        draft.openai_usage ||
        {};


      state.needsReview =
        Number(
          draft.needs_review ||
          0
        );


      state.draft =
        draft;


      state.detectedYear =
        draft.year ||
        state.detectedYear ||
        "";


      state.detectedTerm =
        normalizeTerm(
          draft.term
        ) ||
        state.detectedTerm ||
        "";


      if (
        els.year &&
        draft.year
      ) {
        const hasOption =
          [...els.year.options].some(
            (option) =>
              option.value ===
              String(draft.year)
          );


        if (hasOption) {
          els.year.value =
            String(draft.year);
        }
      }


      if (
        els.classCategory &&
        draft.class_category
      ) {
        els.classCategory.value =
          draft.class_category;
      }


      if (
        els.subject &&
        draft.subject
      ) {
        els.subject.value =
          draft.subject;
      }


      if (
        els.term &&
        state.detectedTerm
      ) {
        els.term.value =
          state.detectedTerm;
      }


      renderJSON(
        els,
        T
      );

      runValidation(
        els,
        T
      );

      renderExtendedUI(
        els,
        T,
        X
      );

      refreshAllUI(
        els,
        T,
        X
      );


      T.flash(
        "Draft loaded. You can now save it to the library.",
        "success"
      );


      T.addLog(
        els.logBody,
        `Loaded temporary draft: ${draft.subject || "Subject"} ${draft.class_category || ""}.`,
        "success"
      );


      window.scrollTo({
        top: 0,
        behavior: "smooth"
      });


    } catch (error) {
      T.flash(
        error.message ||
        "Failed to load draft.",
        "error"
      );
    }
  }


  async function deleteSingleDraft(
    draftId,
    els,
    T,
    X
  ) {
    if (!draftId) return;


    if (
      !confirm(
        "Delete this temporary draft?"
      )
    ) {
      return;
    }


    try {
      await T.fetchJSON(
        `${API.drafts}/${draftId}`,
        {
          method: "DELETE"
        }
      );


      T.flash(
        "Draft deleted.",
        "success"
      );


      T.addLog(
        els.logBody,
        "Temporary draft deleted.",
        "warn"
      );


      loadDrafts(
        els,
        T,
        X
      );


    } catch (error) {
      T.flash(
        error.message ||
        "Failed to delete draft.",
        "error"
      );
    }
  }


  /* ==========================================================
     JSON RENDERING
  ========================================================== */

  function renderJSON(els, T) {
    const pretty =
      state.generatedJSON
        ? T.prettyJSON(
            state.generatedJSON
          )
        : "No JSON generated yet.";


    if (els.jsonPreview) {
      els.jsonPreview.textContent =
        pretty;
    }


    if (els.jsonModalBody) {
      els.jsonModalBody.textContent =
        pretty;
    }


    const subject =
      state.generatedJSON?.subject ||
      "—";


    const cls =
      state.generatedJSON?.class_category ||
      state.generatedJSON?.class ||
      "—";


    const count =
      state.generatedJSON
        ?.questions
        ?.length ||
      0;


    T.text(
      els.jsonSubjectMeta,
      `Subject: ${subject}`
    );


    T.text(
      els.jsonClassMeta,
      `Class: ${cls}`
    );


    T.text(
      els.jsonCountMeta,
      `Questions: ${count}`
    );
  }


  function renderExtendedUI(els, T, X) {
    if (!X) return;


    X.renderUsage?.(
      els,
      {
        openai_usage:
          state.openaiUsage,

        needs_review:
          state.needsReview,
      }
    );


    X.renderAnswerReport?.(
      els,
      state.answerReport
    );


    X.renderStudentJSON?.(
      els,
      state.studentJSON ||
      state.generatedJSON
    );
  }


  /* ==========================================================
     VALIDATION
  ========================================================== */

  function runValidation(els, T) {
    const expected =
      Number(
        els.expectedCount?.value ||
        0
      );


    state.validation =
      T.validateExamJSON(
        state.generatedJSON,
        expected
      );


    const valid =
      state.validation.valid;


    const warnings =
      state.validation.warnings
        ?.length ||
      0;


    const issues =
      state.validation.issues
        ?.length ||
      0;


    const missingAnswers =
      state.validation
        .missing_answers ||
      0;


    T.text(
      els.validationStatus,
      valid
        ? "Ready"
        : "Needs Check"
    );


    T.text(
      els.validationMainText,
      valid
        ? "Ready to Save"
        : "Needs Check"
    );


    T.text(
      els.validationSubText,
      valid
        ? "JSON is ready for the library."
        : `${issues} issue(s), ${warnings} warning(s), ${missingAnswers} missing answer(s).`
    );


    T.text(
      els.detectedGroupMeta,
      state.validation.group_count ||
      0
    );


    T.text(
      els.detectedWarningMeta,
      warnings +
      issues +
      Number(
        state.needsReview ||
        0
      )
    );


    updateCheckCard(
      els.checkQuestionCount,

      expected &&
      state.validation.question_count !==
        expected
        ? "warn"
        : "success",

      "Question Count",

      expected
        ? `${state.validation.question_count} of ${expected} detected`
        : `${state.validation.question_count} detected`
    );


    updateCheckCard(
      els.checkOptions,
      issues
        ? "error"
        : "success",
      "Options",
      issues
        ? "Some questions need checking"
        : "Options look good"
    );


    updateCheckCard(
      els.checkAnswers,
      missingAnswers
        ? "warn"
        : "success",
      "Answers",
      missingAnswers
        ? `${missingAnswers} missing answer(s)`
        : "Answers available"
    );


    updateCheckCard(
      els.checkGroups,
      state.validation.group_count
        ? "success"
        : "warn",
      "Groups & Diagrams",
      state.validation.group_count
        ? `${state.validation.group_count} group(s) detected`
        : "Default group only"
    );


    updateCheckCard(
      els.checkOpenAI,

      state.needsReview
        ? "warn"
        : state.openaiUsage?.total_tokens
          ? "success"
          : "pending",

      "Answer Review",

      state.openaiUsage?.total_tokens
        ? state.needsReview
          ? `${state.needsReview} answer(s) may need review`
          : "Answers generated"
        : "Waiting for generation"
    );


    if (els.saveBtn) {
      els.saveBtn.disabled =
        !state.generatedJSON ||
        !valid;
    }
  }


  function updateCheckCard(
    card,
    status,
    title,
    description
  ) {
    if (!card) return;


    card.classList.remove(
      "pending",
      "success",
      "warn",
      "error"
    );


    card.classList.add(
      status
    );


    const strong =
      card.querySelector(
        "strong"
      );


    const span =
      card.querySelector(
        "span"
      );


    if (strong) {
      strong.textContent =
        title;
    }


    if (span) {
      span.textContent =
        description;
    }
  }


  /* ==========================================================
     DETECTED STATS
  ========================================================== */

  function updateDetectedStats(els, T) {
    const clean =
      els.cleanText?.value ||
      state.cleanText ||
      "";


    const questions =
      T.estimateQuestions(
        clean
      );


    const options =
      T.estimateOptions(
        clean
      );


    T.text(
      els.questionCount,
      questions
    );


    T.text(
      els.detectedQuestionMeta,
      questions
    );


    T.text(
      els.detectedOptionMeta,
      options
    );


    T.text(
      els.diagramCount,
      state.diagramCount ||
      0
    );
  }


  /* ==========================================================
     REFRESH FULL CONVERTER UI
  ========================================================== */

  function refreshAllUI(els, T, X) {
    T.text(
      els.selectedFile,
      state.file?.name ||
      "—"
    );


    T.text(
      els.fileBadge,
      state.file
        ? "1 file"
        : "No file"
    );


    T.text(
      els.diagramCount,
      state.diagramCount ||
      0
    );


    if (els.fileList) {
      els.fileList.innerHTML =
        state.file
          ? `
            <li>
              <i class="fa-solid fa-file-word"></i>
              ${escapeHTML(state.file.name)}
            </li>
          `
          : `
            <li class="empty-file">
              No document selected.
            </li>
          `;
    }


    if (
      !state.generatedJSON &&
      els.jsonPreview
    ) {
      els.jsonPreview.textContent =
        "No JSON generated yet.";
    }


    if (
      els.saveBtn &&
      !state.generatedJSON
    ) {
      els.saveBtn.disabled =
        true;
    }


    updateDetectedStats(
      els,
      T
    );


    renderJSON(
      els,
      T
    );


    renderExtendedUI(
      els,
      T,
      X
    );
  }


  /* ==========================================================
     PIPELINE
  ========================================================== */

  function setPipeline(
    els,
    activeIndex
  ) {
    els.pipelineSteps?.forEach(
      (step, index) => {
        step.classList.toggle(
          "active",
          index <= activeIndex
        );
      }
    );
  }


  /* ==========================================================
     RESET
  ========================================================== */

  function resetWorkspace(els, T, X) {
    state =
      getFreshState();


    if (els.fileInput) {
      els.fileInput.value = "";
    }


    if (els.cleanText) {
      els.cleanText.value = "";
    }


    if (els.subject) {
      els.subject.value = "";
    }


    if (els.classCategory) {
      els.classCategory.value = "";
    }


    if (els.term) {
      els.term.value = "";
    }


    if (els.expectedCount) {
      els.expectedCount.value =
        50;
    }


    if (els.strictJson) {
      els.strictJson.checked =
        true;
    }


    if (els.objectiveOnly) {
      els.objectiveOnly.checked =
        true;
    }


    if (els.extractDiagrams) {
      els.extractDiagrams.checked =
        true;
    }


    T.closeModal(
      els.saveTargetModal
    );


    setPipeline(
      els,
      0
    );


    refreshAllUI(
      els,
      T,
      X
    );


    T.text(
      els.validationStatus,
      "Not Ready"
    );


    T.text(
      els.validationMainText,
      "Waiting"
    );


    T.text(
      els.validationSubText,
      "Generate JSON first."
    );


    [
      els.checkQuestionCount,
      els.checkOptions,
      els.checkAnswers,
      els.checkGroups,
      els.checkOpenAI,
    ].forEach((card) => {
      if (!card) return;

      card.classList.remove(
        "success",
        "warn",
        "error"
      );

      card.classList.add(
        "pending"
      );
    });


    T.text(
      els.answerReportTotal,
      "0"
    );


    T.text(
      els.answerReportClean,
      "0"
    );


    T.text(
      els.answerReportReview,
      "0"
    );


    T.addLog(
      els.logBody,
      "Workspace reset.",
      "warn"
    );
  }


  /* ==========================================================
     TEXT SEARCH
  ========================================================== */

  function searchCleanText(els) {
    const search =
      (
        els.searchCleanText?.value ||
        ""
      )
        .trim()
        .toLowerCase();


    const clean =
      state.cleanText ||
      els.cleanText?.value ||
      "";


    if (!search) {
      if (els.cleanText) {
        els.cleanText.value =
          clean;
      }

      return;
    }


    const lines =
      clean.split("\n");


    const filtered =
      lines.filter(
        (line) =>
          line.toLowerCase()
            .includes(search)
      );


    if (els.cleanText) {
      els.cleanText.value =
        filtered.join("\n");
    }
  }


  /* ==========================================================
     QUESTIONS VIEW
  ========================================================== */

  function showQuestionsView(els) {
    if (
      !state.generatedJSON
        ?.questions
        ?.length
    ) {
      window.EmisConvertTools.flash(
        "Generate JSON first or load a draft first.",
        "warn"
      );

      return;
    }


    const lines =
      state.generatedJSON.questions.map(
        (question) => {
          return [
            `${question.id}. ${question.question}`,
            ...(question.options || []),
            `Answer: ${question.correctOption || "Not set"}`,
          ].join("\n");
        }
      );


    if (els.cleanText) {
      els.cleanText.value =
        lines.join("\n\n");
    }
  }


  /* ==========================================================
     DIAGRAM VIEW
  ========================================================== */

  function showDiagramsView(els) {
    const entries =
      Object.entries(
        state.diagramMap ||
        {}
      );


    if (!entries.length) {
      if (els.cleanText) {
        els.cleanText.value =
          "No diagrams extracted yet.";
      }

      return;
    }


    if (els.cleanText) {
      els.cleanText.value =
        entries
          .map(
            ([key, value]) =>
              `Diagram ${key}: ${value}`
          )
          .join("\n");
    }
  }


  /* ==========================================================
     ISSUES VIEW
  ========================================================== */

  function showIssuesView(els, T) {
    runValidation(
      els,
      T
    );


    const issues =
      state.validation?.issues ||
      [];


    const warnings =
      state.validation?.warnings ||
      [];


    const objectiveWarnings =
      state.objectiveWarnings ||
      [];


    const output = [
      "ISSUES:",

      issues.length
        ? issues
            .map(
              (item) =>
                `- ${item}`
            )
            .join("\n")
        : "- No blocking issues.",

      "",

      "WARNINGS:",

      warnings.length ||
      objectiveWarnings.length
        ? [
            ...warnings,
            ...objectiveWarnings,
          ]
            .map(
              (item) =>
                `- ${item}`
            )
            .join("\n")
        : "- No warnings.",

      "",

      "ANSWER REVIEW:",

      state.needsReview
        ? `- ${state.needsReview} answer(s) may need review.`
        : "- No review flags.",
    ].join("\n");


    if (els.cleanText) {
      els.cleanText.value =
        output;
    }
  }


  /* ==========================================================
     ESCAPE HTML
  ========================================================== */

  function escapeHTML(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }


  /* ==========================================================
     PUBLIC API
  ========================================================== */

  return {
    initOnce,
    initUploadBridge,

    convertFileToLibrary,

    extractFile,
    generateFromCleanText,
    saveGeneratedExam,

    normalizeClass,
    normalizeTerm,
    termLabel,
    isTermAwareClass,

    getState() {
      return state;
    },
  };

})();


/* ============================================================
   INITIALIZE
============================================================ */

function initEmisConvert() {
  if (
    window.EmisConvert?.initOnce
  ) {
    window.EmisConvert.initOnce(
      document
    );
  }


  if (
    window.EmisConvert?.initUploadBridge
  ) {
    window.EmisConvert.initUploadBridge(
      document
    );
  }
}


if (
  document.readyState === "loading"
) {
  document.addEventListener(
    "DOMContentLoaded",
    initEmisConvert
  );

} else {
  initEmisConvert();
}


/* ============================================================
   SPA / DYNAMIC PAGE SUPPORT
============================================================ */

new MutationObserver(() => {
  window.EmisConvert?.initOnce?.(
    document
  );

  window.EmisConvert?.initUploadBridge?.(
    document
  );
}).observe(
  document.body,
  {
    childList: true,
    subtree: true,
  }
);
// ======================================================
// exam-core.js — EMIS CBT ENGINE v13
// Class-arm aware + full subject resolver
// ======================================================

console.log("[exam-core] EMIS CBT ENGINE v13 LOADED");

window.examData = null;
window.currentQuestionIndex = 0;
window.userAnswers = {};
window.lockedQuestions = new Set();
window.flaggedQuestions = new Set();
window.examTimer = null;
window.timeRemaining = 0;
window.initialTimeAllowed = 0;
window.examStarted = false;
window.examStartTime = null;
window.__examFinished = false;
window.__timeExpired = false;
window.__reviewBlocked = false;
window.realQuestionIndices = [];
window.sectionInstructions = {};

const SS_KEY = "emis_exam_progress";
const LS_RELOADS = "emis_exam_reload_count";
const LS_EXAM_LOCK = "emis_exam_lock_active";

let __warn20Shown = false;
let __warn10Shown = false;
let __warn5Shown = false;

function $(s, r = document) {
  return r.querySelector(s);
}

function $$(s, r = document) {
  return [...r.querySelectorAll(s)];
}

function formatTime(sec) {
  const safe = Math.max(0, sec | 0);
  const m = Math.floor(safe / 60).toString().padStart(2, "0");
  const s = (safe % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function examFlash(message, type = "info") {
  let flashEl =
    document.getElementById("examFlashMessage") ||
    document.getElementById("examFlash") ||
    document.getElementById("flashMessage");

  if (!flashEl) {
    flashEl = document.createElement("div");
    flashEl.id = "examFlash";
    flashEl.className = "exam-flash";
    flashEl.setAttribute("aria-hidden", "true");
    document.body.appendChild(flashEl);
  }

  flashEl.textContent = message;

  flashEl.classList.remove(
    "exam-flash-info",
    "exam-flash-success",
    "exam-flash-warning",
    "exam-flash-danger",
    "show"
  );

  flashEl.classList.add(`exam-flash-${type}`, "show");
  flashEl.style.pointerEvents = "none";

  setTimeout(() => {
    flashEl.classList.remove("show");
  }, 2600);
}

function parseInstructionText(text) {
  if (!text) return null;

  const lines = String(text).split(/\r?\n+/);
  let title = (lines[0] || "").trim();
  title = title.replace(/\s*[:：]\s*$/, "");

  const body = lines.slice(1).join(" ").trim();

  return { title, body, raw: text };
}

function getCorrectIndex(q) {
  if (typeof q.correctIndex === "number") return q.correctIndex;

  const raw =
    q.correctOption ||
    q.correct_option ||
    q.answer ||
    q.correctAnswer ||
    q.correct_answer ||
    "";

  if (!raw) return -1;

  const cleaned = String(raw).trim().toUpperCase();

  if (/^[A-D]$/.test(cleaned)) {
    return cleaned.charCodeAt(0) - 65;
  }

  const optionIndex = Number(cleaned);
  if (!Number.isNaN(optionIndex)) {
    if (optionIndex >= 0 && optionIndex <= 3) return optionIndex;
    if (optionIndex >= 1 && optionIndex <= 4) return optionIndex - 1;
  }

  return -1;
}

/* ======================================================
   FULL EMIS SUBJECT RESOLVER
====================================================== */

function normalizeSubjectKey(subject) {
  let value = String(subject || "").toUpperCase().trim();

  value = value.replace(/\./g, "");
  value = value.replace(/&/g, "AND");
  value = value.replace(/[_\-\/]+/g, " ");
  value = value.replace(/\s+/g, " ").trim();

  const aliases = {
    MATHS: "MATHEMATICS",
    MATH: "MATHEMATICS",
    MATHEMATICS: "MATHEMATICS",

    ENGLISH: "ENGLISH LANGUAGE",
    "ENGLISH LANGUAGE": "ENGLISH LANGUAGE",

    CHEMISTRY: "CHEMISTRY",
    PHYSICS: "PHYSICS",
    BIOLOGY: "BIOLOGY",

    "TECHNICAL": "TECHNICAL DRAWING",
    "TECHNICAL DRAWING": "TECHNICAL DRAWING",

    IRK: "IRS",
    IRS: "IRS",

    ISLAMIYAH: "ISLAMIYYAH",
    ISLAMIYYA: "ISLAMIYYAH",
    ISLAMIYYAH: "ISLAMIYYAH",

    "COMPUTER": "COMPUTER SCIENCE",
    "COMPUTER STUDIES": "COMPUTER SCIENCE",
    "COMPUTER SCIENCE": "COMPUTER SCIENCE",

    "FURTHER MATHS": "FURTHER MATHEMATICS",
    "FURTHER MATHEMATICS": "FURTHER MATHEMATICS",

    AGRICULTURE: "AGRICULTURAL SCIENCE",
    "AGRICULTURAL SCIENCE": "AGRICULTURAL SCIENCE",

    CIVIC: "CIVIC EDUCATION",
    "CIVIC EDUCATION": "CIVIC EDUCATION",

    GEOGRAPHY: "GEOGRAPHY",
    ECONOMICS: "ECONOMICS",
    POISE: "POISE",

    LITERATURE: "LITERATURE",
    "LITERATURE IN ENGLISH": "LITERATURE",
    "LITERATURE-IN-ENGLISH": "LITERATURE",

    GOVERNMENT: "GOVERNMENT",

    HAUSA: "HAUSA LANGUAGE",
    "HAUSA LANGUAGE": "HAUSA LANGUAGE",

    YORUBA: "YORUBA LANGUAGE",
    "YORUBA LANGUAGE": "YORUBA LANGUAGE",

    ARABIC: "ARABIC LANGUAGE",
    "ARABIC LANGUAGE": "ARABIC LANGUAGE",

    MARKETTING: "MARKETING",
    MARKETING: "MARKETING",

    COMMERCE: "COMMERCE",

    ACCOUNT: "FINANCIAL ACCOUNT",
    ACCOUNTS: "FINANCIAL ACCOUNT",
    ACCOUNTING: "FINANCIAL ACCOUNT",
    "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNT",
    "FINANCIAL ACCOUNT": "FINANCIAL ACCOUNT",

    "HERITAGE AND CITIZENSHIP STUDIES": "CIT AND HER STD",
    "HERITAGE CITIZENSHIP STUDIES": "CIT AND HER STD",
    "CITIZENSHIP AND HERITAGE STUDIES": "CIT AND HER STD",
    "CIT AND HER STD": "CIT AND HER STD",
    "CIT HER STD": "CIT AND HER STD",

    "SOC AND CIT STD": "SOC AND CIT STD",
    "SOCIAL AND CITIZENSHIP STUDIES": "SOC AND CIT STD",

    "NATIONAL VALUE": "NATIONAL VALUE",
    "NATIONAL VALUES": "NATIONAL VALUE",

    CCA: "CCA",
    "BUSINESS STUDIES": "BUSINESS STUDIES",
    HISTORY: "HISTORY",

    BST: "BST",

    PHE: "PHE",
    "P H E": "PHE",
    "PHYSICAL HEALTH EDUCATION": "PHE",

    PVS: "PVS",

    "HORTICULTURE AND CROP PRODUCTION": "HORT AND CROP PRODUCTION",
    "HORT AND CROP PRODUCTION": "HORT AND CROP PRODUCTION",
    "HORT CROP PRODUCTION": "HORT AND CROP PRODUCTION",

    "DIGITAL TECH": "DIGITAL TECH",
    "DIGITAL TECHNOLOGY": "DIGITAL TECH",

    "INTER SCIENCE": "INTER SCIENCE",
    "INTEGRATED SCIENCE": "INTER SCIENCE",

    "GARMENT MAKING": "GARMENT MAKING"
  };

  return aliases[value] || value;
}

function subjectKeyToFileBase(subject) {
  const key = normalizeSubjectKey(subject);

  const map = {
    "MATHEMATICS": "mathematics",
    "ENGLISH LANGUAGE": "english",
    "CHEMISTRY": "chemistry",
    "PHYSICS": "physics",
    "BIOLOGY": "biology",
    "TECHNICAL DRAWING": "technical",

    "IRS": "irs",
    "ISLAMIYYAH": "islamiyyah",

    "COMPUTER SCIENCE": "computer_science",
    "FURTHER MATHEMATICS": "further_mathematics",
    "AGRICULTURAL SCIENCE": "agricultural_science",

    "CIVIC EDUCATION": "civic",
    "GEOGRAPHY": "geography",
    "ECONOMICS": "economics",

    "POISE": "poise",

    "LITERATURE": "literature",
    "GOVERNMENT": "government",

    "HAUSA LANGUAGE": "hausa",
    "YORUBA LANGUAGE": "yoruba",
    "ARABIC LANGUAGE": "arabic",

    "MARKETING": "marketing",
    "COMMERCE": "commerce",
    "FINANCIAL ACCOUNT": "accounts",

    "CIT AND HER STD": "cit_her_std",
    "SOC AND CIT STD": "soc_cit_std",

    "NATIONAL VALUE": "national_value",
    "CCA": "cca",
    "BUSINESS STUDIES": "business_studies",
    "HISTORY": "history",

    "BST": "bst",
    "PHE": "phe",
    "PVS": "pvs",

    "HORT AND CROP PRODUCTION": "hort_crop_production",
    "DIGITAL TECH": "digital_tech",
    "INTER SCIENCE": "inter_science",
    "GARMENT MAKING": "garment_making"
  };

  return (
    map[key] ||
    key.toLowerCase()
      .replace(/&/g, "and")
      .replace(/\./g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
  );
}

function getMetaContent(...names) {
  for (const name of names) {
    const meta = document.querySelector(`meta[name="${name}"]`);
    if (meta && meta.content) return meta.content.trim();
  }
  return "";
}

function normalizeClassLevel(value) {
  const raw = String(value || "").toUpperCase().trim().replace(/-/g, "_");
  const compact = raw.replace(/[\s_]/g, "");

  for (const level of ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]) {
    if (compact === level || compact.startsWith(level)) return level;
  }

  return "";
}

function getExamClassLevel(classCategory = "") {
  return (
    normalizeClassLevel(getMetaContent("student-class-level")) ||
    normalizeClassLevel(getMetaContent("student-class-category")) ||
    normalizeClassLevel(classCategory) ||
    normalizeClassLevel(getMetaContent("student-class")) ||
    ""
  );
}

function getExamYear() {
  return (
    getMetaContent("exam-year") ||
    String(new Date().getFullYear())
  );
}

function uniqueArray(items) {
  return [...new Set(items.filter(Boolean))];
}

function buildExamJSONCandidates(subject, classCategory) {
  const year = getExamYear();
  const classLevel = getExamClassLevel(classCategory);
  const clsLower = classLevel.toLowerCase();

  const primary = subjectKeyToFileBase(subject);

  const fallbacks = {
    accounts: [
      "accounts",
      "account",
      "accounting",
      "financial_account",
      "financial_accounting"
    ],
    english: ["english", "english_language"],
    mathematics: ["mathematics", "maths"],
    civic: ["civic", "civic_education"],
    computer_science: ["computer_science", "computer_studies", "computer"],
    technical: ["technical", "technical_drawing"],
    irs: ["irs", "irk"],
    islamiyyah: ["islamiyyah", "islamiyah", "islamiyya"],
    literature: ["literature", "literature_in_english"],
    agricultural_science: ["agricultural_science", "agriculture"],
    further_mathematics: ["further_mathematics", "further_maths"],
    digital_tech: ["digital_tech", "digital_technology"],
    hort_crop_production: [
      "hort_crop_production",
      "hort_and_crop_production",
      "horticulture_and_crop_production"
    ],
    soc_cit_std: [
      "soc_cit_std",
      "soc_and_cit_std",
      "social_and_citizenship_studies"
    ],
    cit_her_std: [
      "cit_her_std",
      "cit_and_her_std",
      "heritage_citizenship_studies",
      "heritage_and_citizenship_studies",
      "hcs"
    ],
    phe: ["phe", "p_h_e"],
    national_value: ["national_value", "national_values"],
    inter_science: ["inter_science", "integrated_science"],
    garment_making: ["garment_making"],
    business_studies: ["business_studies"]
  };

  const bases = uniqueArray([
    primary,
    ...(fallbacks[primary] || [])
  ]);

  return bases.map((base) => {
    return `/static/subjects/${year}/subjects-json/${classLevel}/${base}_${clsLower}.json`;
  });
}

function resolveExamJSON(subject, classCategory) {
  return buildExamJSONCandidates(subject, classCategory)[0];
}

async function fetchFirstWorkingJSON(urls) {
  const errors = [];

  for (const url of urls) {
    try {
      console.log("📥 Trying Exam JSON:", url);

      const res = await fetch(url, { cache: "no-store" });

      if (!res.ok) {
        errors.push(`${url} → ${res.status}`);
        continue;
      }

      const data = await res.json();

      return {
        url,
        data
      };

    } catch (err) {
      errors.push(`${url} → ${err.message}`);
    }
  }

  const error = new Error("Exam JSON not found");
  error.tried = errors;
  throw error;
}

/* ======================================================
   LOAD EXAM DATA
====================================================== */

window.loadExamData = async function (quiet = false) {
  try {
    const subjectMeta = $('meta[name="exam-subject"]');
    const classMeta =
      $('meta[name="student-class-level"]') ||
      $('meta[name="student-class-category"]') ||
      $('meta[name="student-class"]');

    if (!subjectMeta || !classMeta) {
      throw new Error("Missing subject/class metadata.");
    }

    const subject = subjectMeta.content;
    const classCategory = classMeta.content;
    const candidates = buildExamJSONCandidates(subject, classCategory);

    const loaded = await fetchFirstWorkingJSON(candidates);
    let rawData = loaded.data;

    console.log("✅ Exam JSON loaded:", loaded.url);

    rawData.questions = (rawData.questions || []).map((q, idx) => {
      return {
        id: q.id ?? idx,
        question: q.question || "",
        options: q.options || [],
        diagram: q.diagram || null,
        passage: q.passage || null,
        isInstruction: !!q.isInstruction,
        correctIndex: getCorrectIndex(q)
      };
    });

    window.examData =
      typeof shuffleQuestions === "function"
        ? shuffleQuestions(rawData)
        : rawData;

    window.realQuestionIndices = [];

    window.examData.questions.forEach((q, i) => {
      const hasOptions =
        Array.isArray(q.options) &&
        q.options.some((opt) => opt && opt.toString().trim() !== "");

      if (!q.isInstruction && hasOptions) {
        window.realQuestionIndices.push(i);
      }
    });

    window.sectionInstructions = {};
    let currentSectionMeta = null;

    window.examData.questions.forEach((q, i) => {
      if (q.isInstruction) {
        currentSectionMeta = parseInstructionText(q.question);
        return;
      }

      if (!q.isInstruction && currentSectionMeta) {
        window.sectionInstructions[i] = currentSectionMeta;
      }
    });

    const totalReal = window.realQuestionIndices.length;

    if (!totalReal) {
      throw new Error("No valid questions found in JSON.");
    }

    const st = $("#examSubjectTitle");
    if (st) {
      st.innerHTML = `
        <span class="exam-subject-pill">${String(subject).toUpperCase()}</span>
        <span class="exam-question-count">• ${totalReal} QUESTION${totalReal === 1 ? "" : "S"}</span>
      `;
      st.classList.remove("hidden");
    }

    const totalQEl = $("#totalQuestions");
    if (totalQEl) totalQEl.textContent = totalReal;

    window.timeRemaining = (rawData.time_allowed_minutes || 60) * 60;
    window.initialTimeAllowed = window.timeRemaining;

    __warn20Shown = false;
    __warn10Shown = false;
    __warn5Shown = false;

    const td = $("#timerDisplay");
    if (td) td.textContent = formatTime(window.timeRemaining);

    loadQuestion(window.realQuestionIndices[0]);
    updateProgress();
    updateQuestionNavigation();

  } catch (err) {
    console.error("❌ loadExamData error:", err);

    if (err.tried) {
      console.table(err.tried);
    }

    const message =
      "Unable to load exam JSON. Please contact admin. " +
      "Check that the pushed subject file exists for this exam year and class level.";

    examFlash(message, "danger");

    if (!quiet) {
      console.error(message);
    }

    throw err;
  }
};





/* ======================================================
   PROGRESS
====================================================== */

window.updateProgress = function () {
  const total = window.realQuestionIndices.length;
  const answered = window.realQuestionIndices.filter((i) => !!window.userAnswers[i]).length;
  const pct = total ? (answered / total) * 100 : 0;

  const answeredEl = $("#answeredCount");
  const remainingEl = $("#remainingCount");
  const progressBar = $("#progressBar");
  const progressText = $("#progressText");

  if (answeredEl) answeredEl.textContent = answered;
  if (remainingEl) remainingEl.textContent = total - answered;
  if (progressBar) progressBar.style.width = `${pct}%`;
  if (progressText) progressText.textContent = `${Math.round(pct)}% Complete`;
};

/* ======================================================
   NAVIGATION BUTTONS
====================================================== */

window.updateNavigationButtons = function () {
  const prev = $("#prevBtn");
  const next = $("#nextBtn");

  if (!window.realQuestionIndices || window.realQuestionIndices.length === 0) return;

  const firstRealIndex = window.realQuestionIndices[0];
  const lastRealIndex = window.realQuestionIndices[window.realQuestionIndices.length - 1];

  if (prev) {
    prev.disabled = window.currentQuestionIndex === firstRealIndex;
  }

  if (next) {
    const isLast = window.currentQuestionIndex === lastRealIndex;
    next.textContent = isLast ? "Submit" : "Next →";
  }
};

window.updateQuestionNavigation = function () {
  const grid = $("#questionGrid");
  if (!grid || !window.examData) return;

  let html = "";

  window.realQuestionIndices.forEach((trueIndex, pos) => {
    const active = trueIndex === window.currentQuestionIndex ? "active" : "";
    const answered = window.userAnswers[trueIndex] ? "answered" : "";
    const flagged = window.flaggedQuestions.has(trueIndex) ? "flagged" : "";

    html += `
      <button class="question-nav-btn ${active} ${answered} ${flagged}" data-q-index="${trueIndex}">
        ${pos + 1}
      </button>
    `;
  });

  grid.innerHTML = html;

  $$(".question-nav-btn", grid).forEach((btn) => {
    btn.onclick = () => loadQuestion(Number(btn.dataset.qIndex));
  });
};

/* ======================================================
   END EXAM MODAL
====================================================== */

window.endExam = function () {
  if (!window.examData) return;

  const total = window.realQuestionIndices.length;
  const answered = window.realQuestionIndices.filter((i) => !!window.userAnswers[i]).length;

  const msgEl = $("#endExamMessage");
  if (msgEl) {
    msgEl.innerHTML = `
      You answered <b>${answered}</b> out of <b>${total}</b>.<br>
      Unanswered questions will be marked incorrect.<br><br>
      Are you sure you want to end this exam?
    `;
  }

  const modal = $("#endExamModal");
  if (modal) modal.classList.remove("hidden");
};

window.closeEndExam = function () {
  const modal = $("#endExamModal");
  if (modal) modal.classList.add("hidden");
};

/* ======================================================
   SUBMIT EXAM
====================================================== */

window.submitExam = async function (timeUp = false) {
  if (window.__examFinished) return;
  window.__examFinished = true;

  if (window.examTimer) clearInterval(window.examTimer);

  const realIndices = window.realQuestionIndices;
  const total = realIndices.length;

  let correct = 0;

  realIndices.forEach((trueIndex) => {
    const q = window.examData.questions[trueIndex];
    const ua = window.userAnswers[trueIndex];

    if (ua && ua.index === q.correctIndex) {
      correct++;
    }
  });

  const answered = realIndices.filter((i) => !!window.userAnswers[i]).length;
  const incorrect = total - correct;
  const skipped = total - answered;
  const rawScore = correct;

  const flaggedQuestionsDetailed = [...window.flaggedQuestions].map((i) => {
    const q = window.examData.questions[i] || {};
    return {
      index: i,
      question_id: q.id,
      question: q.question
    };
  });

  const subjectMeta = $('meta[name="exam-subject"]');
  const yearMeta = $('meta[name="exam-year"]');

  const payload = {
    subject: subjectMeta ? subjectMeta.content.trim().toUpperCase() : "",
    score: rawScore,
    correct,
    incorrect,
    total,
    answered,
    skipped,
    flagged: flaggedQuestionsDetailed.length,
    flagged_questions: flaggedQuestionsDetailed,
    tabSwitches: window.__TAB_STRIKES || 0,
    time_taken: window.examStartTime
      ? Math.round((Date.now() - window.examStartTime) / 1000)
      : 0,
    submittedAt: new Date().toISOString(),
    status: timeUp ? "timeout" : "completed"
  };

  try {
    const notifyBody = {
      student_name: getMetaContent("student-name"),
      admission_number: getMetaContent("student-admission"),
      class_category: getMetaContent("student-class-level", "student-class-category", "student-class"),
      class_arm: getMetaContent("student-class-arm", "student-class"),
      subject: payload.subject,
      score: rawScore,
      total_questions: total,
      flagged: flaggedQuestionsDetailed.length,
      year: yearMeta?.content || getExamYear(),
      submitted_at: payload.submittedAt,
      status: payload.status
    };

    await fetch("/api/notifications/notify/exam_end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(notifyBody)
    });

  } catch (err) {
    console.error("Failed to send exam_end notification:", err);
  }

  try {
    const res = await fetch("/submit_exam", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const out = await res.json().catch(() => ({}));
      throw new Error(out.error || "Submit failed");
    }

    try {
      sessionStorage.removeItem(SS_KEY);
      localStorage.removeItem(LS_EXAM_LOCK);
    } catch {}

    location.replace("/result");

  } catch (err) {
    window.__examFinished = false;
    examFlash(err.message || "Unable to submit exam. Please contact admin.", "danger");
    console.error("Submit exam error:", err);
  }
};

/* ======================================================
   LOAD QUESTION
====================================================== */

window.loadQuestion = function (i) {
  if (!window.examData) return;
  if (i < 0 || i >= window.examData.questions.length) return;

  const q = window.examData.questions[i];

  if (q.isInstruction) {
    const nextReal = window.realQuestionIndices.find((r) => r > i);
    if (nextReal !== undefined) return loadQuestion(nextReal);
    return;
  }

  window.currentQuestionIndex = i;

  if (typeof updateFlagUI === "function") {
    updateFlagUI(window.flaggedQuestions.has(i));
  }

  const pos = window.realQuestionIndices.indexOf(i);
  const currentQuestionNumber = $("#currentQuestionNumber");

  if (pos !== -1 && currentQuestionNumber) {
    currentQuestionNumber.textContent = pos + 1;
  }

  const prev = window.userAnswers[i]?.index;
  const locked = window.lockedQuestions.has(i);

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function stripLabel(text) {
    return String(text || "").replace(/^[A-Da-d][\.\)\-:\s]+/, "").trim();
  }

  function applyHighlight(text) {
    const safe = escapeHtml(text);
    return safe.replace(/\*(.+?)\*/g, `<span class="focus-word">$1</span>`);
  }

  function convertBlanks(text) {
    if (!text) return text;
    return String(text).replace(/_{3,}\s*(\d+)/g, (_, num) => {
      return `<span class="gap">${num}</span>`;
    });
  }

  const passageBlock = $("#passageBlock");

  if (passageBlock) {
    if (q.passage) {
      passageBlock.style.display = "block";
      passageBlock.innerHTML = `
        <div class="passage-block">
          <div class="passage-text">
            ${convertBlanks(applyHighlight(q.passage))}
          </div>
        </div>
      `;
    } else {
      passageBlock.style.display = "none";
      passageBlock.innerHTML = "";
    }
  }

  let sectionHTML = "";
  const sec = window.sectionInstructions[i];

  const subjectMeta = document.querySelector('meta[name="exam-subject"]');
  const isLiterature =
    subjectMeta && subjectMeta.content.toLowerCase().includes("literature");

  if (sec) {
    const titleHTML = sec.title
      ? `<div class="section-instr-title">${applyHighlight(sec.title)}</div>`
      : "";

    const bodyHTML = sec.body
      ? `<div class="section-instr-body">${convertBlanks(applyHighlight(sec.body))}</div>`
      : "";

    let passageHTML = "";
    if (isLiterature && q.passage) {
      passageHTML = `
        <div class="literature-passage-block" style="margin-top:10px; white-space:pre-line;">
          ${convertBlanks(applyHighlight(q.passage))}
        </div>
      `;
    }

    sectionHTML = `
      <div class="section-instruction-card">
        ${titleHTML}
        ${bodyHTML}
        ${passageHTML}
      </div>
    `;
  }

  let diagramHTML = "";
  if (q.diagram) {
    diagramHTML = `
      <div class="question-diagram mb-4">
        <img src="${escapeHtml(q.diagram)}" class="diagram-img"
             style="max-width:100%; border-radius:6px;">
      </div>
    `;
  }

  const optionsHTML = (q.options || []).map((opt, idx) => {
    const cleanOpt = stripLabel(opt);
    const letter = String.fromCharCode(65 + idx);
    const selected = prev === idx ? "selected" : "";
    const dis = locked ? "disabled" : "";

    return `
      <button class="option-btn ${selected}" data-option-index="${idx}" ${dis}>
        <span class="option-letter">${letter}</span>
        ${applyHighlight(cleanOpt)}
      </button>
    `;
  }).join("");

  const questionContent = $("#questionContent");

  if (questionContent) {
    questionContent.innerHTML = `
      <div class="qa-slide fade-in-up">
        ${diagramHTML}
        ${sectionHTML}
        <h3 class="text-xl font-medium mb-4">
          ${applyHighlight(q.question)}
        </h3>
        <div class="space-y-3">
          ${optionsHTML}
        </div>
      </div>
    `;
  }

  $$(".option-btn").forEach((btn) => {
    btn.onclick = () => selectOption(Number(btn.dataset.optionIndex));
  });

  updateNavigationButtons();
  updateQuestionNavigation();
};

/* ======================================================
   SELECT OPTION
====================================================== */

window.selectOption = function (idx) {
  const qIndex = window.currentQuestionIndex;
  const q = window.examData.questions[qIndex];

  if (window.lockedQuestions.has(qIndex)) return;

  const correct = q.correctIndex;
  const isCorrect = idx === correct;

  window.userAnswers[qIndex] = { index: idx, correct: isCorrect };
  window.lockedQuestions.add(qIndex);

  $$(".option-btn").forEach((btn) => {
    btn.disabled = true;
    btn.classList.toggle(
      "selected",
      Number(btn.dataset.optionIndex) === idx
    );
  });

  updateProgress();
  updateQuestionNavigation();

  setTimeout(() => {
    const pos = window.realQuestionIndices.indexOf(window.currentQuestionIndex);

    if (pos >= 0 && pos < window.realQuestionIndices.length - 1) {
      const nextIndex = window.realQuestionIndices[pos + 1];
      loadQuestion(nextIndex);
    } else {
      const nextBtn = $("#nextBtn");
      if (nextBtn) nextBtn.click();
      else submitExam(false);
    }
  }, 650);
};

/* ======================================================
   QUESTION MOVEMENT
====================================================== */

window.previousQuestion = function () {
  if (!window.realQuestionIndices || window.realQuestionIndices.length === 0) return;

  const pos = window.realQuestionIndices.indexOf(window.currentQuestionIndex);

  if (pos > 0) {
    loadQuestion(window.realQuestionIndices[pos - 1]);
  }
};

window.nextQuestion = function () {
  if (!window.realQuestionIndices || window.realQuestionIndices.length === 0) return;

  const pos = window.realQuestionIndices.indexOf(window.currentQuestionIndex);

  if (pos < window.realQuestionIndices.length - 1) {
    loadQuestion(window.realQuestionIndices[pos + 1]);
  } else {
    submitExam(false);
  }
};

/* ======================================================
   TIMER
====================================================== */

window.startTimer = function () {
  if (window.examTimer) clearInterval(window.examTimer);

  const timerDisplay = $("#timerDisplay");

  window.examTimer = setInterval(() => {
    window.timeRemaining--;

    if (window.timeRemaining < 0) window.timeRemaining = 0;

    if (timerDisplay) {
      timerDisplay.textContent = formatTime(window.timeRemaining);

      if (window.timeRemaining <= 60) {
        timerDisplay.classList.add("timer-critical");
      } else {
        timerDisplay.classList.remove("timer-critical");
      }
    }

    const t = window.timeRemaining;
    const init = window.initialTimeAllowed || t;

    if (!__warn20Shown && init >= 20 * 60 && t <= 20 * 60 && t > 19 * 60) {
      examFlash("⏰ You have 20 minutes left.", "warning");
      __warn20Shown = true;
    }

    if (!__warn10Shown && init >= 10 * 60 && t <= 10 * 60 && t > 9 * 60) {
      examFlash("⏰ You have 10 minutes left.", "warning");
      __warn10Shown = true;
    }

    if (!__warn5Shown && init >= 5 * 60 && t <= 5 * 60 && t > 4 * 60) {
      examFlash("⚠️ Only 5 minutes left. Review and submit!", "danger");
      __warn5Shown = true;
    }

    if (t <= 0) {
      clearInterval(window.examTimer);
      window.__timeExpired = true;
      submitExam(true);
    }
  }, 1000);
};

/* ======================================================
   START EXAM
====================================================== */

window.startExam = async function () {
  if (window.examStarted) return;
  window.examStarted = true;

  try {
    document.body.classList.add("exam-started");

    const modal = $("#instructionsModal");
    if (modal) {
      modal.classList.add("hidden");
      modal.style.display = "none";
    }

    const iface = $("#examInterface");
    if (iface) iface.classList.remove("hidden");

    await loadExamData(true);

    window.examStartTime = Date.now();
    startTimer();

    const timerBlock = $("#examTimer");
    const fullscreenBtn = $("#fullscreenBtn");
    const studentBlock = $(".exam-topbar-student");

    if (timerBlock) timerBlock.classList.remove("hidden");
    if (fullscreenBtn) fullscreenBtn.classList.remove("hidden");
    if (studentBlock) studentBlock.classList.remove("hidden");

  } catch (err) {
    console.error("startExam error:", err);

    window.examStarted = false;

    const iface = $("#examInterface");
    if (iface) iface.classList.add("hidden");

    const modal = $("#instructionsModal");
    if (modal) {
      modal.classList.remove("hidden");
      modal.style.display = "";
    }

    examFlash("Unable to start exam. Contact admin.", "danger");
  }
};

/* ======================================================
   FLAG QUESTION
====================================================== */

window.toggleFlag = function () {
  const qIndex = window.currentQuestionIndex;
  if (qIndex == null) return;

  if (window.flaggedQuestions.has(qIndex)) {
    examFlash("⚠️ This question is already flagged.", "info");
    return;
  }

  window.flaggedQuestions.add(qIndex);
  updateFlagUI(true);
  updateQuestionNavigation();

  examFlash("🚩 Your teacher has been notified of this question.", "success");

  setTimeout(() => {
    updateFlagUI(window.flaggedQuestions.has(qIndex));
  }, 2800);
};

function updateFlagUI(isFlagged) {
  const btn = document.getElementById("flagBtn");
  const txt = document.getElementById("flagText");

  if (!btn || !txt) return;

  if (isFlagged) {
    btn.classList.add("flagged");
    txt.textContent = "Flagged";
  } else {
    btn.classList.remove("flagged");
    txt.textContent = "Flag";
  }
}

/* ======================================================
   DOM READY
====================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const startBtn = $("#startExamBtn");

  if (startBtn) {
    startBtn.addEventListener("click", () => {
      window.startExam();
    });
  }
});

/* ======================================================
   KEYBOARD NAVIGATION
====================================================== */

document.addEventListener("keydown", (e) => {
  if (!window.examStarted || window.__examFinished) return;

  const tag = e.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;

  const real = window.realQuestionIndices;
  if (!real || !real.length) return;

  const pos = real.indexOf(window.currentQuestionIndex);

  if (e.key === "ArrowLeft") {
    e.preventDefault();
    window.previousQuestion();
  }

  if (e.key === "ArrowRight") {
    e.preventDefault();

    if (pos === real.length - 1) return;

    window.nextQuestion();
  }
});
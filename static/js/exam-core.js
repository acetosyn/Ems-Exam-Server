// ======================================================
// exam-core.js — EMIS CBT ENGINE v14
//
// TERM / PORTAL AWARE ENGINE
//
// JSS:
//   /static/portal/<YEAR>/<ARM>/<TERM>/<FILE>.json
//   /static/portal/<YEAR>/<CLASS>/<TERM>/<FILE>.json
//
// SS:
//   /static/portal/<YEAR>/<ARM>/<FILE>.json
//
// Supports:
//   • JSS1 / JSS2 / JSS3 term-aware exams
//   • SS1 / SS2 / SS3 non-term-aware exams
//   • Exact class-arm routing
//   • Broad JSS fallback
//   • Subject alias / filename fallback
//   • Question shuffle
//   • Instructions / passages / diagrams
//   • Locked answers
//   • Flagged questions
//   • Timer
//   • Exam submission
// ======================================================

console.log("[exam-core] EMIS CBT ENGINE v14 — PORTAL + TERM AWARE");


// ======================================================
// GLOBAL EXAM STATE
// ======================================================

window.examData = null;
window.currentQuestionIndex = 0;
window.userAnswers = {};
window.lockedQuestions = new Set();
window.flaggedQuestions = new Set();
window.essayData = null;
window.examSection = "objective";

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

window.__loadedExamJSONUrl = null;


// ======================================================
// STORAGE KEYS
// ======================================================

const SS_KEY = "emis_exam_progress";
const LS_RELOADS = "emis_exam_reload_count";
const LS_EXAM_LOCK = "emis_exam_lock_active";


// ======================================================
// TIMER WARNINGS
// ======================================================

let __warn20Shown = false;
let __warn10Shown = false;
let __warn5Shown = false;


// ======================================================
// BASIC DOM HELPERS
// ======================================================

function $(selector, root = document) {
  return root.querySelector(selector);
}

function $$(selector, root = document) {
  return [...root.querySelectorAll(selector)];
}


// ======================================================
// TIME FORMATTER
// ======================================================

function formatTime(seconds) {
  const safe = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safe / 60).toString().padStart(2, "0");
  const secs = Math.floor(safe % 60).toString().padStart(2, "0");

  return `${minutes}:${secs}`;
}


// ======================================================
// FLASH MESSAGE
// ======================================================

function examFlash(message, type = "info") {
  let flashEl = document.getElementById("examFlashMessage") || document.getElementById("examFlash") || document.getElementById("flashMessage");

  if (!flashEl) {
    flashEl = document.createElement("div");
    flashEl.id = "examFlash";
    flashEl.className = "exam-flash";
    flashEl.setAttribute("aria-hidden", "true");
    document.body.appendChild(flashEl);
  }

  flashEl.textContent = message;

  flashEl.classList.remove("exam-flash-info", "exam-flash-success", "exam-flash-warning", "exam-flash-danger", "show");
  flashEl.classList.add(`exam-flash-${type}`, "show");

  flashEl.style.pointerEvents = "none";

  clearTimeout(window.__examFlashTimer);

  window.__examFlashTimer = setTimeout(() => {
    flashEl.classList.remove("show");
  }, 2800);
}


// ======================================================
// META HELPER
// ======================================================

function getMetaContent(...names) {
  for (const name of names) {
    const meta = document.querySelector(`meta[name="${name}"]`);

    if (meta && String(meta.content || "").trim()) {
      return String(meta.content).trim();
    }
  }

  return "";
}


// ======================================================
// UNIQUE ARRAY
// ======================================================

function uniqueArray(items) {
  return [...new Set((items || []).filter(Boolean))];
}


// ======================================================
// CLASS NORMALIZATION
// ======================================================

function normalizeClassLevel(value) {
  const raw = String(value || "").toUpperCase().trim().replace(/-/g, "_");
  const compact = raw.replace(/[\s_]/g, "");

  for (const level of ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]) {
    if (compact === level || compact.startsWith(level)) {
      return level;
    }
  }

  return "";
}


function getExamClassLevel(classCategory = "") {
  return normalizeClassLevel(getMetaContent("student-class-level")) ||
         normalizeClassLevel(getMetaContent("student-class-category")) ||
         normalizeClassLevel(classCategory) ||
         normalizeClassLevel(getMetaContent("student-class")) ||
         "";
}


// ======================================================
// CLASS ARM
// ======================================================

function getExamClassArm(classLevel = "") {
  const raw = getMetaContent("student-class-arm") || getMetaContent("student-class") || classLevel || "";

  return String(raw).trim().toUpperCase();
}


function getExamArmCandidates(classLevel = "") {
  const arm = getExamClassArm(classLevel);

  return uniqueArray([
    arm,
    arm.replace(/\//g, ""),
    classLevel && arm === classLevel ? classLevel : ""
  ]);
}


// ======================================================
// TERM NORMALIZATION
// ======================================================

function normalizeExamTerm(value) {
  const raw = String(value || "").trim().toUpperCase();

  const aliases = {
    "1": "FIRST", "01": "FIRST", "1ST": "FIRST", "FIRST": "FIRST", "FIRST TERM": "FIRST", "1ST TERM": "FIRST", "TERM 1": "FIRST", "TERM1": "FIRST",
    "2": "SECOND", "02": "SECOND", "2ND": "SECOND", "SECOND": "SECOND", "SECOND TERM": "SECOND", "2ND TERM": "SECOND", "TERM 2": "SECOND", "TERM2": "SECOND",
    "3": "THIRD", "03": "THIRD", "3RD": "THIRD", "THIRD": "THIRD", "THIRD TERM": "THIRD", "3RD TERM": "THIRD", "TERM 3": "THIRD", "TERM3": "THIRD"
  };

  return aliases[raw] || "";
}


function getExamTerm() {
  return normalizeExamTerm(
    getMetaContent("exam-term") ||
    getMetaContent("active-term") ||
    getMetaContent("student-exam-term")
  );
}


function termLabel(term) {
  const normalized = normalizeExamTerm(term);

  return {
    FIRST: "1st Term",
    SECOND: "2nd Term",
    THIRD: "3rd Term"
  }[normalized] || "";
}


function isTermAwareExamClass(classLevel) {
  return ["JSS1", "JSS2", "JSS3"].includes(
    normalizeClassLevel(classLevel)
  );
}


// ======================================================
// EXAM YEAR
// ======================================================

function getExamYear() {
  return getMetaContent("exam-year") || String(new Date().getFullYear());
}


// ======================================================
// EXAM META SNAPSHOT
// ======================================================

function getExamRuntimeMeta(subject = "", classCategory = "") {
  const classLevel = getExamClassLevel(classCategory);
  const classArm = getExamClassArm(classLevel);
  const year = getExamYear();
  const term = isTermAwareExamClass(classLevel) ? getExamTerm() : "";

  return {
    subject: String(subject || getMetaContent("exam-subject") || "").trim(),
    year,
    classLevel,
    classArm,
    term,
    termLabel: termLabel(term),
    termAware: isTermAwareExamClass(classLevel)
  };
}


// ======================================================
// INSTRUCTION PARSER
// ======================================================

function parseInstructionText(text) {
  if (!text) return null;

  const lines = String(text).split(/\r?\n+/);
  let title = String(lines[0] || "").trim();

  title = title.replace(/\s*[:：]\s*$/, "");

  const body = lines.slice(1).join(" ").trim();

  return {
    title,
    body,
    raw: text
  };
}


// ======================================================
// CORRECT ANSWER RESOLVER
// Supports A-D, A-E, labelled answers and numeric indexes.
// ======================================================

function getCorrectIndex(question) {
  if (!question || typeof question !== "object") return -1;
  if (typeof question.correctIndex === "number") return question.correctIndex;

  const raw = question.correctOption || question.correct_option || question.answer || question.correctAnswer || question.correct_answer || "";
  if (raw === null || raw === undefined || raw === "") return -1;

  const cleaned = String(raw).trim().toUpperCase();

  // Letter answers: A, B, C, D, E
  if (/^[A-E]$/.test(cleaned)) return cleaned.charCodeAt(0) - 65;

  // Labelled answers: A. Answer, B) Answer, C - Answer, D: Answer, E Answer
  const letterMatch = cleaned.match(/^([A-E])[\.\)\-:\s]/);
  if (letterMatch) return letterMatch[1].charCodeAt(0) - 65;

  // Numeric answers: 0-4 or 1-5
  const optionIndex = Number(cleaned);

  if (!Number.isNaN(optionIndex)) {
    if (optionIndex >= 0 && optionIndex <= 4) return optionIndex;
    if (optionIndex >= 1 && optionIndex <= 5) return optionIndex - 1;
  }

  return -1;
}

// ======================================================
// FULL EMIS SUBJECT RESOLVER
// ======================================================

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

    TECHNICAL: "TECHNICAL DRAWING",
    "TECHNICAL DRAWING": "TECHNICAL DRAWING",

    IRK: "IRS",
    IRS: "IRS",

    ISLAMIYAH: "ISLAMIYYAH",
    ISLAMIYYA: "ISLAMIYYAH",
    ISLAMIYYAH: "ISLAMIYYAH",

    COMPUTER: "COMPUTER SCIENCE",
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


// ======================================================
// SUBJECT → FILE BASE
// ======================================================

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

  return map[key] || key.toLowerCase()
    .replace(/&/g, "and")
    .replace(/\./g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}


// ======================================================
// SUBJECT FILE FALLBACKS
// ======================================================

function getSubjectFileBases(subject) {
  const primary = subjectKeyToFileBase(subject);

  const fallbacks = {
    accounts: ["accounts", "account", "accounting", "financial_account", "financial_accounting"],

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

    hort_crop_production: ["hort_crop_production", "hort_and_crop_production", "horticulture_and_crop_production"],

    soc_cit_std: ["soc_cit_std", "soc_and_cit_std", "social_and_citizenship_studies"],

    cit_her_std: ["cit_her_std", "cit_and_her_std", "heritage_citizenship_studies", "heritage_and_citizenship_studies", "hcs"],

    phe: ["phe", "p_h_e"],

    national_value: ["national_value", "national_values"],

    inter_science: ["inter_science", "integrated_science"],

    garment_making: ["garment_making"],

    business_studies: ["business_studies"]
  };

  return uniqueArray([
    primary,
    ...(fallbacks[primary] || [])
  ]);
}


// ======================================================
// URL PATH SEGMENT
// ======================================================

function encodePathSegment(value) {
  return encodeURIComponent(String(value || "").trim());
}


// ======================================================
// BUILD PORTAL EXAM JSON CANDIDATES
// ======================================================

function buildExamJSONCandidates(subject, classCategory = "") {
  const meta = getExamRuntimeMeta(subject, classCategory);

  const year = meta.year;
  const classLevel = meta.classLevel;
  const classArm = meta.classArm;
  const term = meta.term;

  if (!year || !classLevel) {
    console.error("[exam-core] Missing year/class metadata:", meta);
    return [];
  }

  if (meta.termAware && !term) {
    console.error("[exam-core] JSS exam term is missing:", meta);
    return [];
  }

  const classSuffix = classLevel.toLowerCase();
  const bases = getSubjectFileBases(subject);

  const armCandidates = uniqueArray([
    classArm,
    String(classArm || "").replace(/\//g, "")
  ]);

  const urls = [];

  // ====================================================
  // JSS — TERM AWARE
  //
  // Exact:
  // /static/portal/2017/JSS1A/FIRST/file.json
  //
  // Broad fallback:
  // /static/portal/2017/JSS1/FIRST/file.json
  // ====================================================

  if (meta.termAware) {
    for (const base of bases) {
      const filename = `${base}_${classSuffix}.json`;

      for (const arm of armCandidates) {
        if (!arm) continue;

        urls.push(
          `/static/portal/${encodePathSegment(year)}/${encodePathSegment(arm)}/${encodePathSegment(term)}/${encodePathSegment(filename)}`
        );
      }

      if (classLevel && classArm !== classLevel) {
        urls.push(
          `/static/portal/${encodePathSegment(year)}/${encodePathSegment(classLevel)}/${encodePathSegment(term)}/${encodePathSegment(filename)}`
        );
      }
    }

    return uniqueArray(urls);
  }

  // ====================================================
  // SS — NON TERM AWARE
  //
  // Exact:
  // /static/portal/2025/SS1_GOLD/file.json
  //
  // Broad SS fallback is deliberately NOT used for
  // streamed students because it could mix subjects.
  // ====================================================

  for (const base of bases) {
    const filename = `${base}_${classSuffix}.json`;

    for (const arm of armCandidates) {
      if (!arm) continue;

      urls.push(
        `/static/portal/${encodePathSegment(year)}/${encodePathSegment(arm)}/${encodePathSegment(filename)}`
      );
    }

    if (classArm === classLevel) {
      urls.push(
        `/static/portal/${encodePathSegment(year)}/${encodePathSegment(classLevel)}/${encodePathSegment(filename)}`
      );
    }
  }

  return uniqueArray(urls);
}


// ======================================================
// PRIMARY EXAM JSON RESOLVER
// ======================================================

function resolveExamJSON(subject, classCategory = "") {
  const candidates = buildExamJSONCandidates(subject, classCategory);
  return candidates[0] || "";
}


// ======================================================
// EXPOSE RESOLVERS FOR DEBUGGING / OTHER SCRIPTS
// ======================================================

window.buildExamJSONCandidates = buildExamJSONCandidates;
window.resolveExamJSON = resolveExamJSON;
window.getExamRuntimeMeta = getExamRuntimeMeta;


// ======================================================
// FETCH FIRST WORKING JSON
// ======================================================

async function fetchFirstWorkingJSON(urls) {
  const errors = [];

  for (const url of urls) {
    try {
      console.log("📥 Trying Exam JSON:", url);

      const response = await fetch(url, {
        cache: "no-store",
        headers: {
          Accept: "application/json"
        }
      });

      if (!response.ok) {
        errors.push(`${url} → HTTP ${response.status}`);
        continue;
      }

      const contentType = response.headers.get("content-type") || "";

      if (!contentType.includes("application/json") && !contentType.includes("text/plain")) {
        const text = await response.text();

        try {
          const parsed = JSON.parse(text);

          return {
            url,
            data: parsed
          };

        } catch {
          errors.push(`${url} → Response is not JSON`);
          continue;
        }
      }

      let data;

      try {
        data = await response.json();
      } catch (error) {
        errors.push(`${url} → Invalid JSON: ${error.message}`);
        continue;
      }

      if (!data || typeof data !== "object" || Array.isArray(data)) {
        errors.push(`${url} → JSON root is not an object`);
        continue;
      }

      return {
        url,
        data
      };

    } catch (error) {
      errors.push(`${url} → ${error.message}`);
    }
  }

  const error = new Error("Exam JSON not found");
  error.tried = errors;

  throw error;
}


// ======================================================
// NORMALIZE QUESTION
// ======================================================

function normalizeExamQuestion(question, index) {
  const q = question && typeof question === "object" ? question : {};

  return {
    ...q,

    id: q.id ?? index + 1,

    question: q.question || q.text || "",

    options: Array.isArray(q.options) ? q.options : [],

    diagram: q.diagram || q.image || null,

    passage: q.passage || null,

    isInstruction: Boolean(
      q.isInstruction ||
      q.is_instruction ||
      q.type === "instruction"
    ),

    correctIndex: getCorrectIndex(q)
  };
}




// ======================================================
// NORMALIZE ESSAY / THEORY DATA
// ======================================================

function normalizeEssayData(essay) {
  const source = essay && typeof essay === "object" && !Array.isArray(essay) ? essay : {};
  const questions = Array.isArray(source.questions) ? source.questions : [];

  return {
    title: String(source.title || "SECTION B - THEORY").trim(),
    instruction: String(source.instruction || "Answer the questions on the answer booklet provided.").trim(),
    questions: questions.map((question, index) => {
      const q = question && typeof question === "object" ? question : {};

      return {
        ...q,
        id: q.id ?? index + 1,
        question: String(q.question || q.text || "").trim(),
        diagram: q.diagram || q.image || null
      };
    }).filter(question => question.question || question.diagram)
  };
}




// ======================================================
// LOAD EXAM DATA
// ======================================================

window.loadExamData = async function (quiet = false) {
  try {
    const subjectMeta = $('meta[name="exam-subject"]');
    const classMeta = $('meta[name="student-class-level"]') || $('meta[name="student-class-category"]') || $('meta[name="student-class"]');

    if (!subjectMeta || !classMeta) throw new Error("Missing subject/class metadata.");

    const subject = String(subjectMeta.content || "").trim();
    const classCategory = String(classMeta.content || "").trim();

    if (!subject) throw new Error("Missing exam subject metadata.");

    const runtimeMeta = getExamRuntimeMeta(subject, classCategory);
    const candidates = buildExamJSONCandidates(subject, classCategory);

    console.log("\n============================================================");
    console.log("[exam-core] EXAM RUNTIME RESOLVER");
    console.log("Subject     :", runtimeMeta.subject);
    console.log("Year        :", runtimeMeta.year);
    console.log("Class Level :", runtimeMeta.classLevel);
    console.log("Class Arm   :", runtimeMeta.classArm);
    console.log("Term Aware  :", runtimeMeta.termAware);
    console.log("Term        :", runtimeMeta.term || "NO TERM");
    console.log("Candidates  :", candidates);
    console.log("============================================================\n");

    if (!runtimeMeta.classLevel) throw new Error("Unable to determine student's class level.");
    if (runtimeMeta.termAware && !runtimeMeta.term) throw new Error(`${runtimeMeta.classLevel} exam term is missing.`);

    if (!candidates.length) {
      throw new Error("No valid exam JSON path could be resolved. Check year, class arm, term and subject.");
    }

    const loaded = await fetchFirstWorkingJSON(candidates);
    const rawData = loaded.data;

    window.__loadedExamJSONUrl = loaded.url;

    console.log("✅ Exam JSON loaded successfully:", loaded.url);

    // ==================================================
    // SECTION A — OBJECTIVE QUESTIONS
    // ==================================================

    const rawQuestions = Array.isArray(rawData.questions) ? rawData.questions : [];

    rawData.questions = rawQuestions.map(
      (question, index) => normalizeExamQuestion(question, index)
    );

    // ==================================================
    // SECTION B — THEORY / ESSAY
    // ==================================================

    window.essayData = normalizeEssayData(rawData.essay);
    window.examSection = "objective";

    console.log("[exam-core] Essay section loaded:", {
      title: window.essayData?.title || "SECTION B - THEORY",
      questions: window.essayData?.questions?.length || 0
    });

    // ==================================================
    // SHUFFLE OBJECTIVE QUESTIONS
    // ==================================================

    window.examData =
      typeof shuffleQuestions === "function"
        ? shuffleQuestions(rawData)
        : rawData;

    if (!window.examData || !Array.isArray(window.examData.questions)) {
      throw new Error("Exam JSON does not contain a valid questions array.");
    }

    // ==================================================
    // REAL OBJECTIVE QUESTIONS
    // ==================================================

    window.realQuestionIndices = [];

    window.examData.questions.forEach((question, index) => {
      const hasOptions =
        Array.isArray(question.options) &&
        question.options.some(
          (option) =>
            option !== null &&
            option !== undefined &&
            String(option).trim() !== ""
        );

      if (!question.isInstruction && hasOptions) {
        window.realQuestionIndices.push(index);
      }
    });

    const totalReal = window.realQuestionIndices.length;

    if (!totalReal) {
      throw new Error("No valid multiple-choice questions found in exam JSON.");
    }

    // ==================================================
    // OBJECTIVE SECTION INSTRUCTIONS
    // ==================================================

    window.sectionInstructions = {};
    let currentSectionMeta = null;

    window.examData.questions.forEach((question, index) => {
      if (question.isInstruction) {
        currentSectionMeta = parseInstructionText(question.question);
        return;
      }

      if (currentSectionMeta) {
        window.sectionInstructions[index] = currentSectionMeta;
      }
    });

    // ==================================================
    // RESET SECTION UI
    // ==================================================

    const objectiveSection = $("#objectiveSection");
    const essaySection = $("#essaySection");
    const sectionStatus = $("#examSectionStatus");

    if (objectiveSection) objectiveSection.classList.remove("hidden");
    if (essaySection) essaySection.classList.add("hidden");
    if (sectionStatus) sectionStatus.textContent = "Section A • Objective";

    // ==================================================
    // EXAM HEADER
    // ==================================================

    const subjectTitle = $("#examSubjectTitle");

    if (subjectTitle) {
      const termText = runtimeMeta.term
        ? ` • ${termLabel(runtimeMeta.term).toUpperCase()}`
        : "";

      subjectTitle.innerHTML = `
        <span class="exam-subject-pill">
          ${escapeHTMLGlobal(String(subject).toUpperCase())}
        </span>

        <span class="exam-question-count">
          • SECTION A • ${totalReal} QUESTION${totalReal === 1 ? "" : "S"}${termText}
        </span>
      `;

      subjectTitle.classList.remove("hidden");
    }

    const totalQuestionsEl = $("#totalQuestions");

    if (totalQuestionsEl) {
      totalQuestionsEl.textContent = totalReal;
    }

    // ==================================================
    // TIMER
    // ==================================================

    const minutes = Number(
      rawData.time_allowed_minutes ??
      rawData.timeAllowedMinutes ??
      rawData.duration_minutes ??
      60
    );

    window.timeRemaining = Math.max(1, Number.isFinite(minutes) ? minutes : 60) * 60;
    window.initialTimeAllowed = window.timeRemaining;

    __warn20Shown = false;
    __warn10Shown = false;
    __warn5Shown = false;

    const timerDisplay = $("#timerDisplay");

    if (timerDisplay) {
      timerDisplay.textContent = formatTime(window.timeRemaining);
    }

    // ==================================================
    // INITIAL QUESTION
    // ==================================================

    window.currentQuestionIndex = window.realQuestionIndices[0];

    loadQuestion(window.currentQuestionIndex);
    updateProgress();
    updateQuestionNavigation();
    updateNavigationButtons();

    console.log("[exam-core] Exam ready:", {
      objectiveQuestions: totalReal,
      essayQuestions: window.essayData?.questions?.length || 0,
      section: window.examSection
    });

  } catch (error) {
    console.error("❌ loadExamData error:", error);

    if (error.tried) {
      console.group("[exam-core] JSON paths attempted");

      error.tried.forEach((item) => {
        console.error(item);
      });

      console.groupEnd();
    }

    const runtime = getExamRuntimeMeta(
      getMetaContent("exam-subject"),
      getMetaContent("student-class-level", "student-class-category")
    );

    console.error("[exam-core] Failed runtime metadata:", runtime);

    const message = "Unable to load exam questions. Please contact your teacher or admin.";

    examFlash(message, "danger");

    if (!quiet) console.error(message);

    throw error;
  }
};



// ======================================================
// GLOBAL HTML ESCAPER
// ======================================================

function escapeHTMLGlobal(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


// ======================================================
// PROGRESS
// ======================================================

window.updateProgress = function () {
  const total = window.realQuestionIndices.length;

  const answered = window.realQuestionIndices.filter(
    (index) => Boolean(window.userAnswers[index])
  ).length;

  const flagged = window.realQuestionIndices.filter(
    (index) => window.flaggedQuestions.has(index)
  ).length;

  const remaining = Math.max(0, total - answered);
  const percentage = total ? (answered / total) * 100 : 0;

  const answeredEl = $("#answeredCount");
  const flaggedEl = $("#flaggedCount");
  const remainingEl = $("#remainingCount");

  const progressBar = $("#progressBar");
  const progressText = $("#progressText");

  if (answeredEl) answeredEl.textContent = answered;
  if (flaggedEl) flaggedEl.textContent = flagged;
  if (remainingEl) remainingEl.textContent = remaining;

  if (progressBar) {
    progressBar.style.width = `${percentage}%`;
  }

  if (progressText) {
    progressText.textContent = `${Math.round(percentage)}% Complete`;
  }
};

// ======================================================
// NAVIGATION BUTTONS
// ======================================================

window.updateNavigationButtons = function () {
  const previous = $("#prevBtn");
  const next = $("#nextBtn");

  if (!window.realQuestionIndices?.length) return;

  const firstRealIndex = window.realQuestionIndices[0];
  const lastRealIndex = window.realQuestionIndices[window.realQuestionIndices.length - 1];

  if (previous) previous.disabled = window.currentQuestionIndex === firstRealIndex;

  if (next) {
    const isLast = window.currentQuestionIndex === lastRealIndex;

    next.innerHTML = isLast
      ? `Section B <i class="fa-solid fa-arrow-right"></i>`
      : `Next <i class="fa-solid fa-arrow-right"></i>`;
  }
};

// ======================================================
// QUESTION NAVIGATION GRID
// ======================================================

window.updateQuestionNavigation = function () {
  const grid = $("#questionGrid");

  if (!grid || !window.examData) {
    return;
  }

  let html = "";

  window.realQuestionIndices.forEach((trueIndex, position) => {
    const active = trueIndex === window.currentQuestionIndex ? "active" : "";
    const answered = window.userAnswers[trueIndex] ? "answered" : "";
    const flagged = window.flaggedQuestions.has(trueIndex) ? "flagged" : "";

    html += `
      <button
        type="button"
        class="question-nav-btn ${active} ${answered} ${flagged}"
        data-q-index="${trueIndex}"
        aria-label="Question ${position + 1}">
        ${position + 1}
      </button>
    `;
  });

  grid.innerHTML = html;

  $$(".question-nav-btn", grid).forEach((button) => {
    button.addEventListener("click", () => {
      loadQuestion(Number(button.dataset.qIndex));
    });
  });

  updateProgress();
};




// ======================================================
// SECTION B — THEORY / ESSAY
// ======================================================

window.renderEssaySection = function () {
  const essay = window.essayData || normalizeEssayData(null);
  const questions = Array.isArray(essay.questions) ? essay.questions : [];

  const titleEl = $("#essayTitle");
  const instructionEl = $("#essayInstruction");
  const questionsEl = $("#essayQuestions");
  const emptyEl = $("#essayEmptyState");

  if (titleEl) titleEl.textContent = essay.title || "SECTION B - THEORY";

  if (instructionEl) {
    instructionEl.textContent = essay.instruction || "";
    instructionEl.classList.toggle("hidden", !essay.instruction);
  }

  if (!questions.length) {
    if (questionsEl) {
      questionsEl.innerHTML = "";
      questionsEl.classList.add("hidden");
    }

    if (emptyEl) emptyEl.classList.remove("hidden");
    return;
  }

  if (emptyEl) emptyEl.classList.add("hidden");
  if (!questionsEl) return;

  questionsEl.classList.remove("hidden");

  questionsEl.innerHTML = questions.map((question, index) => {
    const number = question.id ?? index + 1;

    const diagramHTML = question.diagram ? `
      <img
        src="${escapeHTMLGlobal(question.diagram)}"
        class="essay-diagram"
        alt="Theory question ${escapeHTMLGlobal(number)} diagram"
        loading="lazy">
    ` : "";

    return `
      <article class="essay-question">
        <div class="essay-question-number">${escapeHTMLGlobal(number)}</div>

        <div class="essay-question-content">
          <p>${escapeHTMLGlobal(question.question)}</p>
          ${diagramHTML}
        </div>
      </article>
    `;
  }).join("");
};


window.openEssaySection = function () {
  const objectiveSection = $("#objectiveSection");
  const essaySection = $("#essaySection");
  const sectionStatus = $("#examSectionStatus");
  const subjectTitle = $("#examSubjectTitle");

  window.examSection = "essay";

  if (objectiveSection) objectiveSection.classList.add("hidden");
  if (essaySection) essaySection.classList.remove("hidden");
  if (sectionStatus) sectionStatus.textContent = "Section B • Theory";

  if (subjectTitle) {
    const runtimeMeta = getExamRuntimeMeta(
      getMetaContent("exam-subject"),
      getMetaContent("student-class-level", "student-class-category")
    );

    const termText = runtimeMeta.term
      ? ` • ${termLabel(runtimeMeta.term).toUpperCase()}`
      : "";

    subjectTitle.innerHTML = `
      <span class="exam-subject-pill">
        ${escapeHTMLGlobal(String(runtimeMeta.subject || "").toUpperCase())}
      </span>

      <span class="exam-question-count">
        • SECTION B • THEORY${termText}
      </span>
    `;
  }

  renderEssaySection();

  const summaryModal = $("#summaryModal");
  if (summaryModal) summaryModal.classList.add("hidden");

  window.scrollTo({ top: 0, behavior: "smooth" });
};


window.returnToObjectiveSection = function () {
  const objectiveSection = $("#objectiveSection");
  const essaySection = $("#essaySection");
  const sectionStatus = $("#examSectionStatus");
  const subjectTitle = $("#examSubjectTitle");

  window.examSection = "objective";

  if (essaySection) essaySection.classList.add("hidden");
  if (objectiveSection) objectiveSection.classList.remove("hidden");
  if (sectionStatus) sectionStatus.textContent = "Section A • Objective";

  if (subjectTitle) {
    const runtimeMeta = getExamRuntimeMeta(
      getMetaContent("exam-subject"),
      getMetaContent("student-class-level", "student-class-category")
    );

    const totalReal = window.realQuestionIndices.length;

    const termText = runtimeMeta.term
      ? ` • ${termLabel(runtimeMeta.term).toUpperCase()}`
      : "";

    subjectTitle.innerHTML = `
      <span class="exam-subject-pill">
        ${escapeHTMLGlobal(String(runtimeMeta.subject || "").toUpperCase())}
      </span>

      <span class="exam-question-count">
        • SECTION A • ${totalReal} QUESTION${totalReal === 1 ? "" : "S"}${termText}
      </span>
    `;
  }

  if (window.realQuestionIndices?.length) {
    const validCurrent = window.realQuestionIndices.includes(window.currentQuestionIndex);

    if (!validCurrent) {
      window.currentQuestionIndex =
        window.realQuestionIndices[window.realQuestionIndices.length - 1];
    }

    loadQuestion(window.currentQuestionIndex);
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
};




// ======================================================
// END EXAM MODAL
// ======================================================

window.endExam = function () {
  if (!window.examData) {
    return;
  }

  const total = window.realQuestionIndices.length;

  const answered = window.realQuestionIndices.filter(
    (index) => Boolean(window.userAnswers[index])
  ).length;

  const messageEl = $("#endExamMessage");

  if (messageEl) {
    messageEl.innerHTML = `
      You answered <b>${answered}</b> out of <b>${total}</b>.<br>
      Unanswered questions will be marked incorrect.<br><br>
      Are you sure you want to end this exam?
    `;
  }

  const modal = $("#endExamModal");

  if (modal) {
    modal.classList.remove("hidden");
  }
};


window.closeEndExam = function () {
  const modal = $("#endExamModal");

  if (modal) {
    modal.classList.add("hidden");
  }
};

// ======================================================
// SUBMIT EXAM
// ======================================================

window.submitExam = async function (timeUp = false) {
  if (window.__examFinished) return;

  if (!window.examData || !window.realQuestionIndices.length) {
    examFlash("Exam data is not ready.", "danger");
    return;
  }

  window.__examFinished = true;

  if (window.examTimer) {
    clearInterval(window.examTimer);
    window.examTimer = null;
  }

  const realIndices = window.realQuestionIndices;
  const total = realIndices.length;

  let correct = 0;

  realIndices.forEach((trueIndex) => {
    const question = window.examData.questions[trueIndex];
    const userAnswer = window.userAnswers[trueIndex];

    if (userAnswer && userAnswer.index === question.correctIndex) correct++;
  });

  const answered = realIndices.filter((index) => Boolean(window.userAnswers[index])).length;
  const incorrect = total - correct;
  const skipped = total - answered;
  const rawScore = correct;

  const flaggedQuestionsDetailed = [...window.flaggedQuestions].map((index) => {
    const question = window.examData.questions[index] || {};

    return {
      index,
      question_id: question.id,
      question: question.question
    };
  });

  const runtimeMeta = getExamRuntimeMeta(
    getMetaContent("exam-subject"),
    getMetaContent("student-class-level", "student-class-category")
  );

  const payload = {
    subject: String(runtimeMeta.subject || "").trim().toUpperCase(),

    year: runtimeMeta.year,

    class_level: runtimeMeta.classLevel,
    class_category: runtimeMeta.classLevel,
    class_arm: runtimeMeta.classArm,

    term: runtimeMeta.term || null,
    term_label: runtimeMeta.term ? termLabel(runtimeMeta.term) : null,

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

  // ====================================================
  // SUBMIT RESULT
  //
  // IMPORTANT:
  // /submit_exam is now the authoritative submission flow.
  // It saves the result and the backend sends:
  //
  //   exam_end / timeout
  //   result_available
  //
  // exam-core.js must NOT separately send exam_end,
  // otherwise duplicate submission events are created.
  // ====================================================

  try {
    console.log("[exam-core] Submitting examination:", {
      subject: payload.subject,
      year: payload.year,
      class_level: payload.class_level,
      class_arm: payload.class_arm,
      term: payload.term,
      status: payload.status,
      score: payload.score,
      total: payload.total
    });

    const response = await fetch("/submit_exam", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify(payload)
    });

    const output = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        output.error ||
        `Submit failed (${response.status})`
      );
    }

    console.log(
      "[exam-core] Examination result submitted successfully:",
      output
    );

    try {
      sessionStorage.removeItem(SS_KEY);
      localStorage.removeItem(LS_EXAM_LOCK);
    } catch (storageError) {
      console.warn("[exam-core] Could not clear local exam state:", storageError);
    }

    location.replace("/result");

  } catch (error) {
    window.__examFinished = false;

    console.error(
      "[exam-core] Submit exam error:",
      error
    );

    examFlash(
      error.message ||
      "Unable to submit exam. Please contact admin.",
      "danger"
    );

    if (window.timeRemaining > 0 && !timeUp) {
      startTimer();
    }
  }
};


// ======================================================
// LOAD QUESTION
// ======================================================

window.loadQuestion = function (index) {
  if (!window.examData || !Array.isArray(window.examData.questions)) {
    return;
  }

  if (index < 0 || index >= window.examData.questions.length) {
    return;
  }

  const question = window.examData.questions[index];

  // ====================================================
  // SKIP INSTRUCTION RECORDS
  // ====================================================

  if (question.isInstruction) {
    const nextReal = window.realQuestionIndices.find(
      (realIndex) => realIndex > index
    );

    if (nextReal !== undefined) {
      return loadQuestion(nextReal);
    }

    return;
  }

  window.currentQuestionIndex = index;

  updateFlagUI(
    window.flaggedQuestions.has(index)
  );

  const position = window.realQuestionIndices.indexOf(index);

  const currentQuestionNumber = $("#currentQuestionNumber");

  if (position !== -1 && currentQuestionNumber) {
    currentQuestionNumber.textContent = position + 1;
  }

  const previousAnswer = window.userAnswers[index]?.index;
  const locked = window.lockedQuestions.has(index);

  // ====================================================
  // TEXT HELPERS
  // ====================================================

  function stripLabel(text) {
    return String(text ?? "")
      .replace(/^[A-Da-d][\.\)\-:\s]+/, "")
      .trim();
  }

  function applyHighlight(text) {
    const safe = escapeHTMLGlobal(text);

    return safe.replace(
      /\*(.+?)\*/g,
      `<span class="focus-word">$1</span>`
    );
  }

  function convertBlanks(text) {
    if (!text) {
      return text;
    }

    return String(text).replace(
      /_{3,}\s*(\d+)/g,
      (_, number) => `<span class="gap">${number}</span>`
    );
  }

  // ====================================================
  // PASSAGE
  // ====================================================

  const passageBlock = $("#passageBlock");

  if (passageBlock) {
    if (question.passage) {
      passageBlock.style.display = "block";

      passageBlock.innerHTML = `
        <div class="passage-block">
          <div class="passage-text">
            ${convertBlanks(applyHighlight(question.passage))}
          </div>
        </div>
      `;

    } else {
      passageBlock.style.display = "none";
      passageBlock.innerHTML = "";
    }
  }

  // ====================================================
  // SECTION INSTRUCTION
  // ====================================================

  let sectionHTML = "";

  const section = window.sectionInstructions[index];

  const subjectMeta = document.querySelector(
    'meta[name="exam-subject"]'
  );

  const isLiterature =
    subjectMeta &&
    subjectMeta.content
      .toLowerCase()
      .includes("literature");

  if (section) {
    const titleHTML = section.title
      ? `<div class="section-instr-title">${applyHighlight(section.title)}</div>`
      : "";

    const bodyHTML = section.body
      ? `<div class="section-instr-body">${convertBlanks(applyHighlight(section.body))}</div>`
      : "";

    let literaturePassageHTML = "";

    if (isLiterature && question.passage) {
      literaturePassageHTML = `
        <div class="literature-passage-block" style="margin-top:10px; white-space:pre-line;">
          ${convertBlanks(applyHighlight(question.passage))}
        </div>
      `;
    }

    sectionHTML = `
      <div class="section-instruction-card">
        ${titleHTML}
        ${bodyHTML}
        ${literaturePassageHTML}
      </div>
    `;
  }

  // ====================================================
  // DIAGRAM
  // ====================================================

  let diagramHTML = "";

  if (question.diagram) {
    diagramHTML = `
      <div class="question-diagram mb-4">
        <img
          src="${escapeHTMLGlobal(question.diagram)}"
          class="diagram-img"
          alt="Question diagram"
          loading="eager"
          style="max-width:100%; border-radius:6px;">
      </div>
    `;
  }

  // ====================================================
  // OPTIONS
  // ====================================================

  const optionsHTML = (question.options || []).map(
    (option, optionIndex) => {
      const cleanOption = stripLabel(option);
      const letter = String.fromCharCode(65 + optionIndex);

      const selected =
        previousAnswer === optionIndex
          ? "selected"
          : "";

      const disabled =
        locked
          ? "disabled"
          : "";

      return `
        <button
          type="button"
          class="option-btn ${selected}"
          data-option-index="${optionIndex}"
          ${disabled}>

          <span class="option-letter">
            ${letter}
          </span>

          <span class="option-text">
            ${applyHighlight(cleanOption)}
          </span>

        </button>
      `;
    }
  ).join("");

  // ====================================================
  // QUESTION CONTENT
  // ====================================================

  const questionContent = $("#questionContent");

  if (questionContent) {
    questionContent.innerHTML = `
      <div class="qa-slide fade-in-up">

        ${diagramHTML}

        ${sectionHTML}

        <h3 class="text-xl font-medium mb-4">
          ${applyHighlight(question.question)}
        </h3>

        <div class="space-y-3">
          ${optionsHTML}
        </div>

      </div>
    `;
  }

  // ====================================================
  // OPTION EVENTS
  // ====================================================

  $$(".option-btn", questionContent || document).forEach(
    (button) => {
      button.addEventListener("click", () => {
        selectOption(
          Number(button.dataset.optionIndex)
        );
      });
    }
  );

  updateNavigationButtons();
  updateQuestionNavigation();
};


// ======================================================
// SELECT OPTION
// ======================================================

window.selectOption = function (optionIndex) {
  const questionIndex = window.currentQuestionIndex;

  if (!window.examData?.questions?.[questionIndex]) return;
  if (window.lockedQuestions.has(questionIndex)) return;

  const question = window.examData.questions[questionIndex];
  const correctIndex = question.correctIndex;

  window.userAnswers[questionIndex] = {
    index: optionIndex,
    correct: optionIndex === correctIndex
  };

  window.lockedQuestions.add(questionIndex);

  $$(".option-btn").forEach((button) => {
    button.disabled = true;
    button.classList.toggle("selected", Number(button.dataset.optionIndex) === optionIndex);
  });

  updateProgress();
  updateQuestionNavigation();

  // ====================================================
  // AUTO ADVANCE
  // ====================================================

  setTimeout(() => {
    if (window.__examFinished) return;

    const position = window.realQuestionIndices.indexOf(window.currentQuestionIndex);

    if (position >= 0 && position < window.realQuestionIndices.length - 1) {
      loadQuestion(window.realQuestionIndices[position + 1]);
      return;
    }

    // Last objective question completed.
    // Continue to Section B instead of ending the exam.
    openEssaySection();

  }, 650);
};

// ======================================================
// PREVIOUS QUESTION
// ======================================================

window.previousQuestion = function () {
  if (!window.realQuestionIndices?.length) {
    return;
  }

  const position = window.realQuestionIndices.indexOf(
    window.currentQuestionIndex
  );

  if (position > 0) {
    loadQuestion(
      window.realQuestionIndices[position - 1]
    );
  }
};


// ======================================================
// NEXT QUESTION
// ======================================================

window.nextQuestion = function () {
  if (!window.realQuestionIndices?.length) return;

  const position = window.realQuestionIndices.indexOf(window.currentQuestionIndex);

  if (position >= 0 && position < window.realQuestionIndices.length - 1) {
    loadQuestion(window.realQuestionIndices[position + 1]);
    return;
  }

  openEssaySection();
};


// ======================================================
// TIMER
// ======================================================

window.startTimer = function () {
  if (window.examTimer) {
    clearInterval(window.examTimer);
  }

  const timerDisplay = $("#timerDisplay");

  window.examTimer = setInterval(() => {
    window.timeRemaining--;

    if (window.timeRemaining < 0) {
      window.timeRemaining = 0;
    }

    if (timerDisplay) {
      timerDisplay.textContent = formatTime(
        window.timeRemaining
      );

      timerDisplay.classList.toggle(
        "timer-critical",
        window.timeRemaining <= 60
      );
    }

    const remaining = window.timeRemaining;
    const initial = window.initialTimeAllowed || remaining;

    if (
      !__warn20Shown &&
      initial >= 20 * 60 &&
      remaining <= 20 * 60 &&
      remaining > 19 * 60
    ) {
      examFlash(
        "⏰ You have 20 minutes left.",
        "warning"
      );

      __warn20Shown = true;
    }

    if (
      !__warn10Shown &&
      initial >= 10 * 60 &&
      remaining <= 10 * 60 &&
      remaining > 9 * 60
    ) {
      examFlash(
        "⏰ You have 10 minutes left.",
        "warning"
      );

      __warn10Shown = true;
    }

    if (
      !__warn5Shown &&
      initial >= 5 * 60 &&
      remaining <= 5 * 60 &&
      remaining > 4 * 60
    ) {
      examFlash(
        "⚠️ Only 5 minutes left. Review and submit!",
        "danger"
      );

      __warn5Shown = true;
    }

    if (remaining <= 0) {
      clearInterval(window.examTimer);

      window.__timeExpired = true;

      submitExam(true);
    }

  }, 1000);
};

// ======================================================
// START EXAM
// ======================================================

window.startExam = async function () {
  if (window.examStarted) return;

  window.examStarted = true;

  const loadingOverlay = $("#loadingOverlay");

  try {
    if (loadingOverlay) loadingOverlay.classList.remove("hidden");

    document.body.classList.add("exam-started");

    const modal = $("#instructionsModal");
    if (modal) { modal.classList.add("hidden"); modal.style.display = "none"; }

    const examInterface = $("#examInterface");
    if (examInterface) examInterface.classList.remove("hidden");

    // ==================================================
    // LOAD EXAM FIRST
    // Notification must not fire if questions fail to load.
    // ==================================================

    await loadExamData(true);

    // ==================================================
    // REAL EXAM START
    // ==================================================

    window.examStartTime = Date.now();
    startTimer();

    // ==================================================
    // REAL-TIME EXAM START NOTIFICATION
    //
    // Fires only after:
    //   1. Exam data loads successfully
    //   2. Timer starts
    //
    // Notification failure must NOT stop the exam.
    // ==================================================

    try {
      const runtimeMeta = getExamRuntimeMeta(
        getMetaContent("exam-subject"),
        getMetaContent("student-class-level", "student-class-category")
      );

      const notifyBody = {
        student_name: getMetaContent("student-name"),
        admission_number: getMetaContent("student-admission"),

        class_category: runtimeMeta.classLevel,
        class_level: runtimeMeta.classLevel,
        class_arm: runtimeMeta.classArm,

        subject: String(runtimeMeta.subject || "").trim().toUpperCase(),
        year: runtimeMeta.year,

        term: runtimeMeta.term || null,
        term_label: runtimeMeta.term ? termLabel(runtimeMeta.term) : null,

        started_at: new Date().toISOString()
      };

      console.log("[exam-core] Sending exam_start notification:", notifyBody);

      const notificationResponse = await fetch("/api/notifications/notify/exam_start", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json"
        },
        body: JSON.stringify(notifyBody)
      });

      const notificationResult = await notificationResponse.json().catch(() => ({}));

      if (!notificationResponse.ok) {
        console.error(
          "[exam-core] exam_start notification rejected:",
          notificationResponse.status,
          notificationResult
        );
      } else {
        console.log(
          "[exam-core] exam_start notification sent:",
          notificationResult
        );
      }

    } catch (notificationError) {
      console.error(
        "[exam-core] Failed to send exam_start notification:",
        notificationError
      );
    }

    // ==================================================
    // SHOW ACTIVE EXAM CONTROLS
    // ==================================================

    const timerBlock = $("#examTimer");
    const fullscreenBtn = $("#fullscreenBtn");
    const studentBlock = $(".exam-topbar-student");

    if (timerBlock) timerBlock.classList.remove("hidden");
    if (fullscreenBtn) fullscreenBtn.classList.remove("hidden");
    if (studentBlock) studentBlock.classList.remove("hidden");

    console.log(
      "[exam-core] Exam started successfully:",
      window.__loadedExamJSONUrl
    );

  } catch (error) {
    console.error(
      "[exam-core] startExam error:",
      error
    );

    window.examStarted = false;
    window.examStartTime = null;

    if (window.examTimer) {
      clearInterval(window.examTimer);
      window.examTimer = null;
    }

    document.body.classList.remove("exam-started");

    const examInterface = $("#examInterface");
    if (examInterface) examInterface.classList.add("hidden");

    const modal = $("#instructionsModal");
    if (modal) {
      modal.classList.remove("hidden");
      modal.style.display = "";
    }

    examFlash(
      "Unable to start exam. Contact admin.",
      "danger"
    );

  } finally {
    if (loadingOverlay) loadingOverlay.classList.add("hidden");
  }
};


// ======================================================
// FLAG QUESTION
// ======================================================

window.toggleFlag = function () {
  const questionIndex = window.currentQuestionIndex;

  if (
    questionIndex === null ||
    questionIndex === undefined
  ) {
    return;
  }

  if (window.flaggedQuestions.has(questionIndex)) {
    window.flaggedQuestions.delete(questionIndex);

    updateFlagUI(false);
    updateQuestionNavigation();

    examFlash(
      "Flag removed.",
      "info"
    );

    return;
  }

  window.flaggedQuestions.add(questionIndex);

  updateFlagUI(true);
  updateQuestionNavigation();

  examFlash(
    "🚩 Question flagged for review.",
    "success"
  );
};


// ======================================================
// FLAG UI
// ======================================================

function updateFlagUI(isFlagged) {
  const button = document.getElementById("flagBtn");
  const text = document.getElementById("flagText");

  if (!button || !text) {
    return;
  }

  button.classList.toggle(
    "flagged",
    Boolean(isFlagged)
  );

  text.textContent =
    isFlagged
      ? "Flagged"
      : "Flag";
}


// ======================================================
// DOM READY
// ======================================================

document.addEventListener("DOMContentLoaded", () => {
  const runtimeMeta = getExamRuntimeMeta(
    getMetaContent("exam-subject"),
    getMetaContent(
      "student-class-level",
      "student-class-category"
    )
  );

  console.log(
    "[exam-core] Page metadata:",
    runtimeMeta
  );

  const startButton = $("#startExamBtn");

  if (startButton) {
    startButton.addEventListener(
      "click",
      window.startExam
    );
  }
});


// ======================================================
// KEYBOARD NAVIGATION
// ======================================================

document.addEventListener("keydown", (event) => {
  if (!window.examStarted || window.__examFinished) return;

  // Section B is display-only, so disable objective arrow navigation here.
  if (window.examSection === "essay") return;

  const tag = String(event.target?.tagName || "").toUpperCase();

  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

  const realQuestions = window.realQuestionIndices;

  if (!realQuestions?.length) return;

  const position = realQuestions.indexOf(window.currentQuestionIndex);

  if (event.key === "ArrowLeft") {
    event.preventDefault();
    previousQuestion();
    return;
  }

  if (event.key === "ArrowRight") {
    event.preventDefault();

    if (position < realQuestions.length - 1) {
      nextQuestion();
    }
  }
});
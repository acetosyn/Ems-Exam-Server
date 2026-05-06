// ======================================================
// exam-core.js — MERGED FINAL CBT ENGINE (2025 v12)
// - Pure CBT engine (no anti-cheat; handled by exam-realtime.js)
// - Restores clocks/hourglass/topbar
// - Modern subject title with REAL question count
// - Timer warnings (20, 10, 5 mins) + blinking < 60s
// - No internal shuffling (shuffle.js handles that)
// - English-style SECTION instructions shown as cards
//   (not numbered, not in nav, not counted)
// ======================================================

console.log("[exam-core] MERGED CBT ENGINE v12 LOADED");

// ------------------------------------------------------
// GLOBAL STATE
// ------------------------------------------------------
window.examData             = null;   // full JSON
window.currentQuestionIndex = 0;      // index in examData.questions (real question)
window.userAnswers          = {};     // keyed by QUESTION INDEX (0-based)
window.lockedQuestions      = new Set(); // indexes
window.flaggedQuestions     = new Set();
window.examTimer            = null;
window.timeRemaining        = 0;
window.initialTimeAllowed   = 0;      // for warning thresholds
window.examStarted          = false;
window.examStartTime        = null;
window.__examFinished       = false;
window.__timeExpired        = false;
window.__reviewBlocked      = false;

// Only REAL questions (no instructions) — array of indices
window.realQuestionIndices  = [];

// For each question index i → section instruction meta
// { title, body, raw }
window.sectionInstructions  = {};

const SS_KEY       = "emis_exam_progress";
const LS_RELOADS   = "emis_exam_reload_count";
const LS_EXAM_LOCK = "emis_exam_lock_active";

// Timer warning flags (20, 10, 5 mins)
let __warn20Shown = false;
let __warn10Shown = false;
let __warn5Shown  = false;

// ------------------------------------------------------
// HELPERS
// ------------------------------------------------------
function $(s, r = document) { return r.querySelector(s); }
function $$(s, r = document) { return [...r.querySelectorAll(s)]; }

function formatTime(sec){
  const safe = Math.max(0, sec | 0);
  const m = Math.floor(safe / 60).toString().padStart(2, "0");
  const s = (safe % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// Optional flash helper (uses #examFlash or #flashMessage if present)
// ------------------------------------------------------
// SAFE EXAM FLASH — NO ALERT (ANTI-CHEAT FRIENDLY)
// ------------------------------------------------------
function examFlash(message, type = "info") {
  let flashEl =
    document.getElementById("examFlashMessage") ||
    document.getElementById("examFlash") ||
    document.getElementById("flashMessage");

  // --------------------------------------------------
  // Auto-create flash container if missing (SAFE)
  // --------------------------------------------------
  if (!flashEl) {
    flashEl = document.createElement("div");
    flashEl.id = "examFlash";
    flashEl.className = "exam-flash";
    flashEl.setAttribute("aria-hidden", "true");
    document.body.appendChild(flashEl);
  }

  // --------------------------------------------------
  // Set message & style
  // --------------------------------------------------
  flashEl.textContent = message;

  // Reset classes first
  flashEl.classList.remove(
    "exam-flash-info",
    "exam-flash-success",
    "exam-flash-warning",
    "exam-flash-danger",
    "show"
  );

  // Apply type class
  flashEl.classList.add(`exam-flash-${type}`, "show");

  // 🔒 CRITICAL: prevent click / focus / anti-cheat strike
  flashEl.style.pointerEvents = "none";

  // --------------------------------------------------
  // Auto-dismiss (no interaction)
  // --------------------------------------------------
  setTimeout(() => {
    flashEl.classList.remove("show");
  }, 2600);
}

// Parse instruction text into {title, body, raw}
// e.g. "SECTION 3:\nChoose the interpretation..." ->
//   title: "SECTION 3"
//   body:  "Choose the interpretation..."
function parseInstructionText(text) {
  if (!text) return null;

  const lines = text.split(/\r?\n+/);
  let title = (lines[0] || "").trim();
  // strip trailing colon
  title = title.replace(/\s*[:：]\s*$/, "");

  const body = lines.slice(1).join(" ").trim();

  return {
    title,
    body,
    raw: text
  };
}

// For future use if needed
function getCorrectIndex(q){
  if (typeof q.correctIndex === "number") return q.correctIndex;
  if (q.correctOption){
    return q.correctOption.trim().toUpperCase().charCodeAt(0) - 65;
  }
  return -1;
}

// ------------------------------------------------------
// NORMALIZE SUBJECT NAME (FULL MAP FOR ALL 13 SUBJECTS)
// ------------------------------------------------------
function normalizeSubjectName(subject){
  subject = subject.toLowerCase().trim();

  const map = {
    // 1. BIOLOGY
    "biology": "biology",

    // 2. CHEMISTRY
    "chemistry": "chemistry",

    // 3. CIVIC EDUCATION
    "civic education": "civic",
    "civic": "civic",

    // 4. COMPUTER SCIENCE
    "computer science": "computer_science",
    "computer studies": "computer_science",
    "computer": "computer_science",

    // 5. ECONOMICS
    "economics": "economics",

    // 6. ENGLISH LANGUAGE
    "english language": "english",
    "english": "english",

    // 7. FINANCIAL ACCOUNTING
    "financial accounting": "accounts",
    "accounting": "accounts",

    // 8. GEOGRAPHY
    "geography": "geography",

    // 9. GOVERNMENT
    "government": "government",

    // 10. LITERATURE-IN-ENGLISH
    "literature-in-english": "literature",
    "literature in english": "literature",
    "literature": "literature",

    // 11. MATHEMATICS
    "mathematics": "mathematics",
    "maths": "mathematics",

    // 12. PHYSICS
    "physics": "physics",

    // 13. TECHNICAL DRAWING
    "technical drawing": "technical",
    "technical": "technical"
  };

  return map[subject] || subject.replace(/\s+/g, "");
}

// ------------------------------------------------------
// RESOLVE JSON PATH — NOW INCLUDES YEAR FOLDER
// ------------------------------------------------------
function resolveExamJSON(subject, classCategory){
  const subjectKey = normalizeSubjectName(subject);  // english → english
  const cls        = classCategory.toUpperCase();    // SS1
  const clsLower   = classCategory.toLowerCase();    // ss1

  // Read YEAR passed from exam.html <meta>
  const yearMeta = document.querySelector('meta[name="exam-year"]');
  const year = yearMeta ? yearMeta.content : new Date().getFullYear();

  // NEW correct path:
  return `/static/subjects/${year}/subjects-json/${cls}/${subjectKey}_${clsLower}.json`;
}

// ------------------------------------------------------
// LOAD EXAM DATA (QUIET MODE FOR startExam)
// ------------------------------------------------------
window.loadExamData = async function (quiet = false) {
  try {
    const subjectMeta = $('meta[name="exam-subject"]');
    const classMeta   = $('meta[name="student-class"]');

    if (!subjectMeta || !classMeta) {
      throw new Error("Missing subject/class metadata.");
    }

    const subject       = subjectMeta.content;
    const classCategory = classMeta.content;
    const jsonURL       = resolveExamJSON(subject, classCategory);

    console.log("📥 Loading Exam JSON:", jsonURL);

    const res = await fetch(jsonURL, { cache: "no-store" });
    if (!res.ok) throw new Error("Exam JSON not found");

    let rawData = await res.json();

    // KEEP FULL STRUCTURE
    rawData.questions = (rawData.questions || []).map((q, idx) => {
      let rawCorrect =
        q.correctOption ||
        q.correct_option ||
        q.answer ||
        null;

      let ci = -1;
      if (rawCorrect) {
        ci = rawCorrect.toString().trim().toUpperCase().charCodeAt(0) - 65;
      }

      return {
        id:            q.id ?? idx,
        question:      q.question,
        options:       q.options || [],
        diagram:       q.diagram || null,
        passage:       q.passage || null,
        isInstruction: !!q.isInstruction,
        correctIndex:  ci
      };
    });

    // Shuffle externally-controlled
    window.examData = shuffleQuestions(rawData);

    // ------------------------------------------------------
    // 1️⃣ Compute REAL QUESTIONS (no instructions)
    //     FIXED: handles Literature options safely
    // ------------------------------------------------------
    window.realQuestionIndices = [];
    window.examData.questions.forEach((q, i) => {

      // Detect if options actually contain visible text
      const hasOptions =
        Array.isArray(q.options) &&
        q.options.some(opt => opt && opt.toString().trim() !== "");

      if (!q.isInstruction && hasOptions) {
        window.realQuestionIndices.push(i);
      }
    });

    // ------------------------------------------------------
    // 2️⃣ Compute SECTION INSTRUCTIONS per real question
    // ------------------------------------------------------
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

    // Update subject title
    const st = $("#examSubjectTitle");
    if (st) {
      st.innerHTML = `
        <span class="exam-subject-pill">${subject.toUpperCase()}</span>
        <span class="exam-question-count">• ${totalReal} QUESTION${totalReal === 1 ? "" : "S"}</span>
      `;
      st.classList.remove("hidden");
    }

    const totalQEl = $("#totalQuestions");
    if (totalQEl) totalQEl.textContent = totalReal;

    // Timer setup
    window.timeRemaining      = (rawData.time_allowed_minutes || 60) * 60;
    window.initialTimeAllowed = window.timeRemaining;
    __warn20Shown = __warn10Shown = __warn5Shown = false;

    const td = $("#timerDisplay");
    if (td) td.textContent = formatTime(window.timeRemaining);

    // Load FIRST real question
    if (window.realQuestionIndices.length > 0) {
      loadQuestion(window.realQuestionIndices[0]);
    }

    updateProgress();
    updateQuestionNavigation();

  } catch (err) {
    console.error("❌ loadExamData error:", err);
    if (!quiet) alert("Unable to load exam. Contact admin.");
    throw err;
  }
};

// ------------------------------------------------------
// PROGRESS — counts ONLY real questions
// ------------------------------------------------------
window.updateProgress = function () {
  const total = window.realQuestionIndices.length;

  // userAnswers is keyed by QUESTION INDEX (0-based)
  const answered = window.realQuestionIndices.filter(i => !!window.userAnswers[i]).length;

  const pct = total ? (answered / total) * 100 : 0;

  $("#answeredCount").textContent  = answered;
  $("#remainingCount").textContent = total - answered;
  $("#progressBar").style.width    = `${pct}%`;
  $("#progressText").textContent   = `${Math.round(pct)}% Complete`;
};

// ------------------------------------------------------
// NAVIGATION BUTTONS — last real question submits
// ------------------------------------------------------
window.updateNavigationButtons = function () {
  const prev = $("#prevBtn");
  const next = $("#nextBtn");

  if (!window.realQuestionIndices || window.realQuestionIndices.length === 0) return;

  const firstRealIndex = window.realQuestionIndices[0];
  const lastRealIndex  = window.realQuestionIndices[window.realQuestionIndices.length - 1];

  if (prev) {
    prev.disabled = (window.currentQuestionIndex === firstRealIndex);
  }

  if (next) {
    const last = (window.currentQuestionIndex === lastRealIndex);
    next.textContent = last ? "Submit" : "Next →";
  }
};

// ------------------------------------------------------
// QUESTION NAVIGATION — show ONLY real questions
// ------------------------------------------------------
window.updateQuestionNavigation = function () {
  const grid = $("#questionGrid");
  if (!grid || !window.examData) return;

  let html = "";

  window.realQuestionIndices.forEach((trueIndex, pos) => {
    const active   = (trueIndex === window.currentQuestionIndex) ? "active"   : "";
    const answered = window.userAnswers[trueIndex]               ? "answered" : "";

    html += `
      <button class="question-nav-btn ${active} ${answered}" data-q-index="${trueIndex}">
        ${pos + 1}
      </button>
    `;
  });

  grid.innerHTML = html;

  $$(".question-nav-btn", grid).forEach(btn => {
    btn.onclick = () => loadQuestion(Number(btn.dataset.qIndex));
  });
};

// ------------------------------------------------------
// END EXAM — counts ONLY real questions
// ------------------------------------------------------
window.endExam = function () {
  if (!window.examData) return;

  const total    = window.realQuestionIndices.length;
  const answered = window.realQuestionIndices.filter(i => !!window.userAnswers[i]).length;

  const msgEl = $("#endExamMessage");
  if (msgEl) {
    msgEl.innerHTML = `
      You answered <b>${answered}</b> out of <b>${total}</b>.<br>
      Unanswered will be marked incorrect.<br><br>
      Are you sure you want to end?
    `;
  }

  const modal = $("#endExamModal");
  if (modal) modal.classList.remove("hidden");
};

window.closeEndExam = () => {
  const modal = $("#endExamModal");
  if (modal) modal.classList.add("hidden");
};

// ------------------------------------------------------
// SUBMIT EXAM — now sends RAW SCORE + FLAGGED QUESTIONS
// ------------------------------------------------------
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
    if (ua && ua.index === q.correctIndex) correct++;
  });

  const answered  = realIndices.filter(i => !!window.userAnswers[i]).length;
  const incorrect = total - correct;
  const skipped   = total - answered;

  // ------------------------------------------------------
  // ⭐ RAW SCORE
  // ------------------------------------------------------
  const rawScore = correct;

  // ------------------------------------------------------
  // 🚩 COLLECT FLAGGED QUESTIONS (NEW)
  // ------------------------------------------------------
  const flaggedQuestionsDetailed = [...window.flaggedQuestions].map(i => {
    const q = window.examData.questions[i];
    return {
      index: i,
      question_id: q.id,
      question: q.question
    };
  });

  const payload = {
    subject: $('meta[name="exam-subject"]').content.trim().toUpperCase(),
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

  // ---------------------------------------------
  // 🔔 REAL-TIME NOTIFICATION: Exam End
  // ---------------------------------------------
  try {
    const notifyBody = {
      student_name: document.querySelector('meta[name="student-name"]')?.content || "",
      admission_number: document.querySelector('meta[name="student-admission"]')?.content || "",
      class_category: document.querySelector('meta[name="student-class"]')?.content || "",
      subject: payload.subject,
      score: rawScore,
      total_questions: total,
      flagged: flaggedQuestionsDetailed.length,
      year: document.querySelector('meta[name="exam-year"]')?.content || "",
      submitted_at: payload.submittedAt,
      status: payload.status
    };

    await fetch("/api/notifications/notify/exam_end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(notifyBody)
    });

  } catch (err) {
    console.error("❌ Failed to send exam_end notification:", err);
  }

  // ---------------------------------------------
  // 🔵 NORMAL SUBMISSION TO FLASK
  // ---------------------------------------------
  await fetch("/submit_exam", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  location.replace("/result");
};


// ------------------------------------------------------
// LOAD SINGLE QUESTION  (REAL QUESTION NUMBERING + SECTION CARD)
// ------------------------------------------------------
window.loadQuestion = function (i) {
  if (!window.examData) return;
  if (i < 0 || i >= window.examData.questions.length) return;

  const q = window.examData.questions[i];

  // Prevent loading pure instruction blocks
  if (q.isInstruction) {
    const nextReal = window.realQuestionIndices.find(r => r > i);
    if (nextReal !== undefined) {
      return loadQuestion(nextReal);
    }
    return;
  }

  // Set current question index
  window.currentQuestionIndex = i;

  // ------------------------------------------------------
  // 🚩 SYNC FLAG BUTTON STATE (NEW)
  // ------------------------------------------------------
  if (typeof updateFlagUI === "function") {
    updateFlagUI(window.flaggedQuestions.has(i));
  }

  // ------------------------------------------------------
  // REAL QUESTION NUMBER (1-based)
  // ------------------------------------------------------
  const pos = window.realQuestionIndices.indexOf(i);
  if (pos !== -1) {
    $("#currentQuestionNumber").textContent = pos + 1;
  }

  const prev   = window.userAnswers[i]?.index;
  const locked = window.lockedQuestions.has(i);

  // 🔹 Remove "A." / "B." prefixes from JSON
  function stripLabel(text) {
    return text.replace(/^[A-Da-d][\.\)\-:\s]+/, "").trim();
  }

  function applyHighlight(text) {
    if (!text) return text;
    return text.replace(/\*(.+?)\*/g, `<span class="focus-word">$1</span>`);
  }

  function convertBlanks(text) {
    if (!text) return text;
    return text.replace(/_{3,}\s*(\d+)/g, (_, num) =>
      `<span class="gap">${num}</span>`
    );
  }

  // ------------------------------------------------------
  // PASSAGE BLOCK (FOR English + NON-instruction Literature)
  // ------------------------------------------------------
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

  // ------------------------------------------------------
  // SECTION INSTRUCTION CARD — WITH LITERATURE FIX
  // ------------------------------------------------------
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

  // ------------------------------------------------------
  // DIAGRAM RENDERING
  // ------------------------------------------------------
  let diagramHTML = "";
  if (q.diagram) {
    diagramHTML = `
      <div class="question-diagram mb-4">
        <img src="${q.diagram}" class="diagram-img"
             style="max-width:100%; border-radius:6px;">
      </div>
    `;
  }

  // ------------------------------------------------------
  // OPTIONS RENDERING
  // ------------------------------------------------------
  const optionsHTML = (q.options || []).map((opt, idx) => {
    const cleanOpt = stripLabel(opt);
    const letter   = String.fromCharCode(65 + idx);

    const selected = prev === idx ? "selected" : "";
    const dis      = locked ? "disabled" : "";

    return `
      <button class="option-btn ${selected}" data-option-index="${idx}" ${dis}>
        <span class="option-letter">${letter}</span>
        ${applyHighlight(cleanOpt)}
      </button>
    `;
  }).join("");

  // ------------------------------------------------------
  // RENDER QUESTION CARD
  // ------------------------------------------------------
  $("#questionContent").innerHTML = `
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

  // Bind option selection
  $$(".option-btn").forEach(btn => {
    btn.onclick = () => selectOption(Number(btn.dataset.optionIndex));
  });

  updateNavigationButtons();
  updateQuestionNavigation();
};


// ------------------------------------------------------
// SELECT OPTION — keyed by QUESTION INDEX
// ------------------------------------------------------
window.selectOption = function(idx){
  const qIndex = window.currentQuestionIndex;
  const q      = window.examData.questions[qIndex];

  if (window.lockedQuestions.has(qIndex)) return;

  const correct   = q.correctIndex;
  const isCorrect = (idx === correct);

  window.userAnswers[qIndex] = { index: idx, correct: isCorrect };
  window.lockedQuestions.add(qIndex);

  $$(".option-btn").forEach(btn => {
    btn.disabled = true;
    btn.classList.toggle(
      "selected",
      Number(btn.dataset.optionIndex) === idx
    );
  });

  updateProgress();
  updateQuestionNavigation();

  // Auto-next after a short delay
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

// ------------------------------------------------------
// NAVIGATION — move ONLY through real questions
// ------------------------------------------------------
window.previousQuestion = function(){
  if (!window.realQuestionIndices || window.realQuestionIndices.length === 0) return;

  const pos = window.realQuestionIndices.indexOf(window.currentQuestionIndex);
  if (pos > 0) {
    const prevIndex = window.realQuestionIndices[pos - 1];
    loadQuestion(prevIndex);
  }
};

window.nextQuestion = function(){
  if (!window.realQuestionIndices || window.realQuestionIndices.length === 0) return;

  const pos = window.realQuestionIndices.indexOf(window.currentQuestionIndex);
  if (pos < window.realQuestionIndices.length - 1) {
    const nextIndex = window.realQuestionIndices[pos + 1];
    loadQuestion(nextIndex);
  } else {
    submitExam(false);
  }
};

// ------------------------------------------------------
// TIMER — with warnings & blinking < 60s
// ------------------------------------------------------
window.startTimer = function(){
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

    const t    = window.timeRemaining;
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

// ------------------------------------------------------
// START EXAM  — Stable layout + clocks/hourglass visible
// ------------------------------------------------------
window.startExam = async function(){
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

    const timerBlock   = $("#examTimer");
    const fullscreenBtn = $("#fullscreenBtn");
    const studentBlock  = $(".exam-topbar-student");

    if (timerBlock)   timerBlock.classList.remove("hidden");
    if (fullscreenBtn) fullscreenBtn.classList.remove("hidden");
    if (studentBlock)  studentBlock.classList.remove("hidden");

  } catch (err) {
    console.error("❌ startExam error:", err);
    alert("Unable to start exam. Contact admin.");
  }
};

// ------------------------------------------------------
// DOM READY
// ------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const startBtn = $("#startExamBtn");
  if (startBtn) {
    startBtn.addEventListener("click", () => {
      window.startExam();
    });
  }
});



// ------------------------------------------------------
// FLAG QUESTION — SAFE, NON-INTRUSIVE, ANTI-CHEAT FRIENDLY
// ------------------------------------------------------
window.toggleFlag = function () {
  const qIndex = window.currentQuestionIndex;
  if (qIndex == null) return;

  // Prevent multiple flag toggles per question
  if (window.flaggedQuestions.has(qIndex)) {
    examFlash("⚠️ This question is already flagged.", "info");
    return;
  }

  // Store flag
  window.flaggedQuestions.add(qIndex);

  // Visual update
  updateFlagUI(true);

  // SAFE in-page notification
  examFlash(
    "🚩 Your teacher has been notified of this question.",
    "success"
  );

  // Optional: auto-reset button text after flash
  setTimeout(() => {
    updateFlagUI(false);
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



// ------------------------------------------------------
// KEYBOARD NAVIGATION — ← PREV | → NEXT (ANTI-CHEAT SAFE)
// ------------------------------------------------------
document.addEventListener("keydown", (e) => {

  // Only when exam is active
  if (!window.examStarted || window.__examFinished) return;

  // Do NOT hijack typing inside inputs / textareas
  const tag = e.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;

  const real = window.realQuestionIndices;
  if (!real || !real.length) return;

  const pos = real.indexOf(window.currentQuestionIndex);

  // LEFT ARROW → Previous Question (always allowed)
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    window.previousQuestion();
  }

  // RIGHT ARROW → Next Question (BLOCK on last question)
  if (e.key === "ArrowRight") {
    e.preventDefault();

    // 🚫 If this is the LAST real question → do NOTHING
    if (pos === real.length - 1) {
      return; // stay on last question
    }

    window.nextQuestion();
  }
});

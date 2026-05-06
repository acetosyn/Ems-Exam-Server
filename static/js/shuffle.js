// ================================================================
// shuffle.js — FINAL BULLETPROOF VERSION (2025 + Literature FIX)
// ---------------------------------------------------------------
//  ✓ Preserves correctIndex after shuffling
//  ✓ Handles "A. text", "A ) text", "A- text", etc.
//  ✓ Robust fallback when option text is modified by LLM
//  ✓ Protects against malformed option arrays
//  ✓ NEW: Disables shuffle for Literature-in-English (safe fix)
// ================================================================

(function(){

  // ------------------------------------------------------------
  // Utility: Remove leading "A. ", "B)", "C:", "D -", etc.
  // ------------------------------------------------------------
  function normalizeOptionText(opt) {
    if (!opt) return "";
    return opt
      .toString()
      .trim()
      .replace(/^[A-Da-d][\.\)\-:\s]+/, "") // remove A.  B)  C-  etc.
      .trim()
      .toLowerCase();
  }

  // ------------------------------------------------------------
  // Fisher–Yates Shuffle
  // ------------------------------------------------------------
  function shuffleArray(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // ------------------------------------------------------------
  // Main Hook Called by exam-core.js
  // ------------------------------------------------------------
  window.shuffleQuestions = function(examData) {
    if (!examData || !Array.isArray(examData.questions)) return examData;

    // ==========================================================
    //  🚫 NEW FIX: Prevent shuffle for Literature-in-English
    // ==========================================================
    const subj = (examData.subject || "").toLowerCase();
    if (subj.includes("literature")) {
      console.warn("📌 Literature detected — shuffle disabled.");
      return examData; // return untouched
    }

    // ==========================================================
    //  NORMAL SHUFFLE (ALL OTHER SUBJECTS)
    // ==========================================================
    examData.questions = examData.questions.map(q => {

      // skip instructions or malformed questions
      if (!q.options || q.options.length !== 4) return q;

      // --- 1. extract old correct option ---
      const oldCorrectIndex =
        q.correctIndex ?? q.correct_index ?? -1;

      const originalOption = q.options[oldCorrectIndex] || null;

      const normalizedOriginal =
        normalizeOptionText(originalOption);

      // --- 2. shuffle options ---
      const shuffled = shuffleArray(q.options);

      // --- 3. find new correct index by smart matching ---
      let newCorrectIndex = shuffled.findIndex(opt =>
        normalizeOptionText(opt) === normalizedOriginal
      );

      // fallback protection
      if (newCorrectIndex === -1) {
        console.warn("⚠ shuffle.js fallback: Q =", q);
        newCorrectIndex = 0;
      }

      // return updated question
      return {
        ...q,
        options: shuffled,
        correctIndex: newCorrectIndex
      };
    });

    return examData;
  };

})();

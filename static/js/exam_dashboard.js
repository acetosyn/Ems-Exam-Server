// =============================================================
// EMIS EXAM DASHBOARD JS — Typewriter + Validation + Flash + Modal
// =============================================================

document.addEventListener("DOMContentLoaded", () => {

  // -----------------------------------------------------------
  // 1. TYPEWRITER BANNER
  // -----------------------------------------------------------
  const typeTarget = document.getElementById("typewriter");

  if (typeTarget) {
    const lines = [
      "Welcome to your EMIS Exam Portal",
      "Read instructions carefully before starting",
      "Your progress is auto-saved"
    ];

    let index = 0;
    let char = 0;

    function typeLine() {
      if (char < lines[index].length) {
        typeTarget.textContent += lines[index][char];
        char++;
        setTimeout(typeLine, 50);
      } else {
        setTimeout(() => {
          typeTarget.textContent = "";
          char = 0;
          index = (index + 1) % lines.length;
          typeLine();
        }, 1500);
      }
    }

    typeLine();
  }


  // -----------------------------------------------------------
  // 2. FLASH BAR + EXAM AVAILABLE FLAG
  // -----------------------------------------------------------
  const flashBar = document.getElementById("flashBar");

  function flash(msg, type = "red") {
    if (!flashBar) {
      alert(msg);
      return;
    }
    flashBar.textContent = msg;
    flashBar.className = "flash-bar show flash-" + type;

    setTimeout(() => {
      flashBar.classList.remove("show");
    }, 2600);
  }

  // ⭐ Correct way: read from HTML attribute
  let examAvailable = false;
  if (flashBar && flashBar.dataset.examAvailable) {
    examAvailable = flashBar.dataset.examAvailable === "true";
    console.log("[exam-dashboard] examAvailable =", examAvailable);
  }


  // -----------------------------------------------------------
  // 3. SUPPORT MODAL
  // -----------------------------------------------------------
  const supportModal = document.getElementById("supportModal");
  const openSupport = document.getElementById("openSupport");
  const closeSupport = document.getElementById("closeSupport");
  const dismissSupport = document.getElementById("dismissSupport");

  function showSupport() {
    supportModal?.classList.remove("hidden");
  }

  function hideSupport() {
    supportModal?.classList.add("hidden");
  }

  openSupport?.addEventListener("click", showSupport);
  closeSupport?.addEventListener("click", hideSupport);
  dismissSupport?.addEventListener("click", hideSupport);


  // -----------------------------------------------------------
  // 4. STATUS PILL ANIMATION
  // -----------------------------------------------------------
  const pill = document.querySelector(".status-pill");
  if (pill) {
    pill.style.transition = "transform 0.3s ease, opacity 0.3s ease";
    pill.style.transform = "scale(1.05)";
    pill.style.opacity = "0.9";
    setTimeout(() => {
      pill.style.transform = "scale(1)";
      pill.style.opacity = "1";
    }, 350);
  }

// -----------------------------------------------------------
// 5. EXAM START VALIDATION + MODAL LOGIC + NOTIFICATION
// -----------------------------------------------------------
const openExamModal = document.getElementById("openExamModal");
const examStartModal = document.getElementById("examStartModal");
const closeExamModal = document.getElementById("closeExamModal");

// Read student data from meta tags
const metaStudentName     = document.querySelector('meta[name="student-name"]')?.content || "";
const metaAdmissionNumber = document.querySelector('meta[name="student-admission"]')?.content || "";
const metaStudentClass    = document.querySelector('meta[name="student-class"]')?.content || "";
const metaSubject         = document.querySelector('meta[name="student-subject"]')?.content || "";
const metaYear            = document.querySelector('meta[name="exam-year"]')?.content || "";

openExamModal?.addEventListener("click", async () => {

  if (!examAvailable) {
    flash("❌ This exam is not available. Contact your teacher or admin.", "red");
    return;
  }

  flash("✔ Loading exam…", "green");

  // -----------------------------------------------------
  // 🔔 REAL-TIME NOTIFICATION: Exam Start Trigger
  // -----------------------------------------------------
  try {
    console.log("[notify] Sending exam_start notification…");

    await fetch("/api/notifications/notify/exam_start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_name:     metaStudentName,
        admission_number: metaAdmissionNumber,
        class_category:   metaStudentClass,
        subject:          metaSubject,
        year:             metaYear
      })
    });

  } catch (err) {
    console.error("❌ Exam start notification failed:", err);
  }

  // Open the modal after short delay
  setTimeout(() => {
    examStartModal?.classList.remove("hidden");
  }, 700);
});

// Close modal buttons
closeExamModal?.addEventListener("click", () => {
  examStartModal?.classList.add("hidden");
});

examStartModal?.addEventListener("click", (e) => {
  if (e.target === examStartModal) {
    examStartModal.classList.add("hidden");
  }
});
});
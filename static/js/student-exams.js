document.addEventListener("DOMContentLoaded", () => {

    const examModal = document.getElementById("examModal");
    const subjectDropdown = document.getElementById("subjectDropdown");
    const startBtn = document.getElementById("startExamBtn");
    const closeBtn = document.getElementById("closeExamModal");
    const refreshBtn = document.getElementById("refreshSubjectsBtn");

    // --- OPEN EXAM PORTAL MODAL ---
    const examPortalBtn = document.getElementById("openExamPortal");
    if (examPortalBtn) {
        examPortalBtn.addEventListener("click", () => {
            examModal.classList.add("show");
        });
    }

    // --- CLOSE MODAL ---
    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
            examModal.classList.remove("show");
        });
    }

    // --- ENABLE START BUTTON WHEN SUBJECT SELECTED ---
    if (subjectDropdown) {
        subjectDropdown.addEventListener("change", () => {
            startBtn.disabled = subjectDropdown.value === "";
        });
    }

    // --- START EXAM ---
    if (startBtn) {
        startBtn.addEventListener("click", () => {
            if (!subjectDropdown.value) return;

            fetch("/students/set_subject", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ subject: subjectDropdown.value })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "ok") {
                    window.location.href = "/students/start_exam";
                }
            });
        });
    }

    // --- REFRESH SUBJECTS BUTTON ---
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {

            fetch("/students/get_subjects")
                .then(res => res.json())
                .then(data => {

                    if (!data.subjects) return;

                    // Reset dropdown
                    subjectDropdown.innerHTML = `<option value="">-- Select Subject --</option>`;

                    data.subjects.forEach(sub => {
                        const opt = document.createElement("option");
                        opt.value = sub;
                        opt.textContent = sub;
                        subjectDropdown.appendChild(opt);
                    });

                });
        });
    }

});

// ===============================================
// EMIS Student Login JS — FINAL FIXED VERSION
// ===============================================

document.addEventListener("DOMContentLoaded", () => {

    const loginForm = document.getElementById("studentLoginForm");
    const loginBtn  = document.querySelector(".login-btn");
    const btnText   = document.querySelector(".btn-text");
    const btnSpinner = document.querySelector(".loading-spinner");
    const loadingOverlay = document.getElementById("loadingOverlay");

    if (!loginForm || !loginBtn) return;

    loginForm.addEventListener("submit", async () => {

        // ----------------------------------------------------
        // UI LOADING ANIMATION
        // ----------------------------------------------------
        loginBtn.disabled = true;
        loginBtn.classList.add("loading");
        btnText.classList.add("hidden");
        btnSpinner.classList.remove("hidden");
        loadingOverlay.classList.remove("hidden");

        // ----------------------------------------------------
        // 🔔 SEND REAL LOGIN NOTIFICATION TO BACKEND
        // ----------------------------------------------------
        try {
            const admission = document.querySelector("input[name='admission_number']")?.value.trim() || "";
            const firstName = document.querySelector("input[name='first_name']")?.value.trim() || "";

            if (admission !== "" && firstName !== "") {

                // The correct backend endpoint is now:
                // POST /api/notifications/notify/login
                fetch("/api/notifications/notify/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        student_name: firstName,
                        admission_number: admission,
                        class_category: ""   // (optional, student has not been validated yet)
                    })
                });
            }

        } catch (err) {
            console.error("Login notification error:", err);
        }

        // ----------------------------------------------------
        // DO NOT prevent form submission — Flask handles login
        // ----------------------------------------------------
    });

});

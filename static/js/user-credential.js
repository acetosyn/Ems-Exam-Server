/* user-credential.js
   Handles dynamic popup for generated user credentials
*/

(() => {
  if (window.__USER_CREDENTIALS_INIT__) return;
  window.__USER_CREDENTIALS_INIT__ = true;

  const ready = (cb) =>
    document.readyState !== "loading"
      ? cb()
      : document.addEventListener("DOMContentLoaded", cb);

  // ---------------- Popup UI ----------------
  function showCredentials(creds) {
    const overlay = document.createElement("div");
    overlay.className = "cred-overlay";

    const modal = document.createElement("div");
    modal.className = "cred-modal scale-in";

    modal.innerHTML = `
      <div class="cred-head">
        <h3>Generated Credentials</h3>
        <button class="cred-close" aria-label="Close">&times;</button>
      </div>
      <div class="cred-body">
        ${creds
          .map(
            (c) => `
          <div class="cred-card">
            <div class="cred-row">
              <span class="cred-label">Username:</span>
              <span class="cred-value">${c.username}</span>
              <button class="cred-copy" data-value="${c.username}">📋</button>
            </div>
            <div class="cred-row">
              <span class="cred-label">Password:</span>
              <span class="cred-value cred-pass hidden">${c.password}</span>
              <span class="cred-dots">•••••</span>
              <button class="cred-toggle">👁</button>
              <button class="cred-copy" data-value="${c.password}">📋</button>
            </div>
          </div>
        `
          )
          .join("")}
      </div>
      <div class="cred-foot">
        <button class="cred-close-btn">Close</button>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close logic
    modal.querySelectorAll(".cred-close, .cred-close-btn").forEach((btn) =>
      btn.addEventListener("click", () => overlay.remove())
    );

    // Copy buttons
    modal.querySelectorAll(".cred-copy").forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-value");
        navigator.clipboard.writeText(val).then(() => {
          btn.textContent = "✅";
          setTimeout(() => (btn.textContent = "📋"), 1000);
        });
      });
    });

    // Toggle password visibility
    modal.querySelectorAll(".cred-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const row = btn.closest(".cred-row");
        const passEl = row.querySelector(".cred-pass");
        const dotsEl = row.querySelector(".cred-dots");
        const isHidden = passEl.classList.contains("hidden");

        passEl.classList.toggle("hidden", !isHidden);
        dotsEl.classList.toggle("hidden", isHidden);
      });
    });
  }

  // Expose globally so admin2.js can reuse it
  window.showCredentials = showCredentials;

  // ---------------- API Call ----------------
  async function requestCredentials(count = 1) {
    try {
      console.log(`▶️ Requesting ${count} credential(s)...`);

      const response = await fetch("/generate_credentials", {
        method: "POST",
        body: new URLSearchParams({ count }),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      console.log("📡 Response status:", response.status);

      const data = await response.json();
      console.log("📦 Response JSON:", data);

      if (response.ok && Array.isArray(data) && data.length > 0) {
        showCredentials(data);
      } else {
        console.error("❌ Failed to generate credentials:", data);
        alert(data.error || "Failed to generate credentials. See console.");
      }
    } catch (err) {
      console.error("🚨 Network or script error:", err);
      alert("Network error while generating credentials. See console.");
    }
  }

  // ---------------- Init Handlers ----------------
  function initGenerateHandlers() {
    const autoBtn = document.getElementById("autoCredsBtn");
    const genAllBtn = document.getElementById("generateAllBtn");
    const countInput = document.getElementById("studentCount");

    if (autoBtn) {
      autoBtn.addEventListener("click", () => {
        const count = parseInt(countInput?.value || "1", 10);
        requestCredentials(count);
      });
    }

    if (genAllBtn) {
      genAllBtn.addEventListener("click", () => {
        const count = parseInt(countInput?.value || "1", 10);
        requestCredentials(count);
        // 🔗 TODO: hook in link generation after credentials
      });
    }
  }

  // ---------------- Init ----------------
  ready(() => {
    initGenerateHandlers();
  });
})();

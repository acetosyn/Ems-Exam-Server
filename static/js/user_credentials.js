/* ==========================================================
   user_credentials.js — Enhanced Dynamic Credential Generator
   Architect Build v8
   ========================================================== */

(() => {
  if (window.__CRED_INIT__) return;
  window.__CRED_INIT__ = true;

  document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("cred-modal");
    const openBtns = [
      document.getElementById("generateCredsBtnSidebar"),
      document.getElementById("generateCredsBtnQuick"),
    ].filter(Boolean);
    const closeBtn = document.getElementById("closeCredModal");
    const countInput = document.getElementById("credCount");
    const generateBtn = document.getElementById("generateNowBtn");
    const quickBtns = document.querySelectorAll(".quick-gen-btn");
    const results = document.getElementById("credResults");
    const instruction = document.getElementById("credInstruction");
    const summary = document.getElementById("credSummary");
    const csvBtn = document.getElementById("downloadCSVBtn");

    // --- Helpers ---
    const show = (el) => el?.classList.remove("hidden");
    const hide = (el) => el?.classList.add("hidden");
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

    function openModal() { show(modal); }
    function closeModal() {
      hide(modal);
      results.innerHTML = "";
      hide(instruction);
      hide(summary);
      hide(csvBtn);
    }

    // --- Copy Utility ---
    async function bindCopy(btn, input) {
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(input.value);
          btn.textContent = "✅";
          btn.style.animation = "copyFlash 0.8s";
          await sleep(800);
          btn.textContent = "📋";
          btn.style.animation = "";
        } catch {
          btn.textContent = "❌";
        }
      });
    }

    // --- Toggle View ---
    function bindViewToggle(btn, input) {
      btn.addEventListener("click", () => {
        const isHidden = input.type === "password";
        input.type = isHidden ? "text" : "password";
        btn.textContent = isHidden ? "🙈" : "👁";
      });
    }

    // --- Mark Issued ---
    async function markIssued(username, btn) {
      try {
        const res = await fetch("/mark_issued", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ usernames: [username] }),
        });
        const data = await res.json();
        if (data.success) {
          btn.textContent = "✅ Issued";
          btn.classList.add("disabled");
          btn.disabled = true;
        }
      } catch (err) {
        console.error("[user_credentials] Mark issued failed:", err);
      }
    }

    // --- CSV Download ---
    function downloadCSV(creds) {
      const csvContent =
        "data:text/csv;charset=utf-8," +
        ["username,password"]
          .concat(creds.map((c) => `${c.username},${c.password}`))
          .join("\n");
      const link = document.createElement("a");
      link.href = encodeURI(csvContent);
      link.download = "generated_credentials.csv";
      link.click();
    }

    // --- Generate Credentials ---
    async function generateCreds(count) {
      try {
        results.innerHTML = `<div class="text-center text-navy">⏳ Generating ${count} credentials...</div>`;
        const res = await fetch("/generate_credentials", {
          method: "POST",
          body: new URLSearchParams({ count }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed");

        results.innerHTML = "";
        show(instruction);
        show(csvBtn);
        summary.innerHTML = `✅ Generated ${data.credentials.length} credentials successfully.`;
        show(summary);

        // Render cards
        data.credentials.forEach((cred, i) => {
          const card = document.createElement("div");
          card.className = "cred-card animate-fadeIn";
          card.innerHTML = `
            <div class="font-medium text-navy mb-2">Credential ${i + 1}</div>
            <div class="cred-field">
              <input type="password" value="${cred.username}" readonly />
              <button class="view-btn">👁</button>
              <button class="copy-btn">📋</button>
            </div>
            <div class="cred-field mt-1">
              <input type="password" value="${cred.password}" readonly />
              <button class="view-btn">👁</button>
              <button class="copy-btn">📋</button>
            </div>
            <div class="mt-2 text-right">
              <button class="issue-btn ${cred.issued ? "disabled" : ""}">
                ${cred.issued ? "✅ Issued" : "Mark Issued"}
              </button>
            </div>
          `;
          results.appendChild(card);

          const [uInput, pInput] = card.querySelectorAll("input");
          const [vBtns, cBtns] = [
            card.querySelectorAll(".view-btn"),
            card.querySelectorAll(".copy-btn"),
          ];

          vBtns.forEach((btn, idx) => bindViewToggle(btn, idx ? pInput : uInput));
          cBtns.forEach((btn, idx) => bindCopy(btn, idx ? pInput : uInput));

          const issueBtn = card.querySelector(".issue-btn");
          if (!cred.issued) {
            issueBtn.addEventListener("click", () =>
              markIssued(cred.username, issueBtn)
            );
          }
        });

        // CSV download
        csvBtn.onclick = () => downloadCSV(data.credentials);

      } catch (err) {
        results.innerHTML = `<div class="text-red-600">${err.message}</div>`;
      }
    }

    // --- Event Listeners ---
    openBtns.forEach((btn) => btn.addEventListener("click", openModal));
    closeBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
      if (e.target.id === "cred-modal") closeModal();
    });

    generateBtn.addEventListener("click", () => {
      const count = Math.max(4, parseInt(countInput.value || "4"));
      generateCreds(count);
    });

    quickBtns.forEach((btn, idx) =>
      btn.addEventListener("click", () => generateCreds(idx + 1))
    );

    console.log("[user_credentials] Enhanced modal initialized");
  });
})();

/* ======================================================================
   EMIS CBT SERVER — SUPPORT PAGE
   Small UI helpers only. No backend/API changes required.
   ====================================================================== */

(() => {
  "use strict";

  const root = document.getElementById("emisSupportPage"); if (!root || root.dataset.supportBound === "1") return; root.dataset.supportBound = "1";
  const toastHost = document.getElementById("supportToastHost"), template = document.getElementById("supportMessageTemplate"), templateButton = document.getElementById("copySupportTemplate"), copyright = document.getElementById("supportCopyright");

  function showToast(title, message = "Copied to clipboard") {
    if (!toastHost) return; const toast = document.createElement("div"); toast.className = "support-toast"; toast.innerHTML = `<span><i class="fa-solid fa-circle-check"></i></span><div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(message)}</small></div>`; toastHost.prepend(toast); while (toastHost.children.length > 3) toastHost.lastElementChild?.remove(); requestAnimationFrame(() => toast.classList.add("show")); setTimeout(() => { toast.classList.add("leaving"); setTimeout(() => toast.remove(), 230); }, 2600);
  }

  function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" }[char])); }

  async function copyText(value) {
    const text = String(value ?? "").trim(); if (!text) return false;
    try { await navigator.clipboard.writeText(text); return true; }
    catch (_) { const area = document.createElement("textarea"); area.value = text; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0"; document.body.appendChild(area); area.select(); const copied = document.execCommand("copy"); area.remove(); return copied; }
  }

  root.querySelectorAll("[data-copy-value]").forEach(button => button.addEventListener("click", async () => { const copied = await copyText(button.dataset.copyValue); if (copied) { button.classList.add("copied"); showToast(button.dataset.copyLabel || "Contact copied"); setTimeout(() => button.classList.remove("copied"), 900); } }));

  templateButton?.addEventListener("click", async () => {
    const copied = await copyText(template?.textContent || ""); if (!copied) return; templateButton.classList.add("copied"); templateButton.innerHTML = '<i class="fa-solid fa-check"></i> Template Copied'; showToast("Support template copied", "Paste it into WhatsApp or email and fill in the details."); setTimeout(() => { templateButton.classList.remove("copied"); templateButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copy Support Template'; }, 1800);
  });

  if (copyright) copyright.textContent = `© ${new Date().getFullYear()} Hakeem Tosin`;
})();

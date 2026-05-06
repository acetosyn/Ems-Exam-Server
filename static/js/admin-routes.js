// admin-routes.js — unified panel routing (sidebar + modals + quick actions)
document.addEventListener("DOMContentLoaded", () => {
  const navItems = document.querySelectorAll(".nav-item, .nav-subitem");
  const panels = document.querySelectorAll(".route");
  const breadcrumbs = document.getElementById("breadcrumbs");
  const pageTitle = document.querySelector(".page-title");

  // -----------------------------
  // Core: Activate a panel
  // -----------------------------
  function activatePanel(target, triggerEl = null) {
    if (!target) return;

    // Hide all panels
    panels.forEach(panel => panel.classList.remove("is-active"));

    // Show selected panel
    const activePanel = document.querySelector(target);
    if (activePanel) {
      activePanel.classList.add("is-active");

      // Smooth scroll to top of panel for better UX
      activePanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // Highlight sidebar nav items only (not quick actions)
    navItems.forEach(btn => btn.classList.remove("is-active"));
    if (triggerEl && triggerEl.classList.contains("nav-item")) {
      triggerEl.classList.add("is-active");
    }

    // Update page title + breadcrumbs
    const label =
      triggerEl?.innerText.trim() ||
      activePanel?.querySelector(".panel-title, .card-title")?.textContent ||
      "";
    if (pageTitle && label) pageTitle.textContent = label;
    if (breadcrumbs && label) breadcrumbs.textContent = `Home / ${label}`;
  }

  // -----------------------------
  // Sidebar navigation clicks
  // -----------------------------
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const action = item.dataset.action;
      const target = item.dataset.panel;

      if (action === "open-candidate-login") {
        window.open("/user_login", "_blank");
        return;
      }

      activatePanel(target, item);
    });
  });

  // -----------------------------
  // Special Quick Actions (modals, refresh, etc)
  // -----------------------------
  document.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", async e => {
      e.preventDefault();
      const action = btn.dataset.action;

      switch (action) {
        case "open-candidate-login":
          window.open("/user_login", "_blank");
          break;

        case "refresh-dashboard":
          location.reload();
          break;

        // -----------------------------
        // ✅ NEW: Open Upload Section
        // -----------------------------
        case "open-upload":
          console.log("Navigating to Upload Document panel...");
          activatePanel("#panel-uploads");
          break;

        // -----------------------------
        // 🔹 MODAL ACTIONS — STAY IN DASHBOARD
        // -----------------------------
        case "view-credentials":
          try {
            const res = await fetch("/view_credentials");
            const data = await res.json();
            showCredentialsModal(data.credentials);
          } catch (err) {
            console.error("Failed to load credentials", err);
            showToast("Failed to load credentials", "error");
          }
          break;

        case "view-results":
          try {
            const res = await fetch("/view_results");
            const data = await res.json();
            showResultsModal(data.results);
          } catch (err) {
            console.error("Failed to load results", err);
            showToast("Failed to load results", "error");
          }
          break;

        // -----------------------------
        // 🔹 REFRESH INSIDE MODALS
        // -----------------------------
        case "refresh-results-modal":
          try {
            const res = await fetch("/view_results");
            const data = await res.json();
            showResultsModal(data.results);
          } catch {
            showToast("Failed to refresh results", "error");
          }
          break;

        case "refresh-creds-modal":
          try {
            const res = await fetch("/view_credentials");
            const data = await res.json();
            showCredentialsModal(data.credentials);
          } catch {
            showToast("Failed to refresh credentials", "error");
          }
          break;

        default:
          console.warn(`⚠️ No handler defined for action: ${action}`);
      }
    });
  });

  // -----------------------------
  // Default active dashboard
  // -----------------------------
  const defaultPanel = document.querySelector("#panel-dashboard");
  if (defaultPanel) {
    defaultPanel.classList.add("is-active");
  }
});


document.querySelectorAll("a[href$='/admin/results']").forEach(a => {
    a.addEventListener("click", () => {
        window.location.href = "/admin/results";
    });
});

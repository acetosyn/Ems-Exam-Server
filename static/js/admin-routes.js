// admin-routes.js — unified panel routing (sidebar + modals + quick actions)
document.addEventListener("DOMContentLoaded", () => {
  const navItems = document.querySelectorAll(".nav-item, .nav-subitem");
  const panels = document.querySelectorAll(".route");
  const breadcrumbs = document.getElementById("breadcrumbs");
  const pageTitle = document.querySelector(".page-title");

  function activatePanel(target, triggerEl = null) {
    if (!target) return;

    panels.forEach(panel => panel.classList.remove("is-active"));

    const activePanel = document.querySelector(target);
    if (activePanel) {
      activePanel.classList.add("is-active");
      activePanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    navItems.forEach(btn => btn.classList.remove("is-active"));
    if (triggerEl && triggerEl.classList.contains("nav-item")) triggerEl.classList.add("is-active");

    const label = triggerEl?.innerText.trim() || activePanel?.querySelector(".panel-title, .card-title")?.textContent || "";
    if (pageTitle && label) pageTitle.textContent = label;
    if (breadcrumbs && label) breadcrumbs.textContent = `Home / ${label}`;
  }

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const action = item.dataset.action;
      const target = item.dataset.panel;

      if (action === "open-candidate-login") {
        window.open("/student_login", "_blank", "noopener");
        return;
      }

      activatePanel(target, item);
    });
  });

  document.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", async event => {
      event.preventDefault();
      const action = btn.dataset.action;

      switch (action) {
        case "open-candidate-login":
          window.open("/student_login", "_blank", "noopener");
          break;

        case "refresh-dashboard":
          location.reload();
          break;

        case "open-upload":
          activatePanel("#panel-uploads");
          break;

        case "view-credentials":
          try {
            const res = await fetch("/view_credentials");
            const data = await res.json();
            showCredentialsModal(data.credentials);
          } catch (error) {
            console.error("Failed to load credentials", error);
            showToast("Failed to load credentials", "error");
          }
          break;

        case "view-results":
          try {
            const res = await fetch("/view_results");
            const data = await res.json();
            showResultsModal(data.results);
          } catch (error) {
            console.error("Failed to load results", error);
            showToast("Failed to load results", "error");
          }
          break;

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
          console.warn(`No handler defined for action: ${action}`);
      }
    });
  });

  const defaultPanel = document.querySelector("#panel-dashboard");
  if (defaultPanel) defaultPanel.classList.add("is-active");
});


document.querySelectorAll("a[href$='/admin/results']").forEach(anchor => {
  anchor.addEventListener("click", () => { window.location.href = "/admin/results"; });
});

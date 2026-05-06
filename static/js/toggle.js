// =============================================================
// toggle.js — Sidebar Control (Stable v9: Original Layout + Mobile)
// =============================================================
document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("sidebarToggle");
  const mobileBtn = document.getElementById("mobileSidebarBtn");
  const mainContent = document.querySelector(".main-content");
  const sidebarTitle = document.querySelector(".sidebar-title");
  const logoutText = document.querySelector(".btn-logout span");
  const menuTextSpans = document.querySelectorAll(".sidebar-menu a span");

  let isCollapsed = false;
  let isMobile = window.innerWidth < 768;

  // =========================================================
  // 🖥️ DESKTOP SIDEBAR TOGGLE (Collapse)
  // =========================================================
  toggleBtn?.addEventListener("click", (e) => {
    e.stopPropagation();

    // If mobile, redirect to mobile open/close
    if (isMobile) {
      toggleMobileSidebar();
      return;
    }

    isCollapsed = !isCollapsed;
    sidebar.classList.toggle("collapsed", isCollapsed);
    sidebar.style.transition = "width 0.25s ease";
    mainContent.style.transition = "margin-left 0.25s ease";

    sidebar.style.width = isCollapsed ? "4.2rem" : "14rem";
    mainContent.style.marginLeft = isCollapsed ? "4.2rem" : "14rem";

    const display = isCollapsed ? "none" : "inline";
    if (sidebarTitle) sidebarTitle.style.display = display;
    if (logoutText) logoutText.style.display = display;
    menuTextSpans.forEach((span) => (span.style.display = display));

    const icon = toggleBtn.querySelector("i");
    if (icon) {
      icon.style.transform = isCollapsed ? "rotate(90deg)" : "rotate(0deg)";
      icon.style.transition = "transform 0.25s ease";
    }
  });

  // =========================================================
  // 📱 MOBILE SIDEBAR TOGGLE (Floating Button)
  // =========================================================
  mobileBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleMobileSidebar();
  });

  function toggleMobileSidebar() {
    sidebar.classList.toggle("open");
    document.body.classList.toggle("sidebar-open", sidebar.classList.contains("open"));
    handleOverlay();
  }

  // =========================================================
  // 🚪 CLOSE SIDEBAR WHEN CLICKING OUTSIDE (MOBILE)
  // =========================================================
  document.addEventListener("click", (e) => {
    if (isMobile && sidebar.classList.contains("open")) {
      const clickedOutside = !sidebar.contains(e.target) && !mobileBtn.contains(e.target);
      if (clickedOutside) closeMobileSidebar();
    }
  });

  function closeMobileSidebar() {
    sidebar.classList.remove("open");
    document.body.classList.remove("sidebar-open");
    removeOverlay();
  }

  // =========================================================
  // 💡 OVERLAY (Mobile Dimming)
  // =========================================================
function handleOverlay() {
  let overlay = document.querySelector(".sidebar-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.className = "sidebar-overlay fixed inset-0 bg-black/50 transition-opacity duration-300";

    overlay.style.zIndex = "1990";
    document.body.appendChild(overlay);
    overlay.addEventListener("click", closeMobileSidebar);
  }
  overlay.style.opacity = "1";
  overlay.style.pointerEvents = "auto";
}

  function removeOverlay() {
    const overlay = document.querySelector(".sidebar-overlay");
    if (overlay) {
      overlay.style.opacity = "0";
      overlay.style.pointerEvents = "none";
      setTimeout(() => overlay.remove(), 250);
    }
  }

  // =========================================================
  // 🔄 WINDOW RESIZE HANDLER (Fix Blurry/Overlay Desync)
  // =========================================================
  window.addEventListener("resize", () => {
    isMobile = window.innerWidth < 768;

    if (isMobile) {
      // Switch to mobile layout
      sidebar.classList.remove("collapsed");
      sidebar.style.width = "14rem";
      sidebar.style.transform = "translateX(-105%)";
      sidebar.style.opacity = "0";
      sidebar.style.visibility = "hidden";
      mainContent.style.marginLeft = "0";

      // Ensure overlay removed
      removeOverlay();
      document.body.classList.remove("sidebar-open");

    } else {
      // Switch to desktop layout
      sidebar.classList.remove("open");
      sidebar.style.transform = "translateX(0)";
      sidebar.style.opacity = "1";
      sidebar.style.visibility = "visible";
      mainContent.style.marginLeft = isCollapsed ? "4.2rem" : "14rem";
      removeOverlay();
      document.body.classList.remove("sidebar-open");
    }
  });

  // =========================================================
  // 🧭 HEADER DROPDOWNS (Modules + Notifications)
  // =========================================================
  const modulesBtn = document.getElementById("modulesBtn");
  const modulesMenu = document.getElementById("modulesMenu");
  const notifBtn = document.getElementById("notifBtn");
  const notifMenu = notifBtn?.nextElementSibling;

  function showMenu(menu) {
    if (!menu) return;
    menu.classList.remove("hidden");
    menu.classList.add("flex", "animate-dropdown");
  }
  function hideMenu(menu) {
    if (!menu) return;
    menu.classList.add("hidden");
    menu.classList.remove("flex");
  }

  if (!isMobile) {
    [[modulesBtn, modulesMenu], [notifBtn, notifMenu]].forEach(([btn, menu]) => {
      if (btn && menu) {
        btn.addEventListener("mouseenter", () => showMenu(menu));
        btn.addEventListener("mouseleave", () => {
          setTimeout(() => {
            if (!menu.matches(":hover")) hideMenu(menu);
          }, 200);
        });
        menu.addEventListener("mouseleave", () => hideMenu(menu));
        menu.addEventListener("mouseenter", () => showMenu(menu));
      }
    });
  }

  [[modulesBtn, modulesMenu], [notifBtn, notifMenu]].forEach(([btn, menu]) => {
    btn?.addEventListener("click", (e) => {
      if (isMobile) {
        e.stopPropagation();
        const isHidden = menu.classList.contains("hidden");
        document.querySelectorAll(".dropdown-menu").forEach((m) => m.classList.add("hidden"));
        if (isHidden) showMenu(menu);
        else hideMenu(menu);
      }
    });
  });

  document.addEventListener("click", (e) => {
    if (isMobile) {
      [modulesMenu, notifMenu].forEach((menu) => {
        const btn = menu?.previousElementSibling;
        if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) hideMenu(menu);
      });
    }
  });
});

// =============================================================
// toggle.js — Stable Sidebar Controller v10
// Desktop Collapse + Mobile Slide Panel
// =============================================================

document.addEventListener("DOMContentLoaded", () => {

  const sidebar = document.getElementById("sidebar");
  const desktopBtn = document.getElementById("sidebarToggle");
  const mobileBtn = document.getElementById("mobileSidebarBtn");

  const modulesBtn = document.getElementById("modulesBtn");
  const modulesMenu = document.getElementById("modulesMenu");

  const notifBtn = document.getElementById("notifBtn");
  const notifMenu = document.getElementById("notifMenu");

  const overlay = document.querySelector(".sidebar-overlay");

  let isCollapsed =
    localStorage.getItem("sidebarCollapsed") === "true";

  let isMobile = window.innerWidth <= 768;

  // =========================================================
  // INITIALIZE
  // =========================================================

  function applyDesktopState() {
    if (!sidebar) return;

    if (isCollapsed) {
      sidebar.classList.add("collapsed");
    } else {
      sidebar.classList.remove("collapsed");
    }
  }

  applyDesktopState();

  // =========================================================
  // DESKTOP SIDEBAR
  // =========================================================

  desktopBtn?.addEventListener("click", () => {

    if (isMobile) return;

    isCollapsed = !isCollapsed;

    sidebar.classList.toggle(
      "collapsed",
      isCollapsed
    );

    localStorage.setItem(
      "sidebarCollapsed",
      isCollapsed
    );
  });

  // =========================================================
  // MOBILE SIDEBAR OPEN
  // =========================================================

  function openMobileSidebar() {

    sidebar?.classList.add("open");

    document.body.classList.add(
      "sidebar-open"
    );

    overlay?.classList.add("active");
  }

  // =========================================================
  // MOBILE SIDEBAR CLOSE
  // =========================================================

  function closeMobileSidebar() {

    sidebar?.classList.remove("open");

    document.body.classList.remove(
      "sidebar-open"
    );

    overlay?.classList.remove("active");
  }

  // =========================================================
  // MOBILE BUTTON
  // =========================================================

  mobileBtn?.addEventListener("click", (e) => {

    e.preventDefault();
    e.stopPropagation();

    const isOpen =
      sidebar.classList.contains("open");

    if (isOpen) {
      closeMobileSidebar();
    } else {
      openMobileSidebar();
    }
  });

  // =========================================================
  // OVERLAY CLOSE
  // =========================================================

  overlay?.addEventListener(
    "click",
    closeMobileSidebar
  );

  // =========================================================
  // CLICK OUTSIDE
  // =========================================================

  document.addEventListener("click", (e) => {

    if (!isMobile) return;

    const clickedSidebar =
      sidebar?.contains(e.target);

    const clickedButton =
      mobileBtn?.contains(e.target);

    if (
      sidebar?.classList.contains("open") &&
      !clickedSidebar &&
      !clickedButton
    ) {
      closeMobileSidebar();
    }
  });

  // =========================================================
  // WINDOW RESIZE
  // =========================================================

  function handleResize() {

    isMobile = window.innerWidth <= 768;

    if (!isMobile) {

      closeMobileSidebar();

      sidebar?.classList.remove("open");

      applyDesktopState();
    }
  }

  window.addEventListener(
    "resize",
    handleResize
  );

  // =========================================================
  // DROPDOWNS
  // =========================================================

  function hideMenu(menu) {
    if (!menu) return;
    menu.style.display = "none";
  }

  function showMenu(menu) {
    if (!menu) return;
    menu.style.display = "block";
  }

  function toggleMenu(menu) {

    if (!menu) return;

    const visible =
      menu.style.display === "block";

    document
      .querySelectorAll(".dropdown-menu")
      .forEach(m => {
        m.style.display = "none";
      });

    if (!visible) {
      menu.style.display = "block";
    }
  }

  modulesBtn?.addEventListener("click", (e) => {

    e.stopPropagation();

    toggleMenu(modulesMenu);
  });

  notifBtn?.addEventListener("click", (e) => {

    e.stopPropagation();

    toggleMenu(notifMenu);
  });

  document.addEventListener("click", () => {

    hideMenu(modulesMenu);
    hideMenu(notifMenu);
  });

  // =========================================================
  // DESKTOP HOVER MENUS
  // =========================================================

  if (!isMobile) {

    [[modulesBtn, modulesMenu],
     [notifBtn, notifMenu]]
      .forEach(([btn, menu]) => {

      btn?.addEventListener(
        "mouseenter",
        () => showMenu(menu)
      );

      btn?.addEventListener(
        "mouseleave",
        () => {
          setTimeout(() => {

            if (
              !menu?.matches(":hover")
            ) {
              hideMenu(menu);
            }

          }, 200);
        }
      );

      menu?.addEventListener(
        "mouseleave",
        () => hideMenu(menu)
      );
    });
  }

});
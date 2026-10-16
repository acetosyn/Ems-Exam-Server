// =============================================================
// EMIS SHELL CONTROLLER — Stage 1 / Phase 1
// SAGE-inspired responsive navigation, accessible drawer, dropdowns
// and lightweight navigation progress without changing page backends.
// =============================================================

document.addEventListener("DOMContentLoaded", () => {
  const body = document.body, sidebar = document.getElementById("sidebar"), desktopBtn = document.getElementById("sidebarToggle"), mobileBtn = document.getElementById("mobileSidebarBtn"), mobileClose = document.getElementById("mobileSidebarClose"), mobileMore = document.getElementById("mobileMoreBtn"), overlay = document.querySelector(".sidebar-overlay"), modulesBtn = document.getElementById("modulesBtn"), modulesMenu = document.getElementById("modulesMenu"), notifBtn = document.getElementById("notifBtn"), notifMenu = document.getElementById("notifMenu"), progress = document.getElementById("emisPageProgress"), MOBILE_BREAKPOINT = 900;
  let isCollapsed = localStorage.getItem("sidebarCollapsed") === "true", lastDrawerTrigger = null, touchStartX = null;
  const isMobile = () => window.innerWidth <= MOBILE_BREAKPOINT;

  // =========================================================
  // DESKTOP COLLAPSE
  // =========================================================
  const applyDesktopState = () => { if (!sidebar || isMobile()) return; sidebar.classList.toggle("collapsed", isCollapsed); sidebar.setAttribute("aria-hidden", "false"); };
  applyDesktopState();
  desktopBtn?.addEventListener("click", () => { if (isMobile() || !sidebar) return; isCollapsed = !isCollapsed; sidebar.classList.toggle("collapsed", isCollapsed); localStorage.setItem("sidebarCollapsed", String(isCollapsed)); });

  // =========================================================
  // MOBILE DRAWER
  // =========================================================
  function setMobileDrawer(open, trigger = null) {
    if (!sidebar || !isMobile()) return;
    if (open && trigger) lastDrawerTrigger = trigger;
    sidebar.classList.toggle("open", open); body.classList.toggle("sidebar-open", open); overlay?.classList.toggle("active", open); overlay?.setAttribute("aria-hidden", String(!open)); sidebar.setAttribute("aria-hidden", String(!open)); mobileBtn?.setAttribute("aria-expanded", String(open)); mobileMore?.setAttribute("aria-expanded", String(open));
    if (open) requestAnimationFrame(() => (mobileClose || sidebar.querySelector("a.active") || sidebar.querySelector("a"))?.focus({ preventScroll:true })); else lastDrawerTrigger?.focus?.({ preventScroll:true });
  }
  const openMobileDrawer = trigger => setMobileDrawer(true, trigger), closeMobileDrawer = () => setMobileDrawer(false);
  mobileBtn?.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); sidebar?.classList.contains("open") ? closeMobileDrawer() : openMobileDrawer(mobileBtn); });
  mobileMore?.addEventListener("click", e => { e.preventDefault(); openMobileDrawer(mobileMore); });
  mobileClose?.addEventListener("click", closeMobileDrawer); overlay?.addEventListener("click", closeMobileDrawer);
  sidebar?.addEventListener("click", e => { if (isMobile() && e.target.closest("a[href]:not(.disabled-link)")) closeMobileDrawer(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") { closeMobileDrawer(); hideAllMenus(); } });

  // Swipe left anywhere inside the drawer to close it on touch devices.
  sidebar?.addEventListener("touchstart", e => { touchStartX = e.touches?.[0]?.clientX ?? null; }, { passive:true });
  sidebar?.addEventListener("touchend", e => { if (touchStartX === null) return; const endX = e.changedTouches?.[0]?.clientX ?? touchStartX; if (touchStartX - endX > 70) closeMobileDrawer(); touchStartX = null; }, { passive:true });

  // =========================================================
  // HEADER DROPDOWNS
  // =========================================================
  function hideMenu(menu, button) { if (!menu) return; menu.style.display = "none"; button?.setAttribute("aria-expanded", "false"); }
  function showMenu(menu, button) { if (!menu) return; menu.style.display = "block"; button?.setAttribute("aria-expanded", "true"); }
  function hideAllMenus(except = null) { [[modulesMenu,modulesBtn],[notifMenu,notifBtn]].forEach(([menu,button]) => { if (menu !== except) hideMenu(menu,button); }); }
  function toggleMenu(menu, button) { if (!menu) return; const visible = getComputedStyle(menu).display !== "none"; hideAllMenus(menu); visible ? hideMenu(menu,button) : showMenu(menu,button); }
  modulesBtn?.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); toggleMenu(modulesMenu,modulesBtn); });
  notifBtn?.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); toggleMenu(notifMenu,notifBtn); });
  document.addEventListener("click", e => { if (!e.target.closest(".base-dropdown")) hideAllMenus(); });

  // Desktop-only hover remains available, while mobile stays click/touch driven.
  [[modulesBtn,modulesMenu],[notifBtn,notifMenu]].forEach(([button,menu]) => { button?.addEventListener("mouseenter", () => { if (!isMobile()) showMenu(menu,button); }); button?.addEventListener("mouseleave", () => { if (!isMobile()) setTimeout(() => { if (!menu?.matches(":hover")) hideMenu(menu,button); }, 160); }); menu?.addEventListener("mouseleave", () => { if (!isMobile()) hideMenu(menu,button); }); });

  // =========================================================
  // RESIZE / ORIENTATION
  // =========================================================
  function handleViewportChange() { if (isMobile()) { sidebar?.classList.remove("collapsed"); sidebar?.setAttribute("aria-hidden", String(!sidebar.classList.contains("open"))); } else { sidebar?.classList.remove("open"); body.classList.remove("sidebar-open"); mobileBtn?.setAttribute("aria-expanded", "false"); mobileMore?.setAttribute("aria-expanded", "false"); overlay?.classList.remove("active"); overlay?.setAttribute("aria-hidden", "true"); sidebar?.setAttribute("aria-hidden", "false"); applyDesktopState(); } hideAllMenus(); }
  window.addEventListener("resize", handleViewportChange, { passive:true }); window.addEventListener("orientationchange", handleViewportChange, { passive:true }); handleViewportChange();

  // =========================================================
  // NAVIGATION FEEDBACK — Stage 1 / Phase 5
  // Hybrid router owns soft navigation; normal Flask navigation still receives
  // immediate progress feedback without competing click handlers.
  // =========================================================
  function navigationStart() { body.classList.add("emis-navigating"); progress?.setAttribute("aria-hidden", "false"); if (progress) { progress.style.opacity = "1"; progress.style.width = "68%"; } closeMobileDrawer(); hideAllMenus(); }
  function navigationEnd() { body.classList.remove("emis-navigating"); if (!progress) return; progress.style.width = "100%"; progress.style.opacity = "0"; setTimeout(() => { progress.style.width = "0"; progress.removeAttribute("style"); progress.setAttribute("aria-hidden", "true"); }, 180); }
  document.addEventListener("emis:navigation-start", navigationStart); document.addEventListener("emis:navigation-end", navigationEnd); document.addEventListener("emis:navigation-error", navigationEnd);
  document.addEventListener("click", e => { const link=e.target.closest("a[href]"); if(!link || e.defaultPrevented || e.button!==0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || link.target==="_blank" || link.hasAttribute("download"))return; let url; try{url=new URL(link.href,location.href);}catch(_){return;} if(url.origin!==location.origin || url.href===location.href || (url.hash && url.pathname===location.pathname))return; if(body.dataset.emisSoftNav==="1" && window.EMISRouter?.isSoftRoute?.(url.href))return; navigationStart(); });
  window.addEventListener("pageshow", navigationEnd);
});

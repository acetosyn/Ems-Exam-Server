/* ==========================================================
   EMIS TEACHER PAGE ROUTER — teacher_pageroutes.js v2
   ----------------------------------------------------------
   • Dynamic modules: Upload Exams + Convert Questions
   • Direct teacher routes: Results + Attendance + CA Tests
   • External Student Exam Login
   • Keyboard accessible module cards
========================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const dynamicContainer = document.getElementById("teacherDynamicContent");
  const toolButtons = [...document.querySelectorAll(".module-item[data-page], .module-item[data-route], .module-item[data-external]")];
  const dynamicButtons = toolButtons.filter(button => button.dataset.page);
  const routeCache = new Map();

  const loaderHTML = (label = "Opening module...") => `
    <div class="teacher-route-loader fade-in">
      <div class="teacher-loader-card">
        <div class="teacher-loader-orbit"><span></span><span></span><span></span></div>
        <div><h3>${label}</h3><p>Please wait while EMIS prepares your workspace.</p></div>
      </div>
    </div>`;

  const errorHTML = (page, error) => `
    <div class="teacher-route-error fade-in">
      <div class="error-icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
      <h3>Unable to load module</h3>
      <p>Could not open <strong>${page}</strong>.<br><small>${error.message || "Unknown error"}</small></p>
      <button id="retryTeacherRoute" class="btn-primary"><i class="fa-solid fa-rotate"></i> Try Again</button>
    </div>`;

  function normalizePage(page) { page = String(page || "").trim(); return page.endsWith(".html") ? page : `${page}.html`; }
  function routeName(page) { return page.replace(".html", ""); }
  function setActiveButton(activeBtn) { toolButtons.forEach(btn => btn.classList.remove("active")); activeBtn?.classList.add("active"); }

  function updateUrl(page) {
    const url = new URL(window.location.href);
    url.searchParams.set("open", routeName(page));
    window.history.replaceState({}, "", url);
  }

  function parseHTML(html) { const temp = document.createElement("div"); temp.innerHTML = html; return temp; }

  function preloadStyles(scope) {
    const links = [...scope.querySelectorAll('link[rel="stylesheet"]')];
    return Promise.all(links.map(oldLink => {
      const href = oldLink.getAttribute("href");
      if (!href) return Promise.resolve();

      const alreadyLoaded = [...document.querySelectorAll('link[rel="stylesheet"]')].some(link => link.getAttribute("href") === href);
      if (alreadyLoaded) { oldLink.remove(); return Promise.resolve(); }

      return new Promise(resolve => {
        const newLink = document.createElement("link");
        newLink.rel = "stylesheet";
        newLink.href = href;
        newLink.dataset.dynamicTeacherStyle = "true";
        newLink.onload = resolve;
        newLink.onerror = resolve;
        document.head.appendChild(newLink);
        oldLink.remove();
        setTimeout(resolve, 700);
      });
    }));
  }

  function reexecuteScripts(scope) {
    scope.querySelectorAll("script[src]").forEach(oldScript => {
      const src = oldScript.getAttribute("src");
      if (!src) return;

      const existing = [...document.querySelectorAll("script[data-dynamic-teacher-script]")].find(script => script.getAttribute("src") === src);
      if (existing) existing.remove();

      const script = document.createElement("script");
      script.src = src;
      script.async = false;
      script.dataset.dynamicTeacherScript = "true";
      document.body.appendChild(script);
      oldScript.remove();
    });

    scope.querySelectorAll("script:not([src])").forEach(inline => {
      try {
        const script = document.createElement("script");
        script.textContent = inline.textContent;
        document.body.appendChild(script);
        script.remove();
        inline.remove();
      } catch (error) {
        console.error("Inline script error:", error);
      }
    });
  }

  function initLoadedModule(page) {
    if (page === "uploads.html") {
      const wrap = dynamicContainer?.querySelector(".uploads-wrapper");
      if (wrap) { wrap.__initialized__ = false; wrap.__push_initialized__ = false; }
      window.EmisUploads?.initOnce?.(dynamicContainer);
      window.EmisPush?.init?.();
      window.EmisAvailableYears?.reload?.();
    }

    if (page === "convert.html") {
      const wrap = dynamicContainer?.querySelector(".convert-wrapper");
      if (wrap) wrap.__initialized__ = false;
      window.EmisConvert?.initOnce?.(dynamicContainer);
    }
  }

  async function loadTeacherPage(button, useCache = true) {
    if (!dynamicContainer) return;

    const page = normalizePage(button.dataset.page);
    const endpoint = `/admin/${routeName(page)}`;

    setActiveButton(button);
    updateUrl(page);
    dynamicContainer.innerHTML = loaderHTML(`Loading ${routeName(page).replaceAll("_", " ")}...`);
    dynamicContainer.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      let html = "";

      if (useCache && routeCache.has(endpoint)) html = routeCache.get(endpoint);
      else {
        const response = await fetch(endpoint, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" });
        if (!response.ok) throw new Error(`Page not found (${response.status})`);
        html = await response.text();
        routeCache.set(endpoint, html);
      }

      const parsed = parseHTML(html);
      await preloadStyles(parsed);
      await new Promise(resolve => setTimeout(resolve, 120));

      dynamicContainer.innerHTML = `<div class="teacher-route-content fade-slide-in">${parsed.innerHTML}</div>`;
      reexecuteScripts(dynamicContainer);
      setTimeout(() => initLoadedModule(page), 80);

    } catch (error) {
      console.error("Teacher route load error:", error);
      dynamicContainer.innerHTML = errorHTML(page, error);
      document.getElementById("retryTeacherRoute")?.addEventListener("click", () => loadTeacherPage(button, false));
    }
  }

  function activateTool(button) {
    if (button.dataset.external) {
      window.open(button.dataset.external, "_blank", "noopener");
      return;
    }

    if (button.dataset.route) {
      window.location.href = button.dataset.route;
      return;
    }

    if (button.dataset.page) loadTeacherPage(button);
  }

  toolButtons.forEach(button => {
    button.addEventListener("click", () => activateTool(button));
    button.addEventListener("keydown", event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      activateTool(button);
    });
  });

  const moduleToOpen = new URLSearchParams(window.location.search).get("open");
  if (moduleToOpen) {
    const targetBtn = dynamicButtons.find(button => routeName(normalizePage(button.dataset.page)) === moduleToOpen);
    if (targetBtn) setTimeout(() => loadTeacherPage(targetBtn), 350);
  }

  document.getElementById("refreshDashboard")?.addEventListener("click", () => {
    routeCache.clear();
    location.reload();
  });
});

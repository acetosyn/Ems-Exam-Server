/* ==========================================================
   EMIS TEACHER PAGE ROUTER — teacher_pageroutes.js
   Dynamic module loader with CSS preloader to prevent raw page flash
========================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const dynamicContainer = document.getElementById("teacherDynamicContent");
  const toolButtons = document.querySelectorAll(".module-item[data-page]");

  if (!dynamicContainer) return;

  const routeCache = new Map();

  const loaderHTML = (label = "Opening module...") => `
    <div class="teacher-route-loader fade-in">
      <div class="teacher-loader-card">
        <div class="teacher-loader-orbit">
          <span></span>
          <span></span>
          <span></span>
        </div>

        <div>
          <h3>${label}</h3>
          <p>Please wait while EMIS prepares your workspace.</p>
        </div>
      </div>
    </div>
  `;

  const errorHTML = (page, error) => `
    <div class="teacher-route-error fade-in">
      <div class="error-icon">
        <i class="fa-solid fa-triangle-exclamation"></i>
      </div>

      <h3>Unable to load module</h3>
      <p>
        Could not open <strong>${page}</strong>.
        <br>
        <small>${error.message || "Unknown error"}</small>
      </p>

      <button id="retryTeacherRoute" class="btn-primary">
        <i class="fa-solid fa-rotate"></i>
        Try Again
      </button>
    </div>
  `;

  function normalizePage(page) {
    page = String(page || "").trim();
    if (!page.endsWith(".html")) page = `${page}.html`;
    return page;
  }

  function routeName(page) {
    return page.replace(".html", "");
  }

  function setActiveButton(activeBtn) {
    toolButtons.forEach((btn) => btn.classList.remove("active"));
    activeBtn?.classList.add("active");
  }

  function updateUrl(page) {
    const openName = routeName(page);
    const url = new URL(window.location.href);
    url.searchParams.set("open", openName);
    window.history.replaceState({}, "", url);
  }

  function parseHTML(html) {
    const temp = document.createElement("div");
    temp.innerHTML = html;
    return temp;
  }

  function preloadStyles(scope) {
    const links = [...scope.querySelectorAll('link[rel="stylesheet"]')];

    const loadPromises = links.map((oldLink) => {
      const href = oldLink.getAttribute("href");
      if (!href) return Promise.resolve();

      const alreadyLoaded = [...document.querySelectorAll('link[rel="stylesheet"]')]
        .some((link) => link.getAttribute("href") === href);

      if (alreadyLoaded) {
        oldLink.remove();
        return Promise.resolve();
      }

      return new Promise((resolve) => {
        const newLink = document.createElement("link");
        newLink.rel = "stylesheet";
        newLink.href = href;
        newLink.dataset.dynamicTeacherStyle = "true";

        newLink.onload = () => resolve();
        newLink.onerror = () => resolve();

        document.head.appendChild(newLink);
        oldLink.remove();

        setTimeout(resolve, 700);
      });
    });

    return Promise.all(loadPromises);
  }

  function reexecuteScripts(scope) {
    const externalScripts = scope.querySelectorAll("script[src]");

    externalScripts.forEach((oldScript) => {
      const src = oldScript.getAttribute("src");
      if (!src) return;

      const existingDynamic = [...document.querySelectorAll("script[data-dynamic-teacher-script]")]
        .find((script) => script.getAttribute("src") === src);

      if (existingDynamic) existingDynamic.remove();

      const newScript = document.createElement("script");
      newScript.src = src;
      newScript.async = false;
      newScript.dataset.dynamicTeacherScript = "true";
      document.body.appendChild(newScript);

      oldScript.remove();
    });

    const inlineScripts = scope.querySelectorAll("script:not([src])");

    inlineScripts.forEach((inline) => {
      try {
        const script = document.createElement("script");
        script.textContent = inline.textContent;
        document.body.appendChild(script);
        script.remove();
        inline.remove();
      } catch (err) {
        console.error("Inline script error:", err);
      }
    });
  }

  function initLoadedModule(page) {
    if (page === "uploads.html") {
      const wrap = dynamicContainer.querySelector(".uploads-wrapper");

      if (wrap) {
        wrap.__initialized__ = false;
        wrap.__push_initialized__ = false;
      }

      if (window.EmisUploads?.initOnce) {
        window.EmisUploads.initOnce(dynamicContainer);
      }

      if (window.EmisPush?.init) {
        window.EmisPush.init();
      }

      if (window.EmisAvailableYears?.reload) {
        window.EmisAvailableYears.reload();
      }
    }

    if (page === "convert.html") {
      const wrap = dynamicContainer.querySelector(".convert-wrapper");

      if (wrap) {
        wrap.__initialized__ = false;
      }

      if (window.EmisConvert?.initOnce) {
        window.EmisConvert.initOnce(dynamicContainer);
      }
    }
  }

  async function loadTeacherPage(button, useCache = true) {
    const page = normalizePage(button.dataset.page);
    const endpoint = `/admin/${routeName(page)}`;

    setActiveButton(button);
    updateUrl(page);

    dynamicContainer.innerHTML = loaderHTML(
      `Loading ${routeName(page).replaceAll("_", " ")}...`
    );

    dynamicContainer.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });

    try {
      let html = "";

      if (useCache && routeCache.has(endpoint)) {
        html = routeCache.get(endpoint);
      } else {
        const response = await fetch(endpoint, {
          headers: {
            "X-Requested-With": "fetch",
          },
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Page not found (${response.status})`);
        }

        html = await response.text();
        routeCache.set(endpoint, html);
      }

      const parsed = parseHTML(html);

      await preloadStyles(parsed);

      await new Promise((resolve) => setTimeout(resolve, 120));

      dynamicContainer.innerHTML = `
        <div class="teacher-route-content fade-slide-in">
          ${parsed.innerHTML}
        </div>
      `;

      reexecuteScripts(dynamicContainer);

      setTimeout(() => {
        initLoadedModule(page);
      }, 80);

    } catch (error) {
      console.error("Teacher route load error:", error);

      dynamicContainer.innerHTML = errorHTML(page, error);

      const retryBtn = document.getElementById("retryTeacherRoute");
      retryBtn?.addEventListener("click", () => loadTeacherPage(button, false));
    }
  }

  toolButtons.forEach((btn) => {
    btn.addEventListener("click", () => loadTeacherPage(btn));
  });

  const urlParams = new URLSearchParams(window.location.search);
  const moduleToOpen = urlParams.get("open");

  if (moduleToOpen) {
    const targetBtn = document.querySelector(
      `.module-item[data-page="${moduleToOpen}.html"], .module-item[data-page="${moduleToOpen}"]`
    );

    if (targetBtn) {
      setTimeout(() => loadTeacherPage(targetBtn), 350);
    }
  }

  const refreshBtn = document.getElementById("refreshDashboard");
  refreshBtn?.addEventListener("click", () => {
    routeCache.clear();
    location.reload();
  });
});
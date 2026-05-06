/* ==========================================================
   EMIS TEACHER PAGE ROUTER — teacher_pageroutes.js (v6)
   ----------------------------------------------------------
   Dynamically loads teacher tools (uploads, results, reports)
   into #teacherDynamicContent without leaving teachers.html

   ✳️ Fixes:
   - Reinitialize uploads.js + push.js after dynamic load
   - Ensures push buttons work inside uploads.html
   - Prevents duplicate event binding
========================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const dynamicContainer = document.getElementById("teacherDynamicContent");
  const toolButtons = document.querySelectorAll(".module-item[data-page]");

  const loaderHTML = `
    <div class="route-loader fade-in">
      <div class="loader-spinner"></div>
      <p>Loading, please wait...</p>
    </div>
  `;

  /* ==========================================================
     AUTO LOAD VIA ?open=uploads
  ========================================================== */
  const urlParams = new URLSearchParams(window.location.search);
  const moduleToOpen = urlParams.get("open");

  if (moduleToOpen) {
    const targetBtn = document.querySelector(
      `.module-item[data-page="${moduleToOpen}.html"]`
    );

    if (targetBtn) {
      setTimeout(() => {
        targetBtn.click();
      }, 350);
    }
  }

  /* ==========================================================
     LOAD MODULE WHEN BUTTON CLICKED
  ========================================================== */
  toolButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      let page = btn.dataset.page;

      if (!page.endsWith(".html")) {
        page = `${page}.html`;
      }

      toolButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      dynamicContainer.innerHTML = loaderHTML;

      try {
        const response = await fetch(`/admin/${page.replace(".html", "")}`);
        if (!response.ok) throw new Error(`Page not found (${response.status})`);

        const html = await response.text();

        setTimeout(() => {
          dynamicContainer.innerHTML = `<div class="fade-slide-in">${html}</div>`;
          dynamicContainer.scrollIntoView({ behavior: "smooth" });

          /* ================================================
             AUTO INIT MODULES AFTER HTML INSERTION
          ================================================= */
          if (page === "uploads.html") {
            // Init uploads (file convert UI)
            if (window.EmisUploads) {
              EmisUploads.initOnce(dynamicContainer);
            }

            // Init push controller (push modals)
            if (window.EmisPush) {
              EmisPush.init();  
            }
          }

          /* ================================================
             RE-EXECUTE EXTERNAL SCRIPTS INSIDE LOADED HTML
          ================================================= */
          const scriptTags = dynamicContainer.querySelectorAll("script[src]");
          scriptTags.forEach((oldScript) => {
            const newScript = document.createElement("script");
            newScript.src = oldScript.src;
            newScript.async = true;
            document.body.appendChild(newScript);
          });

          /* Execute inline scripts */
          const inlineScripts = dynamicContainer.querySelectorAll("script:not([src])");
          inlineScripts.forEach((inline) => {
            try {
              eval(inline.textContent);
            } catch (err) {
              console.error("⚠️ Inline script error:", err);
            }
          });

        }, 250);
      } catch (error) {
        console.error("❌ Route load error:", error);
        dynamicContainer.innerHTML = `
          <div class="error-panel fade-in">
            <i class="fa-solid fa-triangle-exclamation text-red-500"></i>
            <p>⚠️ Unable to load <strong>${page}</strong><br>
            <small>${error.message}</small></p>
          </div>
        `;
      }
    });
  });

  /* ==========================================================
     DASHBOARD REFRESH BUTTON
  ========================================================== */
  const refreshBtn = document.getElementById("refreshDashboard");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => location.reload());
  }
});

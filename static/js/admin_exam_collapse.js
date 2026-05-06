/* admin_exam_collapse.js — use built-in admin1.css collapsible */
(() => {
  if (window.__EXAM_COLLAPSE_INIT__) return;
  window.__EXAM_COLLAPSE_INIT__ = true;

  const ready = (cb) =>
    document.readyState !== "loading"
      ? cb()
      : document.addEventListener("DOMContentLoaded", cb);

  ready(() => {
    const groups = document.querySelectorAll(".nav-group");

    groups.forEach((group) => {
      const parentBtn = group.querySelector(".nav-parent");
      const caret = parentBtn?.querySelector(".nav-caret");

      if (!parentBtn) return;

      parentBtn.addEventListener("click", () => {
        const isOpen = group.classList.contains("open");

        // Close other groups
        document.querySelectorAll(".nav-group.open").forEach((g) => {
          g.classList.remove("open");
          g.querySelector(".nav-caret")?.classList.remove("rotate");
        });

        // Toggle this one
        if (!isOpen) {
          group.classList.add("open");
          caret?.classList.add("rotate");
        } else {
          group.classList.remove("open");
          caret?.classList.remove("rotate");
        }
      });
    });

    console.log("[exam-collapse] Initialized");
  });
})();

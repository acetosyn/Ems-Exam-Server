document.addEventListener("DOMContentLoaded", () => {
  /* ----- Typewriter Banner ----- */
  const el = document.getElementById("typewriter");
  if (el) {
    const subject = sessionStorage.getItem("chosenSubject") || "your exam";
    const messages = [
      `📘 You are about to take ${subject.toUpperCase()}`,
      "✅ Ensure a stable internet connection",
      "🌐 Use a modern browser (Chrome, Edge, Safari, Firefox)",
      "🚫 Close other apps/tabs to avoid distractions",
      "🔋 Keep your device fully charged",
      "📝 Verify your full name is correct (first & last)",
      "🎥 Ensure camera/mic are allowed if required"
    ];
    let msgIndex = 0, charIndex = 0, deleting = false;

    function type() {
      const current = messages[msgIndex];
      if (!deleting) {
        el.textContent = current.substring(0, charIndex++) + "▋";
        if (charIndex > current.length) {
          deleting = true;
          setTimeout(type, 1000);
          return;
        }
      } else {
        el.textContent = current.substring(0, charIndex--) + "▋";
        if (charIndex === 0) {
          deleting = false;
          msgIndex = (msgIndex + 1) % messages.length;
        }
      }
      setTimeout(type, deleting ? 40 : 70);
    }
    type();
  }

  /* ----- Reveal on scroll ----- */
  const cards = document.querySelectorAll(".up-card");
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add("in-view");
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.2 });
  cards.forEach(c => io.observe(c));

  /* ----- Modal Support ----- */
  const modal = document.getElementById("supportModal");
  const openBtn = document.getElementById("openSupport");
  const closeBtn = document.getElementById("closeSupport");
  const dismissBtn = document.getElementById("dismissSupport");

  const open = () => modal.classList.remove("hidden");
  const close = () => modal.classList.add("hidden");
  openBtn?.addEventListener("click", open);
  closeBtn?.addEventListener("click", close);
  dismissBtn?.addEventListener("click", close);
  modal.addEventListener("click", e => { if (e.target === modal) close(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });

  /* ----- Activity Feed ----- */
  const activityList = document.getElementById("activityList");
  function logActivity(title) {
    const meta = new Date().toLocaleString();
    const div = document.createElement("div");
    div.className = "up-activity-item";
    div.innerHTML = `<div class="dot"></div><div><div class="title">${title}</div><div class="meta">${meta}</div></div>`;
    activityList.prepend(div);
  }

  logActivity("Portal Accessed");

  // log chosen subject
  const subject = sessionStorage.getItem("chosenSubject");
  if (subject) {
    logActivity(`Subject chosen: ${subject}`);
  }

  // track button clicks
  document.querySelectorAll("button, a").forEach(el => {
    el.addEventListener("click", () => logActivity(el.textContent.trim()));
  });
});

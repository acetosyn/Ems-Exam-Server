// =========================
// GLOBAL PAGE ROUTER (EXCEPT TEACHERS & UPLOAD EXAM)
// =========================

document.addEventListener("click", function (event) {

    // ❌ Never run router when Teacher Dashboard button is clicked
    if (event.target.closest(".module-item.green")) return;

    // ❌ Never run router when Upload Exam button is clicked
    if (event.target.closest(".uploads-btn")) return;

    // ❌ Never run router inside Teacher Dashboard
    if (window.location.pathname.includes("/admin/teachers")) return;

    // ❌ Never run router inside Upload Exam page
    if (window.location.pathname.includes("/admin/uploads")) return;

    // Look for elements using SPA routes
    const btn = event.target.closest("[data-route]");
    if (!btn) return;

    event.preventDefault();

    const route = btn.getAttribute("data-route");

    fetch(route)
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            const mainTag = doc.querySelector("main");
            if (!mainTag) return;

            const newContent = mainTag.innerHTML;

            document.querySelector("main").innerHTML = newContent;

            window.scrollTo({ top: 0, behavior: "smooth" });
        })
        .catch(err => console.error("Routing Error:", err));
});

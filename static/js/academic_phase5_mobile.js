/* =================================================================================================
   EMIS ACADEMIC WORKSPACE — PHASE 5
   Smart auto-flow + safe viewport modal behavior for CA/Test + Report Sheets.
   ================================================================================================= */
(() => {
    "use strict";
    const $ = (selector, root = document) => root.querySelector(selector), $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
    const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
    const usableOptions = select => select ? [...select.options].filter(option => option.value && !option.disabled) : [];

    function dispatchChange(node) { if (node) node.dispatchEvent(new Event("change", { bubbles:true })); }
    function autoChooseSingleton(select) { if (!select || select.disabled || select.value) return false; const options = usableOptions(select); if (options.length !== 1) return false; select.value = options[0].value; dispatchChange(select); return true; }

    function portalizeModal(modal) {
        if (!modal || modal.dataset.phase45Portal === "1" || modal.parentElement === document.body) return; modal.dataset.phase45Portal = "1"; modal._phase45Home = { parent:modal.parentElement, next:modal.nextSibling }; modal.classList.add("phase45-viewport-modal"); document.body.appendChild(modal);
    }
    function restoreModal(modal) { const home = modal?._phase45Home; if (!modal || !home?.parent?.isConnected) return; if (home.next?.parentNode === home.parent) home.parent.insertBefore(modal, home.next); else home.parent.appendChild(modal); modal.classList.remove("phase45-viewport-modal"); delete modal.dataset.phase45Portal; delete modal._phase45Home; }
    function observeModals(selector) {
        $$(selector).forEach(modal => {
            if (modal.dataset.phase45Observed === "1") return; modal.dataset.phase45Observed = "1";
            const sync = () => { const open = modal.getAttribute("aria-hidden") === "false" || modal.classList.contains("open") || modal.classList.contains("active") || modal.classList.contains("show"); if (open) portalizeModal(modal); else if (modal.parentElement === document.body) restoreModal(modal); };
            if (window.MutationObserver) new MutationObserver(sync).observe(modal, { attributes:true, attributeFilter:["aria-hidden","class","style"] }); sync();
        });
    }

    function initCaAutoFlow() {
        const root = $("#caPage"); if (!root || root.dataset.phase5Ready === "1") return; root.dataset.phase5Ready = "1";
        const level = $("#caClassLevel", root), arm = $("#caClassArm", root), subject = $("#caSubject", root), load = $("#loadCAStudentsBtn", root), session = $("#caSession", root), term = $("#caTerm", root);
        let timer = 0, subjectObserver;
        const maybeLoad = () => { clearTimeout(timer); timer = window.setTimeout(() => { if (session?.value && term?.value && level?.value && arm?.value && subject?.value && !load?.disabled) load?.click(); }, 120); };
        level?.addEventListener("change", async () => { await wait(0); if (autoChooseSingleton(arm)) return; });
        arm?.addEventListener("change", async () => { await wait(30); autoChooseSingleton(subject); });
        subject?.addEventListener("change", maybeLoad);
        [session, term].filter(Boolean).forEach(node => node.addEventListener("change", () => { if (subject?.value) maybeLoad(); }));
        if (subject && window.MutationObserver) { subjectObserver = new MutationObserver(() => { if (!subject.disabled) autoChooseSingleton(subject); }); subjectObserver.observe(subject, { childList:true, attributes:true, attributeFilter:["disabled"] }); }
        observeModals("#caPage .ca-modal");
    }

    function initReportAutoFlow() {
        const root = $("#reportPage"); if (!root || root.dataset.phase5Ready === "1") return; root.dataset.phase5Ready = "1";
        const level = $("#reportClassLevel", root), arm = $("#reportClassArm", root), load = $("#loadReportStudentsBtn", root), session = $("#reportSession", root), term = $("#reportTerm", root);
        let timer = 0;
        const maybeLoad = () => { clearTimeout(timer); timer = window.setTimeout(() => { if (session?.value && term?.value && level?.value && arm?.value && !load?.disabled) load?.click(); }, 150); };
        level?.addEventListener("change", async () => { await wait(0); if (autoChooseSingleton(arm)) return; });
        arm?.addEventListener("change", maybeLoad);
        [session, term].filter(Boolean).forEach(node => node.addEventListener("change", () => { if (level?.value && arm?.value) maybeLoad(); }));
        observeModals("#reportPage .report-modal");
    }

    function init() { initCaAutoFlow(); initReportAutoFlow(); }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once:true }); else init();
    document.addEventListener("emis:page-ready", init);
})();

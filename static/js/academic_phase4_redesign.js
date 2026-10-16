/* =================================================================================================
   EMIS ACADEMIC WORKSPACE — PHASE 4
   UI-only structural transformation. No backend routes are changed here.
   ================================================================================================= */
(() => {
    "use strict";
    const $ = (selector, root = document) => root.querySelector(selector), $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

    function initCaPhase4() {
        const root = $("#caPage"); if (!root || root.dataset.phase4Ready === "1") return; root.dataset.phase4Ready = "1"; root.classList.add("phase45-redesign");
        const dock = $(".ca-action-dock", root), control = $(".ca-control-panel", root), mode = $(".ca-mode-grid", root), toolbar = $(".ca-toolbar", root);
        if (dock && control) {
            const tools = document.createElement("div"); tools.className = "ca-phase45-tools";
            tools.innerHTML = `<div class="phase45-context"><i class="fa-solid fa-table-list"></i><span>Current workspace</span><strong id="caPhase45Context">Choose a class, arm and subject</strong></div><button type="button" class="phase45-tool-trigger" id="caPhase45ToolsBtn" aria-expanded="false"><i class="fa-solid fa-ellipsis"></i> Database Tools</button>`;
            control.insertAdjacentElement("afterend", tools); tools.appendChild(dock);
            const trigger = $("#caPhase45ToolsBtn", tools);
            const close = () => { dock.classList.remove("phase45-open"); trigger?.setAttribute("aria-expanded", "false"); };
            trigger?.addEventListener("click", event => { event.stopPropagation(); const open = dock.classList.toggle("phase45-open"); trigger.setAttribute("aria-expanded", String(open)); });
            document.addEventListener("click", event => { if (!tools.contains(event.target)) close(); });
            document.addEventListener("keydown", event => { if (event.key === "Escape") close(); });
        }
        if (mode && toolbar) {
            const structure = document.createElement("div"); structure.className = "ca-phase45-structure"; structure.innerHTML = `<i class="fa-solid fa-shield-halved"></i><span>Assessment format</span><strong id="caPhase45Structure">Select a class to view the active score structure</strong><small>Protected rules follow the configured school section.</small>`;
            toolbar.insertAdjacentElement("beforebegin", structure);
        }
        const context = $("#caPhase45Context", root), structureText = $("#caPhase45Structure", root), level = $("#caClassLevel", root), arm = $("#caClassArm", root), subject = $("#caSubject", root), session = $("#caSession", root), term = $("#caTerm", root), live = $("#caStructureLabel", root);
        const optionText = node => node?.selectedOptions?.[0]?.textContent?.trim() || "";
        const refresh = () => {
            if (context) context.textContent = [optionText(level), optionText(arm), optionText(subject)].filter(Boolean).join(" • ") || "Choose a class, arm and subject";
            if (structureText) structureText.textContent = live?.textContent?.trim() || "Select a class to view the active score structure";
        };
        [level, arm, subject, session, term].filter(Boolean).forEach(node => node.addEventListener("change", () => setTimeout(refresh, 0)));
        if (live && window.MutationObserver) new MutationObserver(refresh).observe(live, { childList:true, subtree:true, characterData:true }); refresh();
    }

    function initReportPhase4() {
        const root = $("#reportPage"); if (!root || root.dataset.phase4Ready === "1") return; root.dataset.phase4Ready = "1"; root.classList.add("phase45-redesign");
        const stats = $(".report-stats-grid", root), control = $("#reportSetupPanel", root), intelligence = $(".report-intelligence-grid", root);
        if (stats && control && intelligence) {
            const health = document.createElement("div"); health.className = "report-phase45-health";
            health.innerHTML = `<div class="health-title"><i class="fa-solid fa-circle-check"></i><span>Class readiness</span></div><div class="health-meter"><i id="reportPhase45HealthFill"></i></div><div class="health-value"><strong id="reportPhase45HealthPercent">0%</strong> ready</div><div class="health-value"><strong id="reportPhase45Completion">0 / 0</strong> reports</div>`;
            control.insertAdjacentElement("beforebegin", health);
            const sourcePercent = $("#reportReadinessPercent", root), sourceCompletion = $("#reportClassCompletionText", root), fill = $("#reportPhase45HealthFill", root), pct = $("#reportPhase45HealthPercent", root), completed = $("#reportPhase45Completion", root);
            const sync = () => { const value = sourcePercent?.textContent?.trim() || "0%"; if (pct) pct.textContent = value; if (fill) fill.style.width = value; if (completed) completed.textContent = sourceCompletion?.textContent?.trim() || "0 / 0"; };
            [sourcePercent, sourceCompletion].filter(Boolean).forEach(node => { if (window.MutationObserver) new MutationObserver(sync).observe(node, { childList:true, subtree:true, characterData:true }); }); sync();
        }
        const details = $(".report-action-group.details", root), headActions = $(".report-head-actions", root);
        if (details && headActions && !$("#reportPhase45DetailsBtn", root)) {
            const btn = document.createElement("button"); btn.type = "button"; btn.id = "reportPhase45DetailsBtn"; btn.className = "report-phase45-detail-toggle"; btn.innerHTML = `<i class="fa-solid fa-user-tie"></i> Teacher Details`;
            headActions.prepend(btn); btn.addEventListener("click", () => { const open = details.classList.toggle("phase45-open"); btn.classList.toggle("active", open); btn.innerHTML = `<i class="fa-solid ${open ? "fa-chevron-up" : "fa-user-tie"}"></i> ${open ? "Hide Details" : "Teacher Details"}`; });
        }
        const generation = $("#reportGenerationPanel", root), cards = $$(".generation-method-card", generation || root);
        if (generation && cards.length && !$(".report-phase45-workflow", generation)) {
            const names = [{ key:"automatic", label:"Automatic — use available EMIS records", node:cards.find(n => n.classList.contains("automated")) },{ key:"manual", label:"Manual — enter/correct scores", node:cards.find(n => n.classList.contains("manual")) },{ key:"hybrid", label:"Smart Hybrid — automatic + approved manual gaps", node:cards.find(n => n.classList.contains("hybrid")) }].filter(item => item.node);
            names.forEach(item => { item.host = $(".generation-method-actions", item.node); [...(item.host?.children || [])].forEach(button => button.dataset.phase45Origin = item.key); });
            const shell = document.createElement("div"); shell.className = "report-phase45-workflow";
            shell.innerHTML = `<select class="report-phase45-workflow-selector" id="reportPhase45WorkflowSelect" aria-label="Report generation workflow">${names.map(item => `<option value="${item.key}">${item.label}</option>`).join("")}</select><div class="report-phase45-workflow-actions" id="reportPhase45WorkflowActions"></div>`;
            generation.prepend(shell); const select = $("#reportPhase45WorkflowSelect", shell), actions = $("#reportPhase45WorkflowActions", shell);
            const render = () => {
                if (!actions) return;
                $$('[data-phase45-origin]', actions).forEach(button => { const owner = names.find(row => row.key === button.dataset.phase45Origin); owner?.host?.appendChild(button); });
                actions.replaceChildren();
                const item = names.find(row => row.key === select.value) || names[0]; if (!item) return;
                [...(item.host?.children || [])].forEach(button => actions.appendChild(button));
                const note = document.createElement("span"); note.className = "report-phase45-workflow-note"; note.innerHTML = item.key === "automatic" ? `<i class="fa-solid fa-bolt"></i> Fastest standard workflow` : item.key === "manual" ? `<i class="fa-solid fa-pen-ruler"></i> Direct score corrections` : `<i class="fa-solid fa-code-merge"></i> Recommended fallback`; actions.appendChild(note);
            };
            select.addEventListener("change", render); render();
        }
    }

    function init() { initCaPhase4(); initReportPhase4(); }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once:true }); else init();
    document.addEventListener("emis:page-ready", init);
})();

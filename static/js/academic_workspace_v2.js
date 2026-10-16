/* =================================================================================================
   EMIS Academic Workspace V2 — interaction polish for academic modules
   - Dropdown-first auto loading
   - Dedicated Islamiyyah guidance in generic CA/Test
   - Viewport-safe modal portaling (prevents modals rendering far down / behind transformed containers)
   ================================================================================================= */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id), clean = (v) => String(v ?? "").trim();
  let initializedRoot = null, timers = new Map();
  const later = (key, fn, delay = 120) => { clearTimeout(timers.get(key)); timers.set(key, setTimeout(fn, delay)); };
  const clickWhenReady = (button, required = []) => { if (!button || button.disabled || required.some(node => !node || !clean(node.value))) return; button.click(); };

  function portalOpenModals() {
    const selectors = [".ca-modal", ".report-modal", ".attendance-confirm-modal", ".attendance-student-modal", ".attendance-history-modal", ".attendance-delete-modal", ".essay-score-modal", ".modal-backdrop", ".result-summary-modal"];
    document.querySelectorAll(selectors.join(",")).forEach(modal => {
      const ariaOpen = modal.getAttribute("aria-hidden") === "false", classOpen = !modal.classList.contains("hidden") && (modal.classList.contains("show") || modal.classList.contains("active") || modal.classList.contains("open") || modal.classList.contains("is-open"));
      if ((ariaOpen || classOpen) && modal.parentElement !== document.body) document.body.appendChild(modal);
    });
  }

  function bindModalObserver() {
    if (document.documentElement.dataset.awModalObserver === "1") return;
    document.documentElement.dataset.awModalObserver = "1";
    const observer = new MutationObserver(mutations => { if (mutations.some(item => item.type === "attributes" || item.addedNodes.length)) portalOpenModals(); });
    observer.observe(document.body, { subtree:true, childList:true, attributes:true, attributeFilter:["class", "aria-hidden"] });
    document.addEventListener("click", () => requestAnimationFrame(portalOpenModals), true);
  }

  function academyNoticeForCA() {
    const level = $("caClassLevel"), panel = document.querySelector("#caPage .ca-control-panel");
    if (!level || !panel) return;
    let notice = $("academyCAWorkspaceNotice");
    if (!notice) {
      notice = document.createElement("div"); notice.id = "academyCAWorkspaceNotice"; notice.className = "academy-ca-workspace-notice"; notice.hidden = true;
      notice.innerHTML = `<div><i class="fa-solid fa-mosque"></i><span><strong>Islamiyyah dedicated scoring</strong><small>These classes use the Academy CA /30 + Exam /70 score workspace.</small></span></div><a href="/admin/islamiyah#academyScores"><i class="fa-solid fa-arrow-up-right-from-square"></i> Open Academy Scores</a>`;
      panel.appendChild(notice);
    }
    const sync = () => { notice.hidden = !clean(level.value).startsWith("ISLAMIYAH"); };
    level.addEventListener("change", sync); sync();
  }

  function autoSelectSingleArm(levelSelect, armSelect) {
    if (!levelSelect || !armSelect) return;
    const apply = () => later(`single-arm-${armSelect.id}`, () => {
      const choices = [...armSelect.options].filter(option => clean(option.value));
      if (choices.length === 1 && !clean(armSelect.value)) { armSelect.value = choices[0].value; armSelect.dispatchEvent(new Event("change", { bubbles:true })); }
    }, 90);
    if (levelSelect.dataset.awSingleArm !== "1") { levelSelect.dataset.awSingleArm = "1"; levelSelect.addEventListener("change", apply); }
    const observer = new MutationObserver(apply); observer.observe(armSelect, { childList:true }); apply();
  }

  function bindDropdownFirstLoading() {
    // Attendance — arm selection becomes the final step; Load Class remains available as an explicit refresh action.
    const attArm = $("armSelect"), attLoad = $("loadStudentsBtn"), attSession = $("sessionSelect"), attTerm = $("termSelect"), attLevel = $("levelSelect"), attDate = $("attendanceDate");
    autoSelectSingleArm(attLevel, attArm);
    if (attArm && attArm.dataset.awBound !== "1") { attArm.dataset.awBound = "1"; attArm.addEventListener("change", () => later("attendance", () => clickWhenReady(attLoad, [attSession, attTerm, attLevel, attArm, attDate]), 160)); }

    // CA/Test — once subject is selected, load the roster immediately. Dedicated Islamiyyah remains rule-gated by backend.
    const caSubject = $("caSubject"), caLoad = $("loadCAStudentsBtn"), caSession = $("caSession"), caTerm = $("caTerm"), caLevel = $("caClassLevel"), caArm = $("caClassArm");
    autoSelectSingleArm(caLevel, caArm);
    if (caSubject && caSubject.dataset.awBound !== "1") { caSubject.dataset.awBound = "1"; caSubject.addEventListener("change", () => later("ca", () => clickWhenReady(caLoad, [caSession, caTerm, caLevel, caArm, caSubject]), 160)); }

    // Report Sheets — exact arm selection loads the roster/source state, keeping Generate as a separate deliberate action.
    const reportArm = $("reportClassArm"), reportLoad = $("loadReportStudentsBtn"), reportSession = $("reportSession"), reportTerm = $("reportTerm"), reportLevel = $("reportClassLevel");
    autoSelectSingleArm(reportLevel, reportArm);
    if (reportArm && reportArm.dataset.awBound !== "1") { reportArm.dataset.awBound = "1"; reportArm.addEventListener("change", () => later("reports", () => clickWhenReady(reportLoad, [reportSession, reportTerm, reportLevel, reportArm]), 180)); }

    // Broadsheets — class arm is the last class selector; make the workspace feel immediate.
    const broadArm = $("broadArm"), broadLoad = $("loadBroadsheets"), broadSession = $("broadSession"), broadClass = $("broadClass");
    if (broadArm && broadArm.dataset.awBound !== "1") { broadArm.dataset.awBound = "1"; broadArm.addEventListener("change", () => later("broadsheets", () => clickWhenReady(broadLoad, [broadSession, broadClass]), 180)); }
  }

  function scrollRequestedWorkspace() {
    const params = new URLSearchParams(location.search), requested = clean(params.get("view"));
    if (requested === "cumulative") later("annual-jump", () => document.querySelector("#reportCumulativeHub")?.scrollIntoView({ behavior:"smooth", block:"start" }), 350);
  }

  function init() {
    const root = document.querySelector("main.main-content"); if (!root || root === initializedRoot) return; initializedRoot = root;
    bindModalObserver(); bindDropdownFirstLoading(); academyNoticeForCA(); portalOpenModals(); scrollRequestedWorkspace();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once:true }); else init();
  document.addEventListener("emis:page-ready", () => { initializedRoot = null; init(); });
})();

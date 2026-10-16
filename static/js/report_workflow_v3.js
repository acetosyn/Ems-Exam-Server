/* =================================================================================================
   EMIS REPORT SHEETS — WORKFLOW V3
   Keeps Manual Workstation and Third-Term Cumulative visible regardless of the selected generation lane.
   ================================================================================================= */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  function init(){
    const root=$("reportPage"), shell=document.querySelector(".report-phase45-workflow"); if(!root||!shell||$("reportQuickManualBtn")) return;
    const quick=document.createElement("div"); quick.className="report-workflow-quick-actions"; quick.innerHTML=`<button type="button" id="reportQuickManualBtn" class="report-workflow-quick manual" title="Open the full manual / hybrid result entry workstation"><i class="fa-solid fa-pen-ruler"></i><span>Manual Workstation</span><small>Enter scores</small></button><button type="button" id="reportQuickCumulativeBtn" class="report-workflow-quick cumulative" title="Open the Third Term cumulative report workspace"><i class="fa-solid fa-layer-group"></i><span>Cumulative</span><small>Third Term</small></button><span id="reportThirdTermMode" class="report-third-term-mode"><i class="fa-solid fa-circle-check"></i> Third Term = Cumulative Report</span>`; shell.appendChild(quick);
    const term=$("reportTerm"), manual=$("reportQuickManualBtn"), cumulative=$("reportQuickCumulativeBtn"), badge=$("reportThirdTermMode");
    const isThird=()=>String(term?.value||"").toUpperCase().includes("THIRD");
    const sync=()=>{const third=isThird(); cumulative?.classList.toggle("term-third",third); badge?.classList.toggle("visible",third); if(cumulative){cumulative.querySelector("span").textContent=third?"Third Term Cumulative":"Cumulative"; cumulative.title=third?"Open the cumulative compiler for this Third Term class":"Switch to Third Term and open cumulative reports";}};
    manual?.addEventListener("click",()=>{const existing=$("openManualReportStudioBtn"); if(existing) existing.click(); else $("manualResultStudioModal")?.scrollIntoView({behavior:"smooth",block:"start"});});
    cumulative?.addEventListener("click",()=>{if(window.EMISReportWorkspace?.setMode)window.EMISReportWorkspace.setMode("cumulative",false);else if(term&&!isThird()){term.value=[...term.options].find(o=>String(o.value).toUpperCase().includes("THIRD"))?.value||"THIRD TERM";term.dispatchEvent(new Event("change",{bubbles:true}));} const hub=$("reportCumulativeHub"); hub?.classList.remove("is-details-collapsed"); $("toggleCumulativeHubBtn")?.setAttribute("aria-expanded","true"); $("reportCumulativeDetails")?.setAttribute("aria-hidden","false"); hub?.scrollIntoView({behavior:"smooth",block:"start"}); if(!$("reportNextTerm")?.value)setTimeout(()=>$("reportNextTerm")?.focus(),120);});
    term?.addEventListener("change",sync); sync();
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",()=>setTimeout(init,0),{once:true}); else setTimeout(init,0); document.addEventListener("emis:page-ready",()=>setTimeout(init,0));
})();

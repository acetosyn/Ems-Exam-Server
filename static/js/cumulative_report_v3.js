/* =================================================================================================
   EMIS THIRD TERM CUMULATIVE REPORT — V3 LIVE WORKSPACE BRIDGE
   Keeps Third Term cumulative locked to Third Term and connects Manual / Automatic / Hybrid sources.
   ================================================================================================= */
(() => {
  "use strict";
  const $=id=>document.getElementById(id), page=()=>$("reportPage"), third=()=>String($("reportTerm")?.value||"").toUpperCase().includes("THIRD");
  function forceThird(){const term=$("reportTerm");if(!term)return false;if(third())return true;const option=[...term.options].find(o=>String(o.value).toUpperCase().includes("THIRD"));if(!option)return false;const wasDisabled=term.disabled;term.disabled=false;term.value=option.value;term.dispatchEvent(new Event("change",{bubbles:true}));term.disabled=wasDisabled;return true;}
  function syncThirdTermFields(){ $("thirdTermDecisionFields")?.classList.toggle("active",third()); }
  function setSource(source,run=true){const select=$("reportCumulativeSource"),bridge=window.EMISReportCumulative;source=["manual","auto","hybrid"].includes(source)?source:"manual";if(select)select.value=source;if(run)bridge?.refresh?.({source});}
  function openManual(){forceThird();setSource("manual",false);if(window.EMISReportWorkspace?.setMode)window.EMISReportWorkspace.setMode("manual");else $("openManualReportStudioBtn")?.click();}
  function init(){
    if(!page()||document.documentElement.dataset.cumulativeV3==="1")return;document.documentElement.dataset.cumulativeV3="1";
    $("cumulativeAutoGenerateBtn")?.addEventListener("click",()=>{forceThird();setSource("auto",true);}); $("cumulativeHybridSyncBtn")?.addEventListener("click",()=>{forceThird();setSource("hybrid",true);}); $("cumulativeManualGenerateBtn")?.addEventListener("click",openManual);
    $("reportTerm")?.addEventListener("change",()=>{if(page()?.dataset.workspace==="cumulative"&&!third())forceThird();syncThirdTermFields();}); syncThirdTermFields();
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();document.addEventListener("emis:page-ready",init);
})();

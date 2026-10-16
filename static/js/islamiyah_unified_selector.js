/* =================================================================================================
   EMIS ISLAMIC STUDIES — UNIFIED SCHOOL DATABASE CONTROLLER
   One top-level selector drives Register, Scores and Report Sync across Tahfeez, Islamiyyah and the
   normal Basic / Regular School database. This layer only coordinates UI state; existing engines stay intact.
   ================================================================================================= */
(() => {
  "use strict";
  const root=document.getElementById("islamiyahApp"),school=document.getElementById("academySchoolSelect"),klass=document.getElementById("academyClassSelect");if(!root||!school)return;
  function applyPromotionMode(source){document.querySelectorAll("[data-promotion-source]").forEach(box=>{const visible=source!=="regular"&&box.dataset.promotionSource===source;box.hidden=!visible;box.style.display=visible?"":"none";});const notice=document.getElementById("regularPromotionNotice");if(notice){notice.hidden=source!=="regular";notice.style.display=source==="regular"?"":"none";}}
  function publish(){const detail={school:school.value||"tahfeez",classKey:klass?.value||""};root.dataset.schoolSource=detail.school;applyPromotionMode(detail.school);window.dispatchEvent(new CustomEvent("emis:islamiyah-school-change",{detail}));}
  document.addEventListener("click",event=>{if(event.target.closest('[data-islamiyah-tab="scores"],[data-islamiyah-tab="report-sync"]'))setTimeout(publish,0)});
  window.addEventListener("emis:islamiyah-school-change",event=>{const source=event.detail?.school||school.value||"tahfeez";root.dataset.schoolSource=source;applyPromotionMode(source);});
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",()=>setTimeout(publish,0),{once:true});else setTimeout(publish,0);
  document.addEventListener("emis:page-ready",()=>setTimeout(publish,0));
})();

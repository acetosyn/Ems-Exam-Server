// EMIS Academic History Hub — Student History + Broadsheets
(() => { "use strict";
  const root=document.getElementById("academicHistoryHub"); if(!root)return;
  const tabs=[...root.querySelectorAll("[data-history-hub-tab]")],panels=[...root.querySelectorAll("[data-history-hub-panel]")];
  function valid(v){return v==="broadsheets"?"broadsheets":"history"}
  function show(view,{push=false}={}){view=valid(view);tabs.forEach(b=>b.classList.toggle("active",b.dataset.historyHubTab===view));panels.forEach(p=>p.classList.toggle("active",p.dataset.historyHubPanel===view));if(push){const u=new URL(location.href);u.searchParams.set("view",view);history.replaceState(history.state,"",u)}requestAnimationFrame(()=>window.dispatchEvent(new Event("resize")))}
  tabs.forEach(b=>b.addEventListener("click",()=>show(b.dataset.historyHubTab,{push:true})));show(new URLSearchParams(location.search).get("view")||root.dataset.initialView);
})();

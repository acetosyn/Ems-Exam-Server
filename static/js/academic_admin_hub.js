// EMIS Academic Administration Hub — Staff + Subjects + IDs
(() => { "use strict";
  const root=document.getElementById("academicAdminHub"); if(!root)return;
  const role=(root.dataset.staffRole||"").toLowerCase(),tabs=[...root.querySelectorAll("[data-admin-hub-tab]")],panels=[...root.querySelectorAll("[data-admin-hub-panel]")],valid=v=>["teachers","subjects",...(role==="admin"?["ids"]:[])].includes(v)?v:"teachers";
  if(role!=="admin"){root.querySelector('[data-admin-hub-tab="ids"]')?.remove();root.querySelector('[data-admin-hub-panel="ids"]')?.remove()}
  function show(view,{push=false}={}){view=valid(view);tabs.forEach(b=>{const active=b.dataset.adminHubTab===view;b.classList.toggle("active",active);b.setAttribute("aria-selected",String(active))});panels.forEach(p=>p.classList.toggle("active",p.dataset.adminHubPanel===view));if(push){const u=new URL(location.href);u.searchParams.set("view",view);history.replaceState(history.state,"",u)}requestAnimationFrame(()=>window.dispatchEvent(new Event("resize")))}
  tabs.forEach(b=>b.addEventListener("click",()=>show(b.dataset.adminHubTab,{push:true})));show(new URLSearchParams(location.search).get("view")||root.dataset.initialView);document.getElementById("adminHubRefresh")?.addEventListener("click",()=>location.reload());
  root.querySelectorAll(".modal,.cred-overlay,.aa-modal").forEach(modal=>{modal.dataset.emisHubModal="1";document.body.appendChild(modal)});
})();

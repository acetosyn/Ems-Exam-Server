/* ==========================================================
   privileges.js — EMIS role-aware navigation guard v3.0
   Normal Teacher keeps the regular-school workflow visible.
   Report Sheets remains OPEN for assigned score entry; official
   generation and out-of-scope class/subject access are enforced
   inside Report Sheets and again on the backend.
========================================================== */
document.addEventListener("DOMContentLoaded",()=>{
  const sidebarRole=document.querySelector(".sidebar-role"); if(!sidebarRole)return;
  const role=String(sidebarRole.textContent||"").trim().toLowerCase(); if(role!=="teacher")return;
  const allowed=new Set(["dashboard","students & classes","attendance","ca tests","ca test","results","report sheets","support"]),normalize=v=>String(v||"").replace(/\s+/g," ").trim().toLowerCase();
  document.querySelectorAll(".sidebar-menu a").forEach(link=>{const label=normalize(link.textContent),ok=allowed.has(label);link.classList.toggle("restricted",!ok);link.style.opacity=ok?"":"0.5";link.style.pointerEvents="auto";if(ok)return;link.addEventListener("click",event=>{event.preventDefault();event.stopPropagation();showAccessMessage(`Access Restricted — Teacher accounts cannot access "${label.toUpperCase()}".`)})});
});
function showAccessMessage(message){let box=document.getElementById("accessRestrictionNotice");if(!box){box=document.createElement("div");box.id="accessRestrictionNotice";Object.assign(box.style,{position:"fixed",top:"20px",right:"20px",maxWidth:"420px",padding:"14px 18px",background:"#e11d48",color:"#fff",fontWeight:"700",fontFamily:"Inter, sans-serif",borderRadius:"10px",boxShadow:"0 4px 15px rgba(0,0,0,0.2)",zIndex:"99999",transition:"all 0.3s ease"});document.body.appendChild(box)}box.textContent=message;box.style.opacity="1";box.style.transform="translateY(0)";clearTimeout(window.__emisAccessNoticeTimer);window.__emisAccessNoticeTimer=setTimeout(()=>{box.style.opacity="0";box.style.transform="translateY(-10px)"},3200)}

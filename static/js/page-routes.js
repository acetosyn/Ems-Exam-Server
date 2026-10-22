// ============================================================================
// EMIS HYBRID PAGE ROUTER — Stage 1 / Phase 5
// ----------------------------------------------------------------------------
// SAGE-inspired navigation without rewriting Flask routes:
//   • safe workspaces swap <main> + page assets in place
//   • complex/realtime/unsaved-entry pages keep normal browser navigation
//   • internal pages are prefetched on intent for faster hard navigations
//   • browser back/forward, title, active navigation and page CSS/JS stay synced
// ============================================================================

(() => {
  "use strict";

  const body = document.body, MAIN_SELECTOR = "main.main-content", SOFT_PATHS = new Set(["/admin/islamiyah","/admin/academic-history","/admin/settings","/admin/support"]), GLOBAL_CSS = new Set(["/static/css/admin1.css","/static/css/mobile_core.css","/static/css/mobile_phase4.css","/static/css/mobile_phase5.css","/static/css/academic_workspace_v2.css"]), GLOBAL_JS = new Set(["/static/js/academic_context.js","/static/js/toggle.js","/static/js/privileges.js","/static/js/academic_workspace_v2.js","/static/js/page-routes.js"]), PREFETCHED = new Set();
  let navigationSequence = 0, activeController = null;

  const sameOriginUrl = value => { try { const url = new URL(value, location.href); return url.origin === location.origin ? url : null; } catch (_) { return null; } };
  const normalizedPath = url => String(url?.pathname || "").replace(/\/{2,}/g,"/") || "/";
  const isModifiedClick = event => event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
  const isDownloadPath = path => /\.(?:pdf|csv|xlsx?|docx?|zip|json|png|jpe?g|webp)(?:$|\/)/i.test(path);
  const sourceAllowsSoftNavigation = () => body?.dataset.emisSoftNav === "1";
  const routeAllowsSoftNavigation = url => SOFT_PATHS.has(normalizedPath(url));

  function eligibleUrl(anchor) {
    if (!anchor || anchor.hasAttribute("download") || anchor.target === "_blank" || anchor.dataset.emisHardNav === "1") return null;
    const url = sameOriginUrl(anchor.href); if (!url) return null;
    const path = normalizedPath(url); if (!path.startsWith("/admin/") || path === "/admin/logout" || path.startsWith("/admin_login") || isDownloadPath(path)) return null;
    if (url.hash && path === location.pathname && url.search === location.search) return null;
    return url;
  }

  function setBusy(busy, url = "") {
    body.classList.toggle("emis-route-busy", busy); body.toggleAttribute("data-emis-router-busy", busy);
    document.dispatchEvent(new CustomEvent(busy ? "emis:navigation-start" : "emis:navigation-end", { detail:{ url } }));
  }

  function hardNavigate(url, replace = false) { activeController?.abort(); setBusy(false); replace ? location.replace(url.href || String(url)) : location.assign(url.href || String(url)); }

  function dispatchBeforeLeave(url) {
    const lifecycle = new CustomEvent("emis:page-before-leave", { cancelable:true, detail:{ from:location.href, to:url.href } }); document.dispatchEvent(lifecycle); if (lifecycle.defaultPrevented) return false;
    try { const unload = new Event("beforeunload", { cancelable:true }); window.dispatchEvent(unload); if (unload.defaultPrevented) return false; } catch (_) {}
    return true;
  }

  function pageStyles(doc) {
    const found = new Map(); doc.querySelectorAll('link[rel="stylesheet"][href]').forEach(link => { const url=sameOriginUrl(link.href); if (!url || !url.pathname.startsWith("/static/css/") || GLOBAL_CSS.has(url.pathname)) return; found.set(url.href,{ href:url.href, media:link.media || "" }); }); return [...found.values()];
  }

  function clearCurrentPageStyles() {
    document.querySelectorAll('head link[rel="stylesheet"][href], main link[rel="stylesheet"][href]').forEach(link => { const url=sameOriginUrl(link.href); if (url && url.pathname.startsWith("/static/css/") && !GLOBAL_CSS.has(url.pathname)) link.remove(); });
  }

  async function installPageStyles(styles) {
    clearCurrentPageStyles();
    await Promise.all(styles.map(item => new Promise(resolve => { const link=document.createElement("link"); link.rel="stylesheet"; link.href=item.href; if(item.media)link.media=item.media; link.dataset.emisPageStyle="1"; link.onload=link.onerror=()=>resolve(); document.head.appendChild(link); setTimeout(resolve,1100); })));
  }

  function pageScripts(doc) {
    return [...doc.querySelectorAll("script")].filter(script => { const type=(script.type || "text/javascript").toLowerCase(); if (type === "application/json" || type === "application/ld+json") return false; if (script.dataset.emisGlobal === "1") return false; if (!script.src) return Boolean(script.textContent.trim()); const url=sameOriginUrl(script.src); return Boolean(url && url.pathname.startsWith("/static/js/") && !GLOBAL_JS.has(url.pathname)); }).map(script => ({ src:script.src || "", text:script.src ? "" : script.textContent, type:script.type || "text/javascript", async:script.async, defer:script.defer }));
  }

  function clearCurrentPageScripts() {
    document.querySelectorAll('script[data-emis-page-script="1"], script[src]').forEach(script => { if (script.dataset.emisGlobal === "1") return; if (script.dataset.emisPageScript === "1") return script.remove(); if (!script.src) return; const url=sameOriginUrl(script.src); if (url && url.pathname.startsWith("/static/js/") && !GLOBAL_JS.has(url.pathname)) script.remove(); });
  }

  async function installPageScripts(scripts) {
    clearCurrentPageScripts();
    for (const item of scripts) await new Promise((resolve,reject) => { const script=document.createElement("script"); script.dataset.emisPageScript="1"; script.type=item.type; if(item.src){script.src=item.src;script.async=false;script.onload=resolve;script.onerror=()=>reject(new Error(`Could not load ${item.src}`));}else{script.textContent=item.text;resolve();} document.body.appendChild(script); });
  }

  function cleanMain(nextMain) {
    const clone=nextMain.cloneNode(true); clone.querySelectorAll('link[rel="stylesheet"]').forEach(node=>node.remove()); clone.querySelectorAll('script:not([type="application/json"]):not([type="application/ld+json"])').forEach(node=>node.remove()); return clone;
  }

  function updateAcademicContext(nextDoc) {
    const current=document.getElementById("emisAcademicContextData"), next=nextDoc.getElementById("emisAcademicContextData"); if(current && next) current.textContent=next.textContent || "{}";
    if(window.EMISAcademic?.parseContext){ window.EMISAcademicContext=window.EMISAcademic.parseContext(); window.EMISAcademic.applyDefaults?.(document); }
  }

  function syncActiveNavigation(nextDoc) {
    const selectors=["#sidebar a[href]",".emis-mobile-dock a[href]",".base-nav a[href]"];
    selectors.forEach(selector => document.querySelectorAll(selector).forEach(link => { const href=sameOriginUrl(link.href); if(!href)return; const match=[...nextDoc.querySelectorAll(selector)].find(candidate => { const url=sameOriginUrl(candidate.href); return url && url.pathname===href.pathname; }); link.classList.toggle("active",Boolean(match?.classList.contains("active"))); }));
  }

  function updateHistory(url, { push=true, restoreScroll=null } = {}) {
    if(push){ history.replaceState({ ...(history.state || {}), emisSoft:true, scrollY:window.scrollY },"",location.href); history.pushState({ emisSoft:true, scrollY:0 },"",url.href); }
    const target=Number.isFinite(restoreScroll) ? restoreScroll : 0; requestAnimationFrame(()=>window.scrollTo({top:target,left:0,behavior:"instant"}));
  }

  async function softNavigate(url, options={}) {
    const target=sameOriginUrl(url); if(!target)return false;
    if(!sourceAllowsSoftNavigation() || !routeAllowsSoftNavigation(target)) { hardNavigate(target,options.replace); return false; }
    if(!dispatchBeforeLeave(target)){ hardNavigate(target,options.replace); return false; }

    const id=++navigationSequence; activeController?.abort(); activeController=new AbortController(); setBusy(true,target.href);
    try {
      const response=await fetch(target.href,{credentials:"same-origin",headers:{Accept:"text/html","X-EMIS-Soft-Navigation":"1"},signal:activeController.signal});
      if(id!==navigationSequence)return false; if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const finalUrl=sameOriginUrl(response.url || target.href); if(!finalUrl || !routeAllowsSoftNavigation(finalUrl))return hardNavigate(finalUrl || target,options.replace),false;
      const html=await response.text(), nextDoc=new DOMParser().parseFromString(html,"text/html"), nextMain=nextDoc.querySelector(MAIN_SELECTOR); if(!nextMain || nextDoc.body?.dataset.emisSoftNav!=="1")return hardNavigate(finalUrl,options.replace),false;
      const styles=pageStyles(nextDoc), scripts=pageScripts(nextDoc), preparedMain=cleanMain(nextMain), currentMain=document.querySelector(MAIN_SELECTOR); if(!currentMain)throw new Error("Main workspace not found");

      await installPageStyles(styles); if(id!==navigationSequence)return false;
      document.dispatchEvent(new CustomEvent("emis:page-leave",{detail:{from:location.href,to:finalUrl.href}}));
      let swapped=false; const swap=()=>{ if(swapped)return; swapped=true; currentMain.replaceWith(preparedMain); document.title=nextDoc.title || document.title; body.dataset.emisEndpoint=nextDoc.body?.dataset.emisEndpoint || ""; body.dataset.emisSoftNav=nextDoc.body?.dataset.emisSoftNav || "1"; syncActiveNavigation(nextDoc); updateAcademicContext(nextDoc); };
      // Chrome stability: swap directly. Page-level CSS micro-animations remain,
      // but the browser View Transition API is intentionally not used here.
      swap();
      await installPageScripts(scripts); updateAcademicContext(nextDoc); updateHistory(finalUrl,{push:options.push!==false,restoreScroll:options.restoreScroll});
      document.querySelector(MAIN_SELECTOR)?.setAttribute("data-emis-soft-loaded","1"); document.dispatchEvent(new CustomEvent("emis:page-ready",{detail:{url:finalUrl.href,endpoint:body.dataset.emisEndpoint}})); setBusy(false,finalUrl.href); return true;
    } catch(error) {
      if(error?.name==="AbortError")return false; console.warn("[EMIS Router] Soft navigation fallback:",error); document.dispatchEvent(new CustomEvent("emis:navigation-error",{detail:{url:target.href,error}})); hardNavigate(target,options.replace); return false;
    }
  }

  function prefetch(url) {
    if(!url || PREFETCHED.has(url.href))return; PREFETCHED.add(url.href); const link=document.createElement("link"); link.rel="prefetch"; link.href=url.href; link.as="document"; document.head.appendChild(link);
  }

  // Automatic pointer/touch prefetch was removed. On Chrome it can queue several
  // expensive Flask page requests simply while the pointer crosses the sidebar.
  // EMISRouter.prefetch(...) remains available for an intentional future use.

  document.addEventListener("click",event=>{
    const routeButton=event.target.closest?.("[data-route]"); if(routeButton && !routeButton.matches("a[href]")){const raw=routeButton.getAttribute("data-route"),url=sameOriginUrl(raw); if(url && raw.startsWith("/")){event.preventDefault(); sourceAllowsSoftNavigation() && routeAllowsSoftNavigation(url) ? softNavigate(url) : hardNavigate(url); return;}}
    const anchor=event.target.closest?.("a[href]"); if(!anchor || event.defaultPrevented || isModifiedClick(event))return; const url=eligibleUrl(anchor); if(!url)return;
    if(sourceAllowsSoftNavigation() && routeAllowsSoftNavigation(url)){event.preventDefault();softNavigate(url);}
  });

  window.addEventListener("popstate",event=>{const url=sameOriginUrl(location.href); if(!url)return; if(sourceAllowsSoftNavigation() && routeAllowsSoftNavigation(url)){softNavigate(url,{push:false,restoreScroll:Number(event.state?.scrollY || 0)});}else location.reload();});
  history.replaceState({ ...(history.state || {}), emisSoft:sourceAllowsSoftNavigation(), scrollY:window.scrollY },"",location.href);

  window.EMISRouter=Object.freeze({ navigate:value=>{const url=sameOriginUrl(value);return url ? (sourceAllowsSoftNavigation() && routeAllowsSoftNavigation(url) ? softNavigate(url) : hardNavigate(url)) : false;}, prefetch:value=>{const url=sameOriginUrl(value);if(url)prefetch(url);}, isSoftRoute:value=>{const url=sameOriginUrl(value);return Boolean(url && routeAllowsSoftNavigation(url));} });
})();

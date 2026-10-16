// EMIS Global Theme System V2 — ten persistent full-application palettes inspired by SAGE's semantic theme tokens.
(() => { "use strict";
  const themes={
    snow:{label:"Classic White",icon:"fa-sun",color:"#102f50",scheme:"light"},
    ocean:{label:"Ocean Blue",icon:"fa-water",color:"#075985",scheme:"light"},
    emerald:{label:"Emerald",icon:"fa-leaf",color:"#0f6b49",scheme:"light"},
    royal:{label:"Royal Purple",icon:"fa-gem",color:"#51239b",scheme:"light"},
    ruby:{label:"Ruby Red",icon:"fa-heart",color:"#9f1239",scheme:"light"},
    amber:{label:"Solar Gold",icon:"fa-sun",color:"#9a4d06",scheme:"light"},
    aqua:{label:"Aqua Teal",icon:"fa-droplet",color:"#0b6d73",scheme:"light"},
    midnight:{label:"Midnight",icon:"fa-moon",color:"#111721",scheme:"dark"},
    deepnavy:{label:"Deep Navy",icon:"fa-compass",color:"#071426",scheme:"dark"},
    darkviolet:{label:"Dark Violet",icon:"fa-wand-magic-sparkles",color:"#1b0b2f",scheme:"dark"}
  };
  const html=document.documentElement,body=document.body,button=document.getElementById("themeToggle"),menu=document.getElementById("themeMenu"),label=document.getElementById("themeToggleLabel"),icon=document.getElementById("themeToggleIcon"),meta=document.querySelector('meta[name="theme-color"]');
  const valid=value=>themes[value]?value:"snow",isDark=theme=>themes[theme]?.scheme==="dark";
  function apply(theme,{save=true}={}){theme=valid(theme);const config=themes[theme];html.dataset.emisTheme=theme;html.style.colorScheme=config.scheme;body.dataset.emisTheme=theme;body.classList.toggle("dark",isDark(theme));body.classList.toggle("dark-mode",isDark(theme));body.classList.toggle("emis-theme-dark",isDark(theme));if(save)try{localStorage.setItem("emisTheme",theme)}catch(_){}if(label)label.textContent=config.label;if(icon)icon.className=`fa-solid ${config.icon}`;if(meta)meta.setAttribute("content",config.color);menu?.querySelectorAll("[data-theme]").forEach(element=>{const active=element.dataset.theme===theme;element.classList.toggle("active",active);element.setAttribute("aria-checked",String(active))});document.dispatchEvent(new CustomEvent("emis:theme-changed",{detail:{theme,label:config.label,dark:isDark(theme)}}))}
  function setOpen(open){if(!menu||!button)return;menu.style.display=open?"block":"none";button.setAttribute("aria-expanded",String(open))}
  const initial=valid(html.dataset.emisTheme||(()=>{try{return localStorage.getItem("emisTheme")}catch(_){return"snow"}})());apply(initial,{save:false});
  button?.addEventListener("click",event=>{event.preventDefault();event.stopPropagation();setOpen(getComputedStyle(menu).display==="none")});menu?.addEventListener("click",event=>{const option=event.target.closest("[data-theme]");if(!option)return;apply(option.dataset.theme);setOpen(false)});document.addEventListener("click",event=>{if(!event.target.closest(".theme-picker"))setOpen(false)});document.addEventListener("keydown",event=>{if(event.key==="Escape")setOpen(false)});
  window.EMISTheme={apply,get:()=>html.dataset.emisTheme,themes,isDark:()=>isDark(html.dataset.emisTheme)};
})();

/* ======================================================================
   report_voice_entry.js — EMIS Smart Voice Score Entry Extension v3.1
   Purpose:
     • Optional Speech-to-Text score entry for Manual Result Studio
     • Prevent TTS from being re-captured as student scores
     • Voice is OFF by default; wake words work only after explicit activation
     • Wake-word sleep mode, smarter navigation and correction commands
     • Voice actions for Save Draft / Save & Generate / Hybrid Generate
     • Manual typing remains fully available with auto-navigation
     • Window controls for minimize / maximize / close
   Notes:
     • report_sheet.js remains authoritative for validation, saving and generation.
     • This extension only drives the existing UI and dispatches normal events.
   ====================================================================== */

(() => {
  "use strict";

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const synth = window.speechSynthesis || null;
  const $ = id => document.getElementById(id), $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
  const modal = $("manualResultStudioModal");
  if (!modal) return;

  const ui = {
    bar: $("manualVoiceBar"), start: $("manualVoiceStartBtn"), pause: $("manualVoicePauseBtn"), stop: $("manualVoiceStopBtn"), status: $("manualVoiceStatus"), stateDot: $("manualVoiceStateDot"),
    field: $("manualVoiceField"), transcript: $("manualVoiceTranscript"), promptEach: $("manualVoicePromptEach"), safeMode: $("manualVoiceSafeMode"), voice: $("manualVoiceSelect"), tableBody: $("manualScoreTableBody"), scoreWrap: modal.querySelector(".manual-score-table-wrap"),
    saveDraft: $("saveManualDraftBtn"), saveStudent: $("saveManualStudentBtn"), saveNext: $("saveManualNextBtn"), saveGenerate: $("saveGenerateManualBtn"), saveHybrid: $("saveGenerateHybridBtn"), nextStudent: $("manualNextStudentBtn"), prevStudent: $("manualPrevStudentBtn"), clearScores: $("clearManualStudentBtn"), clearClassScores: $("clearManualClassScoresBtn"), clearModal: $("manualScoreClearModal"), studentSelect: $("manualStudentSelect"), daysOpen: $("manualDaysOpen"), present: $("manualPresent"), attendanceOverride: $("manualAttendanceOverride"), note: $("manualTeacherNote"),
    minimize: $("manualStudioMinimizeBtn"), maximize: $("manualStudioMaximizeBtn"), close: $("manualStudioCloseBtn")
  };

  const state = {
    active: false, paused: false, sleeping: false, recognizing: false, current: null, recognition: null, heardFinal: false, voices: [], chosenVoice: "", lastTranscript: "", pendingConfirmation: null,
    pendingSubjectAdvance: null, restartTimer: 0, actionTimer: 0, manualAdvanceTimer: 0, audioContext: null, dictationTarget: null, supported: !!Recognition, lang: "en-NG", ttsActive: false,
    ignoreUntil: 0, suppressRecognitionRestart: false, minimized: false, maximized: false, armed: false, languageIndex: 0, interimCandidate: "", interimCandidateAt: 0, interimStopTimer: 0, sessionAnnounced: false, commandMode: false, lastCompletedStudent: "", studentResumeTimer: 0, suspendedForModal: false
  };

  const fillerWords = new Set(["the","score","mark","marks","is","its","it's","please","enter","put","record","student","got","gets","has","was","equals","equal","to","a"]);
  const units = { zero:0, oh:0, one:1, won:1, two:2, too:2, to:2, three:3, tree:3, four:4, for:4, five:5, six:6, sex:6, seven:7, eight:8, ate:8, nine:9 };
  const teens = { ten:10, eleven:11, twelve:12, thirteen:13, fourteen:14, fifteen:15, sixteen:16, seventeen:17, eighteen:18, nineteen:19 };
  const tens = { twenty:20, thirty:30, forty:40, fifty:50, sixty:60, seventy:70, eighty:80, ninety:90 };
  const fieldAliases = { ca1:["ca1","ca 1","c a 1","first ca","first continuous assessment"], ca2:["ca2","ca 2","c a 2","second ca","second continuous assessment"], test1:["test1","test 1","first test"], test2:["test2","test 2","second test"], ass1:["ass1","assessment 1","first assessment"], ass2:["ass2","assessment 2","second assessment"], test:["test"], exam:["exam","examination"] };

  function clean(value) { return String(value ?? "").trim(); }
  function normalizeText(value) { return clean(value).toLowerCase().replace(/[’']/g,"'").replace(/[^a-z0-9.\s]/g," ").replace(/\s+/g," ").trim(); }
  function isAttendanceVoiceInput(input){ return !!input && (input === ui.daysOpen || input === ui.present); }
  function voiceMaxForInput(input){ if(input===ui.daysOpen)return 366; if(input===ui.present){ const days=Number(ui.daysOpen?.value); return Number.isFinite(days)&&days>0?Math.min(366,days):366; } return Number(input?.max || 100); }
  function labelForInput(input) { if(input===ui.daysOpen)return { subject:"Attendance",field:"DAYS OPEN",max:"366",text:"Attendance • Days Open" }; if(input===ui.present)return { subject:"Attendance",field:"PRESENT",max:String(voiceMaxForInput(input)),text:"Attendance • Present" }; const subject = clean(input?.dataset.manualSubject), field = clean(input?.dataset.manualScore).toUpperCase(), max = clean(input?.max || ""); return { subject, field, max, text:`${subject} • ${field} out of ${max}` }; }
  function setStatus(message, transcript = "") { if (ui.status) ui.status.textContent = message; if (ui.transcript && transcript !== undefined) ui.transcript.textContent = transcript || "—"; }
  function setBarState(mode = "idle") {
    ui.bar?.classList.remove("listening","paused","sleeping","unsupported"); if (mode) ui.bar?.classList.add(mode);
    if (ui.start) ui.start.disabled = !state.supported || state.active || state.sleeping || state.paused;
    if (ui.pause) { ui.pause.disabled = !state.supported || !state.armed; ui.pause.innerHTML = state.paused ? `<i class="fa-solid fa-play"></i><span>Resume</span>` : `<i class="fa-solid fa-pause"></i><span>Pause</span>`; }
    if (ui.stop) ui.stop.disabled = !state.armed;
  }

  /* ============================================================
     TTS — SELF-CAPTURE GUARD
  ============================================================ */

  function voiceScore(voice) {
    const name = clean(voice?.name).toLowerCase(), lang = clean(voice?.lang).toLowerCase(); let score = 0;
    if (lang.startsWith("en-ng")) score += 60; else if (lang.startsWith("en-gb")) score += 50; else if (lang.startsWith("en-us")) score += 40; else if (lang.startsWith("en")) score += 25;
    if (/natural|neural|online/.test(name)) score += 35; if (/microsoft|google/.test(name)) score += 20; if (/zira|aria|sonia|libby|jenny|ryan|davis|george/.test(name)) score += 8; if (voice?.localService) score += 3; return score;
  }

  function voiceKey(voice){ return `${clean(voice?.name)}|||${clean(voice?.lang)}`; }
  function preferredDefaultVoice(){
    if(!state.voices.length)return null;
    const googleUk=state.voices.find(v=>/^google uk english female$/i.test(clean(v.name))) || state.voices.find(v=>/google uk english female/i.test(clean(v.name)));
    if(googleUk)return googleUk;
    const microsoftMark=state.voices.find(v=>/microsoft\s+mark/i.test(clean(v.name))) || state.voices.find(v=>/\bmark\b/i.test(clean(v.name)) && /microsoft/i.test(clean(v.name)));
    if(microsoftMark)return microsoftMark;
    return state.voices.find(v=>/^en[-_]gb/i.test(clean(v.lang)) && /female|sonia|libby|aria|susan|kate/i.test(clean(v.name))) || [...state.voices].sort((a,b)=>voiceScore(b)-voiceScore(a))[0] || null;
  }
  function refreshVoices() {
    if (!synth || !ui.voice) return; const voices = synth.getVoices?.() || []; state.voices = voices.filter(v => /^en[-_]/i.test(v.lang || "") || /^en$/i.test(v.lang || ""));
    const stored = localStorage.getItem("emis_voice_name") || "", previous = stored || ui.voice.value; ui.voice.innerHTML = `<option value="">Best available voice</option>` + state.voices.map(v => `<option value="${encodeURIComponent(voiceKey(v))}">${clean(v.name)} • ${clean(v.lang)}</option>`).join("");
    const legacyIndex=Number(previous), legacyVoice=Number.isInteger(legacyIndex)&&String(legacyIndex)===String(previous)?state.voices[legacyIndex]:null, normalizedPrevious=legacyVoice?encodeURIComponent(voiceKey(legacyVoice)):previous;
    if(normalizedPrevious && [...ui.voice.options].some(o=>o.value===normalizedPrevious)) ui.voice.value=normalizedPrevious;
    else { const preferred=preferredDefaultVoice(); if(preferred) ui.voice.value=encodeURIComponent(voiceKey(preferred)); }
  }

  function selectedVoice() {
    if (!state.voices.length) refreshVoices(); const value=clean(ui.voice?.value); if(value){ let decoded=value; try{decoded=decodeURIComponent(value);}catch(_){} const exact=state.voices.find(v=>voiceKey(v)===decoded); if(exact)return exact; const legacy=Number(value); if(Number.isInteger(legacy)&&state.voices[legacy])return state.voices[legacy]; } return preferredDefaultVoice();
  }

  function stopRecognition({ preserveRestart = false } = {}) {
    clearTimeout(state.restartTimer); state.suppressRecognitionRestart = !preserveRestart; try { state.recognition?.abort(); } catch (_) {} state.recognizing = false; state.heardFinal = false;
    setTimeout(() => { state.suppressRecognitionRestart = false; }, 80);
  }

  function speak(text, { interrupt = true, rate = 1.08 } = {}) {
    if (!synth || !text) return Promise.resolve();
    return new Promise(resolve => {
      try {
        state.ttsActive = true; stopRecognition(); if (interrupt) synth.cancel();
        const utterance = new SpeechSynthesisUtterance(text), voice = selectedVoice();
        if (voice) utterance.voice = voice; utterance.lang = voice?.lang || "en-GB"; utterance.rate = rate; utterance.pitch = 1; utterance.volume = .90;
        const finish = () => { state.ttsActive = false; state.ignoreUntil = Date.now() + 750; resolve(); if ((state.active || state.sleeping) && !state.paused) scheduleRestart(780); };
        utterance.onend = finish; utterance.onerror = finish; synth.speak(utterance);
      } catch (_) { state.ttsActive = false; state.ignoreUntil = Date.now() + 500; resolve(); }
    });
  }

  function tone(ok = true) {
    try { state.audioContext ||= new (window.AudioContext || window.webkitAudioContext)(); const ctx = state.audioContext, osc = ctx.createOscillator(), gain = ctx.createGain(); osc.type = "sine"; osc.frequency.value = ok ? 740 : 230; gain.gain.value = .018; osc.connect(gain); gain.connect(ctx.destination); osc.start(); gain.gain.exponentialRampToValueAtTime(.0001, ctx.currentTime + (ok ? .07 : .13)); osc.stop(ctx.currentTime + (ok ? .075 : .14)); } catch (_) {}
  }

  /* ============================================================
     NUMBERS + COMMANDS
  ============================================================ */

  function parseNumberWords(raw) {
    const normalized = normalizeText(raw).replace(/,/g," "), direct = normalized.match(/(?:^|\s)(\d+(?:\.\d+)?)(?:\s|$)/); if (direct) return Number(direct[1]);
    let tokens = normalized.split(" ").filter(Boolean).filter(token => !fillerWords.has(token)); if (!tokens.length) return null;
    const decimalIndex = tokens.findIndex(token => ["point","dot","decimal"].includes(token)), wholeTokens = decimalIndex >= 0 ? tokens.slice(0,decimalIndex) : tokens, decimalTokens = decimalIndex >= 0 ? tokens.slice(decimalIndex + 1) : [];
    const allowed = token => token in units || token in teens || token in tens || token === "and"; if (!wholeTokens.every(allowed) || !decimalTokens.every(token => token in units)) return null;
    const nonAnd = wholeTokens.filter(token => token !== "and"); let whole = 0;
    if (nonAnd.length > 1 && nonAnd.every(token => token in units)) whole = Number(nonAnd.map(token => units[token]).join(""));
    else for (const token of nonAnd) { if (token in tens) whole += tens[token]; else if (token in teens) whole += teens[token]; else if (token in units) whole += units[token]; else return null; }
    if (!decimalTokens.length) return whole; return Number(`${whole}.${decimalTokens.map(token => units[token]).join("")}`);
  }

  function validScore(transcript, max) { const value = parseNumberWords(transcript); if (!Number.isFinite(value) || value < 0 || value > Number(max || 100)) return null; return Math.round(value * 100) / 100; }
  function wakeWord(text) { return /^(hello|hi|hey|hello emis|hi emis|hey emis)$/.test(normalizeText(text)); }

  const voiceActions = [
    { command:"clear_class_scores", label:"Clear Class Scores", aliases:["clear class scores","clear class score","reset class scores","reset class score","clear all class scores"] },
    { command:"clear_scores", label:"Clear Scores", aliases:["clear scores","clear score","clear student scores","clear student score","reset scores","reset score","reset student scores"] },
    { command:"hybrid_generate", label:"Generate Hybrid Class", aliases:["generate hybrid class","generate hybrid class report","generate hybrid class reports","generate hybrid reports","hybrid class reports","hybrid generate","generate hybrid"] },
    { command:"save_generate", label:"Generate Class Reports", aliases:["generate class report","generate class reports","generate class result","generate class results","generate reports","generate report"] },
    { command:"save_next", label:"Save and Next", aliases:["save and next","save next","save then next","next student and save","save and next student"] },
    { command:"save_student", label:"Save Student", aliases:["save student","save students","save scores","save student scores"] },
    { command:"save_draft", label:"Save Draft", aliases:["save draft","save drought","save draught","safe draft","safe drought","save raft"] }
  ];
  function actionCanonicalText(value){
    let t=normalizeText(value).replace(/\bplease\b/g," ").replace(/\b(drought|draught|drafts)\b/g,"draft").replace(/\b(kleer|cleer|claire)\b/g,"clear").replace(/\b(safe|saved)\b/g,"save").replace(/\b(students)\b/g,"student").replace(/\b(results)\b/g,"report").replace(/\b(reports)\b/g,"report").replace(/\b(scores)\b/g,"score").replace(/\b(courses|course|coarse)\b/g,"score").replace(/\b(hybird|highbrid|hy bread|high bread)\b/g,"hybrid").replace(/\s+/g," ").trim();
    let compact=t.replace(/\s+/g,"");
    compact=compact.replace(/drought|draught/g,"draft").replace(/kleer|cleer|claire/g,"clear").replace(/safedraft|safedrought/g,"savedraft").replace(/courses?|coarse/g,"score").replace(/scores/g,"score").replace(/students/g,"student").replace(/results|reports/g,"report").replace(/hybird|highbrid|hybread|highbread/g,"hybrid");
    return { text:t,compact };
  }
  function editDistance(a,b){ a=String(a||"");b=String(b||"");const prev=Array.from({length:b.length+1},(_,i)=>i),cur=new Array(b.length+1);for(let i=1;i<=a.length;i++){cur[0]=i;for(let j=1;j<=b.length;j++)cur[j]=Math.min(cur[j-1]+1,prev[j]+1,prev[j-1]+(a[i-1]===b[j-1]?0:1));for(let j=0;j<=b.length;j++)prev[j]=cur[j];}return prev[b.length]; }
  function phraseSimilarity(a,b){ if(!a||!b)return 0;const max=Math.max(a.length,b.length);return max?1-(editDistance(a,b)/max):1; }
  function hasActionIntent(raw){ const {text,compact}=actionCanonicalText(raw); return /^(save|clear|reset|generate|hybrid|next student)/.test(text) || /^(save|safe|clear|kleer|reset|generate|genrate|generator|hybrid|hybird|nextstudent)/.test(compact); }
  function actionCommand(text) {
    if(!hasActionIntent(text))return ""; const heard=actionCanonicalText(text); let best={ command:"",score:0 };
    for(const action of voiceActions){ for(const alias of action.aliases){ const expected=actionCanonicalText(alias); if(heard.compact===expected.compact || heard.compact.includes(expected.compact) || expected.compact.includes(heard.compact) && heard.compact.length>=7)return action.command; const score=phraseSimilarity(heard.compact,expected.compact); if(score>best.score)best={ command:action.command,score }; } }
    return best.score>=.72?best.command:"";
  }
  function actionLabel(command){ return voiceActions.find(item=>item.command===command)?.label || command; }

  function navigationCommand(text) {
    const t = normalizeText(text);
    if (wakeWord(t)) return "wake";
    if (/\b(stop voice|stop listening|turn voice off|stop)\b/.test(t)) return "stop";
    if (/\b(sleep|go to sleep)\b/.test(t)) return "sleep";
    if (/\b(pause voice|pause)\b/.test(t)) return "pause";
    if (/\b(skip subject)\b/.test(t)) return "skip_subject";
    if (/\b(skip|next box|next field|next subject|next)\b/.test(t)) return "next";
    if (/\b(back|previous box|previous field|previous|go back)\b/.test(t)) return "back";
    if (/\b(repeat|say again|prompt again)\b/.test(t)) return "repeat";
    if (/\b(clear|delete score|clear score)\b/.test(t)) return "clear";
    if (/\b(confirm|confirmed|yes|correct|okay|ok)\b/.test(t)) return "confirm";
    if (/\b(cancel|no|wrong|not correct)\b/.test(t)) return "cancel";
    return "";
  }

  function correctionFromTranscript(raw) {
    const text = normalizeText(raw); if (!/\b(correct|change|replace|set)\b/.test(text)) return null;
    let field = "";
    for (const [key, aliases] of Object.entries(fieldAliases)) { if (aliases.some(alias => text.includes(alias))) { field = key; break; } }
    if (!field) return null; const value = parseNumberWords(text.replace(/\b(correct|change|replace|set|score|mark|to|as)\b/g," ")); if (!Number.isFinite(value)) return null; return { field, value };
  }

  /* ============================================================
     NAVIGATION + MANUAL INPUT
  ============================================================ */

  function allScoreInputs() { return $$('[data-manual-score]', ui.tableBody || modal).filter(input => !input.disabled && input.offsetParent !== null); }
  function checkedRows() { return $$('[data-manual-row]', ui.tableBody || modal).filter(row => row.querySelector('[data-manual-include]')?.checked); }
  function scoreSequence() { const selected = checkedRows(), rows = selected.length ? selected : $$('[data-manual-row]', ui.tableBody || modal); return rows.flatMap(row => $$('[data-manual-score]', row)).filter(input => !input.disabled && input.offsetParent !== null); }
  function attendanceVoiceInputs(){ return [ui.daysOpen,ui.present].filter(input=>input && !input.disabled && input.offsetParent!==null); }
  function voiceSequence(){ return [...scoreSequence(),...attendanceVoiceInputs()]; }
  function voiceInputEmpty(input){ if(!input)return false; if(isAttendanceVoiceInput(input)){ if(input.dataset.voiceAttendanceCaptured==="1")return false; const raw=clean(input.value),numeric=Number(raw); if(raw!=="" && Number.isFinite(numeric) && numeric>0)return false; if(ui.attendanceOverride?.checked && raw!=="")return false; return true; } return clean(input.value)===""; }
  function firstPreferredInput() { const focused = document.activeElement, seq = voiceSequence(); if (focused && seq.includes(focused) && voiceInputEmpty(focused)) return focused; return seq.find(voiceInputEmpty) || null; }
  function resumePreferredInput() {
    const seq = voiceSequence(); if (!seq.length) return null;
    const focused = document.activeElement, anchor = focused && seq.includes(focused) ? focused : (state.current && seq.includes(state.current) ? state.current : null);
    if (anchor) { if (voiceInputEmpty(anchor)) return anchor; const i = seq.indexOf(anchor), later = seq.slice(i + 1).find(voiceInputEmpty); if (later) return later; }
    return seq.find(voiceInputEmpty) || null;
  }
  function focusManualInput(input) {
    if (!input) return; state.current = input; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; clearActiveDecorations();
    input.focus({ preventScroll:true }); input.select?.(); scrollToInput(input);
  }

  function clearActiveDecorations() {
    $$('[data-manual-score]', modal).forEach(input => input.classList.remove("voice-active")); [ui.daysOpen,ui.present].forEach(input=>input?.classList.remove("voice-active")); $$(".manual-voice-cell", modal).forEach(cell => { cell.classList.remove("manual-voice-cell"); cell.removeAttribute("data-voice-hint"); }); $$(".manual-voice-row", modal).forEach(row => row.classList.remove("manual-voice-row"));
  }

  function scrollToInput(input) { if(!input)return; const wrap=input.closest(".manual-score-table-wrap"); if(!wrap){ input.scrollIntoView?.({ behavior:"smooth",block:"center",inline:"nearest" }); return; } const row=input.closest("tr"); if(!row)return; const wr=wrap.getBoundingClientRect(),rr=row.getBoundingClientRect(); if(rr.top<wr.top+44||rr.bottom>wr.bottom-8)row.scrollIntoView({ behavior:"smooth",block:"center",inline:"nearest" }); }

  async function activateInput(input, { speakField = false } = {}) {
    if (!input) { await finishSequence(); return; }
    state.current = input; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; clearActiveDecorations(); input.classList.add("voice-active"); input.closest("tr")?.classList.add("manual-voice-row");
    const cell = input.closest("td"), label = labelForInput(input); if (cell) { cell.classList.add("manual-voice-cell"); cell.dataset.voiceHint = `Say 0–${label.max}`; }
    if (ui.field) ui.field.textContent = label.text; setStatus("Listening for score", `Say a number from 0 to ${label.max}`); scrollToInput(input); input.focus({ preventScroll:true }); input.select?.();
    if (!state.armed || !state.active || state.paused) return;
    if (speakField || ui.promptEach?.checked) await speak(`${label.subject}. ${label.field}.`, { rate:1.12 }); else listenCurrent();
  }

  function nextInputAfter(input) { const seq = voiceSequence(), i = seq.indexOf(input); return i >= 0 ? seq[i + 1] || null : null; }
  function nextEmptyInputAfter(input,{wrap=true}={}) { const seq=voiceSequence(),i=seq.indexOf(input); if(!seq.length)return null; const later=(i>=0?seq.slice(i+1):seq).find(voiceInputEmpty); if(later)return later; return wrap&&i>0?seq.slice(0,i).find(voiceInputEmpty)||null:null; }
  function previousInputBefore(input) { const seq = voiceSequence(), i = seq.indexOf(input); return i > 0 ? seq[i - 1] : null; }
  function rowTotal(row) { return $$('[data-manual-score]', row).reduce((sum,input) => sum + (Number.isFinite(Number(input.value)) ? Number(input.value) : 0),0); }
  function rowComplete(row) { return $$('[data-manual-score]', row).every(input => clean(input.value) !== "" && Number.isFinite(Number(input.value))); }

  async function advanceAfterEntry(input) {
    if (!input) return; const next = nextEmptyInputAfter(input), row = input.closest('[data-manual-row]'), nextRow = next?.closest('[data-manual-row]');

    // Manual mode must stay fully manual: never start recognition, TTS or wake-word listening.
    if (!state.armed || !state.active || state.paused) {
      if (next) focusManualInput(next);
      else { state.current = input; clearActiveDecorations(); setStatus("Manual entry ready","Scores entered manually. Click Start Voice only if you want voice assistance."); if (ui.field) ui.field.textContent = "Manual mode"; }
      return;
    }

    if (next && row === nextRow) { await activateInput(next); return; }
    if (ui.safeMode?.checked && row && rowComplete(row)) {
      const subject = clean(input.dataset.manualSubject), total = rowTotal(row); state.pendingSubjectAdvance = { next, row, subject, total };
      setStatus(`${subject} complete • total ${total}`, next ? "Say “confirm” or “next” to continue. Say “wrong” or tap a box to correct." : "Say “confirm” to finish. Say “wrong” or tap a box to correct.");
      if (ui.field) ui.field.textContent = `${subject} • TOTAL ${total}`; await speak(`${subject} total ${total}. Say confirm or next to continue.`, { rate:1.12 }); return;
    }
    if (next) await activateInput(next); else await finishSequence();
  }

  async function move(direction = 1) {
    if (direction > 0 && state.pendingSubjectAdvance) { const pending = state.pendingSubjectAdvance; state.pendingSubjectAdvance = null; pending.next ? await activateInput(pending.next) : await finishSequence(); return; }
    const target = direction > 0 ? nextEmptyInputAfter(state.current) : previousInputBefore(state.current); if (target) await activateInput(target); else if (direction > 0) await finishSequence();
  }

  async function skipSubject() { const currentRow=state.current?.closest('[data-manual-row]'),rows=checkedRows().length?checkedRows():$$('[data-manual-row]',ui.tableBody||modal),rowIndex=rows.indexOf(currentRow); let target=null; for(let i=rowIndex+1;i<rows.length&&!target;i++)target=$$('[data-manual-score]',rows[i]).find(input=>!input.disabled&&clean(input.value)==="")||null; target ? await activateInput(target) : await finishSequence(); }

  function commitValue(input, value, { source = "voice" } = {}) {
    if (!input) return; if (source === "voice") input.dataset.voiceWriting = "1"; input.value = String(value); if(isAttendanceVoiceInput(input))input.dataset.voiceAttendanceCaptured="1"; input.dispatchEvent(new Event("input",{ bubbles:true })); input.dispatchEvent(new Event("change",{ bubbles:true })); if(isAttendanceVoiceInput(input) && ui.attendanceOverride && !ui.attendanceOverride.checked && attendanceVoiceInputs().every(node=>node.dataset.voiceAttendanceCaptured==="1")){ ui.attendanceOverride.checked=true; ui.attendanceOverride.dispatchEvent(new Event("input",{ bubbles:true })); ui.attendanceOverride.dispatchEvent(new Event("change",{ bubbles:true })); } if (source === "voice") setTimeout(() => delete input.dataset.voiceWriting, 80);
    input.classList.add("voice-captured"); setTimeout(() => input.classList.remove("voice-captured"),500); tone(true);
  }

  function currentStudentKey(){ return clean(ui.studentSelect?.value || $("manualScoreStudentIdentity")?.textContent || "student"); }
  async function enterCommandMode({ announceComplete = false } = {}) {
    if (!state.armed) return; stopRecognition(); state.active = true; state.paused = false; state.sleeping = false; state.commandMode = true; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; clearActiveDecorations(); setBarState("listening"); if (ui.field) ui.field.textContent = "Voice commands ready";
    setStatus("Student entry complete • voice remains active","Say “Save and Next”, “Generate Class Reports”, “Generate Hybrid Class”, or “Clear Scores”.");
    const key=currentStudentKey(); if(announceComplete && state.lastCompletedStudent!==key){ state.lastCompletedStudent=key; await speak("Score entry complete. Voice capture remains active.",{ rate:1.08 }); } else scheduleRestart(180);
  }
  async function finishSequence() { if (!state.armed) return; await enterCommandMode({ announceComplete:true }); }

  function manualInputAutoAdvance(event) {
    const input = event.target.closest?.('[data-manual-score]'); if (!input || input.dataset.voiceWriting === "1") return; state.current = input; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; clearTimeout(state.manualAdvanceTimer);
    const raw = clean(input.value), value = Number(raw), max = Number(input.max || 100); if (!raw || !Number.isFinite(value) || value < 0 || value > max) return;
    state.manualAdvanceTimer = setTimeout(() => { if (document.activeElement !== input && state.active) return; advanceAfterEntry(input); },500);
  }

  function scoreFocusHandler(event) { const input = event.target.closest?.('[data-manual-score]') || (event.target===ui.daysOpen||event.target===ui.present?event.target:null); if (!input) return; state.current = input; state.commandMode=false; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; input.classList.add("manual-keyboard-focus"); input.select?.(); if (state.active && !state.paused) { stopRecognition(); scheduleRestart(180); } }
  function scoreBlurHandler(event) { const input=event.target.closest?.('[data-manual-score]') || (event.target===ui.daysOpen||event.target===ui.present?event.target:null); input?.classList.remove("manual-keyboard-focus"); }
  function stopNumberWheel(event) { if (event.target.closest?.('[data-manual-score]') && document.activeElement === event.target) event.preventDefault(); }
  function manualKeyboardHandler(event) { const input = event.target.closest?.('[data-manual-score]') || (event.target===ui.daysOpen||event.target===ui.present?event.target:null); if (!input) return; if (event.key === "Enter") { event.preventDefault(); clearTimeout(state.manualAdvanceTimer); advanceAfterEntry(input); } if (event.key === "ArrowRight" && event.altKey) { event.preventDefault(); move(1); } if (event.key === "ArrowLeft" && event.altKey) { event.preventDefault(); move(-1); } }

  /* ============================================================
     SPEECH RECOGNITION
  ============================================================ */

  function recognitionLanguages(){ const chosen=clean(document.getElementById("manualVoiceAccent")?.value||"auto"), list=chosen!=="auto"?[chosen,"en-GB","en-US"]:["en-NG","en-GB","en-US"]; return [...new Set(list.filter(Boolean))]; }
  function activeRecognitionLanguage(){ const langs=recognitionLanguages(); return langs[Math.min(state.languageIndex,Math.max(0,langs.length-1))] || "en-GB"; }
  function resetRecognition({ keepLanguage = true } = {}) { clearTimeout(state.interimStopTimer); state.interimStopTimer=0; state.interimCandidate=""; try{state.recognition?.abort();}catch(_){} state.recognition=null; state.recognizing=false; if(!keepLanguage)state.languageIndex=0; }
  function createRecognition() {
    if (!Recognition) return null; const recognition = new Recognition(); recognition.continuous = false; recognition.interimResults = true; recognition.maxAlternatives = 5; recognition.lang = activeRecognitionLanguage();
    recognition.onstart = () => { state.recognizing = true; state.heardFinal = false; }; recognition.onaudiostart=()=>{ if(!state.ttsActive&&!state.sleeping)setStatus("Microphone active • speak normally",state.lastTranscript||"Say the score once in your normal voice"); };
    recognition.onspeechstart = () => { if (!state.ttsActive) setStatus(state.sleeping ? "Wake-word listening…" : "Listening…", state.sleeping ? "Say hello or hi" : (state.lastTranscript || "Speak the score once")); };
    recognition.onresult = event => handleRecognitionResult(event); recognition.onnomatch=()=>{ if(!state.ttsActive)setStatus("I heard you, but not a score","Say only the number again; EMIS is still listening."); };
    recognition.onerror = event => {
      state.recognizing = false; clearTimeout(state.interimStopTimer); const code = clean(event.error);
      if (["not-allowed","service-not-allowed"].includes(code)) { state.active = false; state.sleeping = false; setBarState("unsupported"); setStatus("Microphone permission blocked","Allow microphone access in the browser, then try again."); return; }
      if (["language-not-supported","language_not_supported"].includes(code)) { const langs=recognitionLanguages(); if(state.languageIndex<langs.length-1){ state.languageIndex++; resetRecognition({keepLanguage:true}); setStatus("Switching speech model",`Trying ${activeRecognitionLanguage()}…`); scheduleRestart(160); return; } }
      if (["phrases-not-supported","phrases_not_supported"].includes(code)) { resetRecognition({keepLanguage:true}); setStatus("Compatibility speech mode enabled","Your browser does not support speech phrase hints. EMIS removed them and will continue listening normally."); scheduleRestart(160); return; }
      if (code === "no-speech") { setStatus(state.sleeping ? "Sleeping • waiting for hello" : "Listening quietly…", state.sleeping ? "Say hello or hi to wake." : "No need to shout — say the score once and pause briefly."); scheduleRestart(180); return; }
      if (code === "audio-capture") { tone(false); setStatus("Microphone is not available","Check that the correct microphone is connected and not being blocked by another app."); return; }
      if (code !== "aborted") { tone(false); resetRecognition({keepLanguage:true}); setStatus(`Speech error: ${code || "unknown"}`,"EMIS will reopen a clean listening session automatically."); scheduleRestart(220); }
    };
    recognition.onend = () => { state.recognizing = false; clearTimeout(state.interimStopTimer); if (!state.armed || state.suppressRecognitionRestart || state.ttsActive || state.paused) return; if (state.active || state.sleeping) { state.recognition=null; scheduleRestart(120); } };
    return recognition;
  }

  function scheduleRestart(delay = 160) { clearTimeout(state.restartTimer); if (!state.armed) return; state.restartTimer = setTimeout(() => { if (state.armed && (state.active || state.sleeping) && !state.paused && !state.recognizing && !state.ttsActive && Date.now() >= state.ignoreUntil) listenCurrent(); else if (state.armed && (state.active || state.sleeping) && !state.paused && Date.now() < state.ignoreUntil) scheduleRestart(Math.max(120,state.ignoreUntil-Date.now()+30)); },delay); }
  function listenCurrent() { if (!state.armed || (!state.active && !state.sleeping) || state.paused || !Recognition || state.ttsActive || Date.now() < state.ignoreUntil || state.recognizing) return; state.heardFinal = false; try { state.recognition ||= createRecognition(); if(!state.recognition)return; state.recognition.lang=activeRecognitionLanguage(); state.recognition.start(); } catch (error) { if (!/already started/i.test(clean(error?.message))) { state.recognition=null; scheduleRestart(220); } } }

  function bestFinalAlternatives(event) {
    const candidates = []; for (let i=event.resultIndex;i<event.results.length;i++) { const result = event.results[i]; if (!result.isFinal) { const live = clean(result[0]?.transcript); if (live && !state.ttsActive) { state.lastTranscript = live; if (ui.transcript) ui.transcript.textContent = live; const max=voiceMaxForInput(state.current), parsed=validScore(live,max), liveAction=actionCommand(live); if(parsed!==null || liveAction){ state.interimCandidate=live; clearTimeout(state.interimStopTimer); state.interimStopTimer=setTimeout(()=>{ if(state.recognizing&&state.active&&!state.paused&&clean(state.interimCandidate)===live){ try{state.recognition?.stop();}catch(_){} } },liveAction?360:520); } } continue; } clearTimeout(state.interimStopTimer); state.interimCandidate=""; for (let j=0;j<Math.min(result.length,5);j++) candidates.push({ transcript:clean(result[j].transcript), confidence:Number(result[j].confidence || 0) }); } return candidates;
  }

  function currentStudentVoiceName(){ const selected=ui.studentSelect?.selectedOptions?.[0]?.textContent || ""; if(selected)return clean(selected.split("—")[0]); return clean(modal.querySelector("#manualScoreStudentIdentity strong")?.textContent) || "this student"; }
  function incompleteCurrentScoreFields(){ return scoreSequence().filter(input=>clean(input.value)===""); }
  function pendingClassStudents(){ return $$('.manual-class-student.pending, .manual-class-student.draft',modal).map(button=>clean(button.querySelector('strong')?.textContent)).filter(Boolean); }
  async function explainUnavailableAction(label,button){
    if(button && !button.disabled)return false; tone(false); const student=currentStudentVoiceName(), missing=incompleteCurrentScoreFields(), pending=pendingClassStudents(); let detail="Complete the required class work first.";
    if((label==="Generate Class Reports"||label==="Generate Hybrid Class") && missing.length) detail=`Cannot ${label.toLowerCase()} yet. ${student} still has ${missing.length} incomplete score field${missing.length===1?"":"s"}. Finish and save ${student} first.`;
    else if((label==="Generate Class Reports"||label==="Generate Hybrid Class") && pending.length===1) detail=`Cannot ${label.toLowerCase()} yet. ${pending[0]} is the remaining student with incomplete saved scores.`;
    else if((label==="Generate Class Reports"||label==="Generate Hybrid Class") && pending.length>1) detail=`Cannot ${label.toLowerCase()} yet. ${pending.length} students still have incomplete saved scores. ${pending[0]} is one of them.`;
    else if((label==="Save Student"||label==="Save and Next") && missing.length) detail=`${student} still has ${missing.length} incomplete score field${missing.length===1?"":"s"}. Save Draft is available if you want to stop here.`;
    setStatus(`${label} is not available yet`,`${detail} Voice capture remains active.`); await speak(detail,{ rate:1.06 }); return true;
  }
  async function performAction(command,heardText="") {
    clearTimeout(state.actionTimer); const label=actionLabel(command); if(heardText)setStatus(`Voice command • ${label}`,`Heard “${heardText}” → ${label}`);
    if (command === "save_draft") { const wasArmed=state.armed; stopRecognition(); ui.saveDraft?.click(); setStatus("Saving draft…",heardText?`Heard “${heardText}” and matched it to Save Draft.`:"Draft save command received."); if(wasArmed)setTimeout(()=>{ state.active=true; state.sleeping=false; setBarState("listening"); scheduleRestart(180); },650); return; }
    if (command === "save_student") { if(await explainUnavailableAction("Save Student",ui.saveStudent))return; stopRecognition(); ui.saveStudent?.click(); setStatus("Saving student…","Voice capture will continue after the save."); setTimeout(()=>{ if(state.armed&&!state.paused){ state.active=true; setBarState("listening"); const input=resumePreferredInput(); input?activateInput(input):enterCommandMode(); } },650); return; }
    if (command === "save_next") { if(await explainUnavailableAction("Save and Next",ui.saveNext))return; stopRecognition(); state.commandMode=true; state.current=null; ui.saveNext?.click(); setStatus("Saving and opening next student…","Voice capture will continue automatically."); setTimeout(()=>{ if(state.armed&&!state.paused&&state.commandMode)enterCommandMode({ announceComplete:false }); },1200); return; }
    if (command === "clear_scores" || command === "clear_class_scores") { const button=command==="clear_class_scores"?ui.clearClassScores:ui.clearScores,label=command==="clear_class_scores"?"Clear Class Scores":"Clear Scores"; if(!button)return; await speak(`${label} confirmation opened.`,{ rate:1.08 }); stopRecognition(); state.active=false; state.suspendedForModal=true; setStatus("Voice waiting for confirmation","Complete or cancel the warning modal. Voice capture will resume automatically."); button.click(); return; }
    if (command === "save_generate" || command === "hybrid_generate") { const button=command==="hybrid_generate"?ui.saveHybrid:ui.saveGenerate,label=command==="hybrid_generate"?"Generate Hybrid Class":"Generate Class Reports"; if(await explainUnavailableAction(label,button))return; await speak(command==="hybrid_generate"?"Generating hybrid class reports.":"Generating class reports.",{ rate:1.08 }); hardStopVoice(); button.click(); return; }
  }
  async function applyCorrection(correction) {
    if (!correction) return false; const row = state.current?.closest('[data-manual-row]') || document.activeElement?.closest?.('[data-manual-row]'); if (!row) return false;
    const input = row.querySelector(`[data-manual-score="${correction.field}"]`); if (!input) return false; const max = Number(input.max || 100); if (correction.value < 0 || correction.value > max) { setStatus(`Correction must be 0–${max}`,`Heard ${correction.value}`); tone(false); scheduleRestart(150); return true; }
    commitValue(input,correction.value); state.current = input; setStatus("Score corrected",`${labelForInput(input).field} = ${correction.value}`); await advanceAfterEntry(input); return true;
  }

  async function handleRecognitionResult(event) {
    if (state.ttsActive || Date.now() < state.ignoreUntil) return; const alternatives = bestFinalAlternatives(event); if (!alternatives.length) return;
    state.heardFinal = true; const primary = alternatives[0], heard = primary.transcript; state.lastTranscript = heard; if (ui.transcript) ui.transcript.textContent = heard;

    if (state.sleeping) {
      if (!state.armed) { hardStopVoice(); return; }
      if (wakeWord(heard)) { await wakeVoice(); return; }
      setStatus("Voice sleeping","Wake word is active only for the exact words “hello”, “hi”, “hey”, or “hello EMIS”."); scheduleRestart(220); return;
    }

    const actionHit = alternatives.map(alt=>({ ...alt,command:actionCommand(alt.transcript) })).find(item=>item.command); if (actionHit) { if(ui.transcript)ui.transcript.textContent=actionHit.transcript; state.lastTranscript=actionHit.transcript; await performAction(actionHit.command,actionHit.transcript); return; }
    const navHit = alternatives.map(alt=>({ ...alt,command:navigationCommand(alt.transcript) })).find(item=>item.command); if (navHit) { if(ui.transcript)ui.transcript.textContent=navHit.transcript; state.lastTranscript=navHit.transcript; await handleNavigationCommand(navHit.command); return; }
    const correction = correctionFromTranscript(heard); if (correction && await applyCorrection(correction)) return;

    if (state.pendingSubjectAdvance) { setStatus("Subject total awaiting confirmation",`Say “confirm”, “next”, “wrong”, or tap a score box.`); scheduleRestart(160); return; }

    const input = state.current; if(!input){ state.commandMode=true; setStatus("Voice commands ready","Say “Save and Next”, “Generate Class Reports”, “Generate Hybrid Class”, or “Clear Scores”."); scheduleRestart(180); return; } const max = voiceMaxForInput(input); let chosen = null;
    for (const alt of alternatives) { const value = validScore(alt.transcript,max); if (value !== null) { chosen = { ...alt,value }; break; } }
    if (!chosen) { tone(false); setStatus(`Score must be 0–${max}`,`Heard: “${heard}” • say the number again`); scheduleRestart(170); return; }

    if(input===ui.daysOpen && Number(ui.present?.value||0)>chosen.value){ tone(false); setStatus("Days Open cannot be below Present",`Present is already ${clean(ui.present?.value)}. Say a value of ${clean(ui.present?.value)} or higher.`); scheduleRestart(170); return; }
    if (ui.safeMode?.checked && chosen.confidence > 0 && chosen.confidence < .32) { state.pendingConfirmation = chosen; setStatus(`Confirm ${chosen.value}?`,`Say “confirm”, “wrong”, or simply repeat the correct value.`); scheduleRestart(150); return; }
    commitValue(input,chosen.value); setStatus(isAttendanceVoiceInput(input)?"Attendance captured":"Score captured",`${labelForInput(input).field} = ${chosen.value}`); await advanceAfterEntry(input);
  }

  async function handleNavigationCommand(command) {
    if (command === "wake") { await wakeVoice(); return; }
    if (command === "confirm") {
      if (state.pendingConfirmation) { const pending = state.pendingConfirmation; state.pendingConfirmation = null; commitValue(state.current,pending.value); await advanceAfterEntry(state.current); return; }
      if (state.pendingSubjectAdvance) { const pending = state.pendingSubjectAdvance; state.pendingSubjectAdvance = null; pending.next ? await activateInput(pending.next) : await finishSequence(); return; }
      await move(1); return;
    }
    if (command === "cancel") {
      if (state.pendingConfirmation) { state.pendingConfirmation = null; setStatus("Correction ready","Say the correct score or type it manually."); scheduleRestart(120); return; }
      if (state.pendingSubjectAdvance) { const row = state.pendingSubjectAdvance.row; state.pendingSubjectAdvance = null; const first = row?.querySelector('[data-manual-score]'); if (first) await activateInput(first); setStatus("Correction mode","Tap any score box or say “correct CA1 8”, for example."); return; }
    }
    if (command === "next") { await move(1); return; }
    if (command === "back") { state.pendingSubjectAdvance = null; await move(-1); return; }
    if (command === "skip_subject") { state.pendingSubjectAdvance = null; await skipSubject(); return; }
    if (command === "repeat") { const label = labelForInput(state.current); await speak(`${label.subject}. ${label.field}.`,{ rate:1.08 }); return; }
    if (command === "clear") { if (state.current) { state.current.value = ""; state.current.dispatchEvent(new Event("input",{ bubbles:true })); } tone(true); scheduleRestart(120); return; }
    if (command === "pause") { pauseVoice(true); return; }
    if (command === "sleep") { sleepVoice(); return; }
    if (command === "stop") { hardStopVoice(); }
  }

  /* ============================================================
     START / PAUSE / WAKE / STOP
  ============================================================ */

  async function startVoice() {
    if (!state.supported) { setStatus("Speech recognition is not supported in this browser","Use current Chrome or Edge, or continue typing manually."); return; }
    const input = resumePreferredInput() || firstPreferredInput(); state.armed = true; state.active = true; state.paused = false; state.sleeping = false; state.commandMode = false; state.languageIndex=0; state.lastCompletedStudent=""; resetRecognition({keepLanguage:true}); setBarState("listening");
    if(!state.sessionAnnounced){ state.sessionAnnounced=true; setStatus("Voice capture initiated","Speak each score clearly and naturally. EMIS will move through empty fields automatically."); await speak("Voice capture initiated. Speak each score clearly in your normal voice. Keep the microphone nearby and your device volume audible for prompts. EMIS will move through the empty fields automatically.",{ rate:1.03 }); }
    if(input) await activateInput(input); else await enterCommandMode({ announceComplete:false });
  }

  async function wakeVoice() {
    if (!state.supported || !state.armed) return;
    clearTimeout(state.actionTimer); const input = resumePreferredInput();
    if (!input) { await finishSequence(); return; }
    state.sleeping = false; state.active = true; state.paused = false; setBarState("listening"); setStatus("Voice awake","Continuing from the next unfinished score box.");
    await speak("I'm listening.",{ rate:1.12 }); await activateInput(input);
  }

  function sleepVoice() {
    if (!state.armed) return;
    state.active = false; state.paused = false; state.sleeping = true; stopRecognition(); clearActiveDecorations(); setBarState("sleeping");
    setStatus("Voice sleeping","Wake with the exact word “hello”, “hi”, “hey”, or “hello EMIS”. Press Stop to switch voice off completely."); scheduleRestart(300);
  }

  function pauseVoice(forcePause = null) {
    if (!state.armed) return; state.paused = forcePause === null ? !state.paused : !!forcePause; stopRecognition();
    if (state.paused) { state.active = false; state.sleeping = false; setBarState("paused"); setStatus("Voice paused","Microphone is paused. Wake words are OFF. Click Resume to continue."); }
    else { const input = resumePreferredInput(); state.active = !!input; state.sleeping = false; setBarState(input ? "listening" : "idle"); if (input) { setStatus("Voice entry resumed","Continuing from the next unfinished score box."); activateInput(input); } else finishSequence(); }
  }

  function hardStopVoice() {
    clearTimeout(state.actionTimer); clearTimeout(state.studentResumeTimer); [ui.daysOpen,ui.present].forEach(input=>{ if(input)delete input.dataset.voiceAttendanceCaptured; }); state.armed = false; state.active = false; state.paused = false; state.sleeping = false; state.commandMode = false; state.sessionAnnounced = false; state.lastCompletedStudent = ""; state.suspendedForModal=false; state.pendingConfirmation = null; state.pendingSubjectAdvance = null;
    stopRecognition(); clearActiveDecorations(); setBarState("idle"); if (ui.field) ui.field.textContent = "Manual mode";
    setStatus("Microphone is off","Manual typing only. Click Start Voice to activate voice entry.");
  }

  /* ============================================================
     TEXT DICTATION
  ============================================================ */

  function addDictationButton(textarea) {
    if (!textarea || textarea.dataset.voiceDictationBound === "1") return; textarea.dataset.voiceDictationBound = "1"; const parent = textarea.parentElement; if (!parent) return; parent.classList.add("emis-voice-text-wrap"); const button = document.createElement("button"); button.type = "button"; button.className = "emis-voice-dictate-btn"; button.title = "Dictate text"; button.innerHTML = `<i class="fa-solid fa-microphone"></i>`; parent.appendChild(button); button.addEventListener("click",() => startTextDictation(textarea,button));
  }

  function startTextDictation(textarea,button) {
    if (!Recognition) { button.title = "Speech recognition is not supported"; return; } const resumeMode = { active:state.active, sleeping:state.sleeping, paused:state.paused }; hardStopVoice(); const recognition = new Recognition(); recognition.continuous = false; recognition.interimResults = true; recognition.lang = state.lang; recognition.maxAlternatives = 1; button.classList.add("listening");
    recognition.onresult = event => { let text = ""; for (let i=event.resultIndex;i<event.results.length;i++) if (event.results[i].isFinal) text += clean(event.results[i][0]?.transcript) + " "; text = clean(text); if (!text) return; const existing = clean(textarea.value), prefix = existing && !/[.!?]$/.test(existing) ? `${existing}. ` : existing ? `${existing} ` : ""; textarea.value = `${prefix}${text.charAt(0).toUpperCase()}${text.slice(1)}`; textarea.dispatchEvent(new Event("input",{ bubbles:true })); };
    recognition.onerror = () => tone(false); recognition.onend = () => { button.classList.remove("listening"); if (resumeMode.active) { state.active = true; state.sleeping = false; state.paused = false; setBarState("listening"); scheduleRestart(200); } else if (resumeMode.sleeping) { state.sleeping = true; state.active = false; state.paused = false; setBarState("sleeping"); scheduleRestart(200); } };
    try { recognition.start(); } catch (_) { button.classList.remove("listening"); }
  }
  function bindDictationTargets() { ["manualTeacherNote","teacherRemarkInput","principalRemarkInput"].forEach(id => addDictationButton($(id))); }

  /* ============================================================
     MODAL WINDOW CONTROLS
  ============================================================ */

  function setWindowMode(mode) {
    const panel = modal.querySelector(".manual-result-panel"); if (!panel) return; modal.classList.remove("manual-studio-minimized","manual-studio-maximized"); state.minimized = mode === "minimized"; state.maximized = mode === "maximized";
    if (state.minimized) { modal.classList.add("manual-studio-minimized"); if (state.armed) pauseVoice(true); }
    if (state.maximized) modal.classList.add("manual-studio-maximized");
    if (ui.maximize) ui.maximize.innerHTML = state.maximized ? `<i class="fa-solid fa-down-left-and-up-right-to-center"></i>` : `<i class="fa-solid fa-up-right-and-down-left-from-center"></i>`;
  }

  function toggleMinimize() { setWindowMode(state.minimized ? "normal" : "minimized"); }
  function toggleMaximize() { setWindowMode(state.maximized ? "normal" : "maximized"); }
  function closeStudioVoice() { hardStopVoice(); setWindowMode("normal"); }

  /* ============================================================
     MUTATION / INIT
  ============================================================ */

  function onGridMutation() { if (!ui.tableBody || !state.armed || !state.active || state.paused || state.ttsActive) return; clearTimeout(state.studentResumeTimer); state.studentResumeTimer=setTimeout(()=>{ const candidate=resumePreferredInput(); if(candidate){ state.commandMode=false; activateInput(candidate); } else if(!state.commandMode) enterCommandMode({ announceComplete:false }); },110); }
  function resumeVoiceForLoadedStudent(){ [ui.daysOpen,ui.present].forEach(input=>{ if(input)delete input.dataset.voiceAttendanceCaptured; }); if(!state.armed || state.paused)return; clearTimeout(state.studentResumeTimer); state.studentResumeTimer=setTimeout(()=>{ state.active=true; state.sleeping=false; state.commandMode=false; state.lastCompletedStudent=""; setBarState("listening"); const candidate=resumePreferredInput(); candidate?activateInput(candidate):enterCommandMode({ announceComplete:false }); },160); }
  function resumeAfterClearModal(){ if(!state.suspendedForModal || !state.armed || state.paused)return; state.suspendedForModal=false; state.active=true; setBarState("listening"); const candidate=resumePreferredInput(); candidate?activateInput(candidate):enterCommandMode({ announceComplete:false }); }

  function init() {
    refreshVoices(); if (synth) synth.onvoiceschanged = refreshVoices; bindDictationTargets();
    ui.start?.addEventListener("click",startVoice); ui.pause?.addEventListener("click",() => pauseVoice()); ui.stop?.addEventListener("click",hardStopVoice);
    ui.voice?.addEventListener("change",() => { state.chosenVoice = ui.voice.value; localStorage.setItem("emis_voice_name",ui.voice.value); }); document.getElementById("manualVoiceAccent")?.addEventListener("change",event=>{ localStorage.setItem("emis_voice_accent",event.target.value); state.languageIndex=0; resetRecognition({keepLanguage:true}); if(state.armed&&(state.active||state.sleeping)&&!state.paused)scheduleRestart(140); });
    ui.promptEach?.addEventListener("change",() => localStorage.setItem("emis_voice_prompt_each",ui.promptEach.checked ? "1":"0")); ui.safeMode?.addEventListener("change",() => localStorage.setItem("emis_voice_safe_mode",ui.safeMode.checked ? "1":"0"));
    ui.minimize?.addEventListener("click",toggleMinimize); ui.maximize?.addEventListener("click",toggleMaximize); ui.close?.addEventListener("click",closeStudioVoice);
    refreshVoices(); const storedVoice = localStorage.getItem("emis_voice_name"); if (storedVoice && [...(ui.voice?.options||[])].some(option=>option.value===storedVoice)) ui.voice.value = storedVoice; const accent=document.getElementById("manualVoiceAccent"),storedAccent=localStorage.getItem("emis_voice_accent"); if(accent&&storedAccent&&[...accent.options].some(option=>option.value===storedAccent))accent.value=storedAccent; if (ui.promptEach) ui.promptEach.checked = localStorage.getItem("emis_voice_prompt_each") === "1"; if (ui.safeMode) ui.safeMode.checked = localStorage.getItem("emis_voice_safe_mode") === "1";

    modal.addEventListener("keydown",manualKeyboardHandler); modal.addEventListener("focusin",scoreFocusHandler); modal.addEventListener("focusout",scoreBlurHandler); modal.addEventListener("input",manualInputAutoAdvance); modal.addEventListener("wheel",stopNumberWheel,{ passive:false }); document.addEventListener("emis:manual-student-loaded",resumeVoiceForLoadedStudent);
    modal.addEventListener("transitionend",() => { if (modal.getAttribute("aria-hidden") === "true") closeStudioVoice(); });
    if (ui.tableBody) new MutationObserver(() => { bindDictationTargets(); onGridMutation(); }).observe(ui.tableBody,{ childList:true,subtree:true }); new MutationObserver(bindDictationTargets).observe(document.body,{ childList:true,subtree:true });
    new MutationObserver(() => { if (modal.getAttribute("aria-hidden") === "true") closeStudioVoice(); }).observe(modal,{ attributes:true,attributeFilter:["aria-hidden"] });
    if(ui.clearModal)new MutationObserver(()=>{ if(ui.clearModal.getAttribute("aria-hidden")==="true")resumeAfterClearModal(); }).observe(ui.clearModal,{ attributes:true,attributeFilter:["aria-hidden"] });

    if (!state.supported) { setBarState("unsupported"); setStatus("Voice entry unavailable in this browser","Typing and keyboard auto-navigation still work."); }
    else { setBarState("idle"); setStatus("Manual mode • microphone is off","Voice entry will not listen or wake until you click Start Voice."); }

    window.EMISVoiceEntry = { start:startVoice, pause:pauseVoice, sleep:sleepVoice, stop:hardStopVoice, wake:wakeVoice, next:() => move(1), previous:() => move(-1), supported:state.supported, isArmed:() => state.armed };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",init,{ once:true }); else init();
})();

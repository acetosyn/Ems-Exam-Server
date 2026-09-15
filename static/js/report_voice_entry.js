/* ======================================================================
   report_voice_entry.js — EMIS Smart Voice Score Entry Extension v2.1
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
    saveDraft: $("saveManualDraftBtn"), saveGenerate: $("saveGenerateManualBtn"), saveHybrid: $("saveGenerateHybridBtn"), nextStudent: $("manualNextStudentBtn"), prevStudent: $("manualPrevStudentBtn"), note: $("manualTeacherNote"),
    minimize: $("manualStudioMinimizeBtn"), maximize: $("manualStudioMaximizeBtn"), close: $("manualStudioCloseBtn")
  };

  const state = {
    active: false, paused: false, sleeping: false, recognizing: false, current: null, recognition: null, heardFinal: false, voices: [], chosenVoice: "", lastTranscript: "", pendingConfirmation: null,
    pendingSubjectAdvance: null, restartTimer: 0, actionTimer: 0, manualAdvanceTimer: 0, audioContext: null, dictationTarget: null, supported: !!Recognition, lang: "en-NG", ttsActive: false,
    ignoreUntil: 0, suppressRecognitionRestart: false, minimized: false, maximized: false, armed: false
  };

  const fillerWords = new Set(["the","score","mark","marks","is","its","it's","please","enter","put","record","student","got","gets","has","was","equals","equal","to","a"]);
  const units = { zero:0, oh:0, one:1, won:1, two:2, too:2, to:2, three:3, tree:3, four:4, for:4, five:5, six:6, sex:6, seven:7, eight:8, ate:8, nine:9 };
  const teens = { ten:10, eleven:11, twelve:12, thirteen:13, fourteen:14, fifteen:15, sixteen:16, seventeen:17, eighteen:18, nineteen:19 };
  const tens = { twenty:20, thirty:30, forty:40, fifty:50, sixty:60, seventy:70, eighty:80, ninety:90 };
  const fieldAliases = { ca1:["ca1","ca 1","c a 1","first ca","first continuous assessment"], ca2:["ca2","ca 2","c a 2","second ca","second continuous assessment"], test1:["test1","test 1","first test"], test2:["test2","test 2","second test"], ass1:["ass1","assessment 1","first assessment"], ass2:["ass2","assessment 2","second assessment"], test:["test"], exam:["exam","examination"] };

  function clean(value) { return String(value ?? "").trim(); }
  function normalizeText(value) { return clean(value).toLowerCase().replace(/[’']/g,"'").replace(/[^a-z0-9.\s]/g," ").replace(/\s+/g," ").trim(); }
  function labelForInput(input) { const subject = clean(input?.dataset.manualSubject), field = clean(input?.dataset.manualScore).toUpperCase(), max = clean(input?.max || ""); return { subject, field, max, text:`${subject} • ${field} out of ${max}` }; }
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

  function refreshVoices() {
    if (!synth || !ui.voice) return; const voices = synth.getVoices?.() || []; state.voices = voices.filter(v => /^en[-_]/i.test(v.lang || "") || /^en$/i.test(v.lang || ""));
    const previous = ui.voice.value; ui.voice.innerHTML = `<option value="">Best available voice</option>` + state.voices.map((v,i) => `<option value="${i}">${clean(v.name)} • ${clean(v.lang)}</option>`).join("");
    if (previous && [...ui.voice.options].some(o => o.value === previous)) ui.voice.value = previous;
  }

  function selectedVoice() {
    if (!state.voices.length) refreshVoices(); const explicit = Number(ui.voice?.value);
    if (ui.voice?.value !== "" && Number.isInteger(explicit) && state.voices[explicit]) return state.voices[explicit];
    return [...state.voices].sort((a,b) => voiceScore(b) - voiceScore(a))[0] || null;
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
        if (voice) utterance.voice = voice; utterance.lang = voice?.lang || "en-NG"; utterance.rate = rate; utterance.pitch = 1; utterance.volume = .90;
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

  function actionCommand(text) {
    const t = normalizeText(text);
    if (/\b(save and hybrid generate|save hybrid generate|save then hybrid generate|hybrid generate|generate hybrid|hybrid)\b/.test(t)) return "hybrid_generate";
    if (/\b(save and generate|save generate|save then generate)\b/.test(t)) return "save_generate";
    if (/^(generate|generate report|generate result)$/.test(t)) return "generate_pending";
    if (/\b(save draft)\b/.test(t) || t === "save") return "save_draft";
    return "";
  }

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
  function firstPreferredInput() { const focused = document.activeElement?.matches?.('[data-manual-score]') ? document.activeElement : null, seq = scoreSequence(); if (focused && seq.includes(focused) && clean(focused.value) === "") return focused; return seq.find(input => clean(input.value) === "") || null; }
  function resumePreferredInput() {
    const seq = scoreSequence(); if (!seq.length) return null;
    const focused = document.activeElement?.matches?.('[data-manual-score]') ? document.activeElement : null;
    const anchor = focused && seq.includes(focused) ? focused : (state.current && seq.includes(state.current) ? state.current : null);
    if (anchor) {
      if (clean(anchor.value) === "") return anchor;
      const i = seq.indexOf(anchor), later = seq.slice(i + 1).find(input => clean(input.value) === "");
      if (later) return later;
    }
    return seq.find(input => clean(input.value) === "") || null;
  }
  function focusManualInput(input) {
    if (!input) return; state.current = input; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; clearActiveDecorations();
    input.focus({ preventScroll:true }); input.select?.(); scrollToInput(input);
  }

  function clearActiveDecorations() {
    $$('[data-manual-score]', modal).forEach(input => input.classList.remove("voice-active")); $$(".manual-voice-cell", modal).forEach(cell => { cell.classList.remove("manual-voice-cell"); cell.removeAttribute("data-voice-hint"); }); $$(".manual-voice-row", modal).forEach(row => row.classList.remove("manual-voice-row"));
  }

  function scrollToInput(input) { const wrap = input?.closest(".manual-score-table-wrap"); if (!wrap) return; const row = input.closest("tr"), wr = wrap.getBoundingClientRect(), rr = row.getBoundingClientRect(); if (rr.top < wr.top + 44 || rr.bottom > wr.bottom - 8) row.scrollIntoView({ behavior:"smooth", block:"center", inline:"nearest" }); }

  async function activateInput(input, { speakField = false } = {}) {
    if (!input) { await finishSequence(); return; }
    state.current = input; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; clearActiveDecorations(); input.classList.add("voice-active"); input.closest("tr")?.classList.add("manual-voice-row");
    const cell = input.closest("td"), label = labelForInput(input); if (cell) { cell.classList.add("manual-voice-cell"); cell.dataset.voiceHint = `Say 0–${label.max}`; }
    if (ui.field) ui.field.textContent = label.text; setStatus("Listening for score", `Say a number from 0 to ${label.max}`); scrollToInput(input); input.focus({ preventScroll:true }); input.select?.();
    if (!state.armed || !state.active || state.paused) return;
    if (speakField || ui.promptEach?.checked) await speak(`${label.subject}. ${label.field}.`, { rate:1.12 }); else listenCurrent();
  }

  function nextInputAfter(input) { const seq = scoreSequence(), i = seq.indexOf(input); return i >= 0 ? seq[i + 1] || null : null; }
  function previousInputBefore(input) { const seq = scoreSequence(), i = seq.indexOf(input); return i > 0 ? seq[i - 1] : null; }
  function rowTotal(row) { return $$('[data-manual-score]', row).reduce((sum,input) => sum + (Number.isFinite(Number(input.value)) ? Number(input.value) : 0),0); }
  function rowComplete(row) { return $$('[data-manual-score]', row).every(input => clean(input.value) !== "" && Number.isFinite(Number(input.value))); }

  async function advanceAfterEntry(input) {
    if (!input) return; const next = nextInputAfter(input), row = input.closest('[data-manual-row]'), nextRow = next?.closest('[data-manual-row]');

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
    const target = direction > 0 ? nextInputAfter(state.current) : previousInputBefore(state.current); if (target) await activateInput(target); else if (direction > 0) await finishSequence();
  }

  async function skipSubject() { const currentRow = state.current?.closest('[data-manual-row]'), rows = checkedRows().length ? checkedRows() : $$('[data-manual-row]', ui.tableBody || modal), rowIndex = rows.indexOf(currentRow), target = rows[rowIndex + 1]?.querySelector('[data-manual-score]'); target ? await activateInput(target) : await finishSequence(); }

  function commitValue(input, value, { source = "voice" } = {}) {
    if (!input) return; if (source === "voice") input.dataset.voiceWriting = "1"; input.value = String(value); input.dispatchEvent(new Event("input",{ bubbles:true })); input.dispatchEvent(new Event("change",{ bubbles:true })); if (source === "voice") setTimeout(() => delete input.dataset.voiceWriting, 80);
    input.classList.add("voice-captured"); setTimeout(() => input.classList.remove("voice-captured"),500); tone(true);
  }

  async function finishSequence() {
    stopRecognition(); state.active = false; state.paused = false; state.sleeping = false; state.armed = false; state.pendingConfirmation = null; state.pendingSubjectAdvance = null;
    clearActiveDecorations(); setBarState("idle"); if (ui.field) ui.field.textContent = "Student scores complete";
    setStatus("Voice entry complete","Microphone is off. Manual typing remains available. Click Start Voice if you want voice assistance again.");
    await speak("Score entry complete.",{ rate:1.1 });
  }

  function manualInputAutoAdvance(event) {
    const input = event.target.closest?.('[data-manual-score]'); if (!input || input.dataset.voiceWriting === "1") return; state.current = input; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; clearTimeout(state.manualAdvanceTimer);
    const raw = clean(input.value), value = Number(raw), max = Number(input.max || 100); if (!raw || !Number.isFinite(value) || value < 0 || value > max) return;
    state.manualAdvanceTimer = setTimeout(() => { if (document.activeElement !== input && state.active) return; advanceAfterEntry(input); },500);
  }

  function scoreFocusHandler(event) { const input = event.target.closest?.('[data-manual-score]'); if (!input) return; state.current = input; state.pendingConfirmation = null; state.pendingSubjectAdvance = null; input.classList.add("manual-keyboard-focus"); input.select?.(); if (state.active && !state.paused) { stopRecognition(); scheduleRestart(180); } }
  function scoreBlurHandler(event) { event.target.closest?.('[data-manual-score]')?.classList.remove("manual-keyboard-focus"); }
  function stopNumberWheel(event) { if (event.target.closest?.('[data-manual-score]') && document.activeElement === event.target) event.preventDefault(); }
  function manualKeyboardHandler(event) { const input = event.target.closest?.('[data-manual-score]'); if (!input) return; if (event.key === "Enter") { event.preventDefault(); clearTimeout(state.manualAdvanceTimer); advanceAfterEntry(input); } if (event.key === "ArrowRight" && event.altKey) { event.preventDefault(); move(1); } if (event.key === "ArrowLeft" && event.altKey) { event.preventDefault(); move(-1); } }

  /* ============================================================
     SPEECH RECOGNITION
  ============================================================ */

  function createRecognition() {
    if (!Recognition) return null; const recognition = new Recognition(); recognition.continuous = false; recognition.interimResults = true; recognition.maxAlternatives = 5; recognition.lang = state.lang;
    recognition.onstart = () => { state.recognizing = true; state.heardFinal = false; };
    recognition.onspeechstart = () => { if (!state.ttsActive) setStatus(state.sleeping ? "Wake-word listening…" : "Listening…", state.sleeping ? "Say hello or hi" : (state.lastTranscript || "Speak the score")); };
    recognition.onresult = event => handleRecognitionResult(event);
    recognition.onerror = event => {
      state.recognizing = false; const code = clean(event.error);
      if (["not-allowed","service-not-allowed"].includes(code)) { state.active = false; state.sleeping = false; setBarState("unsupported"); setStatus("Microphone permission blocked","Allow microphone access in the browser, then try again."); return; }
      if (code === "no-speech") { setStatus(state.sleeping ? "Sleeping • waiting for hello" : "No speech heard", state.sleeping ? "Say hello or hi to wake." : "You do not need to shout. Move closer to the microphone or increase Windows microphone input level if needed."); return; }
      if (code !== "aborted") { tone(false); setStatus(`Speech error: ${code || "unknown"}`,"Click Start Voice to retry if listening stops."); }
    };
    recognition.onend = () => { state.recognizing = false; if (!state.armed || state.suppressRecognitionRestart || state.ttsActive || state.paused) return; if (state.active || state.sleeping) scheduleRestart(180); };
    return recognition;
  }

  function scheduleRestart(delay = 160) { clearTimeout(state.restartTimer); if (!state.armed) return; state.restartTimer = setTimeout(() => { if (state.armed && (state.active || state.sleeping) && !state.paused && !state.recognizing && !state.ttsActive && Date.now() >= state.ignoreUntil) listenCurrent(); else if (state.armed && (state.active || state.sleeping) && !state.paused && Date.now() < state.ignoreUntil) scheduleRestart(Math.max(120,state.ignoreUntil-Date.now()+30)); },delay); }
  function listenCurrent() { if (!state.armed || (!state.active && !state.sleeping) || state.paused || !Recognition || state.ttsActive || Date.now() < state.ignoreUntil || state.recognizing) return; state.heardFinal = false; try { state.recognition ||= createRecognition(); state.recognition.lang = state.lang; state.recognition.start(); } catch (error) { if (!/already started/i.test(clean(error?.message))) scheduleRestart(220); } }

  function bestFinalAlternatives(event) {
    const candidates = []; for (let i=event.resultIndex;i<event.results.length;i++) { const result = event.results[i]; if (!result.isFinal) { const live = clean(result[0]?.transcript); if (live && !state.ttsActive) { state.lastTranscript = live; if (ui.transcript) ui.transcript.textContent = live; } continue; } for (let j=0;j<Math.min(result.length,5);j++) candidates.push({ transcript:clean(result[j].transcript), confidence:Number(result[j].confidence || 0) }); } return candidates;
  }

  async function performAction(command) {
    clearTimeout(state.actionTimer);
    if (command === "save_draft") { const wasActive = state.active; stopRecognition(); ui.saveDraft?.click(); setStatus("Saving draft…","Draft save command received."); if (wasActive) setTimeout(() => { state.active = true; state.sleeping = false; setBarState("listening"); scheduleRestart(200); },900); return; }
    if (command === "save_generate") { hardStopVoice(); ui.saveGenerate?.click(); return; }
    if (command === "hybrid_generate") { hardStopVoice(); ui.saveHybrid?.click(); return; }
    if (command === "generate_pending") { setStatus("Generate command heard","Waiting 3 seconds for “hybrid”. Say “hybrid” now for Hybrid Generate."); state.actionTimer = setTimeout(() => { hardStopVoice(); ui.saveGenerate?.click(); },3000); }
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

    const action = actionCommand(heard); if (action) { await performAction(action); return; }
    const nav = navigationCommand(heard); if (nav) { await handleNavigationCommand(nav); return; }
    const correction = correctionFromTranscript(heard); if (correction && await applyCorrection(correction)) return;

    if (state.pendingSubjectAdvance) { setStatus("Subject total awaiting confirmation",`Say “confirm”, “next”, “wrong”, or tap a score box.`); scheduleRestart(160); return; }

    const input = state.current, max = Number(input?.max || 100); let chosen = null;
    for (const alt of alternatives) { const value = validScore(alt.transcript,max); if (value !== null) { chosen = { ...alt,value }; break; } }
    if (!chosen) { tone(false); setStatus(`Score must be 0–${max}`,`Heard: “${heard}” • say the number again`); scheduleRestart(170); return; }

    if (ui.safeMode?.checked && chosen.confidence > 0 && chosen.confidence < .32) { state.pendingConfirmation = chosen; setStatus(`Confirm ${chosen.value}?`,`Say “confirm”, “wrong”, or simply repeat the correct score.`); scheduleRestart(150); return; }
    commitValue(input,chosen.value); setStatus("Score captured",`${labelForInput(input).field} = ${chosen.value}`); await advanceAfterEntry(input);
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
    const input = resumePreferredInput() || firstPreferredInput(); if (!input) { setStatus("No unfinished score boxes","All visible score boxes are already complete."); return; }
    state.armed = true; state.active = true; state.paused = false; state.sleeping = false; setBarState("listening");
    await speak("Voice entry enabled.",{ rate:1.12 }); await activateInput(input);
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
    clearTimeout(state.actionTimer); state.armed = false; state.active = false; state.paused = false; state.sleeping = false; state.pendingConfirmation = null; state.pendingSubjectAdvance = null;
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

  function onGridMutation() { if (!ui.tableBody) return; if (state.armed && state.active) { const candidate = resumePreferredInput(); if (candidate) activateInput(candidate); else finishSequence(); } }

  function init() {
    refreshVoices(); if (synth) synth.onvoiceschanged = refreshVoices; bindDictationTargets();
    ui.start?.addEventListener("click",startVoice); ui.pause?.addEventListener("click",() => pauseVoice()); ui.stop?.addEventListener("click",hardStopVoice);
    ui.voice?.addEventListener("change",() => { state.chosenVoice = ui.voice.value; localStorage.setItem("emis_voice_name",ui.voice.value); });
    ui.promptEach?.addEventListener("change",() => localStorage.setItem("emis_voice_prompt_each",ui.promptEach.checked ? "1":"0")); ui.safeMode?.addEventListener("change",() => localStorage.setItem("emis_voice_safe_mode",ui.safeMode.checked ? "1":"0"));
    ui.minimize?.addEventListener("click",toggleMinimize); ui.maximize?.addEventListener("click",toggleMaximize); ui.close?.addEventListener("click",closeStudioVoice);
    const storedVoice = localStorage.getItem("emis_voice_name"); if (storedVoice) ui.voice.value = storedVoice; if (ui.promptEach) ui.promptEach.checked = localStorage.getItem("emis_voice_prompt_each") === "1"; if (ui.safeMode) ui.safeMode.checked = localStorage.getItem("emis_voice_safe_mode") === "1";

    modal.addEventListener("keydown",manualKeyboardHandler); modal.addEventListener("focusin",scoreFocusHandler); modal.addEventListener("focusout",scoreBlurHandler); modal.addEventListener("input",manualInputAutoAdvance); modal.addEventListener("wheel",stopNumberWheel,{ passive:false });
    modal.addEventListener("transitionend",() => { if (modal.getAttribute("aria-hidden") === "true") closeStudioVoice(); });
    if (ui.tableBody) new MutationObserver(() => { bindDictationTargets(); onGridMutation(); }).observe(ui.tableBody,{ childList:true,subtree:true }); new MutationObserver(bindDictationTargets).observe(document.body,{ childList:true,subtree:true });
    new MutationObserver(() => { if (modal.getAttribute("aria-hidden") === "true") closeStudioVoice(); }).observe(modal,{ attributes:true,attributeFilter:["aria-hidden"] });

    if (!state.supported) { setBarState("unsupported"); setStatus("Voice entry unavailable in this browser","Typing and keyboard auto-navigation still work."); }
    else { setBarState("idle"); setStatus("Manual mode • microphone is off","Voice entry will not listen or wake until you click Start Voice."); }

    window.EMISVoiceEntry = { start:startVoice, pause:pauseVoice, sleep:sleepVoice, stop:hardStopVoice, wake:wakeVoice, next:() => move(1), previous:() => move(-1), supported:state.supported, isArmed:() => state.armed };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",init,{ once:true }); else init();
})();

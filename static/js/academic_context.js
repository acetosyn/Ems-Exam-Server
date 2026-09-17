/* ======================================================================
   academic_context.js — Global EMIS Academic Period Defaults
   ----------------------------------------------------------------------
   Reads the server-injected global academic setting once per page and
   applies it to known year/session/term selectors before page modules
   initialize. It never fires change events and never prevents staff from
   manually choosing a historical period afterwards.
   ====================================================================== */

(() => {
    "use strict";

    const DATA_NODE_ID = "emisAcademicContextData";
    const YEAR_IDS = ["yearSelector"];
    const SESSION_IDS = ["sessionSelect", "historySessionSelect", "caSession", "reportSession", "sessionSelector"];
    const TERM_IDS = ["termSelect", "historyTermSelect", "caTerm", "reportTerm", "termSelector"];

    const clean = value => String(value ?? "").trim();

    function normalizeTerm(value) {
        const raw = clean(value).toUpperCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
        if (["FIRST", "FIRST TERM", "1", "1ST", "1ST TERM", "TERM 1"].includes(raw)) return "FIRST";
        if (["SECOND", "SECOND TERM", "2", "2ND", "2ND TERM", "TERM 2"].includes(raw)) return "SECOND";
        if (["THIRD", "THIRD TERM", "3", "3RD", "3RD TERM", "TERM 3"].includes(raw)) return "THIRD";
        return "";
    }

    function termLabel(value) {
        return { FIRST: "FIRST TERM", SECOND: "SECOND TERM", THIRD: "THIRD TERM" }[normalizeTerm(value)] || "";
    }

    function parseContext() {
        const node = document.getElementById(DATA_NODE_ID);
        if (!node) return {};

        try {
            const raw = JSON.parse(node.textContent || "{}");
            const year = clean(raw.current_year || raw.year);
            const session = clean(raw.current_session || raw.academic_session || raw.session) || (year ? `${year}/${Number(year) + 1}` : "");
            const term = normalizeTerm(raw.current_term || raw.term);

            return {
                ...raw,
                current_year: year,
                year,
                current_session: session,
                academic_session: session,
                session,
                current_term: term,
                term,
                current_term_label: termLabel(term),
                term_label: termLabel(term),
            };
        } catch (error) {
            console.warn("[EMIS] Could not parse global academic context:", error);
            return {};
        }
    }

    function optionByValue(select, value, comparator = null) {
        if (!select || !value) return null;
        return [...select.options].find(option => comparator ? comparator(option.value, value) : clean(option.value) === clean(value)) || null;
    }

    function ensureOption(select, value, label = value) {
        if (!select || !value) return null;
        let option = optionByValue(select, value);
        if (option) return option;

        option = document.createElement("option");
        option.value = value;
        option.textContent = label || value;
        select.appendChild(option);
        return option;
    }

    function applyYear(select, context) {
        const year = clean(context.current_year || context.year);
        if (!select || !year) return false;
        const option = ensureOption(select, year, year);
        select.value = option.value;
        select.dataset.academicDefault = year;
        return true;
    }

    function ensureAcademicSessionRange(select, context) {
        if (!select || select.id === "sessionSelector") return;
        const min = Number(context.year_min || 2025), max = Number(context.year_max || 2040);
        if (!Number.isFinite(min) || !Number.isFinite(max) || max < min) return;
        for (let year = min; year <= max; year += 1) ensureOption(select, `${year}/${year + 1}`, `${year}/${year + 1}`);
    }

    function applySession(select, context) {
        const session = clean(context.current_session || context.session);
        ensureAcademicSessionRange(select, context);
        if (!select || !session) return false;
        const option = ensureOption(select, session, session);
        select.value = option.value;
        select.dataset.academicDefault = session;
        return true;
    }

    function applyTerm(select, context) {
        const term = normalizeTerm(context.current_term || context.term);
        if (!select || !term) return false;

        let option = optionByValue(select, term, (candidate, target) => normalizeTerm(candidate) === normalizeTerm(target));
        if (!option) option = ensureOption(select, term, termLabel(term));

        select.value = option.value;
        select.dataset.academicDefault = term;
        return true;
    }

    function applyDefaults(root = document) {
        const context = window.EMISAcademicContext || parseContext();
        window.EMISAcademicContext = context;

        YEAR_IDS.forEach(id => applyYear(root.getElementById?.(id) || document.getElementById(id), context));
        SESSION_IDS.forEach(id => applySession(root.getElementById?.(id) || document.getElementById(id), context));
        TERM_IDS.forEach(id => applyTerm(root.getElementById?.(id) || document.getElementById(id), context));

        document.dispatchEvent(new CustomEvent("emis:academic-context-applied", { detail: { ...context } }));
        return context;
    }

    window.EMISAcademic = Object.freeze({ parseContext, applyDefaults, normalizeTerm, termLabel });
    window.EMISAcademicContext = parseContext();

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => applyDefaults(), { once: true });
    else applyDefaults();
})();

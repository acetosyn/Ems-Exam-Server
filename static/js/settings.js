/* ======================================================================
   settings.js — EMIS Global Academic Period Controller
   ====================================================================== */

(() => {
    "use strict";

    const $ = id => document.getElementById(id);
    const state = { settings: {}, yearMin: 2025, yearMax: 2040, loading: false };

    const clean = value => String(value ?? "").trim();
    const normalizeTerm = value => window.EMISAcademic?.normalizeTerm?.(value) || (() => {
        const raw = clean(value).toUpperCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
        if (["FIRST", "FIRST TERM", "1", "1ST", "1ST TERM"].includes(raw)) return "FIRST";
        if (["SECOND", "SECOND TERM", "2", "2ND", "2ND TERM"].includes(raw)) return "SECOND";
        if (["THIRD", "THIRD TERM", "3", "3RD", "3RD TERM"].includes(raw)) return "THIRD";
        return "";
    })();
    const termLabel = value => ({ FIRST: "FIRST TERM", SECOND: "SECOND TERM", THIRD: "THIRD TERM" })[normalizeTerm(value)] || "—";
    const deriveSession = year => clean(year) && /^\d{4}$/.test(clean(year)) ? `${clean(year)}/${Number(year) + 1}` : "—";

    async function api(url, options = {}) {
        const response = await fetch(url, { cache: "no-store", credentials: "same-origin", headers: { "Accept": "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) }, ...options });
        let data = {};
        try { data = await response.json(); } catch (_) { data = {}; }
        if (!response.ok || data.success === false) throw new Error(data.error || data.message || `Request failed (${response.status})`);
        return data;
    }

    function populateYears(preferred = "") {
        const select = $("currentYear");
        if (!select) return;
        const previous = clean(preferred || select.value);
        select.innerHTML = `<option value="">Select year</option>`;
        for (let year = Number(state.yearMin); year <= Number(state.yearMax); year += 1) select.insertAdjacentHTML("beforeend", `<option value="${year}">${year}</option>`);
        if (previous && [...select.options].some(option => option.value === previous)) select.value = previous;
    }

    function syncDerivedSession() {
        const value = deriveSession($("currentYear")?.value);
        if ($("derivedSession")) $("derivedSession").value = value;
    }

    function renderSettings(settings = {}) {
        const year = clean(settings.current_year || settings.year);
        const session = clean(settings.current_session || settings.academic_session || settings.session) || deriveSession(year);
        const term = normalizeTerm(settings.current_term || settings.term);

        state.settings = { ...settings, current_year: year, current_session: session, current_term: term };
        populateYears(year);
        if ($("currentYear")) $("currentYear").value = year;
        if ($("currentTerm")) $("currentTerm").value = term;
        if ($("derivedSession")) $("derivedSession").value = session || deriveSession(year);

        setText("activeAcademicYear", year || "—");
        setText("activeAcademicSession", session || "—");
        setText("activeAcademicTerm", termLabel(term));
        setText("activeAcademicLabel", year && term ? `${session} • ${termLabel(term)}` : session || "Academic period not fully configured");
        setText("settingsSourceText", clean(settings.source) || "Local academic settings");
        setText("settingsLastUpdated", settings.updated_at ? `Updated ${formatDateTime(settings.updated_at)}${settings.updated_by ? ` by ${settings.updated_by}` : ""}` : "Ready for initial configuration");
    }

    async function loadAcademicSettings(showNotice = false) {
        try {
            const data = await api("/api/academic-settings");
            state.yearMin = Number(data.year_min || data.settings?.year_min || 2025);
            state.yearMax = Number(data.year_max || data.settings?.year_max || 2040);
            renderSettings(data.settings || {});
            if (showNotice) showMessage("Academic settings refreshed.", "success");
        } catch (error) {
            console.error("ACADEMIC SETTINGS LOAD ERROR:", error);
            showMessage(error.message || "Could not load academic settings.", "error");
            setText("activeAcademicLabel", "Could not load settings");
        }
    }

    async function loadSyncStatus() {
        try {
            const data = await api("/api/sync/status");
            let role = "Standalone";
            if (data.sender_enabled) role = "Local Sender";
            else if (data.receiver_enabled) role = "Cloud Receiver";

            setText("syncRoleText", role);
            setText("syncQueueText", data.sender_enabled ? `${Number(data.pending || 0)} pending • ${Number(data.failed || 0)} failed` : `${Number(data.received || 0)} received`);
            setText("settingsStorageText", "Local JSON + Sync Queue");

            const badge = $("syncStateBadge");
            if (badge) {
                const issue = Number(data.failed || 0) > 0 || (data.sender_enabled && !data.sender_configured) || (data.receiver_enabled && !data.receiver_configured);
                badge.className = `academic-state-badge ${issue ? "warning" : "ready"}`;
                badge.innerHTML = `<i class="fa-solid fa-circle"></i> ${issue ? "Check Sync" : "Sync Ready"}`;
            }
        } catch (error) {
            setText("syncRoleText", "Unavailable");
            setText("syncQueueText", "Status could not be read");
        }
    }

    async function saveAcademicSettings(event) {
        event.preventDefault();
        if (state.loading) return;

        const year = clean($("currentYear")?.value);
        const term = normalizeTerm($("currentTerm")?.value);
        if (!year || !term) return showMessage("Select both the active result year and academic term.", "error");

        const changed = year !== clean(state.settings.current_year) || term !== normalizeTerm(state.settings.current_term);
        if (changed && !window.confirm(`Set ${deriveSession(year)} • ${termLabel(term)} as the global default for Attendance, CA/Test, Results and Report Sheets?`)) return;

        const button = $("saveAcademicSettings");
        state.loading = true;
        setButtonLoading(button, true, "Saving...");

        try {
            const data = await api("/api/academic-settings", { method: "POST", body: JSON.stringify({ current_year: year, current_term: term }) });
            renderSettings(data.settings || {});

            window.EMISAcademicContext = { ...(window.EMISAcademicContext || {}), ...(data.settings || {}) };
            window.EMISAcademic?.applyDefaults?.();
            document.dispatchEvent(new CustomEvent("emis:academic-settings-updated", { detail: { ...(data.settings || {}) } }));

            const sync = data.sync || {};
            const syncText = sync.queued ? ` Cloud sync queued (${sync.status || "PENDING"}).` : sync.status === "DISABLED" ? " Saved on this server." : "";
            showMessage(`Academic period saved successfully.${syncText}`, "success", 5200);
            setTimeout(loadSyncStatus, 700);
        } catch (error) {
            console.error("ACADEMIC SETTINGS SAVE ERROR:", error);
            showMessage(error.message || "Could not save academic settings.", "error", 5200);
        } finally {
            state.loading = false;
            setButtonLoading(button, false, "Save Academic Period");
        }
    }

    function showMessage(message, type = "info", timeout = 4200) {
        const box = $("academicSettingsMsg");
        if (!box) return;
        box.textContent = message;
        box.className = `academic-message show ${type}`;
        clearTimeout(box._timer);
        box._timer = setTimeout(() => box.classList.remove("show"), timeout);
    }

    function setButtonLoading(button, loading, text) {
        if (!button) return;
        button.disabled = loading;
        button.innerHTML = loading ? `<i class="fa-solid fa-spinner fa-spin"></i> ${text}` : `<i class="fa-solid fa-floppy-disk"></i> ${text}`;
    }

    function setText(id, value) { const node = $(id); if (node) node.textContent = value ?? ""; }
    function formatDateTime(value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? clean(value) : date.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); }

    function bindEvents() {
        $("academicSettingsForm")?.addEventListener("submit", saveAcademicSettings);
        $("currentYear")?.addEventListener("change", syncDerivedSession);
        $("refreshAcademicSettings")?.addEventListener("click", async () => {
            const button = $("refreshAcademicSettings");
            if (button) { button.disabled = true; button.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Refreshing...`; }
            await Promise.all([loadAcademicSettings(true), loadSyncStatus()]);
            if (button) { button.disabled = false; button.innerHTML = `<i class="fa-solid fa-rotate"></i> Refresh`; }
        });
    }

    async function init() {
        bindEvents();
        populateYears();
        await Promise.all([loadAcademicSettings(), loadSyncStatus()]);
        syncDerivedSession();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();

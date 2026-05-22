/* ==========================================================
   EMIS SETTINGS — Academic Session & Term
========================================================== */

document.addEventListener("DOMContentLoaded", function () {
  bindEvents();
  loadAcademicSettings();
});

async function loadAcademicSettings() {
  setStatus("Checking...", null);
  setLastUpdated("Checking Supabase...");

  try {
    const res = await fetch("/api/academic-settings");
    const data = await res.json();

    if (!data.success) throw new Error(data.error || "Failed to fetch");

    const settings = data.settings || {};
    const sessionValue = settings.current_session || "";
    const termValue = settings.current_term || "";

    setText("currentSessionText", sessionValue || "--");
    setText("currentTermText", termValue || "--");

    setText(
      "activeAcademicLabel",
      sessionValue && termValue ? `${sessionValue} • ${termValue}` : "No active term set"
    );

    setValue("currentSession", sessionValue);
    setValue("currentTerm", termValue);

    setStatus("Connected", true);
    setLastUpdated(`Last checked: ${formatTime(new Date())}`);

  } catch (err) {
    console.error(err);

    setStatus("Offline / Error", false);
    setText("activeAcademicLabel", "Connection Error");
    setLastUpdated("Could not reach Supabase");
  }
}

async function saveAcademicSettings(e) {
  e.preventDefault();

  const sessionValue = document.getElementById("currentSession")?.value;
  const termValue = document.getElementById("currentTerm")?.value;
  const saveBtn = document.getElementById("saveAcademicSettings");

  if (!sessionValue || !termValue) {
    showMessage("Please select session and term.", "error");
    return;
  }

  try {
    setButtonLoading(saveBtn, true, "Saving...");

    const res = await fetch("/api/academic-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_session: sessionValue,
        current_term: termValue
      })
    });

    const data = await res.json();

    if (!data.success) throw new Error(data.error || "Failed");

    showMessage("Academic settings updated successfully.", "success");
    await loadAcademicSettings();

  } catch (err) {
    console.error(err);
    showMessage("Failed to update settings. Please try again.", "error");

  } finally {
    setButtonLoading(saveBtn, false, "Save Settings");
  }
}

function setStatus(text, isOnline) {
  const el = document.getElementById("supabaseStatusText");
  if (!el) return;

  el.textContent = text;

  if (isOnline === true) el.style.color = "#0f766e";
  else if (isOnline === false) el.style.color = "#be123c";
  else el.style.color = "#f59e0b";
}

function showMessage(message, type) {
  const box = document.getElementById("academicSettingsMsg");
  if (!box) return;

  box.textContent = message;
  box.className = `settings-message show ${type}`;

  clearTimeout(box._timer);
  box._timer = setTimeout(() => {
    box.classList.remove("show");
  }, 4000);
}

function setButtonLoading(button, isLoading, text) {
  if (!button) return;

  button.disabled = isLoading;
  button.innerHTML = isLoading
    ? `<i class="fa-solid fa-spinner fa-spin"></i> ${text}`
    : `<i class="fa-solid fa-floppy-disk"></i> ${text}`;
}

function setLastUpdated(text) {
  setText("settingsLastUpdated", text);
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function setValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value;
}

function formatTime(date) {
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit"
  });
}

function bindEvents() {
  const form = document.getElementById("academicSettingsForm");
  const refreshBtn = document.getElementById("refreshAcademicSettings");

  if (form) {
    form.addEventListener("submit", saveAcademicSettings);
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", async function () {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Refreshing...`;

      await loadAcademicSettings();

      refreshBtn.disabled = false;
      refreshBtn.innerHTML = `<i class="fa-solid fa-rotate"></i> Refresh`;
    });
  }
}
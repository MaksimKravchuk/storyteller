// Storyteller web client — vanilla fetch() against the FastAPI JSON API.
// No framework, no build step. Keeps all state in the DOM + currentGameId.

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const els = {
    loading: $("loading"),
    settingPanel: $("setting-panel"),
    settingForm: $("setting-form"),
    settingInput: $("setting-input"),
    languageSelect: $("language-select"),
    settingStatus: $("setting-status"),
    gamePanel: $("game-panel"),
    log: $("log"),
    actionForm: $("action-form"),
    actionInput: $("action-input"),
    actionSubmit: $("action-submit"),
    actionStatus: $("action-status"),
    newGameBtn: $("new-game-btn"),
  };

  let currentGameId = null;

  function show(el) { el.hidden = false; }
  function hide(el) { el.hidden = true; }

  function setStatus(el, text, kind) {
    el.textContent = text || "";
    el.className = "status" + (kind ? " " + kind : "");
  }

  function appendTurnHTML(role, html) {
    const div = document.createElement("div");
    div.className = "turn " + role;
    // The server pre-renders both player input (escaped) and narrator output
    // (markdown subset → safe HTML), so innerHTML is safe here.
    div.innerHTML = html;
    els.log.appendChild(div);
    els.log.scrollTop = els.log.scrollHeight;
  }

  function renderSnapshot(snapshot) {
    currentGameId = snapshot.game_id;
    els.log.innerHTML = "";
    for (const entry of snapshot.transcript) {
      appendTurnHTML(entry.role, entry.html);
    }
    hide(els.settingPanel);
    show(els.gamePanel);
    show(els.newGameBtn);
    els.actionInput.focus();
  }

  function showSettingPanel() {
    currentGameId = null;
    hide(els.gamePanel);
    hide(els.newGameBtn);
    show(els.settingPanel);
    els.settingInput.focus();
  }

  async function parseError(response) {
    try {
      const body = await response.json();
      return body.detail || response.statusText;
    } catch {
      return response.statusText || "Request failed";
    }
  }

  async function loadCurrent() {
    try {
      const response = await fetch("/api/games/current");
      if (response.status === 404) {
        showSettingPanel();
        return;
      }
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      renderSnapshot(await response.json());
    } catch (err) {
      showSettingPanel();
      setStatus(els.settingStatus, "Could not load current game: " + err.message);
    } finally {
      hide(els.loading);
    }
  }

  async function onStartGame(event) {
    event.preventDefault();
    const setting = els.settingInput.value.trim();
    if (!setting) return;
    const language = els.languageSelect ? els.languageSelect.value : "English";
    setStatus(els.settingStatus, "Researching setting and generating opening scene… (may take a minute)", "info");
    const button = els.settingForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const response = await fetch("/api/games", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ setting, language }),
      });
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      renderSnapshot(await response.json());
      setStatus(els.settingStatus, "");
    } catch (err) {
      setStatus(els.settingStatus, "Failed to start game: " + err.message);
    } finally {
      button.disabled = false;
    }
  }

  function escapeHTML(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  async function onSubmitAction(event) {
    event.preventDefault();
    const action = els.actionInput.value.trim();
    if (!action || !currentGameId) return;
    // Echo the player line immediately while the engine works.
    appendTurnHTML("player", escapeHTML(action));
    els.actionInput.value = "";
    els.actionInput.disabled = true;
    els.actionSubmit.disabled = true;
    setStatus(els.actionStatus, "…", "info");
    try {
      const response = await fetch(
        "/api/games/" + encodeURIComponent(currentGameId) + "/actions",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        },
      );
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const data = await response.json();
      appendTurnHTML("narrator", data.narration_html);
      setStatus(els.actionStatus, "");
    } catch (err) {
      setStatus(els.actionStatus, "Error: " + err.message);
    } finally {
      els.actionInput.disabled = false;
      els.actionSubmit.disabled = false;
      els.actionInput.focus();
    }
  }

  function onNewGame() {
    if (!confirm("Start a new game? This will replace the current one.")) return;
    showSettingPanel();
  }

  els.settingForm.addEventListener("submit", onStartGame);
  els.actionForm.addEventListener("submit", onSubmitAction);
  els.newGameBtn.addEventListener("click", onNewGame);

  loadCurrent();
})();

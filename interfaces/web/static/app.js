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
    charName: $("char-name"),
    charAppearance: $("char-appearance"),
    charInventory: $("char-inventory"),
    useTemplateBtn: $("use-template-btn"),
    settingExamples: $("setting-examples"),
    gamePanel: $("game-panel"),
    log: $("log"),
    actionForm: $("action-form"),
    actionInput: $("action-input"),
    actionSubmit: $("action-submit"),
    actionStatus: $("action-status"),
    newGameBtn: $("new-game-btn"),
    characterHeader: $("character-header"),
    inventoryList: $("inventory-list"),
    knownNpcsList: $("known-npcs-list"),
    recentEventsList: $("recent-events-list"),
    learnedFactsList: $("learned-facts-list"),
    offlineBanner: $("offline-banner"),
  };

  let currentGameId = null;
  // Snapshot of the last character payload, used to detect newly-arrived
  // items so they can briefly glow gold on the turn they appear.
  let prevCharacter = null;

  const FACT_TITLES = {
    FACT: "fact",
    RUMOR: "rumor",
    PERSONAL_EXPERIENCE: "personal experience",
    HEARSAY: "hearsay",
  };

  const identityKey = (value) => value;
  const npcKey = (npc) => npc.name;
  const factKey = (fact) => fact.text;

  function show(el) { el.hidden = false; }
  function hide(el) { el.hidden = true; }

  function setStatus(el, text, kind) {
    el.textContent = text || "";
    el.className = "status" + (kind ? " " + kind : "");
  }

  function setOfflineNotice(showNotice) {
    if (!els.offlineBanner) return;
    els.offlineBanner.hidden = !showNotice;
  }

  function isNetworkError(err) {
    return !navigator.onLine || err instanceof TypeError || err.message.includes("internet connection");
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // The app remains online-only/playable if registration is unavailable.
    });
  }

  function appendTurnHTML(role, html) {
    const div = document.createElement("div");
    div.className = "turn " + role;
    // The server pre-renders both player input (escaped) and narrator output
    // (markdown subset → safe HTML, with inline entity <span>s already wrapped
    // by formatting.entity_markup.wrap_entities), so innerHTML is safe here.
    div.innerHTML = html;
    els.log.appendChild(div);
    els.log.scrollTop = els.log.scrollHeight;
  }

  function renderInventoryItem(item) {
    const li = document.createElement("li");
    li.textContent = item;
    return li;
  }

  function renderKnownNpc(npc) {
    const li = document.createElement("li");
    const line = document.createElement("span");
    line.className = "npc-line";
    const name = document.createElement("span");
    name.className = "npc-name";
    name.textContent = npc.name;
    const sep = document.createElement("span");
    sep.className = "npc-sep";
    sep.textContent = "·";
    const occupation = document.createElement("span");
    occupation.className = "npc-occupation";
    occupation.textContent = npc.occupation;
    line.append(name, sep, occupation);
    const descriptor = document.createElement("span");
    descriptor.className = "npc-descriptor";
    descriptor.textContent = npc.descriptor;
    li.append(line, descriptor);
    return li;
  }

  function renderRecentEvent(event) {
    const li = document.createElement("li");
    li.textContent = event;
    return li;
  }

  function renderLearnedFact(fact) {
    const li = document.createElement("li");
    li.dataset.source = fact.source;
    li.title = "Source: " + (FACT_TITLES[fact.source] || fact.source);
    li.textContent = fact.text;
    return li;
  }

  function renderEmptyPlaceholder(listEl) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "— nothing yet —";
    listEl.appendChild(li);
  }

  // Rebuild listEl from items. Items whose key is absent from prevItems
  // are marked .is-new with a per-item --stagger so the reveal animation
  // staggers from top to bottom.
  function renderList(listEl, items, prevItems, makeItem, getKey) {
    listEl.innerHTML = "";
    if (!items || items.length === 0) {
      renderEmptyPlaceholder(listEl);
      return;
    }
    const prevKeys = new Set((prevItems || []).map(getKey));
    let stagger = 0;
    for (const item of items) {
      const li = makeItem(item);
      if (!prevKeys.has(getKey(item))) {
        li.classList.add("is-new");
        li.style.setProperty("--stagger", String(stagger));
        stagger += 1;
      }
      listEl.appendChild(li);
    }
  }

  function renderCharacterHeader(character) {
    els.characterHeader.innerHTML = "";
    const name = document.createElement("p");
    name.className = "char-name";
    name.textContent = character.name;
    els.characterHeader.appendChild(name);
    if (character.appearance) {
      const appearance = document.createElement("p");
      appearance.className = "char-appearance";
      appearance.textContent = character.appearance;
      els.characterHeader.appendChild(appearance);
    }
    if (character.physical_status && character.physical_status !== "healthy") {
      const status = document.createElement("span");
      status.className = "char-status";
      status.textContent = character.physical_status;
      els.characterHeader.appendChild(status);
    }
  }

  function renderCharacter(character) {
    if (!character) return;
    renderCharacterHeader(character);
    const prev = prevCharacter || {};
    renderList(els.inventoryList, character.inventory, prev.inventory, renderInventoryItem, identityKey);
    renderList(els.knownNpcsList, character.known_npcs, prev.known_npcs, renderKnownNpc, npcKey);
    renderList(els.recentEventsList, character.recent_events, prev.recent_events, renderRecentEvent, identityKey);
    renderList(els.learnedFactsList, character.learned_facts, prev.learned_facts, renderLearnedFact, factKey);
    prevCharacter = character;
  }

  function renderSnapshot(snapshot) {
    currentGameId = snapshot.game_id;
    els.log.innerHTML = "";
    for (const entry of snapshot.transcript) {
      appendTurnHTML(entry.role, entry.html);
    }
    // Seed prevCharacter with the snapshot itself so the first render produces
    // zero "new" items — we don't want every entry to glow on load or reload.
    prevCharacter = snapshot.character;
    renderCharacter(snapshot.character);
    hide(els.settingPanel);
    show(els.gamePanel);
    show(els.newGameBtn);
    els.actionInput.focus();
  }

  function showSettingPanel() {
    currentGameId = null;
    prevCharacter = null;
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
      setOfflineNotice(false);
      renderSnapshot(await response.json());
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      showSettingPanel();
      setStatus(els.settingStatus, "Could not load current game: " + err.message);
    } finally {
      hide(els.loading);
    }
  }

  function gatherCharacter() {
    const name = els.charName ? els.charName.value.trim() : "";
    const appearance = els.charAppearance ? els.charAppearance.value.trim() : "";
    const rawInventory = els.charInventory ? els.charInventory.value : "";
    const inventory = rawInventory
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!name && !appearance && inventory.length === 0) {
      return null;
    }
    return { name, appearance, inventory };
  }

  async function onUseTemplate() {
    setStatus(els.settingStatus, "Loading a character template…", "info");
    try {
      const response = await fetch("/api/character-template");
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      const tpl = await response.json();
      if (els.charName) els.charName.value = tpl.name || "";
      if (els.charAppearance) els.charAppearance.value = tpl.appearance || "";
      if (els.charInventory) els.charInventory.value = (tpl.inventory || []).join(", ");
      setStatus(els.settingStatus, "");
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      setStatus(els.settingStatus, "Could not load template: " + err.message);
    }
  }

  async function onStartGame(event) {
    event.preventDefault();
    const setting = els.settingInput.value.trim();
    if (!setting) return;
    const language = els.languageSelect ? els.languageSelect.value : "English";
    const character = gatherCharacter();
    setStatus(
      els.settingStatus,
      "Building your AI text quest demo: researching the setting and writing the opening scene. This may take a minute…",
      "info",
    );
    const button = els.settingForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const response = await fetch("/api/games", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ setting, language, character }),
      });
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      renderSnapshot(await response.json());
      setStatus(els.settingStatus, "");
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
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
    setStatus(els.actionStatus, "The AI narrator is resolving your action…", "info");
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
      setOfflineNotice(false);
      const data = await response.json();
      appendTurnHTML("narrator", data.narration_html);
      renderCharacter(data.character);
      setStatus(els.actionStatus, "");
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
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

  function onNextActionClick(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    els.actionInput.value = button.dataset.action || "";
    els.actionInput.focus();
  }

  function onSettingExampleClick(event) {
    const button = event.target.closest("button[data-setting-example]");
    if (!button) return;
    els.settingInput.value = button.dataset.settingExample || "";
    els.settingInput.focus();
  }

  function initFoldableSections() {
    document.querySelectorAll(".character-col h4, .character-col h5").forEach((heading) => {
      const list = heading.nextElementSibling;
      if (!list || list.tagName !== "UL") return;
      heading.classList.add("is-foldable");
      heading.addEventListener("click", () => heading.classList.toggle("is-folded"));
    });
  }

  els.settingForm.addEventListener("submit", onStartGame);
  els.actionForm.addEventListener("submit", onSubmitAction);
  els.newGameBtn.addEventListener("click", onNewGame);
  $("next-actions").addEventListener("click", onNextActionClick);
  if (els.settingExamples) {
    els.settingExamples.addEventListener("click", onSettingExampleClick);
  }
  if (els.useTemplateBtn) {
    els.useTemplateBtn.addEventListener("click", onUseTemplate);
  }
  window.addEventListener("online", () => setOfflineNotice(false));
  window.addEventListener("offline", () => setOfflineNotice(true));

  registerServiceWorker();
  setOfflineNotice(!navigator.onLine);
  initFoldableSections();
  loadCurrent();
})();

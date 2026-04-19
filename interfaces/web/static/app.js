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
    characterHeader: $("character-header"),
    inventoryList: $("inventory-list"),
    knownNpcsList: $("known-npcs-list"),
    recentEventsList: $("recent-events-list"),
    learnedFactsList: $("learned-facts-list"),
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

  function appendTurnHTML(role, html, visibleEntities) {
    const div = document.createElement("div");
    div.className = "turn " + role;
    // The server pre-renders both player input (escaped) and narrator output
    // (markdown subset → safe HTML), so innerHTML is safe here.
    div.innerHTML = html;
    if (role === "narrator" && visibleEntities && visibleEntities.length) {
      div.appendChild(renderEntityChips(visibleEntities));
    }
    els.log.appendChild(div);
    els.log.scrollTop = els.log.scrollHeight;
  }

  function renderEntityChips(entities) {
    const row = document.createElement("div");
    row.className = "entity-chips";
    for (const entity of entities) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "entity-chip entity-" + entity.kind;
      chip.dataset.kind = entity.kind;
      chip.dataset.id = entity.id;
      chip.textContent = entity.names[0];
      if (entity.names.length > 1) {
        chip.title = entity.names.slice(1).join(" · ");
      }
      chip.addEventListener("click", () => onChipClick(entity));
      row.appendChild(chip);
    }
    return row;
  }

  function onChipClick(entity) {
    if (!els.actionInput) return;
    const verbs = { npc: "Talk to ", poi: "Examine ", item: "Examine " };
    els.actionInput.value = (verbs[entity.kind] || "Examine ") + entity.names[0];
    els.actionInput.focus();
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
      appendTurnHTML(entry.role, entry.html, entry.visible_entities);
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
      appendTurnHTML("narrator", data.narration_html, data.visible_entities);
      renderCharacter(data.character);
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

  initFoldableSections();
  loadCurrent();
})();

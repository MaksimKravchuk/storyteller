// Storyteller web client - vanilla fetch() against the FastAPI JSON API.
// No framework, no build step. Keeps all state in the DOM + currentGameId.

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const els = {
    loading: $("loading"),
    authPanel: $("auth-panel"),
    loginForm: $("login-form"),
    loginEmail: $("login-email"),
    signupBtn: $("signup-btn"),
    logoutBtn: $("logout-btn"),
    authStatus: $("auth-status"),
    settingPanel: $("setting-panel"),
    storiesPanel: $("stories-panel"),
    storiesList: $("stories-list"),
    storiesStatus: $("stories-status"),
    libraryNewGameBtn: $("library-new-game-btn"),
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
    feedbackForm: $("feedback-form"),
    feedbackCategory: $("feedback-category"),
    feedbackMessage: $("feedback-message"),
    feedbackSubmit: $("feedback-submit"),
    feedbackStatus: $("feedback-status"),
    newGameBtn: $("new-game-btn"),
    characterHeader: $("character-header"),
    inventoryList: $("inventory-list"),
    knownNpcsList: $("known-npcs-list"),
    recentEventsList: $("recent-events-list"),
    learnedFactsList: $("learned-facts-list"),
    dashboard: $("dashboard"),
    panelToolbar: $("panel-toolbar"),
    panelHost: $("panel-host"),
    panelBackdrop: $("panel-backdrop"),
    panelClose: $("panel-close"),
    knowledgeFilter: $("knowledge-filter"),
    mapBreadcrumb: $("map-breadcrumb"),
    mapCurrent: $("map-current"),
    mapConnections: $("map-connections"),
    peopleList: $("people-list"),
    worldClock: $("world-clock"),
    offlineBanner: $("offline-banner"),
  };

  const mobileQuery = window.matchMedia("(max-width: 720px)");
  const isMobile = () => mobileQuery.matches;

  let currentGameId = null;
  let supabaseClient = null;
  let authRequired = false;
  // Snapshot of the last character payload, used to detect newly-arrived
  // items so they can briefly glow gold on the turn they appear.
  let prevCharacter = null;
  // Same delta trick for the world payload (map + people).
  let prevWorld = null;
  // Knowledge panel: client-side source filter ("ALL" or a FactSource value).
  let factFilter = "ALL";
  let allFacts = [];
  let prevFacts = null;
  // Which dashboard panel is selected, and whether the mobile sheet is open.
  let activePanel = "character";
  let sheetOpen = false;

  const FACT_TITLES = {
    FACT: "fact",
    RUMOR: "rumor",
    PERSONAL_EXPERIENCE: "personal experience",
    HEARSAY: "hearsay",
  };

  const identityKey = (value) => value;
  const npcKey = (npc) => npc.name;
  const factKey = (fact) => fact.text;
  const mapNodeKey = (node) => node.id;
  const personKey = (person) => person.label;

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
    // (markdown subset -> safe HTML, with inline entity <span>s already wrapped
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
    sep.textContent = "*";
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
    li.textContent = "- nothing yet -";
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

  // Knowledge panel: render learned facts through the active source filter.
  // ``prevForDelta`` is the set used to decide which rows glow as "new":
  // the previous turn's facts on a turn update, or the current facts on a
  // filter-only re-render (so toggling a filter never re-triggers the glow).
  function renderFacts(prevForDelta) {
    const facts = factFilter === "ALL" ? allFacts : allFacts.filter((fact) => fact.source === factFilter);
    renderList(els.learnedFactsList, facts, prevForDelta, renderLearnedFact, factKey);
  }

  function renderCharacter(character) {
    if (!character) return;
    renderCharacterHeader(character);
    const prev = prevCharacter || {};
    renderList(els.inventoryList, character.inventory, prev.inventory, renderInventoryItem, identityKey);
    renderList(els.knownNpcsList, character.known_npcs, prev.known_npcs, renderKnownNpc, npcKey);
    renderList(els.recentEventsList, character.recent_events, prev.recent_events, renderRecentEvent, identityKey);
    allFacts = character.learned_facts || [];
    renderFacts(prev.learned_facts);
    prevCharacter = character;
  }

  function renderConnectionNode(node) {
    const li = document.createElement("li");
    li.className = "map-node";
    const name = document.createElement("span");
    name.className = "map-node-name";
    name.textContent = node.name;
    const type = document.createElement("span");
    type.className = "map-node-type";
    type.textContent = node.location_type;
    li.append(name, type);
    return li;
  }

  function renderPerson(person) {
    const li = document.createElement("li");
    li.className = "person-row " + (person.known ? "is-known" : "is-stranger");
    const label = document.createElement("span");
    label.className = "person-label";
    label.textContent = person.label;
    const role = document.createElement("span");
    role.className = "person-role";
    role.textContent = person.role;
    li.append(label, role);
    return li;
  }

  function renderMapCurrent(current) {
    els.mapCurrent.innerHTML = "";
    const name = document.createElement("p");
    name.className = "map-current-name";
    const type = document.createElement("p");
    type.className = "map-current-type";
    if (current) {
      name.textContent = current.name;
      type.textContent = current.location_type;
    } else {
      name.textContent = "- location unknown -";
      name.classList.add("empty");
    }
    els.mapCurrent.append(name, type);
  }

  function renderMap(map) {
    const crumbs = (map.breadcrumb || []).map((node) => node.name);
    els.mapBreadcrumb.textContent = crumbs.join("  ›  ");
    renderMapCurrent(map.current);
    const prevConnections = prevWorld && prevWorld.map ? prevWorld.map.connections : null;
    renderList(els.mapConnections, map.connections, prevConnections, renderConnectionNode, mapNodeKey);
  }

  function renderPeopleTime(world) {
    const clock = world.clock || {};
    els.worldClock.textContent = "Day " + (clock.day || 1) + " · " + (clock.time_of_day || "");
    const prevPeople = prevWorld ? prevWorld.people : null;
    renderList(els.peopleList, world.people, prevPeople, renderPerson, personKey);
  }

  function renderWorld(world) {
    if (!world) return;
    renderMap(world.map);
    renderPeopleTime(world);
    prevWorld = world;
  }

  function renderSnapshot(snapshot) {
    currentGameId = snapshot.game_id;
    els.log.innerHTML = "";
    for (const entry of snapshot.transcript) {
      appendTurnHTML(entry.role, entry.html);
    }
    // Seed prevCharacter/prevWorld with the snapshot itself so the first render
    // produces zero "new" items - we don't want every entry to glow on load.
    prevCharacter = snapshot.character;
    renderCharacter(snapshot.character);
    prevWorld = snapshot.world;
    renderWorld(snapshot.world);
    hide(els.settingPanel);
    if (els.storiesPanel) hide(els.storiesPanel);
    show(els.gamePanel);
    show(els.newGameBtn);
    els.actionInput.focus();
  }

  function showSettingPanel() {
    currentGameId = null;
    prevCharacter = null;
    prevWorld = null;
    hide(els.gamePanel);
    hide(els.newGameBtn);
    if (els.storiesPanel) hide(els.storiesPanel);
    show(els.settingPanel);
    els.settingInput.focus();
  }

  function showStoriesPanel() {
    hide(els.settingPanel);
    hide(els.gamePanel);
    show(els.newGameBtn);
    if (els.storiesPanel) show(els.storiesPanel);
  }

  function renderStoryRow(story) {
    const li = document.createElement("li");
    li.className = "story-row";
    const meta = document.createElement("div");
    meta.className = "story-meta";
    const title = document.createElement("strong");
    title.textContent = story.title || story.setting || "Untitled story";
    const details = document.createElement("span");
    details.textContent = (story.setting || "Unknown setting") + " * " + story.turn_count + " turns";
    meta.append(title, details);
    const actions = document.createElement("div");
    actions.className = "story-actions";
    const continueBtn = document.createElement("button");
    continueBtn.type = "button";
    continueBtn.dataset.continueGame = story.game_id;
    continueBtn.textContent = "Continue";
    const archiveBtn = document.createElement("button");
    archiveBtn.type = "button";
    archiveBtn.dataset.archiveGame = story.game_id;
    archiveBtn.textContent = "Archive";
    actions.append(continueBtn, archiveBtn);
    li.append(meta, actions);
    return li;
  }

  function renderStories(games) {
    if (!els.storiesList) return;
    els.storiesList.innerHTML = "";
    if (!games || games.length === 0) {
      showSettingPanel();
      return;
    }
    for (const story of games) {
      els.storiesList.appendChild(renderStoryRow(story));
    }
    setStatus(els.storiesStatus, "");
    showStoriesPanel();
  }

  async function parseError(response) {
    try {
      const body = await response.json();
      return body.detail || response.statusText;
    } catch {
      return response.statusText || "Request failed";
    }
  }

  async function loadStories() {
    try {
      const response = await apiFetch("/api/games");
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      const data = await response.json();
      renderStories(data.games || []);
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      showSettingPanel();
      setStatus(els.settingStatus, "Could not load stories: " + err.message);
    } finally {
      hide(els.loading);
    }
  }

  async function authHeaders() {
    if (!supabaseClient) return {};
    const { data } = await supabaseClient.auth.getSession();
    const token = data && data.session ? data.session.access_token : null;
    return token ? { Authorization: "Bearer " + token } : {};
  }

  async function apiFetch(url, options) {
    const opts = options || {};
    const headers = Object.assign({}, opts.headers || {}, await authHeaders());
    return fetch(url, Object.assign({}, opts, { headers }));
  }

  async function loadPublicConfig() {
    const response = await fetch("/api/config/public");
    if (!response.ok) return;
    const cfg = await response.json();
    authRequired = Boolean(cfg.beta_auth_required);
    if (!authRequired) return;
    if (els.authPanel) show(els.authPanel);
    const supabaseBrowserKey = cfg.supabase_publishable_key;
    if (!(cfg.supabase_url && supabaseBrowserKey && window.supabase)) {
      setStatus(els.authStatus, "Login is not configured for this deployment yet.");
      return;
    }
    supabaseClient = window.supabase.createClient(cfg.supabase_url, supabaseBrowserKey);
    const { data } = await supabaseClient.auth.getSession();
    const signedIn = Boolean(data && data.session);
    if (els.loginForm) els.loginForm.hidden = signedIn;
    if (els.logoutBtn) els.logoutBtn.hidden = !signedIn;
  }

  async function sendMagicLink(shouldCreateUser) {
    if (!supabaseClient || !els.loginEmail) return;
    const email = els.loginEmail.value.trim();
    if (!email) return;
    const { error } = await supabaseClient.auth.signInWithOtp({
      email,
      options: {
        shouldCreateUser: shouldCreateUser,
        emailRedirectTo: window.location.origin,
      },
    });
    const successMessage = shouldCreateUser
      ? "Check your email to finish signing up."
      : "Check your email to log in.";
    setStatus(els.authStatus, error ? error.message : successMessage, error ? "" : "info");
  }

  async function onLogin(event) {
    event.preventDefault();
    await sendMagicLink(false);
  }

  async function onSignup() {
    await sendMagicLink(true);
  }

  async function onLogout() {
    if (!supabaseClient) return;
    await supabaseClient.auth.signOut();
    if (els.loginForm) els.loginForm.hidden = false;
    if (els.logoutBtn) els.logoutBtn.hidden = true;
    setStatus(els.authStatus, "Logged out.", "info");
  }

  async function loadCurrent() {
    try {
      const response = await apiFetch("/api/games/current");
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
    setStatus(els.settingStatus, "Loading a character template...", "info");
    try {
      const response = await apiFetch("/api/character-template");
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
      "Building your AI text quest demo: researching the setting and writing the opening scene. This may take a minute...",
      "info",
    );
    const button = els.settingForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const response = await apiFetch("/api/games", {
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
    setStatus(els.actionStatus, "The AI narrator is resolving your action...", "info");
    try {
      const response = await apiFetch(
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
      renderWorld(data.world);
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

  async function onSubmitFeedback(event) {
    event.preventDefault();
    if (!currentGameId || !els.feedbackMessage) return;
    const message = els.feedbackMessage.value.trim();
    if (!message) return;
    const category = els.feedbackCategory ? els.feedbackCategory.value : "other";
    if (els.feedbackSubmit) els.feedbackSubmit.disabled = true;
    setStatus(els.feedbackStatus, "Sending feedback...", "info");
    try {
      const response = await apiFetch(
        "/api/games/" + encodeURIComponent(currentGameId) + "/feedback",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ category, message }),
        },
      );
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      els.feedbackMessage.value = "";
      setStatus(els.feedbackStatus, "Thanks — beta feedback sent to Max.", "info");
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      setStatus(els.feedbackStatus, "Could not send feedback: " + err.message);
    } finally {
      if (els.feedbackSubmit) els.feedbackSubmit.disabled = false;
    }
  }

  function onNewGame() {
    showSettingPanel();
  }

  async function continueStory(gameId) {
    setStatus(els.storiesStatus, "Loading story...", "info");
    try {
      const response = await apiFetch("/api/games/" + encodeURIComponent(gameId));
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      renderSnapshot(await response.json());
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      setStatus(els.storiesStatus, "Could not continue story: " + err.message);
    }
  }

  async function archiveStory(gameId) {
    if (!confirm("Archive this story?")) return;
    setStatus(els.storiesStatus, "Archiving story...", "info");
    try {
      const response = await apiFetch("/api/games/" + encodeURIComponent(gameId) + "/archive", { method: "POST" });
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      await loadStories();
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      setStatus(els.storiesStatus, "Could not archive story: " + err.message);
    }
  }

  function onStoriesClick(event) {
    const continueBtn = event.target.closest("button[data-continue-game]");
    if (continueBtn) {
      continueStory(continueBtn.dataset.continueGame || "");
      return;
    }
    const archiveBtn = event.target.closest("button[data-archive-game]");
    if (archiveBtn) {
      archiveStory(archiveBtn.dataset.archiveGame || "");
    }
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
    document.querySelectorAll("#panel-host h4").forEach((heading) => {
      const list = heading.nextElementSibling;
      if (!list || list.tagName !== "UL") return;
      heading.classList.add("is-foldable");
      heading.addEventListener("click", () => heading.classList.toggle("is-folded"));
    });
  }

  // ── Dashboard panels (tabbed rail on desktop, bottom-sheet on mobile) ──

  // Background scroll-lock for the mobile bottom-sheet. position:fixed holds the
  // page still (iOS ignores overflow:hidden on the body alone); we stash the
  // scroll offset on lock and restore it on unlock so opening/closing a sheet
  // never moves the transcript behind it.
  let lockedScrollY = 0;

  function lockBodyScroll() {
    lockedScrollY = window.scrollY;
    document.body.style.top = "-" + lockedScrollY + "px";
    document.body.classList.add("sheet-locked");
  }

  function unlockBodyScroll() {
    document.body.classList.remove("sheet-locked");
    document.body.style.top = "";
    window.scrollTo(0, lockedScrollY);
  }

  function selectPanel(name) {
    activePanel = name;
    els.panelHost.querySelectorAll(".panel").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
    els.panelToolbar.querySelectorAll("button[data-panel]").forEach((btn) => {
      btn.setAttribute("aria-selected", String(btn.dataset.panel === name));
    });
  }

  function deselectTabs() {
    els.panelToolbar.querySelectorAll("button[data-panel]").forEach((btn) => {
      btn.setAttribute("aria-selected", "false");
    });
  }

  // Single owner of the mobile-sheet transition: the sheet-open class, the
  // sheetOpen flag, and the background scroll-lock always move together, so no
  // open/close path can flip one without the others. The early return is the one
  // "only on a real transition" guard — re-locking would re-capture scrollY as 0
  // once the body is position:fixed.
  function setSheetOpen(open) {
    if (open === sheetOpen) return;
    sheetOpen = open;
    els.dashboard.classList.toggle("sheet-open", open);
    if (open) {
      lockBodyScroll();
    } else {
      unlockBodyScroll();
    }
  }

  function openPanel(name) {
    selectPanel(name);
    if (isMobile()) setSheetOpen(true);
  }

  function closePanel() {
    setSheetOpen(false);
    deselectTabs();
    const btn = els.panelToolbar.querySelector('button[data-panel="' + activePanel + '"]');
    if (btn) btn.focus();
  }

  function onToolbarClick(event) {
    const btn = event.target.closest("button[data-panel]");
    if (!btn) return;
    const name = btn.dataset.panel;
    // On mobile, tapping the already-open tab toggles the sheet shut.
    if (isMobile() && sheetOpen && name === activePanel) {
      closePanel();
      return;
    }
    openPanel(name);
  }

  function onFactFilterClick(event) {
    const btn = event.target.closest("button[data-fact-filter]");
    if (!btn) return;
    factFilter = btn.dataset.factFilter;
    els.knowledgeFilter.querySelectorAll("button[data-fact-filter]").forEach((other) => {
      other.setAttribute("aria-pressed", String(other === btn));
    });
    renderFacts(allFacts);
  }

  function onBreakpointChange() {
    if (!isMobile()) {
      // Desktop rail is always visible; drop any mobile sheet state (which also
      // releases the scroll-lock if a sheet was open when the bp was crossed).
      setSheetOpen(false);
      selectPanel(activePanel);
    } else if (!sheetOpen) {
      deselectTabs();
    }
  }

  function initDashboard() {
    selectPanel("character");
    if (isMobile()) deselectTabs();
    els.panelToolbar.addEventListener("click", onToolbarClick);
    if (els.knowledgeFilter) els.knowledgeFilter.addEventListener("click", onFactFilterClick);
    if (els.panelClose) els.panelClose.addEventListener("click", closePanel);
    if (els.panelBackdrop) els.panelBackdrop.addEventListener("click", closePanel);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && sheetOpen) closePanel();
    });
    mobileQuery.addEventListener("change", onBreakpointChange);
  }

  els.settingForm.addEventListener("submit", onStartGame);
  els.actionForm.addEventListener("submit", onSubmitAction);
  if (els.feedbackForm) {
    els.feedbackForm.addEventListener("submit", onSubmitFeedback);
  }
  els.newGameBtn.addEventListener("click", onNewGame);
  if (els.libraryNewGameBtn) {
    els.libraryNewGameBtn.addEventListener("click", onNewGame);
  }
  if (els.storiesList) {
    els.storiesList.addEventListener("click", onStoriesClick);
  }
  $("next-actions").addEventListener("click", onNextActionClick);
  if (els.settingExamples) {
    els.settingExamples.addEventListener("click", onSettingExampleClick);
  }
  if (els.useTemplateBtn) {
    els.useTemplateBtn.addEventListener("click", onUseTemplate);
  }
  window.addEventListener("online", () => setOfflineNotice(false));
  window.addEventListener("offline", () => setOfflineNotice(true));
  if (els.loginForm) {
    els.loginForm.addEventListener("submit", onLogin);
  }
  if (els.signupBtn) {
    els.signupBtn.addEventListener("click", onSignup);
  }
  if (els.logoutBtn) {
    els.logoutBtn.addEventListener("click", onLogout);
  }

  registerServiceWorker();
  setOfflineNotice(!navigator.onLine);
  initFoldableSections();
  initDashboard();
  loadPublicConfig().finally(loadStories);
})();

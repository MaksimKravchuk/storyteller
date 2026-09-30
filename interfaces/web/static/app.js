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
    libraryBtn: $("library-btn"),
    settingForm: $("setting-form"),
    settingInput: $("setting-input"),
    languageSelect: $("language-select"),
    settingStatus: $("setting-status"),
    opening: $("opening"),
    charName: $("char-name"),
    charAppearance: $("char-appearance"),
    charInventory: $("char-inventory"),
    useTemplateBtn: $("use-template-btn"),
    settingExamples: $("setting-examples"),
    gamePanel: $("game-panel"),
    stage: $("stage"),
    stagePlaceBtn: $("stage-place-btn"),
    stageCrumbs: $("stage-crumbs"),
    stagePlace: $("stage-place"),
    stageClock: $("stage-clock"),
    stageCast: $("stage-cast"),
    log: $("log"),
    actionForm: $("action-form"),
    actionInput: $("action-input"),
    actionSubmit: $("action-submit"),
    actionStatus: $("action-status"),
    feedbackDialog: $("feedback-dialog"),
    feedbackOpenBtn: $("feedback-open-btn"),
    feedbackCloseBtn: $("feedback-close-btn"),
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
    tabbar: $("tabbar"),
    entPop: $("ent-pop"),
    knowledgeFilter: $("knowledge-filter"),
    mapBreadcrumb: $("map-breadcrumb"),
    mapCurrent: $("map-current"),
    mapConnections: $("map-connections"),
    peopleList: $("people-list"),
    worldClock: $("world-clock"),
    offlineBanner: $("offline-banner"),
  };

  // Must match the rail breakpoint in style.css.
  const desktopQuery = window.matchMedia("(min-width: 960px)");
  const isDesktop = () => desktopQuery.matches;

  let currentGameId = null;
  let supabaseClient = null;
  let authRequired = false;
  // Whether players may ask for a painted poster (ADR-0019, operator flag).
  let postersEnabled = false;
  // Object URLs of painted posters on screen; revoked when the library re-renders.
  let posterUrls = [];
  // Snapshot of the last character payload, used to detect newly-arrived
  // items so they can briefly glow gold on the turn they appear.
  let prevCharacter = null;
  // Same delta trick for the world payload (map + people).
  let prevWorld = null;
  // Knowledge panel: client-side source filter ("ALL" or a FactSource value).
  let factFilter = "ALL";
  let allFacts = [];
  // Which pane the mobile tab bar shows (Story / Character / Map), and which
  // one the desktop rail shows next to the always-visible Story column. Each
  // layout reads its own attribute, so crossing the breakpoint never flashes
  // a side pane in the story's place. On desktop activePane stays "story".
  let activePane = "story";
  let railPane = "character";
  // Mobile: where the reader was in the story before opening another pane.
  let storyScrollY = null;

  const FACT_TITLES = {
    FACT: "fact",
    RUMOR: "rumor",
    PERSONAL_EXPERIENCE: "personal experience",
    HEARSAY: "hearsay",
  };

  // Stage cast chips beyond this count collapse into a "+N" chip.
  const STAGE_CAST_LIMIT = 4;

  // Inline icons. Location types and times of day are drawn rather than
  // written so the chrome stays readable in every story language.
  const svg = (paths) =>
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" ' +
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths + "</svg>";

  const PLACE_ICONS = {
    building: svg('<path d="M5 20V9.5L12 4l7 5.5V20M9.5 20v-5.5h5V20M3 20h18"/>'),
    district: svg('<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>'),
    city: svg('<path d="M3 20h18M5 20v-9h4v9M9 20V5h6v15M15 20v-7h4v7"/>'),
    region: svg('<path d="M2 19 9 8l4 6 3-4 6 9z"/>'),
    country: svg('<path d="M5 21V4M5 4h12l-2.5 4L17 12H5"/>'),
    generic: svg('<path d="M12 4 20 12 12 20 4 12z"/>'),
  };

  const DAYPART_ICONS = {
    morning: svg('<path d="M3 18h18M7 18a5 5 0 0 1 10 0M12 3v5M9.5 5.5 12 3l2.5 2.5M4.9 12.9l1.4 1M19.1 12.9l-1.4 1"/>'),
    afternoon: svg('<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>'),
    evening: svg('<path d="M3 18h18M7 18a5 5 0 0 1 10 0M12 3v5M9.5 5.5 12 8l2.5-2.5M4.9 12.9l1.4 1M19.1 12.9l-1.4 1"/>'),
    night: svg('<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>'),
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

  // One screen at a time: "loading" | "library" | "setting" | "play".
  // Panels and top-bar buttons follow the screen, so there is always a way
  // back to the library and never two "New game" buttons on screen at once.
  function setScreen(name) {
    document.body.dataset.screen = name;
    if (name !== "play") delete document.body.dataset.daypart;
    els.storiesPanel.hidden = name !== "library";
    els.settingPanel.hidden = name !== "setting";
    els.gamePanel.hidden = name !== "play";
    els.libraryBtn.hidden = name === "library" || name === "loading";
    els.newGameBtn.hidden = name !== "play";
    els.feedbackOpenBtn.hidden = name !== "play";
    window.scrollTo(0, 0);
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
    // Entity spans are actions: make them reachable from the keyboard too.
    div.querySelectorAll(".poi").forEach((span) => {
      span.tabIndex = 0;
      span.setAttribute("role", "button");
    });
    els.log.appendChild(div);
    return div;
  }

  // Bring a transcript line to the top of the reading area (below the sticky
  // stage), so a new passage is read from its first line, not its last.
  function scrollToTurn(el, smooth) {
    if (!el || (!isDesktop() && activePane !== "story")) return;
    el.scrollIntoView({ block: "start", behavior: smooth ? "smooth" : "auto" });
  }

  function showPending() {
    const div = document.createElement("div");
    div.className = "turn pending";
    div.setAttribute("role", "status");
    div.innerHTML = '<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>';
    div.append("The AI narrator is resolving your action...");
    els.log.appendChild(div);
    return div;
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
    li.textContent = "Nothing yet.";
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
    flagPaneIfNew("character");
  }

  function placeIcon(locationType) {
    const span = document.createElement("span");
    span.className = "mp-icon";
    span.title = locationType;
    span.innerHTML = PLACE_ICONS[locationType] || PLACE_ICONS.generic;
    return span;
  }

  // Build the shared icon/name row used by both the current place and the
  // connected places. A connection row is a real button carrying the location
  // id and a "go" chevron, so a tap (or Enter) can drive a move gesture.
  function makeMapPlace(node, connection) {
    const row = document.createElement(connection ? "button" : "div");
    row.className = "map-place" + (connection ? "" : " here");
    const name = document.createElement("span");
    name.className = "mp-name";
    name.textContent = node.name;
    row.append(placeIcon(node.location_type), name);
    if (connection) {
      row.type = "button";
      row.dataset.locId = node.id;
      const go = document.createElement("span");
      go.className = "mp-go";
      go.innerHTML = svg('<path d="M9 6l6 6-6 6"/>');
      row.append(go);
    }
    const li = document.createElement("li");
    li.append(row);
    return li;
  }

  function renderConnectionNode(node) {
    return makeMapPlace(node, true);
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
    if (!current) {
      const empty = document.createElement("p");
      empty.className = "map-current-name empty";
      empty.textContent = "Location unknown.";
      els.mapCurrent.appendChild(empty);
      return;
    }
    const ul = document.createElement("ul");
    ul.className = "map-here-rail";
    ul.appendChild(makeMapPlace(current, false));
    els.mapCurrent.appendChild(ul);
  }

  function crumbNames(map) {
    return (map.breadcrumb || []).map((node) => node.name);
  }

  function renderMap(map) {
    els.mapBreadcrumb.textContent = crumbNames(map).join("  ›  ");
    renderMapCurrent(map.current);
    const prevConnections = prevWorld && prevWorld.map ? prevWorld.map.connections : null;
    renderList(els.mapConnections, map.connections, prevConnections, renderConnectionNode, mapNodeKey);
  }

  // "Day 2 · 18:00" with a drawn sun/moon for the time of day.
  function fillClock(el, clock) {
    const hour = String(clock.hour || 0).padStart(2, "0") + ":00";
    el.innerHTML = DAYPART_ICONS[clock.time_of_day] || "";
    el.append(" Day " + (clock.day || 1) + " · " + hour);
    el.title = clock.time_of_day || "";
  }

  function renderPeopleTime(world) {
    fillClock(els.worldClock, world.clock || {});
    const prevPeople = prevWorld ? prevWorld.people : null;
    renderList(els.peopleList, world.people, prevPeople, renderPerson, personKey);
  }

  // The stage: where the scene is, what time it is, and who is on stage.
  // Always in view above the prose; it is the theatre's lit proscenium.
  function renderStage(world) {
    const map = world.map || {};
    els.stageCrumbs.textContent = crumbNames(map).join(" · ");
    els.stagePlace.textContent = map.current ? map.current.name : "…";
    const clock = world.clock || {};
    fillClock(els.stageClock, clock);
    if (clock.time_of_day) document.body.dataset.daypart = clock.time_of_day;
    els.stageCast.innerHTML = "";
    const people = world.people || [];
    for (const person of people.slice(0, STAGE_CAST_LIMIT)) {
      const li = document.createElement("li");
      li.className = person.known ? "cast-known" : "cast-stranger";
      li.textContent = person.label;
      li.title = person.role;
      els.stageCast.appendChild(li);
    }
    if (people.length > STAGE_CAST_LIMIT) {
      const more = document.createElement("li");
      more.className = "cast-more";
      more.textContent = "+" + (people.length - STAGE_CAST_LIMIT);
      els.stageCast.appendChild(more);
    }
  }

  function renderWorld(world) {
    if (!world) return;
    renderStage(world);
    renderMap(world.map);
    renderPeopleTime(world);
    prevWorld = world;
    flagPaneIfNew("map");
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
    setScreen("play");
    // Land on the transcript after (re)loading a game on mobile, resuming at
    // the start of the latest passage.
    storyScrollY = null;
    selectPane("story");
    const cues = els.log.querySelectorAll(".turn.player");
    if (cues.length) scrollToTurn(cues[cues.length - 1], false);
    if (isDesktop()) els.actionInput.focus({ preventScroll: true });
  }

  function showSettingPanel() {
    currentGameId = null;
    prevCharacter = null;
    prevWorld = null;
    resetOpening();
    setScreen("setting");
    els.settingInput.focus({ preventScroll: true });
  }

  function showStoriesPanel() {
    setScreen("library");
  }

  // ── Library playbills ──
  // Every story with a playbill gets a poster: a drawn motif for its place
  // and time of day, replaced by the painted illustration once one exists.
  function posterArt(playbill) {
    const art = document.createElement("div");
    art.className = "poster-art";
    art.dataset.daypart = playbill.daypart;
    art.innerHTML =
      '<svg class="poster-curtains" viewBox="0 0 120 180" preserveAspectRatio="none" aria-hidden="true">' +
      '<path d="M0 0h120v9H0z"/><path d="M0 0c9 38 21 66 46 82C20 81 8 70 0 58z"/>' +
      '<path d="M120 0c-9 38-21 66-46 82 26-1 38-12 46-24z"/></svg>';
    const motif = placeIcon(playbill.place_type);
    motif.className = "poster-motif";
    const sky = document.createElement("span");
    sky.className = "poster-daypart";
    sky.innerHTML = DAYPART_ICONS[playbill.daypart] || "";
    art.append(motif, sky);
    return art;
  }

  // Posters are behind auth, so fetch the bytes rather than pointing <img> at the URL.
  async function loadPosterImage(frame, gameId) {
    try {
      const response = await apiFetch("/api/games/" + encodeURIComponent(gameId) + "/poster");
      if (!response.ok) return;
      const url = URL.createObjectURL(await response.blob());
      posterUrls.push(url);
      const img = document.createElement("img");
      img.className = "poster-img";
      img.alt = "";
      img.src = url;
      frame.appendChild(img);
    } catch {
      // The drawn playbill stays as the poster.
    }
  }

  function renderPoster(story) {
    const frame = document.createElement("div");
    frame.className = "poster";
    frame.dataset.posterFor = story.game_id;
    frame.append(posterArt(story.playbill));
    if (story.has_poster_image) loadPosterImage(frame, story.game_id);
    return frame;
  }

  // "Starring <hero> · with <cast>" — cast labels are already name-gated.
  function renderBilling(playbill) {
    const line = document.createElement("p");
    line.className = "story-cast";
    if (playbill.hero) {
      const hero = document.createElement("span");
      hero.className = "cast-hero";
      hero.textContent = playbill.hero;
      line.append("Starring ", hero);
    }
    playbill.cast.forEach((member, index) => {
      line.append(index === 0 ? (line.childNodes.length ? " · with " : "With ") : ", ");
      const name = document.createElement("span");
      name.className = member.known ? "cast-known" : "cast-stranger";
      name.textContent = member.label;
      line.append(name);
    });
    return line.childNodes.length ? line : null;
  }

  function renderStoryMeta(story) {
    const meta = document.createElement("div");
    meta.className = "story-meta";
    const title = document.createElement("strong");
    title.className = "story-title";
    title.textContent = story.title || story.setting || "Untitled story";
    meta.append(title);
    const playbill = story.playbill;
    if (playbill && playbill.tagline) {
      const tagline = document.createElement("p");
      tagline.className = "story-tagline";
      tagline.textContent = playbill.tagline;
      meta.append(tagline);
    }
    const billing = playbill ? renderBilling(playbill) : null;
    if (billing) meta.append(billing);
    const setting = document.createElement("span");
    setting.className = "story-setting";
    setting.textContent = story.setting || "Unknown setting";
    const turns = document.createElement("span");
    turns.className = "story-turns";
    turns.textContent = story.turn_count + (story.turn_count === 1 ? " turn" : " turns");
    meta.append(setting, turns);
    return meta;
  }

  function actionButton(className, dataKey, gameId, label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.dataset[dataKey] = gameId;
    button.textContent = label;
    return button;
  }

  function renderStoryActions(story) {
    const actions = document.createElement("div");
    actions.className = "story-actions";
    actions.append(actionButton("btn-primary", "continueGame", story.game_id, "Continue"));
    if (postersEnabled && story.playbill && !story.has_poster_image) {
      actions.append(actionButton("btn-secondary", "paintPoster", story.game_id, "Paint poster"));
    }
    actions.append(actionButton("btn-quiet", "archiveGame", story.game_id, "Archive"));
    return actions;
  }

  function renderStoryRow(story) {
    const li = document.createElement("li");
    li.className = "story-row" + (story.playbill ? " has-playbill" : "");
    if (story.playbill) li.append(renderPoster(story));
    li.append(renderStoryMeta(story), renderStoryActions(story));
    return li;
  }

  // Poster errors show on the card they belong to, not at the foot of the list.
  function setPosterStatus(row, text) {
    let note = row.querySelector(".poster-status");
    if (!note) {
      note = document.createElement("p");
      row.querySelector(".story-meta").append(note);
    }
    setStatus(note, text, "poster-status");
  }

  async function paintPoster(button) {
    const gameId = button.dataset.paintPoster || "";
    const row = button.closest(".story-row");
    const frame = row.querySelector(".poster");
    button.disabled = true;
    button.textContent = "Painting…";
    frame.classList.add("is-painting");
    setPosterStatus(row, "");
    try {
      const response = await apiFetch("/api/games/" + encodeURIComponent(gameId) + "/poster", { method: "POST" });
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      button.remove();
      await loadPosterImage(frame, gameId);
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      button.disabled = false;
      button.textContent = "Paint poster";
      setPosterStatus(row, "Could not paint the poster: " + err.message);
    } finally {
      frame.classList.remove("is-painting");
    }
  }

  function renderStories(games) {
    if (!els.storiesList) return;
    posterUrls.forEach((url) => URL.revokeObjectURL(url));
    posterUrls = [];
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

  async function fetchStories() {
    const response = await apiFetch("/api/games");
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    setOfflineNotice(false);
    const data = await response.json();
    return data.games || [];
  }

  async function loadStories() {
    try {
      renderStories(await fetchStories());
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      showSettingPanel();
      setStatus(els.settingStatus, "Could not load stories: " + err.message);
    } finally {
      hide(els.loading);
    }
  }

  // The Stories button. Unlike the first load, a failure keeps the player
  // where they are (a story in play stays playable) and reports it there.
  async function openLibrary() {
    try {
      renderStories(await fetchStories());
    } catch (err) {
      if (isNetworkError(err)) setOfflineNotice(true);
      const status = document.body.dataset.screen === "play" ? els.actionStatus : els.settingStatus;
      setStatus(status, "Could not load stories: " + err.message);
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

  function setSignedIn(signedIn) {
    if (els.authPanel) els.authPanel.hidden = signedIn;
    if (els.loginForm) els.loginForm.hidden = signedIn;
    if (els.logoutBtn) els.logoutBtn.hidden = !signedIn;
  }

  async function loadPublicConfig() {
    const response = await fetch("/api/config/public");
    if (!response.ok) return;
    const cfg = await response.json();
    postersEnabled = Boolean(cfg.poster_images_enabled);
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
    setSignedIn(Boolean(data && data.session));
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
    setSignedIn(false);
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

  // While the opening is built the form steps aside for the curtain.
  function showOpening() {
    hide(els.settingForm);
    show(els.opening);
    window.scrollTo(0, 0);
  }

  function resetOpening() {
    hide(els.opening);
    show(els.settingForm);
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
    // The curtain stays up until this start settles: leaving for the library
    // now would let the late response pull the player back into the new story.
    els.libraryBtn.disabled = true;
    showOpening();
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
      resetOpening();
      setStatus(els.settingStatus, "Failed to start game: " + err.message);
    } finally {
      button.disabled = false;
      els.libraryBtn.disabled = false;
    }
  }

  function escapeHTML(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // One turn at a time across every entry point (composer, entity, map):
  // the composer locks and gestures dim until the narrator answers.
  function setTurnPending(on) {
    els.gamePanel.toggleAttribute("data-turn-pending", on);
    els.actionInput.disabled = on;
    els.actionSubmit.disabled = on;
  }

  function turnPending() {
    return els.gamePanel.hasAttribute("data-turn-pending");
  }

  function releaseComposer() {
    setTurnPending(false);
    // Desktop keeps typing flow; on phones drop the keyboard so the new
    // passage has the whole screen.
    if (isDesktop()) {
      els.actionInput.focus({ preventScroll: true });
    } else {
      els.actionInput.blur();
    }
  }

  // The single render path for every turn entry point: the free-text
  // composer, an in-prose entity tap, and a map place tap. ``body`` is the
  // POST payload (``{action}`` or ``{gesture}``); ``optimisticEcho`` is the
  // player line to echo immediately for free-text (the client knows it).
  // Gesture turns pass no echo and render the server-composed ``action_html``
  // instead, since the phrase is composed server-side in the session language.
  async function submitTurn(body, optimisticEcho) {
    if (!currentGameId || turnPending()) return;
    const gameId = currentGameId;
    setTurnPending(true);
    selectPane("story");
    let cue = optimisticEcho ? appendTurnHTML("player", escapeHTML(optimisticEcho)) : null;
    const pending = showPending();
    scrollToTurn(cue || pending, true);
    setStatus(els.actionStatus, "");
    try {
      const response = await apiFetch(
        "/api/games/" + encodeURIComponent(gameId) + "/actions",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      setOfflineNotice(false);
      const data = await response.json();
      pending.remove();
      // The player may have opened another story while this turn resolved.
      if (currentGameId !== gameId) return;
      if (!cue && data.action_html) cue = appendTurnHTML("player", data.action_html);
      const passage = appendTurnHTML("narrator", data.narration_html);
      passage.classList.add("is-arriving");
      renderCharacter(data.character);
      renderWorld(data.world);
      scrollToTurn(cue || passage, true);
    } catch (err) {
      pending.remove();
      if (isNetworkError(err)) setOfflineNotice(true);
      if (currentGameId === gameId) setStatus(els.actionStatus, "Error: " + err.message);
    } finally {
      releaseComposer();
    }
  }

  function onSubmitAction(event) {
    event.preventDefault();
    const action = els.actionInput.value.trim();
    if (!action || !currentGameId) return;
    els.actionInput.value = "";
    autosizeComposer();
    submitTurn({ action }, action);
  }

  // The composer grows with the player's line, up to the CSS max-height.
  // ``field-sizing: content`` does this natively; the JS path is a fallback.
  const nativeFieldSizing = window.CSS && CSS.supports("field-sizing", "content");

  function autosizeComposer() {
    if (nativeFieldSizing) return;
    const input = els.actionInput;
    input.style.height = "auto";
    input.style.height = input.scrollHeight + 2 + "px";
  }

  // Enter sends; Shift+Enter keeps a line break; IME composition is untouched.
  // Safari reports the Enter that confirms an IME candidate with
  // ``isComposing`` false but the composition keyCode 229.
  function onComposerKeydown(event) {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    els.actionForm.requestSubmit();
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

  function openFeedback() {
    setStatus(els.feedbackStatus, "");
    els.feedbackDialog.showModal();
    els.feedbackMessage.focus();
  }

  function onFeedbackDialogClick(event) {
    // A click on the backdrop lands on the <dialog> element itself.
    if (event.target === els.feedbackDialog) els.feedbackDialog.close();
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
    const paintBtn = event.target.closest("button[data-paint-poster]");
    if (paintBtn) {
      paintPoster(paintBtn);
      return;
    }
    const archiveBtn = event.target.closest("button[data-archive-game]");
    if (archiveBtn) {
      archiveStory(archiveBtn.dataset.archiveGame || "");
    }
  }

  function onSettingExampleClick(event) {
    const button = event.target.closest("button[data-setting-example]");
    if (!button) return;
    els.settingInput.value = button.dataset.settingExample || "";
    els.settingInput.focus();
  }

  function initFoldableSections() {
    document.querySelectorAll(".pane-scroll h4").forEach((heading) => {
      const list = heading.nextElementSibling;
      if (!list || list.tagName !== "UL") return;
      heading.classList.add("is-foldable");
      heading.addEventListener("click", () => heading.classList.toggle("is-folded"));
    });
  }

  // ── Play screen: Story / Character / Map panes + entity popover ──

  function paneEl(name) {
    return document.querySelector('.play-pane[data-pane="' + name + '"]');
  }

  function setBadge(pane, on) {
    const tab = els.tabbar.querySelector('.tab[data-pane="' + pane + '"]');
    if (tab) tab.classList.toggle("has-new", on);
  }

  // Light a tab's "has-new" dot when its pane gained entries this turn and the
  // player isn't already looking at it. ``renderList`` marks fresh rows
  // ``.is-new``; we reuse that signal rather than recomputing the delta.
  function flagPaneIfNew(pane) {
    if (visiblePane() === pane) return;
    const el = paneEl(pane);
    if (el && el.querySelector(".is-new")) setBadge(pane, true);
  }

  // The Character/Map pane on screen: the rail pane on desktop (Story is
  // always beside it), the tab-bar pane on phones.
  function visiblePane() {
    return isDesktop() ? railPane : activePane;
  }

  function applyPanes() {
    const shown = visiblePane();
    document.querySelectorAll(".play-pane").forEach((pane) => {
      pane.toggleAttribute("data-pane-active", pane.dataset.pane === activePane);
      pane.toggleAttribute("data-rail-active", pane.dataset.pane === railPane);
    });
    els.tabbar.querySelectorAll(".tab[data-pane]").forEach((tab) => {
      const selected = tab.dataset.pane === shown;
      tab.classList.toggle("on", selected);
      tab.setAttribute("aria-selected", String(selected));
    });
    setBadge(shown, false);
  }

  function selectPane(name) {
    closePopover();
    if (name !== "story") railPane = name;
    if (isDesktop()) {
      applyPanes();
      return;
    }
    const previous = activePane;
    if (previous === "story" && name !== "story") storyScrollY = window.scrollY;
    activePane = name;
    applyPanes();
    if (previous === name) return;
    // Mobile panes share the page scroll: open side panes at the top and
    // return the reader to where they left the story.
    if (name === "story") {
      window.scrollTo(0, storyScrollY === null ? document.body.scrollHeight : storyScrollY);
    } else {
      window.scrollTo(0, 0);
    }
  }

  function onTabClick(event) {
    const tab = event.target.closest(".tab[data-pane]");
    if (tab) selectPane(tab.dataset.pane);
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

  // ── In-prose entity popover ──
  // Tapping a .poi span offers the verbs valid for its kind; picking one runs
  // a structured gesture (the server composes the localized action phrase).
  const ENTITY_VERBS = {
    npc: [{ label: "Look closer", intent: "examine" }, { label: "Talk", intent: "talk" }],
    poi: [{ label: "Investigate", intent: "examine" }],
    item: [{ label: "Investigate", intent: "examine" }],
  };

  let openSpan = null;

  // Closing hands a keyboard user back to the word the popover came from
  // rather than dropping focus to the page.
  function closePopover() {
    if (els.entPop.hidden) return;
    const hadFocus = els.entPop.contains(document.activeElement);
    els.entPop.hidden = true;
    els.entPop.classList.remove("open");
    els.entPop.innerHTML = "";
    if (openSpan) {
      openSpan.classList.remove("is-open");
      if (hadFocus) openSpan.focus({ preventScroll: true });
    }
    openSpan = null;
  }

  function openPopover(span, fromKeyboard) {
    const kind = span.dataset.kind;
    const id = span.dataset.id;
    const verbs = ENTITY_VERBS[kind];
    if (!verbs || !id || turnPending()) return;
    closePopover();
    openSpan = span;
    span.classList.add("is-open");
    els.entPop.dataset.kind = kind;
    const title = document.createElement("p");
    title.className = "ep-title";
    title.textContent = span.textContent;
    els.entPop.appendChild(title);
    for (const verb of verbs) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ep-act";
      btn.textContent = verb.label;
      btn.addEventListener("click", () => {
        submitTurn({ gesture: { intent: verb.intent, entity_kind: kind, entity_id: id } });
      });
      els.entPop.appendChild(btn);
    }
    // Position near the tapped word, viewport-relative (position:fixed), then
    // reveal so the entry transition runs after layout. Flip above the word
    // when it would run into the composer.
    const rect = span.getBoundingClientRect();
    els.entPop.hidden = false;
    const width = els.entPop.offsetWidth;
    const height = els.entPop.offsetHeight;
    const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
    const below = rect.bottom + 6;
    const floor = els.actionForm.getBoundingClientRect().top;
    const top = below + height > floor ? Math.max(8, rect.top - height - 6) : below;
    els.entPop.style.left = left + "px";
    els.entPop.style.top = top + "px";
    requestAnimationFrame(() => els.entPop.classList.add("open"));
    if (fromKeyboard) {
      const first = els.entPop.querySelector(".ep-act");
      if (first) first.focus();
    }
  }

  function onLogClick(event) {
    const span = event.target.closest(".poi");
    if (span && els.log.contains(span)) {
      if (span === openSpan) {
        closePopover();
      } else {
        openPopover(span, false);
      }
      return;
    }
    closePopover();
  }

  function onLogKeydown(event) {
    if (event.key !== "Enter" && event.key !== " ") return;
    const span = event.target.closest(".poi");
    if (!span) return;
    event.preventDefault();
    openPopover(span, true);
  }

  // Crossing the breakpoint switches between the tab-bar and rail views, and
  // both land on the story. A phone side pane owned the page scroll, so the
  // wide layout puts the reader back where they left the story; the way back
  // keeps the story on screen throughout, so its scroll survives as is.
  function onBreakpointChange() {
    const leftStory = activePane !== "story";
    activePane = "story";
    applyPanes();
    if (isDesktop() && leftStory && storyScrollY !== null) window.scrollTo(0, storyScrollY);
  }

  function onMapPlaceClick(event) {
    const row = event.target.closest(".map-place[data-loc-id]");
    if (!row) return;
    submitTurn({ gesture: { intent: "move", entity_kind: "location", entity_id: row.dataset.locId } });
  }

  function initPlayScreen() {
    applyPanes();
    // Keep --stage-h equal to the sticky stage's real height (it changes with
    // the cast row and the crumbs) so a scrolled-to passage clears it.
    new ResizeObserver(() => {
      document.documentElement.style.setProperty("--stage-h", els.stage.offsetHeight + "px");
    }).observe(els.stage);
    els.tabbar.addEventListener("click", onTabClick);
    if (els.knowledgeFilter) els.knowledgeFilter.addEventListener("click", onFactFilterClick);
    els.log.addEventListener("click", onLogClick);
    els.log.addEventListener("keydown", onLogKeydown);
    window.addEventListener("scroll", closePopover, { passive: true });
    els.mapConnections.addEventListener("click", onMapPlaceClick);
    els.stagePlaceBtn.addEventListener("click", () => selectPane("map"));
    els.actionInput.addEventListener("input", autosizeComposer);
    els.actionInput.addEventListener("keydown", onComposerKeydown);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closePopover();
    });
    document.addEventListener("click", (event) => {
      if (!els.entPop.hidden && !els.entPop.contains(event.target) && !els.log.contains(event.target)) {
        closePopover();
      }
    });
    desktopQuery.addEventListener("change", onBreakpointChange);
  }

  els.settingForm.addEventListener("submit", onStartGame);
  els.actionForm.addEventListener("submit", onSubmitAction);
  if (els.feedbackForm) {
    els.feedbackForm.addEventListener("submit", onSubmitFeedback);
  }
  els.feedbackOpenBtn.addEventListener("click", openFeedback);
  els.feedbackCloseBtn.addEventListener("click", () => els.feedbackDialog.close());
  els.feedbackDialog.addEventListener("click", onFeedbackDialogClick);
  els.newGameBtn.addEventListener("click", onNewGame);
  els.libraryBtn.addEventListener("click", openLibrary);
  if (els.libraryNewGameBtn) {
    els.libraryNewGameBtn.addEventListener("click", onNewGame);
  }
  if (els.storiesList) {
    els.storiesList.addEventListener("click", onStoriesClick);
  }
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
  initPlayScreen();
  loadPublicConfig().finally(loadStories);
})();

// SPDX-License-Identifier: Apache-2.0
/* Enigma2 Connect remote card. Uses the standard remote.send_command action. */
export class HoldController {
  constructor(send, timers = globalThis) {
    this.send = send;
    this.timers = timers;
    this.generation = 0;
    this.timeout = null;
  }

  stop() {
    this.generation += 1;
    this.timers.clearTimeout(this.timeout);
    this.timeout = null;
  }

  async start(key, repeat) {
    this.stop();
    const generation = this.generation;
    const step = async (first) => {
      const success = await this.send(key);
      if (success && repeat && generation === this.generation) {
        this.timeout = this.timers.setTimeout(() => step(false), first ? 450 : 220);
      }
    };
    await step(true);
  }
}

async function actionError(hass, error, fallback) {
  let message = error?.message || fallback;
  if (error?.translation_domain && error.translation_key) {
    try {
      const localize = await hass.loadBackendTranslation?.("exceptions", [error.translation_domain]);
      message = localize?.(`component.${error.translation_domain}.exceptions.${error.translation_key}.message`, error.translation_placeholders || {}) || message;
    } catch { /* Preserve the original error if translations are unavailable. */ }
  }
  return message;
}

// Captures the receiver for every request and discards late replies after rebind.
export class EpgController {
  constructor(changed) { this.changed = changed; this.generation = 0; this.resultsRevision = 0; this.bind(null); }
  bind(device) {
    if (this.device === device) return;
    this.device = device;
    this.generation += 1;
    this.busy = false;
    this.events = [];
    this.page = 0;
    this.recorded = new Set();
    this.message = "";
    this.searched = false;
    this.truncated = false;
  }
  invalidate() { this.device = undefined; this.bind(null); }
  resetSearch() {
    this.resultsRevision += 1;
    this.events = [];
    this.page = 0;
    this.message = "";
    this.searched = false;
    this.truncated = false;
    // Keep busy/recorded: resetting the view cannot cancel a recording request.
    this.changed();
  }
  visibleEvents(mode) {
    return mode === "single" ? this.events.slice(this.page, this.page + 1) : this.events;
  }
  movePage(delta) {
    if (this.busy) return;
    this.page = Math.max(0, Math.min(this.events.length - 1, this.page + delta));
    this.changed();
  }
  key(event) { return JSON.stringify([event.service_reference, event.event_id, event.begin, event.end]); }
  async run(hass, service, input, text) {
    if (!this.device || this.busy) return;
    const generation = this.generation;
    const resultsRevision = this.resultsRevision;
    const obsoleteSearch = () => service !== "record_event" && resultsRevision !== this.resultsRevision;
    const serviceData = {device_id: this.device};
    if (service === "epg_search") {
      if (!input.trim()) return;
      serviceData.query = input.trim();
    } else {
      for (const key of ["service_reference", "event_id", "begin", "end"]) serviceData[key] = input[key];
    }
    this.busy = true;
    this.message = text.loading;
    this.changed();
    try {
      const result = await hass.callWS({type: "call_service", domain: "enigma2_connect", service,
        service_data: serviceData, return_response: true});
      if (generation !== this.generation || obsoleteSearch()) return;
      const response = result?.response;
      if (service === "record_event") {
        if (typeof response?.created !== "boolean") throw new Error(text.failed);
        this.recorded.add(this.key(input));
        this.message = response.created ? text.created : text.existing;
      } else {
        if (!Array.isArray(response?.events)) throw new Error(text.failed);
        this.events = response.events;
        this.page = 0;
        this.truncated = response.truncated === true;
        this.searched = true;
        this.message = this.events.length ? "" : text.empty;
      }
    } catch (error) {
      const message = await actionError(hass, error, text.failed);
      if (generation !== this.generation || obsoleteSearch()) return;
      this.message = message;
    } finally {
      if (generation === this.generation) { this.busy = false; this.changed(); }
    }
  }
}

const ROWS = [
  [["power", "⏻"], ["mute", "Mute"]],
  [["1", "1"], ["2", "2"], ["3", "3"]],
  [["4", "4"], ["5", "5"], ["6", "6"]],
  [["7", "7"], ["8", "8"], ["9", "9"]],
  [["epg", "EPG"], ["0", "0"], ["info", "Info"]],
  [["menu", "Menu"], ["up", "▲"], ["exit", "Exit"]],
  [["left", "◀"], ["ok", "OK"], ["right", "▶"]],
  [["favorites", "Fav"], ["down", "▼"], ["help", "Help"]],
  [["red", "Red"], ["green", "Green"], ["yellow", "Yellow"], ["blue", "Blue"]],
  [["volume_down", "Vol −"], ["volume_up", "Vol +"], ["channel_down", "CH −"], ["channel_up", "CH +"]],
  [["rewind", "≪"], ["play", "Play"], ["pause", "Pause"], ["fast_forward", "≫"]],
  [["stop", "Stop"], ["record", "Rec"], ["tv", "TV"], ["radio", "Radio"]],
  [["audio", "Audio"], ["subtitle", "Sub"], ["text", "Text"]],
];
const REPEAT = new Set(["up", "down", "left", "right", "volume_up", "volume_down", "channel_up", "channel_down", "fast_forward", "rewind"]);

const TEXT = {
  en: {
    epgCardName: "Enigma2 Connect EPG search",
    epgCardDescription: "Search programmes and schedule recordings without remote buttons.",
    options: {results_view: "Result display", show_epg: "Show EPG search", show_playback: "Show playback controls", show_numbers: "Show number buttons"},
    viewOptions: {list: "List", single: "One result with navigation"},
    invalidView: "Result display must be list or single.",
    invalidOption: "Card options must be true or false.",
    cardName: "Enigma2 Connect remote control",
    cardDescription: "Enigma2 / OpenWebif remote: select the receiver and title in the visual editor.",
    invalidEntity: "Configure an Enigma2 Connect remote entity using 'entity: remote.…'.",
    selectReceiver: "Select the receiver control in the card editor.",
    unavailable: "Receiver unavailable.",
    commandFailed: "The remote command failed.",
    key: "Key",
    epg: {title: "Search programmes", query: "Programme title", search: "Search", clear: "Reset search", similar: "Similar", record: "Record",
      loading: "Checking receiver…", empty: "No ongoing or future matches.", failed: "The EPG action failed.",
      created: "Recording timer created.", existing: "A recording timer already covers this programme.",
      count: "{count} results", one: "1 result", position: "Result {index} of {count}",
      more: "more available",
      shown: "{count} results shown; more available", previous: "Previous result", next: "Next result",
      recorded: "Scheduled", limited: "Update the integration to dev.12 or newer to access all returned results.",
      hint: "Searches this receiver's stored EPG. OpenWebif may limit the result pool."},
    buttons: {
      power: "Power", mute: "Mute", epg: "Programme guide", info: "Information",
      menu: "Menu", up: "Up", exit: "Exit", left: "Left", ok: "OK", right: "Right",
      favorites: "Favorites", down: "Down", help: "Help", red: "Red", green: "Green",
      yellow: "Yellow", blue: "Blue", volume_down: "Volume down", volume_up: "Volume up",
      channel_down: "Previous channel", channel_up: "Next channel", rewind: "Rewind",
      play: "Play", pause: "Pause", fast_forward: "Fast forward", stop: "Stop",
      record: "Record", tv: "TV", radio: "Radio", audio: "Audio", subtitle: "Subtitles",
      text: "Teletext",
    },
    labels: {},
  },
  de: {
    epgCardName: "Enigma2 Connect EPG-Suche",
    epgCardDescription: "Sendungen suchen und Aufnahmen planen, ohne Fernbedienungstasten.",
    options: {results_view: "Trefferanzeige", show_epg: "EPG-Suche anzeigen", show_playback: "Videosteuerung anzeigen", show_numbers: "Zahlentasten anzeigen"},
    viewOptions: {list: "Liste", single: "Einzeln mit Blättern"},
    invalidView: "Trefferanzeige muss list oder single sein.",
    invalidOption: "Die Kartenoptionen müssen true oder false sein.",
    cardName: "Enigma2 Connect Fernbedienung",
    cardDescription: "Enigma2 / OpenWebif Fernbedienung: Receiver und Titel im grafischen Editor auswählen.",
    invalidEntity: "Eine Enigma2-Connect-Fernbedienung mit 'entity: remote.…' konfigurieren.",
    selectReceiver: "Bitte die Receiver-Steuerung im Karteneditor auswählen.",
    unavailable: "Receiver nicht verfügbar.",
    commandFailed: "Der Fernbedienungsbefehl ist fehlgeschlagen.",
    key: "Taste",
    epg: {title: "Sendungen suchen", query: "Sendungstitel", search: "Suchen", clear: "Suche zurücksetzen", similar: "Ähnliche", record: "Aufnehmen",
      loading: "Receiver wird geprüft…", empty: "Keine laufenden oder zukünftigen Treffer.", failed: "Die EPG-Aktion ist fehlgeschlagen.",
      created: "Aufnahmetimer angelegt.", existing: "Ein Aufnahmetimer deckt diese Sendung bereits ab.",
      count: "{count} Treffer", one: "1 Treffer", position: "Treffer {index} von {count}",
      more: "weitere vorhanden",
      shown: "{count} Treffer angezeigt; weitere vorhanden", previous: "Vorheriger Treffer", next: "Nächster Treffer",
      recorded: "Eingeplant", limited: "Integration auf dev.12 oder neuer aktualisieren, um alle gelieferten Treffer zu sehen.",
      hint: "Durchsucht das gespeicherte EPG dieses Receivers. OpenWebif kann die Treffermenge begrenzen."},
    buttons: {
      power: "Ein/Aus", mute: "Stumm", epg: "Programmführer", info: "Information",
      menu: "Menü", up: "Nach oben", exit: "Zurück", left: "Nach links", ok: "OK",
      right: "Nach rechts", favorites: "Favoriten", down: "Nach unten", help: "Hilfe",
      red: "Rot", green: "Grün", yellow: "Gelb", blue: "Blau", volume_down: "Leiser",
      volume_up: "Lauter", channel_down: "Vorheriger Sender", channel_up: "Nächster Sender",
      rewind: "Zurückspulen", play: "Wiedergabe", pause: "Pause", fast_forward: "Vorspulen",
      stop: "Stopp", record: "Aufnahme", tv: "Fernsehen", radio: "Radio", audio: "Tonspur",
      subtitle: "Untertitel", text: "Videotext",
    },
    labels: {
      mute: "Stumm", menu: "Menü", exit: "Zurück", help: "Hilfe", red: "Rot", green: "Grün",
      yellow: "Gelb", blue: "Blau", volume_down: "Vol −", volume_up: "Vol +",
      channel_down: "P −", channel_up: "P +", play: "Start", stop: "Stopp", record: "Aufn.",
      subtitle: "UT", audio: "Ton",
    },
  },
};

export function cardLanguage(language) {
  const locale = language || globalThis.document?.documentElement?.lang || globalThis.navigator?.language || "en";
  return /^de(?:[-_]|$)/i.test(locale) ? "de" : "en";
}

// Inline geometry avoids missing glyphs and platform-specific emoji rendering.
const ICONS = {
  power: '<path d="M12 3v9M6.3 5.7a8 8 0 1 0 11.4 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  up: '<path d="m12 5 8 14H4z"/>',
  down: '<path d="m12 19 8-14H4z"/>',
  left: '<path d="m5 12 14-8v16z"/>',
  right: '<path d="m19 12-14-8v16z"/>',
  rewind: '<path d="m3 12 9-7v14zm9 0 9-7v14z"/>',
  fast_forward: '<path d="m21 12-9-7v14zm-9 0L3 5v14z"/>',
};

function buttonContent(key, label) {
  return ICONS[key]
    ? `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[key]}</svg>`
    : label;
}

function isEnigmaRemote(hass, entityId) {
  return typeof entityId === "string" && entityId.startsWith("remote.")
    && hass?.entities?.[entityId]?.platform === "enigma2_connect";
}

export class Enigma2RemoteCard extends HTMLElement {
  static epgOnly = false;

  remoteRows() {
    if (this.constructor.epgOnly) return [];
    const playback = new Set(["rewind", "play", "pause", "fast_forward", "stop", "record"]);
    return ROWS.map(row => row.filter(([key]) =>
      (this.config?.show_numbers !== false || !/^[0-9]$/.test(key)) &&
      (this.config?.show_playback !== false || !playback.has(key))
    )).filter(row => row.length);
  }

  static getStubConfig(hass, entities = [], fallbackEntities = []) {
    const candidates = [...entities, ...fallbackEntities, ...Object.keys(hass?.entities || {})];
    return {entity: candidates.find(entityId => isEnigmaRemote(hass, entityId)) || ""};
  }

  static getConfigForm() {
    return {
      schema: [
        {name: "entity", required: true, selector: {entity: {filter: {domain: "remote", integration: "enigma2_connect"}}}},
        {name: "name", selector: {text: {}}},
        {name: "results_view", default: "single", selector: {select: {mode: "dropdown", options:
          Object.entries(TEXT[cardLanguage()].viewOptions).map(([value, label]) => ({value, label}))}}},
        ...(this.epgOnly ? [] : ["show_epg", "show_playback", "show_numbers"].map(name =>
          ({name, default: name !== "show_epg", selector: {boolean: {}}}))),
      ],
      computeLabel: schema => TEXT[cardLanguage()].options[schema.name],
    };
  }

  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.hold = new HoldController((key) => this.send(key));
    this.epg = new EpgController(() => this.renderEpg());
    this.onBlur = () => this.hold.stop();
    this.onVisibility = () => { if (document.hidden) this.hold.stop(); };
  }

  setConfig(config) {
    if (config.entity && (typeof config.entity !== "string" || !config.entity.startsWith("remote."))) {
      throw new Error(TEXT[cardLanguage(this._hass?.language)].invalidEntity);
    }
    this.hold.stop();
    this.errorMessage = "";
    this.epg.invalidate();
    for (const key of ["show_epg", "show_playback", "show_numbers"]) {
      if (config[key] !== undefined && typeof config[key] !== "boolean") {
        throw new Error(TEXT[cardLanguage(this._hass?.language)].invalidOption);
      }
    }
    if (config.results_view !== undefined && !["list", "single"].includes(config.results_view)) {
      throw new Error(TEXT[cardLanguage(this._hass?.language)].invalidView);
    }
    this.config = {...config, results_view: config.results_view ?? "single"};
    this.render();
  }

  connectedCallback() {
    window.addEventListener("blur", this.onBlur);
    document.addEventListener("visibilitychange", this.onVisibility);
    this.updateState();
  }

  disconnectedCallback() {
    this.hold.stop();
    this.epg.invalidate();
    window.removeEventListener("blur", this.onBlur);
    document.removeEventListener("visibilitychange", this.onVisibility);
  }

  set hass(value) {
    const language = cardLanguage(value?.language);
    this._hass = value;
    if (this.language !== language) {
      this.hold.stop();
      this.epg.invalidate();
      this.errorMessage = "";
      this.render();
      return;
    }
    this.updateState();
  }

  updateState() {
    if (!this.config || !this.shadowRoot.querySelector("h2")) return;
    const state = this._hass?.states[this.config.entity];
    this.available = Boolean(state && !["unavailable", "unknown"].includes(state.state));
    this.shadowRoot.querySelector("h2").textContent = this.config.name || state?.attributes.friendly_name || "Enigma2 Connect";
    this.shadowRoot.querySelectorAll("button[data-key]").forEach((button) => {button.disabled = !this.available;});
    if (!this.config.entity) {
      this.shadowRoot.querySelector("output").textContent = TEXT[this.language].selectReceiver;
    } else if (!this.available) {
      this.shadowRoot.querySelector("output").textContent = TEXT[this.language].unavailable;
    } else {
      this.shadowRoot.querySelector("output").textContent = this.errorMessage || "";
    }
    if (!this.available) this.hold.stop();
    const device = isEnigmaRemote(this._hass, this.config.entity)
      ? this._hass.entities[this.config.entity].device_id : null;
    if (this.epg.device !== (device || null)) {
      this.epg.bind(device || null);
      this.renderEpg();
    }
    this.updateEpgButtons();
  }

  async send(key) {
    if (!this.available || this.pending) return false;
    this.pending = true;
    try {
      await this._hass.callService("remote", "send_command", {entity_id: this.config.entity, command: [key]});
      this.errorMessage = "";
      this.updateState();
      return true;
    } catch (error) {
      this.errorMessage = error?.message || TEXT[this.language].commandFailed;
      if (error?.translation_domain && error.translation_key) {
        try {
          const localize = await this._hass.loadBackendTranslation?.("exceptions", [error.translation_domain]);
          this.errorMessage = localize?.(
            `component.${error.translation_domain}.exceptions.${error.translation_key}.message`,
            error.translation_placeholders || {},
          ) || this.errorMessage;
        } catch {
          // Keep the original error if translation resources cannot be loaded.
        }
      }
      this.updateState();
      return false;
    } finally {
      this.pending = false;
    }
  }

  updateEpgButtons() {
    this.shadowRoot.querySelectorAll(".epg button:not(.epg-clear)").forEach(button => {
      if (button.dataset.page) {
        button.disabled = this.epg.busy || (button.dataset.page === "previous"
          ? this.epg.page === 0 : this.epg.page >= this.epg.events.length - 1);
      } else {
        button.disabled = !this.available || !this.epg.device || this.epg.busy || button.dataset.recorded === "true";
      }
    });
  }

  async epgAction(service, input) {
    if (!this.available) return;
    await this.epg.run(this._hass, service, input, TEXT[this.language].epg);
  }

  clearSearch() {
    const input = this.shadowRoot.querySelector("#epg-query");
    if (!input) return;
    input.value = "";
    this.epg.resetSearch();
    input.focus();
  }

  resultSummary() {
    if (!this.epg.searched) return "";
    const text = TEXT[this.language].epg;
    const count = this.epg.events.length;
    const summary = this.epg.truncated ? text.shown : count === 1 ? text.one : text.count;
    const label = summary.replace("{count}", count);
    return this.config.results_view === "single" && count
      ? `${text.position.replace("{index}", this.epg.page + 1).replace("{count}", count)}${this.epg.truncated ? ` · ${text.more}` : ""}` : label;
  }

  renderEpg() {
    const list = this.shadowRoot.querySelector(".epg-results");
    if (!list) return;
    const text = TEXT[this.language].epg;
    this.shadowRoot.querySelector(".epg-status").textContent = this.epg.message;
    this.shadowRoot.querySelector(".epg-limited").textContent = this.epg.truncated ? text.limited : "";
    this.shadowRoot.querySelector(".epg-count").textContent = this.resultSummary();
    this.shadowRoot.querySelectorAll("[data-page]").forEach(button => {
      button.hidden = this.config.results_view !== "single" || !this.epg.events.length;
    });
    list.replaceChildren();
    const format = new Intl.DateTimeFormat(this._hass?.language || this.language, {
      dateStyle: "short", timeStyle: "short", timeZone: this._hass?.config?.time_zone || "UTC",
    });
    for (const event of this.epg.visibleEvents(this.config.results_view)) {
      const item = document.createElement("li");
      const heading = document.createElement("strong");
      heading.textContent = event.title || "EPG";
      const detail = document.createElement("p");
      detail.textContent = `${event.service_name || ""} · ${format.format(new Date(event.begin * 1000))} – ${format.format(new Date(event.end * 1000))}`;
      const description = document.createElement("p");
      description.textContent = event.description || "";
      const actions = document.createElement("div");
      actions.className = "row";
      for (const service of ["epg_similar", "record_event"]) {
        const button = document.createElement("button");
        button.type = "button";
        const recorded = service === "record_event" && this.epg.recorded.has(this.epg.key(event));
        button.dataset.recorded = String(recorded);
        button.textContent = recorded ? text.recorded : service === "epg_similar" ? text.similar : text.record;
        button.addEventListener("click", () => void this.epgAction(service, event));
        actions.append(button);
      }
      item.append(heading, detail, description, actions);
      list.append(item);
    }
    this.updateEpgButtons();
  }

  render() {
    this.language = cardLanguage(this._hass?.language);
    if (!this.config) return;
    const text = TEXT[this.language];
    const epgOnly = this.constructor.epgOnly;
    const showEpg = epgOnly || this.config.show_epg === true;
    // Only static labels enter HTML; entity names and errors use textContent.
    this.shadowRoot.innerHTML = `<ha-card><style>
      :host{display:block} .remote{max-width:340px;margin:auto;padding:20px}
      h2{font-size:18px;font-weight:500;margin:0 0 18px;color:var(--primary-text-color)}
      .row{display:flex;gap:8px;margin-bottom:8px} button{flex:1;min-height:44px;min-width:0;
        border:1px solid var(--divider-color,#bbb);border-radius:10px;cursor:pointer;touch-action:none;
        background:var(--secondary-background-color,#f2f2f2);color:var(--primary-text-color,#222);font:inherit;font-size:13px}
      button:focus-visible{outline:3px solid var(--primary-color,#03a9f4)} button:active{filter:brightness(.85)}
      button svg{display:block;width:20px;height:20px;margin:auto;fill:currentColor;pointer-events:none}
      button:disabled{opacity:.35;cursor:default} [data-key=red]{border-bottom:4px solid #d43c3c}
      [data-key=green]{border-bottom:4px solid #289752} [data-key=yellow]{border-bottom:4px solid #d5b800}
      [data-key=blue]{border-bottom:4px solid #337dd4} output{display:block;color:var(--error-color,#b00020);font-size:13px}
      .epg{margin-top:18px} .epg summary{cursor:pointer;padding:8px 0;font-weight:500}
      .epg input{box-sizing:border-box;width:100%;padding:10px;margin:8px 0;font:inherit;
        color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color,#bbb);border-radius:6px}
      .epg button{touch-action:manipulation;padding:8px}.epg p{font-size:13px;overflow-wrap:anywhere}
      .epg-results{list-style:none;padding:0;max-height:600px;overflow:auto}.epg-results li{border-top:1px solid var(--divider-color,#bbb);padding-top:12px}
      .epg-nav{display:flex;align-items:center;justify-content:center;gap:12px}.epg-nav button{flex:0 0 44px;font-size:24px}.epg-nav button[hidden]{display:none}.epg-count{font-weight:500;text-align:center}
      .epg-status,.epg-limited{font-size:13px}.epg-status{color:var(--primary-text-color)}
      </style><div class="remote" lang="${this.language}"><h2></h2>${this.remoteRows().map(row => `<div class="row">${row.map(([key,label]) => `<button type="button" data-key="${key}" aria-label="${text.buttons[key] || `${text.key} ${key}`}" title="${text.buttons[key] || `${text.key} ${key}`}">${buttonContent(key, text.labels[key] || label)}</button>`).join("")}</div>`).join("")}<output role="status" aria-live="polite"></output>
      ${showEpg ? `${epgOnly ? '<section class="epg">' : `<details class="epg"><summary>${text.epg.title}</summary>`}<p>${text.epg.hint}</p>
      <form class="epg-form"><label for="epg-query">${text.epg.query}</label><input id="epg-query" type="search" maxlength="200" required autocomplete="off">
      <div class="row"><button type="submit">${text.epg.search}</button><button type="button" class="epg-clear">${text.epg.clear}</button></div></form>
      <p class="epg-status" role="status" aria-live="polite"></p><p class="epg-limited"></p>
      <div class="epg-nav"><button type="button" data-page="previous" aria-label="${text.epg.previous}" title="${text.epg.previous}" hidden>‹</button><span class="epg-count" role="status" aria-live="polite"></span><button type="button" data-page="next" aria-label="${text.epg.next}" title="${text.epg.next}" hidden>›</button></div><ul class="epg-results"></ul>${epgOnly ? "</section>" : "</details>"}` : ""}</div></ha-card>`;
    this.shadowRoot.querySelectorAll("button[data-key]").forEach(button => {
      const key = button.dataset.key;
      button.addEventListener("pointerdown", event => {
        if (event.button !== 0 || !event.isPrimary) return;
        button.setPointerCapture(event.pointerId);
        void this.hold.start(key, REPEAT.has(key));
      });
      for (const name of ["pointerup", "pointercancel", "lostpointercapture"])
        button.addEventListener(name, () => this.hold.stop());
      button.addEventListener("click", event => { if (event.detail === 0) void this.hold.start(key, false); });
    });
    this.shadowRoot.querySelector('[data-page="previous"]')?.addEventListener("click", () => this.epg.movePage(-1));
    this.shadowRoot.querySelector('[data-page="next"]')?.addEventListener("click", () => this.epg.movePage(1));
    this.shadowRoot.querySelector(".epg-clear")?.addEventListener("click", () => this.clearSearch());
    this.shadowRoot.querySelector(".epg-form")?.addEventListener("submit", event => {
      event.preventDefault();
      void this.epgAction("epg_search", this.shadowRoot.querySelector("#epg-query").value);
    });
    this.updateState();
    this.renderEpg();
  }

  getCardSize() { return this.constructor.epgOnly ? 4 : this.remoteRows().length; }
}

export class Enigma2EpgCard extends Enigma2RemoteCard {
  static epgOnly = true;
}

if (!customElements.get("enigma2-connect-epg-card")) customElements.define("enigma2-connect-epg-card", Enigma2EpgCard);
if (!customElements.get("enigma2-connect-remote-card")) customElements.define("enigma2-connect-remote-card", Enigma2RemoteCard);
window.customCards = window.customCards || [];
const cardInfo = {
  type: "enigma2-connect-remote-card",
  get name() { return TEXT[cardLanguage()].cardName; },
  preview: true,
  get description() { return TEXT[cardLanguage()].cardDescription; },
  getEntitySuggestion: (hass, entityId) => isEnigmaRemote(hass, entityId)
    ? {config: {type: "custom:enigma2-connect-remote-card", entity: entityId}}
    : null,
};
const registeredCard = window.customCards.findIndex(card => card.type === cardInfo.type);
if (registeredCard === -1) window.customCards.push(cardInfo);
else window.customCards[registeredCard] = cardInfo;

const epgCardInfo = {
  type: "enigma2-connect-epg-card",
  get name() { return TEXT[cardLanguage()].epgCardName; },
  get description() { return TEXT[cardLanguage()].epgCardDescription; },
  preview: true,
  getEntitySuggestion: (hass, entityId) => isEnigmaRemote(hass, entityId)
    ? {config: {type: "custom:enigma2-connect-epg-card", entity: entityId}} : null,
};
const registeredEpgCard = window.customCards.findIndex(card => card.type === epgCardInfo.type);
if (registeredEpgCard === -1) window.customCards.push(epgCardInfo);
else window.customCards[registeredEpgCard] = epgCardInfo;

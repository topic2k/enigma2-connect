// SPDX-License-Identifier: Apache-2.0
/* Recording library with explicit, guarded management actions. All filters work on the complete loaded catalog. */
const TEXT = {
  de: {
    manage: "Verwalten", action: "Aktion", rename: "Titel ändern", move: "Verschieben", delete: "Löschen",
    newTitle: "Neuer Titel", destination: "Zielordner", execute: "Ausführen", cancel: "Abbrechen", close: "Schließen", dialogTitle: "Aufnahme verwalten", errorTitle: "Aktion nicht ausgeführt", warningTitle: "Abschluss unbestätigt", statusTitle: "Auftragsstatus", check: "Auftragsstatus prüfen",
    deleteQuestion: title => `Aufnahme „${title}“ wirklich löschen?`, deleteButton: "Aufnahme löschen",
    deletion: "Ich bestätige das Löschen. Je nach Receiver-Einstellung kann die Aufnahme endgültig gelöscht werden; ein Papierkorb ist nicht garantiert.",
    pending: "Abschluss noch unbestätigt. Auftragsstatus prüfen; die Aktion nicht erneut ausführen.",
    completed: "Änderung am Receiver bestätigt.", idle: "Kein offener Auftrag.", working: "Auftrag wird geprüft …",
    managementFailed: "Verwaltung fehlgeschlagen. Receiverstatus und aktuelle Aufnahme prüfen.",
    destinationsFailed: "Zielordner konnten nicht geladen werden.",
    display: "Ansicht", details: "Detailansicht", rows: "Zeilenansicht",
    title: "Aufnahmebibliothek", receiver: "Receiver", name: "Titel", load: "Laden / Aktualisieren",
    query: "Titel oder Sender", tag: "Tag", directory: "Ordner", progress: "Wiedergabestand",
    all: "Alle", unknown: "Unbekannt", in_progress: "1–99 % gemeldet", complete: "100 % gemeldet", zero: "0 % gemeldet",
    clear: "Filter zurücksetzen", loading: "Aufnahmen werden geladen …", empty: "Keine passenden Aufnahmen.",
    ready: "Aufnahmen vom Receiver laden.", failed: "Aufnahmebibliothek konnte nicht geladen werden.",
    unavailable: "Enigma2-Connect-Receiver auswählen oder Verbindung prüfen.", count: (n, total) => `${n} von ${total} Aufnahmen`,
    size: "Dateigröße", tags: "Tags", noTags: "Keine Tags", duration: "Dauer", recorded: "Aufnahmedatum",
    channel: "Sender", hint: "Wiedergabestand laut Receiver. 0 % kann auch einen fehlenden Speicherstand bedeuten.",
    config: "Wähle eine media_player-Entität von Enigma2 Connect.", description: "Aufnahmen mit Tags, Ordnern, Dateigröße und gemeldetem Wiedergabestand filtern.",
  },
  en: {
    manage: "Manage", action: "Action", rename: "Change title", move: "Move", delete: "Delete",
    newTitle: "New title", destination: "Destination directory", execute: "Apply", cancel: "Cancel", close: "Close", dialogTitle: "Manage recording", errorTitle: "Action not completed", warningTitle: "Completion unconfirmed", statusTitle: "Operation status", check: "Check operation status",
    deleteQuestion: title => `Delete recording “${title}”?`, deleteButton: "Delete recording",
    deletion: "I confirm deletion. Depending on receiver settings this may permanently delete the recording; a trash folder is not guaranteed.",
    pending: "Completion not yet confirmed. Check operation status; do not repeat the action.",
    completed: "Change confirmed on the receiver.", idle: "No pending operation.", working: "Checking operation …",
    managementFailed: "Management failed. Check receiver state and the current recording.",
    destinationsFailed: "Could not load destination directories.",
    display: "Display", details: "Detail view", rows: "Row view",
    title: "Recording library", receiver: "Receiver", name: "Title", load: "Load / Refresh",
    query: "Title or channel", tag: "Tag", directory: "Directory", progress: "Playback progress",
    all: "All", unknown: "Unknown", in_progress: "1–99% reported", complete: "100% reported", zero: "0% reported",
    clear: "Reset filters", loading: "Loading recordings …", empty: "No matching recordings.",
    ready: "Load recordings from the receiver.", failed: "Could not load the recording library.",
    unavailable: "Select an Enigma2 Connect receiver or check its connection.", count: (n, total) => `${n} of ${total} recordings`,
    size: "File size", tags: "Tags", noTags: "No tags", duration: "Duration", recorded: "Recorded on",
    channel: "Channel", hint: "Progress reported by the receiver. Zero percent may also mean a missing stored position.",
    config: "Select an Enigma2 Connect media_player entity.", description: "Filter recordings by tags, directories, size and reported playback progress.",
  },
};
const lang = hass => String(hass?.language || document.documentElement.lang).toLowerCase().startsWith("de") ? "de" : "en";
const escape = value => String(value).replace(/[&<>"']/g, char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));
export const progressGroup = value => value == null ? "unknown" : value === 0 ? "zero" : value === 100 ? "complete" : "in_progress";

export function filterRecordings(rows, {query = "", tag = "", directory = "", progress = "all"} = {}) {
  const needle = query.trim().toLocaleLowerCase();
  return rows.filter(row => (!needle || [row.title, row.service_name].some(value => (value || "").toLocaleLowerCase().includes(needle)))
    && (!tag || (row.tags || []).includes(tag)) && (!directory || row.directory === directory)
    && (progress === "all" || progressGroup(row.progress_percent) === progress));
}

export class RecordingLibraryController {
  constructor(changed) { this.changed = changed; this.generation = 0; this.reset(); }
  reset() {
    this.generation += 1; this.rows = []; this.tags = []; this.directories = [];
    this.busy = false; this.loaded = false; this.error = false;
  }
  async load(hass, deviceId) {
    if (this.busy) return;
    const generation = ++this.generation;
    this.busy = true; this.error = false; this.rows = []; this.loaded = false;
    this.changed();
    try {
      const result = await hass.callWS({type: "call_service", domain: "enigma2_connect", service: "recordings_list",
        service_data: {device_id: deviceId}, return_response: true});
      if (generation !== this.generation) return;
      const data = result?.response;
      if (!Array.isArray(data?.recordings) || !Array.isArray(data.tags) || !Array.isArray(data.directories)
        || !data.tags.every(value => typeof value === "string") || !data.directories.every(value => typeof value === "string")
        || data.total !== data.recordings.length || data.count !== data.recordings.length
        || !data.recordings.every(row => row && typeof row.service_reference === "string"
          && [row.title, row.service_name, row.directory].every(value => value === null || typeof value === "string")
          && [row.size_bytes, row.recorded_at, row.duration].every(value => value === null || (Number.isSafeInteger(value) && value >= 0))
          && (row.tags === null || (Array.isArray(row.tags) && row.tags.every(value => typeof value === "string")))
          && (row.progress_percent === null || (Number.isInteger(row.progress_percent) && row.progress_percent >= 0 && row.progress_percent <= 100))))
        throw new Error("Invalid recording catalog");
      this.rows = data.recordings; this.tags = data.tags; this.directories = data.directories; this.loaded = true;
    } catch {
      if (generation === this.generation) this.error = true;
    } finally {
      if (generation === this.generation) { this.busy = false; this.changed(); }
    }
  }
}

export class RecordingManagementController {
  constructor(changed) { this.changed = changed; this.generation = 0; this.reset(); }
  reset() { this.generation++; this.busy = false; this.status = ""; this.errorMessage = ""; this.selected = null; this.directories = []; this.directoryError = false; }
  async open(row, hass, deviceId, directories) {
    this.reset(); this.selected = {...row}; this.deviceId = deviceId; this.hass = hass;
    this.directories = [...directories]; this.changed();
    const generation = this.generation;
    try {
      const result = await hass.callWS({type: "call_service", domain: "enigma2_connect", service: "recording_destinations", service_data: {device_id: deviceId}, return_response: true});
      if (generation !== this.generation) return;
      if (!Array.isArray(result?.response?.directories) || !result.response.directories.every(value => typeof value === "string" && value.startsWith("/"))) throw Error("Invalid directories");
      this.directories = [...new Set([...directories, ...result.response.directories])].sort();
    } catch { if (generation === this.generation) this.directoryError = true; }
    if (generation === this.generation) this.changed();
  }
  async run(action, title, directory, confirmed) {
    if (this.busy || this.status === "pending" || !this.selected?.revision || !["rename", "move", "delete"].includes(action)
      || (action === "delete" && !confirmed) || (action === "rename" && !title.trim())
      || (action === "move" && (!this.directories.includes(directory) || directory === this.selected.directory))) return false;
    return this.call(this.hass, this.deviceId, "recording_manage", {service_reference: this.selected.service_reference,
      expected_revision: this.selected.revision, action, ...(action === "rename" ? {title} : action === "move" ? {directory} : {confirm_delete: true})});
  }
  async call(hass, deviceId, service, data = {}) {
    if (this.busy) return false;
    const generation = this.generation; const wasPending = this.status === "pending"; this.errorMessage = ""; this.busy = true; this.status = "working"; this.changed();
    try {
      const result = await hass.callWS({type: "call_service", domain: "enigma2_connect", service, service_data: {device_id: deviceId, ...data}, return_response: true});
      if (generation !== this.generation) return false;
      const status = result?.response?.status;
      if (!["pending", "completed", ...(service === "recording_operation_status" ? ["idle"] : [])].includes(status)) throw Error("Invalid operation reply");
      this.status = status;
      if (status === "completed") this.selected = null;
      return status === "completed";
    } catch (error) {
      if (generation !== this.generation) return false;
      const knownPreflight = error?.translation_domain === "enigma2_connect" && ["recording_path", "recording_destination", "recording_busy", "recording_activity_unknown", "recording_input", "recording_confirm", "recording_stale", "recording_collision", "recording_data"].includes(error.translation_key);
      this.status = wasPending || error?.translation_key === "recording_pending" || (service === "recording_manage" && !knownPreflight) ? "pending" : "managementFailed";
      if (knownPreflight) {
        try {
          const localize = await hass.loadBackendTranslation?.("exceptions", ["enigma2_connect"]);
          if (generation === this.generation) this.errorMessage = localize?.(`component.enigma2_connect.exceptions.${error.translation_key}.message`, {}) || "";
        } catch { /* Keep the localized generic fallback. */ }
      }
      return false;
    }
    finally { if (generation === this.generation) { this.busy = false; this.changed(); } }
  }
}

export function recordingMarkup(row, language, displayMode = "details") {
  const text = TEXT[language];
  const number = new Intl.NumberFormat(language, {maximumFractionDigits: 1});
  const size = row.size_bytes > 0 ? (row.size_bytes >= 1024 ** 3
    ? `${number.format(row.size_bytes / 1024 ** 3)} GiB` : `${number.format(row.size_bytes / 1024 ** 2)} MiB`) : text.unknown;
  const date = row.recorded_at ? new Date(row.recorded_at * 1000) : null;
  const details = [
    [text.channel, row.service_name || text.unknown],
    [text.recorded, date && !Number.isNaN(date.valueOf()) ? date.toLocaleString(language) : text.unknown],
    [text.duration, row.duration == null ? text.unknown : `${number.format(row.duration / 60)} min`],
    [text.size, size], [text.tags, row.tags === null ? text.unknown : row.tags.join(", ") || text.noTags],
    [text.directory, row.directory || text.unknown],
    [text.progress, row.progress_percent == null ? text.unknown : `${row.progress_percent} %`],
  ];
  const title = escape(row.title || text.unknown);
  const controls = row.revision ? `<button type="button" class="manage" data-reference="${escape(row.service_reference)}">${text.manage}</button>` : "";
  const metadata = `<dl>${details.map(([key, value]) => `<dt>${escape(key)}</dt><dd>${escape(value)}</dd>`).join("")}</dl>`;
  if (displayMode === "rows") {
    const recorded = date && !Number.isNaN(date.valueOf()) ? date.toLocaleString(language, {year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}) : text.unknown;
    const fields = [
      ["duration", text.duration, row.duration == null ? text.unknown : `${number.format(row.duration / 60)} min`],
      ["date", text.recorded, recorded], ["channel", text.channel, row.service_name || text.unknown],
      ["progress", text.progress, row.progress_percent == null ? text.unknown : `${row.progress_percent} %`],
      ["size", text.size, size],
    ];
    const columns = fields.map(([key, label, value]) => `<span class="row-${key}" title="${escape(label)}" aria-label="${escape(`${label}: ${value}`)}">${escape(value)}</span>`).join("");
    return `<li class="recording-row"><details><summary><span class="row-title">${title}</span>${columns}</summary>${metadata}${controls}</details></li>`;
  }
  return `<li><h3>${title}</h3>${metadata}${controls}</li>`;
}

export class Enigma2RecordingsCard extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode: "open"}); this.library = new RecordingLibraryController(() => this.update());
    this.management = new RecordingManagementController(() => this.updateManagement());
    this.filters = {}; this.language = "en";
  }
  static getStubConfig(hass) {
    return {entity: Object.keys(hass.entities || {}).find(id => id.startsWith("media_player.") && hass.entities[id].platform === "enigma2_connect") || ""};
  }
  static getConfigForm() {
    const text = TEXT[lang()];
    return {schema: [
      {name: "entity", required: true, selector: {entity: {filter: {domain: "media_player", integration: "enigma2_connect"}}}},
      {name: "name", selector: {text: {}}},
      {name: "display_mode", default: "details", selector: {select: {mode: "dropdown", options: [
        {value: "details", label: text.details}, {value: "rows", label: text.rows},
      ]}}},
    ], computeLabel: schema => ({entity: text.receiver, name: text.name, display_mode: text.display})[schema.name]};
  }
  setConfig(config) {
    if (config.entity && !config.entity.startsWith("media_player.")) throw new Error(TEXT[lang()].config);
    this.config = {...config, display_mode: config.display_mode === "rows" ? "rows" : "details"}; this.closeManagement(true); this.identity = undefined; this.library.reset(); this.management.reset(); this.filters = {}; this.render();
  }
  set hass(hass) {
    this._hass = hass;
    const entity = hass.entities?.[this.config?.entity];
    const state = hass.states?.[this.config?.entity]?.state;
    const identity = entity?.platform === "enigma2_connect" && state && !["unavailable", "unknown"].includes(state) ? entity.device_id : undefined;
    if (identity !== this.identity) { this.closeManagement(true); this.identity = identity; this.library.reset(); this.management.reset(); this.filters = {}; }
    const language = lang(hass);
    if (language !== this.language || !this.shadowRoot.querySelector(".load")) { this.language = language; this.render(); }
    else this.update();
  }
  disconnectedCallback() { this.closeManagement(true); this.library.reset(); this.management.reset(); }
  connectedCallback() { if (this.config) this.update(); }
  render() {
    this.closeManagement(true);
    this.recordingsMarkup = undefined;
    const text = TEXT[this.language];
    this.shadowRoot.innerHTML = `<ha-card><style>
      :host{display:block}section{padding:16px}h2{font-size:20px;margin:0 0 12px}h3{font-size:16px;margin:0 0 8px}
      .filters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.query{grid-column:1/-1}
      label{display:flex;flex-direction:column;gap:4px}input,select,button{font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color,#aaa);border-radius:8px;min-height:44px;box-sizing:border-box;max-width:100%}
      input,select{width:100%;padding:8px}button{padding:8px 12px;cursor:pointer}button:disabled{opacity:.5;cursor:default}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--primary-color)}
      .actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}p{font-size:14px}ul{padding:0 12px 0 0;list-style:none;max-height:650px;overflow:auto;scrollbar-gutter:stable;container:recording-list / inline-size;font-size:14px}li{border-top:1px solid var(--divider-color,#aaa);padding:14px 0;overflow-wrap:anywhere}
      dl{display:grid;grid-template-columns:minmax(90px,auto) minmax(0,1fr);gap:4px 12px;font-size:14px;margin:0}dt{color:var(--secondary-text-color)}dd{margin:0}
      .recording-row{padding:0}.recording-row summary{display:flex;align-items:center;gap:10px;min-height:44px;padding:10px 0;cursor:pointer;list-style:none;font-size:14px}
      .recording-row summary::-webkit-details-marker{display:none}.recording-row summary::before{content:"›";flex:0 0 12px;font-size:22px;text-align:center}
      .recording-row details[open]>summary::before{content:"⌄"}.recording-row summary:focus-visible{outline:2px solid var(--primary-color);outline-offset:-2px;border-radius:4px}
      .row-title{flex:1;min-width:0;font-weight:500}
      .row-duration,.row-date,.row-channel,.row-progress,.row-size{display:none;min-width:0;font-size:12px;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
      .row-date{flex:0 0 9em}.row-channel{flex:0 0 8em}.row-duration,.row-progress,.row-size{flex:0 0 6em;text-align:right}
      /* Available list width, including scrollbar spacing, determines visibility.
         Keep room for the title; add date, channel, duration, progress, then size.
         CSS changes visibility only, preserving open details and keyboard focus. */
      @container recording-list (min-width:22em){.recording-row summary>.row-date{display:block}}
      @container recording-list (min-width:30em){.recording-row summary>.row-channel{display:block}}
      @container recording-list (min-width:36em){.recording-row summary>.row-duration{display:block}}
      @container recording-list (min-width:42em){.recording-row summary>.row-progress{display:block}}
      @container recording-list (min-width:48em){.recording-row summary>.row-size{display:block}}
      .recording-row dl{padding:4px 0 14px 22px}.manage{margin:0 0 12px 22px}.management{margin:12px 0}.management label{margin:8px 0}.confirm-label{display:block}.confirm-delete{width:auto;min-height:auto;margin-right:8px}[hidden]{display:none!important}
      dialog{box-sizing:border-box;width:min(560px,calc(100vw - 24px));max-height:calc(100dvh - 32px);overflow:auto;padding:20px;border:1px solid var(--divider-color,#aaa);border-radius:14px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#212121);box-shadow:0 16px 60px #0006}
      dialog::backdrop{background:#0009}dialog header{display:flex;align-items:center;justify-content:space-between;gap:16px}dialog h2{margin:0}dialog h3{overflow-wrap:anywhere}dialog .dialog-close{flex:none}dialog .dialog-footer{display:flex;justify-content:flex-end;margin-top:16px}
      .notice{border:2px solid var(--primary-color,#03a9f4);border-left-width:6px;border-radius:8px;padding:12px;margin:14px 0;overflow-wrap:anywhere;background:var(--card-background-color,#fff);color:var(--primary-text-color,#212121)}
      .notice[data-kind="error"]{border-color:var(--error-color,#db4437);background:color-mix(in srgb,var(--error-color,#db4437) 12%,var(--card-background-color,#fff))}
      .notice[data-kind="warning"]{border-color:var(--warning-color,#ff9800);background:color-mix(in srgb,var(--warning-color,#ff9800) 12%,var(--card-background-color,#fff))}
      .notice p{margin:8px 0 0}.notice strong{font-size:16px}.notice:focus{outline:2px solid var(--primary-text-color,#212121);outline-offset:2px}.status[data-kind="error"]{font-weight:600}
      @media(max-width:360px){.filters{grid-template-columns:1fr}dl{grid-template-columns:1fr}dd{margin-bottom:5px}}
      </style><section lang="${this.language}"><h2></h2><p>${text.hint}</p><div class="filters">
      <label class="query">${text.query}<input class="search" type="search" maxlength="200"></label>
      <label>${text.tag}<select class="tag"></select></label><label>${text.directory}<select class="directory"></select></label>
      <label>${text.progress}<select class="progress">${["all", "in_progress", "complete", "zero", "unknown"].map(key => `<option value="${key}">${text[key]}</option>`).join("")}</select></label></div>
      <div class="actions"><button class="load" type="button">${text.load}</button><button class="clear" type="button">${text.clear}</button></div>
      <button class="check-operation" type="button">${text.check}</button>
      <div class="management-banner notice" hidden><strong class="banner-title"></strong><p class="banner-message"></p></div>
      <p class="status" role="status" aria-live="polite"></p><ul aria-label="${text.title}"></ul>
      <dialog class="management-dialog" aria-labelledby="management-heading" lang="${this.language}">
      <header><h2 id="management-heading">${text.dialogTitle}</h2><button class="dialog-close" type="button" aria-label="${text.close}">✕</button></header>
      <div class="management-notice notice" tabindex="-1" role="status" aria-live="polite" aria-atomic="true" hidden><strong class="notice-title"></strong><p class="management-status"></p></div>
      <button class="dialog-check" type="button" hidden>${text.check}</button>
      <div class="management" hidden><h3 class="selected-title"></h3>
      <label>${text.action}<select class="management-action">${["rename", "move", "delete"].map(key => `<option value="${key}">${text[key]}</option>`).join("")}</select></label>
      <label class="rename-label">${text.newTitle}<input class="new-title" maxlength="200"></label>
      <label class="move-label">${text.destination}<select class="move-directory"></select></label>
      <p class="delete-question"></p><label class="confirm-label"><input class="confirm-delete" type="checkbox">${text.deletion}</label>
      <p class="directory-error notice" role="alert" hidden></p><div class="actions"><button class="execute" type="button">${text.execute}</button></div></div>
      <div class="dialog-footer"><button class="cancel-management" type="button">${text.cancel}</button></div></dialog>
      </section></ha-card>`;
    this.shadowRoot.querySelector(".load").addEventListener("click", () => { if (this.identity) void this.library.load(this._hass, this.identity); });
    this.shadowRoot.querySelector(".clear").addEventListener("click", () => { this.filters = {}; this.update(); });
    for (const [field, selector] of [["query", ".search"], ["tag", ".tag"], ["directory", ".directory"], ["progress", ".progress"]]) {
      this.shadowRoot.querySelector(selector).addEventListener(field === "query" ? "input" : "change", event => {
        this.filters[field] = event.target.value; this.update();
      });
    }
    const root = this.shadowRoot;
    root.querySelector("ul").addEventListener("click", event => {
      const ref = event.target.closest?.(".manage")?.dataset.reference;
      const row = this.library.rows.find(item => item.service_reference === ref);
      if (!row || !this.identity || this.management.busy || this.management.status === "pending") return;
      root.querySelector(".management-action").value = "rename";
      root.querySelector(".new-title").value = row.title || "";
      root.querySelector(".confirm-delete").checked = false;
      void this.management.open(row, this._hass, this.identity, this.library.directories);
      this.openManagement(event.target.closest(".manage"));
    });
    for (const selector of [".management-action", ".new-title", ".move-directory", ".confirm-delete"]) {
      root.querySelector(selector).addEventListener("input", () => this.updateManagement());
      root.querySelector(selector).addEventListener("change", () => {
        if (selector === ".management-action") root.querySelector(".confirm-delete").checked = false;
        this.updateManagement();
      });
    }
    for (const selector of [".cancel-management", ".dialog-close"]) root.querySelector(selector).addEventListener("click", () => this.closeManagement());
    root.querySelector(".management-dialog").addEventListener("cancel", event => {
      event.preventDefault(); this.closeManagement();
    });
    root.querySelector(".execute").addEventListener("click", async () => {
      const completed = await this.management.run(root.querySelector(".management-action").value,
        root.querySelector(".new-title").value, root.querySelector(".move-directory").value,
        root.querySelector(".confirm-delete").checked);
      if (completed && this.identity) await this.library.load(this._hass, this.identity);
    });
    for (const selector of [".check-operation", ".dialog-check"]) root.querySelector(selector).addEventListener("click", async event => {
      if (!this.identity || this.management.busy) return;
      this.openManagement(event.currentTarget);
      const completed = await this.management.call(this._hass, this.identity, "recording_operation_status");
      if (completed && this.identity) await this.library.load(this._hass, this.identity);
    });
    this.update();
  }
  openManagement(trigger) {
    const dialog = this.shadowRoot.querySelector(".management-dialog");
    if (dialog.open) return;
    this.managementTrigger = trigger; this.lastNotice = undefined;
    dialog.showModal(); this.updateManagement();
    if (!this.management.status) this.shadowRoot.querySelector(".management-action").focus();
  }
  closeManagement(force = false) {
    if (this.management.busy && !force) return;
    const dialog = this.shadowRoot.querySelector(".management-dialog");
    if (!dialog?.open) return;
    dialog.close(); this.management.selected = null;
    if (!force) {
      const target = this.managementTrigger?.isConnected ? this.managementTrigger : this.shadowRoot.querySelector(".check-operation");
      target?.focus(); this.updateManagement();
    }
    this.managementTrigger = undefined;
  }
  updateManagement() {
    const root = this.shadowRoot; if (!root.querySelector(".management")) return;
    const state = this.management; const text = TEXT[this.language];
    root.querySelector(".management").hidden = !state.selected;
    root.querySelector(".selected-title").textContent = state.selected?.title || "";
    const message = state.errorMessage || text[state.status] || "";
    const kind = state.status === "pending" ? "warning" : state.status === "managementFailed" ? "error" : "info";
    const heading = kind === "error" ? `⚠ ${text.errorTitle}` : kind === "warning" ? `⚠ ${text.warningTitle}` : text.statusTitle;
    const notice = root.querySelector(".management-notice"); const banner = root.querySelector(".management-banner");
    const dialog = root.querySelector(".management-dialog");
    notice.hidden = !message; banner.hidden = !message || dialog.open;
    for (const node of [notice, banner]) node.dataset.kind = kind;
    notice.setAttribute("role", kind === "info" ? "status" : "alert");
    notice.setAttribute("aria-live", kind === "info" ? "polite" : "assertive");
    banner.setAttribute("role", dialog.open ? "none" : kind === "info" ? "status" : "alert");
    root.querySelector(".notice-title").textContent = heading;
    root.querySelector(".banner-title").textContent = heading;
    root.querySelector(".banner-message").textContent = message;
    root.querySelector(".management-status").textContent = message;
    if (dialog.open && !state.busy && message && this.lastNotice !== `${state.status}:${message}`) {
      notice.focus(); notice.scrollIntoView({block: "nearest"});
    }
    this.lastNotice = `${state.status}:${message}`;
    root.querySelector(".dialog-check").hidden = state.status !== "pending";
    root.querySelector(".dialog-check").disabled = !this.identity || state.busy;
    root.querySelector(".check-operation").disabled = !this.identity || state.busy;
    const action = root.querySelector(".management-action").value;
    root.querySelector(".rename-label").hidden = action !== "rename";
    root.querySelector(".move-label").hidden = action !== "move";
    root.querySelector(".confirm-label").hidden = action !== "delete";
    root.querySelector(".delete-question").hidden = action !== "delete";
    root.querySelector(".delete-question").textContent = text.deleteQuestion(state.selected?.title || text.unknown);
    root.querySelector(".execute").textContent = action === "delete" ? text.deleteButton : text.execute;
    const select = root.querySelector(".move-directory");
    const options = state.directories.filter(value => value !== state.selected?.directory).map(value => `<option value="${escape(value)}">${escape(value)}</option>`).join("");
    if (select.innerHTML !== options) select.innerHTML = options;
    root.querySelector(".directory-error").textContent = text.destinationsFailed;
    root.querySelector(".directory-error").hidden = action !== "move" || !state.directoryError;
    root.querySelector(".directory-error").dataset.kind = "error";
    for (const selector of [".management-action", ".new-title", ".move-directory", ".confirm-delete"]) root.querySelector(selector).disabled = state.busy || state.status === "pending";
    root.querySelector(".execute").disabled = !this.identity || state.busy || state.status === "pending" || !state.selected?.revision
      || (action === "rename" && !root.querySelector(".new-title").value.trim())
      || (action === "move" && !select.value) || (action === "delete" && !root.querySelector(".confirm-delete").checked);
    root.querySelector(".cancel-management").disabled = state.busy;
    root.querySelector(".dialog-close").disabled = state.busy;
    root.querySelector(".cancel-management").textContent = state.status ? text.close : text.cancel;
  }
  update() {
    if (!this.shadowRoot.querySelector(".load")) return;
    this.updateManagement();
    const text = TEXT[this.language]; const root = this.shadowRoot;
    root.querySelector("h2").textContent = this.config?.name || text.title;
    root.querySelector(".load").disabled = !this.identity || this.library.busy;
    root.querySelector(".search").value = this.filters.query || "";
    root.querySelector(".progress").value = this.filters.progress || "all";
    for (const [key, values] of [["tag", this.library.tags], ["directory", this.library.directories]]) {
      const node = root.querySelector(`.${key}`);
      const options = `<option value="">${text.all}</option>` + values.map(value => `<option value="${escape(value)}">${escape(value)}</option>`).join("");
      if (node.innerHTML !== options) node.innerHTML = options;
      // Refresh may remove a previously selected tag or directory.
      if (!values.includes(this.filters[key])) this.filters[key] = "";
      node.value = this.filters[key] || "";
    }
    const rows = filterRecordings(this.library.rows, this.filters);
    root.querySelector(".status").textContent = !this.identity ? text.unavailable : this.library.busy ? text.loading
      : this.library.error ? text.failed : this.library.loaded ? `${text.count(rows.length, this.library.rows.length)}${rows.length ? "" : ` · ${text.empty}`}` : text.ready;
    root.querySelector(".status").className = this.library.error ? "status notice" : "status";
    root.querySelector(".status").dataset.kind = this.library.error ? "error" : "info";
    root.querySelector(".status").setAttribute("role", this.library.error ? "alert" : "status");
    root.querySelector(".status").setAttribute("aria-live", this.library.error ? "assertive" : "polite");
    const markup = rows.map(row => recordingMarkup(row, this.language, this.config?.display_mode)).join("");
    // Compare rendered data, not live HTML: native details adds an open attribute.
    if (this.recordingsMarkup !== markup) {
      root.querySelector("ul").innerHTML = markup; this.recordingsMarkup = markup;
    }
  }
  getCardSize() { return 6; }
}
if (!customElements.get("enigma2-connect-recordings-card")) customElements.define("enigma2-connect-recordings-card", Enigma2RecordingsCard);
window.customCards = window.customCards || [];
const info = {type: "enigma2-connect-recordings-card", preview: true,
  get name() { return `Enigma2 Connect ${TEXT[lang()].title}`; }, get description() { return TEXT[lang()].description; }};
const index = window.customCards.findIndex(card => card.type === info.type);
if (index < 0) window.customCards.push(info); else window.customCards[index] = info;

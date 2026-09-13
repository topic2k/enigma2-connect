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
  static getStubConfig(hass, entities = [], fallbackEntities = []) {
    const candidates = [...entities, ...fallbackEntities, ...Object.keys(hass?.entities || {})];
    return {entity: candidates.find(entityId => isEnigmaRemote(hass, entityId)) || ""};
  }

  static getConfigForm() {
    return {
      schema: [
        {name: "entity", required: true, selector: {entity: {filter: {domain: "remote", integration: "enigma2_connect"}}}},
        {name: "name", selector: {text: {}}},
      ],
    };
  }

  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.hold = new HoldController((key) => this.send(key));
    this.onBlur = () => this.hold.stop();
    this.onVisibility = () => { if (document.hidden) this.hold.stop(); };
  }

  setConfig(config) {
    if (config.entity && (typeof config.entity !== "string" || !config.entity.startsWith("remote."))) {
      throw new Error("Configure an Enigma2 Connect remote entity using 'entity: remote.…'.");
    }
    this.hold.stop();
    this.config = {...config};
    this.render();
  }

  connectedCallback() {
    window.addEventListener("blur", this.onBlur);
    document.addEventListener("visibilitychange", this.onVisibility);
  }

  disconnectedCallback() {
    this.hold.stop();
    window.removeEventListener("blur", this.onBlur);
    document.removeEventListener("visibilitychange", this.onVisibility);
  }

  set hass(value) {
    this._hass = value;
    this.updateState();
  }

  updateState() {
    if (!this.config || !this.shadowRoot.querySelector("h2")) return;
    const state = this._hass?.states[this.config.entity];
    this.available = Boolean(state && !["unavailable", "unknown"].includes(state.state));
    this.shadowRoot.querySelector("h2").textContent = this.config.name || state?.attributes.friendly_name || "Enigma2 Connect";
    this.shadowRoot.querySelectorAll("button").forEach((button) => {button.disabled = !this.available;});
    if (!this.config.entity) {
      this.shadowRoot.querySelector("output").textContent = this._hass?.language?.startsWith("de")
        ? "Bitte die Receiver-Steuerung im Karteneditor auswählen."
        : "Select the receiver control in the card editor.";
    }
    if (!this.available) this.hold.stop();
  }

  async send(key) {
    if (!this.available || this.pending) return false;
    this.pending = true;
    try {
      await this._hass.callService("remote", "send_command", {entity_id: this.config.entity, command: [key]});
      this.shadowRoot.querySelector("output").textContent = "";
      return true;
    } catch (error) {
      this.shadowRoot.querySelector("output").textContent = error.message || String(error);
      return false;
    } finally {
      this.pending = false;
    }
  }

  render() {
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
      </style><div class="remote"><h2></h2>${ROWS.map(row => `<div class="row">${row.map(([key,label]) => `<button type="button" data-key="${key}" aria-label="${key.replaceAll("_", " ")}">${buttonContent(key, label)}</button>`).join("")}</div>`).join("")}<output role="status" aria-live="polite"></output></div></ha-card>`;
    this.shadowRoot.querySelectorAll("button").forEach(button => {
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
    this.updateState();
  }

  getCardSize() { return 10; }
}

if (!customElements.get("enigma2-connect-remote-card")) customElements.define("enigma2-connect-remote-card", Enigma2RemoteCard);
window.customCards = window.customCards || [];
const cardInfo = {
  type: "enigma2-connect-remote-card",
  name: "Enigma2 Connect Fernbedienung",
  preview: true,
  description: "Enigma2 / OpenWebif remote: Receiver und Titel im grafischen Editor auswählen.",
  getEntitySuggestion: (hass, entityId) => isEnigmaRemote(hass, entityId)
    ? {config: {type: "custom:enigma2-connect-remote-card", entity: entityId}}
    : null,
};
const registeredCard = window.customCards.findIndex(card => card.type === cardInfo.type);
if (registeredCard === -1) window.customCards.push(cardInfo);
else window.customCards[registeredCard] = cardInfo;

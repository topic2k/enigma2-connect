// SPDX-License-Identifier: Apache-2.0
const {test, before} = require('node:test');
const assert = require('node:assert/strict');
let HoldController, Enigma2RemoteCard, cardLanguage;
const registeredElements = new Map();
before(async () => {
  global.HTMLElement = class {
    attachShadow() {
      const nodes = {h2: {textContent: ''}, output: {textContent: ''}};
      this.shadowRoot = {
        innerHTML: '',
        querySelector(selector) { return nodes[selector]; },
        querySelectorAll() { return []; },
      };
    }
  };
  global.customElements = {
    get(name) { return registeredElements.get(name); },
    define(name, element) { registeredElements.set(name, element); },
  };
  global.window = {};
  global.document = {documentElement: {lang: 'en'}};
  ({HoldController, Enigma2RemoteCard, cardLanguage} = await import('../www/enigma2-connect-remote-card.js'));
});

test('Connect card is registered and its picker suggestion resolves to that element', () => {
  const hass = {entities: {'remote.receiver': {platform: 'enigma2_connect'}}};
  const info = window.customCards.find(card => card.type === 'enigma2-connect-remote-card');
  assert.equal(info.name, 'Enigma2 Connect remote control');
  const suggestion = info.getEntitySuggestion(hass, 'remote.receiver');
  assert.deepEqual(suggestion, {
    config: {type: 'custom:enigma2-connect-remote-card', entity: 'remote.receiver'},
  });
  assert.equal(registeredElements.get(suggestion.config.type.replace('custom:', '')), Enigma2RemoteCard);
});

test('Connect receiver discovery and editor filter use the new integration domain', () => {
  const hass = {entities: {
    'remote.other': {platform: 'other_integration'},
    'sensor.receiver': {platform: 'enigma2_connect'},
    'remote.receiver': {platform: 'enigma2_connect'},
  }};
  assert.deepEqual(Enigma2RemoteCard.getStubConfig(hass), {entity: 'remote.receiver'});
  const field = Enigma2RemoteCard.getConfigForm().schema.find(item => item.name === 'entity');
  assert.deepEqual(field.selector.entity.filter, {domain: 'remote', integration: 'enigma2_connect'});
});

function timers() {
  const pending = new Map(); let id = 0;
  return {pending, setTimeout(fn) {pending.set(++id, fn); return id;}, clearTimeout(id) {pending.delete(id);}};
}

test('release while request is in flight cannot restart repetition', async () => {
  const clock = timers(); let resolve;
  const hold = new HoldController(() => new Promise(done => {resolve = done;}), clock);
  const promise = hold.start('up', true);
  hold.stop(); resolve(true); await promise;
  assert.equal(clock.pending.size, 0);
});

test('failed request stops the repeat chain', async () => {
  const clock = timers();
  const hold = new HoldController(async () => false, clock);
  await hold.start('up', true);
  assert.equal(clock.pending.size, 0);
});

test('non-repeat key sends once; stopping repeat clears the timeout', async () => {
  const clock = timers(); const calls = [];
  const hold = new HoldController(async key => {calls.push(key); return true;}, clock);
  await hold.start('power', false);
  assert.deepEqual(calls, ['power']); assert.equal(clock.pending.size, 0);
  await hold.start('up', true); assert.equal(clock.pending.size, 1);
  hold.stop(); assert.equal(clock.pending.size, 0);
});

test('remote labels and accessibility follow profile language without changing commands', async () => {
  const card = new Enigma2RemoteCard();
  card.setConfig({entity: 'remote.receiver', name: '<My receiver>'});
  const calls = [];
  const hass = {
    language: 'de-DE', states: {'remote.receiver': {state: 'on', attributes: {}}},
    async callService(...args) { calls.push(args); },
  };
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /aria-label="Nach oben"/);
  assert.match(card.shadowRoot.innerHTML, />Grün<\/button>/);
  assert.match(card.shadowRoot.innerHTML, /aria-label="Taste 1"/);
  assert.equal(card.shadowRoot.querySelector('h2').textContent, '<My receiver>');
  assert.ok(!card.shadowRoot.innerHTML.includes('<My receiver>'));
  const clock = timers();
  card.hold.timers = clock;
  await card.hold.start('up', true);
  assert.equal(clock.pending.size, 1);
  card.hass = {...hass, language: 'en-GB'};
  assert.equal(clock.pending.size, 0);
  assert.match(card.shadowRoot.innerHTML, /aria-label="Up"/);
  assert.match(card.shadowRoot.innerHTML, />Green<\/button>/);
  assert.match(card.shadowRoot.innerHTML, /aria-label="Key 1"/);
  assert.deepEqual(calls, [['remote', 'send_command', {entity_id: 'remote.receiver', command: ['up']}] ]);
});

test('missing receiver, unavailable state and picker metadata are bilingual', () => {
  const card = new Enigma2RemoteCard();
  card.hass = {language: 'de', states: {}};
  card.setConfig({});
  assert.match(card.shadowRoot.querySelector('output').textContent, /Bitte/);
  assert.throws(() => card.setConfig({entity: 'sensor.receiver'}), /Fernbedienung/);
  card.setConfig({entity: 'remote.receiver'});
  assert.equal(card.shadowRoot.querySelector('output').textContent, 'Receiver nicht verfügbar.');
  card.hass = {language: 'en', states: {}};
  assert.equal(card.shadowRoot.querySelector('output').textContent, 'Receiver unavailable.');
  card.hass = {language: 'en', states: {'remote.receiver': {state: 'on', attributes: {}}}};
  assert.equal(card.shadowRoot.querySelector('output').textContent, '');
  const info = window.customCards[0];
  document.documentElement.lang = 'de';
  assert.equal(info.name, 'Enigma2 Connect Fernbedienung');
  document.documentElement.lang = 'en';
  assert.equal(info.name, 'Enigma2 Connect remote control');
  assert.equal(cardLanguage('de-AT'), 'de');
  assert.equal(cardLanguage('en-US'), 'en');
  assert.equal(cardLanguage('fr'), 'en');
});

test('action errors use HA translation metadata and preserve a fallback', async () => {
  const card = new Enigma2RemoteCard();
  card.setConfig({entity: 'remote.receiver'});
  const failure = {
    message: 'Unknown remote key: nope', translation_domain: 'enigma2_connect',
    translation_key: 'unknown_remote_key', translation_placeholders: {key: 'nope'},
  };
  card.hass = {
    language: 'de', states: {'remote.receiver': {state: 'on', attributes: {}}},
    async callService() { throw failure; },
    async loadBackendTranslation(category, integrations) {
      assert.equal(category, 'exceptions');
      assert.deepEqual(integrations, ['enigma2_connect']);
      return (key, placeholders) => {
        assert.equal(key, 'component.enigma2_connect.exceptions.unknown_remote_key.message');
        return `Unbekannte Fernbedienungstaste: ${placeholders.key}`;
      };
    },
  };
  assert.equal(await card.send('up'), false);
  assert.equal(card.shadowRoot.querySelector('output').textContent, 'Unbekannte Fernbedienungstaste: nope');
  card._hass.loadBackendTranslation = async () => { throw new Error('Offline'); };
  assert.equal(await card.send('up'), false);
  assert.equal(card.shadowRoot.querySelector('output').textContent, failure.message);
});

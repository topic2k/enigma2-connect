// SPDX-License-Identifier: Apache-2.0
const {test, before} = require('node:test');
const assert = require('node:assert/strict');
let HoldController, Enigma2RemoteCard;
const registeredElements = new Map();
before(async () => {
  global.HTMLElement = class {};
  global.customElements = {
    get(name) { return registeredElements.get(name); },
    define(name, element) { registeredElements.set(name, element); },
  };
  global.window = {};
  ({HoldController, Enigma2RemoteCard} = await import('../www/enigma2-connect-remote-card.js'));
});

test('Connect card is registered and its picker suggestion resolves to that element', () => {
  const hass = {entities: {'remote.receiver': {platform: 'enigma2_connect'}}};
  const info = window.customCards.find(card => card.type === 'enigma2-connect-remote-card');
  assert.equal(info.name, 'Enigma2 Connect Fernbedienung');
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

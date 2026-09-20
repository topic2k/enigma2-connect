// SPDX-License-Identifier: Apache-2.0
const {test, before} = require('node:test');
const assert = require('node:assert/strict');
let RecordingLibraryController, filterRecordings, recordingMarkup, Enigma2RecordingsCard;
before(async () => {
  global.HTMLElement = class {
    attachShadow() {
      const nodes = new Map();
      this.shadowRoot = {innerHTML: '', querySelector(selector) {
        if (!this.innerHTML) return null;
        if (!nodes.has(selector)) nodes.set(selector, {innerHTML: '', textContent: '', value: '', listeners: {},
          addEventListener(name, callback) { this.listeners[name] = callback; }});
        return nodes.get(selector);
      }};
    }
  };
  const elements = new Map();
  global.customElements = {get: key => elements.get(key), define: (key, value) => elements.set(key, value)};
  global.window = {}; global.document = {documentElement: {lang: 'en'}};
  ({RecordingLibraryController, filterRecordings, recordingMarkup, Enigma2RecordingsCard} = await import('../www/enigma2-connect-recordings-card.js'));
});
const row = {service_reference: 'opaque', title: 'A & B', service_name: 'News HD', tags: ['Film'], directory: '/media/movie',
  recorded_at: 1789000000, duration: 90, size_bytes: 2**30, progress_percent: 43};
const response = (rows = [row]) => ({response: {recordings: rows, tags: ['Film'], directories: ['/media/movie'], count: rows.length, total: rows.length}});
const hass = () => ({language: 'de', states: {'media_player.receiver': {state: 'idle'}}, entities: {
  'media_player.receiver': {device_id: 'receiver1', platform: 'enigma2_connect'},
}, callWS: async () => response()});

test('unlimited catalog, receiver targeting and no implicit writes', async () => {
  const rows = Array.from({length: 153}, (_, i) => ({...row, service_reference: `movie${i}`}));
  const calls = []; const controller = new RecordingLibraryController(() => {});
  await controller.load({callWS: async args => { calls.push(args); return response(rows); }}, 'receiver1');
  assert.equal(controller.rows.length, 153); assert.equal(controller.loaded, true);
  assert.deepEqual(calls, [{type: 'call_service', domain: 'enigma2_connect', service: 'recordings_list', service_data: {device_id: 'receiver1'}, return_response: true}]);
});
test('stale responses after receiver switch do not replace new results', async () => {
  let finish;
  const controller = new RecordingLibraryController(() => {});
  const pending = controller.load({callWS: () => new Promise(resolve => {finish = resolve;})}, 'old');
  controller.reset();
  await controller.load({callWS: async () => response([{...row, title: 'New'}])}, 'new');
  finish(response()); await pending;
  assert.equal(controller.rows[0].title, 'New'); assert.equal(controller.busy, false);
});
test('stale failure and duplicate clicks cannot replace current status', async () => {
  let fail; const controller = new RecordingLibraryController(() => {});
  const pending = controller.load({callWS: () => new Promise((resolve, reject) => {fail = reject;})}, 'old');
  await controller.load({callWS: () => {throw new Error('must not run');}}, 'old');
  controller.reset(); fail(new Error('offline')); await pending;
  assert.equal(controller.error, false); assert.equal(controller.loaded, false);
});
for (const data of [undefined, {response: {}}, response([{...row, progress_percent: 101}]), response([{...row, tags: 5}]),
  response([{...row, size_bytes: -3}]), {response: {...response().response, total: 2}}]) {
  test('invalid catalog never looks like a successful empty catalog', async () => {
    const controller = new RecordingLibraryController(() => {});
    await controller.load({callWS: async () => data}, 'device');
    assert.equal(controller.error, true); assert.equal(controller.loaded, false); assert.deepEqual(controller.rows, []);
  });
}
test('refresh failure discards old rows', async () => {
  const controller = new RecordingLibraryController(() => {});
  await controller.load({callWS: async () => response()}, 'device');
  await controller.load({callWS: async () => {throw new Error('Offline');}}, 'device');
  assert.equal(controller.error, true); assert.deepEqual(controller.rows, []);
});
test('combined text tag folder and progress filters; no false unwatched claim', () => {
  const rows = [row, {...row, title: 'Zero', progress_percent: 0, tags: null}, {...row, title: 'Unknown', progress_percent: null}, {...row, progress_percent: 100}];
  assert.equal(filterRecordings(rows, {query: ' NEWS hd ', tag: 'Film', directory: '/media/movie', progress: 'in_progress'}).length, 1);
  assert.equal(filterRecordings(rows, {tag: 'film'}).length, 0);
  assert.equal(filterRecordings(rows, {directory: '/media'}).length, 0);
  assert.equal(filterRecordings(rows, {progress: 'complete'}).length, 1);
  assert.equal(filterRecordings(rows, {progress: 'zero'})[0].title, 'Zero');
  assert.equal(filterRecordings(rows, {progress: 'unknown'})[0].title, 'Unknown');
  assert.equal(filterRecordings(rows, {query: 'missing'}).length, 0);
});
test('receiver strings are escaped and missing data stays unknown', () => {
  const markup = recordingMarkup({...row, title: '<img src=x onerror="alert(1)">', directory: '<script>', tags: ['<b>']}, 'de');
  assert.ok(!markup.includes('<img')); assert.ok(!markup.includes('<script>')); assert.ok(!markup.includes('<b>'));
  assert.match(markup, /&lt;img/); assert.match(markup, /1 GiB/); assert.match(markup, /43 %/);
  const unknown = recordingMarkup({...row, recorded_at: null, size_bytes: null, duration: null, tags: null, progress_percent: null}, 'de');
  assert.match(unknown, /Unbekannt/); assert.ok(!unknown.includes('0 %'));
  assert.match(recordingMarkup({...row, tags: [], size_bytes: 1024**2}, 'en'), /No tags/);
  assert.match(recordingMarkup({...row, size_bytes: 1024**2}, 'en'), /1 MiB/);
});
test('card picker and editor only offer Enigma2 media players', () => {
  assert.equal(Enigma2RecordingsCard.getStubConfig(hass()).entity, 'media_player.receiver');
  assert.equal(Enigma2RecordingsCard.getStubConfig({}).entity, '');
  assert.deepEqual(Enigma2RecordingsCard.getConfigForm().schema[0].selector.entity.filter, {domain: 'media_player', integration: 'enigma2_connect'});
  assert.ok(window.customCards.some(info => info.type === 'enigma2-connect-recordings-card'));
});
test('card loads explicitly, applies filters, resets and renders safe title', async () => {
  const card = new Enigma2RecordingsCard(); card.setConfig({entity: 'media_player.receiver', name: '<Test>'}); card.hass = hass();
  assert.equal(card.library.loaded, false); assert.equal(card.shadowRoot.querySelector('h2').textContent, '<Test>');
  assert.equal(card.shadowRoot.querySelector('.load').disabled, false);
  await card.library.load(hass(), card.identity);
  assert.match(card.shadowRoot.querySelector('.status').textContent, /1 von 1/);
  card.shadowRoot.querySelector('.search').listeners.input({target: {value: 'missing'}});
  assert.match(card.shadowRoot.querySelector('.status').textContent, /0 von 1/);
  card.shadowRoot.querySelector('.clear').listeners.click();
  assert.match(card.shadowRoot.querySelector('.status').textContent, /1 von 1/);
  card.hass = {...hass(), language: 'en'};
  assert.match(card.shadowRoot.querySelector('.status').textContent, /1 of 1/);
  card.disconnectedCallback(); assert.equal(card.library.loaded, false);
});
test('offline and different receiver clear results; foreign platform is unavailable', async () => {
  const card = new Enigma2RecordingsCard(); card.setConfig({entity: 'media_player.receiver'}); card.hass = hass();
  await card.library.load(hass(), card.identity);
  card.hass = {...hass(), states: {'media_player.receiver': {state: 'unavailable'}}};
  assert.equal(card.library.loaded, false); assert.equal(card.shadowRoot.querySelector('.load').disabled, true);
  card.hass = {...hass(), entities: {'media_player.receiver': {device_id: 'foreign', platform: 'other'}}};
  assert.equal(card.identity, undefined);
  assert.throws(() => card.setConfig({entity: 'sensor.wrong'}));
});

test('refresh preserves selected tag and folder until the new catalog removes them', async () => {
  const card = new Enigma2RecordingsCard(); card.setConfig({entity: 'media_player.receiver'}); card.hass = hass();
  await card.library.load(hass(), card.identity);
  card.filters = {tag: 'Film', directory: '/media/movie'};
  await card.library.load(hass(), card.identity);
  assert.equal(card.filters.tag, 'Film'); assert.equal(card.filters.directory, '/media/movie');
  await card.library.load({callWS: async () => ({response: {recordings: [], tags: [], directories: [], count: 0, total: 0}})}, card.identity);
  assert.equal(card.filters.tag, ''); assert.equal(card.filters.directory, '');
});

test('view configuration preserves existing cards and offers both variants', () => {
  const card = new Enigma2RecordingsCard();
  for (const display_mode of [undefined, 'invalid', 'details']) {
    card.setConfig({entity: 'media_player.receiver', display_mode});
    assert.equal(card.config.display_mode, 'details');
  }
  card.setConfig({entity: 'media_player.receiver', display_mode: 'rows'});
  assert.equal(card.config.display_mode, 'rows');
  const field = Enigma2RecordingsCard.getConfigForm().schema.find(s => s.name === 'display_mode');
  assert.deepEqual(field.selector.select.options.map(o => o.value), ['details', 'rows']);
  assert.match(recordingMarkup(row, 'de'), /<h3>/);
  assert.ok(!recordingMarkup(row, 'de').includes('<summary>'));
});
test('responsive rows render all fields safely in the requested order and retain full details', () => {
  const markup = recordingMarkup({...row, title: '<img src=x>', service_name: '<b>News</b>', directory: '<script>', tags: ['<b>']}, 'de', 'rows');
  const summary = markup.match(/<summary>(.*?)<\/summary>/s)[1];
  assert.match(summary, /&lt;img src=x&gt;/); assert.match(summary, /&lt;b&gt;News&lt;\/b&gt;/);
  assert.ok(!markup.includes('<img')); assert.ok(!markup.includes('<script>')); assert.ok(!markup.includes('<b>'));
  assert.deepEqual([...summary.matchAll(/class="row-([^"]+)"/g)].map(match => match[1]), ['title', 'duration', 'date', 'channel', 'progress', 'size']);
  assert.match(summary, /Aufnahmedatum: .*2026/); assert.match(summary, /Sender: /);
  assert.match(summary, /aria-label="Dauer: 1,5 min"/);
  assert.match(summary, /aria-label="Wiedergabestand: 43 %"/);
  assert.match(summary, /aria-label="Dateigröße: 1 GiB"/);
  for (const label of ['Sender', 'Aufnahmedatum', 'Dauer', 'Dateigröße', 'Tags', 'Ordner', 'Wiedergabestand']) assert.ok(markup.includes(label));
  assert.match(markup, /1 GiB/); assert.match(markup, /43 %/);
  for (const recorded_at of [null, Number.MAX_SAFE_INTEGER]) {
    const unknown = recordingMarkup({...row, recorded_at, service_name: null, duration: null, progress_percent: null, size_bytes: null}, 'en', 'rows');
    assert.match(unknown, /aria-label="Recorded on: Unknown"/);
    for (const label of ['Channel', 'Duration', 'Playback progress', 'File size']) assert.ok(unknown.includes(`aria-label="${label}: Unknown"`));
  }
});
test('row filters and counters agree; unchanged HA updates preserve expanded entries', async () => {
  const card = new Enigma2RecordingsCard(); card.setConfig({entity: 'media_player.receiver', display_mode: 'rows'}); card.hass = hass();
  await card.library.load(hass(), card.identity);
  const list = card.shadowRoot.querySelector('ul');
  list.innerHTML = list.innerHTML.replace('<details>', '<details open="">');
  const expanded = list.innerHTML;
  card.hass = hass(); assert.equal(list.innerHTML, expanded);
  card.shadowRoot.querySelector('.search').listeners.input({target: {value: 'missing'}});
  assert.equal(list.innerHTML, ''); assert.match(card.shadowRoot.querySelector('.status').textContent, /0 von 1/);
  card.shadowRoot.querySelector('.clear').listeners.click();
  assert.match(list.innerHTML, /<summary>/); assert.match(card.shadowRoot.querySelector('.status').textContent, /1 von 1/);
});

// SPDX-License-Identifier: Apache-2.0
const {test, before} = require('node:test');
const assert = require('node:assert/strict');
let HoldController, Enigma2RemoteCard, cardLanguage, EpgController;
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
  ({HoldController, Enigma2RemoteCard, cardLanguage, EpgController} = await import('../www/enigma2-connect-remote-card.js'));
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

const epgText = {loading:'Loading',empty:'Empty',failed:'Failed',created:'Created',existing:'Existing'};
const epgEvent = {service_reference:'ref',event_id:7,begin:2000,end:2300,title:'<script>text</script>'};
test('EPG actions bind exact device and event, suppress double clicks, preserve created state', async () => {
  const changes=[]; const epg=new EpgController(()=>changes.push(epg.busy)); epg.bind('receiver1');
  const calls=[];
  const hass={async callWS(request) {calls.push(request);return {response:request.service==='record_event'?{created:true}:{events:[epgEvent],truncated:true}};}};
  await epg.run(hass,'epg_search',' News ',epgText);
  assert.deepEqual(calls[0],{type:'call_service',domain:'enigma2_connect',service:'epg_search',service_data:{device_id:'receiver1',query:'News'},return_response:true});
  assert.deepEqual(epg.events,[epgEvent]);assert.equal(epg.truncated,true);
  await Promise.all([epg.run(hass,'record_event',epgEvent,epgText),epg.run(hass,'record_event',epgEvent,epgText)]);
  assert.equal(calls.length,2);assert.equal(epg.message,'Created');assert.equal(epg.recorded.size,1);
  assert.equal(calls[1].service_data.title,undefined);assert.equal(calls[1].service_data.event_id,7);
  assert.deepEqual(changes,[true,false,true,false]);
});
test('EPG receiver change discards late results and errors, and unbound view cannot send', async () => {
  const epg=new EpgController(()=>{});epg.bind('receiver1');let done;
  const promise=epg.run({callWS:()=>new Promise(resolve=>{done=resolve;})},'epg_search','News',epgText);
  epg.bind('receiver2');done({response:{events:[epgEvent]}});await promise;
  assert.deepEqual(epg.events,[]);assert.equal(epg.message,'');
  let reject;
  const failure=epg.run({callWS:()=>new Promise((_,bad)=>{reject=bad;})},'epg_similar',epgEvent,epgText);
  epg.invalidate();reject(new Error('old receiver'));await failure;
  assert.equal(epg.message,'');assert.equal(epg.busy,false);
  await epg.run({callWS:()=>{throw new Error('should not run');}},'epg_search','News',epgText);
});
test('EPG empty, failed, translated, malformed and existing responses remain distinct', async () => {
  const epg=new EpgController(()=>{});epg.bind('receiver');let count=0;
  const hass={async callWS(){count++;return {response:{events:[]}};}};
  await epg.run(hass,'epg_search',' ',epgText);assert.equal(count,0);
  await epg.run(hass,'epg_search','Missing',epgText);assert.equal(epg.message,'Empty');
  hass.callWS=async()=>({response:{created:false}});
  await epg.run(hass,'record_event',epgEvent,epgText);assert.equal(epg.message,'Existing');
  hass.callWS=async()=>({response:{}});
  await epg.run(hass,'record_event',epgEvent,epgText);assert.equal(epg.message,'Failed');
  await epg.run(hass,'epg_search','Missing',epgText);assert.equal(epg.message,'Failed');
  hass.callWS=async()=>{throw {translation_domain:'enigma2_connect',translation_key:'epg_changed'};};
  hass.loadBackendTranslation=async()=>()=> 'Treffer geändert';
  await epg.run(hass,'record_event',epgEvent,epgText);assert.equal(epg.message,'Treffer geändert');
});

test('profile language change clears stale EPG text and receiver-bound responses', () => {
  const card=new Enigma2RemoteCard();card.setConfig({entity:'remote.receiver'});
  const hass={language:'de',states:{'remote.receiver':{state:'on',attributes:{}}},entities:{'remote.receiver':{platform:'enigma2_connect',device_id:'receiver'}}};
  card.hass=hass;card.epg.message='Deutscher Text';card.epg.events=[epgEvent];
  const generation=card.epg.generation;card.hass={...hass,language:'en'};
  assert.equal(card.epg.message,'');assert.deepEqual(card.epg.events,[]);
  assert.ok(card.epg.generation>generation);assert.equal(card.epg.device,'receiver');
});

test('remote sections can be hidden independently without hiding guide or TV keys', () => {
  for (let mask=0;mask<8;mask++) {
    const card=new Enigma2RemoteCard();
    const show_epg=Boolean(mask&1),show_numbers=Boolean(mask&2),show_playback=Boolean(mask&4);
    card.setConfig({entity:'remote.receiver',show_epg,show_numbers,show_playback});
    const html=card.shadowRoot.innerHTML;
    assert.equal(html.includes('class="epg"'),show_epg);
    for (const key of ['0','1','9']) assert.equal(html.includes(`data-key="${key}"`),show_numbers);
    for (const key of ['play','pause','stop','record','rewind','fast_forward']) assert.equal(html.includes(`data-key="${key}"`),show_playback);
    for (const key of ['epg','info','tv','radio','power']) assert.ok(html.includes(`data-key="${key}"`));
    assert.ok(card.remoteRows().every(row=>row.length>0));
  }
  const card=new Enigma2RemoteCard();card.setConfig({entity:'remote.receiver'});
  assert.ok(card.shadowRoot.innerHTML.includes('data-key="0"'));
  assert.ok(card.shadowRoot.innerHTML.includes('data-key="play"'));
  assert.ok(!card.shadowRoot.innerHTML.includes('class="epg"'));
  assert.throws(()=>card.setConfig({show_epg:'false'}),/true or false/);
});

test('both picker cards share receiver discovery but only remote exposes section switches', () => {
  const EpgCard=registeredElements.get('enigma2-connect-epg-card');assert.ok(EpgCard);
  const card=new EpgCard();card.setConfig({entity:'remote.receiver',show_epg:false});
  assert.ok(!/<button[^>]*data-key=/.test(card.shadowRoot.innerHTML));
  assert.ok(card.shadowRoot.innerHTML.includes('<section class="epg">'));
  assert.ok(!card.shadowRoot.innerHTML.includes('<details'));
  assert.equal(card.getCardSize(),4);
  assert.deepEqual(EpgCard.getConfigForm().schema.map(x=>x.name),['entity','name','results_view']);
  const form=Enigma2RemoteCard.getConfigForm();
  assert.deepEqual(form.schema.slice(3).map(x=>x.name),['show_epg','show_playback','show_numbers']);
  document.documentElement.lang='de';assert.equal(form.computeLabel({name:'show_epg'}),'EPG-Suche anzeigen');
  document.documentElement.lang='en';assert.equal(form.computeLabel({name:'show_numbers'}),'Show number buttons');
  const info=window.customCards.find(x=>x.type==='enigma2-connect-epg-card');
  assert.equal(info.name,'Enigma2 Connect EPG search');
  assert.equal(info.getEntitySuggestion({entities:{'remote.r':{platform:'enigma2_connect'}}},'remote.r').config.type,'custom:enigma2-connect-epg-card');
  assert.equal(info.getEntitySuggestion({entities:{}},'remote.other'),null);
});

test('reset clears input and results while preserving an in-flight operation and focus', () => {
  const card=new Enigma2RemoteCard();card.setConfig({entity:'remote.receiver'});
  let focused=false;const input={value:'News',focus(){focused=true;}};
  card.shadowRoot.querySelector=selector=>selector==='#epg-query'?input:undefined;
  card.epg.events=[epgEvent];card.epg.busy=true;const generation=card.epg.generation;
  card.clearSearch();assert.equal(input.value,'');assert.equal(focused,true);
  assert.deepEqual(card.epg.events,[]);assert.equal(card.epg.busy,true);
  assert.equal(card.epg.generation,generation);
  card.shadowRoot.querySelector=()=>undefined;card.clearSearch();
});

test('reset ignores late search/similar results and errors, then releases busy', async () => {
  for (const service of ['epg_search','epg_similar']) for (const failure of [false,true]) {
    const epg=new EpgController(()=>{});epg.bind('receiver');let finish;
    const hass={callWS:()=>new Promise((resolve,reject)=>{finish=()=>failure?reject(new Error('old search')):resolve({response:{events:[epgEvent],truncated:true}});})};
    const pending=epg.run(hass,service,service==='epg_search'?'News':epgEvent,epgText);
    epg.resetSearch();assert.equal(epg.busy,true);finish();await pending;
    assert.deepEqual(epg.events,[]);assert.equal(epg.message,'');
    assert.equal(epg.truncated,false);assert.equal(epg.searched,false);assert.equal(epg.busy,false);
  }
});

test('reset preserves recording acknowledgement and duplicate protection', async () => {
  const epg=new EpgController(()=>{});epg.bind('receiver');let finish;let calls=0;
  const hass={callWS:()=>{calls++;return new Promise(resolve=>{finish=()=>resolve({response:{created:true}});});}};
  epg.events=[epgEvent];
  const pending=epg.run(hass,'record_event',epgEvent,epgText);
  epg.resetSearch();await epg.run(hass,'record_event',epgEvent,epgText);assert.equal(calls,1);
  finish();await pending;assert.equal(epg.message,'Created');assert.equal(epg.recorded.size,1);
  assert.deepEqual(epg.events,[]);assert.equal(epg.busy,false);
});

test('single-result paging stays bounded and resetting or a new search returns to the first', async () => {
  const epg=new EpgController(()=>{});epg.bind('receiver');
  const second={...epgEvent,event_id:8};epg.events=[epgEvent,second];
  assert.deepEqual(epg.visibleEvents('single'),[epgEvent]);
  assert.deepEqual(epg.visibleEvents('list'),[epgEvent,second]);
  epg.movePage(-1);assert.equal(epg.page,0);epg.movePage(1);assert.deepEqual(epg.visibleEvents('single'),[second]);
  epg.movePage(1);assert.equal(epg.page,1);epg.busy=true;epg.movePage(-1);assert.equal(epg.page,1);epg.busy=false;
  await epg.run({callWS:async()=>({response:{events:[epgEvent,second]}})},'epg_similar',second,epgText);
  assert.equal(epg.page,0);epg.movePage(1);epg.resetSearch();assert.equal(epg.page,0);
  epg.movePage(1);assert.deepEqual(epg.visibleEvents('single'),[]);assert.equal(epg.page,0);
});

test('result count distinguishes not searched, empty, single and truncated results in both cards', () => {
  for(const Card of [Enigma2RemoteCard,registeredElements.get('enigma2-connect-epg-card')]) {
    const card=new Card();card.setConfig({results_view:'single',show_epg:true});card.language='de';
    assert.equal(card.resultSummary(),'');card.epg.searched=true;assert.equal(card.resultSummary(),'0 Treffer');
    card.epg.events=[epgEvent,{...epgEvent,event_id:8}];card.epg.page=1;
    assert.equal(card.resultSummary(),'Treffer 2 von 2');
    card.epg.truncated=true;assert.equal(card.resultSummary(),'Treffer 2 von 2 · weitere vorhanden');
    card.config.results_view='list';card.language='en';assert.equal(card.resultSummary(),'2 results shown; more available');
    card.epg.truncated=false;card.epg.events=[epgEvent];assert.equal(card.resultSummary(),'1 result');
    assert.throws(()=>card.setConfig({results_view:'invalid'}),/list or single/);
    const selector=Card.getConfigForm().schema.find(x=>x.name==='results_view');
    assert.equal(selector.default,'single');assert.deepEqual(selector.selector.select.options.map(x=>x.value),['list','single']);
  }
});

test('both cards omit limits and ignore obsolete max_results settings', async () => {
  for(const Card of [Enigma2RemoteCard,registeredElements.get('enigma2-connect-epg-card')]) {
    const card=new Card();card.setConfig({entity:'remote.receiver',max_results:50});
    const calls=[];
    card.hass={language:'en',states:{'remote.receiver':{state:'on',attributes:{}}},entities:{'remote.receiver':{platform:'enigma2_connect',device_id:'receiver'}},
      async callWS(request){calls.push(request);return {response:request.service==='record_event'?{created:true}:{events:[epgEvent]}};}};
    await card.epgAction('epg_search','News');await card.epgAction('epg_similar',epgEvent);await card.epgAction('record_event',epgEvent);
    assert.deepEqual(calls.map(x=>x.service_data.limit),[undefined,undefined,undefined]);
    assert.equal(Card.getConfigForm().schema.find(x=>x.name==='max_results'),undefined);
  }
});


test('single view reaches all 123 matches and places accessible arrows around the count', async () => {
  for(const Card of [Enigma2RemoteCard,registeredElements.get('enigma2-connect-epg-card')]) {
    const card=new Card();card.setConfig({results_view:'single',show_epg:true});card.language='de';
    const markup=card.shadowRoot.innerHTML;
    assert.match(markup,/data-page="previous"[^>]*aria-label="[^"]+"[^>]*>‹<\/button><span class="epg-count"[^>]*><\/span><button[^>]*data-page="next"[^>]*aria-label="[^"]+"[^>]*>›/);
    card.epg.changed=()=>{};card.epg.bind('receiver');
    const events=Array.from({length:123},(_,event_id)=>({...epgEvent,event_id}));
    await card.epg.run({callWS:async()=>({response:{events}})},'epg_search','News',epgText);
    card.epg.movePage(122);assert.equal(card.resultSummary(),'Treffer 123 von 123');
    assert.equal(card.epg.visibleEvents('single')[0].event_id,122);
    card.epg.movePage(1);assert.equal(card.epg.page,122);
    card.epg.movePage(-1);assert.equal(card.epg.page,121);
  }
});


test('both cards default to single view and remote search is opt-in', () => {
  for(const Card of [Enigma2RemoteCard,registeredElements.get('enigma2-connect-epg-card')]) {
    const card=new Card();card.setConfig({});
    assert.equal(card.config.results_view,'single');
    assert.equal(card.shadowRoot.innerHTML.includes('class="epg"'),Card.epgOnly);
    assert.equal(Card.getConfigForm().schema.find(x=>x.name==='results_view').default,'single');
    card.setConfig({results_view:'list',show_epg:true});
    assert.equal(card.config.results_view,'list');
    assert.ok(card.shadowRoot.innerHTML.includes('class="epg"'));
  }
  assert.equal(Enigma2RemoteCard.getConfigForm().schema.find(x=>x.name==='show_epg').default,false);
});

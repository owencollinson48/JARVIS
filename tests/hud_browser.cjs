/* Optional developer browser regression suite; never calls a paid API.
 * Run a Flask instance with a disposable database, then:
 * JARVIS_TEST_URL=http://127.0.0.1:5010 node tests/hud_browser.cjs
 * Requires developer-only Playwright and Chromium; not needed to run JARVIS.
 */
const assert = require('node:assert/strict');
let chromium;
try { ({chromium} = require('playwright')); }
catch { ({chromium} = require('../.ui-check/node_modules/playwright')); }
const base = process.env.JARVIS_TEST_URL || 'http://127.0.0.1:5010';
const executablePath = process.env.JARVIS_TEST_CHROMIUM || '/usr/bin/chromium';
const check = async (page, fn, arg) => page.waitForFunction(fn, arg, {timeout: 10000});
const state = page => page.evaluate(async () => (await fetch('/api/state')).json());
const report = text => console.log('PASS', text);

(async () => {
  const browser = await chromium.launch({executablePath, headless: true, args: [
    '--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'
  ]});
  let context;
  try {
    context = await browser.newContext({viewport: {width: 1440, height: 900}, permissions: ['microphone']});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    let chatRequests = 0, fakeMessages = [], replyMode = 'error', releaseReply;
    await page.route('**/api/chat', async route => {
      chatRequests++;
      const content = route.request().postDataJSON().content;
      if (content.startsWith('/remember ')) {await route.continue(); return;}
      if (replyMode === 'success') {
        await new Promise(resolve => {releaseReply = resolve;});
        fakeMessages.push({id: 10001, role: 'user', content, source: 'openai'},
          {id: 10002, role: 'assistant', content: 'Mocked SDK reply for browser state testing.', source: 'openai'});
        await route.fulfill({json: {ok: true}});
      } else await route.fulfill({status: 503, json: {error: 'AI is not configured (offline browser test).'}});
    });
    await page.route('**/api/state', async route => {
      const response = await route.fetch(), data = await response.json();
      data.messages.push(...fakeMessages);
      await route.fulfill({response, json: data});
    });
    await page.goto(base);
    await check(page, () => document.querySelector('#open-count').textContent !== '—');
    assert.equal(await page.locator('#outer-ticks line').count(), 120);
    assert.equal(await page.locator('#segment-blocks path').count(), 36);
    assert.equal(await page.locator('#input-bars span').count(), 24);
    const clock = await page.locator('#local-time').textContent();
    await check(page, old => document.querySelector('#local-time').textContent !== old, clock);
    await page.locator('#command-input').fill('/help');
    await page.locator('#send-command').click();
    assert.match(await page.locator('#last-response').textContent(), /Local commands/);
    assert.equal(chatRequests, 0);
    await page.locator('#command-input').fill('/tasks');
    await page.locator('#send-command').click();
    assert.equal(await page.locator('#workspace-dialog').evaluate(el => el.open), true);
    assert.match(await page.locator('#workspace-title').textContent(), /Task manager/);
    assert.equal(chatRequests, 0);
    report('Live clock, vector HUD, local commands and modal navigation');

    await page.locator('#tasks .new-task').click();
    await page.locator('#task-title').fill('HUD browser test task');
    await page.locator('#task-due').fill('2027-01-01');
    await page.locator('#task-project').selectOption('University');
    await page.locator('#save-task').click();
    const row = () => page.locator('#task-list .task-row').filter({hasText: 'HUD browser test task'});
    await row().waitFor();
    await row().getByRole('button', {name: 'Edit HUD browser test task', exact: true}).click();
    await page.locator('#task-title').fill('HUD browser test task edited');
    await page.locator('#save-task').click();
    await row().getByRole('checkbox').check();
    await check(page, () => [...document.querySelectorAll('#task-list .task-row')].some(el => el.textContent.includes('HUD browser test task edited') && el.classList.contains('completed')));
    await row().getByRole('checkbox').uncheck();
    await check(page, () => [...document.querySelectorAll('#task-list .task-row')].some(el => el.textContent.includes('HUD browser test task edited') && !el.classList.contains('completed')));
    await row().getByRole('button', {name: 'Delete HUD browser test task edited', exact: true}).click();
    await row().waitFor({state: 'detached'});
    await page.locator('#panel-switch').selectOption('university');
    assert.equal(await page.locator('#university').isVisible(), true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#workspace-dialog').evaluate(el => el.open), false);
    report('Existing tasks add/edit/complete/reopen/delete and University overlay');

    await page.locator('.main-nav [data-page="memory"]').click();
    await page.locator('#memory-content').fill('HUD test preference <b>literal</b>');
    await page.locator('#save-memory').click();
    const memory = page.locator('#memory-list .memory-row').filter({hasText: 'HUD test preference'});
    await memory.waitFor();
    assert.equal(await memory.locator('b').count(), 0);
    await memory.getByRole('button', {name: 'Delete memory:', exact: false}).click();
    await memory.waitFor({state: 'detached'});
    await page.route('**/api/memories', route => route.fulfill({status:400,json:{error:'Mocked memory limit reached'}}));
    await page.locator('#memory-content').fill('Keep this unsent memory');
    await page.locator('#save-memory').click();
    await check(page, () => document.querySelector('#panel-notice').textContent.includes('Mocked memory limit'));
    assert.equal(await page.locator('#panel-notice').isVisible(),true);
    assert.equal(await page.locator('#memory-content').inputValue(),'Keep this unsent memory');
    await page.unroute('**/api/memories');
    await page.locator('#panel-switch').selectOption('projects');
    assert.equal(await page.locator('#project-list .project-card').count(), 3);
    await page.locator('#panel-switch').selectOption('settings');
    const oldName = await page.locator('#display-name').inputValue();
    await page.locator('#display-name').fill('HUD test user');
    await page.locator('#settings-form button').click();
    await check(page, () => document.querySelector('#greeting').textContent.includes('HUD test user'));
    await page.locator('#display-name').fill(oldName);
    await page.locator('#settings-form button').click();
    await check(page, old => document.querySelector('#greeting').textContent.includes(old), oldName);
    await page.keyboard.press('Escape');
    report('Existing memory, project and settings functionality');

    await page.locator('#command-input').fill('Test missing key');
    await page.locator('#send-command').click();
    await check(page, () => document.querySelector('#home-status').textContent.includes('offline browser test') && document.querySelector('#reactor').dataset.state==='error');
    assert.equal(await page.locator('#command-input').inputValue(), 'Test missing key');
    assert.equal(await page.locator('#reactor').getAttribute('data-state'), 'error');
    replyMode = 'success';
    await page.locator('#command-input').fill('Test thinking and reply');
    await page.locator('#send-command').click();
    await check(page, () => document.querySelector('#reactor').dataset.state === 'thinking');
    assert.equal(await page.locator('#voice-core').isDisabled(), false, 'The master off button stays usable during a request');
    assert.equal(await page.locator('#send-chat').isDisabled(), true);
    while (!releaseReply) await new Promise(resolve => setTimeout(resolve, 10));
    releaseReply();
    await check(page, () => document.querySelector('#hud-ai-status').textContent === 'Reply verified');
    assert.match(await page.locator('#last-response').textContent(), /Mocked SDK reply/);
    assert.equal(await page.locator('#reactor').getAttribute('data-state'), 'idle');
    await page.locator('.main-nav [data-page="chat"]').click();
    assert.match(await page.locator('#messages').textContent(), /Mocked SDK reply/);
    await page.keyboard.press('Escape');
    report('Error draft preservation, genuine pending-request state and verified-success status (mock API)');

    await page.emulateMedia({reducedMotion: 'reduce'});
    assert.equal(await page.locator('.ring-outer').evaluate(el => getComputedStyle(el).animationName), 'none');
    await page.emulateMedia({reducedMotion: 'no-preference'});
    for (const viewport of [{width: 1440, height: 900}, {width: 1366, height: 768}, {width: 390, height: 844}, {width: 320, height: 740}]) {
      await page.setViewportSize(viewport);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `No overflow at ${viewport.width}`);
      if (viewport.width < 941) {
        const deck = await page.locator('.interaction-deck').boundingBox(), widgets = await page.locator('.left-telemetry').boundingBox();
        assert.ok(deck.y < widgets.y, 'Text fallback comes before widgets on small screens');
      }
    }
    assert.deepEqual(errors, []);
    report('Desktop/mobile resizing, no horizontal overflow, reduced motion and no browser script errors');

    // Hands-free loop: real Web Audio with fake capture hardware, mocked speech and API services.
    const voicePage = await context.newPage();
    const voiceErrors = [];
    voicePage.on('pageerror', error => voiceErrors.push(error.message));
    voicePage.on('dialog', dialog => dialog.accept());
    await voicePage.addInitScript(() => {
      window.__micCalls = 0;window.__starts = 0;window.__streams = [];
      const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async options => {
        window.__micCalls++;
        const stream = await capture(options);window.__streams.push(stream);return stream;
      };
      window.SpeechRecognition = class {
        constructor() {window.__recognition = this;}
        start() {window.__starts++;setTimeout(() => this.onstart?.(), 0);}
        stop() {setTimeout(() => this.onend?.(), 0);}
        abort() {setTimeout(() => this.onend?.(), 0);}
      };
      window.SpeechSynthesisUtterance = class {constructor(text) {this.text = text;}};
      Object.defineProperty(window, 'speechSynthesis', {configurable: true, value: {
        getVoices: () => [{name:'Test British voice',voiceURI:'test-british',lang:'en-GB',localService:true}],
        speak(utterance) {window.__utterance = utterance;setTimeout(() => utterance.onstart?.(), 0);},
        cancel() {window.__speechCancelled = true;}
      }});
    });
    let voiceChatRequests = 0, actions = 0, voiceMessages = [], computerPending = null, releaseVoice;
    await voicePage.route('**/api/state', async route => {
      const response=await route.fetch(),data=await response.json();data.messages.push(...voiceMessages);await route.fulfill({response,json:data});
    });
    await voicePage.route('**/api/computer/state', async route => {
      const response=await route.fetch(),data=await response.json();data.pending=computerPending;await route.fulfill({response,json:data});
    });
    await voicePage.route('**/api/chat', async route => {
      voiceChatRequests++;
      const body=route.request().postDataJSON();
      if(body.content==='slow reply')await new Promise(resolve=>{releaseVoice=resolve;});
      if(body.content==='error please'){await route.fulfill({status:503,json:{error:'Mocked API outage'}});return;}
      let reply='Mocked conversational reply.',local=false;
      if(body.content==='open spotify'){
        computerPending={id:'test-action',preview:'Open approved target: spotify',expires:Date.now()/1000+120};
        reply='Open Spotify. Say confirm action to execute, or cancel action.';local=true;
      }
      if(body.content==='confirm action'){
        assert.equal(body.action_id,'test-action');actions++;computerPending=null;reply='Test adapter accepted Spotify launch.';local=true;
      }
      if(body.content==='next song'){actions++;reply='Test adapter sent next track.';local=true;}
      voiceMessages.push({role:'user',content:body.content,source:local?'local':'openai'}, {role:'assistant',content:reply,source:local?'local':'openai'});
      await route.fulfill({json:{ok:true,local,reply,action:computerPending||undefined}});
    });
    const say=async text=>voicePage.evaluate(text=>{
      const result=[{transcript:text}];result.isFinal=true;window.__recognition.onresult({results:[result]});
    },text);
    const finishSpeech=async()=>{await voicePage.evaluate(()=>window.__utterance.onend());await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='listening');};
    await voicePage.goto(base);
    await check(voicePage, () => document.querySelector('#open-count').textContent !== '—');
    await voicePage.locator('#voice-core').click();
    assert.equal(await voicePage.locator('#voice-consent').evaluate(el => el.open), true);
    assert.equal(await voicePage.evaluate(() => window.__micCalls), 0);
    await voicePage.locator('#allow-voice').click();
    await check(voicePage, () => document.querySelector('#reactor').dataset.state === 'listening');
    await check(voicePage, () => parseInt(document.querySelector('#mic-strength').textContent) > 0);
    await say('Help me plan tomorrow');
    await check(voicePage, () => document.querySelector('#reactor').dataset.state === 'speaking');
    assert.equal(voiceChatRequests,1,'A final phrase automatically submits exactly one turn');
    assert.equal(await voicePage.evaluate(()=>window.__streams.every(stream=>stream.getTracks().every(track=>track.readyState==='ended'))),true,'Mic is closed during spoken reply');
    assert.equal(await voicePage.evaluate(()=>window.__utterance.lang),'en-GB');
    assert.equal(await voicePage.evaluate(()=>window.__utterance.voice.voiceURI),'test-british');
    await finishSpeech();
    await say('What should I prioritise?');
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='speaking');
    assert.equal(voiceChatRequests,2);
    await voicePage.locator('#voice-core').click();
    assert.equal(await voicePage.evaluate(()=>window.JarvisHUD.conversation.active),false);
    await voicePage.evaluate(()=>window.__utterance.onend()); // Stale event must not revive a stopped session.
    await new Promise(resolve=>setTimeout(resolve,500));
    assert.equal(await voicePage.evaluate(()=>window.__starts),2);
    report('Hands-free listen/send/speak/listen across turns, British voice selection, mic paused during speech, one-button off');

    await voicePage.locator('#voice-core').click();
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='listening');
    await say('open spotify');
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='speaking');
    assert.equal(await voicePage.locator('#computer-preview').isVisible(),true);
    assert.equal(actions,0,'App launch awaits confirmation');
    await finishSpeech();await say('confirm action');
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='speaking');
    assert.equal(actions,1);
    assert.equal(await voicePage.locator('#computer-preview').isVisible(),false);
    await finishSpeech();await say('next song');
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='speaking');
    assert.equal(actions,2,'Playback is immediate as requested');
    await finishSpeech();
    const beforeStop=voiceChatRequests;await say('Jarvis, stop listening');
    assert.equal(await voicePage.evaluate(()=>window.JarvisHUD.conversation.active),false);
    assert.equal(voiceChatRequests,beforeStop,'Spoken stop does not call the API');
    report('Spoken action preview/confirmation, immediate playback and spoken stop (mocked Windows actions)');
    await voicePage.locator('#voice-core').click();
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='listening');
    await say('slow reply');
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='thinking');
    const startsBeforeOff=await voicePage.evaluate(()=>window.__starts);
    await voicePage.locator('#voice-core').click();
    assert.equal(await voicePage.evaluate(()=>window.JarvisHUD.conversation.active),false);
    while(!releaseVoice)await new Promise(resolve=>setTimeout(resolve,10));releaseVoice();
    await check(voicePage,()=>document.querySelector('#home-status').textContent.includes('Reply saved'));
    await new Promise(resolve=>setTimeout(resolve,500));
    assert.equal(await voicePage.evaluate(()=>window.__starts),startsBeforeOff);
    assert.equal(await voicePage.evaluate(()=>window.JarvisHUD.voice.speaking),false);
    report('Master off during an in-flight reply cannot restart speech or listening');

    await voicePage.locator('#voice-core').click();
    await check(voicePage,()=>document.querySelector('#reactor').dataset.state==='listening');
    await say('error please');
    await check(voicePage,()=>document.querySelector('#home-status').textContent.includes('Mocked API outage'));
    assert.equal(await voicePage.evaluate(()=>window.JarvisHUD.conversation.active),false,'API failure ends the session');
    assert.equal(await voicePage.locator('#command-input').inputValue(),'error please');
    await voicePage.evaluate(()=>{navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Denied','NotAllowedError');};});
    await voicePage.locator('#voice-core').click();
    await check(voicePage,()=>document.querySelector('#home-status').textContent.includes('denied'));
    assert.equal(await voicePage.evaluate(()=>window.JarvisHUD.conversation.active),false);
    await voicePage.evaluate(()=>{navigator.mediaDevices.getUserMedia=()=>new Promise(resolve=>{window.__resolveMic=resolve;});});
    await voicePage.locator('#voice-core').click();
    await check(voicePage,()=>Boolean(window.__resolveMic));
    await voicePage.keyboard.press('Escape');
    await voicePage.evaluate(()=>window.__resolveMic({getTracks:()=>[{stop(){window.__lateStreamStopped=true;}}]}));
    await check(voicePage,()=>window.__lateStreamStopped===true);
    assert.deepEqual(voiceErrors,[]);
    report('API failure, permission denial, Escape and late-permission cleanup stop conversation without retry loops');

    const unavailable = await context.newPage();
    await unavailable.addInitScript(() => {
      window.SpeechRecognition = undefined;window.webkitSpeechRecognition = undefined;
    });
    await unavailable.goto(base);
    await check(unavailable, () => document.querySelector('#open-count').textContent !== '—');
    assert.match(await unavailable.locator('#speech-status').textContent(), /unsupported/);
    await unavailable.locator('#voice-core').click();
    assert.match(await unavailable.locator('#home-status').textContent(), /needs browser speech/);
    assert.equal(await unavailable.locator('#voice-consent').evaluate(el => el.open), false);
    await unavailable.locator('#command-input').fill('/help');
    await unavailable.locator('#send-command').click();
    assert.match(await unavailable.locator('#last-response').textContent(), /Local commands/);
    report('Unsupported browser speech falls back to working local text input');

    const lateRefresh = await context.newPage();
    let saved = false, sent = 0;
    await lateRefresh.route('**/api/chat', async route => {saved = true;sent++;await route.fulfill({json:{ok:true}});});
    await lateRefresh.route('**/api/state', async route => saved ? route.abort() : route.continue());
    await lateRefresh.goto(base);
    await check(lateRefresh, () => document.querySelector('#open-count').textContent !== '—');
    await lateRefresh.locator('#command-input').fill('Offline transport test');
    await lateRefresh.locator('#send-command').click();
    await check(lateRefresh, () => document.querySelector('#last-response').textContent.includes('Your message was saved. Refresh'));
    assert.equal(sent,1);
    assert.equal(await lateRefresh.locator('#command-input').inputValue(),'');
    assert.match(await lateRefresh.locator('#home-status').textContent(),/saved/);
    report('Successful send followed by refresh failure is not reported as an unsaved/retried message');

    const offline = await context.newPage();
    await offline.route('**/api/state', route => route.abort());
    await offline.goto(base);
    await check(offline, () => document.querySelector('#reactor').dataset.state === 'offline');
    assert.match(await offline.locator('#connection-status').textContent(), /UNAVAILABLE/);
    await offline.locator('#command-input').fill('/help');
    await offline.locator('#send-command').click();
    assert.match(await offline.locator('#last-response').textContent(),/Local commands/);
    assert.equal(await offline.locator('#reactor').getAttribute('data-state'),'offline');
    report('Truthful local-backend offline state');
    console.log('All browser checks passed. Recognition and speech services were mocked; no real speech service, Windows action or paid API was called.');
  } finally {await context?.close();await browser.close();}
})().catch(error => {console.error(error);process.exitCode = 1;});

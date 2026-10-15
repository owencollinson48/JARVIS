/* Vector HUD and browser signals. Decorative orbits do not imply system activity. */
'use strict';
window.JarvisHUD = (() => {
  const get = id => document.getElementById(id);
  const svgNS = 'http://www.w3.org/2000/svg';
  let backendOnline = false, backendChecked = false, busy = false, lastAI = null, aiError = false;
  let consent = false, consentPending = null, lastReply = '', hasExchange = false;
  const svgNode = (tag, attrs) => {
    const element = document.createElementNS(svgNS, tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  };
  function ticks(id, radius, count) {
    const group = get(id);
    for (let index = 0; index < count; index++) {
      const major = index % 5 === 0;
      group.append(svgNode('line', {x1: 300, x2: 300, y1: 300-radius,
        y2: 300-radius+(major?11:5), transform: `rotate(${index*360/count} 300 300)`, class: `tick ${major?'major':''}`}));
    }
  }
  ticks('outer-ticks', 271, 120);
  ticks('inner-ticks', 199, 120);
  for (let index = 0; index < 36; index++) {
    const angle = index * 10, start = (angle - 90) * Math.PI / 180, end = (angle + 7 - 90) * Math.PI / 180;
    const point = (r, a) => `${300+r*Math.cos(a)},${300+r*Math.sin(a)}`;
    get('segment-blocks').append(svgNode('path', {d: `M${point(252,start)} A252 252 0 0 1 ${point(252,end)} L${point(238,end)} A238 238 0 0 0 ${point(238,start)}Z`, class: `segment-block ${index%9===0?'accent':''}`}));
  }
  const bars = Array.from({length: 24}, () => {const bar = document.createElement('span'); get('input-bars').append(bar); return bar;});
  let previousDay;
  function clock() {
    const now = new Date();
    const day = now.toDateString();
    if (previousDay && previousDay !== day) window.dispatchEvent(new Event('jarvis-day-change'));
    previousDay = day;
    get('local-time').textContent = now.toLocaleTimeString('en-AU', {hour12: false});
    get('local-time').dateTime = now.toISOString();
    get('local-day').textContent = now.toLocaleDateString('en-AU', {weekday: 'long'});
    get('day-number').textContent = now.getDate();
    get('today').textContent = now.toLocaleDateString('en-AU', {day: '2-digit', month: 'long', year: 'numeric'}).toUpperCase();
    get('local-zone').textContent = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Browser local timezone';
  }
  clock();
  const timer = setInterval(clock, 1000);
  window.addEventListener('pagehide', () => {clearInterval(timer); voice.stop();});

  function setState(name, description) {
    if (busy && name !== 'thinking' && name !== 'offline') return;
    if (!backendOnline && backendChecked && name === 'idle') name = 'offline';
    get('reactor').dataset.state = name;
    get('reactor-state').textContent = {idle: 'READY', listening: 'LISTENING', thinking: 'PROCESSING', speaking: 'SPEAKING', error: 'ATTENTION', offline: 'BACKEND OFFLINE'}[name];
    get('reactor-description').textContent = description || 'Your next move starts here.';
    get('voice-core').setAttribute('aria-label', voice?.listening || voice?.starting ? 'Stop voice input' : 'Start voice input');
    get('mic-toggle').setAttribute('aria-label', voice?.listening || voice?.starting ? 'Stop voice input' : 'Start voice input');
    get('mic-toggle').setAttribute('aria-pressed', String(Boolean(voice?.listening || voice?.starting)));
    get('core-action').textContent = name === 'listening' ? 'CLICK TO STOP' : name === 'thinking' ? 'PLEASE WAIT' : 'CLICK TO TALK';
    get('stop-audio').disabled = !(voice?.listening || voice?.starting || voice?.speaking || voice?.utterance);
  }
  function showError(message) {
    get('home-status').textContent = message;
    get('last-response').textContent = message;
    if (get('workspace-dialog').open) {get('panel-notice').textContent = message;get('panel-notice').hidden = false;}
  }
  function askConsent(callback) {
    if (consent) { callback(); return; }
    consentPending = callback;
    get('voice-consent').showModal();
  }
  const voice = new window.JarvisVoice({
    state: setState, error: showError,
    mic: message => { get('mic-status').textContent = message; },
    level: (level, values) => {
      get('reactor').style.setProperty('--mic-level', level.toFixed(3));
      get('mic-strength').textContent = `${Math.round(level*100)}%`;
      get('mic-meter').value = level;
      bars.forEach((bar, index) => {bar.style.transform = `scaleY(${.06+(values[index]||0)*.94})`;});
    },
    transcript: (text, final) => {
      get('last-utterance').textContent = `${final?'Voice draft':'Hearing'}: ${text}`;
      if (final) {
        get('command-input').value = text;
        get('home-status').textContent = 'Voice draft ready. Review it, then choose Send. Nothing has been submitted.';
      }
    }
  });
  function toggleMic() {
    if (busy) {showError('Wait for the current request to finish before starting the microphone.'); return;}
    if (voice.listening || voice.starting) {voice.stopListening(); return;}
    if (get('command-input').value.trim() && !confirm('Voice dictation will replace your current unsent text when a transcript is ready. Continue?')) return;
    if (!voice.inputSupported) {voice.start(); return;}
    askConsent(() => { if (!busy && !document.hidden) voice.start(); });
  }
  get('voice-core').onclick = toggleMic;
  get('mic-toggle').onclick = toggleMic;
  get('allow-voice').onclick = () => {
    consent = true;
    get('speech-status').textContent = voice.inputSupported ? 'Consent granted · microphone opens only on request' : 'Voice input unsupported · text available';
    const callback = consentPending;
    consentPending = null;
    get('voice-consent').close();
    callback?.();
  };
  get('cancel-voice').onclick = () => get('voice-consent').close();
  get('voice-consent').addEventListener('close', () => {consentPending = null;});
  function mute(muted) {
    voice.muted = muted;
    if (muted) voice.stopSpeaking();
    get('mute-toggle').textContent = muted ? 'Speech off' : 'Speech on';
    get('mute-toggle').setAttribute('aria-pressed', String(muted));
    get('speak-reply').disabled = muted || !lastReply || !voice.outputSupported || busy;
  }
  get('mute-toggle').onclick = () => {
    if (!voice.outputSupported) {showError('Speech output is unavailable in this browser. Use the text reply.'); return;}
    voice.muted ? askConsent(() => mute(false)) : mute(true);
  };
  get('speak-reply').onclick = () => {if (lastReply && !busy) askConsent(() => voice.speak(lastReply));};
  get('stop-audio').onclick = () => {voice.stop(); setState('idle', 'Audio stopped.');};
  get('auto-speak').onchange = event => {
    if (event.target.checked) {
      if (!voice.outputSupported) {event.target.checked = false; showError('Speech output is unavailable in this browser.'); return;}
      event.target.checked = false;
      askConsent(() => {event.target.checked = true; mute(false);});
    }
  };
  get('reduce-motion').onchange = event => document.body.classList.toggle('reduce-motion', event.target.checked);
  const support = voice.inputSupported ? 'Browser recognition available · permission not requested' : 'Voice input unsupported · text available';
  get('speech-status').textContent = support;
  get('voice-capabilities').textContent = `${support}. Speech output ${voice.outputSupported?'available':'unsupported'}. No microphone opens until you choose to enable it.`;

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      voice.stop();
      const dialogs = ['voice-consent', 'task-dialog', 'workspace-dialog'];
      const top = dialogs.map(get).find(dialog => dialog.open);
      if (top) {event.preventDefault(); top.close();}
      setState('idle', 'Audio stopped.');
    }
    const typing = event.target.closest('input,textarea,select,button,a,[contenteditable="true"]');
    if (event.code === 'Space' && !typing && !event.repeat && !document.querySelector('dialog[open]')) {
      event.preventDefault(); toggleMic();
    }
  });
  document.addEventListener('visibilitychange', () => {
    document.body.classList.toggle('page-hidden', document.hidden);
    if (document.hidden) voice.stop(); else clock();
  });

  function renderAI(ai) {
    let label = 'Not configured', detail = 'Add your backend API key in Windows environment settings.';
    if (ai.error) {label = 'Configuration error'; detail = ai.error;}
    else if (aiError) {label = 'Last request failed'; detail = 'Check the error below or in History. No connection is assumed.';}
    else if (lastAI) {label = 'Reply verified'; detail = `Last successful AI reply: ${lastAI.toLocaleTimeString('en-AU')}. Not a continuous connection.`;}
    else if (ai.configured) {label = 'Configured · not checked'; detail = 'Service access is verified only when an AI reply succeeds.';}
    get('hud-ai-status').textContent = label;
    get('hud-ai-detail').textContent = detail;
    get('ai-indicator').dataset.status = aiError || ai.error ? 'error' : lastAI ? 'verified' : 'unchecked';
    get('hud-usage').textContent = `${ai.attempts_today ?? 0} / ${ai.daily_limit ?? 0}`;
  }
  return {
    voice,
    render(data) {
      this.backend(true);
      const open = data.tasks.filter(task => !task.completed), done = data.tasks.length-open.length;
      const percent = data.tasks.length ? Math.round(done/data.tasks.length*100) : 0;
      get('completion-percent').textContent = `${percent}%`;
      get('completion-arc').setAttribute('stroke-dasharray', `${percent} ${100-percent}`);
      get('nav-task-count').textContent = open.length;
      const uni = open.filter(task => task.project === 'University');
      get('uni-next').textContent = uni[0]?.title || 'No open university tasks';
      get('uni-date').textContent = uni[0] ? `Due ${new Date(uni[0].due+'T12:00:00').toLocaleDateString('en-AU', {day:'numeric',month:'short',year:'numeric'})}` : 'Add a University task to see its deadline.';
      get('uni-count').textContent = `${uni.length} unfinished`;
      renderAI(data.ai);
      if (!hasExchange && data.messages.length) {
        const last = data.messages.filter(message => message.role === 'assistant').at(-1);
        const user = data.messages.filter(message => message.role === 'user').at(-1);
        if (last) this.exchange(user?.content || 'Local conversation history', last.content);
      }
    },
    renderAI,
    backend(online) {
      backendOnline = online;
      backendChecked = true;
      document.body.dataset.backend = online ? 'online' : 'offline';
      get('connection-status').textContent = online ? 'DATA LOADED' : 'UNAVAILABLE';
      get('footer-state').textContent = online ? 'LOCAL STORAGE / AVAILABLE' : 'LOCAL BACKEND / UNAVAILABLE';
      if (online && get('reactor').dataset.state === 'offline') setState('idle', 'Local data is available again.');
      if (!online) {
        voice.stop();
        setState('offline', 'Cannot reach local JARVIS. Check the command window, then refresh.');
      }
    },
    busy(value) {
      if (value) voice.stop();
      busy = value;
      get('voice-core').disabled = value;
      get('mic-toggle').disabled = value;
      get('speak-reply').disabled = value || voice.muted || !lastReply || !voice.outputSupported;
      setState(value ? 'thinking' : 'idle', value ? 'Waiting for the real request to finish…' : 'Your next move starts here.');
    },
    exchange(user, reply) {
      hasExchange = true;
      get('last-utterance').textContent = user;
      get('last-response').textContent = reply;
      lastReply = reply;
      get('speak-reply').disabled = voice.muted || !voice.outputSupported || busy;
    },
    success(aiReply, replyReady = true) {
      if (aiReply) {aiError = false;lastAI = new Date();}
      if (replyReady && get('auto-speak').checked && !voice.muted && !document.hidden && lastReply) voice.speak(lastReply);
    },
    error(message, isAI = false) {
      if (isAI) aiError = true;
      setState('error', message);
      showError(message);
    },
    stop: () => voice.stop(),
    clockText: () => `${new Date().toLocaleString('en-AU')} (${get('local-zone').textContent})`
  };
})();

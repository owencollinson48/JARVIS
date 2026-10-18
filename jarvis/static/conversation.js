/* Opt-in, alternating listen -> submit -> speak loop. No microphone while speaking. */
'use strict';
window.JarvisConversation = class {
  constructor(voice, hooks) {
    this.voice = voice;
    this.hooks = hooks;
    this.active = false;
    this.waiting = false;
    this.busy = false;
  }
  start() {
    if(this.active)return;
    if (!this.voice.inputSupported || !this.voice.outputSupported) {
      this.hooks.error('Hands-free conversation needs browser speech input and output. Try current Edge or Chrome, or use text.');
      return;
    }
    this.active = true;
    this.waiting = false;
    this.voice.handsFree = true;
    this.voice.muted = false;
    this.hooks.changed(true);
    this.limit = setTimeout(() => {
      this.stop();
      this.hooks.error('The 30-minute voice session ended. Turn conversation on again if you wish to continue.');
    }, 30*60*1000);
    this.resume(0);
  }
  resume(delay = 350) {
    clearTimeout(this.next);
    if (!this.active || this.waiting || this.busy) return;
    this.next = setTimeout(() => {
      if (this.active && !this.waiting && !this.busy && !this.voice.speaking && !this.voice.utterance && !this.voice.listening && !this.voice.starting) this.voice.start();
    }, delay);
  }
  heard(text) {
    if (!this.active || this.waiting || this.busy) return;
    if (/^(?:jarvis[, ]+)?(?:please )?(?:stop everything|stop|cancel that|don['’]t do that|do not do that)[.!?]?$/i.test(text.trim())){this.stop();window.dispatchEvent(new Event('jarvis-emergency'));return;}
    if (/^(?:jarvis[, ]+)?(?:please )?(?:stop listening|stop talking|end conversation|turn off jarvis)(?: please)?[.!?]?$/i.test(text.trim())) {
      this.stop();return;
    }
    this.waiting = true;
    this.voice.stopListening(true);
    this.hooks.submit(text);
  }
  reply(text) {
    this.waiting = false;
    if (!this.active) return;
    if (this.voice.muted) this.resume();
    else this.voice.speak(text);
  }
  speechEnded() {if (this.active) this.resume();}
  setBusy(value) {
    this.busy = value;
    if (value) {clearTimeout(this.next);this.voice.stop();}
  }
  pause() {clearTimeout(this.next);this.voice.stop();this.resume();}
  stop() {
    this.active = false;
    this.waiting = false;
    this.voice.handsFree = false;
    clearTimeout(this.limit);clearTimeout(this.next);
    this.voice.stop();
    this.hooks.changed(false);
  }
};

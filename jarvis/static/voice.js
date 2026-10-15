/* Browser-only voice adapter. No audio is stored or sent to JARVIS's backend. */
'use strict';
window.JarvisVoice = class {
  constructor(callbacks) {
    this.callbacks = callbacks;
    this.Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.AudioContext = window.AudioContext || window.webkitAudioContext;
    this.inputSupported = Boolean(this.Recognition && this.AudioContext && navigator.mediaDevices?.getUserMedia);
    this.outputSupported = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
    this.generation = 0;
    this.speechGeneration = 0;
    this.listening = false;
    this.starting = false;
    this.muted = true;
  }

  async start() {
    if (this.starting || this.listening) { this.stopListening(); return; }
    if (!this.inputSupported) {
      this.fail('Browser voice input is unavailable. Try current Edge or Chrome on localhost, or use the text field.');
      return;
    }
    this.stopSpeaking();
    const generation = ++this.generation;
    this.starting = true;
    this.callbacks.mic('Waiting for permission');
    this.callbacks.state('idle', 'Waiting for microphone permission.');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      if (generation !== this.generation) { stream.getTracks().forEach(track => track.stop()); return; }
      this.stream = stream;
      this.audio = new this.AudioContext();
      if (this.audio.state === 'suspended') await this.audio.resume();
      if (generation !== this.generation) { this.releaseAudio(); return; }
      this.analyser = this.audio.createAnalyser();
      this.analyser.fftSize = 512;
      this.source = this.audio.createMediaStreamSource(stream);
      this.source.connect(this.analyser); // Deliberately not connected to speakers.
      const recognition = new this.Recognition();
      this.recognition = recognition;
      recognition.lang = 'en-AU';
      recognition.continuous = false;
      recognition.interimResults = true;
      let hadError = false;
      recognition.onstart = () => {
        if (generation !== this.generation) return;
        this.starting = false;
        this.listening = true;
        this.callbacks.mic('Listening · live RMS');
        this.callbacks.state('listening', 'Listening. Your transcript will be a draft, not sent automatically.');
        this.sample(generation);
      };
      recognition.onresult = event => {
        if (generation !== this.generation) return;
        const results = Array.from(event.results);
        const final = results.filter(result => result.isFinal).map(result => result[0].transcript).join(' ').trim();
        const interim = results.filter(result => !result.isFinal).map(result => result[0].transcript).join(' ').trim();
        if (final) this.callbacks.transcript(final.slice(0, 2000), true);
        else if (interim) this.callbacks.transcript(interim.slice(0, 2000), false);
      };
      recognition.onerror = event => {
        if (generation !== this.generation) return;
        hadError = true;
        const messages = {
          'not-allowed': 'Microphone or speech permission was denied. Check your browser’s site permissions, then try again.',
          'service-not-allowed': 'Your browser has disabled its speech service. Use text input or check browser settings.',
          'audio-capture': 'No usable microphone was found. Check Windows microphone settings and your input device.',
          'network': 'The browser speech service could not be reached. Text input still works.',
          'no-speech': 'No speech was detected. Try again, or type your request.',
          'language-not-supported': 'This browser does not support Australian English recognition. Use text input.'
        };
        this.stopListening(true);
        this.fail(messages[event.error] || 'Voice recognition stopped unexpectedly. Please use text or try again.');
      };
      recognition.onend = () => {
        if (generation !== this.generation) return;
        this.recognition = null;
        this.starting = false;
        this.listening = false;
        this.releaseAudio();
        this.callbacks.mic('Microphone off');
        if (!hadError) this.callbacks.state('idle', 'Review your transcript, then choose Send.');
      };
      recognition.start();
      // Never leave the microphone running indefinitely if a browser service hangs.
      this.listenTimeout = setTimeout(() => {
        if (generation === this.generation) {
          this.stopListening(true);
          this.fail('Voice input reached its 30-second limit. Review any draft, or try again.');
        }
      }, 30000);
    } catch (error) {
      if (generation !== this.generation) return;
      this.stopListening(true);
      this.fail(error.name === 'NotAllowedError'
        ? 'Microphone access was denied. Use the browser’s site permissions to allow it, or keep using text.'
        : 'Could not open the microphone. Check your device and browser permissions, or use text input.');
    }
  }

  sample(generation) {
    if (!this.listening || generation !== this.generation || !this.analyser) return;
    const samples = new Uint8Array(this.analyser.fftSize);
    this.analyser.getByteTimeDomainData(samples);
    const rms = values => Math.sqrt(values.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / values.length);
    const level = Math.min(1, rms(samples) * 4);
    this.smoothed = (this.smoothed || 0) * .7 + level * .3;
    const bars = Array.from({length: 24}, (_, index) => {
      const start = Math.floor(index * samples.length / 24);
      const end = Math.floor((index + 1) * samples.length / 24);
      return Math.min(1, rms(samples.slice(start, end)) * 4);
    });
    this.callbacks.level(this.smoothed, bars);
    this.frame = requestAnimationFrame(() => this.sample(generation));
  }

  releaseAudio() {
    clearTimeout(this.listenTimeout);
    cancelAnimationFrame(this.frame);
    if (this.stream) this.stream.getTracks().forEach(track => track.stop());
    this.stream = null;
    try { this.source?.disconnect(); } catch { /* An already disconnected source needs no action. */ }
    this.source = null;
    const audio = this.audio;
    this.audio = null;
    if (audio && audio.state !== 'closed') audio.close().catch(() => {});
    this.analyser = null;
    this.smoothed = 0;
    this.callbacks.level(0, Array(24).fill(0));
  }

  stopListening(abort = false) {
    const recognition = this.recognition;
    if (abort) { this.generation++; this.recognition = null; }
    this.starting = false;
    this.listening = false;
    this.releaseAudio();
    this.callbacks.mic('Microphone off');
    if (recognition) {
      try { abort ? recognition.abort() : recognition.stop(); } catch { /* Already stopped. */ }
    } else {
      this.generation++; // Cancels an unresolved getUserMedia permission request.
    }
    this.callbacks.state('idle', 'Microphone stopped. Text input is available.');
  }

  speak(text) {
    if (this.muted) { this.callbacks.error('Speech is off. Use “Speech off” to enable it first.'); return; }
    if (!this.outputSupported) { this.fail('Speech output is unavailable in this browser. Your reply is still available as text.'); return; }
    this.stopListening(true);
    this.stopSpeaking();
    const generation = ++this.speechGeneration;
    const utterance = new SpeechSynthesisUtterance(text.slice(0, 4000));
    utterance.lang = 'en-AU';
    // Prefer an installed voice when available; consent also covers remote browser voices.
    const voices = speechSynthesis.getVoices();
    utterance.voice = voices.find(voice => voice.localService && voice.lang === 'en-AU')
      || voices.find(voice => voice.localService && voice.lang.startsWith('en')) || null;
    utterance.onstart = () => {
      if (generation !== this.speechGeneration) return;
      this.speaking = true;
      this.callbacks.state('speaking', 'Speaking · visual pulse follows speech state, not output amplitude.');
    };
    const finish = () => {
      if (generation !== this.speechGeneration) return;
      this.speaking = false;
      clearTimeout(this.speechTimeout);
      this.utterance = null;
      this.callbacks.state('idle', 'Speech finished. Ready for your next request.');
    };
    utterance.onend = finish;
    utterance.onerror = () => {
      if (generation !== this.speechGeneration) return;
      finish();
      this.fail('Browser speech output failed. Your reply remains available as text.');
    };
    this.utterance = utterance;
    this.callbacks.state('idle', 'Waiting for browser speech output…');
    speechSynthesis.speak(utterance);
    this.speechTimeout = setTimeout(() => {
      if (generation === this.speechGeneration) {
        this.stopSpeaking();
        this.fail('Speech output timed out. You can read the complete reply in History.');
      }
    }, 120000);
  }

  stopSpeaking() {
    this.speechGeneration++;
    clearTimeout(this.speechTimeout);
    if (this.outputSupported && this.utterance) speechSynthesis.cancel();
    this.utterance = null;
    this.speaking = false;
    this.callbacks.state('idle', 'Audio stopped.');
  }

  stop() { this.stopListening(true); this.stopSpeaking(); }
  fail(message) { this.callbacks.mic('Input inactive'); this.callbacks.state('error', message); this.callbacks.error(message); }
};

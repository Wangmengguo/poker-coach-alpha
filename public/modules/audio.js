import { withBase } from '../utils/constants.js';

/**
 * AudioManager - Modern, minimal audio system for poker game
 *
 * Features:
 * - Clean, subtle synthesized sounds (iOS/macOS style)
 * - Support for external audio files (optional upgrade)
 * - Background music with loop and volume control
 * - Smooth ADSR envelopes and filters for professional sound
 *
 * Phase 3.7: Audio Enhancement
 */

// Sound preset configurations for modern minimal style
const SYNTH_PRESETS = {
  // Soft click for check (finger tap on felt)
  check: {
    type: 'sine',
    freq: 180,
    duration: 0.06,
    attack: 0.002,
    decay: 0.05,
    volume: 0.25,
    filterFreq: 800,
  },

  // Gentle tone for call (single chip placed)
  call: {
    type: 'triangle',
    freq: 320,
    duration: 0.08,
    attack: 0.005,
    decay: 0.07,
    volume: 0.2,
    filterFreq: 1200,
  },

  // Subtle ascending tone for raise (confident action)
  raise: {
    type: 'sine',
    freq: [280, 350],
    duration: 0.12,
    attack: 0.01,
    decay: 0.1,
    volume: 0.25,
    filterFreq: 1500,
    slide: true,
  },

  // Soft low thud for fold (card placed down)
  fold: {
    type: 'sine',
    freq: 120,
    duration: 0.1,
    attack: 0.005,
    decay: 0.09,
    volume: 0.2,
    filterFreq: 400,
  },

  // Quick soft click for bet
  bet: {
    type: 'triangle',
    freq: 260,
    duration: 0.07,
    attack: 0.003,
    decay: 0.06,
    volume: 0.22,
    filterFreq: 1000,
  },

  // Gentle notification for your turn (soft bell-like)
  turn: {
    type: 'sine',
    freq: [523, 659],
    duration: 0.15,
    attack: 0.02,
    decay: 0.12,
    volume: 0.18,
    filterFreq: 2000,
    slide: false,
    arpeggio: true,
    arpeggioDelay: 80,
  },

  // Warm, satisfying tone for win (gentle success)
  win: {
    type: 'sine',
    freq: [392, 494, 587],
    duration: 0.2,
    attack: 0.03,
    decay: 0.15,
    volume: 0.2,
    filterFreq: 2500,
    arpeggio: true,
    arpeggioDelay: 100,
  },

  // Card dealing sound
  deal: {
    type: 'noise',
    duration: 0.04,
    attack: 0.001,
    decay: 0.035,
    volume: 0.15,
    filterFreq: 3000,
    filterType: 'highpass',
  },
};

// External sound file paths (optional - if files exist, they'll be used)
const SOUND_FILES = {
  check: withBase('/public/sounds/check.mp3'),
  call: withBase('/public/sounds/call.mp3'),
  raise: withBase('/public/sounds/raise.mp3'),
  fold: withBase('/public/sounds/fold.mp3'),
  bet: withBase('/public/sounds/bet.mp3'),
  turn: withBase('/public/sounds/turn.mp3'),
  win: withBase('/public/sounds/win.mp3'),
  deal: withBase('/public/sounds/deal.mp3'),
};

// Background music configuration
const BGM_CONFIG = {
  defaultUrl: withBase('/public/sounds/bgm-lounge.mp3'),
  volume: 0.15,
  fadeInDuration: 2000,
  fadeOutDuration: 1000,
};

export class AudioManager {
  constructor() {
    this.enabled = true;
    this.sfxVolume = 0.3;
    this.bgmVolume = BGM_CONFIG.volume;
    this.audioContext = null;

    // Cache for loaded audio buffers
    this.audioBuffers = {};
    this.loadedFiles = new Set();
    this.loadingPromises = {};

    // Background music
    this.bgmAudio = null;
    this.bgmEnabled = false;
    this.bgmLoaded = false;

    // Use external files if available, fallback to synth
    this.useExternalFiles = false;
  }

  /**
   * Initialize audio context (must be called after user interaction)
   */
  init() {
    if (this.audioContext) return;
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

      // Try to load external sound files
      this._preloadSoundFiles();

      // Initialize background music element
      this._initBgm();
    } catch (e) {
      console.warn('Web Audio API not supported:', e);
      this.enabled = false;
    }
  }

  /**
   * Try to preload external sound files
   * @private
   */
  async _preloadSoundFiles() {
    for (const [name, path] of Object.entries(SOUND_FILES)) {
      this._loadSoundFile(name, path).catch(() => {
        // Silently fail - will use synth fallback
      });
    }
  }

  /**
   * Load a single sound file
   * @private
   */
  async _loadSoundFile(name, path) {
    if (this.loadingPromises[name]) {
      return this.loadingPromises[name];
    }

    this.loadingPromises[name] = (async () => {
      try {
        const response = await fetch(path);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const arrayBuffer = await response.arrayBuffer();
        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

        this.audioBuffers[name] = audioBuffer;
        this.loadedFiles.add(name);
        this.useExternalFiles = true;
        return audioBuffer;
      } catch (e) {
        // File not found or failed to load - use synth
        delete this.loadingPromises[name];
        throw e;
      }
    })();

    return this.loadingPromises[name];
  }

  /**
   * Initialize background music
   * @private
   */
  _initBgm() {
    if (this.bgmAudio) return;

    this.bgmAudio = new Audio();
    this.bgmAudio.loop = true;
    this.bgmAudio.volume = 0;
    this.bgmAudio.preload = 'auto';

    // Try to load default BGM
    this.bgmAudio.src = BGM_CONFIG.defaultUrl;
    this.bgmAudio.addEventListener('canplaythrough', () => {
      this.bgmLoaded = true;
    });
    this.bgmAudio.addEventListener('error', () => {
      this.bgmLoaded = false;
    });
  }

  /**
   * Play a sound using external file if available, otherwise synth
   */
  play(soundName) {
    if (!this.enabled) return;

    // Lazy init
    if (!this.audioContext) {
      this.init();
    }

    // Try external file first
    if (this.loadedFiles.has(soundName)) {
      this._playBuffer(soundName);
    } else {
      // Fall back to synth
      this._playSynth(soundName);
    }
  }

  /**
   * Play a loaded audio buffer
   * @private
   */
  _playBuffer(name) {
    const buffer = this.audioBuffers[name];
    if (!buffer || !this.audioContext) return;

    try {
      const source = this.audioContext.createBufferSource();
      const gainNode = this.audioContext.createGain();

      source.buffer = buffer;
      gainNode.gain.value = this.sfxVolume;

      source.connect(gainNode);
      gainNode.connect(this.audioContext.destination);

      source.start(0);
    } catch (e) {
      // Silently fail
    }
  }

  /**
   * Play a synthesized sound
   * @private
   */
  _playSynth(soundName) {
    const preset = SYNTH_PRESETS[soundName];
    if (!preset || !this.audioContext) return;

    try {
      if (preset.type === 'noise') {
        this._playNoise(preset);
      } else if (preset.arpeggio && Array.isArray(preset.freq)) {
        this._playArpeggio(preset);
      } else if (preset.slide && Array.isArray(preset.freq)) {
        this._playSlide(preset);
      } else {
        this._playTone(preset);
      }
    } catch (e) {
      // Silently fail
    }
  }

  /**
   * Play a single tone with ADSR envelope and filter
   * @private
   */
  _playTone(preset) {
    const { type, freq, duration, attack, decay, volume, filterFreq } = preset;
    const ctx = this.audioContext;
    const now = ctx.currentTime;

    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();
    const filter = ctx.createBiquadFilter();

    // Configure oscillator
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(
      Array.isArray(freq) ? freq[0] : freq,
      now
    );

    // Configure filter (low-pass for warmth)
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(filterFreq || 2000, now);
    filter.Q.setValueAtTime(0.5, now);

    // ADSR envelope
    const finalVolume = (volume || 0.3) * this.sfxVolume;
    gainNode.gain.setValueAtTime(0, now);
    gainNode.gain.linearRampToValueAtTime(finalVolume, now + attack);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + attack + decay);

    // Connect
    oscillator.connect(filter);
    filter.connect(gainNode);
    gainNode.connect(ctx.destination);

    // Play
    oscillator.start(now);
    oscillator.stop(now + duration);
  }

  /**
   * Play a frequency slide (glide between notes)
   * @private
   */
  _playSlide(preset) {
    const { type, freq, duration, attack, decay, volume, filterFreq } = preset;
    const ctx = this.audioContext;
    const now = ctx.currentTime;

    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();
    const filter = ctx.createBiquadFilter();

    oscillator.type = type;
    oscillator.frequency.setValueAtTime(freq[0], now);
    oscillator.frequency.linearRampToValueAtTime(freq[1], now + duration * 0.7);

    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(filterFreq || 2000, now);

    const finalVolume = (volume || 0.3) * this.sfxVolume;
    gainNode.gain.setValueAtTime(0, now);
    gainNode.gain.linearRampToValueAtTime(finalVolume, now + attack);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + attack + decay);

    oscillator.connect(filter);
    filter.connect(gainNode);
    gainNode.connect(ctx.destination);

    oscillator.start(now);
    oscillator.stop(now + duration);
  }

  /**
   * Play an arpeggio (sequence of notes)
   * @private
   */
  _playArpeggio(preset) {
    const { freq, arpeggioDelay = 100 } = preset;
    if (!Array.isArray(freq)) return;

    freq.forEach((f, i) => {
      setTimeout(() => {
        this._playTone({ ...preset, freq: f });
      }, i * arpeggioDelay);
    });
  }

  /**
   * Play filtered noise (for card/chip sounds)
   * @private
   */
  _playNoise(preset) {
    const { duration, attack, decay, volume, filterFreq, filterType } = preset;
    const ctx = this.audioContext;
    const now = ctx.currentTime;

    // Create noise buffer
    const bufferSize = ctx.sampleRate * duration;
    const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const output = noiseBuffer.getChannelData(0);

    for (let i = 0; i < bufferSize; i++) {
      output[i] = Math.random() * 2 - 1;
    }

    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuffer;

    const filter = ctx.createBiquadFilter();
    filter.type = filterType || 'lowpass';
    filter.frequency.setValueAtTime(filterFreq || 2000, now);

    const gainNode = ctx.createGain();
    const finalVolume = (volume || 0.2) * this.sfxVolume;
    gainNode.gain.setValueAtTime(0, now);
    gainNode.gain.linearRampToValueAtTime(finalVolume, now + attack);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + attack + decay);

    noise.connect(filter);
    filter.connect(gainNode);
    gainNode.connect(ctx.destination);

    noise.start(now);
  }

  /**
   * Play sound for a specific action type
   */
  playAction(actionType) {
    const actionSoundMap = {
      check: 'check',
      call: 'call',
      raise_to: 'raise',
      fold: 'fold',
      bet: 'bet',
    };
    const soundName = actionSoundMap[actionType] || 'check';
    this.play(soundName);
  }

  /**
   * Toggle sound effects on/off
   */
  toggle() {
    this.enabled = !this.enabled;
    return this.enabled;
  }

  /**
   * Set SFX volume (0.0 to 1.0)
   */
  setVolume(vol) {
    this.sfxVolume = Math.max(0, Math.min(1, vol));
  }

  // ==================== Background Music ====================

  /**
   * Start playing background music
   */
  startBgm() {
    if (!this.bgmAudio || !this.bgmLoaded) {
      // Try to init if not already
      if (!this.bgmAudio) this._initBgm();
      return false;
    }

    this.bgmEnabled = true;

    // Fade in
    this.bgmAudio.volume = 0;
    this.bgmAudio.play().catch(() => {
      // Autoplay blocked - user needs to interact first
      this.bgmEnabled = false;
    });

    this._fadeIn();
    return true;
  }

  /**
   * Stop background music
   */
  stopBgm() {
    if (!this.bgmAudio) return;

    this.bgmEnabled = false;
    this._fadeOut(() => {
      this.bgmAudio.pause();
      this.bgmAudio.currentTime = 0;
    });
  }

  /**
   * Toggle background music
   */
  toggleBgm() {
    if (this.bgmEnabled) {
      this.stopBgm();
    } else {
      this.startBgm();
    }
    return this.bgmEnabled;
  }

  /**
   * Set BGM volume (0.0 to 1.0)
   */
  setBgmVolume(vol) {
    this.bgmVolume = Math.max(0, Math.min(1, vol));
    if (this.bgmAudio && this.bgmEnabled) {
      this.bgmAudio.volume = this.bgmVolume;
    }
  }

  /**
   * Fade in BGM
   * @private
   */
  _fadeIn() {
    if (!this.bgmAudio) return;

    const targetVolume = this.bgmVolume;
    const duration = BGM_CONFIG.fadeInDuration;
    const steps = 20;
    const stepTime = duration / steps;
    const stepVolume = targetVolume / steps;
    let currentStep = 0;

    const fade = () => {
      if (currentStep >= steps || !this.bgmEnabled) return;
      currentStep++;
      this.bgmAudio.volume = Math.min(stepVolume * currentStep, targetVolume);
      setTimeout(fade, stepTime);
    };

    fade();
  }

  /**
   * Fade out BGM
   * @private
   */
  _fadeOut(callback) {
    if (!this.bgmAudio) {
      if (callback) callback();
      return;
    }

    const startVolume = this.bgmAudio.volume;
    const duration = BGM_CONFIG.fadeOutDuration;
    const steps = 15;
    const stepTime = duration / steps;
    const stepVolume = startVolume / steps;
    let currentStep = 0;

    const fade = () => {
      if (currentStep >= steps) {
        this.bgmAudio.volume = 0;
        if (callback) callback();
        return;
      }
      currentStep++;
      this.bgmAudio.volume = Math.max(startVolume - stepVolume * currentStep, 0);
      setTimeout(fade, stepTime);
    };

    fade();
  }

  /**
   * Check if BGM file is loaded and ready
   */
  isBgmReady() {
    return this.bgmLoaded;
  }

  /**
   * Load custom BGM from URL
   */
  loadBgm(url) {
    if (!this.bgmAudio) {
      this._initBgm();
    }

    this.bgmLoaded = false;
    this.bgmAudio.src = url;

    return new Promise((resolve, reject) => {
      this.bgmAudio.addEventListener(
        'canplaythrough',
        () => {
          this.bgmLoaded = true;
          resolve();
        },
        { once: true }
      );
      this.bgmAudio.addEventListener(
        'error',
        () => {
          reject(new Error('Failed to load BGM'));
        },
        { once: true }
      );
    });
  }
}

// Singleton instance
export const audioManager = new AudioManager();

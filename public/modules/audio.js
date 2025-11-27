/**
 * AudioManager - Simple audio feedback for poker actions
 * 
 * Uses Web Audio API to generate simple tones as placeholder sounds.
 * Can be enhanced later with actual audio files.
 */

export class AudioManager {
  constructor() {
    this.enabled = true;
    this.volume = 0.3;
    this.audioContext = null;
    
    // Sound configurations (frequency, duration, type)
    this.sounds = {
      check: { freq: 440, duration: 0.08, type: 'sine' },
      call: { freq: 523, duration: 0.1, type: 'sine' },
      raise: { freq: 659, duration: 0.15, type: 'square', decay: true },
      fold: { freq: 220, duration: 0.12, type: 'triangle' },
      deal: { freq: 880, duration: 0.05, type: 'sine' },
      win: { freq: [523, 659, 784], duration: 0.2, type: 'sine', arpeggio: true },
      bet: { freq: 587, duration: 0.1, type: 'square', decay: true },
      turn: { freq: 698, duration: 0.08, type: 'sine' }, // Your turn notification
    };
  }

  /**
   * Initialize audio context (must be called after user interaction)
   */
  init() {
    if (this.audioContext) return;
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {
      console.warn('Web Audio API not supported:', e);
      this.enabled = false;
    }
  }

  /**
   * Play a simple tone
   */
  _playTone(freq, duration, type = 'sine', options = {}) {
    if (!this.enabled || !this.audioContext) return;

    try {
      const oscillator = this.audioContext.createOscillator();
      const gainNode = this.audioContext.createGain();

      oscillator.type = type;
      oscillator.frequency.setValueAtTime(freq, this.audioContext.currentTime);

      gainNode.gain.setValueAtTime(this.volume, this.audioContext.currentTime);
      
      if (options.decay) {
        // Decay envelope for more natural sound
        gainNode.gain.exponentialRampToValueAtTime(
          0.01,
          this.audioContext.currentTime + duration
        );
      } else {
        // Simple fade out
        gainNode.gain.linearRampToValueAtTime(
          0,
          this.audioContext.currentTime + duration
        );
      }

      oscillator.connect(gainNode);
      gainNode.connect(this.audioContext.destination);

      oscillator.start(this.audioContext.currentTime);
      oscillator.stop(this.audioContext.currentTime + duration);
    } catch (e) {
      // Silently fail - audio is non-critical
    }
  }

  /**
   * Play an arpeggio (sequence of notes)
   */
  _playArpeggio(frequencies, duration, type = 'sine') {
    if (!this.enabled || !this.audioContext) return;

    frequencies.forEach((freq, i) => {
      setTimeout(() => {
        this._playTone(freq, duration, type, { decay: true });
      }, i * 100);
    });
  }

  /**
   * Play a sound by name
   */
  play(soundName) {
    if (!this.enabled) return;
    
    // Lazy init on first play (requires user interaction)
    if (!this.audioContext) {
      this.init();
    }

    const sound = this.sounds[soundName];
    if (!sound) return;

    if (sound.arpeggio && Array.isArray(sound.freq)) {
      this._playArpeggio(sound.freq, sound.duration, sound.type);
    } else {
      this._playTone(sound.freq, sound.duration, sound.type, { decay: sound.decay });
    }
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
   * Toggle audio on/off
   */
  toggle() {
    this.enabled = !this.enabled;
    return this.enabled;
  }

  /**
   * Set volume (0.0 to 1.0)
   */
  setVolume(vol) {
    this.volume = Math.max(0, Math.min(1, vol));
  }
}

// Singleton instance
export const audioManager = new AudioManager();



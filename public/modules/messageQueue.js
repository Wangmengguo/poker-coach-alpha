/**
 * MessageQueue - Manages WebSocket message processing with animation pacing.
 *
 * Solves the "fast-forward" problem where bot actions appear instantaneous
 * by queuing messages and processing them with configurable delays.
 *
 * Phase 3.6 implementation.
 */

// Default delays (ms) for different message types
const DEFAULT_DELAYS = {
  action_taken: 650,   // Bot action - pause to show notification
  snapshot: 90,        // State update - quick
  board_change: 1100,  // New community cards dealt - longer pause
  showdown: 1500,      // Showdown - longer pause to view hands
  hand_end: 500,       // Hand completion - brief pause
  prompt: 0,           // User's turn - immediate
  analysis: 0,         // Analysis update - immediate
  session_end: 500,    // Session end - brief pause
  error: 0,            // Errors - immediate
  default: 200,        // Unknown message types
};

// Speed presets
const SPEED_PRESETS = {
  fast: 0.3,      // 30% of normal delay
  normal: 1.0,    // 100% of normal delay
  slow: 2.0,      // 200% of normal delay
  instant: 0,     // No delay (skip all animations)
};

export class MessageQueue {
  /**
   * @param {Function} processCallback - Called for each message to process
   * @param {Object} options - Configuration options
   */
  constructor(processCallback, options = {}) {
    this.queue = [];
    this.processing = false;
    this.processCallback = processCallback;
    this.speedMultiplier = options.speedMultiplier ?? 1.0;
    this.delays = { ...DEFAULT_DELAYS, ...options.delays };
    this.paused = false;
    this.onQueueChange = options.onQueueChange || null;

    // Track pending timeout for cancellation
    this._currentTimeout = null;
    
    // Track board state to detect new community cards
    this._lastBoardLength = 0;
  }

  /**
   * Add a message to the queue
   * @param {Object} msg - WebSocket message
   */
  enqueue(msg) {
    // All messages go through the queue normally so bot actions animate properly.
    // prompt messages are no longer special-cased to flush the queue.
    this.queue.push(msg);
    this._notifyQueueChange();

    if (!this.processing && !this.paused) {
      this._processNext();
    }
  }

  /**
   * Process the next message in the queue
   * @private
   */
  async _processNext() {
    if (this.queue.length === 0) {
      this.processing = false;
      this._notifyQueueChange();
      return;
    }

    if (this.paused) {
      this.processing = false;
      return;
    }

    this.processing = true;
    const msg = this.queue.shift();
    this._notifyQueueChange();

    // Process the message
    try {
      this.processCallback(msg);
    } catch (e) {
      console.error('MessageQueue: Error processing message', e);
    }

    // Calculate delay for this message type
    const delay = this._getDelay(msg);

    if (delay > 0) {
      await this._wait(delay);
    }

    // Continue processing
    this._processNext();
  }

  /**
   * Get the delay for a message type
   * @param {Object} msg - Message object
   * @returns {number} Delay in milliseconds
   * @private
   */
  _getDelay(msg) {
    let baseDelay = this.delays[msg.type] ?? this.delays.default;
    
    // Check for board change in snapshot messages (new community cards)
    if (msg.type === 'snapshot' && msg.table) {
      const board = msg.table.board || [];
      const currentBoardLength = board.length;
      
      if (currentBoardLength > this._lastBoardLength && currentBoardLength > 0) {
        // New community cards were dealt - use longer delay
        baseDelay = this.delays.board_change;
      }
      
      // Update tracked board length
      this._lastBoardLength = currentBoardLength;
    }
    
    // Reset board tracking on hand_end
    if (msg.type === 'hand_end') {
      this._lastBoardLength = 0;
    }
    
    return Math.round(baseDelay * this.speedMultiplier);
  }

  /**
   * Wait for a specified duration
   * @param {number} ms - Milliseconds to wait
   * @returns {Promise}
   * @private
   */
  _wait(ms) {
    return new Promise((resolve) => {
      this._currentTimeout = setTimeout(() => {
        this._currentTimeout = null;
        resolve();
      }, ms);
    });
  }

  /**
   * Immediately process all queued messages without delay (skip animations)
   */
  flush() {
    // Cancel any pending timeout
    if (this._currentTimeout) {
      clearTimeout(this._currentTimeout);
      this._currentTimeout = null;
    }

    // Process all remaining messages immediately
    while (this.queue.length > 0) {
      const msg = this.queue.shift();
      try {
        this.processCallback(msg);
      } catch (e) {
        console.error('MessageQueue: Error flushing message', e);
      }
    }

    this.processing = false;
    this._notifyQueueChange();
  }

  /**
   * Clear all queued messages without processing them
   */
  clear() {
    if (this._currentTimeout) {
      clearTimeout(this._currentTimeout);
      this._currentTimeout = null;
    }
    this.queue = [];
    this.processing = false;
    this._notifyQueueChange();
  }

  /**
   * Pause queue processing
   */
  pause() {
    this.paused = true;
  }

  /**
   * Resume queue processing
   */
  resume() {
    this.paused = false;
    if (this.queue.length > 0 && !this.processing) {
      this._processNext();
    }
  }

  /**
   * Set animation speed
   * @param {number|string} speed - Speed multiplier or preset name ('fast', 'normal', 'slow', 'instant')
   */
  setSpeed(speed) {
    if (typeof speed === 'string') {
      this.speedMultiplier = SPEED_PRESETS[speed] ?? 1.0;
    } else {
      this.speedMultiplier = speed;
    }
  }

  /**
   * Get current speed preset name
   * @returns {string} - 'fast', 'normal', 'slow', or 'custom'
   */
  getSpeedPreset() {
    for (const [name, value] of Object.entries(SPEED_PRESETS)) {
      if (Math.abs(this.speedMultiplier - value) < 0.01) {
        return name;
      }
    }
    return 'custom';
  }

  /**
   * Get queue status
   * @returns {Object} - Queue status info
   */
  getStatus() {
    // Count only player actions (bot moves), exclude state updates and game events
    const actionCount = this.queue.filter(msg => msg.type === 'action_taken').length;
    
    return {
      length: this.queue.length,
      actionCount,  // Count of player actions only
      processing: this.processing,
      paused: this.paused,
      speed: this.getSpeedPreset(),
      speedMultiplier: this.speedMultiplier,
    };
  }

  /**
   * Check if queue is empty
   * @returns {boolean}
   */
  isEmpty() {
    return this.queue.length === 0 && !this.processing;
  }

  /**
   * Notify listeners of queue state change
   * @private
   */
  _notifyQueueChange() {
    if (this.onQueueChange) {
      this.onQueueChange(this.getStatus());
    }
  }
}

export { SPEED_PRESETS, DEFAULT_DELAYS };


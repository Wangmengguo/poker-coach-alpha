import { DEFAULT_TABLE_ID, wsAbsoluteUrl } from '../utils/constants.js';

/**
 * Lightweight WebSocket manager with basic reconnect and event callbacks.
 * Phase 1 deliberately omits offline message queue and complex backoff.
 */
export class WebSocketManager {
  constructor(url, options = {}) {
    this.url = url || wsAbsoluteUrl(`/ws/tables/${DEFAULT_TABLE_ID}?player_id=human`);
    this.maxRetries = options.maxRetries ?? 5;
    this.retryDelay = options.retryDelay ?? 1000;
    this.reconnectAttempts = 0;
    this.ws = null;
    this.eventCallbacks = {};
  }

  on(event, callback) {
    if (!this.eventCallbacks[event]) {
      this.eventCallbacks[event] = [];
    }
    this.eventCallbacks[event].push(callback);
  }

  emit(event, data) {
    const callbacks = this.eventCallbacks[event] || [];
    callbacks.forEach((cb) => {
      try {
        cb(data);
      } catch (e) {
        // Swallow to avoid breaking other listeners
        console.error('WebSocketManager callback error', e);
      }
    });
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  connect() {
    if (this.isConnected()) {
      return;
    }

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.emit('open');
    };

    this.ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (e) {
        this.emit('error', new Error(`Invalid message: ${ev.data}`));
        return;
      }
      this.emit('message', msg);
    };

    this.ws.onclose = () => {
      this.emit('close');
      this.tryReconnect();
    };

    this.ws.onerror = (error) => {
      this.emit('error', error);
    };
  }

  tryReconnect() {
    if (this.reconnectAttempts >= this.maxRetries) {
      this.emit('reconnect_failed', { attempts: this.reconnectAttempts });
      return;
    }
    this.reconnectAttempts += 1;
    const delay = this.retryDelay;
    setTimeout(() => {
      this.emit('reconnecting', { attempts: this.reconnectAttempts });
      this.connect();
    }, delay);
  }

  send(data) {
    if (!this.isConnected()) {
      // For MVP we drop messages when not connected; do not queue.
      return;
    }
    try {
      const payload = typeof data === 'string' ? data : JSON.stringify(data);
      this.ws.send(payload);
    } catch (e) {
      this.emit('error', e);
    }
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}


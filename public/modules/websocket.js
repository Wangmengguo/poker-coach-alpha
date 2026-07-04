import { DEFAULT_TABLE_ID, wsAbsoluteUrl } from '../utils/constants.js';

const PING_INTERVAL_MS = 25000;
const PONG_TIMEOUT_MS = 10000;

/**
 * Lightweight WebSocket manager with heartbeat, exponential backoff reconnect,
 * and event callbacks.
 */
export class WebSocketManager {
  constructor(url, options = {}) {
    this.url = url || wsAbsoluteUrl(`/ws/tables/${DEFAULT_TABLE_ID}?player_id=human`);
    this.maxRetries = options.maxRetries ?? Infinity;
    this.reconnectAttempts = 0;
    this.ws = null;
    this.eventCallbacks = {};
    this._pingIntervalId = null;
    this._pongTimeoutId = null;
  }

  setUrl(url) {
    this.url = url;
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
        console.error('WebSocketManager callback error', e);
      }
    });
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  _clearHeartbeatTimers() {
    if (this._pingIntervalId !== null) {
      clearInterval(this._pingIntervalId);
      this._pingIntervalId = null;
    }
    if (this._pongTimeoutId !== null) {
      clearTimeout(this._pongTimeoutId);
      this._pongTimeoutId = null;
    }
  }

  _armPongTimeout() {
    if (this._pongTimeoutId !== null) {
      clearTimeout(this._pongTimeoutId);
    }
    this._pongTimeoutId = setTimeout(() => {
      this._pongTimeoutId = null;
      if (this.ws) {
        this.ws.close();
      }
    }, PONG_TIMEOUT_MS);
  }

  _startHeartbeat() {
    this._clearHeartbeatTimers();
    this._pingIntervalId = setInterval(() => {
      if (!this.isConnected()) return;
      this.send({ type: 'ping', t: Date.now() });
      this._armPongTimeout();
    }, PING_INTERVAL_MS);
  }

  connect() {
    if (this.isConnected()) {
      return;
    }

    this._clearHeartbeatTimers();
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this._startHeartbeat();
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
      if (msg && msg.type === 'pong') {
        if (this._pongTimeoutId !== null) {
          clearTimeout(this._pongTimeoutId);
          this._pongTimeoutId = null;
        }
        return;
      }
      this.emit('message', msg);
    };

    this.ws.onclose = () => {
      this._clearHeartbeatTimers();
      this.emit('close');
      this.tryReconnect();
    };

    this.ws.onerror = (error) => {
      this.emit('error', error);
    };
  }

  tryReconnect() {
    if (Number.isFinite(this.maxRetries) && this.reconnectAttempts >= this.maxRetries) {
      this.emit('reconnect_failed', { attempts: this.reconnectAttempts });
      return;
    }
    this.reconnectAttempts += 1;
    const baseDelay = Math.min(1000 * 2 ** (this.reconnectAttempts - 1), 30000);
    const jitter = Math.floor(Math.random() * 501);
    const delay = baseDelay + jitter;
    setTimeout(() => {
      this.emit('reconnecting', { attempts: this.reconnectAttempts });
      this.connect();
    }, delay);
  }

  send(data) {
    if (!this.isConnected()) {
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
    this._clearHeartbeatTimers();
    if (this.ws) {
      this.ws.close();
    }
  }
}

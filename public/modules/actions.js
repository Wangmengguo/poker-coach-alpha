import { DEFAULT_TABLE_ID } from '../utils/constants.js';
import { setVisible } from '../utils/dom.js';

/**
 * ActionHandler wires UI buttons to backend REST endpoints and WebSocket actions.
 */
export class ActionHandler {
  constructor(renderer, gameState, wsManager) {
    this.renderer = renderer;
    this.gameState = gameState;
    this.wsManager = wsManager;

    this.joinBtn = document.getElementById('joinBtn');
    this.startBtn = document.getElementById('startBtn');
    this.reconnectBtn = document.getElementById('reconnectBtn');
    this.nextHandBtn = document.getElementById('nextHandBtn');
    this.restartBtn = document.getElementById('restartBtn');
    this.actionsEl = document.getElementById('actions');
  }

  bind() {
    if (this.joinBtn) this.joinBtn.onclick = () => this.join();
    if (this.startBtn) this.startBtn.onclick = () => this.start();
    if (this.reconnectBtn) this.reconnectBtn.onclick = () => this.wsManager.connect();
    if (this.nextHandBtn) {
      this.nextHandBtn.onclick = () => this.nextHand();
    }
    if (this.restartBtn) {
      this.restartBtn.onclick = () => this.restartSession();
    }
  }

  async join() {
    try {
      const res = await fetch('/tables', { method: 'POST' });
      const { table_id } = await res.json();
      const j = await fetch(`/tables/${table_id}/join`, { method: 'POST' });
      const joined = await j.json();
      this.renderer.log(`Joined table ${table_id} as seat ${joined.seat}`);
    } catch (e) {
      this.renderer.log(`Join failed: ${e}`);
    }
  }

  async start() {
    try {
      const res = await fetch(`/tables/${DEFAULT_TABLE_ID}/start`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.renderer.log(`Cannot start session: ${err.error || res.statusText}`);
        return;
      }
      const data = await res.json();
      this.renderer.log(`Session started: ${data.hand_id}`);
    } catch (e) {
      this.renderer.log(`Start error: ${e}`);
    }
  }

  async nextHand() {
    if (!this.nextHandBtn) return;
    try {
      this.nextHandBtn.disabled = true;
      const res = await fetch(`/tables/${DEFAULT_TABLE_ID}/next`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.renderer.log(`Cannot start next hand: ${err.error || res.statusText}`);
      } else {
        const data = await res.json();
        this.renderer.log(`Next hand: ${data.hand_id}`);
        const showdownSummaryEl = document.getElementById('showdownSummary');
        if (showdownSummaryEl) showdownSummaryEl.style.display = 'none';
      }
    } catch (e) {
      this.renderer.log(`Next hand error: ${e}`);
    } finally {
      this.nextHandBtn.disabled = false;
      setVisible(this.nextHandBtn, false);
    }
  }

  async restartSession() {
    if (!this.restartBtn) return;
    try {
      this.restartBtn.disabled = true;
      const res = await fetch(`/tables/${DEFAULT_TABLE_ID}/restart`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.renderer.log(`Restart failed: ${err.error || res.statusText}`);
      } else {
        const data = await res.json();
        this.renderer.log(`Session restarted: ${data.hand_id}`);
        setVisible(this.nextHandBtn, false);
        setVisible(this.restartBtn, false);
        const showdownSummaryEl = document.getElementById('showdownSummary');
        if (showdownSummaryEl) showdownSummaryEl.style.display = 'none';
      }
    } catch (e) {
      this.renderer.log(`Restart error: ${e}`);
    } finally {
      this.restartBtn.disabled = false;
    }
  }

  renderActions(legal) {
    if (!this.actionsEl) return;
    this.gameState.setLegalActions(legal);
    this.actionsEl.innerHTML = '';

    // Detect a range-based raise option (min/max)
    let rangeAction = null;
    for (const a of legal) {
      if (a.type === 'raise_to' && (typeof a.min === 'number' || typeof a.max === 'number')) {
        rangeAction = a;
        break;
      }
    }

    if (rangeAction) {
      const wrap = document.createElement('div');
      wrap.className = 'custom-raise';

      const label = document.createElement('label');
      label.textContent = 'Custom raise:';
      label.style.marginRight = '8px';

      const input = document.createElement('input');
      input.type = 'number';
      input.setAttribute('aria-label', 'Custom raise amount');
      if (typeof rangeAction.min === 'number') input.min = String(rangeAction.min);
      if (typeof rangeAction.max === 'number') input.max = String(rangeAction.max);
      input.step = '1';
      input.placeholder = `${rangeAction.min ?? ''}${
        rangeAction.min != null || rangeAction.max != null ? '-' : ''
      }${rangeAction.max ?? ''}`;
      input.id = 'customRaiseInput';
      input.style.width = '120px';
      input.style.marginRight = '8px';

      const raiseBtn = document.createElement('button');
      raiseBtn.textContent = 'Raise';
      raiseBtn.className = 'raise-btn';
      raiseBtn.disabled = true;
      raiseBtn.setAttribute('aria-label', 'Submit custom raise');

      const validate = () => {
        const v = parseInt(input.value, 10);
        const hasV = !Number.isNaN(v);
        const geMin = rangeAction.min == null || (hasV && v >= rangeAction.min);
        const leMax = rangeAction.max == null || (hasV && v <= rangeAction.max);
        raiseBtn.disabled = !(hasV && geMin && leMax);
      };

      input.addEventListener('input', validate);
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !raiseBtn.disabled) {
          raiseBtn.click();
        }
      });

      raiseBtn.onclick = () => {
        const v = parseInt(input.value, 10);
        if (!Number.isNaN(v)) {
          this.sendAction({ type: 'raise_to', amount: v });
        }
      };

      wrap.appendChild(label);
      wrap.appendChild(input);
      wrap.appendChild(raiseBtn);
      this.actionsEl.appendChild(wrap);
    }

    for (const a of legal) {
      if (
        a.type === 'raise_to' &&
        typeof a.amount !== 'number' &&
        (typeof a.min === 'number' || typeof a.max === 'number')
      ) {
        continue;
      }

      const btn = document.createElement('button');

      if (a.type === 'call') {
        btn.textContent = `Call $${a.amount}`;
        btn.className = 'call-btn';
        btn.setAttribute('aria-label', `Call ${a.amount} dollars`);
      } else if (a.type === 'check') {
        btn.textContent = 'Check';
        btn.className = 'call-btn';
        btn.setAttribute('aria-label', 'Check');
      } else if (a.type === 'fold') {
        btn.textContent = 'Fold';
        btn.className = 'fold-btn';
        btn.setAttribute('aria-label', 'Fold hand');
      } else if (a.type === 'raise_to' && typeof a.amount === 'number') {
        btn.textContent = `Raise to $${a.amount}`;
        btn.className = 'raise-btn';
        btn.setAttribute('aria-label', `Raise to ${a.amount} dollars`);
      } else {
        btn.textContent = a.type;
      }

      btn.onclick = () => this.sendAction(a);
      this.actionsEl.appendChild(btn);
    }
  }

  sendAction(action) {
    if (!this.wsManager || !this.wsManager.isConnected()) return;
    const hand_id = this.gameState.getTable()?.hand_id || 'h_00000';
    const payload = {
      type: 'action',
      action_id: String(Date.now()),
      hand_id,
      seat: 1,
      action,
    };
    this.wsManager.send(payload);
  }
}

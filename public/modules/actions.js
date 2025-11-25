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

  /**
   * Filter raise presets to show only key amounts (2x, 3x, Pot, All-in).
   * Returns at most 3 preset buttons to avoid clutter.
   */
  _filterRaisePresets(legal, rangeAction) {
    if (!rangeAction) return [];

    const min = rangeAction.min ?? 0;
    const max = rangeAction.max ?? Infinity;
    const presets = [];

    // Collect all raise_to with specific amounts
    const allRaises = legal.filter(
      (a) => a.type === 'raise_to' && typeof a.amount === 'number'
    );

    if (allRaises.length === 0) return [];

    // Sort by amount
    allRaises.sort((a, b) => a.amount - b.amount);

    // Find key amounts: smallest (≈2x), middle (≈pot), largest (all-in)
    const smallest = allRaises[0];
    const largest = allRaises[allRaises.length - 1];

    // Always include min raise (2x-ish)
    if (smallest) {
      presets.push({ ...smallest, label: `$${smallest.amount}` });
    }

    // Find a middle option (roughly 3x or pot-sized)
    if (allRaises.length > 2) {
      const midIdx = Math.floor(allRaises.length / 2);
      const mid = allRaises[midIdx];
      if (mid && mid.amount !== smallest?.amount && mid.amount !== largest?.amount) {
        presets.push({ ...mid, label: `$${mid.amount}` });
      }
    }

    // Always include all-in if different from others
    if (largest && largest.amount !== smallest?.amount) {
      const isAllIn = largest.amount === max;
      presets.push({
        ...largest,
        label: isAllIn ? 'All-in' : `$${largest.amount}`,
      });
    }

    return presets;
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

    // === Primary Actions Row ===
    const primaryRow = document.createElement('div');
    primaryRow.className = 'actions-primary';

    // Fold button
    const foldAction = legal.find((a) => a.type === 'fold');
    if (foldAction) {
      const btn = document.createElement('button');
      btn.textContent = 'Fold';
      btn.className = 'fold-btn';
      btn.setAttribute('aria-label', 'Fold hand');
      btn.onclick = () => this.sendAction(foldAction);
      primaryRow.appendChild(btn);
    }

    // Call/Check button
    const callAction = legal.find((a) => a.type === 'call' || a.type === 'check');
    if (callAction) {
      const btn = document.createElement('button');
      if (callAction.type === 'call') {
        btn.textContent = `Call $${callAction.amount}`;
        btn.setAttribute('aria-label', `Call ${callAction.amount} dollars`);
      } else {
        btn.textContent = 'Check';
        btn.setAttribute('aria-label', 'Check');
      }
      btn.className = 'call-btn';
      btn.onclick = () => this.sendAction(callAction);
      primaryRow.appendChild(btn);
    }

    this.actionsEl.appendChild(primaryRow);

    // === Raise Section ===
    if (rangeAction) {
      const raiseSection = document.createElement('div');
      raiseSection.className = 'actions-raise';

      // Filtered preset buttons (max 3)
      const presets = this._filterRaisePresets(legal, rangeAction);
      if (presets.length > 0) {
        const presetsRow = document.createElement('div');
        presetsRow.className = 'raise-presets';

        for (const preset of presets) {
          const btn = document.createElement('button');
          btn.textContent = preset.label;
          btn.className = 'raise-btn raise-preset';
          btn.setAttribute('aria-label', `Raise to ${preset.amount} dollars`);
          btn.onclick = () => this.sendAction({ type: 'raise_to', amount: preset.amount });
          presetsRow.appendChild(btn);
        }

        raiseSection.appendChild(presetsRow);
      }

      // Custom raise input
      const customRow = document.createElement('div');
      customRow.className = 'raise-custom';

      const input = document.createElement('input');
      input.type = 'number';
      input.setAttribute('aria-label', 'Custom raise amount');
      if (typeof rangeAction.min === 'number') input.min = String(rangeAction.min);
      if (typeof rangeAction.max === 'number') input.max = String(rangeAction.max);
      input.step = '1';
      input.placeholder = `${rangeAction.min ?? ''}-${rangeAction.max ?? ''}`;
      input.id = 'customRaiseInput';

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

      customRow.appendChild(input);
      customRow.appendChild(raiseBtn);
      raiseSection.appendChild(customRow);

      this.actionsEl.appendChild(raiseSection);
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

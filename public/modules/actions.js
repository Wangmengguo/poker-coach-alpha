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

    this.startBtn = document.getElementById('startBtn');
    this.reconnectBtn = document.getElementById('reconnectBtn');
    this.nextHandBtn = document.getElementById('nextHandBtn');
    this.actionsEl = document.getElementById('actions');
  }

  bind() {
    if (this.startBtn) this.startBtn.onclick = () => this.start();
    if (this.reconnectBtn) this.reconnectBtn.onclick = () => this.wsManager.connect();
    if (this.nextHandBtn) {
      this.nextHandBtn.onclick = () => this.nextHand();
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
      // New session: reset per-session stats; lifetime base stays.
      try {
        this.gameState.resetSessionStats();
      } catch (e) {
        // ignore
      }
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

  /**
   * Build semantic raise presets: 2x, 3x, Pot, All-in
   * Based on current pot and bet amounts from legal actions
   */
  _buildRaisePresets(legal, rangeAction) {
    if (!rangeAction) return [];

    const min = rangeAction.min ?? 0;
    const max = rangeAction.max ?? Infinity;
    const presets = [];

    // Collect all raise_to with specific amounts to find pot-sized raise
    const allRaises = legal.filter(
      (a) => a.type === 'raise_to' && typeof a.amount === 'number'
    );
    allRaises.sort((a, b) => a.amount - b.amount);

    // Calculate 2x and 3x based on min raise
    const raise2x = min;
    const raise3x = Math.round(min * 1.5); // Approximation for 3x the bet

    // Find pot-sized raise (usually around middle of available raises)
    let potRaise = null;
    if (allRaises.length > 2) {
      const midIdx = Math.floor(allRaises.length / 2);
      potRaise = allRaises[midIdx]?.amount;
    }

    // 2x (min raise)
    if (raise2x >= min && raise2x <= max) {
      presets.push({ amount: raise2x, label: '2x' });
    }

    // 3x
    if (raise3x > raise2x && raise3x <= max) {
      presets.push({ amount: raise3x, label: '3x' });
    }

    // Pot (if distinct from 2x/3x)
    if (potRaise && potRaise > raise3x && potRaise < max) {
      presets.push({ amount: potRaise, label: 'Pot' });
    }

    // All-in
    if (max !== Infinity && max > (potRaise ?? raise3x)) {
      presets.push({ amount: max, label: 'All-in' });
    }

    return presets;
  }

  renderActions(legal) {
    if (!this.actionsEl) return;
    
    // Hide Continue button when showing action buttons to prevent overlap
    if (this.nextHandBtn) {
      setVisible(this.nextHandBtn, false);
    }
    
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

    // === Primary Actions Row (Fold + Call/Check) ===
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

    // === Raise Section (Single row: [2x][3x][Pot][All-in] | $min[slider]$max | $amt [Raise]) ===
    if (rangeAction) {
      const min = rangeAction.min ?? 0;
      const max = rangeAction.max ?? min * 10;

      const raiseSection = document.createElement('div');
      raiseSection.className = 'actions-raise';

      // Quick preset buttons: [2x] [3x] [Pot] [All-in]
      const presets = this._buildRaisePresets(legal, rangeAction);
      if (presets.length > 0) {
        const presetsGroup = document.createElement('div');
        presetsGroup.className = 'raise-presets';

        for (const preset of presets) {
          const btn = document.createElement('button');
          btn.textContent = preset.label;
          btn.className = 'raise-btn raise-preset';
          btn.setAttribute('aria-label', `Raise ${preset.label} to ${preset.amount} dollars`);
          btn.dataset.amount = preset.amount;
          presetsGroup.appendChild(btn);
        }

        raiseSection.appendChild(presetsGroup);
      }

      // Slider group: $min [slider] $max
      const sliderGroup = document.createElement('div');
      sliderGroup.className = 'raise-slider-row';

      const minLabel = document.createElement('span');
      minLabel.className = 'raise-bound raise-min';
      minLabel.textContent = `$${min}`;

      const slider = document.createElement('input');
      slider.type = 'range';
      slider.className = 'raise-slider';
      slider.min = String(min);
      slider.max = String(max);
      slider.value = String(min);
      slider.step = '1';
      slider.id = 'raiseSlider';
      slider.setAttribute('aria-label', 'Raise amount slider');

      const maxLabel = document.createElement('span');
      maxLabel.className = 'raise-bound raise-max';
      maxLabel.textContent = `$${max}`;

      sliderGroup.appendChild(minLabel);
      sliderGroup.appendChild(slider);
      sliderGroup.appendChild(maxLabel);
      raiseSection.appendChild(sliderGroup);

      // Amount display
      const amountDisplay = document.createElement('span');
      amountDisplay.className = 'raise-amount-display';
      amountDisplay.textContent = `$${min}`;
      raiseSection.appendChild(amountDisplay);

      // Raise submit button
      const raiseBtn = document.createElement('button');
      raiseBtn.textContent = 'Raise';
      raiseBtn.className = 'raise-btn raise-submit';
      raiseBtn.setAttribute('aria-label', 'Submit raise');
      raiseSection.appendChild(raiseBtn);

      // Update display on slider change
      const updateDisplay = (value) => {
        amountDisplay.textContent = `$${value}`;
        const percent = ((value - min) / (max - min)) * 100;
        slider.style.setProperty('--fill-percent', `${percent}%`);
      };

      slider.addEventListener('input', () => {
        updateDisplay(parseInt(slider.value, 10));
      });

      // Preset buttons update slider
      if (presets.length > 0) {
        const presetsGroup = raiseSection.querySelector('.raise-presets');
        presetsGroup.addEventListener('click', (e) => {
          const btn = e.target.closest('.raise-preset');
          if (!btn) return;
          const amount = parseInt(btn.dataset.amount, 10);
          if (!Number.isNaN(amount)) {
            slider.value = String(Math.min(Math.max(amount, min), max));
            updateDisplay(parseInt(slider.value, 10));
          }
        });
      }

      // Submit raise action
      raiseBtn.onclick = () => {
        const v = parseInt(slider.value, 10);
        if (!Number.isNaN(v)) {
          this.sendAction({ type: 'raise_to', amount: v });
        }
      };

      // Keyboard: Enter to submit
      slider.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          raiseBtn.click();
        }
      });

      this.actionsEl.appendChild(raiseSection);

      // Initialize slider fill
      updateDisplay(min);
    }
  }

  sendAction(action) {
    if (!this.wsManager || !this.wsManager.isConnected()) return;
    
    // Clear action buttons immediately after user acts
    if (this.actionsEl) {
      this.actionsEl.innerHTML = '';
    }
    
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

import { withBase } from '../utils/constants.js';
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
    const tableId = this.gameState.getTableId();
    if (!tableId) {
      this.renderer.log('No table id yet; waiting for bootstrap.');
      return;
    }
    try {
      const j = await fetch(withBase(`/tables/${tableId}/join`), { method: 'POST' });
      if (!j.ok) {
        const err = await j.json().catch(() => ({}));
        this.renderer.log(`Join failed: ${err.error || j.statusText}`);
        return;
      }
      const joined = await j.json();
      this.renderer.log(`Joined table ${tableId} as seat ${joined.seat}`);
    } catch (e) {
      this.renderer.log(`Join failed: ${e}`);
    }
  }

  async start() {
    try {
      const tableId = this.gameState.getTableId();
      const res = await fetch(withBase(`/tables/${tableId}/start`), { method: 'POST' });
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
      const res = await fetch(withBase(`/tables/${this.gameState.getTableId()}/next`), { method: 'POST' });
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
   * Build semantic raise presets aligned with backend sizing:
   * - Preflop: BB multiples (open) or vs-raise multiples (3-bet/4-bet).
   * - Postflop: pot fractions (1/3, 1/2, 2/3, 1x, 2x).
   * All amounts are taken from legal_actions so they match the coach.
   */
  _buildRaisePresets(legal, rangeAction) {
    if (!rangeAction) return [];

    const table = this.gameState && typeof this.gameState.getTable === 'function'
      ? this.gameState.getTable()
      : null;
    if (!table) return [];

    const street = table.street || 'preflop';

    // Collect all fixed raise_to actions (with concrete amounts)
    const fixedRaises = legal
      .filter((a) => a.type === 'raise_to' && typeof a.amount === 'number')
      .map((a) => ({ ...a, amount: Number(a.amount) }))
      .sort((a, b) => a.amount - b.amount);

    if (!fixedRaises.length) return [];

    const betsObj = table.bets || {};
    const betValsRaw = Object.values(betsObj);
    const betVals = betValsRaw
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v));
    const maxBet = betVals.length ? Math.max(...betVals) : 0;

    const callAction = legal.find((a) => a.type === 'call');
    const toCall =
      callAction && typeof callAction.amount === 'number'
        ? Number(callAction.amount)
        : 0;

    const bb =
      table.blinds && typeof table.blinds.bb === 'number'
        ? Number(table.blinds.bb)
        : 0;
    const potAmt =
      typeof table.pot === 'number' && Number.isFinite(table.pot)
        ? Number(table.pot)
        : 0;

    const maxBound =
      typeof rangeAction.max === 'number' && Number.isFinite(rangeAction.max)
        ? Number(rangeAction.max)
        : null;

    const presets = [];

    // Helper to avoid duplicate amounts
    const pushPreset = (amount, label) => {
      if (!Number.isFinite(amount)) return;
      if (presets.some((p) => p.amount === amount && p.label === label)) return;
      presets.push({ amount, label });
    };

    // Preflop: BB-multiple logic (open) or vs-raise multiples.
    if (street === 'preflop') {
      const isOpenSpot = bb > 0 && maxBet <= bb;

      // Exclude clear all-in candidate from sizing buckets; keep it as dedicated All-in.
      const nonAllInRaises = fixedRaises.filter((r) => {
        if (maxBound == null) return true;
        return Math.abs(r.amount - maxBound) > 1;
      });

      if (isOpenSpot && bb > 0) {
        // Open-raise: classify by BB multiples ~ 2.5x / 3x / 4x.
        const targets = [
          { label: '2.5x', mult: 2.5 },
          { label: '3x', mult: 3.0 },
          { label: '4x', mult: 4.0 },
        ];
        const buckets = new Map();

        for (const r of nonAllInRaises) {
          const amount = r.amount;
          if (!Number.isFinite(amount)) continue;
          const mult = amount / bb;
          if (!Number.isFinite(mult) || mult <= 0) continue;
          let best = null;
          for (const t of targets) {
            const delta = Math.abs(mult - t.mult);
            if (!best || delta < best.delta) {
              best = { target: t, delta };
            }
          }
          if (!best) continue;
          const label = best.target.label;
          const existing = buckets.get(label);
          if (!existing || best.delta < existing.delta) {
            buckets.set(label, { amount, delta: best.delta });
          }
        }

        for (const t of targets) {
          const entry = buckets.get(t.label);
          if (entry) {
            pushPreset(entry.amount, t.label);
          }
        }
      } else if (toCall > 0) {
        // Facing a raise: classify by multiples of the amount to call.
        const targets = [
          { label: '2x', mult: 2.0 },
          { label: '2.5x', mult: 2.5 },
          { label: '3x', mult: 3.0 },
        ];
        const buckets = new Map();

        for (const r of nonAllInRaises) {
          const amount = r.amount;
          if (!Number.isFinite(amount)) continue;
          const kEst = (amount - maxBet) / toCall;
          if (!Number.isFinite(kEst) || kEst <= 0) continue;
          let best = null;
          for (const t of targets) {
            const delta = Math.abs(kEst - t.mult);
            if (!best || delta < best.delta) {
              best = { target: t, delta };
            }
          }
          if (!best) continue;
          const label = best.target.label;
          const existing = buckets.get(label);
          if (!existing || best.delta < existing.delta) {
            buckets.set(label, { amount, delta: best.delta });
          }
        }

        for (const t of targets) {
          const entry = buckets.get(t.label);
          if (entry) {
            pushPreset(entry.amount, t.label);
          }
        }
      }
    } else {
      // Postflop: classify by pot fractions (1/3, 1/2, 2/3, 1x, 2x).
      const denom = potAmt + toCall;
      const nonAllInRaises = fixedRaises.filter((r) => {
        if (maxBound == null) return true;
        return Math.abs(r.amount - maxBound) > 1;
      });

      if (denom > 0) {
        const targets = [
          { label: '1/3 pot', mult: 1 / 3 },
          { label: '1/2 pot', mult: 1 / 2 },
          { label: '2/3 pot', mult: 2 / 3 },
          { label: 'Pot', mult: 1.0 },
          { label: '2x pot', mult: 2.0 },
        ];
        const buckets = new Map();

        for (const r of nonAllInRaises) {
          const amount = r.amount;
          if (!Number.isFinite(amount)) continue;
          const fEst = (amount - maxBet) / denom;
          if (!Number.isFinite(fEst) || fEst <= 0) continue;
          let best = null;
          for (const t of targets) {
            const delta = Math.abs(fEst - t.mult);
            if (!best || delta < best.delta) {
              best = { target: t, delta };
            }
          }
          if (!best) continue;
          const label = best.target.label;
          const existing = buckets.get(label);
          if (!existing || best.delta < existing.delta) {
            buckets.set(label, { amount, delta: best.delta });
          }
        }

        for (const t of targets) {
          const entry = buckets.get(t.label);
          if (entry) {
            pushPreset(entry.amount, t.label);
          }
        }
      }
    }

    // Always add an explicit All-in button when we have a validated max range.
    if (maxBound != null) {
      pushPreset(maxBound, 'All-in');
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

    // === Raise Section (Presets visible, custom slider collapsible) ===
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

        // Preset buttons now directly submit the raise action
        for (const preset of presets) {
          const btn = document.createElement('button');
          btn.textContent = preset.label;
          btn.className = 'raise-btn raise-preset';
          btn.setAttribute(
            'aria-label',
            `Raise ${preset.label} to ${preset.amount} dollars`,
          );
          btn.onclick = () => {
            this.sendAction({ type: 'raise_to', amount: preset.amount });
          };
          presetsGroup.appendChild(btn);
        }

        // Add "Custom..." toggle button
        const customToggleBtn = document.createElement('button');
        customToggleBtn.textContent = 'Custom...';
        customToggleBtn.className = 'raise-btn raise-custom-toggle';
        customToggleBtn.setAttribute('aria-expanded', 'false');
        customToggleBtn.setAttribute('aria-label', 'Show custom raise amount');
        presetsGroup.appendChild(customToggleBtn);

        raiseSection.appendChild(presetsGroup);

        // Custom slider section (initially hidden)
        const customSection = document.createElement('div');
        customSection.className = 'raise-custom-section';
        customSection.style.display = 'none';

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
        customSection.appendChild(sliderGroup);

        // Amount display
        const amountDisplay = document.createElement('span');
        amountDisplay.className = 'raise-amount-display';
        amountDisplay.textContent = `$${min}`;
        customSection.appendChild(amountDisplay);

        // Raise submit button
        const raiseBtn = document.createElement('button');
        raiseBtn.textContent = 'Raise';
        raiseBtn.className = 'raise-btn raise-submit';
        raiseBtn.setAttribute('aria-label', 'Submit custom raise');
        customSection.appendChild(raiseBtn);

        raiseSection.appendChild(customSection);

        // Toggle custom section visibility
        customToggleBtn.onclick = () => {
          const isExpanded = customToggleBtn.getAttribute('aria-expanded') === 'true';
          const nextState = !isExpanded;
          customSection.style.display = nextState ? 'flex' : 'none';
          customToggleBtn.setAttribute('aria-expanded', String(nextState));
          customToggleBtn.textContent = nextState ? 'Hide' : 'Custom...';
          
          // Focus slider when expanding
          if (nextState) {
            setTimeout(() => slider.focus(), 100);
          }
        };

        // Update display on slider change
        const updateDisplay = (value) => {
          amountDisplay.textContent = `$${value}`;
          const percent = ((value - min) / (max - min)) * 100;
          slider.style.setProperty('--fill-percent', `${percent}%`);
        };

        slider.addEventListener('input', () => {
          updateDisplay(parseInt(slider.value, 10));
        });

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

        // Initialize slider fill
        updateDisplay(min);
      }

      this.actionsEl.appendChild(raiseSection);
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

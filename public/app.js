import { GameState } from './modules/state.js';
import { WebSocketManager } from './modules/websocket.js';
import { Renderer } from './modules/renderer.js';
import { ActionHandler } from './modules/actions.js';
import { AnalysisDrawer } from './modules/analysis.js';
import { audioManager } from './modules/audio.js';
import { MessageQueue, SPEED_PRESETS } from './modules/messageQueue.js';
import { withBase } from './utils/constants.js';

const gameState = new GameState();
const renderer = new Renderer();
const wsManager = new WebSocketManager();
const actionHandler = new ActionHandler(renderer, gameState, wsManager);
const analysisDrawer = new AnalysisDrawer(renderer, gameState);

// Track whether we've already auto-joined the default table
let hasAutoJoined = false;

const STORAGE_KEYS = {
  llmEnabled: 'pokerCoach.llmEnabled',
  modelAlias: 'pokerCoach.modelAlias',
  inviteCode: 'pokerCoach.inviteCode',
  inviteSessionId: 'pokerCoach.inviteSessionId',
};

function _setAskButtonState(btn, state, label) {
  if (!btn) return;
  btn.dataset.state = state || 'idle';
  if (typeof label === 'string') {
    btn.textContent = label;
  }
}

function _getStoredBool(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null || raw === undefined) return fallback;
    return raw === '1' || raw === 'true';
  } catch (e) {
    return fallback;
  }
}

function _setStoredBool(key, val) {
  try {
    localStorage.setItem(key, val ? '1' : '0');
  } catch (e) {
    // ignore
  }
}

function _getStoredStr(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return raw;
  } catch (e) {
    return fallback;
  }
}

function _setStoredStr(key, val) {
  try {
    localStorage.setItem(key, String(val || ''));
  } catch (e) {
    // ignore
  }
}

function _getInviteSessionId() {
  let sessionId = _getStoredStr(STORAGE_KEYS.inviteSessionId, '');
  if (sessionId) return sessionId;
  try {
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    sessionId = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  } catch (e) {
    sessionId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }
  _setStoredStr(STORAGE_KEYS.inviteSessionId, sessionId);
  return sessionId;
}

function _sendClientSettings() {
  const llmToggleEl = document.getElementById('llmToggle');
  const modelSelectEl = document.getElementById('modelSelect');
  const inviteCodeEl = document.getElementById('inviteCodeInput');
  const llm_enabled = !!(llmToggleEl && !llmToggleEl.disabled && llmToggleEl.checked);
  const model_alias = modelSelectEl ? modelSelectEl.value : null;
  const invite_code = inviteCodeEl ? inviteCodeEl.value.trim().toUpperCase() : null;
  const invite_session_id = _getInviteSessionId();
  wsManager.send({ type: 'client_settings', llm_enabled, model_alias, invite_code, invite_session_id });
}

function _setInviteStatus(status) {
  const statusEl = document.getElementById('inviteStatus');
  if (!statusEl) return;
  statusEl.dataset.status = status || '';
}

async function initModelSelector() {
  const selectEl = document.getElementById('modelSelect');
  if (!selectEl) return;
  const containerEl = selectEl.closest('.model-selector');
  const llmToggleEl = document.getElementById('llmToggle');
  const askLlmBtn = document.getElementById('askLlmBtn');
  let askInFlight = false;
  try {
    const res = await fetch(withBase('/settings/ai_model'));
    if (!res.ok) return;
    const data = await res.json();
    const {
      llm_available: llmAvailable,
      model_alias: current,
      allowed,
      tiers,
      invite_required: inviteRequired = true,
    } = data || {};
    const isLlmAvailable = !!llmAvailable;
    const availableTiers = Array.isArray(tiers) && tiers.length > 0
      ? tiers.filter((tier) => tier && tier.enabled !== false)
      : (Array.isArray(allowed) ? allowed.map((name) => ({ id: name, label: name })) : []);
    const allowedIds = availableTiers.map((tier) => tier.id);

    // Backend can run in heuristic-only mode; in that case model switching is disabled.
    if (!availableTiers || availableTiers.length === 0) {
      selectEl.innerHTML = '';
      const opt = document.createElement('option');
      opt.value = 'heuristic';
      opt.textContent = 'heuristic';
      opt.selected = true;
      selectEl.appendChild(opt);
      selectEl.disabled = true;
      if (containerEl) {
        containerEl.title = 'Backend is running in heuristic-only mode (LLM disabled)';
      }
      if (llmToggleEl) {
        llmToggleEl.checked = false;
        llmToggleEl.disabled = true;
      }
      if (askLlmBtn) {
        askLlmBtn.disabled = true;
        _setAskButtonState(askLlmBtn, 'idle', 'Ask once');
      }
      return;
    }

    selectEl.innerHTML = '';
    availableTiers.forEach((tier) => {
      const opt = document.createElement('option');
      opt.value = tier.id;
      opt.textContent = tier.label || tier.id;
      selectEl.appendChild(opt);
    });

    // Per-browser defaults (persisted in localStorage)
    const storedAlias = _getStoredStr(STORAGE_KEYS.modelAlias, current);
    const initialAlias = allowedIds.includes(storedAlias)
      ? storedAlias
      : (allowedIds.includes(current) ? current : allowedIds[0]);
    selectEl.value = initialAlias;
    _setStoredStr(STORAGE_KEYS.modelAlias, initialAlias);

    const storedLlmEnabled = _getStoredBool(STORAGE_KEYS.llmEnabled, false);
    const initialLlmEnabled = storedLlmEnabled && isLlmAvailable;
    if (llmToggleEl) {
      llmToggleEl.checked = initialLlmEnabled;
      llmToggleEl.disabled = !isLlmAvailable;
    }
    if (askLlmBtn) {
      askLlmBtn.disabled = !isLlmAvailable;
      _setAskButtonState(askLlmBtn, 'idle', 'Ask once');
    }
    if (containerEl) {
      containerEl.title = isLlmAvailable ? '' : 'LLM not configured on backend';
    }

    selectEl.onchange = () => {
      const alias = selectEl.value;
      _setStoredStr(STORAGE_KEYS.modelAlias, alias);
      const selectedTier = availableTiers.find((tier) => tier.id === alias);
      renderer.log(`LLM mode selected (this browser): ${selectedTier?.label || alias}`);
      _sendClientSettings();
    };

    if (llmToggleEl) {
      llmToggleEl.onchange = () => {
        const enabled = !!llmToggleEl.checked;
        _setStoredBool(STORAGE_KEYS.llmEnabled, enabled);
        renderer.log(`LLM auto-calls (this browser): ${enabled ? 'ON' : 'OFF'}`);
        _sendClientSettings();
      };
    }

    if (askLlmBtn) {
      askLlmBtn.onclick = async () => {
        if (!isLlmAvailable) return;
        if (askInFlight) return;
        const tableId = gameState.getTableId();
        const seat = gameState.getHeroSeat() || 1;
        const alias = selectEl.value;
        const inviteCodeEl = document.getElementById('inviteCodeInput');
        const invite_code = inviteCodeEl ? inviteCodeEl.value.trim().toUpperCase() : '';
        const invite_session_id = _getInviteSessionId();
        if (!tableId) {
          renderer.log('No table id yet; start a session first.');
          _setAskButtonState(askLlmBtn, 'error', 'No table');
          setTimeout(() => _setAskButtonState(askLlmBtn, 'idle', 'Ask once'), 1200);
          return;
        }
        if (inviteRequired && !invite_code) {
          renderer.log('Invite code required for LLM advice.');
          _setAskButtonState(askLlmBtn, 'error', 'Need code');
          setTimeout(() => _setAskButtonState(askLlmBtn, 'idle', 'Ask once'), 1200);
          return;
        }
        askInFlight = true;
        askLlmBtn.disabled = true;
        _setAskButtonState(askLlmBtn, 'loading', 'Asking…');
        try {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 15000);
          const llmRes = await fetch(withBase(`/tables/${tableId}/ai_advice/llm`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ seat, model_alias: alias, invite_code, invite_session_id }),
            signal: controller.signal,
          });
          clearTimeout(timer);
          if (!llmRes.ok) {
            let err = null;
            try {
              err = await llmRes.json();
            } catch (e) {
              // ignore
            }
            const msg = err && err.error ? err.error : `HTTP ${llmRes.status}`;
            renderer.log(`LLM advice unavailable: ${msg}`);
            _setAskButtonState(askLlmBtn, 'error', 'Failed');
            return;
          }
          const adviceMsg = await llmRes.json();
          processMessage(adviceMsg);
          _setAskButtonState(askLlmBtn, 'success', 'Done');
        } catch (e) {
          renderer.log(`Error requesting LLM advice: ${e}`);
          _setAskButtonState(askLlmBtn, 'error', 'Failed');
        } finally {
          askInFlight = false;
          // Re-enable after a short confirmation window.
          setTimeout(() => {
            if (askLlmBtn) {
              askLlmBtn.disabled = !isLlmAvailable;
              _setAskButtonState(askLlmBtn, 'idle', 'Ask once');
            }
          }, 1200);
        }
      };
    }

    // Initialize invite code input
    const inviteCodeEl = document.getElementById('inviteCodeInput');
    if (inviteCodeEl) {
      const storedInviteCode = _getStoredStr(STORAGE_KEYS.inviteCode, '');
      if (storedInviteCode) {
        inviteCodeEl.value = storedInviteCode;
      }

      // Debounced validation on input
      let inviteDebounce = null;
      inviteCodeEl.oninput = () => {
        const code = inviteCodeEl.value.trim().toUpperCase();
        _setStoredStr(STORAGE_KEYS.inviteCode, code);
        if (inviteDebounce) clearTimeout(inviteDebounce);
        if (!code) {
          _setInviteStatus('');
          return;
        }
        _setInviteStatus('pending');
        inviteDebounce = setTimeout(() => {
          _sendClientSettings();
        }, 500);
      };

      // Also validate on blur
      inviteCodeEl.onblur = () => {
        const code = inviteCodeEl.value.trim().toUpperCase();
        if (code) {
          _sendClientSettings();
        }
      };
    }

    // Push current per-browser settings to the server (so auto advice respects the toggle).
    _sendClientSettings();
  } catch (e) {
    // ignore
  }
}

/**
 * Process a single WebSocket message
 * Extracted to be used with MessageQueue
 */
function processMessage(msg) {
  switch (msg.type) {
    case 'snapshot': {
      gameState.updateSnapshot(msg);
      renderer.renderState(msg.table, gameState.snapshot);
      gameState.updateAnalysis({
        pot_math: null,
        pot_extra: null,
        board_texture: null,
        hand_label: null,
        outs: null,
        stats: null,
        context: null,
        hand_strength: null,
      });
      renderer.renderAnalysisDrawer(gameState.analysis);
      // On reload, server only sends a snapshot (no prompt/hand_end),
      // so infer UI state from the table metadata.
      try {
        const table = msg.table || {};
        const legal = Array.isArray(table.legal_actions) ? table.legal_actions : [];
        const actionsEl = document.getElementById('actions');
        const nextHandBtn = document.getElementById('nextHandBtn');
        
        if (table.awaiting_next_hand) {
          // Clear action buttons before showing Continue
          if (actionsEl) actionsEl.innerHTML = '';
          if (nextHandBtn) nextHandBtn.style.display = 'inline-block';
        } else if (legal.length > 0 && table.to_act === 1) {
          // renderActions will hide Continue button
          actionHandler.renderActions(legal);
        }
      } catch (e) {
        // ignore
      }
      break;
    }
    case 'prompt': {
      const legal = msg.legal_actions || [];
      actionHandler.renderActions(legal);
      renderer.log(`Your turn - ${legal.length} options`);
      renderer.announce(`Your turn, ${legal.length} options`);
      audioManager.play('turn');
      try {
        const analysis = msg.analysis || {};
        analysisDrawer.updateAndRender(
          {
            pot_math: analysis.pot_math || null,
            pot_extra: analysis.pot_extra || null,
            stats: analysis.stats || null,
            board_texture: analysis.board_texture || null,
            hand_label: analysis.hand && analysis.hand.label ? analysis.hand.label : null,
            outs: analysis.outs || null,
            context: analysis.context || null,
            hand_strength: null,
          },
          true,
        );
      } catch (e) {
        // ignore
      }
      break;
    }
    case 'showdown': {
      const hands = (msg.players || [])
        .map((p) => `${p.seat}:${p.id} [${(p.hole || []).join(' ')}]`)
        .join(' | ');
      const winners = (msg.winners || [])
        .map((w) => `Seat ${w.seat} (${w.rank}): [${(w.best5 || []).join(' ')}]`)
        .join(' | ');
      renderer.log(
        `Showdown: ${msg.board?.join(' ') || 'no board'} | ${hands}${
          winners ? ' | Winners: ' + winners : ''
        }`,
      );
      renderer.highlightShowdown(msg);
      if (msg.winners && msg.winners.length > 0) {
        audioManager.play('win');
      }
      break;
    }
    case 'hand_end': {
      const actionsEl = document.getElementById('actions');
      if (actionsEl) actionsEl.innerHTML = '';
      const results = (msg.results || [])
        .map((r) => `Seat ${r.seat}: ${r.delta >= 0 ? '+' : ''}$${r.delta}`)
        .join(', ');
      renderer.log(`Hand complete: ${results}`);
      const nextHandBtn = document.getElementById('nextHandBtn');
      if (nextHandBtn) nextHandBtn.style.display = 'inline-block';
      renderer.announce('Hand complete');
      break;
    }
    case 'session_end': {
      const actionsEl = document.getElementById('actions');
      if (actionsEl) actionsEl.innerHTML = '';
      try {
        gameState.commitLifetimeStats();
      } catch (e) {
        // ignore persistence errors
      }
      renderer.updateSessionInfo(null, false);
      const nextHandBtn = document.getElementById('nextHandBtn');
      if (nextHandBtn) nextHandBtn.style.display = 'none';
      renderer.log(`Session ended: ${msg.reason}`);
      renderer.announce(`Session ended: ${msg.reason}`);
      break;
    }
    case 'error': {
      renderer.log(`Error: ${msg.message}`);
      if (msg.trace) {
        // eslint-disable-next-line no-console
        console.error('Server error trace:', msg.trace);
      }
      renderer.announce(`Error: ${msg.message}`);
      break;
    }
    case 'analysis': {
      try {
        const hs = msg.hand_strength || null;
        analysisDrawer.updateAndRender({ hand_strength: hs }, false);
        if (hs && hs.degraded) {
          renderer.log(
            `Hand strength degraded: ${hs.reason || 'timeout or error'}`
          );
        }
      } catch (e) {
        // ignore
      }
      break;
    }
    case 'ai_advice': {
      try {
        const advice = msg.advice || null;
        analysisDrawer.updateAndRender({ ai_advice: advice }, false);
        if (advice && advice.explanation) {
          renderer.log(`AI Coach: ${advice.explanation}`);
        }
      } catch (e) {
        // ignore
      }
      break;
    }
    case 'action_taken': {
      const { seat, player_id, action_type, amount, is_bot } = msg;
      
      let actionText = '';
      switch (action_type) {
        case 'fold':
          actionText = `${player_id} folds`;
          break;
        case 'check':
          actionText = `${player_id} checks`;
          break;
        case 'call':
          actionText = `${player_id} calls${amount ? ` $${amount}` : ''}`;
          break;
        case 'raise_to':
          actionText = `${player_id} raises to $${amount}`;
          break;
        default:
          actionText = `${player_id} ${action_type}${amount ? ` $${amount}` : ''}`;
      }
      
      renderer.log(actionText);
      
      if (is_bot) {
        renderer.showActionNotification(seat, actionText);
      }
      
      audioManager.playAction(action_type);
      renderer.announce(actionText);
      break;
    }
    case 'client_settings_ack': {
      // Handle invite code validation feedback
      if (msg.invite_valid !== undefined) {
        _setInviteStatus(msg.invite_valid ? 'valid' : 'invalid');
      }
      // Optionally log errors
      if (msg.error) {
        renderer.log(`Settings error: ${msg.error}`);
      }
      break;
    }
    default:
      renderer.log(`Unknown message: ${msg.type}`);
  }
}

/**
 * Update the speed button UI to reflect current speed
 */
function updateSpeedButtonUI(speed) {
  const speedBtn = document.getElementById('speedToggleBtn');
  if (!speedBtn) return;
  
  const labels = {
    instant: '⏩',
    fast: '🐇',
    normal: '🎯',
    slow: '🐢',
    custom: '⚙️',
  };
  
  const ariaLabels = {
    instant: 'Speed: Instant (click to change)',
    fast: 'Speed: Fast (click to change)',
    normal: 'Speed: Normal (click to change)',
    slow: 'Speed: Slow (click to change)',
    custom: 'Speed: Custom (click to change)',
  };
  
  speedBtn.textContent = labels[speed] || labels.normal;
  speedBtn.setAttribute('aria-label', ariaLabels[speed] || ariaLabels.normal);
  speedBtn.dataset.speed = speed;
}

/**
 * Update the queue indicator UI
 */
function updateQueueIndicator(status) {
  const indicator = document.getElementById('queueIndicator');
  if (!indicator) return;
  
  // Use actionCount (meaningful actions only) instead of total queue length
  const count = status.actionCount ?? status.length;
  
  if (count > 0) {
    indicator.innerHTML = `⏳<span class="queue-count">${count}</span>`;
    indicator.style.display = 'inline-flex';
    indicator.setAttribute('aria-label', `${count} actions pending`);
  } else {
    indicator.style.display = 'none';
  }
}

// Create message queue with callbacks
const messageQueue = new MessageQueue(processMessage, {
  onQueueChange: updateQueueIndicator,
});

// Bind UI controls
renderer.bindDrawerToggle();
actionHandler.bind();

// Initialize audio on first user interaction
document.addEventListener('click', () => audioManager.init(), { once: true });

// Audio toggle button (sound effects)
const audioToggleBtn = document.getElementById('audioToggleBtn');
if (audioToggleBtn) {
  audioToggleBtn.onclick = () => {
    const enabled = audioManager.toggle();
    audioToggleBtn.textContent = enabled ? '🔊' : '🔇';
    audioToggleBtn.setAttribute('aria-label', enabled ? 'Mute sound effects' : 'Unmute sound effects');
  };
}

// Background music toggle button
const bgmToggleBtn = document.getElementById('bgmToggleBtn');
if (bgmToggleBtn) {
  bgmToggleBtn.onclick = () => {
    // Initialize audio context on first interaction
    audioManager.init();
    
    const playing = audioManager.toggleBgm();
    bgmToggleBtn.textContent = playing ? '🎶' : '🎵';
    bgmToggleBtn.classList.toggle('playing', playing);
    bgmToggleBtn.setAttribute('aria-label', playing ? 'Stop background music' : 'Play background music');
  };
}

// Speed toggle button - cycle through presets
const speedToggleBtn = document.getElementById('speedToggleBtn');
if (speedToggleBtn) {
  // Initialize UI
  updateSpeedButtonUI('normal');
  
  speedToggleBtn.onclick = () => {
    const current = messageQueue.getSpeedPreset();
    const cycle = ['normal', 'fast', 'instant', 'slow'];
    const idx = cycle.indexOf(current);
    const next = cycle[(idx + 1) % cycle.length];
    messageQueue.setSpeed(next);
    updateSpeedButtonUI(next);
  };
}

// Skip button - flush the queue
const skipQueueBtn = document.getElementById('skipQueueBtn');
if (skipQueueBtn) {
  skipQueueBtn.onclick = () => {
    messageQueue.flush();
  };
}

// WebSocket event handlers
wsManager.on('open', () => {
  gameState.setConnectionStatus('connected', 0);
  const reconnectBtn = document.getElementById('reconnectBtn');
  if (reconnectBtn) reconnectBtn.style.display = 'none';
  renderer.log('Connected to server');
  renderer.announce('Connected to server');
  renderer.renderConnectionStatus('connected');

  // Auto-join default table once when the connection is first established
  if (!hasAutoJoined) {
    hasAutoJoined = true;
    actionHandler.join();
  }

  initModelSelector();
});

wsManager.on('reconnecting', ({ attempts }) => {
  gameState.setConnectionStatus('reconnecting', attempts);
  const reconnectBtn = document.getElementById('reconnectBtn');
  if (reconnectBtn) reconnectBtn.style.display = 'inline-block';
  renderer.log(`Reconnecting (#${attempts})...`);
  renderer.announce(`Reconnecting, attempt ${attempts}`);
  renderer.renderConnectionStatus('reconnecting');
});

wsManager.on('reconnect_failed', ({ attempts }) => {
  gameState.setConnectionStatus('failed', attempts);
  renderer.log(`Reconnect failed after ${attempts} attempts`);
  renderer.announce('Reconnect failed');
  renderer.renderConnectionStatus('failed');
});

wsManager.on('close', () => {
  renderer.log('Disconnected from server');
  gameState.setConnectionStatus('disconnected', gameState.connection.retryCount);
  renderer.updateSessionInfo(null, false);
  renderer.announce('Disconnected from server');
  renderer.renderConnectionStatus('disconnected');
  // Clear queue on disconnect
  messageQueue.clear();
});

wsManager.on('error', (error) => {
  renderer.log(`Connection error: ${error}`);
  renderer.announce('Connection error');
  renderer.renderConnectionStatus('failed');
});

// Route all messages through the queue
wsManager.on('message', (msg) => {
  messageQueue.enqueue(msg);
});

// Initialize
gameState.setConnectionStatus('connecting', 0);
renderer.renderConnectionStatus('connecting');
wsManager.connect();
renderer.log('Poker Coach Alpha started');
renderer.updateSessionInfo(null, false);

// Initialize queue indicator
updateQueueIndicator({ length: 0 });

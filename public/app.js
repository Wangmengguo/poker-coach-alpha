// DOM elements
const logEl = document.getElementById('log');
const actionsEl = document.getElementById('actions');
const handCountEl = document.getElementById('handCount');
const sessionStatusEl = document.getElementById('sessionStatus');
const potAmountEl = document.getElementById('potAmount');
const boardEl = document.getElementById('board');
const streetInfoEl = document.getElementById('streetInfo');
const reconnectBtn = document.getElementById('reconnectBtn');
const nextHandBtn = document.getElementById('nextHandBtn');
const restartBtn = document.getElementById('restartBtn');
const showdownSummaryEl = document.getElementById('showdownSummary');
const analysisEl = document.getElementById('analysis');
let lastPotMath = null;
let lastStats = null;

// State
let ws;
let lastSnapshot = null;
let isConnected = false;

// Utility functions
function log(msg) {
  const timestamp = new Date().toLocaleTimeString();
  logEl.textContent += `[${timestamp}] ${msg}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function updateSessionInfo(handId, sessionActive) {
  const handNum = handId ? handId.replace('h_', '').replace(/^0+/, '') || '1' : '-';
  handCountEl.textContent = `Hand: ${handNum}`;
  sessionStatusEl.textContent = sessionActive ? 'Playing' : 'Waiting';
  sessionStatusEl.style.color = sessionActive ? '#4ade80' : '#94a3b8';
  if (restartBtn) restartBtn.style.display = sessionActive ? 'none' : 'inline-block';
}

function renderPotAndBoard(pot, board, street) {
  potAmountEl.textContent = `$${pot}`;
  streetInfoEl.textContent = street || '-';
  
  boardEl.innerHTML = '';
  if (board && board.length > 0) {
    board.forEach(card => {
      const cardEl = document.createElement('div');
      cardEl.className = 'card';
      cardEl.textContent = card;
      boardEl.appendChild(cardEl);
    });
  }
}

function renderPlayers(players, toAct) {
  for (let seat = 1; seat <= 6; seat++) {
    const seatEl = document.querySelector(`[data-seat="${seat}"]`);
    const playerInfoEl = seatEl.querySelector('.player-info');
    const nameEl = playerInfoEl.querySelector('.player-name');
    const posEl = playerInfoEl.querySelector('.player-pos');
    const stackEl = playerInfoEl.querySelector('.player-stack');
    const cardsEl = playerInfoEl.querySelector('.player-cards');
    const betEl = playerInfoEl.querySelector('.player-bet');
    
    // Clean showdown classes on fresh render
    playerInfoEl.classList.remove('winner', 'loser');

    // Find player for this seat
    const player = players.find(p => p.seat === seat);
    
    if (player) {
      nameEl.textContent = player.id;
      stackEl.textContent = `$${player.stack}`;
      // Position label
      try {
        const positions = lastSnapshot?.table?.positions || {};
        posEl.textContent = positions[String(seat)] || '';
      } catch (e) {
        if (posEl) posEl.textContent = '';
      }
      
      // Update player state classes
      playerInfoEl.classList.toggle('active', toAct === seat);
      playerInfoEl.classList.toggle('human', player.id === 'human');
      
      // Render hole cards
      cardsEl.innerHTML = '';
      if (player.hole && player.hole.length > 0) {
        player.hole.forEach(card => {
          const cardEl = document.createElement('div');
          cardEl.className = card === '??' ? 'card hidden' : 'card';
          cardEl.textContent = card === '??' ? '?' : card;
          cardsEl.appendChild(cardEl);
        });
      }
      
      // Render current bet (chips in front)
      const bets = (lastSnapshot?.table?.bets) || {};
      const betAmt = parseInt(bets[String(seat)] || 0, 10);
      if (betEl) {
        if (betAmt > 0) {
          betEl.textContent = `$${betAmt}`;
          betEl.classList.add('show');
        } else {
          betEl.textContent = '';
          betEl.classList.remove('show');
        }
      }
    } else {
      // Empty seat
      nameEl.textContent = 'Empty';
      const posEl = playerInfoEl.querySelector('.player-pos');
      if (posEl) posEl.textContent = '';
      stackEl.textContent = '$0';
      cardsEl.innerHTML = '';
      if (betEl) { betEl.textContent = ''; betEl.classList.remove('show'); }
      playerInfoEl.classList.remove('active', 'human');
    }
  }
}

function renderState(table) {
  updateSessionInfo(table.hand_id, true);
  renderPotAndBoard(table.pot, table.board, table.street);
  renderPlayers(table.players, table.to_act);
  // Hide any prior showdown summary when new snapshot arrives
  if (showdownSummaryEl) showdownSummaryEl.style.display = 'none';
}

function renderActions(legal) {
  actionsEl.innerHTML = '';

  // Detect a range-based raise option (min/max)
  let rangeAction = null;
  for (const a of legal) {
    if (a.type === 'raise_to' && (typeof a.min === 'number' || typeof a.max === 'number')) {
      rangeAction = a;
      break;
    }
  }

  // If present, render custom raise input constrained by backend-provided min/max
  if (rangeAction) {
    const wrap = document.createElement('div');
    wrap.className = 'custom-raise';

    const label = document.createElement('label');
    label.textContent = 'Custom raise:';
    label.style.marginRight = '8px';

    const input = document.createElement('input');
    input.type = 'number';
    if (typeof rangeAction.min === 'number') input.min = String(rangeAction.min);
    if (typeof rangeAction.max === 'number') input.max = String(rangeAction.max);
    input.step = '1';
    input.placeholder = `${rangeAction.min ?? ''}${(rangeAction.min!=null||rangeAction.max!=null)?'-':''}${rangeAction.max ?? ''}`;
    input.id = 'customRaiseInput';
    input.style.width = '120px';
    input.style.marginRight = '8px';

    const raiseBtn = document.createElement('button');
    raiseBtn.textContent = 'Raise';
    raiseBtn.className = 'raise-btn';
    raiseBtn.disabled = true;

    const validate = () => {
      const v = parseInt(input.value, 10);
      const hasV = !Number.isNaN(v);
      const geMin = (rangeAction.min == null) || (hasV && v >= rangeAction.min);
      const leMax = (rangeAction.max == null) || (hasV && v <= rangeAction.max);
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
        sendAction({ type: 'raise_to', amount: v });
      }
    };

    wrap.appendChild(label);
    wrap.appendChild(input);
    wrap.appendChild(raiseBtn);
    actionsEl.appendChild(wrap);
  }

  // Render discrete action buttons (check/call/fold and fixed raise_to amounts)
  for (const a of legal) {
    // Skip the range representation for raise_to; we'll render only discrete raise buttons here
    if (a.type === 'raise_to' && (typeof a.amount !== 'number') && (typeof a.min === 'number' || typeof a.max === 'number')) {
      continue;
    }

    const btn = document.createElement('button');

    // Set button text and classes
    if (a.type === 'call') {
      btn.textContent = `Call $${a.amount}`;
      btn.className = 'call-btn';
    } else if (a.type === 'check') {
      btn.textContent = 'Check';
      btn.className = 'call-btn';
    } else if (a.type === 'fold') {
      btn.textContent = 'Fold';
      btn.className = 'fold-btn';
    } else if (a.type === 'raise_to' && typeof a.amount === 'number') {
      btn.textContent = `Raise to $${a.amount}`;
      btn.className = 'raise-btn';
    } else {
      btn.textContent = a.type;
    }

    btn.onclick = () => sendAction(a);
    actionsEl.appendChild(btn);
  }
}

function sendAction(action) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const hand_id = lastSnapshot?.table?.hand_id || 'h_00000';
  const payload = { type: 'action', action_id: String(Date.now()), hand_id, seat: 1, action };
  ws.send(JSON.stringify(payload));
}

async function join() {
  const res = await fetch('/tables', { method: 'POST' });
  const { table_id } = await res.json();
  const j = await fetch(`/tables/${table_id}/join`, { method: 'POST' });
  const joined = await j.json();
  log(`Joined table ${table_id} as ${joined.player_id} seat ${joined.seat}`);
}

async function start() {
  const table_id = 'default';
  const s = await fetch(`/tables/${table_id}/start`, { method: 'POST' });
  const data = await s.json();
  log(`Session started, hand_id=${data.hand_id}`);
}

function highlightShowdown(msg) {
  // Update board from showdown payload
  renderPotAndBoard(potAmountEl.textContent.replace('$','') || 0, msg.board || [], 'showdown');

  // Reveal showdown hands at seats and mark winners/losers
  const sdPlayers = msg.players || [];
  const winnerSeats = new Set((msg.winners || []).map(w => w.seat));

  // First, clear winner/loser classes
  for (let seat = 1; seat <= 6; seat++) {
    const seatEl = document.querySelector(`[data-seat="${seat}"]`);
    const playerInfoEl = seatEl.querySelector('.player-info');
    playerInfoEl.classList.remove('winner', 'loser');
  }

  // Update cards and add classes
  for (const p of sdPlayers) {
    const seatEl = document.querySelector(`[data-seat="${p.seat}"]`);
    if (!seatEl) continue;
    const playerInfoEl = seatEl.querySelector('.player-info');
    const cardsEl = playerInfoEl.querySelector('.player-cards');
    cardsEl.innerHTML = '';
    (p.hole || []).forEach(card => {
      const cardEl = document.createElement('div');
      cardEl.className = 'card';
      cardEl.textContent = card;
      cardsEl.appendChild(cardEl);
    });
    if (winnerSeats.has(p.seat)) {
      playerInfoEl.classList.add('winner');
    } else {
      playerInfoEl.classList.add('loser');
    }
  }

  // Build and show summary panel
  if (showdownSummaryEl) {
    const winnersTxt = (msg.winners || []).map(w => `Seat ${w.seat} (${w.rank})`).join(', ');
    const losersTxt = sdPlayers.filter(p => !winnerSeats.has(p.seat)).map(p => `Seat ${p.seat} [${(p.hole||[]).join(' ')}]`).join(' | ');
    showdownSummaryEl.innerHTML = `
      <div class="winners">${winnersTxt ? 'Winners: ' + winnersTxt : 'Showdown'}</div>
      ${losersTxt ? `<div class="losers">Losers: ${losersTxt}</div>` : ''}
    `;
    showdownSummaryEl.style.display = 'block';
  }
}

function connectWS() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    return; // Already connected
  }
  
  ws = new WebSocket(`ws://${location.host}/ws/tables/default?player_id=human`);
  
  ws.onopen = () => {
    log('Connected to server');
    isConnected = true;
    reconnectBtn.style.display = 'none';
  };
  
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      handleMessage(msg);
    } catch (e) {
      log(`Invalid message: ${ev.data}`);
    }
  };
  
  ws.onclose = () => {
    log('Disconnected from server');
    isConnected = false;
    reconnectBtn.style.display = 'inline-block';
    updateSessionInfo(null, false);
  };
  
  ws.onerror = (error) => {
    log(`Connection error: ${error}`);
  };
}

function handleMessage(msg) {
  switch (msg.type) {
    case 'snapshot':
      lastSnapshot = msg;
      renderState(msg.table);
      if (analysisEl) analysisEl.textContent = '';
      lastPotMath = null;
      break;
      
    case 'prompt':
      renderActions(msg.legal_actions || []);
      log(`Your turn - ${msg.legal_actions?.length || 0} options`);
      // MVP v0.1: dump raw pot_math JSON if present
      try {
        const potMath = msg.analysis?.pot_math || null;
        const stats = msg.analysis?.stats || null;
        if (analysisEl) {
          lastPotMath = potMath;
          lastStats = stats;
          if (potMath) {
            const obj = { pot_math: potMath, hand_strength: 'computing…' };
            if (stats) {
              obj.stats = stats;
              const n = Number(stats.vpip_voluntary||0);
              const d = Number(stats.vpip_opportunities||0);
              obj.vpip_display = `VPIP: ${d>0?Math.round((n*100)/d):0}% (${n}/${d} hands)`;
              const r = Number(stats.pfr_raises||0);
              const rd = Number(stats.pfr_opportunities||d||0);
              obj.pfr_display = `PFR: ${rd>0?Math.round((r*100)/rd):0}% (${r}/${rd} hands)`;
              const agg = Number(stats.afq_agg||0);
              const tot = Number(stats.afq_total||0);
              obj.afq_display = `AFq: ${tot>0?Math.round((agg*100)/tot):0}% (${agg}/${tot} actions)`;
            }
            analysisEl.textContent = JSON.stringify(obj, null, 2);
          } else {
            analysisEl.textContent = 'computing…';
          }
        }
      } catch (e) {
        if (analysisEl) analysisEl.textContent = '';
      }
      break;
      
    case 'showdown':
      const hands = (msg.players || []).map(p => 
        `${p.seat}:${p.id} [${(p.hole || []).join(' ')}]`
      ).join(' | ');
      const winners = (msg.winners || []).map(w => `Seat ${w.seat} (${w.rank}): [${(w.best5||[]).join(' ')}]`).join(' | ');
      log(`Showdown: ${msg.board?.join(' ') || 'no board'} | ${hands}${winners ? ' | Winners: ' + winners : ''}`);
      highlightShowdown(msg);
      break;
      
    case 'hand_end':
      actionsEl.innerHTML = '';
      const results = (msg.results || []).map(r => 
        `Seat ${r.seat}: ${r.delta >= 0 ? '+' : ''}$${r.delta}`
      ).join(', ');
      log(`Hand complete: ${results}`);
      if (nextHandBtn) nextHandBtn.style.display = 'inline-block';
      break;
      
    case 'session_end':
      actionsEl.innerHTML = '';
      updateSessionInfo(null, false);
      if (nextHandBtn) nextHandBtn.style.display = 'none';
      if (restartBtn) restartBtn.style.display = 'inline-block';
      log(`Session ended: ${msg.reason}`);
      break;
      
    case 'error':
      log(`Error: ${msg.message}`);
      if (msg.trace) {
        console.error('Server error trace:', msg.trace);
      }
      break;

    case 'analysis': {
      // Merge last pot_math with hand_strength update
      try {
        const hs = msg.hand_strength || null;
        if (analysisEl) {
          const obj = {};
          if (lastPotMath) obj.pot_math = lastPotMath;
          obj.hand_strength = hs || { hand_strength_pct: null, reason: '—' };
          obj.hand_strength_display = (hs && hs.hand_strength_pct != null)
            ? (Number(hs.hand_strength_pct).toFixed(1) + '%')
            : '—';
          if (lastStats) {
            obj.stats = lastStats;
            const n = Number(lastStats.vpip_voluntary||0);
            const d = Number(lastStats.vpip_opportunities||0);
            obj.vpip_display = `VPIP: ${d>0?Math.round((n*100)/d):0}% (${n}/${d} hands)`;
            const r = Number(lastStats.pfr_raises||0);
            const rd = Number(lastStats.pfr_opportunities||d||0);
            obj.pfr_display = `PFR: ${rd>0?Math.round((r*100)/rd):0}% (${r}/${rd} hands)`;
            const agg = Number(lastStats.afq_agg||0);
            const tot = Number(lastStats.afq_total||0);
            obj.afq_display = `AFq: ${tot>0?Math.round((agg*100)/tot):0}% (${agg}/${tot} actions)`;
          }
          analysisEl.textContent = JSON.stringify(obj, null, 2);
        }
      } catch (e) {
        // ignore
      }
      break;
    }
      
    default:
      log(`Unknown message: ${msg.type}`);
  }
}

// Button event handlers
document.getElementById('joinBtn').onclick = join;
document.getElementById('startBtn').onclick = start;
reconnectBtn.onclick = connectWS;
if (nextHandBtn) {
  nextHandBtn.onclick = async () => {
    try {
      nextHandBtn.disabled = true;
      const res = await fetch('/tables/default/next', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        log(`Cannot start next hand: ${err.error || res.statusText}`);
      } else {
        const data = await res.json();
        log(`Next hand: ${data.hand_id}`);
        if (showdownSummaryEl) showdownSummaryEl.style.display = 'none';
      }
    } catch (e) {
      log(`Next hand error: ${e}`);
    } finally {
      nextHandBtn.disabled = false;
      nextHandBtn.style.display = 'none';
    }
  };
}
if (restartBtn) {
  restartBtn.onclick = async () => {
    try {
      restartBtn.disabled = true;
      const res = await fetch('/tables/default/restart', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        log(`Restart failed: ${err.error || res.statusText}`);
      } else {
        const data = await res.json();
        log(`Session restarted: ${data.hand_id}`);
        if (nextHandBtn) nextHandBtn.style.display = 'none';
        restartBtn.style.display = 'none';
        if (showdownSummaryEl) showdownSummaryEl.style.display = 'none';
      }
    } catch (e) {
      log(`Restart error: ${e}`);
    } finally {
      restartBtn.disabled = false;
    }
  };
}

// Initialize
connectWS();
log('Poker Coach Alpha started');
updateSessionInfo(null, false);

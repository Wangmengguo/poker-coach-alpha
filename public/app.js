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
const analysisEl = document.getElementById('analysis'); // debug JSON inside drawer
const analysisDrawerEl = document.getElementById('analysisDrawer');
const drawerToggleBtn = document.getElementById('drawerToggleBtn');
const drawerHeroPosEl = document.getElementById('drawerHeroPos');
const drawerCoreMathEl = document.getElementById('drawerCoreMath');
const drawerHandTextureEl = document.getElementById('drawerHandTexture');
const drawerHandStrengthEl = document.getElementById('drawerHandStrength');
const drawerStatsEl = document.getElementById('drawerStats');
let lastPotMath = null;
let lastStats = null;
let lastBoardTexture = null;
let lastHandLabel = null;
let lastOuts = null;
let lastHandStrength = null;
let lastContext = null;
let drawerOpen = false;
let drawerUserPinnedClosed = false;

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

function openDrawer(auto = false) {
  if (!analysisDrawerEl) return;
  if (auto && drawerUserPinnedClosed) return;
  analysisDrawerEl.classList.remove('collapsed');
  drawerOpen = true;
}

function closeDrawer() {
  if (!analysisDrawerEl) return;
  analysisDrawerEl.classList.add('collapsed');
  drawerOpen = false;
}

function renderAnalysisDrawer() {
  if (!analysisDrawerEl) return;

  // Core Math
  if (drawerCoreMathEl) {
    drawerCoreMathEl.innerHTML = '';
    if (lastPotMath) {
      const { to_call, pot, spr } = lastPotMath;
      const p1 = document.createElement('p');
      p1.textContent = `To call: $${Number(to_call ?? 0)}`;
      const p2 = document.createElement('p');
      p2.textContent = `Pot: $${Number(pot ?? 0)}`;
      const p3 = document.createElement('p');
      p3.textContent = `SPR: ${Number(spr ?? 0).toFixed(2)}`;
      drawerCoreMathEl.appendChild(p1);
      drawerCoreMathEl.appendChild(p2);
      drawerCoreMathEl.appendChild(p3);
    } else {
      const p = document.createElement('p');
      p.textContent = 'Waiting for decision...';
      drawerCoreMathEl.appendChild(p);
    }
  }

  // Hand & Texture
  if (drawerHandTextureEl) {
    drawerHandTextureEl.innerHTML = '';
    const pHand = document.createElement('p');
    pHand.textContent = `Hand: ${lastHandLabel || '—'}`;
    drawerHandTextureEl.appendChild(pHand);

    const pTex = document.createElement('p');
    if (lastBoardTexture) {
      const flags = [];
      if (lastBoardTexture.paired) flags.push('paired');
      if (lastBoardTexture.monotone) flags.push('monotone');
      if (lastBoardTexture.two_tone) flags.push('two-tone');
      if (lastBoardTexture.straighty) flags.push('straighty');
      pTex.textContent = `Texture: ${flags.length ? flags.join(' · ') : 'normal'}`;
    } else {
      pTex.textContent = 'Texture: —';
    }
    drawerHandTextureEl.appendChild(pTex);

    const pOuts = document.createElement('p');
    if (lastOuts && lastOuts.outs > 0) {
      const parts = [];
      if (lastOuts.flush_draw) parts.push('flush draw');
      if (lastOuts.oesd) parts.push('OESD');
      if (lastOuts.combo) parts.push('combo');
      pOuts.textContent = `Draws: ${parts.join(' + ')} (${lastOuts.outs} outs)`;
    } else {
      pOuts.textContent = 'Draws: —';
    }
    drawerHandTextureEl.appendChild(pOuts);
  }

  // Hand Strength
  if (drawerHandStrengthEl) {
    drawerHandStrengthEl.innerHTML = '';
    const p = document.createElement('p');
    if (lastHandStrength && lastHandStrength.hand_strength_pct != null) {
      const raw = Number(lastHandStrength.hand_strength_pct);
      const approx = Number.isFinite(raw) ? Math.round(raw) : null;
      if (lastHandStrength.model === 'preflop_lookup') {
        p.textContent = approx != null ? `Preflop strength: ~${approx}%` : 'Preflop strength: —';
      } else {
        p.textContent = approx != null ? `Strength: ~${approx}%` : 'Strength: —';
      }
    } else if (lastHandStrength && lastHandStrength.reason === 'preflop_unavailable') {
      p.textContent = 'Strength: (preflop – not computed)';
    } else {
      p.textContent = 'Strength: —';
    }
    drawerHandStrengthEl.appendChild(p);

    if (lastHandStrength && lastHandStrength.degraded) {
      const p2 = document.createElement('p');
      p2.textContent = `Status: degraded (${lastHandStrength.reason || 'timeout'})`;
      drawerHandStrengthEl.appendChild(p2);
    } else if (!lastHandStrength || lastHandStrength.reason !== 'preflop_unavailable') {
      const p2 = document.createElement('p');
      p2.textContent = 'Estimate via Monte Carlo (approximate)';
      drawerHandStrengthEl.appendChild(p2);
    }
  }

  // Human Stats
  if (drawerStatsEl) {
    drawerStatsEl.innerHTML = '';
    if (lastStats) {
      const n = Number(lastStats.vpip_voluntary || 0);
      const d = Number(lastStats.vpip_opportunities || 0);
      const vpipPct = d > 0 ? Math.round((n * 100) / d) : 0;
      const r = Number(lastStats.pfr_raises || 0);
      const rd = Number(lastStats.pfr_opportunities || d || 0);
      const pfrPct = rd > 0 ? Math.round((r * 100) / rd) : 0;
      const agg = Number(lastStats.afq_agg || 0);
      const tot = Number(lastStats.afq_total || 0);
      const afqPct = tot > 0 ? Math.round((agg * 100) / tot) : 0;

      const p1 = document.createElement('p');
      p1.textContent = `VPIP: ${vpipPct}% (${n}/${d} hands)`;
      const p2 = document.createElement('p');
      p2.textContent = `PFR: ${pfrPct}% (${r}/${rd} hands)`;
      const p3 = document.createElement('p');
      p3.textContent = `AFq: ${afqPct}% (${agg}/${tot} actions)`;

      drawerStatsEl.appendChild(p1);
      drawerStatsEl.appendChild(p2);
      drawerStatsEl.appendChild(p3);
    } else {
      const p = document.createElement('p');
      p.textContent = 'No stats yet';
      drawerStatsEl.appendChild(p);
    }
  }

  // Hero position
  if (drawerHeroPosEl) {
    const pos = lastContext && lastContext.hero_position;
    drawerHeroPosEl.textContent = pos || '';
  }

  // Debug JSON
  if (analysisEl) {
    const debugObj = {
      pot_math: lastPotMath,
      board_texture: lastBoardTexture,
      hand: lastHandLabel,
      outs: lastOuts,
      stats: lastStats,
      context: lastContext,
      hand_strength: lastHandStrength,
    };
    analysisEl.textContent = JSON.stringify(debugObj, null, 2);
  }
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
      lastPotMath = null;
      lastStats = null;
      lastBoardTexture = null;
      lastHandLabel = null;
      lastOuts = null;
      lastHandStrength = null;
      lastContext = null;
      renderAnalysisDrawer();
      break;
      
    case 'prompt':
      renderActions(msg.legal_actions || []);
      log(`Your turn - ${msg.legal_actions?.length || 0} options`);
      try {
        const analysis = msg.analysis || {};
        lastPotMath = analysis.pot_math || null;
        lastStats = analysis.stats || null;
        lastBoardTexture = analysis.board_texture || null;
        lastHandLabel = analysis.hand && analysis.hand.label ? analysis.hand.label : null;
        lastOuts = analysis.outs || null;
        lastContext = analysis.context || null;
        lastHandStrength = null; // will be filled by async analysis message
        renderAnalysisDrawer();
        openDrawer(true);
      } catch (e) {
        // ignore
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
      // Auto-collapse drawer at hand end, but keep stats
      closeDrawer();
      break;
      
    case 'session_end':
      actionsEl.innerHTML = '';
      updateSessionInfo(null, false);
      if (nextHandBtn) nextHandBtn.style.display = 'none';
      if (restartBtn) restartBtn.style.display = 'inline-block';
      log(`Session ended: ${msg.reason}`);
      closeDrawer();
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
        lastHandStrength = hs;
        renderAnalysisDrawer();
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

if (drawerToggleBtn) {
  drawerToggleBtn.onclick = () => {
    if (drawerOpen) {
      closeDrawer();
      drawerUserPinnedClosed = true;
    } else {
      drawerUserPinnedClosed = false;
      openDrawer(false);
    }
  };
}

// Initialize
connectWS();
log('Poker Coach Alpha started');
updateSessionInfo(null, false);

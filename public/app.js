// DOM elements
const logEl = document.getElementById('log');
const actionsEl = document.getElementById('actions');
const handCountEl = document.getElementById('handCount');
const sessionStatusEl = document.getElementById('sessionStatus');
const potAmountEl = document.getElementById('potAmount');
const boardEl = document.getElementById('board');
const streetInfoEl = document.getElementById('streetInfo');
const reconnectBtn = document.getElementById('reconnectBtn');

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
    const stackEl = playerInfoEl.querySelector('.player-stack');
    const cardsEl = playerInfoEl.querySelector('.player-cards');
    
    // Find player for this seat
    const player = players.find(p => p.seat === seat);
    
    if (player) {
      nameEl.textContent = player.id;
      stackEl.textContent = `$${player.stack}`;
      
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
    } else {
      // Empty seat
      nameEl.textContent = 'Empty';
      stackEl.textContent = '$0';
      cardsEl.innerHTML = '';
      playerInfoEl.classList.remove('active', 'human');
    }
  }
}

function renderState(table) {
  updateSessionInfo(table.hand_id, true);
  renderPotAndBoard(table.pot, table.board, table.street);
  renderPlayers(table.players, table.to_act);
}

function renderActions(legal) {
  actionsEl.innerHTML = '';
  for (const a of legal) {
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
    } else if (a.type === 'raise_to') {
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
      break;
      
    case 'prompt':
      renderActions(msg.legal_actions || []);
      log(`Your turn - ${msg.legal_actions?.length || 0} options`);
      break;
      
    case 'showdown':
      const hands = (msg.players || []).map(p => 
        `${p.seat}:${p.id} [${(p.hole || []).join(' ')}]`
      ).join(' | ');
      log(`Showdown: ${msg.board?.join(' ') || 'no board'} | ${hands}`);
      break;
      
    case 'hand_end':
      actionsEl.innerHTML = '';
      const results = (msg.results || []).map(r => 
        `Seat ${r.seat}: ${r.delta >= 0 ? '+' : ''}$${r.delta}`
      ).join(', ');
      log(`Hand complete: ${results}`);
      break;
      
    case 'session_end':
      actionsEl.innerHTML = '';
      updateSessionInfo(null, false);
      log(`Session ended: ${msg.reason}`);
      break;
      
    case 'error':
      log(`Error: ${msg.message}`);
      if (msg.trace) {
        console.error('Server error trace:', msg.trace);
      }
      break;
      
    default:
      log(`Unknown message: ${msg.type}`);
  }
}

// Button event handlers
document.getElementById('joinBtn').onclick = join;
document.getElementById('startBtn').onclick = start;
reconnectBtn.onclick = connectWS;

// Initialize
connectWS();
log('Poker Coach Alpha started');
updateSessionInfo(null, false);

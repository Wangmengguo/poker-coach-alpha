const logEl = document.getElementById('log');
const stateEl = document.getElementById('state');
const actionsEl = document.getElementById('actions');
let ws;
let lastSnapshot = null;

function log(msg) {
  logEl.textContent += `${msg}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function renderState(table) {
  const players = table.players.map(p => `${p.seat}:${p.id} ${p.stack}${p.in_hand?'':' (out)'}`).join(' | ');
  const bets = Object.entries(table.bets).map(([s,b]) => `s${s}:${b}`).join(', ');
  stateEl.textContent = `hand ${table.hand_id}  street=${table.street}  pot=${table.pot}\nboard: ${table.board.join(' ')}\nplayers: ${players}\nbets: ${bets}\nto_act: ${table.to_act}`;
}

function renderActions(legal) {
  actionsEl.innerHTML = '';
  for (const a of legal) {
    const btn = document.createElement('button');
    if (a.type === 'call') btn.textContent = `Call ${a.amount}`;
    else if (a.type === 'check') btn.textContent = 'Check';
    else if (a.type === 'fold') btn.textContent = 'Fold';
    else if (a.type === 'raise_to') btn.textContent = `Raise to ${a.amount}`;
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
  ws = new WebSocket(`ws://${location.host}/ws/tables/default?player_id=human`);
  ws.onopen = () => log('WS connected');
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'snapshot') {
        lastSnapshot = msg;
        renderState(msg.table);
      } else if (msg.type === 'prompt') {
        renderActions(msg.legal_actions || []);
      } else if (msg.type === 'hand_end') {
        actionsEl.innerHTML = '';
        log(`Hand end: ${JSON.stringify(msg.results || [])}`);
      } else if (msg.type === 'error') {
        log(`Error: ${msg.message}`);
      }
    } catch (e) {
      log(`WS ← ${ev.data}`);
    }
  };
  ws.onclose = () => log('WS closed');
}

document.getElementById('joinBtn').onclick = join;
document.getElementById('startBtn').onclick = start;
connectWS();

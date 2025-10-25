const logEl = document.getElementById('log');
function log(msg) {
  logEl.textContent += `${msg}\n`;
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
  const ws = new WebSocket(`ws://${location.host}/ws/tables/default?player_id=human`);
  ws.onopen = () => log('WS connected');
ws.onmessage = (ev) => {
  log(`WS ← ${ev.data}`);
};
  ws.onclose = () => log('WS closed');
  // Example send:
  setTimeout(() => {
    ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: 'action', action_id: 'init', hand_id: 'h_00000', seat: 1, action: { type: 'check' } }));
  }, 1000);
}

document.getElementById('joinBtn').onclick = join;
document.getElementById('startBtn').onclick = start;
connectWS();

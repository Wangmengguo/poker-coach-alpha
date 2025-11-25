import { GameState } from './modules/state.js';
import { WebSocketManager } from './modules/websocket.js';
import { Renderer } from './modules/renderer.js';
import { ActionHandler } from './modules/actions.js';
import { AnalysisDrawer } from './modules/analysis.js';

const gameState = new GameState();
const renderer = new Renderer();
const wsManager = new WebSocketManager();
const actionHandler = new ActionHandler(renderer, gameState, wsManager);
const analysisDrawer = new AnalysisDrawer(renderer, gameState);

renderer.bindDrawerToggle();
actionHandler.bind();

wsManager.on('open', () => {
  gameState.setConnectionStatus('connected', 0);
  const reconnectBtn = document.getElementById('reconnectBtn');
  if (reconnectBtn) reconnectBtn.style.display = 'none';
  renderer.log('Connected to server');
  renderer.announce('Connected to server');
  renderer.renderConnectionStatus('connected');
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
});

wsManager.on('error', (error) => {
  renderer.log(`Connection error: ${error}`);
  renderer.announce('Connection error');
  renderer.renderConnectionStatus('failed');
});

wsManager.on('message', (msg) => {
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
      break;
    }
    case 'prompt': {
      const legal = msg.legal_actions || [];
      actionHandler.renderActions(legal);
      renderer.log(`Your turn - ${legal.length} options`);
      renderer.announce(`Your turn, ${legal.length} options`);
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
      renderer.closeDrawer();
      renderer.announce('Hand complete');
      break;
    }
    case 'session_end': {
      const actionsEl = document.getElementById('actions');
      if (actionsEl) actionsEl.innerHTML = '';
      renderer.updateSessionInfo(null, false);
      const nextHandBtn = document.getElementById('nextHandBtn');
      const restartBtn = document.getElementById('restartBtn');
      if (nextHandBtn) nextHandBtn.style.display = 'none';
      if (restartBtn) restartBtn.style.display = 'inline-block';
      renderer.log(`Session ended: ${msg.reason}`);
      renderer.closeDrawer();
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
      } catch (e) {
        // ignore
      }
      break;
    }
    default:
      renderer.log(`Unknown message: ${msg.type}`);
  }
});

gameState.setConnectionStatus('connecting', 0);
renderer.renderConnectionStatus('connecting');
wsManager.connect();
renderer.log('Poker Coach Alpha started');
renderer.updateSessionInfo(null, false);

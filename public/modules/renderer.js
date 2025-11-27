import { MAX_SEATS, HUMAN_PLAYER_ID } from '../utils/constants.js';
import { clearChildren, setText } from '../utils/dom.js';

/**
 * Renderer handles DOM reads/writes for table state and analysis drawer.
 * Phase 1 focuses on DOM caching and straightforward rendering.
 */
export class Renderer {
  constructor() {
    this.cached = {
      logEl: document.getElementById('log'),
      actionsEl: document.getElementById('actions'),
      handCountEl: document.getElementById('handCount'),
      sessionStatusEl: document.getElementById('sessionStatus'),
       connectionStatusEl: document.getElementById('connectionStatus'),
      potAmountEl: document.getElementById('potAmount'),
      boardEl: document.getElementById('board'),
      streetInfoEl: document.getElementById('streetInfo'),
      reconnectBtn: document.getElementById('reconnectBtn'),
      nextHandBtn: document.getElementById('nextHandBtn'),
      restartBtn: document.getElementById('restartBtn'),
      showdownSummaryEl: document.getElementById('showdownSummary'),
      announcerEl: document.getElementById('srAnnouncer'),
      analysisEl: document.getElementById('analysis'),
      analysisDrawerEl: document.getElementById('analysisDrawer'),
      drawerToggleBtn: document.getElementById('drawerToggleBtn'),
      drawerOpenBtn: document.getElementById('drawerOpenBtn'),
      drawerHeroPosEl: document.getElementById('drawerHeroPos'),
      drawerCoreMathEl: document.getElementById('drawerCoreMath'),
      drawerHandTextureEl: document.getElementById('drawerHandTexture'),
      drawerHandStrengthEl: document.getElementById('drawerHandStrength'),
      drawerStatsEl: document.getElementById('drawerStats'),
      seats: {},
    };

    for (let seat = 1; seat <= MAX_SEATS; seat += 1) {
      const container = document.querySelector(`[data-seat="${seat}"]`);
      if (!container) continue;
      const playerInfo = container.querySelector('.player-info');
      this.cached.seats[seat] = {
        container,
        playerInfo,
        nameEl: playerInfo?.querySelector('.player-name'),
        posEl: playerInfo?.querySelector('.player-pos'),
        stackEl: playerInfo?.querySelector('.player-stack'),
        cardsEl: playerInfo?.querySelector('.player-cards'),
        betEl: playerInfo?.querySelector('.player-bet'),
      };
    }

    this.drawerOpen = false;
    this.drawerUserPinnedClosed = false;
  }

  log(msg) {
    const { logEl } = this.cached;
    if (!logEl) return;
    const timestamp = new Date().toLocaleTimeString();
    logEl.textContent += `[${timestamp}] ${msg}\n`;
    logEl.scrollTop = logEl.scrollHeight;
  }

  announce(message) {
    const { announcerEl } = this.cached;
    if (!announcerEl) return;
    announcerEl.textContent = message;
  }

  /**
   * Show a temporary action notification near a player seat
   */
  showActionNotification(seat, text) {
    const cachedSeat = this.cached.seats[seat];
    if (!cachedSeat || !cachedSeat.container) return;

    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'action-notification';
    notification.textContent = text;
    notification.setAttribute('role', 'status');
    notification.setAttribute('aria-live', 'polite');

    // Position relative to seat
    cachedSeat.container.appendChild(notification);

    // Remove after animation
    setTimeout(() => {
      notification.classList.add('fade-out');
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 2000);
  }

  bindDrawerToggle() {
    const { drawerToggleBtn, drawerOpenBtn } = this.cached;

    // Close button inside drawer header
    if (drawerToggleBtn) {
      drawerToggleBtn.onclick = () => {
        this.closeDrawer();
        this.drawerUserPinnedClosed = true;
      };
    }

    // Floating open button (visible when drawer is closed)
    if (drawerOpenBtn) {
      drawerOpenBtn.onclick = () => {
        this.drawerUserPinnedClosed = false;
        this.openDrawer(false);
      };
    }
  }

  updateSessionInfo(handId, sessionActive) {
    const { handCountEl, sessionStatusEl, restartBtn } = this.cached;
    const handNum = handId ? handId.replace('h_', '').replace(/^0+/, '') || '1' : '-';
    setText(handCountEl, `Hand: ${handNum}`);
    if (sessionStatusEl) {
      sessionStatusEl.textContent = sessionActive ? 'Playing' : 'Waiting';
      sessionStatusEl.style.color = sessionActive ? '#4ade80' : '#94a3b8';
    }
    if (restartBtn) {
      restartBtn.style.display = sessionActive ? 'none' : 'inline-block';
    }
  }

  renderConnectionStatus(status) {
    const { connectionStatusEl } = this.cached;
    if (!connectionStatusEl) return;

    let label = 'Disconnected';
    let color = '#94a3b8';

    switch (status) {
      case 'connecting':
        label = 'Connecting';
        color = '#eab308';
        break;
      case 'connected':
        label = 'Connected';
        color = '#4ade80';
        break;
      case 'reconnecting':
        label = 'Reconnecting';
        color = '#f97316';
        break;
      case 'failed':
        label = 'Connection Failed';
        color = '#f97316';
        break;
      case 'disconnected':
      default:
        label = 'Disconnected';
        color = '#94a3b8';
        break;
    }

    connectionStatusEl.textContent = label;
    connectionStatusEl.style.color = color;
  }

  /**
   * Extract suit from card string (e.g., "Ah" -> "h", "Kd" -> "d")
   */
  getSuit(card) {
    if (!card || card.length < 2) return null;
    const suit = card.charAt(card.length - 1).toLowerCase();
    if (['h', 'd', 's', 'c'].includes(suit)) return suit;
    return null;
  }

  renderPotAndBoard(pot, board, street) {
    const { potAmountEl, boardEl, streetInfoEl } = this.cached;
    setText(potAmountEl, `$${pot}`);
    setText(streetInfoEl, street || '-');
    clearChildren(boardEl);
    if (board && board.length > 0) {
      board.forEach((card) => {
        const cardEl = document.createElement('div');
        cardEl.className = 'card';
        cardEl.textContent = card;
        const suit = this.getSuit(card);
        if (suit) {
          cardEl.dataset.suit = suit;
        }
        boardEl.appendChild(cardEl);
      });
    }
  }

  renderPlayers(table, lastSnapshot) {
    const players = table.players || [];
    const bets = (lastSnapshot?.table?.bets) || {};
    const positions = lastSnapshot?.table?.positions || {};

    for (let seat = 1; seat <= MAX_SEATS; seat += 1) {
      const cachedSeat = this.cached.seats[seat];
      if (!cachedSeat || !cachedSeat.playerInfo) continue;
      const { playerInfo, nameEl, posEl, stackEl, cardsEl, betEl } = cachedSeat;

      playerInfo.classList.remove('winner', 'loser');

      const player = players.find((p) => p.seat === seat);
      if (player) {
        setText(nameEl, player.id);
        setText(stackEl, `$${player.stack}`);
        if (posEl) {
          posEl.textContent = positions[String(seat)] || '';
        }

        playerInfo.classList.toggle('active', table.to_act === seat);
        playerInfo.classList.toggle('human', player.id === HUMAN_PLAYER_ID);

        clearChildren(cardsEl);
        if (player.hole && player.hole.length > 0) {
          player.hole.forEach((card) => {
            const cardEl = document.createElement('div');
            cardEl.className = card === '??' ? 'card hidden' : 'card';
            cardEl.textContent = card === '??' ? '?' : card;
            if (card !== '??') {
              const suit = this.getSuit(card);
              if (suit) {
                cardEl.dataset.suit = suit;
              }
            }
            cardsEl.appendChild(cardEl);
          });
        }

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
        setText(nameEl, 'Empty');
        if (posEl) posEl.textContent = '';
        setText(stackEl, '$0');
        clearChildren(cardsEl);
        if (betEl) {
          betEl.textContent = '';
          betEl.classList.remove('show');
        }
        playerInfo.classList.remove('active', 'human');
      }
    }
  }

  renderState(table, lastSnapshot) {
    this.updateSessionInfo(table.hand_id, true);
    this.renderPotAndBoard(table.pot, table.board, table.street);
    this.renderPlayers(table, lastSnapshot);
    const { showdownSummaryEl } = this.cached;
    if (showdownSummaryEl) showdownSummaryEl.style.display = 'none';
  }

  openDrawer(auto = false) {
    const { analysisDrawerEl } = this.cached;
    if (!analysisDrawerEl) return;
    if (auto && this.drawerUserPinnedClosed) return;
    analysisDrawerEl.classList.remove('collapsed');
    document.body.classList.add('drawer-open');
    this.drawerOpen = true;
  }

  closeDrawer() {
    const { analysisDrawerEl } = this.cached;
    if (!analysisDrawerEl) return;
    analysisDrawerEl.classList.add('collapsed');
    document.body.classList.remove('drawer-open');
    this.drawerOpen = false;
  }

  renderAnalysisDrawer(analysis) {
    const {
      drawerCoreMathEl,
      drawerHandTextureEl,
      drawerHandStrengthEl,
      drawerStatsEl,
      drawerHeroPosEl,
      analysisEl,
    } = this.cached;

    const {
      pot_math: lastPotMath,
      pot_extra: lastPotExtra,
      board_texture: lastBoardTexture,
      hand_label: lastHandLabel,
      outs: lastOuts,
      stats: lastStats,
      context: lastContext,
      hand_strength: lastHandStrength,
    } = analysis || {};

    // Core Math
    if (drawerCoreMathEl) {
      clearChildren(drawerCoreMathEl);
      if (lastPotMath) {
        const { to_call, pot, spr } = lastPotMath;
        const p1 = document.createElement('p');
        p1.textContent = `To call: $${Number(to_call ?? 0)}`;
        const p2 = document.createElement('p');
        p2.textContent = `Pot: $${Number(pot ?? 0)}`;
        const p3 = document.createElement('p');
        p3.textContent = `SPR: ${Number(spr ?? 0).toFixed(2)}`;
        const p4 = document.createElement('p');
        if (lastPotExtra && typeof lastPotExtra.pot_odds_pct === 'number') {
          p4.textContent = `Pot odds: ${Number(lastPotExtra.pot_odds_pct).toFixed(1)}%`;
        } else {
          p4.textContent = 'Pot odds: —';
        }
        drawerCoreMathEl.appendChild(p1);
        drawerCoreMathEl.appendChild(p2);
        drawerCoreMathEl.appendChild(p3);
        drawerCoreMathEl.appendChild(p4);
      } else {
        const p = document.createElement('p');
        p.textContent = 'Waiting for decision...';
        drawerCoreMathEl.appendChild(p);
      }
    }

    // Hand & Texture
    if (drawerHandTextureEl) {
      clearChildren(drawerHandTextureEl);
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
      clearChildren(drawerHandStrengthEl);
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
      clearChildren(drawerStatsEl);
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
         const hands = Number(lastStats.hands != null ? lastStats.hands : d);
         const style = lastStats.style || 'Unknown';

        const p1 = document.createElement('p');
        p1.textContent = `VPIP: ${vpipPct}% (${n}/${d} hands)`;
        const p2 = document.createElement('p');
        p2.textContent = `PFR: ${pfrPct}% (${r}/${rd} hands)`;
        const p3 = document.createElement('p');
        p3.textContent = `AFq: ${afqPct}% (${agg}/${tot} actions)`;
        const p4 = document.createElement('p');
        if (hands < 20) {
          p4.textContent = `Style: Unknown (${hands} hands, small sample)`;
        } else {
          p4.textContent = `Style: ${style} (${hands} hands)`;
        }

        drawerStatsEl.appendChild(p1);
        drawerStatsEl.appendChild(p2);
        drawerStatsEl.appendChild(p3);
        drawerStatsEl.appendChild(p4);
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
        pot_extra: lastPotExtra,
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

  highlightShowdown(msg) {
    const { showdownSummaryEl, potAmountEl, seats } = this.cached;
    if (!showdownSummaryEl) return;

    // Update board from showdown payload while keeping current pot
    let potValue = 0;
    if (potAmountEl && potAmountEl.textContent) {
      const cleaned = potAmountEl.textContent.replace('$', '');
      const num = Number(cleaned);
      potValue = Number.isFinite(num) ? num : 0;
    }
    this.renderPotAndBoard(potValue, msg.board || [], 'showdown');

    const sdPlayers = msg.players || [];
    const winners = msg.winners || [];
    const winnerSeats = new Set(winners.map((w) => w.seat));

    // Clear previous winner/loser classes
    for (let seat = 1; seat <= MAX_SEATS; seat += 1) {
      const cachedSeat = seats[seat];
      if (!cachedSeat || !cachedSeat.playerInfo) continue;
      cachedSeat.playerInfo.classList.remove('winner', 'loser');
    }

    // Reveal showdown hands and mark winners/losers
    for (const p of sdPlayers) {
      const cachedSeat = seats[p.seat];
      if (!cachedSeat || !cachedSeat.playerInfo || !cachedSeat.cardsEl) continue;
      const { playerInfo, cardsEl } = cachedSeat;
      cardsEl.innerHTML = '';
      (p.hole || []).forEach((card) => {
        const cardEl = document.createElement('div');
        cardEl.className = 'card';
        cardEl.textContent = card;
        const suit = this.getSuit(card);
        if (suit) {
          cardEl.dataset.suit = suit;
        }
        cardsEl.appendChild(cardEl);
      });
      if (winnerSeats.has(p.seat)) {
        playerInfo.classList.add('winner');
      } else {
        playerInfo.classList.add('loser');
      }
    }

    // Build and show summary panel
    if (winners.length > 0) {
      const winnersTxt = winners
        .map((w) => `Seat ${w.seat} (${w.rank}) [${(w.best5 || []).join(' ')}]`)
        .join(' | ');
      const losersTxt = sdPlayers
        .filter((p) => !winnerSeats.has(p.seat))
        .map((p) => `Seat ${p.seat} [${(p.hole || []).join(' ')}]`)
        .join(' | ');
      showdownSummaryEl.innerHTML = `
      <div class="winners">${winnersTxt ? 'Winners: ' + winnersTxt : 'Showdown'}</div>
      ${losersTxt ? `<div class="losers">Losers: ${losersTxt}</div>` : ''}
    `;
      showdownSummaryEl.style.display = 'block';
    }
  }
}

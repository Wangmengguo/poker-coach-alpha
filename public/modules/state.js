import { DEFAULT_TABLE_ID, HUMAN_PLAYER_ID } from '../utils/constants.js';

/**
 * Minimal GameState for Phase 1.
 * Centralises snapshot, analysis and connection status in one place.
 */
export class GameState {
  constructor() {
    this.snapshot = null;
    this.analysis = {
      pot_math: null,
      pot_extra: null,
      board_texture: null,
      hand_label: null,
      outs: null,
      stats: null,
      context: null,
      hand_strength: null,
      lifetime_stats: null,
      range_equity: null,
    };
    this.connection = { status: 'disconnected', retryCount: 0 };
    this.legalActions = [];
    this.lifetimeBase = this._loadLifetimeBase();
    this.sessionCommitted = false;
  }

  updateSnapshot(snapshot) {
    // Shallow copy to avoid accidental external mutation
    this.snapshot = snapshot ? { ...snapshot } : null;
  }

  updateAnalysis(partial) {
    this.analysis = { ...this.analysis, ...partial };
    this._recomputeLifetimeStats();
  }

  setConnectionStatus(status, retryCount = this.connection.retryCount) {
    this.connection = { status, retryCount };
  }

  setLegalActions(actions) {
    this.legalActions = Array.isArray(actions) ? actions : [];
  }

  getLegalActions() {
    return this.legalActions;
  }

  getTable() {
    return this.snapshot?.table ?? null;
  }

  getHeroSeat() {
    const table = this.getTable();
    if (!table) return null;
    const players = table.players || [];
    const hero = players.find((p) => p.id === HUMAN_PLAYER_ID);
    return hero ? hero.seat : null;
  }

  getTableId() {
    const table = this.getTable();
    return table?.table_id || DEFAULT_TABLE_ID;
  }

  // ----- Lifetime stats persistence (cross-session human style) -----

  _emptyLifetimeBase() {
    return {
      vpip_voluntary: 0,
      vpip_opportunities: 0,
      pfr_raises: 0,
      afq_agg: 0,
      afq_total: 0,
    };
  }

  _loadLifetimeBase() {
    try {
      if (typeof window === 'undefined' || !window.localStorage) {
        return this._emptyLifetimeBase();
      }
      const raw = window.localStorage.getItem('pokerCoachLifetimeStats_v1');
      if (!raw) return this._emptyLifetimeBase();
      const data = JSON.parse(raw);
      const base = this._emptyLifetimeBase();
      for (const key of Object.keys(base)) {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
          const v = Number(data[key]);
          base[key] = Number.isFinite(v) ? v : 0;
        }
      }
      return base;
    } catch {
      return this._emptyLifetimeBase();
    }
  }

  _saveLifetimeBase() {
    try {
      if (typeof window === 'undefined' || !window.localStorage) return;
      const payload = JSON.stringify(this.lifetimeBase);
      window.localStorage.setItem('pokerCoachLifetimeStats_v1', payload);
    } catch {
      // ignore persistence errors
    }
  }

  _recomputeLifetimeStats() {
    const session = this.analysis.stats;
    const base = this.lifetimeBase || this._emptyLifetimeBase();

    const vpipVol = (session?.vpip_voluntary || 0) + base.vpip_voluntary;
    const vpipOpp = (session?.vpip_opportunities || 0) + base.vpip_opportunities;
    const pfrRaises = (session?.pfr_raises || 0) + base.pfr_raises;
    const afqAgg = (session?.afq_agg || 0) + base.afq_agg;
    const afqTotal = (session?.afq_total || 0) + base.afq_total;

    const hands = vpipOpp;

    if (hands <= 0 && afqTotal <= 0) {
      this.analysis.lifetime_stats = null;
      return;
    }

    const vpipPct = vpipOpp > 0 ? (vpipVol * 100.0) / vpipOpp : 0;
    const pfrPct = vpipOpp > 0 ? (pfrRaises * 100.0) / vpipOpp : 0;
    const afqPct = afqTotal > 0 ? (afqAgg * 100.0) / afqTotal : 0;

    let style = 'Unknown';
    if (hands > 0) {
      const loose = vpipPct >= 28.0;
      const tight = vpipPct <= 18.0;
      const aggressive = afqPct >= 45.0;
      const passive = afqPct <= 30.0;
      if (tight && aggressive) {
        style = 'Tight-Aggressive';
      } else if (tight && passive) {
        style = 'Tight-Passive';
      } else if (loose && aggressive) {
        style = 'Loose-Aggressive';
      } else if (loose && passive) {
        style = 'Loose-Passive';
      }
    }

    this.analysis.lifetime_stats = {
      vpip_pct: Number(vpipPct.toFixed(1)),
      vpip_voluntary: vpipVol,
      vpip_opportunities: vpipOpp,
      pfr_pct: Number(pfrPct.toFixed(1)),
      pfr_raises: pfrRaises,
      pfr_opportunities: vpipOpp,
      afq_pct: Number(afqPct.toFixed(1)),
      afq_agg: afqAgg,
      afq_total: afqTotal,
      hands,
      style,
    };
  }

  commitLifetimeStats() {
    const session = this.analysis.stats;
    if (!session || this.sessionCommitted) {
      return;
    }
    const base = this.lifetimeBase || this._emptyLifetimeBase();
    base.vpip_voluntary += Number(session.vpip_voluntary || 0);
    base.vpip_opportunities += Number(session.vpip_opportunities || 0);
    base.pfr_raises += Number(session.pfr_raises || 0);
    base.afq_agg += Number(session.afq_agg || 0);
    base.afq_total += Number(session.afq_total || 0);
    this.lifetimeBase = base;
    this.sessionCommitted = true;
    this._saveLifetimeBase();
    this._recomputeLifetimeStats();
  }

  resetSessionStats() {
    this.analysis = {
      ...this.analysis,
      stats: null,
    };
    this.sessionCommitted = false;
    this._recomputeLifetimeStats();
  }
}

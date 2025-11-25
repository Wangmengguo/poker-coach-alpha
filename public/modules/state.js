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
    };
    this.connection = { status: 'disconnected', retryCount: 0 };
    this.legalActions = [];
  }

  updateSnapshot(snapshot) {
    // Shallow copy to avoid accidental external mutation
    this.snapshot = snapshot ? { ...snapshot } : null;
  }

  updateAnalysis(partial) {
    this.analysis = { ...this.analysis, ...partial };
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
}

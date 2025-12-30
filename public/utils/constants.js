// Shared frontend constants for the Poker Coach Alpha client.

export const MAX_SEATS = 6;
export const HUMAN_PLAYER_ID = 'human';
export const DEFAULT_TABLE_ID = 'default';

/**
 * Resolve the deployment base path for this app.
 * - Prefer <meta name="app-base" content="/cards">
 * - Fallback: infer from the first path segment (e.g. '/cards', '/poker')
 * Returns '' or a string like '/<prefix>' (no trailing slash).
 */
export function getAppBase() {
  try {
    const meta = document.querySelector('meta[name="app-base"]');
    const raw = meta ? String(meta.getAttribute('content') || '').trim() : '';
    if (raw) {
      let base = raw;
      if (base === '/') base = '';
      if (base && !base.startsWith('/')) base = `/${base}`;
      base = base.replace(/\/+$/, '');
      return base;
    }

    // Infer from URL path. Example deployments:
    // - Root:              /public/app.js          => base ''
    // - Prefixed (cards):  /cards/public/app.js    => base '/cards'
    // - Prefixed (poker):  /poker/public/app.js    => base '/poker'
    const parts = String(location.pathname || '')
      .split('/')
      .filter(Boolean);
    const first = parts[0] || '';
    // If we're already at root endpoints, don't treat them as a base prefix.
    const reserved = new Set(['public', 'tables', 'ws', 'settings']);
    if (!first || reserved.has(first)) return '';
    return `/${first}`;
  } catch (e) {
    return '';
  }
}

/**
 * Prefix an absolute path (e.g. '/tables') with app base (e.g. '/cards').
 */
export function withBase(path) {
  const base = getAppBase();
  const p = String(path || '').startsWith('/') ? String(path || '') : `/${String(path || '')}`;
  return `${base}${p}`;
}

/**
 * Build an absolute ws/wss URL under the base path.
 */
export function wsAbsoluteUrl(path) {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${location.host}${withBase(path)}`;
}


// Lightweight DOM utility helpers for the Poker Coach Alpha frontend.
// Phase 1 keeps this minimal; extend only when there is a clear reuse case.

/**
 * Set text content on an element if the element exists.
 */
export function setText(el, text) {
  if (!el) return;
  el.textContent = text;
}

/**
 * Toggle element visibility using display.
 */
export function setVisible(el, visible, displayValue = 'inline-block') {
  if (!el) return;
  el.style.display = visible ? displayValue : 'none';
}

/**
 * Remove all child nodes from an element.
 */
export function clearChildren(el) {
  if (!el) return;
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
}


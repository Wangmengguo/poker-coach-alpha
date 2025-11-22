# Work Log

Date: 2025-11-22

- Phase 1 (P0) completed:
  - Fixed call EV to return net EV; `compute_pot_math` now exposes `effective_stack`; added pot_odds computation and front-end display; engine injects `compose_analysis` payload into Prompt.
- Phase 2 partially done:
  - Added `DecisionContext` / `compose_analysis`, wired into engine; added a minimal integration test; kept outs as dict for UI compatibility.
- Phase 3 bootstrapped:
  - Added `ranges.py` with non-empty default ranges; implemented `compute_equity_vs_range` (HU Monte Carlo vs range) plus a basic test (AA vs 72o).
- Tests:
  - New/updated tests added; pytest not run on this machine (pytest not installed).

- Outs / draws fixes (MVP):
  - Updated `compute_outs` to add a simple gutshot detection (4 outs when hero+board are one rank short of a 5-long straight window involving hero), restrict draw detection to flop/turn only, and include a `gutshot` flag in the outs payload; added `test_compute_outs_gutshot_simple` to cover the 78 vs TJ gutshot scenario.

from __future__ import annotations

import hashlib
import hmac
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from pokerkit import NoLimitTexasHoldem
from pokerkit.state import Automation, Mode, State

from .bot_manager import BotManager
from .analysis.core import compute_pot_math


def _card_to_str(card) -> str:
    s = str(card)
    return s


# Build automations with graceful fallback across pokerkit versions
_AUTO_NAMES = [
    "ANTE_POSTING",
    "BET_COLLECTION",
    "BLIND_OR_STRADDLE_POSTING",
    "CARD_BURNING",
    "HOLE_DEALING",
    "BOARD_DEALING",
    # Ensure all-in runouts proceed automatically when supported
    "RUNOUT_COUNT_SELECTION",
    "HOLE_CARDS_SHOWING_OR_MUCKING",
    "HAND_KILLING",
    "CHIPS_PUSHING",
    "CHIPS_PULLING",
]
automations = tuple(getattr(Automation, n) for n in _AUTO_NAMES if hasattr(Automation, n))


@dataclass
class EngineConfig:
    seats: int = 6
    sb: int = 1
    bb: int = 2
    starting_stack: int = 400  # chips (≈200bb at 1/2)
    human_seat: int = 1  # 1-indexed
    max_hands: int = 100
    session_id: str = "default"  # for deterministic RNG


class TableEngine:
    def __init__(self, config: EngineConfig) -> None:
        self.cfg = config
        self.hand_index = 0
        self.session_active = False
        self.state: Optional[State] = None
        # Stacks per original seat (0-indexed internally). Persist across hands.
        self.seat_stacks: List[int] = [self.cfg.starting_stack] * self.cfg.seats
        # Active-seat mapping for current hand: state index -> original seat index
        self.seat_map_active: List[int] = list(range(self.cfg.seats))
        self.hand_start_seat_stacks: Optional[List[int]] = None
        self.sequence_number = 0
        self.bot_manager = BotManager(config.session_id)
        self.player_ids: List[str] = [
            ("human" if i + 1 == self.cfg.human_seat else f"bot{i+1}")
            for i in range(self.cfg.seats)
        ]
        # Track folds within a hand by current state index (set/reset each hand)
        self.folded_flags: Optional[List[bool]] = None
        # Persist hole cards for the current hand so we can reveal mucked losers at showdown
        self.hand_hole_cards: Optional[Dict[int, List[str]]] = None
        # Display/state metadata
        self.button_seat: int = 1

    def start_session(self) -> None:
        # Reset session state
        self.session_active = True
        self.hand_index = 0
        self.sequence_number = 0
        self.button_seat = 1
        self.seat_stacks = [self.cfg.starting_stack] * self.cfg.seats
        # Start the first hand
        self._start_new_hand()

    def restart_session(self, new_session_id: Optional[str] = None) -> None:
        """Restart a fresh session with initial stacks and optional new session id."""
        if new_session_id:
            self.cfg.session_id = new_session_id
            self.bot_manager.reset_for_new_session(new_session_id)
        self.start_session()

    def _generate_hand_seed(self) -> int:
        """Generate deterministic RNG seed for current hand."""
        key = f"{self.cfg.session_id}_hand_{self.hand_index}".encode("utf-8")
        # Use HMAC for cryptographically secure deterministic seed
        secret_key = b"poker_coach_alpha"  # In production, use proper secret
        hash_digest = hmac.new(secret_key, key, hashlib.sha256).digest()
        return int.from_bytes(hash_digest[:4], byteorder="big")

    def next_sequence(self) -> int:
        """Get next sequence number for message ordering."""
        self.sequence_number += 1
        return self.sequence_number

    # ---------- Seating helpers ----------
    def _active_seats(self) -> List[int]:
        """List of seat indices (0-based) with positive stacks."""
        return [i for i, s in enumerate(self.seat_stacks) if s > 0]

    def _rotate_to_button(self, seats: List[int], button_seat: int) -> List[int]:
        """Rotate seats so that the first element equals button_seat (1-based)."""
        if not seats:
            return []
        btn_idx0 = button_seat - 1
        if btn_idx0 not in seats:
            # If button seat is busted, move button to the next active seat clockwise
            # Find the minimal positive distance clockwise
            if seats:
                # choose the first seat with index >= btn_idx0, else wrap to first
                after = [s for s in seats if s >= btn_idx0]
                btn_idx0 = after[0] if after else seats[0]
        # Rotate so that btn_idx0 is first
        k = seats.index(btn_idx0)
        return seats[k:] + seats[:k]

    def _next_active_seat(self, cur_button_seat: int) -> int:
        """Return next button seat (1-based) skipping busted seats."""
        if not any(s > 0 for s in self.seat_stacks):
            return cur_button_seat
        # Move at least one step forward
        for step in range(1, self.cfg.seats + 1):
            seat = ((cur_button_seat - 1 + step) % self.cfg.seats) + 1
            if self.seat_stacks[seat - 1] > 0:
                return seat
        return cur_button_seat

    def _seat_to_state_index(self, seat: int) -> Optional[int]:
        """Map original seat (1-based) to current state index, if active."""
        try:
            return self.seat_map_active.index(seat - 1)
        except ValueError:
            return None

    def _state_index_to_seat(self, idx: int) -> int:
        """Map current state index to original seat (1-based)."""
        return self.seat_map_active[idx] + 1

    def _start_new_hand(self) -> None:
        # Build active seating order for this hand starting from button
        active = self._active_seats()
        # If fewer than 2 active players, don't start a new hand here; let caller handle end
        if len(active) < 2:
            self.state = None
            return

        # Rotate seats so SB is first for pokerkit's expected ordering (SB, BB, ...)
        order_btn_first = self._rotate_to_button(active, self.button_seat)
        if order_btn_first:
            self.seat_map_active = order_btn_first[1:] + order_btn_first[:1]
        else:
            self.seat_map_active = []
        stacks = [int(self.seat_stacks[s]) for s in self.seat_map_active]
        # Reset per-hand fold tracking
        self.folded_flags = [False] * len(stacks)
        # Reset per-hand hole card cache
        self.hand_hole_cards = {}

        # Generate deterministic seed for this hand
        hand_seed = self._generate_hand_seed()

        # Create state with only active players
        self.state = NoLimitTexasHoldem.create_state(
            automations,
            False,  # ante trimming off
            0,  # no antes
            (self.cfg.sb, self.cfg.bb),  # blinds
            self.cfg.bb,  # min bet equals big blind for NLHE
            stacks,
            len(stacks),
            mode=Mode.CASH_GAME,
        )

        # Set deterministic seed for this hand
        if hasattr(self.state, "rng") and hasattr(self.state.rng, "seed"):
            self.state.rng.seed(hand_seed)

        # Record seat stacks snapshot at hand start
        self.hand_start_seat_stacks = list(self.seat_stacks)
        self.hand_index += 1

    # ---------- Derived views ----------
    def _amount_to_call(self, idx: int) -> int:
        assert self.state is not None
        mx = max(self.state.bets)
        return max(0, mx - self.state.bets[idx])

    def _min_bet(self) -> int:
        # min bet is bb provided at game creation
        return self.cfg.bb

    def _max_bet_to(self, idx: int) -> int:
        assert self.state is not None
        # Total the player can put in this round (bet so far + stack)
        return self.state.bets[idx] + self.state.stacks[idx]

    def _try_raise_to(self, amount_to: int) -> bool:
        assert self.state is not None
        try_state = deepcopy(self.state)
        try:
            try_state.complete_bet_or_raise_to(amount_to)
            return True
        except Exception:
            return False

    def legal_actions(self) -> List[Dict]:
        assert self.state is not None
        i = self.state.turn_index
        if i is None:
            return []
        actions: List[Dict] = []
        to_call = self._amount_to_call(i)
        if to_call == 0:
            actions.append({"type": "check"})
        else:
            actions.append({"type": "call", "amount": to_call})
            actions.append({"type": "fold"})

        # Pot-based raise candidates (validate via simulation)
        max_bet = max(self.state.bets)
        # Compute pot amount; include current pot and bets if available
        try:
            pot_amt = int(sum(self.state.pot_amounts))  # type: ignore[attr-defined]
        except Exception:
            pot_amt = 0
        fractions = [1 / 3, 1 / 2, 2 / 3, 1.0, 2.0]
        candidates: List[int] = []
        for f in fractions:
            try:
                target = max_bet + int(round((pot_amt + to_call) * f))
                candidates.append(target)
            except Exception:
                continue
        # Always consider all-in as a candidate
        try:
            candidates.append(self._max_bet_to(i))
        except Exception:
            pass

        for amt in sorted(set(candidates)):
            if amt <= max_bet:
                continue
            if self._try_raise_to(amt):
                actions.append({"type": "raise_to", "amount": int(amt)})

        # Provide a custom raise range using min/max bounds validated by simulation
        try:
            # Lower bound: smallest legal raise-to strictly greater than current max bet
            low = max_bet + 1
            # Upper bound: player's maximum bet-to (bet so far + stack)
            high = self._max_bet_to(i)
            min_to: Optional[int] = None
            max_to: Optional[int] = None
            if high is not None and high > low:
                # Find minimum legal raise-to
                # Iterate upward with a safe cap
                cap = min(high, low + 5000)  # safety cap
                for a in range(low, cap + 1):
                    if self._try_raise_to(a):
                        min_to = a
                        break
                # Find maximum legal raise-to (prefer high -> down)
                for a in range(high, (min_to or low) - 1, -1):
                    if self._try_raise_to(a):
                        max_to = a
                        break
            if min_to is not None and max_to is not None and min_to <= max_to:
                actions.append({"type": "raise_to", "min": int(min_to), "max": int(max_to)})
        except Exception:
            # If we fail to compute range, silently skip
            pass

        return actions

    def apply_action(self, action: Dict) -> None:
        assert self.state is not None
        t = action.get("type")
        if t in ("check", "call"):
            self.state.check_or_call()
        elif t == "fold":
            # Mark folded seat for showdown filtering
            try:
                idx = self.state.turn_index
                if idx is not None and self.folded_flags is not None and 0 <= idx < len(self.folded_flags):
                    self.folded_flags[idx] = True
            except Exception:
                pass
            self.state.fold()
        elif t == "raise_to":
            amt = int(action.get("amount", 0))
            self.state.complete_bet_or_raise_to(amt)
        else:
            raise ValueError(f"Unknown action type: {t}")

    def is_hand_over(self) -> bool:
        assert self.state is not None
        return not self.state.status

    def should_end_session(self) -> Tuple[bool, str]:
        """Check if session should end and return reason."""
        if not self.session_active:
            return True, "session_inactive"

        if self.hand_index >= self.cfg.max_hands:
            return True, "max_hands"

        # Use persistent seat_stacks to decide bust status
        stacks = list(self.seat_stacks)
        human_idx = self.cfg.human_seat - 1
        if 0 <= human_idx < len(stacks) and stacks[human_idx] <= 0:
            return True, "player_busted"

        # End if all bots are busted (<=0)
        bot_indices = [i for i in range(self.cfg.seats) if (i + 1) != self.cfg.human_seat]
        if bot_indices and all(stacks[i] <= 0 for i in bot_indices):
            return True, "bots_busted"

        # Also stop if fewer than 2 active players remain
        if sum(1 for s in stacks if s > 0) < 2:
            # Should have been caught by bots_busted or player_busted above, but keep safe
            return True, "insufficient_players"

        return False, ""

    def build_table_snapshot(self) -> Dict:
        assert self.state is not None
        # Build lookup from state index -> seat number
        seat_lookup: Dict[int, int] = {
            i: self._state_index_to_seat(i) for i in range(len(self.seat_map_active))
        }

        # Players payload in fixed seat order 1..seats
        players: List[Dict] = []
        statuses = list(getattr(self.state, "statuses", []) or [])
        hole_cards = list(getattr(self.state, "hole_cards", []) or [])
        hole_statuses = list(getattr(self.state, "hole_card_statuses", []) or [])
        # Update per-hand hole card cache (raw values) when known
        try:
            if self.hand_hole_cards is not None:
                for i, hc in enumerate(hole_cards):
                    if hc:
                        self.hand_hole_cards[i] = [str(c) for c in hc]
        except Exception:
            pass

        for seat in range(1, self.cfg.seats + 1):
            state_idx = self._seat_to_state_index(seat)
            if state_idx is not None:
                # Active seat in this hand
                is_human = seat == self.cfg.human_seat
                if is_human:
                    hole = [str(c) for c in (hole_cards[state_idx] or [])]
                else:
                    hole = []
                    for c, up in zip(hole_cards[state_idx] or [], hole_statuses[state_idx] or []):
                        hole.append(str(c) if up else "??")
                players.append(
                    {
                        "seat": seat,
                        "id": self.player_ids[seat - 1],
                        "stack": int(self.state.stacks[state_idx]),
                        "in_hand": bool(statuses[state_idx]) if state_idx < len(statuses) else True,
                        "hole": hole,
                    }
                )
            else:
                # Busted seat (not in current hand)
                players.append(
                    {
                        "seat": seat,
                        "id": self.player_ids[seat - 1],
                        "stack": int(self.seat_stacks[seat - 1]),
                        "in_hand": False,
                        "hole": [],
                    }
                )

        # Flatten full board across streets (include all flop cards)
        board: List[str] = []
        for cards in self.state.board_cards:
            if cards:
                for c in cards:
                    board.append(_card_to_str(c))
        pot = int(sum(self.state.pot_amounts)) if hasattr(self.state, "pot_amounts") else 0

        # Bets keyed by seat number
        bets: Dict[str, int] = {}
        for i, b in enumerate(self.state.bets):
            bets[str(seat_lookup.get(i, i + 1))] = int(b)

        to_act_state_idx = self.state.turn_index
        to_act_seat = None if to_act_state_idx is None else seat_lookup.get(to_act_state_idx)

        last_op = None
        if getattr(self.state, "operations", None):
            op = self.state.operations[-1]
            last_op = op.__class__.__name__
        return {
            "table_id": "default",
            "hand_id": f"h_{self.hand_index:05d}",
            "button_seat": self.button_seat,
            "blinds": {"sb": self.cfg.sb, "bb": self.cfg.bb},
            "players": players,
            "street": self._street_name(),
            "board": board,
            "pot": pot,
            "bets": bets,
            "to_act": to_act_seat,
            "legal_actions": self.legal_actions(),
            "last_op": last_op,
            "positions": self._positions_map(),
        }

    def _street_name(self) -> str:
        assert self.state is not None
        idx = self.state.street_index
        if idx is None:
            return "showdown" if not self.state.status else "between"
        return ["preflop", "flop", "turn", "river"][min(idx, 3)]

    def _positions_map(self) -> Dict[str, str]:
        labels_6max = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
        pos: Dict[str, str] = {}
        # Assign positions clockwise starting from button_seat
        for offset in range(self.cfg.seats):
            seat = ((self.button_seat - 1 + offset) % self.cfg.seats) + 1
            label = labels_6max[offset] if offset < len(labels_6max) else f"P{offset}"
            pos[str(seat)] = label
        return pos

    def start_next_hand(self) -> Tuple[bool, str]:
        """Start next hand if session active and not ended.
        Returns (ok, reason). If not ok, reason explains why.
        """
        if not self.session_active:
            return False, "session_inactive"
        # Check termination before starting a new hand
        should_end, reason = self.should_end_session()
        if should_end:
            self.session_active = False
            return False, reason

        # Rotate button to next active seat and start new hand
        self.button_seat = self._next_active_seat(self.button_seat)
        self._start_new_hand()
        if self.state is None:
            # Could not start due to insufficient players
            self.session_active = False
            return False, "insufficient_players"
        return True, ""

    # Advance loop applying bot actions until human prompt or hand end
    def advance(self, human_seat: int) -> Tuple[List[Dict], Optional[Dict]]:
        assert self.state is not None
        messages: List[Dict] = []
        prompt: Optional[Dict] = None
        # Iterate until human turn or hand ends
        guard = 0
        while True:
            guard += 1
            if guard > 500:  # safety
                break
            snap = self.build_table_snapshot()
            seq = self.next_sequence()
            messages.append({"type": "snapshot", "seq": seq, "table": snap})

            # If no one can act, try to advance automations (deal/runout/showdown)
            if self.state.turn_index is None and self.state.status:
                # Keep nudging the engine forward within this tick until either
                # a player must act or the hand ends. Prefer calling automate/no_operation
                # repeatedly with a hard cap to avoid infinite loops.
                inner_guard = 0
                while self.state.turn_index is None and self.state.status:
                    inner_guard += 1
                    if inner_guard > 200:
                        break
                    progressed = False

                    # Prefer built-in automation drivers first
                    for meth in ("automate", "no_operation", "advance"):
                        fn = getattr(self.state, meth, None)
                        if callable(fn):
                            try:
                                fn()
                                progressed = True
                                break
                            except Exception:
                                continue

                    # If still not progressed, try stage helpers
                    if not progressed:
                        # Try to select single runout (if needed)
                        sel = getattr(self.state, "select_runout_count", None)
                        if callable(sel):
                            try:
                                sel(1)
                                progressed = True
                            except Exception:
                                pass
                    if not progressed:
                        for meth in (
                            "collect_bets",
                            "burn_card",
                            "deal_board_cards",
                            "deal_board",
                            "show_or_muck_hole_cards",
                            "show_hole_cards_or_muck",
                            "hole_cards_show_or_muck",
                            "push_chips",
                            "pull_chips",
                        ):
                            fn = getattr(self.state, meth, None)
                            if callable(fn):
                                try:
                                    fn()
                                    progressed = True
                                    break
                                except Exception:
                                    continue

                    # As a last resort in HoleCardsShowingOrMucking, force show for all
                    if not progressed and getattr(self.state, "operations", None):
                        try:
                            if (
                                self.state.operations[-1].__class__.__name__
                                == "HoleCardsShowingOrMucking"
                            ):
                                statuses = list(getattr(self.state, "statuses", []) or [])
                                for i, alive in enumerate(statuses):
                                    if not alive:
                                        continue
                                    for meth in (
                                        "show_or_muck_hole_cards",
                                        "show_hole_cards_or_muck",
                                        "hole_cards_show_or_muck",
                                    ):
                                        fn = getattr(self.state, meth, None)
                                        if callable(fn):
                                            try:
                                                fn(i, True)
                                                progressed = True
                                                break
                                            except Exception:
                                                try:
                                                    fn(i)
                                                    progressed = True
                                                    break
                                                except Exception:
                                                    continue
                                    if progressed:
                                        break
                        except Exception:
                            pass

                    if not progressed:
                        break
                # After inner stepping, loop back to emit a fresh snapshot
                continue

            if self.is_hand_over():
                # Emit showdown info (full board + revealed holes)
                try:
                    board_cards = []
                    for cards in getattr(self.state, "board_cards", []) or []:
                        for c in cards or []:
                            board_cards.append(c)
                    board_strs = [_card_to_str(c) for c in board_cards]

                    statuses = list(
                        getattr(self.state, "statuses", [True] * len(self.seat_map_active)) or []
                    )
                    # Include all players who did NOT fold (even if they lost at showdown)
                    folded = list(self.folded_flags or [False] * len(self.seat_map_active))
                    sd_players = []
                    for i in range(len(self.seat_map_active)):
                        # Consider a player part of showdown if they were not marked folded
                        in_showdown = not (folded[i])
                        if not in_showdown:
                            continue  # hide folded
                        seat_num = self._state_index_to_seat(i)
                        # Prefer live state's hole cards; fallback to cached dealt cards for mucked players
                        live_holes = [
                            str(c) for c in getattr(self.state, "hole_cards", [])[i] or []
                        ]
                        if not live_holes:
                            try:
                                live_holes = list((self.hand_hole_cards or {}).get(i, []))
                            except Exception:
                                live_holes = []
                        sd_players.append(
                            {
                                "seat": seat_num,
                                "id": self.player_ids[seat_num - 1],
                                "hole": live_holes,
                                "in_hand": bool(statuses[i]),
                            }
                        )

                    winners_payload: List[Dict] = []
                    try:
                        winners_payload = self._compute_showdown_winners(board_cards)
                        # Remap winner seats to original seat numbers
                        for w in winners_payload:
                            w["seat"] = self._state_index_to_seat(w["seat"] - 1)
                    except Exception:
                        winners_payload = []

                    messages.append(
                        {
                            "type": "showdown",
                            "hand_id": f"h_{self.hand_index:05d}",
                            "board": board_strs,
                            "players": sd_players,
                            "winners": winners_payload or None,
                        }
                    )
                except Exception:
                    pass

                # Update persistent seat stacks from state result
                try:
                    for i, s in enumerate(self.state.stacks):
                        seat_num = self._state_index_to_seat(i)
                        self.seat_stacks[seat_num - 1] = int(s)
                except Exception:
                    pass

                # hand end payload using payoffs if available; else compute delta via seat_stacks diff
                results = []
                payoffs = getattr(self.state, "payoffs", None)
                if payoffs:
                    for i, delta in enumerate(payoffs):
                        seat_num = self._state_index_to_seat(i)
                        results.append({"seat": seat_num, "delta": int(delta)})
                elif self.hand_start_seat_stacks is not None:
                    try:
                        for i, end_stack in enumerate(self.state.stacks):
                            seat_num = self._state_index_to_seat(i)
                            start = self.hand_start_seat_stacks[seat_num - 1]
                            results.append({"seat": seat_num, "delta": int(end_stack - start)})
                    except Exception:
                        results = []
                messages.append(
                    {
                        "type": "hand_end",
                        "hand_id": f"h_{self.hand_index:05d}",
                        "results": results,
                        "next_button_seat": self._next_active_seat(self.button_seat),
                    }
                )

                # Check if session should end
                should_end, end_reason = self.should_end_session()
                if should_end:
                    self.session_active = False
                    messages.append({"type": "session_end", "reason": end_reason})
                # Do NOT auto-start next hand; wait for REST /next
                break

            idx = self.state.turn_index
            if idx is None:
                # Automated stage but no progression method available; loop back to snapshot
                continue

            seat = self._state_index_to_seat(idx)
            if seat == human_seat:
                # Build prompt
                la = self.legal_actions()
                seq = self.next_sequence()
                # Minimal MVP v0.1 analysis: pot_math only
                try:
                    pot_math = compute_pot_math(self.state, idx)
                except Exception:
                    pot_math = None

                prompt = {
                    "type": "prompt",
                    "seq": seq,
                    "to_act": seat,
                    "legal_actions": la,
                    "analysis": {"pot_math": pot_math} if pot_math is not None else {},
                }
                messages.append(prompt)
                break
            else:
                # Bot seat - delegate to BotManager
                # Note: This is sync version, will be made async later
                la = self.legal_actions()
                if self.bot_manager.is_bot_seat(seat):
                    # For now, use simple bot logic until async integration
                    action = None
                    # prefer check > call > min raise > fold
                    for a in la:
                        if a["type"] == "check":
                            action = a
                            break
                    if action is None:
                        for a in la:
                            if a["type"] == "call":
                                action = a
                                break
                    if action is None:
                        raises = [a for a in la if a.get("type") == "raise_to"]
                        if raises:
                            raises.sort(key=lambda a: a.get("amount", 0))
                            action = raises[0]
                    if action is None and la:
                        action = la[0]
                    if action is None:
                        break
                    self.apply_action(action)
                else:
                    # Non-bot seat but not human - skip or error
                    break
                # loop continues
        return messages, prompt

    def _compute_showdown_winners(self, board_cards: List) -> List[Dict]:
        """Compute showdown winners and best-5 using pokerkit when possible.
        Returns list of {seat, best5, rank} dicts.
        """
        assert self.state is not None
        winners_payload: List[Dict] = []

        # Determine winners primarily from payoffs if available
        payoffs = getattr(self.state, "payoffs", None)
        winner_indices: List[int] = []
        if payoffs is not None:
            try:
                max_pay = max(payoffs)
                if max_pay > 0:
                    winner_indices = [i for i, d in enumerate(payoffs) if d == max_pay]
            except Exception:
                winner_indices = []

        # Helper to stringify 5 cards
        def to_strs(cards) -> List[str]:
            try:
                return [str(c) for c in cards]
            except Exception:
                return []

        def _humanize_label(label_obj) -> str:
            try:
                s = str(label_obj)
                # Common forms: 'Label.TWO_PAIR' or 'Two Pair'
                if "." in s:
                    s = s.split(".", 1)[1]
                s = s.replace("_", " ").title()
                # Prefer standard poker casing
                replacements = {
                    "Of A Kind": "of a Kind",
                }
                for k, v in replacements.items():
                    s = s.replace(k, v)
                return s
            except Exception:
                return "Best 5"

        # Helpers for detailed human reason from best 5
        def _abbr(card) -> str:
            try:
                s = str(card)
                if "(" in s and ")" in s:
                    return s[s.rfind("(") + 1 : s.rfind(")")]
                return s
            except Exception:
                return str(card)

        rank_order = {r: i for i, r in enumerate(list("--23456789TJQKA"))}
        rank_name = {
            14: "Ace",
            13: "King",
            12: "Queen",
            11: "Jack",
            10: "Ten",
            9: "Nine",
            8: "Eight",
            7: "Seven",
            6: "Six",
            5: "Five",
            4: "Four",
            3: "Trey",
            2: "Deuce",
        }
        def plural(n: int) -> str:
            return (rank_name.get(n, str(n)) + "s") if n not in (3, 5) else ("Treys" if n == 3 else "Fives")

        def describe_best5(combo_cards) -> str:
            try:
                ab = [_abbr(c) for c in combo_cards]
                ranks = [rank_order.get(a[0], 0) for a in ab]
                suits = [a[1] if len(a) > 1 else "?" for a in ab]
                # Counts
                from collections import Counter
                rc = Counter(ranks)
                counts = sorted(((cnt, r) for r, cnt in rc.items()), key=lambda x: (x[0], x[1]), reverse=True)
                uniq = sorted(set(ranks))
                # Straight detection (A-5)
                is_straight = False
                high_straight = 0
                if len(uniq) == 5:
                    if max(uniq) - min(uniq) == 4:
                        is_straight = True
                        high_straight = max(uniq)
                    elif set(uniq) == {14, 5, 4, 3, 2}:
                        is_straight = True
                        high_straight = 5
                is_flush = len(set(suits)) == 1

                if is_straight and is_flush:
                    if high_straight == 14 and 10 in uniq:
                        return "Royal Flush"
                    return f"Straight Flush to {rank_name.get(high_straight, str(high_straight))}"
                if counts[0][0] == 4:
                    return f"Four of a Kind, {plural(counts[0][1])}"
                if counts[0][0] == 3 and counts[1][0] == 2:
                    return f"Full House, {plural(counts[0][1])} over {plural(counts[1][1])}"
                if is_flush:
                    hi = max(ranks)
                    return f"Flush, {rank_name.get(hi, str(hi))} high"
                if is_straight:
                    return f"Straight to {rank_name.get(high_straight, str(high_straight))}"
                if counts[0][0] == 3:
                    return f"Three of a Kind, {plural(counts[0][1])}"
                if counts[0][0] == 2 and counts[1][0] == 2:
                    hi_pair = max(counts[0][1], counts[1][1])
                    lo_pair = min(counts[0][1], counts[1][1])
                    # kicker
                    kick = max([r for r in ranks if r not in (hi_pair, lo_pair)])
                    return f"Two Pair, {plural(hi_pair)} and {plural(lo_pair)} ({rank_name.get(kick, str(kick))} kicker)"
                if counts[0][0] == 2:
                    pair = counts[0][1]
                    # best kicker
                    kickers = sorted([r for r in ranks if r != pair], reverse=True)
                    kick = rank_name.get(kickers[0], str(kickers[0])) if kickers else ""
                    return f"Pair of {plural(pair)}{(' (' + kick + ' kicker)') if kick else ''}"
                hi = max(ranks)
                return f"High Card, {rank_name.get(hi, str(hi))}"
            except Exception:
                return "Best 5"

        # Prefer a local, deterministic best-of-7 evaluator to avoid library ordering ambiguity
        def best5_for_idx(idx: int) -> Tuple[str, List[str]]:
            seven = list(getattr(self.state, "hole_cards", [])[idx] or []) + list(board_cards)

            def score_combo(combo_cards):
                try:
                    ab = [_abbr(c) for c in combo_cards]
                    ranks = [rank_order.get(a[0], 0) for a in ab]
                    suits = [a[1] if len(a) > 1 else "?" for a in ab]
                    from collections import Counter
                    rc = Counter(ranks)
                    counts = sorted(((cnt, r) for r, cnt in rc.items()), key=lambda x: (x[0], x[1]), reverse=True)
                    uniq = sorted(set(ranks))
                    # Straight detection (A-5 allowed)
                    is_straight = False
                    high_straight = 0
                    if len(uniq) == 5:
                        if max(uniq) - min(uniq) == 4:
                            is_straight = True
                            high_straight = max(uniq)
                        elif set(uniq) == {14, 5, 4, 3, 2}:
                            is_straight = True
                            high_straight = 5
                    is_flush = len(set(suits)) == 1

                    # Category ordering (higher is better)
                    # 8: Straight Flush, 7: Quads, 6: Full House, 5: Flush, 4: Straight, 3: Trips, 2: Two Pair, 1: Pair, 0: High Card
                    if is_straight and is_flush:
                        return (8, [high_straight])
                    if counts[0][0] == 4:
                        # (quad_rank, kicker)
                        quad = counts[0][1]
                        kicker = max([r for r in ranks if r != quad])
                        return (7, [quad, kicker])
                    if counts[0][0] == 3 and counts[1][0] == 2:
                        # (trips_rank, pair_rank)
                        return (6, [counts[0][1], counts[1][1]])
                    if is_flush:
                        # 5 kickers sorted
                        return (5, sorted(ranks, reverse=True))
                    if is_straight:
                        return (4, [high_straight])
                    if counts[0][0] == 3:
                        trips = counts[0][1]
                        kickers = sorted([r for r in ranks if r != trips], reverse=True)
                        return (3, [trips] + kickers)
                    if counts[0][0] == 2 and counts[1][0] == 2:
                        hi_pair = max(counts[0][1], counts[1][1])
                        lo_pair = min(counts[0][1], counts[1][1])
                        kicker = max([r for r in ranks if r not in (hi_pair, lo_pair)])
                        return (2, [hi_pair, lo_pair, kicker])
                    if counts[0][0] == 2:
                        pr = counts[0][1]
                        kickers = sorted([r for r in ranks if r != pr], reverse=True)
                        return (1, [pr] + kickers[:3])
                    return (0, sorted(ranks, reverse=True))
                except Exception:
                    return (-1, [])

            best_combo = None
            best_key = None
            for combo in combinations(seven, 5):
                key = score_combo(combo)
                if best_key is None or key > best_key:
                    best_key = key
                    best_combo = combo

            # As a fallback, try pokerkit lookups if we somehow failed
            if best_combo is None:
                try:
                    from pokerkit.lookups import StandardLookup  # type: ignore
                    best_entry = None
                    for combo in combinations(seven, 5):
                        entry = StandardLookup.lookup(combo)  # type: ignore
                        if best_entry is None or entry > best_entry:
                            best_entry = entry
                            best_combo = combo
                except Exception:
                    best_combo = seven[:5]

            detail = describe_best5(best_combo or seven[:5])
            return detail, to_strs(best_combo or seven[:5])

        for idx in winner_indices:
            try:
                rank, best5 = best5_for_idx(idx)
                winners_payload.append({"seat": idx + 1, "best5": best5, "rank": rank})
            except Exception:
                winners_payload.append({"seat": idx + 1, "best5": [], "rank": "Best 5"})
        return winners_payload

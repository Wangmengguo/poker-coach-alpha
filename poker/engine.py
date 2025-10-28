from __future__ import annotations

import hashlib
import hmac
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from itertools import combinations

from pokerkit import NoLimitTexasHoldem
from pokerkit.state import Automation, Mode, State

from .bot_manager import BotManager


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
        self.hand_start_stacks: Optional[List[int]] = None
        self.sequence_number = 0
        self.bot_manager = BotManager(config.session_id)
        self.player_ids: List[str] = [
            ("human" if i + 1 == self.cfg.human_seat else f"bot{i+1}")
            for i in range(self.cfg.seats)
        ]
        # Display/state metadata
        self.button_seat: int = 1

    def start_session(self) -> None:
        self.session_active = True
        self.hand_index = 0
        self.sequence_number = 0
        self.button_seat = 1
        self._start_new_hand()

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

    def _start_new_hand(self) -> None:
        # Determine stacks for new hand; if first hand, initialize to starting stacks
        if self.state is None or not getattr(self.state, "stacks", None):
            stacks = [self.cfg.starting_stack] * self.cfg.seats
        else:
            stacks = [int(s) for s in self.state.stacks]

        # Generate deterministic seed for this hand
        hand_seed = self._generate_hand_seed()

        self.state = NoLimitTexasHoldem.create_state(
            automations,
            False,  # ante trimming off
            0,  # no antes
            (self.cfg.sb, self.cfg.bb),  # blinds
            self.cfg.bb,  # min bet equals big blind for NLHE
            stacks,
            self.cfg.seats,
            mode=Mode.CASH_GAME,
        )

        # Set deterministic seed for this hand
        if hasattr(self.state, "rng") and hasattr(self.state.rng, "seed"):
            self.state.rng.seed(hand_seed)

        # Record stacks at the start of this hand for delta fallback
        self.hand_start_stacks = list(self.state.stacks)
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

        seen = set()
        for amt in sorted(set(candidates)):
            if amt <= max_bet:
                continue
            if self._try_raise_to(amt):
                actions.append({"type": "raise_to", "amount": int(amt)})
                seen.add(amt)
        return actions

    def apply_action(self, action: Dict) -> None:
        assert self.state is not None
        t = action.get("type")
        if t in ("check", "call"):
            self.state.check_or_call()
        elif t == "fold":
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

        # Check stacks if available
        if self.state is not None:
            stacks = list(self.state.stacks)
            human_idx = self.cfg.human_seat - 1
            if human_idx < len(stacks) and stacks[human_idx] <= 0:
                return True, "player_busted"
            # End if all bots are busted (<=0)
            bot_indices = [i for i in range(self.cfg.seats) if (i + 1) != self.cfg.human_seat]
            if bot_indices and all(stacks[i] <= 0 for i in bot_indices):
                return True, "bots_busted"

        return False, ""

    def build_table_snapshot(self) -> Dict:
        assert self.state is not None
        players = []
        for idx in self.state.player_indices:
            # Hole cards perspective: human sees own holes fully; others show up cards only
            if (idx + 1) == self.cfg.human_seat:
                hole = [str(c) for c in self.state.hole_cards[idx]]
            else:
                hole = []
                for c, up in zip(self.state.hole_cards[idx], self.state.hole_card_statuses[idx]):
                    hole.append(str(c) if up else "??")
            players.append(
                {
                    "seat": idx + 1,
                    "id": self.player_ids[idx],
                    "stack": int(self.state.stacks[idx]),
                    "in_hand": bool(self.state.statuses[idx]),
                    "hole": hole,
                }
            )
        # Flatten full board across streets (include all flop cards)
        board: List[str] = []
        for cards in self.state.board_cards:
            if cards:
                for c in cards:
                    board.append(_card_to_str(c))
        pot = int(sum(self.state.pot_amounts)) if hasattr(self.state, "pot_amounts") else 0
        bets: Dict[str, int] = {str(i + 1): int(b) for i, b in enumerate(self.state.bets)}

        to_act = self.state.turn_index
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
            "to_act": None if to_act is None else to_act + 1,
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
        # Rotate button and start new hand
        self.button_seat = 1 + (self.button_seat % self.cfg.seats)
        self._start_new_hand()
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

                    statuses = list(getattr(self.state, "statuses", [True] * self.cfg.seats) or [])
                    sd_players = []
                    for i in range(self.cfg.seats):
                        in_hand = bool(statuses[i])
                        if not in_hand:
                            continue  # hide folded
                        sd_players.append(
                            {
                                "seat": i + 1,
                                "id": self.player_ids[i],
                                "hole": [str(c) for c in getattr(self.state, "hole_cards", [])[i] or []],
                                "in_hand": in_hand,
                            }
                        )

                    winners_payload: List[Dict] = []
                    try:
                        winners_payload = self._compute_showdown_winners(board_cards)
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

                # hand end payload using payoffs if available; else compute delta via stacks diff
                results = []
                payoffs = getattr(self.state, "payoffs", None)
                if payoffs:
                    for i, delta in enumerate(payoffs):
                        results.append({"seat": i + 1, "delta": int(delta)})
                elif self.hand_start_stacks is not None:
                    try:
                        for i, (start, end) in enumerate(
                            zip(self.hand_start_stacks, self.state.stacks)
                        ):
                            results.append({"seat": i + 1, "delta": int(end - start)})
                    except Exception:
                        results = []
                messages.append(
                    {
                        "type": "hand_end",
                        "hand_id": f"h_{self.hand_index:05d}",
                        "results": results,
                        "next_button_seat": (1 + (self.button_seat % self.cfg.seats)),
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

            seat = idx + 1
            if seat == human_seat:
                # Build prompt
                la = self.legal_actions()
                seq = self.next_sequence()
                prompt = {
                    "type": "prompt",
                    "seq": seq,
                    "to_act": seat,
                    "legal_actions": la,
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

        # Try pokerkit hand evaluation APIs
        def best5_for_idx(idx: int) -> Tuple[str, List[str]]:
            seven = list(getattr(self.state, "hole_cards", [])[idx] or []) + list(board_cards)
            # Attempt to use pokerkit's high-hand utilities; fallback to simple pick
            try:
                # Option A: StandardHighHand with best-of-7
                try:
                    from pokerkit.hands import StandardHighHand as SHH  # type: ignore

                    best = None
                    best_rank = None
                    best_combo = None
                    for combo in combinations(seven, 5):
                        h = SHH(combo) if callable(SHH) else SHH.from_cards(combo)  # type: ignore
                        rank_val = getattr(h, "rank", None) or getattr(h, "value", None)
                        if best is None or (rank_val is not None and rank_val > best_rank):
                            best = h
                            best_rank = rank_val
                            best_combo = combo
                    label = getattr(best, "label", None) or getattr(best, "__class__", type("", (), {})).__name__
                    return str(label) if label else "Best 5", to_strs(best_combo or seven[:5])
                except Exception:
                    pass
                # Option B: StandardLookup
                try:
                    from pokerkit.lookups import StandardLookup  # type: ignore

                    best_combo = None
                    best_entry = None
                    for combo in combinations(seven, 5):
                        entry = StandardLookup.lookup(combo)  # type: ignore
                        if best_entry is None or entry > best_entry:
                            best_entry = entry
                            best_combo = combo
                    rank_name = getattr(best_entry, "label", None) or getattr(best_entry, "name", None) or "Best 5"
                    return str(rank_name), to_strs(best_combo or seven[:5])
                except Exception:
                    pass
            except Exception:
                pass
            # Fallback: just pick any 5
            return "Best 5", to_strs(seven[:5])

        for idx in winner_indices:
            try:
                rank, best5 = best5_for_idx(idx)
                winners_payload.append({"seat": idx + 1, "best5": best5, "rank": rank})
            except Exception:
                winners_payload.append({"seat": idx + 1, "best5": [], "rank": "Best 5"})
        return winners_payload

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from pokerkit import NoLimitTexasHoldem
from pokerkit.state import Automation, Mode, State


def _card_to_str(card) -> str:
    s = str(card)
    return s


automations = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.CARD_BURNING,
    Automation.HOLE_DEALING,
    Automation.BOARD_DEALING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)


@dataclass
class EngineConfig:
    seats: int = 6
    sb: int = 1
    bb: int = 2
    starting_stack: int = 400  # chips (≈200bb at 1/2)
    human_seat: int = 1  # 1-indexed
    max_hands: int = 100


class TableEngine:
    def __init__(self, config: EngineConfig) -> None:
        self.cfg = config
        self.hand_index = 0
        self.session_active = False
        self.state: Optional[State] = None
        self.player_ids: List[str] = [
            ("human" if i + 1 == self.cfg.human_seat else f"bot{i+1}")
            for i in range(self.cfg.seats)
        ]

    def start_session(self) -> None:
        self.session_active = True
        self.hand_index = 0
        self._start_new_hand()

    def _start_new_hand(self) -> None:
        stacks = [self.cfg.starting_stack] * self.cfg.seats
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

        # Candidate raises (validate via simulation)
        max_bet = max(self.state.bets)
        min_bet = self._min_bet()
        candidates = [max_bet + min_bet]
        # try a couple bigger sizes and all-in
        candidates.append(max_bet + 2 * min_bet)
        # all-in as raise-to total bet this street
        candidates.append(self._max_bet_to(i))

        seen = set()
        for amt in candidates:
            if amt <= max_bet:
                continue
            if amt in seen:
                continue
            if self._try_raise_to(amt):
                actions.append({"type": "raise_to", "amount": amt})
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

    def build_table_snapshot(self) -> Dict:
        assert self.state is not None
        players = []
        for idx in self.state.player_indices:
            players.append(
                {
                    "seat": idx + 1,
                    "id": self.player_ids[idx],
                    "stack": int(self.state.stacks[idx]),
                    "in_hand": bool(self.state.statuses[idx]),
                }
            )
        # Flatten single board across streets
        board: List[str] = []
        for cards in self.state.board_cards:
            if cards:
                board.append(_card_to_str(cards[0]))
        pot = int(sum(self.state.pot_amounts)) if hasattr(self.state, "pot_amounts") else 0
        bets: Dict[str, int] = {str(i + 1): int(b) for i, b in enumerate(self.state.bets)}

        to_act = self.state.turn_index
        return {
            "table_id": "default",
            "hand_id": f"h_{self.hand_index:05d}",
            "button_seat": 1,  # TODO: rotate in later versions
            "blinds": {"sb": self.cfg.sb, "bb": self.cfg.bb},
            "players": players,
            "street": self._street_name(),
            "board": board,
            "pot": pot,
            "bets": bets,
            "to_act": None if to_act is None else to_act + 1,
            "legal_actions": self.legal_actions(),
        }

    def _street_name(self) -> str:
        assert self.state is not None
        idx = self.state.street_index
        if idx is None:
            return "showdown" if not self.state.status else "between"
        return ["preflop", "flop", "turn", "river"][min(idx, 3)]

    # Advance loop applying bot actions until human prompt or hand end
    def advance(self, human_seat: int) -> Tuple[List[Dict], Optional[Dict]]:
        assert self.state is not None
        messages: List[Dict] = []
        prompt: Optional[Dict] = None
        # Iterate until human turn or hand ends
        guard = 0
        while True:
            guard += 1
            if guard > 200:  # safety
                break
            snap = self.build_table_snapshot()
            messages.append({"type": "snapshot", "seq": guard, "table": snap})

            if self.is_hand_over():
                # hand end payload using payoffs if available
                results = []
                if hasattr(self.state, "payoffs") and self.state.payoffs:
                    for i, delta in enumerate(self.state.payoffs):
                        results.append({"seat": i + 1, "delta": int(delta)})
                messages.append(
                    {
                        "type": "hand_end",
                        "hand_id": f"h_{self.hand_index:05d}",
                        "results": results,
                        "next_button_seat": 1,
                    }
                )
                # Start next hand if session active and cap not reached
                if self.session_active and self.hand_index < self.cfg.max_hands:
                    self._start_new_hand()
                    continue
                break

            idx = self.state.turn_index
            if idx is None:
                # Automated stage (deals/collections); loop back to snapshot
                continue

            seat = idx + 1
            if seat == human_seat:
                # Build prompt
                la = self.legal_actions()
                prompt = {
                    "type": "prompt",
                    "seq": guard + 1,
                    "to_act": seat,
                    "legal_actions": la,
                }
                messages.append(prompt)
                break
            else:
                # Bot acts: simple policy
                la = self.legal_actions()
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
                    for a in la:
                        if a["type"] == "raise_to":
                            action = a
                            break
                if action is None and la:
                    action = la[0]
                if action is None:
                    break
                self.apply_action(action)
                # loop continues
        return messages, prompt

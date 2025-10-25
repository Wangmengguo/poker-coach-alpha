from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PlayerView:
    seat: int
    id: str
    stack: int
    in_hand: bool = True


@dataclass
class TableState:
    table_id: str
    hand_id: str
    seq: int = 0
    button_seat: int = 1
    blinds: Dict[str, int] = field(default_factory=lambda: {"sb": 1, "bb": 2})
    players: List[PlayerView] = field(default_factory=list)
    street: str = "preflop"
    board: List[str] = field(default_factory=list)
    pot: int = 0
    bets: Dict[int, int] = field(default_factory=dict)
    to_act: Optional[int] = None
    legal_actions: List[dict] = field(default_factory=list)
    human_player_id: Optional[str] = None
    session_active: bool = False

    @staticmethod
    def default() -> "TableState":
        # 1 human + 5 bots scaffold (stacks 400 chips ≈ 200bb at 1/2)
        players = [
            PlayerView(seat=1, id="human", stack=400),
            PlayerView(seat=2, id="bot2", stack=400),
            PlayerView(seat=3, id="bot3", stack=400),
            PlayerView(seat=4, id="bot4", stack=400),
            PlayerView(seat=5, id="bot5", stack=400),
            PlayerView(seat=6, id="bot6", stack=400),
        ]
        return TableState(
            table_id="default",
            hand_id="h_00000",
            players=players,
            to_act=2,
            legal_actions=[{"type": "fold"}, {"type": "call", "amount": 2}, {"type": "raise", "min": 6, "max": 400}],
        )

    def snapshot(self) -> dict:
        return {
            "type": "snapshot",
            "seq": self.seq,
            "table": {
                "table_id": self.table_id,
                "hand_id": self.hand_id,
                "button_seat": self.button_seat,
                "blinds": self.blinds,
                "players": [p.__dict__ for p in self.players],
                "street": self.street,
                "board": self.board,
                "pot": self.pot,
                "bets": {str(k): v for k, v in self.bets.items()},
                "to_act": self.to_act,
                "legal_actions": self.legal_actions,
            },
        }

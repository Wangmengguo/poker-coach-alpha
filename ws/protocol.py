from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# ========== Action & Legal Action Models ==========


class LegalAction(BaseModel):
    type: str
    amount: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None


class ClientAction(BaseModel):
    type: Literal["action"] = "action"
    action_id: str
    hand_id: str
    seat: int
    action: LegalAction


# ========== Player & Table State Models ==========


class PlayerSnapshot(BaseModel):
    seat: int
    id: str
    stack: int
    in_hand: bool = True
    hole: List[str] = Field(default_factory=list)


class TableSnapshot(BaseModel):
    table_id: str
    hand_id: str
    button_seat: int
    blinds: Dict[str, int]
    players: List[PlayerSnapshot]
    street: str
    board: List[str]
    pot: int
    bets: Dict[str, int]
    to_act: Optional[int]
    legal_actions: List[LegalAction]
    last_op: Optional[str] = None
    positions: Optional[Dict[str, str]] = None


# ========== WebSocket Message Types ==========


class Snapshot(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    seq: int
    table: TableSnapshot


class Prompt(BaseModel):
    type: Literal["prompt"] = "prompt"
    seq: int
    to_act: int
    deadline: Optional[str] = None
    legal_actions: List[LegalAction]
    # Optional minimal analysis for MVP; payload may be partial
    analysis: Optional[Dict[str, Any]] = None


class HandResult(BaseModel):
    seat: int
    delta: int


class HandEnd(BaseModel):
    type: Literal["hand_end"] = "hand_end"
    hand_id: str
    results: List[HandResult]
    next_button_seat: int


class ShowdownPlayer(BaseModel):
    seat: int
    id: str
    hole: List[str]
    in_hand: bool


class WinnerInfo(BaseModel):
    seat: int
    best5: List[str]
    rank: str


class Showdown(BaseModel):
    type: Literal["showdown"] = "showdown"
    hand_id: str
    board: List[str]
    players: List[ShowdownPlayer]
    winners: Optional[List[WinnerInfo]] = None


class SessionEnd(BaseModel):
    type: Literal["session_end"] = "session_end"
    reason: str  # "player_busted", "max_hands", "requested"


class Error(BaseModel):
    type: Literal["error"] = "error"
    message: str
    trace: Optional[str] = None
    snapshot: Optional[TableSnapshot] = None


class Resume(BaseModel):
    type: Literal["resume"] = "resume"
    from_seq: int


class Ack(BaseModel):
    type: Literal["ack"] = "ack"
    received: Dict[str, Any]


# ========== Analysis Update ==========


class HandStrengthPayload(BaseModel):
    hand_strength_pct: Optional[float] = None
    model: str = "pokerkit.calculate_hand_strength"
    sample_count: int
    players: int
    degraded: Optional[bool] = False
    reason: Optional[str] = None


class AnalysisUpdate(BaseModel):
    type: Literal["analysis"] = "analysis"
    seq: int
    to_act: int
    hand_strength: Optional[HandStrengthPayload] = None


class ActionNotification(BaseModel):
    """Notification when any player (human or bot) takes an action."""

    type: Literal["action_taken"] = "action_taken"
    seat: int
    player_id: str
    action_type: str  # "fold", "check", "call", "raise_to"
    amount: Optional[int] = None  # For call/raise
    is_bot: bool = False


class AiAdvicePayload(BaseModel):
    recommended_action: Optional[LegalAction] = None
    secondary_action: Optional[LegalAction] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    reason: Optional[str] = None


class AiAdviceUpdate(BaseModel):
    type: Literal["ai_advice"] = "ai_advice"
    seq: int
    to_act: int
    advice: Optional[AiAdvicePayload] = None


# ========== Message Union Type ==========

ServerMessage = Union[
    Snapshot,
    Prompt,
    HandEnd,
    Showdown,
    SessionEnd,
    Error,
    Ack,
    AnalysisUpdate,
    ActionNotification,
    AiAdviceUpdate,
]
ClientMessage = Union[ClientAction, Resume]


# ========== Validation Utilities ==========


def _get_attr(obj: Union[LegalAction, Dict[str, Any]], name: str):
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name)
    return None


def validate_action_against_legal(
    action: Union[LegalAction, Dict[str, Any]],
    legal_actions: List[Union[LegalAction, Dict[str, Any]]],
) -> bool:
    """Validate that an action is in the list of legal actions.
    Accepts either Pydantic models or plain dicts for legal actions.
    """
    a_type = _get_attr(action, "type")
    a_amt = _get_attr(action, "amount")
    for legal in legal_actions:
        l_type = _get_attr(legal, "type")
        if l_type != a_type:
            continue
        # For type-only actions, any matching type is valid
        if a_type in ("check", "fold"):
            return True
        # For amount-bearing actions, match amount exactly; keep searching otherwise
        elif a_type == "call":
            if a_amt == _get_attr(legal, "amount"):
                return True
        elif a_type == "raise_to":
            l_amt = _get_attr(legal, "amount")
            if l_amt is not None and a_amt == l_amt:
                return True
            # Support range-based validation when min/max are provided
            l_min = _get_attr(legal, "min")
            l_max = _get_attr(legal, "max")
            if a_amt is not None and (l_min is not None or l_max is not None):
                if (l_min is None or a_amt >= l_min) and (l_max is None or a_amt <= l_max):
                    return True
        return False


def is_action_idempotent(action_id: str, processed_actions: set) -> bool:
    """Check if action_id has already been processed."""
    return action_id not in processed_actions

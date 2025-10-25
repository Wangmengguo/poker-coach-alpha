from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class LegalAction(BaseModel):
    type: str
    amount: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None


class Prompt(BaseModel):
    type: str = Field(default="prompt", const=True)
    seq: int
    to_act: int
    deadline: Optional[str]
    legal_actions: List[LegalAction]


class ClientAction(BaseModel):
    type: str = Field(default="action", const=True)
    action_id: str
    hand_id: str
    seat: int
    action: LegalAction

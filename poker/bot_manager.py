from __future__ import annotations

import asyncio
import hashlib
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Protocol

from .bots import SimpleBot


class BotPolicy(Protocol):
    """Protocol for bot decision-making policies."""

    def choose(self, legal_actions: List[Dict]) -> Dict:
        """Choose an action from the list of legal actions."""
        ...


class AsyncBotPolicy(ABC):
    """Base class for async bot policies with timing."""

    @abstractmethod
    async def choose_async(self, legal_actions: List[Dict], seat: int, game_state: Dict) -> Dict:
        """Choose an action asynchronously with optional delay."""
        pass


class SimpleAsyncBot(AsyncBotPolicy):
    """Async wrapper around SimpleBot with configurable timing."""

    def __init__(
        self, min_delay_ms: int = 500, max_delay_ms: int = 2000, seed: Optional[int] = None
    ):
        self.bot = SimpleBot()
        self.min_delay = min_delay_ms / 1000.0
        self.max_delay = max_delay_ms / 1000.0
        self.rng = random.Random(seed)

    async def choose_async(self, legal_actions: List[Dict], seat: int, game_state: Dict) -> Dict:
        """Choose action with realistic timing delay."""
        # Add thinking time based on decision complexity
        base_delay = self.rng.uniform(self.min_delay, self.max_delay)

        # Add extra time for complex decisions (multiple raise options)
        raise_actions = [a for a in legal_actions if a.get("type") == "raise_to"]
        if len(raise_actions) > 1:
            base_delay += self.rng.uniform(0.2, 0.8)

        await asyncio.sleep(base_delay)
        return self.bot.choose(legal_actions)


class TightBot(AsyncBotPolicy):
    """More conservative bot that folds more often."""

    def __init__(
        self,
        fold_probability: float = 0.4,
        min_delay_ms: int = 300,
        max_delay_ms: int = 1500,
        seed: Optional[int] = None,
    ):
        self.fold_prob = fold_probability
        self.min_delay = min_delay_ms / 1000.0
        self.max_delay = max_delay_ms / 1000.0
        self.rng = random.Random(seed)

    async def choose_async(self, legal_actions: List[Dict], seat: int, game_state: Dict) -> Dict:
        """Conservative decision making with folding bias."""
        await asyncio.sleep(self.rng.uniform(self.min_delay, self.max_delay))

        # Check if we can check (no cost)
        for action in legal_actions:
            if action.get("type") == "check":
                return action

        # Fold with higher probability when facing a bet
        if self.rng.random() < self.fold_prob:
            for action in legal_actions:
                if action.get("type") == "fold":
                    return action

        # Otherwise call
        for action in legal_actions:
            if action.get("type") == "call":
                return action

        # Fallback to first available action
        return legal_actions[0] if legal_actions else {"type": "check"}


class BotManager:
    """Manages bot actions for multiple seats with different policies."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.bot_policies: Dict[int, AsyncBotPolicy] = {}  # seat -> policy
        self.processed_actions: set = set()
        self._setup_default_bots()

    def _setup_default_bots(self):
        """Initialize default bot policies for seats 2-6."""
        # Use session_id to create deterministic bot seeds
        base_seed = self._generate_seed("bot_setup")

        # Mix of bot types for variety
        self.bot_policies[2] = SimpleAsyncBot(seed=base_seed + 2)
        self.bot_policies[3] = TightBot(seed=base_seed + 3)
        self.bot_policies[4] = SimpleAsyncBot(seed=base_seed + 4)
        self.bot_policies[5] = TightBot(fold_probability=0.3, seed=base_seed + 5)
        self.bot_policies[6] = SimpleAsyncBot(
            min_delay_ms=200, max_delay_ms=1000, seed=base_seed + 6
        )

    def _generate_seed(self, context: str) -> int:
        """Generate deterministic seed from session_id and context."""
        key = f"{self.session_id}_{context}".encode("utf-8")
        hash_digest = hashlib.md5(key).digest()
        return int.from_bytes(hash_digest[:4], byteorder="big")

    def is_bot_seat(self, seat: int) -> bool:
        """Check if a seat is controlled by a bot."""
        return seat in self.bot_policies

    async def get_bot_action(
        self, seat: int, legal_actions: List[Dict], game_state: Dict
    ) -> Optional[Dict]:
        """Get bot action for the specified seat."""
        if not self.is_bot_seat(seat):
            return None

        if not legal_actions:
            return None

        bot_policy = self.bot_policies[seat]
        try:
            action = await bot_policy.choose_async(legal_actions, seat, game_state)
            return action
        except Exception:
            # Fallback to safe action if bot policy fails
            for safe_action in legal_actions:
                if safe_action.get("type") in ("check", "fold"):
                    return safe_action
            return legal_actions[0] if legal_actions else None

    def add_processed_action(self, action_id: str):
        """Track processed action for idempotency."""
        self.processed_actions.add(action_id)

    def is_action_processed(self, action_id: str) -> bool:
        """Check if action has already been processed."""
        return action_id in self.processed_actions

    def set_bot_policy(self, seat: int, policy: AsyncBotPolicy):
        """Set a specific policy for a bot seat."""
        self.bot_policies[seat] = policy

    def remove_bot(self, seat: int):
        """Remove bot from a seat (convert to human seat)."""
        if seat in self.bot_policies:
            del self.bot_policies[seat]

    def reset_for_new_session(self, session_id: str):
        """Reset for a new session with new deterministic seeds."""
        self.session_id = session_id
        self.processed_actions.clear()
        self._setup_default_bots()

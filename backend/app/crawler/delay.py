from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import random
from typing import Final, Literal


Sleep = Callable[[float], Awaitable[None]]
RandomUniform = Callable[[float, float], float]
InteractionDelayPreset = Literal[
    "very_fast",
    "fast",
    "normal",
    "careful",
    "very_careful",
]
DEFAULT_INTERACTION_DELAY_PRESET: InteractionDelayPreset = "normal"
INTERACTION_DELAY_RANGES: Final[
    dict[InteractionDelayPreset, tuple[float, float]]
] = {
    "very_fast": (0.5, 0.5),
    "fast": (0.7, 1.2),
    "normal": (1.0, 2.5),
    "careful": (2.0, 5.0),
    "very_careful": (3.0, 7.0),
}


@dataclass(frozen=True, slots=True)
class DelayObservation:
    reason: str
    seconds: float


class HumanizedDelay:
    def __init__(
        self,
        min_seconds: float = 1.0,
        max_seconds: float = 3.0,
        *,
        sleep: Sleep = asyncio.sleep,
        uniform: RandomUniform = random.uniform,
    ) -> None:
        if min_seconds < 0 or max_seconds < min_seconds:
            raise ValueError("delay range must satisfy 0 <= min_seconds <= max_seconds")
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.sleep = sleep
        self.uniform = uniform

    async def wait(self, reason: str) -> DelayObservation:
        seconds = self.uniform(self.min_seconds, self.max_seconds)
        await self.sleep(seconds)
        return DelayObservation(reason, seconds)


def humanized_delay_for_preset(
    preset: str,
    *,
    sleep: Sleep = asyncio.sleep,
    uniform: RandomUniform = random.uniform,
) -> HumanizedDelay:
    try:
        min_seconds, max_seconds = INTERACTION_DELAY_RANGES[preset]
    except KeyError as exc:
        raise ValueError(
            f"unsupported interaction delay preset: {preset}"
        ) from exc
    return HumanizedDelay(
        min_seconds,
        max_seconds,
        sleep=sleep,
        uniform=uniform,
    )

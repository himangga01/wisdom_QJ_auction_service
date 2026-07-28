import asyncio

import pytest

from app.crawler.delay import (
    DelayObservation,
    HumanizedDelay,
    humanized_delay_for_preset,
)
from app.core.config import Settings
from app.crawler.browser import PlaywrightNaverLandCollector


def test_wait_uses_injected_uniform_and_sleep_and_returns_observation() -> None:
    uniform_calls: list[tuple[float, float]] = []
    sleep_calls: list[float] = []

    def fake_uniform(min_seconds: float, max_seconds: float) -> float:
        uniform_calls.append((min_seconds, max_seconds))
        return 2.25

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    observation = asyncio.run(
        HumanizedDelay(sleep=fake_sleep, uniform=fake_uniform).wait(
            "open_broker_group"
        )
    )

    assert uniform_calls == [(1.0, 3.0)]
    assert sleep_calls == [2.25]
    assert observation == DelayObservation("open_broker_group", 2.25)


@pytest.mark.parametrize(
    ("min_seconds", "max_seconds"),
    [
        (-0.1, 3.0),
        (3.0, 2.0),
    ],
)
def test_rejects_invalid_range(min_seconds: float, max_seconds: float) -> None:
    with pytest.raises(ValueError):
        HumanizedDelay(min_seconds=min_seconds, max_seconds=max_seconds)


def test_collector_preserves_injected_delay() -> None:
    delay = HumanizedDelay()

    collector = PlaywrightNaverLandCollector(
        Settings(_env_file=None),
        delay=delay,
    )

    assert collector.delay is delay


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ("very_fast", (0.5, 0.5)),
        ("fast", (0.7, 1.2)),
        ("normal", (1.0, 2.5)),
        ("careful", (2.0, 5.0)),
        ("very_careful", (3.0, 7.0)),
    ],
)
def test_delay_presets_resolve_to_exact_ranges(
    preset: str,
    expected: tuple[float, float],
) -> None:
    delay = humanized_delay_for_preset(preset)

    assert (delay.min_seconds, delay.max_seconds) == expected


def test_very_fast_preset_waits_exactly_half_a_second() -> None:
    uniform_calls: list[tuple[float, float]] = []
    sleep_calls: list[float] = []

    def fake_uniform(min_seconds: float, max_seconds: float) -> float:
        uniform_calls.append((min_seconds, max_seconds))
        return min_seconds

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    observation = asyncio.run(
        humanized_delay_for_preset(
            "very_fast",
            sleep=fake_sleep,
            uniform=fake_uniform,
        ).wait("open_article_detail")
    )

    assert uniform_calls == [(0.5, 0.5)]
    assert sleep_calls == [0.5]
    assert observation == DelayObservation("open_article_detail", 0.5)


def test_unknown_delay_preset_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported interaction delay preset"):
        humanized_delay_for_preset("turbo")

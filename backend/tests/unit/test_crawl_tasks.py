import pytest

from app.tasks.crawl_tasks import _collector_for_run


def test_worker_collector_uses_run_delay_preset() -> None:
    collector = _collector_for_run("fast", progress=None)

    assert collector.delay.min_seconds == 0.7
    assert collector.delay.max_seconds == 1.2


def test_worker_collector_rejects_corrupt_delay_preset() -> None:
    with pytest.raises(ValueError, match="unsupported interaction delay preset"):
        _collector_for_run("turbo", progress=None)

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.analyses import create_analysis
from app.schemas.analysis import AnalysisCreate


class _Service:
    def __init__(self) -> None:
        self.create_calls = 0

    async def create_for_user(self, *_: object, **__: object) -> None:
        self.create_calls += 1
        raise AssertionError("unavailable browser must stop before persistence")


def test_immediate_analysis_returns_503_before_service_create() -> None:
    service = _Service()
    payload = AnalysisCreate(
        source_url="https://fin.land.naver.com/complexes/123",
        collect_broker_details=True,
        interaction_delay_preset="normal",
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            create_analysis(
                payload=payload,
                user=SimpleNamespace(id=uuid4()),
                analysis_service=service,
                browser="unavailable",
            )
        )

    assert raised.value.status_code == 503
    assert raised.value.detail == {
        "code": "browser_unavailable",
        "message": "수집용 Chrome이 준비되지 않았습니다.",
    }
    assert service.create_calls == 0

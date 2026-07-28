import asyncio
import json

from app.crawler import browser_readiness


class _Response:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_probe_browser_cdp_accepts_chrome_version_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        browser_readiness,
        "urlopen",
        lambda request, timeout: _Response(
            {
                "Browser": "Chrome/138.0.7204.49",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/browser/id",
            }
        ),
    )

    assert (
        asyncio.run(
            browser_readiness.probe_browser_cdp("http://127.0.0.1:42973")
        )
        == "ready"
    )


def test_probe_browser_cdp_normalizes_invalid_payload_to_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        browser_readiness,
        "urlopen",
        lambda request, timeout: _Response(
            {"Browser": "Chromium/138.0", "webSocketDebuggerUrl": ""}
        ),
    )

    assert (
        asyncio.run(
            browser_readiness.probe_browser_cdp("http://127.0.0.1:42973")
        )
        == "unavailable"
    )

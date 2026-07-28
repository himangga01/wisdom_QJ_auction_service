import asyncio
import json
from typing import Literal
from urllib.request import Request, urlopen

BrowserStatus = Literal["ready", "unavailable"]


def _probe(endpoint_url: str, timeout_seconds: float) -> BrowserStatus:
    request = Request(
        f"{endpoint_url.rstrip('/')}/json/version",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                return "unavailable"
            payload = json.loads(response.read())
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
        return "unavailable"

    if not isinstance(payload, dict):
        return "unavailable"
    browser = payload.get("Browser")
    websocket_url = payload.get("webSocketDebuggerUrl")
    if (
        isinstance(browser, str)
        and browser.startswith("Chrome/")
        and isinstance(websocket_url, str)
        and bool(websocket_url)
    ):
        return "ready"
    return "unavailable"


async def probe_browser_cdp(
    endpoint_url: str,
    *,
    timeout_seconds: float = 2.0,
) -> BrowserStatus:
    return await asyncio.to_thread(_probe, endpoint_url, timeout_seconds)

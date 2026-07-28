from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ALLOWED_SCHEME = "https"
ALLOWED_HOST = "fin.land.naver.com"


class InvalidSourceUrl(ValueError):
    code = "invalid_source_url"


@dataclass(frozen=True, slots=True)
class SourceUrlIdentity:
    source_url: str
    normalized_url: str
    url_hash: str


def normalize_source_url(source_url: str) -> SourceUrlIdentity:
    try:
        parsed = urlsplit(source_url)
        port = parsed.port
    except ValueError as exc:
        raise InvalidSourceUrl("유효한 네이버 부동산 URL이 아닙니다.") from exc

    if (
        parsed.scheme.lower() != ALLOWED_SCHEME
        or parsed.hostname is None
        or parsed.hostname.lower() != ALLOWED_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise InvalidSourceUrl(
            "https://fin.land.naver.com 주소만 조사할 수 있습니다."
        )

    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    normalized = urlunsplit(
        (ALLOWED_SCHEME, ALLOWED_HOST, parsed.path or "/", query, "")
    )
    return SourceUrlIdentity(
        source_url=source_url,
        normalized_url=normalized,
        url_hash=sha256(normalized.encode("utf-8")).hexdigest(),
    )

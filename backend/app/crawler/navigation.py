from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit


ALLOWED_HOST = "fin.land.naver.com"
ARTICLE_PATH = re.compile(r"^/articles/(?P<article_id>[A-Za-z0-9_-]+)$")


class UnsafeArticleTarget(ValueError):
    code = "unsafe_article_target"


def validate_internal_article_href(href: str | None) -> str:
    if not href:
        raise UnsafeArticleTarget("내부 매물 링크가 없습니다.")
    try:
        parsed = urlsplit(href)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeArticleTarget("유효하지 않은 매물 링크입니다.") from exc

    if "/out-link-bridge" in parsed.path:
        raise UnsafeArticleTarget("외부 연결 브리지는 열 수 없습니다.")
    if parsed.scheme and parsed.scheme != "https":
        raise UnsafeArticleTarget("HTTPS 네이버 내부 링크만 열 수 있습니다.")
    if parsed.hostname and parsed.hostname.lower() != ALLOWED_HOST:
        raise UnsafeArticleTarget("외부 도메인 링크는 열 수 없습니다.")
    if parsed.username or parsed.password or port not in (None, 443):
        raise UnsafeArticleTarget("허용되지 않은 네이버 링크입니다.")
    if ARTICLE_PATH.fullmatch(parsed.path) is None:
        raise UnsafeArticleTarget("/articles/{articleId} 링크만 열 수 있습니다.")
    return parsed.path


def choose_article_target(*, npay_href: str | None, internal_href: str | None) -> str:
    # An invalid Npay link is a hard failure; silently falling back would violate policy.
    if npay_href:
        return validate_internal_article_href(npay_href)
    return validate_internal_article_href(internal_href)


def reconcile_broker_count(*, displayed_count: int | None, collected_count: int) -> str:
    if displayed_count is not None and displayed_count != collected_count:
        return "partial"
    return "completed"


@dataclass(frozen=True, slots=True)
class ArticleCandidate:
    group_id: str | None
    npay_href: str | None
    internal_href: str | None


class _ArticleCandidateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.group_stack: list[str | None] = []
        self._active_anchor: dict[str, str] | None = None
        self._active_group: str | None = None
        self._anchor_text: list[str] = []
        self._by_group: dict[str | None, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag in {"article", "li"} and "data-group-id" in attributes:
            self.group_stack.append(attributes["data-group-id"])
        if tag == "a":
            self._active_anchor = attributes
            self._active_group = self.group_stack[-1] if self.group_stack else None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._active_anchor is not None:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_anchor is not None:
            href = self._active_anchor.get("href")
            kind = self._active_anchor.get("data-link-kind", "")
            text = " ".join(self._anchor_text).strip()
            slot = self._by_group.setdefault(
                self._active_group, {"npay_href": None, "internal_href": None}
            )
            if href and (kind == "npay" or "Npay 부동산에서 보기" in text):
                slot["npay_href"] = href
            elif href and "/articles/" in urlsplit(href).path:
                slot["internal_href"] = href
            self._active_anchor = None
            self._active_group = None
            self._anchor_text = []
        elif tag in {"article", "li"} and self.group_stack:
            self.group_stack.pop()

    def candidates(self) -> list[ArticleCandidate]:
        return [
            ArticleCandidate(group_id, values["npay_href"], values["internal_href"])
            for group_id, values in self._by_group.items()
        ]


def extract_article_candidates(html: str) -> list[ArticleCandidate]:
    parser = _ArticleCandidateParser()
    parser.feed(html)
    return parser.candidates()

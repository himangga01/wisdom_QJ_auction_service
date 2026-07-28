from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass


SUPPORTED_TRADE_TYPES = frozenset({"매매", "전세", "월세"})


@dataclass(frozen=True, slots=True)
class CrawlScope:
    trade_types: tuple[str, ...] = ("매매", "전세", "월세")
    max_groups_per_trade_type: int | None = None
    expected_article_ids: frozenset[str] = frozenset()
    collect_broker_details: bool = True

    def __post_init__(self) -> None:
        trade_types = tuple(self.trade_types)
        article_ids = frozenset(self.expected_article_ids)
        if any(trade_type not in SUPPORTED_TRADE_TYPES for trade_type in trade_types):
            raise ValueError("unsupported trade type")
        if len(set(trade_types)) != len(trade_types):
            raise ValueError("duplicate trade types are not allowed")
        if (
            self.max_groups_per_trade_type is not None
            and self.max_groups_per_trade_type <= 0
        ):
            raise ValueError("max_groups_per_trade_type must be positive")
        if any(not article_id.strip() for article_id in article_ids):
            raise ValueError("expected article IDs must not be empty")
        object.__setattr__(self, "trade_types", trade_types)
        object.__setattr__(self, "expected_article_ids", article_ids)

    @classmethod
    def sampled(
        cls,
        article_ids: Collection[str],
        collect_broker_details: bool = True,
    ) -> CrawlScope:
        return cls(
            max_groups_per_trade_type=25,
            expected_article_ids=frozenset(article_ids),
            collect_broker_details=collect_broker_details,
        )

    @classmethod
    def full(cls, collect_broker_details: bool = True) -> CrawlScope:
        return cls(collect_broker_details=collect_broker_details)

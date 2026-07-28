from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.crawler.parsers.broker_article import parse_broker_article
from app.crawler.parsers._html import parse_money
from app.crawler.parsers.market_details import parse_market_details


FIXTURE = Path(__file__).parents[1] / "fixtures" / "article_detail.html"
CAPTURED_AT = datetime(2026, 7, 22, 0, 48, tzinfo=timezone.utc)


def test_parses_man_won_composite_amount_without_dropping_won_remainder() -> None:
    assert parse_money("38만 4,141원") == 384_141


def test_parses_structured_article_fields_without_inference() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    detail = parse_broker_article(
        html,
        article_url="https://fin.land.naver.com/articles/2407000001",
        captured_at=CAPTURED_AT,
    )

    assert detail.article_id == "2407000001"
    assert detail.advertised_price == 720_000_000
    assert detail.management_fee == 250_000
    assert detail.supply_area_m2 == Decimal("112.40")
    assert detail.exclusive_area_m2 == Decimal("84.99")
    assert detail.option_tags == ["에어컨 3대", "식세기", "전자 계약"]
    assert detail.realtor is not None
    assert detail.realtor.registration_number == "11110-2026-00001"
    assert detail.captured_at == CAPTURED_AT
    assert "price_mismatch" in detail.warnings


def test_parses_common_market_sections_and_preserves_values() -> None:
    details = parse_market_details(
        FIXTURE.read_text(encoding="utf-8"), captured_at=CAPTURED_AT
    )

    assert details.finance["대출한도"] == "4억 5,000만원"
    assert details.transactions["최근 실거래"] == "6억 9,800만원"
    assert details.costs["취득세"] == "1,980만원"
    assert details.maintenance["월평균 관리비"] == "28만원"
    assert details.location["배정학교"] == "샘플초등학교"
    assert details.complex["세대수"] == "1,200세대"
    assert details.captured_at == CAPTURED_AT

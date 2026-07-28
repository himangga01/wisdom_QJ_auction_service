from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.crawler.live_dom import (
    extract_option_mentions,
    parse_complex_panel,
    parse_live_broker_card,
    parse_live_listing_group,
)
from app.crawler.parsers.broker_article import parse_broker_article
from app.crawler.parsers.market_details import parse_market_details


FIXTURES = Path(__file__).parents[1] / "fixtures"
CAPTURED_AT = datetime(2026, 7, 24, 1, 30, tzinfo=timezone.utc)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_live_complex_link_name_and_trade_counts() -> None:
    observation = parse_complex_panel(
        _fixture("live_complex_panel.html"), title="신동탄포레자이"
    )

    assert observation.complex_id == "131197"
    assert observation.name == "신동탄포레자이"
    assert observation.trade_counts == {"매매": 53, "전세": 2, "월세": 1}
    with pytest.raises(FrozenInstanceError):
        observation.name = "변경 불가"  # type: ignore[misc]


def test_rejects_ambiguous_complex_links_without_exact_title_match() -> None:
    html = """
    <section>
      <a href="/complexes/111">첫 단지</a>
      <a href="/complexes/222">둘째 단지</a>
      <button data-sentry-component="ButtonBoxLink">매매1</button>
    </section>
    """

    with pytest.raises(ValueError, match="ambiguous"):
        parse_complex_panel(html, title="일치하지 않는 title")


def test_allows_repeated_exact_complex_links_for_same_complex() -> None:
    observation = parse_complex_panel(
        """
        <section>
          <a href="/complexes/131197">신동탄포레자이</a>
          <a href="/complexes/131197">신동탄포레자이</a>
          <button data-sentry-component="ButtonBoxLink">매매53</button>
          <button data-sentry-component="ButtonBoxLink">전세2</button>
          <button data-sentry-component="ButtonBoxLink">월세1</button>
        </section>
        """,
        title="신동탄포레자이",
    )

    assert observation.complex_id == "131197"
    assert observation.name == "신동탄포레자이"


def test_uses_title_when_trade_links_repeat_the_same_complex_id() -> None:
    observation = parse_complex_panel(
        """
        <section>
          <a href="/complexes/131197?tab=article">매매 53</a>
          <a href="/complexes/131197?tab=transaction">실거래</a>
          <a href="/complexes/131197?tab=story">이야기 25</a>
          <button data-sentry-component="ButtonBoxLink">매매53</button>
          <button data-sentry-component="ButtonBoxLink">전세2</button>
          <button data-sentry-component="ButtonBoxLink">월세1</button>
        </section>
        """,
        title="신동탄포레자이",
    )

    assert observation.complex_id == "131197"
    assert observation.name == "신동탄포레자이"


def test_allows_single_complex_link_when_title_does_not_match() -> None:
    observation = parse_complex_panel(
        """
        <section>
          <a href="/complexes/333">유일 단지</a>
          <button data-sentry-component="ButtonBoxLink">매매1</button>
        </section>
        """,
        title="caller fallback",
    )

    assert observation.complex_id == "333"
    assert observation.name == "유일 단지"


def test_parses_live_listing_group_visible_values() -> None:
    listing = parse_live_listing_group(
        _fixture("live_listing_group.html"), captured_at=CAPTURED_AT
    )

    assert listing.source_group_id is None
    assert listing.trade_type == "매매"
    assert listing.price == 900_000_000
    assert listing.building == "108동"
    assert listing.supply_area == Decimal("108")
    assert listing.exclusive_area == Decimal("84.97")
    assert listing.floor == "중/33층"
    assert listing.direction == "남동향"
    assert listing.displayed_broker_count == 3
    assert listing.captured_at == CAPTURED_AT


def test_parses_monthly_deposit_rent_and_single_article_count() -> None:
    listing = parse_live_listing_group(
        """
        <article>
          <span>월세 1억/150만원</span><span>108동</span>
          <a href="/articles/2639879471">매물 보러가기</a>
        </article>
        """,
        captured_at=CAPTURED_AT,
    )

    assert listing.trade_type == "월세"
    assert listing.deposit == 100_000_000
    assert listing.monthly_rent == 1_500_000
    assert listing.displayed_broker_count == 1


def test_parses_grouped_monthly_price_range_with_bare_manwon_shorthand() -> None:
    listing = parse_live_listing_group(
        """
        <article>
          <span>월세 5억 7,000/120 ~ 6억/100</span>
          <span>320동</span>
          <button data-nlogs-area="article*l.group">매물목록 펼치기</button>
        </article>
        """,
        captured_at=CAPTURED_AT,
    )

    assert listing.trade_type == "월세"
    assert listing.deposit == 570_000_000
    assert listing.monthly_rent == 1_200_000


def test_listing_description_does_not_override_displayed_trade_type() -> None:
    listing = parse_live_listing_group(
        """
        <article>
          <span>전세 22억</span>
          <p>보증금 조정 가능, 월세 12억/360도 가능</p>
          <a href="/articles/2639879471">매물 보러가기</a>
        </article>
        """,
        captured_at=CAPTURED_AT,
    )

    assert listing.trade_type == "전세"
    assert listing.deposit == 2_200_000_000
    assert listing.monthly_rent is None


def test_prefers_internal_npay_link_and_excludes_out_link_bridge() -> None:
    observation = parse_live_broker_card(_fixture("live_listing_group.html"))

    assert observation.article_href == "/articles/2639879471"
    assert observation.provider == "부동산포스"
    assert (
        observation.description
        == "시스템 에어컨2. 중문. 식기세척기. 시에2. 중문"
    )
    assert observation.is_npay is True


def test_broker_provider_ignores_empty_svg_leaf_nodes() -> None:
    observation = parse_live_broker_card(
        """
        <li>
          <p>"<span>중문 설치</span>"</p>
          <ul>
            <li>확인매물 2026.07.24</li>
            <li>신동탄공인중개사사무소</li>
            <li><button>부동산뱅크</button></li>
          </ul>
          <button>
            <svg><path d="M0 0"></path></svg>
            <span>관심매물</span>
          </button>
          <a data-nlogs-area="article*l.group"
             href="/articles/2639749182">
            <span>매물 보러가기</span>
          </a>
        </li>
        """
    )

    assert observation.provider == "부동산뱅크"


def test_broker_provider_uses_article_broker_info_after_early_interest_button() -> None:
    observation = parse_live_broker_card(
        """
        <li>
          <button><span>관심매물</span></button>
          <p>"즉시입주 가능"</p>
          <span>확인매물 2026.07.25</span>
          <ul data-sentry-component="ArticleBrokerInfo">
            <li>신동탄공인중개사사무소</li>
            <li><button>부동산렛츠</button></li>
          </ul>
          <a data-nlogs-area="article*l.list"
             href="/articles/2639086493">
            <span>매물 보러가기</span>
          </a>
        </li>
        """
    )

    assert observation.provider == "부동산렛츠"


def test_does_not_infer_missing_broker_provider() -> None:
    observation = parse_live_broker_card(
        """
        <div>
          <span>9억</span>
          <span>"짧은 소개"</span>
          <span>확인매물 2026.07.24.</span>
          <span>샘플중개사</span>
          <button>관심매물</button>
          <a href="/out-link-bridge?articleId=2639879472">외부 매물 보기</a>
          <a href="/articles/2639879472">매물 보러가기</a>
        </div>
        """
    )

    assert observation.article_href == "/articles/2639879472"
    assert observation.description == "짧은 소개"
    assert observation.provider == ""
    assert observation.is_npay is False


@pytest.mark.parametrize(
    ("action_text", "is_npay"),
    [
        ("매물 보러가기", False),
        ("Npay 부동산에서 보기", True),
    ],
)
def test_extracts_provider_before_action_when_interest_precedes_confirmation(
    action_text: str,
    is_npay: bool,
) -> None:
    observation = parse_live_broker_card(
        f"""
        <div>
          <span>9억</span>
          <span>"짧은 소개"</span>
          <button>관심매물</button>
          <span>확인매물 2026.07.24.</span>
          <span>샘플중개사</span>
          <span>부동산뱅크 제공</span>
          <a href="/articles/2639879473">{action_text}</a>
        </div>
        """
    )

    assert observation.article_href == "/articles/2639879473"
    assert observation.provider == "부동산뱅크"
    assert observation.is_npay is is_npay


def test_normalizes_only_observed_option_aliases_in_first_seen_order() -> None:
    assert extract_option_mentions(
        "중문, 시스템 에어컨2, 식세기, 시에2, 중문, 붙박이장"
    ) == ["중문", "시스템에어컨", "식기세척기"]


def test_parses_live_article_fields_and_prioritizes_caller_metadata() -> None:
    detail = parse_broker_article(
        _fixture("live_article_detail.html"),
        article_url="https://fin.land.naver.com/articles/111",
        provider="caller-provider",
        is_npay=False,
        captured_at=CAPTURED_AT,
    )

    assert detail.article_id == "2639879471"
    assert detail.provider == "caller-provider"
    assert detail.is_npay is False
    assert detail.advertised_price == 900_000_000
    assert detail.management_fee == 240_000
    assert detail.supply_area_m2 == Decimal("81.03")
    assert detail.exclusive_area_m2 == Decimal("59.98")
    assert detail.floor == "27/29층"
    assert detail.room_count == 3
    assert detail.bathroom_count == 2
    assert detail.direction == "남동향"
    assert detail.structure == "단층"
    assert detail.move_in_date == "즉시입주 협의 가능"
    assert detail.option_tags == ["시스템에어컨", "중문", "식기세척기"]
    assert detail.realtor is None


@pytest.mark.parametrize(
    ("label", "displayed_price", "expected_price"),
    [
        ("매매가", "9억", 900_000_000),
        ("전세가", "16억", 1_600_000_000),
    ],
)
def test_parses_trade_specific_detail_price_as_advertised_price(
    label: str,
    displayed_price: str,
    expected_price: int,
) -> None:
    detail = parse_broker_article(
        f"""
        <section>
          <div><span>{label}</span><span>{displayed_price}</span></div>
        </section>
        """,
        article_url="https://fin.land.naver.com/articles/2639879473",
        provider="부동산뱅크",
        is_npay=False,
        captured_at=CAPTURED_AT,
    )

    assert detail.advertised_price == expected_price


def test_parses_privacy_minimized_active_article_slide_fixture() -> None:
    fixture_path = FIXTURES / "live_article_slide.html"

    assert fixture_path.exists(), "active article slide fixture is missing"
    html = fixture_path.read_text(encoding="utf-8")
    detail = parse_broker_article(html, captured_at=CAPTURED_AT)

    assert detail.article_id == "2637329815"
    assert detail.provider == "부동산포스"
    assert detail.is_npay is True
    assert detail.advertised_price == 900_000_000
    assert detail.management_fee == 240_000
    assert detail.supply_area_m2 == Decimal("81.03")
    assert detail.exclusive_area_m2 == Decimal("59.98")
    assert detail.floor == "27/29층"
    assert detail.room_count == 3
    assert detail.bathroom_count == 2
    assert detail.direction == "남동향"
    assert detail.structure == "판상형"
    assert detail.move_in_date == "즉시입주 협의"
    assert detail.description == ""
    assert detail.option_tags == ["시스템에어컨"]
    assert detail.realtor is None
    assert detail.captured_at == CAPTURED_AT
    assert "전화번호" not in html
    assert "중개사주소" not in html
    assert "등록번호" not in html


def test_classifies_live_market_pairs_and_preserves_unknown_values() -> None:
    details = parse_market_details(
        _fixture("live_article_detail.html"), captured_at=CAPTURED_AT
    )

    assert details.finance["대출한도"] == "5억 4,000만원"
    assert details.costs["중개보수"] == "360만원"
    assert details.complex["세대수"] == "1,234세대"
    assert details.extra_fields["기타교통"] == "광역버스"
    assert details.captured_at == CAPTURED_AT

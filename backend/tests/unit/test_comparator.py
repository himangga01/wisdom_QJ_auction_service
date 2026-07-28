from app.domain.comparator import (
    ComparableListing,
    compare_listings,
    transition_absence,
    transition_presence,
)


def listing(**changes) -> ComparableListing:
    values = {
        "price": 720_000_000,
        "deposit": None,
        "monthly_rent": None,
        "management_fee": "25만원",
        "move_in_date": "즉시입주",
        "floor": "12/25층",
        "direction": "남향",
        "option_tags": ("식기세척기",),
        "article_ids": frozenset({"1", "2"}),
    }
    values.update(changes)
    return ComparableListing(**values)


def test_changed_fields_are_auditable() -> None:
    change = compare_listings(
        listing(), listing(price=698_000_000, option_tags=("식기세척기", "전자계약"))
    )

    assert change.event_type == "changed"
    assert change.changed_fields == ("price", "optionTags")
    assert change.before == {"price": 720_000_000, "optionTags": ["식기세척기"]}
    assert change.after == {
        "price": 698_000_000,
        "optionTags": ["식기세척기", "전자계약"],
    }


def test_only_two_consecutive_complete_absences_remove_listing() -> None:
    suppressed = transition_absence(state="active", missing_count=0, run_status="partial")
    first = transition_absence(state="active", missing_count=0, run_status="completed")
    second = transition_absence(
        state=first.state, missing_count=first.missing_count, run_status="completed"
    )

    assert (suppressed.state, suppressed.missing_count, suppressed.event_type) == (
        "active",
        0,
        None,
    )
    assert (first.state, first.missing_count, first.event_type) == ("missing", 1, "missing")
    assert (second.state, second.missing_count, second.event_type) == ("removed", 2, "removed")


def test_reappearance_restores_existing_group() -> None:
    transition = transition_presence(state="removed", missing_count=2)
    assert (transition.state, transition.missing_count, transition.event_type) == (
        "active",
        0,
        "restored",
    )


def test_detail_fields_are_gated_but_price_and_article_ids_are_not() -> None:
    change = compare_listings(
        listing(),
        listing(
            price=698_000_000,
            management_fee="30만원",
            move_in_date="협의",
            option_tags=("전자계약",),
            article_ids=frozenset({"2", "3"}),
        ),
        compare_detail_fields=False,
    )

    assert change.changed_fields == ("price", "articleIds")
    assert change.before == {"price": 720_000_000, "articleIds": ["1", "2"]}
    assert change.after == {"price": 698_000_000, "articleIds": ["2", "3"]}

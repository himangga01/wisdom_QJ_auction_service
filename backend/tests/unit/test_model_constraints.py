from datetime import time

import pytest
from pydantic import ValidationError
from sqlalchemy import BigInteger, CheckConstraint, Numeric, UniqueConstraint

from app.models import Base
from app.schemas.analysis import AnalysisCreate
from app.schemas.schedule import ScheduleCreate


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_required_tables_are_registered() -> None:
    assert {
        "tracked_sources",
        "crawl_runs",
        "apartments",
        "apartment_snapshots",
        "listing_groups",
        "listing_snapshots",
        "broker_articles",
        "broker_article_snapshots",
        "listing_aggregates",
        "market_detail_snapshots",
        "change_events",
        "crawl_schedules",
        "source_listing_states",
    }.issubset(Base.metadata.tables)


def test_identity_and_snapshot_uniqueness_constraints() -> None:
    assert ("url_hash",) not in _unique_column_sets("tracked_sources")
    assert ("owner_user_id", "url_hash") in _unique_column_sets("tracked_sources")
    assert ("source_id", "listing_group_id") in _unique_column_sets(
        "source_listing_states"
    )
    assert ("naver_complex_id",) in _unique_column_sets("apartments")
    assert ("naver_article_id",) in _unique_column_sets("broker_articles")
    assert ("run_id", "listing_group_id") in _unique_column_sets(
        "listing_snapshots"
    )
    assert ("run_id", "broker_article_id") in _unique_column_sets(
        "broker_article_snapshots"
    )


def test_money_area_and_timestamp_types_match_storage_contract() -> None:
    listing = Base.metadata.tables["listing_snapshots"]
    assert isinstance(listing.c.price.type, BigInteger)
    assert isinstance(listing.c.deposit.type, BigInteger)
    assert isinstance(listing.c.monthly_rent.type, BigInteger)
    assert isinstance(listing.c.supply_area.type, Numeric)
    assert listing.c.supply_area.type.precision == 10
    assert listing.c.supply_area.type.scale == 2
    assert listing.c.captured_at.type.timezone is True


def test_foreign_keys_preserve_history_instead_of_cascading_deletes() -> None:
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.ondelete != "CASCADE"


def test_broker_detail_collection_defaults_to_enabled() -> None:
    analysis = AnalysisCreate(sourceUrl="https://fin.land.naver.com/map?a=1")
    schedule = ScheduleCreate(
        sourceUrl="https://fin.land.naver.com/map?a=1",
        cadence="daily",
        time=time(9),
    )

    assert analysis.collect_broker_details is True
    assert schedule.collect_broker_details is True
    for table_name in ("crawl_runs", "crawl_schedules"):
        column = Base.metadata.tables[table_name].c.collect_broker_details
        assert column.default.arg is True
        assert str(column.server_default.arg) == "true"


def test_interaction_delay_preset_defaults_validation_and_storage_contract() -> None:
    analysis = AnalysisCreate(sourceUrl="https://fin.land.naver.com/map?a=1")

    assert analysis.interaction_delay_preset == "normal"
    with pytest.raises(ValidationError):
        AnalysisCreate(
            sourceUrl="https://fin.land.naver.com/map?a=1",
            interactionDelayPreset="turbo",
        )

    expected_values = {
        "very_fast",
        "fast",
        "normal",
        "careful",
        "very_careful",
    }
    for table_name in ("crawl_runs", "crawl_schedules"):
        table = Base.metadata.tables[table_name]
        column = table.c.interaction_delay_preset
        assert column.nullable is False
        assert column.default.arg == "normal"
        assert str(column.server_default.arg) == "'normal'"
        check_sql = " ".join(
            str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
        assert "interaction_delay_preset IN" in check_sql
        assert all(value in check_sql for value in expected_values)

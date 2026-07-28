from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


VERSIONS = Path(__file__).parents[2] / "alembic" / "versions"


def _load(name: str):
    path = VERSIONS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sqlite_legacy_owner_default_uses_uuid_hex_storage() -> None:
    migration = _load("0007_auth_principal_and_source_owner_expand.py")

    assert str(migration._legacy_owner_server_default("sqlite")) == (
        "'00000000000000000000000000000001'"
    )
    assert str(migration._legacy_owner_server_default("postgresql")) == (
        "'00000000-0000-0000-0000-000000000001'"
    )


class _Rows:
    def first(self):
        return ("duplicate-hash", 2)


class _Bind:
    def execute(self, _statement):
        return _Rows()


def test_owner_downgrade_refuses_to_restore_global_url_uniqueness_with_duplicates() -> None:
    migration = _load("0008_source_owner_contract_and_listing_state.py")

    with pytest.raises(RuntimeError, match="duplicate tracked source URL hashes"):
        migration._assert_global_url_hashes_unique(_Bind())

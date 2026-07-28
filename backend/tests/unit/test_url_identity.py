import pytest

from app.domain.url_identity import InvalidSourceUrl, normalize_source_url


def test_normalizes_query_order_and_removes_fragment() -> None:
    first = normalize_source_url(
        "https://fin.land.naver.com/map?zoom=17&center=abc#listing"
    )
    second = normalize_source_url(
        "https://fin.land.naver.com/map?center=abc&zoom=17"
    )

    assert first.normalized_url == (
        "https://fin.land.naver.com/map?center=abc&zoom=17"
    )
    assert first.url_hash == second.url_hash


@pytest.mark.parametrize(
    "url",
    [
        "http://fin.land.naver.com/map?complexId=1",
        "https://land.naver.com/map?complexId=1",
        "https://fin.land.naver.com.evil.example/map?complexId=1",
    ],
)
def test_rejects_non_https_and_external_hosts(url: str) -> None:
    with pytest.raises(InvalidSourceUrl) as error:
        normalize_source_url(url)

    assert error.value.code == "invalid_source_url"


def test_preserves_duplicate_parameters_in_deterministic_order() -> None:
    identity = normalize_source_url(
        "https://fin.land.naver.com/map?tag=z&tag=a&empty="
    )

    assert identity.normalized_url == (
        "https://fin.land.naver.com/map?empty=&tag=a&tag=z"
    )

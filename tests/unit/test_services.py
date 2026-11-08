from __future__ import annotations

from campus.core.pagination import clamp_page
from campus.services.academics import compute_final


def test_compute_final_weights() -> None:
    assert compute_final(80.0, 90.0) == 86.0
    assert compute_final(100.0, 100.0) == 100.0
    assert compute_final(0.0, 0.0) == 0.0


def test_compute_final_requires_both_parts() -> None:
    assert compute_final(None, 90.0) is None
    assert compute_final(80.0, None) is None


def test_clamp_page_limits_range() -> None:
    params = clamp_page(0, 500)
    assert params.page == 1
    assert params.page_size == 100
    assert params.offset == 0

    second = clamp_page(3, 10)
    assert second.offset == 20

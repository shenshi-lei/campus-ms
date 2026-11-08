from __future__ import annotations

from datetime import date

from campus.services.timetable import parse_weeks, week_number


def test_parse_weeks_supports_ranges_and_odd_even() -> None:
    assert parse_weeks("1-4") == {1, 2, 3, 4}
    assert parse_weeks("1-6单") == {1, 3, 5}
    assert parse_weeks("1-6双") == {2, 4, 6}
    assert parse_weeks("1,3,5") == {1, 3, 5}
    assert parse_weeks("1-3,7-9") == {1, 2, 3, 7, 8, 9}
    assert parse_weeks("1-16（单）") == {1, 3, 5, 7, 9, 11, 13, 15}
    assert parse_weeks("") == set()


def test_week_number_uses_semester_start() -> None:
    start = date(2026, 9, 1)
    assert week_number(start, date(2026, 9, 1)) == 1
    assert week_number(start, date(2026, 9, 7)) == 1
    assert week_number(start, date(2026, 9, 8)) == 2
    assert week_number(start, date(2026, 10, 20)) == 8

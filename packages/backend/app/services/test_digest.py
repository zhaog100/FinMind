"""Tests for the digest service."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


class TestParseWeek:
    def _import(self):
        from packages.backend.app.services.digest import _parse_week
        return _parse_week

    def test_basic(self):
        _parse_week = self._import()
        start, end = _parse_week("2026-W12")
        assert start == date(2026, 3, 16)
        assert end == date(2026, 3, 22)

    def test_week_1(self):
        _parse_week = self._import()
        start, end = _parse_week("2025-W01")
        assert start == date(2024, 12, 30)
        assert end == date(2025, 1, 5)


class TestWeekKey:
    def test_basic(self):
        from packages.backend.app.services.digest import _week_key
        assert _week_key(date(2026, 3, 16)) == "2026-W12"


class TestComputeWoWChanges:
    def _import(self):
        from packages.backend.app.services.digest import compute_wow_changes
        return compute_wow_changes

    def test_increase(self):
        compute = self._import()
        result = compute(
            {"income": 1100, "expenses": 1050},
            {"income": 1000, "expenses": 1000},
        )
        assert result["expense_change_pct"] == 5.0
        assert result["income_change_pct"] == 10.0

    def test_decrease(self):
        compute = self._import()
        result = compute(
            {"income": 900, "expenses": 800},
            {"income": 1000, "expenses": 1000},
        )
        assert result["expense_change_pct"] == -20.0
        assert result["income_change_pct"] == -10.0

    def test_zero_previous(self):
        compute = self._import()
        result = compute(
            {"income": 500, "expenses": 500},
            {"income": 0, "expenses": 0},
        )
        assert result["expense_change_pct"] is None
        assert result["income_change_pct"] is None


class TestGenerateInsights:
    def _import(self):
        from packages.backend.app.services.digest import generate_insights
        return generate_insights

    def test_expense_increase(self):
        gen = self._import()
        data = {
            "week_over_week": {"expense_change_pct": 5.2, "income_change_pct": None},
            "top_categories": [{"name": "Food", "amount": 100, "percentage": 50.0}],
            "savings_rate": 20.0,
        }
        insights = gen(data)
        assert any("5.2%" in i and "increased" in i for i in insights)
        assert any("Food" in i for i in insights)

    def test_positive_savings(self):
        gen = self._import()
        data = {
            "week_over_week": {"expense_change_pct": 0, "income_change_pct": 0},
            "top_categories": [],
            "savings_rate": 35.0,
        }
        insights = gen(data)
        assert any("strong" in i.lower() for i in insights)

    def test_negative_savings(self):
        gen = self._import()
        data = {
            "week_over_week": {"expense_change_pct": 0, "income_change_pct": 0},
            "top_categories": [],
            "savings_rate": -5.0,
        }
        insights = gen(data)
        assert any("spent more" in i.lower() for i in insights)

    def test_empty_data_fallback(self):
        gen = self._import()
        insights = gen({})
        assert len(insights) >= 1


class TestGetCategoryBreakdown:
    def test_empty(self):
        with patch("packages.backend.app.services.digest.db") as mock_db:
            mock_query = MagicMock()
            mock_db.session.query.return_value = mock_query
            mock_query.outerjoin.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.group_by.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []

            from packages.backend.app.services.digest import get_category_breakdown
            result = get_category_breakdown(1, date(2026, 3, 16), date(2026, 3, 22))
            assert result == []

    def test_with_data(self):
        mock_row = MagicMock()
        mock_row.category_id = 1
        mock_row.category_name = "Food"
        mock_row.total_amount = 1000

        with patch("packages.backend.app.services.digest.db") as mock_db:
            mock_query = MagicMock()
            mock_db.session.query.return_value = mock_query
            mock_query.outerjoin.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.group_by.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = [mock_row]

            from packages.backend.app.services.digest import get_category_breakdown
            result = get_category_breakdown(1, date(2026, 3, 16), date(2026, 3, 22))
            assert len(result) == 1
            assert result[0]["name"] == "Food"
            assert result[0]["amount"] == 1000.0
            assert result[0]["percentage"] == 100.0

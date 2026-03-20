"""Weekly digest service — computes summaries, WoW changes, and insights."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func

from ..extensions import db
from ..models import Expense, Category, RecurringExpense


# ── helpers ──────────────────────────────────────────────────────────


def _parse_week(week_str: str) -> tuple[date, date]:
    """Parse 'YYYY-WNN' into (monday, sunday)."""
    year, week_num = week_str.split("-W")
    year, week_num = int(year), int(week_num)
    monday = date.fromisocalendar(year, week_num, 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _week_key(monday: date) -> str:
    iso = monday.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _prev_week_key(week_str: str) -> str:
    monday, _ = _parse_week(week_str)
    prev_monday = monday - timedelta(weeks=1)
    return _week_key(prev_monday)


# ── public API ───────────────────────────────────────────────────────


def calculate_weekly_digest(user_id: int, week_str: str) -> dict[str, Any]:
    """Build a complete weekly digest for *user_id* and the given ISO week."""
    start, end = _parse_week(week_str)

    total_income = _sum_amount(user_id, start, end, "INCOME")
    total_expenses = _sum_amount(user_id, start, end, "EXPENSE")
    net_savings = round(total_income - total_expenses, 2)
    savings_rate = round(net_savings / total_income * 100, 1) if total_income > 0 else 0.0

    days = 7
    daily_average = round(total_expenses / days, 2)

    recurring_total = _recurring_total(user_id, start, end)

    top_categories = get_category_breakdown(user_id, start, end)

    # WoW comparison
    prev_week = _prev_week_key(week_str)
    prev_start, prev_end = _parse_week(prev_week)
    prev_income = _sum_amount(user_id, prev_start, prev_end, "INCOME")
    prev_expenses = _sum_amount(user_id, prev_start, prev_end, "EXPENSE")

    wow = compute_wow_changes(
        {"income": total_income, "expenses": total_expenses},
        {"income": prev_income, "expenses": prev_expenses},
    )

    data = {
        "week": week_str,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": net_savings,
        "savings_rate": savings_rate,
        "top_categories": top_categories,
        "daily_average": daily_average,
        "recurring_total": recurring_total,
        "week_over_week": wow,
        "insights": [],
    }

    data["insights"] = generate_insights(data)
    return data


def compute_wow_changes(
    current: dict[str, float],
    previous: dict[str, float],
) -> dict[str, float | None]:
    """Compute percentage changes for income and expenses vs previous week."""
    expense_pct = None
    income_pct = None

    if previous["expenses"] and previous["expenses"] > 0:
        expense_pct = round(
            (current["expenses"] - previous["expenses"]) / previous["expenses"] * 100, 1
        )
    if previous["income"] and previous["income"] > 0:
        income_pct = round(
            (current["income"] - previous["income"]) / previous["income"] * 100, 1
        )

    return {"expense_change_pct": expense_pct, "income_change_pct": income_pct}


def generate_insights(data: dict[str, Any]) -> list[str]:
    """Produce a list of plain-text insight strings from digest data."""
    insights: list[str] = []

    wow = data.get("week_over_week", {})
    exp_pct = wow.get("expense_change_pct")
    inc_pct = wow.get("income_change_pct")

    if exp_pct is not None:
        if exp_pct > 0:
            insights.append(f"Spending increased {exp_pct}% vs last week")
        elif exp_pct < 0:
            insights.append(f"Spending decreased {abs(exp_pct)}% vs last week — great job!")
        else:
            insights.append("Spending stayed flat compared to last week")

    if inc_pct is not None:
        if inc_pct > 0:
            insights.append(f"Income grew {inc_pct}% compared to last week")
        elif inc_pct < 0:
            insights.append(f"Income dropped {abs(inc_pct)}% compared to last week")

    cats = data.get("top_categories", [])
    if cats:
        top = cats[0]
        insights.append(f"{top['name']} is the highest spending category ({top['percentage']:.1f}%)")

    savings_rate = data.get("savings_rate", 0)
    if savings_rate >= 30:
        insights.append(f"Savings rate is strong at {savings_rate}%")
    elif savings_rate > 0:
        insights.append(f"Savings rate is {savings_rate}% — consider aiming for 30%+")
    else:
        insights.append("You spent more than you earned this week — review expenses")

    if not insights:
        insights.append("No significant patterns detected this week")

    return insights


def get_category_breakdown(
    user_id: int,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Return top spending categories for a date range."""
    rows = (
        db.session.query(
            Expense.category_id,
            func.coalesce(Category.name, "Uncategorized").label("category_name"),
            func.coalesce(func.sum(Expense.amount), 0).label("total_amount"),
        )
        .outerjoin(
            Category,
            (Category.id == Expense.category_id) & (Category.user_id == user_id),
        )
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start,
            Expense.spent_at <= end,
            Expense.expense_type != "INCOME",
        )
        .group_by(Expense.category_id, Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .limit(10)
        .all()
    )

    total = sum(float(r.total_amount or 0) for r in rows)
    return [
        {
            "name": r.category_name,
            "amount": round(float(r.total_amount or 0), 2),
            "percentage": round(float(r.total_amount or 0) / total * 100, 1)
            if total > 0
            else 0,
        }
        for r in rows
    ]


def get_trends(user_id: int, num_weeks: int) -> list[dict[str, Any]]:
    """Return digest summaries for the last *num_weeks* weeks (including current)."""
    today = date.today()
    current_iso = today.isocalendar()
    current_monday = date.fromisocalendar(current_iso[0], current_iso[1], 1)
    weeks: list[dict[str, Any]] = []

    for i in range(num_weeks - 1, -1, -1):
        monday = current_monday - timedelta(weeks=i)
        sunday = monday + timedelta(days=6)
        week_str = _week_key(monday)

        income = _sum_amount(user_id, monday, sunday, "INCOME")
        expenses = _sum_amount(user_id, monday, sunday, "EXPENSE")
        weeks.append(
            {
                "week": week_str,
                "period": {"start": monday.isoformat(), "end": sunday.isoformat()},
                "total_income": income,
                "total_expenses": expenses,
                "net_savings": round(income - expenses, 2),
                "savings_rate": round((income - expenses) / income * 100, 1)
                if income > 0
                else 0.0,
            }
        )

    return weeks


# ── private helpers ──────────────────────────────────────────────────


def _sum_amount(user_id: int, start: date, end: date, expense_type: str) -> float:
    val = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start,
            Expense.spent_at <= end,
            Expense.expense_type == expense_type,
        )
        .scalar()
    )
    return float(val or 0)


def _recurring_total(user_id: int, start: date, end: date) -> float:
    val = (
        db.session.query(func.coalesce(func.sum(RecurringExpense.amount), 0))
        .filter(
            RecurringExpense.user_id == user_id,
            RecurringExpense.active.is_(True),
            RecurringExpense.start_date <= end,
            (RecurringExpense.end_date.is_(None)) | (RecurringExpense.end_date >= start),
        )
        .scalar()
    )
    return float(val or 0)

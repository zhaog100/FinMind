"""Smart reminder timing optimization based on user behavior."""

import logging
from collections import defaultdict
from datetime import datetime, date, timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Expense, Reminder

bp = Blueprint("smart_reminder", __name__)
logger = logging.getLogger("finmind.smart_reminder")


@bp.get("/insights")
@jwt_required()
def timing_insights():
    """Analyze user expense patterns to suggest optimal reminder timing."""
    uid = int(get_jwt_identity())
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.spent_at).all()

    if not expenses:
        return jsonify({"message": "No expense data", "suggestions": []})

    # Analyze spending by day of week and time patterns
    dow_counts = defaultdict(int)
    dow_amounts = defaultdict(float)
    for exp in expenses:
        if exp.spent_at:
            dow = exp.spent_at.weekday()
            dow_counts[dow] += 1
            dow_amounts[dow] += float(exp.amount)

    # Find most active days
    avg_amounts = {k: v / max(dow_counts[k], 1) for k, v in dow_amounts.items()}
    top_days = sorted(avg_amounts.items(), key=lambda x: x[1], reverse=True)[:3]

    # Monthly spending patterns
    monthly = defaultdict(float)
    for exp in expenses:
        if exp.spent_at:
            monthly[exp.spent_at.strftime("%Y-%m")] += float(exp.amount)

    # Predict next month spending based on trend
    months_sorted = sorted(monthly.items())
    trend = None
    if len(months_sorted) >= 2:
        recent = [v for _, v in months_sorted[-3:]]
        if len(recent) >= 2:
            trend = "increasing" if recent[-1] > recent[0] * 1.05 else ("decreasing" if recent[-1] < recent[0] * 0.95 else "stable")

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    suggestions = []
    for dow, avg in top_days:
        suggestions.append({
            "type": "best_day",
            "day": day_names[dow],
            "day_index": dow,
            "avg_spending": round(avg, 2),
            "transaction_count": dow_counts[dow],
            "tip": f"You spend most on {day_names[dow]}s. Set reminders the day before.",
        })

    if trend:
        suggestions.append({
            "type": "spending_trend",
            "trend": trend,
            "tip": f"Spending is {trend}. {'Consider tightening budgets.' if trend == 'increasing' else 'Good job!'}",
        })

    # Suggest reminder frequency
    total_expenses = len(expenses)
    if total_expenses > 50:
        suggestions.append({"type": "frequency", "recommended": "weekly", "tip": "High activity — weekly check-ins recommended."})
    elif total_expenses > 20:
        suggestions.append({"type": "frequency", "recommended": "biweekly", "tip": "Moderate activity — biweekly reviews are sufficient."})
    else:
        suggestions.append({"type": "frequency", "recommended": "monthly", "tip": "Light activity — monthly review is fine."})

    return jsonify({
        "total_expenses": total_expenses,
        "spending_by_day": {day_names[k]: {"count": dow_counts[k], "avg": round(avg_amounts[k], 2)} for k in dow_counts},
        "monthly_totals": dict(sorted(monthly.items())[-6:]),
        "trend": trend,
        "suggestions": suggestions,
    })


@bp.get("/optimal-times")
@jwt_required()
def optimal_times():
    """Get suggested reminder days based on bill/recurring patterns."""
    uid = int(get_jwt_identity())
    reminders = Reminder.query.filter_by(user_id=uid).all()

    if not reminders:
        return jsonify({"message": "No reminders set", "optimal_days": []})

    # Extract due dates
    due_days = []
    for r in reminders:
        if r.due_date:
            due_days.append(r.due_date.day)

    if not due_days:
        return jsonify({"message": "No due dates found", "optimal_days": []})

    # Suggest reminding 3 days before most common due date
    from collections import Counter
    common_days = Counter(due_days).most_common(3)
    optimal = []
    for day, count in common_days:
        reminder_day = day - 3 if day > 3 else 28 - (3 - day)
        optimal.append({
            "due_day": day,
            "bills_count": count,
            "reminder_day": reminder_day,
            "tip": f"Remind on day {reminder_day} for {count} bill(s) due on day {day}",
        })

    return jsonify({"optimal_days": optimal})

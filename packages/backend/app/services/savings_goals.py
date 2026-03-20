from datetime import date, datetime
from decimal import Decimal
from ..models import SavingsGoal


def _pct(current: Decimal, target: Decimal) -> float:
    if target <= 0:
        return 100.0 if current >= target else 0.0
    return round(float(current / target) * 100, 2)


def calculate_progress(goal: SavingsGoal) -> dict:
    target = Decimal(goal.target_amount)
    current = Decimal(goal.current_amount)
    pct = _pct(current, target)
    remaining = round(float(max(target - current, 0)), 2)
    days_left = None
    if goal.target_date:
        delta = (goal.target_date - date.today()).days
        days_left = max(delta, 0)
    return {
        "percentage": pct,
        "current_amount": float(current),
        "target_amount": float(target),
        "remaining": remaining,
        "days_left": days_left,
        "is_completed": pct >= 100,
    }


def auto_milestones(goal: SavingsGoal) -> list[str]:
    target = Decimal(goal.target_amount)
    return [
        f"25% – {float(target * Decimal('0.25')):.2f}",
        f"50% – {float(target * Decimal('0.50')):.2f}",
        f"75% – {float(target * Decimal('0.75')):.2f}",
        f"100% – {float(target):.2f}",
    ]


def check_milestone(goal: SavingsGoal) -> dict:
    """Return newly achieved milestones and update the goal's milestone list."""
    target = Decimal(goal.target_amount)
    current = Decimal(goal.current_amount)
    existing = set(goal.milestones or [])
    thresholds = [25, 50, 75, 100]
    newly_achieved = []
    for t in thresholds:
        label = f"{t}%"
        if label not in existing and _pct(current, target) >= t:
            newly_achieved.append(label)
            existing.add(label)
    goal.milestones = sorted(existing)
    goal.updated_at = datetime.utcnow()
    return {"new_milestones": newly_achieved, "all_milestones": sorted(existing)}

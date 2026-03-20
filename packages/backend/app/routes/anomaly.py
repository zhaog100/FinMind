"""Recurring transaction anomaly alerts."""

import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Expense

bp = Blueprint("anomaly", __name__)
logger = logging.getLogger("finmind.anomaly")


@bp.get("")
@jwt_required()
def list_anomalies():
    """List recent anomaly alerts for the user."""
    uid = int(get_jwt_identity())
    alerts = AnomalyAlert.query.filter_by(user_id=uid).order_by(AnomalyAlert.created_at.desc()).limit(50).all()
    return jsonify([a.to_dict() for a in alerts])


@bp.post("/scan")
@jwt_required()
def scan_anomalies():
    """Scan for recurring transaction anomalies."""
    uid = int(get_jwt_identity())
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.spent_at).all()

    # Group by payee/notes
    groups = defaultdict(list)
    for exp in expenses:
        key = (exp.payee or exp.notes or "").strip().lower()
        if key:
            groups[key].append(exp)

    anomalies = []
    for key, exps in groups.items():
        if len(exps) < 3:
            continue

        amounts = [float(e.amount) for e in exps]
        avg = sum(amounts) / len(amounts)
        std = (sum((a - avg) ** 2 for a in amounts) / len(amounts)) ** 0.5

        # Check for amount spikes (>2 std dev or >50% change)
        for i, exp in enumerate(exps):
            if i == 0:
                continue
            pct_change = abs(float(exp.amount) - amounts[i-1]) / max(amounts[i-1], 0.01)
            deviation = abs(float(exp.amount) - avg)
            is_anomaly = False
            reason = ""

            if std > 0 and deviation > 2 * std:
                is_anomaly = True
                reason = f"Amount deviation: {float(exp.amount):.2f} vs avg {avg:.2f} ({deviation/std:.1f}x std)"
            elif pct_change > 0.5:
                is_anomaly = True
                reason = f"Amount change: {amounts[i-1]:.2f} → {float(exp.amount):.2f} ({pct_change*100:.0f}% change)"

            # Check for missed payment (gap > 1.5x average interval)
            if i >= 2:
                intervals = [(exps[j].spent_at - exps[j-1].spent_at).days for j in range(1, i+1)]
                avg_interval = sum(intervals) / len(intervals)
                last_gap = intervals[-1]
                if avg_interval > 0 and last_gap > 1.5 * avg_interval and last_gap - avg_interval > 7:
                    is_anomaly = True
                    reason = f"Payment gap: {last_gap} days (avg {avg_interval:.0f} days)"

            if is_anomaly:
                alert = AnomalyAlert(
                    user_id=uid, expense_id=exp.id,
                    anomaly_type="amount_spike" if "Amount" in reason else "payment_gap",
                    description=reason, severity="high" if pct_change > 1.0 else "medium",
                    merchant_hint=key[:100],
                )
                db.session.add(alert)
                anomalies.append(alert.to_dict())

    db.session.commit()
    return jsonify({"anomalies_found": len(anomalies), "anomalies": anomalies[:100]})


@bp.post("/<int:alert_id>/dismiss")
@jwt_required()
def dismiss_alert(alert_id):
    uid = int(get_jwt_identity())
    alert = AnomalyAlert.query.filter_by(id=alert_id, user_id=uid).first()
    if not alert:
        return jsonify({"error": "Alert not found"}), 404
    alert.status = "dismissed"
    db.session.commit()
    return jsonify({"message": "Dismissed"})


# --- Model defined inline since this is a new feature ---
from ..models import db as _db, User
from datetime import datetime

class AnomalyAlert(db.Model):
    __tablename__ = "anomaly_alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=True)
    anomaly_type = db.Column(db.String(50), nullable=False)  # amount_spike, payment_gap, new_merchant
    description = db.Column(db.String(500), nullable=True)
    severity = db.Column(db.String(20), default="medium")  # low, medium, high
    status = db.Column(db.String(20), default="new")  # new, dismissed, acknowledged
    merchant_hint = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id,
            "expense_id": self.expense_id,
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "merchant_hint": self.merchant_hint,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

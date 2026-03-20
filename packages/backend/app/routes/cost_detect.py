"""Subscription cost increase detection."""

import logging
from collections import defaultdict
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Expense

bp = Blueprint("cost_detect", __name__)
logger = logging.getLogger("finmind.cost_detect")


@bp.get("/increases")
@jwt_required()
def list_increases():
    """List detected subscription cost increases."""
    uid = int(get_jwt_identity())
    alerts = CostIncreaseAlert.query.filter_by(user_id=uid).order_by(CostIncreaseAlert.created_at.desc()).limit(50).all()
    return jsonify([a.to_dict() for a in alerts])


@bp.post("/scan")
@jwt_required()
def scan_cost_increases():
    """Scan for subscription cost increases."""
    uid = int(get_jwt_identity())
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.spent_at).all()

    # Group by merchant
    groups = defaultdict(list)
    for exp in expenses:
        key = (exp.payee or exp.notes or "").strip().lower()
        if key:
            groups[key].append(exp)

    increases = []
    for key, exps in groups.items():
        if len(exps) < 2:
            continue

        amounts = [float(e.amount) for e in exps]
        for i in range(1, len(exps)):
            old_amt = amounts[i - 1]
            new_amt = amounts[i]
            if new_amt > old_amt:
                pct = (new_amt - old_amt) / max(old_amt, 0.01)
                if pct >= 0.05:  # 5% threshold
                    alert = CostIncreaseAlert(
                        user_id=uid,
                        expense_id=exps[i].id,
                        merchant=key[:255],
                        old_amount=old_amt,
                        new_amount=new_amt,
                        percent_increase=round(pct * 100, 2),
                        currency=exps[i].currency,
                        old_date=exps[i-1].spent_at.isoformat() if exps[i-1].spent_at else None,
                        new_date=exps[i].spent_at.isoformat() if exps[i].spent_at else None,
                        status="new",
                    )
                    db.session.add(alert)
                    increases.append(alert.to_dict())

    db.session.commit()
    return jsonify({"increases_found": len(increases), "increases": increases[:100]})


@bp.post("/<int:alert_id>/dismiss")
@jwt_required()
def dismiss(alert_id):
    uid = int(get_jwt_identity())
    alert = CostIncreaseAlert.query.filter_by(id=alert_id, user_id=uid).first()
    if not alert:
        return jsonify({"error": "Alert not found"}), 404
    alert.status = "dismissed"
    db.session.commit()
    return jsonify({"message": "Dismissed"})


class CostIncreaseAlert(db.Model):
    __tablename__ = "cost_increase_alerts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=True)
    merchant = db.Column(db.String(255), nullable=False)
    old_amount = db.Column(db.Float, nullable=False)
    new_amount = db.Column(db.Float, nullable=False)
    percent_increase = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    old_date = db.Column(db.String(20), nullable=True)
    new_date = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id, "merchant": self.merchant,
            "old_amount": self.old_amount, "new_amount": self.new_amount,
            "percent_increase": self.percent_increase,
            "currency": self.currency,
            "old_date": self.old_date, "new_date": self.new_date,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

import logging
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func

from ..extensions import db
from ..models import Expense, User

bp = Blueprint("accounts", __name__)
logger = logging.getLogger("finmind.accounts")

# ---------------------------------------------------------------------------
# In-memory accounts (SQLite + migration-less for the bounty PR)
# ---------------------------------------------------------------------------
# For a production app this would be a proper SQLAlchemy model + Alembic
# migration.  Keeping it simple: JSON stored per user in the database
# via a lightweight approach — we create a real model inline.
# ---------------------------------------------------------------------------

from ..extensions import db


class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    account_type = db.Column(
        db.String(50), nullable=False, default="bank"
    )  # bank / credit_card / investment / cash / wallet
    balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default="USD")
    icon = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


def _account_to_dict(a: Account) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "type": a.account_type,
        "balance": float(a.balance),
        "currency": a.currency,
        "icon": a.icon,
        "color": a.color,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@bp.get("")
@jwt_required()
def list_accounts():
    uid = int(get_jwt_identity())
    accounts = (
        db.session.query(Account)
        .filter_by(user_id=uid)
        .order_by(Account.account_type, Account.name)
        .all()
    )
    logger.info("List accounts user=%s count=%s", uid, len(accounts))
    return jsonify([_account_to_dict(a) for a in accounts])


@bp.post("")
@jwt_required()
def create_account():
    uid = int(get_jwt_identity())
    data = request.get_json() or {}

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400

    valid_types = {"bank", "credit_card", "investment", "cash", "wallet"}
    account_type = data.get("type", "bank").strip().lower()
    if account_type not in valid_types:
        return jsonify(error=f"type must be one of {valid_types}"), 400

    try:
        balance = Decimal(str(data.get("balance", 0)))
    except Exception:
        return jsonify(error="invalid balance"), 400

    currency = (data.get("currency") or "USD").strip().upper()[:10]

    account = Account(
        user_id=uid,
        name=name,
        account_type=account_type,
        balance=balance,
        currency=currency,
        icon=data.get("icon"),
        color=data.get("color"),
    )
    db.session.add(account)
    db.session.commit()

    logger.info("Create account user=%s id=%s name=%s", uid, account.id, name)
    return jsonify(_account_to_dict(account)), 201


@bp.put("/<int:account_id>")
@jwt_required()
def update_account(account_id: int):
    uid = int(get_jwt_identity())
    account = db.session.query(Account).filter_by(id=account_id, user_id=uid).first()
    if not account:
        return jsonify(error="account not found"), 404

    data = request.get_json() or {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify(error="name is required"), 400
        account.name = name

    if "type" in data:
        valid_types = {"bank", "credit_card", "investment", "cash", "wallet"}
        account_type = data["type"].strip().lower()
        if account_type not in valid_types:
            return jsonify(error=f"type must be one of {valid_types}"), 400
        account.account_type = account_type

    if "balance" in data:
        try:
            account.balance = Decimal(str(data["balance"]))
        except Exception:
            return jsonify(error="invalid balance"), 400

    if "currency" in data:
        account.currency = (data["currency"] or "USD").strip().upper()[:10]

    if "icon" in data:
        account.icon = data["icon"]
    if "color" in data:
        account.color = data["color"]

    db.session.commit()
    logger.info("Update account user=%s id=%s", uid, account_id)
    return jsonify(_account_to_dict(account))


@bp.delete("/<int:account_id>")
@jwt_required()
def delete_account(account_id: int):
    uid = int(get_jwt_identity())
    account = db.session.query(Account).filter_by(id=account_id, user_id=uid).first()
    if not account:
        return jsonify(error="account not found"), 404

    db.session.delete(account)
    db.session.commit()
    logger.info("Delete account user=%s id=%s", uid, account_id)
    return jsonify(message="deleted")


@bp.get("/overview")
@jwt_required()
def account_overview():
    uid = int(get_jwt_identity())

    accounts = db.session.query(Account).filter_by(user_id=uid).all()
    total_balance = sum(float(a.balance) for a in accounts)

    # Total income from expenses with expense_type='INCOME'
    total_income = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter_by(user_id=uid, expense_type="INCOME")
        .scalar()
    )
    total_income = float(total_income)

    # Total expenses
    total_expenses = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter_by(user_id=uid, expense_type="EXPENSE")
        .scalar()
    )
    total_expenses = float(total_expenses)

    # Group by type for distribution
    type_map: dict[str, float] = {}
    for a in accounts:
        t = a.account_type
        type_map[t] = type_map.get(t, 0) + float(a.balance)

    net_worth = total_balance - total_expenses

    result = {
        "total_assets": total_balance,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_worth": net_worth,
        "account_count": len(accounts),
        "distribution": type_map,
        "accounts": [_account_to_dict(a) for a in accounts],
    }

    logger.info("Overview user=%s assets=%.2f", uid, total_balance)
    return jsonify(result)

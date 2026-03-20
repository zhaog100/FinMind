"""Advanced search across transactions and bills."""

import logging
from decimal import Decimal
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, and_
from ..extensions import db
from ..models import Expense, Category

bp = Blueprint("search", __name__)
logger = logging.getLogger("finmind.search")


@bp.get("")
@jwt_required()
def advanced_search():
    """Search expenses by merchant, tag, note, category, amount, or date range."""
    uid = int(get_jwt_identity())
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", type=int)
    min_amount = request.args.get("min_amount", type=float)
    max_amount = request.args.get("max_amount", type=float)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    expense_type = request.args.get("expense_type", "").strip().upper()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    query = Expense.query.filter_by(user_id=uid)

    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(
            Expense.notes.ilike(pattern),
            Expense.payee.ilike(pattern),
        ))

    if category_id:
        query = query.filter(Expense.category_id == category_id)

    if min_amount is not None:
        query = query.filter(Expense.amount >= Decimal(str(min_amount)))
    if max_amount is not None:
        query = query.filter(Expense.amount <= Decimal(str(max_amount)))

    if date_from:
        from datetime import datetime
        try:
            query = query.filter(Expense.spent_at >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        from datetime import datetime
        try:
            query = query.filter(Expense.spent_at <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass

    if expense_type and expense_type in ("EXPENSE", "INCOME"):
        query = query.filter(Expense.expense_type == expense_type)

    query = query.order_by(Expense.spent_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    results = []
    for exp in pagination.items:
        cat_name = None
        if exp.category_id:
            cat = Category.query.get(exp.category_id)
            if cat:
                cat_name = cat.name
        results.append({
            "id": exp.id,
            "amount": str(exp.amount),
            "currency": exp.currency,
            "notes": exp.notes,
            "payee": exp.payee,
            "spent_at": exp.spent_at.isoformat() if exp.spent_at else None,
            "expense_type": exp.expense_type,
            "category": cat_name,
        })

    return jsonify({
        "results": results,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })

"""Keyboard shortcuts configuration and API."""

import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db

bp = Blueprint("shortcuts", __name__)
logger = logging.getLogger("finmind.shortcuts")

# Built-in shortcuts
BUILTIN_SHORTCUTS = [
    {"key": "n", "ctrl": True, "action": "new_expense", "description": "Create new expense"},
    {"key": "s", "ctrl": True, "action": "search", "description": "Focus search bar"},
    {"key": "k", "ctrl": True, "action": "command_palette", "description": "Open command palette"},
    {"key": "/", "ctrl": False, "action": "search", "description": "Quick search"},
    {"key": "Escape", "ctrl": False, "action": "close_modal", "description": "Close current modal"},
    {"key": "ArrowLeft", "ctrl": True, "action": "navigate_back", "description": "Go back"},
    {"key": "ArrowRight", "ctrl": True, "action": "navigate_forward", "description": "Go forward"},
    {"key": "t", "ctrl": True, "action": "toggle_theme", "description": "Toggle dark/light theme"},
]


class Shortcut(db.Model):
    __tablename__ = "shortcuts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    key = db.Column(db.String(50), nullable=False)
    ctrl = db.Column(db.Boolean, default=False)
    shift = db.Column(db.Boolean, default=False)
    alt = db.Column(db.Boolean, default=False)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "key", "ctrl", "shift", "alt"),)

    def to_dict(self):
        return {
            "id": self.id, "key": self.key,
            "ctrl": self.ctrl, "shift": self.shift, "alt": self.alt,
            "action": self.action, "description": self.description,
            "is_active": self.is_active,
        }


@bp.get("")
@jwt_required()
def list_shortcuts():
    """List all shortcuts (built-in + user custom)."""
    uid = int(get_jwt_identity())
    customs = Shortcut.query.filter_by(user_id=uid, is_active=True).all()
    return jsonify({
        "builtin": BUILTIN_SHORTCUTS,
        "custom": [s.to_dict() for s in customs],
    })


@bp.post("")
@jwt_required()
def create_shortcut():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    action = (data.get("action") or "").strip()

    if not key or not action:
        return jsonify({"error": "key and action are required"}), 400

    # Check conflict with built-in
    for b in BUILTIN_SHORTCUTS:
        if b["key"].lower() == key.lower() and b.get("ctrl") == data.get("ctrl", False):
            return jsonify({"error": f"Conflicts with built-in shortcut: {b['description']}"}), 409

    sc = Shortcut(
        user_id=uid, key=key,
        ctrl=bool(data.get("ctrl")),
        shift=bool(data.get("shift")),
        alt=bool(data.get("alt")),
        action=action,
        description=data.get("description", ""),
    )
    db.session.add(sc)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Shortcut already exists"}), 409

    return jsonify(sc.to_dict()), 201


@bp.put("/<int:sc_id>")
@jwt_required()
def update_shortcut(sc_id):
    uid = int(get_jwt_identity())
    sc = Shortcut.query.filter_by(id=sc_id, user_id=uid).first()
    if not sc:
        return jsonify({"error": "Shortcut not found"}), 404
    data = request.get_json(silent=True) or {}
    for field in ("key", "action", "description"):
        if field in data:
            setattr(sc, field, data[field].strip())
    if "is_active" in data:
        sc.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify(sc.to_dict())


@bp.delete("/<int:sc_id>")
@jwt_required()
def delete_shortcut(sc_id):
    uid = int(get_jwt_identity())
    sc = Shortcut.query.filter_by(id=sc_id, user_id=uid).first()
    if not sc:
        return jsonify({"error": "Shortcut not found"}), 404
    db.session.delete(sc)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

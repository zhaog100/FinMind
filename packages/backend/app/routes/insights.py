import json
from datetime import date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..services.ai import monthly_budget_suggestion
from ..services.cache import cache_get, cache_set, insights_key
import logging

bp = Blueprint("insights", __name__)
logger = logging.getLogger("finmind.insights")


@bp.get("/budget-suggestion")
@jwt_required()
def budget_suggestion():
    uid = int(get_jwt_identity())
    ym = (request.args.get("month") or date.today().strftime("%Y-%m")).strip()
    
    # Cache check
    persona = (request.headers.get("X-Insight-Persona") or "").strip() or "default"
    cache_key = insights_key(uid, ym)
    cached = cache_get(cache_key)
    if cached and cached.get("persona") == persona:
        logger.info("Insights cache hit user=%s month=%s", uid, ym)
        return jsonify(cached)
    
    user_gemini_key = (request.headers.get("X-Gemini-Api-Key") or "").strip() or None
    suggestion = monthly_budget_suggestion(
        uid,
        ym,
        gemini_api_key=user_gemini_key,
        persona=persona,
    )
    
    # Cache result (TTL 600s — insights change less frequently)
    suggestion["persona"] = persona
    cache_set(cache_key, suggestion, ttl_seconds=600)
    
    logger.info("Budget suggestion served user=%s month=%s", uid, ym)
    return jsonify(suggestion)

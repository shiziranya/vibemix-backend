from __future__ import annotations
import json as _json
import time

from flask import Blueprint, Response, request, stream_with_context
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import get_redis
from ..services.recommend_service import recommend_service
from ..utils.errors import AppError, ValidationError
from ..utils.response import error, success
from ..utils.validators import validate_recommend_request

recommend_bp = Blueprint("recommend", __name__)


@recommend_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return error(e.code, e.message, e.http_status)


def _check_rate_limit(user_id: str, limit: int = 3, window: int = 10) -> bool:
    """Return True if request is allowed, False if rate limited."""
    try:
        r = get_redis()
        key = f"ratelimit:recommend:{user_id}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        results = pipe.execute()
        count = results[0]
        return count <= limit
    except Exception:
        return True  # Redis unavailable: allow through


@recommend_bp.route("", methods=["POST"])
@jwt_required()
def recommend():
    user_id = get_jwt_identity()

    if not _check_rate_limit(user_id):
        return error(4299, "请求过于频繁，请稍后再试", 429)

    data = request.get_json(silent=True) or {}
    try:
        prefs = validate_recommend_request(data)
    except ValidationError as e:
        return error(e.code, e.message, e.http_status)

    result = recommend_service.recommend(user_id=user_id, prefs=prefs)
    return success(result)


@recommend_bp.route("/refresh", methods=["POST"])
@jwt_required()
def refresh_recommend():
    user_id = get_jwt_identity()

    if not _check_rate_limit(user_id):
        return error(4299, "请求过于频繁，请稍后再试", 429)

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    if not session_id:
        return error(4101, "session_id 必填", 422)

    result = recommend_service.refresh(user_id=user_id, session_id=session_id)
    return success(result)


@recommend_bp.route("/stream", methods=["POST"])
@jwt_required()
def stream_recommend():
    """SSE streaming recommendation endpoint.

    Sends Server-Sent Events:
      data: {"type":"chunk","text":"..."}   — LLM token fragments (raw JSON being built)
      data: {"type":"done","data":{...}}    — full structured result (same schema as POST /)
      data: {"type":"error","message":"..."} — on failure
    """
    user_id = get_jwt_identity()

    if not _check_rate_limit(user_id):
        return error(4299, "请求过于频繁，请稍后再试", 429)

    data = request.get_json(silent=True) or {}
    try:
        prefs = validate_recommend_request(data)
    except ValidationError as e:
        return error(e.code, e.message, e.http_status)

    def generate():
        session_id, event_gen = recommend_service.stream_recommend(user_id=user_id, prefs=prefs)
        # Immediately send session_id so the client can reference it for /refresh
        data_line = f"data: {_json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        yield data_line.encode('utf-8')
        for event in event_gen:
            # batch1 also carries session_id for convenience
            if event.get("type") == "batch1":
                event["session_id"] = session_id
            data_line = f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
            yield data_line.encode('utf-8')

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
            "Content-Encoding": "identity",  # disable gzip for this endpoint
        },
    )


@recommend_bp.route("/stream_refresh", methods=["POST"])
@jwt_required()
def stream_refresh_recommend():
    """SSE streaming refresh (换一杯) endpoint.
    
    Sends Server-Sent Events with the same format as /stream:
      data: {"type":"batch1",...}
      data: {"type":"batch2",...}
      data: {"type":"batch3",...}
      data: {"type":"done"}
      data: {"type":"error","message":"..."}
    """
    user_id = get_jwt_identity()

    if not _check_rate_limit(user_id):
        return error(4299, "请求过于频繁，请稍后再试", 429)

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    if not session_id:
        return error(4101, "session_id 必填", 422)

    def generate():
        try:
            event_gen = recommend_service.stream_refresh(user_id=user_id, session_id=session_id)
            for event in event_gen:
                # batch1 carries session_id for convenience
                if event.get("type") == "batch1":
                    event["session_id"] = session_id
                data_line = f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
                yield data_line.encode('utf-8')
        except Exception as e:
            data_line = f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield data_line.encode('utf-8')

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
            "Content-Encoding": "identity",  # disable gzip for this endpoint
        },
    )


@recommend_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 50)

    result = recommend_service.get_history(user_id, page=page, per_page=per_page)
    return success(result)

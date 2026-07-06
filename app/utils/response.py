from __future__ import annotations
from flask import jsonify


def success(data=None, message="ok", http_status=200):
    return jsonify({"code": 0, "data": data, "message": message}), http_status


def error(code: int, message: str, http_status: int = 400, data=None):
    return jsonify({"code": code, "data": data, "message": message}), http_status

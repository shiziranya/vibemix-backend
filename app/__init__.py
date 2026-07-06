from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

from .config import get_config
from .extensions import db, jwt, init_celery


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())

    db.init_app(app)
    jwt.init_app(app)
    CORS(app, origins="*")
    init_celery(app)

    from .api import auth_bp, cabinet_bp, recommend_bp, cocktails_bp, card_bp
    from .api.map import map_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(cabinet_bp, url_prefix="/api/cabinet")
    app.register_blueprint(recommend_bp, url_prefix="/api/recommend")
    app.register_blueprint(cocktails_bp, url_prefix="/api/cocktails")
    app.register_blueprint(card_bp, url_prefix="/api/card")
    app.register_blueprint(map_bp, url_prefix="/api/v1/map")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app

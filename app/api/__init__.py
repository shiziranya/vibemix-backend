from __future__ import annotations
from .auth import auth_bp
from .cabinet import cabinet_bp
from .recommend import recommend_bp
from .cocktails import cocktails_bp
from .card import card_bp
from .map import map_bp

__all__ = ["auth_bp", "cabinet_bp", "recommend_bp", "cocktails_bp", "card_bp", "map_bp"]

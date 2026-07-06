from __future__ import annotations
import logging
import uuid

import bcrypt
import requests as http_requests
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)

from ..extensions import db, get_redis
from ..models.user import User
from ..utils.errors import (
    InvalidCredentials,
    PhoneAlreadyRegistered,
    UserNotFound,
    WechatAuthError,
)

WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class AuthService:
    def register(
        self,
        phone: str,
        password: str,
        nickname: str | None = None,
        avatar_url: str | None = None,
    ) -> dict:
        existing = db.session.query(User).filter_by(phone=phone).first()
        if existing:
            raise PhoneAlreadyRegistered()

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        user = User(
            id=uuid.uuid4(),
            phone=phone,
            password_hash=pw_hash,
            nickname=nickname or f"用户{phone[-4:]}",
            avatar_url=avatar_url,
        )
        db.session.add(user)
        db.session.commit()

        return self._issue_tokens(user)

    def login(self, phone: str, password: str) -> dict:
        user = db.session.query(User).filter_by(phone=phone).first()
        if not user:
            raise InvalidCredentials()

        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            raise InvalidCredentials()

        return self._issue_tokens(user)

    def wx_login(self, code: str) -> dict:
        """微信小程序登录：用 code 换取 openid，查询或自动创建用户，签发 JWT。"""
        appid = current_app.config.get("WECHAT_APP_ID", "")
        secret = current_app.config.get("WECHAT_APP_SECRET", "")

        if not appid or not secret:
            raise WechatAuthError("服务端微信配置缺失，请联系管理员")

        try:
            resp = http_requests.get(
                WECHAT_CODE2SESSION_URL,
                params={
                    "appid": appid,
                    "secret": secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
                timeout=8,
            ).json()
        except Exception:
            raise WechatAuthError("无法连接微信服务器，请稍后重试")

        if resp.get("errcode") and resp["errcode"] != 0:
            errcode = resp["errcode"]
            errmsg = resp.get("errmsg", "")
            rid = resp.get("rid", "")
            logger.warning(
                "wx code2Session failed | errcode=%s errmsg=%s rid=%s appid=%s",
                errcode, errmsg, rid, appid,
            )
            if errcode == 40029:
                raise WechatAuthError("无效的微信登录凭证，请重新登录（code 已过期或已使用，或小程序 AppID 与后端不一致）")
            if errcode == 45011:
                raise WechatAuthError("登录请求过于频繁，请稍后重试")
            if errcode == 40163:
                raise WechatAuthError("登录凭证已被使用，请重新获取后登录")
            raise WechatAuthError(f"微信登录失败（{errcode}）：{errmsg}")

        openid = resp.get("openid")
        if not openid:
            raise WechatAuthError("未能获取微信用户标识，请重试")

        # session_key 只在需要解密敏感数据时使用，不下发给客户端
        session_key = resp.get("session_key", "")
        self._cache_session_key(openid, session_key)

        user = db.session.query(User).filter_by(openid=openid).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                openid=openid,
                nickname=f"微醺用户{openid[-6:]}",
            )
            db.session.add(user)
            db.session.commit()

        return self._issue_tokens(user)

    def _cache_session_key(self, openid: str, session_key: str) -> None:
        """将 session_key 存入 Redis（TTL 2 小时），仅供后端解密使用。"""
        if not session_key:
            return
        try:
            r = get_redis()
            r.setex(f"wx:session_key:{openid}", 7200, session_key)
        except Exception:
            pass

    def refresh_token(self, user_id: str) -> dict:
        user = db.session.get(User, uuid.UUID(user_id))
        if not user:
            raise UserNotFound()

        access_token = create_access_token(identity=str(user.id))
        return {"access_token": access_token}

    def get_user(self, user_id: str) -> User:
        user = db.session.get(User, uuid.UUID(user_id))
        if not user:
            raise UserNotFound()
        return user

    def update_profile(
        self,
        user_id: str,
        nickname: str | None = None,
        avatar_url: str | None = None,
    ) -> dict:
        user = self.get_user(user_id)
        if nickname is not None:
            user.nickname = nickname[:50]
        if avatar_url is not None:
            user.avatar_url = avatar_url
        db.session.commit()
        return user.to_dict()

    def revoke_refresh_token(self, user_id: str) -> None:
        """Store revoked token marker in Redis (logout)."""
        try:
            r = get_redis()
            ttl = int(
                current_app.config["JWT_REFRESH_TOKEN_EXPIRES"].total_seconds()
            )
            r.setex(f"revoked:refresh:{user_id}", ttl, "1")
        except Exception:
            pass

    def _issue_tokens(self, user: User) -> dict:
        user_id_str = str(user.id)
        access_token = create_access_token(identity=user_id_str)
        refresh_token = create_refresh_token(identity=user_id_str)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user.to_dict(),
        }


auth_service = AuthService()

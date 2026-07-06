from __future__ import annotations
class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, code: int = 5001, http_status: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


# 4001-4099: Auth errors
class AuthError(AppError):
    def __init__(self, message: str, code: int = 4001):
        super().__init__(message, code=code, http_status=401)


class PhoneAlreadyRegistered(AuthError):
    def __init__(self):
        super().__init__("手机号已注册", code=4001)


class InvalidCredentials(AuthError):
    def __init__(self):
        super().__init__("手机号或密码错误", code=4002)


class TokenExpired(AuthError):
    def __init__(self):
        super().__init__("Token 已过期，请重新登录", code=4003)


class UserNotFound(AuthError):
    def __init__(self):
        super().__init__("用户不存在", code=4004)


class WechatAuthError(AuthError):
    def __init__(self, message: str = "微信登录失败，请重试"):
        super().__init__(message, code=4005)


# 4101-4199: Validation errors
class ValidationError(AppError):
    def __init__(self, message: str, code: int = 4101):
        super().__init__(message, code=code, http_status=422)


# 4201-4299: Business logic errors
class BusinessError(AppError):
    def __init__(self, message: str, code: int = 4201):
        super().__init__(message, code=code, http_status=400)


class IngredientNotFound(BusinessError):
    def __init__(self):
        super().__init__("原料不存在", code=4201)


class IngredientAlreadyInCabinet(BusinessError):
    def __init__(self):
        super().__init__("该原料已在酒柜中", code=4202)


class FamilyNotFound(BusinessError):
    def __init__(self):
        super().__init__("原料品类不存在", code=4207)


class FamilyAlreadyInCabinet(BusinessError):
    def __init__(self):
        super().__init__("该原料品类已在酒柜中", code=4208)


class CocktailNotFound(BusinessError):
    def __init__(self):
        super().__init__("配方不存在", code=4203)


class NoCandidatesFound(BusinessError):
    def __init__(self):
        super().__init__("根据当前酒柜和偏好，未找到合适的配方，请尝试调整偏好或补充酒柜", code=4204)


class CardNotFound(BusinessError):
    def __init__(self):
        super().__init__("卡片不存在", code=4205)


class SessionNotFound(BusinessError):
    def __init__(self):
        super().__init__("推荐会话不存在或已过期", code=4206)


# 5001-5099: Server errors
class LLMError(AppError):
    def __init__(self, message: str = "AI 服务暂时不可用，已使用备选推荐"):
        super().__init__(message, code=5001, http_status=200)


class StorageError(AppError):
    def __init__(self, message: str = "文件存储失败"):
        super().__init__(message, code=5002, http_status=500)

"""
نظام الأمان والتوكنات
يتعامل مع JWT tokens وتشفير البيانات الحساسة
"""
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# خوارزمية التشفير
ALGORITHM = "HS256"

# سياق تشفير كلمات المرور
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    إنشاء JWT Access Token
    subject: عادةً user_id
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str | Any) -> str:
    """
    إنشاء JWT Refresh Token - صلاحيته أطول
    يُستخدم لتجديد Access Token دون إعادة تسجيل الدخول
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> str | None:
    """
    التحقق من صحة التوكن
    يعيد user_id إذا كان التوكن صحيحاً، وNone إذا كان منتهياً أو مزوراً
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def hash_password(password: str) -> str:
    """تشفير كلمة المرور قبل الحفظ"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """مقارنة كلمة المرور المدخلة مع المشفرة"""
    return pwd_context.verify(plain_password, hashed_password)

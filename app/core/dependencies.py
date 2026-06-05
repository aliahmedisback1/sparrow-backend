"""
التبعيات المشتركة (Dependencies)
يُستخدم في كل endpoint يحتاج مستخدماً مسجلاً
"""
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User, UserRole

# اسم الـ cookie — يجب أن يطابق ما في auth.py
ACCESS_COOKIE = "sparrow_access"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    التحقق من أن الطلب قادم من مستخدم مسجّل وحسابه نشط
    يقرأ التوكن من HTTP-only cookie بدل الـ Authorization header
    يُستخدم كـ Depends في كل endpoint محمي
    """
    token = request.cookies.get(ACCESS_COOKIE)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="يرجى تسجيل الدخول أولاً",
        )

    user_id = verify_token(token, token_type="access")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="التوكن غير صالح أو منتهي الصلاحية",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    # التحقق من حالة الحساب
    if not user.is_active():
        detail = {
            "banned":    "الحساب محظور نهائياً",
            "suspended": "الحساب موقوف مؤقتاً",
            "frozen":    f"الحساب مجمّد حتى {user.frozen_until}",
        }.get(user.status.value, "الحساب غير نشط")
        raise HTTPException(status_code=403, detail=detail)

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    مثل get_current_user لكن يشترط أن يكون المستخدم أدمن
    يُستخدم في endpoints لوحة الإدارة فقط
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه العملية تتطلب صلاحيات أدمن",
        )
    return current_user

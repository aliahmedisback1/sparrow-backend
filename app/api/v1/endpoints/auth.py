"""
نقاط نهاية المصادقة (Authentication)
تتعامل مع تسجيل الدخول عبر فيسبوك وإصدار التوكنات
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserStatus
from app.services.meta_service import meta_service, MetaAPIError

router = APIRouter()


@router.get("/facebook/login")
async def facebook_login():
    """
    الخطوة 1: توجيه المستخدم إلى صفحة تسجيل دخول فيسبوك
    يفتح نافذة المصادقة من Meta
    """
    return RedirectResponse(url=settings.META_OAUTH_URL)


@router.get("/facebook/callback")
async def facebook_callback(
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    الخطوة 2: فيسبوك يعود هنا بعد موافقة المستخدم
    نتبادل الـ code بـ access_token ثم نسجّل/نحدّث المستخدم
    """

    # إذا رفض المستخدم الإذن
    if error:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=facebook_denied"
        )

    if not code:
        raise HTTPException(status_code=400, detail="لم يتم استلام كود المصادقة")

    try:
        # 1. تبادل الكود بـ Access Token
        token_data = await meta_service.exchange_code_for_token(code)
        access_token = token_data["access_token"]

        # 2. جلب بيانات المستخدم من فيسبوك
        profile = await meta_service.get_user_profile(access_token)
        facebook_id = profile["id"]
        facebook_name = profile["name"]
        facebook_email = profile.get("email")
        picture_url = profile.get("picture", {}).get("data", {}).get("url")

    except MetaAPIError as e:
        raise HTTPException(status_code=400, detail=f"خطأ في فيسبوك: {e.message}")

    # 3. البحث عن المستخدم أو إنشاؤه
    result = await db.execute(
        select(User).where(User.facebook_id == facebook_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # مستخدم جديد - ننشئ حسابه
        user = User(
            facebook_id=facebook_id,
            facebook_name=facebook_name,
            facebook_email=facebook_email,
            facebook_picture_url=picture_url,
            facebook_access_token=access_token,
        )
        db.add(user)
    else:
        # مستخدم موجود - نتحقق من حالته
        if not user.is_active():
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/login?error=account_suspended"
            )
        # تحديث بياناته
        user.facebook_access_token = access_token
        user.facebook_name = facebook_name
        user.facebook_picture_url = picture_url

    # تحديث وقت آخر دخول
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    # 4. إصدار توكنات التطبيق
    app_access_token = create_access_token(subject=str(user.id))
    app_refresh_token = create_refresh_token(subject=str(user.id))

    # 5. توجيه المستخدم للواجهة مع التوكنات
    # ملاحظة: في الإنتاج نستخدم HTTP-only cookies بدلاً من query params
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/success"
            f"?access_token={app_access_token}"
            f"&refresh_token={app_refresh_token}"
    )


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """تجديد Access Token باستخدام Refresh Token"""
    from app.core.security import verify_token

    user_id = verify_token(refresh_token, token_type="refresh")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token غير صالح أو منتهي الصلاحية",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active():
        raise HTTPException(status_code=403, detail="الحساب موقوف")

    new_access_token = create_access_token(subject=str(user.id))
    return {"access_token": new_access_token, "token_type": "bearer"}

"""
نقاط نهاية المصادقة (Authentication)
تتعامل مع تسجيل الدخول عبر فيسبوك وإصدار التوكنات في HTTP-only cookies
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.models.user import User
from app.services.meta_service import meta_service, MetaAPIError

router = APIRouter()

# أسماء الـ cookies
ACCESS_COOKIE  = "sparrow_access"
REFRESH_COOKIE = "sparrow_refresh"

# في الإنتاج نفعّل secure=True
IS_PROD = settings.APP_ENV == "production"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """
    يضع التوكنين في HTTP-only cookies آمنة
    SameSite=lax يسمح بالـ redirect القادم من فيسبوك
    """
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/auth/refresh",  # محدود بـ endpoint التجديد فقط
    )


def clear_auth_cookies(response: Response):
    """يمسح التوكنين عند تسجيل الخروج"""
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/auth/refresh")


@router.get("/facebook/login")
async def facebook_login():
    """
    الخطوة 1: توجيه المستخدم لصفحة تسجيل دخول فيسبوك
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
    نضع التوكنات في cookies ونعيد redirect نظيف بدون tokens في URL
    """

    # إذا رفض المستخدم الإذن
    if error:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=facebook_denied"
        )

    if not code:
        raise HTTPException(status_code=400, detail="لم يتم استلام كود المصادقة")

    try:
        # 1. تبادل الكود بـ Access Token من فيسبوك
        token_data = await meta_service.exchange_code_for_token(code)
        fb_access_token = token_data["access_token"]

        # 2. جلب بيانات المستخدم من فيسبوك
        profile       = await meta_service.get_user_profile(fb_access_token)
        facebook_id   = profile["id"]
        facebook_name = profile["name"]
        facebook_email = profile.get("email")
        picture_url   = profile.get("picture", {}).get("data", {}).get("url")

    except MetaAPIError as e:
        raise HTTPException(status_code=400, detail=f"خطأ في فيسبوك: {e.message}")

    # 3. البحث عن المستخدم أو إنشاؤه
    result = await db.execute(select(User).where(User.facebook_id == facebook_id))
    user = result.scalar_one_or_none()

    if user is None:
        # مستخدم جديد — ننشئ حسابه
        user = User(
            facebook_id=facebook_id,
            facebook_name=facebook_name,
            facebook_email=facebook_email,
            facebook_picture_url=picture_url,
            facebook_access_token=fb_access_token,
        )
        db.add(user)
    else:
        # مستخدم موجود — نتحقق من حالته
        if not user.is_active():
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/login?error=account_suspended"
            )
        # تحديث بياناته
        user.facebook_access_token = fb_access_token
        user.facebook_name         = facebook_name
        user.facebook_picture_url  = picture_url

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    # 4. إصدار توكنات التطبيق
    app_access_token  = create_access_token(subject=str(user.id))
    app_refresh_token = create_refresh_token(subject=str(user.id))

    # 5. Redirect نظيف — التوكنات في cookies وليس في URL
    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/success")
    set_auth_cookies(redirect, app_access_token, app_refresh_token)
    return redirect


@router.post("/refresh")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    تجديد Access Token باستخدام Refresh Token من الـ cookie
    """
    token = request.cookies.get(REFRESH_COOKIE)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="لا يوجد refresh token",
        )

    user_id = verify_token(token, token_type="refresh")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token غير صالح أو منتهي الصلاحية",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active():
        raise HTTPException(status_code=403, detail="الحساب موقوف")

    # إصدار access token جديد ووضعه في cookie
    new_access_token = create_access_token(subject=str(user.id))
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=new_access_token,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    """تسجيل الخروج — مسح الـ cookies"""
    clear_auth_cookies(response)
    return {"ok": True}

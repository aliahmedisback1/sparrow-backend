"""
APIs الكوبونات
الأدمن: إنشاء/تعديل/حذف الكوبونات
المستخدم: التحقق من كوبون وتطبيقه عند الاشتراك
"""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.models.coupon import Coupon, CouponUsage, DiscountType
from app.models.subscription import Subscription, SubscriptionStatus, PlanType
from app.schemas.coupon import CouponCreate, CouponPublic, CouponApply, CouponValidation
from app.schemas.subscription import PLAN_LIMITS
from app.services.stripe_service import PLAN_PRICES

router = APIRouter()


# =============================================
# APIs الأدمن — إدارة الكوبونات
# =============================================

@router.get("/admin", response_model=list[CouponPublic])
async def list_coupons(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """جلب كل الكوبونات"""
    result = await db.execute(select(Coupon).order_by(Coupon.created_at.desc()))
    return result.scalars().all()


@router.post("/admin", response_model=CouponPublic, status_code=201)
async def create_coupon(
    data: CouponCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """إنشاء كوبون جديد"""
    # التحقق من عدم تكرار الكود
    existing = await db.execute(select(Coupon).where(Coupon.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"الكود '{data.code}' موجود مسبقاً")

    coupon = Coupon(**data.model_dump())
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.patch("/admin/{coupon_id}/toggle", response_model=CouponPublic)
async def toggle_coupon(
    coupon_id: UUID,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """تفعيل/إيقاف كوبون"""
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="الكوبون غير موجود")

    coupon.is_active = not coupon.is_active
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.delete("/admin/{coupon_id}", status_code=204)
async def delete_coupon(
    coupon_id: UUID,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """حذف كوبون"""
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="الكوبون غير موجود")

    await db.delete(coupon)
    await db.commit()


# =============================================
# APIs المستخدم — التحقق والتطبيق
# =============================================

@router.post("/validate", response_model=CouponValidation)
async def validate_coupon(
    data: CouponApply,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    التحقق من صلاحية كوبون قبل الدفع
    يُستدعى فور إدخال الكود لإظهار الخصم للمستخدم
    """
    code = data.code.upper().strip()

    # جلب الكوبون
    result = await db.execute(select(Coupon).where(Coupon.code == code))
    coupon = result.scalar_one_or_none()

    if not coupon or not coupon.is_valid():
        return CouponValidation(valid=False, message="الكوبون غير صالح أو منتهي الصلاحية")

    # التحقق من الخطة المطبق عليها
    if coupon.applicable_plan and coupon.applicable_plan != data.plan_type:
        return CouponValidation(valid=False, message=f"هذا الكوبون خاص بخطة {coupon.applicable_plan} فقط")

    # التحقق من الاستخدام المسبق لنفس المستخدم
    if coupon.one_per_user:
        used = await db.execute(
            select(CouponUsage).where(
                CouponUsage.coupon_id == coupon.id,
                CouponUsage.user_id == current_user.id,
            )
        )
        if used.scalar_one_or_none():
            return CouponValidation(valid=False, message="استخدمت هذا الكوبون مسبقاً")

    # حساب الخصم
    base_price = PLAN_PRICES.get(data.plan_type, 0)
    final_price = base_price
    free_days = None

    if coupon.discount_type == DiscountType.PERCENTAGE:
        final_price = base_price * (1 - coupon.discount_value / 100)
        message = f"خصم {int(coupon.discount_value)}% — ستدفع ${final_price:.2f} بدلاً من ${base_price:.2f}"

    elif coupon.discount_type == DiscountType.FREE_DAYS:
        free_days = int(coupon.discount_value)
        message = f"ستحصل على {free_days} يوم مجاني إضافي مع اشتراكك"

    elif coupon.discount_type == DiscountType.FREE_PLAN:
        free_days = int(coupon.discount_value)
        final_price = 0
        message = f"اشتراك مجاني لمدة {free_days} يوم"

    return CouponValidation(
        valid=True,
        message=message,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        final_price_usd=round(final_price, 2),
        free_days_added=free_days,
    )


@router.post("/apply")
async def apply_coupon(
    data: CouponApply,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    تطبيق الكوبون بعد إتمام الدفع
    يُستدعى من endpoint الاشتراك بعد التحقق من الدفع
    """
    code = data.code.upper().strip()
    result = await db.execute(select(Coupon).where(Coupon.code == code))
    coupon = result.scalar_one_or_none()

    if not coupon or not coupon.is_valid():
        raise HTTPException(status_code=400, detail="الكوبون غير صالح")

    # جلب اشتراك المستخدم الحالي
    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))
    subscription = sub_result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="لا يوجد اشتراك لتطبيق الكوبون عليه")

    now = datetime.now(timezone.utc)

    # تطبيق الخصم على الاشتراك
    if coupon.discount_type == DiscountType.FREE_DAYS:
        # إضافة أيام مجانية لتاريخ الانتهاء
        subscription.expires_at += timedelta(days=int(coupon.discount_value))

    elif coupon.discount_type == DiscountType.FREE_PLAN:
        # تفعيل خطة كاملة مجانية
        limits = PLAN_LIMITS.get(PlanType(data.plan_type), PLAN_LIMITS[PlanType.MONTHLY])
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.expires_at = now + timedelta(days=int(coupon.discount_value))
        subscription.max_pages = limits["max_pages"]
        subscription.max_active_campaigns = limits["max_active_campaigns"]
        subscription.max_comments_per_month = limits["max_comments_per_month"]

    # تسجيل الاستخدام
    usage = CouponUsage(coupon_id=coupon.id, user_id=current_user.id)
    db.add(usage)
    coupon.uses_count += 1

    await db.commit()
    return {"message": "تم تطبيق الكوبون بنجاح", "expires_at": subscription.expires_at}

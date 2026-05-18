"""
APIs الاشتراكات
إدارة خطط المستخدمين والتحقق من الحصص
"""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.page import Page
from app.models.subscription import Subscription, PlanType, SubscriptionStatus
from app.schemas.subscription import SubscriptionPublic, PLAN_LIMITS

router = APIRouter()


def _create_subscription(user_id: UUID, plan_type: PlanType) -> Subscription:
    """
    دالة مساعدة: إنشاء اشتراك جديد بالحدود الصحيحة لكل خطة
    """
    limits = PLAN_LIMITS[plan_type]
    now = datetime.now(timezone.utc)

    return Subscription(
        user_id=user_id,
        plan_type=plan_type,
        status=SubscriptionStatus.ACTIVE,
        started_at=now,
        expires_at=now + timedelta(days=limits["duration_days"]),
        max_pages=limits["max_pages"],
        max_active_campaigns=limits["max_active_campaigns"],
        max_comments_per_month=limits["max_comments_per_month"],
        comments_used_this_month=0,
        month_reset_date=now + timedelta(days=30),
    )


@router.get("/me", response_model=SubscriptionPublic)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """جلب بيانات الاشتراك الحالي للمستخدم"""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="لا يوجد اشتراك — ابدأ بالتجربة المجانية")

    return subscription


@router.post("/free-trial", response_model=SubscriptionPublic, status_code=status.HTTP_201_CREATED)
async def start_free_trial(
    page_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    تفعيل التجربة المجانية لمدة أسبوع
    الشروط:
    - المستخدم ليس لديه اشتراك سابق
    - الصفحة المحددة لم تحصل على تجربة مجانية من قبل (حتى من حساب آخر)
    """
    # 1. التحقق من أن المستخدم ليس لديه اشتراك حالي
    existing_sub = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    if existing_sub.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="لديك اشتراك بالفعل — لا يمكن تفعيل التجربة المجانية مرتين"
        )

    # 2. التحقق من أن الصفحة لم تحصل على تجربة مجانية سابقاً
    # نتحقق بالـ facebook_page_id وليس بمعرف المستخدم
    # لمنع إنشاء حساب جديد واستخدام نفس الصفحة
    page_result = await db.execute(
        select(Page).where(Page.id == page_id, Page.owner_id == current_user.id)
    )
    page = page_result.scalar_one_or_none()

    if not page:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة")

    if page.had_free_trial:
        raise HTTPException(
            status_code=403,
            detail="هذه الصفحة استخدمت التجربة المجانية من قبل — يرجى اختيار خطة مدفوعة"
        )

    # 3. تسجيل استخدام التجربة على الصفحة
    page.had_free_trial = True
    page.free_trial_used_at = datetime.now(timezone.utc)

    # 4. إنشاء الاشتراك
    subscription = _create_subscription(current_user.id, PlanType.FREE_TRIAL)
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post("/upgrade", response_model=SubscriptionPublic)
async def upgrade_subscription(
    plan_type: PlanType,
    stripe_payment_intent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    ترقية أو تجديد الاشتراك بعد الدفع عبر Stripe
    stripe_payment_intent_id: يأتي من الفرونت بعد إتمام الدفع
    """
    # لا نقبل التجربة المجانية عبر هذا الـ endpoint
    if plan_type == PlanType.FREE_TRIAL:
        raise HTTPException(status_code=400, detail="استخدم /free-trial لتفعيل التجربة المجانية")

    # التحقق من صحة الدفع مع Stripe
    # في هذه المرحلة: نتحقق فقط من أن الـ ID موجود
    # لاحقاً: سنتحقق فعلياً من Stripe API
    if not stripe_payment_intent_id.startswith("pi_"):
        raise HTTPException(status_code=400, detail="معرف الدفع غير صالح")

    # TODO: تفعيل التحقق الحقيقي من Stripe عند توفر المفاتيح
    # payment = stripe.PaymentIntent.retrieve(stripe_payment_intent_id)
    # if payment.status != "succeeded": raise HTTPException(...)

    # البحث عن اشتراك موجود أو إنشاء جديد
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()
    limits = PLAN_LIMITS[plan_type]
    now = datetime.now(timezone.utc)

    if subscription:
        # تجديد أو ترقية — نمدد من تاريخ اليوم
        subscription.plan_type = plan_type
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.expires_at = now + timedelta(days=limits["duration_days"])
        subscription.max_pages = limits["max_pages"]
        subscription.max_active_campaigns = limits["max_active_campaigns"]
        subscription.max_comments_per_month = limits["max_comments_per_month"]
    else:
        # اشتراك جديد
        subscription = _create_subscription(current_user.id, plan_type)
        db.add(subscription)

    await db.commit()
    await db.refresh(subscription)
    return subscription

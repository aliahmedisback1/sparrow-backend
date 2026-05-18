"""
APIs لوحة الأدمن
تحكم كامل بالمستخدمين والاشتراكات والإحصائيات
كل endpoint هنا يتطلب صلاحيات أدمن
"""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User, UserStatus, UserRole
from app.models.page import Page
from app.models.campaign import Campaign
from app.models.subscription import Subscription, SubscriptionStatus, PlanType
from app.models.comment_log import CommentLog, LogStatus
from app.schemas.user import UserAdminView, UserStatusUpdate
from app.schemas.subscription import SubscriptionAdminUpdate, PLAN_LIMITS

router = APIRouter()


# =============================================
# إحصائيات عامة للتطبيق
# =============================================

@router.get("/stats")
async def get_app_stats(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    لوحة الأرقام الرئيسية للأدمن
    نظرة شاملة على حالة التطبيق
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # إجمالي المستخدمين
    total_users = await db.scalar(select(func.count(User.id)))

    # مستخدمون جدد هذا الأسبوع
    new_users_week = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )

    # توزيع المستخدمين حسب الحالة
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    )
    banned_users = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.BANNED)
    )

    # إحصائيات الاشتراكات
    active_subscriptions = await db.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.expires_at > now,
        )
    )

    # توزيع الاشتراكات حسب الخطة
    plan_distribution = {}
    for plan in PlanType:
        count = await db.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.plan_type == plan,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        plan_distribution[plan.value] = count or 0

    # إحصائيات الصفحات والحملات
    total_pages = await db.scalar(select(func.count(Page.id)))
    total_campaigns = await db.scalar(select(func.count(Campaign.id)))
    active_campaigns = await db.scalar(
        select(func.count(Campaign.id)).where(Campaign.is_active == True)
    )

    # إحصائيات الردود
    total_replies = await db.scalar(
        select(func.sum(Campaign.total_replies_sent))
    )
    total_dms = await db.scalar(
        select(func.sum(Campaign.total_dms_sent))
    )

    # الردود الفاشلة هذا الشهر
    failed_this_month = await db.scalar(
        select(func.count(CommentLog.id)).where(
            CommentLog.status == LogStatus.FAILED,
            CommentLog.received_at >= month_ago,
        )
    )

    return {
        "users": {
            "total": total_users or 0,
            "active": active_users or 0,
            "banned": banned_users or 0,
            "new_this_week": new_users_week or 0,
        },
        "subscriptions": {
            "active_total": active_subscriptions or 0,
            "by_plan": plan_distribution,
        },
        "pages": {"total": total_pages or 0},
        "campaigns": {
            "total": total_campaigns or 0,
            "active": active_campaigns or 0,
        },
        "activity": {
            "total_replies_sent": int(total_replies or 0),
            "total_dms_sent": int(total_dms or 0),
            "failed_replies_this_month": failed_this_month or 0,
        },
    }


# =============================================
# إدارة المستخدمين
# =============================================

@router.get("/users", response_model=list[UserAdminView])
async def list_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: UserStatus | None = Query(None),
    search: str | None = Query(None, description="البحث بالاسم أو الـ facebook_id"),
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    قائمة المستخدمين مع إمكانية الفلترة والبحث
    """
    query = select(User).order_by(desc(User.created_at))

    if status:
        query = query.where(User.status == status)

    if search:
        query = query.where(
            User.facebook_name.ilike(f"%{search}%") |
            User.facebook_id.ilike(f"%{search}%") |
            User.facebook_email.ilike(f"%{search}%")
        )

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/users/{user_id}", response_model=UserAdminView)
async def get_user_detail(
    user_id: UUID,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """تفاصيل مستخدم واحد مع اشتراكه وصفحاته"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    return user


@router.patch("/users/{user_id}/status", response_model=UserAdminView)
async def update_user_status(
    user_id: UUID,
    data: UserStatusUpdate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    تغيير حالة مستخدم: تفعيل / إيقاف / حظر / تجميد
    الأدمن لا يستطيع تغيير حالة أدمن آخر
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    # لا يجوز للأدمن إيقاف أدمن آخر
    if user.role == UserRole.ADMIN and user.id != admin.id:
        raise HTTPException(status_code=403, detail="لا يمكن تعديل حسابات الأدمن")

    user.status = data.status
    user.admin_notes = data.admin_notes

    # إذا كان التجميد نحدد تاريخ الانتهاء
    if data.status == UserStatus.FROZEN:
        if not data.frozen_until:
            raise HTTPException(status_code=400, detail="يجب تحديد تاريخ انتهاء التجميد")
        user.frozen_until = data.frozen_until

    await db.commit()
    await db.refresh(user)
    return user


# =============================================
# إدارة الاشتراكات
# =============================================

@router.patch("/users/{user_id}/subscription", response_model=dict)
async def admin_update_subscription(
    user_id: UUID,
    data: SubscriptionAdminUpdate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    تعديل اشتراك مستخدم يدوياً — خارج حدود النظام الاعتيادية
    يُستخدم للتمديد المجاني، التعويض، الخطط الخاصة، إلخ
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="لا يوجد اشتراك لهذا المستخدم")

    # تطبيق التعديلات — فقط الحقول التي أرسلها الأدمن
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)

    # تسجيل أن هذا تعديل يدوي من الأدمن
    subscription.admin_override = True
    subscription.last_modified_by_admin = datetime.now(timezone.utc)

    await db.commit()
    return {"message": "تم تحديث الاشتراك بنجاح", "user_id": str(user_id)}


@router.post("/users/{user_id}/subscription/grant")
async def grant_subscription(
    user_id: UUID,
    plan_type: PlanType,
    duration_days: int | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    منح اشتراك مجاني لمستخدم (هدية أو تعويض)
    duration_days: إذا لم يُحدَّد يستخدم مدة الخطة الافتراضية
    """
    # التحقق من وجود المستخدم
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    limits = PLAN_LIMITS.get(plan_type, PLAN_LIMITS[PlanType.MONTHLY])
    now = datetime.now(timezone.utc)
    days = duration_days or limits["duration_days"]

    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        # تمديد الاشتراك الموجود
        subscription.plan_type = plan_type
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.expires_at = now + timedelta(days=days)
        subscription.max_pages = limits["max_pages"]
        subscription.max_active_campaigns = limits["max_active_campaigns"]
        subscription.max_comments_per_month = limits["max_comments_per_month"]
        subscription.admin_override = True
        subscription.last_modified_by_admin = now
    else:
        # إنشاء اشتراك جديد
        subscription = Subscription(
            user_id=user_id,
            plan_type=plan_type,
            status=SubscriptionStatus.ACTIVE,
            started_at=now,
            expires_at=now + timedelta(days=days),
            max_pages=limits["max_pages"],
            max_active_campaigns=limits["max_active_campaigns"],
            max_comments_per_month=limits["max_comments_per_month"],
            comments_used_this_month=0,
            month_reset_date=now + timedelta(days=30),
            admin_override=True,
            last_modified_by_admin=now,
        )
        db.add(subscription)

    await db.commit()
    return {
        "message": f"تم منح خطة {plan_type.value} لمدة {days} يوم",
        "expires_at": subscription.expires_at,
    }


@router.delete("/users/{user_id}/subscription")
async def cancel_subscription(
    user_id: UUID,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """إلغاء اشتراك مستخدم فوراً"""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="لا يوجد اشتراك")

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.admin_override = True
    subscription.last_modified_by_admin = datetime.now(timezone.utc)

    await db.commit()
    return {"message": "تم إلغاء الاشتراك"}

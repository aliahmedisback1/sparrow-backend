"""
APIs الحملات
إنشاء وإدارة الردود التلقائية على البوستات
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.page import Page
from app.models.campaign import Campaign
from app.models.comment_log import CommentLog
from app.models.subscription import Subscription
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignPublic

router = APIRouter()


async def _get_page_for_user(page_id: UUID, user_id: UUID, db: AsyncSession) -> Page:
    """
    دالة مساعدة: جلب صفحة والتحقق من أنها تخص المستخدم الحالي
    تُستخدم في عدة endpoints لتجنب تكرار الكود
    """
    result = await db.execute(
        select(Page).where(Page.id == page_id, Page.owner_id == user_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة أو لا تملك صلاحية الوصول إليها")
    return page


async def _get_campaign_for_user(campaign_id: UUID, user_id: UUID, db: AsyncSession) -> Campaign:
    """
    دالة مساعدة: جلب حملة والتحقق من ملكيتها عبر الصفحة
    """
    result = await db.execute(
        select(Campaign)
        .join(Page)
        .where(Campaign.id == campaign_id, Page.owner_id == user_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="الحملة غير موجودة")
    return campaign


@router.get("", response_model=list[CampaignPublic])
async def get_campaigns(
    page_id: UUID | None = Query(None, description="فلترة حسب الصفحة"),
    active_only: bool = Query(False, description="عرض النشطة فقط"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    جلب قائمة الحملات
    يمكن فلترتها حسب الصفحة أو حسب الحالة (نشطة/متوقفة)
    """
    query = (
        select(Campaign)
        .join(Page)
        .where(Page.owner_id == current_user.id)
    )

    if page_id:
        query = query.where(Campaign.page_id == page_id)

    if active_only:
        query = query.where(Campaign.is_active == True)

    # الأحدث أولاً
    query = query.order_by(Campaign.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=CampaignPublic, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    إنشاء حملة جديدة (تفعيل الرد التلقائي على بوست)
    يتحقق من: ملكية الصفحة، حدود الاشتراك، عدم تكرار البوست
    """
    # 1. التحقق من أن الصفحة تخص المستخدم
    await _get_page_for_user(data.page_id, current_user.id, db)

    # 2. التحقق من أن هذا البوست ليس لديه حملة نشطة مسبقاً
    existing = await db.execute(
        select(Campaign).where(
            Campaign.facebook_post_id == data.facebook_post_id,
            Campaign.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="يوجد رد تلقائي نشط بالفعل على هذا البوست"
        )

    # 3. التحقق من حدود الاشتراك (عدد الحملات النشطة)
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    if not subscription or not subscription.is_valid():
        raise HTTPException(status_code=403, detail="لا يوجد اشتراك نشط")

    active_count = await db.scalar(
        select(func.count())
        .select_from(Campaign)
        .join(Page)
        .where(Page.owner_id == current_user.id, Campaign.is_active == True)
    )

    if active_count >= subscription.max_active_campaigns:
        raise HTTPException(
            status_code=403,
            detail=f"وصلت للحد الأقصى ({subscription.max_active_campaigns} حملة نشطة) — أوقف حملة أخرى أو ارقِّ اشتراكك"
        )

    # 4. إنشاء الحملة
    campaign = Campaign(
        facebook_post_id=data.facebook_post_id,
        page_id=data.page_id,
        post_url=data.post_url,
        post_preview=data.post_preview,
        reply_type=data.reply_type,
        custom_reply_text=data.custom_reply_text,
        random_replies=data.random_replies,
        send_dm=data.send_dm,
        dm_text=data.dm_text,
        dm_condition=data.dm_condition,
        dm_keywords=data.dm_keywords,
        reply_all_comments=data.reply_all_comments,
        dm_once_per_user=data.dm_once_per_user,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignPublic)
async def get_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """جلب تفاصيل حملة واحدة"""
    return await _get_campaign_for_user(campaign_id, current_user.id, db)


@router.put("/{campaign_id}", response_model=CampaignPublic)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    تعديل إعدادات حملة موجودة
    يُستخدم لتغيير نوع الرد، نص الرد، إعدادات الـ DM، إلخ
    """
    campaign = await _get_campaign_for_user(campaign_id, current_user.id, db)

    # تحديث فقط الحقول التي أرسلها المستخدم (PATCH سلوك داخل PUT)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.patch("/{campaign_id}/toggle", response_model=CampaignPublic)
async def toggle_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    تفعيل/إيقاف الرد التلقائي على بوست
    المستخدم يتحكم يدوياً في كل بوست على حدة
    """
    campaign = await _get_campaign_for_user(campaign_id, current_user.id, db)

    # إذا كان يريد إعادة التفعيل — نتحقق من حدود الاشتراك
    if not campaign.is_active:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.user_id == current_user.id)
        )
        subscription = sub_result.scalar_one_or_none()

        if not subscription or not subscription.is_valid():
            raise HTTPException(status_code=403, detail="لا يوجد اشتراك نشط")

        active_count = await db.scalar(
            select(func.count())
            .select_from(Campaign)
            .join(Page)
            .where(Page.owner_id == current_user.id, Campaign.is_active == True)
        )

        if active_count >= subscription.max_active_campaigns:
            raise HTTPException(
                status_code=403,
                detail="وصلت للحد الأقصى من الحملات النشطة"
            )

    campaign.is_active = not campaign.is_active
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    حذف حملة نهائياً مع كل سجلات التعليقات الخاصة بها
    """
    campaign = await _get_campaign_for_user(campaign_id, current_user.id, db)
    await db.delete(campaign)
    await db.commit()


@router.get("/{campaign_id}/logs")
async def get_campaign_logs(
    campaign_id: UUID,
    limit: int = Query(50, le=200, description="عدد السجلات (بحد أقصى 200)"),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    عرض سجل التعليقات والردود لحملة معيّنة
    يدعم Pagination لأن السجلات قد تكون كثيرة
    """
    # التحقق من الملكية أولاً
    await _get_campaign_for_user(campaign_id, current_user.id, db)

    result = await db.execute(
        select(CommentLog)
        .where(CommentLog.campaign_id == campaign_id)
        .order_by(CommentLog.received_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = result.scalars().all()

    # إجمالي عدد السجلات للـ Pagination
    total = await db.scalar(
        select(func.count()).where(CommentLog.campaign_id == campaign_id)
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": str(log.id),
                "comment_id": log.facebook_comment_id,
                "commenter_name": log.commenter_name,
                "comment_text": log.comment_text,
                "reply_sent": log.reply_text_sent,
                "dm_sent": log.dm_text_sent,
                "status": log.status.value,
                "received_at": log.received_at,
            }
            for log in logs
        ],
    }

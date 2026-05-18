"""
نقاط نهاية المستخدم
بيانات الحساب والإعدادات الشخصية
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserPublic

router = APIRouter()


@router.get("/me", response_model=UserPublic)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """جلب بيانات المستخدم المسجّل حالياً"""
    return current_user


@router.get("/me/stats")
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    إحصائيات الحساب الكاملة
    عدد الصفحات، الحملات، التعليقات، والـ DMs
    """
    from sqlalchemy import select, func
    from app.models.page import Page
    from app.models.campaign import Campaign
    from app.models.comment_log import CommentLog, LogStatus

    # عدد الصفحات المربوطة
    pages_count = await db.scalar(
        select(func.count()).where(Page.owner_id == current_user.id)
    )

    # عدد الحملات النشطة
    active_campaigns = await db.scalar(
        select(func.count())
        .select_from(Campaign)
        .join(Page)
        .where(Page.owner_id == current_user.id, Campaign.is_active == True)
    )

    # إجمالي التعليقات المستلمة والردود
    totals = await db.execute(
        select(
            func.sum(Campaign.total_comments_received),
            func.sum(Campaign.total_replies_sent),
            func.sum(Campaign.total_dms_sent),
        )
        .join(Page)
        .where(Page.owner_id == current_user.id)
    )
    row = totals.one()

    return {
        "pages_count": pages_count or 0,
        "active_campaigns": active_campaigns or 0,
        "total_comments_received": int(row[0] or 0),
        "total_replies_sent": int(row[1] or 0),
        "total_dms_sent": int(row[2] or 0),
    }

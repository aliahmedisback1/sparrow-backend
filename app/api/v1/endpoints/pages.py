"""
APIs الصفحات
ربط وإدارة صفحات فيسبوك للمستخدم
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.page import Page
from app.models.subscription import Subscription
from app.schemas.page import PagePublic, PageConnect
from app.services.meta_service import meta_service, MetaAPIError

router = APIRouter()


@router.get("", response_model=list[PagePublic])
async def get_my_pages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """جلب كل الصفحات المربوطة بحساب المستخدم"""
    result = await db.execute(
        select(Page).where(Page.owner_id == current_user.id)
    )
    return result.scalars().all()


@router.get("/available")
async def get_available_facebook_pages(
    current_user: User = Depends(get_current_user),
):
    """
    جلب قائمة الصفحات التي يديرها المستخدم على فيسبوك
    يُستخدم في واجهة "ربط صفحة جديدة" لعرض الخيارات المتاحة
    """
    if not current_user.facebook_access_token:
        raise HTTPException(
            status_code=400,
            detail="لا يوجد توكن فيسبوك — يرجى إعادة تسجيل الدخول"
        )

    try:
        pages = await meta_service.get_user_pages(current_user.facebook_access_token)
    except MetaAPIError as e:
        raise HTTPException(status_code=400, detail=f"خطأ في فيسبوك: {e.message}")

    return pages


@router.post("", response_model=PagePublic, status_code=status.HTTP_201_CREATED)
async def connect_page(
    data: PageConnect,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    ربط صفحة فيسبوك بالحساب
    يتحقق من: حدود الاشتراك، وعدم تكرار الصفحة
    """
    # 1. التحقق من حدود الاشتراك
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    if not subscription or not subscription.is_valid():
        raise HTTPException(status_code=403, detail="لا يوجد اشتراك نشط")

    # عدد الصفحات الحالية
    pages_count = await db.scalar(
        select(func.count()).where(Page.owner_id == current_user.id)
    )

    if pages_count >= subscription.max_pages:
        raise HTTPException(
            status_code=403,
            detail=f"وصلت للحد الأقصى ({subscription.max_pages} صفحات) — يرجى ترقية الاشتراك"
        )

    # 2. التحقق من أن الصفحة غير مربوطة مسبقاً بأي حساب
    existing = await db.execute(
        select(Page).where(Page.facebook_page_id == data.facebook_page_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="هذه الصفحة مربوطة بالفعل بحساب آخر"
        )

    # 3. إنشاء الصفحة
    page = Page(
        facebook_page_id=data.facebook_page_id,
        page_name=data.page_name,
        page_access_token=data.page_access_token,
        page_category=data.page_category,
        page_picture_url=data.page_picture_url,
        page_followers_count=data.page_followers_count,
        owner_id=current_user.id,
    )
    db.add(page)
    await db.flush()

    # 4. تفعيل Webhook لهذه الصفحة
    try:
        subscribed = await meta_service.subscribe_page_to_webhook(
            page_id=data.facebook_page_id,
            page_access_token=data.page_access_token,
        )
        page.webhook_subscribed = subscribed
    except MetaAPIError:
        # فشل الـ Webhook لا يمنع ربط الصفحة — يمكن إعادة المحاولة لاحقاً
        page.webhook_subscribed = False

    await db.commit()
    await db.refresh(page)
    return page


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_page(
    page_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    فصل صفحة عن الحساب
    يلغي الـ Webhook ويحذف الصفحة مع كل حملاتها
    """
    result = await db.execute(
        select(Page).where(Page.id == page_id, Page.owner_id == current_user.id)
    )
    page = result.scalar_one_or_none()

    if not page:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة")

    # إلغاء Webhook قبل الحذف
    if page.webhook_subscribed:
        try:
            await meta_service.unsubscribe_page_from_webhook(
                page_id=page.facebook_page_id,
                page_access_token=page.page_access_token,
            )
        except MetaAPIError:
            pass  # إذا فشل الإلغاء نكمل الحذف على أي حال

    await db.delete(page)
    await db.commit()


@router.post("/{page_id}/webhook/retry")
async def retry_webhook_subscription(
    page_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    إعادة محاولة تفعيل Webhook لصفحة فشل تفعيله عند الربط
    """
    result = await db.execute(
        select(Page).where(Page.id == page_id, Page.owner_id == current_user.id)
    )
    page = result.scalar_one_or_none()

    if not page:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة")

    try:
        subscribed = await meta_service.subscribe_page_to_webhook(
            page_id=page.facebook_page_id,
            page_access_token=page.page_access_token,
        )
        page.webhook_subscribed = subscribed
        await db.commit()
        return {"webhook_subscribed": subscribed}
    except MetaAPIError as e:
        raise HTTPException(status_code=400, detail=e.message)

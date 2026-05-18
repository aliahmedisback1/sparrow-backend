"""
معالج الردود التلقائية
يعمل في الخلفية بعد استلام التعليق من Webhook
منطق الرد الكامل موجود هنا
"""
import random
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.campaign import Campaign, ReplyType, DmCondition
from app.models.comment_log import CommentLog, LogStatus
from app.models.page import Page
from app.models.subscription import Subscription
from app.services.meta_service import meta_service, MetaAPIError


# الرد الافتراضي الثابت (يمكن جعله إعداداً في قاعدة البيانات لاحقاً)
DEFAULT_REPLY_TEXT = "شكراً على تعليقك! سنتواصل معك قريباً."


async def process_comment_task(
    campaign_id: str,
    comment_id: str,
    commenter_id: str,
    commenter_name: str,
    comment_text: str,
):
    """
    المهمة الرئيسية لمعالجة كل تعليق جديد
    تعمل بشكل غير متزامن بعد استلام Webhook
    """
    async with AsyncSessionLocal() as db:
        try:
            await _process_comment(
                db, campaign_id, comment_id,
                commenter_id, commenter_name, comment_text
            )
        except Exception as e:
            # نسجّل الخطأ لكن لا نوقف التطبيق
            print(f"خطأ في معالجة التعليق {comment_id}: {e}")


async def _process_comment(
    db: AsyncSession,
    campaign_id: str,
    comment_id: str,
    commenter_id: str,
    commenter_name: str,
    comment_text: str,
):
    """المنطق الفعلي لمعالجة التعليق"""

    # 1. التحقق من أن هذا التعليق لم يُعالج من قبل (منع التكرار)
    existing = await db.execute(
        select(CommentLog).where(CommentLog.facebook_comment_id == comment_id)
    )
    if existing.scalar_one_or_none():
        return  # تم معالجته مسبقاً

    # 2. جلب الحملة مع بيانات الصفحة
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign or not campaign.is_active:
        return

    # 3. جلب بيانات الصفحة (للحصول على page_access_token)
    page_result = await db.execute(
        select(Page).where(Page.id == campaign.page_id)
    )
    page = page_result.scalar_one_or_none()

    if not page or not page.is_active:
        return

    # 4. التحقق من حصة الاشتراك
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == page.owner_id)
    )
    subscription = sub_result.scalar_one_or_none()

    if not subscription or not subscription.is_valid() or not subscription.has_comment_quota():
        # تجاوز الحصة - نسجّل ونتجاهل
        log = CommentLog(
            campaign_id=campaign_id,
            facebook_comment_id=comment_id,
            commenter_facebook_id=commenter_id,
            commenter_name=commenter_name,
            comment_text=comment_text,
            status=LogStatus.SKIPPED,
            error_message="تجاوز حصة الاشتراك",
        )
        db.add(log)
        await db.commit()
        return

    # 5. تحديد نص الرد بناءً على نوع الحملة
    reply_text = _select_reply_text(campaign)

    # 6. إنشاء سجل في قاعدة البيانات قبل الإرسال
    log = CommentLog(
        campaign_id=campaign_id,
        facebook_comment_id=comment_id,
        commenter_facebook_id=commenter_id,
        commenter_name=commenter_name,
        comment_text=comment_text,
        reply_text_sent=reply_text,
        status=LogStatus.PENDING,
    )
    db.add(log)
    await db.flush()

    # 7. إرسال الرد على التعليق
    try:
        await meta_service.post_comment_reply(
            comment_id=comment_id,
            reply_text=reply_text,
            page_access_token=page.page_access_token,
        )
        log.status = LogStatus.REPLIED
        log.processed_at = datetime.now(timezone.utc)

        # تحديث إحصائيات الحملة
        campaign.total_comments_received += 1
        campaign.total_replies_sent += 1

        # تحديث حصة الاشتراك
        subscription.comments_used_this_month += 1

    except MetaAPIError as e:
        log.status = LogStatus.FAILED
        log.error_message = e.message
        await db.commit()
        return

    # 8. التحقق وإرسال الرسالة الخاصة (DM) إذا كانت مفعّلة
    if campaign.send_dm and campaign.dm_text:
        should_send_dm = await _check_should_send_dm(
            db, campaign, commenter_id, comment_text
        )

        if should_send_dm:
            try:
                await meta_service.send_dm(
                    page_id=page.facebook_page_id,
                    recipient_id=commenter_id,
                    message_text=campaign.dm_text,
                    page_access_token=page.page_access_token,
                )
                log.dm_text_sent = campaign.dm_text
                log.status = LogStatus.DM_SENT
                log.dm_already_sent = True
                campaign.total_dms_sent += 1

            except MetaAPIError as e:
                # فشل الـ DM لا يلغي نجاح الرد على التعليق
                log.error_message = f"DM فشل: {e.message}"

    await db.commit()


def _select_reply_text(campaign: Campaign) -> str:
    """
    اختيار نص الرد بناءً على نوع الحملة
    DEFAULT: الرد الثابت الافتراضي
    CUSTOM: الرد الذي كتبه المستخدم لهذا البوست
    RANDOM: يختار عشوائياً من القائمة
    """
    if campaign.reply_type == ReplyType.CUSTOM and campaign.custom_reply_text:
        return campaign.custom_reply_text

    if campaign.reply_type == ReplyType.RANDOM and campaign.random_replies:
        return random.choice(campaign.random_replies)

    # الافتراضي إذا لم يُحدَّد شيء آخر
    return DEFAULT_REPLY_TEXT


async def _check_should_send_dm(
    db: AsyncSession,
    campaign: Campaign,
    commenter_id: str,
    comment_text: str,
) -> bool:
    """
    تحديد إذا كان يجب إرسال رسالة خاصة لهذا المعلّق
    يراعي: شرط الكلمات المفتاحية، وقاعدة "رسالة واحدة لكل مستخدم"
    """

    # إذا كان الشرط "كلمات مفتاحية" - نتحقق من وجودها في التعليق
    if campaign.dm_condition == DmCondition.KEYWORDS:
        if not campaign.dm_keywords:
            return False
        comment_lower = comment_text.lower()
        keyword_found = any(kw.lower() in comment_lower for kw in campaign.dm_keywords)
        if not keyword_found:
            return False

    # إذا كانت قاعدة "رسالة واحدة لكل مستخدم" مفعّلة
    if campaign.dm_once_per_user:
        previous_dm = await db.execute(
            select(CommentLog).where(
                CommentLog.campaign_id == str(campaign.id),
                CommentLog.commenter_facebook_id == commenter_id,
                CommentLog.dm_already_sent == True,
            )
        )
        if previous_dm.scalar_one_or_none():
            return False  # أرسلنا له رسالة من قبل في هذه الحملة

    return True

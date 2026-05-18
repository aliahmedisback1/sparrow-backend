"""
استقبال Webhooks من Meta
هنا تصل التعليقات الجديدة في الوقت الفعلي
"""
import hashlib
import hmac
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.campaign import Campaign
from app.workers.reply_worker import process_comment_task

router = APIRouter()


def verify_webhook_signature(payload: bytes, signature_header: str) -> bool:
    """
    التحقق من أن الطلب قادم فعلاً من Meta
    Meta ترسل توقيعاً مشفراً في كل طلب — إذا لم يتطابق نرفض الطلب
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    # نحسب التوقيع المتوقع بنفس الطريقة التي تستخدمها Meta
    expected = hmac.new(
        key=settings.META_APP_SECRET.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    received = signature_header[7:]  # إزالة "sha256=" من البداية

    # compare_digest يمنع هجمات Timing Attack
    return hmac.compare_digest(expected, received)


@router.get("/webhook")
async def webhook_verification(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    """
    Meta تستدعي هذا مرة واحدة للتحقق من الـ Webhook
    نرد بالـ challenge إذا كان الـ verify_token صحيحاً
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        return int(hub_challenge)

    raise HTTPException(status_code=403, detail="فشل التحقق — راجع META_WEBHOOK_VERIFY_TOKEN")


@router.post("/webhook")
async def webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    استقبال أحداث Meta (تعليقات جديدة)
    نرد بـ 200 فوراً، ثم نعالج في الخلفية
    Meta تلغي الـ Webhook إذا لم نرد خلال 20 ثانية
    """
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")

    # في بيئة التطوير بدون مفاتيح Meta نتجاوز التحقق
    if settings.META_APP_SECRET and not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=403, detail="توقيع الطلب غير صالح")

    data = await request.json()

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "feed":
                continue

            value = change.get("value", {})

            # نريد فقط التعليقات الجديدة وليس التعديلات أو الحذف
            if value.get("item") != "comment" or value.get("verb") != "add":
                continue

            post_id = value.get("post_id")
            comment_id = value.get("comment_id")
            commenter_id = value.get("from", {}).get("id", "")
            commenter_name = value.get("from", {}).get("name", "")
            comment_text = value.get("message", "")

            # البحث عن الحملة المرتبطة بهذا البوست
            result = await db.execute(
                select(Campaign).where(
                    Campaign.facebook_post_id == post_id,
                    Campaign.is_active == True,
                )
            )
            campaign = result.scalar_one_or_none()

            if campaign:
                background_tasks.add_task(
                    process_comment_task,
                    campaign_id=str(campaign.id),
                    comment_id=comment_id,
                    commenter_id=commenter_id,
                    commenter_name=commenter_name,
                    comment_text=comment_text,
                )

    return {"status": "ok"}

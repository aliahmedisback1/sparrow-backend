"""
المهام الدورية المجدوَلة
تعمل تلقائياً في الخلفية بدون تدخل بشري
"""
from datetime import datetime, timezone
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.expire_old_subscriptions")
def expire_old_subscriptions():
    """
    تشغيل كل ساعة
    تحديث حالة الاشتراكات المنتهية من ACTIVE إلى EXPIRED
    """
    import asyncio
    from sqlalchemy import select, update
    from app.core.database import AsyncSessionLocal
    from app.models.subscription import Subscription, SubscriptionStatus

    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Subscription).where(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.expires_at < now,
                    Subscription.admin_override == False,  # لا نلغي الاشتراكات اليدوية
                )
            )
            expired = result.scalars().all()

            for sub in expired:
                sub.status = SubscriptionStatus.EXPIRED

            await db.commit()
            print(f"⏰ انتهت {len(expired)} اشتراكات")

    asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.reset_monthly_quotas")
def reset_monthly_quotas():
    """
    تشغيل كل منتصف ليل
    إعادة تعيين عداد التعليقات الشهري للمستخدمين الذين حان موعد تجديدهم
    """
    import asyncio
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.subscription import Subscription, SubscriptionStatus
    from datetime import timedelta

    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Subscription).where(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.month_reset_date <= now,
                )
            )
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                sub.comments_used_this_month = 0
                sub.month_reset_date = now + timedelta(days=30)

            await db.commit()
            print(f"🔄 تم تجديد حصة {len(subscriptions)} مشترك")

    asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.refresh_expiring_tokens")
def refresh_expiring_tokens():
    """
    تشغيل أسبوعياً
    تجديد توكنات فيسبوك التي ستنتهي خلال 7 أيام
    يمنع توقف الردود التلقائية فجأة بسبب انتهاء التوكن
    """
    import asyncio
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.page import Page
    from datetime import timedelta

    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            week_from_now = now + timedelta(days=7)

            # جلب الصفحات التي ستنتهي توكناتها خلال أسبوع
            result = await db.execute(
                select(Page).where(
                    Page.is_active == True,
                    Page.token_expires_at != None,
                    Page.token_expires_at <= week_from_now,
                )
            )
            pages = result.scalars().all()

            for page in pages:
                # TODO: استدعاء Meta API لتجديد التوكن
                print(f"⚠️ توكن الصفحة {page.page_name} سينتهي قريباً")

            print(f"🔑 {len(pages)} صفحة تحتاج تجديد توكن")

    asyncio.run(_run())

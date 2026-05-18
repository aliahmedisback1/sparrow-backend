"""
إعداد Celery للمهام الدورية والمعالجة في الخلفية
يعمل بشكل مستقل عن FastAPI
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# إنشاء تطبيق Celery
celery_app = Celery(
    "autoreply",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    # إعدادات الأداء
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # إعادة المحاولة التلقائية عند فشل مهمة
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_default_retry_delay=60,  # انتظر دقيقة قبل إعادة المحاولة
)

# المهام الدورية المجدوَلة
celery_app.conf.beat_schedule = {

    # كل منتصف ليل: إعادة تعيين حصة التعليقات الشهرية للمستخدمين
    "reset-monthly-comment-quota": {
        "task": "app.workers.tasks.reset_monthly_quotas",
        "schedule": crontab(hour=0, minute=0),
    },

    # كل ساعة: تحديث حالة الاشتراكات المنتهية
    "expire-subscriptions": {
        "task": "app.workers.tasks.expire_old_subscriptions",
        "schedule": crontab(minute=0),
    },

    # كل أسبوع الأحد: تجديد توكنات فيسبوك قبل انتهائها
    "refresh-facebook-tokens": {
        "task": "app.workers.tasks.refresh_expiring_tokens",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
}

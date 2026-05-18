"""
Schemas الخاصة بالاشتراكات
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.subscription import PlanType, SubscriptionStatus


class SubscriptionPublic(BaseModel):
    """بيانات الاشتراك كما يراها المستخدم"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_type: PlanType
    status: SubscriptionStatus
    started_at: datetime
    expires_at: datetime
    max_pages: int
    max_active_campaigns: int
    max_comments_per_month: int
    comments_used_this_month: int

    @property
    def comments_remaining(self) -> int:
        return max(0, self.max_comments_per_month - self.comments_used_this_month)

    @property
    def days_remaining(self) -> int:
        delta = self.expires_at - datetime.now(self.expires_at.tzinfo)
        return max(0, delta.days)


class SubscriptionAdminUpdate(BaseModel):
    """
    تعديل اشتراك مستخدم من الأدمن
    يتجاوز القيود الاعتيادية للنظام
    """
    plan_type: PlanType | None = None
    status: SubscriptionStatus | None = None
    expires_at: datetime | None = None
    max_pages: int | None = None
    max_active_campaigns: int | None = None
    max_comments_per_month: int | None = None
    admin_notes: str | None = None


# حدود كل خطة — مرجع مركزي يُستخدم عند إنشاء الاشتراكات
PLAN_LIMITS: dict[PlanType, dict] = {
    PlanType.FREE_TRIAL: {
        "max_pages": 1,
        "max_active_campaigns": 3,
        "max_comments_per_month": 50,
        "duration_days": 7,
    },
    PlanType.MONTHLY: {
        "max_pages": 5,
        "max_active_campaigns": 20,
        "max_comments_per_month": 2000,
        "duration_days": 30,
    },
    PlanType.SEMI_ANNUAL: {
        "max_pages": 10,
        "max_active_campaigns": 50,
        "max_comments_per_month": 5000,
        "duration_days": 180,
    },
    PlanType.ANNUAL: {
        "max_pages": 20,
        "max_active_campaigns": 100,
        "max_comments_per_month": 15000,
        "duration_days": 365,
    },
}

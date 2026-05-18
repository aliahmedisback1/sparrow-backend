"""
نموذج الاشتراك
يحدد خطة كل مستخدم وحدود استخدامه
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class PlanType(str, enum.Enum):
    """أنواع خطط الاشتراك"""
    FREE_TRIAL = "free_trial"  # تجربة مجانية لمدة أسبوع
    MONTHLY = "monthly"        # شهري
    SEMI_ANNUAL = "semi_annual" # نصف سنوي
    ANNUAL = "annual"          # سنوي
    CUSTOM = "custom"          # خطة مخصصة من الأدمن


class SubscriptionStatus(str, enum.Enum):
    """حالة الاشتراك"""
    ACTIVE = "active"      # نشط
    EXPIRED = "expired"    # منتهي
    CANCELLED = "cancelled" # ملغي
    PAUSED = "paused"      # موقوف مؤقتاً من الأدمن


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- المستخدم ---
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    user: Mapped["User"] = relationship("User", back_populates="subscription")

    # --- نوع الخطة والحالة ---
    plan_type: Mapped[PlanType] = mapped_column(SAEnum(PlanType))
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE
    )

    # --- تواريخ الاشتراك ---
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # --- حدود الاستخدام حسب الخطة ---
    max_pages: Mapped[int] = mapped_column(Integer, default=1)
    max_active_campaigns: Mapped[int] = mapped_column(Integer, default=3)
    max_comments_per_month: Mapped[int] = mapped_column(Integer, default=50)

    # --- استهلاك الشهر الحالي ---
    comments_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    month_reset_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # --- تعديلات الأدمن ---
    # الأدمن يستطيع تمديد أو إلغاء الاشتراك بشكل يدوي
    admin_override: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_modified_by_admin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- التوقيتات ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def is_valid(self) -> bool:
        """هل الاشتراك صالح الآن؟"""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def has_comment_quota(self) -> bool:
        """هل بقي من حصة التعليقات الشهرية؟"""
        return self.comments_used_this_month < self.max_comments_per_month

    def __repr__(self) -> str:
        return f"<Subscription user={self.user_id} plan={self.plan_type} expires={self.expires_at.date()}>"

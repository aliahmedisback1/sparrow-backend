"""
نموذج الكوبون
يدعم ثلاثة أنواع:
  - خصم بنسبة مئوية على السعر
  - أيام مجانية إضافية
  - خطة كاملة مجانية لمدة محددة
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, Float, Enum as SAEnum, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class DiscountType(str, enum.Enum):
    PERCENTAGE = "percentage"  # خصم نسبة مئوية على السعر (مثلاً 20%)
    FREE_DAYS  = "free_days"   # أيام مجانية إضافية (مثلاً 30 يوم)
    FREE_PLAN  = "free_plan"   # خطة كاملة مجانية لمدة محددة


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- بيانات الكوبون ---
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # نوع الخصم وقيمته
    discount_type: Mapped[DiscountType] = mapped_column(SAEnum(DiscountType))

    # القيمة حسب النوع:
    # PERCENTAGE → نسبة الخصم (مثلاً 20 تعني 20%)
    # FREE_DAYS  → عدد الأيام المجانية
    # FREE_PLAN  → عدد الأيام للخطة المجانية
    discount_value: Mapped[float] = mapped_column(Float)

    # الخطة التي ينطبق عليها الكوبون (None = ينطبق على الكل)
    applicable_plan: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- حدود الاستخدام ---
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = غير محدود
    uses_count: Mapped[int] = mapped_column(Integer, default=0)

    # هل يُسمح لنفس المستخدم باستخدامه مرة واحدة فقط؟
    one_per_user: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- الصلاحية ---
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- التوقيتات ---
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # --- العلاقات ---
    usages: Mapped[list["CouponUsage"]] = relationship("CouponUsage", back_populates="coupon")

    def is_valid(self) -> bool:
        """هل الكوبون صالح للاستخدام؟"""
        if not self.is_active:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        if self.max_uses and self.uses_count >= self.max_uses:
            return False
        return True

    def __repr__(self) -> str:
        return f"<Coupon {self.code} type={self.discount_type} value={self.discount_value}>"


class CouponUsage(Base):
    """سجل استخدامات الكوبون — لمنع الاستخدام المتكرر"""
    __tablename__ = "coupon_usages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    coupon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coupons.id"))
    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="usages")

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

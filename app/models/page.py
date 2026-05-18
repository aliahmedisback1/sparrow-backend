"""
نموذج صفحة فيسبوك
كل مستخدم يستطيع ربط صفحة أو أكثر يديرها
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- بيانات فيسبوك ---
    # facebook_page_id هو المعرف الفريد من فيسبوك - يُستخدم لمنع التجربة المجانية المتكررة
    facebook_page_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    page_name: Mapped[str] = mapped_column(String(300))
    page_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    page_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_followers_count: Mapped[int] = mapped_column(BigInteger, default=0)

    # توكن وصول الصفحة - هذا هو الأهم للعمليات على الصفحة
    # يختلف عن توكن المستخدم - خاص بكل صفحة
    page_access_token: Mapped[str] = mapped_column(String(1000))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- الحالة ---
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # هل حصلت هذه الصفحة على تجربة مجانية من قبل؟
    # حتى لو تم تسجيلها من حساب مستخدم آخر
    had_free_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    free_trial_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # هل الـ Webhook مفعّل لهذه الصفحة؟
    webhook_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- المالك ---
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    owner: Mapped["User"] = relationship("User", back_populates="pages")

    # --- التوقيتات ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- العلاقات ---
    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="page", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Page {self.page_name} ({self.facebook_page_id})>"

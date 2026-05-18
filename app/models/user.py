"""
نموذج المستخدم في قاعدة البيانات
يمثل كل شخص سجّل في التطبيق عبر حسابه على فيسبوك
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class UserStatus(str, enum.Enum):
    """حالة حساب المستخدم"""
    ACTIVE = "active"        # نشط وطبيعي
    SUSPENDED = "suspended"  # موقوف مؤقتاً من الأدمن
    BANNED = "banned"        # محظور نهائياً
    FROZEN = "frozen"        # مجمّد لعدة أيام


class UserRole(str, enum.Enum):
    """صلاحيات المستخدم"""
    USER = "user"   # مشترك عادي
    ADMIN = "admin" # أدمن النظام


class User(Base):
    __tablename__ = "users"

    # --- المعرّف الفريد ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- بيانات فيسبوك ---
    facebook_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    facebook_name: Mapped[str] = mapped_column(String(200))
    facebook_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facebook_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # توكن وصول فيسبوك - مشفّر في الحفظ
    # يُستخدم للعمليات نيابةً عن المستخدم
    facebook_access_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    facebook_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- بيانات التطبيق ---
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.USER
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus), default=UserStatus.ACTIVE
    )

    # تاريخ انتهاء التجميد (يُستخدم مع status=FROZEN)
    frozen_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ملاحظات الأدمن على هذا الحساب
    admin_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # --- توقيتات ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- العلاقات ---
    pages: Mapped[list["Page"]] = relationship("Page", back_populates="owner", cascade="all, delete-orphan")
    subscription: Mapped["Subscription | None"] = relationship("Subscription", back_populates="user", uselist=False)

    def is_active(self) -> bool:
        """هل الحساب يستطيع استخدام التطبيق؟"""
        if self.status == UserStatus.BANNED:
            return False
        if self.status == UserStatus.SUSPENDED:
            return False
        if self.status == UserStatus.FROZEN:
            if self.frozen_until and datetime.now(timezone.utc) < self.frozen_until:
                return False
            # انتهى التجميد - نعيده تلقائياً
        return True

    def __repr__(self) -> str:
        return f"<User {self.facebook_name} ({self.facebook_id})>"

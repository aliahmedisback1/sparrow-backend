"""
سجل التعليقات والردود
يتتبع كل تعليق استلمه التطبيق وما تم فعله تجاهه
يُستخدم أيضاً لمنع إرسال رسالة خاصة مكررة لنفس المستخدم
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


class LogStatus(str, enum.Enum):
    """حالة معالجة التعليق"""
    PENDING = "pending"      # في الانتظار
    REPLIED = "replied"      # تم الرد
    DM_SENT = "dm_sent"      # تم إرسال رسالة خاصة أيضاً
    FAILED = "failed"        # فشل الرد
    SKIPPED = "skipped"      # تجاهله (مثلاً تجاوز الحصة)


class CommentLog(Base):
    __tablename__ = "comment_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- ارتباط بالحملة ---
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="comment_logs")

    # --- بيانات التعليق من فيسبوك ---
    facebook_comment_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    # معرّف صاحب التعليق - لتتبع من علّق
    commenter_facebook_id: Mapped[str] = mapped_column(String(50), index=True)
    commenter_name: Mapped[str] = mapped_column(String(200))

    # نص التعليق الأصلي
    comment_text: Mapped[str] = mapped_column(Text)

    # --- ما أرسله التطبيق ---
    reply_text_sent: Mapped[str | None] = mapped_column(Text, nullable=True)
    dm_text_sent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- الحالة والأخطاء ---
    status: Mapped[LogStatus] = mapped_column(SAEnum(LogStatus), default=LogStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # هل أرسلنا رسالة خاصة لهذا المستخدم في هذه الحملة من قبل؟
    # يُستخدم لتطبيق قاعدة "رسالة واحدة لكل مستخدم"
    dm_already_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- التوقيتات ---
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<CommentLog {self.facebook_comment_id} status={self.status}>"

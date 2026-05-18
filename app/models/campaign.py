"""
نموذج الحملة (Campaign)
كل بوست يتم تفعيل الرد التلقائي عليه يصبح "حملة"
المستخدم يفعّلها يدوياً لكل بوست على حدة
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Enum as SAEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy import ARRAY as SA_ARRAY
import enum
from app.core.database import Base


class ReplyType(str, enum.Enum):
    """نوع الرد التلقائي على التعليقات"""
    DEFAULT = "default"    # تعليق ثابت محدد من الأدمن
    CUSTOM = "custom"      # تعليق يحدده المستخدم لهذا البوست
    RANDOM = "random"      # يختار عشوائياً من قائمة التعليقات


class DmCondition(str, enum.Enum):
    """شرط إرسال رسالة خاصة"""
    ALWAYS = "always"      # أرسل رسالة خاصة لكل تعليق
    KEYWORDS = "keywords"  # أرسل فقط إذا احتوى التعليق على كلمة مفتاحية


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- ارتباط بالبوست والصفحة ---
    facebook_post_id: Mapped[str] = mapped_column(String(100), index=True)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pages.id"))
    page: Mapped["Page"] = relationship("Page", back_populates="campaigns")

    # رابط البوست للعرض في الواجهة
    post_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # مقتطف من نص البوست للعرض
    post_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- إعدادات الرد على التعليقات ---
    reply_type: Mapped[ReplyType] = mapped_column(SAEnum(ReplyType), default=ReplyType.DEFAULT)

    # الرد المخصص (يُستخدم عندما reply_type = CUSTOM)
    custom_reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # قائمة الردود العشوائية (تُستخدم عندما reply_type = RANDOM)
    # يختار النظام واحداً عشوائياً في كل مرة
    random_replies: Mapped[list[str] | None] = mapped_column(
        SA_ARRAY(Text), nullable=True
    )

    # --- إعدادات الرسائل الخاصة (DM) ---
    send_dm: Mapped[bool] = mapped_column(Boolean, default=False)
    dm_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dm_condition: Mapped[DmCondition] = mapped_column(SAEnum(DmCondition), default=DmCondition.ALWAYS)

    # الكلمات المفتاحية التي تُشغّل إرسال الرسالة الخاصة
    dm_keywords: Mapped[list[str] | None] = mapped_column(SA_ARRAY(Text), nullable=True)

    # --- التحكم في السلوك ---
    # هل ترد على كل تعليق للمستخدم أم تعليق واحد فقط؟
    reply_all_comments: Mapped[bool] = mapped_column(Boolean, default=True)

    # ترسل رسالة خاصة مرة واحدة فقط لكل مستخدم حتى لو علّق أكثر من مرة
    dm_once_per_user: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- الحالة ---
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # إحصائيات هذه الحملة
    total_comments_received: Mapped[int] = mapped_column(Integer, default=0)
    total_replies_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_dms_sent: Mapped[int] = mapped_column(Integer, default=0)

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
    comment_logs: Mapped[list["CommentLog"]] = relationship("CommentLog", back_populates="campaign")

    def __repr__(self) -> str:
        return f"<Campaign post={self.facebook_post_id} type={self.reply_type}>"

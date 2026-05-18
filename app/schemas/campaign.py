"""
Schemas الخاصة بالحملات
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.campaign import ReplyType, DmCondition


class CampaignCreate(BaseModel):
    """
    طلب إنشاء حملة جديدة على بوست معيّن
    المستخدم يُرسل هذا عند تفعيل الرد التلقائي على بوست
    """
    facebook_post_id: str
    page_id: uuid.UUID
    post_url: str | None = None
    post_preview: str | None = None

    # إعدادات الرد على التعليقات
    reply_type: ReplyType = ReplyType.DEFAULT
    custom_reply_text: str | None = None
    random_replies: list[str] | None = None

    # إعدادات الرسالة الخاصة
    send_dm: bool = False
    dm_text: str | None = None
    dm_condition: DmCondition = DmCondition.ALWAYS
    dm_keywords: list[str] | None = None

    # خيارات السلوك
    reply_all_comments: bool = True
    dm_once_per_user: bool = True

    @field_validator("custom_reply_text")
    @classmethod
    def validate_custom_reply(cls, v, info):
        """إذا النوع CUSTOM يجب أن يكون هناك نص"""
        if info.data.get("reply_type") == ReplyType.CUSTOM and not v:
            raise ValueError("يجب تحديد نص الرد المخصص عند اختيار النوع CUSTOM")
        return v

    @field_validator("random_replies")
    @classmethod
    def validate_random_replies(cls, v, info):
        """إذا النوع RANDOM يجب أن تكون هناك قائمة بتعليقين على الأقل"""
        if info.data.get("reply_type") == ReplyType.RANDOM:
            if not v or len(v) < 2:
                raise ValueError("يجب تحديد تعليقين على الأقل للرد العشوائي")
        return v

    @field_validator("dm_text")
    @classmethod
    def validate_dm_text(cls, v, info):
        """إذا send_dm مفعّل يجب أن يكون هناك نص للرسالة"""
        if info.data.get("send_dm") and not v:
            raise ValueError("يجب تحديد نص الرسالة الخاصة")
        return v


class CampaignUpdate(BaseModel):
    """تعديل إعدادات حملة موجودة"""
    reply_type: ReplyType | None = None
    custom_reply_text: str | None = None
    random_replies: list[str] | None = None
    send_dm: bool | None = None
    dm_text: str | None = None
    dm_condition: DmCondition | None = None
    dm_keywords: list[str] | None = None
    is_active: bool | None = None


class CampaignPublic(BaseModel):
    """بيانات الحملة كما تظهر للمستخدم"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    facebook_post_id: str
    page_id: uuid.UUID
    post_url: str | None
    post_preview: str | None
    reply_type: ReplyType
    custom_reply_text: str | None
    random_replies: list[str] | None
    send_dm: bool
    dm_condition: DmCondition
    dm_keywords: list[str] | None
    is_active: bool
    total_comments_received: int
    total_replies_sent: int
    total_dms_sent: int
    created_at: datetime

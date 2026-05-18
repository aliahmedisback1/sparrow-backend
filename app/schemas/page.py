"""
Schemas الخاصة بصفحات فيسبوك
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PagePublic(BaseModel):
    """بيانات الصفحة كما تظهر للمستخدم"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    facebook_page_id: str
    page_name: str
    page_category: str | None
    page_picture_url: str | None
    page_followers_count: int
    is_active: bool
    webhook_subscribed: bool
    had_free_trial: bool
    created_at: datetime


class PageConnect(BaseModel):
    """
    طلب ربط صفحة جديدة
    يأتي من الفرونت بعد اختيار المستخدم للصفحة
    """
    facebook_page_id: str
    page_name: str
    page_access_token: str
    page_category: str | None = None
    page_picture_url: str | None = None
    page_followers_count: int = 0

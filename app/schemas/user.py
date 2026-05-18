"""
Schemas الخاصة بالمستخدم
تتحكم في شكل البيانات الواردة والصادرة من API
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.user import UserStatus, UserRole


class UserPublic(BaseModel):
    """
    البيانات التي يراها المستخدم عن نفسه
    لا نُرسل التوكنات أو البيانات الحساسة
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    facebook_name: str
    facebook_email: str | None
    facebook_picture_url: str | None
    role: UserRole
    status: UserStatus
    created_at: datetime
    last_login_at: datetime | None


class UserAdminView(UserPublic):
    """
    البيانات الإضافية التي يراها الأدمن فقط
    """
    facebook_id: str
    admin_notes: str | None
    frozen_until: datetime | None


class UserStatusUpdate(BaseModel):
    """
    طلب تغيير حالة مستخدم (من الأدمن)
    """
    status: UserStatus
    frozen_until: datetime | None = None  # مطلوب فقط إذا status = frozen
    admin_notes: str | None = None

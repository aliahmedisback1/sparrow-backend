"""Schemas الكوبونات"""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.coupon import DiscountType


class CouponCreate(BaseModel):
    """إنشاء كوبون جديد من الأدمن"""
    code:            str
    description:     str | None    = None
    discount_type:   DiscountType
    discount_value:  float
    applicable_plan: str | None    = None  # None = ينطبق على الكل
    max_uses:        int | None    = None  # None = غير محدود
    one_per_user:    bool          = True
    expires_at:      datetime | None = None

    @field_validator("discount_value")
    @classmethod
    def validate_value(cls, v, info):
        if info.data.get("discount_type") == DiscountType.PERCENTAGE:
            if not (1 <= v <= 100):
                raise ValueError("نسبة الخصم يجب أن تكون بين 1 و 100")
        elif v <= 0:
            raise ValueError("القيمة يجب أن تكون أكبر من صفر")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        return v.upper().strip()


class CouponPublic(BaseModel):
    """بيانات الكوبون للعرض"""
    model_config = ConfigDict(from_attributes=True)

    id:              uuid.UUID
    code:            str
    description:     str | None
    discount_type:   DiscountType
    discount_value:  float
    applicable_plan: str | None
    max_uses:        int | None
    uses_count:      int
    one_per_user:    bool
    is_active:       bool
    expires_at:      datetime | None
    created_at:      datetime


class CouponApply(BaseModel):
    """طلب تطبيق كوبون من المستخدم"""
    code:      str
    plan_type: str  # الخطة التي يريد الاشتراك بها


class CouponValidation(BaseModel):
    """نتيجة التحقق من الكوبون"""
    valid:            bool
    message:          str
    discount_type:    DiscountType | None = None
    discount_value:   float | None        = None
    final_price_usd:  float | None        = None  # السعر بعد الخصم
    free_days_added:  int | None          = None   # الأيام المجانية المضافة

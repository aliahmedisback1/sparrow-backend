"""تجميع جميع النماذج — يضمن اكتشاف Alembic لكل الجداول"""
from app.models.user import User, UserStatus, UserRole
from app.models.page import Page
from app.models.campaign import Campaign, ReplyType, DmCondition
from app.models.subscription import Subscription, PlanType, SubscriptionStatus
from app.models.comment_log import CommentLog, LogStatus
from app.models.coupon import Coupon, CouponUsage, DiscountType

__all__ = [
    "User", "UserStatus", "UserRole",
    "Page",
    "Campaign", "ReplyType", "DmCondition",
    "Subscription", "PlanType", "SubscriptionStatus",
    "CommentLog", "LogStatus",
    "Coupon", "CouponUsage", "DiscountType",
]

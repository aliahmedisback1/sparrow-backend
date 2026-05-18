"""
خدمة Stripe للمدفوعات
جاهزة للتفعيل عند إضافة المفاتيح في .env
"""
from app.core.config import settings


class StripeService:
    """
    كل عمليات الدفع تمر من هنا
    الآن: تعمل في وضع محاكاة (Mock)
    بعد إضافة STRIPE_SECRET_KEY في .env: تعمل حقيقياً بدون أي تعديل في الكود
    """

    def __init__(self):
        self.secret_key = getattr(settings, "STRIPE_SECRET_KEY", "")
        self.is_live = bool(self.secret_key)

    async def create_payment_intent(
        self,
        amount_usd: float,
        user_id: str,
        plan_type: str,
        currency: str = "usd",
    ) -> dict:
        """
        إنشاء طلب دفع جديد
        الفرونت يستخدم الـ client_secret لإتمام الدفع
        """
        if not self.is_live:
            # وضع المحاكاة — يعيد بيانات وهمية للتطوير
            return {
                "id": f"pi_mock_{user_id[:8]}",
                "client_secret": f"pi_mock_secret_{user_id[:8]}",
                "amount": int(amount_usd * 100),
                "currency": currency,
                "status": "requires_payment_method",
                "mode": "mock",
            }

        # الكود الحقيقي — يعمل بعد إضافة المفتاح
        import stripe
        stripe.api_key = self.secret_key

        intent = stripe.PaymentIntent.create(
            amount=int(amount_usd * 100),  # Stripe يعمل بالسنتات
            currency=currency,
            metadata={"user_id": user_id, "plan_type": plan_type},
        )
        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
        }

    async def verify_payment(self, payment_intent_id: str) -> bool:
        """
        التحقق من اكتمال الدفع
        يُستدعى من endpoint الترقية قبل تفعيل الاشتراك
        """
        if not self.is_live:
            # في وضع المحاكاة: أي payment_intent_id يبدأ بـ pi_ يُعتبر ناجحاً
            return payment_intent_id.startswith("pi_")

        import stripe
        stripe.api_key = self.secret_key

        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return intent.status == "succeeded"


# نسخة واحدة مشتركة
stripe_service = StripeService()


# أسعار الخطط بالدولار — ستنقلها إلى قاعدة البيانات لاحقاً لسهولة التعديل
PLAN_PRICES = {
    "monthly": 19.99,
    "semi_annual": 99.99,   # توفير ~17%
    "annual": 179.99,       # توفير ~25%
}

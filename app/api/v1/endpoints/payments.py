"""
APIs الدفع عبر Stripe
إنشاء طلبات الدفع واستقبال تأكيدات Stripe
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.subscription import PlanType
from app.services.stripe_service import stripe_service, PLAN_PRICES

router = APIRouter()


@router.post("/create-intent")
async def create_payment_intent(
    plan_type: PlanType,
    current_user: User = Depends(get_current_user),
):
    """
    الخطوة 1: إنشاء طلب دفع
    الفرونت يستخدم client_secret لفتح نافذة Stripe
    """
    if plan_type == PlanType.FREE_TRIAL:
        raise HTTPException(status_code=400, detail="التجربة المجانية لا تحتاج دفعاً")

    price = PLAN_PRICES.get(plan_type.value)
    if not price:
        raise HTTPException(status_code=400, detail="خطة غير صالحة")

    intent = await stripe_service.create_payment_intent(
        amount_usd=price,
        user_id=str(current_user.id),
        plan_type=plan_type.value,
    )

    return {
        "client_secret": intent["client_secret"],
        "amount": intent["amount"],
        "currency": intent["currency"],
        "plan_type": plan_type.value,
        "price_usd": price,
    }


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Stripe يستدعي هذا تلقائياً عند اكتمال أي دفع
    نفعّل الاشتراك هنا بدلاً من الانتظار من الفرونت
    (أكثر أماناً لأنه لا يعتمد على المتصفح)
    """
    # TODO: إضافة STRIPE_WEBHOOK_SECRET في .env لتفعيل التحقق
    # في الوقت الحالي نسجّل الحدث فقط
    payload = await request.json()
    event_type = payload.get("type", "")

    if event_type == "payment_intent.succeeded":
        payment_intent = payload.get("data", {}).get("object", {})
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_type = metadata.get("plan_type")

        # TODO: استدعاء منطق تفعيل الاشتراك هنا
        print(f"✅ دفع ناجح — user: {user_id}, plan: {plan_type}")

    return {"received": True}

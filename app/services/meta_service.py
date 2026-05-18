"""
خدمة التواصل مع Meta Graph API
جميع الاتصالات مع فيسبوك تمر من هنا
"""
import httpx
from typing import Any
from app.core.config import settings


class MetaAPIError(Exception):
    """استثناء خاص بأخطاء Meta API"""
    def __init__(self, message: str, code: int = 0):
        self.message = message
        self.code = code
        super().__init__(message)


class MetaService:
    """
    خدمة موحّدة للتعامل مع Meta Graph API
    تستخدم httpx للطلبات الغير متزامنة
    """

    def __init__(self):
        self.base_url = settings.META_GRAPH_URL
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET

    async def exchange_code_for_token(self, code: str) -> dict:
        """
        تبادل الـ code (من OAuth callback) بـ Access Token حقيقي
        هذه الخطوة تحدث مرة واحدة بعد تسجيل الدخول
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/oauth/access_token",
                params={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "redirect_uri": f"{settings.APP_BASE_URL}/auth/facebook/callback",
                    "code": code,
                }
            )
            data = response.json()

            if "error" in data:
                raise MetaAPIError(data["error"]["message"], data["error"]["code"])

            return data  # يحتوي على: access_token, token_type, expires_in

    async def get_user_profile(self, access_token: str) -> dict:
        """
        جلب بيانات المستخدم الأساسية من فيسبوك
        نستخدم هذا عند تسجيل الدخول لأول مرة
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me",
                params={
                    "fields": "id,name,email,picture.width(200)",
                    "access_token": access_token,
                }
            )
            data = response.json()

            if "error" in data:
                raise MetaAPIError(data["error"]["message"])

            return data

    async def get_user_pages(self, user_access_token: str) -> list[dict]:
        """
        جلب قائمة الصفحات التي يديرها المستخدم
        كل صفحة تأتي مع page_access_token خاص بها
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me/accounts",
                params={
                    "fields": "id,name,category,picture,fan_count,access_token",
                    "access_token": user_access_token,
                }
            )
            data = response.json()

            if "error" in data:
                raise MetaAPIError(data["error"]["message"])

            return data.get("data", [])

    async def post_comment_reply(
        self, comment_id: str, reply_text: str, page_access_token: str
    ) -> dict:
        """
        الرد على تعليق معيّن
        comment_id: معرّف التعليق على فيسبوك
        reply_text: نص الرد
        page_access_token: توكن الصفحة (ليس المستخدم)
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{comment_id}/comments",
                params={"access_token": page_access_token},
                json={"message": reply_text},
            )
            data = response.json()

            if "error" in data:
                raise MetaAPIError(data["error"]["message"], data["error"].get("code", 0))

            return data  # يحتوي على id التعليق الجديد

    async def send_dm(
        self, page_id: str, recipient_id: str, message_text: str, page_access_token: str
    ) -> dict:
        """
        إرسال رسالة خاصة لشخص علّق على الصفحة
        يتطلب صلاحية pages_messaging
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{page_id}/messages",
                params={"access_token": page_access_token},
                json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": message_text},
                    "messaging_type": "RESPONSE",
                }
            )
            data = response.json()

            if "error" in data:
                raise MetaAPIError(data["error"]["message"], data["error"].get("code", 0))

            return data

    async def subscribe_page_to_webhook(self, page_id: str, page_access_token: str) -> bool:
        """
        تفعيل استقبال Webhooks لصفحة معيّنة
        بعد هذه الخطوة سيستقبل التطبيق إشعارات بكل تعليق جديد
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{page_id}/subscribed_apps",
                params={"access_token": page_access_token},
                json={"subscribed_fields": ["feed", "messages"]},
            )
            data = response.json()
            return data.get("success", False)

    async def unsubscribe_page_from_webhook(self, page_id: str, page_access_token: str) -> bool:
        """إلغاء تفعيل Webhooks لصفحة (عند حذف الصفحة أو إيقافها)"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/{page_id}/subscribed_apps",
                params={"access_token": page_access_token},
            )
            data = response.json()
            return data.get("success", False)


# نسخة واحدة مشتركة في التطبيق كله
meta_service = MetaService()

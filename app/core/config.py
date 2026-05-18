"""
إعدادات التطبيق المركزية
يتم قراءة جميع القيم من ملف .env تلقائياً
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- إعدادات عامة ---
    APP_NAME: str = "AutoReply Pro"
    APP_ENV: str = "development"
    SECRET_KEY: str
    DEBUG: bool = False

    # --- قاعدة البيانات ---
    DATABASE_URL: str

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Meta / Facebook ---
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_WEBHOOK_VERIFY_TOKEN: str = "dev_verify_token"
    META_API_VERSION: str = "v19.0"

    # --- عناوين التطبيق ---
    APP_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- التوكنات ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    @property
    def META_OAUTH_URL(self) -> str:
        """رابط تسجيل الدخول عبر فيسبوك"""
        return (
            f"https://www.facebook.com/{self.META_API_VERSION}/dialog/oauth"
            f"?client_id={self.META_APP_ID}"
            f"&redirect_uri={self.APP_BASE_URL}/auth/facebook/callback"
            f"&scope=pages_show_list,pages_read_engagement,"
            f"pages_manage_engagement,pages_messaging,pages_manage_posts"
        )

    @property
    def META_GRAPH_URL(self) -> str:
        return f"https://graph.facebook.com/{self.META_API_VERSION}"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """إرجاع نسخة واحدة من الإعدادات (Singleton)"""
    return Settings()


# اختصار للاستخدام في باقي الملفات
settings = get_settings()

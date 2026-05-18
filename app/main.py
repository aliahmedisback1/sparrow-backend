"""نقطة انطلاق التطبيق — النسخة الكاملة"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.endpoints import auth, webhook, users, pages, campaigns, subscriptions, admin, payments, coupons


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ {settings.APP_NAME} — وضع {settings.APP_ENV}")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"

app.include_router(auth.router,          prefix="/auth",                 tags=["المصادقة"])
app.include_router(webhook.router,       prefix="/meta",                 tags=["Webhooks"])
app.include_router(users.router,         prefix=f"{API}/users",          tags=["المستخدمون"])
app.include_router(pages.router,         prefix=f"{API}/pages",          tags=["الصفحات"])
app.include_router(campaigns.router,     prefix=f"{API}/campaigns",      tags=["الحملات"])
app.include_router(subscriptions.router, prefix=f"{API}/subscriptions",  tags=["الاشتراكات"])
app.include_router(payments.router,      prefix=f"{API}/payments",       tags=["المدفوعات"])
app.include_router(admin.router,         prefix=f"{API}/admin",          tags=["الأدمن"])
app.include_router(coupons.router,       prefix=f"{API}/coupons",        tags=["الكوبونات"])


@app.get("/health", tags=["النظام"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}

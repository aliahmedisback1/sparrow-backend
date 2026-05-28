"""
إعداد بيئة Alembic للـ migrations
يدعم الوضعين: offline (توليد SQL) و online (تطبيق مباشر)
"""
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from alembic import context
import sys
import os

# إضافة مسار المشروع للـ Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base

# استيراد جميع الموديلز حتى يكتشفها Alembic
import app.models  # noqa: F401

# إعداد الـ logging
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# الـ metadata المصدر لتوليد الجداول
target_metadata = Base.metadata


def get_url() -> str:
    """قراءة DATABASE_URL من متغيرات البيئة"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost/db"
    )


def run_migrations_offline() -> None:
    """
    وضع offline: يولّد SQL بدون اتصال فعلي بقاعدة البيانات
    مفيد لمراجعة الـ migrations قبل تطبيقها
    """
    url = get_url().replace("postgresql+asyncpg://", "postgresql://")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """تنفيذ الـ migrations على الاتصال المعطى"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """وضع online: تطبيق الـ migrations مباشرة على قاعدة البيانات"""
    from sqlalchemy.ext.asyncio import create_async_engine

    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """نقطة الدخول للوضع online"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

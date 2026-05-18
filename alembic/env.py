"""
إعداد Alembic لإدارة تغييرات قاعدة البيانات
كل تغيير في النماذج يصبح migration يمكن تطبيقه أو التراجع عنه
"""
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.core.database import Base
from app.core.config import settings
import app.models  # noqa

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn, target_metadata=target_metadata
            )
        )
        async with connectable.connect() as conn:
            await conn.run_sync(
                lambda c: context.run_migrations()
            )
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


run_migrations_online()

"""
إعداد الاتصال بقاعدة البيانات
نستخدم SQLAlchemy مع asyncpg للأداء العالي
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


# محرك قاعدة البيانات - echo=True يطبع SQL في وضع التطوير
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # يتحقق من الاتصال قبل كل استعلام
)

# مصنع الجلسات
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """الكلاس الأساسي لجميع نماذج قاعدة البيانات"""
    pass


async def get_db() -> AsyncSession:
    """
    Dependency يُستخدم في كل endpoint يحتاج قاعدة البيانات
    يفتح الجلسة ويغلقها تلقائياً بعد انتهاء الطلب
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

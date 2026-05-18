FROM python:3.12-slim

# منع Python من كتابة ملفات .pyc وتفعيل stdout مباشرة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# تثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY . .

# فتح البورت
EXPOSE 8000

# أمر التشغيل الافتراضي (يُستبدل في docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

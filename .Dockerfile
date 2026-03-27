# استخدام نسخة بايثون مستقرة وخفيفة
FROM python:3.11-slim

# ضبط مجلد العمل داخل الحاوية
WORKDIR /app

# تثبيت أدوات النظام الضرورية
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً لتسريع البناء (Caching)
COPY requirements.txt .

# تثبيت المكتبات البرمجية
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كافة ملفات المشروع إلى الحاوية
COPY . .

# التأكد من وجود مجلد الموديولات
RUN mkdir -p modules

# الأمر المشغل للبوت الرئيسي
CMD ["python", "main.py"]

import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import logging
import uuid 

# استيراد محرك الذاكرة المؤقتة للمصنع كامل

from cache_manager import get_bot_data_from_cache, smart_sync_check, update_global_version, ensure_bot_sync_row

def get_system_time(mode="full"):
    """
    المحرك الموحد للوقت في المنصة:
    mode="date"   -> يعيد التاريخ فقط (2026-04-06)
    mode="time"   -> يعيد الوقت فقط (15:30:05)
    mode="full"   -> يعيد التاريخ والوقت (2026-04-06 15:30:05)
    """
    now = datetime.now()
    if mode == "date":
        return now.strftime("%Y-%m-%d")
    elif mode == "time":
        return now.strftime("%H:%M:%S")
    else:
        return now.strftime("%Y-%m-%d %H:%M:%S")


# إعداد اللوجر الاحترافي مع التسلسل الهرمي (Hierarchy Logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [CORE:DB] %(message)s')
logger = logging.getLogger(__name__)

# --- إعداد المتغيرات العالمية لكافة أوراق العمل (14 ورقة كاملة) ---
client = None
ss = None
users_sheet = None           # 1. المستخدمين
bots_sheet = None            # 2. البوتات_المصنوعة
content_sheet = None         # 3. إعدادات_المحتوى
logs_sheet = None            # 4. السجلات
stats_sheet = None           # 5. الإحصائيات
payments_sheet = None        # 6. المدفوعات
students_db_sheet = None      # 7. قاعدة_بيانات_الطلاب
registrations_logs_sheet = None # 8. سجل_التسجيلات
departments_sheet = None        # 9. الأقسام
discount_codes_sheet = None     # 10. أكواد_الخصم
coupons_sheet = None            # 11. الكوبونات
courses_sheet = None            # 12. الدورات_التدريبية
faq_sheet = None                # 13. الأسئلة_الشائعة
meta_sheet = None               # 14. _meta (الإصدار والتحقق)
coaches_sheet = None            # 15. ورقة المدربين (الإضافة الجديدة)
lectures_sheet = None        # ورقة جدول_المحاضرات (إضافة جديدة)

# معرف ملف Google Sheet الخاص بمصنع البوتات
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

# --- إعدادات النظام المتقدمة (Production Core) ---
STRICT_SCHEMA = True
SCHEMA_VERSION = "1.3"
BATCH_SIZE = 50
RETRY_ATTEMPTS = 3
AUTO_RESIZE = False
SENSITIVE_FIELDS = {"التوكن", "كلمة_المرور", "token", "api_key", "credentials", "private_key","bot_id"}




# --- [ 1. كتل إدارة المخطط والهيكل - يجب أن تكون في البداية ] ---
# --------------------------------------------------------------------------
def get_sheets_structure():
    sheets_config = [
    

        {"name": "الإعدادات","cols": ["bot_id", "المفتاح_البرمجي", "العنوان", "القيمة", "ملاحظات"],"color": {"red": 0.8, "green": 0.9, "blue": 1}},
        {"name":"نظام_المزامنة","cols":["bot_id","رقم_الإصدار","آخر_تحديث","الحالة","ID_المالك","ID_المطور"],"color":{"red":0.9,"green":0.8,"blue":1}}, 
        {"name": "الهيكل_التنظيمي_والصلاحيات", "cols": ["bot_id", "معرف_الفرع", "ID_الموظف_أو_المدرب", "صلاحية_الأقسام", "صلاحية_الدورات", "صلاحية_المدربين", "صلاحية_الموظفين", "صلاحية_الإحصائيات", "صلاحية_الإذاعة", "صلاحية_الرسائل_الخاصة", "صلاحية_الكوبونات", "صلاحية_أكواد_الخصم", "الدورات_المسموحة", "المجموعات_المسموحة", "تحديث_السيرفر"]}, 
        {"name": "المستخدمين", "cols": ["ID المستخدم","اسم المستخدم","تاريخ التسجيل","الحالة","نوع الاشتراك","عدد البوتات","آخر نشاط","اللغة","مصدر التسجيل","معرف إحالة","رصيد"], "color": {"red": 0.85, "green": 0.92, "blue": 0.83}},
        {"name": "البوتات_المصنوعة", "cols": ["ID المالك","نوع البوت","اسم البوت","التوكن","حالة التشغيل","bot_id","username_bot","تاريخ الإنشاء","آخر تشغيل","عدد المستخدمين","عدد الرسائل","الحالة التقنية","webhook_url","api_type","plan","expiration_date","is_active","errors_log","تاريخ_آخر_تجديد","سعر_الاشتراك","رصيد_البوت","الحد_الأقصى_للطلاب","الحد_الأقصى_للدوات","الحد_الأقصى_للاقسام", "ميزة_الذكاء_الاصطناعي", "ميزة_رفع_وتصدير_البيانات_اكسل" ,"معرف_الفاتورة","متوسط_زمن_الاستجابة","استخدام_CPU","استخدام_الذاكرة","المستخدمون_النشطون_يومياً","المستخدمون_النشطون_شهرياً","معدل_الاحتفاظ","تاريخ_آخر_تحديث_للتوكن","حالة_التوكن","حالة_الدفع","طريقة_الدفع","دورة_الفوترة","إصدار_البوت","بيئة_التشغيل","إعادة_تشغيل_تلقائي","نموذج_الذكاء_الاصطناعي","استهلاك_التوكنات_AI","تكلفة_AI"], "color": {"red":0.81,"green":0.88,"blue":0.95} }, 
        {"name": "إعدادات_المحتوى", "cols": ["bot_id","الرسالة الترحيبية","القوانين","رد التوقف","auto_reply","ai_enabled","welcome_enabled","buttons","banned_words","admin_ids","language","theme","delay_response","broadcast_enabled","custom_commands", "welcome_morning", "welcome_noon", "welcome_evening", "welcome_night"], "color": {"red": 1.0, "green": 0.95, "blue": 0.8}},
        {"name": "الإحصائيات", "cols": ["bot_id","daily_users","messages_count","new_users","blocked_users","date"], "color": {"red": 0.92, "green": 0.82, "blue": 0.86}},
        {"name": "السجلات", "cols": ["bot_id","type","message","time"], "color": {"red": 0.93, "green": 0.93, "blue": 0.93}},
        {"name": "_meta", "cols": ["key", "value", "updated_at"], "color": {"red": 1, "green": 0.8, "blue": 0.8}}, 
        {"name": "الذكاء_الإصطناعي", "cols": ["bot_id","ID_المستخدم","اسم_المستخدم","تاريخ_التسجيل","الحالة","نوع_الاشتراك","عدد_البوتات","آخر_نشاط","اللغة","مصدر_التسجيل","معرف_إحالة","رصيد","اسم_المؤسسة","تعليمات_AI"] }, 
        {"name": "المدفوعات", "cols": ["bot_id", "معرف_الفرع", "user_id","amount","method","date","status"], "color": {"red": 0.99, "green": 0.9, "blue": 0.8}},
        {"name": "قاعدة_بيانات_الطلاب", "cols": ["bot_id","معرف_الفرع", "معرف_الطالب","ID_المستخدم_تيليجرام","الاسم_بالإنجليزي","الاسم_بالعربي","العمر","البلد","المدينة","رقم_الهاتف","البريد_الإلكتروني","تاريخ_الميلاد","المستوى","الحالة","كلمة_المرور","رابط_الصورة","معرف_الدورة","اسم_الدورة","معرف_المجموعة", "اسم_المجموعة","الجنس","اسم_ ولي_الأمر","رقم_تواصل_ولي_الأمر","المؤهل_العلمي","التخصص","سنوات_الخبرة","دورات_سابقة","رابط_LinkedIn","رابط_Telegram","الرسوم","طريقة_الدفع","رابط_الإيصال","سبب_الرفض","النسبة%","المبلغ_المستحق","حالة_الحظر","معرف_الموظف","اسم_الموظف","معرف_الحملة_التسويقية","اسم_الفرع","ملاحظات"]},
        {"name": "سجل_التسجيلات", "cols": ["bot_id", "معرف_الفرع" , "معرف_التسجيل","طابع_زمني","معرف_الطالب","اسم_الطالب","ID_المستخدم_تيليجرام","معرف_الدورة","اسم_الدورة","معرف_المجموعة","اسم_المجموعة","تاريخ_التسجيل","حالة_التسجيل","طريقة_التسجيل","معرف_الخصم","قيمة_الخصم","السعر_الأصلي","السعر_بعد_الخصم","المبلغ_المدفوع","المبلغ_المتبقي","حالة_الدفع","طريقة_الدفع","رابط_الإيصال","اسم_الموظف","معرف_الموظف","معرف_الحملة_التسويقية","اسم_الفرع","حالة_القبول","سبب_الرفض","تاريخ_آخر_تحديث","ملاحظات","تاريخ_الانسحاب","حالة_الترقية","الدورة_السابقة","المجموعة_السابقة","ملاحظات_الإدارة","تاريخ_تأكيد_الدفع","تاريخ_تذكير_الدفع"]},
        {"name": "الأقسام", "cols": ["bot_id","معرف_القسم","اسم_القسم","الحالة","ترتيب_العرض","تاريخ_الإنشاء","معرف_الفرع","ملاحظات"]},
        {"name": "الكوبونات", "cols": ["bot_id", "معرف_الفرع", "معرف_الكوبون","معرف_الطالب","قيمة_الخصم","نوع_الخصم","الحد_الأقصى_للاستخدام","حالة_الكوبون","تاريخ_الإنشاء","تاريخ_الانتهاء","ملاحظات"]},
        {"name": "الدورات_التدريبية", "cols": ["bot_id", "معرف_الفرع", "معرف_الدورة", "اسم_الدورة", "الوصف", "تاريخ_البداية", "تاريخ_النهاية", "نوع_الدورة", "سعر_الدورة", "الحد_الأقصى", "المتطلبات", "اسم_الموظف", "معرف_الموظف", "معرف_الحملة_التسويقية", "معرف_المدرب", "ID_المدرب", "اسم_المدرب", "معرف_القسم"]},
        {"name": "المدربين", "cols": ["bot_id","معرف_الفرع ","ID", "اسم_المدرب", "التخصص", "رقم_الهاتف", "البريد_الإلكتروني", "السيرة_الذاتية", "رابط_الصورة", "الحالة", "اسم_الفرع", "عدد_الدورات_الحالية", "تاريخ_التعاقد", "ملاحظات"], "color": {"red": 0.88, "green": 0.95, "blue": 0.88}},
        {"name": "إدارة_الحملات_الإعلانية", "cols": ["bot_id", "معرف_الفرع","معرف_الدورة", "معرف_الحملة","المنصة","تاريخ_البداية","تاريخ_النهاية","الميزانية","عدد_المسجلين","الحالة","ID_المسوق"] },
        {"name": "أكواد_الخصم", "cols": ["bot_id", "معرف_الفرع", "معرف_الخصم","نوع_الخصم","الوصف","قيمة_الخصم","الحد_الأقصى_للاستخدام","عدد_الاستخدامات","تاريخ_البداية","تاريخ_الانتهاء","الحالة","معرف_الدورة","اسم_الموظف","معرف_الحملة_التسويقية","ملاحظات"]},
        {"name": "الأسئلة_الشائعة", "cols": ["bot_id" ,"معرف_الفرع", "معرف_القسم","معرف_الدورة","اسم_الدورة", "محتوى_السؤال_مع_الإجابة","الحالة","ترتيب_العرض","تاريخ_الإنشاء","معرف_الفرع","اسم_الفرع","ملاحظات"]},
        {"name": "إدارة_الموظفين", "cols": ["bot_id","معرف_الفرع ","ID","معرف_الموظف","الاسم_الكامل","الجنس","تاريخ_الميلاد","رقم_الهوية","العنوان","الصورة_الشخصية","التخصص","المسمى_الوظيفي","المواد_التي_يدرسها","المؤهل_العلمي","سنوات_الخبرة","الشهادات_المهنية","مستوى_التقييم","رقم_الهاتف","رقم_واتساب","رقم_طوارئ","البريد_الإلكتروني","كلمة_المرور","نوع_العقد","تاريخ_التعيين","تاريخ_بداية_العقد","تاريخ_نهاية_العقد","عدد_ساعات_العمل","الدرجة_الوظيفية","الحالة_الوظيفية","الراتب_الأساسي","نسبة_الحوافز","البدلات","الخصومات","إجمالي_الراتب","طريقة_الدفع","رقم_الحساب_المالي","المشرف_المباشر","الصلاحيات","تاريخ_آخر_تسجيل_دخول","حالة_الحساب","اسم_الموظف"] },
        {"name": "إدارة_الفروع", "cols": ["bot_id","معرف_الفرع","اسم_الفرع","الدولة", "المدير_المسؤول", "العملة", "ملاحظات"] }, 
        {"name": "بنك_الأسئلة", "cols": ["bot_id","معرف_الفرع","معرف_الاختبار", "معرف_الدورة","معرف_المجموعة", "معرف_السؤال","نص_السؤال","الخيار_A","الخيار_B","الخيار_C","الخيار_D","الإجابة_الصحيحة","الدرجة","مدة_السؤال_بالثواني","مستوى_الصعوبة","نوع_السؤال","شرح_الإجابة","الوسم_التصنيفي","حالة_السؤال","تاريخ_الإضافة","معرف_مُنشئ_السؤال"]},
        {"name": "الاختبارات_الآلية", "cols": ["bot_id", "معرف_الفرع", "معرف_الاختبار","معرف_الدورة","المجموعات_المستهدفة", "قائمة_الأسئلة","عدد_الأسئلة","درجة_النجاح","مدة_الاختبار","طريقة_حساب_الوقت","ترتيب_عشوائي","عدد_المحاولات","ظهور_النتيجة","حالة_الاختبار","معرف_المدرب", "تاريخ_الإنشاء"]},
        {"name": "سجل_الإجابات", "cols": ["bot_id","معرف_الفرع", "معرف_الدورة", "معرف_الاختبار", "معرف_الطالب", "تفاصيل_الاجابات", "الإجابات_الخاطئة", "الدرجة", "النسبة_المئوية", "حالة_النجاح", "تاريخ_الاختبار", "وقت_البدء", "وقت_التسليم","محاولات_الغش", "الرقم_التسلسلي", "تاريخ_الإصدار", "الحالة", "نوع_الشهادة", "رابط_الشهادة", "سبب_الالغاء"]}, 
        {"name": "الإدارة_المالية", "cols": ["bot_id", "معرف_الفرع", "معرف_الدفع","معرف_الطالب","معرف_الدورة","المبلغ_المدفوع","المبلغ_الإجمالي","تاريخ_الدفع","طريقة_الدفع","رابط_الإيصال","حالة_السداد","معرف_الموظف","معرف_الحملة_التسويقية","ملاحظات"] }, 
        {"name": "المهام_الإدارية", "cols": ["bot_id", "معرف_الفرع", "معرف_المهمة", "عنوان_المهمة", "الوصف", "الموظف_المسؤول", "تاريخ_الإسناد", "الموعد_النهائي", "الحالة", "الأولوية", "تاريخ_الإتمام", "ملاحظات_المتابعة", "المرفقات", "نوع_المهمة", "تاريخ_آخر_تحديث", "حالة_التنبيه"] },
        {"name": "سجل_العمليات_الإدارية", "cols": ["bot_id","معرف_الفرع ","معرف_الموظف", "التاريخ_والوقت", "الإجراء", "التفاصيل"] },
        {"name": "الطلبات", "cols": ["bot_id","معرف_الفرع ","معرف_الطلب", "التاريخ", "معرف_الطالب", "اسم_الطالب", "نوع_الطلب", "التفاصيل", "الأولوية", "الحالة", "الموظف_المسؤول", "قناة_الطلب", "تاريخ_الرد", "تاريخ_الإغلاق", "مدة_المعالجة", "ملاحظات_الإدارة", "مرفقات", "آخر_تحديث"] },
        {"name": "المكتبة", "cols": ["bot_id","معرف_الفرع ","معرف_الملف","اسم_الملف","النوع","التصنيف","الدورة","الوصف","الرابط","صلاحية_الوصول","سعر_الوصول","عدد_المشاهدات","عدد_المشتركين","لغة_المحتوى","المستوى","مدة_المحاضرة","تاريخ_الإضافة","تاريخ_آخر_تحديث","أضيف_بواسطة","الحالة","سجل_التعديل","عدد_التقييمات","متوسط_التقييم","تعليقات","عدد_المشاركات"] },
        {"name": "الأوسمة", "cols": ["bot_id","معرف_الفرع", "معرف_الوسام", "معرف_الطالب", "اسم_الوسام", "وصف_الوسام", "سبب_المنح", "تاريخ_المنح", "منح_بواسطة", "مرئي_للطالب", "ملاحظات"] },
        {"name": "الإنجازات", "cols": ["bot_id","معرف_الفرع ","معرف_الإنجاز", "معرف_الطالب", "اسم_الطالب", "معرف_الدورة", "معرف_المجموعة", "نوع_الإنجاز", "وصف_الإنجاز", "التاريخ", "المصدر", "المستوى", "النقاط", "مرئي_للطالب", "ملاحظات", "تاريخ_آخر_تحديث"] }, 
        {"name": "الواجبات", "cols": ["bot_id", "معرف_الفرع", "معرف_الواجب", "معرف_الدورة", "معرف_المجموعة", "عنوان_الواجب", "وصف_الواجب", "تاريخ_الإسناد", "تاريخ_التسليم", "طريقة_التسليم", "الحالة", "درجة_كاملة", "ملاحظات_المعلم", "مرفقات", "آخر_تحديث"] },
        {"name": "تنفيذ_الواجبات_من_الطلاب", "cols": ["bot_id","معرف_الفرع ","معرف_التنفيذ","معرف_الواجب","معرف_الطالب","معرف_المجموعة","معرف_الدورة","تاريخ_البداية","تاريخ_التسليم","حالة_التنفيذ","النقاط_المكتسبة","ملاحظات_المعلم","مرفقات_الطالب","عدد_محاولات_التسليم","وقت_الإكمال","تقييم_التسليم","آخر_تحديث","مرئي_للطالب"] },  
        {"name": "إدارة_المجموعات", "cols": ["bot_id","معرف_الفرع ", "معرف_المجموعة","اسم_المجموعة","معرف_الدورة","أيام_الدراسة","توقيت_الدراسة","ID_المعلم_المسؤول","حالة_المجموعة","معرف_الموظف","معرف_الحملة_التسويقية", "سعة_المجموعة", "عدد_الطلاب_الحالي", "رابط_المجموعة", "تاريخ_الإنشاء"] },
        {"name": "جدول_المحاضرات", "cols": ["bot_id","معرف_الفرع ","التاريخ", "اليوم", "وقت_البداية", "وقت_النهاية", "معرف_الدورة", "معرف_المجموعة", "معرف_المدرب", "اسم_المدرب", "الحالة", "ملاحظات", "نوع_الحصة", "رابط_الحصة", "تنبيه_تلقائي"] },
        {"name": "سجل_ساعات_العمل", "cols": ["bot_id","معرف_الفرع ","معرف_الموظف", "وقت_تسجيل_الدخول", "وقت_تسجيل_الخروج", "نوع_النشاط", "ملاحظات"] },
        {"name": "كشوف_المرتبات", "cols": ["bot_id","معرف_الفرع ","الشهر", "معرف_الموظف", "الراتب_الأساسي", "الحوافز", "الخصومات", "صافي_الراتب", "حالة_الصرف"] },
        
    

        
    ]
    return sheets_config
# --------------------------------------------------------------------------
# [ نظام التحقق الذكي من الجداول والأعمدة بدون إعادة تهيئة ]

def ensure_sheet_structure(sheet_name, required_headers):
    """
    التحقق من وجود الورقة + الأعمدة
    - لا يحذف أي شيء
    - لا يعيد إنشاء الورقة إذا كانت موجودة
    - يضيف فقط الأعمدة الناقصة
    """
    try:
        try:
            sheet = ss.worksheet(sheet_name)
        except:
            # إنشاء الورقة إذا لم تكن موجودة
            sheet = ss.add_worksheet(title=sheet_name, rows="1000", cols="50")
            sheet.append_row(required_headers)
            print(f"✅ تم إنشاء الورقة: {sheet_name}")
            return True

        # جلب الصف الأول (العناوين)
        existing_headers = sheet.row_values(1)

        # إذا كانت الورقة فارغة
        if not existing_headers:
            sheet.append_row(required_headers)
            print(f"✅ تم إضافة العناوين للورقة الفارغة: {sheet_name}")
            return True

        # تحديد الأعمدة الناقصة فقط
        missing_headers = [h for h in required_headers if h not in existing_headers]

        # إضافة الأعمدة الناقصة فقط
        if missing_headers:
            new_headers = existing_headers + missing_headers
            sheet.update('1:1', [new_headers])
            print(f"⚙️ تم تحديث الأعمدة في {sheet_name} (إضافة الناقص فقط)")
        else:
            print(f"✔️ الورقة {sheet_name} جاهزة ولا تحتاج تعديل")

        return True

    except Exception as e:
        print(f"❌ خطأ في التحقق من الورقة {sheet_name}: {e}")
        return False



# --------------------------------------------------------------------------
# دالة تحديث الأعمدة 
def ensure_sheet_schema(worksheet, required_headers):
    """تحديث أعمدة ورقة واحدة دون حذف البيانات"""
    try:
        existing_headers = worksheet.row_values(1)
        new_headers = [h for h in required_headers if h not in existing_headers]
        if new_headers:
            next_col = len(existing_headers) + 1
            worksheet.update_cell(1, next_col, new_headers)
            print(f"✅ تمت إضافة أعمدة جديدة لـ {worksheet.title}")
    except Exception as e:
        print(f"❌ خطأ في تحديث أعمدة {worksheet.title}: {e}")
# --------------------------------------------------------------------------
# دالة النظام الشامل 
def ensure_all_sheets_schema(spreadsheet, sheets_structure):
    """
    نظام مزامنة ذكي (النسخة المطورة):
    - يجلب قائمة الأوراق بالكامل مرة واحدة لتوفير طلبات API.
    - يتفادى خطأ "A sheet with the name ... already exists".
    - يضيف الأعمدة الناقصة فقط ولا يلمس البيانات الموجودة.
    """
    try:
        # جلب أسماء كل الأوراق الموجودة حالياً دفعة واحدة
        existing_sheet_names = [ws.title for ws in spreadsheet.worksheets()]
        
        for sheet_def in sheets_structure:
            sheet_name = sheet_def.get("name")
            required_headers = sheet_def.get("cols", [])

            if not sheet_name or not required_headers:
                continue

            # التحقق محلياً من القائمة
            if sheet_name not in existing_sheet_names:
                # إنشاء الورقة فقط إذا لم تكن موجودة
                worksheet = spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows="1000",
                    cols=str(len(required_headers) + 10)
                )
                print(f"🆕 تم إنشاء الورقة بنجاح: {sheet_name}")
            else:
                # إذا كانت موجودة، نفتحها لنفحص أعمدتها
                worksheet = spreadsheet.worksheet(sheet_name)

            # فحص وتحديث الأعمدة الناقصة
            ensure_sheet_schema(worksheet, required_headers)

    except Exception as e:
        print(f"❌ خطأ في مزامنة الأوراق: {e}")

# --------------------------------------------------------------------------
# كاش داخلي لتسريع العمليات
_ws_cache = {}
# --- [ 2. كتل الاتصال والتهيئة الأساسية ] ---
def get_config():
    """جلب وتصحيح مفاتيح الوصول من متغيرات البيئة لضمان توافق RSA و JWT الرقمي"""
    raw_key = os.getenv("G_PRIVATE_KEY")
    if not raw_key:
        print("❌ خطأ حرج: G_PRIVATE_KEY مفقود من إعدادات السيرفر!")
        return None
    try:
        clean_key = raw_key.replace('\\n', '\n').strip().strip('"').strip("'")
        return {
            "type": "service_account",
            "project_id": os.getenv("G_PROJECT_ID"),
            "private_key_id": os.getenv("G_PRIVATE_KEY_ID"),
            "private_key": clean_key,
            "client_email": os.getenv("G_CLIENT_EMAIL"),
            "client_id": os.getenv("G_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("G_CLIENT_CERT_URL")
        }
    except Exception as e:
        print(f"❌ خطأ في معالجة القاموس البرمجي للاعتمادات: {e}")
        return None
# --------------------------------------------------------------------------
# --- [ 2. دالة الاتصال المصححة والمضمونة ] ---
def connect_to_google():
    """تأسيس الاتصال وربط المتغيرات مع فحص المخطط فورياً"""
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    global stats_sheet, payments_sheet, students_db_sheet, registrations_logs_sheet
    global departments_sheet, discount_codes_sheet, coupons_sheet, courses_sheet 
    global faq_sheet, meta_sheet, coaches_sheet, lectures_sheet

    config = get_config()
    if not config: return False

    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        ss = client.open_by_key(SPREADSHEET_ID)
        
        # --- [إصلاح: تعريف الدالة المساعدة بشكل صحيح] ---
        def safe_get_sheet(name):
            try: return ss.worksheet(name)
            except: return None

        users_sheet = safe_get_sheet("المستخدمين")
        bots_sheet = safe_get_sheet("البوتات_المصنوعة")
        content_sheet = safe_get_sheet("إعدادات_المحتوى")
        logs_sheet = safe_get_sheet("السجلات")
        stats_sheet = safe_get_sheet("الإحصائيات")
        payments_sheet = safe_get_sheet("المدفوعات")
        students_db_sheet = safe_get_sheet("قاعدة_بيانات_الطلاب")
        registrations_logs_sheet = safe_get_sheet("سجل_التسجيلات")
        departments_sheet = safe_get_sheet("الأقسام")
        discount_codes_sheet = safe_get_sheet("أكواد_الخصم")
        coupons_sheet = safe_get_sheet("الكوبونات")
        courses_sheet = safe_get_sheet("الدورات_التدريبية")
        faq_sheet = safe_get_sheet("الأسئلة_الشائعة")
        meta_sheet = safe_get_sheet("_meta")
        coaches_sheet = safe_get_sheet("المدربين") 
        lectures_sheet = safe_get_sheet("جدول_المحاضرات")

        print("✅ تم الاتصال بجوجل بنجاح. الجداول بانتظار التهيئة اليدوية ⚙️")
        return True
    except Exception as e:
        print(f"❌ فشل الاتصال الأولي: {str(e)}")
        return False

# تنفيذ محاولة الاتصال الفورية
connect_to_google() 

# --------------------------------------------------------------------------
# --- [ 3. الدوال الوظيفية لبوت المصنع والطلاب ] ---
# --- الدوال الوظيفية الأساسية ---

def save_user(user_id, username):
    global users_sheet
    if users_sheet is None:
        if not connect_to_google(): return False
    try:
        try:
            exists = users_sheet.find(str(user_id))
            if exists: return False
        except: pass
        now = get_system_time("full")
        row = [str(user_id), str(username), now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        users_sheet.insert_row(row, 2)
        return True
    except Exception as e:
        print(f"❌ خطأ تسجيل مستخدم: {e}")
        return False
# --------------------------------------------------------------------------
# دالة الحفظ وتهيئة البوت

def save_bot(owner_id, bot_type, bot_name, bot_token):
    global bots_sheet, content_sheet
    if bots_sheet is None or content_sheet is None:
        if not connect_to_google(): return False
    try:
        now = get_system_time("full")
        today = get_system_time("date")
        bot_token = str(bot_token).strip()
        
        # 1. جلب معلومات البوت من تيليجرام لضمان الدقة
        real_bot_name = bot_name
        username_bot = ""
        try:
            import requests
            res = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe").json()
            if res.get("ok"):
                real_bot_name = res["result"]["first_name"]
                username_bot = res["result"]["username"]
        except: pass

        # 2. زرع الإعدادات الافتراضية أولاً لضمان وجود القيم
        seed_default_settings(bot_token)

        # --- [ جلب القيم الحقيقية من ورقة الإعدادات قبل الحفظ ] ---
        sub_price = get_bot_setting(bot_token, "subscription_price", default="100")
        max_students = get_bot_setting(bot_token, "maximum_number_students", default="100")
        max_courses = get_bot_setting(bot_token, "maximum_number_courses", default="10")
        max_sections = get_bot_setting(bot_token, "maximum_number_sections", default="3")
        ai_cost_val = get_bot_setting(bot_token, "AI_cost", default="100")
        op_env = get_bot_setting(bot_token, "operating_environment", default="Production")

        # 3. بناء مصفوفة البيانات الكاملة (44 عموداً) بالترتيب الدقيق والمحدث
        bot_row = [
            str(owner_id),          # 1. ID المالك
            bot_type,               # 2. نوع البوت
            real_bot_name,          # 3. اسم البوت
            bot_token,              # 4. التوكن
            "نشط",                  # 5. حالة التشغيل
            bot_token.split(':')[0],# 6. bot_id
            username_bot,           # 7. username_bot
            now,                    # 8. تاريخ الإنشاء
            now,                    # 9. آخر تشغيل
            0,                      # 10. عدد المستخدمين
            0,                      # 11. عدد الرسائل
            "جيد",                  # 12. الحالة التقنية
            "",                     # 13. webhook_url
            "polling",              # 14. api_type
            "free",                 # 15. plan
            "",                     # 16. expiration_date
            "true",                 # 17. is_active
            "",                     # 18. errors_log
            today,                  # 19. تاريخ_آخر_تجديد
            str(sub_price),         # 20. سعر_الاشتراك (ديناميكي)
            "0",                    # 21. رصيد_البوت
            str(max_students),      # 22. الحد_الأقصى_للطلاب (ديناميكي)
            str(max_courses),       # 23. الحد_الأقصى_للدوات (ديناميكي)
            str(max_sections),      # 24. الحد_الأقصى_للاقسام (ديناميكي)
            "TRUE",                 # 25. ميزة_الذكاء_الاصطناعي
            "FALSE",                # 26. ميزة_رفع_وتصدير_البيانات_اكسل (القيمة الافتراضية المطلوبة)
            f"INV-{uuid.uuid4().hex[:6].upper()}", # 27. معرف_الفاتورة
            "0ms",                  # 28. متوسط_زمن_الاستجابة
            "0%",                   # 29. استخدام_CPU
            "0MB",                  # 30. استخدام_الذاكرة
            0,                      # 31. المستخدمون_النشطون_يومياً
            0,                      # 32. المستخدمون_النشطون_شهرياً
            "100%",                 # 33. معدل_الاحتفاظ
            now,                    # 34. تاريخ_آخر_تحديث_للتوكن
            "Valid",                # 35. حالة_التوكن
            "Pending",              # 36. حالة_الدفع
            "Manual",               # 37. طريقة_الدفع
            "Monthly",              # 38. دورة_الفوترة
            "1.0.0",                # 39. إصدار_البوت
            str(op_env),            # 40. بيئة_التشغيل (ديناميكي)
            "true",                 # 41. إعادة_تشغيل_تلقائي
            "Gemini-1.5-Flash",     # 42. نموذج_الذكاء_الاصطناعي
            0,                      # 43. استهلاك_التوكنات_AI
            str(ai_cost_val)        # 44. تكلفة_AI (ديناميكي)
        ]
        
        try:
            # البحث عن التوكن لمعرفة هل هو بوت موجود مسبقاً
            cell_bot = bots_sheet.find(bot_token)
            row_idx = cell_bot.row
            # تحديث (الحالة، آخر تشغيل، الإصدار) فقط للحفاظ على تاريخ الإنشاء والباقة الأصلية
            updates = [
                {'range': f"E{row_idx}", 'values': [["نشط"]]}, 
                {'range': f"I{row_idx}", 'values': [[now]]},
                {'range': f"AM{row_idx}", 'values': [["1.0.0"]]}
            ]
            bots_sheet.batch_update(updates)
            print(f"♻️ تم تحديث بيانات التشغيل للبوت في السطر {row_idx} مع حماية التاريخ والباقة")
        except:
            # إضافة صف جديد بالكامل فقط إذا لم يكن البوت موجوداً نهائياً
            bots_sheet.append_row(bot_row)
            print("✨ تم إضافة بوت جديد ببياناته الكاملة")


        # 5. إدارة ورقة "إعدادات_المحتوى" لضمان الملكية
        content_row = [
            bot_token, "أهلاً بك! 🤖", "لا توجد قوانين حالياً.", 
            "عذراً، البوت متوقف مؤقتاً.", "false", "false", "true", "[]", "[]", 
            str(owner_id), "ar", "default", "0", "true", "[]"
        ]

        try:
            cell_content = content_sheet.find(bot_token)
            # تحديث معرف المالك لضمان السيطرة
            content_sheet.update_cell(cell_content.row, 10, str(owner_id))
            print(f"✅ تم تحديث ملكية المحتوى للتليجرام ID: {owner_id}")
        except:
            # تنفيذ هذا السطر في حال فشل العثور على البوت (إنشاء جديد)
            content_sheet.append_row(content_row)
            print("📝 تم إنشاء سجل إعدادات المحتوى لأول مرة")

        # --- [ حجر الأساس: ربط البوت بنظام المزامنة والذاكرة المؤقتة ] ---
        ensure_bot_sync_row(bot_token, owner_id)
        return True
    except Exception as e:
        print(f"❌ خطأ حرج في save_bot المحدثة: {e}")
        return False



# --------------------------------------------------------------------------

def update_content_setting(bot_id, column_name, new_value):
    global content_sheet
    if content_sheet is None:
        if not connect_to_google(): return False
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            headers = content_sheet.row_values(1)
            if column_name in headers:
                col_index = headers.index(column_name) + 1
                content_sheet.update_cell(cell.row, col_index, new_value)
                return True
    except Exception as e:
        print(f"❌ خطأ تحديث إعدادات: {e}")
    return False

def get_bot_config(bot_id):
    global content_sheet
    if content_sheet is None:
        if not connect_to_google(): return False
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            values = content_sheet.row_values(cell.row)
            headers = content_sheet.row_values(1)
            return dict(zip(headers, values))
    except Exception as e:
        print(f"❌ خطأ جلب تكوين: {e}")
    return {}

def add_log_entry(bot_id, log_type, message):
    global logs_sheet
    if logs_sheet is None:
        if not connect_to_google(): return False
    try:
        now = get_system_time("full")
        logs_sheet.append_row([str(bot_id), log_type, message, now])
        return True
    except Exception as e:
        print(f"❌ خطأ تدوين سجل: {e}")
        return False

def check_connection():
    try:
        ss.title
        return True
    except:
        return connect_to_google()

# --------------------------------------------------------------------------
# جلب الإحصائيات 
def get_all_active_bots():
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try:
        all_records = bots_sheet.get_all_records()
        return [bot for bot in all_records if bot.get("التوكن") and bot.get("حالة التشغيل") == "نشط"]
    except Exception as e:
        print(f"❌ خطأ جلب البوتات: {e}")
        return []

def get_total_bots_count():
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try: return len(bots_sheet.col_values(1)) - 1
    except: return 0

def get_bot_users_count(bot_token):
    return 1

def get_bot_blocks_count(bot_token):
    return 0

def get_total_factory_users():
    global users_sheet
    if users_sheet is None: connect_to_google()
    try: return len(users_sheet.col_values(1)) - 1
    except: return 0

# --------------------------------------------------------------------------
def safe_api_call(func, *args, **kwargs):
    """
    الوسيط الذكي: 
    - يعالج مشكلة (name 'safe_api_call' is not defined).
    - يعالج مشكلة (Quota exceeded 429) عبر الانتظار وإعادة المحاولة.
    """
    for attempt in range(RETRY_ATTEMPTS):
        try:
            # محاولة تنفيذ الطلب (سواء كان إضافة ورقة أو قراءة بيانات)
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if "429" in str(e):
                # إذا تجاوزنا الكوتا، ننتظر وقتاً يتضاعف مع كل محاولة
                wait_time = (attempt + 1) * 3 
                logger.warning(f"⚠️ تجاوزت كوتا جوجل. انتظر {wait_time} ثانية (محاولة {attempt + 1})...")
                time.sleep(wait_time)
            else:
                # إذا كان خطأ آخر، نرفعه للنظام
                raise e
        except Exception as e:
            logger.error(f"❌ خطأ غير متوقع في طلب API: {e}")
            time.sleep(1)
    return None

# --------------------------------------------------------------------------
# دالة إنشاء وتجهيز الورق - النسخة المعززة بالفواصل الزمنية
# دالة إنشاء وتجهيز الورق - النسخة المحدثة مع تعطيل الحجم التلقائي وإضافة فواصل زمنية

def setup_bot_factory_database(bot_token=None):
    """المحرك الشامل: ينشئ الجداول، ينسق الهيدرز، يزرع الإعدادات، ويعيد عدد الأوراق ديناميكياً"""
    global ss, _ws_cache
    if 'ss' not in globals() or ss is None: connect_to_google()
    all_requests = []

    # جلب الهيكل وحساب عدد الأوراق الكلي بشكل ديناميكي  
    structures = get_sheets_structure()  
    total_sheets = len(structures)   

    # إضافة تأخير بسيط قبل البدء بجلب كافة الأوراق لتجنب الضغط الأولي  
    time.sleep(1)  
    _ws_cache = {ws.title: ws for ws in ss.worksheets()}  

    for config in structures:  
        try:  
            sheet_name = config["name"]  
            headers = config["cols"]  
            if sheet_name not in _ws_cache:  
                worksheet = safe_api_call(ss.add_worksheet, title=sheet_name, rows="500", cols=str(len(headers) + 2))  
                _ws_cache[sheet_name] = worksheet  
                time.sleep(1) # تأخير إضافي عند إنشاء ورقة جديدة  
            else:  
                worksheet = _ws_cache[sheet_name]  

            # قراءة العناوين الحالية  
            current_headers = worksheet.row_values(1)  

            # --- [ MIGRATION SYSTEM: إضافة الأعمدة الجديدة بدون حذف القديمة ] ---
            try:
                new_columns = [col for col in headers if col not in current_headers]

                if new_columns:
                    print(f"🆕 اكتشاف أعمدة جديدة في {sheet_name}: {new_columns}")

                    try:
                        current_col_count = len(current_headers)
                    except:
                        current_col_count = 0

                    try:
                        required_cols = current_col_count + len(new_columns)
                        safe_api_call(
                            worksheet.add_cols,
                            len(new_columns)
                        )
                        time.sleep(1)
                    except Exception as e:
                        print(f"⚠️ فشل في توسيع الأعمدة في {sheet_name}: {e}")

                    try:
                        refreshed_headers = worksheet.row_values(1)
                    except:
                        refreshed_headers = current_headers

                    updated_headers = refreshed_headers + new_columns

                    try:
                        safe_api_call(
                            worksheet.update,
                            '1:1',
                            [updated_headers]
                        )
                        print(f"✅ تمت إضافة الأعمدة الجديدة في {sheet_name}")
                        time.sleep(1)

                        # ✅ تحديث current_headers لمنع التحديث المزدوج
                        current_headers = updated_headers

                    except Exception as e:
                        print(f"❌ فشل تحديث الهيدرز بعد الإضافة في {sheet_name}: {e}")

            except Exception as e:
                print(f"❌ خطأ في نظام Migration داخل {sheet_name}: {e}")

            time.sleep(0.6) # فاصل زمني بعد عملية القراءة  

            if set(current_headers) != set(headers):  
                if STRICT_SCHEMA:  
                    safe_api_call(worksheet.update, '1:1', [headers])  
                    time.sleep(1) # تأخير بعد تحديث العناوين  

            sheet_id = worksheet.id  
            all_requests.extend([  
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1}, "cell": {"userEnteredFormat": {"backgroundColor": config.get("color", {"red": 1, "green": 1, "blue": 1}), "textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}}, "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"}},  
                {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}}  
            ])  

            # تم تعطيل هذا الجزء آلياً بناءً على قيمة AUTO_RESIZE = False في الأعلى  
            if AUTO_RESIZE and (not current_headers or set(current_headers) != set(headers)):  
                safe_api_call(worksheet.columns_auto_resize, 0, len(headers))  
                time.sleep(0.8)   

            # الفاصل الزمني الأساسي داخل الحلقة لمنع الاصطدام بالحدود  
            time.sleep(1.5)  

        except Exception as e:   
            print(f"❌ خطأ تهيئة {sheet_name}: {e}")  
            time.sleep(2) # انتظار أطول في حال حدوث خطأ  

    if all_requests:  
        for i in range(0, len(all_requests), BATCH_SIZE):  
            safe_api_call(ss.batch_update, {"requests": all_requests[i:i+BATCH_SIZE]})  
            # تأخير بين دفعات التحديث الجماعي  
            time.sleep(2.5)   

    # --- [ إضافة: زرع الإعدادات الافتراضية ضمن عملية التهيئة ] ---  
    if bot_token:  
        seed_default_settings(bot_token)  
        time.sleep(1.2)  

    update_meta_info()  
    time.sleep(1)  

    # الحفاظ على وظيفة التحقق مع إرجاع العدد الديناميكي في حال النجاح  
    if verify_setup(structures):  
        return total_sheets  
    return 0


# --------------------------------------------------------------------------    
# تجهيز وتعبئة ورقة الإعدادات (الدالة المدمجة والكاملة)
def seed_default_settings(bot_token):
    """تعبئة المفاتيح البرمجية الافتراضية في ورقة الإعدادات لتجنب الأخطاء"""
    try:
        sheet = ss.worksheet("الإعدادات")
        existing_records = sheet.get_all_records()
        
        # 1. تحديد كافة المفاتيح الأساسية مع الأوصاف التفصيلية الكاملة
        default_keys = [
            {
                "key": "ref_points_join",
                "title": "نقاط دعوة صديق",
                "value": "10",
                "note": "النقاط التي يحصل عليها الشخص عند دخول صديق عبر رابطه"
            },
            {
                "key": "ref_points_purchase",
                "title": "نقاط الشراء",
                "value": "50",
                "note": "النقاط التي يحصل عليها الداعي عند قيام الصديق بشراء دورة"
            },
            {
                "key": "min_points_redeem",
                "title": "حد استبدال النقاط",
                "value": "100",
                "note": "الحد الأدنى من النقاط المطلوب لفتح دورة مجانية"
            },
            {
                "key": "AI_cost",
                "title": "تكلفة_AI",
                "value": "100",
                "note": "تكلفة استخدام الذكاء الاصطناعي لكل بوت"
            },
            {
                "key": "operating_environment",
                "title": "بيئة_التشغيل",
                "value": "Ar",
                "note": "تحدد بيئة تشغيل البوت (إنتاج/تجريبي)"
            },
            {
                "key": "subscription_price",
                "title": "سعر_الاشتراك",
                "value": "100",
                "note": "السعر المطلوب للاشتراك في البوت"
            },
            {
                "key": "maximum_number_sections",
                "title": "الحد الأقصى للاقسام",
                "value": "3",
                "note": "أقصى عدد أقسام يمكن للبوت إدارتها"
            },
            {
                "key": "maximum_number_courses",
                "title": "الحد الأقصى للدورات",
                "value": "10",
                "note": "أقصى عدد دورات يمكن للبوت إدارتها"
            },
            {
                "key": "maximum_number_students",
                "title": "الحد الأقصى للطلاب",
                "value": "100",
                "note": "أقصى عدد طلاب يمكن للبوت خدمتهم"
            },
            {
                "key": "currency_unit",
                "title": "وحدة العملة",
                "value": "نقطة",
                "note": "الاسم الذي يظهر بجانب الرصيد (مثلاً: نقطة أو ريال)"
            },
            {
                "key": "homework_grade",
                "title": "درجة الواجبات",
                "value": "10",
                "note": "درجة الواجبات اليومية للطلاب"
            }
        ]

        # 2. فحص كل مفتاح لضمان عدم التكرار لنفس البوت
        for item in default_keys:
            # التحقق من وجود المفتاح في السجلات الحالية
            exists = any(
                str(r.get('bot_id')) == str(bot_token) and 
                str(r.get('المفتاح_البرمجي')) == item['key'] 
                for r in existing_records
            )
            
            if not exists:
                # إعداد الصف الجديد بنفس الترتيب المعتمد
                new_row = [str(bot_token), item['key'], item['title'], item['value'], item['note']]
                
                # استخدام وظيفة safe_api_call لضمان استقرار الاتصال وإعادة المحاولة
                safe_api_call(sheet.append_row, new_row)
                
                # طباعة إشعار النجاح في سجلات السيرفر
                print(f"✅ تم زرع المفتاح: {item['key']}")
                
        return True
    except Exception as e:
        # تسجيل الخطأ بوضوح في حال حدوث أي مشكلة تقنية
        print(f"❌ خطأ أثناء تعبئة الإعدادات: {e}")
        return False

# --------------------------------------------------------------------------
# --- [ كتلة تحديث الميتا والتحقق من سلامة الهيكل ] ---
# تقوم دالة update_meta_info بتسجيل حالة المحرك وإصدار المخطط في ورقة _meta لضمان التوافق.
# تقوم دالة verify_setup بفحص كافة أوراق العمل والتأكد من مطابقة الأعمدة للهيكل المعتمد.

def update_meta_info():
    """تحديث سجلات النظام وإصدار الهيكل في ورقة الميتا لضمان صحة عمل المحرك"""
    try:
        # استدعاء ورقة الميتا من الكاش الداخلي
        meta_ws = _ws_cache.get("_meta")
        if meta_ws:
            # مسح البيانات القديمة لتجنب تداخل الإصدارات
            meta_ws.clear()
            # إعداد مصفوفة البيانات الجديدة (الإصدار، حالة المحرك، تاريخ التحديث)
            meta_data = [
                ["key", "value", "updated_at"], 
                ["version", SCHEMA_VERSION, get_system_time("date")], 
                ["engine_status", "HEALTHY", datetime.now().isoformat()]
            ]
            # تنفيذ الكتابة عبر الوسيط الذكي لضمان تجاوز حدود API جوجل
            safe_api_call(meta_ws.update, 'A1', meta_data)
    except Exception as e: 
        print(f"❌ فشل ميتا: {e}")

def verify_setup(structures):
    """الفحص النهائي: التأكد من أن كل ورقة تم إنشاؤها تحتوي على كافة الأعمدة المطلوبة"""
    for config in structures:
        # جلب الورقة من الكاش
        ws = _ws_cache.get(config["name"])
        # التحقق من وجود الورقة ومطابقة عناوين الأعمدة (Headers) للهيكل الأصلي
        if not ws or set(ws.row_values(1)) != set(config["cols"]): 
            return False
    # في حال اجتياز كافة الفحوصات يعيد نجاح كامل للتهيئة
    return True

# --------------------------------------------------------------------------
# إضافة قسم 
def add_new_category(bot_token, cat_id, cat_name):
    """إضافة قسم جديد لجدول الأقسام بالترتيب الصحيح (8 أعمدة)"""
    try:
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if departments_sheet is not None:
            # الترتيب مطابق للهيكل: bot_id, معرف_القسم, اسم_القسم, الحالة, ترتيب_العرض, تاريخ_الإنشاء, معرف_الفرع, ملاحظات
            row = [
                str(bot_token).strip(),       # 1. bot_id
                str(cat_id).strip(),          # 2. معرف_القسم
                str(cat_name).strip(),        # 3. اسم_القسم
                "نشط",                        # 4. الحالة
                "0",                          # 5. ترتيب_العرض (افتراضي)
                current_date,                 # 6. تاريخ_الإنشاء
                "001",                        # 7. معرف_الفرع (افتراضي)
                "إضافة عبر لوحة التحكم"       # 8. ملاحظات
            ]
            departments_sheet.append_row(row)
            update_global_version(bot_token)


            return True
        return False
    except Exception as e:
        print(f"❌ Error in add_new_category: {e}")
        return False

#دالة حذف القسم والبحث 
def delete_category_by_id(bot_token, cat_id):
    """حذف صف القسم من قاعدة البيانات بناءً على ID القسم والتوكن"""
    try:
        if departments_sheet is None: return False
        
        all_rows = departments_sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # التأكد من مطابقة التوكن (العمود 1) والـ ID (العمود 2)
            if row[0] == bot_token and row[1] == cat_id:
                departments_sheet.delete_rows(i + 1)
                # يجب أن تكون هنا لضمان أن التحديث تم فعلاً
                update_global_version(bot_token)
                return True




                return True
        return False
    except Exception as e:
        print(f"❌ Error in delete_category: {e}")
        return False
        
 # دالة تبحث عن الـ ID وتقوم بتغيير الاسم في ذلك الصف
def update_category_name(bot_token, cat_id, new_name):
    """تحديث اسم قسم موجود في قاعدة البيانات"""
    try:
        if departments_sheet is None: return False
        
        all_rows = departments_sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # العمود 1 توكن، العمود 2 ID
            if row[0] == bot_token and row[1] == cat_id:
                # 1. تحديث الخلية في جوجل شيت
                departments_sheet.update_cell(i + 1, 3, new_name)
                
                # 2. رفع إصدار البوت فوراً لتحديث الكاش (داخل شرط الـ if)
                update_global_version(bot_token)
                
                # 3. العودة بنجاح
                return True
                
        return False
    except Exception as e:
        print(f"❌ Error in update_category_name: {e}")
        return False


# --------------------------------------------------------------------------
#إضافة الدورات 
def add_new_course(bot_token, course_id, name, hours, start_date, end_date, c_type, price, limit, reqs, rep_name, rep_code, campaign, coach_user, coach_id, coach_name, cat_id, **kwargs):
    """إضافة دورة كاملة مع ربطها بالقسم (العمود 18) بالترتيب البرمجي الصحيح"""
    try:
        if courses_sheet is None: return False
        
        # 1. يجب تعريف branch_id أولاً قبل استخدامه في المصفوفة
        branch_id = kwargs.get('branch_id', '001') 
        
        # 2. بناء مصفوفة البيانات بالترتيب المطابق لهيكل جوجل شيت (18 عموداً)
        row = [
            bot_token,          # 1. bot_id
            branch_id,          # 2. معرف_الفرع
            course_id,          # 3. معرف_الدورة
            name,               # 4. اسم_الدورة
            hours,              # 5. عدد_الساعات
            start_date,         # 6. تاريخ_البداية
            end_date,           # 7. تاريخ_النهاية
            c_type,             # 8. نوع_الدورة
            price,              # 9. سعر_الدورة
            limit,              # 10. الحد_الأقصى
            reqs,               # 11. المتطلبات
            rep_name,           # 12. اسم_الموظف
            rep_code,           # 13. معرف_الموظف
            campaign,           # 14. معرف_الحملة_التسويقية
            coach_user,         # 15. معرف_المدرب (يوزر)
            coach_id,           # 16. ID_المدرب (رقمي)
            coach_name,         # 17. اسم_المدرب
            cat_id              # 18. معرف_القسم (للربط الهرمي)
        ]
        
        # 3. تنفيذ عملية الحفظ الفعلية
        courses_sheet.append_row(row)
        update_global_version(bot_token)


        return True
    except Exception as e:
        print(f"❌ Error in add_new_course: {e}")
        return False

# --------------------------------------------------------------------------
# دالة جلب الدورات بقسم محدد
def get_courses_by_category(bot_token, cat_id):
    """جلب كافة الدورات المرتبطة بقسم محدد بناءً على ID القسم (العمود 18)"""
    try:
        # يجب أن تبدأ بـ 8 مسافات (داخل try)
        smart_sync_check(bot_token)
        all_courses = get_bot_data_from_cache(bot_token, "الدورات_التدريبية")
        return [{"id": c.get("معرف_الدورة"), "name": c.get("اسم_الدورة")} for c in all_courses if str(c.get("معرف_القسم")) == str(cat_id)]

    except Exception as e:

        print(f"❌ Error fetching courses from cache: {e}")
        return []


def get_all_categories(bot_token):
    """جلب كافة الأقسام المتاحة لبوت معين"""
    try:
        # إزاحة للداخل (داخل try)
        smart_sync_check(bot_token)
        records = get_bot_data_from_cache(bot_token, "الأقسام")
        return [{"id": r.get("معرف_القسم"), "name": r.get("اسم_القسم")} for r in records]

    except Exception as e:
        print(f"❌ Error fetching categories: {e}")
        return []




# --------------------------------------------------------------------------
# دالة حذف الدورات
def delete_course_by_id(bot_token, course_id):
    """حذف صف دورة محددة من الشيت بناءً على معرف الدورة والتوكن لضمان الدقة وعدم تداخل البيانات"""
    try:
        if courses_sheet is None: return False
        all_rows = courses_sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # التحقق من مطابقة التوكن (العمود 1) ومعرف الدورة (العمود 3 -> Index 2)
            if len(row) >= 3 and str(row[0]) == str(bot_token) and str(row[2]) == str(course_id):
                # 1. تنفيذ الحذف الفعلي من جوجل شيت
                courses_sheet.delete_rows(i + 1)
                
                # 2. رفع رقم الإصدار لتحديث الرام (يجب أن يكون بمحاذاة delete_rows)
                update_global_version(bot_token)
                
                # 3. العودة بنجاح (يجب أن يكون بمحاذاة delete_rows)
                return True
                
        return False
    except Exception as e:
        print(f"❌ Error deleting course: {e}")
        return False

#دالة البحث عن مدرب
def find_user_by_username(bot_token, username):
    """البحث عن بيانات المدرب في شيت المستخدمين باستخدام اليوزرنايم"""
    try:
        # ورقة المستخدمين (تأكد من تسميتها حسب ملفك، سأفترض أنها users_sheet)
        if users_sheet is None: return None
        all_rows = users_sheet.get_all_values()
        search_name = username.replace("@", "").lower()
        
        for row in all_rows[1:]:
            # فحص التوكن واليوزرنايم (العمود 1 والعمود 3 عادةً)
            if row[0] == bot_token and row[2].lower() == search_name:
                return {
                    "id": row[1],   # معرف المستخدم الرقمي
                    "name": row[3] if len(row) > 3 else "مدرب" # الاسم (العمود الرابع)
                }
        return None
    except Exception as e:
        print(f"❌ Error finding user in sheets: {e}")
        return None
# --------------------------------------------------------------------------
#دالة إضافة المدربين

def add_new_coach_advanced(bot_token, coach_id, name, specialty, phone, **kwargs):
    """
    إضافة مدرب جديد لورقة المدربين بنظام متطور.
    kwargs: تتيح لك إرسال قيم اختيارية مثل (email, bio, photo, status, branch_name, notes)
    """
    try:
        if coaches_sheet is None:
            print("⚠️ خطأ: ورقة المدربين غير متصلة.")
            return False

        # 1. التوليد التلقائي لتاريخ اليوم
        today_date = get_system_time("date")

            # الترتيب الصحيح حسب المخطط: bot_id, معرف_الفرع, ID, اسم_المدرب...
        row = [
            str(bot_token),                           # 1. bot_id
            kwargs.get('branch_id', "001"),           # 2. معرف_الفرع
            str(coach_id).strip(),                    # 3. ID (المعرف الرقمي)
            str(name).strip(),                        # 4. اسم_المدرب
            str(specialty).strip(),                   # 5. التخصص
            str(phone).strip(),                       # 6. رقم_الهاتف
            kwargs.get('email', "لا يوجد"),           # 7. البريد_الإلكتروني
            kwargs.get('bio', "لا يوجد"),             # 8. السيرة_الذاتية
            kwargs.get('photo', "لا يوجد"),           # 9. رابط_الصورة
            kwargs.get('status', "نشط"),              # 10. الحالة
            str(bot_token),                           # 11. bot_id (مكرر حسب مخططك)
            kwargs.get('branch_id', "001"),           # 12. معرف_الفرع (مكرر)
            kwargs.get('branch_name', "الرئيسي"),      # 13. اسم_الفرع
            kwargs.get('courses_count', "0"),         # 14. عدد_الدورات
            today_date,                               # 15. تاريخ_التعاقد
            kwargs.get('notes', "إضافة عبر البوت")      # 16. ملاحظات
        ]


        # 3. إضافة الصف للشيت
        coaches_sheet.append_row(row)
        update_global_version(bot_token)
        
        # 4. تسجيل العملية في سجل العمليات (Logging) لزيادة الاحترافية
        print(f"✅ تم تسجيل المدرب {name} بنجاح بتاريخ {today_date}")
        return True

    except Exception as e:
        print(f"❌ خطأ برمي في إضافة المدرب: {e}")
        return False

# --------------------------------------------------------------------------
#جلب بيانات المدربين
def get_all_coaches(bot_token):
    """جلب قائمة المدربين المخصصين لهذا البوت من ورقة المدربين"""
    try:
        # تأكد أن اسم الورقة في المتغير هو coaches_sheet أو جلبها بالاسم
        # coaches_sheet = client.open_by_key(SPREADSHEET_ID).worksheet("المدربين")
        if coaches_sheet is None: return []
        all_rows = coaches_sheet.get_all_values()
        coaches = []
        for row in all_rows[1:]:
            # العمود 9 هو bot_id (Index 8) والعمود 1 هو ID_المدرب (Index 0) والعمود 2 هو الاسم (Index 1)
            # التعديل: التوكن في العمود 1 (Index 0)، الـ ID في 3 (Index 2)، الاسم في 4 (Index 3)
            if len(row) >= 1 and row[0] == bot_token:
                coaches.append({
                    "id": row[2],    # ID_المدرب
                    "name": row[3]   # اسم_المدرب
                })

        return coaches
    except Exception as e:
        print(f"❌ Error fetching coaches: {e}")
        return []
 
def delete_coach_from_sheet(bot_token, coach_id):
    """حذف مدرب من الشيت بناءً على الـ ID وتوكن البوت"""
    try:
        if coaches_sheet is None: return False
        all_rows = coaches_sheet.get_all_values()
        for i, row in enumerate(all_rows):
           
            # التعديل: ID المدرب في Index 2، والتوكن في Index 0
            if len(row) >= 3 and str(row[2]) == str(coach_id) and row[0] == bot_token:
                coaches_sheet.delete_rows(i + 1)
                return True
        return False
    except Exception as e:
        print(f"❌ Error deleting coach: {e}")
        return False

# --------------------------------------------------------------------------
# دالة جلب إعدادات الذكاء الاصطناعي (تم توحيد المسمى لـ setup)
def get_ai_setup(bot_token):
    """جلب إعدادات الهوية والذكاء من ورقة الذكاء_الإصطناعي"""
    try:
        # التأكد من مطابقة اسم الورقة تماماً لما في قاعدة البيانات
        sheet = ss.worksheet("الذكاء_الإصطناعي")
        records = sheet.get_all_records()
        for r in records:
            # تنظيف التوكن من أي مسافات زائدة للمقارنة الدقيقة
            if str(r.get('bot_id', '')).strip() == str(bot_token).strip():
                return r
        return None
    except Exception as e:
        print(f"❌ Error fetching AI setup: {e}")
        return None
# --------------------------------------------------------------------------
# دالة حفظ أو تحديث إعدادات الذكاء الاصطناعي (تم توحيد المسمى لـ setup)
def save_ai_setup(bot_token, user_id, username, institution_name=None, ai_instructions=None):
    """حفظ أو تحديث بيانات المؤسسة وتعليمات الذكاء الاصطناعي"""
    try:
        sheet = ss.worksheet("الذكاء_الإصطناعي")
        cell = None
        try: 
            # البحث عن التوكن في العمود الأول فقط (A) لتجنب الأخطاء
            cell = sheet.find(str(bot_token).strip(), in_column=1)
        except: pass

        now = get_system_time("full")
        
        if cell:
            # تحديث البيانات في الأعمدة 13 و 14 (حسب ترتيبك)
            if institution_name: sheet.update_cell(cell.row, 13, institution_name)
            if ai_instructions: sheet.update_cell(cell.row, 14, ai_instructions)
            sheet.update_cell(cell.row, 8, now) # تحديث عمود آخر نشاط (H)
        else:
            # إضافة صف جديد (14 عنصراً لتتطابق مع تصميم الورقة الخاص بك)
            row = [
                str(bot_token).strip(), str(user_id), username, now, 
                "نشط", "إداري", 0, now, "ar", "Direct", 
                "", 0, institution_name or "", ai_instructions or ""
            ]
            sheet.append_row(row)
            update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ Error saving AI setup: {e}")
        return False

# --------------------------------------------------------------------------
def get_courses_knowledge_base(bot_token):
    """جلب بيانات الدورات وتحويلها لنص يفهمه الذكاء الاصطناعي"""
    try:
        if courses_sheet is None: return "لا توجد بيانات حالياً."
        all_courses = courses_sheet.get_all_records()
        bot_courses = [c for c in all_courses if str(c.get('bot_id')) == str(bot_token)]
        if not bot_courses: return "لا توجد دورات متاحة حالياً."
        kb = "قائمة الدورات:\n"
        for c in bot_courses:
            kb += f"- {c.get('اسم_الدورة')}، السعر: {c.get('سعر_الدورة')}، المدرب: {c.get('اسم_المدرب')}.\n"
        return kb
    except Exception as e:
        print(f"❌ خطأ في جلب قاعدة معرفة الدورات: {e}")
        return "المعلومات قيد التحديث حالياً، يرجى المحاولة لاحقاً."


# --------------------------------------------------------------------------
#دالة الصلاحيات 
def get_employee_permissions(bot_token, employee_id):
    """جلب سجل الصلاحيات الكامل لموظف محدد"""
    try:
        sheet = ss.worksheet("الهيكل_التنظيمي_والصلاحيات")
        records = sheet.get_all_records()
        for r in records:
            if str(r.get("bot_id")) == str(bot_token) and str(r.get("ID_الموظف_أو_المدرب")) == str(employee_id):
                return r
        return {}
    except: return {}

def toggle_employee_permission(bot_token, employee_id, col_name):
    """تبديل القيمة بين TRUE و FALSE في خلية محددة"""
    try:
        sheet = ss.worksheet("الهيكل_التنظيمي_والصلاحيات")
        cell_bot = sheet.find(str(bot_token))
        # البحث عن الصف الصحيح (مطابقة التوكن و ID الموظف)
        all_rows = sheet.get_all_values()
        headers = all_rows[0]
        col_index = headers.index(col_name) + 1
        
        for i, row in enumerate(all_rows):
            if row[0] == str(bot_token) and row[1] == str(employee_id):
                current_val = str(row[col_index-1]).upper()
                new_val = "FALSE" if current_val == "TRUE" else "TRUE"
                sheet.update_cell(i + 1, col_index, new_val)
                return new_val
        return "FALSE"
    except Exception as e:
        print(f"Error toggling permission: {e}")
        return "FALSE"
 
 
def check_user_permission(bot_token, user_id, permission_col):
    """
    التحقق مما إذا كان المستخدم لديه صلاحية محددة.
    يعيد True إذا كان المالك أو موظفاً لديه صلاحية TRUE.
    """
    try:
        # 1. جلب إعدادات البوت لمعرفة المالك
        config = get_bot_config(bot_token)
        if str(user_id) in str(config.get("admin_ids", "")).split(','):
            return True  # المالك لديه كافة الصلاحيات دائماً

        # 2. البحث في ورقة الصلاحيات للموظف
        perms = get_employee_permissions(bot_token, user_id)
        if not perms:
            return False
            
        # التحقق من القيمة في العمود المطلوب
        return str(perms.get(permission_col, "FALSE")).upper() == "TRUE"
    except Exception as e:
        print(f"❌ خطأ في فحص الصلاحية: {e}")
        return False

# --------------------------------------------------------------------------
def toggle_scope_id(bot_token, employee_id, scope_column, target_id):
    """
    إضافة أو حذف ID (دورة أو مجموعة) من قائمة الموظف
    scope_column: "الدورات_المسموحة" أو "المجموعات_المسموحة"
    """
    try:
        permission_sheet = ss.worksheet("الهيكل_التنظيمي_والصلاحيات")
        all_data = permission_sheet.get_all_values()
        headers = all_data[0]
        col_index = headers.index(scope_column) + 1
        
        for i, row in enumerate(all_data):
            if str(row[0]) == str(bot_token) and str(row[1]) == str(employee_id):
                current_ids = str(row[col_index-1]).strip().split(",") if row[col_index-1] else []
                # تنظيف الفراغات
                current_ids = [x.strip() for x in current_ids if x.strip()]
                
                if str(target_id) in current_ids:
                    current_ids.remove(str(target_id)) # حذف إذا كان موجود
                else:
                    current_ids.append(str(target_id)) # إضافة إذا لم يكن موجود
                
                new_value = ",".join(current_ids)
                permission_sheet.update_cell(i + 1, col_index, new_value)
                return True
        return False
    except Exception as e:
        print(f"❌ خطأ في تحديث النطاق: {e}")
        return False


def check_access(bot_token, user_id, permission_col, target_id=None, scope_type=None):
    """
    الدالة الشاملة لفحص الصلاحيات والنطاقات (الدورات والمجموعات والأقسام)
    :param permission_col: اسم عمود الصلاحية (مثل: صلاحية_الإذاعة)
    :param target_id: المعرف المراد فحص الوصول إليه (مثل ID الدورة 101)
    :param scope_type: نوع النطاق المقيد (الدورات_المسموحة أو المجموعات_المسموحة)
    """
    try:
        # 1. المالك (Admin) يتخطى كافة القيود دائماً
        config = get_bot_config(bot_token)
        if str(user_id) == str(config.get("admin_ids")):
            return True

        # 2. جلب سجل الموظف من ورقة الصلاحيات
        perms = get_employee_permissions(bot_token, user_id)
        if not perms:
            return False

        # 3. فحص الصلاحية العامة (هل يملك حق فتح القسم أصلاً؟)
        # هذا الجزء يتعامل مع كافة الأعمدة التي أضفتها (كوبونات، خصم، إذاعة...)
        if str(perms.get(permission_col, "FALSE")).upper() != "TRUE":
            return False

        # 4. فحص "النطاق" (التعدد في الدورات أو المجموعات)
        # إذا طلبنا فحص الوصول لدورة معينة (target_id)
        if target_id and scope_type:
            # نحول النص (ID1,ID2,ID3) إلى قائمة برمجية
            allowed_scopes = str(perms.get(scope_type, "")).split(",")
            allowed_scopes = [s.strip() for s in allowed_scopes if s.strip()]
            
            # التحقق هل الـ ID المطلوب موجود ضمن القائمة المسموحة للموظف
            return str(target_id) in allowed_scopes

        # إذا كانت الصلاحية عامة (مثل الإحصائيات) ولا تحتاج فحص ID معين
        return True
    except Exception as e:
        print(f"❌ خطأ في فحص الوصول الشامل: {e}")
        return False

def get_all_personnel_list(bot_token):
    """جلب قائمة موحدة للموظفين والمدربين مع أسمائهم ومعرفاتهم"""
    personnel = []
    try:
        # 1. جلب الموظفين
        emp_sheet = ss.worksheet("إدارة_الموظفين")
        emp_records = emp_sheet.get_all_records()
        for r in emp_records:
            if str(r.get("bot_id")) == str(bot_token):
                personnel.append({
                    "id": str(r.get("ID")),
                    "name": r.get("الاسم_الكامل") or r.get("اسم_الموظف") or "موظف بلا اسم",
                    "type": "موظف"
                })
        
        # 2. جلب المدربين
        coach_sheet = ss.worksheet("المدربين")
        coach_records = coach_sheet.get_all_records()
        for r in coach_records:
            if str(r.get("bot_id")) == str(bot_token):
                personnel.append({
                    "id": str(r.get("ID")),
                    "name": r.get("اسم_المدرب") or "مدرب بلا اسم",
                    "type": "مدرب"
                })
    except Exception as e:
        print(f"❌ خطأ في جلب القائمة الموحدة: {e}")
    return personnel
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# دالة إضافة المجموعات (النسخة المحدثة لـ 15 عموداً)
# --------------------------------------------------------------------------
def add_new_group(bot_token, group_id, name, course_id, days, timing, teacher_id, **kwargs):
    """إضافة مجموعة تعليمية جديدة مع كافة التفاصيل لجدول (إدارة_المجموعات)"""
    try:
        sheet = ss.worksheet("إدارة_المجموعات")
        # ترتيب الأعمدة الـ 15 المحدثة بدقة حسب المخطط
        row = [
            str(bot_token),                            # 1. bot_id
            kwargs.get('branch_id', '001'),            # 2. معرف_الفرع
            str(group_id),                             # 3. معرف_المجموعة
            str(name),                                 # 4. اسم_المجموعة
            str(course_id),                            # 5. معرف_الدورة
            str(days),                                 # 6. أيام_الدراسة
            str(timing),                               # 7. توقيت_الدراسة
            str(teacher_id),                           # 8. ID_المعلم_المسؤول
            "نشطة",                                    # 9. حالة_المجموعة
            kwargs.get('emp_id', 'Admin'),             # 10. معرف_الموظف
            kwargs.get('campaign', 'Direct'),          # 11. معرف_الحملة_التسويقية
            kwargs.get('capacity', '30'),              # 12. سعة_المجموعة
            "0",                                       # 13. عدد_الطلاب_الحالي
            kwargs.get('link', 'لم يحدد بعد'),          # 14. رابط_المجموعة
            get_system_time("date")        # 15. تاريخ_الإنشاء
        ]
        sheet.append_row(row)
        update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ خطأ في إضافة المجموعة: {e}")
        return False

# --------------------------------------------------------------------------
# دالة جلب المجموعات (تم توحيدها على جدول إدارة_المجموعات)
# --------------------------------------------------------------------------
def get_groups_by_course(bot_token, course_id):
    """جلب كافة المجموعات الدراسية المرتبطة بدورة معينة من (إدارة_المجموعات)"""
    try:
        sheet = ss.worksheet("إدارة_المجموعات")
        records = sheet.get_all_records()
        return [r for r in records if str(r.get("bot_id")) == str(bot_token) and str(r.get("معرف_الدورة")) == str(course_id)]
    except Exception as e:
        print(f"❌ خطأ في جلب المجموعات: {e}")
        return []

# --------------------------------------------------------------------------
# دالة الحفظ الفعلي (المستخدمة في المحرك الرئيسي)
# --------------------------------------------------------------------------
def save_group_to_db(bot_token, data):
    """حفظ المجموعة في الشيت بناءً على الأعمدة الـ 15 المحدثة"""
    try:
        sheet = ss.worksheet("إدارة_المجموعات")
        now = get_system_time("full")
        row = [
            str(bot_token),                # 1. bot_id
            "001",                         # 2. معرف_الفرع
            data['group_id'],              # 3. معرف_المجموعة
            data['name'],                  # 4. اسم_المجموعة
            data['course_id'],             # 5. معرف_الدورة
            data['days'],                  # 6. أيام_الدراسة
            data['time'],                  # 7. توقيت_الدراسة
            data['teacher_id'],            # 8. ID_المعلم_المسؤول
            "نشطة",                        # 9. حالة_المجموعة
            "Admin",                       # 10. معرف_الموظف
            "Direct",                      # 11. معرف_الحملة_التسويقية
            "30",                          # 12. سعة_المجموعة
            "0",                           # 13. عدد_الطلاب_الحالي
            "لم يحدد",                     # 14. رابط_المجموعة
            now                            # 15. تاريخ_الإنشاء
        ]
        sheet.append_row(row)
        update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ Error saving group: {e}")
        return False

# --------------------------------------------------------------------------
# دالة الحذف (تم توحيدها وتصحيح الفهارس)
# --------------------------------------------------------------------------
def delete_group_by_id(bot_token, group_id):
    """حذف مجموعة من شيت (إدارة_المجموعات) بناءً على ID المجموعة والتوكن"""
    try:
        sheet = ss.worksheet("إدارة_المجموعات")
        all_rows = sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # الترتيب: bot_id (0), معرف_المجموعة (2)
            if len(row) >= 3 and str(row[0]) == str(bot_token) and str(row[2]) == str(group_id):
                sheet.delete_rows(i + 1)
            update_global_version(bot_token)
            return True
        return False
    except Exception as e:
        print(f"❌ Error deleting group: {e}")
        return False

# --------------------------------------------------------------------------
# دالة التعديل (تصحيح مرجع اللوجر والشيت)
# --------------------------------------------------------------------------
def update_group_field(bot_token, group_id, col_name, new_value):
    """تحديث قيمة محددة في سجل المجموعة داخل (إدارة_المجموعات)"""
    try:
        sheet = ss.worksheet("إدارة_المجموعات")
        all_rows = sheet.get_all_values()
        headers = all_rows[0]
        col_index = headers.index(col_name) + 1
        
        for i, row in enumerate(all_rows):
            if len(row) >= 3 and str(row[0]) == str(bot_token) and str(row[2]) == str(group_id):
                sheet.update_cell(i + 1, col_index, str(new_value))
                # رفع إصدار البوت فوراً لتحديث بيانات المجموعات في الرام
                update_global_version(bot_token)
                return True
        return False
    except Exception as e:
        print(f"❌ Error updating group field: {e}")
        return False


# --------------------------------------------------------------------------
# بنك الأسئلة وإنشاء الاختبارات
def add_question_to_bank(bot_token, data):
    """إضافة سؤال لبنك الأسئلة بناءً على الأعمدة الـ 21 المعتمدة"""
    try:
        sheet = ss.worksheet("بنك_الأسئلة")
        row = [
            str(bot_token),                    # 1. bot_id
            data.get('branch_id', '001'),      # 2. معرف_الفرع
            data.get('quiz_id', 'GENERAL'),    # 3. معرف_الاختبار
            data.get('course_id'),             # 4. معرف_الدورة
            data.get('group_id', 'ALL'),       # 5. معرف_المجموعة
            data.get('q_id'),                  # 6. معرف_السؤال
            data.get('text'),                  # 7. نص_السؤال
            data.get('a'),                     # 8. الخيار_A
            data.get('b'),                     # 9. الخيار_B
            data.get('c'),                     # 10. الخيار_C
            data.get('d'),                     # 11. الخيار_D
            data.get('correct'),               # 12. الإجابة_الصحيحة
            data.get('grade', '1'),            # 13. الدرجة
            data.get('duration', '30'),        # 14. مدة_السؤال
            data.get('level', 'متوسط'),         # 15. مستوى_الصعوبة
            data.get('type', 'اختيار'),         # 16. نوع_السؤال
            data.get('explanation', ''),       # 17. شرح_الإجابة
            data.get('tag', 'عام'),            # 18. الوسم_التصنيفي
            "نشط",                             # 19. حالة_السؤال
            get_system_time("date"),     # 20. تاريخ_الإضافة
            data.get('creator_id')             # 21. معرف_المنشئ
        ]
        sheet.append_row(row)
                # إبلاغ النظام برفع رقم الإصدار لتحديث بنك الأسئلة في الرام فوراً
        update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ خطأ في بنك الأسئلة: {e}")
        return False


# --- [ قسم الكنترول والاختبارات الآلية ] ---

def create_auto_quiz(bot_token, data):
    """إنشاء اختبار جديد مع وضع الحالة الافتراضية FALSE (مخفي عن الموظفين)"""
    try:
        sheet = ss.worksheet("الاختبارات_الآلية")
        # الترتيب بناءً على الـ 16 عموداً التي حددتها
        row = [
            str(bot_token),                    # 1
            data.get('branch_id', '001'),      # 2
            data.get('quiz_id'),               # 3
            data.get('course_id'),             # 4
            data.get('target_groups', 'ALL'),  # 5. المجموعات_المستهدفة
            data.get('q_list'),                # 6
            data.get('q_count'),               # 7
            data.get('pass_score'),            # 8
            data.get('duration'),              # 9
            data.get('timer_type'),            # 10
            data.get('random', 'TRUE'),        # 11
            data.get('attempts', 1),           # 12
            data.get('show_res', 'TRUE'),      # 13
            "FALSE",                           # 14. حالة_الاختبار (تبدأ مخفية)
            data.get('coach_id'),              # 15
            get_system_time("date")         # 16
        ]
        sheet.append_row(row)
                # إبلاغ النظام برفع رقم الإصدار لتحديث بنك الأسئلة في الرام فوراً
        update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ خطأ إنشاء اختبار: {e}")
        return False

def toggle_quiz_visibility(bot_token, quiz_id):
    """تبديل حالة الاختبار بين TRUE و FALSE (العمود 14)"""
    try:
        sheet = ss.worksheet("الاختبارات_الآلية")
        all_rows = sheet.get_all_values()
        for i, row in enumerate(all_rows):
            if row[0] == str(bot_token) and row[2] == str(quiz_id):
                # العمود 14 (Index 13)
                current_val = str(row[13]).upper()
                new_val = "FALSE" if current_val == "TRUE" else "TRUE"
                sheet.update_cell(i + 1, 14, new_val)
                update_global_version(bot_token)
                return new_val
        return "FALSE"
    except:
        return "FALSE"

# --------------------------------------------------------------------------
# --- [ قسم التأسيس الصامت للصلاحيات ] ---
def ensure_permission_row_exists(bot_token, person_id):
    """التأكد من وجود سجل صلاحيات للموظف/المدرب، وإنشاؤه صامتاً إذا لم يوجد"""
    try:
        sheet = ss.worksheet("الهيكل_التنظيمي_والصلاحيات")
        existing = get_employee_permissions(bot_token, person_id)
        
        if not existing:
            # إنشاء صف بـ 14 عموداً: bot_id, ID, 9 صلاحيات (FALSE), نطاقات (فارغ), تحديث
            new_row = [str(bot_token), str(person_id)] + ["FALSE"] * 9 + ["", "", "FALSE"]
            sheet.append_row(new_row)
            return True

    except Exception as e:
        print(f"❌ خطأ في تأسيس الصلاحية: {e}")
        return False



# --------------------------------------------------------------------------
# جلب الأسئلة 
def get_all_questions_from_bank(bot_token):
    """جلب كافة الأسئلة المسجلة لهذا البوت من بنك الأسئلة"""
    try:
        # ضمان تحديث البيانات قبل القراءة (المزامنة الصامتة)
        smart_sync_check(bot_token)
        records = get_bot_data_from_cache(bot_token, "بنك_الأسئلة")
        
        return records

    except Exception as e:
        print(f"❌ خطأ جلب الأسئلة: {e}")
        return []
#حذف الأسئلة 
def delete_question_from_bank(bot_token, q_id):
    """حذف سؤال محدد من البنك بناءً على معرفه"""
    try:
        sheet = ss.worksheet("بنك_الأسئلة")
        all_rows = sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # العمود 1 توكن، العمود 6 معرف السؤال (Index 5)
            if row[0] == str(bot_token) and str(row[5]) == str(q_id):
                sheet.delete_rows(i + 1)
                                # رفع إصدار البوت فوراً لتحديث الرام وحذف السؤال من الكاش
                update_global_version(bot_token)
                return True
        return False
    except Exception as e:
        print(f"❌ خطأ حذف سؤال: {e}")
        return False

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# --- [ 1. دوال مسار الموظف - بناءً على الصلاحيات ] ---
def get_employee_allowed_courses(bot_token, employee_id):
    """جلب قائمة الدورات المسموحة للموظف من ورقة الصلاحيات"""
    try:
        # ضمان مزامنة البيانات قبل التحقق
        smart_sync_check(bot_token)
        
        perms = get_employee_permissions(bot_token, employee_id)
        if not perms: return []
        
        # استخراج المعرفات (تحويل النص CRS1,CRS2 إلى قائمة برمجية)
        allowed_ids = str(perms.get("الدورات_المسموحة", "")).split(",")
        allowed_ids = [i.strip() for i in allowed_ids if i.strip()]
        
        # جلب البيانات من الرام فوراً (0 استهلاك API)
        all_courses = get_bot_data_from_cache(bot_token, "الدورات_التدريبية")
        
        return [
            {"id": c.get("معرف_الدورة"), "name": c.get("اسم_الدورة")}
            for c in all_courses 
            if str(c.get("معرف_الدورة")) in allowed_ids
        ]

    except Exception as e:
        print(f"❌ Error fetching employee courses: {e}")
        return []

def get_employee_allowed_groups(bot_token, employee_id, course_id):
    """جلب المجموعات التابعة لدورة محددة والمسموحة لهذا الموظف"""
    try:
        # ضمان المزامنة الصامتة
        smart_sync_check(bot_token)
        
        perms = get_employee_permissions(bot_token, employee_id)
        if not perms: return []
        
        allowed_group_ids = str(perms.get("المجموعات_المسموحة", "")).split(",")
        allowed_group_ids = [i.strip() for i in allowed_group_ids if i.strip()]
        
        # جلب المجموعات من الرام بدلاً من ورقة إدارة_المجموعات مباشرة
        all_groups = get_bot_data_from_cache(bot_token, "إدارة_المجموعات")
        
        return [
            {"id": g.get("معرف_المجموعة"), "name": g.get("اسم_المجموعة")}
            for g in all_groups
            if str(g.get("معرف_الدورة")) == str(course_id)
            and str(g.get("معرف_المجموعة")) in allowed_group_ids
        ]

    except: return []

# --- [ 2. دوال مسار الطالب - بناءً على قاعدة البيانات ] ---

def get_student_enrollment_data(bot_token, telegram_id):
    """جلب بيانات تسجيل الطالب (الدورة والمجموعة) من قاعدة بيانات الطلاب"""
    try:
        # ضمان مزامنة البيانات قبل القراءة (المزامنة الصامتة)
        smart_sync_check(bot_token)
        
        # جلب سجلات الطلاب من الرام فوراً (0 استهلاك API)
        # الدالة تعيد تلقائياً السجلات المفلترة لهذا الـ bot_token
        records = get_bot_data_from_cache(bot_token, "قاعدة_بيانات_الطلاب")
        
        for r in records:
            # البحث عن الطالب باستخدام ID التليجرام داخل سجلات البوت الحالي
            if str(r.get("ID_المستخدم_تيليجرام")) == str(telegram_id):
                return {
                    "student_name": r.get("الاسم_بالعربي"),
                    "course_id": r.get("معرف_الدورة"),
                    "course_name": r.get("اسم_الدورة"),
                    "group_id": r.get("معرف_المجموعة"),
                    "group_name": r.get("اسم_المجموعة")
                }
        return None
    except: return None

# --------------------------------------------------------------------------
# --- [ 3. محرك جلب الحصص الفعلي ] ---
def get_lectures_by_group(bot_token, group_id):
    """جلب جدول الحصص الفعلي من ورقة جدول_المحاضرات بناءً على المجموعة"""
    try:
        # ضمان تحديث البيانات في الرام قبل القراءة (المزامنة الصامتة)
        smart_sync_check(bot_token)
        
        # جلب سجلات جدول المحاضرات من الرام فوراً (0 استهلاك API)
        # الدالة تعيد فقط السجلات الخاصة بـ bot_token هذا
        records = get_bot_data_from_cache(bot_token, "جدول_المحاضرات")
        
        # التصفية حسب المجموعة [بناءً على طلبك في الكود الأصلي]
        return [
            r for r in records 
            if str(r.get("معرف_المجموعة")) == str(group_id)
        ]

    except: return []

# --------------------------------------------------------------------------
#اكود الخصم 
def get_active_discount_codes(bot_token):
    """جلب أكواد الخصم النشطة مع أسماء الدورات المربوطة بها"""
    try:
        # ضمان تحديث البيانات قبل القراءة
        smart_sync_check(bot_token)
        
        # سحب سجلات الأكواد والدورات من الرام فوراً (0 استهلاك API)
        records = get_bot_data_from_cache(bot_token, "أكواد_الخصم")
        all_courses = get_bot_data_from_cache(bot_token, "الدورات_التدريبية")
        
        active_codes = []
        
        # بناء خريطة الدورات من البيانات المخزنة في الرام
        courses = {c.get("معرف_الدورة"): c.get("اسم_الدورة") for c in all_courses}
        
        for r in records:
            # التحقق من الحالة من الرام (عمود bot_id مفلتر تلقائياً داخل الدالة)
            if str(r.get("الحالة")) == "نشط":
                course_name = courses.get(str(r.get("معرف_الدورة")), "كافة الدورات")
                active_codes.append({
                    "code": r.get("معرف_الخصم"),
                    "value": r.get("قيمة_الخصم"),
                    "course": course_name,
                    "expiry": r.get("تاريخ_الانتهاء")
                })
        return active_codes

    except: return []

#التحقق من وجود كود الخصم 
def check_course_has_discount(bot_token, course_id):
    """التحقق من وجود كود سابق للدورة"""
    try:
        smart_sync_check(bot_token)
        # جلب البيانات المفلترة لهذا البوت من الرام
        records = get_bot_data_from_cache(bot_token, "أكواد_الخصم")
        
        for r in records:
            # المقارنة تتم على مستوى معرف الدورة داخل سجلات البوت
            if str(r.get("معرف_الدورة")) == str(course_id):
                return r.get("معرف_الخصم")
        return None
    except: return None


#حفظ كود الخصم 
# التعديل الذهبي والمطابق لهيكل ورقتك (15 عموداً)
def save_discount_code_full(bot_token, data):
    """حفظ البيانات بمطابقة تامة لهيكل ورقة 'أكواد_الخصم' المكونة من 15 عموداً"""
    try:
        sheet = ss.worksheet("أكواد_الخصم")
        now_date = get_system_time("date") # تاريخ اليوم
        
        # الترتيب الذي تطلبه ورقتك حرفياً:
        row = [
            str(bot_token),             # 1. bot_id
            "001",                      # 2. معرف_الفرع
            data['final_code'],         # 3. معرف_الخصم (الكود)
            "نسبة مئوية",               # 4. نوع_الخصم
            data['desc'],               # 5. الوصف (مثل: خصم عيد)
            data['value'],              # 6. قيمة_الخصم (الرقم)
            data['max_use'],            # 7. الحد_الأقصى_للاستخدام
            "0",                        # 8. عدد_الاستخدامات (يبدأ بـ 0)
            now_date,                   # 9. تاريخ_البداية
            data['expiry'],             # 10. تاريخ_الانتهاء
            "نشط",                      # 11. الحالة
            data['course_id'],          # 12. معرف_الدورة
            "المالك",                   # 13. اسم_الموظف
            "Direct",                   # 14. معرف_الحملة_التسويقية
            "إضافة آلية"                # 15. ملاحظات
        ]
        
        sheet.append_row(row)
        # رفع إصدار البوت لتحديث الرام فوراً ليعلم النظام بالكود الجديد
        update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ خطأ في مطابقة الأعمدة: {e}")
        return False

# --------------------------------------------------------------------------
 # قسم روابط الاحالة
def get_bot_setting(bot_token, key, default=0):
    """جلب قيمة إعداد محدد من الرام فوراً (0 استهلاك API)"""
    try:
        # 1. المزامنة الصامتة (تتصل بجوجل فقط مرة كل 15 دقيقة)
        smart_sync_check(bot_token)
        
        # 2. جلب كافة إعدادات المصنع المخزنة في الرام (RAM)
        all_settings = get_bot_data_from_cache(bot_token, "الإعدادات")
        
        # 3. البحث داخل القائمة المخزنة محلياً عن المفتاح المطلوب
        # ملاحظة: get_bot_data_from_cache تعيد فقط إعدادات البوت الحالي
        for r in all_settings:
            if str(r.get('المفتاح_البرمجي')) == key:
                return r.get('القيمة')
        
        return default
    except Exception as e:
        print(f"❌ خطأ في جلب الإعداد {key} من الكاش: {e}")
        return default


 
def link_user_to_inviter(bot_token, student_id, inviter_id):
    """ربط الطالب بالداعي ومنح النقاط ديناميكياً مع الهروب من الـ API [نظام الكاش]"""
    try:
        # 0. المزامنة الذكية قبل البدء لضمان دقة البيانات
        smart_sync_check(bot_token)
        
        # 1. جلب قيمة النقاط من الرام (بدلاً من ورقة الإعدادات مباشرة)
        settings_records = get_bot_data_from_cache(bot_token, "الإعدادات")
        points_to_add = 10  # القيمة الافتراضية
        
        for reg in settings_records:
            # الفلترة تتم آلياً داخل الكاش، نبحث فقط عن المفتاح
            if reg.get('المفتاح_البرمجي') == 'ref_points_join':
                points_to_add = float(reg.get('القيمة') or 10)
                break

        # 2. جلب بيانات المستخدمين من الرام لتحديد الصفوف (توفير عمليات find)
        users_records = get_bot_data_from_cache(bot_token, "المستخدمين")
        sheet_users = ss.worksheet("المستخدمين")
        
        # البحث عن الداعي (Inviter) والطالب (Student) في الرام
        inviter_data = next((r for r in users_records if str(r.get("ID_المستخدم")) == str(inviter_id)), None)
        
        # تنفيذ العمليات في جوجل شيت بناءً على البيانات المستخرجة
        # ملاحظة: سنستخدم find هنا فقط للكتابة (Write) لضمان دقة رقم الصف
        
        # أ) إضافة النقاط للداعي
        inviter_cell = sheet_users.find(str(inviter_id), in_column=1)
        if inviter_cell:
            # الرصيد الحالي نجلبة من الرام (user_data) لتوفير طلب API
            current_balance = float(inviter_data.get("النقاط") or 0) if inviter_data else 0
            sheet_users.update_cell(inviter_cell.row, 11, current_balance + points_to_add)
        
        # ب) تسجيل معرف الإحالة للطالب الجديد
        student_cell = sheet_users.find(str(student_id), in_column=1)
        if student_cell:
            sheet_users.update_cell(student_cell.row, 10, str(inviter_id))
            
        # 3. رفع إصدار البوت فوراً لتحديث الرام في العمليات القادمة
        update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ خطأ في نظام الإحالة الديناميكي: {e}")
        return False


# --------------------------------------------------------------------------
# جلب الإحصائيات 
def get_user_referral_stats(bot_token, user_id):
    """حساب عدد المدعوين والرصيد المكتسب من ورقة المستخدمين"""
    try:
        # إزاحة 8 مسافات (داخل try)
        smart_sync_check(bot_token)
        all_users = get_bot_data_from_cache(bot_token, "المستخدمين")
        count = sum(1 for u in all_users if str(u.get('معرف إحالة', '')).strip() == str(user_id))
        user_data = next((u for u in all_users if str(u.get('ID المستخدم')) == str(user_id)), {})
        return {"count": count, "balance": user_data.get('رصيد', 0)}

    except Exception as e:

        print(f"❌ خطأ في جلب إحصائيات الإحالة: {e}")
        return {"count": 0, "balance": 0}
# --------------------------------------------------------------------------
# استبدال النقاط 
def redeem_points_for_course(bot_token, user_id, course_price):
    """التحقق من الرصيد وخصم النقاط لفتح دورة [بأقصى سرعة وأقل استهلاك API]"""
    try:
        # 1. ضمان مزامنة البيانات قبل التحقق من الرصيد
        smart_sync_check(bot_token)
        
        # 2. جلب بيانات المستخدمين من الرام بدلاً من البحث المباشر في الشيت
        users_records = get_bot_data_from_cache(bot_token, "المستخدمين")
        
        # البحث عن سجل المستخدم (العمود 1 هو ID المستخدم)
        user_data = next((r for r in users_records if str(r.get("ID_المستخدم")) == str(user_id)), None)
        
        if user_data:
            # افتراض أن العمود 11 هو 'النقاط' أو 'الرصيد' حسب ترتيب ورقة المستخدمين
            current_balance = float(user_data.get("النقاط") or 0)
            
            if current_balance >= float(course_price):
                # 3. جلب الورقة للكتابة فقط (توفير API القراءة)
                sheet_users = ss.worksheet("المستخدمين")
                
                # البحث عن الصف لتحديثه
                user_cell = sheet_users.find(str(user_id), in_column=1)
                if user_cell:
                    new_balance = current_balance - float(course_price)
                    
                    # تحديث القيمة في جوجل شيت (العمود 11)
                    sheet_users.update_cell(user_cell.row, 11, new_balance)
                    
                    # 4. رفع إصدار البوت فوراً لتحديث الرام في الطلب القادم
                    update_global_version(bot_token)
                    return True, new_balance
                    
        return False, 0
    except Exception as e:
        print(f"❌ خطأ في عملية استبدال النقاط: {e}")
        return False, 0



# --------------------------------------------------------------------------
# جلب بيانات المكتبة 
def get_filtered_library_content(bot_token, user_id, course_id):
    """جلب المحتوى المخصص للطالب بناءً على حالة الدفع والدورة"""
    try:
        # ضمان تحديث البيانات في الرام قبل البدء (نبضة الـ 15 دقيقة)
        smart_sync_check(bot_token)
        
        # 1. جلب بيانات الطلاب من الرام (بدلاً من الاتصال المباشر بجوجل)
        student_records = get_bot_data_from_cache(bot_token, "قاعدة_بيانات_الطلاب")
        
        # البحث عن سجل الطالب المطابق للتوكن والآيدي
        student_data = next((r for r in student_records if str(r.get("ID_المستخدم_تيليجرام")) == str(user_id)), None)
        
        # منطق التحقق من الدفع (لم يتغير لضمان الوظيفة)
        is_paid = False
        if student_data and str(student_data.get("الحالة")).strip() in ["مدفوع", "دافع", "مقبول"]:
            is_paid = True

        # 2. جلب محتوى المكتبة كامل المصنع من الرام وتصفيته
        all_content = get_bot_data_from_cache(bot_token, "المكتبة")
        
        filtered_content = []
        for item in all_content:
            # فلترة المحتوى بناءً على الدورة المحددة (التي مررها البوت)
            if str(item.get("الدورة")) == str(course_id):
                status = str(item.get("الحالة")).strip()
                
                # السماح بالوصول بناءً على القواعد المذكورة في التعليمات
                if status == "مجاني" or (status == "مدفوع" and is_paid):
                    filtered_content.append(item)
        
        return filtered_content

    except Exception as e:
        print(f"❌ خطأ في تصفية محتوى المكتبة: {e}")
        return []
 
# --------------------------------------------------------------------------
# فحص حالة الطالب 
def get_filtered_library_content(bot_token, user_id, course_id):
    """جلب المحتوى المخصص للطالب بناءً على حالة الدفع والدورة"""
    try:
        # 1. التحقق من حالة الطالب في قاعدة بيانات الطلاب
        student_sheet = ss.worksheet("قاعدة_بيانات_الطلاب")
        student_records = student_sheet.get_all_records()
        
        # البحث عن سجل الطالب المطابق للتوكن والآيدي
        student_data = next((r for r in student_records if str(r.get("ID_المستخدم_تيليجرام")) == str(user_id) 
                             and str(r.get("bot_id")) == str(bot_token)), None)
        
        # نعتبره "دافع" فقط إذا كانت حالته (مدفوع) أو (دافع)
        is_paid = False
        if student_data and str(student_data.get("الحالة")).strip() in ["مدفوع", "دافع"]:
            is_paid = True

        # 2. جلب وتصفية محتوى المكتبة
        library_sheet = ss.worksheet("المكتبة")
        all_content = library_sheet.get_all_records()
        
        filtered_content = []
        for item in all_content:
            # التحقق من أن الملف يخص هذا البوت وهذه الدورة تحديداً
            if str(item.get("bot_id")) == str(bot_token) and str(item.get("الدورة")) == str(course_id):
                file_status = str(item.get("الحالة")).strip() # حالة الملف (مجاني/مدفوع)
                
                # السماح بالوصول في حالتين: الملف مجاني للكل، أو الملف مدفوع والطالب دافع
                if file_status == "مجاني" or (file_status == "مدفوع" and is_paid):
                    filtered_content.append(item)
        
        return filtered_content
    except Exception as e:
        print(f"❌ خطأ في تصفية المكتبة: {e}")
        return []

# --------------------------------------------------------------------------
# اشعار التفعيل 
def get_newly_activated_students(bot_token):
    """جلب الطلاب الذين تم تفعيلهم حديثاً ولم يرسل لهم إشعار"""
    try:
        sheet = ss.worksheet("قاعدة_بيانات_الطلاب")
        records = sheet.get_all_records()
        activated = []
        
        for i, r in enumerate(records, start=2): # يبدأ من 2 لتجاوز العنوان
            # الشرط: الحالة مدفوع + لم يتم إرسال إشعار (سجل التعديل فارغ)
            if (str(r.get("bot_id")) == str(bot_token) and 
                str(r.get("الحالة")) in ["مدفوع", "دافع"] and 
                not str(r.get("سجل_التعديل"))):
                
                activated.append({
                    "row": i,
                    "user_id": r.get("ID_المستخدم_تيليجرام"),
                    "name": r.get("اسم_المستخدم"),
                    "course": r.get("الدورة")
                })
        return activated
    except: return []
    
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# --- [ نظام الطلاب - محرك الواجبات ] ---

def get_student_assignments(bot_token, course_id, group_id):
    """جلب الواجبات المفلترة والمسموحة للطالب (مرئي_للطالب == TRUE)"""
    try:
        smart_sync_check(bot_token)
        records = get_bot_data_from_cache(bot_token, "الواجبات")
        # الفلترة: bot_id + الدورة + المجموعة + شرط الرؤية [بند 1، 5 في الوثيقة]
        return [r for r in records if str(r.get("bot_id")) == str(bot_token) 
                and str(r.get("معرف_الدورة")) == str(course_id) 
                and str(group_id) in str(r.get("معرف_المجموعة", ""))
                and str(r.get("مرئي_للطالب", "FALSE")).upper() == "TRUE"]

    except: return []

def check_student_submission(bot_token, student_id, hw_id):
    """فحص محرك الحالات: هل يوجد تسليم سابق لهذا الواجب؟ [بند 2 في الوثيقة]"""
    try:
        smart_sync_check(bot_token)
        records = get_bot_data_from_cache(bot_token, "تنفيذ_الواجبات_من_الطلاب")
        # البحث عن آخر تسليم للطالب لهذا الواجب
        submission = next((r for r in records if str(r.get("bot_id")) == str(bot_token) 
                           and str(r.get("معرف_الطالب")) == str(student_id) 
                           and str(r.get("معرف_الواجب")) == str(hw_id)), None)
        return submission

    except: return None

def record_student_submission(bot_token, data):
    """تدوين البيانات في ورقة تنفيذ_الواجبات_من_الطلاب [ثالثاً في الوثيقة]"""
    try:
        sheet = ss.worksheet("تنفيذ_الواجبات_من_الطلاب")
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # حساب وقت الإكمال بالدقائق (تاريخ_التسليم - تاريخ_البداية)
        start_time = datetime.strptime(data['start_time'], "%Y-%m-%d %H:%M:%S")
        duration = round((now - start_time).total_seconds() / 60, 2)

        # الالتزام الحرفي بأسماء الأعمدة الـ 18 المذكورة في الوثيقة
        row = [
            str(bot_token),                # bot_id
            data.get('branch_id', '001 '), # معرف_الفرع (مع المسافة حسب طلبك)
            f"EXEC{str(uuid.uuid4().int)[:5]}", # معرف_التنفيذ
            data['hw_id'],                 # معرف_الواجب
            data['student_id'],            # معرف_الطالب
            data['group_id'],              # معرف_المجموعة
            data['course_id'],             # معرف_الدورة
            data['start_time'],            # تاريخ_البداية
            now_str,                       # تاريخ_التسليم
            "قيد المراجعة",                # حالة_التنفيذ
            "0",                           # النقاط_المكتسبة
            "",                            # ملاحظات_المعلم
            data['file_link'],             # مرفقات_الطالب
            "1",                           # عدد_محاولات_التسليم
            str(duration),                 # وقت_الإكمال (بالدقائق)
            "",                            # تقييم_التسليم
            now_str,                       # آخر_تحديث
            "TRUE"                         # مرئي_للطالب
        ]
        sheet.append_row(row)
        update_global_version(bot_token)
        return True
    except Exception as e:
        print(f"❌ Error Recording Submission: {e}")
        return False

# --------------------------------------------------------------------------
# دالة فحص الصلاحيات والقيود للبوتات 
def check_bot_limits(bot_token, feature_name):
    """
    المحرك المركزي لفحص القيود (الدورات، الأقسام، الطلاب، والذكاء الاصطناعي)
    feature_name: "course", "section", "student", "ai", "excel"
    """
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    
    try:
        # 1. جلب بيانات البوت من ورقة "البوتات_المصنوعة"
        cell = bots_sheet.find(str(bot_token).strip())
        if not cell: return False, "البوت غير مسجل في النظام."
        
        bot_data = bots_sheet.row_values(cell.row)
        # توضيح الفهارس بناءً على الهيكل الـ 44 عموداً
        plan = bot_data[14]           # العمود 15: plan
        created_at_str = bot_data[7]  # العمود 8: تاريخ الإنشاء
        is_active = bot_data[16]      # العمود 17: is_active
        
        # فحص حالة النشاط العامة
        if str(is_active).upper() != "TRUE":
            return False, "عذراً، هذا البوت متوقف حالياً من قبل الإدارة."

        # 2. منطق الذكاء الاصطناعي (الفترة التجريبية 30 يوم)
        if feature_name == "ai":
            from datetime import datetime
            # تحويل تاريخ الإنشاء لمقارنته
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            days_passed = (datetime.now() - created_at).days
            
            ai_feature_status = str(bot_data[24]).upper() # العمود 25: ميزة_الذكاء_الاصطناعي
            
            # إذا مر أكثر من 30 يوم والباقة مجانية، يتم القفل آلياً
            if days_passed > 30 and str(plan).lower() == "free":
                # تحديث الشيت آلياً إلى FALSE عند المحاولة بعد 30 يوم
                bots_sheet.update_cell(cell.row, 25, "FALSE")
                return False, "انتهت الفترة التجريبية لمساعد الذكاء الاصطناعي (30 يوم). يرجى الترقية للاستمرار."
            
            return (ai_feature_status == "TRUE"), "ميزة الذكاء الاصطناعي غير مفعلة في باقتك."

        # 3. منطق حدود الأقسام والدورات
        if feature_name == "section":
            max_sections = int(bot_data[23]) # العمود 24: الحد_الأقصى_للاقسام
            from sheets import departments_sheet
            all_deps = departments_sheet.get_all_records()
            current_count = sum(1 for d in all_deps if str(d.get('bot_id')) == str(bot_token))
            
            if current_count >= max_sections:
                return False, f"لقد وصلت للحد الأقصى للأقسام ({max_sections}). ارتقِ بباقتك لفتح المزيد."

        if feature_name == "course":
            max_courses = int(bot_data[22]) # العمود 23: الحد_الأقصى_للدوات
            from sheets import courses_sheet
            all_crs = courses_sheet.get_all_records()
            current_count = sum(1 for c in all_crs if str(c.get('bot_id')) == str(bot_token))
            
            if current_count >= max_courses:
                return False, f"لقد وصلت للحد الأقصى للدورات ({max_courses}). ارتقِ بباقتك لإضافة دورات جديدة."

        # 4. منطق ميزة الإكسل
        if feature_name == "excel":
            excel_status = str(bot_data[25]).upper() # العمود 26: ميزة_رفع_وتصدير_البيانات_اكسل
            if excel_status != "TRUE":
                return False, "ميزة استيراد وتصدير بيانات الإكسل متاحة فقط في الباقة الاحترافية."

        return True, "Success"

    except Exception as e:
        print(f"❌ خطأ في محرك القيود: {e}")
        return False, "حدث خطأ أثناء التحقق من الصلاحيات."


# دالة التخزين المؤقت 
def sync_bot_limits(context, bot_token):
    """جلب بيانات البوت من الشيت وتخزينها في ذاكرة البوت المؤقتة"""
    global bots_sheet
    try:
        cell = bots_sheet.find(str(bot_token).strip())
        if cell:
            # جلب الصف بالكامل (44 عموداً)
            row = bots_sheet.row_values(cell.row)
            
            # تخزين البيانات في قاموس منظم داخل الذاكرة
            context.bot_data['limits'] = {
                'plan': row[14],               # plan
                'created_at': row[7],          # تاريخ الإنشاء
                'max_students': int(row[21]),  # الحد_الأقصى_للطلاب
                'max_courses': int(row[22]),   # الحد_الأقصى_للدورات
                'max_sections': int(row[23]),  # الحد_الأقصى_للاقسام
                'ai_active': str(row[24]).upper() == "TRUE",
                'excel_active': str(row[25]).upper() == "TRUE",
                'last_sync': get_system_time("full")
            }
            return True
    except Exception as e:
        print(f"❌ فشل مزامنة الذاكرة: {e}")
    return False
 
# --------------------------------------------------------------------------
# --- 1. جلب قائمة الفروع ---
def get_all_branches(bot_token):
    """يعيد قائمة بالفروع: [{'id': 'معرف_الفرع', 'name': 'اسم_الفرع'}]"""
    branches = []
    try:
        smart_sync_check(bot_token)
        records = get_bot_data_from_cache(bot_token, "إدارة_الفروع")
        for r in records:
            if str(r.get("bot_id")) == str(bot_token):
                branches.append({
                    "id": str(r.get("معرف_الفرع")),
                    "name": r.get("اسم_الفرع") or "فرع بلا اسم"
                })

    except Exception as e:
        print(f"❌ خطأ في جلب الفروع: {e}")
    return branches

# --- 2. جلب قائمة الموظفين ---
def get_all_personnel(bot_token):
    """يعيد قائمة بالموظفين: [{'id': 'ID', 'name': 'الاسم_الكامل'}]"""
    staff = []
    try:
        smart_sync_check(bot_token)
        records = get_bot_data_from_cache(bot_token, "إدارة_الموظفين")
        for r in records:
            if str(r.get("bot_id")) == str(bot_token):
                staff.append({
                    "id": str(r.get("ID")),
                    "name": r.get("الاسم_الكامل") or r.get("اسم_الموظف") or "موظف مجهول"
                })

    except Exception as e:
        print(f"❌ خطأ في جلب الموظفين: {e}")
    return staff

# --- 3. جلب قائمة المدربين ---
def get_all_coaches_list(bot_token):
    """يعيد قائمة بالمدربين: [{'id': 'ID', 'name': 'اسم_المدرب'}]"""
    coaches = []
    try:
        smart_sync_check(bot_token)
        records = get_bot_data_from_cache(bot_token, "المدربين")
        for r in records:
            if str(r.get("bot_id")) == str(bot_token):
                coaches.append({
                    "id": str(r.get("ID")),
                    "name": r.get("اسم_المدرب") or "مدرب مجهول"
                })

    except Exception as e:
        print(f"❌ خطأ في جلب المدربين: {e}")
    return coaches

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------


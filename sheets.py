import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# --- إعداد المتغيرات العالمية للوصول الشامل والآمن عبر الملف ---
client = None
ss = None
users_sheet = None
bots_sheet = None
content_sheet = None
logs_sheet = None
# معرف ملف Google Sheet الخاص بمصنع البوتات
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

def get_config():
    """جلب وتصحيح مفاتيح الوصول من متغيرات البيئة لضمان توافق RSA و JWT الرقمي"""
    raw_key = os.getenv("G_PRIVATE_KEY")
    if not raw_key:
        print("❌ خطأ حرج: G_PRIVATE_KEY مفقود من إعدادات السيرفر!")
        return None
    
    try:
        # تصحيح شامل للمفتاح الخاص: معالجة فواصل الأسطر البرمجية (\n)
        # وإزالة أي شوائب ناتجة عن عملية النسخ واللصق من المتصفح
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

def connect_to_google():
    """تأسيس الاتصال بجوجل وتعيين أوراق العمل مع نظام فحص استباقي للصلاحيات"""
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    config = get_config()
    if not config:
        return False

    try:
        # تحديد نطاقات الوصول المطلوبة (جداول البيانات ومحرك الأقراص) لضمان القدرة على التعديل
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        
        # محاولة فتح ملف قاعدة البيانات عبر المعرف الفريد
        ss = client.open_by_key(SPREADSHEET_ID)
        
        # جلب أسماء الأوراق الحالية للتأكد من مطابقتها برمجياً
        sheets_names = [s.title for s in ss.worksheets()]
        print(f"📋 الأوراق المكتشفة في الملف هي: {sheets_names}")

        # ربط الأوراق بالمتغيرات العالمية (يجب أن تكون الأسماء في الشيت مطابقة تماماً)
        users_sheet = ss.worksheet("المستخدمين")
        bots_sheet = ss.worksheet("البوتات_المصنوعة")
        content_sheet = ss.worksheet("إعدادات_المحتوى")
        logs_sheet = ss.worksheet("السجلات")
        
        print("✅ تم الاتصال بنجاح: كافة الصلاحيات (Sheets & Drive) مفعلة وقاعدة البيانات جاهزة.")
        return True
    except gspread.exceptions.WorksheetNotFound as e:
        print(f"❌ خطأ: لم يتم العثور على ورقة بهذا الاسم (يرجى فحص أسماء Tabs في الشيت): {e}")
    except Exception as e:
        print(f"❌ فشل الاتصال النهائي: {str(e)}")
    return False

# تنفيذ محاولة الاتصال الفورية عند إقلاع ملف sheets.py
connect_to_google()

# --- كافة الدوال الوظيفية المطلوبة لإدارة بيانات المصنع بالكامل ---

def save_user(user_id, username):
    """حفظ بيانات المستخدم الجديد مع نظام الكتابة القسرية في السطر الثاني لضمان الرؤية"""
    global users_sheet
    print(f"🚀 بدء محاولة تسجيل المستخدم: {user_id} (@{username})")
    
    if users_sheet is None:
        if not connect_to_google():
            print("❌ فشل التسجيل: تعذر الوصول إلى جوجل شيت حالياً.")
            return False

    try:
        # محاولة سريعة لفحص وجود المستخدم مسبقاً لتجنب التكرار
        try:
            exists = users_sheet.find(str(user_id))
            if exists:
                print(f"ℹ️ المستخدم {user_id} مسجل بالفعل في الصف رقم {exists.row}")
                return False
        except:
            pass # في حال عدم العثور، ننتقل للكتابة

        # إعداد بيانات المستخدم
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(user_id), str(username), now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        
        # استخدام insert_row في السطر 2 لضمان الرؤية الفورية وتجنب الصفوف العالقة
        users_sheet.insert_row(row, 2)
        print(f"✅ تم تسجيل المستخدم {user_id} في السطر الثاني بنجاح تام!")
        return True
    except Exception as e:
        print(f"❌ خطأ فني أثناء الكتابة في الشيت: {e}")
        return False

def save_bot(owner_id, bot_type, bot_name, bot_token):
    """توثيق البوت المَصنوع، حفظ التوكن، وإنشاء ملف إعداداته فوراً في ورقة إعدادات المحتوى"""
    global bots_sheet, content_sheet
    if bots_sheet is None or content_sheet is None: 
        if not connect_to_google(): return False
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. تسجيل البوت في ورقة "البوتات_المصنوعة" (تحديث الخانات بالتوكن والبيانات)
        # الترتيب حسب ملف التأسيس: ID المالك، نوع البوت، اسم البوت، التوكن، حالة التشغيل، ...الخ
        bot_row = [
            str(owner_id), bot_type, bot_name, bot_token, "نشط", 
            "", "", now, "", 0, 0, "جيد", "", "polling", 
            "free", "", "true", ""
        ]
        bots_sheet.append_row(bot_row)

        # 2. إنشاء إعدادات افتراضية فورية في ورقة "إعدادات_المحتوى" لربطها بالبوت الجديد
        # الترتيب حسب ملف التأسيس: ID البوت (التوكن)، الرسالة الترحيبية، القوانين، ...الخ
        content_row = [
            bot_token, "أهلاً بك في بوتك الجديد! 🤖", "لا توجد قوانين حالياً.", 
            "عذراً، البوت متوقف مؤقتاً.", "false", "false", "true", 
            "[]", "[]", str(owner_id), "ar", "default", "0", "true", "[]"
        ]
        content_sheet.append_row(content_row)
        
        print(f"✅ تم تصنيع البوت ({bot_name}) وإنشاء ملفات التكوين بنجاح للمالك {owner_id}")
        return True
    except Exception as e:
        print(f"❌ خطأ حرج في عملية تصنيع وحفظ البوت: {e}")
        return False

def update_content_setting(bot_id, column_name, new_value):
    """تحديث ديناميكي لأي إعداد في ورقة إعدادات المحتوى (ترحيب، قوانين، موديولات)"""
    global content_sheet
    if content_sheet is None: 
        if not connect_to_google(): return False
    try:
        # البحث عن صف البوت المطلوب تحديثه
        cell = content_sheet.find(str(bot_id))
        if cell:
            # جلب رؤوس الأعمدة لمعرفة رقم العمود المستهدف ديناميكياً
            headers = content_sheet.row_values(1)
            if column_name in headers:
                col_index = headers.index(column_name) + 1
                content_sheet.update_cell(cell.row, col_index, new_value)
                print(f"✅ تم تحديث {column_name} بنجاح للقيمة الجديدة.")
                return True
    except Exception as e:
        print(f"❌ خطأ في تحديث إعدادات المحتوى: {e}")
    return False

def get_bot_config(bot_id):
    """جلب كامل إعدادات البوت وتحويلها إلى قاموس (Dict) لسهولة الاستخدام برمجياً"""
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
        print(f"❌ خطأ في جلب بيانات تكوين البوت: {e}")
    return {}

def add_log_entry(bot_id, log_type, message):
    """إضافة سجل تقني دقيق لمراقبة العمليات والأخطاء داخل المصنع"""
    global logs_sheet
    if logs_sheet is None: 
        if not connect_to_google(): return False
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs_sheet.append_row([str(bot_id), log_type, message, now])
        return True
    except Exception as e:
        print(f"❌ خطأ في تدوين سجل العملية: {e}")
        return False

def check_connection():
    """وظيفة المراقبة الدورية لسلامة الاتصال بجوجل شيت (Heartbeat)"""
    try:
        ss.title
        return True
    except:
        print("🔄 محاولة إعادة الاتصال التلقائي بقاعدة البيانات...")
        return connect_to_google()


# --------------------------------------------------------------------------


def get_all_active_bots():
    """جلب كافة البوتات التي حالتها 'نشط' لتشغيلها"""
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try:
        all_records = bots_sheet.get_all_records()
        # جلب البوتات التي تحتوي على توكن وحالتها "نشط"
        return [bot for bot in all_records if bot.get("التوكن") and bot.get("حالة التشغيل") == "نشط"]
    except Exception as e:
        print(f"❌ خطأ في جلب البوتات النشطة: {e}")
        return []
# --------------------------------------------------------------------------

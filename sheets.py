import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- إعداد المتغيرات العالمية للوصول الشامل ---
client = None
ss = None
users_sheet = None
bots_sheet = None
content_sheet = None
logs_sheet = None
# معرف ملف Google Sheet الخاص بالمصنع
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

def get_config():
    """جلب وتصحيح المفاتيح من متغيرات البيئة لضمان توافق RSA و JWT"""
    raw_key = os.getenv("G_PRIVATE_KEY")
    if not raw_key:
        print("❌ خطأ حرج: G_PRIVATE_KEY مفقود من إعدادات السيرفر!")
        return None
    
    try:
        # تصحيح شامل للمفتاح الخاص: معالجة فواصل الأسطر، إزالة علامات الاقتباس الزائدة، والمسافات المخفية
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
    """تأسيس الاتصال بجوجل وتعيين أوراق العمل مع نظام تقرير أخطاء عميق"""
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    config = get_config()
    if not config:
        return False

    try:
        # تحديد نطاقات الوصول المطلوبة (Sheets و Drive) للكتابة والقراءة
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        
        # محاولة فتح ملف قاعدة البيانات
        ss = client.open_by_key(SPREADSHEET_ID)
        
        # فحص استباقي لأسماء الأوراق للتأكد من مطابقتها يدوياً وبرمجياً
        sheets_names = [s.title for s in ss.worksheets()]
        print(f"📋 الأوراق المكتشفة في الملف هي: {sheets_names}")

        # ربط الأوراق بالمتغيرات العالمية (يجب أن تكون الأسماء مطابقة تماماً في الشيت)
        # ملاحظة: تأكد أن "المستخدمين" في الشيت مكتوبة بالياء "ي" وليس "ى"
        users_sheet = ss.worksheet("المستخدمين")
        bots_sheet = ss.worksheet("البوتات_المصنوعة")
        content_sheet = ss.worksheet("إعدادات_المحتوى")
        logs_sheet = ss.worksheet("السجلات")
        
        print("✅ تم الاتصال بنجاح: كافة الصلاحيات مفعلة وقاعدة البيانات جاهزة.")
        return True
    except gspread.exceptions.WorksheetNotFound as e:
        print(f"❌ خطأ: لم يتم العثور على ورقة بهذا الاسم (تأكد من الياء والى): {e}")
    except Exception as e:
        print(f"❌ فشل الاتصال النهائي أو نقص في صلاحيات Drive API: {str(e)}")
    return False

# محاولة الاتصال الفوري عند إقلاع البوت
connect_to_google()

# --- الدوال الوظيفية الكاملة لإدارة بيانات المصنع ---

def save_user(user_id, username):
    """حفظ بيانات المستخدم الجديد مع فحص التكرار ونظام الكتابة الفورية"""
    global users_sheet
    print(f"🔍 محاولة فحص وتسجيل المستخدم: {user_id} (@{username})")
    
    if users_sheet is None:
        if not connect_to_google():
            print("❌ فشل التسجيل: تعذر الوصول إلى جوجل شيت.")
            return False

    try:
        # البحث عن ID المستخدم لمنع تكرار البيانات
        search_result = users_sheet.find(str(user_id))
        if search_result:
            print(f"ℹ️ المستخدم {user_id} مسجل بالفعل في الصف {search_result.row}")
            return False
    except (gspread.exceptions.CellNotFound, Exception):
        # في حال لم يتم العثور على المستخدم، نبدأ عملية الإضافة
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # ترتيب الأعمدة: ID، اسم، تاريخ، حالة، اشتراك، عدد بوتات، نشاط، لغة، مصدر، كود، رصيد
            row = [str(user_id), str(username), now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
            
            # الكتابة في السطر الثاني مباشرة لضمان الظهور الفوري وتجنب الصفوف العالقة
            users_sheet.insert_row(row, 2) 
            print(f"✅ تم تسجيل المستخدم {user_id} بنجاح في قاعدة البيانات.")
            return True
        except Exception as e:
            print(f"❌ خطأ تقني أثناء إضافة الصف (تحقق من Drive API): {e}")
    return False

def save_bot(owner_id, bot_type, bot_name):
    """توثيق البوتات التي يتم صنعها في ورقة البوتات_المصنوعة"""
    global bots_sheet
    if bots_sheet is None: 
        if not connect_to_google(): return False
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # بيانات البوت الافتراضية
        row = [
            str(owner_id), bot_type, bot_name, "", "متوقف", 
            "", "", now, "", 0, 0, "جيد", "", "polling", 
            "free", "", "true", ""
        ]
        bots_sheet.append_row(row)
        print(f"✅ تم تسجيل بوت جديد ({bot_name}) للمالك {owner_id}")
        return True
    except Exception as e:
        print(f"❌ خطأ في حفظ بيانات البوت: {e}")
    return False

def update_content_setting(bot_id, column_name, new_value):
    """تحديث ديناميكي لإعدادات المحتوى لأي بوت مصنوع"""
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
                print(f"✅ تم تحديث {column_name} للبوت {bot_id}")
                return True
    except Exception as e:
        print(f"❌ خطأ في تحديث إعدادات المحتوى: {e}")
    return False

def get_bot_config(bot_id):
    """جلب كافة إعدادات البوت المصنوع في قاموس برمجى واحد"""
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
        print(f"❌ خطأ في جلب بيانات البوت: {e}")
    return {}

def add_log_entry(bot_id, log_type, message):
    """إضافة سجل تقني لمراقبة أداء العمليات داخل المصنع"""
    global logs_sheet
    if logs_sheet is None: 
        if not connect_to_google(): return False
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs_sheet.append_row([str(bot_id), log_type, message, now])
        return True
    except Exception as e:
        print(f"❌ خطأ في تدوين السجل: {e}")
        return False

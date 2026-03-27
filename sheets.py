import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- إعداد المتغيرات العالمية ---
client = None
ss = None
users_sheet = None
bots_sheet = None
content_sheet = None
logs_sheet = None
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

def get_config():
    """جلب وتصحيح المفاتيح من السيرفر"""
    raw_key = os.getenv("G_PRIVATE_KEY")
    if not raw_key:
        print("❌ خطأ حرج: G_PRIVATE_KEY مفقود من إعدادات السيرفر!")
        return None
    
    try:
        # معالجة فورية للمفتاح الخاص لضمان صيغة RSA سليمة
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
        print(f"❌ خطأ في معالجة القاموس البرمجي: {e}")
        return None

def connect_to_google():
    """محاولة الاتصال مع تقرير تفصيلي عن الأخطاء"""
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    config = get_config()
    if not config: return False

    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        
        # محاولة فتح الملف
        ss = client.open_by_key(SPREADSHEET_ID)
        
        # محاولة الوصول للأوراق مع فحص الأسماء
        sheets_names = [s.title for s in ss.worksheets()]
        print(f"📋 الأوراق الموجودة في الشيت هي: {sheets_names}")

        # ربط الأوراق (تأكد من مطابقة هذه الأسماء تماماً في ملف جوجل)
        users_sheet = ss.worksheet("المستخدمين")
        bots_sheet = ss.worksheet("البوتات_المصنوعة")
        content_sheet = ss.worksheet("إعدادات_المحتوى")
        logs_sheet = ss.worksheet("السجلات")
        
        print("✅ متصل بنجاح: قاعدة البيانات جاهزة للكتابة والقراءة.")
        return True
    except gspread.exceptions.WorksheetNotFound as e:
        print(f"❌ خطأ: لم يتم العثور على ورقة بهذا الاسم: {e}")
    except Exception as e:
        print(f"❌ فشل الاتصال النهائي: {str(e)}")
    return False

# تشغيل الاتصال عند بدء البوت
connect_to_google()

# --- الدوال الوظيفية مع نظام كشف الأخطاء أثناء التنفيذ ---

def save_user(user_id, username):
    global users_sheet
    print(f"🔍 محاولة تسجيل مستخدم: {user_id} - {username}")
    
    if users_sheet is None:
        if not connect_to_google():
            print("❌ تعذر التسجيل: لا يوجد اتصال بجوجل شيت.")
            return False

    try:
        # فحص هل المستخدم موجود
        search_result = users_sheet.find(str(user_id))
        if search_result:
            print(f"ℹ️ المستخدم {user_id} موجود مسبقاً في الصف رقم {search_result.row}")
            return False
    except (gspread.exceptions.CellNotFound, Exception):
        # إذا لم يجد المستخدم، نقوم بإضافته
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [str(user_id), str(username), now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
            users_sheet.append_row(row)
            print(f"✅ تم تسجيل المستخدم {user_id} بنجاح في الشيت.")
            return True
        except Exception as e:
            print(f"❌ فشل إضافة الصف في الشيت: {e}")
    return False

def save_bot(owner_id, bot_type, bot_name):
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(owner_id), bot_type, bot_name, "", "متوقف", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""]
        bots_sheet.append_row(row)
        print(f"✅ تم تسجيل البوت الجديد للمالك {owner_id}")
        return True
    except Exception as e:
        print(f"❌ خطأ في حفظ البوت: {e}")
    return False

def update_content_setting(bot_id, column_name, new_value):
    global content_sheet
    if content_sheet is None: connect_to_google()
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            headers = content_sheet.row_values(1)
            if column_name in headers:
                content_sheet.update_cell(cell.row, headers.index(column_name) + 1, new_value)
                return True
    except Exception as e:
        print(f"❌ خطأ في تحديث المحتوى: {e}")
    return False

def get_bot_config(bot_id):
    global content_sheet
    if content_sheet is None: connect_to_google()
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            return dict(zip(content_sheet.row_values(1), content_sheet.row_values(cell.row)))
    except: pass
    return {}

def add_log_entry(bot_id, log_type, message):
    global logs_sheet
    if logs_sheet is None: connect_to_google()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs_sheet.append_row([str(bot_id), log_type, message, now])
        return True
    except: return False

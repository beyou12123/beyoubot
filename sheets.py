import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- نظام الاتصال المباشر (الأكثر استقراراً) ---

def get_config():
    # جلب المفتاح الخاص ومعالجته بدقة
    raw_key = os.getenv("G_PRIVATE_KEY")
    if raw_key:
        # إصلاح مشكلة الهروب (Escape) يدوياً لضمان قبول جوجل للمفتاح
        clean_key = raw_key.replace('\\n', '\n').strip().strip('"')
        
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
    return None

# إعداد المتغيرات العالمية
client = None
ss = None
users_sheet = None
bots_sheet = None
content_sheet = None
logs_sheet = None
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

def connect_to_google():
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    config = get_config()
    if not config or not config["private_key"]:
        print("❌ خطأ: لم يتم ضبط G_PRIVATE_KEY بشكل صحيح في السيرفر")
        return False

    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        ss = client.open_by_key(SPREADSHEET_ID)
        
        users_sheet = ss.worksheet("المستخدمين")
        bots_sheet = ss.worksheet("البوتات_المصنوعة")
        content_sheet = ss.worksheet("إعدادات_المحتوى")
        logs_sheet = ss.worksheet("السجلات")
        
        print("✅ تم الاتصال بقاعدة بيانات جوجل بنجاح")
        return True
    except Exception as e:
        print(f"❌ فشل الاتصال: {str(e)}")
        return False

connect_to_google()

# --- الدوال الوظيفية (كاملة وبدون حذف) ---

def save_user(user_id, username):
    global users_sheet
    if users_sheet is None: connect_to_google()
    try:
        users_sheet.find(str(user_id))
        return False
    except:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        users_sheet.append_row([str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0])
        return True

def save_bot(owner_id, bot_type, bot_name):
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bots_sheet.append_row([str(owner_id), bot_type, bot_name, "", "متوقف", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""])
        return True
    except: return False

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
    except: return False

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

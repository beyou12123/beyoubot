import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- نظام فك التشفير الذكي لضمان سلامة التوقيع الرقمي 100% ---

# جلب النص المشفر من متغيرات البيئة
encoded_creds = os.getenv("GOOGLE_CREDS")

if encoded_creds:
    try:
        # فك تشفير Base64 للعودة إلى صيغة JSON الأصلية
        decoded_bytes = base64.b64decode(encoded_creds)
        SERVICE_ACCOUNT_CONFIG = json.loads(decoded_bytes.decode('utf-8'))
        
        # معالجة المفتاح الخاص لضمان سلامة الرموز (سطر جديد)
        if "private_key" in SERVICE_ACCOUNT_CONFIG:
            SERVICE_ACCOUNT_CONFIG["private_key"] = SERVICE_ACCOUNT_CONFIG["private_key"].replace('\\n', '\n')

        # تحديد نطاق الوصول
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # إنشاء الاعتمادات البرمجية
        creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_CONFIG, scope)
        client = gspread.authorize(creds)
    except Exception as e:
        raise ValueError(f"❌ خطأ فادح في فك تشفير المفاتيح: {str(e)}")
else:
    raise ValueError("❌ لم يتم العثور على متغير GOOGLE_CREDS المشفر في السيرفر")

# معرف ملف Google Sheet الخاص بك
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"
ss = client.open_by_key(SPREADSHEET_ID)

# تعريف الأوراق (Tabs) للوصول المباشر
users_sheet = ss.worksheet("المستخدمين")
bots_sheet = ss.worksheet("البوتات_المصنوعة")
content_sheet = ss.worksheet("إعدادات_المحتوى")
logs_sheet = ss.worksheet("السجلات")

# --- كافة الوظائف البرمجية المطلوبة (بدون أي اختصار) ---

def save_user(user_id, username):
    """تسجيل مستخدم جديد في ورقة المستخدمين"""
    try:
        users_sheet.find(str(user_id))
        return False  # موجود مسبقاً
    except gspread.exceptions.CellNotFound:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # الترتيب: ID، اسم، تاريخ، حالة، نوع اشتراك، عدد بوتات، نشاط، لغة، مصدر، كود، رصيد
        row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        users_sheet.append_row(row)
        return True

def save_bot(owner_id, bot_type, bot_name):
    """حفظ بيانات البوت المصنوع حديثاً"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # الترتيب حسب أعمدة الشيت
    row = [str(owner_id), bot_type, bot_name, "", "متوقف", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""]
    bots_sheet.append_row(row)

def update_content_setting(bot_id, column_name, new_value):
    """تحديث عمود معين في إعدادات المحتوى"""
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            headers = content_sheet.row_values(1)
            if column_name in headers:
                col_index = headers.index(column_name) + 1
                content_sheet.update_cell(cell.row, col_index, new_value)
                return True
    except Exception as e:
        print(f"Error updating sheet: {e}")
    return False

def get_bot_config(bot_id):
    """جلب كامل إعدادات البوت في قاموس بايثون"""
    try:
        cell = content_sheet.find(str(bot_id))
        values = content_sheet.row_values(cell.row)
        headers = content_sheet.row_values(1)
        return dict(zip(headers, values))
    except:
        return {}

def add_log_entry(bot_id, log_type, message):
    """إضافة سجل جديد للعمليات"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs_sheet.append_row([str(bot_id), log_type, message, now])

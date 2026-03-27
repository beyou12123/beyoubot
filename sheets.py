import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- إعداد المتغيرات بشكل عالمي لتجنب NameError ---
client = None
ss = None
users_sheet = None
bots_sheet = None
content_sheet = None
logs_sheet = None

# معرف ملف Google Sheet
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

def connect_to_google():
    """وظيفة للاتصال بجوجل وتحديث المتغيرات العالمية"""
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    
    encoded_creds = os.getenv("GOOGLE_CREDS")
    if not encoded_creds:
        print("❌ خطأ: لم يتم العثور على متغير GOOGLE_CREDS")
        return False

    try:
        # فك تشفير Base64
        decoded_bytes = base64.b64decode(encoded_creds)
        config = json.loads(decoded_bytes.decode('utf-8'))
        
        if "private_key" in config:
            config["private_key"] = config["private_key"].replace('\\n', '\n')

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        
        # فتح الشيت والوصول للأوراق
        ss = client.open_by_key(SPREADSHEET_ID)
        users_sheet = ss.worksheet("المستخدمين")
        bots_sheet = ss.worksheet("البوتات_المصنوعة")
        content_sheet = ss.worksheet("إعدادات_المحتوى")
        logs_sheet = ss.worksheet("السجلات")
        
        print("✅ تم الاتصال بقاعدة بيانات جوجل بنجاح")
        return True
    except Exception as e:
        print(f"❌ فشل الاتصال بقاعدة بيانات جوجل: {str(e)}")
        return False

# محاولة الاتصال الأولية عند تشغيل الملف
connect_to_google()

# --- كافة الوظائف البرمجية بدون حذف أو اختصار ---

def save_user(user_id, username):
    """تسجيل مستخدم جديد"""
    global users_sheet
    if users_sheet is None: connect_to_google()
    
    try:
        users_sheet.find(str(user_id))
        return False
    except (gspread.exceptions.CellNotFound, gspread.CellNotFound):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        users_sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Error in save_user: {e}")
        return False

def save_bot(owner_id, bot_type, bot_name):
    """حفظ بيانات البوت المصنوع"""
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(owner_id), bot_type, bot_name, "", "متوقف", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""]
        bots_sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Error in save_bot: {e}")
        return False

def update_content_setting(bot_id, column_name, new_value):
    """تحديث عمود معين في إعدادات المحتوى"""
    global content_sheet
    if content_sheet is None: connect_to_google()
    
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            headers = content_sheet.row_values(1)
            if column_name in headers:
                col_index = headers.index(column_name) + 1
                content_sheet.update_cell(cell.row, col_index, new_value)
                return True
    except Exception as e:
        print(f"Error in update_content: {e}")
    return False

def get_bot_config(bot_id):
    """جلب إعدادات البوت"""
    global content_sheet
    if content_sheet is None: connect_to_google()
    
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            return dict(zip(content_sheet.row_values(1), content_sheet.row_values(cell.row)))
    except:
        pass
    return {}

def add_log_entry(bot_id, log_type, message):
    """إضافة سجل للعمليات"""
    global logs_sheet
    if logs_sheet is None: connect_to_google()
    
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs_sheet.append_row([str(bot_id), log_type, message, now])
        return True
    except:
        return False

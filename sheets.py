import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- نظام الاتصال الاحترافي: معالجة النصوص المشوهة وتصحيح التنسيق ---

def get_clean_creds():
    raw_creds = os.getenv("GOOGLE_CREDS")
    if not raw_creds:
        print("❌ خطأ: متغير GOOGLE_CREDS غير موجود في السيرفر")
        return None

    try:
        # 1. تنظيف شامل للنص من أي مسافات أو علامات اقتباس محيطة
        clean_text = raw_creds.strip().strip('"').strip("'")
        
        # 2. فك التشفير من Base64
        decoded_data = base64.b64decode(clean_text, validate=False)
        
        # 3. تحويل البيانات إلى نص ومعالجة الهروب (Escape characters) يدوياً إذا لزم الأمر
        json_str = decoded_data.decode('utf-8', errors='ignore')
        
        # 4. محاولة تحميل الـ JSON
        creds_dict = json.loads(json_str)
        
        # 5. معالجة دقيقة للمفتاح الخاص لضمان قبول جوجل للتوقيع
        if "private_key" in creds_dict:
            # استبدال الهروب المزدوج بأسطر حقيقية
            creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
            
        return creds_dict
    except Exception as e:
        print(f"❌ خطأ في معالجة المفتاح: {str(e)}")
        return None

# --- إعداد الثوابت والمتغيرات العالمية ---
client = None
ss = None
users_sheet = None
bots_sheet = None
content_sheet = None
logs_sheet = None
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

def connect_to_google():
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    config = get_clean_creds()
    if not config: return False

    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        ss = client.open_by_key(SPREADSHEET_ID)
        
        # ربط الأوراق (تأكد من مطابقة الأسماء تماماً في الشيت)
        users_sheet = ss.worksheet("المستخدمين")
        bots_sheet = ss.worksheet("البوتات_المصنوعة")
        content_sheet = ss.worksheet("إعدادات_المحتوى")
        logs_sheet = ss.worksheet("السجلات")
        
        print("✅ تم الاتصال بنجاح وقاعدة البيانات جاهزة للعمل")
        return True
    except Exception as e:
        print(f"❌ فشل فتح الملف أو الأوراق: {str(e)}")
        return False

# محاولة الاتصال عند إقلاع الملف
connect_to_google()

# --- كافة الدوال الوظيفية المطلوبة (بدون اختصار) ---

def save_user(user_id, username):
    global users_sheet
    if users_sheet is None: connect_to_google()
    try:
        if users_sheet:
            try:
                users_sheet.find(str(user_id))
                return False # موجود مسبقاً
            except (gspread.exceptions.CellNotFound, gspread.CellNotFound):
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # ID، اسم، تاريخ، حالة، اشتراك، عدد بوتات، نشاط، لغة، مصدر، كود، رصيد
                row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
                users_sheet.append_row(row)
                return True
    except Exception as e:
        print(f"Error in save_user: {e}")
    return False

def save_bot(owner_id, bot_type, bot_name):
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try:
        if bots_sheet:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [str(owner_id), bot_type, bot_name, "", "متوقف", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""]
            bots_sheet.append_row(row)
            return True
    except Exception as e:
        print(f"Error in save_bot: {e}")
    return False

def update_content_setting(bot_id, column_name, new_value):
    global content_sheet
    if content_sheet is None: connect_to_google()
    try:
        if content_sheet:
            cell = content_sheet.find(str(bot_id))
            if cell:
                headers = content_sheet.row_values(1)
                if column_name in headers:
                    col_index = headers.index(column_name) + 1
                    content_sheet.update_cell(cell.row, col_index, new_value)
                    return True
    except: pass
    return False

def get_bot_config(bot_id):
    global content_sheet
    if content_sheet is None: connect_to_google()
    try:
        if content_sheet:
            cell = content_sheet.find(str(bot_id))
            if cell:
                return dict(zip(content_sheet.row_values(1), content_sheet.row_values(cell.row)))
    except: pass
    return {}

def add_log_entry(bot_id, log_type, message):
    global logs_sheet
    if logs_sheet is None: connect_to_google()
    try:
        if logs_sheet:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logs_sheet.append_row([str(bot_id), log_type, message, now])
            return True
    except: pass
    return False

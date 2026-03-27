import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- إعداد الاتصال بقاعدة البيانات عبر متغيرات البيئة لضمان القوة والاستقرار ---

# استدعاء البيانات من متغير بيئة شامل اسمه GOOGLE_CREDS
creds_json = os.getenv("GOOGLE_CREDS")

if creds_json:
    try:
        # تحويل النص المستلم من السيرفر إلى قاموس بايثون
        SERVICE_ACCOUNT_CONFIG = json.loads(creds_json)
        
        # معالجة المفتاح الخاص لضمان سلامة الرموز البرمجية (سطر جديد)
        if "private_key" in SERVICE_ACCOUNT_CONFIG:
            SERVICE_ACCOUNT_CONFIG["private_key"] = SERVICE_ACCOUNT_CONFIG["private_key"].replace('\\n', '\n')

        # تحديد نطاق الوصول لصلاحيات جوجل درايف وشيت
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # إنشاء الاعتمادات البرمجية من القاموس مباشرة
        creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_CONFIG, scope)
        client = gspread.authorize(creds)
    except Exception as e:
        raise ValueError(f"❌ خطأ في معالجة بيانات GOOGLE_CREDS: {str(e)}")
else:
    # في حال لم يتم ضبط المتغير في السيرفر بعد
    raise ValueError("❌ لم يتم العثور على متغير البيئة GOOGLE_CREDS في إعدادات السيرفر")

# معرف ملف Google Sheet الخاص بمصنعك
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"
ss = client.open_by_key(SPREADSHEET_ID)

# تعريف الأوراق (Tabs) للوصول المباشر والسريع
users_sheet = ss.worksheet("المستخدمين")
bots_sheet = ss.worksheet("البوتات_المصنوعة")
content_sheet = ss.worksheet("إعدادات_المحتوى")
logs_sheet = ss.worksheet("السجلات")

# --- وظائف التعامل مع بيانات المستخدمين ---

def save_user(user_id, username):
    """تسجيل مستخدم جديد في ورقة المستخدمين مع الإعدادات الافتراضية الكاملة"""
    try:
        # البحث للتأكد من عدم تكرار المستخدم
        cell = users_sheet.find(str(user_id))
        return False  # المستخدم مسجل مسبقاً
    except gspread.exceptions.CellNotFound:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # الترتيب: ID، اسم، تاريخ، حالة، نوع اشتراك، عدد بوتات، نشاط، لغة، مصدر، كود، رصيد
        row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        users_sheet.append_row(row)
        return True

# --- وظائف إدارة وتصنيع البوتات ---

def save_bot(owner_id, bot_type, bot_name):
    """حفظ بيانات البوت المصنوع حديثاً في ورقة البوتات_المصنوعة"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # الترتيب: ID المالك، نوع البوت، اسم البوت، التوكن، حالة التشغيل، bot_id، username_bot، تاريخ الإنشاء... إلخ
    # تم ترك الخانات التي تملأ لاحقاً فارغة
    row = [str(owner_id), bot_type, bot_name, "", "متوقف", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""]
    bots_sheet.append_row(row)

# --- وظائف التحكم في المحتوى (لوحة الإدارة) ---

def update_content_setting(bot_id, column_name, new_value):
    """تحديث ديناميكي لأي قيمة في إعدادات المحتوى (ترحيب، قوانين، AI، إلخ)"""
    try:
        cell = content_sheet.find(str(bot_id))
        if cell:
            # جلب عناوين الأعمدة لمعرفة رقم العمود المستهدف ديناميكياً
            headers = content_sheet.row_values(1)
            if column_name in headers:
                col_index = headers.index(column_name) + 1
                content_sheet.update_cell(cell.row, col_index, new_value)
                return True
    except Exception as e:
        print(f"Error updating content: {e}")
    return False

def get_bot_config(bot_id):
    """جلب كامل إعدادات البوت في قاموس (Dictionary) لسهولة الاستخدام في الموديولات"""
    try:
        cell = content_sheet.find(str(bot_id))
        values = content_sheet.row_values(cell.row)
        headers = content_sheet.row_values(1)
        # دمج العناوين مع القيم في قاموس واحد
        return dict(zip(headers, values))
    except:
        return {}

# --- وظائف تتبع السجلات والعمليات ---

def add_log_entry(bot_id, log_type, message):
    """إضافة سجل جديد في ورقة السجلات لضمان المراقبة الدقيقة"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs_sheet.append_row([str(bot_id), log_type, message, now])

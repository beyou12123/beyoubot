import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- إعداد الاتصال الآمن والمباشر عبر متغيرات البيئة المستقلة لضمان استقرار المصنع ---

def get_private_key():
    """معالجة المفتاح الخاص لضمان سلامة الرموز البرمجية وفواصل الأسطر"""
    key = os.getenv("G_PRIVATE_KEY")
    if key:
        # معالجة الـ Slash المزدوج لضمان وصول المفتاح لجوجل بصيغته الأصلية
        return key.replace('\\n', '\n')
    return None

# بناء قاموس الاعتمادات برمجياً من متغيرات البيئة المستقلة في السيرفر
SERVICE_ACCOUNT_CONFIG = {
    "type": "service_account",
    "project_id": os.getenv("G_PROJECT_ID"),
    "private_key_id": os.getenv("G_PRIVATE_KEY_ID"),
    "private_key": get_private_key(),
    "client_email": os.getenv("G_CLIENT_EMAIL"),
    "client_id": os.getenv("G_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv("G_CLIENT_CERT_URL")
}

# التحقق من وجود البيانات الحساسة قبل محاولة الاتصال
if not SERVICE_ACCOUNT_CONFIG["private_key"] or not SERVICE_ACCOUNT_CONFIG["client_email"]:
    print("❌ خطأ: لم يتم العثور على متغيرات البيئة المطلوبة في إعدادات السيرفر.")
    # لا نوقف البرنامج هنا لمنع الـ Crash ولكن الاتصال سيفشل عند الطلب الأول

try:
    # تحديد نطاق الصلاحيات المطلوبة (شيت ودرايف)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # إنشاء الاعتمادات من القاموس مباشرة
    creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_CONFIG, scope)
    client = gspread.authorize(creds)
    
    # معرف ملف Google Sheet الخاص بمصنعك
    SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"
    ss = client.open_by_key(SPREADSHEET_ID)
    
    # تعريف الوصول المباشر للأوراق (Tabs)
    users_sheet = ss.worksheet("المستخدمين")
    bots_sheet = ss.worksheet("البوتات_المصنوعة")
    content_sheet = ss.worksheet("إعدادات_المحتوى")
    logs_sheet = ss.worksheet("السجلات")
    
except Exception as e:
    print(f"❌ فشل الاتصال بقاعدة بيانات جوجل: {str(e)}")

# --- وظائف التعامل مع بيانات المستخدمين ---

def save_user(user_id, username):
    """تسجيل مستخدم جديد في ورقة المستخدمين مع كامل البيانات الافتراضية"""
    try:
        # التأكد أولاً إذا كان المستخدم موجوداً لمنع التكرار
        users_sheet.find(str(user_id))
        return False  # المستخدم مسجل مسبقاً
    except gspread.exceptions.CellNotFound:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # الترتيب: ID، اسم، تاريخ، حالة، نوع اشتراك، عدد بوتات، نشاط، لغة، مصدر، كود، رصيد
        row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        users_sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Error in save_user: {e}")
        return False

# --- وظائف إدارة وتصنيع البوتات ---

def save_bot(owner_id, bot_type, bot_name):
    """حفظ بيانات البوت المصنوع حديثاً في ورقة البوتات_المصنوعة"""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # الترتيب حسب أعمدة الشيت المقررة في مصفوفة البيانات
        row = [
            str(owner_id), bot_type, bot_name, "", "متوقف", 
            "", "", now, "", 0, 0, "جيد", "", "polling", 
            "free", "", "true", ""
        ]
        bots_sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Error in save_bot: {e}")
        return False

# --- وظائف التحكم في المحتوى (لوحة الإدارة والموديولات) ---

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
        if cell:
            values = content_sheet.row_values(cell.row)
            headers = content_sheet.row_values(1)
            # دمج العناوين مع القيم في قاموس واحد
            return dict(zip(headers, values))
    except Exception as e:
        print(f"Error getting bot config: {e}")
    return {}

# --- وظائف تتبع السجلات والعمليات لمراقبة أداء المصنع ---

def add_log_entry(bot_id, log_type, message):
    """إضافة سجل جديد في ورقة السجلات لضمان المراقبة الدقيقة والتدقيق"""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs_sheet.append_row([str(bot_id), log_type, message, now])
        return True
    except Exception as e:
        print(f"Error adding log: {e}")
        return False

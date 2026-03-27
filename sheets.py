import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# إعدادات الاتصال الأساسية
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# فتح ملف قاعدة البيانات الخاص بك
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"
ss = client.open_by_key(SPREADSHEET_ID)

# تعريف الوصول للأوراق
users_sheet = ss.worksheet("المستخدمين")
bots_sheet = ss.worksheet("البوتات_المصنوعة")
content_sheet = ss.worksheet("إعدادات_المحتوى")
logs_sheet = ss.worksheet("السجلات")

# --- دوال التعامل مع المستخدمين ---

def register_user(user_id, username):
    """تسجيل مستخدم جديد مع كامل البيانات الافتراضية"""
    try:
        # التأكد أولاً إذا كان المستخدم موجوداً
        if not users_sheet.find(str(user_id)):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # الأعمدة: ID، اسم، تاريخ، حالة، اشتراك، عدد بوتات، نشاط، لغة، مصدر، كود، رصيد
            row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Bot", "", 0]
            users_sheet.append_row(row)
            return True
    except gspread.exceptions.CellNotFound:
        # إذا لم يجد المستخدم، نقوم بتسجيله (نفس الكود أعلاه)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Bot", "", 0]
        users_sheet.append_row(row)
        return True
    return False

# --- دوال التحكم في المحتوى (لوحة الإدارة) ---

def update_content_setting(bot_id, column_name, new_value):
    """تحديث أي قيمة في إعدادات المحتوى (ترحيب، قوانين، إلخ)"""
    # البحث عن سطر البوت
    cell = content_sheet.find(str(bot_id))
    if cell:
        # جلب عناوين الأعمدة لمعرفة رقم العمود المستهدف
        headers = content_sheet.row_values(1)
        col_index = headers.index(column_name) + 1
        content_sheet.update_cell(cell.row, col_index, new_value)
        return True
    return False

def get_bot_config(bot_id):
    """جلب كل إعدادات البوت في قاموس (Dictionary) لسهولة الاستخدام"""
    try:
        cell = content_sheet.find(str(bot_id))
        values = content_sheet.row_values(cell.row)
        headers = content_sheet.row_values(1)
        return dict(zip(headers, values))
    except:
        return None

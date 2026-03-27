import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1. إعداد بيانات الاعتماد مباشرة من البيانات التي أرسلتها
# تم وضعها هنا لضمان عدم تلف التنسيق أثناء الرفع
SERVICE_ACCOUNT_CONFIG = {
  "type": "service_account",
  "project_id": "rbotssheet",
  "private_key_id": "256a8265413faf5687c25f97d773d7a8e963efd1",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDKkEvt8LAgNlcg\nKuASpT0AA7Dg+lbMSBfU3UAOr2KepYOEVuGlOJTh+c9k4+yxIQTq9lghPhrSws3k\nVYo9tgtmcSPRsqfEye4MkGSbjK0gSLpz1+wkq6drgJHXNx7psTjXtYSpgPZfT8sQ\nV1XNxl6pseL46cf2BGkHQw/wsfQY42n4m7/KsEuI77TZoTMfIvn+r5UDn0EEohNf\nRGaeXaGMku2FJ4pbLzx96V0vpGnC7wDSnN0RUeXDpAx86bd5kqFVxQSFMJLqRPQd\nDgHRO3FGVcFUyTH/xhfwpZRQFH8rp5SnVcxHw2q8asBCVGaTjLVd6dOemdxPOQjK\nfgzKOR0/AgMBAAECggEAE6az1XJw3vC9CBMqWzS2xvSuT4BWmyMKIm3ECqJFWrQe\nhUazRYbIaGagEgVLz5OvLFo+V4J0y+oqwXi/XHHeOw+r1J3Ur8v4cTVkeHPjBP6s\nc/n7eaoOqAIeylAZiom79+IVhVoymWS4A8hToluY9s6ANGF9s1mSYapF9oK7dkFH\nppntvMJlM3GI4/fbn1aUFf9ZWeqP0VJSLsASNvcB2tzdd7Beh17GfScGVQteZjHx\nZa0I4pxxipk/Lh6Dx7q+ctcPEibT7qQkI3lFiF85e7ugKxbkcH/x6xbVox+DlbaS\nVr3iNT+NqsEAZ1qiMdzkIY2cCHV1yOvdudyUWBuUcQKBgQD9zeRsmepcMuNOvfaU\neQUVW+BmtmrW/lMh2R+iojrw+B56qOU9q1dNQNzRzSMpnGx5DNR+x1AF+TpjDTH4\nwFb0Tyl2/atIjEUyy0JSRkBU5ditA6rYT650NpjJJcoGlA9SniZt1rsJ/HgXxE9P\nUXul+V6Nr5OzwhIp9p2Gb/TE8QKBgQDMUOuVSzjLyvKvMVXIMsg0WGPu9VJ2ZAHX\nECY3bUZeH2h7EXanvoo9t7US3X93EKskTjcCerTemeXoc8jiw0tZDM/oqAnjK2lN\nYVh0mO800cPv+zLttbrkiixEgU0cs97ZJTZms92sIiWoy8kz9HoQJueqXhxvaQUm\nlSHQZnRFLwKBgQDlXxm8/CzNPkAnfY5HCEgL0YivytQrkJTY1jy84hiaheIlwFXM\nsfioHKJ0CQxqIq/1hh7UpJQxkdeuhNJQmKL9ED3NB9uwKPSwvvklGdAx6bc0RUg1\nTW3AIUdbIge+gjiG1d6tDY7jq4NtF0EF0gIJMaC+M5ssrYt02Sfrw2pWQQKBgFJ/\nQgBQFSjEU2VFyFtDle782az8xUUkcFHEJYovxz/t8qPukzh8CRmOecCaSwNqaZAJ\nPND1dt6CyYAocC6PqHbWY4SPhR6CwswJyEucDMoJANJ/XTr6K/JnkCRBCT/TqOGI\n0wR5D8KXLxmO3zjpN/gZnWT/BwA9KWVAxhx9oejlAoGBAM9UPIIu/pt9wIVWEy5v\nujoLclGKXxZ4xM2DjU+eiITqaAfQQ+1cvs5DOJ3hmUnUEM7ZPy9zMoEcZzKXGrIP\nFbsi66XxlFMRoaddURJkUd+bSnsdfkUgYH3aZTwTji/oj9uv0btytsUz052bLdrD\nP9UEZppf7CKd44EukgcEAYBX\n-----END PRIVATE KEY-----\n",
  "client_email": "bot-factoryalmss@rbotssheet.iam.gserviceaccount.com",
  "client_id": "113596584371083576496",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/bot-factoryalmss%40rbotssheet.iam.gserviceaccount.com"
}

# 2. إعداد الاتصال باستخدام القاموس مباشرة
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_CONFIG, scope)
client = gspread.authorize(creds)

# 3. فتح ملف قاعدة البيانات الخاص بك
# ملاحظة: تأكد أنك عملت Share لهذا الإيميل:
# bot-factoryalmss@rbotssheet.iam.gserviceaccount.com
# في ملف الشيت 1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"
ss = client.open_by_key(SPREADSHEET_ID)

# تعريف الوصول للأوراق
users_sheet = ss.worksheet("المستخدمين")
bots_sheet = ss.worksheet("البوتات_المصنوعة")
content_sheet = ss.worksheet("إعدادات_المحتوى")
logs_sheet = ss.worksheet("السجلات")

# --- الدوال المطلوبة ---

def save_user(user_id, username):
    """تسجيل أو تحديث بيانات المستخدم"""
    try:
        cell = users_sheet.find(str(user_id))
        return False # المستخدم موجود مسبقاً
    except:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(user_id), username, now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        users_sheet.append_row(row)
        return True

def save_bot(owner_id, bot_type, bot_name):
    """حفظ بيانات البوت المصنوع"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # الترتيب حسب أعمدة الشيت (ID المالك، نوع، اسم...)
    row = [str(owner_id), bot_type, bot_name, "", "متوقف", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""]
    bots_sheet.append_row(row)

def update_content_setting(bot_id, column_name, new_value):
    """تحديث عمود معين لبوت معين"""
    cell = content_sheet.find(str(bot_id))
    if cell:
        headers = content_sheet.row_values(1)
        col_index = headers.index(column_name) + 1
        content_sheet.update_cell(cell.row, col_index, new_value)

def get_bot_config(bot_id):
    """جلب إعدادات بوت معين"""
    try:
        cell = content_sheet.find(str(bot_id))
        values = content_sheet.row_values(cell.row)
        headers = content_sheet.row_values(1)
        return dict(zip(headers, values))
    except:
        return {}

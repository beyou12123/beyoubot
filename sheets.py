import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import logging

# إعداد اللوجر الاحترافي مع التسلسل الهرمي (Hierarchy Logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [CORE:DB] %(message)s')
logger = logging.getLogger(__name__)

# --- إعداد المتغيرات العالمية لكافة أوراق العمل (14 ورقة كاملة) ---
client = None
ss = None
users_sheet = None           # 1. المستخدمين
bots_sheet = None            # 2. البوتات_المصنوعة
content_sheet = None         # 3. إعدادات_المحتوى
logs_sheet = None            # 4. السجلات
stats_sheet = None           # 5. الإحصائيات
payments_sheet = None        # 6. المدفوعات
students_db_sheet = None      # 7. قاعدة_بيانات_الطلاب
registrations_logs_sheet = None # 8. سجل_التسجيلات
departments_sheet = None        # 9. الأقسام
discount_codes_sheet = None     # 10. أكواد_الخصم
coupons_sheet = None            # 11. الكوبونات
courses_sheet = None            # 12. الدورات_التدريبية
faq_sheet = None                # 13. الأسئلة_الشائعة
meta_sheet = None               # 14. _meta (الإصدار والتحقق)
coaches_sheet = None            # 15. ورقة المدربين (الإضافة الجديدة)
# معرف ملف Google Sheet الخاص بمصنع البوتات
SPREADSHEET_ID = "1e0tREOyfmZgQ_iCvWXJL2GpR_I4WfCpBlU7DYUclsfY"

# --- إعدادات النظام المتقدمة (Production Core) ---
STRICT_SCHEMA = True
SCHEMA_VERSION = "1.3"
BATCH_SIZE = 50
RETRY_ATTEMPTS = 3
AUTO_RESIZE = True 
SENSITIVE_FIELDS = {"التوكن", "كلمة_المرور", "token", "api_key", "credentials", "private_key"}

# كاش داخلي لتسريع العمليات
_ws_cache = {}

def get_config():
    """جلب وتصحيح مفاتيح الوصول من متغيرات البيئة لضمان توافق RSA و JWT الرقمي"""
    raw_key = os.getenv("G_PRIVATE_KEY")
    if not raw_key:
        print("❌ خطأ حرج: G_PRIVATE_KEY مفقود من إعدادات السيرفر!")
        return None
    try:
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
    """تأسيس الاتصال بجوجل وتعيين أوراق العمل مع نظام فحص استباقي للصلاحيات"""
    global client, ss, users_sheet, bots_sheet, content_sheet, logs_sheet
    global stats_sheet, payments_sheet, students_db_sheet, registrations_logs_sheet
    global departments_sheet, discount_codes_sheet, coupons_sheet, courses_sheet, faq_sheet, meta_sheet
    global courses_sheet, coaches_sheet, faq_sheet # أضف coaches_sheet هنا
    config = get_config()
    if not config: return False

    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config, scope)
        client = gspread.authorize(creds)
        ss = client.open_by_key(SPREADSHEET_ID)
        
        def safe_get_sheet(name):
            try: return ss.worksheet(name)
            except: return None

        # ربط كافة المتغيرات بالأوراق الـ 14
        users_sheet = safe_get_sheet("المستخدمين")
        bots_sheet = safe_get_sheet("البوتات_المصنوعة")
        content_sheet = safe_get_sheet("إعدادات_المحتوى")
        logs_sheet = safe_get_sheet("السجلات")
        stats_sheet = safe_get_sheet("الإحصائيات")
        payments_sheet = safe_get_sheet("المدفوعات")
        students_db_sheet = safe_get_sheet("قاعدة_بيانات_الطلاب")
        registrations_logs_sheet = safe_get_sheet("سجل_التسجيلات")
        departments_sheet = safe_get_sheet("الأقسام")
        discount_codes_sheet = safe_get_sheet("أكواد_الخصم")
        coupons_sheet = safe_get_sheet("الكوبونات")
        courses_sheet = safe_get_sheet("الدورات_التدريبية")
        faq_sheet = safe_get_sheet("الأسئلة_الشائعة")
        meta_sheet = safe_get_sheet("_meta")
        coaches_sheet = ss.worksheet("المدربين") 

        
        print("✅ تم الاتصال بنجاح وربط كافة المتغيرات بالأوراق المتاحة.")
        return True
    except Exception as e:
        print(f"❌ فشل الاتصال النهائي: {str(e)}")
        return False

def safe_api_call(func, *args, **kwargs):
    """نظام إعادة المحاولة التلقائي لضمان استقرار العمليات"""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            wait_time = (attempt + 1) * 2
            print(f"⚠️ API Retry {attempt+1}/{RETRY_ATTEMPTS} failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
    raise Exception("❌ Critical API Failure after multiple attempts.")

# تنفيذ محاولة الاتصال الفورية
connect_to_google()

# --- الدوال الوظيفية الأساسية ---

def save_user(user_id, username):
    global users_sheet
    if users_sheet is None:
        if not connect_to_google(): return False
    try:
        try:
            exists = users_sheet.find(str(user_id))
            if exists: return False
        except: pass
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(user_id), str(username), now, "نشط", "مجاني", 0, now, "ar", "Direct", "", 0]
        users_sheet.insert_row(row, 2)
        return True
    except Exception as e:
        print(f"❌ خطأ تسجيل مستخدم: {e}")
        return False

def save_bot(owner_id, bot_type, bot_name, bot_token):
    global bots_sheet, content_sheet
    if bots_sheet is None or content_sheet is None:
        if not connect_to_google(): return False
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot_row = [str(owner_id), bot_type, bot_name, bot_token, "نشط", "", "", now, "", 0, 0, "جيد", "", "polling", "free", "", "true", ""]
        bots_sheet.append_row(bot_row)
        content_row = [bot_token, "أهلاً بك في بوتك الجديد! 🤖", "لا توجد قوانين حالياً.", "عذراً، البوت متوقف مؤقتاً.", "false", "false", "true", "[]", "[]", str(owner_id), "ar", "default", "0", "true", "[]"]
        content_sheet.append_row(content_row)
        return True
    except Exception as e:
        print(f"❌ خطأ حفظ بوت: {e}")
        return False

def update_content_setting(bot_id, column_name, new_value):
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
                return True
    except Exception as e:
        print(f"❌ خطأ تحديث إعدادات: {e}")
    return False

def get_bot_config(bot_id):
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
        print(f"❌ خطأ جلب تكوين: {e}")
    return {}

def add_log_entry(bot_id, log_type, message):
    global logs_sheet
    if logs_sheet is None:
        if not connect_to_google(): return False
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs_sheet.append_row([str(bot_id), log_type, message, now])
        return True
    except Exception as e:
        print(f"❌ خطأ تدوين سجل: {e}")
        return False

def check_connection():
    try:
        ss.title
        return True
    except:
        return connect_to_google()

def get_all_active_bots():
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try:
        all_records = bots_sheet.get_all_records()
        return [bot for bot in all_records if bot.get("التوكن") and bot.get("حالة التشغيل") == "نشط"]
    except Exception as e:
        print(f"❌ خطأ جلب البوتات: {e}")
        return []

def get_total_bots_count():
    global bots_sheet
    if bots_sheet is None: connect_to_google()
    try: return len(bots_sheet.col_values(1)) - 1
    except: return 0

def get_bot_users_count(bot_token):
    return 1

def get_bot_blocks_count(bot_token):
    return 0

def get_total_factory_users():
    global users_sheet
    if users_sheet is None: connect_to_google()
    try: return len(users_sheet.col_values(1)) - 1
    except: return 0

# --- نظام إدارة المخطط الاحترافي (Schema Engine) ---

def get_sheets_structure():
    sheets_config = [
        {"name": "المستخدمين", "cols": ["ID المستخدم","اسم المستخدم","تاريخ التسجيل","الحالة","نوع الاشتراك","عدد البوتات","آخر نشاط","اللغة","مصدر التسجيل","كود إحالة","رصيد"], "color": {"red": 0.85, "green": 0.92, "blue": 0.83}},
        {"name": "البوتات_المصنوعة", "cols": ["ID المالك","نوع البوت","اسم البوت","التوكن","حالة التشغيل","bot_id","username_bot","تاريخ الإنشاء","آخر تشغيل","عدد المستخدمين","عدد الرسائل","الحالة التقنية","webhook_url","api_type","plan","expiration_date","is_active","errors_log"], "color": {"red": 0.81, "green": 0.88, "blue": 0.95}},
        {"name": "إعدادات_المحتوى", "cols": ["ID البوت","الرسالة الترحيبية","القوانين","رد التوقف","auto_reply","ai_enabled","welcome_enabled","buttons","banned_words","admin_ids","language","theme","delay_response","broadcast_enabled","custom_commands", "welcome_morning", "welcome_noon", "welcome_evening", "welcome_night"], "color": {"red": 1.0, "green": 0.95, "blue": 0.8}},
        {"name": "الإحصائيات", "cols": ["bot_id","daily_users","messages_count","new_users","blocked_users","date"], "color": {"red": 0.92, "green": 0.82, "blue": 0.86}},
        {"name": "المدفوعات", "cols": ["user_id","amount","method","date","status"], "color": {"red": 0.99, "green": 0.9, "blue": 0.8}},
        {"name": "قاعدة_بيانات_الطلاب", "cols": ["طابع_زمني","معرف_الطلاب","ID_المستخدم_تيليجرام","الاسم_بالإنجليزي","الاسم_بالعربي","العمر","البلد","المدينة","رقم_الهاتف","البريد_الإلكتروني","تاريخ_الميلاد","المستوى","الحالة","كلمة_المرور","رابط_الصورة","معرف_الدورة","اسم_الدورة","الجنس","اسم_ ولي_الأمر","رقم_تواصل_ولي_الأمر","المؤهل_العلمي","التخصص","سنوات_الخبرة","دورات_سابقة","رابط_LinkedIn","رابط_Telegram","الرسوم","طريقة_الدفع","رابط_الإيصال","سبب_الرفض","النسبة%","المبلغ_المستحق","حالة_الحظر","كود_المندوب","اسم_المندوب","الحملة_التسويقية","معرف_الفرع","اسم_الفرع","ملاحظات"]},
        {"name": "سجل_التسجيلات", "cols": ["معرف_التسجيل","طابع_زمني","معرف_الطالب","اسم_الطالب","ID_المستخدم_تيليجرام","معرف_الدورة","اسم_الدورة","معرف_المجموعة","اسم_المجموعة","تاريخ_التسجيل","حالة_التسجيل","طريقة_التسجيل","كود_الخصم","قيمة_الخصم","السعر_الأصلي","السعر_بعد_الخصم","المبلغ_المدفوع","المبلغ_المتبقي","حالة_الدفع","طريقة_الدفع","رابط_الإيصال","اسم_المندوب","كود_المندوب","الحملة_التسويقية","معرف_الفرع","اسم_الفرع","حالة_القبول","سبب_الرفض","تاريخ_آخر_تحديث","ملاحظات","تاريخ_الانسحاب","حالة_الترقية","الدورة_السابقة","المجموعة_السابقة","ملاحظات_الإدارة","تاريخ_تأكيد_الدفع","تاريخ_تذكير_الدفع"]},
        {"name": "الأقسام", "cols": ["معرف_البوت","معرف_القسم","الوصف","الحالة","ترتيب_العرض","تاريخ_الإنشاء","معرف_الفرع","اسم_الفرع","ملاحظات"]},
        {"name": "أكواد_الخصم", "cols": ["كود_الخصم","نوع_الخصم","قيمة_الخصم","الحد_الأقصى_للاستخدام","عدد_الاستخدامات","تاريخ_البداية","تاريخ_الانتهاء","الحالة","معرف_الدورة","اسم_المندوب","الحملة_التسويقية","ملاحظات"]},
        {"name": "الكوبونات", "cols": ["معرف_الكوبون","كود_الكوبون","معرف_الطالب","اسم_الطالب","قيمة_الخصم","نوع_الخصم","الحد_الأقصى_للاستخدام","حالة_الكوبون","تاريخ_الإنشاء","تاريخ_الانتهاء","ملاحظات"]},
        {"name": "الدورات_التدريبية", "cols": ["bot_id", "معرف_الدورة", "اسم_الدورة", "عدد_الساعات", "تاريخ_البداية", "تاريخ_النهاية", "نوع_الدورة", "سعر_الدورة", "الحد_الأقصى", "المتطلبات", "اسم_المندوب", "كود_المندوب", "الحملة_التسويقية", "معرف_المدرب", "ID_المدرب", "اسم_المدرب", "معرف_القسم"]},
        {"name": "الأسئلة_الشائعة", "cols": ["bot_id", "معرف_القسم","معرف_الدورة","اسم_الدورة", "محتوى_السؤال_مع_الإجابة","الحالة","ترتيب_العرض","تاريخ_الإنشاء","معرف_الفرع","اسم_الفرع","ملاحظات"]},
        {"name": "السجلات", "cols": ["bot_id","type","message","time"], "color": {"red": 0.93, "green": 0.93, "blue": 0.93}},
        {"name": "_meta", "cols": ["key", "value", "updated_at"], "color": {"red": 1, "green": 0.8, "blue": 0.8}}, 
        {"name": "المدربين", "cols": ["ID_المدرب", "اسم_المدرب", "التخصص", "رقم_الهاتف", "البريد_الإلكتروني", "السيرة_الذاتية", "رابط_الصورة", "الحالة", "bot_id", "معرف_الفرع", "اسم_الفرع", "عدد_الدورات_الحالية", "تاريخ_التعاقد", "ملاحظات"], "color": {"red": 0.88, "green": 0.95, "blue": 0.88}}

    ]
    return sheets_config

def setup_bot_factory_database():
    global ss, _ws_cache
    if 'ss' not in globals() or ss is None: connect_to_google()
    all_requests = []
    structures = get_sheets_structure()
    _ws_cache = {ws.title: ws for ws in ss.worksheets()}
    for config in structures:
        try:
            sheet_name = config["name"]
            headers = config["cols"]
            if sheet_name not in _ws_cache:
                worksheet = safe_api_call(ss.add_worksheet, title=sheet_name, rows="500", cols=str(len(headers) + 2))
                _ws_cache[sheet_name] = worksheet
            else:
                worksheet = _ws_cache[sheet_name]
            current_headers = worksheet.row_values(1)
            if set(current_headers) != set(headers):
                if STRICT_SCHEMA:
                    safe_api_call(worksheet.update, '1:1', [headers])
            sheet_id = worksheet.id
            all_requests.extend([
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1}, "cell": {"userEnteredFormat": {"backgroundColor": config.get("color", {"red": 1, "green": 1, "blue": 1}), "textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}}, "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"}},
                {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}}
            ])
            if AUTO_RESIZE and (not current_headers or set(current_headers) != set(headers)):
                safe_api_call(worksheet.columns_auto_resize, 0, len(headers))
        except Exception as e: print(f"❌ خطأ تهيئة {sheet_name}: {e}")
    if all_requests:
        for i in range(0, len(all_requests), BATCH_SIZE):
            safe_api_call(ss.batch_update, {"requests": all_requests[i:i+BATCH_SIZE]})
    update_meta_info()
    return verify_setup(structures)

def update_meta_info():
    try:
        meta_ws = _ws_cache.get("_meta")
        if meta_ws:
            meta_ws.clear()
            meta_data = [["key", "value", "updated_at"], ["version", SCHEMA_VERSION, datetime.now().isoformat()], ["engine_status", "HEALTHY", datetime.now().isoformat()]]
            safe_api_call(meta_ws.update, 'A1', meta_data)
    except Exception as e: print(f"❌ فشل ميتا: {e}")

def verify_setup(structures):
    for config in structures:
        ws = _ws_cache.get(config["name"])
        if not ws or set(ws.row_values(1)) != set(config["cols"]): return False
    return True
# --------------------------------------------------------------------------
def add_new_category(bot_token, cat_id, cat_name):
    """إضافة قسم جديد باستخدام المتغير departments_sheet"""
    try:
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # التأكد أن المتغير ليس None
        if departments_sheet is not None:
            # إضافة: التوكن، المعرف، الاسم، التاريخ
            departments_sheet.append_row([bot_token, cat_id, cat_name, current_date])
            return True
        return False
    except Exception as e:
        print(f"❌ Error in add_new_category: {e}")
        return False

def get_all_categories(bot_token):
    """جلب الأقسام باستخدام المتغير departments_sheet"""
    try:
        if departments_sheet is None:
            return []
            
        all_rows = departments_sheet.get_all_values()
        categories = []
        for row in all_rows[1:]: # تخطي العنوان
            if row[0] == bot_token:
                categories.append({
                    "id": row[1],
                    "name": row[2]
                })
        return categories
    except Exception as e:
        print(f"❌ Error in get_all_categories: {e}")
        return []
#دالة حذف القسم والبحث 
def delete_category_by_id(bot_token, cat_id):
    """حذف صف القسم من جوجل شيت بناءً على ID القسم والتوكن"""
    try:
        if departments_sheet is None: return False
        
        all_rows = departments_sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # التأكد من مطابقة التوكن (العمود 1) والـ ID (العمود 2)
            if row[0] == bot_token and row[1] == cat_id:
                # i+1 لأن جوجل شيت يبدأ العد من 1 وليس 0
                departments_sheet.delete_rows(i + 1)
                return True
        return False
    except Exception as e:
        print(f"❌ Error in delete_category: {e}")
        return False
 # دالة تبحث عن الـ ID وتقوم بتغيير الاسم في ذلك الصف
def update_category_name(bot_token, cat_id, new_name):
    """تحديث اسم قسم موجود في جوجل شيت"""
    try:
        if departments_sheet is None: return False
        
        all_rows = departments_sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # العمود 1 توكن، العمود 2 ID
            if row[0] == bot_token and row[1] == cat_id:
                # تحديث العمود الثالث (Index 3 في الشيت يبدأ من 1)
                departments_sheet.update_cell(i + 1, 3, new_name)
                return True
        return False
    except Exception as e:
        print(f"❌ Error in update_category_name: {e}")
        return False

# --------------------------------------------------------------------------

#دالة اضافة الدورات_التدريبية
def add_new_course(bot_token, course_id, name, hours, start_date, end_date, c_type, price, limit, reqs, rep_name, rep_code, campaign, coach_user, coach_id, coach_name, cat_id):
    """إضافة دورة كاملة مع إضافة 'معرف القسم' في العمود رقم 17 لضمان الربط"""
    try:
        if courses_sheet is None: return False
        
        # الترتيب المحدث ليشمل معرف القسم في النهاية:
        row = [
            bot_token,    # 1
            course_id,    # 2
            name,         # 3
            hours,        # 4
            start_date,   # 5
            end_date,     # 6
            c_type,       # 7
            price,        # 8
            limit,        # 9
            reqs,         # 10
            rep_name,     # 11
            rep_code,     # 12
            campaign,     # 13
            coach_user,   # 14
            coach_id,     # 15
            coach_name,   # 16
            cat_id        # 17. معرف_القسم (تمت إضافته هنا)
        ]
        
        courses_sheet.append_row(row)
        return True
    except Exception as e:
        print(f"❌ Error in add_new_course: {e}")
        return False



def get_courses_by_category(bot_token, cat_id):
    """جلب كافة الدورات المرتبطة بقسم محدد بناءً على ID القسم المخزن في الشيت"""
    try:
        if courses_sheet is None: return []
        all_rows = courses_sheet.get_all_values()
        courses = []
        for row in all_rows[1:]:
            # في نظامك الجديد، سنبحث عن ID القسم (غالباً يكون في عمود إضافي أو ضمن البيانات)
            # إذا كنت تضع ID القسم في العمود 15 (Index 14) كما فعلنا سابقاً:
            if len(row) >= 15 and row[0] == bot_token and row[14] == cat_id:
                courses.append({
                    "id": row[1],    # معرف الدورة
                    "name": row[2]   # اسم الدورة
                })
        return courses
    except Exception as e:
        print(f"❌ Error fetching courses: {e}")
        return []

def delete_course_by_id(bot_token, course_id):
    """حذف صف دورة محددة من الشيت بناءً على معرف الدورة والتوكن لضمان الدقة وعدم تداخل البيانات"""
    try:
        if courses_sheet is None: return False
        all_rows = courses_sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # التحقق من مطابقة التوكن (العمود 1) ومعرف الدورة (العمود 2)
            if len(row) >= 2 and row[0] == bot_token and row[1] == course_id:
                # i + 1 لأن ترقيم جوجل شيت يبدأ من 1 وليس 0
                courses_sheet.delete_rows(i + 1)
                return True
        return False
    except Exception as e:
        print(f"❌ Error deleting course: {e}")
        return False


# --------------------------------------------------------------------------
def find_user_by_username(bot_token, username):
    """البحث عن بيانات المدرب في شيت المستخدمين باستخدام اليوزرنايم"""
    try:
        # ورقة المستخدمين (تأكد من تسميتها حسب ملفك، سأفترض أنها users_sheet)
        if users_sheet is None: return None
        all_rows = users_sheet.get_all_values()
        search_name = username.replace("@", "").lower()
        
        for row in all_rows[1:]:
            # فحص التوكن واليوزرنايم (العمود 1 والعمود 3 عادةً)
            if row[0] == bot_token and row[2].lower() == search_name:
                return {
                    "id": row[1],   # معرف المستخدم الرقمي
                    "name": row[3] if len(row) > 3 else "مدرب" # الاسم (العمود الرابع)
                }
        return None
    except Exception as e:
        print(f"❌ Error finding user in sheets: {e}")
        return None

# --------------------------------------------------------------------------
#دالة إضافة المدربين
  # تأكد من وجود هذا الاستيراد في بداية الملف

def add_new_coach_advanced(bot_token, coach_id, name, specialty, phone, **kwargs):
    """
    إضافة مدرب جديد لورقة المدربين بنظام متطور.
    kwargs: تتيح لك إرسال قيم اختيارية مثل (email, bio, photo, status, branch_name, notes)
    """
    try:
        if coaches_sheet is None:
            print("⚠️ خطأ: ورقة المدربين غير متصلة.")
            return False

        # 1. التوليد التلقائي لتاريخ اليوم
        today_date = datetime.now().strftime('%Y-%m-%d')

        # 2. تجهيز البيانات مع تنظيفها (strip) ووضع قيم افتراضية ذكية
        # نستخدم kwargs.get لكي نأخذ القيمة إذا أرسلتها، وإلا نضع القيمة الافتراضية
        row = [
            str(coach_id).strip(),                    # 1. ID_المدرب
            str(name).strip(),                        # 2. اسم_المدرب
            str(specialty).strip(),                   # 3. التخصص
            str(phone).strip(),                       # 4. رقم_الهاتف
            kwargs.get('email', "لا يوجد"),           # 5. البريد_الإلكتروني
            kwargs.get('bio', "لا يوجد"),             # 6. السيرة_الذاتية
            kwargs.get('photo', "لا يوجد"),           # 7. رابط_الصورة
            kwargs.get('status', "نشط"),              # 8. الحالة
            str(bot_token),                           # 9. bot_id
            kwargs.get('branch_id', "001"),           # 10. معرف_الفرع
            kwargs.get('branch_name', "الرئيسي"),      # 11. اسم_الفرع
            kwargs.get('courses_count', "0"),         # 12. عدد_الدورات_الحالية
            today_date,                               # 13. تاريخ_التعاقد (تلقائي)
            kwargs.get('notes', "إضافة عبر البوت")      # 14. ملاحظات
        ]

        # 3. إضافة الصف للشيت
        coaches_sheet.append_row(row)
        
        # 4. تسجيل العملية في سجل العمليات (Logging) لزيادة الاحترافية
        print(f"✅ تم تسجيل المدرب {name} بنجاح بتاريخ {today_date}")
        return True

    except Exception as e:
        print(f"❌ خطأ برمي في إضافة المدرب: {e}")
        return False


#جلب بيانات المدربين
def get_all_coaches(bot_token):
    """جلب قائمة المدربين المخصصين لهذا البوت من ورقة المدربين"""
    try:
        # تأكد أن اسم الورقة في المتغير هو coaches_sheet أو جلبها بالاسم
        # coaches_sheet = client.open_by_key(SPREADSHEET_ID).worksheet("المدربين")
        if coaches_sheet is None: return []
        all_rows = coaches_sheet.get_all_values()
        coaches = []
        for row in all_rows[1:]:
            # العمود 9 هو bot_id (Index 8) والعمود 1 هو ID_المدرب (Index 0) والعمود 2 هو الاسم (Index 1)
            if len(row) >= 9 and row[8] == bot_token:
                coaches.append({
                    "id": row[0],    # ID_المدرب
                    "name": row[1]   # اسم_المدرب
                })
        return coaches
    except Exception as e:
        print(f"❌ Error fetching coaches: {e}")
        return []
 
def delete_coach_from_sheet(bot_token, coach_id):
    """حذف مدرب من الشيت بناءً على الـ ID وتوكن البوت"""
    try:
        if coaches_sheet is None: return False
        all_rows = coaches_sheet.get_all_values()
        for i, row in enumerate(all_rows):
            # العمود 1 هو ID_المدرب (Index 0) والعمود 9 هو bot_id (Index 8)
            if len(row) >= 9 and str(row[0]) == str(coach_id) and row[8] == bot_token:
                coaches_sheet.delete_rows(i + 1)
                return True
        return False
    except Exception as e:
        print(f"❌ Error deleting coach: {e}")
        return False

# --------------------------------------------------------------------------
#دالة  الذكاء الاصطناعي 

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------




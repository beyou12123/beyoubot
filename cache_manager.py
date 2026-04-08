import logging
import time
from datetime import datetime
import gspread

# ==========================================================================
# كتلة الإعدادات الأساسية والمحرك العام
# ==========================================================================

DEVELOPER_ID = 873158772  # معرف المطور الثابت
logger = logging.getLogger(__name__)

# المتغيرات الخاصة بالهروب من الـ API (المزامنة الصامتة)
LAST_CHECK_TIME = 0       # تخزين وقت آخر فحص قام به السيرفر لجوجل شيت
CHECK_INTERVAL = 900      # المدة الزمنية للفحص التلقائي (900 ثانية = 15 دقيقة)

# مستودع الذاكرة المركزية للمصنع كامل (RAM)
FACTORY_GLOBAL_CACHE = {
    "data": {},      # سيحتوي على بيانات الـ 37 ورقة كاملة للمصنع
    "versions": {}   # سيحتوي على أرقام الإصدارات لكل bot_id
}

# ــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ

def get_system_time():
    """جلب الوقت الحالي بتنسيق (سنة-شهر-يوم ساعة:دقيقة:ثانية) للتوثيق في الشيت"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ

def ensure_bot_sync_row(bot_id, owner_id=None, developer_id=None):
    """
    الوظيفة: إضافة صف جديد للبوت في ورقة 'نظام_المزامنة' عند الصنع لأول مرة.
    المكان: تُستدعى من دالة save_bot في sheets.py.
    """
    # استيراد محلي لتجنب الخطأ الدائري
    from sheets import ss, safe_api_call

    try:
        # الاتصال بورقة نظام_المزامنة المخصصة للتحكم في الكاش
        try:
            sync_sheet = ss.worksheet("نظام_المزامنة")
        except:
            logger.error("❌ ورقة 'نظام_المزامنة' غير موجودة في ملف جوجل شيت!")
            return False

        # التحقق من وجود البوت مسبقاً في العمود الأول (ID البوت) لمنع تكرار الصفوف
        cell = None
        try:
            cell = sync_sheet.find(str(bot_id), in_column=1)
        except:
            pass

        if not cell:
            # بناء المصفوفة الخاصة بالصف الجديد للمصنع
            # الترتيب: [bot_id, رقم_الإصدار, آخر_تحديث, الحالة, ID_المالك, ID_المطور]
            new_row = [
                str(bot_id),            # معرف البوت (التوكن)
                1,                      # بداية الإصدار من الرقم 1
                get_system_time(),      # توقيت التسجيل في النظام
                "نشط",                  # حالة المزامنة
                str(owner_id) if owner_id else "",   # صاحب البوت
                str(DEVELOPER_ID)       # معرف المطور الثابت
            ]
            
            # تنفيذ الإضافة الفعلية لضمان تسجيل البوت في محرك المزامنة
            safe_api_call(sync_sheet.append_row, new_row)
            print(f"✅ [نظام المزامنة]: تم تسجيل البوت الجديد {bot_id} بنجاح.")
            return True
        else:
            # إذا كان البوت موجوداً، لا يتم إضافة صف جديد حفاظاً على نظافة البيانات
            print(f"ℹ️ [نظام المزامنة]: البوت {bot_id} مسجل مسبقاً في النظام.")
            return True

    except Exception as e:
        print(f"❌ خطأ في إضافة صف المزامنة: {e}")
        return False

# ==========================================================================
# كتلة محرك السحب الشامل (The Core Fetch Engine)
# ==========================================================================

def fetch_full_factory_data():
    """
    المهمة: سحب بيانات المصنع كاملة (37 ورقة) وتخزينها في الرام.
    هذه الدالة هي المسؤولة عن ملء مستودع FACTORY_GLOBAL_CACHE بالبيانات الحقيقية.
    """
    # استيراد محلي لتجنب الخطأ الدائري
    from sheets import ss, get_sheets_structure

    global FACTORY_GLOBAL_CACHE
    try:
        # جلب الهيكل التنظيمي لكافة أوراق المصنع
        structures = get_sheets_structure()
        print(f"🚀 [المحرك]: بدء عملية المزامنة الشاملة للمصنع ({len(structures)} ورقة)...")

        for config in structures:
            sheet_name = config["name"]
            try:
                sheet = ss.worksheet(sheet_name)
                # جلب كافة السجلات في طلب واحد (Batch Read) لتوفير الـ API
                records = sheet.get_all_records()
                
                # تخزين بيانات الورقة كاملة في الذاكرة المركزية (المصنع كامل)
                FACTORY_GLOBAL_CACHE["data"][sheet_name] = records
                
                print(f"✅ تم سحب ورقة: {sheet_name} | عدد السجلات: {len(records)}")
                
                # تأخير بسيط جداً لحماية الأيبي من الحظر أثناء عملية السحب الضخمة
                time.sleep(0.2) 
            except Exception as e:
                print(f"⚠️ تخطي الورقة {sheet_name} بسبب: {e}")

        # تحديث خريطة الإصدارات من ورقة 'نظام_المزامنة'
        try:
            sync_sheet = ss.worksheet("نظام_المزامنة")
            sync_data = sync_sheet.get_all_records()
            for row in sync_data:
                b_id = str(row.get("bot_id"))
                version = int(row.get("رقم_الإصدار", 1))
                FACTORY_GLOBAL_CACHE["versions"][b_id] = version
        except:
            print("⚠️ تنبيه: تعذر تحديث خريطة الإصدارات من الشيت.")

        print("🎊 [المحرك]: اكتملت المزامنة الشاملة. المصنع كامل الآن في الذاكرة.")
        return True
    except Exception as e:
        print(f"❌ خطأ حرج في المزامنة الشاملة للمصنع: {e}")
        return False

# ــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ

def get_bot_data_from_cache(bot_id, sheet_name):
    """
    جلب البيانات التي تخص بوت معين فقط من الذاكرة المركزية للمصنع.
    تُستخدم هذه الدالة بدلاً من الاتصال المباشر بجوجل شيت لتقليل الضغط.
    """
    # البحث في البيانات المخزنة مسبقاً في الرام لورقة معينة
    all_records = FACTORY_GLOBAL_CACHE["data"].get(sheet_name, [])
    # تصفية الصفوف وإعادة ما يخص هذا البوت فقط بناءً على bot_id
    return [r for r in all_records if str(r.get("bot_id")) == str(bot_id)]

# ==========================================================================
# كتلة الهروب من الـ API (نظام المزامنة الصامتة الذكي)
# ==========================================================================

def smart_sync_check(bot_id):
    """
    الدالة الجوهرية للهروب من كثرة الاتصال بـ API جوجل.
    تعتمد على الذاكرة المحلية للسيرفر ولا تتصل بجوجل إلا عند الضرورة القصوى.
    """
    global LAST_CHECK_TIME
    current_time = time.time()

    # 1. إذا كان البوت له بيانات في الرام ولم تنتهِ مدة الـ 15 دقيقة:
    # نقوم بإرجاع True فوراً (0 طلب API) ليعمل البوت من الرام.
    if bot_id in FACTORY_GLOBAL_CACHE["versions"] and (current_time - LAST_CHECK_TIME) < CHECK_INTERVAL:
        return True

    # 2. في حال انتهاء الوقت أو عدم وجود بيانات (أول تشغيل):
    # نقوم بتحديث وقت الفحص والذهاب لجوجل شيت مرة واحدة فقط للمصنع كامل.
    LAST_CHECK_TIME = current_time
    print(f"🔍 [المزامنة الصامتة]: حان موعد فحص التحديثات من جوجل للمصنع...")
    return fetch_full_factory_data()

# ــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ

def update_global_version(bot_id):
    """
    رفع رقم الإصدار في جوجل شيت عند قيام الأدمن بأي تعديل (إضافة/حذف).
    تُحدث أيضاً الذاكرة المحلية للسيرفر فوراً لضمان الاتساق.
    """
    # استيراد محلي لتجنب الخطأ الدائري
    from sheets import ss

    try:
        sync_sheet = ss.worksheet("نظام_المزامنة")
        cell = sync_sheet.find(str(bot_id), in_column=1)
        
        if cell:
            # جلب الرقم الحالي وزيادته بمقدار 1 ليكون هو "الزناد" للتحديث
            current_version = int(sync_sheet.cell(cell.row, 2).value or 0)
            new_version = current_version + 1
            
            # تحديث الخلية في جوجل شيت (تغيير رقم الإصدار والوقت)
            sync_sheet.update_cell(cell.row, 2, new_version)
            sync_sheet.update_cell(cell.row, 3, get_system_time())
            
            # تحديث الذاكرة المحلية للسيرفر فوراً (Push Update) ليعرف السيرفر بالتغيير
            FACTORY_GLOBAL_CACHE["versions"][str(bot_id)] = new_version
            
            print(f"🔄 [نظام المزامنة]: تم رفع إصدار البوت {bot_id} إلى {new_version}")
            return new_version
    except Exception as e:
        print(f"❌ فشل رفع رقم الإصدار العالمي: {e}")
        return None


# تحميل الكاش

async def download_bot_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة تسمح للمطور بتحميل ملف الكاش المحلي (المرآة) لأي بوت"""
    if update.effective_user.id != ADMIN_ID: return

    # نتحقق إذا كان المطور أرسل توكن معين أو يريد كاش المصنع
    query = update.callback_query
    await query.answer()
    
    # مسار مجلد الكاش (تأكد أن هذا هو المسار المستخدم في cache_manager)
    cache_dir = "./cache" 
    
    if not os.path.exists(cache_dir):
        await query.edit_message_text("❌ لا يوجد مجلد كاش حالياً في السيرفر.")
        return

    # جلب قائمة الملفات الموجودة في الكاش
    files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
    
    if not files:
        await query.edit_message_text("❌ مجلد الكاش فارغ، لا توجد مرآة حالياً.")
        return

    await query.edit_message_text(f"⏳ جاري تحضير {len(files)} ملفات كاش للإرسال...")

    for file_name in files:
        file_path = os.path.join(cache_dir, file_name)
        try:
            with open(file_path, 'rb') as doc:
                await context.bot.send_document(
                    chat_id=ADMIN_ID,
                    document=doc,
                    filename=file_name,
                    caption=f"📄 نسخة المرآة لـ: {file_name}"
                )
        except Exception as e:
            print(f"❌ خطأ في إرسال ملف {file_name}: {e}")
 
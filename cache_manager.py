import logging
import time
import json
import os
import asyncio
from datetime import datetime
import gspread

# ==========================================================================
# 1. كتلة الإعدادات الأساسية والمحرك العام (المفاتيح الأصلية)
# ==========================================================================

DEVELOPER_ID = 873158772  # معرف المطور الثابت
logger = logging.getLogger(__name__)

# المتغيرات الخاصة بالهروب من الـ API (المزامنة الصامتة)
LAST_CHECK_TIME = 0       
CHECK_INTERVAL = 900      # 15 دقيقة

# مسارات الحفظ الفيزيائي (المرآة) لضمان بقاء البيانات وتمكين التحميل
CACHE_DIR = "./cache_data"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# مستودع الذاكرة المركزية للمصنع كامل (RAM)
FACTORY_GLOBAL_CACHE = {
    "data": {},      # بيانات الـ 37 ورقة
    "versions": {}   # أرقام الإصدارات
}

# ==========================================================================
# 2. دوال الوقت والنظام
# ==========================================================================

def get_system_time():
    """جلب الوقت الحالي بتنسيق التوثيق المعتمد"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def save_cache_to_disk():
    """
    محرك الحفظ الفيزيائي: يحول بيانات الرام إلى ملفات JSON حقيقية.
    هذه الدالة هي التي تجعل عملية 'التحميل' ممكنة من البوت.
    """
    try:
        if not FACTORY_GLOBAL_CACHE["data"]:
            logger.warning("⚠️ محاولة حفظ كاش فارغ على القرص، تم الإلغاء.")
            return

        for sheet_name, records in FACTORY_GLOBAL_CACHE["data"].items():
            file_path = os.path.join(CACHE_DIR, f"{sheet_name}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=4)
        
        # حفظ خريطة الإصدارات للرجوع إليها عند إعادة التشغيل
        version_path = os.path.join(CACHE_DIR, "versions_map.json")
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(FACTORY_GLOBAL_CACHE["versions"], f, ensure_ascii=False, indent=4)
            
        logger.info(f"💾 [المرآة]: تم تحديث كافة ملفات الكاش على القرص بنجاح.")
    except Exception as e:
        logger.error(f"❌ خطأ حرج أثناء الكتابة على القرص: {e}")

# ==========================================================================
# 3. إدارة نظام المزامنة (Core Logic)
# ==========================================================================

def ensure_bot_sync_row(bot_id, owner_id=None, developer_id=None):
    """إضافة صف جديد للبوت في ورقة 'نظام_المزامنة'"""
    from sheets import ss, safe_api_call

    try:
        try:
            sync_sheet = ss.worksheet("نظام_المزامنة")
        except:
            logger.error("❌ ورقة 'نظام_المزامنة' مفقودة من الملف!")
            return False

        cell = None
        try:
            cell = sync_sheet.find(str(bot_id), in_column=1)
        except: pass

        if not cell:
            # الترتيب: [bot_id, رقم_الإصدار, آخر_تحديث, الحالة, ID_المالك, ID_المطور]
            new_row = [
                str(bot_id), 1, get_system_time(), "نشط",
                str(owner_id) if owner_id else "", str(DEVELOPER_ID)
            ]
            safe_api_call(sync_sheet.append_row, new_row)
            print(f"✅ [نظام المزامنة]: تم تسجيل البوت {bot_id} بنجاح.")
            return True
        else:
            print(f"ℹ️ [نظام المزامنة]: البوت {bot_id} موجود مسبقاً.")
            return True
    except Exception as e:
        print(f"❌ خطأ في إضافة صف المزامنة: {e}")
        return False

# ==========================================================================
# 4. محرك السحب الشامل المطور (Comprehensive Fetch Engine)
# ==========================================================================

def fetch_full_factory_data():
    """سحب بيانات المصنع كاملة وتحديث الرام والقرص"""
    from sheets import ss, get_sheets_structure

    global FACTORY_GLOBAL_CACHE
    try:
        structures = get_sheets_structure()
        print(f"🚀 [المحرك]: بدء المزامنة الشاملة ({len(structures)} ورقة)...")

        for config in structures:
            sheet_name = config["name"]
            try:
                sheet = ss.worksheet(sheet_name)
                # سحب البيانات في طلب واحد Batch Read
                records = sheet.get_all_records()
                FACTORY_GLOBAL_CACHE["data"][sheet_name] = records
                
                print(f"✅ سحب: {sheet_name} | سجلات: {len(records)}")
                time.sleep(0.3) # حماية API جوجل
            except Exception as e:
                logger.warning(f"⚠️ تخطي الورقة {sheet_name}: {e}")

        # تحديث الإصدارات
        try:
            sync_sheet = ss.worksheet("نظام_المزامنة")
            sync_data = sync_sheet.get_all_records()
            for row in sync_data:
                b_id = str(row.get("bot_id"))
                FACTORY_GLOBAL_CACHE["versions"][b_id] = int(row.get("رقم_الإصدار", 1))
        except:
            print("⚠️ تعذر جلب الإصدارات.")

        # تنفيذ الحفظ الفيزيائي فور انتهاء السحب
        save_cache_to_disk()

        print("🎊 [المحرك]: اكتملت المزامنة الشاملة (رام + قرص).")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ حرج في المزامنة: {e}")
        return False

# ==========================================================================
# 5. دوال الواجهة (API Interface)
# ==========================================================================

def get_bot_data_from_cache(bot_id, sheet_name):
    """جلب بيانات بوت معين من الذاكرة المركزية"""
    all_records = FACTORY_GLOBAL_CACHE["data"].get(sheet_name, [])
    return [r for r in all_records if str(r.get("bot_id")) == str(bot_id)]

def smart_sync_check(bot_id):
    """المزامنة الصامتة للهروب من قيود API جوجل"""
    global LAST_CHECK_TIME
    current_time = time.time()

    # فحص الوقت والوجود في الذاكرة
    if bot_id in FACTORY_GLOBAL_CACHE["versions"] and (current_time - LAST_CHECK_TIME) < CHECK_INTERVAL:
        return True

    LAST_CHECK_TIME = current_time
    print(f"🔍 [المزامنة الصامتة]: تحديث بيانات المصنع...")
    return fetch_full_factory_data()

def update_global_version(bot_id):
    """رفع رقم الإصدار وتحديث المرآة فوراً"""
    from sheets import ss
    try:
        sync_sheet = ss.worksheet("نظام_المزامنة")
        cell = sync_sheet.find(str(bot_id), in_column=1)
        
        if cell:
            current_v = int(sync_sheet.cell(cell.row, 2).value or 0)
            new_v = current_v + 1
            
            sync_sheet.update_cell(cell.row, 2, new_v)
            sync_sheet.update_cell(cell.row, 3, get_system_time())
            
            FACTORY_GLOBAL_CACHE["versions"][str(bot_id)] = new_v
            
            # تحديث القرص لضمان أن 'التحميل' سيعطي أحدث نسخة
            save_cache_to_disk()
            
            print(f"🔄 [نظام المزامنة]: الإصدار الجديد لـ {bot_id} هو {new_v}")
            return new_v
    except Exception as e:
        logger.error(f"❌ فشل رفع الإصدار: {e}")
        return None

# ==========================================================================
# 6. دالة التحميل الذكي (تُستدعى من main.py)
# ==========================================================================

async def download_mirror_files(bot, admin_id):
    """
    إرسال ملفات الكاش الفيزيائية من مجلد السيرفر إلى المطور عبر البوت.
    تستخدم asyncio لضمان عدم توقف المحرك أثناء الإرسال.
    """
    if not os.path.exists(CACHE_DIR):
        await bot.send_message(chat_id=admin_id, text="❌ مجلد المرآة غير موجود في السيرفر.")
        return

    files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
    if not files:
        await bot.send_message(chat_id=admin_id, text="⚠️ لا توجد ملفات كاش جاهزة للتحميل حالياً.")
        return

    await bot.send_message(chat_id=admin_id, text=f"📥 جاري جلب {len(files)} ملف من مرآة السيرفر...")

    for file_name in files:
        file_path = os.path.join(CACHE_DIR, file_name)
        try:
            with open(file_path, 'rb') as doc:
                await bot.send_document(
                    chat_id=admin_id,
                    document=doc,
                    caption=f"📄 ملف المرآة: {file_name}\n⏰ توقيت السحب: {get_system_time()}"
                )
            await asyncio.sleep(0.5) # تجنب الحظر عند إرسال ملفات كثيرة
        except Exception as e:
            logger.error(f"❌ فشل إرسال ملف {file_name}: {e}")

# ==========================================================================
# نهاية الملف - تم الحفاظ على كافة المفاتيح والهيكل الأصلي للمصنع
# ==========================================================================

import logging
import time
import json
import os
import asyncio
from datetime import datetime
import gspread
import base64
# ==========================================================================
# 1. كتلة الإعدادات الأساسية والمحرك العام (المفاتيح الأصلية)
# ==========================================================================

DEVELOPER_ID = 873158772  # معرف المطور الثابت
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache_data")

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
    print(f"📁 تم إنشاء مجلد الكاش في المسار: {CACHE_DIR}")

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
    "temp_registration_tokens": {} # تخزين روابط الموظفين والمدربين الموّلدة لحظياً
   
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


# انشاء نسخة مشفرة



def generate_secure_backup(bot_id=None):
    """إنشاء نسخة احتياطية مشفرة: للمطور (الكل) أو للعميل (خاص ببوت معين)"""
    try:
        # إذا كان bot_id موجود، نسحب بياناته فقط، وإذا لم يوجد (مطور) نسحب الكل
        data_to_save = {}
        if bot_id:
            for sheet_name, records in FACTORY_GLOBAL_CACHE["data"].items():
                filtered = [r for r in records if str(r.get("bot_id")) == str(bot_id)]
                if filtered: data_to_save[sheet_name] = filtered
        else:
            data_to_save = FACTORY_GLOBAL_CACHE["data"]

        # تحويل البيانات إلى نص مشفر Base64 لضمان قبول الاستضافة وسهولة الرفع
        json_string = json.dumps(data_to_save, ensure_ascii=False, indent=2)
        encoded_data = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
        
        backup_content = {
            "backup_info": {
                "type": "FULL" if not bot_id else "CLIENT",
                "bot_id": bot_id,
                "timestamp": get_system_time()
            },
            "payload": encoded_data
        }
        
        file_path = os.path.join(CACHE_DIR, f"backup_{bot_id if bot_id else 'MASTER'}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(backup_content, f, ensure_ascii=False, indent=4)
        return file_path
    except Exception as e:
        logger.error(f"❌ خطأ في تشفير النسخة: {e}")
        return None
 



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
    """سحب بيانات المصنع كاملة وتحديث الرام والقرص مع ضمان الحفظ الفوري لكل ورقة"""
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
                
                # --- [ التصحيح الجذري: الحفظ الفيزيائي الفوري لكل ورقة ] ---
                # نضمن هنا كتابة الملف على القرص فور سحبه لضمان وجوده للتحميل
                try:
                    file_path = os.path.join(CACHE_DIR, f"{sheet_name}.json")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(records, f, ensure_ascii=False, indent=4)
                    print(f"✅ سحب وحفظ: {sheet_name} | سجلات: {len(records)}")
                except Exception as disk_err:
                    print(f"⚠️ فشل الكتابة الفيزيائية للورقة {sheet_name}: {disk_err}")
                
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

        # تنفيذ الحفظ الفيزيائي الشامل (للمراجعة النهائية وخريطة الإصدارات)
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
# --------------------------------------------------------------------------
def update_global_version(bot_id):
    """تحديث الإصدار في نظام_المزامنة باستخدام المطابقة المباشرة للمصفوفة لضمان الدقة"""
    from sheets import ss, safe_api_call
    try:
        # التأكد من الاتصال
        if 'ss' not in globals() or ss is None:
            from sheets import connect_to_google
            connect_to_google()

        sync_sheet = ss.worksheet("نظام_المزامنة")
        # جلب العمود الأول بالكامل (معرفات البوتات) لضمان المطابقة النصية الدقيقة
        all_ids = sync_sheet.col_values(1)
        
        search_id = str(bot_id).strip()
        target_row = None

        # البحث عن الصف المناسب بمطابقة النص حرفياً لتجنب مشاكل التنسيق في شيت
        for index, row_id in enumerate(all_ids):
            if str(row_id).strip() == search_id:
                target_row = index + 1
                break

        # تعريف الوقت الحالي في أعلى الكتلة لاستخدامه في الحالتين (تحديث أو إضافة)
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if target_row:
            # جلب القيمة الحالية من الخلية مباشرة للتأكد من الرقم الأخير
            current_val = sync_sheet.cell(target_row, 2).value
            try:
                current_v = int(current_val) if current_val else 0
            except:
                current_v = 0
                
            new_v = current_v + 1

            # تحديث الخلايا في جوجل شيت باستخدام الوسيط الآمن safe_api_call لمنع الحظر
            safe_api_call(sync_sheet.update_cell, target_row, 2, new_v)
            safe_api_call(sync_sheet.update_cell, target_row, 3, now_time)

            # تحديث الذاكرة المركزية RAM لضمان استجابة البوت الفورية بالبيانات الجديدة
            FACTORY_GLOBAL_CACHE["versions"][search_id] = new_v
            
            # حفظ الكاش فيزيائياً على القرص لضمان بقاء البيانات عند إعادة التشغيل
            save_cache_to_disk()

            print(f"🔄 [نظام المزامنة]: تم تحديث التوكن بنجاح في الصف {target_row} إلى الإصدار {new_v}")
            return new_v
        else:
            # 🆕 التسجيل التلقائي: إذا لم يجد التوكن يقوم بإضافته فوراً في نظام المزامنة
            # الترتيب المعتمد: [bot_id, رقم_الإصدار, آخر_تحديث, الحالة, ID_المالك, ID_المطور]
            new_row = [search_id, 1, now_time, "نشط", "تلقائي", str(DEVELOPER_ID)]
            safe_api_call(sync_sheet.append_row, new_row)
            
            # تحديث الذاكرة والقرص للبوت الجديد لضمان مزامنته فوراً
            new_v = 1
            FACTORY_GLOBAL_CACHE["versions"][search_id] = new_v
            save_cache_to_disk()
            
            print(f"✨ [نظام المزامنة]: تم تسجيل توكن جديد تلقائياً: {search_id}")
            return new_v
            
    except Exception as e:
        logger.error(f"❌ فشل رفع الإصدار: {e}")
        return None



# ==========================================================================
# 6. دالة التحميل الذكي (تُستدعى من main.py)
# ==========================================================================
async def download_mirror_files(bot, user_id):
    """إرسال نسخة احتياطية مشفرة وموحدة بناءً على صلاحية المستخدم"""
    # التحقق هل المستخدم مطور أم عميل
    is_developer = (str(user_id) == str(DEVELOPER_ID))
    bot_id_filter = None if is_developer else user_id

    await bot.send_message(chat_id=user_id, text="🔐 جاري تجهيز النسخة الاحتياطية المشفرة...")

    # توليد الملف الموحد المشفر فوراً
    file_path = generate_secure_backup(bot_id_filter)

    if file_path and os.path.exists(file_path):
        try:
            caption = "👑 <b>نسخة المطور الشاملة</b>" if is_developer else "📦 <b>نسخة البوت الخاصة بك</b>"
            caption += f"\n📅 التاريخ: {get_system_time()}\n🛡️ الحالة: مشفرة وقابلة للاستعادة."
            
            with open(file_path, 'rb') as doc:
                await bot.send_document(
                    chat_id=user_id,
                    document=doc,
                    filename=f"BACKUP_{'MASTER' if is_developer else user_id}.json",
                    caption=caption,
                    parse_mode="HTML"
                )
            # حذف الملف المؤقت بعد الإرسال
            os.remove(file_path)
        except Exception as e:
            logger.error(f"❌ فشل إرسال النسخة: {e}")
    else:
        await bot.send_message(chat_id=user_id, text="⚠️ فشل إنشاء النسخة، تأكد من وجود بيانات في الكاش أولاً.")



# --------------------------------------------------------------------------
# دالة الاستعادة 
def process_restore_logic(file_content, requester_id):
    """المحرك الذكي: يقرأ الملف ويقرر نوع الاستبدال (شامل للمطور أو جزئي للعميل)"""
    from sheets import ss
    try:
        # 1. فك التشفير
        backup_data = json.loads(file_content)
        encoded_payload = backup_data.get("payload")
        decoded_data = json.loads(base64.b64decode(encoded_payload).decode('utf-8'))
        
        is_developer = (str(requester_id) == str(DEVELOPER_ID))
        
        # 2. حلقة المزامنة (التنفيذ على السيرفر + جوجل)
        for sheet_name, new_records in decoded_data.items():
            try:
                sheet = ss.worksheet(sheet_name)
                
                if is_developer:
                    # المطور: استبدال شامل للورقة
                    sheet.clear()
                    if new_records:
                        headers = list(new_records[0].keys())
                        rows = [list(r.values()) for r in new_records]
                        sheet.append_row(headers)
                        sheet.append_rows(rows)
                    FACTORY_GLOBAL_CACHE["data"][sheet_name] = new_records
                else:
                    # العميل: استبدال أسطره فقط والحفاظ على البقية
                    current_records = FACTORY_GLOBAL_CACHE["data"].get(sheet_name, [])
                    # حذف أسطر العميل القديمة وإضافة الجديدة
                    updated_list = [r for r in current_records if str(r.get("bot_id")) != str(requester_id)]
                    updated_list.extend(new_records)
                    
                    # رفع القائمة المحدثة لجوجل (تحديث ذكي)
                    sheet.clear()
                    if updated_list:
                        headers = list(updated_list[0].keys())
                        rows = [list(r.values()) for r in updated_list]
                        sheet.append_row(headers)
                        sheet.append_rows(rows)
                    
                    FACTORY_GLOBAL_CACHE["data"][sheet_name] = updated_list

                # تحديث ملف الكاش الفيزيائي (JSON) لكل ورقة
                file_path = os.path.join(CACHE_DIR, f"{sheet_name}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(FACTORY_GLOBAL_CACHE["data"][sheet_name], f, ensure_ascii=False, indent=4)

            except Exception as e:
                print(f"⚠️ خطأ أثناء معالجة الورقة {sheet_name}: {e}")
        
        save_cache_to_disk() # حفظ نهائي
        return True
    except Exception as e:
        print(f"❌ خطأ حرج في محرك الاستعادة: {e}")
        return False
 



# ==========================================================================
# نهاية الملف - تم الحفاظ على كافة المفاتيح والهيكل الأصلي للمصنع
# ==========================================================================

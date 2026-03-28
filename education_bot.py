import json
import os
import logging
import asyncio
import re
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)

# --- [إعدادات وقواعد بيانات الموديول - مدمجة لضمان الاستقلالية] ---
DB_FILE = "db.json"

def load_db():
    """تحميل قاعدة البيانات المحلية للموديول"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    # هيكل افتراضي في حال عدم وجود الملف
    return {
        "users": [], 
        "admins": [], 
        "categories": [], 
        "courses": [], 
        "registrations": [], 
        "promo_codes": {}
    }

def save_db(db):
    """حفظ قاعدة البيانات المحلية للموديول"""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

# محاولة استيراد الربط مع جوجل (تأكد من وجود google_services.py بجانب main.py)
try:
    from config import *
    from google_services import SHEET_CATS, SHEET_REGS, SHEET_COURSES, SHEET_PROMO_CODES
except:
    # قيم احتياطية لضمان عدم توقف الكود عند الاستيراد
    DEV_ID = 873158772
    pass

# إعداد logging لتتبع العمليات الإدارية بدقة
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- تعريف الثوابت لضمان عدم التداخل مع المصنع ---
(
    GET_ADMIN_ID_TO_ADD, GET_ADMIN_ID_TO_REMOVE, GET_BROADCAST_MESSAGE,
    ADD_CATEGORY_NAME, DELETE_CATEGORY_CONFIRM, CONFIRM_FINAL_DELETE,
    ADD_COURSE_NAME, ADD_COURSE_DESC, ADD_COURSE_PRICE, ADD_COURSE_CAT,
    GET_ACCEPT_MESSAGE, GET_REJECT_MESSAGE, GET_BACKUP_FILE,
    GET_PROMO_NAME, GET_PROMO_PERCENT
) = range(100, 115)

# --------------------------------------------------------------------------
# --- [قسم الربط مع المصنع - مداخل المحرك الديناميكي] ---
# --------------------------------------------------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة الانطلاق الرئيسية للمنصة التعليمية"""
    user = update.effective_user
    db = load_db()
    
    if user.id not in db.get("users", []):
        db["users"].append(user.id)
        save_db(db)

    welcome_text = (
        f"🎓 **مرحباً بك في المنصة التعليمية**\n\n"
        f"يمكنك من خلال هذا البوت تصفح الأقسام والدورات التدريبية المتاحة والتسجيل فيها مباشرة."
    )
    
    keyboard = [
        [InlineKeyboardButton("📚 تصفح الأقسام", callback_data="dev_categories")],
        [InlineKeyboardButton("👤 حسابي التعليمي", callback_data="my_account")]
    ]
    
    owner_id = context.bot_data.get("owner_id")
    if user.id == owner_id or user.id in db.get("admins", []):
        keyboard.append([InlineKeyboardButton("🛠 لوحة التحكم (للمسؤول)", callback_data="dev_panel")])
        
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """المعالج المركزي للرسائل لضمان عمل نظام الإيصالات"""
    # في المنصة التعليمية، أي رسالة خارج الأوامر تُعامل كإيصال أو رد
    await handle_receipt(update, context)

# --------------------------------------------------------------------------
# --- 1. دوال عرض لوحات التحكم والقوائم ---
# --------------------------------------------------------------------------

async def show_dev_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    user_id = update.effective_user.id
    owner_id = context.bot_data.get("owner_id")
    
    if user_id not in db["admins"] and user_id != owner_id:
        await query.edit_message_text("عذرًا، أنت لست مديرًا.")
        return

    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات", callback_data="dev_stats")],
        [InlineKeyboardButton("👤 إدارة المستخدمين", callback_data="dev_users")],
        [InlineKeyboardButton("📚 إدارة الدورات", callback_data="dev_courses")],
        [InlineKeyboardButton("🗂️ إدارة الاقسام", callback_data="dev_categories")],
        [InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="dev_broadcast")],
        [InlineKeyboardButton("🎫 إضافة كود خصم", callback_data="dev_add_promo")],
        [InlineKeyboardButton("📥 تحميل نسخة احتياطية", callback_data="backup_download")],
        [InlineKeyboardButton("📤 رفع نسخة احتياطية", callback_data="backup_upload")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_edu_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("مرحباً بك في لوحة المطور! اختر من القائمة:", reply_markup=reply_markup)

async def show_dev_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    
    num_users = len(db.get("users", []))
    num_courses = len(db.get("courses", []))
    num_admins = len(db.get("admins", []))
    num_pending = len([r for r in db.get("registrations", []) if r["status"] == "pending"])
    num_accepted = len([r for r in db.get("registrations", []) if r["status"] == "accepted"])
    num_rejected = len([r for r in db.get("registrations", []) if r["status"] == "rejected"])

    stats_text = (
        f"**📊 إحصائيات البوت**\n\n"
        f"عدد المستخدمين: {num_users}\n"
        f"عدد الدورات: {num_courses}\n"
        f"عدد المديرين: {num_admins}\n\n"
        f"**إحصائيات التسجيلات:**\n"
        f"طلبات معلقة: {num_pending}\n"
        f"طلبات مقبولة: {num_accepted}\n"
        f"طلبات مرفوضة: {num_rejected}"
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ رجوع", callback_data="dev_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_dev_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مشرف", callback_data="dev_add_admin")],
        [InlineKeyboardButton("➖ إزالة مشرف", callback_data="dev_remove_admin")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="dev_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("اختر عملية إدارة المستخدمين:", reply_markup=reply_markup)

# --- 2. إدارة المشرفين (Admins) ---

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👤 أرسل معرف المستخدم (User ID) الذي تريد منحه صلاحيات الإدارة:")
    return GET_ADMIN_ID_TO_ADD

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_admin_id = int(update.message.text)
        db = load_db()
        if new_admin_id in db["admins"]:
            await update.message.reply_text("⚠️ هذا المستخدم هو مشرف بالفعل.")
            return ConversationHandler.END
        db["admins"].append(new_admin_id)
        save_db(db)
        await update.message.reply_text(f"✅ تم إضافة المستخدم {new_admin_id} كمشرف بنجاح.")
        try:
            await context.bot.send_message(chat_id=new_admin_id, text="✅ تهانينا! لقد تم إضافتك كمدير في البوت.")
        except Exception:
            pass
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ خطأ: أرسل (User ID) بالأرقام فقط.")
        return GET_ADMIN_ID_TO_ADD

async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db = load_db()
    owner_id = context.bot_data.get("owner_id")
    admins_to_remove = [admin for admin in db["admins"] if admin != owner_id]
    if not admins_to_remove:
        await query.edit_message_text("لا يوجد مشرفون لإزالتهم.")
        return ConversationHandler.END
    admin_list = "\n".join([str(a) for a in admins_to_remove])
    await query.edit_message_text(f"أرسل معرف المستخدم (User ID) الذي تريد إزالته:\n\nالمشرفون:\n{admin_list}")
    return GET_ADMIN_ID_TO_REMOVE

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        admin_id_to_remove = int(update.message.text)
        db = load_db()
        owner_id = context.bot_data.get("owner_id")
        if admin_id_to_remove == owner_id:
            await update.message.reply_text("لا يمكنك إزالة المطور الأساسي.")
        elif admin_id_to_remove in db["admins"]:
            db["admins"].remove(admin_id_to_remove)
            save_db(db)
            await update.message.reply_text(f"تم إزالة المستخدم {admin_id_to_remove} من المشرفين.")
        else:
            await update.message.reply_text("هذا المستخدم ليس مشرفًا.")
    except ValueError:
        await update.message.reply_text("الرجاء إرسال رقم صحيح.")
    return ConversationHandler.END

# --- 3. الإرسال الجماعي (Broadcast) ---

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("الرجاء إرسال الرسالة التي تريد إرسالها لجميع المستخدمين:")
    return GET_BROADCAST_MESSAGE

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text
    db = load_db()
    users = db.get("users", [])
    if not users:
        await update.message.reply_text("⚠️ لا يوجد مستخدمون لإرسال الرسالة لهم.")
        return ConversationHandler.END
    success, fail = 0, 0
    status_msg = await update.message.reply_text("⏳ جاري بدء الإرسال الجماعي...")
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=int(user_id), text=message_text, parse_mode='Markdown')
            success += 1
            await asyncio.sleep(0.05) 
        except Exception as e:
            if "Flood control exceeded" in str(e): await asyncio.sleep(20)
            fail += 1
    await status_msg.edit_text(f"✅ اكتمل الإرسال\n• نجاح: {success}\n• فشل: {fail}")
    return ConversationHandler.END

# --- 4. إدارة الأقسام (Categories) والربط مع Sheets ---

async def show_manage_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    categories_list = "\n".join([f"- {cat}" for cat in db.get("categories", [])]) if db.get("categories") else "لا توجد أقسام."
    keyboard = [
        [InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="dev_add_cat")],
        [InlineKeyboardButton("🗑️ حذف قسم", callback_data="dev_delete_cat")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="dev_panel")]
    ]
    await query.edit_message_text(f"**🗂️ إدارة الاقسام**\n\n{categories_list}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def add_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("الرجاء إرسال اسم القسم الجديد:")
    return ADD_CATEGORY_NAME

async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category_name = update.message.text
    try:
        from google_services import SHEET_CATS
        all_data = SHEET_CATS.get_all_values()
        new_id = len(all_data) 
        current_date = datetime.now().strftime("%Y-%m-%d")
        SHEET_CATS.append_row([new_id, category_name, "", "", "", current_date])
        db = load_db()
        if category_name not in db["categories"]:
            db["categories"].append(category_name)
            save_db(db)
        await update.message.reply_text(f"✅ تم إضافة القسم بنجاح: {category_name}")
    except Exception as e:
        await update.message.reply_text(f"❌ تم الحفظ محلياً (فشل مزامنة الشيت): {str(e)}")
        db = load_db()
        if category_name not in db["categories"]:
            db["categories"].append(category_name)
            save_db(db)
    return ConversationHandler.END

async def delete_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db = load_db()
    if not db.get("categories"):
        await query.edit_message_text("لا توجد أقسام لحذفها.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"del_cat_confirm_{cat}")] for cat in db["categories"]]
    keyboard.append([InlineKeyboardButton("⬅️ إلغاء", callback_data="dev_categories")])
    await query.edit_message_text("اختر القسم الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DELETE_CATEGORY_CONFIRM

async def confirm_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat_name = query.data.split("del_cat_confirm_")[1]
    context.user_data["temp_category_name"] = cat_name
    keyboard = [
        [InlineKeyboardButton("🗑️ حذف القسم فقط", callback_data="delete_cat_only"),
         InlineKeyboardButton("🔥 حذف القسم والدورات", callback_data="delete_cat_with_courses")],
        [InlineKeyboardButton("⬅️ إلغاء", callback_data="dev_categories")]
    ]
    await query.edit_message_text(f"⚠️ أنت تحذف القسم: **{cat_name}**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CONFIRM_FINAL_DELETE

async def execute_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data
    cat_name = context.user_data.pop("temp_category_name")
    db = load_db()
    if choice == "delete_cat_with_courses":
        db["courses"] = [c for c in db.get("courses", []) if c.get("category") != cat_name]
    if cat_name in db["categories"]:
        db["categories"].remove(cat_name)
    save_db(db)
    await query.edit_message_text(f"✅ تم حذف القسم بنجاح.")
    return ConversationHandler.END

# --- 5. إدارة الدورات (Courses) والربط مع Sheets ---

async def show_manage_courses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    courses_list = "".join([f"- {'✅' if c.get('active') else '❌'} {c['name']} (ID: {c['id']})\n" for c in db.get("courses", [])]) if db.get("courses") else "لا توجد دورات."
    keyboard = [
        [InlineKeyboardButton("➕ إضافة دورة", callback_data="dev_add_course"), InlineKeyboardButton("🗑️ حذف دورة", callback_data="dev_delete_course")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="dev_panel")]
    ]
    await query.edit_message_text(f"**📚 إدارة الدورات**\n\n{courses_list}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def add_course_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("الرجاء إدخال **اسم الدورة**:")
    return ADD_COURSE_NAME

async def add_course_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["temp_course_data"] = {"name": update.message.text}
    await update.message.reply_text("أدخل **وصف الدورة**:")
    return ADD_COURSE_DESC

async def add_course_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["temp_course_data"]["description"] = update.message.text
    await update.message.reply_text("أدخل **سعر الدورة** (أرقام فقط):")
    return ADD_COURSE_PRICE

async def add_course_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = float(update.message.text)
        context.user_data["temp_course_data"]["price"] = price
        db = load_db()
        if not db.get("categories"):
            await update.message.reply_text("لا توجد أقسام، أضف قسماً أولاً.")
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"select_cat_{cat}")] for cat in db["categories"]]
        await update.message.reply_text("اختر **قسم الدورة**:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ADD_COURSE_CAT
    except:
        await update.message.reply_text("الرجاء إدخال رقم صحيح.")
        return ADD_COURSE_PRICE

async def add_course_cat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    category = query.data.split("select_cat_")[1]
    temp_data = context.user_data.pop("temp_course_data")
    db = load_db()
    new_id = max([c["id"] for c in db.get("courses", [])] + [0]) + 1
    
    try:
        from google_services import SHEET_COURSES
        SHEET_COURSES.append_row([new_id, temp_data['name'], "", "", "", "", temp_data['price']])
    except: pass

    temp_data.update({"id": new_id, "category": category, "active": True})
    db["courses"].append(temp_data)
    save_db(db)
    await query.edit_message_text(f"✅ تم إضافة الدورة بنجاح.")
    return ConversationHandler.END

# --- 6. معالجة التسجيلات والإيصالات ---

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db = load_db()
    reg = next((r for r in db.get("registrations", []) if r["user_id"] == user_id and r["status"] == "accepted" and r.get("receipt") is None), None)
    if not reg: return
    
    owner_id = context.bot_data.get("owner_id")
    caption = f"💰 إيصال دفع جديد!\nالطالب: {reg.get('name')}\nالايدي: `{user_id}`"
    
    if update.message.photo:
        fid = update.message.photo[-1].file_id
        reg["receipt"] = f"صورة: {fid}"
        await context.bot.send_photo(chat_id=owner_id, photo=fid, caption=caption)
    elif update.message.document:
        fid = update.message.document.file_id
        reg["receipt"] = f"ملف: {fid}"
        await context.bot.send_document(chat_id=owner_id, document=fid, caption=caption)
    
    save_db(db)
    await update.message.reply_text("✅ تم استلام الإيصال وجاري المراجعة.")

# --- 7. محرك المزامنة العميقة (Deep Sync Engine) ---

async def sync_backup_to_sheets(data):
    try:
        from google_services import SHEET_CATS, SHEET_COURSES, SHEET_REGS
        # مزامنة الأقسام
        rows_cats = len(SHEET_CATS.get_all_values())
        if rows_cats > 1: SHEET_CATS.delete_rows(2, rows_cats)
        cat_rows = [[i+1, name, "", "", "", datetime.now().strftime("%Y-%m-%d")] for i, name in enumerate(data.get("categories", []))]
        if cat_rows: SHEET_CATS.append_rows(cat_rows)
        # مزامنة الدورات
        rows_courses = len(SHEET_COURSES.get_all_values())
        if rows_courses > 1: SHEET_COURSES.delete_rows(2, rows_courses)
        course_rows = [[c["id"], c["name"], "", "", "", "", c["price"]] for c in data.get("courses", [])]
        if course_rows: SHEET_COURSES.append_rows(course_rows)
        return True
    except Exception as e:
        print(f"خطأ مزامنة: {e}")
        return False

async def download_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if os.path.exists(DB_FILE):
        await context.bot.send_document(chat_id=update.effective_user.id, document=open(DB_FILE, 'rb'), filename="edu_db_backup.json")

async def upload_backup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.edit_message_text("أرسل ملف `db.json` الجديد:")
    return GET_BACKUP_FILE

async def receive_backup_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    document = update.message.document
    if not document.file_name.endswith('.json'):
        await update.message.reply_text("❌ أرسل ملف .json فقط.")
        return GET_BACKUP_FILE
    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(DB_FILE)
    await update.message.reply_text("✅ تم رفع النسخة الاحتياطية وتحديث النظام.")
    return ConversationHandler.END

# --- 8. إدارة كود الخصم (Promo Codes) ---

async def add_promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.edit_message_text("أرسل اسم الكود (مثال: SAVE50):")
    return GET_PROMO_NAME

async def get_promo_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["temp_promo_name"] = update.message.text.upper()
    await update.message.reply_text("أرسل نسبة الخصم (رقم فقط):")
    return GET_PROMO_PERCENT

async def get_promo_percent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        percent = int(update.message.text)
        db = load_db()
        db["promo_codes"][context.user_data["temp_promo_name"]] = percent
        save_db(db)
        await update.message.reply_text(f"✅ تم تفعيل الكود بنسبة {percent}%")
        return ConversationHandler.END
    except:
        await update.message.reply_text("خطأ! أرسل رقماً صحيحاً.")
        return GET_PROMO_PERCENT

# --- دالة معالجة الـ Callbacks ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    if data == "back_to_edu_main": await start_handler(update, context)
    elif data == "dev_panel": await show_dev_panel(update, context)
    elif data == "dev_stats": await show_dev_stats(update, context)
    elif data == "dev_users": await show_dev_users(update, context)
    elif data == "dev_categories": await show_manage_categories_menu(update, context)
    elif data == "dev_courses": await show_manage_courses_menu(update, context)
    elif data == "backup_download": await download_backup(update, context)
    elif data == "dev_add_cat": return await add_category_start(update, context)
    elif data == "dev_add_course": return await add_course_start(update, context)
    elif data == "dev_broadcast": return await broadcast_start(update, context)

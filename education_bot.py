import json
import os
import logging
import asyncio
import re
import importlib
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

# محاولة الاستيراد مع الحفاظ على استمرارية الكود
try:
    from config import *
    from utils.helpers import load_db, save_db
    from google_services import SHEET_CATS, SHEET_REGS, SHEET_COURSES, SHEET_PROMO_CODES
except Exception as e:
    print(f"⚠️ تنبيه: تعذر تحميل بعض الملفات المساعدة، تأكد من وجودها بجانب main.py: {e}")

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
# --- [قسم الربط مع المصنع - إلزامي للتشغيل] ---
# --------------------------------------------------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة الانطلاق الرئيسية المتوافقة مع محرك المصنع لفتح المنصة التعليمية"""
    user = update.effective_user
    db = load_db()
    
    # تسجيل المستخدم في db.json الخاص بالبوت إذا لم يوجد
    if user.id not in db.get("users", []):
        db["users"].append(user.id)
        save_db(db)

    welcome_text = (
        f"🎓 **مرحباً بك في المنصة التعليمية**\n\n"
        f"يمكنك من خلال هذا البوت تصفح الأقسام والدورات التدريبية المتاحة والتسجيل فيها مباشرة."
    )
    
    keyboard = [
        [InlineKeyboardButton("📚 تصفح الأقسام", callback_data="dev_categories")], # ربط مباشر مع دالتك الأصلية
        [InlineKeyboardButton("👤 حسابي التعليمي", callback_data="my_account")]
    ]
    
    # التحقق من الصلاحية (عبر المالك في المصنع أو قائمة المشرفين في db.json)
    owner_id = context.bot_data.get("owner_id")
    if user.id == owner_id or user.id in db.get("admins", []):
        keyboard.append([InlineKeyboardButton("🛠 لوحة التحكم (للمسؤول)", callback_data="dev_panel")])
        
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """المعالج المركزي للرسائل لضمان عمل نظام الإيصالات الخاص بك"""
    await handle_receipt(update, context)

# --------------------------------------------------------------------------
# --- 1. دوال عرض لوحات التحكم والقوائم (كودك الأصلي كاملاً) ---
# --------------------------------------------------------------------------

async def show_dev_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    user_id = update.effective_user.id
    
    # التحقق من الصلاحية (دعم المالك والمشرفين)
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
        await update.message.reply_text(f"✅ تم إضافة المستخدم {new_admin_id} كمشرف بنجاح.", reply_markup=ReplyKeyboardRemove())
        try:
            await context.bot.send_message(chat_id=new_admin_id, text="✅ تهانينا! لقد تم إضافتك كمدير في البوت.")
        except Exception:
            await update.message.reply_text("💡 تم التفعيل، لكن لم نتمكن من إرسال إشعار للمستخدم.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ خطأ: أرسل (User ID) بالأرقام فقط.\nحاول مرة أخرى أو أرسل /cancel للإلغاء:")
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

# --- 4. إدارة الأقسام (Categories) والربط مع Sheets (9 أعمدة) ---

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
        all_data = SHEET_CATS.get_all_values()
        existing_names = [row[1] for row in all_data if len(row) > 1]
        if category_name in existing_names:
            await update.message.reply_text("❌ هذا القسم موجود بالفعل في جوجل شيت.")
            return ConversationHandler.END
        
        new_id = len(all_data) 
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # ✅ حفظ في جوجل شيت (التاريخ في العمود السادس حسب التأسيس)
        SHEET_CATS.append_row([new_id, category_name, "", "", "", current_date])

        db = load_db()
        if category_name not in db["categories"]:
            db["categories"].append(category_name)
            save_db(db)
        await update.message.reply_text(f"✅ تم إضافة القسم بنجاح: {category_name}", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
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
    await query.edit_message_text(f"⚠️ تنبيه: أنت تحذف القسم: **{cat_name}**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CONFIRM_FINAL_DELETE

async def execute_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data
    cat_name = context.user_data.pop("temp_category_name")
    db = load_db()
    if choice == "delete_cat_with_courses":
        db["courses"] = [c for c in db.get("courses", []) if c["category"] != cat_name]
    if cat_name in db["categories"]:
        db["categories"].remove(cat_name)
        
    save_db(db)
    await query.edit_message_text(f"✅ تم الحذف للقسم: {cat_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ العودة", callback_data="dev_categories")]]))
    return ConversationHandler.END

# --- 5. إدارة الدورات (Courses) والربط مع Sheets (14 عموداً) ---

async def show_manage_courses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    courses_list = "".join([f"- {'✅' if c['active'] else '❌'} {c['name']} (ID: {c['id']})\n" for c in db.get("courses", [])]) if db.get("courses") else "لا توجد دورات."
    keyboard = [
        [InlineKeyboardButton("➕ إضافة دورة جديدة", callback_data="dev_add_course"),InlineKeyboardButton("✏️ تعديل دورة", callback_data="dev_edit_course")],
        [InlineKeyboardButton("➡️ نقل دورة", callback_data="dev_move_course"),InlineKeyboardButton("🗑️ حذف دورة", callback_data="dev_delete_course")],
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
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح للسعر.")
        return ADD_COURSE_PRICE

async def add_course_cat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    category = query.data.split("select_cat_")[1]
    temp_data = context.user_data.pop("temp_course_data", None)
    
    # حساب المعرف وتحديث الشيت والمحلي
    db = load_db()
    new_id = max([c["id"] for c in db.get("courses", [])] + [0]) + 1
    
    # ✅ حفظ في جوجل شيت (السعر في العمود السابع)
    try:
        SHEET_COURSES.append_row([new_id, temp_data['name'], "", "", "", "", temp_data['price']])
    except Exception as e:
        logging.error(f"Sync Error (Course): {e}")

    temp_data.update({"id": new_id, "category": category, "active": True})
    db["courses"].append(temp_data)
    save_db(db)
    await query.edit_message_text(f"✅ تم إضافة الدورة: {temp_data['name']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ العودة", callback_data="dev_courses")]]))
    return ConversationHandler.END

# --- 6. معالجة التسجيلات (قبول/رفض/إيصالات) ---

async def accept_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, u_id, c_id = query.data.split('_')
    context.user_data.update({'temp_reg_user_id': int(u_id), 'temp_reg_course_id': int(c_id)})
    await context.bot.send_message(chat_id=update.effective_user.id, text="أرسل رسالة القبول للمستخدم:")
    return GET_ACCEPT_MESSAGE

async def send_accept_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message.text
    u_id, c_id = context.user_data.pop('temp_reg_user_id'), context.user_data.pop('temp_reg_course_id')
    db = load_db()
    for reg in db.get("registrations", []):
        if reg["user_id"] == u_id and reg["course_id"] == c_id:
            reg["status"] = "accepted"
            break
    save_db(db)
    await context.bot.send_message(chat_id=u_id, text=f"✅ تم قبول طلبك!\n\n{msg}\n\nيرجى إرسال إيصال الدفع.")
    await update.message.reply_text("تم إرسال القبول بنجاح.")
    return ConversationHandler.END

async def reject_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, u_id, c_id = query.data.split('_')
    context.user_data.update({'temp_reg_user_id': int(u_id), 'temp_reg_course_id': int(c_id)})
    await context.bot.send_message(chat_id=update.effective_user.id, text="أرسل رسالة الرفض للمستخدم:")
    return GET_REJECT_MESSAGE

async def send_reject_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message.text
    u_id, c_id = context.user_data.pop('temp_reg_user_id'), context.user_data.pop('temp_reg_course_id')
    db = load_db()
    for reg in db.get("registrations", []):
        if reg["user_id"] == u_id and reg["course_id"] == c_id:
            reg["status"] = "rejected"
            break
    save_db(db)
    await context.bot.send_message(chat_id=u_id, text=f"❌ تم رفض طلبك.\n\n{msg}")
    await update.message.reply_text("تم إرسال الرفض بنجاح.")
    return ConversationHandler.END

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db = load_db()
    reg = next((r for r in db.get("registrations", []) if r["user_id"] == user_id and r["status"] == "accepted" and r.get("receipt") is None), None)
    if not reg: return
    caption = f"💰 إيصال دفع جديد!\nالطالب: {reg['name']}\nالايدي: `{user_id}`"
    
    # الإرسال للمالك المسجل في المصنع
    owner_id = context.bot_data.get("owner_id")
    target_ids = set(db.get("admins", []) + [owner_id])
    
    if update.message.photo:
        fid = update.message.photo[-1].file_id
        reg["receipt"] = f"صورة: {fid}"
        for aid in target_ids: 
            try: await context.bot.send_photo(chat_id=aid, photo=fid, caption=caption)
            except: pass
    elif update.message.document:
        fid = update.message.document.file_id
        reg["receipt"] = f"ملف: {fid}"
        for aid in target_ids: 
            try: await context.bot.send_document(chat_id=aid, document=fid, caption=caption)
            except: pass
    elif update.message.text and re.search(r'\d{4,}', update.message.text):
        reg["receipt"] = f"رقم: {update.message.text}"
        for aid in target_ids: 
            try: await context.bot.send_message(chat_id=aid, text=f"{caption}\nالبيانات: {update.message.text}")
            except: pass
    save_db(db)
    await update.message.reply_text("✅ تم استلام الإيصال وجاري المراجعة.")

# --- 7. محرك المزامنة العميقة (Deep Sync Engine) ---

async def sync_backup_to_sheets(data):
    try:
        rows_cats = len(SHEET_CATS.get_all_values())
        if rows_cats > 1: SHEET_CATS.delete_rows(2, rows_cats)
        cat_rows = [[i+1, name, "", "", "", datetime.now().strftime("%Y-%m-%d")] for i, name in enumerate(data.get("categories", []))]
        if cat_rows: SHEET_CATS.append_rows(cat_rows)

        rows_courses = len(SHEET_COURSES.get_all_values())
        if rows_courses > 1: SHEET_COURSES.delete_rows(2, rows_courses)
        course_rows = [[c["id"], c["name"], "", "", "", "", c["price"]] for c in data.get("courses", [])]
        if course_rows: SHEET_COURSES.append_rows(course_rows)

        rows_regs = len(SHEET_REGS.get_all_values())
        if rows_regs > 1: SHEET_REGS.delete_rows(2, rows_regs)
        headers = SHEET_REGS.row_values(1)
        reg_rows = []
        for reg in data.get("registrations", []):
            row = [""] * len(headers)
            def fill(col, val): 
                if col in headers: row[headers.index(col)] = val
            fill("طابع_زمني", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            fill("معرف_الطالب", f"STU-{reg['user_id']}")
            fill("ID_المستخدم_تيليجرام", str(reg["user_id"]))
            fill("الاسم_بالعربي", reg["name"])
            fill("العمر", str(reg.get("age", "")))
            fill("البلد", reg.get("country", ""))
            fill("المدينة", reg.get("city", ""))
            fill("رقم_الهاتف", str(reg["phone"]))
            fill("البريد_الإلكتروني", reg["email"])
            fill("الحالة", reg.get("status", "pending"))
            fill("معرف_الدورة", str(reg["course_id"]))
            fill("الجنس", reg.get("gender", ""))
            reg_rows.append(row)
        if reg_rows: SHEET_REGS.append_rows(reg_rows)
        return True
    except Exception as e:
        logging.error(f"خطأ مزامنة شاملة: {e}")
        return False

async def download_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if os.path.exists(DB_FILE):
        await context.bot.send_document(chat_id=update.effective_user.id, document=open(DB_FILE, 'rb'), filename=DB_FILE)

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
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        status = await update.message.reply_text("⏳ جاري المزامنة الشاملة مع Google Sheets...")
        if await sync_backup_to_sheets(new_data):
            await status.edit_text("✅ تم التحديث والمزامنة بنجاح!")
        else:
            await status.edit_text("⚠️ تم التحديث محلياً وفشلت المزامنة.")
    except:
        await update.message.reply_text("❌ خطأ في معالجة الملف.")
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
        try:
            SHEET_PROMO_CODES.append_row([context.user_data["temp_promo_name"], "نسبة", percent, "", "", "", "", "نشط"])
        except: 
            pass
        await update.message.reply_text(f"✅ تم تفعيل الكود بنسبة {percent}%")
        return ConversationHandler.END
    except:
        await update.message.reply_text("خطأ! أرسل رقماً صحيحاً.")
        return GET_PROMO_PERCENT

# --- دالة مساعدة لربط الـ Callbacks بالمصنع ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    
    if data == "back_to_edu_main":
        await start_handler(update, context)
    elif data == "dev_panel":
        await show_dev_panel(update, context)
    elif data == "dev_stats":
        await show_dev_stats(update, context)
    elif data == "dev_users":
        await show_dev_users(update, context)
    elif data == "dev_categories":
        await show_manage_categories_menu(update, context)
    elif data == "dev_courses":
        await show_manage_courses_menu(update, context)
    elif data == "dev_add_cat":
        return await add_category_start(update, context)
    elif data == "dev_delete_cat":
        return await delete_category_start(update, context)
    elif data == "dev_add_course":
        return await add_course_start(update, context)
    elif data == "backup_download":
        await download_backup(update, context)
    elif data == "backup_upload":
        return await upload_backup_start(update, context)
    elif data == "dev_broadcast":
        return await broadcast_start(update, context)
    elif data == "dev_add_promo":
        return await add_promo_start(update, context)

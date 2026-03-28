import logging
import re
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, ChatMember
from telegram.ext import ContextTypes, ChatMemberHandler
from sheets import (
    get_bot_config, 
    add_log_entry, 
    get_bot_users_count, 
    get_bot_blocks_count,
    save_user,
    get_all_categories,
    add_new_category,
    delete_category_by_id,
    update_category_name
)

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- [ القوائم الرئيسية للمنصة ] ---

def get_student_menu():
    keyboard = [
        [InlineKeyboardButton("📚 استعراض الدورات", callback_data="view_courses")],
        [InlineKeyboardButton("👤 ملفي الدراسي", callback_data="my_profile"), InlineKeyboardButton("🎟 تفعيل دورة", callback_data="redeem_code")],
        [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="edu_faq"), InlineKeyboardButton("💬 الدعم الفني", callback_data="edu_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel():
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات الذكية", callback_data="admin_stats")],
        [InlineKeyboardButton("📁 إدارة الأقسام", callback_data="manage_cats"), InlineKeyboardButton("📚 إدارة الدورات", callback_data="manage_courses")],
        [InlineKeyboardButton("🎟 الكوبونات", callback_data="manage_coupons"), InlineKeyboardButton("📢 الإعلانات", callback_data="manage_ads")],
        [InlineKeyboardButton("📡 الإذاعة المستهدفة", callback_data="smart_broadcast")],
        [InlineKeyboardButton("🛠 الإعدادات التقنية", callback_data="tech_settings"), InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- [ المعالجات الأساسية ] ---

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    # تسجيل الطالب في قاعدة البيانات
    save_user(user.id, user.username)

    if user.id == bot_owner_id:
        await update.message.reply_text(
            f"<b>مرحباً بك يا دكتور {user.first_name} في لوحة تحكم منصتك</b> 🎓\n\nيمكنك إدارة الطلاب، الدورات، والمبيعات من هنا:",
            reply_markup=get_admin_panel(),
            parse_mode="HTML"
        )
    else:
        welcome_msg = config.get("الرسالة الترحيبية", "مرحباً بك في المنصة التعليمية! ابدأ رحلة تعلمك الآن.")
        await update.message.reply_text(
            f"<b>{welcome_msg}</b>",
            reply_markup=get_student_menu(),
            parse_mode="HTML"
        )

# --------------------------------------------------------------------------

async def contact_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    await query.answer()

    # --- إدارة الإحصائيات ---
    if data == "admin_stats":
        total_students = get_bot_users_count(bot_token)
        blocks = get_bot_blocks_count(bot_token)
        stats_text = (
            f"<b>📊 تقرير المنصة الحالي:</b>\n"
            f"-----------------------\n"
            f"👥 إجمالي الطلاب: {total_students}\n"
            f"🚫 عدد المحظورين: {blocks}\n"
            f"💰 مبيعات اليوم: 0.00$\n"
            f"📈 أكثر دورة طلباً: لا يوجد بيانات بعد"
        )
        await query.edit_message_text(stats_text, reply_markup=get_admin_panel(), parse_mode="HTML")

    # --- إدارة الأقسام (العرض) ---
    elif data == "manage_courses":
        await query.edit_message_text(
            "📚 <b>إدارة الدورات التدريبية:</b>\n\nيمكنك إضافة دورات جديدة وربطها بالأقسام المتاحة.", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة دورة جديدة", callback_data="start_add_course")],
                [InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")]
            ]), 
            parse_mode="HTML"
        )

        elif data == "start_add_course":
        # جلب الأقسام ليختار المسؤول أين يضع الدورة
        from sheets import get_all_categories
        categories = get_all_categories(bot_token)
        if not categories:
            await query.edit_message_text("⚠️ لا توجد أقسام حالياً! يرجى إضافة قسم أولاً قبل إضافة الدورات.", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_cats")]]), parse_mode="HTML")
            return
            
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"sel_cat_for_crs_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")])
        
        await query.edit_message_text("🎯 <b>اختر القسم الذي تريد إضافة الدورة إليه:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("sel_cat_for_crs_"):
        cat_id = data.replace("sel_cat_for_crs_", "")
        context.user_data['temp_course_cat'] = cat_id # حفظ القسم مؤقتاً
        context.user_data['action'] = 'awaiting_course_name'
        
        await query.edit_message_text("✍️ <b>ممتاز! الآن أرسل اسم الدورة الجديدة:</b>", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")]]), parse_mode="HTML")

    # --- عرض خيارات القسم المختار (تعديل/حذف) ---
    elif data.startswith("edit_cat_"):
        cat_id = data.replace("edit_cat_", "")
        context.user_data['selected_cat_id'] = cat_id
        
                keyboard = [
            [InlineKeyboardButton("📝 تعديل اسم القسم", callback_data="rename_cat")],
            [InlineKeyboardButton("📚 عرض دورات القسم", callback_data=f"view_crs_in_{cat_id}")],
            [InlineKeyboardButton("🗑️ حذف القسم", callback_data="confirm_delete_cat")],
            [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="manage_cats")]
        ]

        await query.edit_message_text(
            f"🛠 <b>إدارة القسم:</b>\n🆔 المعرف: <code>{cat_id}</code>\n\nاختر الإجراء المطلوب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # --- بدء عملية إضافة قسم جديد ---
    elif data == "add_cat_start":
        context.user_data['action'] = 'awaiting_cat_name'
        await query.edit_message_text(
            "✍️ <b>إضافة قسم جديد:</b>\n\nيرجى إرسال اسم القسم الذي تريد إنشاءه الآن:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إلغاء العملية", callback_data="manage_cats")]
            ]),
            parse_mode="HTML"
        )

    # --- تأكيد حذف القسم ---
    elif data == "confirm_delete_cat":
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف", callback_data="exec_delete_cat")],
            [InlineKeyboardButton("❌ تراجع", callback_data="manage_cats")]
        ]
        await query.edit_message_text(
            "⚠️ <b>تنبيه هام!</b>\nهل أنت متأكد من حذف هذا القسم؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # --- تنفيذ الحذف النهائي ---
    elif data == "exec_delete_cat":
        cat_id = context.user_data.get('selected_cat_id')
        from sheets import delete_category_by_id
        if delete_category_by_id(bot_token, cat_id):
            await query.edit_message_text(
                "✅ <b>تم حذف القسم بنجاح!</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للأقسام", callback_data="manage_cats")]]),
                parse_mode="HTML"
            )
    else:
            await query.edit_message_text("❌ حدث خطأ أثناء محاولة الحذف.")

    # --- بدء عملية تعديل الاسم ---
    elif data == "rename_cat":
        context.user_data['action'] = 'awaiting_new_cat_name'
        await query.edit_message_text(
            "📝 <b>تعديل اسم القسم:</b>\nيرجى إرسال الاسم الجديد الآن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="manage_cats")]]),
            parse_mode="HTML"
        )

    elif data.startswith("manage_crs_"):
        course_id = data.replace("manage_crs_", "")
        context.user_data['selected_course_id'] = course_id
        
        keyboard = [
            [InlineKeyboardButton("🗑️ حذف هذه الدورة", callback_data="confirm_delete_crs")],
            [InlineKeyboardButton("🔙 عودة لقائمة الدورات", callback_data="manage_courses")]
        ]
        
        await query.edit_message_text(
            f"📖 <b>إدارة الدورة:</b>\n🆔 المعرف: <code>{course_id}</code>\n\nاختر الإجراء المطلوب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # --- تأكيد وحذف الدورة ---
    elif data == "confirm_delete_crs":
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف الدورة", callback_data="exec_delete_crs")],
            [InlineKeyboardButton("❌ تراجع", callback_data="manage_courses")]
        ]
        await query.edit_message_text("⚠️ <b>تأكيد الحذف:</b>\nهل أنت متأكد من حذف هذه الدورة نهائياً؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "exec_delete_crs":
        course_id = context.user_data.get('selected_course_id')
        from sheets import delete_course_by_id
        
        if delete_course_by_id(bot_token, course_id):
            await query.edit_message_text("✅ <b>تم حذف الدورة بنجاح!</b>", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للإدارة", callback_data="manage_courses")]]), parse_mode="HTML")
        else:
            await query.edit_message_text("❌ فشل الحذف، تأكد من وجود الدورة في الشيت.")


    # --- بقية وظائف اللوحة ---
    elif data == "smart_broadcast":
        await query.edit_message_text("📡 <b>الإذاعة الذكية:</b>", 
                                      reply_markup=InlineKeyboardMarkup([
                                          [InlineKeyboardButton("📢 للكل", callback_data="bc_all"), InlineKeyboardButton("🎓 لمشتركي دورة", callback_data="bc_course")]
                                      ]), parse_mode="HTML")
                                          elif data.startswith("view_crs_in_"):
                                              
        cat_id = data.replace("view_crs_in_", "")
        from sheets import get_courses_by_category
        courses = get_courses_by_category(bot_token, cat_id)
        
        
        keyboard = []
        if courses:
            for crs in courses:
                keyboard.append([InlineKeyboardButton(f"📖 {crs['name']}", callback_data=f"manage_crs_{crs['id']}")])
        else:
            stats_text = "ℹ️ لا توجد دورات في هذا القسم حالياً."
            
        keyboard.append([InlineKeyboardButton("🔙 عودة للقسم", callback_data=f"edit_cat_{cat_id}")])
        
        await query.edit_message_text(
            f"📚 <b>الدورات التابعة للقسم {cat_id}:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )


    elif data == "close_panel":
        await query.edit_message_text("🔒 تم إغلاق لوحة التحكم.")

    # --- التنقل والعودة ---
    elif data == "back_to_admin":
        await query.edit_message_text(
            f"<b>مرحباً بك مجدداً يا دكتور {query.from_user.first_name}</b> 🎓",
            reply_markup=get_admin_panel(),
            parse_mode="HTML"
        )

    elif data == "main_menu":
        welcome_msg = config.get("الرسالة الترحيبية", "مرحباً بك في المنصة التعليمية!")
        await query.edit_message_text(
            f"<b>{welcome_msg}</b>",
            reply_markup=get_student_menu(),
            parse_mode="HTML"
        )

# --------------------------------------------------------------------------

async def handle_contact_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    # --- [ فحص الحالات الخاصة بالمسؤول (إضافة وتعديل) ] ---
    if user.id == bot_owner_id:
        action = context.user_data.get('action')
        
        if action == 'awaiting_cat_name':
            cat_id = f"C{str(uuid.uuid4().int)[:4]}"
            cat_name = text.strip()
            if add_new_category(bot_token, cat_id, cat_name):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إنشاء القسم: <b>{cat_name}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return
            
        elif action == 'awaiting_new_cat_name':
            cat_id = context.user_data.get('selected_cat_id')
            new_name = text.strip()
            if update_category_name(bot_token, cat_id, new_name):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم تحديث الاسم إلى: <b>{new_name}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return
        # --- معالجة استلام اسم الدورة الجديدة ---
        elif action == 'awaiting_course_name':
            import uuid
            from sheets import add_new_course 
            
            course_cat = context.user_data.get('temp_course_cat')
            course_id = f"CRS{str(uuid.uuid4().int)[:4]}"
            course_name = text.strip()
            
            if add_new_course(bot_token, course_id, course_name, course_cat):
                context.user_data['action'] = None
                await update.message.reply_text(
                    f"✅ <b>تم إضافة الدورة بنجاح!</b>\n\n"
                    f"📚 الاسم: {course_name}\n"
                    f"🆔 المعرف: <code>{course_id}</code>\n"
                    f"📂 القسم: <code>{course_cat}</code>",
                    reply_markup=get_admin_panel(),
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("❌ حدث خطأ أثناء حفظ الدورة.")
            return

    # نظام الرد الآلي الذكي (Smart FAQ)
    faq_keywords = {
        "طريقة الدفع": "💳 يمكنك الدفع عبر (زين كاش، بايبال، أو كروت التعبئة).",
        "تفعيل": "🎟 لتفعيل الدورة، يرجى إرسال الكود الذي حصلت عليه.",
        "قائمة": "📚 يمكنك استعراض كافة الدورات المتاحة."
    }

    if user.id != bot_owner_id:
        for key, response in faq_keywords.items():
            if key in text:
                await update.message.reply_text(response)
                return

        info = f"📩 <b>سؤال جديد من طالب:</b>\nالاسم: {user.full_name}\nID: <code>{user.id}</code>\n\n{text}"
        try:
            await context.bot.send_message(chat_id=bot_owner_id, text=info, parse_mode="HTML")
            await update.message.reply_text("✅ تم إرسال استفسارك للمدرب، سيتم الرد عليك قريباً.")
        except:
            await update.message.reply_text("⚠️ فشل التواصل مع الإدارة حالياً.")



async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    user = result.from_user
    bot_owner_id = int(get_bot_config(context.bot.token).get("admin_ids", 0))

    if result.new_chat_member.status == ChatMember.BANNED:
        msg = f"<b>🚫 قام الطالب {user.full_name} بحظر المنصة.</b>"
        try: await context.bot.send_message(chat_id=bot_owner_id, text=msg, parse_mode="HTML")
        except: pass
    elif result.new_chat_member.status == ChatMember.MEMBER:
        msg = f"<b>📶 عاد الطالب {user.full_name} لاستخدام المنصة.</b>"
        try: await context.bot.send_message(chat_id=bot_owner_id, text=msg, parse_mode="HTML")
        except: pass
    

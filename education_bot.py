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
    update_category_name,
    add_new_course,
    get_courses_by_category,
    delete_course_by_id
)

# إعداد السجلات (Logging) لمراقبة أداء البوت وتتبع الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- [ القوائم الرئيسية للمنصة - أزرار واجهة المستخدم ] ---

def get_student_menu():
    """قائمة الأزرار الرئيسية التي تظهر للطلاب"""
    keyboard = [
        [InlineKeyboardButton("📚 استعراض الدورات", callback_data="view_courses")],
        [InlineKeyboardButton("👤 ملفي الدراسي", callback_data="my_profile"), InlineKeyboardButton("🎟 تفعيل دورة", callback_data="redeem_code")],
        [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="edu_faq"), InlineKeyboardButton("💬 الدعم الفني", callback_data="edu_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel():
    """قائمة الأزرار الرئيسية للوحة تحكم الإدارة"""
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات الذكية", callback_data="admin_stats")],
        [InlineKeyboardButton("📁 إدارة الأقسام", callback_data="manage_cats"), InlineKeyboardButton("📚 إدارة الدورات", callback_data="manage_courses")],
        [InlineKeyboardButton("🎟 الكوبونات", callback_data="manage_coupons"), InlineKeyboardButton("📢 الإعلانات", callback_data="manage_ads")],
        [InlineKeyboardButton("📡 الإذاعة المستهدفة", callback_data="smart_broadcast")],
        [InlineKeyboardButton("🛠 الإعدادات التقنية", callback_data="tech_settings"), InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- [ المعالجات الأساسية - أمر البداية ] ---

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start وتسجيل المستخدم وعرض القائمة المناسبة"""
    user = update.effective_user
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    # تسجيل الطالب في قاعدة البيانات (Google Sheets)
    save_user(user.id, user.username)

    if user.id == bot_owner_id:
        # واجهة المسؤول
        await update.message.reply_text(
            f"<b>مرحباً بك يا دكتور {user.first_name} في لوحة تحكم منصتك</b> 🎓\n\nيمكنك إدارة الطلاب، الدورات، والمبيعات من هنا:",
            reply_markup=get_admin_panel(),
            parse_mode="HTML"
        )
    else:
        # واجهة الطالب
        welcome_msg = config.get("الرسالة الترحيبية", "مرحباً بك في المنصة التعليمية! ابدأ رحلة تعلمك الآن.")
        await update.message.reply_text(
            f"<b>{welcome_msg}</b>",
            reply_markup=get_student_menu(),
            parse_mode="HTML"
        )

# --------------------------------------------------------------------------
# --- [ معالج ضغطات الأزرار (Callback Query Handler) ] ---
# --------------------------------------------------------------------------

async def contact_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحكم في كافة عمليات الضغط على الأزرار الشفافة Inline Buttons"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    await query.answer()

    # --- 1. إدارة الإحصائيات ---
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

    # --- 2. إدارة الدورات التدريبية (الواجهة الرئيسية) ---
    elif data == "manage_courses":
        await query.edit_message_text(
            "📚 <b>إدارة الدورات التدريبية:</b>\n\nيمكنك إضافة دورات جديدة وربطها بالأقسام المتاحة.", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة دورة جديدة", callback_data="start_add_course")],
                [InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")]
            ]), 
            parse_mode="HTML"
        )

    # --- 3. بدء عملية إضافة دورة جديدة (اختيار القسم أولاً) ---
    elif data == "start_add_course":
        from sheets import get_all_categories
        categories = get_all_categories(bot_token)
        if not categories:
            await query.edit_message_text("⚠️ لا توجد أقسام حالياً! يرجى إضافة قسم أولاً قبل إضافة الدورات.", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_cats")]]), parse_mode="HTML")
            return
            
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"sel_cat_for_crs_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")])
        
        await query.edit_message_text("🎯 <b>اختر القسم الذي تريد إضافة الدورة إليه:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # --- 4. معالجة القسم المختار للدورة وبدء طلب الاسم ---
    elif data.startswith("set_crs_cat_"):
        cat_id = data.replace("set_crs_cat_", "")
        context.user_data['temp_crs_cat'] = cat_id
        context.user_data['action'] = 'awaiting_crs_name'
        await query.edit_message_text("✍️ **الخطوة 2:** أرسل اسم الدورة الآن:")

    elif data == "confirm_save_full_crs":
        from sheets import add_new_course_full
        d = context.user_data.get('temp_crs')
        cat_id = context.user_data.get('temp_crs_cat')
        c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
        
        # استدعاء دالة الحفظ مع كافة المعايير
        success = add_new_course_full(
            bot_token, c_id, d['name'], d['hours'], d['start_date'], 
            "", "أونلاين", d['price'], "100", "لا يوجد", "إدارة", "001", "عام",
            d['coach_user'], d['coach_id'], d['coach_name']
        )
        
        if success:
            await query.edit_message_text("✅ **تم اعتماد الدورة وحفظها في جوجل شيت بنجاح!**", 
                                          reply_markup=get_admin_panel())
        else:
            await query.edit_message_text("❌ حدث خطأ أثناء الحفظ.")


    # --- 5. إدارة الأقسام (عرض القائمة) ---
    elif data == "manage_cats":
        from sheets import get_all_categories 
        categories = get_all_categories(bot_token)
        
        keyboard = []
        if categories:
            for cat in categories:
                keyboard.append([InlineKeyboardButton(f"📂 {cat['name']}", callback_data=f"edit_cat_{cat['id']}")])
        
        keyboard.append([InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="add_cat_start")])
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            "🗂 <b>قائمة الأقسام الحالية:</b>\nاختر قسماً للتعديل أو اضغط إضافة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    elif data == "start_add_course":
        from sheets import get_all_categories
        categories = get_all_categories(bot_token)
        if not categories:
            await query.edit_message_text("⚠️ أضف قسماً أولاً!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_cats")]]), parse_mode="HTML")
            return
        # الخطوة 1: اختيار القسم
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"set_crs_cat_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")])
        await query.edit_message_text("🎯 **الخطوة 1:** اختر القسم المخصص للدورة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # --- 6. عرض خيارات القسم المختار (تعديل/حذف/عرض دورات) ---
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

    # --- 7. عرض الدورات التابعة لقسم محدد ---
    elif data.startswith("view_crs_in_"):
        cat_id = data.replace("view_crs_in_", "")
        from sheets import get_courses_by_category
        courses = get_courses_by_category(bot_token, cat_id)
        
        keyboard = []
        if courses:
            for crs in courses:
                keyboard.append([InlineKeyboardButton(f"📖 {crs['name']}", callback_data=f"manage_crs_{crs['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 عودة للقسم", callback_data=f"edit_cat_{cat_id}")])
        
        await query.edit_message_text(
            f"📚 <b>الدورات التابعة للقسم {cat_id}:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # --- 8. بدء عملية إضافة قسم جديد ---
    elif data == "add_cat_start":
        context.user_data['action'] = 'awaiting_cat_name'
        await query.edit_message_text(
            "✍️ <b>إضافة قسم جديد:</b>\n\nيرجى إرسال اسم القسم الذي تريد إنشاءه الآن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء العملية", callback_data="manage_cats")]]),
            parse_mode="HTML"
        )

    # --- 9. تأكيد حذف القسم ---
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

    # --- 10. تنفيذ الحذف النهائي للقسم ---
    elif data == "exec_delete_cat":
        cat_id = context.user_data.get('selected_cat_id')
        if delete_category_by_id(bot_token, cat_id):
            await query.edit_message_text("✅ <b>تم حذف القسم بنجاح!</b>", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للأقسام", callback_data="manage_cats")]]), parse_mode="HTML")
        else:
            await query.edit_message_text("❌ حدث خطأ أثناء محاولة الحذف.")

    # --- 11. بدء عملية تعديل اسم القسم ---
    elif data == "rename_cat":
        context.user_data['action'] = 'awaiting_new_cat_name'
        await query.edit_message_text(
            "📝 <b>تعديل اسم القسم:</b>\nيرجى إرسال الاسم الجديد الآن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="manage_cats")]]),
            parse_mode="HTML"
        )

    # --- 12. واجهة إدارة دورة محددة ---
    elif data.startswith("manage_crs_"):
        course_id = data.replace("manage_crs_", "")
        context.user_data['selected_course_id'] = course_id
        
        keyboard = [
            [InlineKeyboardButton("🗑️ حذف هذه الدورة", callback_data="confirm_delete_crs")],
            [InlineKeyboardButton("🔙 عودة لقائمة الدورات", callback_data="manage_courses")]
        ]
        await query.edit_message_text(f"📖 <b>إدارة الدورة:</b>\n🆔 المعرف: <code>{course_id}</code>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # --- 13. تأكيد وحذف الدورة ---
    elif data == "confirm_delete_crs":
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف الدورة", callback_data="exec_delete_crs")],
            [InlineKeyboardButton("❌ تراجع", callback_data="manage_courses")]
        ]
        await query.edit_message_text("⚠️ <b>تأكيد الحذف:</b>\nهل أنت متأكد من حذف هذه الدورة؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "exec_delete_crs":
        course_id = context.user_data.get('selected_course_id')
        if delete_course_by_id(bot_token, course_id):
            await query.edit_message_text("✅ <b>تم حذف الدورة بنجاح!</b>", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="manage_courses")]]), parse_mode="HTML")

    # --- 14. الإذاعة والتنقل العام ---
    elif data == "smart_broadcast":
        await query.edit_message_text("📡 <b>الإذاعة الذكية:</b>", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 للكل", callback_data="bc_all"), InlineKeyboardButton("🎓 لمشتركي دورة", callback_data="bc_course")]]), parse_mode="HTML")

    elif data == "close_panel":
        await query.edit_message_text("🔒 تم إغلاق لوحة التحكم.")

    elif data == "back_to_admin":
        await query.edit_message_text(f"<b>مرحباً بك مجدداً يا دكتور {query.from_user.first_name}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")

# --------------------------------------------------------------------------
# --- [ معالج الرسائل النصية (Message Handler) ] ---
# --------------------------------------------------------------------------

async def handle_contact_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة كافة الرسائل النصية الواردة للبوت وتوجيهها حسب الحالة"""
    text = update.message.text
    user = update.effective_user
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))
    action = context.user_data.get('action')

    # --- [ الجزء الخاص بالمسؤول (إدارة المحتوى) ] ---
    if user.id == bot_owner_id:
        # حالة 1: إضافة قسم جديد
        if action == 'awaiting_cat_name':
            cat_id = f"C{str(uuid.uuid4().int)[:4]}"
            if add_new_category(bot_token, cat_id, text.strip()):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إنشاء القسم: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return
            
        # حالة 2: تعديل اسم قسم
        elif action == 'awaiting_new_cat_name':
            cat_id = context.user_data.get('selected_cat_id')
            if update_category_name(bot_token, cat_id, text.strip()):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم تحديث الاسم إلى: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # حالة 3: إضافة دورة جديدة
        elif action == 'awaiting_course_name':
            course_cat = context.user_data.get('temp_course_cat')
            course_id = f"CRS{str(uuid.uuid4().int)[:4]}"
            if add_new_course(bot_token, course_id, text.strip(), course_cat):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إضافة الدورة: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML" )
            return
            
    # --- [ تسلسل إضافة دورة احترافي ] ---
    if user.id == bot_owner_id:
        # الخطوة 2: استلام الاسم والطلب الساعات (أو الوصف)
        if action == 'awaiting_crs_name':
            context.user_data['temp_crs'] = {'name': text.strip()}
            context.user_data['action'] = 'awaiting_crs_hours'
            await update.message.reply_text("⏳ **الخطوة 3:** أرسل عدد ساعات الدورة (أو وصفاً قصيراً):")
            return

        # الخطوة 3: استلام الساعات والطلب السعر
        elif action == 'awaiting_crs_hours':
            context.user_data['temp_crs']['hours'] = text.strip()
            context.user_data['action'] = 'awaiting_crs_price'
            await update.message.reply_text("💰 **الخطوة 4:** أرسل سعر الدورة (أرقام فقط):")
            return

        # الخطوة 4: استلام السعر والطلب يوزر المدرب
        elif action == 'awaiting_crs_price':
            context.user_data['temp_crs']['price'] = text.strip()
            context.user_data['action'] = 'awaiting_crs_coach'
            await update.message.reply_text("👨‍🏫 **الخطوة 5:** أرسل (يوزرنايم) المدرب مع الـ @\nمثال: @CoachName")
            return

        # الخطوة 5: استلام يوزر المدرب والبحث عن الـ ID اتماتيكياً
        elif action == 'awaiting_crs_coach':
            coach_username = text.strip().replace("@", "")
            try:
                # محاولة الحصول على معلومات المدرب من التليجرام اتماتيكياً
                coach_chat = await context.bot.get_chat(f"@{coach_username}")
                context.user_data['temp_crs']['coach_user'] = f"@{coach_username}"
                context.user_data['temp_crs']['coach_id'] = coach_chat.id
                context.user_data['temp_crs']['coach_name'] = coach_chat.full_name
                
                context.user_data['action'] = 'awaiting_crs_date'
                await update.message.reply_text(f"✅ تم العثور على المدرب: {coach_chat.full_name}\n🆔 معرفه: {coach_chat.id}\n\n🗓 **الخطوة 6:** أرسل تاريخ بداية الدورة (مثال: 2026-04-01):")
            except Exception:
                await update.message.reply_text("❌ لم أستطع العثور على هذا اليوزر. تأكد من صحته أو اطلب من المدرب مراسلة البوت أولاً.")
            return

        # الخطوة 6: تجميع المعلومات وعرض "تأكيد الاعتماد"
        elif action == 'awaiting_crs_date':
            context.user_data['temp_crs']['start_date'] = text.strip()
            d = context.user_data['temp_crs']
            
            summary = (
                f"📝 **مراجعة بيانات الدورة:**\n"
                f"━━━━━━━━━━━━━━\n"
                f"📂 القسم: {context.user_data.get('temp_crs_cat')}\n"
                f"📚 الاسم: {d['name']}\n"
                f"⏳ الساعات: {d['hours']}\n"
                f"💰 السعر: {d['price']}$\n"
                f"👨‍🏫 المدرب: {d['coach_name']}\n"
                f"🗓 البداية: {d['start_date']}\n"
                f"━━━━━━━━━━━━━━\n"
                f"**هل تريد اعتماد وتسجيل الدورة؟**"
            )
            keyboard = [
                [InlineKeyboardButton("✅ نعم، اعتمد الدورة", callback_data="confirm_save_full_crs")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")]
            ]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return

    # --- [ الجزء الخاص بالطلاب والردود الآلية ] ---
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

        # توجيه الرسالة للمدرب
        info = f"📩 <b>سؤال جديد من طالب:</b>\n{user.full_name}\n\n{text}"
        try:
            await context.bot.send_message(chat_id=bot_owner_id, text=info, parse_mode="HTML")
            await update.message.reply_text("✅ تم إرسال استفسارك للمدرب.")
        except:
            await update.message.reply_text("⚠️ فشل التواصل مع الإدارة.")

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تتبع الطلاب (حظر/إلغاء حظر البوت)"""
    result = update.my_chat_member
    bot_owner_id = int(get_bot_config(context.bot.token).get("admin_ids", 0))
    status = "حظر البوت 🚫" if result.new_chat_member.status == ChatMember.BANNED else "عاد للبوت ✅"
    msg = f"👤 الطالب {result.from_user.full_name} قام بـ {status}"
    try: await context.bot.send_message(chat_id=bot_owner_id, text=msg, parse_mode="HTML")
    except: pass

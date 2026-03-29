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
    """قائمة الأزرار الرئيسية للوحة تحكم الإدارة - النسخة الشاملة"""
    keyboard = [
        # الصف الأول: الإحصائيات
        [InlineKeyboardButton("📊 الإحصائيات الذكية", callback_data="admin_stats")],
        [
            InlineKeyboardButton("📁 إدارة الأقسام", callback_data="manage_cats"),
            InlineKeyboardButton("📚 إدارة الدورات", callback_data="manage_courses")
        ],
        [InlineKeyboardButton("👨‍🏫 إدارة شؤون المدربين", callback_data="manage_coaches")],
        [
            InlineKeyboardButton("🎟 الكوبونات", callback_data="manage_coupons"),
            InlineKeyboardButton("📢 الإعلانات", callback_data="manage_ads")
        ],
        [InlineKeyboardButton("📡 الإذاعة المستهدفة", callback_data="smart_broadcast")],
        [
            InlineKeyboardButton("🛠 الإعدادات التقنية", callback_data="tech_settings"),
            InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")
        ]
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
# --------------------------------------------------------------------------
    # --- 3. بدء عملية إضافة مدرب  جديد  ---
        elif data == "manage_coaches":
        await query.edit_message_text(
            "👨‍🏫 <b>إدارة شؤون المدربين:</b>\nيمكنك إضافة مدربين جدد أو استعراض القائمة الحالية للحذف.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة مدرب جديد", callback_data="start_add_coach")],
                [InlineKeyboardButton("📋 عرض قائمة المدربين", callback_data="list_coaches")],
                [InlineKeyboardButton("🔙 عودة للوحة التحكم", callback_data="back_to_admin")]
            ]), parse_mode="HTML"
        )

    # 1. عرض قائمة المدربين كأزرار
    elif data == "list_coaches":
        from sheets import get_all_coaches
        coaches = get_all_coaches(bot_token)
        if not coaches:
            await query.edit_message_text("⚠️ لا يوجد مدربون مسجلون حالياً.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_coaches")]]))
            return

        keyboard = [[InlineKeyboardButton(f"👤 {c['name']}", callback_data=f"view_coach_{c['id']}")] for c in coaches]
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_coaches")])
        await query.edit_message_text("🎯 **اختر مدرباً لعرض تفاصيله أو حذفه:**", reply_markup=InlineKeyboardMarkup(keyboard))

    # 2. عرض تفاصيل مدرب محدد مع زر الحذف
    elif data.startswith("view_coach_"):
        coach_id = data.replace("view_coach_", "")
        from sheets import get_all_coaches
        coaches = get_all_coaches(bot_token)
        coach = next((c for c in coaches if str(c['id']) == str(coach_id)), None)
        
        if coach:
            text = f"👤 **معلومات المدرب:**\n━━━━━━━━━━━━━━\nالاسم: {coach['name']}\nID: <code>{coach['id']}</code>"
            keyboard = [
                [InlineKeyboardButton("🗑️ حذف المدرب نهائياً", callback_data=f"del_coach_{coach['id']}")],
                [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="list_coaches")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # 3. تنفيذ الحذف الفعلي
    elif data.startswith("del_coach_"):
        coach_id = data.replace("del_coach_", "")
        from sheets import delete_coach_from_sheet
        if delete_coach_from_sheet(bot_token, coach_id):
            await query.answer("✅ تم حذف المدرب بنجاح", show_alert=True)
            # العودة للقائمة بعد الحذف
            await query.edit_message_text("✅ تم الحذف. هل تريد إدارة مدرب آخر؟", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 عرض القائمة", callback_data="list_coaches")]]))
        else:
            await query.answer("❌ فشل الحذف", show_alert=True)


    elif data == "start_add_coach":
        context.user_data['action'] = 'await_coach_name'
        await query.edit_message_text("✍️ <b>الخطوة 1:</b> أرسل اسم المدرب الثلاثي:", parse_mode="HTML")

    elif data == "confirm_save_coach":
        # دمجنا الوظيفتين هنا واستخدمنا النسخة المتطورة
        from sheets import add_new_coach_advanced
        
        # 1. جلب بيانات المدرب من الذاكرة المؤقتة
        c = context.user_data.get('temp_coach')
        
        if not c:
            await query.edit_message_text("⚠️ خطأ: تعذر العثور على البيانات، يرجى إعادة المحاولة من جديد.")
            return

        # 2. تنفيذ الحفظ الفعلي باستخدام الدالة المتطورة
        success = add_new_coach_advanced(
            bot_token=bot_token,
            coach_id=c['id'],
            name=c['name'],
            specialty=c['spec'],
            phone=c['phone'],
            notes="تمت الإضافة عبر لوحة التحكم"
        )
        
        if success:
            await query.edit_message_text(
                f"✅ <b>تم تسجيل المدرب بنجاح!</b>\n\n"
                f"👤 الاسم: {c['name']}\n"
                f"🎓 التخصص: {c['spec']}\n"
                f"🆔 المعرف: <code>{c['id']}</code>",
                reply_markup=get_admin_panel(),
                parse_mode="HTML"
            )
            # مسح البيانات المؤقتة لضمان نظافة الذاكرة
            context.user_data.pop('temp_coach', None)
        else:
            await query.edit_message_text("❌ حدث خطأ تقني أثناء الحفظ في جوجل شيت. تأكد من إعدادات الملف.")

# --------------------------------------------------------------------------
    # --- 4. معالجة القسم المختار للدورة وبدء طلب الاسم ---
    elif data.startswith("set_crs_cat_"):
        cat_id = data.replace("set_crs_cat_", "")
        context.user_data['temp_crs_cat'] = cat_id
        context.user_data['action'] = 'awaiting_crs_name'
        await query.edit_message_text("✍️ **الخطوة 2:** أرسل اسم الدورة الآن:")

    elif data == "confirm_save_full_crs":
        from sheets import add_new_course 
        import uuid
        
        # 1. جلب البيانات المؤقتة
        d = context.user_data.get('temp_crs')
        cat_id = context.user_data.get('temp_crs_cat')
        
        if not d:
            await query.edit_message_text("⚠️ خطأ: تعذر العثور على البيانات المؤقتة، يرجى المحاولة مجدداً.")
            return

        # 2. توليد معرف فريد للدورة
        c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
        
        # 3. تنفيذ الحفظ الفعلي (إرسال الـ 16 متغير بالترتيب للأعمدة)
        success = add_new_course(
            bot_token,          # 1. bot_id
            c_id,               # 2. معرف_الدورة
            d['name'],          # 3. اسم_الدورة
            d['hours'],         # 4. عدد_الساعات
            d['start_date'],    # 5. تاريخ_البداية
            "",                 # 6. تاريخ_النهاية
            "أونلاين",          # 7. نوع_الدورة
            d['price'],         # 8. سعر_الدورة
            "100",              # 9. الحد_الأقصى
            "لا يوجد",          # 10. المتطلبات
            "إدارة المنصة",      # 11. اسم_المندوب
            "ADMIN01",          # 12. كود_المندوب
            "عام",              # 13. الحملة_التسويقية
            d['coach_user'],    # 14. معرف_المدرب (اليوزر)
            d['coach_id'],      # 15. ID_المدرب (الرقمي)
            d['coach_name']     # 16. اسم_المدرب
        )
        
        if success:
            await query.edit_message_text(
                f"✅ <b>تم اعتماد الدورة وحفظها بنجاح!</b>\n\n"
                f"🆔 المعرف: <code>{c_id}</code>\n"
                f"📂 القسم: <code>{cat_id}</code>\n"
                f"👨‍🏫 المدرب: {d['coach_name']}",
                reply_markup=get_admin_panel(),
                parse_mode="HTML"
            )
            context.user_data.pop('temp_crs', None) # مسح البيانات المؤقتة
        else:
            await query.edit_message_text("❌ فشل الحفظ في جوجل شيت، تأكد من صلاحيات الملف.")

        # استدعاء الدالة بالاسم الصحيح المذكور في sheets.py
        success = add_new_course(
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
    """معالجة كافة الرسائل النصية الواردة للبوت وتوجيهها حسب الحالة دون حذف أي وظيفة"""
    text = update.message.text
    user = update.effective_user
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))
    action = context.user_data.get('action')

    # --- [ الجزء الخاص بالمسؤول - إدارة المحتوى والدورات ] ---
    if user.id == bot_owner_id:
        # 1. حالة إضافة قسم جديد
        if action == 'awaiting_cat_name':
            cat_id = f"C{str(uuid.uuid4().int)[:4]}"
            if add_new_category(bot_token, cat_id, text.strip()):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إنشاء القسم بنجاح: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return
            
        # 2. حالة تعديل اسم قسم
        elif action == 'awaiting_new_cat_name':
            cat_id = context.user_data.get('selected_cat_id')
            if update_category_name(bot_token, cat_id, text.strip()):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم تحديث اسم القسم إلى: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # 3. حالة إضافة دورة جديدة (النظام البسيط القديم - اسم فقط)
        elif action == 'awaiting_course_name':
            course_cat = context.user_data.get('temp_course_cat')
            course_id = f"CRS{str(uuid.uuid4().int)[:4]}"
            if add_new_course(bot_token, course_id, text.strip(), course_cat):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إضافة الدورة بنجاح: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # 4. تسلسل إضافة دورة احترافي (الخطوة 2: استلام الاسم وطلب الساعات)
        elif action == 'awaiting_crs_name':
            context.user_data['temp_crs'] = {'name': text.strip()}
            context.user_data['action'] = 'awaiting_crs_hours'
            await update.message.reply_text("⏳ <b>الخطوة 3:</b> أرسل عدد ساعات الدورة (أو وصفاً قصيراً):", parse_mode="HTML")
            return

        # 5. الخطوة 3: استلام الساعات والطلب السعر
        elif action == 'awaiting_crs_hours':
            context.user_data['temp_crs']['hours'] = text.strip()
            context.user_data['action'] = 'awaiting_crs_price'
            await update.message.reply_text("💰 <b>الخطوة 4:</b> أرسل سعر الدورة (أرقام فقط):", parse_mode="HTML")
            return

        # 6. الخطوة 4: استلام السعر وعرض خيارات المدربين (من الشيت أو يدوياً)
        elif action == 'awaiting_crs_price':
            context.user_data['temp_crs']['price'] = text.strip()
            from sheets import get_all_coaches
            coaches = get_all_coaches(bot_token) # جلب المدربين من الورقة الجديدة
            
            msg = "👨‍🏫 <b>الخطوة 5:</b> اختر المدرب من القائمة أدناه، أو أرسل (يوزرنايم/ID) يدوي:"
            keyboard = []
            
            if coaches:
                for c in coaches:
                    keyboard.append([InlineKeyboardButton(f"👤 {c['name']}", callback_data=f"sel_coach_for_crs_{c['id']}")])
            
            keyboard.append([InlineKeyboardButton("❌ إلغاء العملية", callback_data="manage_courses")])
            
            context.user_data['action'] = 'awaiting_crs_coach' # البوت جاهز لاستقبال نص أو ضغطة زر
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        # 7. الخطوة 5: استلام بيانات المدرب (يدوياً إذا لم يستخدم الأزرار)
        elif action == 'awaiting_crs_coach':
            input_val = text.strip()
            from sheets import find_user_by_username
            
            # فحص: هل المسؤول أرسل ID رقمي؟
            if input_val.isdigit():
                context.user_data['temp_crs'].update({
                    'coach_user': "إدخال يدوي رقمي",
                    'coach_id': input_val,
                    'coach_name': f"مدرب (ID: {input_val})"
                })
                context.user_data['action'] = 'awaiting_crs_date'
                await update.message.reply_text(f"✅ تم قبول المعرف الرقمي: <code>{input_val}</code>\n\n🗓 <b>الخطوة 6:</b> أرسل تاريخ بداية الدورة:", parse_mode="HTML")
            
            # فحص: هل المسؤول أرسل يوزرنايم؟
            else:
                coach_username = input_val.replace("@", "")
                user_data = find_user_by_username(bot_token, coach_username) # البحث في شيت المستخدمين
                
                if user_data:
                    context.user_data['temp_crs'].update({
                        'coach_user': f"@{coach_username}",
                        'coach_id': user_data['id'],
                        'coach_name': user_data['name']
                    })
                    context.user_data['action'] = 'awaiting_crs_date'
                    await update.message.reply_text(f"✅ تم العثور على المدرب في القاعدة: {user_data['name']}\n\n🗓 <b>الخطوة 6:</b> أرسل تاريخ بداية الدورة:", parse_mode="HTML")
                else:
                    try:
                        # محاولة أخيرة عبر سيرفرات تليجرام
                        coach_chat = await context.bot.get_chat(f"@{coach_username}")
                        context.user_data['temp_crs'].update({
                            'coach_user': f"@{coach_username}",
                            'coach_id': coach_chat.id,
                            'coach_name': coach_chat.full_name
                        })
                        context.user_data['action'] = 'awaiting_crs_date'
                        await update.message.reply_text(f"✅ تم العثور عبر تليجرام: {coach_chat.full_name}\n\n🗓 <b>الخطوة 6:</b> أرسل تاريخ البداية:", parse_mode="HTML")
                    except Exception:
                        await update.message.reply_text(
                            "❌ <b>فشل العثور على المدرب!</b>\n\n"
                            "💡 يرجى إرسال <b>المعرف الرقمي (ID)</b> للمدرب الآن (مثل: 873158772)، أو تأكد من مراسلته للبوت.",
                            parse_mode="HTML"
                        )
            return

        # 8. الخطوة 6: مراجعة البيانات وعرض التأكيد النهائي للحفظ في "الدورات_التدريبية"
        elif action == 'awaiting_crs_date':
            context.user_data['temp_crs']['start_date'] = text.strip()
            d = context.user_data['temp_crs']
            
            summary = (
                f"📝 <b>مراجعة بيانات الدورة قبل الاعتماد:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📂 القسم: <code>{context.user_data.get('temp_crs_cat')}</code>\n"
                f"📚 الاسم: <b>{d['name']}</b>\n"
                f"⏳ الساعات: {d['hours']}\n"
                f"💰 السعر: {d['price']}$\n"
                f"👨‍🏫 المدرب: {d['coach_name']}\n"
                f"🆔 معرف المدرب: <code>{d['coach_id']}</code>\n"
                f"🗓 البداية: {d['start_date']}\n"
                f"━━━━━━━━━━━━━━\n"
                f"<b>هل تريد تسجيل هذه الدورة رسمياً؟</b>"
            )
            keyboard = [
                [InlineKeyboardButton("✅ نعم، اعتمد واحفظ", callback_data="confirm_save_full_crs")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")]
            ]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return

        # --- [ تسلسل إضافة مدرب ] ---
        # 1. استلام الاسم والطلب التخصص
        elif action == 'await_coach_name':
            context.user_data['temp_coach'] = {'name': text.strip()}
            context.user_data['action'] = 'await_coach_spec'
            await update.message.reply_text("🎓 <b>الخطوة 2:</b> أرسل تخصص المدرب (مثلاً: لغة عربية، برمجة...):", parse_mode="HTML")
            return

        # 2. استلام التخصص والطلب الهاتف
        elif action == 'await_coach_spec':
            context.user_data['temp_coach']['spec'] = text.strip()
            context.user_data['action'] = 'await_coach_phone'
            await update.message.reply_text("📞 <b>الخطوة 3:</b> أرسل رقم هاتف المدرب:")
            return

        # 3. استلام الهاتف والطلب الـ ID
        elif action == 'await_coach_phone':
            context.user_data['temp_coach']['phone'] = text.strip()
            context.user_data['action'] = 'await_coach_id'
            await update.message.reply_text("🆔 <b>الخطوة 4:</b> أرسل المعرف الرقمي (ID) للمدرب (مثال: 873158772):", parse_mode="HTML")
            return

        # 4. استلام الـ ID وعرض الملخص
        elif action == 'await_coach_id':
            context.user_data['temp_coach']['id'] = text.strip()
            c = context.user_data['temp_coach']
            summary = (
                f"📝 <b>مراجعة بيانات المدرب:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"👨‍🏫 الاسم: {c['name']}\n"
                f"🎓 التخصص: {c['spec']}\n"
                f"📞 الهاتف: {c['phone']}\n"
                f"🆔 المعرف: <code>{c['id']}</code>\n"
                f"━━━━━━━━━━━━━━\n"
                f"<b>هل تريد حفظ المدرب في القاعدة؟</b>"
            )
            keyboard = [[InlineKeyboardButton("✅ نعم، احفظ", callback_data="confirm_save_coach")], [InlineKeyboardButton("❌ إلغاء", callback_data="manage_coaches")]]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return


    # --- [ الجزء الخاص بالطلاب والردود الآلية والأسئلة الشائعة ] ---
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

        # تحويل سؤال الطالب للمدرب/المسؤول
        info = f"📩 <b>سؤال جديد من طالب:</b>\nالاسم: {user.full_name}\nالمعرف: <code>{user.id}</code>\n\nالرسالة: {text}"
        try:
            await context.bot.send_message(chat_id=bot_owner_id, text=info, parse_mode="HTML")
            await update.message.reply_text("✅ تم إرسال استفسارك بنجاح، سيتم الرد عليك قريباً.")
        except:
            await update.message.reply_text("⚠️ المعذرة، تعذر التواصل مع الإدارة حالياً.")

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import uuid
import pandas as pd
import io

# كتلة استيراد ملف sheets.py
from sheets import (
    ss, courses_sheet, get_bot_config, get_bot_setting, 
    get_groups_by_course, save_group_to_db, delete_group_by_id, 
    update_group_field, get_all_personnel_list, get_employee_permissions, 
    toggle_employee_permission, toggle_scope_id, check_user_permission, 
    get_all_coaches, delete_coach_from_sheet, add_new_coach_advanced, 
    add_new_course, delete_course_by_id, get_all_categories, 
    get_courses_by_category, get_user_referral_stats, redeem_points_for_course, 
    ensure_permission_row_exists, toggle_quiz_visibility, create_auto_quiz, 
    add_question_to_bank, delete_question_from_bank, get_system_time
)

# كتلة استيراد ملف educational_manager.py
from educational_manager import (
    show_lectures_logic, show_discount_codes_logic, add_discount_start, 
    process_dsc_check, process_dsc_ask_desc, list_all_discounts_ui, 
    view_discount_details_ui, manage_groups_main, start_add_group, 
    confirm_group_save, group_options_ui, confirm_delete_group_ui, 
    manage_control_ui, quiz_create_start_ui, manage_homeworks_main_ui, 
    hw_view_submissions_course_select, homework_add_select_course, 
    hw_add_select_groups_ui, save_homework_to_db, quiz_gen_select_groups_ui, 
    q_bank_manager_ui, browse_q_bank_ui, view_question_details_ui, 
    start_add_question_ui, #quiz_activation_start,
    quiz_activation_groups, 
    employee_quiz_view, quiz_options_ui
)
# كتلة استيراد ملفات المحرك وواجهة المستخدم 
from course_engine import (
    show_course_content_ui, show_student_homeworks_list, show_homework_details
)
from education_bot import start_handler
# --------------------------------------------------------------------------
async def handle_permission_toggle(query, bot_token, employee_id, col_name):
    """تحديث صلاحية الموظف في الشيت وإعادة رسم لوحة التحكم للمالك فوراً"""

    
    # 1. تحديث القيمة في الشيت
    new_status = toggle_employee_permission(bot_token, employee_id, col_name)
    
    # 2. جلب الصلاحيات المحدثة لإعادة رسم الكيبورد
    updated_perms = get_employee_permissions(bot_token, employee_id)
    
    # 3. تحديث الرسالة فوراً للمالك
    await query.edit_message_reply_markup(
        reply_markup=get_permissions_keyboard(bot_token, employee_id, updated_perms)
    )
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
 # دالة توليد أزرار الدورات لاختيارها للموظف
async def show_course_selector(update, context, employee_id):

    
    bot_token = context.bot.token
    # جلب الصلاحيات الحالية لمعرفة ما هو "مختار" سابقاً
    perms = get_employee_permissions(bot_token, employee_id)
    allowed_courses = str(perms.get("الدورات_المسموحة", "")).split(",")
    
    # جلب كل دورات البوت
    all_courses = courses_sheet.get_all_records()
    bot_courses = [c for c in all_courses if str(c['bot_id']) == str(bot_token)]
    
    keyboard = []
    for crs in bot_courses:
        crs_id = str(crs['معرف_الدورة'])
        icon = "☑️" if crs_id in allowed_courses else "✖️"
        # callback يبدأ بـ p_limit لتمييزه
        keyboard.append([InlineKeyboardButton(f"{crs['اسم_الدورة']} {icon}", 
                                             callback_data=f"p_limit_crs_{employee_id}_{crs_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 عودة للصلاحيات", callback_data=f"manage_perms_{employee_id}")])
    
    await update.callback_query.edit_message_text("🎯 اختر الدورات التي يمكن للموظف إدارتها:", 
                                                 reply_markup=InlineKeyboardMarkup(keyboard))
# --------------------------------------------------------------------------
 # --- [ دوال الواجهات المساعدة - نقلت هنا لتوحيد المرجع ] --- 
def get_admin_panel():
    """قائمة الأزرار الرئيسية للوحة تحكم الإدارة"""
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات الذكية", callback_data="admin_stats")],
        [InlineKeyboardButton("📡 الإذاعة المستهدفة", callback_data="smart_broadcast")],
        [InlineKeyboardButton("🛠 الإعدادات التقنية", callback_data="tech_settings")],
        [InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)
# --------------------------------------------------------------------------
# دالة توليد لوحة الصلاحيات (التي أرسلتها أنت)
def get_permissions_keyboard(bot_token, employee_id, current_perms):
    perms_map = {
        "📁 الأقسام": "صلاحية_الأقسام", "📚 الدورات": "صلاحية_الدورات",
        "👨‍🏫 المدربين": "صلاحية_المدربين", "👥 الموظفين": "صلاحية_الموظفين",
        "📊 الإحصائيات": "صلاحية_الإحصائيات", "📢 الإذاعة": "صلاحية_الإذاعة",
        "💬 رسائل خاصة": "صلاحية_الرسائل_الخاصة", "🎟 الكوبونات": "صلاحية_الكوبونات",
        "🏷 أكواد الخصم": "صلاحية_أكواد_الخصم"
    }
    keyboard = []
    items = list(perms_map.items())
    for i in range(0, len(items), 2):
        row = []
        for label, col in items[i:i+2]:
            status = current_perms.get(col, "FALSE")
            icon = "☑️" if str(status).upper() == "TRUE" else "✖️"
            row.append(InlineKeyboardButton(f"{label} {icon}", callback_data=f"p_toggle_{employee_id}_{col}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🎯 تحديد الدورات المسموحة", callback_data=f"p_limit_crs_{employee_id}")])
    keyboard.append([InlineKeyboardButton("🔙 عودة لقائمة الموظفين", callback_data="manage_personnel")])

    return InlineKeyboardMarkup(keyboard)
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
    bot_owner_id = str(config.get("owner_id", "0"))
    admin_list = str(config.get("admin_ids", "0")).split(",")



    await query.answer()
# --------------------------------------------------------------------------
    # 1. معالجة جداول المحاضرات
    if data == "schedules_lectures":

        await show_lectures_logic(update, context)
        
    # 2. فتح لوحة إدارة أكواد الخصم الرئيسية
    elif data == "discount_codes":

        await show_discount_codes_logic(update, context)

    # 3. زر "إضافة كود جديد" (هذا الزر كان مفقوداً في ملفك)
    elif data == "add_discount_start":

        await add_discount_start(update, context)

    # 4. معالجة خطوات التحقق من الدورة والاستمرار
    # التعديل المطلوب لضمان الاستجابة وعدم التجمد:
    elif data.startswith("d_ch_"): # استخدمنا d_ch_ بدلاً من dsc_check_
        course_id = data.replace("d_ch_", "")

        await process_dsc_check(update, context, course_id)

       
    elif data == "dsc_continue":

        await process_dsc_ask_desc(update, context)

    # 5. عرض وإدارة الأكواد للمالك
    elif data == "list_all_discounts":

        await list_all_discounts_ui(update, context)

    # 6. عرض تفاصيل كود محدد
    elif data.startswith("view_disc_"):
        disc_id = data.replace("view_disc_", "")

        await view_discount_details_ui(update, context, disc_id)

    # 7. معالج حذف الكود
    elif data.startswith("confirm_del_disc_"):
        disc_id = data.replace("confirm_del_disc_", "")

        sheet = ss.worksheet("أكواد_الخصم")
        try:
            cell = sheet.find(disc_id, in_column=3)
            if cell:
                sheet.delete_rows(cell.row)
                await query.answer("✅ تم حذف كود الخصم بنجاح!", show_alert=True)

                await list_all_discounts_ui(update, context)
        except:
            await query.answer("❌ فشل الحذف.", show_alert=True)

    # 8. زر العودة للقائمة الرئيسية (تم تصحيح الشرط هنا لضمان تسلسل elif)
    elif data == "main_menu":

        await start_handler(update, context)

    # معالج اربح معنا (تم ربطه بـ elif لضمان الاستجابة)
    elif data == "referral_system":
        # ملاحظة: تم إزالة query.answer() المكررة هنا لأنها تم استدعاؤها في بداية الدالة
        user_id = query.from_user.id
        bot_token = context.bot.token
        
        # جلب يوزر البوت ديناميكياً لتوليد الرابط
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        # جلب إحصائيات الإحالة والرصيد من ملف sheets

        stats = get_user_referral_stats(bot_token, user_id)
        
        text = (
            f"💰 <b>نظام المكافآت والإحالة</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"مرحباً بك! يمكنك الآن الحصول على دوراتنا <b>مجاناً</b> عبر دعوة أصدقائك للمنصة.\n\n"
            f"📢 <b>كيف يعمل النظام؟</b>\n"
            f"1️⃣ انسخ رابطك الفريد أدناه.\n"
            f"2️⃣ شاركه مع أصدقائك أو في مجموعات الدراسة.\n"
            f"3️⃣ مقابل كل شخص يسجل عبرك، ستحصل على <b>نقاط رصيد</b>.\n\n"
            f"🔗 <b>رابط الإحالة الخاص بك:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"📊 <b>إحصائياتك الحالية:</b>\n"
            f"👤 عدد الناجحين في دعوتهم: <b>{stats.get('count', 0)}</b> طالب\n"
            f"💰 رصيدك المكتسب: <b>{stats.get('balance', 0)} نقطة</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 <i>يمكنك استبدال النقاط بفتح الدورات المدفوعة فور وصولك للحد المطلوب.</i>"
        )
        
        # تعديل أزرار قائمة الإحالة لتشمل المتجر
        # السطر 262 يبدأ من هنا تقريباً
        keyboard = [
            [InlineKeyboardButton("🛒 استبدال النقاط بالدورات", callback_data="redeem_store")],
            [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="referral_system")],
            [InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


    # معالج تعطيل/تفعيل الكود مؤقتاً
    elif data.startswith("dsc_tog_"):
        parts = data.split("_")
        disc_id = parts[2]
        new_action = parts[3] # on أو off
        

        sheet = ss.worksheet("أكواد_الخصم")
        try:
            cell = sheet.find(disc_id, in_column=3) # البحث في عمود معرف_الخصم
            if cell:
                new_status = "نشط" if new_action == "on" else "معطل"
                sheet.update_cell(cell.row, 11, new_status) # تحديث العمود 11 (الحالة)
                await query.answer(f"✅ تم تغيير حالة الكود إلى: {new_status}", show_alert=True)
                
                # إعادة تحديث الواجهة لإظهار الحالة الجديدة

                await view_discount_details_ui(update, context, disc_id)
        except Exception as e:
            await query.answer("❌ فشل تحديث الحالة.")

#استبدل النقاط 
    # أضف هذا الشرط داخل دالة contact_callback_handler في education_bot.py
    elif data == "redeem_store":
        await query.answer()

        
        stats = get_user_referral_stats(bot_token, user_id)
        current_balance = stats.get('balance', 0)
        
        # جلب سعر الدورة الموحد من الإعدادات (أو يمكنك جعلها لكل دورة)
        redeem_cost = get_bot_setting(bot_token, "min_points_redeem", default=100)
        
        text = (
            f"🛒 <b>متجر استبدال النقاط</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"رصيدك الحالي: 💰 <b>{current_balance} نقطة</b>\n"
            f"تكلفة فتح أي دورة: 🎫 <b>{redeem_cost} نقطة</b>\n\n"
            f"اختر الدورة التي تود فتحها برصيدك:"
        )
        
        # جلب الدورات المتاحة (يمكنك تعديل هذا لجلب دورات محددة فقط)
        # هنا سنعرض مثالاً لجلب كافة الدورات لتبسيط الاختيار

        courses_ws = ss.worksheet("الدورات_التدريبية")
        all_courses = courses_ws.get_all_records()
        
        keyboard = []
        for course in all_courses:
            if str(course.get('bot_id')) == str(bot_token):
                c_name = course.get('اسم_الدورة')
                c_id = course.get('ID_الدورة')
                
                # زر الشراء يتغير حسب الرصيد
                if float(current_balance) >= float(redeem_cost):
                    keyboard.append([InlineKeyboardButton(f"✅ فتح: {c_name}", callback_data=f"buy_c_{c_id}")])
                else:
                    keyboard.append([InlineKeyboardButton(f"🔒 {c_name} (تحتاج نقاط)", callback_data="insufficient_points")])
        
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="referral_system")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # معالج عملية الشراء الفعلية
    elif data.startswith("buy_c_"):
        course_id = data.replace("buy_c_", "")

        
        redeem_cost = get_bot_setting(bot_token, "min_points_redeem", default=100)
        success, new_balance = redeem_points_for_course(bot_token, user_id, redeem_cost)
        
        if success:
            await query.answer("🎉 مبروك! تم فتح الدورة بنجاح", show_alert=True)
            # هنا يمكنك إضافة كود لإرسال رابط الدورة للطالب أو تسجيله فيها آلياً
            await query.edit_message_text(f"✅ تم شراء الدورة بنجاح!\nرصيدك المتبقي: {new_balance} نقطة.\nيمكنك الآن البدء بالدراسة من القائمة الرئيسية.")
        else:
            await query.answer("❌ فشلت العملية، تأكد من رصيدك.", show_alert=True)
# ربط الدورات بالنقاط
    elif data == "my_profile":
        await query.answer()

        # جلب الدورات التي تسجل فيها الطالب من ورقة سجل_التسجيلات
        reg_sheet = ss.worksheet("سجل_التسجيلات")
        all_regs = reg_sheet.get_all_records()
        
        # تصفية الدورات الخاصة بهذا الطالب في هذا البوت
        student_courses = [
            r for r in all_regs 
            if str(r.get("bot_id")) == str(bot_token) and str(r.get("ID_المستخدم_تيليجرام")) == str(user_id)
        ]

        if not student_courses:
            text = "👤 <b>ملفك الدراسي</b>\n\nأنت غير مشترك في أي دورة حالياً. يمكنك استخدام نقاطك لفتح دورة جديدة!"
            keyboard = [[InlineKeyboardButton("💰 اربح نقاط", callback_data="referral_system")]]
        else:
            text = "👤 <b>ملفك الدراسي</b>\n\nإليك الدورات التي تمتلك حق الوصول إليها:"
            keyboard = []
            for reg in student_courses:
                c_name = reg.get('اسم_الدورة')
                c_id = reg.get('معرف_الدورة')
                keyboard.append([InlineKeyboardButton(f"📖 {c_name}", callback_data=f"open_content_{c_id}")])

        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="main_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # معالج فتح محتوى الدورة
    elif data.startswith("open_content_"):
        course_id = data.replace("open_content_", "")

        await show_course_content_ui(update, context, course_id)

# --------------------------------------------------------------------------

    # --- [ نظام واجبات الطلاب - الروابط ] ---
    elif data == "std_hw_list":

        await show_student_homeworks_list(update, context)

    elif data.startswith("std_hw_view_"):
        hw_id = data.replace("std_hw_view_", "")

        await show_homework_details(update, context, hw_id)

    elif data.startswith("std_hw_upload_"):
        hw_id = data.replace("std_hw_upload_", "")
        context.user_data['action'] = 'awaiting_solution'
        context.user_data['target_hw_id'] = hw_id
        await query.edit_message_text("📤 <b>رفع الحل:</b>\nيرجى إرسال الحل الآن (نص، صورة، أو ملف PDF):", parse_mode="HTML")
# --------------------------------------------------------------------------


 
 
 

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
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
# تحديث قسم إدارة الدورات ليشمل كافة طرق الاستيراد المتاحة
    elif data == "manage_courses":
        await query.edit_message_text(
        "📚 <b>إدارة واستيراد الدورات:</b>\n\nاختر الطريقة التي تفضلها لإضافة البيانات:", 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة دورة فردية", callback_data="start_add_course")],
            [
                InlineKeyboardButton("📥 نصية (|)", callback_data="bulk_add_start")
            ],
            [
                InlineKeyboardButton("📄 ملف CSV", callback_data="csv_import_start"),
                InlineKeyboardButton("🔗 رابط Google Sheet", callback_data="sheet_link_import")
            ],
            [InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")]
        ]), 
        parse_mode="HTML"
    )
# --------------------------------------------------------------------------
    # إضافة هذا القسم للتعامل مع زر إدارة المجموعات
    elif data == "manage_group":
        # بما أن إدارة المجموعات تتطلب معرفة الدورة، سنعرض قائمة الدورات أولاً لاختيار واحدة

        all_courses = courses_sheet.get_all_records()
        bot_courses = [c for c in all_courses if str(c.get('bot_id')) == str(bot_token)]
        
        if not bot_courses:
            await query.edit_message_text("⚠️ لا توجد دورات مضافة حالياً لإنشاء مجموعات لها.")
            return

        keyboard = [[InlineKeyboardButton(f"📖 {c['اسم_الدورة']}", callback_data=f"sel_course_groups_{c['معرف_الدورة']}")] for c in bot_courses]
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_educational")])
        
        await query.edit_message_text("🎯 **اختر الدورة المراد إدارة مجموعاتها:**", reply_markup=InlineKeyboardMarkup(keyboard))

    # معالجة اختيار الدورة للانتقال لملف المجموعات
    elif data.startswith("sel_course_groups_"):
        course_id = data.replace("sel_course_groups_", "")

        await manage_groups_main(update, context, course_id)




# --------------------------------------------------------------------------
    # --- 3. إدارة شؤون المدربين ---
    elif data == "manage_coaches":
        await query.edit_message_text(
            "👨‍🏫 <b>إدارة شؤون المدربين:</b>\nيمكنك إضافة مدربين جدد أو استعراض القائمة الحالية للحذف.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة مدرب جديد", callback_data="start_add_coach")],
                [InlineKeyboardButton("📋 عرض قائمة المدربين", callback_data="list_coaches")],
                [InlineKeyboardButton("🔙 عودة للوحة التحكم", callback_data="back_to_admin")]
            ]), parse_mode="HTML"
        )
# --------------------------------------------------------------------------
    elif data == "setup_ai_start":
        context.user_data['action'] = 'awaiting_institution_name'
        await query.edit_message_text("🤖 <b>إعداد الهوية الذكية:</b>\nيرجى إرسال اسم المنصة التعليمية الآن:")

# --------------------------------------------------------------------------
    # عرض قائمة المدربين كأزرار
    elif data == "list_coaches":

        coaches = get_all_coaches(bot_token)
        if not coaches:
            await query.edit_message_text("⚠️ لا يوجد مدربون مسجلون حالياً.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_coaches")]]))
            return

        keyboard = [[InlineKeyboardButton(f"👤 {c['name']}", callback_data=f"view_coach_{c['id']}")] for c in coaches]
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_coaches")])
        await query.edit_message_text("🎯 **اختر مدرباً لعرض تفاصيله أو حذفه:**", reply_markup=InlineKeyboardMarkup(keyboard))
# --------------------------------------------------------------------------
    # عرض تفاصيل مدرب محدد مع زر الحذف
    elif data.startswith("view_coach_"):
        coach_id = data.replace("view_coach_", "")

        coaches = get_all_coaches(bot_token)
        coach = next((c for c in coaches if str(c['id']) == str(coach_id)), None)
        
        if coach:
            text = f"👤 **معلومات المدرب:**\n━━━━━━━━━━━━━━\nالاسم: {coach['name']}\nID: <code>{coach['id']}</code>"
            keyboard = [
                [InlineKeyboardButton("🗑️ حذف المدرب نهائياً", callback_data=f"del_coach_{coach['id']}")],
                [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="list_coaches")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
# --------------------------------------------------------------------------
    # تنفيذ الحذف الفعلي للمدرب
    elif data.startswith("del_coach_"):
        coach_id = data.replace("del_coach_", "")

        if delete_coach_from_sheet(bot_token, coach_id):
            await query.answer("✅ تم حذف المدرب بنجاح", show_alert=True)
            await query.edit_message_text("✅ تم الحذف. هل تريد إدارة مدرب آخر؟", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 عرض القائمة", callback_data="list_coaches")]]))
        else:
            await query.answer("❌ فشل الحذف", show_alert=True)
# --------------------------------------------------------------------------
    elif data == "bulk_add_start":
        context.user_data['action'] = 'awaiting_bulk_courses'
        instruction = (
            "📥 <b>إضافة دورات دفعة واحدة:</b>\n\n"
            "يرجى إرسال الدورات بحيث يكون كل سطر دورة مستقلة بهذا التنسيق:\n"
            "<code>اسم الدورة |  الوصف وعدد الساعات | السعر | معرف المدرب | معرف القسم</code>\n\n"
            "💡 مثال:\n"
            "<code>دورة البرمجة | 40 | 150 | 873158997 | C1234</code>"
        )
        await query.edit_message_text(instruction, parse_mode="HTML")
# --------------------------------------------------------------------------
#دالة إرسال ملف للموظف وانتظار رفعه الى السيرفر 
    elif data == "excel_import_start":

        
        # تجهيز البيانات العشوائية المترابطة (Sample Data) لضمان فهم الموظف للربط
        # لاحظ أن كلمة "البرمجة" و "أحمد علي" و "بايثون" ستتكرر للربط
        
        sheets_content = {
            "الاقسام": {
                "اسم_القسم": ["البرمجة"],
                "الوصف": ["دورات لغات البرمجة وتطوير المواقع"]
            },
            "المدربين": {
                "اسم_المدرب": ["أحمد علي"],
                "التخصص": ["بايثون"],
                "رقم_الهاتف": ["0501234567"],
                "ID_المدرب": ["873158997"] # معرف تيليجرام
            },
            "الدورات": {
                "الاسم": ["بايثون للمبتدئين"],
                "الوصف": ["دورة شاملة من الصفر - 40 ساعة"],
                "السعر": [150],
                "اسم_المدرب": ["أحمد علي"], # يطابق ورقة المدربين
                "اسم_القسم": ["البرمجة"]      # يطابق ورقة الأقسام
            },
            "المجموعات": {
                "اسم_المجموعة": ["مجموعة التميز A"],
                "اسم_الدورة": ["بايثون للمبتدئين"], # يطابق ورقة الدورات
                "الحد_الأقصى": [25]
            },
            "الموظفين": {
                "اسم_الموظف": ["سارة خالد"],
                "الوظيفة": ["مسؤولة دعم"],
                "رقم_الهاتف": ["0551112223"]
            },
            "قاعده بيانات الطلاب": {
                "الاسم_بالعربي": ["خالد محمد"],
                "رقم_الهاتف": ["0540001112"],
                "البريد_الإلكتروني": ["khaled@test.com"],
                "اسم_الدورة": ["بايثون للمبتدئين"] # يطابق ورقة الدورات
            },
            "الإختبارات الآلية": {
                "اسم_الاختبار": ["اختبار بايثون الأساسي"],
                "اسم_الدورة": ["بايثون للمبتدئين"], # يطابق ورقة الدورات
                "درجة_النجاح": [60]
            },
            "الأسئلة": {
                "اسم_الاختبار": ["اختبار بايثون الأساسي"], # يطابق ورقة الاختبارات
                "نص_السؤال": ["ما هي دالة الطباعة في بايثون؟"],
                "الخيار_1": ["print()"],
                "الخيار_2": ["echo()"],
                "الخيار_3": ["echo()"],
                "الإجابة_الصحيحة": ["print()"]
            },
            "الكوبونات": {
                "كود_الكوبون": ["PROMO2026"],
                "قيمة_الخصم": ["50"],
                "تاريخ_الانتهاء": ["2026-12-31"]
            },
            "اكود الخصم": {
                "كود_الخصم": ["SAVE20"],
                "اسم_الدورة": ["بايثون للمبتدئين"], # يطابق ورقة الدورات
                "قيمة_الخصم": ["20"]
            },
            "الأسئلة الشائعة": {
                "اسم_الدورة": ["بايثون للمبتدئين"], # يطابق ورقة الدورات
                "السؤال": ["هل يوجد شهادة؟"],
                "الإجابة": ["نعم، شهادة معتمدة عند الاجتياز"]
            }
        }

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for name, data in sheets_content.items():
                pd.DataFrame(data).to_excel(writer, index=False, sheet_name=name)
        
        output.seek(0)
        context.user_data['action'] = 'awaiting_excel_file'
        
        caption = (
            "🚀 <b>نموذج الرفع الشامل للمنصة التعليمية:</b>\n\n"
            "يرجى تعبئة الملف مع الالتزام التام بـ <b>قاعدة التطابق:</b>\n"
            "⚠️ <b>الأسماء المرتبطة</b> (مثل اسم الدورة أو القسم) يجب أن ترفع بنفس النص في كافة الأوراق دون اختلاف حرف واحد.\n\n"
            "💡 <b>مثال:</b> إذا سميت القسم 'البرمجة' في ورقة الأقسام، يجب أن تكتبه 'البرمجة' في ورقة الدورات وليس 'برمجة'.\n\n"
            "📦 الملف يحتوي على بيانات تجريبية مترابطة، امسحها وأضف بياناتك الحقيقية."
        )

        await context.bot.send_document(chat_id=query.message.chat_id, document=output, 
                                        filename="نموذج_إدارة_المنصة_الشامل.xlsx", caption=caption, parse_mode="HTML")



    elif data == "csv_import_start":
        context.user_data['action'] = 'awaiting_csv_file'
        await query.edit_message_text("📄 أرسل ملف CSV الآن:")

    elif data == "sheet_link_import":
        context.user_data['action'] = 'awaiting_sheet_link'
        await query.edit_message_text("🔗 أرسل رابط Google Sheet المفتوح للمشاركة:")

# --------------------------------------------------------------------------
    elif data == "start_add_coach":
        context.user_data['action'] = 'await_coach_name'
        await query.edit_message_text("✍️ <b>الخطوة 1:</b> أرسل اسم المدرب الثلاثي:", parse_mode="HTML")

    elif data == "confirm_save_coach":

        c = context.user_data.get('temp_coach')
        
        if not c:
            await query.edit_message_text("⚠️ خطأ: تعذر العثور على البيانات، يرجى إعادة المحاولة من جديد.")
            return

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
            context.user_data.pop('temp_coach', None)
        else:
            await query.edit_message_text("❌ حدث خطأ تقني أثناء الحفظ في قاعدة البيانات.")

# --------------------------------------------------------------------------
    # --- 4. معالجة القسم المختار للدورة وبدء طلب الاسم ---
    elif data.startswith("set_crs_cat_"):
        cat_id = data.replace("set_crs_cat_", "")
        context.user_data['temp_crs_cat'] = cat_id
        context.user_data['action'] = 'awaiting_crs_name'
        await query.edit_message_text("✍️ **الخطوة 2:** أرسل اسم الدورة الآن:")

    elif data == "confirm_save_full_crs":
 

        
        # 1. جلب البيانات المؤقتة (البيانات + معرف القسم)
        d = context.user_data.get('temp_crs')
        cat_id = context.user_data.get('temp_crs_cat') # هذا هو الرابط الضروري
        
        if not d or not cat_id:
            await query.edit_message_text("⚠️ خطأ: تعذر العثور على البيانات المؤقتة، يرجى المحاولة مجدداً.")
            return

        # 2. توليد معرف فريد للدورة
        c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
        
        # 3. تنفيذ الحفظ الفعلي (إرسال الـ 17 متغير بالترتيب)
        success = add_new_course(
            bot_token,          # 1
            c_id,               # 2
            d['name'],          # 3
            d['hours'],         # 4
            d['start_date'],    # 5
            "",                 # 6
            "أونلاين",          # 7
            d['price'],         # 8
            "100",              # 9
            "لا يوجد",          # 10
            "إدارة المنصة",      # 11
            "ADMIN01",          # 12
            "عام",              # 13
            d['coach_user'],    # 14
            d['coach_id'],      # 15
            d['coach_name'],    # 16
            cat_id              # 17. تم إضافة معرف القسم هنا بنجاح!
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
            # تنظيف الذاكرة بعد النجاح
            context.user_data.pop('temp_crs', None)
            context.user_data.pop('temp_crs_cat', None)
        else:
            await query.edit_message_text("❌ فشل الحفظ في قاعدة البيانات، تأكد من إعدادات دالة add_new_course.")

    # --- 5. إدارة الأقسام (عرض القائمة) ---
    elif data == "manage_cats":

        # نتحقق هل لديه صلاحية الأقسام؟
        if not check_user_permission(bot_token, user_id, "صلاحية_الأقسام"):
            await query.answer("🚫 ليس لديك صلاحية لإدارة الأقسام.", show_alert=True)
            return
            
        # إذا كان لديه صلاحية، يكمل الكود الطبيعي...
 
        categories = get_all_categories(bot_token)
        # ... بقية الكود

        
    elif data == "start_add_course":

        categories = get_all_categories(bot_token)
        if not categories:
            await query.edit_message_text("⚠️ أضف قسماً أولاً!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_cats")]]), parse_mode="HTML")
            return
        # اختيار القسم قبل البدء
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"set_crs_cat_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")])
        await query.edit_message_text("🎯 **الخطوة 1:** اختر القسم المخصص للدورة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # --- [ معالجة اختيار المدرب من القائمة ] ---
    elif data.startswith("sel_coach_for_crs_"):
        coach_id = data.replace("sel_coach_for_crs_", "")

        
        # جلب قائمة المدربين للتأكد من الاسم والبيانات
        coaches = get_all_coaches(bot_token)
        coach = next((c for c in coaches if str(c['id']) == str(coach_id)), None)
        
        if coach:
            # تخزين بيانات المدرب في ذاكرة الدورة المؤقتة
            if 'temp_crs' not in context.user_data:
                context.user_data['temp_crs'] = {}
                
            context.user_data['temp_crs'].update({
                'coach_user': "اختيار من القائمة",
                'coach_id': coach['id'],
                'coach_name': coach['name']
            })
            
            # الانتقال للخطوة التالية (تاريخ البداية)
            context.user_data['action'] = 'awaiting_crs_date'
            await query.edit_message_text(
                f"✅ تم اختيار المدرب: <b>{coach['name']}</b>\n\n"
                f"🗓 <b>الخطوة 6:</b> أرسل الآن تاريخ بداية الدورة (مثلاً: 2026/05/01):",
                parse_mode="HTML"
            )
        else:
            await query.answer("⚠️ عذراً، تعذر العثور على بيانات هذا المدرب.", show_alert=True)

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

    elif data.startswith("view_crs_in_"):
        cat_id = data.replace("view_crs_in_", "")

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

    elif data == "add_cat_start":
        context.user_data['action'] = 'awaiting_cat_name'
        await query.edit_message_text(
            "✍️ <b>إضافة قسم جديد:</b>\n\nيرجى إرسال اسم القسم الذي تريد إنشاءه الآن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء العملية", callback_data="manage_cats")]]),
            parse_mode="HTML"
        )

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

    elif data == "exec_delete_cat":
        cat_id = context.user_data.get('selected_cat_id')
        if delete_category_by_id(bot_token, cat_id):
            await query.edit_message_text("✅ <b>تم حذف القسم بنجاح!</b>", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للأقسام", callback_data="manage_cats")]]), parse_mode="HTML")
        else:
            await query.edit_message_text("❌ حدث خطأ أثناء محاولة الحذف.")

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
        await query.edit_message_text(f"📖 <b>إدارة الدورة:</b>\n🆔 المعرف: <code>{course_id}</code>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

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

    elif data == "smart_broadcast":
        await query.edit_message_text("📡 <b>الإذاعة الذكية:</b>", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 للكل", callback_data="bc_all"), InlineKeyboardButton("🎓 لمشتركي دورة", callback_data="bc_course")]]), parse_mode="HTML")





    # --- [ إعدادات الكليشات الذكية ] ---
    elif data == "tech_settings":
        keyboard = [
            [InlineKeyboardButton("📝 كليشة الترحيب الذكية", callback_data="manage_welcome_texts")],
            [InlineKeyboardButton("👨‍🏫 إدارة المدربين", callback_data="manage_coaches"),InlineKeyboardButton("👨‍🏫 إدارة الموظفين", callback_data="manage_personnel")],
            [InlineKeyboardButton("🤖 ضبط الـ AI", callback_data="setup_ai_start"),InlineKeyboardButton("إدارة الفروع", callback_data="manage_branches")],
            [InlineKeyboardButton("🎟 الكوبونات", callback_data="manage_coupons"),InlineKeyboardButton("📢 الإعلانات", callback_data="manage_ads")],
            [InlineKeyboardButton("الإدارة المالية", callback_data="manage_financial"), InlineKeyboardButton("إدارة الفروع", callback_data="manage_branches")],
            [InlineKeyboardButton("المهام الإدارية", callback_data="administrative_tasks"), InlineKeyboardButton("الكنترول", callback_data="manage_control")],
            [InlineKeyboardButton("📊  استيراد البيانات من ملف Excel", callback_data="excel_import_start")], 
            [InlineKeyboardButton("الإدارة التعليمية", callback_data="manage_educational")],
            [InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")]
            ]
        await query.edit_message_text("🛠 <b>الإعدادات التقنية:</b>\nتحكم في نصوص النظام والترحيب الذكي من هنا.", 
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "manage_welcome_texts":
        keyboard = [
            [InlineKeyboardButton("🌅 الصباحية", callback_data="edit_welcome_morning"), InlineKeyboardButton("☀️ الظهرية", callback_data="edit_welcome_noon")],
            [InlineKeyboardButton("🌆 المسائية", callback_data="edit_welcome_evening"), InlineKeyboardButton("🌃 الليلية", callback_data="edit_welcome_night")],
            [InlineKeyboardButton("🔙 عودة", callback_data="tech_settings")]
        ]
        await query.edit_message_text("🖼 <b>تعديل كليشات الترحيب:</b>\nاختر الفترة التي تريد تغيير رسالتها:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("edit_welcome_"):
        period = data.replace("edit_welcome_", "")
        context.user_data['edit_period'] = period
        context.user_data['action'] = 'awaiting_new_welcome_text'
        periods_ar = {"morning": "الصباحية", "noon": "الظهرية", "evening": "المسائية", "night": "الليلية"}
        await query.edit_message_text(f"✍️ <b>تعديل الرسالة {periods_ar[period]}:</b>\n\nأرسل الآن النص الجديد (يمكنك استخدام HTML):")
# --------------------------------------------------------------------------
#قسم الأزرار الاضافية الجديدة 
    elif data == "manage_educational":
        await query.edit_message_text(
            "👨‍🏫 <b>إدارة الشؤون التعليمية :</b>\nيمكنك إضافة مدربين جدد دورات جديدة او اقسام او مجموعات أو استعراض القائمة الحالية للحذف.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 إدارة الأقسام", callback_data="manage_cats"), InlineKeyboardButton("📚 إدارة الدورات", callback_data="manage_courses")],
                [InlineKeyboardButton("المكتبة الشاملة", callback_data="manage_library"), InlineKeyboardButton("الأوسمة والإنجازات", callback_data="honors_achievements")],
                [InlineKeyboardButton("إدارة المجموعات", callback_data="manage_group"), InlineKeyboardButton("الأسئلة الشائعة", callback_data="frequently_guestions")],
                [InlineKeyboardButton("جداول المحاضرات", callback_data="schedules_lectures"), InlineKeyboardButton("أكواد الخصم", callback_data="discount_codes")],
                [InlineKeyboardButton("الإدارة المالية", callback_data="manage_financial"), InlineKeyboardButton("إدارة الفروع", callback_data="manage_branches")],
                [InlineKeyboardButton("🎟 الكوبونات", callback_data="manage_coupons"), InlineKeyboardButton("📢 الإعلانات", callback_data="manage_ads")],
                [InlineKeyboardButton("الكنترول", callback_data="manage_control")],
                [InlineKeyboardButton("المهام الإدارية", callback_data="administrative_tasks"), InlineKeyboardButton("🔙 عودة", callback_data="tech_settings")]
            ]), parse_mode="HTML"
        )
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
    # --- [ قسم إدارة الكنترول والاختبارات ] ---
    
    # 1. الدخول لغرفة الكنترول الرئيسية
    elif data == "manage_control":

        await manage_control_ui(update, context)
#إنشاء الاختبارات الآلية 
    elif data == "manage_quizzes":

        await quiz_create_start_ui(update, context)
    # --------------------------------------------------------------------------
    # ربط نظام إدارة الواجبات (أدمن)
    elif data == "manage_homeworks":

        await manage_homeworks_main_ui(update, context)
        
    elif data == "hw_view_submissions":

        await hw_view_submissions_course_select(update, context)

        
    # --- [ نظام الواجبات - معالجة الأزرار والخطوات ] ---
    elif data == "hw_add_start":

        await homework_add_select_course(update, context)

    elif data.startswith("hw_sel_crs_"):
        course_id = data.replace("hw_sel_crs_", "")

        await hw_add_select_groups_ui(update, context, course_id)

    elif data.startswith("hw_grp_sel_"):
        parts = data.split("_")
        g_id, course_id = parts[3], parts[4]
        auth = context.user_data.get('temp_hw', {'target_groups': []})
        
        if g_id == "ALL":

            all_ids = [str(g['معرف_المجموعة']) for g in get_groups_by_course(bot_token, course_id)]
            if set(all_ids).issubset(set(auth['target_groups'])):
                auth['target_groups'] = [gid for gid in auth['target_groups'] if gid not in all_ids]
            else:
                auth['target_groups'] = list(set(auth['target_groups'] + all_ids))
        else:
            if g_id in auth['target_groups']: auth['target_groups'].remove(g_id)
            else: auth['target_groups'].append(g_id)
        
        context.user_data['temp_hw'] = auth

        await hw_add_select_groups_ui(update, context, course_id)

    elif data == "hw_gen_next_title":
        if not context.user_data.get('temp_hw', {}).get('target_groups'):
            await query.answer("⚠️ يرجى اختيار مجموعة واحدة على الأقل!", show_alert=True)
            return
        context.user_data['action'] = 'awaiting_hw_title'
        await query.edit_message_text("📝 <b>إسناد واجب:</b> أرسل الآن <b>عنوان الواجب</b>:", parse_mode="HTML")

    elif data == "exec_save_hw_final":

        if await save_homework_to_db(bot_token, context.user_data.get('temp_hw')):
            await query.answer("✅ تم إسناد الواجب بنجاح للمجموعات المختارة", show_alert=True)

            await manage_homeworks_main_ui(update, context)
            context.user_data.pop('temp_hw', None)

        
    # --------------------------------------------------------------------------


    elif data.startswith("q_gen_crs_"):
        course_id = data.replace("q_gen_crs_", "")

        await quiz_gen_select_groups_ui(update, context, course_id)

    elif data.startswith("q_gen_grp_"):
        parts = data.split("_")
        g_id = parts[3]
        course_id = parts[4]
        
        if g_id == "ALL":
            context.user_data['temp_quiz']['target_groups'] = ["ALL"]
        else:
            if "ALL" in context.user_data['temp_quiz']['target_groups']:
                context.user_data['temp_quiz']['target_groups'].remove("ALL")
            
            if g_id in context.user_data['temp_quiz']['target_groups']:
                context.user_data['temp_quiz']['target_groups'].remove(g_id)
            else:
                context.user_data['temp_quiz']['target_groups'].append(g_id)
        

        await quiz_gen_select_groups_ui(update, context, course_id)

    elif data == "q_gen_next_settings":
        if not context.user_data.get('temp_quiz', {}).get('target_groups'):
            await query.answer("⚠️ يرجى اختيار مجموعة واحدة على الأقل!", show_alert=True)
            return
        context.user_data['action'] = 'awaiting_quiz_title'
        await query.edit_message_text("🏷 <b>الخطوة 3:</b> أرسل <b>عنواناً للاختبار</b> (مثلاً: اختبار نهاية الفصل الأول):")







    # 2. الدخول لبنك الأسئلة
    elif data == "manage_q_bank":

        await q_bank_manager_ui(update, context)
        #استيراد الأسئلة 
    elif data == "import_q_excel":

        
        # 1. تجهيز بيانات النموذج الإرشادي للأسئلة
        q_sample = {
            'نص السؤال': ['مثال: ما هو عاصمة اليمن؟'],
            'A': ['صنعاء'],
            'B': ['عدن'],
            'C': ['تعز'],
            'D': ['إب'],
            'الإجابة الصحيحة': ['A'],
            'الدرجة': [1],
            'الصعوبة': ['متوسط'],
            'معرف الدورة': ['أدخل هنا ID الدورة']
        }
        
        # 2. إنشاء ملف Excel في الذاكرة (Buffer)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(q_sample).to_excel(writer, index=False, sheet_name='الأسئلة')
        output.seek(0)
        
        # 3. تحديث حالة البوت لانتظار الملف
        context.user_data['action'] = 'awaiting_q_excel'
        
        caption = (
            "📥 <b>نظام استيراد الأسئلة الذكي:</b>\n\n"
            "1️⃣ قمت بإرفاق <b>نموذج Excel</b> جاهز لك.\n"
            "2️⃣ يرجى تعبئة أسئلتك في ورقة <b>(الأسئلة)</b> بنفس الترتيب.\n"
            "3️⃣ تأكد من كتابة حرف الإجابة الصحيحة (A, B, C, D) فقط.\n\n"
            "⚠️ بعد الانتهاء، أرسل الملف هنا بصيغة <b>.xlsx</b> ليتم رفعه للبنك."
        )

        # إرسال الملف مع الشرح
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=output,
            filename="نموذج_استيراد_الأسئلة.xlsx",
            caption=caption,
            parse_mode="HTML"
        )

    elif data == "browse_q_bank":

        await browse_q_bank_ui(update, context)

    elif data.startswith("view_q_det_"):
        q_id = data.replace("view_q_det_", "")

        await view_question_details_ui(update, context, q_id)

    elif data.startswith("exec_del_q_"):
        q_id = data.replace("exec_del_q_", "")

        if delete_question_from_bank(bot_token, q_id):
            await query.answer("🗑️ تم حذف السؤال من البنك بنجاح", show_alert=True)

            await browse_q_bank_ui(update, context)
        else:
            await query.answer("❌ فشل حذف السؤال.")

#ربط  اضافة السؤال اليدوي
    elif data == "add_q_manual":

        await start_add_question_ui(update, context)

    elif data.startswith("sel_q_crs_"):
        course_id = data.replace("sel_q_crs_", "")
        # تخزين معرف الدورة لبدء تسلسل الأسئلة
        context.user_data['temp_q'] = {'course_id': course_id}
        context.user_data['action'] = 'awaiting_q_text'
        await query.edit_message_text("✍️ <b>الخطوة 2:</b> أرسل الآن <b>نص السؤال</b> الذي تود إضافته:")
     # معالجة اختيار الإجابة الصحيحة
    elif data.startswith("set_q_ans_"):
        ans = data.replace("set_q_ans_", "")
        context.user_data['temp_q']['correct'] = ans
        context.user_data['action'] = 'awaiting_q_grade'
        await query.edit_message_text(f"✅ تم تحديد الإجابة الصحيحة: <b>({ans})</b>\n\n🎯 <b>الخطوة 8:</b> أرسل <b>درجة السؤال</b> (أرقام فقط، مثلاً: 5):", parse_mode="HTML")

    # معالجة اختيار مستوى الصعوبة وعرض المراجعة النهائية
    elif data.startswith("set_q_lv_"):
        lv = data.replace("set_q_lv_", "")
        context.user_data['temp_q']['level'] = lv
        q = context.user_data['temp_q']
        summary = (
            f"📝 <b>مراجعة السؤال قبل الحفظ النهائي:</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"📚 الدورة: <code>{q['course_id']}</code>\n"
            f"❓ السؤال: {q['text']}\n"
            f"✅ الإجابة الصحيحة: {q['correct']}\n"
            f"🎯 الدرجة: {q['grade']} | 📊 المستوى: {lv}\n"
            f"━━━━━━━━━━━━━━\n"
            f"هل تريد تأكيد الحفظ في بنك الأسئلة؟"
        )
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احفظ الآن", callback_data="exec_save_question")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="manage_q_bank")]
        ]
        await query.edit_message_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # التنفيذ الفعلي للحفظ في الشيت
    elif data == "exec_save_question":

        q_data = context.user_data.get('temp_q')
        q_data['q_id'] = f"Q{str(uuid.uuid4().int)[:5]}"
        q_data['creator_id'] = str(user_id)
        
        if add_question_to_bank(bot_token, q_data):
            await query.answer("✅ تم حفظ السؤال في بنك الأسئلة بنجاح", show_alert=True)

            await q_bank_manager_ui(update, context)
            context.user_data.pop('temp_q', None)
        else:
            await query.answer("❌ فشل الحفظ في الشيت")

    elif data == "exec_create_quiz_final":

        quiz_data = context.user_data.get('temp_quiz')
        # تحويل القائمة لنص لحفظها في الشيت
        quiz_data['target_groups'] = ",".join(quiz_data['target_groups'])
        quiz_data['coach_id'] = str(user_id)
        
        if create_auto_quiz(bot_token, quiz_data):
            await query.answer("🚀 تم إنشاء الاختبار بنجاح وهو الآن في حالة (مخفي).", show_alert=True)

            await manage_control_ui(update, context)
            context.user_data.pop('temp_quiz', None)
        else:
            await query.answer("❌ فشل الحفظ في الشيت.")


    # 3. بدء تفعيل/إنشاء الاختبارات (اختيار الدورة)
    elif data == "manage_tests":

        await quiz_activation_start(update, context)

    # 4. اختيار المجموعات المستهدفة للاختبار
    elif data.startswith("act_q_crs_"):
        course_id = data.replace("act_q_crs_", "")

        await quiz_activation_groups(update, context, course_id)

    # 5. عرض الاختبارات المتاحة للموظف (الأرشيف)
    elif data == "manage_archiveaq":

        await employee_quiz_view(update, context)

    # 6. تبديل حالة ظهور الاختبار (TRUE/FALSE)
    # معالج تبديل رؤية الاختبار (النسخة المعتمدة والمرنة)
    elif data.startswith("q_toggle_vis_"):
        quiz_id = data.replace("q_toggle_vis_", "")

        
        # 1. تغيير الحالة في الشيت (TRUE <-> FALSE)
        new_status = toggle_quiz_visibility(bot_token, quiz_id)
        
        # 2. إرسال تنبيه سريع للمستخدم بالحالة الجديدة
        await query.answer(f"✅ تم تغيير الحالة إلى: {new_status}")
        
        # 3. تحديث واجهة الخيارات فوراً لإظهار الأيقونة المحدثة (عين أو قفل)

        await quiz_options_ui(update, context, quiz_id)

    # 7. إدارة صلاحيات الموظف (التأسيس الصامت + عرض اللوحة)
    elif data.startswith("setup_p_perms_"):
        person_id = data.replace("setup_p_perms_", "")

        
        # التأكد من وجود سجل في ورقة الهيكل التنظيمي
        ensure_permission_row_exists(bot_token, person_id)
        
        # جلب الصلاحيات وعرض لوحة التحكم (الصح والخطأ)
        current_perms = get_employee_permissions(bot_token, person_id)
        await query.edit_message_text(
            f"🔐 <b>ضبط صلاحيات المستخدم ID:</b> <code>{person_id}</code>",
            reply_markup=get_permissions_keyboard(bot_token, person_id, current_perms),
            parse_mode="HTML"
        )

        
        
        
        
# --------------------------------------------------------------------------

    elif data == "administrative_tasks":
        await query.edit_message_text(
            "أهلاً في إدارة المهام الإدارية، يمكنك إضافة المهام الفردية والجماعية إلى كافة الموظفين أو المدربين.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة مهمة فردية", callback_data="single_missions"), InlineKeyboardButton("➕ إضافة مهمة لمجموعة", callback_data="single_group")],
                [InlineKeyboardButton("➕ إضافة مهمة لدورة", callback_data="single_course"), InlineKeyboardButton("➕ إضافة مهمة جماعية", callback_data="single_all")],
                [InlineKeyboardButton("عرض جميع المهام", callback_data="single_show")],
                [InlineKeyboardButton("🔙 عودة", callback_data="manage_educational")]
            ]), parse_mode="HTML"
        )

               
# --------------------------------------------------------------------------
# أضف هذه الحالات داخل contact_callback_handler في education_bot.py

    # استدعاء واجهة المجموعات الرئيسية لدورة معينة
    elif data.startswith("manage_group_"):
        course_id = data.replace("manage_group_", "")

        await manage_groups_main(update, context, course_id)

    # بدء إضافة مجموعة جديدة
    elif data.startswith("grp_add_start_"):
        course_id = data.replace("grp_add_start_", "")

        await start_add_group(update, context, course_id)

    # اختيار المعلم أثناء الإضافة
    elif data.startswith("sel_teacher_"):
        parts = data.split("_")
        teacher_id = parts[2]
        # جلب الاسم من دالة جلب المدربين السابقة

        coaches = get_all_coaches(bot_token)
        teacher_name = next((c['name'] for c in coaches if str(c['id']) == str(teacher_id)), "مدرب")
        

        await confirm_group_save(update, context, teacher_id, teacher_name)

    # التنفيذ الفعلي للحفظ
    elif data == "exec_save_group":

        group_data = context.user_data.get('temp_grp')
        if save_group_to_db(bot_token, group_data):
            await query.answer("✅ تم إنشاء المجموعة بنجاح", show_alert=True)
            # العودة لواجهة المجموعات

            await manage_groups_main(update, context, group_data['course_id'])
            context.user_data.pop('temp_grp', None)
        else:
            await query.answer("❌ فشل الحفظ في قاعدة البيانات", show_alert=True)

    # عرض خيارات مجموعة معينة (تعديل/حذف)
    elif data.startswith("grp_show_"):
        group_id = data.replace("grp_show_", "")

        await group_options_ui(update, context, group_id)

    # تأكيد الحذف
    elif data.startswith("grp_confirm_del_"):
        group_id = data.replace("grp_confirm_del_", "")

        await confirm_delete_group_ui(update, context, group_id)

    # التنفيذ الفعلي للحذف
    elif data.startswith("grp_exec_del_"):
        group_id = data.replace("grp_exec_del_", "")

        if delete_group_by_id(bot_token, group_id):
            await query.answer("🗑️ تم حذف المجموعة بنجاح", show_alert=True)
            # العودة للقائمة (ستحتاج لتخزين course_id في context.user_data للعودة الصحيحة)
            await query.edit_message_text("✅ تم الحذف. يرجى العودة للقائمة الرئيسية.")
        else:
            await query.answer("❌ فشل الحذف", show_alert=True)

    # التعديلات (تغيير الحالة كمثال سريع)
    elif data.startswith("grp_edit_status_"):
        group_id = data.replace("grp_edit_status_", "")

        # تبديل الحالة بين نشطة ومغلقة
        update_group_field(bot_token, group_id, "حالة_المجموعة", "مغلقة")
        await query.answer("✅ تم تغيير حالة المجموعة إلى مغلقة")

        await group_options_ui(update, context, group_id)

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------



# --------------------------------------------------------------------------
    # --- [ جزء استعراض الطلاب للدورات ] ---
    elif data == "view_courses":

        categories = get_all_categories(bot_token)
        if not categories:
            await query.edit_message_text("⚠️ لا توجد أقسام تعليمية متاحة حالياً.")
            return
        
        # عرض الأقسام كأزرار للطالب
        keyboard = [[InlineKeyboardButton(f"📂 {cat['name']}", callback_data=f"std_cat_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("🔙 عودة للقائمة الرئيسية", callback_data="back_to_student")])
        await query.edit_message_text("🎓 <b>اختر القسم الذي تود استعراض دوراته:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("std_cat_"):
        cat_id = data.replace("std_cat_", "")

        courses = get_courses_by_category(bot_token, cat_id)
        
        if not courses:
            await query.edit_message_text("⚠️ لا توجد دورات متاحة في هذا القسم حالياً.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة للأقسام", callback_data="view_courses")]]))
            return

        keyboard = [[InlineKeyboardButton(f"📘 {crs['name']}", callback_data=f"std_crs_det_{crs['id']}")] for crs in courses]
        keyboard.append([InlineKeyboardButton("🔙 عودة للأقسام", callback_data="view_courses")])
        await query.edit_message_text("📚 <b>الدورات المتاحة في هذا القسم:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "back_to_student":
        await query.edit_message_text("مرحباً بك في القائمة الرئيسية:", reply_markup=get_student_menu())

# --------------------------------------------------------------------------
    if data.startswith("p_limit_crs_"):
        parts = data.split("_")
        emp_id = parts[3]
        target_crs_id = parts[4]
        

        # تحديث القائمة في الشيت (إضافة/حذف ID الدورة)
        toggle_scope_id(bot_token, emp_id, "الدورات_المسموحة", target_crs_id)
        
        # إعادة تحديث الواجهة لإظهار الصح والخطأ الجديد
        await show_course_selector(query, context, emp_id)




# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# أضف هذا الجزء داخل دالة contact_callback_handler في ملف education_bot.py
    elif data == "manage_personnel":

        people = get_all_personnel_list(bot_token)
        
        if not people:
            await query.edit_message_text("⚠️ لا يوجد موظفون أو مدربون مسجلون حالياً.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="tech_settings")]]))
            return

        keyboard = []
        for p in people:
            # نضع الاسم والنوع على الزر، والـ ID مخفي في الـ callback_data
            label = f"👤 {p['name']} ({p['type']})"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"manage_perms_{p['id']}")])
        
        # خيار إضافي في حال أردت إدخال ID غير موجود بالقائمة
        keyboard.append([InlineKeyboardButton("🔍 إدخال ID يدوي", callback_data="ask_emp_id_perms")])
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="tech_settings")])
        
        await query.edit_message_text("👥 <b>اختر الموظف أو المدرب لضبط صلاحياته:</b>", 
                                     reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # 2. عرض لوحة الصلاحيات (الصح ☑️ والخطأ ✖️) فور اختيار الاسم
    elif data.startswith("manage_perms_"):
        emp_id = data.replace("manage_perms_", "")

        
        # جلب الصلاحيات الحالية لعرض حالة الأزرار
        current_perms = get_employee_permissions(bot_token, emp_id)
        
        await query.edit_message_text(
            f"🔐 <b>ضبط صلاحيات المستخدم ID:</b> <code>{emp_id}</code>\n\nاضغط على المهمة لتبديل الحالة:",
            reply_markup=get_permissions_keyboard(bot_token, emp_id, current_perms),
            parse_mode="HTML"
        )

    # 3. معالجة التبديل (Toggle) للصلاحيات الوظيفية
    elif data.startswith("p_toggle_"):
        parts = data.split("_")
        emp_id = parts[2]
        col_name = "_".join(parts[3:])
        # استدعاء الدالة التي أضفتها أنت في نهاية الملف
        await handle_permission_toggle(query, bot_token, emp_id, col_name)

    # 4. فتح واجهة اختيار الدورات المسموحة
    elif data.startswith("p_limit_crs_"):
        parts = data.split("_")
        emp_id = parts[3]
        if len(parts) == 4: # فقط طلب فتح القائمة
            await show_course_selector(query, context, emp_id)
        else: # طلب تبديل دورة محددة
            target_crs_id = parts[4]

            toggle_scope_id(bot_token, emp_id, "الدورات_المسموحة", target_crs_id)
            await show_course_selector(query, context, emp_id)


    elif data == "view_courses_admin": # زر استعراض الدورات للموظف

        
        perms = get_employee_permissions(bot_token, user_id)
        allowed_str = perms.get("الدورات_المسموحة", "")
        
        # جلب كل الدورات وتصفيتها
        all_courses = courses_sheet.get_all_records()
        
        if allowed_str:
            allowed_list = [x.strip() for x in allowed_str.split(",") if x.strip()]
            # تصفية: أظهر فقط الدورات التي تنتمي لهذا البوت وموجودة في قائمة المسموح
            filtered = [c for c in all_courses if str(c['bot_id']) == str(bot_token) and str(c['معرف_الدورة']) in allowed_list]
        else:
            # إذا كان المالك (allowed_str فارغ غالباً)، اعرض الكل
            filtered = [c for c in all_courses if str(c['bot_id']) == str(bot_token)]
            


# --------------------------------------------------------------------------
    elif data == "close_panel":
        await query.edit_message_text("🔒 تم إغلاق لوحة التحكم.")

    elif data == "back_to_admin":
        await query.edit_message_text(f"<b>مرحباً بك مجدداً يا دكتور {query.from_user.first_name}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
# --------------------------------------------------------------------------


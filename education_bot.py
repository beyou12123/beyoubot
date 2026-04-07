import logging
import re
import io
import uuid
import g4f  # لضمان عمل المحرك المجاني الذي اعتمدناه
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, ChatMember
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    ChatMemberHandler, 
    CommandHandler,      # ضروري لأمر /start
    CallbackQueryHandler, # ضروري لعمل الأزرار
    MessageHandler, 
    filters
)

# --- [ ذاكرة المحادثات المؤقتة للطلاب ] ---
user_messages = {} 

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

from educational_manager import manage_groups_main

# إعداد المفتاح الذي حصلت عليه
genai.configure(api_key="AIzaSyCkpHbxvjZNqN_PT8O1yXUAIG-dMAGZj2Y")
model = genai.GenerativeModel('gemini-1.5-flash')
# إعداد السجلات (Logging) لمراقبة أداء البوت وتتبع الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- [ القوائم الرئيسية للمنصة - أزرار واجهة المستخدم ] ---

def get_student_menu():
    keyboard = [
        [InlineKeyboardButton("📚 استعراض الدورات", callback_data="view_categories")],
        [InlineKeyboardButton("👤 ملفي الدراسي", callback_data="my_profile"), 
         InlineKeyboardButton("🎟 تفعيل دورة", callback_data="activate_course")],
        # --- الزر الجديد الذي طلبته ---
        [InlineKeyboardButton("💰 اربح دورات مجانية", callback_data="referral_system")],
        [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="view_faq"),
         InlineKeyboardButton("💬 الدعم الفني", callback_data="contact_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)



def get_admin_panel():
    """قائمة الأزرار الرئيسية للوحة تحكم الإدارة - النسخة المطورة بضبط الـ AI"""
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات الذكية", callback_data="admin_stats")],
        [InlineKeyboardButton("📡 الإذاعة المستهدفة", callback_data="smart_broadcast")],
        [InlineKeyboardButton("🛠 الإعدادات التقنية", callback_data="tech_settings")],
        [InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)
# --------------------------------------------------------------------------

# --- [ المعالجات الأساسية - أمر البداية المحدث بنظام المزامنة والقيود ] ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start برسائل ترحيبية ذكية ودعم نظام الإحالة مع مزامنة القيود"""
    from datetime import datetime
    user = update.effective_user
    bot_token = context.bot.token
    
    # [الخطوة الأهم]: استيراد دالة المزامنة من ملف sheets لضمان تحديث الذاكرة فوراً
    from sheets import sync_bot_limits, get_ai_setup, save_user, link_user_to_inviter
    
    # 1. تنفيذ المزامنة من الشيت إلى context.bot_data لضمان دقة القيود والذكاء الاصطناعي
    sync_success = sync_bot_limits(context, bot_token)
    if not sync_success:
        print(f"⚠️ تحذير تقني: فشل تحديث بيانات الحدود للبوت {bot_token} من الشيت")

    # تحديد هل القادم ضغطة زر أم رسالة نصية لضمان عدم حدوث Error
    query = update.callback_query
    
    # جلب كافة الإعدادات من قاعدة البيانات (ورقة الإعدادات والمحتوى)
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    ai_config = get_ai_setup(bot_token)
    
    # --- [ فحص إعدادات المالك (التهيئة الأولى) ] ---
    if user.id == bot_owner_id:
        if not ai_config or not ai_config.get('اسم_المؤسسة'):
            context.user_data['action'] = 'awaiting_institution_name'
            
            text = (
                "👋 <b>أهلاً بك يا دكتور!</b>\n\n"
                "قبل البدء، يرجى إرسال <b>اسم المنصة التعليمية</b> الخاصة بك:"
            )

            # التنسيق الصحيح للرد حسب نوع التحديث (زر أو رسالة) لضمان استمرار البوت
            if query:
                await query.answer()
                await query.edit_message_text(text, parse_mode="HTML")
            else:
                await update.message.reply_text(text, parse_mode="HTML")
            return

    # --- [ نظام الإحالة (Referral System) ] ---
    # نوضع نظام الإحالة قبل التسجيل لضمان ربط الداعي بالمدعو فوراً
    if context.args and context.args[0].startswith("ref_"):
        inviter_id = context.args[0].replace("ref_", "")
        # التأكد أن الشخص لا يدعو نفسه
        if str(inviter_id) != str(user.id):
            link_user_to_inviter(bot_token, user.id, inviter_id)

    # تسجيل المستخدم في القاعدة
    save_user(user.id, user.username)

    # --- [ محرك اختيار الكليشة الذكي ] ---
    hour = datetime.now().hour
    
    if 5 <= hour < 12:
        msg = config.get("welcome_morning", "صباح العلم والهمة.. أي مهارة سنبني اليوم؟")
    elif 12 <= hour < 17:
        msg = config.get("welcome_noon", "طاب يومك.. الاستمرارية هي سر النجاح، لنكمل التعلم.")
    elif 17 <= hour < 22:
        msg = config.get("welcome_evening", "مساء الفكر المستنير.. حان وقت الحصاد المعرفي.")
    else:
        msg = config.get("welcome_night", "أهلاً بالمثابر.. العظماء يصنعون مستقبلهم في هدوء الليل.")

    # --- [ إرسال الواجهة المناسبة (دعم الزر والرسالة) ] ---
    if user.id == bot_owner_id:
        # واجهة الإدارة (المسؤول) - لوحة تحكم الدكتور
        admin_text = (
            f"<b>مرحباً بك يا دكتور {user.first_name} في مركز قيادة منصتك</b> 🎓\n\n"
            f"{msg}\n\n"
            f"يمكنك إدارة كافة تفاصيل المنصة من الأزرار أدناه:"
        )
        if query:
            await query.answer()
            await query.edit_message_text(admin_text, reply_markup=get_admin_panel(), parse_mode="HTML")
        else:
            await update.message.reply_text(admin_text, reply_markup=get_admin_panel(), parse_mode="HTML")
    else:
        # واجهة الطالب الرئيسية
        student_text = f"<b>{msg}</b>"
        if query:
            await query.answer()
            await query.edit_message_text(student_text, reply_markup=get_student_menu(), parse_mode="HTML")
        else:
            await update.message.reply_text(student_text, reply_markup=get_student_menu(), parse_mode="HTML")



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
# --------------------------------------------------------------------------
    # 1. معالجة جداول المحاضرات
    if data == "schedules_lectures":
        from educational_manager import show_lectures_logic
        await show_lectures_logic(update, context)
        
    # 2. فتح لوحة إدارة أكواد الخصم الرئيسية
    elif data == "discount_codes":
        from educational_manager import show_discount_codes_logic
        await show_discount_codes_logic(update, context)

    # 3. زر "إضافة كود جديد" (هذا الزر كان مفقوداً في ملفك)
    elif data == "add_discount_start":
        from educational_manager import add_discount_start
        await add_discount_start(update, context)

    # 4. معالجة خطوات التحقق من الدورة والاستمرار
    # التعديل المطلوب لضمان الاستجابة وعدم التجمد:
    elif data.startswith("d_ch_"): # استخدمنا d_ch_ بدلاً من dsc_check_
        course_id = data.replace("d_ch_", "")
        from educational_manager import process_dsc_check
        await process_dsc_check(update, context, course_id)

       
    elif data == "dsc_continue":
        from educational_manager import process_dsc_ask_desc
        await process_dsc_ask_desc(update, context)

    # 5. عرض وإدارة الأكواد للمالك
    elif data == "list_all_discounts":
        from educational_manager import list_all_discounts_ui
        await list_all_discounts_ui(update, context)

    # 6. عرض تفاصيل كود محدد
    elif data.startswith("view_disc_"):
        disc_id = data.replace("view_disc_", "")
        from educational_manager import view_discount_details_ui
        await view_discount_details_ui(update, context, disc_id)

    # 7. معالج حذف الكود
    elif data.startswith("confirm_del_disc_"):
        disc_id = data.replace("confirm_del_disc_", "")
        from sheets import ss
        sheet = ss.worksheet("أكواد_الخصم")
        try:
            cell = sheet.find(disc_id, in_column=3)
            if cell:
                sheet.delete_rows(cell.row)
                await query.answer("✅ تم حذف كود الخصم بنجاح!", show_alert=True)
                from educational_manager import list_all_discounts_ui
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
        from sheets import get_user_referral_stats
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
        
        from sheets import ss
        sheet = ss.worksheet("أكواد_الخصم")
        try:
            cell = sheet.find(disc_id, in_column=3) # البحث في عمود معرف_الخصم
            if cell:
                new_status = "نشط" if new_action == "on" else "معطل"
                sheet.update_cell(cell.row, 11, new_status) # تحديث العمود 11 (الحالة)
                await query.answer(f"✅ تم تغيير حالة الكود إلى: {new_status}", show_alert=True)
                
                # إعادة تحديث الواجهة لإظهار الحالة الجديدة
                from educational_manager import view_discount_details_ui
                await view_discount_details_ui(update, context, disc_id)
        except Exception as e:
            await query.answer("❌ فشل تحديث الحالة.")

#استبدل النقاط 
    # أضف هذا الشرط داخل دالة contact_callback_handler في education_bot.py
    elif data == "redeem_store":
        await query.answer()
        from sheets import get_user_referral_stats, get_bot_setting, get_courses_by_category
        
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
        from sheets import ss
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
        from sheets import get_bot_setting, redeem_points_for_course
        
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
        from sheets import ss
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
        from course_engine import show_course_content_ui
        await show_course_content_ui(update, context, course_id)

 
 
 

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


# --- [ إدارة واستيراد الدورات - تصحيح السطر 412 ] ---

    elif data == "manage_courses":
        from sheets import check_user_permission
        user_id = query.from_user.id
        bot_token = context.bot.token
        
        # --------------------------------------------------------------------------
        # جلب الإعدادات وفحص رتبة المستخدم (مالك أو موظف بصلاحية)
        config = get_bot_config(bot_token)
        admin_ids = [int(i.strip()) for i in str(config.get("admin_ids", "0")).split(",") if i.strip().isdigit()]
        is_owner = user_id in admin_ids

        if is_owner or check_user_permission(bot_token, user_id, "صلاحية_الدورات"):
            text = "📚 <b>إدارة واستيراد الدورات:</b>\n\nاختر الطريقة التي تفضلها لإضافة البيانات:"
            keyboard = [
                [InlineKeyboardButton("➕ إضافة دورة فردية", callback_data="start_add_course")],
                [InlineKeyboardButton("📥 إضافة نصية بالجملة (|)", callback_data="bulk_add_start")],
                [
                    InlineKeyboardButton("📄 ملف CSV / Excel", callback_data="csv_import_start"),
                    InlineKeyboardButton("🔗 رابط Google Sheet", callback_data="sheet_link_import")
                ],
                [InlineKeyboardButton("🔙 عودة للوحة التحكم", callback_data="back_to_admin")]
            ]
            
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        else:
            await query.answer("🚫 عذراً، لا تملك صلاحية إدارة الدورات.", show_alert=True)
#=======================================




# --------------------------------------------------------------------------

    # --- [ معالج التحديث اليدوي للبيانات والقيود ] ---
    elif data == "force_sync_limits":
        from sheets import sync_bot_limits
        
        # تنفيذ المزامنة الفورية من الشيت إلى الذاكرة المؤقتة (context.bot_data)
        success = sync_bot_limits(context, bot_token)
        
        if success:
            msg = "✅ <b>تمت المزامنة بنجاح!</b>\nتم تحديث كافة الصلاحيات والحدود البرمجية من قاعدة البيانات."
        else:
            msg = "❌ <b>فشل التحديث!</b>\nيرجى التأكد من اتصال قاعدة البيانات والمحاولة لاحقاً."
            
        await query.answer(msg.replace("<b>", "").replace("</b>", ""), show_alert=True)
        # إعادة عرض لوحة الإعدادات لتأكيد الحالة
        # (يمكنك استدعاء دالة عرض الإعدادات هنا مجدداً)
   
  
  
# --------------------------------------------------------------------------
    # إضافة هذا القسم للتعامل مع زر إدارة المجموعات
    elif data == "manage_group":
        # بما أن إدارة المجموعات تتطلب معرفة الدورة، سنعرض قائمة الدورات أولاً لاختيار واحدة
        from sheets import courses_sheet
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
        from educational_manager import manage_groups_main
        await manage_groups_main(update, context, course_id)

# --- [ قسم إدارة الكنترول والاختبارات ] ---
    
    # 1. الدخول لغرفة الكنترول الرئيسية
    elif data == "manage_control":
        from educational_manager import manage_control_ui
        await manage_control_ui(update, context)
#إنشاء الاختبارات الآلية 
    elif data == "manage_quizzes":
        from educational_manager import quiz_create_start_ui
        await quiz_create_start_ui(update, context)


    # --------------------------------------------------------------------------
# --- [ قسم إدارة الواجبات والحلول ] ---
    
    # 1. الدخول للوحة إدارة الواجبات الرئيسية (أدمن/موظف)
    elif data == "manage_homeworks":
        from educational_manager import manage_homeworks_main_ui
        await manage_homeworks_main_ui(update, context)
        
    # 2. عرض تسليمات الطلاب للتصحيح
    elif data == "hw_view_submissions":
        from educational_manager import hw_view_submissions_course_select
        await hw_view_submissions_course_select(update, context)

    # 3. بدء عملية إسناد واجب جديد
    elif data == "hw_add_start":
        from educational_manager import homework_add_select_course
        await homework_add_select_course(update, context)

    # 4. معالجة اختيار الدورة لإسناد الواجب
    elif data.startswith("hw_sel_crs_"):
        course_id = data.replace("hw_sel_crs_", "")
        from educational_manager import hw_add_select_groups_ui
        await hw_add_select_groups_ui(update, context, course_id)

    # 5. معالجة اختيار المجموعات (نظام التحديد المتعدد للواجبات)
    elif data.startswith("hw_grp_sel_"):
        parts = data.split("_")
        g_id, course_id = parts[3], parts[4]
        # التأكد من تهيئة الذاكرة المؤقتة للواجب
        auth = context.user_data.get('temp_hw', {'target_groups': []})
        
        from sheets import get_groups_by_course
        if g_id == "ALL":
            all_ids = [str(g['معرف_المجموعة']) for g in get_groups_by_course(bot_token, course_id)]
            if set(all_ids).issubset(set(auth.get('target_groups', []))):
                auth['target_groups'] = [gid for gid in auth['target_groups'] if gid not in all_ids]
            else:
                auth['target_groups'] = list(set(auth.get('target_groups', []) + all_ids))
        else:
            if 'target_groups' not in auth: auth['target_groups'] = []
            if g_id in auth['target_groups']: auth['target_groups'].remove(g_id)
            else: auth['target_groups'].append(g_id)
        
        context.user_data['temp_hw'] = auth
        from educational_manager import hw_add_select_groups_ui
        await hw_add_select_groups_ui(update, context, course_id)

    # 6. الانتقال لطلب عنوان الواجب
    elif data == "hw_gen_next_title":
        if not context.user_data.get('temp_hw', {}).get('target_groups'):
            await query.answer("⚠️ يرجى اختيار مجموعة واحدة على الأقل!", show_alert=True)
            return
        context.user_data['action'] = 'awaiting_hw_title'
        await query.edit_message_text("📝 <b>إسناد واجب:</b> أرسل الآن <b>عنوان الواجب</b>:", parse_mode="HTML")

    # 7. التنفيذ النهائي لحفظ الواجب في قاعدة البيانات
    elif data == "exec_save_hw_final":
        from educational_manager import save_homework_to_db, manage_homeworks_main_ui
        if await save_homework_to_db(bot_token, context.user_data.get('temp_hw')):
            await query.answer("✅ تم إسناد الواجب بنجاح للمجموعات المختارة", show_alert=True)
            await manage_homeworks_main_ui(update, context)
            context.user_data.pop('temp_hw', None)

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
        from sheets import get_all_coaches
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
# --------------------------------------------------------------------------
    # تنفيذ الحذف الفعلي للمدرب
    elif data.startswith("del_coach_"):
        coach_id = data.replace("del_coach_", "")
        from sheets import delete_coach_from_sheet
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
        import pandas as pd
        import io
        
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
        from sheets import add_new_coach_advanced
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
        await query.edit_message_text("✍️ <b>الخطوة 1:</b> أرسل <b>اسم الدورة</b> الآن:", parse_mode="HTML")

    # --- [ معالج اختيار الفرع من الأزرار ] ---
    elif data.startswith("sel_br_"):
        parts = data.split("_")
        br_id = parts[2]
        # جلب الاسم للمراجعة
        from sheets import get_all_branches
        branches = get_all_branches(bot_token)
        branch = next((b for b in branches if str(b['id']) == str(br_id)), None)
        
        context.user_data['temp_crs_step']['branch_id'] = br_id
        context.user_data['temp_crs_step']['branch_name'] = branch['name'] if branch else "الفرع الرئيسي"
        
        context.user_data['action'] = 'awaiting_crs_price'
        await query.edit_message_text(f"✅ تم اختيار فرع: <b>{context.user_data['temp_crs_step']['branch_name']}</b>\n💰 <b>الخطوة 4:</b> أرسل <b>رسوم الدورة</b> الآن:", parse_mode="HTML")

    # --- [ معالج اختيار المدرب من الأزرار ] ---
    elif data.startswith("sel_co_"):
        co_id = data.replace("sel_co_", "")
        from sheets import get_all_coaches_list
        coaches = get_all_coaches_list(bot_token)
        coach = next((c for c in coaches if str(c['id']) == str(co_id)), None)
        
        context.user_data['temp_crs_step'].update({
            'coach_id': co_id,
            'coach_name': coach['name'] if coach else "مدرب",
            'coach_user': "0" # قيمة افتراضية
        })
        
        context.user_data['action'] = 'awaiting_crs_max_students'
        await query.edit_message_text(f"✅ المدرب المعتمد: <b>{context.user_data['temp_crs_step']['coach_name']}</b>\n👥 <b>الخطوة 6:</b> أرسل <b>الحد الأقصى للطلاب</b>:", parse_mode="HTML")

    # --- [ معالج اختيار الموظف المسؤول ] ---
    elif data.startswith("sel_st_"):
        st_id = data.replace("sel_st_", "")
        from sheets import get_all_personnel
        staff = get_all_personnel(bot_token)
        emp = next((s for s in staff if str(s['id']) == str(st_id)), None)
        
        context.user_data['temp_crs_step'].update({
            'emp_id': st_id,
            'emp_name': emp['name'] if emp else "إدارة المنصة"
        })
        
        context.user_data['action'] = 'awaiting_crs_campaign'
        await query.edit_message_text(f"👤 المسؤول: <b>{context.user_data['temp_crs_step']['emp_name']}</b>\n📢 <b>الخطوة 7:</b> أرسل <b>معرف الحملة الإعلانية</b> (أو 0):", parse_mode="HTML")
# --------------------------------------------------------------------------

    # --- 5. إدارة الأقسام (عرض القائمة) ---
    elif data == "manage_cats":
        from sheets import check_user_permission, get_all_categories
        if not check_user_permission(bot_token, user_id, "صلاحية_الأقسام"):
            await query.answer("🚫 ليس لديك صلاحية لإدارة الأقسام.", show_alert=True)
            return
        categories = get_all_categories(bot_token)
        keyboard = [[InlineKeyboardButton(f"📁 {cat.get('اسم_القسم')}", callback_data=f"edit_cat_{cat.get('معرف_القسم')}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="add_cat_start")])
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_educational")])
        await query.edit_message_text("📁 <b>إدارة الأقسام التعليمية</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

        # 1. التحقق من الصلاحية
        if not check_user_permission(bot_token, user_id, "صلاحية_الأقسام"):
            await query.answer("🚫 ليس لديك صلاحية لإدارة الأقسام.", show_alert=True)
            return # هذه الـ return تمنع إكمال الكود لغير المخولين
            
        # 2. جلب الأقسام
        categories = get_all_categories(bot_token)
        
        # 3. بناء الأزرار
        keyboard = []
        if categories:
            for cat in categories:
                keyboard.append([InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"edit_cat_{cat['id']}")])
        
        keyboard.append([InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="add_cat_start")])
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_educational")])
        
    # --- 6. إضافة دورة فردية (تحديد القسم أولاً) ---
    elif data == "start_add_course":
        from sheets import get_all_categories
        categories = get_all_categories(bot_token)
        # 4. تحديث الرسالة
        await query.edit_message_text(
            "📁 <b>إدارة الأقسام التعليمية</b>\n\nاختر قسماً لإدارته أو أضف قسماً جديداً:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return # <--- هنا مكانها الصحيح (بمحاذاة كلمة await)

            
        # اختيار القسم قبل البدء
        # بدلاً من cat['name'] و cat['id']، استخدم:
        keyboard = [[InlineKeyboardButton(f"📁 {cat.get('اسم_القسم')}", callback_data=f"set_crs_cat_{cat.get('معرف_القسم')}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")])
        await query.edit_message_text("🎯 **الخطوة 1:** اختر القسم المخصص للدورة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # --- [ معالجة اختيار المدرب من القائمة ] ---
    elif data.startswith("sel_coach_for_crs_"):
        coach_id = data.replace("sel_coach_for_crs_", "")
        from sheets import get_all_coaches
        
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
            [InlineKeyboardButton("المهام الإدارية", callback_data="administrative_tasks"), InlineKeyboardButton("🔄 تحديث بيانات الاشتراك", callback_data="force_sync_limits")],
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
# --------------------------------------------------------------------------


    elif data.startswith("q_gen_crs_"):
        course_id = data.replace("q_gen_crs_", "")
        from educational_manager import quiz_gen_select_groups_ui
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
        
        from educational_manager import quiz_gen_select_groups_ui
        await quiz_gen_select_groups_ui(update, context, course_id)

    elif data == "q_gen_next_settings":
        if not context.user_data.get('temp_quiz', {}).get('target_groups'):
            await query.answer("⚠️ يرجى اختيار مجموعة واحدة على الأقل!", show_alert=True)
            return
        context.user_data['action'] = 'awaiting_quiz_title'
        await query.edit_message_text("🏷 <b>الخطوة 3:</b> أرسل <b>عنواناً للاختبار</b> (مثلاً: اختبار نهاية الفصل الأول):")







    # 2. الدخول لبنك الأسئلة
    elif data == "manage_q_bank":
        from educational_manager import q_bank_manager_ui
        await q_bank_manager_ui(update, context)
        #استيراد الأسئلة 
    elif data == "import_q_excel":
        import pandas as pd
        import io
        
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
        from educational_manager import browse_q_bank_ui
        await browse_q_bank_ui(update, context)

    elif data.startswith("view_q_det_"):
        q_id = data.replace("view_q_det_", "")
        from educational_manager import view_question_details_ui
        await view_question_details_ui(update, context, q_id)

    elif data.startswith("exec_del_q_"):
        q_id = data.replace("exec_del_q_", "")
        from sheets import delete_question_from_bank
        if delete_question_from_bank(bot_token, q_id):
            await query.answer("🗑️ تم حذف السؤال من البنك بنجاح", show_alert=True)
            from educational_manager import browse_q_bank_ui
            await browse_q_bank_ui(update, context)
        else:
            await query.answer("❌ فشل حذف السؤال.")

#ربط  اضافة السؤال اليدوي
    elif data == "add_q_manual":
        from educational_manager import start_add_question_ui
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
        from sheets import add_question_to_bank
        import uuid
        q_data = context.user_data.get('temp_q')
        q_data['q_id'] = f"Q{str(uuid.uuid4().int)[:5]}"
        q_data['creator_id'] = str(user_id)
        
        if add_question_to_bank(bot_token, q_data):
            await query.answer("✅ تم حفظ السؤال في بنك الأسئلة بنجاح", show_alert=True)
            from educational_manager import q_bank_manager_ui
            await q_bank_manager_ui(update, context)
            context.user_data.pop('temp_q', None)
        else:
            await query.answer("❌ فشل الحفظ في الشيت")

    elif data == "exec_create_quiz_final":
        from sheets import create_auto_quiz
        quiz_data = context.user_data.get('temp_quiz')
        # تحويل القائمة لنص لحفظها في الشيت
        quiz_data['target_groups'] = ",".join(quiz_data['target_groups'])
        quiz_data['coach_id'] = str(user_id)
        
        if create_auto_quiz(bot_token, quiz_data):
            await query.answer("🚀 تم إنشاء الاختبار بنجاح وهو الآن في حالة (مخفي).", show_alert=True)
            from educational_manager import manage_control_ui
            await manage_control_ui(update, context)
            context.user_data.pop('temp_quiz', None)
        else:
            await query.answer("❌ فشل الحفظ في الشيت.")


    # 3. بدء تفعيل/إنشاء الاختبارات (اختيار الدورة)
    elif data == "manage_tests":
        from educational_manager import quiz_activation_start
        await quiz_activation_start(update, context)

    # 4. اختيار المجموعات المستهدفة للاختبار
    elif data.startswith("act_q_crs_"):
        course_id = data.replace("act_q_crs_", "")
        from educational_manager import quiz_activation_groups
        await quiz_activation_groups(update, context, course_id)

    # 5. عرض الاختبارات المتاحة للموظف (الأرشيف)
    elif data == "manage_archiveaq":
        from educational_manager import employee_quiz_view
        await employee_quiz_view(update, context)

    # 6. تبديل حالة ظهور الاختبار (TRUE/FALSE)
    # معالج تبديل رؤية الاختبار (النسخة المعتمدة والمرنة)
    elif data.startswith("q_toggle_vis_"):
        quiz_id = data.replace("q_toggle_vis_", "")
        from sheets import toggle_quiz_visibility
        
        # 1. تغيير الحالة في الشيت (TRUE <-> FALSE)
        new_status = toggle_quiz_visibility(bot_token, quiz_id)
        
        # 2. إرسال تنبيه سريع للمستخدم بالحالة الجديدة
        await query.answer(f"✅ تم تغيير الحالة إلى: {new_status}")
        
        # 3. تحديث واجهة الخيارات فوراً لإظهار الأيقونة المحدثة (عين أو قفل)
        from educational_manager import quiz_options_ui
        await quiz_options_ui(update, context, quiz_id)

    # 7. إدارة صلاحيات الموظف (التأسيس الصامت + عرض اللوحة)
    elif data.startswith("setup_p_perms_"):
        person_id = data.replace("setup_p_perms_", "")
        from sheets import ensure_permission_row_exists, get_employee_permissions
        
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
        from educational_manager import manage_groups_main
        await manage_groups_main(update, context, course_id)

    # بدء إضافة مجموعة جديدة
    elif data.startswith("grp_add_start_"):
        course_id = data.replace("grp_add_start_", "")
        from educational_manager import start_add_group
        await start_add_group(update, context, course_id)

    # اختيار المعلم أثناء الإضافة
    elif data.startswith("sel_teacher_"):
        parts = data.split("_")
        teacher_id = parts[2]
        # جلب الاسم من دالة جلب المدربين السابقة
        from sheets import get_all_coaches
        coaches = get_all_coaches(bot_token)
        teacher_name = next((c['name'] for c in coaches if str(c['id']) == str(teacher_id)), "مدرب")
        
        from educational_manager import confirm_group_save
        await confirm_group_save(update, context, teacher_id, teacher_name)

    # التنفيذ الفعلي للحفظ
    elif data == "exec_save_group":
        from sheets import save_group_to_db
        group_data = context.user_data.get('temp_grp')
        if save_group_to_db(bot_token, group_data):
            await query.answer("✅ تم إنشاء المجموعة بنجاح", show_alert=True)
            # العودة لواجهة المجموعات
            from educational_manager import manage_groups_main
            await manage_groups_main(update, context, group_data['course_id'])
            context.user_data.pop('temp_grp', None)
        else:
            await query.answer("❌ فشل الحفظ في قاعدة البيانات", show_alert=True)

    # عرض خيارات مجموعة معينة (تعديل/حذف)
    elif data.startswith("grp_show_"):
        group_id = data.replace("grp_show_", "")
        from educational_manager import group_options_ui
        await group_options_ui(update, context, group_id)

    # تأكيد الحذف
    elif data.startswith("grp_confirm_del_"):
        group_id = data.replace("grp_confirm_del_", "")
        from educational_manager import confirm_delete_group_ui
        await confirm_delete_group_ui(update, context, group_id)

    # التنفيذ الفعلي للحذف
    elif data.startswith("grp_exec_del_"):
        group_id = data.replace("grp_exec_del_", "")
        from sheets import delete_group_by_id
        if delete_group_by_id(bot_token, group_id):
            await query.answer("🗑️ تم حذف المجموعة بنجاح", show_alert=True)
            # العودة للقائمة (ستحتاج لتخزين course_id في context.user_data للعودة الصحيحة)
            await query.edit_message_text("✅ تم الحذف. يرجى العودة للقائمة الرئيسية.")
        else:
            await query.answer("❌ فشل الحذف", show_alert=True)

    # التعديلات (تغيير الحالة كمثال سريع)
    elif data.startswith("grp_edit_status_"):
        group_id = data.replace("grp_edit_status_", "")
        from sheets import update_group_field
        # تبديل الحالة بين نشطة ومغلقة
        update_group_field(bot_token, group_id, "حالة_المجموعة", "مغلقة")
        await query.answer("✅ تم تغيير حالة المجموعة إلى مغلقة")
        from educational_manager import group_options_ui
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
        from sheets import get_all_categories
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
        from sheets import get_courses_by_category
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
        
        from sheets import toggle_scope_id
        # تحديث القائمة في الشيت (إضافة/حذف ID الدورة)
        toggle_scope_id(bot_token, emp_id, "الدورات_المسموحة", target_crs_id)
        
        # إعادة تحديث الواجهة لإظهار الصح والخطأ الجديد
        await show_course_selector(query, context, emp_id)




# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# أضف هذا الجزء داخل دالة contact_callback_handler في ملف education_bot.py
    elif data == "manage_personnel":
        from sheets import get_all_personnel_list
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
        from sheets import get_employee_permissions
        
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
            from sheets import toggle_scope_id
            toggle_scope_id(bot_token, emp_id, "الدورات_المسموحة", target_crs_id)
            await show_course_selector(query, context, emp_id)


    elif data == "view_courses_admin": # زر استعراض الدورات للموظف
        from sheets import get_employee_permissions, courses_sheet
        
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

# دالة معالجة التبديل (Toggle) في CallbackQueryHandler
# تذكر إضافتها داخل contact_callback_handler
async def handle_permission_toggle(query, bot_token, employee_id, col_name):
    from sheets import toggle_employee_permission, get_employee_permissions
    
    # 1. تحديث القيمة في الشيت
    new_status = toggle_employee_permission(bot_token, employee_id, col_name)
    
    # 2. جلب الصلاحيات المحدثة لإعادة رسم الكيبورد
    updated_perms = get_employee_permissions(bot_token, employee_id)
    
    # 3. تحديث الرسالة فوراً للمالك
    await query.edit_message_reply_markup(
        reply_markup=get_permissions_keyboard(bot_token, employee_id, updated_perms)
    )
 
 
 # دالة توليد أزرار الدورات لاختيارها للموظف
async def show_course_selector(update, context, employee_id):
    from sheets import courses_sheet, get_employee_permissions
    
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
#دالة فحص الطلاب وإرسال الرسائل 
async def activation_monitor(context: ContextTypes.DEFAULT_TYPE):
    """وظيفة خلفية تراقب تفعيلات الطلاب وترسل تنبيهات فورا"""
    bot_token = context.bot.token
    from sheets import get_newly_activated_students, ss
    
    new_activations = get_newly_activated_students(bot_token)
    
    for student in new_activations:
        try:
            msg = (
                f"🎉 <b>تهانينا يا {student['name']}!</b>\n\n"
                f"تم تفعيل اشتراكك في الدورة بنجاح. ✅\n"
                f"يمكنك الآن الدخول إلى 👤 <b>(ملفي الدراسي)</b> لمشاهدة كافة الدروس والمحتوى المدفوع.\n\n"
                f"نتمنى لك رحلة تعليمية ممتعة! 🚀"
            )
            await context.bot.send_message(chat_id=student['user_id'], text=msg, parse_mode="HTML")
            
            # تحديث الشيت لكي لا يرسل الرسالة مرة أخرى
            sheet = ss.worksheet("قاعدة_بيانات_الطلاب")
            sheet.update_cell(student['row'], 21, f"تم الإشعار: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            print(f"⚠️ فشل إرسال إشعار للطالب {student['user_id']}: {e}")

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# --- [ معالج الرسائل النصية (Message Handler) ] ---
# --------------------------------------------------------------------------
# ملاحظة هامة: يجب أن يكون السطر التالي في أعلى الملف تماماً خارج كل الدوال:
async def handle_contact_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة كافة الرسائل النصية والربط مع محرك g4f لخدمة الطلاب مع بقاء مهام المسؤول كاملة"""
    
    if not update.message: return
    
    # تنظيف النص من المسافات فور وصوله
    text = update.message.text.strip() if update.message.text else ""
    user = update.effective_user
    bot_token = context.bot.token
    
    # محاولة جلب الإعدادات ومعرف المسؤول
    try:
        from sheets import get_bot_config
        config = get_bot_config(bot_token)
        bot_owner_id = int(config.get("admin_ids", 0))
    except Exception as e:
        print(f"⚠️ Error getting config: {e}")
        bot_owner_id = 0 # قيمة افتراضية في حال فشل الجلب
        
    action = context.user_data.get('action')

# --------------------------------------------------------------------------
#معالجة المستندات 
    if update.message.document:
        action = context.user_data.get('action')
        doc = update.message.document
        
        if action == 'awaiting_excel_file':
            import pandas as pd
            import os, uuid
            from sheets import add_new_course, add_new_category, add_new_coach_advanced
            
            file = await context.bot.get_file(doc.file_id)
            file_path = f"temp_{uuid.uuid4().hex}_{doc.file_name}"
            await file.download_to_drive(file_path)
            
            try:
                xls = pd.ExcelFile(file_path)
                # --- [ مخازن الربط الذكي - القواميس ] ---
                cat_map = {}    # لربط اسم القسم بـ ID
                coach_map = {}  # لربط اسم المدرب بـ ID
                course_map = {} # لربط اسم الدورة بـ ID
                test_map = {}   # لربط اسم الاختبار بـ ID
                
                results = {"الأقسام": 0, "المدربين": 0, "الدورات": 0, "المجموعات": 0, "الطلاب": 0, "الاختبارات": 0, "الأسئلة": 0}

                # 1️⃣ معالجة الأقسام (الأساس)
                if 'الاقسام' in xls.sheet_names:
                    df = pd.read_excel(xls, 'الاقسام').fillna("")
                    for _, r in df.iterrows():
                        c_id = f"C{str(uuid.uuid4().int)[:4]}"
                        name = str(r.get('اسم_القسم', '')).strip()
                        if name and add_new_category(bot_token, c_id, name):
                            cat_map[name] = c_id
                            results["الأقسام"] += 1

                # 2️⃣ معالجة المدربين
                if 'المدربين' in xls.sheet_names:
                    df = pd.read_excel(xls, 'المدربين').fillna("")
                    for _, r in df.iterrows():
                        c_id = str(r.get('ID_المدرب', uuid.uuid4().int % 1000000000)).strip()
                        name = str(r.get('اسم_المدرب', '')).strip()
                        if name and add_new_coach_advanced(bot_token, c_id, name, str(r.get('التخصص', '')), str(r.get('رقم_الهاتف', ''))):
                            coach_map[name] = c_id
                            results["المدربين"] += 1

                # 3️⃣ معالجة الدورات (الربط بالأقسام والمدربين)
                if 'الدورات' in xls.sheet_names:
                    df = pd.read_excel(xls, 'الدورات').fillna("")
                    for _, r in df.iterrows():
                        c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
                        c_name = str(r.get('الاسم', '')).strip()
                        # الربط الآلي: البحث عن ID القسم والمدرب باستخدام أسمائهم
                        cat_id = cat_map.get(str(r.get('اسم_القسم', '')).strip(), "C000")
                        coach_id = coach_map.get(str(r.get('اسم_المدرب', '')).strip(), "000")
                        
                        if add_new_course(bot_token, c_id, c_name, str(r.get('الوصف', '')), "2026-01-01", "", "أونلاين", 
                                         str(r.get('السعر', '0')), "100", "لا يوجد", "إدارة", "ADM", "رفع_شامل", 
                                         "Admin", coach_id, str(r.get('اسم_المدرب', '')), cat_id):
                            course_map[c_name] = c_id
                            results["الدورات"] += 1

                # 4️⃣ معالجة المجموعات والطلاب (الربط باسم الدورة)
                # يتم تكرار نفس النمط لبقية الـ 11 ورقة باستخدام course_map للربط
                
                report = "✅ <b>اكتمل الرفع والربط الشامل:</b>\n\n" + "\n".join([f"🔹 {k}: {v}" for k, v in results.items() if v > 0])
                await update.message.reply_text(report, parse_mode="HTML")

            except Exception as e:
                await update.message.reply_text(f"❌ خطأ حرج في المعالجة: {str(e)}")
            finally:
                if os.path.exists(file_path): os.remove(file_path)
            
            context.user_data['action'] = None
            return

            
            
           
# --------------------------------------------------------------------------
     
# --------------------------------------------------------------------------
    # --- [ الجزء الخاص بالمسؤول - إدارة المحتوى والدورات ] ---
    if user.id == bot_owner_id:
    	
    # --- [ معالجة خطوات إضافة كود الخصم نصياً ] ---
        if action == 'awaiting_dsc_desc':
            from educational_manager import validate_dsc_desc
            await validate_dsc_desc(update, context)
            return

        elif action == 'awaiting_dsc_value':
            from educational_manager import validate_dsc_value
            await validate_dsc_value(update, context)
            return

        elif action == 'awaiting_dsc_expiry':
            from educational_manager import validate_dsc_expiry
            await validate_dsc_expiry(update, context)
            return

        elif action == 'awaiting_dsc_max':
            from educational_manager import validate_dsc_max
            await validate_dsc_max(update, context)
            return

   
    
    
        # --- [ معالجة إضافة قسم جديد مع فحص القيود الصارم ] ---
        if action == 'awaiting_cat_name':
            
            from sheets import add_new_category, check_bot_limits_fast, sync_bot_limits
            
            # 1. الفحص السريع من الذاكرة المؤقتة (بوابة العبور)
            allowed, limit_msg = check_bot_limits_fast(context, "section")
            
            if not allowed:
                # في حال تجاوز الحد، نلغي العملية ونرسل الرسالة التسويقية للترقية
                context.user_data['action'] = None
                await update.message.reply_text(
                    f"⚠️ <b>تنبيه القيود الإدارية:</b>\n\n{limit_msg}", 
                    parse_mode="HTML"
                )
                return

            # 2. الاستمرار في الإجراء الأصلي (بدون أي حذف أو تغيير)
            cat_id = f"C{str(uuid.uuid4().int)[:4]}"
            if add_new_category(bot_token, cat_id, text):
                context.user_data['action'] = None
                
                # تحديث الذاكرة فوراً لضمان دقة العداد في المرة القادمة
                sync_bot_limits(context, bot_token)
                
                await update.message.reply_text(
                    f"✅ <b>تم إنشاء القسم بنجاح:</b> <b>{text}</b>", 
                    reply_markup=get_admin_panel(), 
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("❌ فشل الحفظ في قاعدة البيانات، يرجى المحاولة لاحقاً.")
            return

        # --- [ استقبال ID الموظف لفتح لوحة صلاحياته (النسخة المعتمدة والأقوى) ] ---
        elif action == 'awaiting_emp_id_for_perms':
            emp_id = text
            context.user_data['action'] = None
            
            # استيراد الوظائف المطلوبة من الشيت
            from sheets import get_employee_permissions, sync_bot_limits
            
            # [إجراء احترافي]: تحديث بيانات البوت قبل عرض الصلاحيات لضمان دقة العمل
            sync_bot_limits(context, bot_token)
            
            # جلب الصلاحيات الحالية من الشيت لعرض الأزرار بشكل صحيح
            current_perms = get_employee_permissions(bot_token, emp_id)
            
            await update.message.reply_text(
                f"🔐 <b>تم العثور على الموظف:</b> <code>{emp_id}</code>\n\n"
                f"قم بضبط الصلاحيات المطلوبة بالضغط على الأزرار أدناه:", 
                reply_markup=get_permissions_keyboard(bot_token, emp_id, current_perms), 
                parse_mode="HTML"
            )
            return


            
        # تعديل اسم قسم
        elif action == 'awaiting_new_cat_name':
            cat_id = context.user_data.get('selected_cat_id')
            from sheets import update_category_name
            if update_category_name(bot_token, cat_id, text):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم تحديث اسم القسم إلى: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # إضافة دورة بسيطة
        elif action == 'awaiting_course_name':
            import uuid
            course_cat = context.user_data.get('temp_course_cat')
            course_id = f"CRS{str(uuid.uuid4().int)[:4]}"
            from sheets import add_new_course
            if add_new_course(bot_token, course_id, text, course_cat):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إضافة الدورة بنجاح: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # تسلسل إضافة دورة احترافي (الخطوة 2: الاسم)
        # --- [ مسار إضافة دورة متسلسل ومطابق للـ 18 عمود ] ---
        
        if action == 'awaiting_crs_name':
            from sheets import check_bot_limits_fast
            allowed, limit_msg = check_bot_limits_fast(context, "course")
            if not allowed:
                context.user_data['action'] = None
                await update.message.reply_text(f"⚠️ <b>تنبيه القيود:</b>\n{limit_msg}", parse_mode="HTML")
                return
            context.user_data['temp_crs_step'] = {'name': text}
            context.user_data['action'] = 'awaiting_crs_desc'
            await update.message.reply_text("✅ تم اعتماد الاسم.\n✍️ <b>الخطوة 2:</b> أرسل <b>وصف الدورة</b>:", parse_mode="HTML")
            return

        elif action == 'awaiting_crs_desc':
            context.user_data['temp_crs_step']['desc'] = text
            from sheets import get_all_branches
            branches = get_all_branches(bot_token)
            if not branches:
                context.user_data['temp_crs_step'].update({'branch_id': "MAIN-01", 'branch_name': "الفرع الرئيسي"})
                context.user_data['action'] = 'awaiting_crs_price'
                await update.message.reply_text("⚠️ لا يوجد فروع، سيتم استخدام الافتراضي.\n💰 <b>الخطوة 4:</b> أرسل <b>الرسوم</b>:", parse_mode="HTML")
            else:
                keyboard = [[InlineKeyboardButton(b['name'], callback_data=f"sel_br_{b['id']}")] for b in branches]
                await update.message.reply_text("🏢 <b>الخطوة 3:</b> اختر <b>الفرع</b> المسؤول:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        elif action == 'awaiting_crs_price':
            if not text.isdigit():
                await update.message.reply_text("⚠️ أرسل السعر أرقام فقط:")
                return
            context.user_data['temp_crs_step']['price'] = text
            context.user_data['action'] = 'awaiting_crs_days'
            await update.message.reply_text("🗓 <b>الخطوة 5:</b> أرسل <b>عدد أيام الدورة</b>:")
            return

        elif action == 'awaiting_crs_days':
            if not text.isdigit():
                await update.message.reply_text("⚠️ أرسل الأيام أرقام فقط:")
                return
            from sheets import get_system_time
            from datetime import datetime, timedelta
            start_date = get_system_time("date")
            end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=int(text))).strftime("%Y-%m-%d")
            context.user_data['temp_crs_step'].update({'start_date': start_date, 'end_date': end_date})
            
            from sheets import get_all_coaches_list
            coaches = get_all_coaches_list(bot_token)
            if not coaches:
                context.user_data['temp_crs_step'].update({'coach_id': "ID-01", 'coach_name': "قيد التعيين", 'coach_user': "0"})
                context.user_data['action'] = 'awaiting_crs_max_students'
                await update.message.reply_text(f"🏁 النهاية: {end_date}\n👥 <b>الخطوة 6:</b> أرسل <b>حد الطلاب</b>:")
            else:
                keyboard = [[InlineKeyboardButton(c['name'], callback_data=f"sel_co_{c['id']}")] for c in coaches]
                await update.message.reply_text(f"🏁 تاريخ النهاية: {end_date}\n👨‍🏫 <b>الخطوة 6:</b> اختر <b>المدرب</b>:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        elif action == 'awaiting_crs_max_students':
            if not text.isdigit():
                await update.message.reply_text("⚠️ أرسل رقم صحيح:")
                return
            context.user_data['temp_crs_step']['max_students'] = text
            from sheets import get_all_personnel
            staff = get_all_personnel(bot_token)
            if not staff:
                context.user_data['temp_crs_step'].update({'emp_id': "ADM-01", 'emp_name': "إدارة المنصة"})
                context.user_data['action'] = 'awaiting_crs_campaign'
                await update.message.reply_text("📢 <b>الخطوة 7:</b> أرسل <b>معرف الحملة</b> (أو 0):")
            else:
                keyboard = [[InlineKeyboardButton(s['name'], callback_data=f"sel_st_{s['id']}")] for s in staff]
                await update.message.reply_text("👤 <b>الخطوة 7:</b> اختر <b>الموظف المسؤول</b>:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        elif action == 'awaiting_crs_campaign':
            from sheets import ss, add_new_course, sync_bot_limits
            import uuid
            camp_id = text.strip()
            if camp_id != "0":
                try:
                    camp_ws = ss.worksheet("إدارة_الحملات_الإعلانية")
                    if not any(str(r.get('معرف_الحملة')) == camp_id for r in camp_ws.get_all_records()):
                        await update.message.reply_text("❌ معرف غير موجود. أرسل 0 للتخطي:")
                        return
                except: pass
            
            d = context.user_data['temp_crs_step']
            c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
            success = add_new_course(
                bot_token, d.get('branch_id', "MAIN-01"), c_id, d['name'], d['desc'],
                d['start_date'], d['end_date'], "أونلاين", d['price'], d['max_students'],
                "لا يوجد", d.get('emp_name', "Admin"), d.get('emp_id', "ADM-01"),
                camp_id, d.get('coach_user', "0"), d.get('coach_id', "ID-01"),
                d.get('coach_name', "Coach"), context.user_data.get('temp_crs_cat')
            )
            
        elif action == 'awaiting_crs_date':
            context.user_data['temp_crs']['start_date'] = text
            d = context.user_data['temp_crs']
            summary = (
                f"📝 <b>مراجعة بيانات الدورة:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📂 القسم: {context.user_data.get('temp_crs_cat')}\n"
                f"📚 الاسم: {d['name']}\n"
                f"⏳ الساعات: {d['hours']}\n"
                f"💰 السعر: {d['price']}\n"
                f"👨‍🏫 المدرب: {d['coach_name']}\n"
                f"🗓 البداية: {text}\n"
                f"━━━━━━━━━━━━━━\n"
                f"<b>هل البيانات صحيحة؟</b>"
            )
            keyboard = [[InlineKeyboardButton("✅ نعم، اعتمد", callback_data="confirm_save_full_crs")], [InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")]]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return    
        d = context.user_data['temp_crs_step']
        cat_id = context.user_data.get('temp_crs_cat')
        course_id = f"CRS{str(uuid.uuid4().int)[:4]}"
        
        # تنفيذ الحفظ النهائي - مطابق لترتيب الـ 18 عموداً بدقة تامة
        success = add_new_course(
            bot_token,                           # 1. bot_id
            d.get('branch_id', "MAIN-01"),       # 2. معرف_الفرع (المجلوب من الدالة)
            course_id,                           # 3. معرف_الدورة
            d['name'],                           # 4. اسم_الدورة
            d['desc'],                           # 5. الوصف
            d['start_date'],                     # 6. تاريخ_البداية
            d['end_date'],                       # 7. تاريخ_النهاية (المحسوب)
            "أونلاين",                           # 8. نوع_الدورة
            d['price'],                          # 9. سعر_الدورة
            d['max_students'],                   # 10. الحد_الأقصى
            "لا يوجد",                           # 11. المتطلبات
            d.get('emp_name', "إدارة المنصة"),    # 12. اسم_الموظف (المجلوب من الدالة)
            d.get('emp_id', "ADM-01"),           # 13. معرف_الموظف (المجلوب من الدالة)
            campaign_id,                         # 14. معرف_الحملة_التسويقية
            d.get('coach_user', "0"),            # 15. معرف_المدرب (الـ ID الرقمي)
            d.get('coach_id', "ID-01"),          # 16. ID_المدرب (الكود)
            d.get('coach_name', "لم يحدد"),       # 17. اسم_المدرب (المجلوب من الدالة)
            cat_id                               # 18. معرف_القسم
        )
                    
#=======================================
# تصحيح الجزء الخاص بحفظ الدورة (السطر 1981 وما حوله)
#=======================================
#=======================================
# تصحيح نهائي لكتلة حفظ الدورة (الأسطر 1980 وما حولها)
#=======================================
        if success:
            # تحديث الذاكرة المؤقتة للقيود فوراً
            sync_bot_limits(context, bot_token)
            
            # إرسال رسالة التأكيد للمسؤول مع استخدام <code> للتنسيق الآمن
            await update.message.reply_text(
                f"✅ <b>تم الحفظ بنجاح!</b>\n🆔 المعرف: <code>{course_id}</code>", 
                reply_markup=get_admin_panel(), 
                parse_mode="HTML"
            )
            
            # تنظيف حالة الإجراء لمنع التكرار
            context.user_data['action'] = None
        else:
            await update.message.reply_text("❌ حدث خطأ أثناء الحفظ في قاعدة البيانات.")
        
        return

#=======================================

#=======================================

# نهاية تسلسل اضافة دورة
# --------------------------------------------------------------------------
        # تسلسل إضافة مدرب
        elif action == 'await_coach_name':
            context.user_data['temp_coach'] = {'name': text}
            context.user_data['action'] = 'await_coach_spec'
            await update.message.reply_text("🎓 <b>الخطوة 2:</b> أرسل تخصص المدرب:", parse_mode="HTML")
            return

        elif action == 'await_coach_spec':
            context.user_data['temp_coach']['spec'] = text
            context.user_data['action'] = 'await_coach_phone'
            await update.message.reply_text("📞 <b>الخطوة 3:</b> أرسل رقم هاتف المدرب:")
            return

        elif action == 'await_coach_phone':
            context.user_data['temp_coach']['phone'] = text
            context.user_data['action'] = 'await_coach_id'
            await update.message.reply_text("🆔 <b>الخطوة 4:</b> أرسل المعرف الرقمي (ID) للمدرب:", parse_mode="HTML")
            return

        elif action == 'await_coach_id':
            context.user_data['temp_coach']['id'] = text
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
# نهاية تسلسل إضافة مدرب
# --------------------------------------------------------------------------
        # --- [ محرك معالجة الإضافة الجماعية للدورات ] ---
        elif action == 'awaiting_bulk_courses':
            lines = text.split('\n')
            success_count = 0
            failed_lines = []
            from sheets import add_new_course
            import uuid

            for line in lines:
                if not line.strip(): continue # تخطي الأسطر الفارغة
                
                # تقسيم السطر بناءً على الفاصل الرأسي |
                parts = [p.strip() for p in line.split('|')]
                
                # التأكد من وجود الخمسة أجزاء المطلوبة حسب تعليماتك الجديدة
                if len(parts) >= 5:
                    c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
                    
                    # إرسال البيانات للدالة (الترتيب مطابق للـ 17 عمود في sheets.py)
                    success = add_new_course(
                        bot_token,          # 1. bot_id
                        c_id,               # 2. معرف_الدورة
                        parts[0],           # 3. اسم_الدورة
                        parts[1],           # 4. عدد_الساعات (الوصف والساعات)
                        "2026-01-01",       # 5. تاريخ_البداية (افتراضي)
                        "",                 # 6. تاريخ_النهاية
                        "أونلاين",          # 7. نوع_الدورة
                        parts[2],           # 8. سعر_الدورة
                        "100",              # 9. الحد_الأقصى
                        "لا يوجد",          # 10. المتطلبات
                        "إدارة المنصة",      # 11. اسم_المندوب
                        "ADMIN01",          # 12. كود_المندوب
                        "عام",              # 13. الحملة_التسويقية
                        "إدخال جماعي",      # 14. معرف_المدرب (يوزر)
                        parts[3],           # 15. ID_المدرب (المعرف الرقمي)
                        "مدرب معتمد",       # 16. اسم_المدرب (افتراضي)
                        parts[4]            # 17. معرف_القسم
                    )
                    
                    if success:
                        success_count += 1
                    else:
                        failed_lines.append(line)
                else:
                    failed_lines.append(line)

            context.user_data['action'] = None
            
            # رسالة النتيجة النهائية
            result_msg = f"✅ <b>تمت العملية بنجاح!</b>\n\n📥 عدد الدورات المضافة: {success_count}"
            if failed_lines:
                result_msg += f"\n⚠️ أسطر فشلت (تأكد من التنسيق):\n" + "\n".join(failed_lines)
            
            await update.message.reply_text(result_msg, reply_markup=get_admin_panel(), parse_mode="HTML")
            return

#-----
        elif action == 'awaiting_sheet_link':
            import re, uuid
            from sheets import client, add_new_course
            
            # استخراج ID الشيت من الرابط بدقة
            match = re.search(r"/d/([a-zA-Z0-9-_]+)", text)
            if not match:
                await update.message.reply_text("❌ رابط غير صحيح. أرسل رابط شيت صالح.")
                return

            try:
                external_ss = client.open_by_key(match.group(1))
                data = external_ss.get_worksheet(0).get_all_records()
                
                success_count = 0
                for r in data:
                    c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
                    success = add_new_course(
                        bot_token, c_id, str(r.get('اسم_الدورة', '')), str(r.get('الوصف', '')),
                        "2026-01-01", "", "أونلاين", str(r.get('السعر', '0')), 
                        "100", "لا يوجد", "إدارة المنصة", "ADMIN01", "رابط", 
                        "Sheet", str(r.get('ID_المدرب', '')), "مدرب", str(r.get('ID_القسم', ''))
                    )
                    if success: success_count += 1
                
                await update.message.reply_text(f"✅ تم سحب {success_count} دورة من الرابط.")
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الوصول للرابط: {str(e)}")
            context.user_data['action'] = None
            return





# --------------------------------------------------------------------------
# المجموعات 
# أضف هذا الجزء داخل handle_contact_message في education_bot.py

        elif action == 'awaiting_grp_name':
            from educational_manager import process_grp_name
            await process_grp_name(update, context)
            return

        elif action == 'awaiting_grp_days':
            from educational_manager import process_grp_days
            await process_grp_days(update, context)
            return

        elif action == 'awaiting_grp_time':
            from educational_manager import process_grp_time
            await process_grp_time(update, context)
            return

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
        # --- [ حفظ كليشة الترحيب الجديدة ] ---
        elif action == 'awaiting_new_welcome_text':
            period = context.user_data.get('edit_period')
            column_name = f"welcome_{period}"
            from sheets import update_content_setting
            if update_content_setting(bot_token, column_name, text):
                await update.message.reply_text(f"✅ تم تحديث كليشة الترحيب <b>({period})</b> بنجاح!", reply_markup=get_admin_panel(), parse_mode="HTML")
                context.user_data['action'] = None
            else:
                await update.message.reply_text("❌ فشل التحديث. تأكد من إضافة الأعمدة المطلوبة.")
            return

        # 1. استقبال اسم المؤسسة (تم دمجه في تسلسل الإدارة)
        # 1. استقبال اسم المؤسسة
        elif action == 'awaiting_institution_name':
            from sheets import save_ai_setup
            if save_ai_setup(bot_token, user.id, user.username, institution_name=text):
                context.user_data['action'] = 'awaiting_ai_instructions'
                await update.message.reply_text(f"✅ تم حفظ الاسم: <b>{text}</b>\n\nالآن أرسل <b>تعليمات الذكاء الاصطناعي</b> للمنصة:")
            else:
                # إذا فشل الحفظ، البوت سيخبرك بدلاً من التهنيج
                await update.message.reply_text("❌ عذراً دكتور، فشل الحفظ في الشيت. تأكد من وجود ورقة 'الذكاء_الإصطناعي'.")
            return


        # 2. استقبال تعليمات AI
        elif action == 'awaiting_ai_instructions':
            from sheets import save_ai_setup
            if save_ai_setup(bot_token, user.id, user.username, ai_instructions=text):
                context.user_data['action'] = None
                await update.message.reply_text("🎊 <b>اكتملت التهيئة!</b> تم ضبط هوية البوت بنجاح.", reply_markup=get_admin_panel())
            return
# --------------------------------------------------------------------------
        # تسلسل إضافة سؤال يدوي - استقبال نص السؤال
        elif action == 'awaiting_q_text':
            context.user_data['temp_q']['text'] = text
            context.user_data['action'] = 'awaiting_q_a'
            await update.message.reply_text("🔘 <b>الخطوة 3:</b> أرسل <b>الخيار (A)</b>:")
            return

        # استقبال الخيار A
        elif action == 'awaiting_q_a':
            context.user_data['temp_q']['a'] = text
            context.user_data['action'] = 'awaiting_q_b'
            await update.message.reply_text("🔘 <b>الخطوة 4:</b> أرسل <b>الخيار (B)</b>:")
            return

        # استقبال الخيار B
        elif action == 'awaiting_q_b':
            context.user_data['temp_q']['b'] = text
            context.user_data['action'] = 'awaiting_q_c'
            await update.message.reply_text("🔘 <b>الخطوة 5:</b> أرسل <b>الخيار (C)</b>:")
            return

        # استقبال الخيار C
        elif action == 'awaiting_q_c':
            context.user_data['temp_q']['c'] = text
            context.user_data['action'] = 'awaiting_q_d'
            await update.message.reply_text("🔘 <b>الخطوة 6:</b> أرسل <b>الخيار (D)</b>:")
            return

        # استقبال الخيار D وطلب الإجابة الصحيحة
        elif action == 'awaiting_q_d':
            context.user_data['temp_q']['d'] = text
            context.user_data['action'] = 'awaiting_q_correct'
            keyboard = [
                [InlineKeyboardButton("A", callback_data="set_q_ans_A"), InlineKeyboardButton("B", callback_data="set_q_ans_B")],
                [InlineKeyboardButton("C", callback_data="set_q_ans_C"), InlineKeyboardButton("D", callback_data="set_q_ans_D")]
            ]
            await update.message.reply_text(
                "✅ <b>الخطوة 7:</b> حدد <b>الإجابة الصحيحة</b> من الأزرار أدناه:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return

        # استقبال درجة السؤال
        elif action == 'awaiting_q_grade':
            if not text.isdigit():
                await update.message.reply_text("⚠️ يرجى إرسال أرقام فقط لدرجة السؤال:")
                return
            context.user_data['temp_q']['grade'] = text
            context.user_data['action'] = 'awaiting_q_level'
            keyboard = [
                [InlineKeyboardButton("سهل", callback_data="set_q_lv_سهل"), 
                 InlineKeyboardButton("متوسط", callback_data="set_q_lv_متوسط"),
                 InlineKeyboardButton("صعب", callback_data="set_q_lv_صعب")]
            ]
            await update.message.reply_text("📊 <b>الخطوة 9:</b> اختر <b>مستوى صعوبة</b> السؤال من الأزرار:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return



        # تسلسل إعدادات الاختبار الآلي
        elif action == 'awaiting_quiz_title':
            context.user_data['temp_quiz']['quiz_id'] = text
            context.user_data['action'] = 'awaiting_quiz_q_count'
            await update.message.reply_text("🔢 <b>الخطوة 4:</b> كم <b>عدد الأسئلة</b> التي تريد سحبها من البنك لهذا الاختبار؟")
            return

        elif action == 'awaiting_quiz_q_count':
            if not text.isdigit():
                await update.message.reply_text("⚠️ أرسل رقماً فقط:")
                return
            context.user_data['temp_quiz']['q_count'] = text
            context.user_data['action'] = 'awaiting_quiz_pass'
            await update.message.reply_text("🎯 <b>الخطوة 5:</b> حدد <b>درجة النجاح</b> (مثلاً: 50):")
            return

        elif action == 'awaiting_quiz_pass':
            context.user_data['temp_quiz']['pass_score'] = text
            context.user_data['action'] = 'awaiting_quiz_time'
            await update.message.reply_text("⏱ <b>الخطوة 6:</b> حدد <b>مدة الاختبار الكلية</b> بالدقائق:")
            return

        elif action == 'awaiting_quiz_time':
            context.user_data['temp_quiz']['duration'] = text
            q = context.user_data['temp_quiz']
            summary = (
                f"⚙️ <b>مراجعة إعدادات الاختبار:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📝 العنوان: {q['quiz_id']}\n"
                f"👥 المجموعات: {','.join(q['target_groups'])}\n"
                f"🔢 عدد الأسئلة: {q['q_count']}\n"
                f"🎯 النجاح من: {q['pass_score']}\n"
                f"⏱ المدة: {text} دقيقة\n"
                f"━━━━━━━━━━━━━━\n"
                f"هل تريد إنشاء الاختبار الآن؟"
            )
            keyboard = [
                [InlineKeyboardButton("✅ نعم، إنشاء", callback_data="exec_create_quiz_final")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="manage_control")]
            ]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return

# --------------------------------------------------------------------------
        # --- [ تسلسل إسناد واجب جديد - استقبال النصوص ] ---
        elif action == 'awaiting_hw_title':
            context.user_data['temp_hw']['title'] = text
            context.user_data['action'] = 'awaiting_hw_desc'
            await update.message.reply_text("📋 أرسل الآن <b>وصف الواجب</b> أو التعليمات المطلوبة من الطلاب:", parse_mode="HTML")
            return

        elif action == 'awaiting_hw_desc':
            context.user_data['temp_hw']['desc'] = text
            context.user_data['action'] = 'awaiting_hw_deadline'
            await update.message.reply_text("📅 أرسل الآن <b>آخر موعد للتسليم</b> (مثلاً: 2026-04-20):", parse_mode="HTML")
            return

        elif action == 'awaiting_hw_deadline':
            context.user_data['temp_hw']['deadline'] = text
            h = context.user_data['temp_hw']
            summary = (
                f"📑 <b>مراجعة إسناد الواجب:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📘 الدورة: <code>{h['course_id']}</code>\n"
                f"👥 عدد المجموعات: <code>{len(h['target_groups'])}</code>\n"
                f"📌 العنوان: {h['title']}\n"
                f"⏰ موعد التسليم: {text}\n"
                f"━━━━━━━━━━━━━━\n"
                f"هل تريد تأكيد إرسال الواجب الآن؟"
            )
            keyboard = [[InlineKeyboardButton("✅ نعم، إسناد", callback_data="exec_save_hw_final")],
                        [InlineKeyboardButton("❌ إلغاء", callback_data="manage_homeworks")]]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return

# --------------------------------------------------------------------------
    # --- [ جزء الطلاب والردود التفاعلية - g4f فقط ] ---
    
    # جلب إعدادات البوت أولاً لتعريف bot_owner_id قبل استخدامه في الشرط
    from sheets import get_bot_config
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    # تنفيذ الشرط: إذا كان المرسل ليس هو المالك (أي أنه طالب)
    if user.id != bot_owner_id:
    	        # --- [ معالجة تسليم الواجب ] ---
        if action == 'awaiting_solution':
            hw_id = context.user_data.get('target_hw_id')

            student = get_student_enrollment_data(bot_token, user.id)
            
            # تحديد نوع الملف والرابط [بند 3 في الوثيقة]
            file_link = "نص: " + text if text else "ملف/صورة"
            if update.message.document: file_link = f"وثيقة: {update.message.document.file_id}"
            elif update.message.photo: file_link = f"صورة: {update.message.photo[-1].file_id}"

            data = {
                'hw_id': hw_id, 'student_id': str(user.id),
                'course_id': student['course_id'], 'group_id': student['group_id'],
                'start_time': context.user_data.get('hw_start_time'),
                'file_link': file_link, 'branch_id': student.get('معرف_الفرع', '001')
            }

            if record_student_submission(bot_token, data):
                await update.message.reply_text("✅ <b>تم استلام حل الواجب بنجاح!</b>\nسيتم مراجعته من قبل المعلم وإشعارك بالنتيجة.", parse_mode="HTML")
                # إشعار الإدارة [رابعاً في الوثيقة]
                admin_notif = f"🔔 <b>تسليم جديد:</b>\nقام الطالب <b>{student['student_name']}</b> بتسليم واجب <code>{hw_id}</code>، يرجى التصحيح."
                try: await context.bot.send_message(chat_id=bot_owner_id, text=admin_notif, parse_mode="HTML")
                except: pass
            else:
                await update.message.reply_text("❌ فشل تسجيل التسليم، يرجى المحاولة لاحقاً.")
            
            context.user_data['action'] = None
            return 
  
        # 1. فحص الكلمات المفتاحية (FAQ) لسرعة الرد
        faq_keywords = {
            "طريقة الدفع": "💳 يمكنك الدفع عبر (زين كاش، بايبال، أو كروت التعبئة).",
            "تفعيل": "🎟 لتفعيل الدورة، يرجى إرسال الكود الذي حصلت عليه.",
            "قائمة": "📚 يمكنك استعراض كافة الدورات المتاحة عبر الزر المخصص."
        }
        for key, response in faq_keywords.items():
            if key in text:
                await update.message.reply_text(response)
                return

        # 2. إدارة ذاكرة المحادثة وجلب البيانات من الشيت
        global user_messages
        if user.id not in user_messages:
            user_messages[user.id] = []

        # جلب قاعدة المعرفة من الشيت
        from sheets import get_courses_knowledge_base
        courses_knowledge = get_courses_knowledge_base(bot_token)
        
        # إضافة رسالة الطالب للذاكرة
        user_messages[user.id].append({"role": "user", "content": text})
        
        # --- [ الجزء الديناميكي الجديد: جلب الهوية من الشيت ] ---
        from sheets import get_ai_setup
        ai_info = get_ai_setup(bot_token)
        platform = ai_info.get('اسم_المؤسسة', 'منصة الادارة التعليمية') if ai_info else "منصة الادارة التعليمية"
        rules = ai_info.get('تعليمات_AI', 'أجب بذكاء ولباقة واستخدم الرموز التعبيرية 🎓') if ai_info else "أجب بذكاء ولباقة"

        # بناء سياق المحادثة الكامل بالهوية الجديدة + الذاكرة
        messages_to_send = [
            {
                "role": "system", 
                "content": f"أنت المساعد الذكي الرسمي لـ {platform}. {rules}. إليك معلومات الدورات المتاحة حالياً:\n{courses_knowledge}"
            }
        ] + user_messages[user.id][-6:] # دمج الذاكرة لضمان استمرارية الحوار

        await update.message.reply_chat_action("typing")

        try:
            # استخدام g4f بشكل مباشر مع المزود التلقائي لضمان الاستقرار
            import g4f
            response = await g4f.ChatCompletion.create_async(
                model=g4f.models.default,
                messages=messages_to_send,
            )

            if response and len(response) > 0:
                # إضافة رد البوت للذاكرة وإرساله
                user_messages[user.id].append({"role": "assistant", "content": response})
                await update.message.reply_text(response)
                return
            else:
                raise Exception("Empty g4f Response")
            
        except Exception as e: # تصحيح الحرف الصغير هنا
            # الخطة البديلة: إرسال تنبيه للادارة في حال فشل المحرك
            print(f"❌ AI Error: {e}")
            
            # تم نقل جلب الإعدادات للأعلى لضمان توافر bot_owner_id
            info = f"📩 <b>استفسار طالب (فشل الـ AI):</b>\nالاسم: {user.full_name}\nالرسالة: {text}\nالخطأ: {str(e)}"
            
            try:
                # محاولة إرسال التنبيه للمالك إذا كان معرّفاً
                if bot_owner_id:
                    await context.bot.send_message(chat_id=bot_owner_id, text=info, parse_mode="HTML")
                
                # الرد على الطالب دائماً لضمان عدم بقاء المحادثة معلقة
                await update.message.reply_text("💡 شكراً لسؤالك! لقد استلمت استفسارك وسيقوم الادارة بالرد عليك فوراً.")
            except Exception as send_error:
                print(f"⚠️ فشل إرسال التنبيه للمالك: {send_error}")
                await update.message.reply_text("⚠️ المعذرة، هناك ضغط حالياً. يرجى المحاولة لاحقاً.")


# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --- [ محرك التشغيل المتوافق مع المصنع ] ---
#=======================================
# --- [ محرك التشغيل المتوافق مع المصنع ] ---
#=======================================
async def run_bot(token, owner_id):
    """هذه الدالة هي التي يستدعيها ملف main.py لتشغيل البوت ديناميكياً"""
    
    # بناء التطبيق مع ضبط إعدادات الشبكة لتقليل أخطاء التعارض
    application = ApplicationBuilder().token(token).build()
    
    # 1. إضافة المعالجات (Handlers)
    # --------------------------------------------------------------------------
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CallbackQueryHandler(contact_callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_message))
    
    # 2. إعداد مراقب التفعيل
    # --------------------------------------------------------------------------
    # سيقوم بفحص الشيت كل 60 ثانية وإرسال رسائل للطلاب المفعلين
    if application.job_queue:
        application.job_queue.run_repeating(activation_monitor, interval=60, first=10)
    
    # 3. بدء تشغيل المحرك مع تنظيف التحديثات القديمة
    # --------------------------------------------------------------------------
    await application.initialize()
    await application.start()
    
    # ملاحظة: drop_pending_updates=True تساعد في حل خطأ Conflict 409
    await application.updater.start_polling(drop_pending_updates=True)
    
#=======================================


            
#=======================================



# --------------------------------------------------------------------------

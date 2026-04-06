from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from sheets import (
    get_filtered_library_content, get_user_referral_stats, 
    ss, get_student_enrollment_data, get_student_assignments,
    get_system_time, check_student_submission
)

async def show_course_content_ui(update, context, course_id):
    """عرض الدروس المتاحة للطالب فقط (مجاني + مدفوع إذا دفع)"""
    query = update.callback_query
    user_id = query.from_user.id
    bot_token = context.bot.token
    
    # استدعاء الدالة الذكية الجديدة التي تربط حالة الدفع في (قاعدة_بيانات_الطلاب) مع نوع الملف في (المكتبة)

    library_items = get_filtered_library_content(bot_token, user_id, course_id)
    
    # معالجة حالة عدم وجود محتوى متاح (إما لعدم الرفع أو لعدم الدفع)
    if not library_items:
        text = (
            "⚠️ <b>تنبيه:</b>\n"
            "لا يوجد محتوى متاح لك حالياً في هذه الدورة.\n"
            "💡 إذا كانت الدورة مدفوعة، يرجى التأكد من إتمام عملية الدفع وتفعيل حسابك من قبل الإدارة."
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 العودة", callback_data="my_profile")]
        ]), parse_mode="HTML")
        return

    text = (
        f"📖 <b>مكتبة الدورة التعليمية:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"إليك الدروس والملفات المتاحة لك:"
    )

    keyboard = []
    for item in library_items:
        # تحديد الأيقونة بناءً على نوع الملف من عمود "النوع"
        icon = "📺" if "فيديو" in str(item.get('النوع')) else "📄"
        
        # إضافة تمييز للملفات المدفوعة بنجمة ذهبية لتعزيز قيمة الاشتراك
        label = f"{icon} {item.get('اسم_الملف')}"
        if str(item.get('الحالة')).strip() == "مدفوع":
            label += " ⭐"
            
        url = item.get('الرابط')
        # التحقق من صحة الرابط قبل إنشاء الزر لضمان تجربة مستخدم خالية من الأخطاء
        if url and str(url).startswith('http'):
            keyboard.append([InlineKeyboardButton(label, url=url)])
    
    # إضافة زر العودة لضمان سهولة التنقل داخل المنصة
    keyboard.append([InlineKeyboardButton("🔙 العودة لدروسي", callback_data="my_profile")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --------------------------------------------------------------------------
#    لوحة التحكم الخاص بالطالب 
# أضف هذه الدالة في ملف course_engine.py
async def show_student_profile(update, context):
    """لوحة التحكم الخاصة بالطالب (نقاط، دورات، أوسمة)"""
    query = update.callback_query
    user_id = query.from_user.id
    bot_token = context.bot.token
    

    stats = get_user_referral_stats(bot_token, user_id)
    
    # جلب الدورات المشترك بها الطالب من سجل_التسجيلات
    reg_sheet = ss.worksheet("سجل_التسجيلات")
    student_courses = [r for r in reg_sheet.get_all_records() 
                       if str(r.get("bot_id")) == str(bot_token) and str(r.get("ID_المستخدم_تيليجرام")) == str(user_id)]

    text = (
        f"👤 <b>ملفك الدراسي الرقمي</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 رصيد النقاط: <b>{stats.get('balance', 0)} نقطة</b>\n"
        f"📚 عدد الدورات: <b>{len(student_courses)} دورة</b>\n"
        f"📝 <b>الواجبات:</b> يمكنك متابعة مهامك من الزر أدناه\n"
        f"━━━━━━━━━━━━━━\n"
        f"اختر دورة لبدء التعلم:"
    )

    keyboard = []
    for reg in student_courses:
        keyboard.append([InlineKeyboardButton(f"📖 {reg.get('اسم_الدورة')}", callback_data=f"open_content_{reg.get('معرف_الدورة')}")])
        keyboard.append([InlineKeyboardButton("📝 الواجبات الدراسية", callback_data="std_hw_list")])
    
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="main_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
async def show_student_homeworks_list(update, context):
    """عرض قائمة الواجبات المسموحة للطالب بناءً على مجموعته [بند 1 في الوثيقة]"""
    query = update.callback_query
    user_id = query.from_user.id
    bot_token = context.bot.token
    

    student = get_student_enrollment_data(bot_token, user_id)
    
    if not student:
        await query.answer("⚠️ يجب أن تكون مسجلاً في دورة ومجموعة لرؤية الواجبات.", show_alert=True)
        return

    hw_list = get_student_assignments(bot_token, student['course_id'], student['group_id'])
    
    if not hw_list:
        await query.edit_message_text("✅ لا توجد واجبات مطلوبة منك حالياً في هذه المجموعة.", 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="my_profile")]]))
        return

    keyboard = []
    for hw in hw_list:
        keyboard.append([InlineKeyboardButton(f"📄 {hw['عنوان_الواجب']}", callback_data=f"std_hw_view_{hw['معرف_الواجب']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="my_profile")])
    await query.edit_message_text(f"📝 <b>قائمة الواجبات - {student['course_name']}:</b>", 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def show_homework_details(update, context, hw_id):
    """عرض تفاصيل الواجب وفحص حالة التسليم [بند 2 في الوثيقة]"""
    query = update.callback_query
    user_id = query.from_user.id
    bot_token = context.bot.token
    

    sheet = ss.worksheet("الواجبات")
    hw = next((r for r in sheet.get_all_records() if str(r.get("معرف_الواجب")) == str(hw_id)), None)
    
    if not hw: return

    # لحظة فتح تفاصيل الواجب (تاريخ_البداية)
    
    context.user_data['hw_start_time'] = get_system_time("full")


    # محرك فحص الحالات [بند 2 في الوثيقة]
    submission = check_student_submission(bot_token, user_id, hw_id)
    
    status_text = ""
    keyboard = []
    
    if submission:
        status_text = (
            f"\n✅ <b>حالة التسليم:</b> تم التسليم بنجاح\n"
            f"📊 التقييم: <code>{submission.get('تقييم_التسليم', 'قيد الانتظار')}</code>\n"
            f"📝 ملاحظات المعلم: {submission.get('ملاحظات_المعلم', '-')}"
        )
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة", callback_data="std_hw_list")])
    else:
        status_text = "\n⏳ <b>الحالة:</b> لم يتم التسليم بعد"
        keyboard.append([InlineKeyboardButton("📤 رفع الحل الآن", callback_data=f"std_hw_upload_{hw_id}")])
        keyboard.append([InlineKeyboardButton("🔙 تراجع", callback_data="std_hw_list")])

    text = (
        f"📄 <b>تفاصيل الواجب:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"📌 العنوان: {hw['عنوان_الواجب']}\n"
        f"📝 الوصف: {hw['وصف_الواجب']}\n"
        f"⏰ الموعد النهائي: <code>{hw['تاريخ_التسليم']}</code>\n"
        f"💯 الدرجة: {hw['درجة_كاملة']}\n"
        f"━━━━━━━━━━━━━━"
        f"{status_text}"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------





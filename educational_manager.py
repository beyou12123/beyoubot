from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from datetime import datetime
import uuid
import time
# استيراد الدوال من ملف sheets (تأكد من مطابقة أسماء الدوال لما هو موجود في ملف sheets.py)
from sheets import (
    get_groups_by_course, 
    add_new_group, 
    get_all_coaches, 
    get_employee_allowed_courses,
    get_employee_allowed_groups,
    get_student_enrollment_data,
    get_lectures_by_group,
    get_active_discount_codes,
    check_user_permission, # للتأكد من هوية الموظف
    delete_group_by_id  # تم تصحيح الاسم هنا ليتطابق مع المحرك
)

# أضف هذه الدوال لقائمة الاستيراد الموجودة في بداية الملف
from sheets import (
    
)


async def manage_groups_main(update, context, course_id):
    """الواجهة الرئيسية لإدارة مجموعات دورة محددة"""
    query = update.callback_query
    bot_token = context.bot.token
    
    # 1. جلب المجموعات الحالية
    groups = get_groups_by_course(bot_token, course_id)
    
    keyboard = []
    # 2. عرض المجموعات كأزرار (تعديل/عرض)
    if groups:
        for g in groups:
            # استخدام get لتجنب أخطاء المفاتيح المفقودة
            label = f"👥 {g.get('اسم_المجموعة', 'بلا اسم')} | 👤 {g.get('عدد_الطلاب_الحالي', 0)}/{g.get('سعة_المجموعة', 30)}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"grp_show_{g.get('معرف_المجموعة')}")])
    
    # 3. أزرار التحكم الثابتة
    keyboard.append([InlineKeyboardButton("➕ إنشاء مجموعة جديدة", callback_data=f"grp_add_start_{course_id}")])
    keyboard.append([InlineKeyboardButton("🔙 عودة للدورة", callback_data=f"manage_crs_{course_id}")])
    
    text = (
        f"📂 <b>نظام إدارة المجموعات</b>\n"
        f"الدورة: <code>{course_id}</code>\n\n"
        f"يمكنك متابعة سعة المجموعات وتعيين المعلمين من هنا."
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def group_details_ui(update, context, group_id):
    """واجهة خيارات المجموعة (تعديل، حذف، رابط)"""
    query = update.callback_query
    # هنا سنعرض خيارات: تعديل الوقت، تغيير المعلم، حذف المجموعة
    keyboard = [
        [InlineKeyboardButton("📝 تعديل البيانات", callback_data=f"grp_mod_{group_id}"),
         InlineKeyboardButton("🔗 رابط المجموعة", callback_data=f"grp_link_{group_id}")],
        [InlineKeyboardButton("🗑️ حذف المجموعة", callback_data=f"grp_confirm_del_{group_id}")],
        [InlineKeyboardButton("🔙 عودة للمجموعات", callback_data="manage_group_back")] 
    ]
    await query.edit_message_text(f"🛠 <b>إدارة المجموعة:</b> <code>{group_id}</code>", 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# دالة الحفظ (تتم معالجتها في المحرك الرئيسي عبر callback exec_save_group)

# 1. بدء عملية إضافة مجموعة (الاسم)
async def start_add_group(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    context.user_data['action'] = 'awaiting_grp_name'
    context.user_data['temp_grp'] = {'course_id': course_id}
    
    await query.edit_message_text(
        f"✍️ <b>إضافة مجموعة جديدة للدورة:</b> <code>{course_id}</code>\n"
        f"الخطوة 1: أرسل <b>اسم المجموعة</b> (مثلاً: مجموعة التميز - صباحي):",
        parse_mode="HTML"
    )

# 2. طلب أيام الدراسة
async def process_grp_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['temp_grp']['name'] = text
    context.user_data['action'] = 'awaiting_grp_days'
    
    await update.message.reply_text(
        "📅 <b>الخطوة 2:</b> أرسل <b>أيام الدراسة</b> (مثلاً: السبت، الاثنين، الأربعاء):",
        parse_mode="HTML"
    )

# 3. طلب توقيت الدراسة
async def process_grp_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['temp_grp']['days'] = text
    context.user_data['action'] = 'awaiting_grp_time'
    
    await update.message.reply_text(
        "⏰ <b>الخطوة 3:</b> أرسل <b>توقيت الدراسة</b> (مثلاً: من 4:00 م إلى 6:00 م):",
        parse_mode="HTML"
    )

# 4. طلب سعة المجموعة واختيار المعلم
async def process_grp_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['temp_grp']['time'] = text
    bot_token = context.bot.token
    
    # جلب المدربين لاختيار أحدهم
    coaches = get_all_coaches(bot_token)
    keyboard = []
    if coaches:
        for c in coaches:
            keyboard.append([InlineKeyboardButton(f"👨‍🏫 {c['name']}", callback_data=f"sel_teacher_{c['id']}")])
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="manage_educational")])
    
    await update.message.reply_text(
        "👨‍🏫 <b>الخطوة 4:</b> اختر <b>المعلم المسؤول</b> عن هذه المجموعة من القائمة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

# 5. المراجعة النهائية والحفظ
async def confirm_group_save(update: Update, context: ContextTypes.DEFAULT_TYPE, teacher_id: str, teacher_name: str):
    query = update.callback_query
    d = context.user_data.get('temp_grp')
    
    # توليد ID فريد للمجموعة
    group_id = f"GRP{str(uuid.uuid4().int)[:4]}"
    
    summary = (
        f"📝 <b>مراجعة بيانات المجموعة الجديدة:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"📚 الدورة: <code>{d['course_id']}</code>\n"
        f"👥 الاسم: {d['name']}\n"
        f"📅 الأيام: {d['days']}\n"
        f"⏰ الوقت: {d['time']}\n"
        f"👨‍🏫 المعلم: {teacher_name}\n"
        f"━━━━━━━━━━━━━━\n"
        f"هل تريد الحفظ والاعتماد؟"
    )
    
    context.user_data['temp_grp']['teacher_id'] = teacher_id
    context.user_data['temp_grp']['group_id'] = group_id
    
    keyboard = [
        [InlineKeyboardButton("✅ نعم، احفظ الآن", callback_data="exec_save_group")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="manage_educational")]
    ]
    await query.edit_message_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
 
async def group_options_ui(update, context, group_id):
    """واجهة التحكم في مجموعة محددة (تعديل/حذف)"""
    query = update.callback_query
    # زر الحذف وزر التعديل
    keyboard = [
        [
            InlineKeyboardButton("📝 تعديل الاسم", callback_data=f"grp_edit_name_{group_id}"),
            InlineKeyboardButton("⏰ تعديل الوقت", callback_data=f"grp_edit_time_{group_id}")
        ],
        [
            InlineKeyboardButton("👨‍🏫 تغيير المعلم", callback_data=f"grp_edit_teacher_{group_id}"),
            InlineKeyboardButton("🚫 تغيير الحالة", callback_data=f"grp_edit_status_{group_id}")
        ],
        [InlineKeyboardButton("🗑️ حذف المجموعة نهائياً", callback_data=f"grp_confirm_del_{group_id}")],
        [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="manage_educational")] 
    ]
    
    await query.edit_message_text(
        f"🛠️ <b>إدارة المجموعة:</b> <code>{group_id}</code>\nاختر الإجراء المطلوب من القائمة أدناه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def confirm_delete_group_ui(update, context, group_id):
    """واجهة تأكيد الحذف لمنع الحذف بالخطأ"""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("✅ نعم، احذف", callback_data=f"grp_exec_del_{group_id}")],
        [InlineKeyboardButton("❌ تراجع", callback_data=f"grp_show_{group_id}")]
    ]
    await query.edit_message_text(
        f"⚠️ <b>تحذير:</b> هل أنت متأكد من حذف المجموعة <code>{group_id}</code>؟\nلا يمكن التراجع عن هذا الإجراء.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

 
# --------------------------------------------------------------------------
#ادارة الاختبارات والاسئلة 
async def manage_control_ui(update, context):
    """واجهة الكنترول التعليمي الرئيسية"""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📝 إدارة الاختبارات", callback_data="manage_quizzes"),
         InlineKeyboardButton("📚 بنك الأسئلة", callback_data="manage_q_bank")],
        [InlineKeyboardButton("📝 سجل الإجابات", callback_data="view_exam_logs"),
         InlineKeyboardButton("📑 إدارة الواجبات", callback_data="manage_homeworks")],
        [InlineKeyboardButton("🔙 عودة", callback_data="manage_educational")]
    ]
    await query.edit_message_text(
        "🎮 <b>مرحباً بك في غرفة الكنترول التعليمي:</b>\n"
        "من هنا يمكنك التحكم في الاختبارات، بنك الأسئلة، وتصحيح الواجبات.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def q_bank_manager_ui(update, context):
    """واجهة إدارة بنك الأسئلة (إضافة/عرض/حذف/تعديل)"""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("➕ إضافة سؤال يدوي", callback_data="add_q_manual")],
        [InlineKeyboardButton("📥 استيراد أسئلة (Excel)", callback_data="import_q_excel")],
        [InlineKeyboardButton("🔍 استعراض وحذف الأسئلة", callback_data="browse_q_bank")],
        [InlineKeyboardButton("🔙 عودة للكنترول", callback_data="manage_control")]
    ]
    await query.edit_message_text(
        "🗄 <b>مخزن بنك الأسئلة:</b>\n"
        "يمكنك بناء قاعدة بيانات لأسئلتك واستخدامها في عدة اختبارات لاحقاً.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def question_bank_ui(update, context):
    """واجهة بنك الأسئلة"""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("➕ إضافة سؤال يدوي", callback_data="add_q_manual")],
        [InlineKeyboardButton("📥 استيراد أسئلة (Excel)", callback_data="import_q_excel")],
        [InlineKeyboardButton("🔍 استعراض الأسئلة", callback_data="browse_questions")],
        [InlineKeyboardButton("🔙 عودة للكنترول", callback_data="manage_control")]
    ]
    await query.edit_message_text(
        "🗄 <b>مخزن بنك الأسئلة:</b>\n"
        "قم ببناء قاعدة أسئلتك لاستخدامها في الاختبارات الآلية لاحقاً.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
 


# --------------------------------------------------------------------------
async def quiz_options_ui(update, context, quiz_id):
    """واجهة التحكم في الاختبار للأدمن (مع زر الظهور/الإخفاء)"""
    query = update.callback_query
    bot_token = context.bot.token
    
    # جلب بيانات الاختبار لمعرفة حالته الحالية
    from sheets import ss
    sheet = ss.worksheet("الاختبارات_الآلية")
    all_q = sheet.get_all_records()
    quiz = next((q for q in all_q if str(q['معرف_الاختبار']) == str(quiz_id)), {})
    
    status = str(quiz.get('حالة_الاختبار', 'FALSE')).upper()
    icon = "👁️ متاح للموظفين" if status == "TRUE" else "🚫 مخفي عن الموظفين"
    
    keyboard = [
        [InlineKeyboardButton(f"{icon}", callback_data=f"q_toggle_vis_{quiz_id}")],
        [InlineKeyboardButton("🗑️ حذف الاختبار", callback_data=f"quiz_confirm_del_{quiz_id}")],
        [InlineKeyboardButton("🔙 عودة", callback_data="manage_quizzes")]
    ]
    
    await query.edit_message_text(
        f"🛠️ <b>إدارة الاختبار:</b> <code>{quiz_id}</code>\n"
        f"الحالة الحالية: <b>{status}</b>",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    
async def manage_personnel_ui(update, context):
    """عرض القائمة الموحدة للموظفين والمدربين من دالتك الأصلية"""
    query = update.callback_query
    bot_token = context.bot.token
    
    # استخدام دالتك الموحدة
    from sheets import get_all_personnel_list
    people = get_all_personnel_list(bot_token)
    
    if not people:
        await query.edit_message_text("⚠️ لا يوجد موظفون أو مدربون مسجلون حالياً.")
        return

    keyboard = []
    for p in people:
        label = f"👤 {p['name']} ({p['type']})"
        # عند الضغط، نرسل الـ ID لعملية التأسيس والضبط
        keyboard.append([InlineKeyboardButton(label, callback_data=f"setup_p_perms_{p['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="tech_settings")])
    await query.edit_message_text("👥 <b>إدارة الصلاحيات والمهام:</b>\nاختر الشخص للبدء بضبط مهامه:", 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
 
# --------------------------------------------------------------------------
# دالة اختيار الدورة لربط السؤال بها
async def start_add_question_ui(update, context):
    """الخطوة 1: اختيار الدورة لربط السؤال بها في بنك الأسئلة"""
    query = update.callback_query
    bot_token = context.bot.token
    
    # جلب الدورات الخاصة بهذا البوت فقط
    from sheets import courses_sheet
    all_courses = courses_sheet.get_all_records()
    bot_courses = [c for c in all_courses if str(c.get('bot_id')) == str(bot_token)]
    
    if not bot_courses:
        await query.edit_message_text("⚠️ لا توجد دورات حالياً، يجب إضافة دورة أولاً لربط الأسئلة بها.")
        return

    keyboard = [[InlineKeyboardButton(f"📘 {c['اسم_الدورة']}", callback_data=f"sel_q_crs_{c['معرف_الدورة']}")] for c in bot_courses]
    keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_q_bank")])
    
    await query.edit_message_text("🎯 <b>إضافة سؤال يدوي:</b>\nاختر الدورة التي يتبع لها هذا السؤال لربطها ببنك الأسئلة:", 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")




# --------------------------------------------------------------------------
# واجهة لعرض الأسئلة كأزرار 
async def browse_q_bank_ui(update, context):
    """عرض قائمة الأسئلة الموجودة في البنك لاختيار أحدها"""
    query = update.callback_query
    bot_token = context.bot.token
    
    from sheets import get_all_questions_from_bank
    questions = get_all_questions_from_bank(bot_token)
    
    if not questions:
        await query.edit_message_text("🗄 <b>بنك الأسئلة فارغ حالياً.</b>\nابدأ بإضافة أسئلة أولاً لتظهر هنا.", 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_q_bank")]]), parse_mode="HTML")
        return

    keyboard = []
    # عرض أول 10 أسئلة (لضمان عدم تجاوز حجم الرسالة)
    for q in questions[:10]:
        # نأخذ أول 30 حرف من السؤال كعنوان للزر
        q_text = (q['نص_السؤال'][:30] + '..') if len(q['نص_السؤال']) > 30 else q['نص_السؤال']
        keyboard.append([InlineKeyboardButton(f"❓ {q_text}", callback_data=f"view_q_det_{q['معرف_السؤال']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_q_bank")])
    await query.edit_message_text(f"🔍 <b>استعراض الأسئلة ({len(questions)} سؤال):</b>\nاختر سؤالاً لعرض تفاصيله أو حذفه:", 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def view_question_details_ui(update, context, q_id):
    """عرض تفاصيل السؤال مع زر الحذف"""
    query = update.callback_query
    bot_token = context.bot.token
    
    from sheets import get_all_questions_from_bank
    all_q = get_all_questions_from_bank(bot_token)
    q = next((item for item in all_q if str(item['معرف_السؤال']) == str(q_id)), None)
    
    if not q:
        await query.answer("⚠️ تعذر العثور على السؤال.")
        return

    text = (
        f"📝 <b>تفاصيل السؤال:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"❓ <b>السؤال:</b> {q['نص_السؤال']}\n"
        f"🅰️ الخيار A: {q['الخيار_A']}\n"
        f"🅱️ الخيار B: {q['الخيار_B']}\n"
        f"🆃 الخيار C: {q['الخيار_C']}\n"
        f"🅳 الخيار D: {q['الخيار_D']}\n\n"
        f"✅ <b>الإجابة الصحيحة:</b> {q['الإجابة_الصحيحة']}\n"
        f"🎯 الدرجة: {q['الدرجة']} | 📊 المستوى: {q['مستوى_الصعوبة']}\n"
        f"📚 الدورة: <code>{q['معرف_الدورة']}</code>\n"
        f"━━━━━━━━━━━━━━"
    )
    
    keyboard = [
        [InlineKeyboardButton("🗑️ حذف السؤال نهائياً", callback_data=f"exec_del_q_{q_id}")],
        [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="browse_q_bank")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --------------------------------------------------------------------------
# بدء عملية إنشاء الاختبارات واختيار المجموعات والدورات
async def quiz_create_start_ui(update, context):
    """الخطوة 1: اختيار الدورة المراد إنشاء اختبار آلي لها"""
    query = update.callback_query
    bot_token = context.bot.token
    
    from sheets import courses_sheet
    all_courses = courses_sheet.get_all_records()
    bot_courses = [c for c in all_courses if str(c.get('bot_id')) == str(bot_token)]
    
    if not bot_courses:
        await query.edit_message_text("⚠️ يجب إضافة دورة تعليمية أولاً لتتمكن من إنشاء اختبار لها.")
        return

    keyboard = [[InlineKeyboardButton(f"📘 {c['اسم_الدورة']}", callback_data=f"q_gen_crs_{c['معرف_الدورة']}")] for c in bot_courses]
    keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_control")])
    
    await query.edit_message_text("📝 <b>إنشاء اختبار آلي جديد:</b>\nاختر الدورة التدريبية المراد سحب الأسئلة لها:", 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def quiz_gen_select_groups_ui(update, context, course_id):
    """الخطوة 2: اختيار المجموعات المستهدفة (نظام الاختيار المتعدد)"""
    query = update.callback_query
    bot_token = context.bot.token
    
    from sheets import get_groups_by_course
    groups = get_groups_by_course(bot_token, course_id)
    
    if 'temp_quiz' not in context.user_data:
        context.user_data['temp_quiz'] = {'course_id': course_id, 'target_groups': []}

    keyboard = []
    # زر "الكل"
    all_icon = "✅" if "ALL" in context.user_data['temp_quiz']['target_groups'] else "⬜"
    keyboard.append([InlineKeyboardButton(f"{all_icon} كافة المجموعات", callback_data=f"q_gen_grp_ALL_{course_id}")])
    
    for g in groups:
        g_id = str(g['معرف_المجموعة'])
        icon = "✅" if g_id in context.user_data['temp_quiz']['target_groups'] else "⬜"
        keyboard.append([InlineKeyboardButton(f"{icon} {g['اسم_المجموعة']}", callback_data=f"q_gen_grp_{g_id}_{course_id}")])
    
    keyboard.append([InlineKeyboardButton("🚀 الخطوة التالية (الإعدادات)", callback_data=f"q_gen_next_settings")])
    keyboard.append([InlineKeyboardButton("🔙 تراجع", callback_data="manage_control")])
    
    await query.edit_message_text(f"👥 <b>تحديد المجموعات:</b>\nاختر المجموعات التي سيظهر لها الاختبار في لوحتهم:", 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")



# --------------------------------------------------------------------------
#جدول المحاضرات
async def show_lectures_logic(update, context):
    """المنطق الذكي لعرض المحاضرات بناءً على نوع المستخدم"""
    query = update.callback_query
    user_id = update.effective_user.id
    bot_token = context.bot.token
    
    # 1. محاولة جلب بيانات الطالب أولاً
    student_data = get_student_enrollment_data(bot_token, user_id)
    
    if student_data:
        # --- مسار الطالب: عرض الجدول المباشر ---
        lectures = get_lectures_by_group(bot_token, student_data['group_id'])
        
        msg = (
            f"<b>🗓 جدول محاضراتك يا {student_data['student_name']}</b>\n"
            f"📚 الدورة: {student_data['course_name']}\n"
            f"👥 المجموعة: {student_data['group_name']}\n"
            f"---------------------------\n"
        )
        
        keyboard = []
        if lectures:
            for lec in lectures:
                msg += (
                    f"🔹 <b>{lec.get('التاريخ')} ({lec.get('اليوم')})</b>\n"
                    f"⏰ الوقت: {lec.get('وقت_البداية')} - {lec.get('وقت_النهاية')}\n"
                    f"👨‍🏫 المدرب: {lec.get('اسم_المدرب')}\n"
                    f"📝 ملاحظة: {lec.get('ملاحظات', '-')}\n\n"
                )
                # إضافة زر الانضمام إذا وجد رابط
                if lec.get('رابط_الحصة') and str(lec.get('رابط_الحصة')).startswith('http'):
                    keyboard.append([InlineKeyboardButton(f"🔗 انضم لمحاضرة {lec.get('التاريخ')}", url=lec.get('رابط_الحصة'))])
        else:
            msg += "⚠️ لا توجد محاضرات مجدولة حالياً لهذه المجموعة."
            
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="main_menu")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        
    else:
        # --- مسار الموظف: رحلة الاختيار بناءً على الصلاحيات ---
        allowed_courses = get_employee_allowed_courses(bot_token, user_id)
        
        if allowed_courses:
            keyboard = []
            for course in allowed_courses:
                keyboard.append([InlineKeyboardButton(f"📚 {course['name']}", callback_data=f"lec_course_{course['id']}")])
            
            keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="main_menu")])
            await query.edit_message_text("⚙️ <b>لوحة الموظف:</b>\nيرجى اختيار الدورة لعرض مجموعاتها المسموحة:", 
                                          reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            await query.answer("⚠️ عذراً، لا تملك صلاحيات لعرض الجداول أو لست مسجلاً كطالب.", show_alert=True)
 




# --------------------------------------------------------------------------
#دالة عرض اكود الخصم 
async def show_discount_codes_logic(update, context):
    """عرض كافة الأكواد النشطة للمستخدمين"""
    query = update.callback_query
    bot_token = context.bot.token
    
    codes = get_active_discount_codes(bot_token)
    
    msg = "<b>🎟 أكواد الخصم المتاحة حالياً:</b>\n\n"
    if codes:
        for c in codes:
            msg += (
                f"✅ الكود: <code>{c['code']}</code>\n"
                f"💰 الخصم: <b>{c['value']}</b>\n"
                f"📖 مخصص لـ: {c['course']}\n"
                f"📅 ينتهي في: {c['expiry']}\n"
                f"---------------------------\n"
            )
    else:
        msg += "⚠️ لا توجد أكواد خصم نشطة حالياً."
        
    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
 


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

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
    delete_group_by_id  # تم تصحيح الاسم هنا ليتطابق مع المحرك
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

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

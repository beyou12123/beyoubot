import logging
import re
import g4f
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sheets import ss, get_bot_setting, update_global_version, get_system_time
from sheets import get_filtered_library_content, get_user_referral_stats


logger = logging.getLogger(__name__)



# --------------------------------------------------------------------------



# --- [ 1. محرك الترجمة الذكي ] ---
async def translate_name_ai(arabic_name):
    """ترجمة الاسم للإنجليزية باستخدام g4f مع خطة احتياطية"""
    try:
        messages = [{"role": "system", "content": "Translate the following Arabic full name to English for a certificate. Return ONLY the English name."},
                    {"role": "user", "content": arabic_name}]
        response = await g4f.ChatCompletion.create_async(model=g4f.models.default, messages=messages)
        return response.strip() if response else arabic_name
    except:
        return arabic_name 
# --------------------------------------------------------------------------


# --- [ 2. بدء بوابة التسجيل الموحدة ] ---
async def start_registration_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id, payment_method="manual"):
    """بدء جمع البيانات البشرية خطوة بخطوة"""
    query = update.callback_query
    context.user_data['reg_flow'] = {
        'course_id': course_id,
        'pay_method': payment_method,
        'step': 'awaiting_full_name'
    }
    
    # جلب اسم الدورة من الكاش لسرعة الاستجابة
    from sheets import get_bot_data_from_cache
    courses = get_bot_data_from_cache(context.bot.token, "الدورات_التدريبية")
    course = next((c for c in courses if str(c.get('معرف_الدورة')) == str(course_id)), {})
    context.user_data['reg_flow']['course_name'] = course.get('اسم_الدورة', 'دورة تعليمية')

    await query.edit_message_text("📝 <b>بوابة التسجيل الموحدة</b>\n\nيرجى إرسال <b>اسمك الثلاثي باللغة العربية</b>:")
# --------------------------------------------------------------------------


# --- [ 3. معالج الخطوات التتابعية ] ---
async def process_registration_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = context.user_data.get('reg_flow')
    step = state.get('step')

    if step == 'awaiting_full_name':
        state['name_ar'] = text
        await update.message.reply_chat_action("typing")
        state['name_en'] = await translate_name_ai(text) # ترجمة آلية
        
        state['step'] = 'awaiting_gender'
        keyboard = [[InlineKeyboardButton("ذكر ♂️", callback_data="reg_gen_male"), 
                     InlineKeyboardButton("أنثى ♀️", callback_data="reg_gen_female")]]
        await update.message.reply_text("👤 يرجى اختيار الجنس:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif step == 'awaiting_country':
        state['country'] = text
        state['step'] = 'awaiting_phone'
        await update.message.reply_text("📞 أرسل <b>رقم الهاتف</b> مع المفتاح الدولي (يجب أن يبدأ بـ +):")

    elif step == 'awaiting_phone':
        # التحقق الصارم من علامة + والأرقام
        if not re.match(r'^\+\d+$', text):
            await update.message.reply_text("⚠️ خطأ! يجب أن يبدأ الرقم بـ + (مثال: +967700000000):")
            return
        state['phone'] = text
        state['step'] = 'awaiting_email'
        await update.message.reply_text("📧 أرسل <b>البريد الإلكتروني</b>:")

    elif step == 'awaiting_email':
        state['email'] = text
        await show_review_card(update, context)
# --------------------------------------------------------------------------


# --- [ 4. بطاقة المراجعة النهائية ] ---
async def show_review_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('reg_flow')
    review = (
        f"📋 <b>مراجعة بيانات التسجيل:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 الاسم (عربي): {state['name_ar']}\n"
        f"👤 الاسم (انجليزي): {state['name_en']}\n"
        f"🌍 البلد: {state['country']}\n"
        f"📞 الهاتف: {state['phone']}\n"
        f"📧 البريد: {state['email']}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💡 هل البيانات صحيحة؟"
    )
    keyboard = [
        [InlineKeyboardButton("نعم، البيانات صحيحة ✅", callback_data="confirm_reg_final")],
        [InlineKeyboardButton("تصحيح الاسم الإنجليزي 📝", callback_data="edit_reg_en_name")],
        [InlineKeyboardButton("العودة خطوة للخلف 🔙", callback_data="reg_back_step")],
        [InlineKeyboardButton("إلغاء والعودة للرئيسية 🏠", callback_data="main_menu")]
    ]
    await update.message.reply_text(review, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
# --------------------------------------------------------------------------


# --- [ 5. الضخ النهائي في قواعد البيانات (41 و 37 عمود) ] ---
async def finalize_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    bot_token = context.bot.token
    state = context.user_data.get('reg_flow')
    user = query.from_user
    now = get_system_time("full")

    try:
        # أ: تجهيز بيانات قاعدة_بيانات_الطلاب (41 عموداً)
        # الترتيب: bot_id(1), معرف_الفرع(2), معرف_الطالب(3), ID_المستخدم(4), الاسم_بالإنجليزي(5), الاسم_بالعربي(6)...
        student_id = f"STU{str(uuid.uuid4().int)[:5]}"
        row_db = [""] * 41
        row_db[0], row_db[1], row_db[2], row_db[3] = bot_token, "1001001", student_id, user.id
        row_db[4], row_db[5], row_db[7], row_db[9], row_db[10] = state['name_en'], state['name_ar'], state['country'], state['phone'], state['email']
        row_db[13], row_db[16], row_db[17], row_db[37] = "نشط", state['course_id'], state['course_name'], user.username
        
        ss.worksheet("قاعدة_بيانات_الطلاب").append_row(row_db)

        # ب: تجهيز سجل_التسجيلات (37 عموداً)
        reg_id = f"REG{str(uuid.uuid4().int)[:5]}"
        row_reg = [""] * 37
        row_reg[0], row_reg[1], row_reg[2], row_reg[3] = bot_token, "1001001", reg_id, now
        row_reg[4], row_reg[5], row_reg[6], row_reg[7], row_reg[8] = student_id, state['name_ar'], user.id, state['course_id'], state['course_name']
        row_reg[11], row_reg[13] = now, state['pay_method']
        
        ss.worksheet("سجل_التسجيلات").append_row(row_reg)
        update_global_version(bot_token)

        # تفرقة المسار المالي
        if state['pay_method'] == "manual":
            pay_info = get_bot_setting(bot_token, "payment_information", default="تواصل مع الإدارة")
            text = f"✅ <b>تم تسجيل بياناتك!</b>\n\n💰 <b>بيانات الدفع:</b>\n<code>{pay_info}</code>\n\n⚠️ يرجى إرسال صورة إيصال الدفع الآن:"
            context.user_data['action'] = 'awaiting_payment_receipt'
            await query.edit_message_text(text, parse_mode="HTML")
        else:
            await query.edit_message_text("🎉 مبروك! تم تفعيل الدورة بنجاح باستخدام نقاطك.")
            
        context.user_data.pop('reg_flow', None)
    except Exception as e:
        logger.error(f"Save error: {e}")
        await query.answer("❌ حدث خطأ في الحفظ.")


# --------------------------------------------------------------------------


async def show_course_content_ui(update, context, course_id):
    """عرض الدروس المتاحة للطالب فقط (مجاني + مدفوع إذا دفع)"""
    query = update.callback_query
    user_id = query.from_user.id
    bot_token = context.bot.token
    
    # استدعاء الدالة الذكية الجديدة التي تربط حالة الدفع في (قاعدة_بيانات_الطلاب) مع نوع الملف في (المكتبة)
    from sheets import get_filtered_library_content
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
    
    from sheets import get_user_referral_stats, ss
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
        f"━━━━━━━━━━━━━━\n"
        f"اختر دورة لبدء التعلم:"
    )
    
    keyboard = []
    for reg in student_courses:
        keyboard.append([InlineKeyboardButton(f"📖 {reg.get('اسم_الدورة')}", callback_data=f"open_content_{reg.get('معرف_الدورة')}")])
    
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="main_menu")])
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

# --------------------------------------------------------------------------





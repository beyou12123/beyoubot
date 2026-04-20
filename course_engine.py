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
        
        elif state['pay_method'] == "Gift":
            # جلب بيانات المسوق (المهدِي) لتنفيذ الخصم والإشعار
            gift_code = state.get('gift_code')
            from sheets import ss
            sheet_coupons = ss.worksheet("الكوبونات")
            coupon_cell = sheet_coupons.find(gift_code, in_column=3)
            
            if coupon_cell:
                inviter_id = sheet_coupons.cell(coupon_cell.row, 4).value # آيدي المسوق
                redeem_cost = get_bot_setting(bot_token, "min_points_redeem", default=100)
                
                # تنفيذ الخصم من رصيد المسوق
                from sheets import redeem_points_for_course
                success_deduct, new_balance = redeem_points_for_course(bot_token, inviter_id, redeem_cost)
                
                if success_deduct:
                    # تحديث حالة الكوبون وتوثيق الاستخدام بشكل احترافي
                    current_notes = sheet_coupons.cell(coupon_cell.row, 11).value or "" # جلب الملاحظة الحالية (اسم الدورة)
                    usage_log = f"{current_notes} | استخدمه: {state['name_ar']} ({user.id}) بتاريخ: {now}" # بناء السجل التوثيقي

                    sheet_coupons.update_cell(coupon_cell.row, 11, usage_log) # تحديث عمود الملاحظات
                    sheet_coupons.update_cell(coupon_cell.row, 8, "مستعمل") # تحديث الحالة لمنع إعادة الاستخدام
                    
                    # إرسال إشعار للمسوق باستخدام البيانات المجمعة
                    notification_text = (
                        f"📶 <b>عزيزي العميل</b>\n"
                        f"تم استخدام الهدية الممنوحة من قبلكم من قبل الشخص:\n\n"
                        f"👤 <b>معلومات العضو:</b>\n"
                        f"• الاسم: {state['name_ar']}\n"
                        f"• المعرّف: @{user.username or 'بدون'}\n"
                        f"• الآيدي: <code>{user.id}</code>\n\n"
                        f"💰 <b>رصيدك الحالي هو:</b> {new_balance} نقطة"
                    )
                    await context.bot.send_message(chat_id=inviter_id, text=notification_text, parse_mode="HTML")
                    await query.edit_message_text("🎉 مبروك! تم تفعيل الهدية وفتح الدورة لك بنجاح.")
                else:
                    await query.edit_message_text("⚠️ عذراً، تعذر إتمام عملية الهدية نظراً لنقص رصيد المانح أو خطأ في الكوبون.")
        
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
async def show_financial_dashboard(update, context):
    query = update.callback_query
    bot_token = context.bot.token
    
    # الاستدعاء المباشر من الكاش لتعويض الدوال المحذوفة
    from sheets import get_bot_data_from_cache
    
    # جلب البيانات الخام من الأوراق الأربعة
    users = get_bot_data_from_cache(bot_token, "المستخدمين")
    payroll = get_bot_data_from_cache(bot_token, "كشوف_المرتبات")
    withdrawals = get_bot_data_from_cache(bot_token, "سجل_السحوبات")
    registrations = get_bot_data_from_cache(bot_token, "سجل_التسجيلات")

    # الحسابات (بناءً على أعمدة الشيت التي حددتها)
    total_income = sum(float(r.get("المبلغ_المدفوع", 0) or 0) for r in registrations if r.get("حالة_الدفع") == "مدفوع")
    affiliate_liabilities = sum(float(u.get("رصيد", 0) or 0) for u in users)
    pending_payroll = sum(float(p.get("صافي_الراتب", 0) or 0) for p in payroll if p.get("حالة_الصرف") == "معلق")
    actual_payouts = sum(float(w.get("المبلغ", 0) or 0) for w in withdrawals if w.get("الحالة") == "مكتمل")

    current_cash = total_income - actual_payouts
    net_profit = current_cash - affiliate_liabilities - pending_payroll

    # نص الرسالة المنسق
    text = (
        f"📊 <b>تقرير الخزينة والتدفق المالي اللحظي:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <b>إجمالي الإيرادات:</b> <code>{total_income}</code>\n"
        f"💸 <b>سحوبات تم سدادها:</b> <code>{actual_payouts}</code>\n"
        f"--------------------------\n"
        f"🏛 <b>السيولة الحالية (Cash):</b> <code>{current_cash}</code>\n"
        f"--------------------------\n"
        f"⚠️ <b>التزامات مالية قائمة:</b>\n"
        f"👥 أرصدة مسوقين: <code>{affiliate_liabilities}</code>\n"
        f"👔 رواتب معلقة: <code>{pending_payroll}</code>\n"
        f"--------------------------\n"
        f"💎 <b>صافي الربح المتوقع:</b> <code>{net_profit}</code>\n\n"
        f"<i>💡 البيانات مجلوبة من الكاش المركزي لضمان السرعة.</i>"
    )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[InlineKeyboardButton("🔙 عودة للوحة المالية", callback_data="manage_financial")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --------------------------------------------------------------------------
# =============================================================
# --- [ محرك إدارة مستحقات الكادر والمسوقين ] ---
# =============================================================

async def show_payroll_management(update, context):
    """عرض قائمة الرواتب المعلقة للصرف بناءً على الكاش"""
    query = update.callback_query
    bot_token = context.bot.token
    from sheets import get_bot_data_from_cache
    
    payroll_list = get_bot_data_from_cache(bot_token, "كشوف_المرتبات")
    # تصفية الرواتب المعلقة (حالة_الصرف هو العمود 9 في الشيت)
    pending = [p for p in payroll_list if str(p.get("حالة_الصرف")) == "معلق"]
    
    if not pending:
        text = "✅ <b>لا توجد رواتب معلقة للصرف حالياً.</b>"
        keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data="manage_financial")]]
    else:
        text = "👔 <b>كشوف المرتبات المعلقة (انتظار الصرف):</b>\n"
        text += "━━━━━━━━━━━━━━\n"
        for p in pending:
            text += f"👤 <b>الموظف:</b> <code>{p.get('معرف_الموظف')}</code>\n" \
                    f"📅 <b>الشهر:</b> {p.get('الشهر')}\n" \
                    f"💵 <b>المبلغ:</b> <code>{p.get('صافي_الراتب')}</code>\n" \
                    f"--------------------------\n"
        text += "\n💡 <i>يمكنك تحديث الحالة إلى 'تم الصرف' من الشيت لتنعكس هنا فوراً.</i>"
        keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data="manage_financial")]]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --------------------------------------------------------------------------
# --- [ محرك إدارة سحوبات المسوقين ] ---
async def show_marketers_payouts(update, context):
    """عرض طلبات السحب المقدمة من المسوقين"""
    query = update.callback_query
    bot_token = context.bot.token
    
    from sheets import get_bot_data_from_cache
    withdrawals = get_bot_data_from_cache(bot_token, "سجل_السحوبات")
    
    # تصفية الطلبات التي تنتظر التنفيذ
    pending_reqs = [w for w in withdrawals if str(w.get("الحالة")) == "قيد الانتظار"]
    
    if not pending_reqs:
        text = "✅ <b>لا توجد طلبات سحب معلقة حالياً.</b>"
        keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data="manage_financial")]]
    else:
        text = "💸 <b>طلبات سحب الأرباح المعلقة:</b>\n"
        text += "━━━━━━━━━━━━━━\n"
        for r in pending_reqs:
            text += f"👤 <b>المسوق:</b> {r.get('اسم_المستخدم')}\n" \
                    f"💰 <b>المبلغ:</b> <code>{r.get('المبلغ')}</code>\n" \
                    f"🏦 <b>الوسيلة:</b> {r.get('وسيلة_التحويل')}\n" \
                    f"🎫 <b>المعرف:</b> <code>{r.get('معرف_الطلب')}</code>\n" \
                    f"--------------------------\n"
        text += "\n⚠️ يرجى استخدام زر (اعتماد الصرف) المرفق مع كل طلب في سجل المحادثات."
        keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data="manage_financial")]]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --------------------------------------------------------------------------
# --- [ محرك ضبط الإعدادات المالية ] ---
async def show_financial_settings(update, context):
    """عرض واجهة التحكم في الأسعار والعمولات من الكاش"""
    query = update.callback_query
    bot_token = context.bot.token
    
    from sheets import get_bot_setting
    
    # جلب القيم الحالية من ورقة الإعدادات عبر الكاش لضمان السرعة
    course_price = get_bot_setting(bot_token, "subscription_price", default="100")
    commission = get_bot_setting(bot_token, "marketers_commission", default="10%")
    min_payout = get_bot_setting(bot_token, "maximum_withdrawal_marketers", default="50")
    currency = get_bot_setting(bot_token, "currency_unit", default="نقطة")

    text = (
        f"⚙️ <b>ضبط الإعدادات المالية للمنصة:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <b>سعر الاشتراك الافتراضي:</b> <code>{course_price}</code>\n"
        f"📣 <b>عمولة المسوقين:</b> <code>{commission}</code>\n"
        f"💳 <b>الحد الأدنى للسحب:</b> <code>{min_payout} {currency}</code>\n"
        f"🪙 <b>وحدة العملة:</b> <code>{currency}</code>\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚠️ <i>ملاحظة: يمكنك تعديل هذه القيم مباشرة من ورقة 'الإعدادات' في ملف جوجل شيت لتحديثها فوراً في البوت.</i>"
    )

    keyboard = [[InlineKeyboardButton("🔙 عودة للوحة المالية", callback_data="manage_financial")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --------------------------------------------------------------------------
# =============================================================
# --- [ محرك الأوسمة والإنجازات التحفيزي ] ---
# =============================================================

async def show_honors_main_menu(update, context):
    """الواجهة الرئيسية للأوسمة (تختلف حسب الرتبة)"""
    query = update.callback_query
    user_id = query.from_user.id
    bot_token = context.bot.token
    
    from sheets import get_bot_config
    config = get_bot_config(bot_token)
    is_admin = str(user_id) == str(config.get("admin_ids"))

    if is_admin:
        text = "🏆 <b>لوحة التحكم في الأوسمة والإنجازات:</b>\nيمكنك منح أوسمة جديدة للطلاب المتميزين أو استعراض سجل الإنجازات العام."
        keyboard = [
            [InlineKeyboardButton("🏅 منح وسام لطالب", callback_data="grant_medal_start")],
            [InlineKeyboardButton("📜 سجل الإنجازات العام", callback_data="view_all_achievements")],
            [InlineKeyboardButton("🔙 عودة", callback_data="tech_settings")]
        ]
    else:
        # واجهة الطالب لاستعراض أوسمته الخاصة
        from sheets import ss
        sheet = ss.worksheet("الأوسمة")
        my_medals = [r for r in sheet.get_all_records() 
                     if str(r.get("bot_id")) == str(bot_token) and str(r.get("معرف_الطالب")) == str(user_id)]
        
        text = f"🏅 <b>خزانة أوسمتك الرقمية:</b>\nلديك حالياً ({len(my_medals)}) أوسمة تكريمية."
        keyboard = []
        for m in my_medals:
            keyboard.append([InlineKeyboardButton(f"🎖 {m.get('اسم_الوسام')}", callback_data=f"view_medal_{m.get('معرف_الوسام')}")])
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="main_menu")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# استبدل الدالة القديمة في course_engine.py بهذه النسخة المحدثة
async def process_grant_medal_step(update, context):
    """معالجة خطوات منح (وسام/إنجاز) وربطها بالمحرك الموحد لـ 19 عموداً"""
    text = update.message.text.strip()
    action = context.user_data.get('action')
    
    if action == 'awaiting_medal_student_id':
        # الخطوة 1: استقبال ID الطالب
        context.user_data['temp_reward'] = {'student_id': text} # نستخدم temp_reward الموحد
        context.user_data['action'] = 'awaiting_medal_name'
        await update.message.reply_text("🏅 أرسل الآن <b>عنوان التكريم</b> (مثلاً: الطالب المثالي):", parse_mode="HTML")
    
    elif action == 'awaiting_medal_name':
        # الخطوة 2: استقبال العنوان
        context.user_data['temp_reward']['title'] = text
        context.user_data['action'] = 'awaiting_medal_reason'
        await update.message.reply_text("📝 أرسل <b>سبب المنح أو تفاصيل الإنجاز</b> باختصار:", parse_mode="HTML")
        
    elif action == 'awaiting_medal_reason':
        # الخطوة 3: استقبال السبب والحفظ النهائي
        context.user_data['temp_reward']['reason'] = text
        
        # استدعاء المحرك الموحد (الذي يحفظ الـ 19 عموداً)
        success = await grant_reward_unified(update, context, reward_type="وسام")
        
        if success:
            await update.message.reply_text(f"✅ تم منح وسام <b>{context.user_data['temp_reward']['title']}</b> وحفظه في السجل الموحد بنجاح!")
        else:
            await update.message.reply_text("❌ حدث خطأ أثناء الحفظ في الورقة المدمجة.")
            
        context.user_data['action'] = None
        context.user_data.pop('temp_reward', None)

# =============================================================
# --- [ محرك الأوسمة والإنجازات المدمج - 19 عموداً ] ---
# =============================================================
async def grant_reward_unified(update, context, reward_type="وسام"):
    """
    منح وسام أو إنجاز وحفظه في الورقة المدمجة (19 عموداً) + الإعلان في القنوات
    reward_type: "وسام" أو "إنجاز"
    """
    bot_token = context.bot.token
    admin_id = update.effective_user.id
    # سحب البيانات من ذاكرة المحادثة المؤقتة
    reward_data = context.user_data.get('temp_reward', {})
    
    from sheets import ss, get_system_time, update_global_version, get_bot_setting
    from telegram import Bot
    
    try:
        # بناء الصف الموحد (19 عموداً) بمطابقة تامة للمخطط المدمج
        row = [
            str(bot_token),                            # 1. bot_id
            "1001001",                                 # 2. معرف_الفرع
            f"REW{str(uuid.uuid4().int)[:5]}",         # 3. معرف_السجل
            str(reward_data.get('student_id')),        # 4. معرف_الطالب
            str(reward_data.get('student_name', '-')), # 5. اسم_الطالب
            str(reward_type),                          # 6. النوع (وسام/إنجاز)
            str(reward_data.get('title')),             # 7. العنوان
            str(reward_data.get('desc', '-')),         # 8. الوصف
            str(reward_data.get('reason', '-')),       # 9. السبب_أو_المصدر
            get_system_time("date"),                   # 10. تاريخ_الحدث
            str(admin_id),                             # 11. منح_بواسطة
            str(reward_data.get('course_id', '-')),    # 12. معرف_الدورة
            str(reward_data.get('group_id', '-')),     # 13. معرف_المجموعة
            str(reward_data.get('level', '-')),        # 14. المستوى
            str(reward_data.get('points', '0')),       # 15. النقاط
            "TRUE",                                    # 16. مرئي_للطالب
            str(reward_data.get('notes', '-')),        # 17. ملاحظات
            get_system_time("full"),                   # 18. تاريخ_التحديث
            "نشط"                                      # 19. حالة_السجل
        ]
        
        # 1. التنفيذ الفعلي في جوجل شيت
        ss.worksheet("الأوسمة_والإنجازات").append_row(row)
        
        # 2. رفع الإصدار لتحديث الكاش فوراً
        update_global_version(bot_token)

        # 3. محرك الإعلان العام (اللمسة الإضافية)
        public_chan = get_bot_setting(bot_token, "public_channel_id")
        honors_chan = get_bot_setting(bot_token, "honors_channel_id")
        
        icon = "🏅" if str(reward_type) == "وسام" else "📜"
        announcement_text = (
            f"🎊 <b>تهنئة مستحقة لـ أحد أبطالنا!</b> 🎊\n\n"
            f"تم منح الطالب: <b>{reward_data.get('student_name', '-')}</b>\n"
            f"{icon} <b>{reward_type}:</b> {reward_data.get('title')}\n"
            f"🎯 <b>بسبب:</b> {reward_data.get('reason', '-')}\n\n"
            f"<i>نحن نفخر بوجود أمثالك في منصتنا.. إلى الأمام! 🚀</i>"
        )

        # محاولة الإرسال للقنوات المحددة في الإعدادات
        target_channels = []
        if public_chan: target_channels.append(public_chan)
        if honors_chan: target_channels.append(honors_chan)

        for channel_id in target_channels:
            if str(channel_id).startswith("-100"):
                try:
                    await context.bot.send_message(chat_id=channel_id, text=announcement_text, parse_mode="HTML")
                except Exception as send_err:
                    logger.error(f"⚠️ فشل الإرسال للقناة {channel_id}: {send_err}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error in grant_reward_unified: {e}")
        return False


# دالة عرض تفاصيل الوسام
async def view_medal_details(update, context, record_id):
    """عرض تفاصيل وسام أو إنجاز محدد من الكاش"""
    query = update.callback_query
    bot_token = context.bot.token
    from sheets import get_bot_data_from_cache

    # سحب البيانات من الكاش لسرعة استجابة فائقة
    rewards = get_bot_data_from_cache(bot_token, "الأوسمة_والإنجازات")
    medal = next((r for r in rewards if str(r.get("معرف_السجل")) == str(record_id)), None)

    if not medal:
        await query.answer("⚠️ تعذر العثور على تفاصيل هذا السجل.", show_alert=True)
        return

    text = (
        f"{'🏅' if medal.get('النوع') == 'وسام' else '📜'} <b>تفاصيل الإنجاز:</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 <b>الطالب:</b> {medal.get('اسم_الطالب')}\n"
        f"🏷 <b>العنوان:</b> {medal.get('العنوان')}\n"
        f"📝 <b>الوصف:</b> {medal.get('الوصف')}\n"
        f"🎯 <b>السبب:</b> {medal.get('السبب_أو_المصدر')}\n"
        f"💰 <b>النقاط المكتسبة:</b> {medal.get('النقاط')} نقطة\n"
        f"📅 <b>التاريخ:</b> {medal.get('تاريخ_الحدث')}\n"
        f"━━━━━━━━━━━━━━"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data="honors_achievements")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
 
# عرض تفاصيل الوسام ادمن 
async def view_all_achievements_admin(update, context):
    """عرض سجل بكافة الأوسمة الممنوحة في البوت (للمالك)"""
    query = update.callback_query
    bot_token = context.bot.token
    from sheets import get_bot_data_from_cache

    rewards = get_bot_data_from_cache(bot_token, "الأوسمة_والإنجازات")
    
    if not rewards:
        text = "📭 <b>سجل الإنجازات فارغ حالياً.</b>"
        keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data="honors_achievements")]]
    else:
        text = "📜 <b>السجل العام للأوسمة والإنجازات:</b>\nانقر على السجل للتفاصيل:"
        keyboard = []
        for r in rewards[-10:]: # عرض آخر 10 إنجازات فقط للسرعة
            label = f"{r.get('اسم_الطالب')} - {r.get('العنوان')}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"view_medal_{r.get('معرف_السجل')}")])
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="honors_achievements")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
 # =============================================================
# --- [ واجهة الطالب للأوسمة والإنجازات - النظام المدمج ] ---
# =============================================================

async def show_student_honors(update, context):
    """عرض قائمة أوسمة وإنجازات الطالب من الكاش"""
    query = update.callback_query
    user_id = query.from_user.id
    bot_token = context.bot.token
    
    from sheets import get_bot_data_from_cache
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # جلب البيانات المدمجة من الكاش
    all_records = get_bot_data_from_cache(bot_token, "الأوسمة_والإنجازات")
    
    # فلترة السجلات الخاصة بهذا الطالب والتي تم تعليمها كـ "مرئي_للطالب"
    student_rewards = [
        r for r in all_records 
        if str(r.get("معرف_الطالب")) == str(user_id) and str(r.get("مرئي_للطالب")).upper() == "TRUE"
    ]

    if not student_rewards:
        text = "🏅 <b>سجل الأوسمة:</b>\n\nلا توجد أوسمة أو إنجازات مسجلة باسمك حالياً. استمر في الاجتهاد لتظهر إنجازاتك هنا! ✨"
        keyboard = [[InlineKeyboardButton("🔙 عودة للقائمة الرئيسية", callback_data="main_menu")]]
    else:
        text = "🏆 <b>خزانة الأوسمة والإنجازات:</b>\nفخورون بك! إليك قائمة بإنجازاتك المحققة، انقر على أي منها للتفاصيل:"
        keyboard = []
        
        # بناء قائمة الأزرار ديناميكياً
        for item in student_rewards:
            # تمييز النوع بالإيموجي
            icon = "🏅" if item.get("النوع") == "وسام" else "📜"
            label = f"{icon} {item.get('العنوان')} ({item.get('تاريخ_الحدث')})"
            # نرسل معرف السجل في الـ callback ليتم التعرف عليه
            keyboard.append([InlineKeyboardButton(label, callback_data=f"st_medal_{item.get('معرف_السجل')}")])
        
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="main_menu")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def view_single_achievement(update, context, record_id):
    """عرض التفاصيل الفخمة لإنجاز محدد"""
    query = update.callback_query
    bot_token = context.bot.token
    from sheets import get_bot_data_from_cache
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    all_records = get_bot_data_from_cache(bot_token, "الأوسمة_والإنجازات")
    item = next((r for r in all_records if str(r.get("معرف_السجل")) == str(record_id)), None)

    if not item:
        await query.answer("⚠️ تعذر العثور على تفاصيل السجل.", show_alert=True)
        return

    # تنسيق الرسالة بشكل فخم
    icon = "🏅" if item.get("النوع") == "وسام" else "📜"
    text = (
        f"{icon} <b>بطل الإنجاز: {item.get('اسم_الطالب')}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"✨ <b>العنوان:</b> {item.get('العنوان')}\n"
        f"📝 <b>الوصف:</b> {item.get('الوصف')}\n"
        f"🎯 <b>السبب/المصدر:</b> {item.get('السبب_أو_المصدر')}\n"
        f"--------------------------\n"
        f"📊 <b>المستوى:</b> {item.get('المستوى')}\n"
        f"➕ <b>النقاط المضافة:</b> <code>{item.get('النقاط')}</code> نقطة\n"
        f"📅 <b>تاريخ المنح:</b> {item.get('تاريخ_الحدث')}\n"
        f"━━━━━━━━━━━━━━\n"
        f"<i>مبارك لك هذا التميز، استمر نحو القمة! 🚀</i>"
    )

    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="honors_achievements")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --------------------------------------------------------------------------
# --- [ محرك ضبط قنوات الإشعارات ] ---

# =============================================================
# --- [ محرك ضبط قنوات الإشعارات - التنفيذي ] ---
# =============================================================

async def set_channel_id_flow(update, context, channel_type):
    """بدء عملية طلب معرف القناة من المالك"""
    query = update.callback_query
    
    # ربط المفاتيح البرمجية بالعناوين العربية للعرض
    titles = {
        "public_channel_id": "القناة الرسمية",
        "honors_channel_id": "قناة الأوسمة والإنجازات"
    }
    
    # تخزين الحالة في user_data لتوجيه الرسالة القادمة
    context.user_data['awaiting_setting_key'] = channel_type
    context.user_data['awaiting_setting_title'] = titles.get(channel_type)
    
    text = (
        f"🛠 <b>إعداد {titles.get(channel_type)} :</b>\n\n"
        f"يرجى إرسال بيانات القناة الآن بأي صيغة تفضلها:\n"
        f"🔗 <b>رابط القناة:</b> <code>https://t.me/Afaq_Library</code>\n"
        f"📧 <b>معرف القناة:</b> <code>@Afaq_Library</code>\n"
        f"🆔 <b>الآيدي الرقمي:</b> <code>-1001197736144</code>\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚠️ <b>تنبيهات هامة:</b>\n"
        f"1️⃣ يجب أن يكون البوت <b>مشرفاً (Admin)</b> في القناة.\n"
        f"2️⃣ تأكد من منح البوت صلاحية <b>'نشر الرسائل'</b>.\n"
        f"3️⃣ سيقوم النظام بالتعرف على القناة وحفظها آلياً.\n\n"
        f"<i>بانتظار إرسال الرابط أو المعرف...</i>"
    )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="database_preparation")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def save_channel_id_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دالة ذكية تستقبل (رابط، يوزر، أو ID) وتقوم بتحويله إلى ID رقمي 
    ثم تحفظه في شيت الإعدادات مع تحديث الكاش.
    """
    user_input = update.message.text.strip()
    setting_key = context.user_data.get('awaiting_setting_key')
    setting_title = context.user_data.get('awaiting_setting_title')
    bot_token = context.bot.token

    # 1. المحرك الذكي لاستخراج المعرف (Username) من المدخلات
    target_username = user_input
    
    # إذا كان الرابط كاملاً https://t.me/Afaq_Library
    if "t.me/" in user_input:
        target_username = user_input.split("t.me/")[-1].replace("@", "")
    # إذا كان يوزر يبدأ بـ @
    elif user_input.startswith("@"):
        target_username = user_input.replace("@", "")
    
    try:
        # 2. الاستعلام من تليجرام للحصول على البيانات الرسمية (get_chat)
        # ملاحظة: يجب أن يكون البوت مشرفاً في القناة ليتمكن من جلب بياناتها
        chat_data = await context.bot.get_chat(target_username)
        final_chat_id = str(chat_data.id)
        channel_name = chat_data.title
        
        # 3. التأكد من أن المعرف يبدأ بـ -100 (للقنوات والمجموعات الخارقة)
        # تليجرام يعيد المعرف الرقمي كاملاً تلقائياً عبر get_chat
        
        # 4. عملية الحفظ في جوجل شيت (نفس المنطق الأصلي بدون تغيير)
        from sheets import ss, update_global_version  # استيراد محلي للحفاظ على الهيكل
        
        try:
            sheet = ss.worksheet("الإعدادات")
            cell = sheet.find(setting_key)
            row_index = cell.row
            
            # تحديث القيمة في العمود C (المعرف الرقمي الصافي)
            sheet.update_cell(row_index, 3, final_chat_id)
            
            # مزامنة الكاش فوراً لضمان عمل البوتات الأخرى بالمعرف الجديد
            update_global_version(bot_token)
            
            success_msg = (
                f"✅ <b>تم الربط بنجاح!</b>\n\n"
                f"📢 <b>القناة:</b> {channel_name}\n"
                f"🆔 <b>المعرف الرقمي:</b> <code>{final_chat_id}</code>\n"
                f"⚙️ <b>الإعداد:</b> {setting_title}\n\n"
                f"<i>الآن سيقوم البوت باستخدام هذا المعرف لإرسال الأوسمة والتحقق من الاشتراك.</i>"
            )
            await update.message.reply_text(success_msg, parse_mode="HTML")
            
        except Exception as sheet_error:
            logger.error(f"❌ Error updating sheet: {sheet_error}")
            await update.message.reply_text(f"❌ فشل تحديث الشيت، تأكد من وجود المفتاح <code>{setting_key}</code>")

    except Exception as telegram_error:
        logger.warning(f"⚠️ Telegram API Error: {telegram_error}")
        error_text = (
            f"❌ <b>تعذر التعرف على القناة!</b>\n\n"
            f"تأكد من الآتي:\n"
            f"1. أن الرابط أو المعرف صحيح.\n"
            f"2. أن البوت <b>مشرف (Admin)</b> في القناة ليتمكن من استخراج بياناتها."
        )
        await update.message.reply_text(error_text, parse_mode="HTML")

    # تنظيف ذاكرة الجلسة
    context.user_data.pop('awaiting_setting_key', None)
    context.user_data.pop('awaiting_setting_title', None)

# --------------------------------------------------------------------------
# دالة المعلومات الشاملة للمالك 
async def show_system_setup_information(update, context):
    """عرض الدليل الشامل لتهيئة المنصة التعليمية للمالك"""
    query = update.callback_query
    
    text = (
        "🚀 <b>الدليل الشامل لتهيئة منصتك التعليمية</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "مرحباً بك يا دكتور! لضمان عمل المنصة بكفاءة واستقرار، يرجى اتباع الخطوات التالية بالترتيب الموصى به:\n\n"
        
        "1️⃣ <b>تنشيط نبض النظام (المزامنة):</b>\n"
        "بدايةً، قم بالضغط على زر <b>(🛠 الإعدادات العامة وتجهيز النظام)</b>، ثم <b>(🔄 المزامنة)</b>. هذا الإجراء يضمن سحب كافة هياكل الجداول وتجهيز الذاكرة المركزية للبوت ليعمل بأقصى سرعة.\n\n"
        
       "2️⃣ <b>ضبط الهوية الذكية (AI):</b>\n"
       "انتقل إلى <b>(🤖 ضبط الـ AI)</b> لتعريف اسم منشأتك ووضع التعليمات الخاصة بمساعدك الذكي، ليرد على الطلاب بهويتك الرسمية. (ملاحظة هامة: قد يتم مطالبتك بها عند بداية تشغيل البوت، وإذا تم ضبطها فلا داعي لضبطها مرة أخرى).\n\n"
        
        "3️⃣ <b>تأسيس الفروع الإدارية:</b>\n"
        "توجه إلى <b>(إدارة الفروع)</b> وأنشئ فرعك الأول. لا يمكن إضافة مدربين أو دورات دون وجود فرع واحد على الأقل مسجل في النظام.\n\n"
        
        "4️⃣ <b>بناء الكادر التعليمي والإداري:</b>\n"
        "من قسم <b>(تكويد الكادر)</b>، قم بتوليد روابط انضمام للمدربين والموظفين. بعد انضمامهم، انتقل لـ <b>(👨‍🏫 الصلاحيات)</b> لمنح كل فرد مهامه المحددة.\n\n"
        
        "5️⃣ <b>هيكلة المحتوى التعليمي:</b>\n"
        "• أضف <b>(📁 الأقسام)</b> أولاً (مثلاً: قسم اللغات).\n"
        "• ثم أضف <b>(📚 الدورات)</b> داخل تلك الأقسام واربطها بمدربيها.\n"
        "• أنشئ <b>(إدارة المجموعات)</b> لتحديد مواقيت الدراسة لكل دورة.\n\n"
        
        "6️⃣ <b>تفعيل القنوات الرسمية:</b>\n"
        "من <b>(تجهيز قاعدة البيانات)</b>، قم بربط آيدي القناة العامة وقناة الأوسمة، ليفوم النظام بنشر الإشعارات والتكريمات تلقائياً.\n\n"
        
        "7️⃣ <b>الضبط المالي ونقاط الإحالة:</b>\n"
        "قم بضبط <b>(معلومات الدفع)</b> وقيم النقاط الممنوحة عند دعوة الطلاب، لتفعيل نظام (اربح دورات مجانية) لطلابك.\n\n"
        
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>ملاحظة: يمكنك دائماً استيراد البيانات دفعة واحدة عبر ملف Excel من خلال زر (📊 استيراد Excel) لتوفير الوقت.</i>"
    )

    keyboard = [[InlineKeyboardButton("🔙 عودة للوحة التحكم", callback_data="back_to_admin")]]
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





import logging
import re
import io
import uuid
import g4f  # لضمان عمل المحرك المجاني الذي اعتمدناه
import google.generativeai as genai
from datetime import datetime
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

# الكتلة المدمجة لملف sheets.py 
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
    delete_course_by_id,
    get_system_time, 
    get_ai_setup,        # مضافة من الاستدعاء الداخلي
    link_user_to_inviter, # مضافة من الاستدعاء الداخلي
    get_newly_activated_students, # مضافة من مراقب التفعيل
    ss                   # مضافة لاستخدامها في تحديث الشيت
)
# كتلة استيراد الملفات الزميلة (الموديولات) 
from educational_manager import manage_groups_main
from bot_callbacks import contact_callback_handler, get_admin_panel
from bot_messages import handle_contact_message
# --- [ ذاكرة المحادثات المؤقتة للطلاب ] ---
user_messages = {} 
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

# --- [ المعالجات الأساسية - أمر البداية ] ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start برسائل ترحيبية ذكية ودعم نظام الإحالة"""

    user = update.effective_user
    bot_token = context.bot.token
    # تحديد هل القادم ضغطة زر أم رسالة نصية لضمان عدم حدوث Error
    query = update.callback_query
    # جلب كافة الإعدادات من قاعدة البيانات
    config = get_bot_config(bot_token)
    bot_owner_id = str(config.get("owner_id", "0"))
    admin_list = str(config.get("admin_ids", "0")).split(",")
    ai_config = get_ai_setup(bot_token)
    # --- [ فحص إعدادات المالك (التهيئة الأولى) ] ---
    if str(user.id) == bot_owner_id:

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
    # نضع نظام الإحالة قبل التسجيل لضمان ربط الداعي بالمدعو فوراً
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
    if str(user.id) == bot_owner_id or str(user.id) in admin_list:

        # واجهة الإدارة (المسؤول)
        admin_text = (
            f"<b>مرحباً بك يا دكتور {user.first_name} في مركز قيادة منصتك</b> 🎓\n\n"
            f"{msg}\n\n"
            f"يمكنك إدارة كافة تفاصيل المنصة من الأزرار أدناه:"
        )
        
        # تصحيح: دمج السطر العائم المكرر داخل شرط التحقق لضمان عدم توقف البوت

        if query:
            await query.answer()
            await query.edit_message_text(admin_text, reply_markup=get_admin_panel(), parse_mode="HTML")
    else:
        # واجهة الطالب
        student_text = f"<b>{msg}</b>"
        if query:
            await query.answer()
            await query.edit_message_text(admin_text, reply_markup=get_admin_panel(), parse_mode="HTML")
        else:
            await update.message.reply_text(admin_text, reply_markup=get_admin_panel(), parse_mode="HTML")

# --------------------------------------------------------------------------
#دالة فحص الطلاب وإرسال الرسائل 
async def activation_monitor(context: ContextTypes.DEFAULT_TYPE):
    """وظيفة خلفية تراقب تفعيلات الطلاب وترسل تنبيهات فورا"""
    bot_token = context.bot.token

    
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
            sheet.update_cell(student['row'], 21, f"تم الإشعار: {get_system_time('full')}")

        except Exception as e:
            print(f"⚠️ فشل إرسال إشعار للطالب {student['user_id']}: {e}")


# --- [ محرك التشغيل المتوافق مع المصنع ] ---

async def run_bot(token, owner_id):
    """هذه الدالة هي التي يستدعيها ملف main.py لتشغيل البوت ديناميكياً"""
    application = ApplicationBuilder().token(token).build()
    
    # 1. إضافة المعالجات (Handlers)
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CallbackQueryHandler(contact_callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_message))
    
    # 2. إعداد مراقب التفعيل (يُوضع هنا بعد تعريف الـ application)
    # سيقوم بفحص الشيت كل 60 ثانية وإرسال رسائل للطلاب المفعلين
    job_queue = application.job_queue
    job_queue.run_repeating(activation_monitor, interval=60, first=10)
    
    # 3. بدء تشغيل المحرك
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
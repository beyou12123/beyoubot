import os
import sys
import re
import asyncio

# استيراد الأدوات الأساسية من مكتبة تليجرام
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardRemove
)

# استيراد أدوات المعالجة والتشغيل من مكتبة telegram.ext
from telegram.ext import (
    Application,
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler, 
    ConversationHandler
)

# استيراد الدوال من ملف البرمجة الخاص بجوجل شيت (sheets.py)
from sheets import save_user, save_bot, update_content_setting, get_bot_config, add_log_entry

# --- الإعدادات الأساسية ---
TOKEN = "8532487667:AAGeWhNyLZri9BxZMCw3AQZaJmOI5OVdxkE"
ADMIN_ID = 873158772  # معرف المطور والمالك

# تعريف مراحل محادثة إنشاء البوت (حالات الـ ConversationHandler)
CHOOSING_TYPE, GETTING_TOKEN, GETTING_NAME = range(3)

# --- القوائم (Keyboard Markups) ---
main_menu = [["➕ إنشاء بوت"], ["🛠 لوحة التحكم (للمالك)"]]
admin_options = [["📝 تعديل النصوص", "⚙️ إعدادات الموديولات"], ["🔙 العودة للقائمة الرئيسية"]]
types_menu = [["📩 تواصل"], ["🛡 حماية"], ["🎓 منصة تعليمية"], ["🛒 متجر"]]

# --------------------------------------------------------------------------

async def load_and_run_sub_bots():
    """هذه الدالة تقرأ التوكينات من الشيت وتشغلها"""
    # هنا سنقوم بجلب التوكينات من ورقة 'البوتات_المصنوعة'
    # وتشغيلها باستخدام نظام الحلقات (Loops)
    # ملاحظة: يتطلب هذا وجود ملف برمجى لكل نوع بوت (تواصل، حماية، إلخ)
    print("🔄 جاري تحميل وتشغيل البوتات المصنوعة...")
    pass 
# --------------------------------------------------------------------------
# [مكان إضافة الدوال والوظائف البرمجية المستقبلية]
# يمكنك كتابة أي دوال جديدة هنا (مثل دوال الإحصائيات المتقدمة أو أنظمة الدفع)
# --------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة الانطلاق وتسجيل المستخدم في قاعدة البيانات"""
    user = update.effective_user
    # حفظ أو تحديث بيانات المستخدم في جوجل شيت
    save_user(user.id, user.username)
    
    # التحقق من الصلاحيات لإظهار لوحة التحكم للمالك فقط
    current_menu = main_menu if user.id == ADMIN_ID else [["➕ إنشاء بوت"]]
    
    await update.message.reply_text(
        "✨ أهلاً بك في مصنع البوتات المتطور 🤖\n\n"
        "أنا بوت المصنع، يمكنني مساعدتك في إنشاء وإدارة بوتاتك الخاصة بسهولة وربطها بقاعدة بيانات جوجل.",
        reply_markup=ReplyKeyboardMarkup(current_menu, resize_keyboard=True)
    )

# --- نظام إنشاء البوت (Conversation Flow) ---

async def start_create_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إنشاء بوت جديد وطلب اختيار النوع"""
    await update.message.reply_text(
        "🛠 **مرحباً بك في قسم التصنيع**\n\nاختر نوع البوت الذي تريد إنشاءه:",
        reply_markup=ReplyKeyboardMarkup(types_menu, resize_keyboard=True, one_time_keyboard=True)
    )
    return CHOOSING_TYPE

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخزين النوع المختار وطلب التوكن"""
    bot_type = update.message.text
    context.user_data["type"] = bot_type
    
    await update.message.reply_text(
        f"✅ تم اختيار نوع: {bot_type}\n\n"
        "الآن، من فضلك أرسل **API Token** الخاص بالبوت.\n"
        "يمكنك الحصول عليه من @BotFather",
        reply_markup=ReplyKeyboardRemove()
    )
    return GETTING_TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من صحة التوكن وطلب اسم البوت"""
    token = update.message.text.strip()
    
    # التحقق من تنسيق التوكن باستخدام التعبيرات النمطية (Regex)
    if not re.match(r'^\d+:[A-Za-z0-9_-]{35,}$', token):
        await update.message.reply_text("❌ التوكن غير صحيح! يرجى إرسال توكن صالح من @BotFather")
        return GETTING_TOKEN
    
    context.user_data["bot_token"] = token
    await update.message.reply_text("✅ التوكن سليم. الآن أرسل **اسماً** لهذا البوت:")
    return GETTING_NAME
# --------------------------------------------------------------------------

async def finalize_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ البيانات وإنهاء المحادثة مع تشغيل البوت في مهمة منفصلة لعدم التعليق"""
    bot_name = update.message.text.strip()
    user_id = update.effective_user.id
    bot_type = context.user_data.get("type")
    bot_token = context.user_data.get("bot_token")
    
    msg = await update.message.reply_text("⏳ جاري تسجيل البوت وتشغيل المحرك...")

    # 1. عملية الحفظ في الشيت
    success = save_bot(user_id, bot_type, bot_name, bot_token)

    if success:
        # 2. تشغيل البوت الجديد (نستخدم دالة منفصلة لتجنب التعليق)
        from contact_bot import start_handler, handle_contact_message, contact_callback_handler
        
        async def run_new_bot():
            try:
                new_bot_app = ApplicationBuilder().token(bot_token).build()
                new_bot_app.bot_data["owner_id"] = int(user_id)
                new_bot_app.add_handler(CommandHandler("start", start_handler))
                new_bot_app.add_handler(CallbackQueryHandler(contact_callback_handler))
                new_bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_contact_message))
                new_bot_app.add_handler(MessageHandler(filters.PHOTO, handle_contact_message))
                
                await new_bot_app.initialize()
                await new_bot_app.start()
                await new_bot_app.updater.start_polling()
                print(f"🚀 المحرك يعمل الآن للبوت: {bot_name}")
            except Exception as e:
                print(f"⚠️ خطأ في تشغيل المحرك: {e}")

        # إطلاق المهمة في الخلفية فوراً دون انتظارها (Non-blocking)
        asyncio.create_task(run_new_bot())

        # 3. إرسال رسالة النجاح فوراً
        await msg.edit_text(
            f"🎉 **مبروك! تم إنشاء بوتك بنجاح**\n\n"
            f"📦 النوع: {bot_type}\n"
            f"📛 الاسم: {bot_name}\n"
            "🚀 البوت يعمل الآن، جربه الآن!",
            reply_markup=ReplyKeyboardMarkup(main_menu if user_id == ADMIN_ID else [["➕ إنشاء بوت"]], resize_keyboard=True)
        )
    else:
        await msg.edit_text("❌ حدث خطأ أثناء الحفظ. تأكد من إعدادات جوجل شيت.")

    context.user_data.clear()
    return ConversationHandler.END

# --------------------------------------------------------------------------
# --- لوحة التحكم والعمليات الإدارية ---

async def owner_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المطور (المالك)"""
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوتات", callback_data="stats_all")],
        [InlineKeyboardButton("📢 إذاعة للمشتركين", callback_data="broadcast_owners")],
        [InlineKeyboardButton("🔄 تحديث السيرفر", callback_data="restart_factory")]
    ]
    await update.message.reply_text(
        "🛠 **لوحة تحكم المطور**\nإدارة المصنع والعمليات المركزية:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية والأزرار الدائمة"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # زر العودة للقائمة الرئيسية
    if text == "🔙 العودة للقائمة الرئيسية":
        await start(update, context)
        return

    # الدخول للوحة التحكم (للمالك فقط)
    elif text == "🛠 لوحة التحكم (للمالك)" and user_id == ADMIN_ID:
        await update.message.reply_text(
            "مرحباً بك في غرفة القيادة 🕹️\nاختر القسم الذي تريد إدارته:", 
            reply_markup=ReplyKeyboardMarkup(admin_options, resize_keyboard=True)
        )
        await owner_dashboard(update, context)

    # تعديل النصوص (وظيفة للمالك)
    elif text == "📝 تعديل النصوص" and user_id == ADMIN_ID:
        await update.message.reply_text("أرسل ID البوت أو التوكن الذي تريد تعديل نصوصه:")
        context.user_data["admin_action"] = "edit_texts"

    # معالجة المدخلات الخاصة بالأدمن (تعديل المحتوى)
    elif context.user_data.get("admin_action") == "edit_texts" and user_id == ADMIN_ID:
        target_bot = text
        context.user_data["target_bot"] = target_bot
        keyboard = [
            [InlineKeyboardButton("الرسالة الترحيبية", callback_data="set_welcome")],
            [InlineKeyboardButton("القوانين", callback_data="set_rules")]
        ]
        await update.message.reply_text(
            f"ماذا تريد أن تعدل في سجلات البوت {target_bot}؟", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["admin_action"] = None

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ضغطات الأزرار الشفافة (Inline Buttons)"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "restart_factory":
        await query.edit_message_text("🔄 جاري إعادة تشغيل المصنع لتطبيق التحديثات...")
        # إعادة تشغيل البايثون فوراً
        os.execv(sys.executable, ['python'] + sys.argv)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة إلغاء عملية إنشاء البوت والعودة للقائمة الرئيسية"""
    user_id = update.effective_user.id
    # العودة للقائمة الرئيسية بناءً على هوية المستخدم
    current_menu = main_menu if user_id == ADMIN_ID else [["➕ إنشاء بوت"]]
    
    await update.message.reply_text(
        "❌ تم إلغاء عملية الإنشاء والعودة للقائمة الرئيسية.",
        reply_markup=ReplyKeyboardMarkup(current_menu, resize_keyboard=True)
    )
    # مسح البيانات المؤقتة
    context.user_data.clear()
    return ConversationHandler.END

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال ملفات البرمجة وتحديث الموديولات برمجياً"""
    if update.effective_user.id != ADMIN_ID: 
        return
        
    doc = update.message.document
    if doc.file_name.endswith(".py"):
        file = await doc.get_file()
        # التأكد من وجود مجلد الموديولات
        if not os.path.exists("modules"): 
            os.makedirs("modules")
            
        file_path = f"modules/{doc.file_name}"
        await file.download_to_drive(file_path)
        
        await update.message.reply_text(f"✅ تم تحديث موديول {doc.file_name} بنجاح!\n🔄 جاري إعادة التشغيل...")
        # إعادة التشغيل لتفعيل الموديول الجديد
        os.execv(sys.executable, ['python'] + sys.argv)

# --- بناء وتشغيل التطبيق ---

# إعداد الـ ConversationHandler لعملية إنشاء البوت
create_bot_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^➕ إنشاء بوت$'), start_create_bot)],
    states={
        CHOOSING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_type)],
        GETTING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
        GETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_bot)],
    },
    fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Regex('^🔙 العودة$'), cancel)],
)
# --------------------------------------------------------------------------
# --- دالة تشغيل البوتات المصنوعة تلقائياً ---
async def start_all_sub_bots():
    from sheets import get_all_active_bots
    from contact_bot import start_handler, handle_contact_message, contact_callback_handler
    
    active_bots = get_all_active_bots()
    print(f"🔄 جاري محاولة تشغيل {len(active_bots)} بوت مصنوع...")
    
    for bot_data in active_bots:
        token = bot_data.get("التوكن")
        owner_id = bot_data.get("ID المالك")
        try:
            # إنشاء تطبيق منفصل لكل توكن
            sub_app = ApplicationBuilder().token(token).build()
            sub_app.bot_data["owner_id"] = int(owner_id)
            
            # ربط موديول التواصل بالبوت الجديد
            sub_app.add_handler(CommandHandler("start", start_handler))
            sub_app.add_handler(CallbackQueryHandler(contact_callback_handler))
            sub_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_contact_message))
            
            # تشغيل البوت في الخلفية
            await sub_app.initialize()
            await sub_app.start()
            await sub_app.updater.start_polling()
            print(f"✅ تم تشغيل بوت التوكن: {token[:10]}...")
        except Exception as e:
            print(f"❌ فشل تشغيل بوت {token[:10]}: {e}")


# --------------------------------------------------------------------------
# بناء التطبيق
app = ApplicationBuilder().token(TOKEN).build()

# إضافة المعالجات (Handlers)
app.add_handler(CommandHandler("start", start))
app.add_handler(create_bot_conv)  # معالج محادثة الإنشاء
app.add_handler(CallbackQueryHandler(button_callback))  # معالج أزرار لوحة التحكم
app.add_handler(MessageHandler(filters.Document.FileExtension("py"), handle_docs))  # معالج ملفات البرمجة
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))  # معالج النصوص العام

# --------------------------------------------------------------------------

# تشغيل البوت بنظام Polling
if __name__ == "__main__":
    # تشغيل المصنع والبوتات القديمة معاً
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        # استدعاء الدالة التي تجلب البوتات "النشطة" وتشغلها عند بداية السيرفر
        loop.create_task(start_all_sub_bots()) 
        
        print("🚀 مصنع البوتات يعمل الآن بكافة محركاته...")
        app.run_polling()
    except Exception as e:
        print(f"🔴 خطأ في إقلاع المصنع: {e}")

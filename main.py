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
    ConversationHandler,
    ChatMemberHandler
)

# استيراد الدوال من ملف البرمجة الخاص بجوجل شيت (sheets.py)
from sheets import save_user, save_bot, update_content_setting, get_bot_config, add_log_entry, get_total_bots_count

# --- الإعدادات الأساسية ---
TOKEN = "8532487667:AAGYgoSw-S2G7ruf_To8LGGd5OGCfn_T6dw"
ADMIN_ID = 873158772  # معرف المطور والمالك

# تعريف مراحل محادثة إنشاء البوت (حالات الـ ConversationHandler)
CHOOSING_TYPE, GETTING_TOKEN, GETTING_NAME = range(3)

# --- القوائم الشفافة المحدثة (Inline Keyboards) ---
def get_main_menu_inline(user_id):
    keyboard = [[InlineKeyboardButton("➕ إنشاء بوت", callback_data="start_manufacture")]]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 لوحة التحكم (للمالك)", callback_data="open_admin_dashboard")])
    return InlineKeyboardMarkup(keyboard)

def get_types_menu_inline():
    keyboard = [
        [InlineKeyboardButton("📩 تواصل", callback_data="set_type_📩 تواصل")],
        [InlineKeyboardButton("🛡 حماية", callback_data="set_type_🛡 حماية")],
        [InlineKeyboardButton("🎓 منصة تعليمية", callback_data="set_type_🎓 منصة تعليمية")],
        [InlineKeyboardButton("🛒 متجر", callback_data="set_type_🛒 متجر")],
        [InlineKeyboardButton("🔙 إلغاء", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(keyboard)

# القوائم القديمة (للحفاظ على التوافق مع الوظائف التي قد تطلبها)
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
    """دالة الانطلاق، تسجيل المستخدم، وإشعار المطور بالعضو الجديد"""
    user = update.effective_user
    
    # استيراد الدالة المطلوبة من sheets
    from sheets import save_user, get_total_factory_users
    
    # محاولة حفظ المستخدم (الدالة تعيد True إذا كان المستخدم جديداً)
    is_new = save_user(user.id, user.username)
    
    # إذا كان المستخدم جديداً، أرسل إشعاراً للمطور (أنت)
    if is_new:
        total_factory_users = get_total_factory_users()
        factory_notif = (
            f"<b>تم دخول شخص جديد إلى المصنع الخاص بك</b> 👾\n"
            f"            -----------------------\n"
            f"• معلومات العضو الجديد .\n\n"
            f"• الاسم : {user.full_name}\n"
            f"• معرف : @{user.username if user.username else 'لا يوجد'}\n"
            f"• الايدي : <code>{user.id}</code>\n"
            f"            -----------------------\n"
            f"• عدد الأعضاء الكلي للمصنع : {total_factory_users}"
        )
        try:
            # إرسال الإشعار لك عبر بوت المصنع
            await context.bot.send_message(chat_id=ADMIN_ID, text=factory_notif, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ فشل إرسال إشعار العضو الجديد للمطور: {e}")

    # إظهار القائمة الرئيسية للمستخدم
    await update.message.reply_text(
        "✨ أهلاً بك في مصنع البوتات المتطور 🤖\n\n"
        "أنا بوت المصنع، يمكنني مساعدتك في إنشاء وإدارة بوتاتك الخاصة بسهولة وربطها بقاعدة بيانات جوجل.",
        reply_markup=get_main_menu_inline(user.id)
    )

# --- نظام إنشاء البوت (Conversation Flow) ---

async def start_create_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إنشاء بوت جديد وطلب اختيار النوع (عن طريق الأزرار الشفافة)"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🛠 **مرحباً بك في قسم التصنيع**\n\nاختر نوع البوت الذي تريد إنشاءه:",
            reply_markup=get_types_menu_inline()
        )
    else:
        await update.message.reply_text(
            "🛠 **مرحباً بك في قسم التصنيع**\n\nاختر نوع البوت الذي تريد إنشاءه:",
            reply_markup=get_types_menu_inline()
        )
    return CHOOSING_TYPE

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخزين النوع المختار وطلب التوكن"""
    query = update.callback_query
    await query.answer()
    
    # استخراج النوع من callback_data
    bot_type = query.data.replace("set_type_", "")
    context.user_data["type"] = bot_type
    
    await query.edit_message_text(
        f"✅ تم اختيار نوع: {bot_type}\n\n"
        "الآن، من فضلك أرسل **API Token** الخاص بالبوت.\n"
        "يمكنك الحصول عليه من @BotFather"
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
    # ملاحظة: تم الإبقاء على الوظيفة كما هي بناءً على النسخة السابقة مع تفعيل التجاوز التلقائي لاحقاً
    await finalize_bot(update, context)
    return ConversationHandler.END

# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
async def finalize_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ البيانات، فك تداخل التوكينات، وتشغيل الإشعارات الثلاثية بصيغ مميزة وتنسيق آمن"""
    bot_token = update.message.text.strip()
    user = update.effective_user
    user_id = user.id
    bot_type = context.user_data.get("type")
    
    if not re.match(r'^\d+:[A-Za-z0-9_-]{35,}$', bot_token):
        await update.message.reply_text("❌ التوكن غير صحيح! يرجى إرسال توكن صالح.")
        return GETTING_TOKEN

    msg = await update.message.reply_text("⏳ جاري تهيئة المحرك وفك تداخل التوكينات...")

    try:
        from telegram import Bot
        # إنشاء كائن بوت مستقل للتعامل مع التوكن الجديد
        temp_bot = Bot(bot_token)
        
        # حماية: إلغاء أي جلسات نشطة ومسح الرسائل العالقة لإنهاء مشكلة Conflict و Keyboard Expected
        await temp_bot.delete_webhook(drop_pending_updates=True)
        
        bot_info = await temp_bot.get_me()
        bot_username = f"@{bot_info.username}"
        bot_display_name = bot_type

        # حفظ البيانات في جوجل شيت
        from sheets import save_bot, get_total_bots_count
        success = save_bot(user_id, bot_type, bot_display_name, bot_token)

        if success:
            from contact_bot import start_handler, handle_contact_message, contact_callback_handler, track_chats

            async def run_new_bot():
                try:
                    # بناء تطبيق البوت الجديد بشكل منعزل
                    new_app = ApplicationBuilder().token(bot_token).build()
                    new_app.bot_data["owner_id"] = int(user_id)
                    
                    # ربط المعالجات (Handlers)
                    new_app.add_handler(CommandHandler("start", start_handler))
                    new_app.add_handler(CallbackQueryHandler(contact_callback_handler))
                    new_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_contact_message))
                    new_app.add_handler(MessageHandler(filters.PHOTO, handle_contact_message))
                    
                    # إضافة معالج تتبع الحظر وفك الحظر
                    new_app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
                    
                    await new_app.initialize()
                    await new_app.start()
                    # البدء بصفحة بيضاء تماماً
                    await new_app.updater.start_polling(drop_pending_updates=True)
                except Exception as e:
                    print(f"⚠️ خطأ في تشغيل محرك البوت الجديد: {e}")

            # إطلاق مهمة التشغيل في الخلفية
            asyncio.create_task(run_new_bot())

            # --- [الرسالة الأولى: إشعار النجاح للمستخدم في المصنع] ---
            user_success_text = (
                f"<b>🎊 تمت العملية بنجاح!</b>\n\n"
                f"لقد انتهينا من برمجة بوتك الجديد وإطلاقه في الفضاء الرقمي.\n\n"
                f"📦 <b>نوع الموديول:</b> {bot_type}\n"
                f"🤖 <b>يوزر البوت:</b> {bot_username}\n\n"
                f"🚀 البوت الآن في وضع التشغيل، يمكنك التوجه إليه والبدء باستخدامه فوراً!"
            )
            await msg.edit_text(
                text=user_success_text,
                reply_markup=get_main_menu_inline(user_id),
                parse_mode="HTML"
            )

            # --- [الرسالة الثانية: إشعار التهنئة داخل البوت الجديد] ---
            factory_info = await context.bot.get_me()
            congrats_text = (
                f"<b>🎈 أهلاً بك في عالمك الخاص!</b>\n\n"
                f"لقد تم ربط هذا البوت بنجاح بمصنع البوتات وقاعدة بيانات جوجل.\n\n"
                f"📋 <b>الوظيفة الأساسية:</b> {bot_type}\n"
                f"⚙️ <b>الحالة:</b> مرتبط وجاهز للعمل\n"
                f"-----------------------\n"
                f"تم الإنشاء بواسطة: @{factory_info.username}"
            )
            try:
                await temp_bot.send_message(chat_id=user_id, text=congrats_text, parse_mode="HTML")
            except: pass

            # --- [الرسالة الثالثة: إشعار تفصيلي لك (المطور)] ---
            total_bots = get_total_bots_count()
            admin_notification = (
                f"<b>🔔 إشعار تصنيع جديد</b>\n"
                f"-----------------------\n"
                f"👤 <b>المنشئ:</b> {user.full_name}\n"
                f"🔗 <b>يوزر المالك:</b> @{user.username if user.username else 'لا يوجد'}\n"
                f"🆔 <b>آيدي المالك:</b> <code>{user_id}</code>\n"
                f"-----------------------\n"
                f"🤖 <b>نوع البوت:</b> {bot_type}\n"
                f"🎈 <b>يوزر البوت:</b> {bot_username}\n"
                f"-----------------------\n\n"
                f"📈 <b>إجمالي إنتاج المصنع:</b> {total_bots} بوت"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode="HTML")

        else:
            await msg.edit_text("❌ حدث خطأ أثناء الحفظ في جوجل شيت.")

    except Exception as e:
        print(f"❌ Error in finalize: {e}")
        await msg.edit_text(f"⚠️ <b>تنبيه تقني:</b>\nحدث تداخل بسيط أثناء التهيئة، لكن البوت {bot_username} قد يكون جاهزاً. يرجى التحقق منه.", parse_mode="HTML")

    context.user_data.clear()
    return ConversationHandler.END

# --------------------------------------------------------------------------
# --- لوحة التحكم والعمليات الإدارية ---

async def owner_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المطور (المالك) - متوافقة مع الأزرار الشفافة"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوتات", callback_data="stats_all")],
        [InlineKeyboardButton("📢 إذاعة للمشتركين", callback_data="broadcast_owners")],
        [InlineKeyboardButton("🔄 تحديث السيرفر", callback_data="restart_factory")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_to_main")]
    ]
    
    text = "🛠 **لوحة تحكم المطور**\nإدارة المصنع والعمليات المركزية:"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية والأزرار الدائمة"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "🔙 العودة للقائمة الرئيسية":
        await start(update, context)
        return

    elif text == "🛠 لوحة التحكم (للمالك)" and user_id == ADMIN_ID:
        await owner_dashboard(update, context)

    elif text == "➕ إنشاء بوت":
        await start_create_bot(update, context)

    elif text == "📝 تعديل النصوص" and user_id == ADMIN_ID:
        await update.message.reply_text("أرسل ID البوت أو التوكن الذي تريد تعديل نصوصه:")
        context.user_data["admin_action"] = "edit_texts"

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
    """معالجة ضغطات الأزرار الشفافة المركزية"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data == "restart_factory":
        await query.answer("🔄 جاري إعادة التشغيل...")
        await query.edit_message_text("🔄 جاري إعادة تشغيل المصنع لتطبيق التحديثات...")
        os.execv(sys.executable, ['python'] + sys.argv)
        
    elif data == "open_admin_panel":
        await owner_dashboard(update, context)
        
    elif data == "back_to_main":
        await query.answer()
        await query.edit_message_text(
            "✨ أهلاً بك في مصنع البوتات المتطور 🤖\n\nاختر ما تريد القيام به:",
            reply_markup=get_main_menu_inline(user_id)
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة إلغاء عملية إنشاء البوت والعودة للقائمة الرئيسية"""
    user_id = update.effective_user.id
    text = "❌ تم إلغاء عملية الإنشاء والعودة للقائمة الرئيسية."
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=get_main_menu_inline(user_id))
    else:
        await update.message.reply_text(text, reply_markup=get_main_menu_inline(user_id))
        
    context.user_data.clear()
    return ConversationHandler.END

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال ملفات البرمجة وتحديث الموديولات برمجياً"""
    if update.effective_user.id != ADMIN_ID: 
        return
        
    doc = update.message.document
    if doc.file_name.endswith(".py"):
        file = await doc.get_file()
        if not os.path.exists("modules"): 
            os.makedirs("modules")
            
        file_path = f"modules/{doc.file_name}"
        await file.download_to_drive(file_path)
        
        await update.message.reply_text(f"✅ تم تحديث موديول {doc.file_name} بنجاح!\n🔄 جاري إعادة التشغيل...")
        os.execv(sys.executable, ['python'] + sys.argv)

# إعداد الـ ConversationHandler لإنشاء البوت
create_bot_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex('^➕ إنشاء بوت$'), start_create_bot),
        CallbackQueryHandler(start_create_bot, pattern="^start_manufacture$")
    ],
    states={
        CHOOSING_TYPE: [CallbackQueryHandler(select_type, pattern="^set_type_")],
        GETTING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_bot)],
    },
    fallbacks=[
        CommandHandler('cancel', cancel), 
        CallbackQueryHandler(cancel, pattern="^cancel_action$"),
        MessageHandler(filters.Regex('^🔙 العودة$'), cancel)
    ],
)

# --- دالة تشغيل البوتات المصنوعة تلقائياً ---
async def start_all_sub_bots():
    from sheets import get_all_active_bots
    from contact_bot import start_handler, handle_contact_message, contact_callback_handler, track_chats
    
    active_bots = get_all_active_bots()
    print(f"🔄 جاري محاولة تشغيل {len(active_bots)} بوت مصنوع...")
    
    for bot_data in active_bots:
        token = bot_data.get("التوكن")
        owner_id = bot_data.get("ID المالك")
        try:
            sub_app = ApplicationBuilder().token(token).build()
            sub_app.bot_data["owner_id"] = int(owner_id)
            
            sub_app.add_handler(CommandHandler("start", start_handler))
            sub_app.add_handler(CallbackQueryHandler(contact_callback_handler))
            sub_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_contact_message))
            
            # إضافة معالج تتبع الحظر للبوتات القديمة أيضاً
            sub_app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
            
            await sub_app.initialize()
            await sub_app.start()
            await sub_app.updater.start_polling()
            print(f"✅ تم تشغيل بوت التوكن: {token[:10]}...")
        except Exception as e:
            print(f"❌ فشل تشغيل بوت {token[:10]}: {e}")

# بناء التطبيق
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(create_bot_conv) 
app.add_handler(CallbackQueryHandler(button_callback))
app.add_handler(MessageHandler(filters.Document.FileExtension("py"), handle_docs))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

if __name__ == "__main__":
    import asyncio
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.create_task(start_all_sub_bots()) 
        print("🚀 مصنع البوتات يعمل الآن بكافة محركاته...")
        app.run_polling()
    except Exception as e:
        print(f"🔴 خطأ في إقلاع المصنع: {e}")

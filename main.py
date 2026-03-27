import os
import sys
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from sheets import save_user, save_bot, update_content_setting, get_bot_config # تأكد من وجود هذه الدوال في sheets.py

# إعدادات البوت والتحقق
TOKEN = "8532487667:AAGeWhNyLZri9BxZMCw3AQZaJmOI5OVdxkE"
ADMIN_ID = 873158772 # معرفك الخاص

# القوائم
main_menu = [["➕ إنشاء بوت"], ["🛠 لوحة التحكم (للمالك)"]]
admin_options = [["📝 تعديل النصوص", "⚙️ إعدادات الموديولات"], ["🔙 العودة للقائمة الرئيسية"]]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username)
    
    # إظهار زر لوحة التحكم فقط للمالك
    current_menu = main_menu if user.id == ADMIN_ID else [["➕ إنشاء بوت"]]
    
    await update.message.reply_text(
        "أهلاً بك في مصنع البوتات المتطور 🤖",
        reply_markup=ReplyKeyboardMarkup(current_menu, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    # أضف هذا الجزء لملف main.py تحت handle_message

async def owner_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم خاصة بك أنت (المطور والمالك للمصنع)"""
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوتات", callback_data="stats_all")],
        [InlineKeyboardButton("📢 إذاعة للمشتركين", callback_data="broadcast_owners")],
        [InlineKeyboardButton("🔄 تحديث السيرفر", callback_data="restart_factory")]
    ]
    await update.message.reply_text("🛠 **لوحة تحكم المطور**\nإدارة المصنع والمشتركين:", 
                                   reply_markup=InlineKeyboardMarkup(keyboard))

# معالجة الضغط على الأزرار في لوحة التحكم
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "restart_factory":
        await query.edit_message_text("🔄 جاري إعادة تشغيل المصنع لتطبيق التحديثات...")
        os.execv(sys.executable, ['python'] + sys.argv)

    
    
    
    # --- قسم المستخدم العادي ---
    if text == "➕ إنشاء بوت":
        keyboard = [["📩 تواصل"], ["🛡 حماية"], ["🎓 منصة تعليمية"], ["🛒 متجر"]]
        await update.message.reply_text("اختر نوع البوت:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    
    elif text in ["📩 تواصل", "🛡 حماية", "🎓 منصة تعليمية", "🛒 متجر"]:
        context.user_data["type"] = text
        await update.message.reply_text("أرسل اسم البوت:")

    # --- قسم لوحة تحكم المالك ---
    elif text == "🛠 لوحة التحكم (للمالك)" and user_id == ADMIN_ID:
        await update.message.reply_text("مرحباً بك في غرفة القيادة 🕹️\nاختر القسم الذي تريد إدارته:", 
                                       reply_markup=ReplyKeyboardMarkup(admin_options, resize_keyboard=True))

    elif text == "📝 تعديل النصوص" and user_id == ADMIN_ID:
        await update.message.reply_text("أرسل ID البوت الذي تريد تعديل نصوصه (ترحيب/قوانين):")
        context.user_data["admin_action"] = "edit_texts"

    elif text == "🔙 العودة للقائمة الرئيسية":
        await start(update, context)

    # معالجة إنشاء البوت أو إدخالات الأدمن
    else:
        # إذا كان الأدمن يريد تعديل نص
        if context.user_data.get("admin_action") == "edit_texts":
            bot_id_to_edit = text
            context.user_data["target_bot"] = bot_id_to_edit
            keyboard = [[InlineKeyboardButton("الرسالة الترحيبية", callback_data="set_welcome"),
                         InlineKeyboardButton("القوانين", callback_data="set_rules")]]
            await update.message.reply_text(f"ماذا تريد أن تعدل في البوت {bot_id_to_edit}؟", 
                                           reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["admin_action"] = None
            
        # كود إنشاء البوت الأصلي (لا يحذف)
        else:
            bot_type = context.user_data.get("type")
            if bot_type:
                save_bot(user_id, bot_type, text)
                await update.message.reply_text(f"✅ تم إنشاء بوت ({bot_type}) باسم: {text}")
                context.user_data.clear()

# معالج الملفات (المحرك القوي للتحديث)
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    doc = update.message.document
    if doc.file_name.endswith(".py"):
        file = await doc.get_file()
        if not os.path.exists("modules"): os.makedirs("modules")
        await file.download_to_drive(f"modules/{doc.file_name}")
        await update.message.reply_text(f"✅ تم تحديث موديول {doc.file_name} بنجاح!")
        os.execv(sys.executable, ['python'] + sys.argv)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Document.FileExtension("py"), handle_docs))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.run_polling()

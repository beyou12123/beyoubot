
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sheets import get_bot_config, add_log_entry

# إعداد التنبيهات لمراقبة الأداء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرسالة الترحيبية عند دخول أي مستخدم لبوت التواصل الخاص بالمشترك"""
    bot_id = context.bot.id
    config = get_bot_config(bot_id)
    
    # جلب الترحيب من الشيت أو نص افتراضي
    welcome_text = config.get("الرسالة الترحيبية", "مرحباً بك في بوت التواصل الخاص بنا. أرسل رسالتك وسنرد عليك قريباً.")
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توجيه الرسائل من المستخدمين إلى صاحب البوت (المشترك)"""
    user = update.effective_user
    bot_owner_id = context.bot_data.get("owner_id") # يتم تعيينه عند تشغيل البوت من المصنع
    bot_id = context.bot.id

    # إذا كان المرسل هو "صاحب البوت" (يريد الرد على شخص)
    if user.id == bot_owner_id:
        if update.message.reply_to_message:
            try:
                # استخراج ID المستخدم المستهدف من الرسالة الموجهة
                # ملاحظة: نعتمد هنا على أن الرسالة الموجهة تحتوي على الـ ID في الوصف
                target_text = update.message.reply_to_message.text or update.message.reply_to_message.caption
                target_user_id = target_text.split("ID:")[1].split("\n")[0].strip()
                
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💬 **رد من الإدارة:**\n\n{update.message.text}"
                )
                await update.message.reply_text("✅ تم إرسال ردك للمستخدم.")
            except Exception as e:
                await update.message.reply_text("❌ يرجى الرد مباشرة على رسالة المستخدم الموجهة إليك.")
        else:
            await update.message.reply_text("💡 للرد على مستخدم، قم بعمل Reply على رسالته التي وصلت إليك.")

    # إذا كان المرسل مستخدم عادي (يريد مراسلة صاحب البوت)
    else:
        # توجيه الرسالة لصاحب البوت
        await context.bot.send_message(
            chat_id=bot_owner_id,
            text=f"📩 **رسالة جديدة**\nمن: {user.mention_markdown_v2()}\nID: `{user.id}`\n\n{update.message.text if update.message.text else '[محتوى وسائط]'}",
            parse_mode="MarkdownV2"
        )
        # تأكيد الاستلام للمستخدم
        await update.message.reply_text("✅ تم إرسال رسالتك بنجاح، انتظر الرد.")
        
        # تسجيل العملية في قاعدة البيانات
        add_log_entry(bot_id, "CONTACT_MSG", f"From {user.id} to Owner {bot_owner_id}")

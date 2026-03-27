
import re
from telegram import Update
from telegram.ext import ContextTypes
from sheets import get_bot_config, add_log_entry

async def protect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المحرك المسؤول عن فحص الرسائل وحماية المجموعة"""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    bot_id = context.bot.id
    chat_id = update.effective_chat.id
    text = update.message.text
    
    # 1. جلب إعدادات الحماية من Google Sheets
    config = get_bot_config(bot_id)
    # جلب الكلمات المحظورة وتحويلها لقائمة (مخزنة في الشيت مفصولة بفاصلة)
    banned_words = config.get("banned_words", "").split(",")
    admin_ids = config.get("admin_ids", "").split(",")
    
    # 2. استثناء المطور (أنت) وصاحب البوت من الفحص
    if str(user.id) in admin_ids or str(user.id) == str(context.bot_data.get("owner_id")):
        return

    # 3. فحص المحتوى (الكلمات المحظورة)
    for word in banned_words:
        word = word.strip()
        if word and re.search(rf"\b{word}\b", text, re.IGNORECASE):
            # إجراء الحماية: حذف الرسالة
            try:
                await update.message.delete()
                # إرسال تحذير للمستخدم
                warn_msg = await update.message.reply_text(f"⚠️ عذراً {user.first_name}، رسالتك تحتوي على كلمات غير مسموح بها.")
                
                # تسجيل المخالفة في شيت السجلات
                add_log_entry(bot_id, "PROTECTION_VIOLATION", f"User {user.id} sent banned word: {word}")
                
                # اختياري: كتم المستخدم لمدة ساعة إذا تكرر الأمر (يمكن تطويرها)
            except Exception as e:
                print(f"Error in protection: {e}")
            break

async def auto_kick_spammers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منطق إضافي لحظر الروابط أو التكرار المزعج"""
    # يمكن إضافة فحص الروابط (Regex) هنا بنفس الطريقة
    pass

import os
import re
import asyncio
import yt_dlp
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sheets import add_log_entry, get_bot_config

# مجلد مؤقت للتحميلات (سيتم تنظيفه آلياً)
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# --- [ الدوال المساعدة ] ---

async def get_video_info(url):
    """استخراج معلومات الفيديو باستخدام yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return await asyncio.to_thread(ydl.extract_info, url, download=False)
    except Exception as e:
        print(f"Error fetching info: {e}")
        return None

# --- [ معالجات البوت (Handlers) ] ---

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الترحيب وتعليمات الاستخدام"""
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    welcome_msg = config.get("الرسالة الترحيبية", "🚀 أهلاً بك في بوت التحميل الشامل!\n\nأرسل رابط الفيديو من (يوتيوب، تيك توك، إنستغرام، فيسبوك) وسأقوم بجلب خيارات التحميل لك فوراً.")
    await update.message.reply_text(welcome_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المحرك الرئيسي للتعامل مع الروابط"""
    url = update.message.text.strip()
    if not re.match(r'http[s]?://', url):
        return

    msg = await update.message.reply_text("🔍 جاري فحص الرابط واستخراج الجودات المتاحة...")
    
    info = await get_video_info(url)
    if not info:
        await msg.edit_text("❌ عذراً، تعذر الوصول لمحتوى هذا الرابط. تأكد أنه عام وليس خاصاً.")
        return

    title = info.get('title', 'فيديو بدون عنوان')
    duration = info.get('duration_string', 'غير محدد')
    uploader = info.get('uploader', 'غير معروف')
    
    text = (
        f"✅ <b>تم العثور على الفيديو!</b>\n\n"
        f"📝 <b>العنوان:</b> {title}\n"
        f"👤 <b>الناشر:</b> {uploader}\n"
        f"⏱ <b>المدة:</b> {duration}\n\n"
        f"اختر صيغة التحميل المطلوبة أدناه:"
    )

    keyboard = []
    # تخصيص الأزرار بناءً على المنصة
    if 'tiktok.com' in url:
        keyboard.append([InlineKeyboardButton("🎬 فيديو (بدون علامة مائية)", callback_data=f"dl_tt_no_wm|{url}")])
    else:
        keyboard.append([InlineKeyboardButton("🎬 فيديو (أعلى جودة)", callback_data=f"dl_best_v|{url}")])
    
    keyboard.append([InlineKeyboardButton("🎵 صوت فقط (MP3)", callback_data=f"dl_audio|{url}")])

    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ عملية التحميل والإرسال"""
    query = update.callback_query
    data = query.data
    action, url = data.split('|', 1)
    
    await query.answer("⏳ بدأت عملية المعالجة.. يرجى الانتظار")
    status_msg = await query.message.reply_text("📥 جاري التحميل من السيرفر الأصلي...")

    # توليد اسم ملف فريد
    file_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    # إعدادات التحميل بناءً على الاختيار
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
    }

    if action == "dl_audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    elif action == "dl_tt_no_wm":
        ydl_opts.update({'format': 'bestvideo+bestaudio/best'})
    else:
        ydl_opts.update({'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})

    try:
        # عملية التحميل الفعلي
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename = ydl.prepare_filename(info)
            if action == "dl_audio":
                filename = filename.rsplit('.', 1)[0] + ".mp3"

        await status_msg.edit_text("📤 جاري الرفع إلى تليجرام...")
        
        # إرسال الملف بناءً على نوعه
        with open(filename, 'rb') as f:
            if action == "dl_audio":
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f, title=info.get('title'))
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=f, caption=f"✅ {info.get('title')}\n\nتم التحميل بواسطة بوت المصنع.")

        await status_msg.delete()
        add_log_entry(context.bot.token, "DOWNLOAD_SUCCESS", f"Type: {action}")

    except Exception as e:
        await status_msg.edit_text(f"❌ فشلت العملية: {str(e)}")
    
    finally:
        # الحذف الفوري للملف من السيرفر للحفاظ على المساحة
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)


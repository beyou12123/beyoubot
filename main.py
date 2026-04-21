import os
import sys
import re
import asyncio
import time
import importlib # استيراد الموديولات ديناميكياً لتشغيل الملفات المرفوعة

# استيراد الأدوات الأساسية من مكتبة تليجرام
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardRemove,
    Bot
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

# استيراد الدوال من ملف البرمجة الخاص بقاعدة البيانات(sheets.py)
from sheets import (
    save_user, 
    save_bot, 
    update_content_setting, 
    get_bot_config, 
    add_log_entry, 
    get_total_bots_count,
    get_total_factory_users,
    get_all_active_bots,
    setup_bot_factory_database, # أضف هذه أيضاً لأنها المحرك الرئيسي
    ensure_sheet_schema,
    reset_entire_database, 
    ensure_all_sheets_schema
)


# --- الإعدادات الأساسية ---
TOKEN = "1657415602:AAFZzxVc9ECvdJ5WwmzVyM219ilLhjUDgLM"
ADMIN_ID = 873158772  # معرف المطور والمالك

# تعريف مراحل محادثة إنشاء البوت (حالات الـ ConversationHandler)
CHOOSING_TYPE, GETTING_TOKEN, GETTING_NAME = range(3)
# تعريف حالة انتظار اسم الموديول الجديد (خاصة بالمطور)
WAITING_FOR_MODULE_NAME = 4

# --- القوائم الشفافة المحدثة (Inline Keyboards) ---
def get_main_menu_inline(user_id):
    keyboard = [[InlineKeyboardButton("➕ إنشاء بوت", callback_data="start_manufacture")]]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 لوحة التحكم (للمالك)", callback_data="open_admin_dashboard")])
    return InlineKeyboardMarkup(keyboard)
# --------------------------------------------------------------------------
def get_types_menu_inline(user_id):
    hidden_dev_files = ['test_lab.py']
 
    keyboard = [
        [InlineKeyboardButton("📩 تواصل", callback_data="set_type_contact_bot"),
         InlineKeyboardButton("🛡 حماية", callback_data="set_type_protection_bot")],
        [InlineKeyboardButton("🎓 منصة تعليمية", callback_data="set_type_education_bot"),
         InlineKeyboardButton("🛒 متجر", callback_data="set_type_store_bot")]
    ]
    
    # استيراد ورقة الميتا لجلب الأوصاف
    from sheets import meta_sheet
    descriptions = {}
    try:
        if meta_sheet:
            records = meta_sheet.get_all_records()
            descriptions = {r['key']: r['value'] for r in records if str(r['key']).startswith('desc_')}
    except: pass

    exclude_files = ['main.py', 'sheets.py','downloader_bot', 'ai_bot', 'transcriber_bot', 'cache_manager.py', 'contact_bot.py', 'education_bot.py', 'protection_bot.py', 'store_bot.py', 'config.py', 'runner.py', 'course_engine.py', 'educational_manager.py']
    
    dynamic_buttons = []
    for file in os.listdir('.'):
        if file.endswith('.py') and file not in exclude_files:
            if file in hidden_dev_files and user_id != ADMIN_ID:
                continue
        	
            module_name = file[:-3]
            # جلب الاسم الوصفي من الشيت، وإذا لم يوجد نستخدم اسم الملف كبديل
            display_name = descriptions.get(f"desc_{file}", module_name)
            dynamic_buttons.append(InlineKeyboardButton(f"🤖 {display_name}", callback_data=f"set_type_{module_name}"))
    
    for i in range(0, len(dynamic_buttons), 2):
        keyboard.append(dynamic_buttons[i:i + 2])
    
    keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="cancel_action")])
    return InlineKeyboardMarkup(keyboard)


# --------------------------------------------------------------------------

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
        "أنا بوت المصنع، يمكنني مساعدتك في إنشاء وإدارة بوتاتك الخاصة بسهولة وربطها بقاعدة قاعدة البيانات.",parse_mode="HTML", 
        reply_markup=get_main_menu_inline(user.id)
    )

# --- نظام إنشاء البوت (Conversation Flow) ---
async def start_create_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إنشاء بوت جديد وطلب اختيار النوع (عن طريق الأزرار الشفافة)"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🛠 **مرحباً بك في قسم التصنيع**\n\nاختر نوع البوت الذي تريد إنشاءه:",parse_mode="HTML", 
            reply_markup=get_types_menu_inline(query.from_user.id)
        )
    else:
        await update.message.reply_text(
            "🛠 **مرحباً بك في قسم التصنيع**\n\nاختر نوع البوت الذي تريد إنشاءه:",parse_mode="HTML", 
            reply_markup=get_types_menu_inline(update.effective_user.id)
        )
    return CHOOSING_TYPE

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخزين النوع المختار وطلب التوكن"""
    query = update.callback_query
    await query.answer()
    
    # استخراج النوع من callback_data
    bot_type = query.data.replace("set_type_", "")
    context.user_data["type"] = bot_type
    
    # استخراج الاسم العربي من الأزرار ديناميكياً لضمان الدقة
    friendly_name = "غير معروف"
    for row in query.message.reply_markup.inline_keyboard:
        for button in row:
            if button.callback_data == query.data:
                friendly_name = button.text
                break
    
    # تخزين الاسم العربي في الذاكرة المؤقتة لاستخدامه في finalize_bot
    context.user_data["bot_friendly_name"] = friendly_name
    
    # إرسال الرسالة المنسقة للمستخدم بالاسم العربي
    await query.edit_message_text(
        text=f"✅ تم اختيار نوع: <b>{friendly_name}</b>\n\n"
             "الآن، من فضلك أرسل <b>API Token</b> الخاص بالبوت.\n"
             "يمكنك الحصول عليه من @BotFather",
        parse_mode="HTML"
    )

    return GETTING_TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    if not re.match(r'^\d+:[A-Za-z0-9_-]{35,}$', token):
        await update.message.reply_text("❌ التوكن غير صحيح!")
        return GETTING_TOKEN
    
    context.user_data["bot_token"] = token
    bot_type = context.user_data.get("type", "")

    # 1. محاولة جلب الاسم العربي المخزن سابقاً من الذاكرة (الأولوية القصوى)
    friendly_name = context.user_data.get("bot_friendly_name")

    # 2. إذا لم يوجد الاسم في الذاكرة (فقط وحصراً)، نبحث عنه في الميتا
    if not friendly_name:
        try:
            from sheets import meta_sheet
            records = meta_sheet.get_all_records()
            for r in records:
                if str(r.get('key')) == f"desc_{bot_type.strip()}.py":
                    friendly_name = r.get('value')
                    break
        except: 
            pass

    # 3. إذا لم يوجد في الذاكرة ولا في الميتا، نستخدم النوع التقني كخيار أخير
    if not friendly_name:
        friendly_name = bot_type

    # تخزين الاسم النهائي في الذاكرة لضمان وصوله إلى finalize_bot بشكل صحيح
    context.user_data["bot_friendly_name"] = friendly_name
    
    await finalize_bot(update, context)
    return ConversationHandler.END

# --------------------------------------------------------------------------
# --- المحرك الديناميكي الأوتوماتيكي المطور ---
# --------------------------------------------------------------------------

async def run_dynamic_bot(bot_token, bot_type, user_id):
    """الحل الجذري: ربط الاسم الوصفي بالملف البرمجي وتشغيل المحرك"""
    try:
        from sheets import meta_sheet
        import importlib
        
        # 1. تحديد اسم الملف البرمجي الحقيقي (Mapping)
        module_file_name = None
        
        # البحث في قاعدة البيانات (الميتا) عن اسم الملف المرتبط بهذا النوع
        try:
            if meta_sheet:
                records = meta_sheet.get_all_records()
                # نبحث عن السطر الذي يحتوي على الاسم الوصفي في العمود الثاني
                for r in records:
                    if str(r.get('key')) == f"desc_{bot_type.strip()}.py":
                        # نأخذ اسم الملف من الـ key (نزيل منه desc_)
                        module_file_name = str(r.get('key')).replace('desc_', '').replace('.py', '')
                        break
        except Exception as e:
            print(f"⚠️ خطأ أثناء فحص الميتا: {e}")

        # إذا لم يجد في الميتا، نستخدم التحويلات اليدوية كخطة بديلة
        if not module_file_name:
            if "تواصل" in bot_type: module_file_name = "contact_bot"
            elif "حماية" in bot_type: module_file_name = "protection_bot"
            elif "تعليمية" in bot_type: module_file_name = "education_bot"
            elif "متجر" in bot_type: module_file_name = "store_bot"
            else: module_file_name = bot_type.strip() # آخر محاولة

        # 2. استيراد الموديول برمجياً
        print(f"📦 محاولة تحميل الملف: {module_file_name}.py للنوع: {bot_type}")
        module = importlib.import_module(module_file_name)
        importlib.reload(module) 

        # 3. بناء تطبيق البوت وتجهيزه
        new_app = ApplicationBuilder().token(bot_token).build()
        new_app.bot_data["owner_id"] = int(user_id)

        # 4. ربط المعالجات (Handlers) - الترتيب هنا هو سر النجاح
        
        # أ: معالج /start
        if hasattr(module, 'start_handler'):
            new_app.add_handler(CommandHandler("start", module.start_handler))
        
        # ب: معالج الأزرار (Callback)
        if hasattr(module, 'callback_handler'):
            new_app.add_handler(CallbackQueryHandler(module.callback_handler))
        elif hasattr(module, 'contact_callback_handler'):
            new_app.add_handler(CallbackQueryHandler(module.contact_callback_handler))

        # ج: الحل الجذري للرسائل (توجيه شامل للموديول)
        # نضع filters.ALL لضمان أن الموديول هو من يتحكم بكل شيء (نصوص، صور، الخ)
        main_filter = filters.ALL & (~filters.COMMAND)
        
        if hasattr(module, 'handle_message'):
            # هذا السطر هو الذي سيشغل موديول الذكاء الاصطناعي
            new_app.add_handler(MessageHandler(main_filter, module.handle_message))
        elif hasattr(module, 'handle_contact_message'):
            # هذا لبوت التواصل
            new_app.add_handler(MessageHandler(main_filter, module.handle_contact_message))

        # د: معالج الحظر
        if hasattr(module, 'track_chats'):
            new_app.add_handler(ChatMemberHandler(module.track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

        # 5. تشغيل البوت
        await new_app.initialize()
        await new_app.start()
        await new_app.updater.start_polling(drop_pending_updates=True)
        print(f"🚀 [نجاح]: البوت بنوع [{bot_type}] يعمل الآن عبر ملف [{module_file_name}.py]")

    except ModuleNotFoundError:
        print(f"❌ [خطأ]: تعذر العثور على ملف باسم {module_file_name}.py")
    except Exception as e:
        print(f"⚠️ [خطأ]: في تشغيل البot الديناميكي: {e}")


# --------------------------------------------------------------------------
async def finalize_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ البيانات، تشغيل المحرك، وإرسال إشعارات النجاح بكافة اللغات والمسميات"""
    

    # 1. جلب البيانات من الذاكرة المؤقتة
    # friendly_type_name: هو الاسم العربي الذي تم التقاطه من الزر (مثل: 🛡 حماية)
    friendly_name = context.user_data.get("bot_friendly_name", "بوت مخصص")

    user = update.effective_user
    user_id = user.id
    bot_type = context.user_data.get("type") 
    bot_token = context.user_data.get("bot_token")

    msg = await update.message.reply_text("⏳ جاري تهيئة المحرك ...")

    try:
        from telegram import Bot
        temp_bot = Bot(bot_token)
        
        await temp_bot.delete_webhook(drop_pending_updates=True)
        
        bot_info = await temp_bot.get_me()
        bot_username = f"@{bot_info.username}"

        from sheets import save_bot, get_total_bots_count
        success = save_bot(user_id, bot_type, friendly_name, bot_token)

        if success:
            #from main--import run_dynamic_bot 
            asyncio.create_task(run_dynamic_bot(bot_token, bot_type, user_id))

            # --- [ الرسالة الأولى: في بوت المصنع ] ---
            user_success_text = (
                f"<b>🎊 تمت العملية بنجاح!</b>\n\n"
                f"لقد انتهينا من برمجة بوتك الجديد وإطلاقه.\n\n"
                f"📛 <b>الاسم المخصص:</b> {friendly_name}\n"
                f"🤖 <b>يوزر البوت:</b> {bot_username}\n\n"
                f"🚀 البوت الآن جاهز للعمل!"
            )
            # تم إضافة استيراد get_main_menu_inline لضمان عدم حدوث خطأ
            #from main--import get_main_menu_inline
            await msg.edit_text(text=user_success_text, reply_markup=get_main_menu_inline(user_id), parse_mode="HTML")

            # --- [ الرسالة الثانية: داخل البوت الجديد ] ---
            factory_info = await context.bot.get_me()
            congrats_text = (
                f"<b>🎈 أهلاً بك في عالمك الخاص!</b>\n\n"
                f"لقد تم ربط هذا البوت بنجاح بمصنع البوتات وقاعدة البيانات.\n\n"
                f"📛 <b>الاسم:</b> {friendly_name}\n"
                f"⚙️ <b>الحالة:</b> مرتبط وجاهز للعمل\n"
                f"-----------------------\n"
                f"تم الإنشاء بواسطة: @{factory_info.username}"
            )
            try:
                await temp_bot.send_message(chat_id=user_id, text=congrats_text, parse_mode="HTML")
                
                # إرسال الدليل فقط إذا كان النوع منصة تعليمية
                if bot_type == "education_bot":
                    # تصحيح: استخدام النص المعرف مباشرة أو استيراده بشكل صحيح
                    setup_guide_text = (
                        "🚀 <b>الدليل الشامل لتهيئة منصتك التعليمية</b>\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "مرحباً بك يا دكتور! لضمان عمل المنصة بكفاءة واستقرار، يرجى اتباع الخطوات التالية بالترتيب الموصى به:\n\n"
                        "1️⃣ <b>تنشيط نبض النظام (المزامنة):</b>\n"
                        "بدايةً، قم بالضغط على زر <b>(🛠 الإعدادات العامة وتجهيز النظام)</b>، ثم <b>(🔄 المزامنة)</b>.\n\n"
                        "2️⃣ <b>ضبط الهوية الذكية (AI):</b>\n"
                        "انتقل إلى <b>(🤖 ضبط الـ AI)</b> لتعريف اسم منشأتك ووضع التعليمات.\n\n"
                        "3️⃣ <b>تأسيس الفروع الإدارية:</b>\n"
                        "توجه إلى <b>(إدارة الفروع)</b> وأنشئ فرعك الأول.\n\n"
                        "4️⃣ <b>بناء الكادر التعليمي والإداري:</b>\n"
                        "من قسم <b>(تكويد الكادر)</b>، قم بتوليد روابط انضمام.\n\n"
                        "5️⃣ <b>هيكلة المحتوى التعليمي:</b>\n"
                        "• أضف <b>(📁 الأقسام)</b> أولاً ثم <b>(📚 الدورات)</b>.\n\n"
                        "6️⃣ <b>تفعيل القنوات الرسمية:</b>\n"
                        "من <b>(تجهيز قاعدة البيانات)</b>، قم بربط آيدي القنوات.\n\n"
                        "7️⃣ <b>الضبط المالي ونقاط الإحالة:</b>\n"
                        "قم بضبط <b>(معلومات الدفع)</b>.\n\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "💡 <i>استخدم لوحة التحكم للبدء في التهيئة الآن.</i>"
                    )
                    await temp_bot.send_message(chat_id=user_id, text=setup_guide_text, parse_mode="HTML")
            except Exception as e:
                print(f"⚠️ فشل إرسال رسائل الترحيب: {e}")

            # --- [ الرسالة الثالثة: إشعار المطور ] ---
            total_bots = get_total_bots_count()
            admin_notification = (
                f"<b>🔔 إشعار تصنيع جديد</b>\n"
                f"-----------------------\n"
                f"👤 <b>المنشئ:</b> {user.full_name}\n"
                f"🔗 <b>يوزر المالك:</b> @{user.username if user.username else 'لا يوجد'}\n"
                f"🆔 <b>آيدي المالك:</b> <code>{user_id}</code>\n"
                f"-----------------------\n"
                f"🤖 <b>نوع البوت:</b> {friendly_name}\n"
                f"📛 <b>الاسم:</b> {friendly_name}\n"
                f"🎈 <b>يوزر البوت:</b> {bot_username}\n"
                f"-----------------------\n\n"
                f"📈 <b>إجمالي إنتاج المصنع:</b> {total_bots} بوت"
            )
            #from main--import ADMIN_ID
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode="HTML")

        else:
            await msg.edit_text("❌ حدث خطأ أثناء الحفظ.")

    except Exception as e:
        print(f"❌ Error in finalize: {e}")
        await msg.edit_text("⚠️ حدث تداخل بسيط أثناء التهيئة.")

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
        [InlineKeyboardButton("⚙️ تهيئة الجداول", callback_data="run_setup_db_now")],
        [InlineKeyboardButton("📢 إذاعة للمشتركين", callback_data="broadcast_owners")],
        [
            InlineKeyboardButton("📥 تحميل نسخة", callback_data="download_cache_files"),
            InlineKeyboardButton("📤 رفع نسخة", callback_data="start_restore_request")
        ],
        [
            InlineKeyboardButton("🔄 تحديث السيرفر", callback_data="restart_factory"), 
            InlineKeyboardButton("♻️ إعادة تشغيل", callback_data="reboot_system")
        ],
        [InlineKeyboardButton("⏳ بدء المزامنة اليدوية", callback_data="start_sync_shet")],
        [InlineKeyboardButton("⚠️ تصفير النظام بالكامل", callback_data="confirm_hard_reset")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
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
#>>>>>>>>>>>>>>>>
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ضغطات الأزرار الشفافة المركزية"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer() # لإيقاف مؤشر التحميل في تليجرام
    if data == "confirm_hard_reset":
        keyboard = [
            [InlineKeyboardButton("✅ نعم، متأكد", callback_data="execute_hard_reset")],
            [InlineKeyboardButton("❌ تراجع", callback_data="dev_panel")]
        ]
        await query.edit_message_text("‼️ **تحذير حرج:**\nهذا الإجراء سيحذف كافة البيانات في جوجل شيت. هل أنت متأكد؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "execute_hard_reset":
        await query.edit_message_text("⏳ جاري التصفير...")
        if reset_entire_database():
            await query.edit_message_text("✅ تم تصفير النظام بنجاح.\nيرجى إعادة تشغيل السيرفر الآن.")
        else:
            await query.edit_message_text("❌ فشلت العملية. راجع السجلات.")

    
    elif data == "restart_factory":
        await query.answer("🔄 جاري إعادة التشغيل...")
        from cache_manager import fetch_full_factory_data; await fetch_full_factory_data()        
        await query.edit_message_text("🔄 جاري إعادة تشغيل المصنع لتطبيق التحديثات...")
        os.execv(sys.executable, ['python'] + sys.argv)
#~~~~~~~~~~~~~~~~
    # --- [ معالج زر إعادة تشغيل المحرك لقتل النسخ المتضاربة ] ---
    elif data == "reboot_system":
        from course_engine import restart_bot_logic
        await restart_bot_logic(update, context)

#~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~~


    # --- [ معالج زر بدء المزامنة اليدوية ] ---
    elif data == "start_sync_shet":
        # إرسال رسالة أولية للمستخدم
        msg = await query.edit_message_text("🔄 جاري بدء مزامنة المصنع مع السحابة... يرجى الانتظار")
        
        try:
            # استدعاء دالة المزامنة الذكية التي صممناها في cache_manager
            from cache_manager import sync_factory_to_sheets_smart
            
            # تشغيل المزامنة
            await sync_factory_to_sheets_smart()
            
            # تحديث الرسالة بعد النجاح
            await query.edit_message_text("✅ اكتملت المزامنة اليدوية بنجاح وتم تحديث كافة البيانات.")
        except Exception as e:
            await query.edit_message_text(f"❌ فشلت المزامنة اليدوية: {str(e)}")
        
    elif data == "open_admin_panel" or data == "open_admin_dashboard":
        await owner_dashboard(update, context)
        
    elif data == "download_cache_files":
        await download_bot_cache(update, context)
        
    elif data == "start_restore_request":
        await query.answer()
        await query.edit_message_text("📥 <b>نظام الاستعادة:</b>\nيرجى إرسال ملف النسخة الاحتياطية (.json) الآن.", parse_mode="HTML")
        
    # استعادة النسخة - القرار النهائي
    elif data == "confirm_restore":
        content = context.user_data.get('pending_restore_content')
        if not content:
            await query.edit_message_text("❌ انتهت صلاحية الجلسة أو الملف غير موجود، يرجى المحاولة مجدداً.")
            return

        # إظهار رسالة بدء العمليات
        await query.edit_message_text("⏳ <b>المرحلة 1:</b> جاري تحديث بيانات السيرفر المحلي وفك التشفير...", parse_mode="HTML")
        
        from cache_manager import process_restore_logic
        
        # بدء التنفيذ المتسلسل للمحرك المرن (يعمل مع المصنع الشامل أو البوت الفرعي)
        if await process_restore_logic(content, user_id):
            # المرحلة 2: تحديث السحابة (تتم داخل الدالة ولكن نظهرها هنا للتوضيح كما في كودك)
            await query.edit_message_text("📡 <b>المرحلة 2:</b> نجح تحديث السيرفر، جاري الآن مزامنة التحديث مع Google Sheets...", parse_mode="HTML")
            
            await asyncio.sleep(2) # محاكاة المزامنة لضمان استقرار الرسائل للمستخدم
            
            # الرسالة النهائية للنجاح
            await query.edit_message_text("🎊 <b>تمت الاستعادة والمزامنة بنجاح!</b>\nتم تحديث قاعدة البيانات بالكامل حسب صلاحياتك.", parse_mode="HTML")
        else:
            # في حال فشل المحرك في فك التشفير أو الوصول للأوراق
            await query.edit_message_text("❌ فشلت عملية الاستعادة. الملف قد يكون تالفاً أو لا يخص هذا المصنع.")
        
        # تنظيف الذاكرة المؤقتة بعد الانتهاء
        context.user_data.pop('pending_restore_content', None)

    elif data == "cancel_restore":
        context.user_data.pop('pending_restore_content', None)
        await query.edit_message_text("❌ تم إلغاء عملية الاستعادة بنجاح.")

    elif data == "back_to_main":
        await query.answer()
        await query.edit_message_text(
            "✨ أهلاً بك في مصنع البوتات المتطور 🤖\n\nاختر ما تريد القيام به:",parse_mode="HTML", 
            reply_markup=get_main_menu_inline(user_id)
        )
# --------------------------------------------------------------------------

    # تهيئة الورق والإعدادات - النسخة الاحترافية النهائية
    elif data == "run_setup_db_now":
        # 1. نظام الحماية من التشغيل المزدوج
        if context.user_data.get("setup_running"):
            await query.answer("⚠️ العملية قيد التنفيذ بالفعل...", show_alert=True)
            return

        context.user_data["setup_running"] = True
        context.user_data["cancel_setup"] = False
        
        loading_colors = ["🔴", "🟠", "🟡", "🟢", "🔵", "🟣"]
        base_loading_msg = (
            "⏳ <b>جاري تشغيل محركات المصنع...</b>\n"
            "━━━━━━━━━━━━━━\n"
            "🔄 جاري فحص وإنشاء جداول قاعدة البيانات...\n"
            "🎨 جاري تنسيق الصفوف والألوان تلقائياً...\n"
            "⚙️ جاري زرع الإعدادات الافتراضية للبوت...\n\n"
            "<i>يرجى الانتظار، لا تغلق هذه الصفحة...</i>"
        )

        from sheets import setup_bot_factory_database
        import time

        # 2. تشغيل المهمة في مسار خلفي لضمان استجابة البوت
        setup_task = asyncio.create_task(asyncio.to_thread(setup_bot_factory_database, context.bot.token))
        
        try:
            color_index = 0
            start_time = time.time()
            
            # 3. حلقة الوميض وشريط التقدم (Loop)
            while not setup_task.done():
                if context.user_data.get("cancel_setup"):
                    setup_task.cancel()
                    break

                # حساب التقدم (Progress Bar)
                elapsed = time.time() - start_time
                progress = min(98, int((elapsed / 60) * 100))
                bar = "🟩" * (progress // 10) + "⬜" * (10 - (progress // 10))
                
                current_color = loading_colors[color_index % len(loading_colors)]
                status_text = (
                    f"{current_color} {base_loading_msg}\n\n"
                    f"📊 <b>التقدم:</b> [{bar}] {progress}%\n"
                    f"⏱️ الوقت المنقضي: {int(elapsed)} ثانية"
                )

                try:
                    # تحديث الرسالة كل 2.5 ثانية (التوقيت الذهبي)
                    await query.edit_message_text(
                        status_text, 
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_setup")]]),
                        parse_mode="HTML"
                    )
                except: 
                    pass

                color_index += 1
                await asyncio.sleep(2.5) 

            # 4. انتظار النتيجة النهائية  ← تم إخراجها خارج while فقط بالمسافات
                # 4. انتظار النتيجة النهائية
                try:
                    # تشغيل محرك التهيئة في خيط منفصل لضمان عدم تجميد البوت
                    # الدالة ensure_all_sheets_schema تعيد عدد الأوراق المعالجة (int)
                    result = await asyncio.to_thread(ensure_all_sheets_schema)
                    
                    # --- [ نظام الحساب الديناميكي المرن ] ---
                    # إذا كانت النتيجة رقماً (عدد الأوراق)، نستخدمها مباشرة
                    if isinstance(result, (int, float)):
                        sheets_count = int(result)
                    # إذا كانت النتيجة منطقية (True)، نجلب العدد ديناميكياً من دالة الهيكل
                    elif result is True:
                        try:
                            from sheets import get_sheets_structure
                            dynamic_structure = get_sheets_structure()
                            sheets_count = len(dynamic_structure)
                        except:
                            sheets_count = "غير محدد"
                    else:
                        sheets_count = 0
                    
                    if sheets_count != 0:
                        result_text = (
                            "✅ <b>تمت العملية بنجاح!</b>\n"
                            "━━━━━━━━━━━━━━\n"
                            f"📦 تم إنشاء وتنسيق (<b>{sheets_count} ورقة</b>) بالكامل.\n"
                            "🛡️ نظام الحماية والتحقق من المخطط (Schema) نشط الآن."
                        )
                    else:
                        result_text = "⚠️ <b>النظام مهيأ بالفعل!</b>\nالجداول موجودة ومحدثة."
                    
                    # تحديث الرام فوراً لضمان مطابقة البيانات الجديدة (وظيفة أساسية)
                    from cache_manager import fetch_full_factory_data
                    await fetch_full_factory_data()
                        
                except Exception as e:
                    print(f"❌ خطأ في التهيئة: {e}")
                    result_text = f"❌ <b>فشلت العملية!</b>\nحدث خطأ أثناء المعالجة: {str(e)}"
                    
                finally:
                    # إنهاء حالة التشغيل للسماح بالعمليات المستقبلية (وظيفة أساسية)
                    context.user_data["setup_running"] = False

                # إرسال الرسالة النهائية وتوفير زر العودة
                keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="open_admin_panel")]]
                await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- نهاية معالج الأزرار وبداية الدوال المستقلة ---

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

# --------------------------------------------------------------------------
# دالة رفع ملف بوت جديد (تحديث تفاعلي للمطور)
async def handle_module_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الخطوة 1: استقبال الملف البرمجي من المطور"""
    if update.effective_user.id != ADMIN_ID: return
    
    doc = update.message.document
    if doc.file_name.endswith(".py"):
        file = await doc.get_file()
        file_path = f"./{doc.file_name}"
        await file.download_to_drive(file_path)
        
        # حفظ اسم الملف مؤقتاً للخطوة التالية
        context.user_data["uploaded_module_file"] = doc.file_name
        
        await update.message.reply_text(
            f"✅ تم رفع الملف <code>{doc.file_name}</code> بنجاح.\n\n"
            f"<b>الآن أرسل الاسم (النوع) الجديد الذي تريد ربطه بهذا الملف:</b>",
            parse_mode="HTML"
        )
        return WAITING_FOR_MODULE_NAME

# --------------------------------------------------------------------------
async def finalize_module_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الخطوة 2: استقبال اسم الموديول، حفظ الوصف في الشيت، وإعادة تشغيل المصنع"""
    if update.effective_user.id != ADMIN_ID: return
    
    module_display_name = update.message.text.strip()
    file_name = context.user_data.get("uploaded_module_file")
    key_name = f"desc_{file_name}"
    
    # --- نظام الحفظ الذكي في شيت الميتا (تحديث أو إضافة) ---
    status_msg = "تمت إضافته كنوع جديد"
    try:
        from sheets import meta_sheet
        from datetime import datetime
        if meta_sheet:
            # البحث عن الملف إذا كان مسجلاً مسبقاً
            cell = None
            try:
                cell = meta_sheet.find(key_name)
            except:
                pass

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if cell:
                # إذا وجدناه، نقوم بتحديث العمود الثاني (الاسم الوصفي) والثالث (التاريخ)
                meta_sheet.update_cell(cell.row, 2, module_display_name)
                meta_sheet.update_cell(cell.row, 3, now_str)
                status_msg = "تم تحديث بيانات الموديول الحالي"
            else:
                # إذا لم نجده، نضيف سطراً جديداً
                meta_sheet.append_row([key_name, module_display_name, now_str])
    except Exception as e:
        print(f"⚠️ خطأ في مزامنة الميتا: {e}")
        status_msg = "تم الرفع (مع تعذر تحديث قاعدة البيانات)"

    # رسالة التأكيد الاحترافية التي طلبتها
    await update.message.reply_text(
        f"<b>🚀 {status_msg} بنجاح!</b>\n"
        f"-----------------------\n"
        f"📛 <b>الاسم الوصفي:</b> {module_display_name}\n"
        f"📄 <b>الملف البرمجي:</b> <code>{file_name}</code>\n"
        f"⚙️ <b>الحالة:</b> مرتبط وجاهز للتشغيل\n"
        f"-----------------------\n"
        f"🔄 جاري الآن إعادة تشغيل المصنع لتفعيل التحديثات فوراً...",
        parse_mode="HTML"
    )
    
    context.user_data.clear()
    # إعادة التشغيل لتطبيق التغييرات برمجياً
    os.execv(sys.executable, ['python'] + sys.argv)

# --------------------------------------------------------------------------

# إعداد الـ ConversationHandler لإنشاء البوت (مع خطوة الاسم المخصص)
create_bot_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex('^➕ إنشاء بوت$'), start_create_bot),
        CallbackQueryHandler(start_create_bot, pattern="^start_manufacture$")
    ],
    states={
        CHOOSING_TYPE: [CallbackQueryHandler(select_type, pattern="^set_type_")],
        GETTING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
        GETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_bot)],
    },
    fallbacks=[
        CommandHandler('cancel', cancel), 
        CallbackQueryHandler(cancel, pattern="^cancel_action$"),
        MessageHandler(filters.Regex('^🔙 العودة$'), cancel)
    ],
)

# إعداد الـ ConversationHandler لرفع الموديولات للمطور
admin_module_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Document.FileExtension("py"), handle_module_upload)],
    states={
        WAITING_FOR_MODULE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_module_name)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

# --------------------------------------------------------------------------


# --- دالة تحميل مرآة الكاش (توضع في main.py) ---
async def download_bot_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استدعاء محرك تحميل ملفات المرآة وإرسالها حسب صلاحية المستخدم"""
    user_id = update.effective_user.id
    # (تمت إزالة شرط التحقق الصارم من ADMIN_ID للسماح للعملاء بتحميل بياناتهم)
    
    query = update.callback_query
    if query: await query.answer()

    from cache_manager import download_mirror_files
    
    # التعديل هنا: نمرر user_id (المستخدم الحالي) بدلاً من ADMIN_ID الثابت
    await download_mirror_files(context.bot, user_id)

#رفع النسخة 
async def start_restore_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المرحلة الأولى: استقبال الملف وعرض التحذير"""
    user_id = update.effective_user.id
    doc = update.message.document
    
    if not doc.file_name.endswith('.json'):
        await update.message.reply_text("❌ عذراً، يجب أن يكون الملف بصيغة .json المشفرة.")
        return

    # حفظ محتوى الملف مؤقتاً في ذاكرة المستخدم
    file = await context.bot.get_file(doc.file_id)
    content = await file.download_as_bytearray()
    context.user_data['pending_restore_content'] = content.decode('utf-8')

    keyboard = [
        [
            InlineKeyboardButton("✅ نعم، أوافق", callback_data="confirm_restore"),
            InlineKeyboardButton("❌ لا، إلغاء", callback_data="cancel_restore")
        ]
    ]
    
    warn_text = (
        "⚠️ <b>تحذير هام جداً!</b>\n"
        "━━━━━━━━━━━━━━\n"
        "لقد قمت برفع نسخة احتياطية. إذا وافقت:\n"
        "1. سيتم استبدال البيانات الحالية ببيانات النسخة.\n"
        "2. قد تفقد أي تحديثات تمت بعد تاريخ هذه النسخة.\n\n"
        "<b>هل أنت متأكد من رغبتك في التنفيذ؟</b>"
    )
    await update.message.reply_text(warn_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")



# --------------------------------------------------------------------------


# --------------------------------------------------------------------------



# --- [ القسم 1: الدوال التشغيلية (يجب أن تظل في الأعلى) ] ---

# دالة تشغيل كافة البوتات عند الإقلاع لضمان التنفيذ المتسلسل
async def start_all_sub_bots():
    from sheets import get_all_active_bots
    active_bots = get_all_active_bots()
    print(f"🔄 جاري محاولة تشغيل {len(active_bots)} بوت مصنوع...")
    
    for bot_data in active_bots:
        token = bot_data.get("التوكن")
        owner_id = bot_data.get("ID المالك")
        bot_type = bot_data.get("نوع البوت")
        
        if token and bot_type:
            await asyncio.sleep(1.5) 
            asyncio.create_task(run_dynamic_bot(token, bot_type, owner_id))
            print(f"✅ تم إرسال أمر تشغيل للبوت: {bot_type}")

    print("🎊 اكتملت عملية إقلاع كافة البوتات التابعة.")

async def boot_all_bots():
    from sheets import get_all_active_bots
    active_bots = get_all_active_bots()
    print(f"🔄 جاري تحضير إقلاع {len(active_bots)} بوت تابعة للمصنع...")




# --- [ القسم 3: المحرك الرئيسي (نهاية الملف) ] ---
async def main_factory_launcher():
    global app
    try:
        # 1. بناء التطبيق أولاً (TOKEN يجب أن يكون معرفاً في الأعلى)
        print("🔧 جاري بناء محرك البوت الرئيسي...")
        app = ApplicationBuilder().token(TOKEN).build()

        # 2. إضافة المعالجات (تأكد من وجود handlers المعرفة سابقاً)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(create_bot_conv) 
        app.add_handler(admin_module_conv)
        app.add_handler(CallbackQueryHandler(button_callback, pattern="^(stats_all|run_setup_db_now|broadcast_owners|restart_factory|download_cache_files|reboot_system|confirm_hard_reset|execute_hard_reset|start_sync_shet|start_restore_request|back_to_main|open_admin_dashboard)$"))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, start_restore_process))

        # 3. استدعاء البوتات التابعة (الآن لن يظهر خطأ Not Defined)
        await boot_all_bots() 
        asyncio.create_task(start_all_sub_bots()) 

        # 4. تشغيل محرك المصنع
        print("🚀 مصنع البوتات يعمل الآن بكافة محركاته...")
        await app.initialize()
        await app.updater.start_polling(drop_pending_updates=True)
        await app.start()
        
        # إشعار المطور بالنجاح
        try:
            await app.bot.send_message(chat_id=ADMIN_ID, text="✅ **تم إعادة تشغيل المحرك بنجاح!**")
        except: pass
        
        while True:
            await asyncio.sleep(3600)

    except Exception as e:
        print(f"🔴 خطأ حرج في إقلاع المصنع: {e}")


if __name__ == "__main__":
    import asyncio
    import logging
    # تشغيل المحرك الرئيسي من خلال asyncio.run لضمان استقرار الـ Loop
    try:
        asyncio.run(main_factory_launcher())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 تم إيقاف المصنع يدوياً.")
    except Exception as e:
        print(f"🔴 فشل المحرك الرئيسي الحرج: {e}")

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
    get_total_factory_users, # دالة إحصائيات مستخدمي المصنع
    get_all_active_bots
)

# --- الإعدادات الأساسية ---
TOKEN = "8532487667:AAGYgoSw-S2G7ruf_To8LGGd5OGCfn_T6dw"
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
def get_types_menu_inline():
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

    exclude_files = ['main.py', 'sheets.py', 'contact_bot.py', 'education_bot.py', 'protection_bot.py', 'store_bot.py', 'config.py', 'runner.py', 'course_engine.py', 'educational_manager.py']
    
    dynamic_buttons = []
    for file in os.listdir('.'):
        if file.endswith('.py') and file not in exclude_files:
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
                    if str(r.get('value')) == bot_type.strip():
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
    """حفظ البيانات، فك تداخل التوكينات، وتشغيل الإشعارات الثلاثية بصيغ مميزة وتنسيق آمن"""
    bot_display_name = update.message.text.strip()
    user = update.effective_user
    user_id = user.id
    bot_type = context.user_data.get("type")
    bot_token = context.user_data.get("bot_token")

    msg = await update.message.reply_text("⏳ جاري تهيئة المحرك وفك تداخل التوكينات...")

    try:
        from telegram import Bot
        # إنشاء كائن بوت مستقل للتعامل مع التوكن الجديد
        temp_bot = Bot(bot_token)
        
        # حماية: إلغاء أي جلسات نشطة ومسح الرسائل العالقة لإنهاء مشكلة Conflict
        await temp_bot.delete_webhook(drop_pending_updates=True)
        
        bot_info = await temp_bot.get_me()
        bot_username = f"@{bot_info.username}"

        # حفظ البيانات في جوجل شيت
        from sheets import save_bot, get_total_bots_count
        success = save_bot(user_id, bot_type, bot_display_name, bot_token)

        if success:
            # تشغيل البوت أوتوماتيكياً باستخدام المحرك الديناميكي الجديد
            asyncio.create_task(run_dynamic_bot(bot_token, bot_type, user_id))

            # --- [الرسالة الأولى: إشعار النجاح للمستخدم في المصنع] ---
            user_success_text = (
                f"<b>🎊 تمت العملية بنجاح!</b>\n\n"
                f"لقد انتهينا من برمجة بوتك الجديد وإطلاقه في الفضاء الرقمي.\n\n"
                f"📦 <b>نوع الموديول:</b> {bot_type}\n"
                f"📛 <b>الاسم المخصص:</b> {bot_display_name}\n"
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
                f"📛 <b>الاسم:</b> {bot_display_name}\n"
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
                f"📛 <b>الاسم:</b> {bot_display_name}\n"
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
        [InlineKeyboardButton("⚙️ تهيئة الجداول", callback_data="setup_db_menu")],
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
        
    elif data == "open_admin_panel" or data == "open_admin_dashboard":
        await owner_dashboard(update, context)
        
    elif data == "back_to_main":
        await query.answer()
        await query.edit_message_text(
            "✨ أهلاً بك في مصنع البوتات المتطور 🤖\n\nاختر ما تريد القيام به:",
            reply_markup=get_main_menu_inline(user_id)
        )
# --------------------------------------------------------------------------


    # تهيئة الورق والإعدادات مع لودينج "وميض ألوان مستمر" في ملف main.py
    elif data == "run_setup_db_now":
        # 1. قائمة الألوان للمحاكاة البصرية المستمرة
        loading_colors = ["🔴", "🟠", "🟡", "🟢", "🔵", "🟣"]
        
        base_loading_msg = (
            "<b>جاري تشغيل محركات المصنع...</b>\n"
            "━━━━━━━━━━━━━━\n"
            "🔄 جاري فحص وإنشاء جداول قاعدة البيانات...\n"
            "🎨 جاري تنسيق الصفوف والألوان تلقائياً...\n"
            "⚙️ جاري زرع الإعدادات الافتراضية للبوت...\n\n"
            "<i>يرجى الانتظار، العملية مستمرة حتى اكتمال كافة الجداول...</i>"
        )

        # 2. تشغيل عملية الشيت في "مهمة خلفية" لضمان عدم تجميد الألوان
        from sheets import setup_bot_factory_database
        
        # إنشاء المهمة (Task) للعملية الثقيلة لتعمل في مسار منفصل
        setup_task = asyncio.create_task(asyncio.to_thread(setup_bot_factory_database, context.bot.token))
        
        # 3. حلقة التكرار للألوان (Loop) - تستمر طالما أن إنشاء الجداول لم ينتهِ
        color_index = 0
        while not setup_task.done():
            try:
                # اختيار اللون التالي من المصفوفة بشكل دوري
                current_color = loading_colors[color_index % len(loading_colors)]
                
                # تحديث الرسالة باللون الجديد مع الحفاظ على النص كاملاً
                await query.edit_message_text(
                    f"{current_color} {base_loading_msg}", 
                    parse_mode="HTML"
                )
                
                color_index += 1
                # سرعة الوميض: 0.8 ثانية لضمان سلاسة الحركة وعدم تجاوز قيود تليجرام
                await asyncio.sleep(0.8) 
            except Exception:
                # لتجنب توقف البوت في حال حاول تحديث نفس الرسالة بسرعة
                break
        
        # 4. انتظار الحصول على النتيجة النهائية (عدد الأوراق) بعد انتهاء المهمة
        sheets_count = await setup_task
        
        # 5. عرض النتيجة النهائية بعد اكتمال العمل بالكامل
        if sheets_count > 0:
            result_text = (
                "✅ <b>تمت العملية بنجاح!</b>\n"
                "━━━━━━━━━━━━━━\n"
                f"📦 تم إنشاء وتنسيق (<b>{sheets_count} ورقة</b>) بالكامل.\n"
                "🛡️ نظام الحماية والتحقق من المخطط (Schema) نشط الآن."
            )
        else:
            result_text = (
                "❌ <b>فشلت العملية!</b>\n"
                "حدث خطأ أثناء الاتصال بجوجل شيت، يرجى مراجعة سجلات السيرفر."
            )
            
        keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="open_admin_panel")]]
        
        # استبدال حالة الوميض بالنتيجة النهائية وأزرار التحكم
        await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------


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

# --- دالة تشغيل البوتات المصنوعة تلقائياً ---
async def start_all_sub_bots():
    from sheets import get_all_active_bots
    active_bots = get_all_active_bots()
    print(f"🔄 جاري محاولة تشغيل {len(active_bots)} بوت مصنوع...")
    
    for bot_data in active_bots:
        token = bot_data.get("التوكن")
        owner_id = bot_data.get("ID المالك")
        bot_type = bot_data.get("نوع البوت")
        if token and bot_type:
            # تشغيل كل بوت في مهمة مستقلة لضمان عدم توقف المصنع
            asyncio.create_task(run_dynamic_bot(token, bot_type, owner_id))

        
        # تشغيل البوتات تلقائياً باستخدام المحرك الديناميكي





# بناء التطبيق
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(create_bot_conv) 
app.add_handler(admin_module_conv) # محادثة الرفع الجديدة
app.add_handler(CallbackQueryHandler(button_callback))
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

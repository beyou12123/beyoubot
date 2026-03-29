import logging
import re
import io
import uuid
import g4f  # لضمان عمل المحرك المجاني الذي اعتمدناه
import google.generativeai as genai
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

# --- [ ذاكرة المحادثات المؤقتة للطلاب ] ---
user_messages = {} 

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
    delete_course_by_id
)


# إعداد المفتاح الذي حصلت عليه
genai.configure(api_key="AIzaSyCkpHbxvjZNqN_PT8O1yXUAIG-dMAGZj2Y")
model = genai.GenerativeModel('gemini-1.5-flash')
# إعداد السجلات (Logging) لمراقبة أداء البوت وتتبع الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- [ القوائم الرئيسية للمنصة - أزرار واجهة المستخدم ] ---

def get_student_menu():
    """قائمة الأزرار الرئيسية التي تظهر للطلاب"""
    keyboard = [
        [InlineKeyboardButton("📚 استعراض الدورات", callback_data="view_courses")],
        [InlineKeyboardButton("👤 ملفي الدراسي", callback_data="my_profile"), InlineKeyboardButton("🎟 تفعيل دورة", callback_data="redeem_code")],
        [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="edu_faq"), InlineKeyboardButton("💬 الدعم الفني", callback_data="edu_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel():
    """قائمة الأزرار الرئيسية للوحة تحكم الإدارة - النسخة المطورة بضبط الـ AI"""
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات الذكية", callback_data="admin_stats")],
        [
            InlineKeyboardButton("📁 إدارة الأقسام", callback_data="manage_cats"),
            InlineKeyboardButton("📚 إدارة الدورات", callback_data="manage_courses")
        ],
        [InlineKeyboardButton("👨‍🏫 إدارة شؤون المدربين", callback_data="manage_coaches")],
        [
            InlineKeyboardButton("🎟 الكوبونات", callback_data="manage_coupons"),
            InlineKeyboardButton("📢 الإعلانات", callback_data="manage_ads")
        ],
        [InlineKeyboardButton("📡 الإذاعة المستهدفة", callback_data="smart_broadcast")],
        [
            InlineKeyboardButton("🛠 الإعدادات التقنية", callback_data="tech_settings"),
            InlineKeyboardButton("🤖 ضبط الـ AI", callback_data="setup_ai_start") # الزر الجديد هنا
        ],
        [InlineKeyboardButton("❌ إغلاق", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- [ المعالجات الأساسية - أمر البداية ] ---

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /start برسائل ترحيبية ذكية يحددها المسؤول حسب الوقت"""
    from datetime import datetime
    user = update.effective_user
    bot_token = context.bot.token
    
    # جلب كافة الإعدادات من جوجل شيت
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    # ... (بعد جلب bot_owner_id)
    from sheets import get_ai_setup
    ai_config = get_ai_setup(bot_token)
    
    # تصحيح الـ HTML والإزاحة لضمان استجابة البوت

    if user.id == bot_owner_id:
        if not ai_config or not ai_config.get('اسم_المؤسسة'):

            context.user_data['action'] = 'awaiting_institution_name'
            await update.message.reply_text(
                "👋 <b>أهلاً بك يا دكتور!</b>\n\n"
                "قبل البدء، يرجى إرسال <b>اسم المنصة التعليمية</b> الخاصة بك:",
                parse_mode="HTML"
            )
            return



    # تسجيل المستخدم في القاعدة
    save_user(user.id, user.username)

    # --- [ محرك اختيار الكليشة الذكي ] ---
    hour = datetime.now().hour
    
    # تحديد الفترة وجلب النص المخصص من الشيت (مع نص افتراضي في حال كان العمود فارغاً)
    if 5 <= hour < 12:
        msg = config.get("welcome_morning", "صباح العلم والهمة.. أي مهارة سنبني اليوم؟")
    elif 12 <= hour < 17:
        msg = config.get("welcome_noon", "طاب يومك.. الاستمرارية هي سر النجاح، لنكمل التعلم.")
    elif 17 <= hour < 22:
        msg = config.get("welcome_evening", "مساء الفكر المستنير.. حان وقت الحصاد المعرفي.")
    else:
        msg = config.get("welcome_night", "أهلاً بالمثابر.. العظماء يصنعون مستقبلهم في هدوء الليل.")

    # --- [ إرسال الواجهة المناسبة ] ---
    if user.id == bot_owner_id:
        # واجهة الدكتور (المسؤول)
        await update.message.reply_text(
            f"<b>مرحباً بك يا دكتور {user.first_name} في مركز قيادة منصتك</b> 🎓\n\n"
            f"{msg}\n\n"
            f"يمكنك إدارة كافة مفاصل المنصة من الأزرار أدناه:",
            reply_markup=get_admin_panel(),
            parse_mode="HTML"
        )
    else:
        # واجهة الطالب
        await update.message.reply_text(
            f"<b>{msg}</b>",
            reply_markup=get_student_menu(),
            parse_mode="HTML"
        )



# --------------------------------------------------------------------------
# --- [ معالج ضغطات الأزرار (Callback Query Handler) ] ---
# --------------------------------------------------------------------------

async def contact_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحكم في كافة عمليات الضغط على الأزرار الشفافة Inline Buttons"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    bot_token = context.bot.token
    config = get_bot_config(bot_token)
    bot_owner_id = int(config.get("admin_ids", 0))

    await query.answer()

    # --- 1. إدارة الإحصائيات ---
    if data == "admin_stats":
        total_students = get_bot_users_count(bot_token)
        blocks = get_bot_blocks_count(bot_token)
        stats_text = (
            f"<b>📊 تقرير المنصة الحالي:</b>\n"
            f"-----------------------\n"
            f"👥 إجمالي الطلاب: {total_students}\n"
            f"🚫 عدد المحظورين: {blocks}\n"
            f"💰 مبيعات اليوم: 0.00$\n"
            f"📈 أكثر دورة طلباً: لا يوجد بيانات بعد"
        )
        await query.edit_message_text(stats_text, reply_markup=get_admin_panel(), parse_mode="HTML")

    # --- 2. إدارة الدورات التدريبية (الواجهة الرئيسية) ---
# تحديث قسم إدارة الدورات ليشمل كافة طرق الاستيراد المتاحة
    elif data == "manage_courses":
        await query.edit_message_text(
        "📚 <b>إدارة واستيراد الدورات:</b>\n\nاختر الطريقة التي تفضلها لإضافة البيانات:", 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة دورة فردية", callback_data="start_add_course")],
            [
                InlineKeyboardButton("📥 نصية (|)", callback_data="bulk_add_start"),
                InlineKeyboardButton("📊 ملف Excel", callback_data="excel_import_start")
            ],
            [
                InlineKeyboardButton("📄 ملف CSV", callback_data="csv_import_start"),
                InlineKeyboardButton("🔗 رابط Google Sheet", callback_data="sheet_link_import")
            ],
            [InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")]
        ]), 
        parse_mode="HTML"
    )

# --------------------------------------------------------------------------
    # --- 3. إدارة شؤون المدربين ---
    elif data == "manage_coaches":
        await query.edit_message_text(
            "👨‍🏫 <b>إدارة شؤون المدربين:</b>\nيمكنك إضافة مدربين جدد أو استعراض القائمة الحالية للحذف.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة مدرب جديد", callback_data="start_add_coach")],
                [InlineKeyboardButton("📋 عرض قائمة المدربين", callback_data="list_coaches")],
                [InlineKeyboardButton("🔙 عودة للوحة التحكم", callback_data="back_to_admin")]
            ]), parse_mode="HTML"
        )
# --------------------------------------------------------------------------
    elif data == "setup_ai_start":
        context.user_data['action'] = 'awaiting_institution_name'
        await query.edit_message_text("🤖 <b>إعداد الهوية الذكية:</b>\nيرجى إرسال اسم المنصة التعليمية الآن:")

# --------------------------------------------------------------------------
    # عرض قائمة المدربين كأزرار
    elif data == "list_coaches":
        from sheets import get_all_coaches
        coaches = get_all_coaches(bot_token)
        if not coaches:
            await query.edit_message_text("⚠️ لا يوجد مدربون مسجلون حالياً.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_coaches")]]))
            return

        keyboard = [[InlineKeyboardButton(f"👤 {c['name']}", callback_data=f"view_coach_{c['id']}")] for c in coaches]
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="manage_coaches")])
        await query.edit_message_text("🎯 **اختر مدرباً لعرض تفاصيله أو حذفه:**", reply_markup=InlineKeyboardMarkup(keyboard))
# --------------------------------------------------------------------------
    # عرض تفاصيل مدرب محدد مع زر الحذف
    elif data.startswith("view_coach_"):
        coach_id = data.replace("view_coach_", "")
        from sheets import get_all_coaches
        coaches = get_all_coaches(bot_token)
        coach = next((c for c in coaches if str(c['id']) == str(coach_id)), None)
        
        if coach:
            text = f"👤 **معلومات المدرب:**\n━━━━━━━━━━━━━━\nالاسم: {coach['name']}\nID: <code>{coach['id']}</code>"
            keyboard = [
                [InlineKeyboardButton("🗑️ حذف المدرب نهائياً", callback_data=f"del_coach_{coach['id']}")],
                [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="list_coaches")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
# --------------------------------------------------------------------------
    # تنفيذ الحذف الفعلي للمدرب
    elif data.startswith("del_coach_"):
        coach_id = data.replace("del_coach_", "")
        from sheets import delete_coach_from_sheet
        if delete_coach_from_sheet(bot_token, coach_id):
            await query.answer("✅ تم حذف المدرب بنجاح", show_alert=True)
            await query.edit_message_text("✅ تم الحذف. هل تريد إدارة مدرب آخر؟", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 عرض القائمة", callback_data="list_coaches")]]))
        else:
            await query.answer("❌ فشل الحذف", show_alert=True)
# --------------------------------------------------------------------------
    elif data == "bulk_add_start":
        context.user_data['action'] = 'awaiting_bulk_courses'
        instruction = (
            "📥 <b>إضافة دورات دفعة واحدة:</b>\n\n"
            "يرجى إرسال الدورات بحيث يكون كل سطر دورة مستقلة بهذا التنسيق:\n"
            "<code>اسم الدورة |  الوصف وعدد الساعات | السعر | معرف المدرب | معرف القسم</code>\n\n"
            "💡 مثال:\n"
            "<code>دورة البرمجة | 40 | 150 | 873158997 | C1234</code>"
        )
        await query.edit_message_text(instruction, parse_mode="HTML")

    elif data == "excel_import_start":
        import pandas as pd
        import io
        
        # 1. تجهيز بيانات ورقة الدورات (Reference)
        courses_sample = {
            'الاسم': ['دورة الذكاء الاصطناعي الشاملة'],
            'الوصف': ['شرح مفصل للأدوات - 20 ساعة تدريبية'],
            'السعر': [100],
            'ID_المدرب': ['873158997'],
            'ID_القسم': ['C101']
        }
        
        # 2. تجهيز بيانات ورقة الأقسام (كمرجع للمالك ليعرف الأكواد)
        from sheets import get_all_categories
        categories = get_all_categories(bot_token)
        if categories:
            cats_sample = {
                'معرف_القسم': [c['id'] for c in categories],
                'اسم_القسم': [c['name'] for c in categories]
            }
        else:
            cats_sample = {'معرف_القسم': ['C101'], 'اسم_القسم': ['قسم تجريبي']}

        # إنشاء ملف Excel في الذاكرة دون الحاجة لحفظه على السيرفر
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(courses_sample).to_excel(writer, index=False, sheet_name='الدورات_التدريبية')
            pd.DataFrame(cats_sample).to_excel(writer, index=False, sheet_name='أكواد_الأقسام_المتاحة')
        
        output.seek(0)

        # تحديث حالة البوت لانتظار الملف
        context.user_data['action'] = 'awaiting_excel_file'
        
        caption = (
            "📊 <b>نظام الاستيراد الذكي من Excel:</b>\n\n"
            "1️⃣ قمت بإرفاق <b>نموذج إرشادى</b> لك يحتوي على ورقتين.\n"
            "2️⃣ ورقة <b>(الدورات)</b>: هي التي يجب تعبئتها بالبيانات الجديدة.\n"
            "3️⃣ ورقة <b>(الأقسام)</b>: مرجع لك لتعرف الأكواد المضافة حالياً في نظامك.\n\n"
            "⚠️ يرجى تعبئة الملف وإرساله لي هنا بصيغة <b>.xlsx</b>"
        )

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=output,
            filename="نموذج_استيراد_الدورات.xlsx",
            caption=caption,
            parse_mode="HTML"
        )


    elif data == "csv_import_start":
        context.user_data['action'] = 'awaiting_csv_file'
        await query.edit_message_text("📄 أرسل ملف CSV الآن:")

    elif data == "sheet_link_import":
        context.user_data['action'] = 'awaiting_sheet_link'
        await query.edit_message_text("🔗 أرسل رابط Google Sheet المفتوح للمشاركة:")

# --------------------------------------------------------------------------
    elif data == "start_add_coach":
        context.user_data['action'] = 'await_coach_name'
        await query.edit_message_text("✍️ <b>الخطوة 1:</b> أرسل اسم المدرب الثلاثي:", parse_mode="HTML")

    elif data == "confirm_save_coach":
        from sheets import add_new_coach_advanced
        c = context.user_data.get('temp_coach')
        
        if not c:
            await query.edit_message_text("⚠️ خطأ: تعذر العثور على البيانات، يرجى إعادة المحاولة من جديد.")
            return

        success = add_new_coach_advanced(
            bot_token=bot_token,
            coach_id=c['id'],
            name=c['name'],
            specialty=c['spec'],
            phone=c['phone'],
            notes="تمت الإضافة عبر لوحة التحكم"
        )
        
        if success:
            await query.edit_message_text(
                f"✅ <b>تم تسجيل المدرب بنجاح!</b>\n\n"
                f"👤 الاسم: {c['name']}\n"
                f"🎓 التخصص: {c['spec']}\n"
                f"🆔 المعرف: <code>{c['id']}</code>",
                reply_markup=get_admin_panel(),
                parse_mode="HTML"
            )
            context.user_data.pop('temp_coach', None)
        else:
            await query.edit_message_text("❌ حدث خطأ تقني أثناء الحفظ في جوجل شيت.")

# --------------------------------------------------------------------------
    # --- 4. معالجة القسم المختار للدورة وبدء طلب الاسم ---
    elif data.startswith("set_crs_cat_"):
        cat_id = data.replace("set_crs_cat_", "")
        context.user_data['temp_crs_cat'] = cat_id
        context.user_data['action'] = 'awaiting_crs_name'
        await query.edit_message_text("✍️ **الخطوة 2:** أرسل اسم الدورة الآن:")

    elif data == "confirm_save_full_crs":
        from sheets import add_new_course 
        import uuid
        
        # 1. جلب البيانات المؤقتة (البيانات + معرف القسم)
        d = context.user_data.get('temp_crs')
        cat_id = context.user_data.get('temp_crs_cat') # هذا هو الرابط الضروري
        
        if not d or not cat_id:
            await query.edit_message_text("⚠️ خطأ: تعذر العثور على البيانات المؤقتة، يرجى المحاولة مجدداً.")
            return

        # 2. توليد معرف فريد للدورة
        c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
        
        # 3. تنفيذ الحفظ الفعلي (إرسال الـ 17 متغير بالترتيب)
        success = add_new_course(
            bot_token,          # 1
            c_id,               # 2
            d['name'],          # 3
            d['hours'],         # 4
            d['start_date'],    # 5
            "",                 # 6
            "أونلاين",          # 7
            d['price'],         # 8
            "100",              # 9
            "لا يوجد",          # 10
            "إدارة المنصة",      # 11
            "ADMIN01",          # 12
            "عام",              # 13
            d['coach_user'],    # 14
            d['coach_id'],      # 15
            d['coach_name'],    # 16
            cat_id              # 17. تم إضافة معرف القسم هنا بنجاح!
        )
        
        if success:
            await query.edit_message_text(
                f"✅ <b>تم اعتماد الدورة وحفظها بنجاح!</b>\n\n"
                f"🆔 المعرف: <code>{c_id}</code>\n"
                f"📂 القسم: <code>{cat_id}</code>\n"
                f"👨‍🏫 المدرب: {d['coach_name']}",
                reply_markup=get_admin_panel(),
                parse_mode="HTML"
            )
            # تنظيف الذاكرة بعد النجاح
            context.user_data.pop('temp_crs', None)
            context.user_data.pop('temp_crs_cat', None)
        else:
            await query.edit_message_text("❌ فشل الحفظ في جوجل شيت، تأكد من إعدادات دالة add_new_course.")

    # --- 5. إدارة الأقسام (عرض القائمة) ---
    elif data == "manage_cats":
        from sheets import get_all_categories 
        categories = get_all_categories(bot_token)
        
        keyboard = []
        if categories:
            for cat in categories:
                keyboard.append([InlineKeyboardButton(f"📂 {cat['name']}", callback_data=f"edit_cat_{cat['id']}")])
        
        keyboard.append([InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="add_cat_start")])
        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            "🗂 <b>قائمة الأقسام الحالية:</b>\nاختر قسماً للتعديل أو اضغط إضافة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    elif data == "start_add_course":
        from sheets import get_all_categories
        categories = get_all_categories(bot_token)
        if not categories:
            await query.edit_message_text("⚠️ أضف قسماً أولاً!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="manage_cats")]]), parse_mode="HTML")
            return
        # اختيار القسم قبل البدء
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"set_crs_cat_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")])
        await query.edit_message_text("🎯 **الخطوة 1:** اختر القسم المخصص للدورة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # --- [ معالجة اختيار المدرب من القائمة ] ---
    elif data.startswith("sel_coach_for_crs_"):
        coach_id = data.replace("sel_coach_for_crs_", "")
        from sheets import get_all_coaches
        
        # جلب قائمة المدربين للتأكد من الاسم والبيانات
        coaches = get_all_coaches(bot_token)
        coach = next((c for c in coaches if str(c['id']) == str(coach_id)), None)
        
        if coach:
            # تخزين بيانات المدرب في ذاكرة الدورة المؤقتة
            if 'temp_crs' not in context.user_data:
                context.user_data['temp_crs'] = {}
                
            context.user_data['temp_crs'].update({
                'coach_user': "اختيار من القائمة",
                'coach_id': coach['id'],
                'coach_name': coach['name']
            })
            
            # الانتقال للخطوة التالية (تاريخ البداية)
            context.user_data['action'] = 'awaiting_crs_date'
            await query.edit_message_text(
                f"✅ تم اختيار المدرب: <b>{coach['name']}</b>\n\n"
                f"🗓 <b>الخطوة 6:</b> أرسل الآن تاريخ بداية الدورة (مثلاً: 2026/05/01):",
                parse_mode="HTML"
            )
        else:
            await query.answer("⚠️ عذراً، تعذر العثور على بيانات هذا المدرب.", show_alert=True)

    elif data.startswith("edit_cat_"):
        cat_id = data.replace("edit_cat_", "")
        context.user_data['selected_cat_id'] = cat_id
        
        keyboard = [
            [InlineKeyboardButton("📝 تعديل اسم القسم", callback_data="rename_cat")],
            [InlineKeyboardButton("📚 عرض دورات القسم", callback_data=f"view_crs_in_{cat_id}")],
            [InlineKeyboardButton("🗑️ حذف القسم", callback_data="confirm_delete_cat")],
            [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="manage_cats")]
        ]
        await query.edit_message_text(
            f"🛠 <b>إدارة القسم:</b>\n🆔 المعرف: <code>{cat_id}</code>\n\nاختر الإجراء المطلوب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data.startswith("view_crs_in_"):
        cat_id = data.replace("view_crs_in_", "")
        from sheets import get_courses_by_category
        courses = get_courses_by_category(bot_token, cat_id)
        
        keyboard = []
        if courses:
            for crs in courses:
                keyboard.append([InlineKeyboardButton(f"📖 {crs['name']}", callback_data=f"manage_crs_{crs['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 عودة للقسم", callback_data=f"edit_cat_{cat_id}")])
        
        await query.edit_message_text(
            f"📚 <b>الدورات التابعة للقسم {cat_id}:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data == "add_cat_start":
        context.user_data['action'] = 'awaiting_cat_name'
        await query.edit_message_text(
            "✍️ <b>إضافة قسم جديد:</b>\n\nيرجى إرسال اسم القسم الذي تريد إنشاءه الآن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء العملية", callback_data="manage_cats")]]),
            parse_mode="HTML"
        )

    elif data == "confirm_delete_cat":
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف", callback_data="exec_delete_cat")],
            [InlineKeyboardButton("❌ تراجع", callback_data="manage_cats")]
        ]
        await query.edit_message_text(
            "⚠️ <b>تنبيه هام!</b>\nهل أنت متأكد من حذف هذا القسم؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data == "exec_delete_cat":
        cat_id = context.user_data.get('selected_cat_id')
        if delete_category_by_id(bot_token, cat_id):
            await query.edit_message_text("✅ <b>تم حذف القسم بنجاح!</b>", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للأقسام", callback_data="manage_cats")]]), parse_mode="HTML")
        else:
            await query.edit_message_text("❌ حدث خطأ أثناء محاولة الحذف.")

    elif data == "rename_cat":
        context.user_data['action'] = 'awaiting_new_cat_name'
        await query.edit_message_text(
            "📝 <b>تعديل اسم القسم:</b>\nيرجى إرسال الاسم الجديد الآن:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="manage_cats")]]),
            parse_mode="HTML"
        )

    elif data.startswith("manage_crs_"):
        course_id = data.replace("manage_crs_", "")
        context.user_data['selected_course_id'] = course_id
        
        keyboard = [
            [InlineKeyboardButton("🗑️ حذف هذه الدورة", callback_data="confirm_delete_crs")],
            [InlineKeyboardButton("🔙 عودة لقائمة الدورات", callback_data="manage_courses")]
        ]
        await query.edit_message_text(f"📖 <b>إدارة الدورة:</b>\n🆔 المعرف: <code>{course_id}</code>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "confirm_delete_crs":
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف الدورة", callback_data="exec_delete_crs")],
            [InlineKeyboardButton("❌ تراجع", callback_data="manage_courses")]
        ]
        await query.edit_message_text("⚠️ <b>تأكيد الحذف:</b>\nهل أنت متأكد من حذف هذه الدورة؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "exec_delete_crs":
        course_id = context.user_data.get('selected_course_id')
        if delete_course_by_id(bot_token, course_id):
            await query.edit_message_text("✅ <b>تم حذف الدورة بنجاح!</b>", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="manage_courses")]]), parse_mode="HTML")

    elif data == "smart_broadcast":
        await query.edit_message_text("📡 <b>الإذاعة الذكية:</b>", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 للكل", callback_data="bc_all"), InlineKeyboardButton("🎓 لمشتركي دورة", callback_data="bc_course")]]), parse_mode="HTML")

    # --- [ إعدادات الكليشات الذكية ] ---
    elif data == "tech_settings":
        keyboard = [
            [InlineKeyboardButton("📝 كليشة الترحيب الذكية", callback_data="manage_welcome_texts")],
            [InlineKeyboardButton("🔙 عودة", callback_data="back_to_admin")]
        ]
        await query.edit_message_text("🛠 <b>الإعدادات التقنية:</b>\nتحكم في نصوص النظام والترحيب الذكي من هنا.", 
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "manage_welcome_texts":
        keyboard = [
            [InlineKeyboardButton("🌅 الصباحية", callback_data="edit_welcome_morning"), InlineKeyboardButton("☀️ الظهرية", callback_data="edit_welcome_noon")],
            [InlineKeyboardButton("🌆 المسائية", callback_data="edit_welcome_evening"), InlineKeyboardButton("🌃 الليلية", callback_data="edit_welcome_night")],
            [InlineKeyboardButton("🔙 عودة", callback_data="tech_settings")]
        ]
        await query.edit_message_text("🖼 <b>تعديل كليشات الترحيب:</b>\nاختر الفترة التي تريد تغيير رسالتها:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("edit_welcome_"):
        period = data.replace("edit_welcome_", "")
        context.user_data['edit_period'] = period
        context.user_data['action'] = 'awaiting_new_welcome_text'
        periods_ar = {"morning": "الصباحية", "noon": "الظهرية", "evening": "المسائية", "night": "الليلية"}
        await query.edit_message_text(f"✍️ <b>تعديل الرسالة {periods_ar[period]}:</b>\n\nأرسل الآن النص الجديد (يمكنك استخدام HTML):")

    elif data == "close_panel":
        await query.edit_message_text("🔒 تم إغلاق لوحة التحكم.")

    elif data == "back_to_admin":
        await query.edit_message_text(f"<b>مرحباً بك مجدداً يا دكتور {query.from_user.first_name}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")

# --------------------------------------------------------------------------
# --- [ معالج الرسائل النصية (Message Handler) ] ---
# --------------------------------------------------------------------------
# ملاحظة هامة: يجب أن يكون السطر التالي في أعلى الملف تماماً خارج كل الدوال:
async def handle_contact_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة كافة الرسائل النصية والربط مع محرك g4f لخدمة الطلاب مع بقاء مهام المسؤول كاملة"""
    
    if not update.message: return
    
    # تنظيف النص من المسافات فور وصوله
    text = update.message.text.strip() if update.message.text else ""
    user = update.effective_user
    bot_token = context.bot.token
    
    # محاولة جلب الإعدادات ومعرف المسؤول
    try:
        from sheets import get_bot_config
        config = get_bot_config(bot_token)
        bot_owner_id = int(config.get("admin_ids", 0))
    except Exception as e:
        print(f"⚠️ Error getting config: {e}")
        bot_owner_id = 0 # قيمة افتراضية في حال فشل الجلب
        
    action = context.user_data.get('action')

# --------------------------------------------------------------------------
#معالجة المستندات 
    if update.message.document:
        action = context.user_data.get('action')
        doc = update.message.document
        
        if action == 'awaiting_excel_file':
            import pandas as pd
            import os, uuid
            from sheets import add_new_course, add_new_category
            
            # تحميل الملف مؤقتاً
            file = await context.bot.get_file(doc.file_id)
            file_path = f"temp_{uuid.uuid4().hex}_{doc.file_name}"
            await file.download_to_drive(file_path)
            
            try:
                # فتح ملف الإكسل للوصول لكافة الصفحات
                xls = pd.ExcelFile(file_path)
                
                # --- 1. معالجة ورقة الأقسام أولاً (لضمان وجود الأكواد) ---
                cat_count = 0
                if 'الأقسام' in xls.sheet_names:
                    df_cats = pd.read_excel(xls, 'الأقسام').fillna("")
                    for _, r in df_cats.iterrows():
                        c_id = str(r.get('معرف_القسم', '')).strip()
                        c_name = str(r.get('اسم_القسم', '')).strip()
                        if c_id and c_name:
                            # إضافة القسم لجدول "الأقسام" في جوجل شيت
                            if add_new_category(bot_token, c_id, c_name):
                                cat_count += 1

                # --- 2. معالجة ورقة الدورات ثانياً ---
                course_count = 0
                if 'الدورات' in xls.sheet_names:
                    df_courses = pd.read_excel(xls, 'الدورات').fillna("")
                    for _, r in df_courses.iterrows():
                        course_id = f"CRS{str(uuid.uuid4().int)[:4]}"
                        # إرسال الـ 17 متغيراً بالترتيب الصحيح لورقة "الدورات_التدريبية"
                        success = add_new_course(
                            bot_token, course_id, str(r.get('الاسم', '')), str(r.get('الوصف', '')),
                            "2026-01-01", "", "أونلاين", str(r.get('السعر', '0')), 
                            "100", "لا يوجد", "إدارة المنصة", "ADMIN01", "رفع شامل", 
                            "ملف", str(r.get('ID_المدرب', '')), "مدرب", str(r.get('ID_القسم', ''))
                        )
                        if success: course_count += 1
                
                await update.message.reply_text(
                    f"✅ <b>تم التحديث بنجاح!</b>\n\n"
                    f"📁 الأقسام الجديدة المضافة: {cat_count}\n"
                    f"📚 الدورات الجديدة المضافة: {course_count}",
                    parse_mode="HTML"
                )
            except Exception as e:
                await update.message.reply_text(f"❌ خطأ في معالجة الملف الشامل: {str(e)}")
            finally:
                if os.path.exists(file_path): os.remove(file_path) # حذف الملف المؤقت
            
            context.user_data['action'] = None
            return



# --------------------------------------------------------------------------
    # --- [ الجزء الخاص بالمسؤول - إدارة المحتوى والدورات ] ---
    if user.id == bot_owner_id:
        # إضافة قسم جديد
        if action == 'awaiting_cat_name':
            import uuid
            cat_id = f"C{str(uuid.uuid4().int)[:4]}"
            from sheets import add_new_category
            if add_new_category(bot_token, cat_id, text):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إنشاء القسم بنجاح: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return
            
        # تعديل اسم قسم
        elif action == 'awaiting_new_cat_name':
            cat_id = context.user_data.get('selected_cat_id')
            from sheets import update_category_name
            if update_category_name(bot_token, cat_id, text):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم تحديث اسم القسم إلى: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # إضافة دورة بسيطة
        elif action == 'awaiting_course_name':
            import uuid
            course_cat = context.user_data.get('temp_course_cat')
            course_id = f"CRS{str(uuid.uuid4().int)[:4]}"
            from sheets import add_new_course
            if add_new_course(bot_token, course_id, text, course_cat):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إضافة الدورة بنجاح: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # تسلسل إضافة دورة احترافي (الخطوة 2: الاسم)
        elif action == 'awaiting_crs_name':
            context.user_data['temp_crs'] = {'name': text}
            context.user_data['action'] = 'awaiting_crs_hours'
            await update.message.reply_text("⏳ <b>الخطوة 3:</b> أرسل عدد ساعات الدورة (أو وصفاً قصيراً):", parse_mode="HTML")
            return

        # الخطوة 3: الساعات
        elif action == 'awaiting_crs_hours':
            context.user_data['temp_crs']['hours'] = text
            context.user_data['action'] = 'awaiting_crs_price'
            await update.message.reply_text("💰 <b>الخطوة 4:</b> أرسل سعر الدورة (أرقام فقط):", parse_mode="HTML")
            return

        # الخطوة 4: السعر وعرض خيارات المدربين
        elif action == 'awaiting_crs_price':
            context.user_data['temp_crs']['price'] = text
            from sheets import get_all_coaches
            coaches = get_all_coaches(bot_token)
            
            msg = "👨‍🏫 <b>الخطوة 5:</b> اختر المدرب من القائمة أدناه، أو أرسل (يوزرنايم/ID) يدوي:"
            keyboard = []
            if coaches:
                for c in coaches:
                    keyboard.append([InlineKeyboardButton(f"👤 {c['name']}", callback_data=f"sel_coach_for_crs_{c['id']}")])
            
            keyboard.append([InlineKeyboardButton("❌ إلغاء العملية", callback_data="manage_courses")])
            context.user_data['action'] = 'awaiting_crs_coach'
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        # الخطوة 5: استقبال المدرب
        elif action == 'awaiting_crs_coach':
            input_val = text
            if input_val.isdigit():
                context.user_data['temp_crs'].update({'coach_user': "إدخال يدوي", 'coach_id': input_val, 'coach_name': f"مدرب (ID: {input_val})"})
                context.user_data['action'] = 'awaiting_crs_date'
                await update.message.reply_text(f"✅ تم قبول المعرف: <code>{input_val}</code>\n\n🗓 <b>الخطوة 6:</b> أرسل تاريخ بداية الدورة:", parse_mode="HTML")
            else:
                coach_username = input_val.replace("@", "")
                from sheets import find_user_by_username
                user_data = find_user_by_username(bot_token, coach_username)
                if user_data:
                    context.user_data['temp_crs'].update({'coach_user': f"@{coach_username}", 'coach_id': user_data['id'], 'coach_name': user_data['name']})
                else:
                    try:
                        coach_chat = await context.bot.get_chat(f"@{coach_username}")
                        context.user_data['temp_crs'].update({'coach_user': f"@{coach_username}", 'coach_id': coach_chat.id, 'coach_name': coach_chat.full_name})
                    except:
                        await update.message.reply_text("❌ لم أستطع العثور عليه. أرسل **المعرف الرقمي** للمدرب الآن:")
                        return
                context.user_data['action'] = 'awaiting_crs_date'
                await update.message.reply_text(f"✅ تم العثور على: {context.user_data['temp_crs']['coach_name']}\n\n🗓 <b>الخطوة 6:</b> أرسل تاريخ البداية:")
            return

        # الخطوة 6: التاريخ والمراجعة
        elif action == 'awaiting_crs_date':
            context.user_data['temp_crs']['start_date'] = text
            d = context.user_data['temp_crs']
            summary = (
                f"📝 <b>مراجعة بيانات الدورة:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📂 القسم: {context.user_data.get('temp_crs_cat')}\n"
                f"📚 الاسم: {d['name']}\n"
                f"⏳ الساعات: {d['hours']}\n"
                f"💰 السعر: {d['price']}\n"
                f"👨‍🏫 المدرب: {d['coach_name']}\n"
                f"🗓 البداية: {text}\n"
                f"━━━━━━━━━━━━━━\n"
                f"<b>هل البيانات صحيحة؟</b>"
            )
            keyboard = [[InlineKeyboardButton("✅ نعم، اعتمد", callback_data="confirm_save_full_crs")], [InlineKeyboardButton("❌ إلغاء", callback_data="manage_courses")]]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return

        # تسلسل إضافة مدرب
        elif action == 'await_coach_name':
            context.user_data['temp_coach'] = {'name': text}
            context.user_data['action'] = 'await_coach_spec'
            await update.message.reply_text("🎓 <b>الخطوة 2:</b> أرسل تخصص المدرب:", parse_mode="HTML")
            return

        elif action == 'await_coach_spec':
            context.user_data['temp_coach']['spec'] = text
            context.user_data['action'] = 'await_coach_phone'
            await update.message.reply_text("📞 <b>الخطوة 3:</b> أرسل رقم هاتف المدرب:")
            return

        elif action == 'await_coach_phone':
            context.user_data['temp_coach']['phone'] = text
            context.user_data['action'] = 'await_coach_id'
            await update.message.reply_text("🆔 <b>الخطوة 4:</b> أرسل المعرف الرقمي (ID) للمدرب:", parse_mode="HTML")
            return

        elif action == 'await_coach_id':
            context.user_data['temp_coach']['id'] = text
            c = context.user_data['temp_coach']
            summary = (
                f"📝 <b>مراجعة بيانات المدرب:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"👨‍🏫 الاسم: {c['name']}\n"
                f"🎓 التخصص: {c['spec']}\n"
                f"📞 الهاتف: {c['phone']}\n"
                f"🆔 المعرف: <code>{c['id']}</code>\n"
                f"━━━━━━━━━━━━━━\n"
                f"<b>هل تريد حفظ المدرب في القاعدة؟</b>"
            )
            keyboard = [[InlineKeyboardButton("✅ نعم، احفظ", callback_data="confirm_save_coach")], [InlineKeyboardButton("❌ إلغاء", callback_data="manage_coaches")]]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return
# دالة الإضافة الجماعية
# --------------------------------------------------------------------------
        # --- [ محرك معالجة الإضافة الجماعية للدورات ] ---
        elif action == 'awaiting_bulk_courses':
            lines = text.split('\n')
            success_count = 0
            failed_lines = []
            from sheets import add_new_course
            import uuid

            for line in lines:
                if not line.strip(): continue # تخطي الأسطر الفارغة
                
                # تقسيم السطر بناءً على الفاصل الرأسي |
                parts = [p.strip() for p in line.split('|')]
                
                # التأكد من وجود الخمسة أجزاء المطلوبة حسب تعليماتك الجديدة
                if len(parts) >= 5:
                    c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
                    
                    # إرسال البيانات للدالة (الترتيب مطابق للـ 17 عمود في sheets.py)
                    success = add_new_course(
                        bot_token,          # 1. bot_id
                        c_id,               # 2. معرف_الدورة
                        parts[0],           # 3. اسم_الدورة
                        parts[1],           # 4. عدد_الساعات (الوصف والساعات)
                        "2026-01-01",       # 5. تاريخ_البداية (افتراضي)
                        "",                 # 6. تاريخ_النهاية
                        "أونلاين",          # 7. نوع_الدورة
                        parts[2],           # 8. سعر_الدورة
                        "100",              # 9. الحد_الأقصى
                        "لا يوجد",          # 10. المتطلبات
                        "إدارة المنصة",      # 11. اسم_المندوب
                        "ADMIN01",          # 12. كود_المندوب
                        "عام",              # 13. الحملة_التسويقية
                        "إدخال جماعي",      # 14. معرف_المدرب (يوزر)
                        parts[3],           # 15. ID_المدرب (المعرف الرقمي)
                        "مدرب معتمد",       # 16. اسم_المدرب (افتراضي)
                        parts[4]            # 17. معرف_القسم
                    )
                    
                    if success:
                        success_count += 1
                    else:
                        failed_lines.append(line)
                else:
                    failed_lines.append(line)

            context.user_data['action'] = None
            
            # رسالة النتيجة النهائية
            result_msg = f"✅ <b>تمت العملية بنجاح!</b>\n\n📥 عدد الدورات المضافة: {success_count}"
            if failed_lines:
                result_msg += f"\n⚠️ أسطر فشلت (تأكد من التنسيق):\n" + "\n".join(failed_lines)
            
            await update.message.reply_text(result_msg, reply_markup=get_admin_panel(), parse_mode="HTML")
            return

#-----
        elif action == 'awaiting_sheet_link':
            import re, uuid
            from sheets import client, add_new_course
            
            # استخراج ID الشيت من الرابط بدقة
            match = re.search(r"/d/([a-zA-Z0-9-_]+)", text)
            if not match:
                await update.message.reply_text("❌ رابط غير صحيح. أرسل رابط شيت صالح.")
                return

            try:
                external_ss = client.open_by_key(match.group(1))
                data = external_ss.get_worksheet(0).get_all_records()
                
                success_count = 0
                for r in data:
                    c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
                    success = add_new_course(
                        bot_token, c_id, str(r.get('اسم_الدورة', '')), str(r.get('الوصف', '')),
                        "2026-01-01", "", "أونلاين", str(r.get('السعر', '0')), 
                        "100", "لا يوجد", "إدارة المنصة", "ADMIN01", "رابط", 
                        "Sheet", str(r.get('ID_المدرب', '')), "مدرب", str(r.get('ID_القسم', ''))
                    )
                    if success: success_count += 1
                
                await update.message.reply_text(f"✅ تم سحب {success_count} دورة من الرابط.")
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الوصول للرابط: {str(e)}")
            context.user_data['action'] = None
            return


# --------------------------------------------------------------------------
        # --- [ حفظ كليشة الترحيب الجديدة ] ---
        elif action == 'awaiting_new_welcome_text':
            period = context.user_data.get('edit_period')
            column_name = f"welcome_{period}"
            from sheets import update_content_setting
            if update_content_setting(bot_token, column_name, text):
                await update.message.reply_text(f"✅ تم تحديث كليشة الترحيب <b>({period})</b> بنجاح!", reply_markup=get_admin_panel(), parse_mode="HTML")
                context.user_data['action'] = None
            else:
                await update.message.reply_text("❌ فشل التحديث. تأكد من إضافة الأعمدة المطلوبة.")
            return

        # 1. استقبال اسم المؤسسة (تم دمجه في تسلسل الإدارة)
        # 1. استقبال اسم المؤسسة
        elif action == 'awaiting_institution_name':
            from sheets import save_ai_setup
            if save_ai_setup(bot_token, user.id, user.username, institution_name=text):
                context.user_data['action'] = 'awaiting_ai_instructions'
                await update.message.reply_text(f"✅ تم حفظ الاسم: <b>{text}</b>\n\nالآن أرسل <b>تعليمات الذكاء الاصطناعي</b> للمنصة:")
            else:
                # إذا فشل الحفظ، البوت سيخبرك بدلاً من التهنيج
                await update.message.reply_text("❌ عذراً دكتور، فشل الحفظ في الشيت. تأكد من وجود ورقة 'الذكاء_الإصطناعي'.")
            return


        # 2. استقبال تعليمات AI
        elif action == 'awaiting_ai_instructions':
            from sheets import save_ai_setup
            if save_ai_setup(bot_token, user.id, user.username, ai_instructions=text):
                context.user_data['action'] = None
                await update.message.reply_text("🎊 <b>اكتملت التهيئة!</b> تم ضبط هوية البوت بنجاح.", reply_markup=get_admin_panel())
            return

    # --- [ جزء الطلاب والردود التفاعلية - g4f فقط ] ---
    if user.id != bot_owner_id:
        # 1. فحص الكلمات المفتاحية (FAQ) لسرعة الرد
        faq_keywords = {
            "طريقة الدفع": "💳 يمكنك الدفع عبر (زين كاش، بايبال، أو كروت التعبئة).",
            "تفعيل": "🎟 لتفعيل الدورة، يرجى إرسال الكود الذي حصلت عليه.",
            "قائمة": "📚 يمكنك استعراض كافة الدورات المتاحة عبر الزر المخصص."
        }
        for key, response in faq_keywords.items():
            if key in text:
                await update.message.reply_text(response)
                return

        # 2. إدارة ذاكرة المحادثة وجلب البيانات من الشيت
        global user_messages
        if user.id not in user_messages:
            user_messages[user.id] = []

        # جلب قاعدة المعرفة من الشيت
        from sheets import get_courses_knowledge_base
        courses_knowledge = get_courses_knowledge_base(bot_token)
        
        # إضافة رسالة الطالب للذاكرة
        user_messages[user.id].append({"role": "user", "content": text})
        
        # --- [ الجزء الديناميكي الجديد: جلب الهوية من الشيت ] ---
        from sheets import get_ai_setup
        ai_info = get_ai_setup(bot_token)
        platform = ai_info.get('اسم_المؤسسة', 'منصة الدكتور التعليمية') if ai_info else "منصة الدكتور التعليمية"
        rules = ai_info.get('تعليمات_AI', 'أجب بذكاء ولباقة واستخدم الرموز التعبيرية 🎓') if ai_info else "أجب بذكاء ولباقة"

        # بناء سياق المحادثة الكامل بالهوية الجديدة + الذاكرة
        messages_to_send = [
            {
                "role": "system", 
                "content": f"أنت المساعد الذكي الرسمي لـ {platform}. {rules}. إليك معلومات الدورات المتاحة حالياً:\n{courses_knowledge}"
            }
        ] + user_messages[user.id][-6:] # دمج الذاكرة لضمان استمرارية الحوار

        await update.message.reply_chat_action("typing")

        try:
            # استخدام g4f بشكل مباشر مع المزود التلقائي لضمان الاستقرار
            import g4f
            response = await g4f.ChatCompletion.create_async(
                model=g4f.models.default,
                messages=messages_to_send,
            )

            if response and len(response) > 0:
                # إضافة رد البوت للذاكرة وإرساله
                user_messages[user.id].append({"role": "assistant", "content": response})
                await update.message.reply_text(response)
                return
            else:
                raise Exception("Empty g4f Response")
            
        except Exception as e:
            # الخطة البديلة: إرسال تنبيه للدكتور في حال فشل المحرك
            print(f"❌ AI Error: {e}")
            info = f"📩 <b>استفسار طالب (فشل الـ AI):</b>\nالاسم: {user.full_name}\nالرسالة: {text}\nالخطأ: {str(e)}"
            try:
                await context.bot.send_message(chat_id=bot_owner_id, text=info, parse_mode="HTML")
                await update.message.reply_text("💡 شكراً لسؤالك! لقد استلمت استفسارك وسيقوم الدكتور بالرد عليك فوراً.")
            except:
                await update.message.reply_text("⚠️ المعذرة، هناك ضغط حالياً. يرجى المحاولة لاحقاً.")


# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
def main():
    TOKEN = "TOKEN_HERE" 
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CallbackQueryHandler(contact_callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact_message))
    application.run_polling()

if __name__ == '__main__':
    main()


# --------------------------------------------------------------------------

import os
import uuid
import pandas as pd
import io
import re
from datetime import datetime
import g4f
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# استيراد من sheets (تم حصر كل ما يستخدمه هذا الملف)
from sheets import (
    get_bot_config, 
    get_ai_setup, 
    save_ai_setup, 
    add_new_category, 
    get_employee_permissions, 
    update_category_name, 
    add_new_course, 
    get_all_coaches, 
    find_user_by_username, 
    record_student_submission, 
    get_student_enrollment_data, 
    get_courses_knowledge_base, 
    client, 
    get_now_date, 
    add_new_coach_advanced,
    update_content_setting # أضفتها لك هنا لدمجها
)

# الكتلة المدمجة لملف educational_manager.py 
from educational_manager import (
    validate_dsc_desc, 
    validate_dsc_value, 
    validate_dsc_expiry, 
    validate_dsc_max, 
    process_grp_name, 
    process_grp_days, 
    process_grp_time
)
# استيراد واجهات المستخدم (كما هي) 
from bot_callbacks import get_admin_panel, get_permissions_keyboard
# ذاكرة المحادثات (انتقلت هنا لتكون قريبة من المعالج)
user_messages = {}
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

        config = get_bot_config(bot_token)
        bot_owner_id = str(config.get("owner_id", "0"))
        admin_list = str(config.get("admin_ids", "0")).split(",")


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

            file = await context.bot.get_file(doc.file_id)
            file_path = f"temp_{uuid.uuid4().hex}_{doc.file_name}"
            await file.download_to_drive(file_path)
            
            try:
                xls = pd.ExcelFile(file_path)
                # --- [ مخازن الربط الذكي - القواميس ] ---
                cat_map = {}    # لربط اسم القسم بـ ID
                coach_map = {}  # لربط اسم المدرب بـ ID
                course_map = {} # لربط اسم الدورة بـ ID
                test_map = {}   # لربط اسم الاختبار بـ ID
                
                results = {"الأقسام": 0, "المدربين": 0, "الدورات": 0, "المجموعات": 0, "الطلاب": 0, "الاختبارات": 0, "الأسئلة": 0}

                # 1️⃣ معالجة الأقسام (الأساس)
                if 'الاقسام' in xls.sheet_names:
                    df = pd.read_excel(xls, 'الاقسام').fillna("")
                    for _, r in df.iterrows():
                        c_id = f"C{str(uuid.uuid4().int)[:4]}"
                        name = str(r.get('اسم_القسم', '')).strip()
                        if name and add_new_category(bot_token, c_id, name):
                            cat_map[name] = c_id
                            results["الأقسام"] += 1

                # 2️⃣ معالجة المدربين
                if 'المدربين' in xls.sheet_names:
                    df = pd.read_excel(xls, 'المدربين').fillna("")
                    for _, r in df.iterrows():
                        c_id = str(r.get('ID_المدرب', uuid.uuid4().int % 1000000000)).strip()
                        name = str(r.get('اسم_المدرب', '')).strip()
                        if name and add_new_coach_advanced(bot_token, c_id, name, str(r.get('التخصص', '')), str(r.get('رقم_الهاتف', ''))):
                            coach_map[name] = c_id
                            results["المدربين"] += 1

                # 3️⃣ معالجة الدورات (الربط بالأقسام والمدربين)
                if 'الدورات' in xls.sheet_names:
                    df = pd.read_excel(xls, 'الدورات').fillna("")
                    for _, r in df.iterrows():
                        c_id = f"CRS{str(uuid.uuid4().int)[:4]}"
                        c_name = str(r.get('الاسم', '')).strip()
                        # الربط الآلي: البحث عن ID القسم والمدرب باستخدام أسمائهم
                        cat_id = cat_map.get(str(r.get('اسم_القسم', '')).strip(), "C000")
                        coach_id = coach_map.get(str(r.get('اسم_المدرب', '')).strip(), "000")
                        
                        if add_new_course(bot_token, c_id, c_name, str(r.get('الوصف', '')), "2026-01-01", "", "أونلاين", 
                                         str(r.get('السعر', '0')), "100", "لا يوجد", "إدارة", "ADM", "رفع_شامل", 
                                         "Admin", coach_id, str(r.get('اسم_المدرب', '')), cat_id):
                            course_map[c_name] = c_id
                            results["الدورات"] += 1

                # 4️⃣ معالجة المجموعات والطلاب (الربط باسم الدورة)
                # يتم تكرار نفس النمط لبقية الـ 11 ورقة باستخدام course_map للربط
                
                report = "✅ <b>اكتمل الرفع والربط الشامل:</b>\n\n" + "\n".join([f"🔹 {k}: {v}" for k, v in results.items() if v > 0])
                await update.message.reply_text(report, parse_mode="HTML")

            except Exception as e:
                await update.message.reply_text(f"❌ خطأ حرج في المعالجة: {str(e)}")
            finally:
                if os.path.exists(file_path): os.remove(file_path)
            
            context.user_data['action'] = None
            return

            
            
           
# --------------------------------------------------------------------------
     
# --------------------------------------------------------------------------
    # --- [ الجزء الخاص بالمسؤول - إدارة المحتوى والدورات ] ---
    if user.id == bot_owner_id:
    	
    # --- [ معالجة خطوات إضافة كود الخصم نصياً ] ---
        if action == 'awaiting_dsc_desc':

            await validate_dsc_desc(update, context)
            return

        elif action == 'awaiting_dsc_value':

            await validate_dsc_value(update, context)
            return

        elif action == 'awaiting_dsc_expiry':

            await validate_dsc_expiry(update, context)
            return

        elif action == 'awaiting_dsc_max':

            await validate_dsc_max(update, context)
            return

   
    
    
        # إضافة قسم جديد
        if action == 'awaiting_cat_name':

            cat_id = f"C{str(uuid.uuid4().int)[:4]}"

            if add_new_category(bot_token, cat_id, text):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم إنشاء القسم بنجاح: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return
            

        # استقبال ID الموظف لفتح لوحة صلاحياته
        # استقبال ID الموظف لفتح لوحة صلاحياته (النسخة المعتمدة والأقوى)
        elif action == 'awaiting_emp_id_for_perms':
            emp_id = text
            context.user_data['action'] = None

            
            # جلب الصلاحيات الحالية من الشيت لعرض الأزرار بشكل صحيح
            current_perms = get_employee_permissions(bot_token, emp_id)
            
            await update.message.reply_text(
                f"🔐 <b>تم العثور على الموظف:</b> <code>{emp_id}</code>\n\n"
                f"قم بضبط الصلاحيات المطلوبة بالضغط على الأزرار أدناه:", 
                reply_markup=get_permissions_keyboard(bot_token, emp_id, current_perms), 
                parse_mode="HTML"
            )
            return

            
        # تعديل اسم قسم
        elif action == 'awaiting_new_cat_name':
            cat_id = context.user_data.get('selected_cat_id')

            if update_category_name(bot_token, cat_id, text):
                context.user_data['action'] = None
                await update.message.reply_text(f"✅ تم تحديث اسم القسم إلى: <b>{text}</b>", reply_markup=get_admin_panel(), parse_mode="HTML")
            return

        # إضافة دورة بسيطة
        elif action == 'awaiting_course_name':

            course_cat = context.user_data.get('temp_course_cat')
            course_id = f"CRS{str(uuid.uuid4().int)[:4]}"

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

# --------------------------------------------------------------------------
        # --- [ محرك معالجة الإضافة الجماعية للدورات ] ---
        elif action == 'awaiting_bulk_courses':
            lines = text.split('\n')
            success_count = 0
            failed_lines = []


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
# المجموعات 
# أضف هذا الجزء داخل handle_contact_message في education_bot.py

        elif action == 'awaiting_grp_name':

            await process_grp_name(update, context)
            return

        elif action == 'awaiting_grp_days':

            await process_grp_days(update, context)
            return

        elif action == 'awaiting_grp_time':

            await process_grp_time(update, context)
            return

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
        # --- [ حفظ كليشة الترحيب الجديدة ] ---
        elif action == 'awaiting_new_welcome_text':
            period = context.user_data.get('edit_period')
            column_name = f"welcome_{period}"

            if update_content_setting(bot_token, column_name, text):
                await update.message.reply_text(f"✅ تم تحديث كليشة الترحيب <b>({period})</b> بنجاح!", reply_markup=get_admin_panel(), parse_mode="HTML")
                context.user_data['action'] = None
            else:
                await update.message.reply_text("❌ فشل التحديث. تأكد من إضافة الأعمدة المطلوبة.")
            return

        # 1. استقبال اسم المؤسسة (تم دمجه في تسلسل الإدارة)
        # 1. استقبال اسم المؤسسة
        elif action == 'awaiting_institution_name':

            if save_ai_setup(bot_token, user.id, user.username, institution_name=text):
                context.user_data['action'] = 'awaiting_ai_instructions'
                await update.message.reply_text(f"✅ تم حفظ الاسم: <b>{text}</b>\n\nالآن أرسل <b>تعليمات الذكاء الاصطناعي</b> للمنصة:")
            else:
                # إذا فشل الحفظ، البوت سيخبرك بدلاً من التهنيج
                await update.message.reply_text("❌ عذراً دكتور، فشل الحفظ في الشيت. تأكد من وجود ورقة 'الذكاء_الإصطناعي'.")
            return


        # 2. استقبال تعليمات AI
        elif action == 'awaiting_ai_instructions':

            if save_ai_setup(bot_token, user.id, user.username, ai_instructions=text):
                context.user_data['action'] = None
                await update.message.reply_text("🎊 <b>اكتملت التهيئة!</b> تم ضبط هوية البوت بنجاح.", reply_markup=get_admin_panel())
            return
# --------------------------------------------------------------------------
        # تسلسل إضافة سؤال يدوي - استقبال نص السؤال
        elif action == 'awaiting_q_text':
            context.user_data['temp_q']['text'] = text
            context.user_data['action'] = 'awaiting_q_a'
            await update.message.reply_text("🔘 <b>الخطوة 3:</b> أرسل <b>الخيار (A)</b>:")
            return

        # استقبال الخيار A
        elif action == 'awaiting_q_a':
            context.user_data['temp_q']['a'] = text
            context.user_data['action'] = 'awaiting_q_b'
            await update.message.reply_text("🔘 <b>الخطوة 4:</b> أرسل <b>الخيار (B)</b>:")
            return

        # استقبال الخيار B
        elif action == 'awaiting_q_b':
            context.user_data['temp_q']['b'] = text
            context.user_data['action'] = 'awaiting_q_c'
            await update.message.reply_text("🔘 <b>الخطوة 5:</b> أرسل <b>الخيار (C)</b>:")
            return

        # استقبال الخيار C
        elif action == 'awaiting_q_c':
            context.user_data['temp_q']['c'] = text
            context.user_data['action'] = 'awaiting_q_d'
            await update.message.reply_text("🔘 <b>الخطوة 6:</b> أرسل <b>الخيار (D)</b>:")
            return

        # استقبال الخيار D وطلب الإجابة الصحيحة
        elif action == 'awaiting_q_d':
            context.user_data['temp_q']['d'] = text
            context.user_data['action'] = 'awaiting_q_correct'
            keyboard = [
                [InlineKeyboardButton("A", callback_data="set_q_ans_A"), InlineKeyboardButton("B", callback_data="set_q_ans_B")],
                [InlineKeyboardButton("C", callback_data="set_q_ans_C"), InlineKeyboardButton("D", callback_data="set_q_ans_D")]
            ]
            await update.message.reply_text(
                "✅ <b>الخطوة 7:</b> حدد <b>الإجابة الصحيحة</b> من الأزرار أدناه:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return

        # استقبال درجة السؤال
        elif action == 'awaiting_q_grade':
            if not text.isdigit():
                await update.message.reply_text("⚠️ يرجى إرسال أرقام فقط لدرجة السؤال:")
                return
            context.user_data['temp_q']['grade'] = text
            context.user_data['action'] = 'awaiting_q_level'
            keyboard = [
                [InlineKeyboardButton("سهل", callback_data="set_q_lv_سهل"), 
                 InlineKeyboardButton("متوسط", callback_data="set_q_lv_متوسط"),
                 InlineKeyboardButton("صعب", callback_data="set_q_lv_صعب")]
            ]
            await update.message.reply_text("📊 <b>الخطوة 9:</b> اختر <b>مستوى صعوبة</b> السؤال من الأزرار:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return



        # تسلسل إعدادات الاختبار الآلي
        elif action == 'awaiting_quiz_title':
            context.user_data['temp_quiz']['quiz_id'] = text
            context.user_data['action'] = 'awaiting_quiz_q_count'
            await update.message.reply_text("🔢 <b>الخطوة 4:</b> كم <b>عدد الأسئلة</b> التي تريد سحبها من البنك لهذا الاختبار؟")
            return

        elif action == 'awaiting_quiz_q_count':
            if not text.isdigit():
                await update.message.reply_text("⚠️ أرسل رقماً فقط:")
                return
            context.user_data['temp_quiz']['q_count'] = text
            context.user_data['action'] = 'awaiting_quiz_pass'
            await update.message.reply_text("🎯 <b>الخطوة 5:</b> حدد <b>درجة النجاح</b> (مثلاً: 50):")
            return

        elif action == 'awaiting_quiz_pass':
            context.user_data['temp_quiz']['pass_score'] = text
            context.user_data['action'] = 'awaiting_quiz_time'
            await update.message.reply_text("⏱ <b>الخطوة 6:</b> حدد <b>مدة الاختبار الكلية</b> بالدقائق:")
            return

        elif action == 'awaiting_quiz_time':
            context.user_data['temp_quiz']['duration'] = text
            q = context.user_data['temp_quiz']
            summary = (
                f"⚙️ <b>مراجعة إعدادات الاختبار:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📝 العنوان: {q['quiz_id']}\n"
                f"👥 المجموعات: {','.join(q['target_groups'])}\n"
                f"🔢 عدد الأسئلة: {q['q_count']}\n"
                f"🎯 النجاح من: {q['pass_score']}\n"
                f"⏱ المدة: {text} دقيقة\n"
                f"━━━━━━━━━━━━━━\n"
                f"هل تريد إنشاء الاختبار الآن؟"
            )
            keyboard = [
                [InlineKeyboardButton("✅ نعم، إنشاء", callback_data="exec_create_quiz_final")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="manage_control")]
            ]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return

# --------------------------------------------------------------------------
        # --- [ تسلسل إسناد واجب جديد - استقبال النصوص ] ---
        elif action == 'awaiting_hw_title':
            context.user_data['temp_hw']['title'] = text
            context.user_data['action'] = 'awaiting_hw_desc'
            await update.message.reply_text("📋 أرسل الآن <b>وصف الواجب</b> أو التعليمات المطلوبة من الطلاب:", parse_mode="HTML")
            return

        elif action == 'awaiting_hw_desc':
            context.user_data['temp_hw']['desc'] = text
            context.user_data['action'] = 'awaiting_hw_deadline'
            await update.message.reply_text("📅 أرسل الآن <b>آخر موعد للتسليم</b> (مثلاً: 2026-04-20):", parse_mode="HTML")
            return

        elif action == 'awaiting_hw_deadline':
            context.user_data['temp_hw']['deadline'] = text
            h = context.user_data['temp_hw']
            summary = (
                f"📑 <b>مراجعة إسناد الواجب:</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📘 الدورة: <code>{h['course_id']}</code>\n"
                f"👥 عدد المجموعات: <code>{len(h['target_groups'])}</code>\n"
                f"📌 العنوان: {h['title']}\n"
                f"⏰ موعد التسليم: {text}\n"
                f"━━━━━━━━━━━━━━\n"
                f"هل تريد تأكيد إرسال الواجب الآن؟"
            )
            keyboard = [[InlineKeyboardButton("✅ نعم، إسناد", callback_data="exec_save_hw_final")],
                        [InlineKeyboardButton("❌ إلغاء", callback_data="manage_homeworks")]]
            await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            context.user_data['action'] = None
            return



# --------------------------------------------------------------------------
    # --- [ جزء الطلاب والردود التفاعلية - g4f فقط ] ---
    
    # جلب إعدادات البوت أولاً لتعريف bot_owner_id قبل استخدامه في الشرط

    config = get_bot_config(bot_token)
    bot_owner_id = str(config.get("owner_id", "0"))
    admin_list = str(config.get("admin_ids", "0")).split(",")



    # تنفيذ الشرط: إذا كان المرسل ليس هو المالك (أي أنه طالب)
    if user.id != bot_owner_id:
        # --- [ معالجة تسليم الواجب ] ---
        if action == 'awaiting_solution':
            hw_id = context.user_data.get('target_hw_id')

            student = get_student_enrollment_data(bot_token, user.id)
            
            # تحديد نوع الملف والرابط [بند 3 في الوثيقة]
            file_link = "نص: " + text if text else "ملف/صورة"
            if update.message.document: file_link = f"وثيقة: {update.message.document.file_id}"
            elif update.message.photo: file_link = f"صورة: {update.message.photo[-1].file_id}"

            data = {
                'hw_id': hw_id, 'student_id': str(user.id),
                'course_id': student['course_id'], 'group_id': student['group_id'],
                'start_time': context.user_data.get('hw_start_time'),
                'file_link': file_link, 'branch_id': student.get('معرف_الفرع', '001')
            }

            if record_student_submission(bot_token, data):
                await update.message.reply_text("✅ <b>تم استلام حل الواجب بنجاح!</b>\nسيتم مراجعته من قبل المعلم وإشعارك بالنتيجة.", parse_mode="HTML")
                # إشعار الإدارة [رابعاً في الوثيقة]
                admin_notif = f"🔔 <b>تسليم جديد:</b>\nقام الطالب <b>{student['student_name']}</b> بتسليم واجب <code>{hw_id}</code>، يرجى التصحيح."
                try: await context.bot.send_message(chat_id=bot_owner_id, text=admin_notif, parse_mode="HTML")
                except: pass
            else:
                await update.message.reply_text("❌ فشل تسجيل التسليم، يرجى المحاولة لاحقاً.")
            
            context.user_data['action'] = None
            return 
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

        courses_knowledge = get_courses_knowledge_base(bot_token)
        
        # إضافة رسالة الطالب للذاكرة
        user_messages[user.id].append({"role": "user", "content": text})
        
        # --- [ الجزء الديناميكي الجديد: جلب الهوية من الشيت ] ---

        ai_info = get_ai_setup(bot_token)
        platform = ai_info.get('اسم_المؤسسة', 'منصة الادارة التعليمية') if ai_info else "منصة الادارة التعليمية"
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
            
        except Exception as e: # تصحيح الحرف الصغير هنا
            # الخطة البديلة: إرسال تنبيه للادارة في حال فشل المحرك
            print(f"❌ AI Error: {e}")
            
            # تم نقل جلب الإعدادات للأعلى لضمان توافر bot_owner_id
            info = f"📩 <b>استفسار طالب (فشل الـ AI):</b>\nالاسم: {user.full_name}\nالرسالة: {text}\nالخطأ: {str(e)}"
            
            try:
                # محاولة إرسال التنبيه للمالك إذا كان معرّفاً
                if bot_owner_id:
                    await context.bot.send_message(chat_id=bot_owner_id, text=info, parse_mode="HTML")
                
                # الرد على الطالب دائماً لضمان عدم بقاء المحادثة معلقة
                await update.message.reply_text("💡 شكراً لسؤالك! لقد استلمت استفسارك وسيقوم الادارة بالرد عليك فوراً.")
            except Exception as send_error:
                print(f"⚠️ فشل إرسال التنبيه للمالك: {send_error}")
                await update.message.reply_text("⚠️ المعذرة، هناك ضغط حالياً. يرجى المحاولة لاحقاً.")
               
               
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------



# --------------------------------------------------------------------------






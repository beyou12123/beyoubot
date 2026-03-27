import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from sheets import bots_sheet, get_bot_config # استدعاء البيانات من الشيت
import importlib

# إعداد السجلات لمراقبة أداء البوتات المشغلة
logging.basicConfig(level=logging.INFO)

def start_all_bots():
    """جلب كافة البوتات النشطة من الشيت وتشغيلها"""
    # جلب البيانات من ورقة "البوتات_المصنوعة"
    all_bots = bots_sheet.get_all_records()
    
    for bot_data in all_bots:
        if bot_data['حالة التشغيل'] == 'نشط':
            token = bot_data['التوكن']
            bot_type = bot_data['نوع البوت']
            owner_id = bot_data['ID المالك']
            
            # تشغيل البوت في عملية مستقلة أو Thread
            run_individual_bot(token, bot_type, owner_id)

def run_individual_bot(token, bot_type, owner_id):
    """تشغيل بوت واحد وربطه بالموديول المناسب"""
    app = ApplicationBuilder().token(token).build()
    
    # ربط الموديول ديناميكياً من مجلد modules
    # إذا أرسلت ملف contact.py سيتم استدعاؤه هنا
    module_name = ""
    if bot_type == "📩 تواصل": module_name = "modules.contact"
    elif bot_type == "🛡 حماية": module_name = "modules.protection"
    
    if module_name:
        module = importlib.import_module(module_name)
        # إضافة المعالجات الخاصة بالموديول
        if hasattr(module, 'handle_message'):
            app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), module.handle_message))
        if hasattr(module, 'start_handler'):
            app.add_handler(CommandHandler("start", module.start_handler))

    # تخزين معرف المالك في بيانات البوت ليعرف الموديول من هو المتحكم
    app.bot_data['owner_id'] = owner_id
    
    print(f"🚀 تم تشغيل بوت {bot_type} بنجاح للمالك {owner_id}")
    app.run_polling(close_loop=False)


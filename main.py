import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import g4f

# --- الإعدادات الأساسية ---
TOKEN = os.getenv("BOT_TOKEN") 
DB_DIR = "/data/vector_db" if os.path.exists("/data") else "vector_db"

# قاموس لتخزين ذاكرة المحادثات لكل مستخدم (تعدد المحادثات)
# الهيكل: {user_id: [قائمة الرسائل]}
chat_histories = {}

# إعداد المحرك التضميني
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# تهيئة قاعدة البيانات المتجهة للذاكرة الدائمة (المستندات)
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)
vector_db = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)

SYSTEM_PROMPT = "أنت مبرمج خبير. وظيفتك تحليل الكود فقط. استخدم السياق المرفق وتاريخ المحادثة بدقة للإجابة."

async def ask_g4f(prompt, context_data="", chat_history=None):
    """
    وظيفة التواصل مع g4f مع دعم الذاكرة والسياق
    """
    if chat_history is None:
        chat_history = []
        
    # بناء قائمة الرسائل المتكاملة للذكاء الاصطناعي
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nسياق المستندات المرفوعة:\n{context_data}"}]
    
    # إضافة تاريخ المحادثة (آخر 6 رسائل لضمان استقرار الأداء)
    messages.extend(chat_history[-6:])
    
    # إضافة الرسالة الحالية
    messages.append({"role": "user", "content": prompt})

    try:
        response = await g4f.ChatCompletion.create_async(
            model=g4f.models.default,
            messages=messages,
        )
        if response:
            # تحديث الذاكرة بالرد الجديد
            chat_history.append({"role": "user", "content": prompt})
            chat_history.append({"role": "assistant", "content": response})
            return response
        return "لم أستطع تحليل المعلومات، حاول مجدداً."
    except Exception as e:
        print(f"G4F Error: {e}")
        return "⚠️ خطأ في الاتصال بالذكاء الاصطناعي."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل مع دعم الذاكرة لكل مستخدم"""
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    user_query = update.message.text
    
    # تهيئة ذاكرة المستخدم إذا كان أول اتصال
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    
    # البحث في الذاكرة الدائمة للمستندات
    try:
        docs = vector_db.similarity_search(user_query, k=2)
        context_data = "\n".join([d.page_content for d in docs])
    except Exception as e:
        print(f"Chroma Search Error: {e}")
        context_data = ""
    
    await update.message.reply_chat_action("typing")
    
    # إرسال الطلب مع تاريخ المحادثة الخاص بهذا المستخدم تحديداً
    response = await ask_g4f(user_query, context_data, chat_histories[user_id])
    
    # إرسال الرد للمستخدم
    await update.message.reply_text(response)

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحليل المستندات وحفظها في الذاكرة الدائمة"""
    if not update.message.document:
        return

    doc = update.message.document
    try:
        f = await context.bot.get_file(doc.file_id)
        content_bytes = await f.download_as_bytearray()
        content = content_bytes.decode('utf-8', errors='ignore')
        
        # تقطيع النص لزيادة الدقة
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
        splits = text_splitter.create_documents([content])
        
        # الإضافة لقاعدة البيانات المتجهة
        vector_db.add_documents(splits)
        if hasattr(vector_db, 'persist'):
            vector_db.persist()
            
        await update.message.reply_text(f"✅ تم حفظ {doc.file_name} في الذاكرة الدائمة ومتاح لجميع محادثاتك.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ أثناء معالجة الملف: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء محادثة جديدة وتصفير الذاكرة المؤقتة لهذا المستخدم"""
    user_id = update.message.from_user.id
    chat_histories[user_id] = [] # تصفير التاريخ عند بدء محادثة جديدة
    await update.message.reply_text("أهلاً بك! تم فتح محادثة جديدة بذاكرة نظيفة. أنا جاهز لتحليل أكوادك.")

def main():
    if not TOKEN:
        print("BOT_TOKEN is missing!")
        return
        
    app = Application.builder().token(TOKEN).build()
    
    # المعالجات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
    
    print("البوت يعمل بذاكرة محادثات وتعدد مستخدمين...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

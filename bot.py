import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# بيانات القصص (يمكن استبدالها بقاعدة بيانات)
STORIES = {
    "قصص رعب": {
        "البيت المسكون": "كان هناك بيت قديم في نهاية القرية...",
        "المرأة في المرآة": "في كل ليلة، تظهر صورة امرأة في المرآة...",
        "النداء الغامض": "سمعت صوتاً ينادي اسمي من الغرفة الفارغة..."
    },
    "قصص رومانسية": {
        "لقاء مصادفي": "التقينا في يوم ممطر تحت المظلة...",
        "رسالة حب": "وجدت رسالة حب قديمة في كتاب المدرسة...",
        "الوعد": "وعدت بأن أعود، وبعد سنوات عدت..."
    },
    "قصص خيال علمي": {
        "المسافر عبر الزمن": "اكتشفت جهازاً يمكنه نقلي إلى أي زمان...",
        "الكائن الفضائي": "التقيت بكائن فضائي ودود في الحديقة...",
        "المدينة الذكية": "في المستقبل، حيث تحكم الآلات المدينة..."
    }
}

# لوحة المفاتيح الرئيسية
def main_keyboard():
    keyboard = [
        [KeyboardButton("📚 أقسام القصص")],
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحة أقسام القصص
def categories_keyboard():
    categories = list(STORIES.keys())
    keyboard = []
    
    # تقسيم الأزرار إلى صفوف كل صف فيه زرين
    for i in range(0, len(categories), 2):
        row = categories[i:i+2]
        keyboard.append([KeyboardButton(category) for category in row])
    
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحة القصص في قسم معين
def stories_keyboard(category):
    stories = list(STORIES[category].keys())
    keyboard = []
    
    for i in range(0, len(stories), 2):
        row = stories[i:i+2]
        keyboard.append([KeyboardButton(story) for story in row])
    
    keyboard.append([KeyboardButton("🔙 رجوع")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# أمر البدء
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    welcome_text = f"""
مرحباً {user.first_name}! 👋

🎭 **بوت القصص التفاعلي**
اختر من القصص المتنوعة والمثيرة

📖 **مميزات البوت:**
• قصص متنوعة في عدة أقسام
• واجهة سهلة بالأزرار
• تجربة قراءة ممتعة

اختر "📚 أقسام القصص" لبدء الرحلة!
    """
    await update.message.reply_text(welcome_text, reply_markup=main_keyboard())

# معالجة الرسائل
async def handle_message(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    
    if text == "🏠 الرئيسية":
        await update.message.reply_text(
            "تم العودة إلى الصفحة الرئيسية",
            reply_markup=main_keyboard()
        )
    
    elif text == "📚 أقسام القصص":
        await update.message.reply_text(
            "📚 **أقسام القصص المتاحة:**\nاختر القسم الذي تفضله:",
            reply_markup=categories_keyboard()
        )
    
    elif text == "🔙 رجوع":
        await update.message.reply_text(
            "📚 **أقسام القصص المتاحة:**",
            reply_markup=categories_keyboard()
        )
    
    elif text == "ℹ️ حول البوت":
        about_text = """
🤖 **حول بوت القصص**

• هذا البوت مخصص لعشاق القراءة والقصص
• يحتوي على مجموعة متنوعة من القصص
• واجهة سهلة الاستخدام

المطور: [اسمك]
        """
        await update.message.reply_text(about_text)
    
    elif text == "📞 اتصل بنا":
        contact_text = """
📞 **للتواصل معنا:**

✉️ Email: example@email.com
📱 Telegram: @username

نسعد بتواصلكم واقتراحاتكم!
        """
        await update.message.reply_text(contact_text)
    
    elif text in STORIES:
        # إذا كان الزر هو أحد الأقسام
        await update.message.reply_text(
            f"📖 **{text}**\nاختر القصة التي تريد قراءتها:",
            reply_markup=stories_keyboard(text)
        )
    
    else:
        # البحث عن القصة في جميع الأقسام
        for category, stories in STORIES.items():
            if text in stories:
                story_content = f"📖 **{text}**\n\n{stories[text]}\n\n---\nنهاية القصة 📚"
                await update.message.reply_text(
                    story_content,
                    reply_markup=stories_keyboard(category)
                )
                return
        
        # إذا لم يتم التعرف على الأمر
        await update.message.reply_text(
            "لم أفهم طلبك، يرجى استخدام الأزرار المتاحة",
            reply_markup=main_keyboard()
        )

# معالجة الأخطاء
async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"حدث خطأ: {context.error}")

# الدالة الرئيسية
def main():
    # الحصول على التوكن من متغير البيئة
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة")
    
    # إنشاء التطبيق
    application = Application.builder().token(token).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # بدء البوت
    port = int(os.environ.get('PORT', 8443))
    webhook_url = os.getenv('WEBHOOK_URL')
    
    if webhook_url:
        # استخدام webhook للاستضافة
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=f"{webhook_url}/{token}"
        )
    else:
        # استخدام polling للتطوير المحلي
        application.run_polling()

if __name__ == '__main__':
    main()

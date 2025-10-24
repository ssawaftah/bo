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

# بيانات القصص
STORIES = {
    "قصص رعب": {
        "البيت المسكون": "كان هناك بيت قديم في نهاية القرية...",
        "المرأة في المرآة": "في كل ليلة، تظهر صورة امرأة في المرآة...",
    },
    "قصص رومانسية": {
        "لقاء مصادفي": "التقينا في يوم ممطر تحت المظلة...",
        "رسالة حب": "وجدت رسالة حب قديمة في كتاب المدرسة...",
    }
}

# دوال لوحات المفاتيح (نفس الكود السابق)
def main_keyboard():
    keyboard = [
        [KeyboardButton("📚 أقسام القصص")],
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def categories_keyboard():
    categories = list(STORIES.keys())
    keyboard = []
    for i in range(0, len(categories), 2):
        row = categories[i:i+2]
        keyboard.append([KeyboardButton(category) for category in row])
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def stories_keyboard(category):
    stories = list(STORIES[category].keys())
    keyboard = []
    for i in range(0, len(stories), 2):
        row = stories[i:i+2]
        keyboard.append([KeyboardButton(story) for story in row])
    keyboard.append([KeyboardButton("🔙 رجوع")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# المعالجات (نفس الكود السابق)
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    welcome_text = f"""
مرحباً {user.first_name}! 👋

🎭 **بوت القصص التفاعلي**
اختر من القصص المتنوعة والمثيرة
    """
    await update.message.reply_text(welcome_text, reply_markup=main_keyboard())

async def handle_message(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    
    if text == "🏠 الرئيسية":
        await update.message.reply_text("تم العودة إلى الصفحة الرئيسية", reply_markup=main_keyboard())
    elif text == "📚 أقسام القصص":
        await update.message.reply_text("📚 أقسام القصص المتاحة:", reply_markup=categories_keyboard())
    elif text == "🔙 رجوع":
        await update.message.reply_text("📚 أقسام القصص المتاحة:", reply_markup=categories_keyboard())
    elif text in STORIES:
        await update.message.reply_text(f"📖 {text}\nاختر القصة:", reply_markup=stories_keyboard(text))
    else:
        for category, stories in STORIES.items():
            if text in stories:
                story_content = f"📖 {text}\n\n{stories[text]}\n\n---\nنهاية القصة 📚"
                await update.message.reply_text(story_content, reply_markup=stories_keyboard(category))
                return
        await update.message.reply_text("لم أفهم طلبك", reply_markup=main_keyboard())

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"حدث خطأ: {context.error}")

# الدالة الرئيسية المعدلة
def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("لم يتم تعيين TELEGRAM_BOT_TOKEN")
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    # استخدام polling بدلاً من webhook مؤقتاً
    logger.info("بدء البوت باستخدام polling...")
    application.run_polling()

if __name__ == '__main__':
    main()

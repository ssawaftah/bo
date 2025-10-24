import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
import os

# تفعيل اللوج
logging.basicConfig(level=logging.INFO)

# تحميل متغيرات البيئة
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# التحقق من التوكن
if not BOT_TOKEN:
    raise ValueError("يرجى وضع BOT_TOKEN في ملف .env")

# إنشاء بوت و Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# أمر /start
@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    await message.answer("مرحبًا! هذا بوت جديد باستخدام Aiogram 3.3 🚀")

# أمر /help
@dp.message(Command(commands=["help"]))
async def cmd_help(message: Message):
    help_text = (
        "قائمة الأوامر:\n"
        "/start - بدء البوت\n"
        "/help - عرض هذه الرسالة"
    )
    await message.answer(help_text)

# أي رسالة غير معروفة
@dp.message()
async def echo_message(message: Message):
    await message.answer(f"لم أفهم: {message.text}")

# تشغيل البوت
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))

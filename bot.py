import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# رسالة ترحيب
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("مرحبًا! البوت يعمل على Render 🚀")

# إعادة الرسائل
@dp.message()
async def echo(message: Message):
    await message.answer(f"أرسلت: {message.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))

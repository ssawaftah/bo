# bot.py
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
import asyncio
import os
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# إنشاء بوت و Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# رسالة الترحيب عند الضغط على /start
@dp.message(Command(commands=["start"]))
async def start_command(message: Message):
    await message.reply(f"أهلاً وسهلاً بك، {message.from_user.full_name} 🌸")

# تشغيل البوت
async def main():
    try:
        print("Bot is running...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply(f"أهلاً وسهلاً بك، {message.from_user.full_name} 🌸")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

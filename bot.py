import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

# توكن البوت من متغير البيئة
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("API_TOKEN not set in environment variables!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# بيانات وهمية للقصص
stories = {
    "خرافات": {
        "الثعلب والمكعب": "كان يا مكان...",
        "الأرنب والسلحفاة": "في قديم الزمان..."
    },
    "حكايات": {
        "القمر والعصفور": "ذات يوم..."
    }
}

# زر الصفحة الرئيسية
def main_menu():
    kb = InlineKeyboardMarkup()
    for section in stories.keys():
        kb.add(InlineKeyboardButton(section, callback_data=f"section_{section}"))
    return kb

# زر الرجوع
def back_button(to="main"):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("رجوع", callback_data=f"back_{to}"))
    return kb

# رسالة البدء
@dp.message()
async def handle_message(message: types.Message):
    if message.text == "/start":
        await message.answer("أهلاً بك في بوت القصص!", reply_markup=main_menu())

# التعامل مع أزرار القصص
@dp.callback_query()
async def handle_callbacks(call: types.CallbackQuery):
    data = call.data
    if data.startswith("section_"):
        section = data.split("_")[1]
        kb = InlineKeyboardMarkup()
        for title in stories[section]:
            kb.add(InlineKeyboardButton(title, callback_data=f"story_{section}_{title}"))
        kb.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        await call.message.edit_text(f"قسم {section}:", reply_markup=kb)

    elif data.startswith("story_"):
        _, section, title = data.split("_")
        await call.message.edit_text(stories[section][title], reply_markup=back_button(to=section))

    elif data.startswith("back_"):
        target = data.split("_")[1]
        if target == "main":
            await call.message.edit_text("الصفحة الرئيسية", reply_markup=main_menu())
        else:
            kb = InlineKeyboardMarkup()
            for title in stories[target]:
                kb.add(InlineKeyboardButton(title, callback_data=f"story_{target}_{title}"))
            kb.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
            await call.message.edit_text(f"قسم {target}:", reply_markup=kb)

# تشغيل البوت
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))

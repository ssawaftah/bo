from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = "YOUR_BOT_TOKEN"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

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

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("أهلاً بك في بوت القصص!", reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith("section_"))
async def show_stories(call: types.CallbackQuery):
    section = call.data.split("_")[1]
    kb = InlineKeyboardMarkup()
    for title in stories[section].keys():
        kb.add(InlineKeyboardButton(title, callback_data=f"story_{section}_{title}"))
    kb.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
    await call.message.edit_text(f"قسم {section}:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("story_"))
async def show_story(call: types.CallbackQuery):
    _, section, title = call.data.split("_")
    text = stories[section][title]
    await call.message.edit_text(text, reply_markup=back_button(to=section))

@dp.callback_query_handler(lambda c: c.data.startswith("back_"))
async def go_back(call: types.CallbackQuery):
    target = call.data.split("_")[1]
    if target == "main":
        await call.message.edit_text("الصفحة الرئيسية", reply_markup=main_menu())
    else:
        # الرجوع للقسم
        kb = InlineKeyboardMarkup()
        for title in stories[target].keys():
            kb.add(InlineKeyboardButton(title, callback_data=f"story_{target}_{title}"))
        kb.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        await call.message.edit_text(f"قسم {target}:", reply_markup=kb)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

TOKEN = "8380344606:AAH-23GbbdbRdwG6rnJmJ9UfRZ7X7uh2tE0"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ---------- البيانات ----------
sections = {
    "حكايات عربية": ["قصة 1", "قصة 2"],
    "حكايات عالمية": ["قصة 3", "قصة 4"]
}

stories = {
    "قصة 1": "نص قصة 1 ...",
    "قصة 2": "نص قصة 2 ...",
    "قصة 3": "نص قصة 3 ...",
    "قصة 4": "نص قصة 4 ..."
}

# ---------- أزرار ----------
def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📚 أقسام القصص", callback_data="sections"))
    kb.add(InlineKeyboardButton("ℹ️ عن البوت", callback_data="about"))
    return kb

def sections_menu():
    kb = InlineKeyboardMarkup()
    for section in sections.keys():
        kb.add(InlineKeyboardButton(section, callback_data=f"section_{section}"))
    kb.add(InlineKeyboardButton("🏠 رجوع", callback_data="home"))
    return kb

def stories_menu(section):
    kb = InlineKeyboardMarkup()
    for story in sections[section]:
        kb.add(InlineKeyboardButton(story, callback_data=f"story_{story}"))
    kb.add(InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="sections"))
    return kb

# ---------- البداية ----------
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("مرحبًا! اختر ما تريد:", reply_markup=main_menu())

# ---------- التعامل مع الأزرار ----------
@dp.callback_query_handler(lambda c: True)
async def callbacks(call: types.CallbackQuery):
    data = call.data

    if data == "home":
        await call.message.edit_text("مرحبًا! اختر ما تريد:", reply_markup=main_menu())
    elif data == "about":
        await call.message.edit_text("بوت للقصص بالكامل بالأزرار.", reply_markup=main_menu())
    elif data == "sections":
        await call.message.edit_text("اختر القسم:", reply_markup=sections_menu())
    elif data.startswith("section_"):
        section_name = data.split("_", 1)[1]
        await call.message.edit_text(f"اختر القصة من {section_name}:", reply_markup=stories_menu(section_name))
    elif data.startswith("story_"):
        story_name = data.split("_", 1)[1]
        await call.message.edit_text(stories[story_name], reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="sections")))

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

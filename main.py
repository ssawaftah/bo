import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# =============================
# إعداد البيئة
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("❌ تأكد من تعيين متغيرات البيئة BOT_TOKEN و ADMIN_ID في Render")

# =============================
# إعداد السجل (logging)
# =============================
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =============================
# قاعدة البيانات
# =============================
DB_PATH = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT,
            content TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    """)
    conn.commit()
    conn.close()

def db_execute(query, params=(), fetch=False, many=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if many:
        cur.executemany(query, params)
    else:
        cur.execute(query, params)
    data = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return data

# =============================
# دوال مساعدة
# =============================
def get_main_menu():
    cats = db_execute("SELECT name FROM categories", fetch=True)
    kb = InlineKeyboardBuilder()
    for (cat,) in cats:
        kb.button(text=cat, callback_data=f"cat:{cat}")
    return kb.adjust(2).as_markup() if cats else None

def get_story_menu(cat_name: str):
    cat_id = db_execute("SELECT id FROM categories WHERE name=?", (cat_name,), fetch=True)
    if not cat_id:
        return None
    cat_id = cat_id[0][0]
    stories = db_execute("SELECT title FROM stories WHERE category_id=?", (cat_id,), fetch=True)
    kb = InlineKeyboardBuilder()
    for (title,) in stories:
        kb.button(text=title, callback_data=f"story:{cat_name}:{title}")
    kb.button(text="🔙 رجوع", callback_data="back_main")
    return kb.adjust(2).as_markup()

# =============================
# /start للمستخدم
# =============================
@dp.message(CommandStart())
async def start_cmd(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "بدون_اسم"

    user = db_execute("SELECT status FROM users WHERE user_id=?", (user_id,), fetch=True)

    if user:
        status = user[0][0]
        if status == "approved":
            kb = get_main_menu()
            await message.answer("✅ مرحباً! يمكنك استخدام البوت.", reply_markup=kb)
        elif status == "pending":
            await message.answer("⏳ طلبك قيد الانتظار، في انتظار موافقة المدير.")
        else:
            await message.answer("🚫 تم حظرك من استخدام البوت.")
    else:
        db_execute("INSERT INTO users (user_id, username, status) VALUES (?, ?, ?)",
                   (user_id, username, "pending"))
        await message.answer("✋ طلبك تم تسجيله، في انتظار موافقة المدير.")
        await bot.send_message(
            ADMIN_ID,
            f"👤 طلب جديد لاستخدام البوت:\n\n"
            f"🆔 ID: {user_id}\n"
            f"📛 Username: @{username}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ موافقة", callback_data=f"approve:{user_id}"),
                 InlineKeyboardButton(text="❌ رفض", callback_data=f"reject:{user_id}")]
            ])
        )

# =============================
# موافقة / رفض المدير
# =============================
@dp.callback_query(F.data.startswith("approve:"))
async def approve_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    db_execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
    await bot.send_message(
        user_id,
        "✅ تم قبول طلبك! اضغط على 'ابدأ' لاستخدام البوت.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 ابدأ", callback_data="start_use")]
        ])
    )
    await callback.message.edit_text(f"✅ تم قبول المستخدم {user_id}")

@dp.callback_query(F.data.startswith("reject:"))
async def reject_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    db_execute("UPDATE users SET status='banned' WHERE user_id=?", (user_id,))
    await bot.send_message(user_id, "❌ تم رفض طلبك من قبل المدير.")
    await callback.message.edit_text(f"🚫 تم رفض المستخدم {user_id}")

# =============================
# بدء الاستخدام بعد الموافقة
# =============================
@dp.callback_query(F.data == "start_use")
async def start_use(callback: CallbackQuery):
    kb = get_main_menu()
    if not kb:
        await callback.message.answer("⚠️ لا توجد أقسام بعد.")
    else:
        await callback.message.answer("📚 اختر قسم القصص:", reply_markup=kb)

# =============================
# عرض الأقسام والقصص
# =============================
@dp.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    cat_name = callback.data.split(":")[1]
    kb = get_story_menu(cat_name)
    if kb:
        await callback.message.edit_text(f"📖 قسم: {cat_name}", reply_markup=kb)
    else:
        await callback.answer("🚫 لا توجد قصص في هذا القسم بعد.", show_alert=True)

@dp.callback_query(F.data.startswith("story:"))
async def show_story(callback: CallbackQuery):
    _, cat_name, title = callback.data.split(":")
    cat_id = db_execute("SELECT id FROM categories WHERE name=?", (cat_name,), fetch=True)
    if not cat_id:
        return
    cat_id = cat_id[0][0]
    story = db_execute("SELECT content FROM stories WHERE category_id=? AND title=?",
                       (cat_id, title), fetch=True)
    if story:
        content = story[0][0]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"cat:{cat_name}"),
             InlineKeyboardButton(text="🏠 الرئيسية", callback_data="back_main")]
        ])
        await callback.message.edit_text(f"📘 {title}\n\n{content}", reply_markup=kb)

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    kb = get_main_menu()
    await callback.message.edit_text("📚 اختر قسم القصص:", reply_markup=kb)

# =============================
# لوحة تحكم المدير
# =============================
@dp.message(F.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🚫 ليس لديك صلاحية الوصول لهذه المنطقة.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة قسم", callback_data="add_cat"),
         InlineKeyboardButton(text="➖ حذف قسم", callback_data="del_cat")],
        [InlineKeyboardButton(text="📖 إضافة قصة", callback_data="add_story")],
        [InlineKeyboardButton(text="📢 إرسال رسالة جماعية", callback_data="broadcast")]
    ])
    await message.answer("⚙️ لوحة تحكم المدير", reply_markup=kb)

# =============================
# تشغيل البوت
# =============================
async def main():
    init_db()
    logging.info("🚀 البوت يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

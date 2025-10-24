import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pydantic import BaseModel
from typing import Dict, List

# =============================
# تحميل الإعدادات من البيئة
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("❌ تأكد من تعيين متغيرات البيئة BOT_TOKEN و ADMIN_ID في Render")

# =============================
# إعداد السجل (logging)
# =============================
logging.basicConfig(level=logging.INFO)

# =============================
# إنشاء الكائنات الأساسية
# =============================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =============================
# قاعدة بيانات مؤقتة (في الذاكرة)
# =============================
class User(BaseModel):
    user_id: int
    username: str
    status: str  # pending | approved | banned

users: Dict[int, User] = {}
categories: Dict[str, List[Dict[str, str]]] = {}

# =============================
# دوال مساعدة
# =============================
def get_main_menu():
    kb = InlineKeyboardBuilder()
    for cat_name in categories.keys():
        kb.button(text=cat_name, callback_data=f"cat:{cat_name}")
    return kb.adjust(2).as_markup()

def get_story_menu(cat_name: str):
    kb = InlineKeyboardBuilder()
    for story in categories.get(cat_name, []):
        kb.button(text=story["title"], callback_data=f"story:{cat_name}:{story['title']}")
    kb.button(text="🔙 رجوع", callback_data="back_main")
    return kb.adjust(2).as_markup()

# =============================
# /start للمستخدم
# =============================
@dp.message(CommandStart())
async def start_cmd(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "بدون_اسم"

    if user_id in users:
        user = users[user_id]
        if user.status == "approved":
            await message.answer("✅ مرحباً! يمكنك استخدام البوت.", reply_markup=get_main_menu())
        elif user.status == "pending":
            await message.answer("⏳ طلبك قيد الانتظار، في انتظار موافقة المدير.")
        else:
            await message.answer("🚫 تم حظرك من استخدام البوت.")
    else:
        users[user_id] = User(user_id=user_id, username=username, status="pending")
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
# رد المدير على الطلب
# =============================
@dp.callback_query(F.data.startswith("approve:"))
async def approve_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    if user_id in users:
        users[user_id].status = "approved"
        await bot.send_message(user_id, "✅ تم قبول طلبك! اضغط على 'ابدأ' لاستخدام البوت.",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                   [InlineKeyboardButton(text="🚀 ابدأ", callback_data="start_use")]
                               ]))
        await callback.message.edit_text(f"✅ تم قبول المستخدم {user_id}")
    else:
        await callback.answer("❌ المستخدم غير موجود")

@dp.callback_query(F.data.startswith("reject:"))
async def reject_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    if user_id in users:
        users[user_id].status = "banned"
        await bot.send_message(user_id, "❌ تم رفض طلبك من قبل المدير.")
        await callback.message.edit_text(f"🚫 تم رفض المستخدم {user_id}")
    else:
        await callback.answer("❌ المستخدم غير موجود")

# =============================
# بدء الاستخدام بعد الموافقة
# =============================
@dp.callback_query(F.data == "start_use")
async def start_use(callback: CallbackQuery):
    await callback.message.answer("📚 اختر قسم القصص:", reply_markup=get_main_menu())

# =============================
# عرض قسم القصص
# =============================
@dp.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    cat_name = callback.data.split(":")[1]
    await callback.message.edit_text(f"📖 قسم: {cat_name}", reply_markup=get_story_menu(cat_name))

# =============================
# عرض محتوى القصة
# =============================
@dp.callback_query(F.data.startswith("story:"))
async def show_story(callback: CallbackQuery):
    _, cat_name, story_title = callback.data.split(":")
    story = next((s for s in categories.get(cat_name, []) if s["title"] == story_title), None)
    if story:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 رجوع", callback_data=f"cat:{cat_name}")
        kb.button(text="🏠 الرئيسية", callback_data="back_main")
        await callback.message.edit_text(f"📘 {story['title']}\n\n{story['content']}",
                                         reply_markup=kb.adjust(2).as_markup())

# =============================
# رجوع للرئيسية
# =============================
@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("📚 اختر قسم القصص:", reply_markup=get_main_menu())

# =============================
# واجهة المدير الأساسية
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
    logging.info("🚀 البوت يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

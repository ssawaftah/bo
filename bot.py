import os
import logging
import sqlite3
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# فئة قاعدة البيانات المطورة
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('stories_bot.db', check_same_thread=False)
        self.create_tables()
        self.create_admin()

    def create_tables(self):
        # جدول المستخدمين
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_approved INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول الأقسام
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_by INTEGER,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول القصص المطور
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                content_type TEXT DEFAULT 'text', -- text, video, photo
                file_id TEXT, -- لحفظ file_id للملفات
                category_id INTEGER,
                created_by INTEGER,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول طلبات الانضمام
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS join_requests (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def create_admin(self):
        admin_id = int(os.getenv('ADMIN_ID', 123456789))
        self.conn.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, is_approved, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (admin_id, 'admin', 'Admin', 'Bot', 1, 1))
        self.conn.commit()

    # دوال المستخدمين
    def add_user(self, user_id, username, first_name, last_name, is_approved=False, is_admin=False):
        self.conn.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, is_approved, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, is_approved, is_admin))
        self.conn.commit()

    def get_user(self, user_id):
        cursor = self.conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()

    def approve_user(self, user_id):
        self.conn.execute('UPDATE users SET is_approved = 1 WHERE user_id = ?', (user_id,))
        self.conn.execute('DELETE FROM join_requests WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def reject_user(self, user_id):
        self.conn.execute('DELETE FROM join_requests WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def get_all_users(self):
        cursor = self.conn.execute('SELECT * FROM users WHERE is_approved = 1')
        return cursor.fetchall()

    def get_pending_requests(self):
        cursor = self.conn.execute('SELECT * FROM join_requests')
        return cursor.fetchall()

    def delete_user(self, user_id):
        self.conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()

    # دوال الأقسام
    def add_category(self, name, created_by):
        self.conn.execute('INSERT OR IGNORE INTO categories (name, created_by) VALUES (?, ?)', (name, created_by))
        self.conn.commit()

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories')
        return cursor.fetchall()

    def get_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        return cursor.fetchone()

    def delete_category(self, category_id):
        self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.execute('DELETE FROM stories WHERE category_id = ?', (category_id,))
        self.conn.commit()

    # دوال القصص المطورة
    def add_story(self, title, content, content_type, file_id, category_id, created_by):
        self.conn.execute('''
            INSERT INTO stories (title, content, content_type, file_id, category_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, content, content_type, file_id, category_id, created_by))
        self.conn.commit()

    def get_stories_by_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM stories WHERE category_id = ?', (category_id,))
        return cursor.fetchall()

    def get_story(self, story_id):
        cursor = self.conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,))
        return cursor.fetchone()

    def get_all_stories(self):
        cursor = self.conn.execute('''
            SELECT s.*, c.name as category_name 
            FROM stories s 
            JOIN categories c ON s.category_id = c.id
        ''')
        return cursor.fetchall()

    def delete_story(self, story_id):
        self.conn.execute('DELETE FROM stories WHERE id = ?', (story_id,))
        self.conn.commit()

    def update_story(self, story_id, title, content):
        self.conn.execute('UPDATE stories SET title = ?, content = ? WHERE id = ?', (title, content, story_id))
        self.conn.commit()

# إنشاء قاعدة البيانات
db = Database()

# دوال المساعدة
def get_admin_id():
    return int(os.getenv('ADMIN_ID', 123456789))

def get_category_id_by_name(name):
    categories = db.get_categories()
    for cat in categories:
        if cat[1] == name:
            return cat[0]
    return None

def get_category_name_by_id(category_id):
    category = db.get_category(category_id)
    return category[1] if category else "غير معروف"

# لوحات المفاتيح للمستخدم العادي
def main_keyboard():
    keyboard = [
        [KeyboardButton("📚 أقسام القصص")],
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def categories_keyboard():
    categories = db.get_categories()
    keyboard = []
    for i in range(0, len(categories), 2):
        row = categories[i:i+2]
        keyboard.append([KeyboardButton(cat[1]) for cat in row])
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def stories_keyboard(category_id):
    stories = db.get_stories_by_category(category_id)
    keyboard = []
    for i in range(0, len(stories), 2):
        row = stories[i:i+2]
        keyboard.append([KeyboardButton(f"📖 {story[1]}") for story in row])
    keyboard.append([KeyboardButton("🔙 رجوع")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحات المفاتيح للمدير - المطورة
def admin_main_keyboard():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📖 إدارة القصص"), KeyboardButton("📊 إحصائيات")],
        [KeyboardButton("📢 إرسال إشعار"), KeyboardButton("🔙 وضع المستخدم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_users_keyboard():
    keyboard = [
        [KeyboardButton("📋 عرض المستخدمين"), KeyboardButton("⏳ طلبات الانضمام")],
        [KeyboardButton("🗑 حذف مستخدم"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_categories_keyboard():
    keyboard = [
        [KeyboardButton("➕ إضافة قسم"), KeyboardButton("🗑 حذف قسم")],
        [KeyboardButton("📋 عرض الأقسام"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_stories_keyboard():
    keyboard = [
        [KeyboardButton("➕ إضافة قصة"), KeyboardButton("✏️ تعديل قصة")],
        [KeyboardButton("🗑 حذف قصة"), KeyboardButton("📋 عرض القصص")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_add_story_keyboard():
    categories = db.get_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([KeyboardButton(f"📁 إضافة في {cat[1]}")])
    keyboard.append([KeyboardButton("🔙 إدارة القصص")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_story_type_keyboard():
    keyboard = [
        [KeyboardButton("📝 قصة نصية"), KeyboardButton("🎥 قصة فيديو")],
        [KeyboardButton("🖼️ قصة صورة"), KeyboardButton("🔙 إضافة قصة")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_edit_stories_keyboard():
    stories = db.get_all_stories()
    keyboard = []
    for story in stories:
        category_name = get_category_name_by_id(story[5])
        keyboard.append([KeyboardButton(f"✏️ {story[1]} - {category_name}")])
    keyboard.append([KeyboardButton("🔙 إدارة القصص")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_delete_stories_keyboard():
    stories = db.get_all_stories()
    keyboard = []
    for story in stories:
        category_name = get_category_name_by_id(story[5])
        keyboard.append([KeyboardButton(f"🗑 {story[1]} - {category_name}")])
    keyboard.append([KeyboardButton("🔙 إدارة القصص")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# معالجة الأوامر للمستخدمين
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    if user_id == get_admin_id():
        db.add_user(user_id, user.username, user.first_name, user.last_name, True, True)
        await update.message.reply_text(
            f"مرحباً آلة المدير {user.first_name}! 👑",
            reply_markup=admin_main_keyboard()
        )
        return
    
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    user_data = db.get_user(user_id)
    
    if user_data and user_data[4] == 1:
        await update.message.reply_text(
            f"مرحباً kembali {user.first_name}! 👋",
            reply_markup=main_keyboard()
        )
    else:
        db.conn.execute('''
            INSERT OR REPLACE INTO join_requests (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, user.username, user.first_name, user.last_name))
        db.conn.commit()
        
        admin_id = get_admin_id()
        keyboard = [
            [
                InlineKeyboardButton("✅ الموافقة", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 طلب انضمام جديد:\n\n👤 الاسم: {user.first_name} {user.last_name or ''}\n📱 username: @{user.username or 'لا يوجد'}\n🆔 ID: {user_id}",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة للمدير: {e}")
        
        await update.message.reply_text(
            "📋 تم إرسال طلب انضمامك إلى المدير. ستصلك رسالة تأكيد عند الموافقة على طلبك."
        )

# معالجة ضغطات الأزرار للمدير
async def handle_admin_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if user_id != get_admin_id():
        await query.edit_message_text("❌ ليس لديك صلاحية للقيام بهذا الإجراء.")
        return
    
    if data.startswith('approve_'):
        target_user_id = int(data.split('_')[1])
        db.approve_user(target_user_id)
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 تمت الموافقة على طلب انضمامك!\n\nانقر على الزر أدناه لبدء الاستخدام:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🚀 بدء الاستخدام")]], resize_keyboard=True)
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
        
        await query.edit_message_text(f"✅ تمت الموافقة على المستخدم {target_user_id}")
        
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        db.reject_user(target_user_id)
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")

# معالجة الوسائط (فيديوهات وصور)
async def handle_media(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    
    if user_id != get_admin_id():
        return
    
    # إذا كان المدير في وضع إضافة قصة
    if context.user_data.get('adding_story'):
        content_type = context.user_data.get('story_content_type')
        category_id = context.user_data.get('story_category_id')
        title = context.user_data.get('story_title')
        
        if content_type == 'video' and update.message.video:
            file_id = update.message.video.file_id
            # حفظ القصة
            db.add_story(title, "فيديو", "video", file_id, category_id, user_id)
            await update.message.reply_text(f"✅ تم إضافة القصة الفيديوية: {title}", reply_markup=admin_stories_keyboard())
            
        elif content_type == 'photo' and update.message.photo:
            file_id = update.message.photo[-1].file_id
            # حفظ القصة
            db.add_story(title, "صورة", "photo", file_id, category_id, user_id)
            await update.message.reply_text(f"✅ تم إضافة القصة المصورة: {title}", reply_markup=admin_stories_keyboard())
        
        # تنظيف البيانات المؤقتة
        context.user_data.pop('adding_story', None)
        context.user_data.pop('story_content_type', None)
        context.user_data.pop('story_category_id', None)
        context.user_data.pop('story_title', None)

# معالجة الرسائل للمستخدمين
async def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    # إذا كان المدير
    if user_id == get_admin_id():
        await handle_admin_message(update, context)
        return
    
    user_data = db.get_user(user_id)
    if not user_data or user_data[4] == 0:
        if text == "🚀 بدء الاستخدام":
            db.approve_user(user_id)
            await update.message.reply_text("🎉 أهلاً وسهلاً! تم تفعيل حسابك.", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("⏳ لم يتم الموافقة على حسابك بعد. انتظر الموافقة من المدير.")
        return
    
    # معالجة رسائل المستخدم العادي
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 الصفحة الرئيسية", reply_markup=main_keyboard())
    
    elif text == "🚀 بدء الاستخدام":
        await update.message.reply_text("أهلاً وسهلاً! 🌟", reply_markup=main_keyboard())
    
    elif text == "📚 أقسام القصص":
        categories = db.get_categories()
        if categories:
            await update.message.reply_text("📚 اختر قسم:", reply_markup=categories_keyboard())
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif text == "🔙 رجوع":
        await update.message.reply_text("📚 أقسام القصص:", reply_markup=categories_keyboard())
    
    elif text == "ℹ️ حول البوت":
        await update.message.reply_text("🤖 بوت القصص التفاعلي\nنسخة احترافية مع إدارة متكاملة")
    
    elif text == "📞 اتصل بنا":
        await update.message.reply_text("📞 للتواصل: @username")
    
    else:
        # البحث في الأقسام
        category_id = get_category_id_by_name(text)
        if category_id:
            stories = db.get_stories_by_category(category_id)
            if stories:
                await update.message.reply_text(f"📖 {text} - اختر قصة:", reply_markup=stories_keyboard(category_id))
            else:
                await update.message.reply_text(f"⚠️ لا توجد قصص في قسم {text}.")
            return
        
        # البحث في القصص (بإزالة الإيموجي)
        if text.startswith("📖 "):
            story_title = text[2:]  # إزالة الإيموجي
            all_stories = db.get_all_stories()
            for story in all_stories:
                if story[1] == story_title:
                    if story[3] == 'text':  # قصة نصية
                        await update.message.reply_text(f"📖 {story[1]}\n\n{story[2]}\n\n---\nنهاية القصة 📚")
                    elif story[3] == 'video':  # فيديو
                        await update.message.reply_video(story[4], caption=f"🎥 {story[1]}")
                    elif story[3] == 'photo':  # صورة
                        await update.message.reply_photo(story[4], caption=f"🖼️ {story[1]}")
                    return
        
        await update.message.reply_text("⚠️ لم أفهم طلبك.", reply_markup=main_keyboard())

# معالجة رسائل المدير المطورة
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if user_id != get_admin_id():
        await update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى لوحة التحكم.")
        return
    
    # نظام إضافة القصص المحسن
    if context.user_data.get('awaiting_story_title'):
        title = text
        context.user_data['story_title'] = title
        context.user_data['awaiting_story_title'] = False
        
        content_type = context.user_data.get('story_content_type')
        
        if content_type == 'text':
            await update.message.reply_text("📝 الآن أرسل محتوى القصة النصية:")
            context.user_data['awaiting_story_content'] = True
        else:
            # للفيديو أو الصورة
            context.user_data['adding_story'] = True
            if content_type == 'video':
                await update.message.reply_text("🎥 الآن أرسل الفيديو:")
            else:
                await update.message.reply_text("🖼️ الآن أرسل الصورة:")
    
    elif context.user_data.get('awaiting_story_content'):
        content = text
        title = context.user_data.get('story_title')
        category_id = context.user_data.get('story_category_id')
        
        # حفظ القصة النصية
        db.add_story(title, content, 'text', None, category_id, user_id)
        await update.message.reply_text(f"✅ تم إضافة القصة: {title}", reply_markup=admin_stories_keyboard())
        
        # تنظيف البيانات
        context.user_data.pop('awaiting_story_content', None)
        context.user_data.pop('story_title', None)
        context.user_data.pop('story_category_id', None)
    
    # الأوامر الرئيسية للمدير
    elif text == "🔙 وضع المستخدم":
        await update.message.reply_text("تم التبديل إلى وضع المستخدم", reply_markup=main_keyboard())
        return
    
    elif text == "👥 إدارة المستخدمين":
        await update.message.reply_text("👥 لوحة إدارة المستخدمين:", reply_markup=admin_users_keyboard())
    
    elif text == "📁 إدارة الأقسام":
        await update.message.reply_text("📁 لوحة إدارة الأقسام:", reply_markup=admin_categories_keyboard())
    
    elif text == "📖 إدارة القصص":
        await update.message.reply_text("📖 لوحة إدارة القصص:", reply_markup=admin_stories_keyboard())
    
    elif text == "🔙 لوحة التحكم":
        await update.message.reply_text("👑 لوحة تحكم المدير", reply_markup=admin_main_keyboard())
    
    elif text == "🔙 إدارة القصص":
        await update.message.reply_text("📖 لوحة إدارة القصص:", reply_markup=admin_stories_keyboard())
    
    elif text == "🔙 إضافة قصة":
        await update.message.reply_text("📖 اختر نوع القصة:", reply_markup=admin_story_type_keyboard())
    
    # إدارة القصص - النظام الجديد
    elif text == "➕ إضافة قصة":
        categories = db.get_categories()
        if not categories:
            await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
            return
        await update.message.reply_text("📁 اختر قسم لإضافة القصة:", reply_markup=admin_add_story_keyboard())
    
    elif text.startswith("📁 إضافة في "):
        category_name = text.replace("📁 إضافة في ", "")
        category_id = get_category_id_by_name(category_name)
        if category_id:
            context.user_data['story_category_id'] = category_id
            await update.message.reply_text("📖 اختر نوع القصة:", reply_markup=admin_story_type_keyboard())
        else:
            await update.message.reply_text("❌ قسم غير موجود")
    
    elif text == "📝 قصة نصية":
        context.user_data['story_content_type'] = 'text'
        await update.message.reply_text("📝 أرسل عنوان القصة:")
        context.user_data['awaiting_story_title'] = True
    
    elif text == "🎥 قصة فيديو":
        context.user_data['story_content_type'] = 'video'
        await update.message.reply_text("🎥 أرسل عنوان الفيديو:")
        context.user_data['awaiting_story_title'] = True
    
    elif text == "🖼️ قصة صورة":
        context.user_data['story_content_type'] = 'photo'
        await update.message.reply_text("🖼️ أرسل عنوان الصورة:")
        context.user_data['awaiting_story_title'] = True
    
    elif text == "🗑 حذف قصة":
        stories = db.get_all_stories()
        if stories:
            await update.message.reply_text("📖 اختر القصة للحذف:", reply_markup=admin_delete_stories_keyboard())
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    elif text.startswith("🗑 "):
        story_title = text.replace("🗑 ", "").split(" - ")[0]
        stories = db.get_all_stories()
        for story in stories:
            if story[1] == story_title:
                db.delete_story(story[0])
                await update.message.reply_text(f"✅ تم حذف القصة: {story_title}", reply_markup=admin_stories_keyboard())
                return
        await update.message.reply_text("❌ قصة غير موجودة")
    
    elif text == "✏️ تعديل قصة":
        stories = db.get_all_stories()
        if stories:
            await update.message.reply_text("📖 اختر القصة للتعديل:", reply_markup=admin_edit_stories_keyboard())
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    elif text.startswith("✏️ "):
        story_title = text.replace("✏️ ", "").split(" - ")[0]
        stories = db.get_all_stories()
        for story in stories:
            if story[1] == story_title:
                if story[3] == 'text':
                    await update.message.reply_text(f"📝 قصة: {story[1]}\n\nالمحتوى الحالي:\n{story[2]}\n\nأرسل المحتوى الجديد:")
                    context.user_data['editing_story_id'] = story[0]
                else:
                    await update.message.reply_text("⚠️ يمكن تعديل المحتوى النصي فقط حالياً.")
                return
        await update.message.reply_text("❌ قصة غير موجودة")
    
    elif context.user_data.get('editing_story_id'):
        story_id = context.user_data['editing_story_id']
        db.update_story(story_id, db.get_story(story_id)[1], text)  # الحفاظ على العنوان نفسه
        await update.message.reply_text("✅ تم تعديل القصة بنجاح", reply_markup=admin_stories_keyboard())
        context.user_data.pop('editing_story_id', None)
    
    # باقي أوامر المدير (نفس السابق)
    elif text == "📋 عرض القصص":
        stories = db.get_all_stories()
        if stories:
            stories_text = "📖 جميع القصص:\n\n"
            for story in stories:
                type_icon = "📝" if story[3] == 'text' else "🎥" if story[3] == 'video' else "🖼️"
                stories_text += f"{type_icon} {story[1]} - 📂 {story[6]}\n"
            await update.message.reply_text(stories_text)
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    # ... باقي الأوامر نفس الكود السابق
    
    else:
        await update.message.reply_text("👑 لوحة تحكم المدير", reply_markup=admin_main_keyboard())

# معالجة الأخطاء
async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"حدث خطأ: {context.error}")

# الدالة الرئيسية
def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("❌ لم يتم تعيين TELEGRAM_BOT_TOKEN")
    
    application = Application.builder().token(token).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_media))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت الاحترافي المطور...")
    application.run_polling()

if __name__ == '__main__':
    main()

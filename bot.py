
import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# فئة قاعدة البيانات
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('stories_bot.db', check_same_thread=False)
        self.create_tables()
        self.create_admin()

    def create_tables(self):
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
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                category_id INTEGER,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS join_requests (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        self.conn.commit()

    def create_admin(self):
        admin_id = int(os.getenv('ADMIN_ID', 123456789))
        self.conn.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, is_approved, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (admin_id, 'admin', 'Admin', 'Bot', 1, 1))
        
        # الإعدادات الافتراضية
        default_settings = [
            ('welcome_message', 'مرحباً بك في بوت القصص! 🎭'),
            ('approval_required', '1'),
            ('about_text', '🤖 بوت القصص التفاعلي'),
            ('contact_text', '📞 للتواصل: @username'),
            ('start_button_text', '🚀 بدء الاستخدام')
        ]
        for key, value in default_settings:
            self.conn.execute('INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)', (key, value))
        self.conn.commit()

    def get_setting(self, key):
        cursor = self.conn.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else None

    def update_setting(self, key, value):
        self.conn.execute('UPDATE bot_settings SET value = ? WHERE key = ?', (value, key))
        self.conn.commit()

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

    def add_category(self, name):
        self.conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (name,))
        self.conn.commit()

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories')
        return cursor.fetchall()

    def delete_category(self, category_id):
        self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.execute('DELETE FROM stories WHERE category_id = ?', (category_id,))
        self.conn.commit()

    def add_story(self, title, content, category_id):
        self.conn.execute('INSERT INTO stories (title, content, category_id) VALUES (?, ?, ?)', (title, content, category_id))
        self.conn.commit()

    def get_stories_by_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM stories WHERE category_id = ?', (category_id,))
        return cursor.fetchall()

    def get_all_stories(self):
        cursor = self.conn.execute('SELECT s.*, c.name as category_name FROM stories s JOIN categories c ON s.category_id = c.id')
        return cursor.fetchall()

    def delete_story(self, story_id):
        self.conn.execute('DELETE FROM stories WHERE id = ?', (story_id,))
        self.conn.commit()

db = Database()

# دوال المساعدة
def get_admin_id():
    return int(os.getenv('ADMIN_ID', 123456789))

def is_admin(user_id):
    return user_id == get_admin_id()

def get_category_id_by_name(name):
    categories = db.get_categories()
    for cat in categories:
        if cat[1] == name:
            return cat[0]
    return None

# لوحات المفاتيح للمستخدم
def main_keyboard():
    keyboard = [
        [KeyboardButton("📚 أقسام القصص")],
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def start_keyboard():
    start_text = db.get_setting('start_button_text') or '🚀 بدء الاستخدام'
    return ReplyKeyboardMarkup([[KeyboardButton(start_text)]], resize_keyboard=True)

def categories_keyboard():
    categories = db.get_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([KeyboardButton(cat[1])])
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحات المفاتيح للمدير - مبسطة
def admin_main_keyboard():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📖 إدارة القصص"), KeyboardButton("⚙️ الإعدادات")],
        [KeyboardButton("📊 الإحصائيات"), KeyboardButton("📢 البث الجماعي")],
        [KeyboardButton("🔙 وضع المستخدم")]
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
        [KeyboardButton("➕ إضافة قصة"), KeyboardButton("🗑 حذف قصة")],
        [KeyboardButton("📋 عرض القصص"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_settings_keyboard():
    keyboard = [
        [KeyboardButton("✏️ تعديل رسالة الترحيب"), KeyboardButton("📝 تعديل حول البوت")],
        [KeyboardButton("📞 تعديل اتصل بنا"), KeyboardButton("🔄 تعديل زر البدء")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# معالجة START
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    context.user_data.clear()
    
    if is_admin(user_id):
        await update.message.reply_text(
            f"👑 **مرحباً بك آلة المدير!**\n\nلوحة التحكم جاهزة.",
            reply_markup=admin_main_keyboard()
        )
        return
    
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    user_data = db.get_user(user_id)
    
    if user_data and user_data[4] == 1:
        welcome_message = db.get_setting('welcome_message') or 'مرحباً بك!'
        await update.message.reply_text(
            f"{welcome_message}\nمرحباً kembali {user.first_name}! 👋",
            reply_markup=main_keyboard()
        )
    else:
        # إرسال طلب انضمام للمدير
        db.conn.execute('INSERT OR REPLACE INTO join_requests (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
                       (user_id, user.username, user.first_name, user.last_name))
        db.conn.commit()
        
        admin_id = get_admin_id()
        keyboard = [
            [InlineKeyboardButton("✅ الموافقة", callback_data=f"approve_{user_id}"),
             InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 طلب انضمام جديد:\n👤 {user.first_name}\n📱 @{user.username or 'لا يوجد'}\n🆔 {user_id}",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة للمدير: {e}")
        
        await update.message.reply_text(
            "📋 تم إرسال طلب انضمامك إلى المدير. انتظر الموافقة.",
            reply_markup=start_keyboard()
        )

# معالجة Callback للمدير
async def handle_admin_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("❌ ليس لديك صلاحية.")
        return
    
    if data.startswith('approve_'):
        target_user_id = int(data.split('_')[1])
        db.approve_user(target_user_id)
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 تمت الموافقة على طلبك!",
                reply_markup=main_keyboard()
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
        
        await query.edit_message_text(f"✅ تمت الموافقة على المستخدم {target_user_id}")
        
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        db.reject_user(target_user_id)
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")

# معالجة رسائل المدير
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if not is_admin(user_id):
        return

    # تنظيف الحالات
    if text in ["🔙 لوحة التحكم", "🏠 الرئيسية"]:
        context.user_data.clear()

    # الأوامر الرئيسية
    if text == "🔙 وضع المستخدم":
        context.user_data.clear()
        await update.message.reply_text("تم التبديل إلى وضع المستخدم", reply_markup=main_keyboard())
    
    elif text == "👥 إدارة المستخدمين":
        await update.message.reply_text("👥 إدارة المستخدمين:", reply_markup=admin_users_keyboard())
    
    elif text == "📁 إدارة الأقسام":
        await update.message.reply_text("📁 إدارة الأقسام:", reply_markup=admin_categories_keyboard())
    
    elif text == "📖 إدارة القصص":
        await update.message.reply_text("📖 إدارة القصص:", reply_markup=admin_stories_keyboard())
    
    elif text == "⚙️ الإعدادات":
        await update.message.reply_text("⚙️ الإعدادات:", reply_markup=admin_settings_keyboard())
    
    elif text == "📊 الإحصائيات":
        users_count = len(db.get_all_users())
        stories_count = len(db.get_all_stories())
        pending_count = len(db.get_pending_requests())
        
        stats_text = f"📊 الإحصائيات:\n👥 المستخدمين: {users_count}\n📖 القصص: {stories_count}\n⏳ في الانتظار: {pending_count}"
        await update.message.reply_text(stats_text)
    
    elif text == "📢 البث الجماعي":
        await update.message.reply_text("أرسل الرسالة للبث الجماعي:")
        context.user_data['broadcasting'] = True
    
    # إدارة المستخدمين
    elif text == "📋 عرض المستخدمين":
        users = db.get_all_users()
        if users:
            users_text = "👥 المستخدمين:\n\n"
            for user_data in users:
                users_text += f"🆔 {user_data[0]} - 👤 {user_data[2]}\n"
            await update.message.reply_text(users_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد مستخدمين.")
    
    elif text == "⏳ طلبات الانضمام":
        requests = db.get_pending_requests()
        if requests:
            req_text = "📩 طلبات الانضمام:\n\n"
            for req in requests:
                req_text += f"🆔 {req[0]} - 👤 {req[2]}\n"
            await update.message.reply_text(req_text)
        else:
            await update.message.reply_text("✅ لا توجد طلبات.")
    
    elif text == "🗑 حذف مستخدم":
        await update.message.reply_text("أرسل ID المستخدم للحذف:")
        context.user_data['awaiting_user_id'] = True
    
    # إدارة الأقسام
    elif text == "📋 عرض الأقسام":
        categories = db.get_categories()
        if categories:
            cats_text = "📁 الأقسام:\n\n"
            for cat in categories:
                cats_text += f"📂 {cat[1]}\n"
            await update.message.reply_text(cats_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    elif text == "➕ إضافة قسم":
        await update.message.reply_text("أرسل اسم القسم الجديد:")
        context.user_data['adding_category'] = True
    
    elif text == "🗑 حذف قسم":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                keyboard.append([KeyboardButton(f"حذف {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة الأقسام")])
            await update.message.reply_text("اختر قسم للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    # إدارة القصص
    elif text == "📋 عرض القصص":
        stories = db.get_all_stories()
        if stories:
            stories_text = "📖 القصص:\n\n"
            for story in stories:
                stories_text += f"📚 {story[1]} - {story[4]}\n"
            await update.message.reply_text(stories_text)
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    elif text == "➕ إضافة قصة":
        categories = db.get_categories()
        if not categories:
            await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
            return
        await update.message.reply_text("أرسل القصة بالتنسيق:\nالقسم: اسم القسم\nالعنوان: عنوان القصة\nالمحتوى: محتوى القصة")
        context.user_data['adding_story'] = True
    
    elif text == "🗑 حذف قصة":
        stories = db.get_all_stories()
        if stories:
            keyboard = []
            for story in stories:
                keyboard.append([KeyboardButton(f"حذف {story[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة القصص")])
            await update.message.reply_text("اختر قصة للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    # الإعدادات
    elif text == "✏️ تعديل رسالة الترحيب":
        current = db.get_setting('welcome_message') or 'مرحباً بك!'
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_welcome'] = True
    
    elif text == "📝 تعديل حول البوت":
        current = db.get_setting('about_text') or 'بوت القصص'
        await update.message.reply_text(f"النص الحالي:\n{current}\n\nأرسل النص الجديد:")
        context.user_data['editing_about'] = True
    
    elif text == "📞 تعديل اتصل بنا":
        current = db.get_setting('contact_text') or 'للتواصل: @username'
        await update.message.reply_text(f"النص الحالي:\n{current}\n\nأرسل النص الجديد:")
        context.user_data['editing_contact'] = True
    
    elif text == "🔄 تعديل زر البدء":
        current = db.get_setting('start_button_text') or '🚀 بدء الاستخدام'
        await update.message.reply_text(f"النص الحالي: {current}\n\nأرسل النص الجديد:")
        context.user_data['editing_start_button'] = True
    
    # معالجة إدخال البيانات
    elif context.user_data.get('awaiting_user_id'):
        try:
            target_user_id = int(text)
            db.delete_user(target_user_id)
            await update.message.reply_text(f"✅ تم حذف المستخدم {target_user_id}", reply_markup=admin_users_keyboard())
        except:
            await update.message.reply_text("❌ ID غير صحيح", reply_markup=admin_users_keyboard())
        context.user_data.clear()
    
    elif context.user_data.get('adding_category'):
        db.add_category(text)
        await update.message.reply_text(f"✅ تم إضافة القسم: {text}", reply_markup=admin_categories_keyboard())
        context.user_data.clear()
    
    elif context.user_data.get('adding_story'):
        try:
            lines = text.split('\n')
            category_name = lines[0].replace('القسم:', '').strip()
            title = lines[1].replace('العنوان:', '').strip()
            content = lines[2].replace('المحتوى:', '').strip()
            
            category_id = get_category_id_by_name(category_name)
            if category_id:
                db.add_story(title, content, category_id)
                await update.message.reply_text(f"✅ تم إضافة القصة: {title}", reply_markup=admin_stories_keyboard())
            else:
                await update.message.reply_text("❌ قسم غير موجود")
        except:
            await update.message.reply_text("❌ تنسيق غير صحيح")
        context.user_data.clear()
    
    elif context.user_data.get('editing_welcome'):
        db.update_setting('welcome_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
    
    elif context.user_data.get('editing_about'):
        db.update_setting('about_text', text)
        await update.message.reply_text("✅ تم تحديث حول البوت", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
    
    elif context.user_data.get('editing_contact'):
        db.update_setting('contact_text', text)
        await update.message.reply_text("✅ تم تحديث اتصل بنا", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
    
    elif context.user_data.get('editing_start_button'):
        db.update_setting('start_button_text', text)
        await update.message.reply_text("✅ تم تحديث زر البدء", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
    
    elif context.user_data.get('broadcasting'):
        users = db.get_all_users()
        success = 0
        for user_data in users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=f"📢 إشعار:\n\n{text}")
                success += 1
            except:
                continue
        await update.message.reply_text(f"✅ تم الإرسال إلى {success} مستخدم", reply_markup=admin_main_keyboard())
        context.user_data.clear()
    
    # معالجة الحذف
    elif text.startswith("حذف "):
        item_name = text.replace("حذف ", "")
        
        # حذف قسم
        category_id = get_category_id_by_name(item_name)
        if category_id:
            db.delete_category(category_id)
            await update.message.reply_text(f"✅ تم حذف القسم: {item_name}", reply_markup=admin_categories_keyboard())
            return
        
        # حذف قصة
        stories = db.get_all_stories()
        for story in stories:
            if story[1] == item_name:
                db.delete_story(story[0])
                await update.message.reply_text(f"✅ تم حذف القصة: {item_name}", reply_markup=admin_stories_keyboard())
                return
        
        await update.message.reply_text("❌ لم يتم العثور")
    
    else:
        await update.message.reply_text("👑 لوحة تحكم المدير", reply_markup=admin_main_keyboard())

# معالجة رسائل المستخدمين
async def handle_user_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if is_admin(user_id):
        await handle_admin_message(update, context)
        return
    
    user_data = db.get_user(user_id)
    start_text = db.get_setting('start_button_text') or '🚀 بدء الاستخدام'
    
    if text == start_text:
        if not user_data or user_data[4] == 0:
            await update.message.reply_text("⏳ لم يتم الموافقة على حسابك بعد.")
        else:
            await update.message.reply_text("🎭 مرحباً بك!", reply_markup=main_keyboard())
        return
    
    if not user_data or user_data[4] == 0:
        await update.message.reply_text("⏳ لم يتم الموافقة على حسابك بعد.")
        return
    
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 الرئيسية", reply_markup=main_keyboard())
    
    elif text == "📚 أقسام القصص":
        categories = db.get_categories()
        if categories:
            await update.message.reply_text("📚 اختر قسم:", reply_markup=categories_keyboard())
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    elif text == "ℹ️ حول البوت":
        about_text = db.get_setting('about_text') or 'بوت القصص'
        await update.message.reply_text(about_text)
    
    elif text == "📞 اتصل بنا":
        contact_text = db.get_setting('contact_text') or 'للتواصل: @username'
        await update.message.reply_text(contact_text)
    
    else:
        category_id = get_category_id_by_name(text)
        if category_id:
            stories = db.get_stories_by_category(category_id)
            if stories:
                stories_text = f"📖 {text}:\n\n"
                for story in stories:
                    stories_text += f"📚 {story[1]}\n{story[2]}\n\n"
                await update.message.reply_text(stories_text)
            else:
                await update.message.reply_text(f"⚠️ لا توجد قصص في {text}.")
        else:
            await update.message.reply_text("⚠️ لم أفهم طلبك.", reply_markup=main_keyboard())

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"حدث خطأ: {context.error}")

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("❌ لم يتم تعيين TELEGRAM_BOT_TOKEN")
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت...")
    application.run_polling()

if __name__ == '__main__':
    main()

import os
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('content_bot.db', check_same_thread=False)
        self.create_tables()
        self.create_admin()
        self.create_default_settings()

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
                is_premium INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول الأقسام
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                is_premium_category INTEGER DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول المحتوى
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                content_type TEXT,
                category_id INTEGER,
                is_premium INTEGER DEFAULT 0,
                file_id TEXT,
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

        # جدول الإعدادات
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # جدول الأقسام المميزة
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS premium_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                section_name TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def create_admin(self):
        admin_id = int(os.getenv('ADMIN_ID', 123456789))
        self.conn.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, is_approved, is_admin, is_premium)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (admin_id, 'admin', 'Admin', 'Bot', 1, 1, 1))
        self.conn.commit()

    def create_default_settings(self):
        default_settings = [
            ('welcome_message', '🎭 **مرحباً بك في بوت المحتوى المميز!**'),
            ('approval_required', '1'),
            ('about_text', '🤖 **بوت المحتوى التفاعلي**\n\nبوت متخصص لمشاركة المحتوى المميز.'),
            ('contact_text', '📞 **للتواصل:** @username'),
            ('start_button_text', '🚀 ابدأ الرحلة'),
            ('auto_approve', '0'),
            ('premium_enabled', '1'),
            ('premium_section_name', '⭐ المحتوى المميز'),
            ('premium_access_message', '🔒 هذا المحتوى متاح للأعضاء المميزين فقط.\n\n💎 لترقية حسابك، تواصل مع الإدارة.'),
            ('broadcast_notification_text', '📢 إشعار من الإدارة'),
            ('admin_contact', '@username')
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

    def get_all_settings(self):
        cursor = self.conn.execute('SELECT * FROM bot_settings')
        return cursor.fetchall()

    def add_user(self, user_id, username, first_name, last_name, is_approved=False, is_admin=False):
        self.conn.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, is_approved, is_admin, last_active)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, last_name, is_approved, is_admin))
        self.conn.commit()

    def update_user_activity(self, user_id):
        self.conn.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
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

    def get_active_users(self, days=30):
        cutoff_date = datetime.now() - timedelta(days=days)
        cursor = self.conn.execute('''
            SELECT * FROM users 
            WHERE is_approved = 1 AND last_active > ?
        ''', (cutoff_date,))
        return cursor.fetchall()

    def get_pending_requests(self):
        cursor = self.conn.execute('SELECT * FROM join_requests')
        return cursor.fetchall()

    def delete_user(self, user_id):
        self.conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def make_premium(self, user_id):
        self.conn.execute('UPDATE users SET is_premium = 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def remove_premium(self, user_id):
        self.conn.execute('UPDATE users SET is_premium = 0 WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def add_category(self, name, is_premium_category=False):
        self.conn.execute('INSERT OR IGNORE INTO categories (name, is_premium_category) VALUES (?, ?)', 
                         (name, 1 if is_premium_category else 0))
        self.conn.commit()

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories ORDER BY name')
        return cursor.fetchall()

    def get_normal_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories WHERE is_premium_category = 0 ORDER BY name')
        return cursor.fetchall()

    def get_premium_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories WHERE is_premium_category = 1 ORDER BY name')
        return cursor.fetchall()

    def update_category(self, category_id, name, is_premium_category):
        self.conn.execute('UPDATE categories SET name = ?, is_premium_category = ? WHERE id = ?', 
                         (name, is_premium_category, category_id))
        self.conn.commit()

    def delete_category(self, category_id):
        self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.execute('DELETE FROM content WHERE category_id = ?', (category_id,))
        self.conn.commit()

    def add_content(self, title, content, content_type, category_id, is_premium=False, file_id=None):
        self.conn.execute('''
            INSERT INTO content (title, content, content_type, category_id, is_premium, file_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, content, content_type, category_id, 1 if is_premium else 0, file_id))
        self.conn.commit()

    def get_content_by_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM content WHERE category_id = ? ORDER BY created_date DESC', (category_id,))
        return cursor.fetchall()

    def get_premium_content(self):
        cursor = self.conn.execute('SELECT * FROM content WHERE is_premium = 1 ORDER BY created_date DESC')
        return cursor.fetchall()

    def get_all_content(self):
        cursor = self.conn.execute('''
            SELECT c.*, cat.name as category_name 
            FROM content c JOIN categories cat ON c.category_id = cat.id 
            ORDER BY c.created_date DESC
        ''')
        return cursor.fetchall()

    def delete_content(self, content_id):
        self.conn.execute('DELETE FROM content WHERE id = ?', (content_id,))
        self.conn.commit()

    def get_content(self, content_id):
        cursor = self.conn.execute('SELECT * FROM content WHERE id = ?', (content_id,))
        return cursor.fetchone()

    def add_premium_section(self, category_id, section_name):
        self.conn.execute('INSERT OR IGNORE INTO premium_sections (category_id, section_name) VALUES (?, ?)', 
                         (category_id, section_name))
        self.conn.commit()

    def get_premium_sections(self):
        cursor = self.conn.execute('''
            SELECT ps.*, c.name as category_name 
            FROM premium_sections ps 
            JOIN categories c ON ps.category_id = c.id
        ''')
        return cursor.fetchall()

    def delete_premium_section(self, section_id):
        self.conn.execute('DELETE FROM premium_sections WHERE id = ?', (section_id,))
        self.conn.commit()

db = Database()

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

# لوحات المفاتيح للمستخدم - محسنة حسب المتطلبات
def user_main_menu():
    premium_section_name = db.get_setting('premium_section_name') or '⭐ المحتوى المميز'
    keyboard = [
        [KeyboardButton("📁 أقسام البوت"), KeyboardButton(premium_section_name)],
        [KeyboardButton("👤 الملف الشخصي"), KeyboardButton("ℹ️ حول البوت")],
        [KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_categories_menu():
    categories = db.get_normal_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([KeyboardButton(cat[1])])
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_premium_sections_menu():
    premium_sections = db.get_premium_sections()
    keyboard = []
    for section in premium_sections:
        keyboard.append([KeyboardButton(section[2])])  # section_name
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_content_menu(category_id):
    content_items = db.get_content_by_category(category_id)
    keyboard = []
    for content in content_items:
        keyboard.append([KeyboardButton(f"📄 {content[1]}")])  # title
    keyboard.append([KeyboardButton("🔙 رجوع")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحات المفاتيح للمدير - محسنة
def admin_main_menu():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📦 إدارة المحتوى"), KeyboardButton("⚙️ إعدادات البوت")],
        [KeyboardButton("📊 الإحصائيات"), KeyboardButton("📢 البث الجماعي")],
        [KeyboardButton("🎯 إدارة المميزين"), KeyboardButton("🔧 الأقسام المميزة")],
        [KeyboardButton("🔙 وضع المستخدم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_users_menu():
    keyboard = [
        [KeyboardButton("📋 عرض المستخدمين"), KeyboardButton("⏳ طلبات الانضمام")],
        [KeyboardButton("💎 ترقية مستخدم"), KeyboardButton("🗑 حذف مستخدم")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_categories_menu():
    keyboard = [
        [KeyboardButton("➕ إضافة قسم"), KeyboardButton("✏️ تعديل قسم")],
        [KeyboardButton("🗑 حذف قسم"), KeyboardButton("📋 عرض الأقسام")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_content_menu():
    keyboard = [
        [KeyboardButton("➕ إضافة محتوى"), KeyboardButton("✏️ تعديل محتوى")],
        [KeyboardButton("🗑 حذف محتوى"), KeyboardButton("📋 عرض المحتوى")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_premium_sections_menu():
    keyboard = [
        [KeyboardButton("➕ إضافة قسم مميز"), KeyboardButton("🗑 حذف قسم مميز")],
        [KeyboardButton("📋 عرض الأقسام المميزة"), KeyboardButton("✏️ تعديل اسم القسم المميز")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_settings_menu():
    keyboard = [
        [KeyboardButton("✏️ رسالة الترحيب"), KeyboardButton("📝 حول البوت")],
        [KeyboardButton("📞 اتصل بنا"), KeyboardButton("🔄 زر البدء")],
        [KeyboardButton("🔐 نظام الموافقة"), KeyboardButton("🎯 إعدادات المميزين")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# معالجة START - محسنة
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    context.user_data.clear()
    db.update_user_activity(user_id)
    
    if is_admin(user_id):
        await update.message.reply_text(
            "👑 **مرحباً بك آلة المدير!**\n\nلوحة التحكم المتقدمة جاهزة.",
            reply_markup=admin_main_menu()
        )
        return
    
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    user_data = db.get_user(user_id)
    auto_approve = db.get_setting('auto_approve') == '1'
    approval_required = db.get_setting('approval_required') == '1'
    
    # الموافقة التلقائية
    if auto_approve and not user_data[4]:
        db.approve_user(user_id)
        user_data = db.get_user(user_id)
    
    if user_data and user_data[4] == 1:
        welcome_message = db.get_setting('welcome_message')
        await update.message.reply_text(
            f"{welcome_message}\n\nمرحباً بك {user.first_name}! 👋",
            reply_markup=user_main_menu()
        )
    elif not approval_required:
        # إذا لم يكن نظام الموافقة مفعل
        db.approve_user(user_id)
        welcome_message = db.get_setting('welcome_message')
        await update.message.reply_text(
            f"{welcome_message}\n\nمرحباً بك {user.first_name}! 👋",
            reply_markup=user_main_menu()
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
        
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 طلب انضمام جديد:\n👤 {user.first_name}\n📱 @{user.username or 'لا يوجد'}\n🆔 {user_id}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة للمدير: {e}")
        
        await update.message.reply_text(
            "📋 تم إرسال طلب انضمامك إلى المدير. انتظر الموافقة.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔄 تحديث الحالة")]], resize_keyboard=True)
        )

# معالجة Callback للمدير
async def handle_callback(update: Update, context: CallbackContext) -> None:
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
                reply_markup=user_main_menu()
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
        
        await query.edit_message_text(f"✅ تمت الموافقة على المستخدم {target_user_id}")
        
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        db.reject_user(target_user_id)
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")

# معالجة رسائل المستخدمين - محسنة تماماً
async def handle_user_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if is_admin(user_id):
        await handle_admin_message(update, context)
        return
    
    db.update_user_activity(user_id)
    user_data = db.get_user(user_id)
    
    if not user_data or user_data[4] == 0:
        if text == "🔄 تحديث الحالة":
            user_data = db.get_user(user_id)
            if user_data and user_data[4] == 1:
                await update.message.reply_text("🎉 تمت الموافقة على طلبك!", reply_markup=user_main_menu())
            else:
                await update.message.reply_text("⏳ لا يزال طلبك قيد المراجعة...")
        return
    
    # معالجة أوامر المستخدم الرئيسية
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    elif text == "📁 أقسام البوت":
        categories = db.get_normal_categories()
        if categories:
            await update.message.reply_text("📁 اختر قسم:", reply_markup=user_categories_menu())
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif text == db.get_setting('premium_section_name') or text == "⭐ المحتوى المميز":
        if user_data[6] == 1:
            premium_sections = db.get_premium_sections()
            if premium_sections:
                await update.message.reply_text("👑 الأقسام المميزة:", reply_markup=user_premium_sections_menu())
            else:
                await update.message.reply_text("⚠️ لا توجد أقسام مميزة حالياً.")
        else:
            premium_message = db.get_setting('premium_access_message')
            await update.message.reply_text(premium_message)
    
    elif text == "👤 الملف الشخصي":
        user_stats = f"👤 **الملف الشخصي**\n\n"
        user_stats += f"🆔 الرقم: {user_id}\n"
        user_stats += f"👤 الاسم: {user.first_name}\n"
        user_stats += f"📅 تاريخ الانضمام: {user_data[7].split()[0] if user_data[7] else 'غير معروف'}\n"
        user_stats += f"💎 العضوية: {'مميز 👑' if user_data[6] == 1 else 'عادي ⭐'}\n"
        
        if user_data[6] == 0:
            user_stats += f"\n💡 لترقية حسابك إلى مميز، تواصل مع: {db.get_setting('admin_contact')}"
        
        await update.message.reply_text(user_stats)
    
    elif text == "ℹ️ حول البوت":
        about_text = db.get_setting('about_text')
        await update.message.reply_text(about_text)
    
    elif text == "📞 اتصل بنا":
        contact_text = db.get_setting('contact_text')
        await update.message.reply_text(contact_text)
    
    elif text == "🔙 رجوع":
        await update.message.reply_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    else:
        # التحقق إذا كان النص هو اسم قسم عادي
        category_id = get_category_id_by_name(text)
        if category_id:
            category_data = next((cat for cat in db.get_categories() if cat[0] == category_id), None)
            if category_data and category_data[2] == 0:  # قسم عادي
                content_items = db.get_content_by_category(category_id)
                if content_items:
                    await update.message.reply_text(
                        f"📁 قسم: {text}\n\nاختر المحتوى:",
                        reply_markup=user_content_menu(category_id)
                    )
                else:
                    await update.message.reply_text(f"⚠️ لا يوجد محتوى في قسم {text}.")
                return
        
        # التحقق إذا كان النص هو اسم قسم مميز
        premium_sections = db.get_premium_sections()
        for section in premium_sections:
            if section[2] == text:  # section_name
                if user_data[6] == 1:
                    content_items = db.get_content_by_category(section[1])  # category_id
                    if content_items:
                        await update.message.reply_text(
                            f"👑 قسم: {text}\n\nاختر المحتوى:",
                            reply_markup=user_content_menu(section[1])
                        )
                    else:
                        await update.message.reply_text(f"⚠️ لا يوجد محتوى في قسم {text}.")
                else:
                    premium_message = db.get_setting('premium_access_message')
                    await update.message.reply_text(premium_message)
                return
        
        # التحقق إذا كان النص هو عنوان محتوى
        if text.startswith("📄 "):
            content_title = text[2:]  # إزالة الإيموجي
            all_content = db.get_all_content()
            for content in all_content:
                if content[1] == content_title:  # title
                    # التحقق إذا كان المحتوى مميزاً
                    if content[5] == 1 and user_data[6] == 0:
                        premium_message = db.get_setting('premium_access_message')
                        await update.message.reply_text(premium_message)
                        return
                    
                    # إرسال المحتوى
                    if content[3] == 'text':  # content_type
                        await update.message.reply_text(
                            f"📖 **{content[1]}**\n\n{content[2]}\n\n---\nنهاية المحتوى 📚"
                        )
                    elif content[3] == 'photo' and content[6]:  # file_id
                        await update.message.reply_photo(
                            photo=content[6],
                            caption=f"📸 **{content[1]}**\n\n{content[2]}"
                        )
                    elif content[3] == 'video' and content[6]:  # file_id
                        await update.message.reply_video(
                            video=content[6],
                            caption=f"🎥 **{content[1]}**\n\n{content[2]}"
                        )
                    else:
                        await update.message.reply_text(
                            f"📖 **{content[1]}**\n\n{content[2]}\n\n---\nنهاية المحتوى 📚"
                        )
                    return
        
        await update.message.reply_text("❌ لم أفهم طلبك.", reply_markup=user_main_menu())

# معالجة الوسائط (صور، فيديو) - جديدة
async def handle_media(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    if not is_admin(user_id):
        return
    
    # إذا كان المدير يضيف محتوى
    if context.user_data.get('adding_content'):
        content_type = None
        file_id = None
        
        if update.message.photo:
            content_type = 'photo'
            file_id = update.message.photo[-1].file_id
        elif update.message.video:
            content_type = 'video'
            file_id = update.message.video.file_id
        
        if content_type and file_id:
            context.user_data['content_file_id'] = file_id
            context.user_data['content_type'] = content_type
            await update.message.reply_text("✅ تم استلام الملف. الآن أرسل وصف المحتوى:")
            context.user_data['awaiting_content_description'] = True

# معالجة رسائل المدير - محسنة بالكامل
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if not is_admin(user_id):
        return

    db.update_user_activity(user_id)

    # تنظيف الحالات
    if text in ["🔙 لوحة التحكم", "🏠 الرئيسية"]:
        context.user_data.clear()

    # الأوامر الرئيسية للمدير
    if text == "🔙 وضع المستخدم":
        context.user_data.clear()
        await update.message.reply_text("تم التبديل إلى وضع المستخدم", reply_markup=user_main_menu())
    
    elif text == "👥 إدارة المستخدمين":
        await update.message.reply_text("👥 إدارة المستخدمين", reply_markup=admin_users_menu())
    
    elif text == "📁 إدارة الأقسام":
        await update.message.reply_text("📁 إدارة الأقسام", reply_markup=admin_categories_menu())
    
    elif text == "📦 إدارة المحتوى":
        await update.message.reply_text("📦 إدارة المحتوى", reply_markup=admin_content_menu())
    
    elif text == "🔧 الأقسام المميزة":
        await update.message.reply_text("🔧 إدارة الأقسام المميزة", reply_markup=admin_premium_sections_menu())
    
    elif text == "⚙️ إعدادات البوت":
        await update.message.reply_text("⚙️ إعدادات البوت", reply_markup=admin_settings_menu())
    
    elif text == "🎯 إدارة المميزين":
        await show_premium_management(update, context)
    
    elif text == "📊 الإحصائيات":
        await show_statistics(update, context)
    
    elif text == "📢 البث الجماعي":
        await show_broadcast_menu(update, context)
    
    # إدارة الأقسام
    elif text == "➕ إضافة قسم":
        await update.message.reply_text("أرسل اسم القسم الجديد:")
        context.user_data['adding_category'] = True
    
    elif text == "📋 عرض الأقسام":
        categories = db.get_categories()
        if categories:
            cats_text = "📁 **جميع الأقسام:**\n\n"
            for cat in categories:
                premium_status = "👑" if cat[2] == 1 else "⭐"
                cats_text += f"{premium_status} {cat[1]} (ID: {cat[0]})\n"
            await update.message.reply_text(cats_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    elif text == "🗑 حذف قسم":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                keyboard.append([KeyboardButton(f"حذف قسم {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة الأقسام")])
            await update.message.reply_text("اختر قسم للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    # إدارة المحتوى
    elif text == "➕ إضافة محتوى":
        categories = db.get_categories()
        if not categories:
            await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
            return
        
        keyboard = [
            [KeyboardButton("📝 نص"), KeyboardButton("📸 صورة")],
            [KeyboardButton("🎥 فيديو"), KeyboardButton("🔙 إدارة المحتوى")]
        ]
        await update.message.reply_text("اختر نوع المحتوى:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    
    elif text in ["📝 نص", "📸 صورة", "🎥 فيديو"]:
        content_type_map = {"📝 نص": "text", "📸 صورة": "photo", "🎥 فيديو": "video"}
        context.user_data['content_type'] = content_type_map[text]
        context.user_data['adding_content'] = True
        
        if text == "📝 نص":
            await update.message.reply_text("أرسل المحتوى النصي:")
        else:
            await update.message.reply_text(f"أرسل {text} الآن:")
    
    elif text == "📋 عرض المحتوى":
        content_items = db.get_all_content()
        if content_items:
            content_text = "📦 **جميع المحتويات:**\n\n"
            for content in content_items:
                content_type_icon = "📝" if content[3] == 'text' else "📸" if content[3] == 'photo' else "🎥"
                premium_status = "👑" if content[5] == 1 else "⭐"
                content_text += f"{content_type_icon}{premium_status} {content[1]} - {content[7]}\n"
            await update.message.reply_text(content_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
    
    elif text == "🗑 حذف محتوى":
        content_items = db.get_all_content()
        if content_items:
            keyboard = []
            for content in content_items:
                keyboard.append([KeyboardButton(f"حذف محتوى {content[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
            await update.message.reply_text("اختر محتوى للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
    
    # الأقسام المميزة
    elif text == "➕ إضافة قسم مميز":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                keyboard.append([KeyboardButton(f"إضافة {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 الأقسام المميزة")])
            await update.message.reply_text("اختر قسم لإضافته للأقسام المميزة:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    elif text == "📋 عرض الأقسام المميزة":
        premium_sections = db.get_premium_sections()
        if premium_sections:
            sections_text = "👑 **الأقسام المميزة:**\n\n"
            for section in premium_sections:
                sections_text += f"📁 {section[2]} (القسم: {section[3]})\n"
            await update.message.reply_text(sections_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام مميزة.")
    
    elif text == "🗑 حذف قسم مميز":
        premium_sections = db.get_premium_sections()
        if premium_sections:
            keyboard = []
            for section in premium_sections:
                keyboard.append([KeyboardButton(f"حذف {section[2]}")])
            keyboard.append([KeyboardButton("🔙 الأقسام المميزة")])
            await update.message.reply_text("اختر قسم مميز للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام مميزة.")
    
    elif text == "✏️ تعديل اسم القسم المميز":
        current_name = db.get_setting('premium_section_name')
        await update.message.reply_text(f"الاسم الحالي: {current_name}\n\nأرسل الاسم الجديد:")
        context.user_data['editing_premium_section_name'] = True
    
    # الإعدادات
    elif text == "✏️ رسالة الترحيب":
        current = db.get_setting('welcome_message')
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_welcome'] = True
    
    elif text == "📝 حول البوت":
        current = db.get_setting('about_text')
        await update.message.reply_text(f"النص الحالي:\n{current}\n\nأرسل النص الجديد:")
        context.user_data['editing_about'] = True
    
    elif text == "🎯 إعدادات المميزين":
        current_message = db.get_setting('premium_access_message')
        await update.message.reply_text(f"رسالة المميزين الحالية:\n{current_message}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_premium_message'] = True
    
    elif text == "🔐 نظام الموافقة":
        current = db.get_setting('approval_required')
        new_status = '0' if current == '1' else '1'
        db.update_setting('approval_required', new_status)
        status = "معطل" if new_status == '0' else "مفعل"
        await update.message.reply_text(f"✅ تم {status} نظام الموافقة")
    
    # معالجة إدخال البيانات
    elif context.user_data.get('adding_category'):
        db.add_category(text)
        await update.message.reply_text(f"✅ تم إضافة القسم: {text}", reply_markup=admin_categories_menu())
        context.user_data.clear()
    
    elif context.user_data.get('adding_content') and context.user_data.get('awaiting_content_description'):
        # تم استلام وصف المحتوى، الآن نطلب العنوان
        context.user_data['content_description'] = text
        context.user_data['awaiting_content_description'] = False
        context.user_data['awaiting_content_title'] = True
        
        categories = db.get_categories()
        keyboard = []
        for cat in categories:
            keyboard.append([KeyboardButton(f"القسم {cat[1]}")])
        keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
        
        await update.message.reply_text(
            "✅ تم حفظ الوصف. الآن اختر القسم:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    
    elif context.user_data.get('awaiting_content_title'):
        # تم استلام القسم، الآن نطلب إذا كان المحتوى مميزاً
        if text.startswith("القسم "):
            category_name = text[6:]  # إزالة "القسم "
            category_id = get_category_id_by_name(category_name)
            if category_id:
                context.user_data['content_category_id'] = category_id
                
                keyboard = [
                    [KeyboardButton("👑 محتوى مميز"), KeyboardButton("⭐ محتوى عادي")],
                    [KeyboardButton("🔙 إدارة المحتوى")]
                ]
                await update.message.reply_text(
                    "اختر نوع المحتوى:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
            else:
                await update.message.reply_text("❌ قسم غير موجود")
        else:
            await update.message.reply_text("❌ الرجاء اختيار قسم صحيح")
    
    elif text in ["👑 محتوى مميز", "⭐ محتوى عادي"]:
        is_premium = text == "👑 محتوى مميز"
        
        # حفظ المحتوى في قاعدة البيانات
        title = f"محتوى {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        content_type = context.user_data.get('content_type', 'text')
        description = context.user_data.get('content_description', '')
        category_id = context.user_data.get('content_category_id')
        file_id = context.user_data.get('content_file_id')
        
        db.add_content(title, description, content_type, category_id, is_premium, file_id)
        
        status = "مميز 👑" if is_premium else "عادي ⭐"
        await update.message.reply_text(
            f"✅ تم إضافة المحتوى ({status})",
            reply_markup=admin_content_menu()
        )
        context.user_data.clear()
    
    elif context.user_data.get('editing_premium_section_name'):
        db.update_setting('premium_section_name', text)
        await update.message.reply_text(f"✅ تم تحديث اسم القسم المميز إلى: {text}", reply_markup=admin_premium_sections_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_welcome'):
        db.update_setting('welcome_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب", reply_markup=admin_settings_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_about'):
        db.update_setting('about_text', text)
        await update.message.reply_text("✅ تم تحديث حول البوت", reply_markup=admin_settings_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_premium_message'):
        db.update_setting('premium_access_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة المميزين", reply_markup=admin_settings_menu())
        context.user_data.clear()
    
    # معالجة الحذف
    elif text.startswith("حذف قسم "):
        category_name = text[9:]  # إزالة "حذف قسم "
        category_id = get_category_id_by_name(category_name)
        if category_id:
            db.delete_category(category_id)
            await update.message.reply_text(f"✅ تم حذف القسم: {category_name}", reply_markup=admin_categories_menu())
        else:
            await update.message.reply_text("❌ قسم غير موجود")
    
    elif text.startswith("حذف محتوى "):
        content_title = text[11:]  # إزالة "حذف محتوى "
        all_content = db.get_all_content()
        for content in all_content:
            if content[1] == content_title:
                db.delete_content(content[0])
                await update.message.reply_text(f"✅ تم حذف المحتوى: {content_title}", reply_markup=admin_content_menu())
                return
        await update.message.reply_text("❌ محتوى غير موجود")
    
    elif text.startswith("حذف "):
        section_name = text[5:]  # إزالة "حذف "
        premium_sections = db.get_premium_sections()
        for section in premium_sections:
            if section[2] == section_name:
                db.delete_premium_section(section[0])
                await update.message.reply_text(f"✅ تم حذف القسم المميز: {section_name}", reply_markup=admin_premium_sections_menu())
                return
        await update.message.reply_text("❌ قسم مميز غير موجود")
    
    elif text.startswith("إضافة "):
        category_name = text[6:]  # إزالة "إضافة "
        category_id = get_category_id_by_name(category_name)
        if category_id:
            db.add_premium_section(category_id, category_name)
            await update.message.reply_text(f"✅ تم إضافة القسم {category_name} إلى الأقسام المميزة", reply_markup=admin_premium_sections_menu())
        else:
            await update.message.reply_text("❌ قسم غير موجود")
    
    else:
        await update.message.reply_text("👑 لوحة تحكم المدير", reply_markup=admin_main_menu())

# دوال مساعدة للمدير
async def show_premium_management(update: Update, context: CallbackContext):
    premium_users = [u for u in db.get_all_users() if u[6] == 1]
    total_users = len(db.get_all_users())
    
    keyboard = [
        [KeyboardButton("💎 ترقية مستخدم"), KeyboardButton("🔻 إزالة التميز")],
        [KeyboardButton("👑 عرض المميزين"), KeyboardButton("📊 إحصائيات المميزين")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    
    stats_text = f"💎 **إدارة المميزين**\n\n"
    stats_text += f"👑 الأعضاء المميزين: {len(premium_users)}\n"
    stats_text += f"👥 إجمالي المستخدمين: {total_users}\n"
    stats_text += f"📈 النسبة: {(len(premium_users)/total_users*100) if total_users > 0 else 0:.1f}%"
    
    await update.message.reply_text(stats_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def show_statistics(update: Update, context: CallbackContext):
    total_users = len(db.get_all_users())
    active_users = len(db.get_active_users(30))
    premium_users = len([u for u in db.get_all_users() if u[6] == 1])
    total_content = len(db.get_all_content())
    total_categories = len(db.get_categories())
    premium_sections = len(db.get_premium_sections())
    
    stats_text = f"📊 **إحصائيات البوت:**\n\n"
    stats_text += f"👥 المستخدمون: {total_users}\n"
    stats_text += f"🎯 النشطون: {active_users}\n"
    stats_text += f"💎 المميزون: {premium_users}\n"
    stats_text += f"📦 المحتوى: {total_content}\n"
    stats_text += f"📁 الأقسام: {total_categories}\n"
    stats_text += f"👑 الأقسام المميزة: {premium_sections}"
    
    await update.message.reply_text(stats_text)

async def show_broadcast_menu(update: Update, context: CallbackContext):
    keyboard = [
        [KeyboardButton("📢 للجميع"), KeyboardButton("👥 للنشطين")],
        [KeyboardButton("💎 للمميزين فقط"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    await update.message.reply_text("📢 اختر نوع البث:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"حدث خطأ: {context.error}")

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("❌ لم يتم تعيين TELEGRAM_BOT_TOKEN")
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت المحسن...")
    application.run_polling()

if __name__ == '__main__':
    main()

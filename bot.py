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
                is_premium INTEGER DEFAULT 0,
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
            ('welcome_message', '🎭 مرحباً بك في بوت المحتوى المميز!'),
            ('approval_required', '1'),
            ('about_text', '🤖 بوت المحتوى التفاعلي\n\nبوت متخصص لمشاركة المحتوى المميز.'),
            ('contact_text', '📞 للتواصل: @username'),
            ('start_button_text', '🚀 ابدأ الرحلة'),
            ('auto_approve', '0'),
            ('premium_enabled', '1'),
            ('premium_section_name', '👑 قسم المميز'),
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

    def get_premium_users(self):
        cursor = self.conn.execute('SELECT * FROM users WHERE is_premium = 1 AND is_approved = 1')
        return cursor.fetchall()

    def add_category(self, name, is_premium=False):
        self.conn.execute('INSERT OR IGNORE INTO categories (name, is_premium) VALUES (?, ?)', 
                         (name, 1 if is_premium else 0))
        self.conn.commit()

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories ORDER BY name')
        return cursor.fetchall()

    def get_normal_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories WHERE is_premium = 0 ORDER BY name')
        return cursor.fetchall()

    def get_premium_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories WHERE is_premium = 1 ORDER BY name')
        return cursor.fetchall()

    def update_category(self, category_id, name, is_premium):
        self.conn.execute('UPDATE categories SET name = ?, is_premium = ? WHERE id = ?', 
                         (name, is_premium, category_id))
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

def get_category_name_by_id(category_id):
    categories = db.get_categories()
    for cat in categories:
        if cat[0] == category_id:
            return cat[1]
    return "غير معروف"

# لوحات المفاتيح للمستخدم
def user_main_menu():
    premium_section_name = db.get_setting('premium_section_name') or '👑 قسم المميز'
    keyboard = [
        [KeyboardButton("📁 الاقسام"), KeyboardButton(premium_section_name)],
        [KeyboardButton("👤 الملف الشخصي"), KeyboardButton("ℹ️ حول البوت")],
        [KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_categories_menu():
    categories = db.get_normal_categories()
    keyboard = []
    row = []
    for i, cat in enumerate(categories):
        row.append(KeyboardButton(cat[1]))
        if len(row) == 2 or i == len(categories) - 1:
            keyboard.append(row)
            row = []
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_premium_categories_menu():
    categories = db.get_premium_categories()
    keyboard = []
    row = []
    for i, cat in enumerate(categories):
        row.append(KeyboardButton(cat[1]))
        if len(row) == 2 or i == len(categories) - 1:
            keyboard.append(row)
            row = []
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_content_menu(category_name, category_id):
    content_items = db.get_content_by_category(category_id)
    keyboard = []
    row = []
    for i, content in enumerate(content_items):
        short_title = content[1][:15] + "..." if len(content[1]) > 15 else content[1]
        row.append(KeyboardButton(f"📄 {short_title}"))
        if len(row) == 2 or i == len(content_items) - 1:
            keyboard.append(row)
            row = []
    keyboard.append([KeyboardButton(f"🔙 رجوع إلى {category_name}")])
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحات المفاتيح للمدير
def admin_main_menu():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📦 إدارة المحتوى"), KeyboardButton("⚙️ إعدادات البوت")],
        [KeyboardButton("📊 الإحصائيات"), KeyboardButton("📢 البث الجماعي")],
        [KeyboardButton("🎯 إدارة المميزين")],
        [KeyboardButton("🔙 وضع المستخدم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_users_menu():
    keyboard = [
        [KeyboardButton("📋 عرض المستخدمين"), KeyboardButton("⏳ طلبات الانضمام")],
        [KeyboardButton("💎 ترقية مستخدم"), KeyboardButton("🔻 إزالة التميز")],
        [KeyboardButton("🗑 حذف مستخدم"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_categories_menu():
    keyboard = [
        [KeyboardButton("➕ إضافة قسم"), KeyboardButton("✏️ تعديل قسم")],
        [KeyboardButton("🗑 حذف قسم"), KeyboardButton("📋 عرض الأقسام")],
        [KeyboardButton("🔧 جعل قسم مميز"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_content_menu():
    keyboard = [
        [KeyboardButton("➕ إضافة محتوى"), KeyboardButton("🗑 حذف محتوى")],
        [KeyboardButton("📋 عرض المحتوى"), KeyboardButton("🔧 جعل محتوى مميز")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_premium_menu():
    keyboard = [
        [KeyboardButton("👑 عرض المميزين"), KeyboardButton("💎 ترقية مستخدم")],
        [KeyboardButton("🔻 إزالة التميز"), KeyboardButton("📊 إحصائيات المميزين")],
        [KeyboardButton("✏️ تعديل رسالة المميزين"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_settings_menu():
    keyboard = [
        [KeyboardButton("✏️ رسالة الترحيب"), KeyboardButton("📝 حول البوت")],
        [KeyboardButton("📞 اتصل بنا"), KeyboardButton("🔄 زر البدء")],
        [KeyboardButton("🔐 نظام الموافقة"), KeyboardButton("🎯 إعدادات المميزين")],
        [KeyboardButton("✏️ اسم قسم المميز"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# معالجة START
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    context.user_data.clear()
    db.update_user_activity(user_id)
    
    if is_admin(user_id):
        await update.message.reply_text(
            "👑 مرحباً بك آلة المدير!\n\nلوحة التحكم المتقدمة جاهزة.",
            reply_markup=admin_main_menu()
        )
        return
    
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    user_data = db.get_user(user_id)
    auto_approve = db.get_setting('auto_approve') == '1'
    approval_required = db.get_setting('approval_required') == '1'
    
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
        db.approve_user(user_id)
        welcome_message = db.get_setting('welcome_message')
        await update.message.reply_text(
            f"{welcome_message}\n\nمرحباً بك {user.first_name}! 👋",
            reply_markup=user_main_menu()
        )
    else:
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

# معالجة الوسائط
async def handle_media(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    if not is_admin(user_id):
        return
    
    if context.user_data.get('content_stage') == 'content':
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
            context.user_data['content_stage'] = 'category'
            
            categories = db.get_categories()
            keyboard = []
            for cat in categories:
                premium_status = "👑" if cat[2] == 1 else "⭐"
                keyboard.append([KeyboardButton(f"{premium_status} {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
            
            await update.message.reply_text(
                "📁 المرحلة 3 من 3\n\nاختر القسم الذي تريد إضافة المحتوى إليه:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )

# معالجة رسائل المستخدمين
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
    
    # معالجة الأوامر الرئيسية
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    elif text == "📁 الاقسام":
        categories = db.get_normal_categories()
        if categories:
            await update.message.reply_text("📁 الاقسام المتاحة:\n\nاختر قسم:", reply_markup=user_categories_menu())
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif text == db.get_setting('premium_section_name') or text == "👑 قسم المميز":
        if user_data[6] == 1:
            categories = db.get_premium_categories()
            if categories:
                await update.message.reply_text("👑 الأقسام المميزة:\n\nاختر قسم:", reply_markup=user_premium_categories_menu())
            else:
                await update.message.reply_text("⚠️ لا توجد أقسام مميزة حالياً.")
        else:
            premium_message = db.get_setting('premium_access_message')
            await update.message.reply_text(premium_message)
    
    elif text == "👤 الملف الشخصي":
        user_stats = f"👤 الملف الشخصي\n\n"
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
    
    elif text.startswith("🔙 رجوع إلى "):
        category_name = text[13:]
        category_id = get_category_id_by_name(category_name)
        if category_id:
            content_items = db.get_content_by_category(category_id)
            if content_items:
                await update.message.reply_text(
                    f"📁 قسم: {category_name}\n\nاختر المحتوى:",
                    reply_markup=user_content_menu(category_name, category_id)
                )
            else:
                await update.message.reply_text(f"⚠️ لا يوجد محتوى في قسم {category_name}.")
        else:
            await update.message.reply_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    else:
        # التحقق إذا كان النص هو اسم قسم
        category_id = get_category_id_by_name(text)
        if category_id:
            category_data = next((cat for cat in db.get_categories() if cat[0] == category_id), None)
            if category_data:
                if category_data[2] == 1 and user_data[6] == 0:
                    premium_message = db.get_setting('premium_access_message')
                    await update.message.reply_text(premium_message)
                    return
                
                content_items = db.get_content_by_category(category_id)
                if content_items:
                    await update.message.reply_text(
                        f"📁 قسم: {text}\n\nاختر المحتوى:",
                        reply_markup=user_content_menu(text, category_id)
                    )
                else:
                    await update.message.reply_text(f"⚠️ لا يوجد محتوى في قسم {text}.")
            return
        
        # التحقق إذا كان النص هو عنوان محتوى
        if text.startswith("📄 "):
            content_title = text[2:]
            all_content = db.get_all_content()
            for content in all_content:
                if content[1].startswith(content_title):
                    if content[5] == 1 and user_data[6] == 0:
                        premium_message = db.get_setting('premium_access_message')
                        await update.message.reply_text(premium_message)
                        return
                    
                    if content[3] == 'text':
                        await update.message.reply_text(
                            f"📖 {content[1]}\n\n{content[2]}\n\n---\nنهاية المحتوى 📚"
                        )
                    elif content[3] == 'photo' and content[6]:
                        await update.message.reply_photo(
                            photo=content[6],
                            caption=f"📸 {content[1]}\n\n{content[2]}"
                        )
                    elif content[3] == 'video' and content[6]:
                        await update.message.reply_video(
                            video=content[6],
                            caption=f"🎥 {content[1]}\n\n{content[2]}"
                        )
                    else:
                        await update.message.reply_text(
                            f"📖 {content[1]}\n\n{content[2]}\n\n---\nنهاية المحتوى 📚"
                        )
                    return
        
        await update.message.reply_text("❌ لم أفهم طلبك.", reply_markup=user_main_menu())

# معالجة رسائل المدير - تم إصلاح جميع المشاكل
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if not is_admin(user_id):
        return

    db.update_user_activity(user_id)

    # تنظيف الحالات عند العودة للوحة التحكم
    if text in ["🔙 لوحة التحكم", "🔙 إدارة الأقسام", "🔙 إدارة المحتوى", "🔙 إدارة المميزين"]:
        context.user_data.clear()

    if text == "🔙 وضع المستخدم":
        context.user_data.clear()
        await update.message.reply_text("تم التبديل إلى وضع المستخدم", reply_markup=user_main_menu())
        return
    
    elif text == "👥 إدارة المستخدمين":
        await update.message.reply_text("👥 إدارة المستخدمين", reply_markup=admin_users_menu())
        return
    
    elif text == "📁 إدارة الأقسام":
        await update.message.reply_text("📁 إدارة الأقسام", reply_markup=admin_categories_menu())
        return
    
    elif text == "📦 إدارة المحتوى":
        await update.message.reply_text("📦 إدارة المحتوى", reply_markup=admin_content_menu())
        return
    
    elif text == "🎯 إدارة المميزين":
        await update.message.reply_text("🎯 إدارة المميزين", reply_markup=admin_premium_menu())
        return
    
    elif text == "⚙️ إعدادات البوت":
        await update.message.reply_text("⚙️ إعدادات البوت", reply_markup=admin_settings_menu())
        return
    
    elif text == "📊 الإحصائيات":
        await show_statistics(update, context)
        return
    
    elif text == "📢 البث الجماعي":
        await update.message.reply_text("أرسل الرسالة للبث لجميع المستخدمين:")
        context.user_data['broadcasting'] = True
        return
    
    # إدارة المستخدمين
    elif text == "📋 عرض المستخدمين":
        users = db.get_all_users()
        if users:
            users_text = "👥 المستخدمون:\n\n"
            for user_data in users:
                status = "👑" if user_data[6] == 1 else "⭐"
                users_text += f"{status} {user_data[0]} - {user_data[2]}\n"
            await update.message.reply_text(users_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد مستخدمين.")
        return
    
    elif text == "⏳ طلبات الانضمام":
        requests = db.get_pending_requests()
        if requests:
            req_text = "📩 طلبات الانضمام:\n\n"
            for req in requests:
                req_text += f"🆔 {req[0]} - 👤 {req[2]} - 📱 @{req[1] or 'لا يوجد'}\n"
            await update.message.reply_text(req_text)
        else:
            await update.message.reply_text("✅ لا توجد طلبات انتظار.")
        return
    
    elif text == "💎 ترقية مستخدم":
        await update.message.reply_text("أرسل ID المستخدم للترقية:")
        context.user_data['awaiting_premium_user'] = True
        return
    
    elif text == "🔻 إزالة التميز":
        premium_users = db.get_premium_users()
        if premium_users:
            users_text = "👑 المستخدمون المميزون:\n\n"
            for user_data in premium_users:
                users_text += f"{user_data[0]} - {user_data[2]}\n"
            users_text += "\nأرسل ID المستخدم لإزالة التميز:"
            await update.message.reply_text(users_text)
            context.user_data['awaiting_remove_premium'] = True
        else:
            await update.message.reply_text("⚠️ لا يوجد مستخدمين مميزين.")
        return
    
    elif text == "🗑 حذف مستخدم":
        await update.message.reply_text("أرسل ID المستخدم للحذف:")
        context.user_data['awaiting_user_delete'] = True
        return
    
    # إدارة الأقسام - تم إصلاح الحذف
    elif text == "➕ إضافة قسم":
        await update.message.reply_text("أرسل اسم القسم الجديد:")
        context.user_data['adding_category'] = True
        return
    
    elif text == "✏️ تعديل قسم":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                keyboard.append([KeyboardButton(f"تعديل {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة الأقسام")])
            await update.message.reply_text("اختر قسم للتعديل:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
        return
    
    elif text.startswith("تعديل "):
        category_name = text[6:]
        category_id = get_category_id_by_name(category_name)
        if category_id:
            context.user_data['editing_category_id'] = category_id
            context.user_data['editing_category_name'] = category_name
            await update.message.reply_text(f"✏️ تعديل القسم: {category_name}\n\nأرسل الاسم الجديد للقسم:")
            context.user_data['awaiting_new_category_name'] = True
        else:
            await update.message.reply_text("❌ قسم غير موجود")
        return
    
    elif text == "📋 عرض الأقسام":
        categories = db.get_categories()
        if categories:
            cats_text = "📁 جميع الأقسام:\n\n"
            for cat in categories:
                premium_status = "👑" if cat[2] == 1 else "⭐"
                cats_text += f"{premium_status} {cat[1]} (ID: {cat[0]})\n"
            await update.message.reply_text(cats_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
        return
    
    elif text == "🔧 جعل قسم مميز":
        categories = db.get_normal_categories()
        if categories:
            keyboard = []
            for cat in categories:
                keyboard.append([KeyboardButton(f"جعل {cat[1]} مميز")])
            keyboard.append([KeyboardButton("🔙 إدارة الأقسام")])
            await update.message.reply_text("اختر قسم لجعله مميز:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام عادية.")
        return
    
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
        return
    
    # إدارة المحتوى - تم إصلاح الحذف وعرض المحتوى
    elif text == "➕ إضافة محتوى":
        categories = db.get_categories()
        if not categories:
            await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
            return
        
        context.user_data['adding_content'] = True
        context.user_data['content_stage'] = 'type'
        
        keyboard = [
            [KeyboardButton("📝 نص"), KeyboardButton("📸 صورة")],
            [KeyboardButton("🎥 فيديو"), KeyboardButton("🔙 إدارة المحتوى")]
        ]
        await update.message.reply_text("📝 بدء إضافة محتوى جديد\n\nاختر نوع المحتوى:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return
    
    elif text in ["📝 نص", "📸 صورة", "🎥 فيديو"] and context.user_data.get('content_stage') == 'type':
        content_type_map = {"📝 نص": "text", "📸 صورة": "photo", "🎥 فيديو": "video"}
        context.user_data['content_type'] = content_type_map[text]
        context.user_data['content_stage'] = 'title'
        
        await update.message.reply_text("✏️ المرحلة 1 من 3\n\nأرسل عنوان المحتوى (مثال: قصة جميلة، فيديو رائع، إلخ):")
        return
    
    elif text == "📋 عرض المحتوى":
        content_items = db.get_all_content()
        if content_items:
            content_text = "📦 جميع المحتويات:\n\n"
            for content in content_items:
                content_type_icon = "📝" if content[3] == 'text' else "📸" if content[3] == 'photo' else "🎥"
                premium_status = "👑" if content[5] == 1 else "⭐"
                content_text += f"{content_type_icon}{premium_status} {content[1]} - {content[7]}\n"
            await update.message.reply_text(content_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
        return
    
    elif text == "🔧 جعل محتوى مميز":
        content_items = db.get_all_content()
        normal_content = [c for c in content_items if c[5] == 0]
        if normal_content:
            keyboard = []
            for content in normal_content[:10]:
                keyboard.append([KeyboardButton(f"تمييز {content[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
            await update.message.reply_text("اختر محتوى لجعله مميز:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى عادي.")
        return
    
    elif text == "🗑 حذف محتوى":
        content_items = db.get_all_content()
        if content_items:
            keyboard = []
            for content in content_items[:10]:
                keyboard.append([KeyboardButton(f"حذف {content[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
            await update.message.reply_text("اختر محتوى للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
        return
    
    # إدارة المميزين - تم إصلاح الإعدادات
    elif text == "👑 عرض المميزين":
        premium_users = db.get_premium_users()
        if premium_users:
            users_text = "👑 المستخدمون المميزون:\n\n"
            for user_data in premium_users:
                users_text += f"🆔 {user_data[0]} - 👤 {user_data[2]} - 📅 {user_data[7].split()[0] if user_data[7] else 'غير معروف'}\n"
            await update.message.reply_text(users_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد مستخدمين مميزين.")
        return
    
    elif text == "📊 إحصائيات المميزين":
        premium_users = db.get_premium_users()
        total_users = len(db.get_all_users())
        
        stats_text = f"💎 إحصائيات المميزين:\n\n"
        stats_text += f"👑 عدد المميزين: {len(premium_users)}\n"
        stats_text += f"👥 إجمالي المستخدمين: {total_users}\n"
        stats_text += f"📈 نسبة المميزين: {(len(premium_users)/total_users*100) if total_users > 0 else 0:.1f}%"
        
        await update.message.reply_text(stats_text)
        return
    
    elif text == "✏️ تعديل رسالة المميزين":
        current = db.get_setting('premium_access_message')
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_premium_message'] = True
        return
    
    elif text == "🎯 إعدادات المميزين":
        current_message = db.get_setting('premium_access_message')
        await update.message.reply_text(f"🎯 إعدادات المميزين\n\nرسالة المميزين الحالية:\n{current_message}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_premium_message'] = True
        return
    
    # الإعدادات
    elif text == "✏️ رسالة الترحيب":
        current = db.get_setting('welcome_message')
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_welcome'] = True
        return
    
    elif text == "📝 حول البوت":
        current = db.get_setting('about_text')
        await update.message.reply_text(f"النص الحالي:\n{current}\n\nأرسل النص الجديد:")
        context.user_data['editing_about'] = True
        return
    
    elif text == "📞 اتصل بنا":
        current = db.get_setting('contact_text')
        await update.message.reply_text(f"النص الحالي:\n{current}\n\nأرسل النص الجديد:")
        context.user_data['editing_contact'] = True
        return
    
    elif text == "🔄 زر البدء":
        current = db.get_setting('start_button_text')
        await update.message.reply_text(f"النص الحالي: {current}\n\nأرسل النص الجديد لزر البدء:")
        context.user_data['editing_start_button'] = True
        return
    
    elif text == "✏️ اسم قسم المميز":
        current = db.get_setting('premium_section_name')
        await update.message.reply_text(f"الاسم الحالي: {current}\n\nأرسل الاسم الجديد:")
        context.user_data['editing_premium_section_name'] = True
        return
    
    elif text == "🔐 نظام الموافقة":
        current = db.get_setting('approval_required')
        new_status = '0' if current == '1' else '1'
        db.update_setting('approval_required', new_status)
        status = "معطل" if new_status == '0' else "مفعل"
        await update.message.reply_text(f"✅ تم {status} نظام الموافقة")
        return
    
    # معالجة مراحل إضافة المحتوى
    elif context.user_data.get('content_stage') == 'title':
        context.user_data['content_title'] = text
        context.user_data['content_stage'] = 'content'
        
        content_type = context.user_data.get('content_type')
        if content_type == 'text':
            await update.message.reply_text("📝 المرحلة 2 من 3\n\nأرسل محتوى النص:")
        else:
            type_name = "صورة" if content_type == 'photo' else "فيديو"
            await update.message.reply_text(f"📸 المرحلة 2 من 3\n\nأرسل {type_name} الآن:")
        return
    
    elif context.user_data.get('content_stage') == 'content':
        if context.user_data.get('content_type') == 'text':
            context.user_data['content_description'] = text
            context.user_data['content_stage'] = 'category'
            
            categories = db.get_categories()
            keyboard = []
            for cat in categories:
                premium_status = "👑" if cat[2] == 1 else "⭐"
                keyboard.append([KeyboardButton(f"{premium_status} {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
            
            await update.message.reply_text(
                "📁 المرحلة 3 من 3\n\nاختر القسم الذي تريد إضافة المحتوى إليه:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        return
    
    elif context.user_data.get('content_stage') == 'category':
        category_text = text
        if text.startswith("👑 ") or text.startswith("⭐ "):
            category_name = text[2:]
        else:
            category_name = text
            
        category_id = get_category_id_by_name(category_name)
        if category_id:
            keyboard = [
                [KeyboardButton("✅ نعم، جعله مميز"), KeyboardButton("❌ لا، محتوى عادي")],
                [KeyboardButton("🔙 إدارة المحتوى")]
            ]
            
            context.user_data['content_category_id'] = category_id
            context.user_data['content_stage'] = 'premium_choice'
            
            await update.message.reply_text(
                f"🎯 المرحلة النهائية\n\nهل تريد جعل هذا المحتوى مميزاً؟\n\nالعنوان: {context.user_data.get('content_title', 'بدون عنوان')}\nالقسم: {category_name}",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        else:
            await update.message.reply_text("❌ قسم غير موجود. الرجاء اختيار قسم من القائمة.")
        return
    
    elif context.user_data.get('content_stage') == 'premium_choice':
        if text == "✅ نعم، جعله مميز":
            is_premium = True
        elif text == "❌ لا، محتوى عادي":
            is_premium = False
        else:
            await update.message.reply_text("❌ الرجاء الاختيار من الخيارات المتاحة.")
            return
        
        title = context.user_data.get('content_title', 'بدون عنوان')
        content_type = context.user_data.get('content_type', 'text')
        description = context.user_data.get('content_description', '')
        category_id = context.user_data.get('content_category_id')
        file_id = context.user_data.get('content_file_id')
        
        db.add_content(title, description, content_type, category_id, is_premium, file_id)
        
        status = "مميز 👑" if is_premium else "عادي ⭐"
        content_type_name = "نص" if content_type == 'text' else "صورة" if content_type == 'photo' else "فيديو"
        
        await update.message.reply_text(
            f"✅ تم إضافة المحتوى بنجاح!\n\n"
            f"📝 النوع: {content_type_name}\n"
            f"🎯 العنوان: {title}\n"
            f"📁 القسم: {get_category_name_by_id(category_id)}\n"
            f"💎 الحالة: {status}",
            reply_markup=admin_content_menu()
        )
        context.user_data.clear()
        return
    
    # معالجة إدخال البيانات الأخرى
    elif context.user_data.get('awaiting_premium_user'):
        try:
            target_user_id = int(text)
            db.make_premium(target_user_id)
            await update.message.reply_text(f"✅ تم ترقية المستخدم {target_user_id} إلى مميز", reply_markup=admin_users_menu())
        except:
            await update.message.reply_text("❌ ID غير صحيح", reply_markup=admin_users_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('awaiting_remove_premium'):
        try:
            target_user_id = int(text)
            db.remove_premium(target_user_id)
            await update.message.reply_text(f"✅ تم إزالة التميز من المستخدم {target_user_id}", reply_markup=admin_users_menu())
        except:
            await update.message.reply_text("❌ ID غير صحيح", reply_markup=admin_users_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('awaiting_user_delete'):
        try:
            target_user_id = int(text)
            db.delete_user(target_user_id)
            await update.message.reply_text(f"✅ تم حذف المستخدم {target_user_id}", reply_markup=admin_users_menu())
        except:
            await update.message.reply_text("❌ ID غير صحيح", reply_markup=admin_users_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('adding_category'):
        db.add_category(text)
        await update.message.reply_text(f"✅ تم إضافة القسم: {text}", reply_markup=admin_categories_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('awaiting_new_category_name'):
        category_id = context.user_data.get('editing_category_id')
        old_name = context.user_data.get('editing_category_name')
        if category_id:
            db.update_category(category_id, text, 0)
            await update.message.reply_text(f"✅ تم تعديل القسم من '{old_name}' إلى '{text}'", reply_markup=admin_categories_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_premium_message'):
        db.update_setting('premium_access_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة المميزين", reply_markup=admin_settings_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_welcome'):
        db.update_setting('welcome_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب", reply_markup=admin_settings_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_about'):
        db.update_setting('about_text', text)
        await update.message.reply_text("✅ تم تحديث حول البوت", reply_markup=admin_settings_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_contact'):
        db.update_setting('contact_text', text)
        await update.message.reply_text("✅ تم تحديث اتصل بنا", reply_markup=admin_settings_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_start_button'):
        db.update_setting('start_button_text', text)
        await update.message.reply_text("✅ تم تحديث زر البدء", reply_markup=admin_settings_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_premium_section_name'):
        db.update_setting('premium_section_name', text)
        await update.message.reply_text(f"✅ تم تحديث اسم قسم المميز إلى: {text}", reply_markup=admin_settings_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('broadcasting'):
        users = db.get_all_users()
        success = 0
        for user_data in users:
            try:
                await context.bot.send_message(
                    chat_id=user_data[0], 
                    text=f"📢 إشعار من الإدارة:\n\n{text}"
                )
                success += 1
            except:
                continue
        await update.message.reply_text(f"✅ تم الإرسال إلى {success} مستخدم", reply_markup=admin_main_menu())
        context.user_data.clear()
        return
    
    # معالجة الأزرار الخاصة - تم إصلاح جميع مشاكل الحذف
    elif text.startswith("جعل "):
        if text.endswith(" مميز"):
            category_name = text[4:-5]
            category_id = get_category_id_by_name(category_name)
            if category_id:
                db.update_category(category_id, category_name, 1)
                await update.message.reply_text(f"✅ تم جعل القسم {category_name} مميز", reply_markup=admin_categories_menu())
            else:
                await update.message.reply_text("❌ قسم غير موجود")
        return
    
    elif text.startswith("تمييز "):
        content_title = text[7:]
        all_content = db.get_all_content()
        content_found = False
        for content in all_content:
            if content[1].startswith(content_title):
                db.conn.execute('UPDATE content SET is_premium = 1 WHERE id = ?', (content[0],))
                db.conn.commit()
                await update.message.reply_text(f"✅ تم جعل المحتوى {content[1]} مميز", reply_markup=admin_content_menu())
                content_found = True
                break
        
        if not content_found:
            await update.message.reply_text("❌ محتوى غير موجود")
        return
    
    elif text.startswith("حذف "):
        # حذف قسم
        category_name = text[5:]
        category_id = get_category_id_by_name(category_name)
        if category_id:
            db.delete_category(category_id)
            await update.message.reply_text(f"✅ تم حذف القسم: {category_name}", reply_markup=admin_categories_menu())
            return
        
        # حذف محتوى
        all_content = db.get_all_content()
        content_found = False
        for content in all_content:
            if content[1].startswith(category_name):
                db.delete_content(content[0])
                await update.message.reply_text(f"✅ تم حذف المحتوى: {content[1]}", reply_markup=admin_content_menu())
                content_found = True
                break
        
        if not content_found:
            await update.message.reply_text("❌ غير موجود")
        return
    
    else:
        await update.message.reply_text("👑 لوحة تحكم المدير", reply_markup=admin_main_menu())

# دوال مساعدة
async def show_statistics(update: Update, context: CallbackContext):
    total_users = len(db.get_all_users())
    active_users = len(db.get_active_users(30))
    premium_users = len(db.get_premium_users())
    total_content = len(db.get_all_content())
    total_categories = len(db.get_categories())
    premium_categories = len(db.get_premium_categories())
    
    stats_text = f"📊 إحصائيات البوت:\n\n"
    stats_text += f"👥 المستخدمون: {total_users}\n"
    stats_text += f"🎯 النشطون: {active_users}\n"
    stats_text += f"💎 المميزون: {premium_users}\n"
    stats_text += f"📦 المحتوى: {total_content}\n"
    stats_text += f"📁 الأقسام: {total_categories}\n"
    stats_text += f"👑 الأقسام المميزة: {premium_categories}"
    
    await update.message.reply_text(stats_text)

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

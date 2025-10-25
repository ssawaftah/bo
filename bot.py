import os
import logging
import sqlite3
import json
import zipfile
import io
import tempfile
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
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                has_subscribed INTEGER DEFAULT 0
            )
        ''')

        # جدول الأقسام
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
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
        
        # جدول النسخ الاحتياطية
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_name TEXT,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                description TEXT
            )
        ''')
        self.conn.commit()

    def create_admin(self):
        admin_id = int(os.getenv('ADMIN_ID', 123456789))
        self.conn.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, is_approved, is_admin, is_premium, has_subscribed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (admin_id, 'admin', 'Admin', 'Bot', 1, 1, 1, 1))
        self.conn.commit()

    def create_default_settings(self):
        default_settings = [
            ('welcome_message', '🎭 مرحباً بك في بوت المحتوى المميز!'),
            ('approval_required', '1'),
            ('about_text', '🤖 بوت المحتوى التفاعلي\n\nبوت متخصص لمشاركة المحتوى المميز.'),
            ('contact_text', '📞 للتواصل: @username'),
            ('start_button_text', '🚀 ابدأ الرحلة'),
            ('auto_approve', '0'),
            ('admin_contact', '@username'),
            ('backup_password', 'Mkfrky'),
            ('subscription_required', '0'),
            ('subscription_channel', '@username'),
            ('subscription_message', '📢 يجب الاشتراك في القناة أولاً لاستخدام البوت\n\nاشترك ثم اضغط على زر التحقق'),
            ('subscription_success_message', '✅ شكراً لك! تم التحقق من اشتراكك بنجاح\n\nيمكنك الآن استخدام البوت')
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

    def mark_user_subscribed(self, user_id):
        self.conn.execute('UPDATE users SET has_subscribed = 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def add_category(self, name):
        self.conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (name,))
        self.conn.commit()
        return self.conn.execute('SELECT last_insert_rowid()').fetchone()[0]

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories ORDER BY name')
        return cursor.fetchall()

    def update_category(self, category_id, name):
        self.conn.execute('UPDATE categories SET name = ? WHERE id = ?', (name, category_id))
        self.conn.commit()

    def delete_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        category = cursor.fetchone()
        if not category:
            return False
        
        self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.execute('DELETE FROM content WHERE category_id = ?', (category_id,))
        self.conn.commit()
        return True

    def add_content(self, title, content, content_type, category_id, file_id=None):
        self.conn.execute('''
            INSERT INTO content (title, content, content_type, category_id, file_id) 
            VALUES (?, ?, ?, ?, ?)
        ''', (title, content, content_type, category_id, file_id))
        self.conn.commit()
        return self.conn.execute('SELECT last_insert_rowid()').fetchone()[0]

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

    def get_recent_content(self, limit=7):
        cursor = self.conn.execute('''
            SELECT c.*, cat.name as category_name 
            FROM content c JOIN categories cat ON c.category_id = cat.id 
            ORDER BY c.created_date DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def delete_content(self, content_id):
        cursor = self.conn.execute('SELECT * FROM content WHERE id = ?', (content_id,))
        content = cursor.fetchone()
        if not content:
            return False
        
        self.conn.execute('DELETE FROM content WHERE id = ?', (content_id,))
        self.conn.commit()
        return True

    def get_content(self, content_id):
        cursor = self.conn.execute('SELECT * FROM content WHERE id = ?', (content_id,))
        return cursor.fetchone()

    def get_category_by_id(self, category_id):
        cursor = self.conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        return cursor.fetchone()

    def search_content_by_title(self, title):
        cursor = self.conn.execute('SELECT * FROM content WHERE title LIKE ?', (f'%{title}%',))
        return cursor.fetchall()

    def create_backup(self):
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'version': '2.0',
            'users': self.get_all_users_data(),
            'categories': self.get_all_categories_data(),
            'content': self.get_all_content_data(),
            'settings': self.get_all_settings_data(),
            'join_requests': self.get_all_join_requests_data()
        }
        return backup_data

    def get_all_users_data(self):
        cursor = self.conn.execute('SELECT * FROM users')
        columns = [description[0] for description in cursor.description]
        users = cursor.fetchall()
        return {'columns': columns, 'data': users}

    def get_all_categories_data(self):
        cursor = self.conn.execute('SELECT * FROM categories')
        columns = [description[0] for description in cursor.description]
        categories = cursor.fetchall()
        return {'columns': columns, 'data': categories}

    def get_all_content_data(self):
        cursor = self.conn.execute('SELECT * FROM content')
        columns = [description[0] for description in cursor.description]
        content = cursor.fetchall()
        return {'columns': columns, 'data': content}

    def get_all_settings_data(self):
        cursor = self.conn.execute('SELECT * FROM bot_settings')
        columns = [description[0] for description in cursor.description]
        settings = cursor.fetchall()
        return {'columns': columns, 'data': settings}

    def get_all_join_requests_data(self):
        cursor = self.conn.execute('SELECT * FROM join_requests')
        columns = [description[0] for description in cursor.description]
        requests = cursor.fetchall()
        return {'columns': columns, 'data': requests}

    def restore_backup(self, backup_data):
        try:
            self.conn.execute('BEGIN TRANSACTION')
            
            self.conn.execute('DELETE FROM users')
            self.conn.execute('DELETE FROM categories')
            self.conn.execute('DELETE FROM content')
            self.conn.execute('DELETE FROM bot_settings')
            self.conn.execute('DELETE FROM join_requests')
            
            users_data = backup_data.get('users', {})
            if users_data.get('data'):
                columns = users_data['columns']
                placeholders = ', '.join(['?'] * len(columns))
                for row in users_data['data']:
                    self.conn.execute(f'INSERT INTO users ({", ".join(columns)}) VALUES ({placeholders})', row)
            
            categories_data = backup_data.get('categories', {})
            if categories_data.get('data'):
                columns = categories_data['columns']
                placeholders = ', '.join(['?'] * len(columns))
                for row in categories_data['data']:
                    self.conn.execute(f'INSERT INTO categories ({", ".join(columns)}) VALUES ({placeholders})', row)
            
            content_data = backup_data.get('content', {})
            if content_data.get('data'):
                columns = content_data['columns']
                placeholders = ', '.join(['?'] * len(columns))
                for row in content_data['data']:
                    self.conn.execute(f'INSERT INTO content ({", ".join(columns)}) VALUES ({placeholders})', row)
            
            settings_data = backup_data.get('settings', {})
            if settings_data.get('data'):
                columns = settings_data['columns']
                placeholders = ', '.join(['?'] * len(columns))
                for row in settings_data['data']:
                    self.conn.execute(f'INSERT INTO bot_settings ({", ".join(columns)}) VALUES ({placeholders})', row)
            
            requests_data = backup_data.get('join_requests', {})
            if requests_data.get('data'):
                columns = requests_data['columns']
                placeholders = ', '.join(['?'] * len(columns))
                for row in requests_data['data']:
                    self.conn.execute(f'INSERT INTO join_requests ({", ".join(columns)}) VALUES ({placeholders})', row)
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.execute('ROLLBACK')
            logger.error(f"خطأ في استعادة النسخة الاحتياطية: {e}")
            return False

    def add_backup_record(self, backup_name, file_size, description=""):
        self.conn.execute('''
            INSERT INTO backups (backup_name, file_size, description)
            VALUES (?, ?, ?)
        ''', (backup_name, file_size, description))
        self.conn.commit()

    def get_backup_history(self):
        cursor = self.conn.execute('SELECT * FROM backups ORDER BY backup_date DESC LIMIT 10')
        return cursor.fetchall()

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
    category = db.get_category_by_id(category_id)
    return category[1] if category else "غير معروف"

async def check_subscription(user_id, context: CallbackContext):
    """التحقق من اشتراك المستخدم في القناة"""
    subscription_channel = db.get_setting('subscription_channel')
    if not subscription_channel or subscription_channel == '@username':
        return True
    
    try:
        # إزالة @ من اسم القناة إذا وجد
        channel = subscription_channel.replace('@', '')
        chat_member = await context.bot.get_chat_member(f'@{channel}', user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"خطأ في التحقق من الاشتراك: {e}")
        return False

def user_main_menu():
    keyboard = [
        [KeyboardButton("📁 الاقسام"), KeyboardButton("📚 آخر القصص")],
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_subscription_menu():
    subscription_channel = db.get_setting('subscription_channel')
    keyboard = [
        [InlineKeyboardButton("📢 انضم إلى القناة", url=f"https://t.me/{subscription_channel.replace('@', '')}")],
        [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")],
        [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_subscription")]
    ]
    return InlineKeyboardMarkup(keyboard)

def user_categories_menu():
    categories = db.get_categories()
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
    
    for content in content_items:
        short_title = content[1][:20] + "..." if len(content[1]) > 20 else content[1]
        keyboard.append([InlineKeyboardButton(f"📄 {short_title}", callback_data=f"content_{content[0]}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_categories")])
    
    return InlineKeyboardMarkup(keyboard)

def user_recent_content_menu():
    recent_content = db.get_recent_content(7)
    keyboard = []
    
    for content in recent_content:
        short_title = content[1][:20] + "..." if len(content[1]) > 20 else content[1]
        keyboard.append([InlineKeyboardButton(f"📄 {short_title}", callback_data=f"content_{content[0]}")])
    
    keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

def admin_main_menu():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📦 إدارة المحتوى"), KeyboardButton("⚙️ إعدادات البوت")],
        [KeyboardButton("📊 الإحصائيات"), KeyboardButton("📢 البث الجماعي")],
        [KeyboardButton("💾 النسخ الاحتياطي"), KeyboardButton("🔙 وضع المستخدم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_users_menu():
    keyboard = [
        [KeyboardButton("📋 عرض المستخدمين"), KeyboardButton("⏳ طلبات الانضمام")],
        [KeyboardButton("🗑 حذف مستخدم"), KeyboardButton("🔙 لوحة التحكم")]
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
        [KeyboardButton("➕ إضافة محتوى"), KeyboardButton("🗑 حذف محتوى")],
        [KeyboardButton("📋 عرض المحتوى"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_settings_menu():
    keyboard = [
        [KeyboardButton("✏️ رسالة الترحيب"), KeyboardButton("📝 حول البوت")],
        [KeyboardButton("📞 اتصل بنا"), KeyboardButton("🔄 زر البدء")],
        [KeyboardButton("🔐 نظام الموافقة"), KeyboardButton("📢 إعدادات الاشتراك")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_subscription_menu():
    subscription_status = "✅ مفعل" if db.get_setting('subscription_required') == '1' else "❌ معطل"
    keyboard = [
        [KeyboardButton(f"🔧 حالة الاشتراك: {subscription_status}")],
        [KeyboardButton("✏️ رسالة الاشتراك"), KeyboardButton("🔗 رابط القناة")],
        [KeyboardButton("✏️ رسالة النجاح"), KeyboardButton("🔙 الإعدادات")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_backup_menu():
    keyboard = [
        [KeyboardButton("📥 تنزيل نسخة"), KeyboardButton("📤 رفع نسخة")],
        [KeyboardButton("📋 سجل النسخ"), KeyboardButton("🔧 إعدادات النسخ")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_categories_list():
    categories = db.get_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(cat[1], callback_data=f"delete_cat_{cat[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="cancel_delete")])
    return InlineKeyboardMarkup(keyboard)

def admin_content_list():
    content_items = db.get_all_content()
    keyboard = []
    for content in content_items[:15]:
        short_title = content[1][:15] + "..." if len(content[1]) > 15 else content[1]
        keyboard.append([InlineKeyboardButton(f"🗑 {short_title}", callback_data=f"delete_content_{content[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="cancel_delete")])
    return InlineKeyboardMarkup(keyboard)

async def create_and_send_backup(update: Update, context: CallbackContext):
    try:
        backup_data = db.create_backup()
        json_data = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('backup_data.json', json_data)
        
        zip_buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bot_backup_{timestamp}.Mkfrky"
        
        if isinstance(update, Update) and update.message:
            await update.message.reply_document(
                document=zip_buffer,
                filename=filename,
                caption=f"📦 النسخة الاحتياطية للبوت\n\n✅ تم إنشاء النسخة في: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🔐 كلمة السر: {db.get_setting('backup_password')}"
            )
        else:
            await update.callback_query.message.reply_document(
                document=zip_buffer,
                filename=filename,
                caption=f"📦 النسخة الاحتياطية للبوت\n\n✅ تم إنشاء النسخة في: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🔐 كلمة السر: {db.get_setting('backup_password')}"
            )
        
        db.add_backup_record(filename, len(zip_buffer.getvalue()), "نسخة احتياطية تلقائية")
        
    except Exception as e:
        error_msg = f"❌ خطأ في إنشاء النسخة الاحتياطية: {str(e)}"
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(error_msg)
        else:
            await update.callback_query.message.reply_text(error_msg)

async def restore_backup_from_file(update: Update, context: CallbackContext, file):
    try:
        file_obj = await context.bot.get_file(file.file_id)
        file_content = await file_obj.download_as_bytearray()
        
        zip_buffer = io.BytesIO(file_content)
        with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
            json_data = zip_file.read('backup_data.json').decode('utf-8')
            backup_data = json.loads(json_data)
        
        success = db.restore_backup(backup_data)
        
        if success:
            await update.message.reply_text(
                f"✅ تم استعادة النسخة الاحتياطية بنجاح!\n\n"
                f"📅 تاريخ النسخة: {backup_data.get('timestamp', 'غير معروف')}\n"
                f"👥 المستخدمون: {len(backup_data.get('users', {}).get('data', []))}\n"
                f"📁 الأقسام: {len(backup_data.get('categories', {}).get('data', []))}\n"
                f"📦 المحتوى: {len(backup_data.get('content', {}).get('data', []))}",
                reply_markup=admin_main_menu()
            )
            
            filename = file.file_name
            db.add_backup_record(filename, len(file_content), "استعادة نسخة احتياطية")
        else:
            await update.message.reply_text("❌ فشل في استعادة النسخة الاحتياطية")
            
    except zipfile.BadZipFile:
        await update.message.reply_text("❌ الملف ليس نسخة احتياطية صالحة")
    except KeyError:
        await update.message.reply_text("❌ الملف لا يحتوي على بيانات نسخ احتياطي صالحة")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في استعادة النسخة الاحتياطية: {str(e)}")

async def show_backup_history(update: Update, context: CallbackContext):
    backups = db.get_backup_history()
    
    if backups:
        history_text = "📋 سجل النسخ الاحتياطية:\n\n"
        for backup in backups:
            date = backup[3].split()[0] if backup[3] else "غير معروف"
            size_kb = backup[4] / 1024 if backup[4] else 0
            history_text += f"📁 {backup[1]}\n"
            history_text += f"📅 {date} | 📊 {size_kb:.1f} KB\n"
            if backup[5]:
                history_text += f"📝 {backup[5]}\n"
            history_text += "─" * 30 + "\n"
    else:
        history_text = "⚠️ لا توجد نسخ احتياطية سابقة"
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(history_text)
    else:
        await update.message.reply_text(history_text)

async def show_statistics(update: Update, context: CallbackContext):
    total_users = len(db.get_all_users())
    active_users = len(db.get_active_users(30))
    total_content = len(db.get_all_content())
    total_categories = len(db.get_categories())
    
    stats_text = f"📊 إحصائيات البوت:\n\n"
    stats_text += f"👥 المستخدمون: {total_users}\n"
    stats_text += f"🎯 النشطون: {active_users}\n"
    stats_text += f"📦 المحتوى: {total_content}\n"
    stats_text += f"📁 الأقسام: {total_categories}"
    
    await update.message.reply_text(stats_text)

async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    context.user_data.clear()
    db.update_user_activity(user_id)
    
    # التحقق أولاً إذا كان المستخدم موجوداً ومقبولاً
    existing_user = db.get_user(user_id)
    
    if existing_user:
        # المستخدم موجود في النظام
        if is_admin(user_id):
            await update.message.reply_text(
                "👑 مرحباً بك آلة المدير!\n\nلوحة التحكم المتقدمة جاهزة.",
                reply_markup=admin_main_menu()
            )
            return
        
        if existing_user[4] == 1:  # المستخدم مقبول
            subscription_required = db.get_setting('subscription_required') == '1'
            
            # التحقق من الاشتراك إذا كان مطلوباً
            if subscription_required and existing_user[9] == 0:
                subscription_message = db.get_setting('subscription_message')
                subscription_channel = db.get_setting('subscription_channel')
                
                await update.message.reply_text(
                    f"{subscription_message}\n\nالقناة: {subscription_channel}",
                    reply_markup=user_subscription_menu()
                )
                return
            
            welcome_message = db.get_setting('welcome_message')
            await update.message.reply_text(
                f"{welcome_message}\n\nمرحباً بك مرة أخرى {user.first_name}! 👋",
                reply_markup=user_main_menu()
            )
            return
        else:
            # المستخدم موجود لكن غير مقبول
            await update.message.reply_text(
                "⏳ لا يزال طلبك قيد المراجعة...",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔄 تحديث الحالة")]], resize_keyboard=True)
            )
            return
    
    # المستخدم جديد - إضافته للنظام
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
        subscription_required = db.get_setting('subscription_required') == '1'
        
        # التحقق من الاشتراك إذا كان مطلوباً
        if subscription_required and user_data[9] == 0:
            subscription_message = db.get_setting('subscription_message')
            subscription_channel = db.get_setting('subscription_channel')
            
            await update.message.reply_text(
                f"{subscription_message}\n\nالقناة: {subscription_channel}",
                reply_markup=user_subscription_menu()
            )
            return
        
        welcome_message = db.get_setting('welcome_message')
        await update.message.reply_text(
            f"{welcome_message}\n\nمرحباً بك {user.first_name}! 👋",
            reply_markup=user_main_menu()
        )
    elif not approval_required:
        db.approve_user(user_id)
        
        subscription_required = db.get_setting('subscription_required') == '1'
        if subscription_required:
            subscription_message = db.get_setting('subscription_message')
            subscription_channel = db.get_setting('subscription_channel')
            
            await update.message.reply_text(
                f"{subscription_message}\n\nالقناة: {subscription_channel}",
                reply_markup=user_subscription_menu()
            )
            return
        
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

async def handle_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith('approve_'):
        if not is_admin(user_id):
            await query.edit_message_text("❌ ليس لديك صلاحية.")
            return
            
        target_user_id = int(data.split('_')[1])
        db.approve_user(target_user_id)
        
        try:
            # إرسال رسالة للمستخدم بأنه تمت الموافقته
            user_data = db.get_user(target_user_id)
            if user_data:
                subscription_required = db.get_setting('subscription_required') == '1'
                
                if subscription_required:
                    subscription_message = db.get_setting('subscription_message')
                    subscription_channel = db.get_setting('subscription_channel')
                    
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"🎉 تمت الموافقة على طلبك!\n\n{subscription_message}\n\nالقناة: {subscription_channel}",
                        reply_markup=user_subscription_menu()
                    )
                else:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text="🎉 تمت الموافقة على طلبك!\n\nيمكنك الآن استخدام البوت.",
                        reply_markup=user_main_menu()
                    )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
        
        await query.edit_message_text(f"✅ تمت الموافقة على المستخدم {target_user_id}")
        
    elif data.startswith('reject_'):
        if not is_admin(user_id):
            await query.edit_message_text("❌ ليس لديك صلاحية.")
            return
            
        target_user_id = int(data.split('_')[1])
        db.reject_user(target_user_id)
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="❌ تم رفض طلب انضمامك."
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
            
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")
    
    elif data.startswith('content_'):
        content_id = int(data.split('_')[1])
        content = db.get_content(content_id)
        
        if content:
            if content[3] == 'text':
                await query.message.reply_text(
                    f"📖 {content[1]}\n\n{content[2]}\n\n---\nنهاية المحتوى 📚"
                )
            elif content[3] == 'photo' and content[5]:
                await query.message.reply_photo(
                    photo=content[5],
                    caption=f"📸 {content[1]}\n\n{content[2]}"
                )
            elif content[3] == 'video' and content[5]:
                await query.message.reply_video(
                    video=content[5],
                    caption=f"🎥 {content[1]}\n\n{content[2]}"
                )
        else:
            await query.message.reply_text("❌ المحتوى غير موجود")
    
    elif data == 'back_to_categories':
        categories = db.get_categories()
        if categories:
            await query.message.edit_text("📁 الاقسام المتاحة:\n\nاختر قسم:", reply_markup=user_categories_menu())
        else:
            await query.message.edit_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif data == 'back_to_main':
        await query.message.edit_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    elif data == 'check_subscription' or data == 'refresh_subscription':
        subscription_required = db.get_setting('subscription_required') == '1'
        
        if not subscription_required:
            await query.edit_message_text("✅ نظام الاشتراك غير مفعل حالياً")
            return
        
        is_subscribed = await check_subscription(user_id, context)
        
        if is_subscribed:
            db.mark_user_subscribed(user_id)
            success_message = db.get_setting('subscription_success_message')
            
            # إرسال رسالة جديدة بدلاً من تعديل الرسالة القديمة
            await query.message.reply_text(
                f"{success_message}\n\nمرحباً بك في البوت! 👋",
                reply_markup=user_main_menu()
            )
            
            # حذف الرسالة القديمة
            try:
                await query.message.delete()
            except:
                pass
        else:
            subscription_message = db.get_setting('subscription_message')
            subscription_channel = db.get_setting('subscription_channel')
            
            # إرسال رسالة جديدة بدلاً من تعديل الرسالة القديمة
            await query.message.reply_text(
                f"❌ لم يتم التحقق من اشتراكك بعد!\n\n{subscription_message}\n\nالقناة: {subscription_channel}",
                reply_markup=user_subscription_menu()
            )
            
            # حذف الرسالة القديمة
            try:
                await query.message.delete()
            except:
                pass
    
    elif data.startswith('delete_cat_'):
        if not is_admin(user_id):
            await query.edit_message_text("❌ ليس لديك صلاحية.")
            return
            
        category_id = int(data.split('_')[2])
        category = db.get_category_by_id(category_id)
        
        if category:
            success = db.delete_category(category_id)
            if success:
                await query.edit_message_text(f"✅ تم حذف القسم: {category[1]}", reply_markup=admin_categories_menu())
            else:
                await query.edit_message_text("❌ حدث خطأ أثناء حذف القسم")
        else:
            await query.edit_message_text("❌ القسم غير موجود")
    
    elif data.startswith('delete_content_'):
        if not is_admin(user_id):
            await query.edit_message_text("❌ ليس لديك صلاحية.")
            return
            
        content_id = int(data.split('_')[2])
        content = db.get_content(content_id)
        
        if content:
            success = db.delete_content(content_id)
            if success:
                await query.edit_message_text(f"✅ تم حذف المحتوى: {content[1]}", reply_markup=admin_content_menu())
            else:
                await query.edit_message_text("❌ حدث خطأ أثناء حذف المحتوى")
        else:
            await query.edit_message_text("❌ المحتوى غير موجود")
    
    elif data == 'cancel_delete':
        await query.edit_message_text("❌ تم إلغاء العملية", reply_markup=admin_main_menu())
    
    elif data == 'download_backup':
        if not is_admin(user_id):
            await query.edit_message_text("❌ ليس لديك صلاحية.")
            return
        
        await create_and_send_backup(update, context)
    
    elif data == 'backup_history':
        if not is_admin(user_id):
            await query.edit_message_text("❌ ليس لديك صلاحية.")
            return
        
        await show_backup_history(update, context)

async def handle_media(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    if not is_admin(user_id):
        return
    
    if update.message.document:
        file = update.message.document
        filename = file.file_name
        
        if filename and filename.endswith('.Mkfrky'):
            await update.message.reply_text("🔄 جاري استعادة النسخة الاحتياطية...")
            await restore_backup_from_file(update, context, file)
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
            if categories:
                keyboard = []
                for cat in categories:
                    keyboard.append([KeyboardButton(cat[1])])
                keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
                
                await update.message.reply_text(
                    "📁 المرحلة 3 من 3\n\nاختر القسم الذي تريد إضافة المحتوى إليه:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
            else:
                await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
                context.user_data.clear()

async def handle_user_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if is_admin(user_id):
        await handle_admin_message(update, context)
        return
    
    db.update_user_activity(user_id)
    user_data = db.get_user(user_id)
    
    if not user_data:
        # إذا لم يكن المستخدم موجوداً في النظام
        await start(update, context)
        return
    
    if user_data[4] == 0:  # المستخدم غير مقبول
        if text == "🔄 تحديث الحالة":
            user_data = db.get_user(user_id)
            if user_data and user_data[4] == 1:
                subscription_required = db.get_setting('subscription_required') == '1'
                if subscription_required and user_data[9] == 0:
                    subscription_message = db.get_setting('subscription_message')
                    subscription_channel = db.get_setting('subscription_channel')
                    
                    await update.message.reply_text(
                        f"🎉 تمت الموافقة على طلبك!\n\n{subscription_message}\n\nالقناة: {subscription_channel}",
                        reply_markup=user_subscription_menu()
                    )
                    return
                
                await update.message.reply_text("🎉 تمت الموافقة على طلبك!", reply_markup=user_main_menu())
            else:
                await update.message.reply_text("⏳ لا يزال طلبك قيد المراجعة...")
        return
    
    # التحقق من الاشتراك إذا كان مطلوباً
    subscription_required = db.get_setting('subscription_required') == '1'
    if subscription_required and user_data[9] == 0:
        if text != "🔄 تحديث الحالة":
            subscription_message = db.get_setting('subscription_message')
            subscription_channel = db.get_setting('subscription_channel')
            
            await update.message.reply_text(
                f"{subscription_message}\n\nالقناة: {subscription_channel}",
                reply_markup=user_subscription_menu()
            )
            return
    
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    elif text == "📁 الاقسام":
        categories = db.get_categories()
        if categories:
            await update.message.reply_text("📁 الاقسام المتاحة:\n\nاختر قسم:", reply_markup=user_categories_menu())
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif text == "📚 آخر القصص":
        recent_content = db.get_recent_content(7)
        if recent_content:
            await update.message.reply_text(
                "📚 آخر القصص المضافة:\n\nاختر قصة للقراءة:",
                reply_markup=user_recent_content_menu()
            )
        else:
            await update.message.reply_text("⚠️ لا توجد قصص متاحة حالياً.")
    
    elif text == "ℹ️ حول البوت":
        about_text = db.get_setting('about_text')
        await update.message.reply_text(about_text)
    
    elif text == "📞 اتصل بنا":
        contact_text = db.get_setting('contact_text')
        await update.message.reply_text(contact_text)
    
    else:
        category_id = get_category_id_by_name(text)
        if category_id:
            content_items = db.get_content_by_category(category_id)
            if content_items:
                await update.message.reply_text(
                    f"📁 قسم: {text}\n\nاختر المحتوى:",
                    reply_markup=user_content_menu(text, category_id)
                )
            else:
                await update.message.reply_text(f"⚠️ لا يوجد محتوى في قسم {text}.")
            return
        
        await update.message.reply_text("❌ لم أفهم طلبك.", reply_markup=user_main_menu())

# ... باقي دوال handle_admin_message و error_handler تبقى كما هي بدون تغيير ...
# [يتبع باقي الكود بدون تغيير]
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if not is_admin(user_id):
        return

    db.update_user_activity(user_id)

    if text in ["🔙 لوحة التحكم", "🔙 إدارة الأقسام", "🔙 إدارة المحتوى", "🔙 إدارة المستخدمين", "🔙 النسخ الاحتياطي", "🔙 الإعدادات"]:
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
    
    elif text == "⚙️ إعدادات البوت":
        await update.message.reply_text("⚙️ إعدادات البوت", reply_markup=admin_settings_menu())
        return
    
    elif text == "📢 إعدادات الاشتراك":
        await update.message.reply_text("📢 إعدادات الاشتراك الإجباري", reply_markup=admin_subscription_menu())
        return
    
    elif text.startswith("🔧 حالة الاشتراك:"):
        current = db.get_setting('subscription_required')
        new_status = '0' if current == '1' else '1'
        db.update_setting('subscription_required', new_status)
        status = "معطل" if new_status == '0' else "مفعل"
        await update.message.reply_text(f"✅ تم {status} نظام الاشتراك الإجباري", reply_markup=admin_subscription_menu())
        return
    
    elif text == "✏️ رسالة الاشتراك":
        current = db.get_setting('subscription_message')
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_subscription_message'] = True
        return
    
    elif text == "🔗 رابط القناة":
        current = db.get_setting('subscription_channel')
        await update.message.reply_text(f"رابط القناة الحالي: {current}\n\nأرسل رابط القناة الجديد (مثال: @channel_name):")
        context.user_data['editing_subscription_channel'] = True
        return
    
    elif text == "✏️ رسالة النجاح":
        current = db.get_setting('subscription_success_message')
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_subscription_success'] = True
        return
    
    elif text == "💾 النسخ الاحتياطي":
        await update.message.reply_text("💾 نظام النسخ الاحتياطي", reply_markup=admin_backup_menu())
        return
    
    elif text == "📊 الإحصائيات":
        await show_statistics(update, context)
        return
    
    elif text == "📢 البث الجماعي":
        await update.message.reply_text("أرسل الرسالة للبث لجميع المستخدمين:")
        context.user_data['broadcasting'] = True
        return
    
    elif text == "📥 تنزيل نسخة":
        await update.message.reply_text("🔄 جاري إنشاء النسخة الاحتياطية...")
        await create_and_send_backup(update, context)
        return
    
    elif text == "📤 رفع نسخة":
        await update.message.reply_text(
            "📤 لرفع نسخة احتياطية:\n\n"
            "1. أرسل ملف النسخة الاحتياطية (بصيغة .Mkfrky)\n"
            "2. انتظر اكتمال الاستعادة\n\n"
            "⚠️ تحذير: سيتم استبدال جميع البيانات الحالية!"
        )
        context.user_data['awaiting_backup_file'] = True
        return
    
    elif text == "📋 سجل النسخ":
        await show_backup_history(update, context)
        return
    
    elif text == "🔧 إعدادات النسخ":
        current_password = db.get_setting('backup_password')
        await update.message.reply_text(
            f"🔧 إعدادات النسخ الاحتياطي:\n\n"
            f"🔐 كلمة السر الحالية: {current_password}\n\n"
            f"أرسل كلمة السر الجديدة:"
        )
        context.user_data['editing_backup_password'] = True
        return
    
    elif text == "📋 عرض المستخدمين":
        users = db.get_all_users()
        if users:
            users_text = "👥 المستخدمون:\n\n"
            for user_data in users:
                subscription_status = "✅" if user_data[9] == 1 else "❌"
                users_text += f"{subscription_status} {user_data[0]} - 👤 {user_data[2]}\n"
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
    
    elif text == "🗑 حذف مستخدم":
        await update.message.reply_text("أرسل ID المستخدم للحذف:")
        context.user_data['awaiting_user_delete'] = True
        return
    
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
                cats_text += f"📁 {cat[1]} (ID: {cat[0]})\n"
            await update.message.reply_text(cats_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
        return
    
    elif text == "🗑 حذف قسم":
        categories = db.get_categories()
        if categories:
            await update.message.reply_text(
                "اختر قسم للحذف:",
                reply_markup=admin_categories_list()
            )
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
        return
    
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
    
    elif text == "📋 عرض المحتوى":
        content_items = db.get_all_content()
        if content_items:
            content_text = "📦 جميع المحتويات:\n\n"
            for content in content_items:
                content_type_icon = "📝" if content[3] == 'text' else "📸" if content[3] == 'photo' else "🎥"
                content_text += f"{content_type_icon} {content[1]} - {get_category_name_by_id(content[4])}\n"
            await update.message.reply_text(content_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
        return
    
    elif text == "🗑 حذف محتوى":
        content_items = db.get_all_content()
        if content_items:
            await update.message.reply_text(
                "اختر محتوى للحذف:",
                reply_markup=admin_content_list()
            )
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
        return
    
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
    
    elif text == "🔐 نظام الموافقة":
        current = db.get_setting('approval_required')
        new_status = '0' if current == '1' else '1'
        db.update_setting('approval_required', new_status)
        status = "❌ معطل" if new_status == '0' else "✅ مفعل"
        await update.message.reply_text(f"{status} نظام الموافقة")
        return
    
    elif context.user_data.get('content_stage') == 'type':
        if text in ["📝 نص", "📸 صورة", "🎥 فيديو"]:
            content_type_map = {"📝 نص": "text", "📸 صورة": "photo", "🎥 فيديو": "video"}
            context.user_data['content_type'] = content_type_map[text]
            context.user_data['content_stage'] = 'title'
            
            await update.message.reply_text("✏️ المرحلة 1 من 3\n\nأرسل عنوان المحتوى (مثال: قصة جميلة، فيديو رائع، إلخ):")
            return
    
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
            if categories:
                keyboard = []
                for cat in categories:
                    keyboard.append([KeyboardButton(cat[1])])
                keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
                
                await update.message.reply_text(
                    "📁 المرحلة 3 من 3\n\nاختر القسم الذي تريد إضافة المحتوى إليه:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
            else:
                await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
                context.user_data.clear()
        return
    
    elif context.user_data.get('content_stage') == 'category':
        category_name = text
        category_id = get_category_id_by_name(category_name)
        if category_id:
            title = context.user_data.get('content_title', 'بدون عنوان')
            content_type = context.user_data.get('content_type', 'text')
            description = context.user_data.get('content_description', '')
            file_id = context.user_data.get('content_file_id')
            
            content_id = db.add_content(title, description, content_type, category_id, file_id)
            
            content_type_name = "نص" if content_type == 'text' else "صورة" if content_type == 'photo' else "فيديو"
            
            await update.message.reply_text(
                f"✅ تم إضافة المحتوى بنجاح!\n\n"
                f"📝 النوع: {content_type_name}\n"
                f"🎯 العنوان: {title}\n"
                f"📁 القسم: {category_name}\n"
                f"🆔 الرقم: {content_id}",
                reply_markup=admin_content_menu()
            )
            context.user_data.clear()
        else:
            await update.message.reply_text("❌ قسم غير موجود. الرجاء اختيار قسم من القائمة.")
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
        category_id = db.add_category(text)
        await update.message.reply_text(f"✅ تم إضافة القسم: {text} (ID: {category_id})", reply_markup=admin_categories_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('awaiting_new_category_name'):
        category_id = context.user_data.get('editing_category_id')
        old_name = context.user_data.get('editing_category_name')
        if category_id:
            db.update_category(category_id, text)
            await update.message.reply_text(f"✅ تم تعديل القسم من '{old_name}' إلى '{text}'", reply_markup=admin_categories_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_subscription_message'):
        db.update_setting('subscription_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة الاشتراك", reply_markup=admin_subscription_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_subscription_channel'):
        db.update_setting('subscription_channel', text)
        await update.message.reply_text(f"✅ تم تحديث رابط القناة إلى: {text}", reply_markup=admin_subscription_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_subscription_success'):
        db.update_setting('subscription_success_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة النجاح", reply_markup=admin_subscription_menu())
        context.user_data.clear()
        return
    
    elif context.user_data.get('editing_backup_password'):
        db.update_setting('backup_password', text)
        await update.message.reply_text(f"✅ تم تحديث كلمة سر النسخ الاحتياطي إلى: {text}", reply_markup=admin_backup_menu())
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
    
    elif context.user_data.get('broadcasting'):
        users = db.get_all_users()
        success = 0
        for user_data in users:
            try:
                await context.bot.send_message(
                    chat_id=user_data[0], 
                    text=f"*إشعار عام من الإدارة:*\n\n{text}"
                )
                success += 1
            except:
                continue
        await update.message.reply_text(f"✅ تم الإرسال إلى {success} مستخدم", reply_markup=admin_main_menu())
        context.user_data.clear()
        return
    
    else:
        await update.message.reply_text("👑 لوحة تحكم المدير", reply_markup=admin_main_menu())

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"حدث خطأ: {context.error}")

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("❌ لم يتم تعيين TELEGRAM_BOT_TOKEN")
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت الكامل مع نظام الاشتراك الإجباري...")
    application.run_polling()

if __name__ == '__main__':
    main()

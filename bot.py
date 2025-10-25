import os
import logging
import sqlite3
import json
import atexit
import shutil
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FirebaseManager:
    def __init__(self):
        self.db = None
        self.initialized = False
        self.init_firebase()
    
    def init_firebase(self):
        """تهيئة Firebase"""
        try:
            # محاولة استيراد Firebase
            import firebase_admin
            from firebase_admin import credentials, firestore
            
            # طرق مختلفة لتحميل credentials
            if os.path.exists('firebase-key.json'):
                cred = credentials.Certificate('firebase-key.json')
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                self.initialized = True
                logger.info("✅ تم تهيئة Firebase بنجاح")
            else:
                logger.warning("❌ لم يتم العثور على ملف firebase-key.json")
                
        except ImportError:
            logger.warning("❌ مكتبة firebase-admin غير مثبتة. قم بتثبيتها: pip install firebase-admin")
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة Firebase: {e}")
    
    def add_user_firebase(self, user_data):
        if not self.initialized:
            return False
        
        try:
            user_ref = self.db.collection('users').document(str(user_data['user_id']))
            user_ref.set({
                'user_id': user_data['user_id'],
                'username': user_data['username'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'is_approved': user_data['is_approved'],
                'is_admin': user_data['is_admin'],
                'joined_date': datetime.now(),
                'last_active': datetime.now()
            })
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة مستخدم لـ Firebase: {e}")
            return False
    
    def get_user_firebase(self, user_id):
        if not self.initialized:
            return None
        
        try:
            user_ref = self.db.collection('users').document(str(user_id))
            user_doc = user_ref.get()
            return user_doc.to_dict() if user_doc.exists else None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب مستخدم من Firebase: {e}")
            return None
    
    def update_user_activity_firebase(self, user_id):
        if not self.initialized:
            return False
        
        try:
            user_ref = self.db.collection('users').document(str(user_id))
            user_ref.update({
                'last_active': datetime.now()
            })
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث نشاط المستخدم في Firebase: {e}")
            return False
    
    def add_category_firebase(self, category_data):
        if not self.initialized:
            return None
        
        try:
            category_ref = self.db.collection('categories').document()
            category_data['created_date'] = datetime.now()
            category_ref.set(category_data)
            return category_ref.id
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة قسم لـ Firebase: {e}")
            return None
    
    def get_categories_firebase(self):
        if not self.initialized:
            return []
        
        try:
            categories_ref = self.db.collection('categories')
            docs = categories_ref.stream()
            
            categories = []
            for doc in docs:
                category_data = doc.to_dict()
                category_data['id'] = doc.id
                categories.append(category_data)
            
            return categories
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الأقسام من Firebase: {e}")
            return []
    
    def add_content_firebase(self, content_data):
        if not self.initialized:
            return None
        
        try:
            content_ref = self.db.collection('content').document()
            content_data['created_date'] = datetime.now()
            content_ref.set(content_data)
            return content_ref.id
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة محتوى لـ Firebase: {e}")
            return None
    
    def get_content_by_category_firebase(self, category_id):
        if not self.initialized:
            return []
        
        try:
            content_ref = self.db.collection('content')
            docs = content_ref.where('category_id', '==', category_id).stream()
            
            content_list = []
            for doc in docs:
                content_data = doc.to_dict()
                content_data['id'] = doc.id
                content_list.append(content_data)
            
            return content_list
        except Exception as e:
            logger.error(f"❌ خطأ في جلب المحتوى من Firebase: {e}")
            return []
    
    def get_all_content_firebase(self):
        if not self.initialized:
            return []
        
        try:
            content_ref = self.db.collection('content')
            docs = content_ref.stream()
            
            content_list = []
            for doc in docs:
                content_data = doc.to_dict()
                content_data['id'] = doc.id
                content_list.append(content_data)
            
            return content_list
        except Exception as e:
            logger.error(f"❌ خطأ في جلب كل المحتوى من Firebase: {e}")
            return []

class LocalDatabase:
    def __init__(self):
        self.db_path = 'content_bot.db'
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()
        self.create_admin()
        self.create_default_settings()
        atexit.register(self.close_connection)
        logger.info("✅ تم تهيئة قاعدة البيانات المحلية بنجاح")

    def close_connection(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def create_tables(self):
        tables = [
            '''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_approved INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                content_type TEXT,
                category_id INTEGER,
                file_id TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS join_requests (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )'''
        ]
        
        for table in tables:
            self.conn.execute(table)
        self.conn.commit()

    def create_admin(self):
        admin_id = int(os.getenv('ADMIN_ID', 123456789))
        try:
            self.conn.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, is_approved, is_admin)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (admin_id, 'admin', 'Admin', 'Bot', 1, 1))
            self.conn.commit()
        except Exception as e:
            logger.error(f"خطأ في إنشاء المدير: {e}")

    def create_default_settings(self):
        default_settings = [
            ('welcome_message', '🎭 مرحباً بك في بوت المحتوى المميز!'),
            ('approval_required', '1'),
            ('about_text', '🤖 بوت المحتوى التفاعلي\n\nبوت متخصص لمشاركة المحتوى المميز.'),
            ('contact_text', '📞 للتواصل: @username'),
            ('start_button_text', '🚀 ابدأ الرحلة'),
            ('auto_approve', '0'),
            ('admin_contact', '@username')
        ]
        try:
            for key, value in default_settings:
                self.conn.execute('INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)', (key, value))
            self.conn.commit()
        except Exception as e:
            logger.error(f"خطأ في إنشاء الإعدادات: {e}")

    def get_setting(self, key):
        cursor = self.conn.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else None

    def update_setting(self, key, value):
        self.conn.execute('UPDATE bot_settings SET value = ? WHERE key = ?', (value, key))
        self.conn.commit()

    def add_user(self, user_id, username, first_name, last_name, is_approved=False, is_admin=False):
        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, is_approved, is_admin, last_active)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name, is_approved, is_admin))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في إضافة المستخدم: {e}")
            return False

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

    def add_category(self, name):
        try:
            self.conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (name,))
            self.conn.commit()
            return self.conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        except Exception as e:
            logger.error(f"خطأ في إضافة القسم: {e}")
            return None

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories ORDER BY name')
        return cursor.fetchall()

    def update_category(self, category_id, name):
        self.conn.execute('UPDATE categories SET name = ? WHERE id = ?', (name, category_id))
        self.conn.commit()

    def delete_category(self, category_id):
        try:
            cursor = self.conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
            category = cursor.fetchone()
            if not category:
                return False
            
            self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            self.conn.execute('DELETE FROM content WHERE category_id = ?', (category_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في حذف القسم: {e}")
            return False

    def add_content(self, title, content, content_type, category_id, file_id=None):
        try:
            self.conn.execute('''
                INSERT INTO content (title, content, content_type, category_id, file_id) 
                VALUES (?, ?, ?, ?, ?)
            ''', (title, content, content_type, category_id, file_id))
            self.conn.commit()
            return self.conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        except Exception as e:
            logger.error(f"خطأ في إضافة المحتوى: {e}")
            return None

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
        try:
            cursor = self.conn.execute('SELECT * FROM content WHERE id = ?', (content_id,))
            content = cursor.fetchone()
            if not content:
                return False
            
            self.conn.execute('DELETE FROM content WHERE id = ?', (content_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في حذف المحتوى: {e}")
            return False

    def get_content(self, content_id):
        cursor = self.conn.execute('SELECT * FROM content WHERE id = ?', (content_id,))
        return cursor.fetchone()

    def get_category_by_id(self, category_id):
        cursor = self.conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        return cursor.fetchone()

class HybridDatabase:
    def __init__(self):
        self.firebase = FirebaseManager()
        self.local_db = LocalDatabase()
        self.sync_enabled = self.firebase.initialized
        logger.info(f"🔥 حالة Firebase: {'مفعل' if self.sync_enabled else 'معطل'}")
    
    def add_user(self, user_id, username, first_name, last_name, is_approved=False, is_admin=False):
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'is_approved': is_approved,
            'is_admin': is_admin
        }
        
        # حفظ محلي
        local_success = self.local_db.add_user(user_id, username, first_name, last_name, is_approved, is_admin)
        
        # مزامنة مع Firebase
        firebase_success = True
        if self.sync_enabled:
            firebase_success = self.firebase.add_user_firebase(user_data)
        
        return local_success and firebase_success
    
    def get_user(self, user_id):
        # محاولة جلب من Firebase أولاً
        if self.sync_enabled:
            user_data = self.firebase.get_user_firebase(user_id)
            if user_data:
                return user_data
        
        # إذا فشل، جلب من SQLite
        return self.local_db.get_user(user_id)
    
    def update_user_activity(self, user_id):
        # تحديث محلي
        self.local_db.update_user_activity(user_id)
        
        # مزامنة مع Firebase
        if self.sync_enabled:
            self.firebase.update_user_activity_firebase(user_id)
    
    def add_category(self, name):
        category_data = {'name': name}
        
        # حفظ محلي
        local_id = self.local_db.add_category(name)
        
        # مزامنة مع Firebase
        firebase_id = None
        if self.sync_enabled:
            firebase_id = self.firebase.add_category_firebase(category_data)
        
        return {'local_id': local_id, 'firebase_id': firebase_id}
    
    def get_categories(self):
        # محاولة جلب من Firebase أولاً
        if self.sync_enabled:
            categories = self.firebase.get_categories_firebase()
            if categories:
                return categories
        
        # إذا فشل، جلب من SQLite
        return self.local_db.get_categories()
    
    def add_content(self, title, content, content_type, category_id, file_id=None):
        content_data = {
            'title': title,
            'content': content,
            'content_type': content_type,
            'category_id': category_id,
            'file_id': file_id
        }
        
        # حفظ محلي
        local_id = self.local_db.add_content(title, content, content_type, category_id, file_id)
        
        # مزامنة مع Firebase
        firebase_id = None
        if self.sync_enabled:
            firebase_id = self.firebase.add_content_firebase(content_data)
        
        return {'local_id': local_id, 'firebase_id': firebase_id}
    
    def get_content_by_category(self, category_id):
        # محاولة جلب من Firebase أولاً
        if self.sync_enabled:
            content = self.firebase.get_content_by_category_firebase(category_id)
            if content:
                return content
        
        # إذا فشل، جلب من SQLite
        return self.local_db.get_content_by_category(category_id)
    
    def get_all_content(self):
        # محاولة جلب من Firebase أولاً
        if self.sync_enabled:
            content = self.firebase.get_all_content_firebase()
            if content:
                return content
        
        # إذا فشل، جلب من SQLite
        return self.local_db.get_all_content()
    
    # دوال SQLite الأصلية للتوافق
    def get_setting(self, key):
        return self.local_db.get_setting(key)
    
    def update_setting(self, key, value):
        return self.local_db.update_setting(key, value)
    
    def approve_user(self, user_id):
        return self.local_db.approve_user(user_id)
    
    def reject_user(self, user_id):
        return self.local_db.reject_user(user_id)
    
    def get_all_users(self):
        return self.local_db.get_all_users()
    
    def get_active_users(self, days=30):
        return self.local_db.get_active_users(days)
    
    def get_pending_requests(self):
        return self.local_db.get_pending_requests()
    
    def delete_user(self, user_id):
        return self.local_db.delete_user(user_id)
    
    def update_category(self, category_id, name):
        return self.local_db.update_category(category_id, name)
    
    def delete_category(self, category_id):
        return self.local_db.delete_category(category_id)
    
    def delete_content(self, content_id):
        return self.local_db.delete_content(content_id)
    
    def get_content(self, content_id):
        return self.local_db.get_content(content_id)
    
    def get_category_by_id(self, category_id):
        return self.local_db.get_category_by_id(category_id)

# تهيئة قاعدة البيانات الهجينة
db = HybridDatabase()

def get_admin_id():
    return int(os.getenv('ADMIN_ID', 123456789))

def is_admin(user_id):
    return user_id == get_admin_id()

def get_category_id_by_name(name):
    categories = db.get_categories()
    for cat in categories:
        if isinstance(cat, tuple):  # SQLite tuple
            if cat[1] == name:
                return cat[0]
        else:  # Firebase dict
            if cat['name'] == name:
                return cat['id']
    return None

def get_category_name_by_id(category_id):
    category = db.get_category_by_id(category_id)
    if category:
        if isinstance(category, tuple):  # SQLite
            return category[1]
        else:  # Firebase
            return category['name']
    return "غير معروف"

# لوحات المفاتيح للمستخدم
def user_main_menu():
    keyboard = [
        [KeyboardButton("📁 الاقسام"), KeyboardButton("👤 الملف الشخصي")],
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_categories_menu():
    categories = db.get_categories()
    keyboard = []
    row = []
    for i, cat in enumerate(categories):
        cat_name = cat[1] if isinstance(cat, tuple) else cat['name']
        row.append(KeyboardButton(cat_name))
        if len(row) == 2 or i == len(categories) - 1:
            keyboard.append(row)
            row = []
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_content_menu(category_name, category_id):
    content_items = db.get_content_by_category(category_id)
    keyboard = []
    
    for content in content_items:
        if isinstance(content, tuple):  # SQLite
            content_title = content[1]
            content_id = content[0]
        else:  # Firebase
            content_title = content['title']
            content_id = content['id']
        
        short_title = content_title[:20] + "..." if len(content_title) > 20 else content_title
        keyboard.append([InlineKeyboardButton(f"📄 {short_title}", callback_data=f"content_{content_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(keyboard)

# لوحات المفاتيح للمدير
def admin_main_menu():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📦 إدارة المحتوى"), KeyboardButton("⚙️ إعدادات البوت")],
        [KeyboardButton("📊 الإحصائيات"), KeyboardButton("📢 البث الجماعي")],
        [KeyboardButton("💾 معلومات التخزين"), KeyboardButton("🔄 مزامنة البيانات")],
        [KeyboardButton("🔙 وضع المستخدم")]
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
        [KeyboardButton("🔐 نظام الموافقة"), KeyboardButton("🔙 لوحة التحكم")]
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
    
    if auto_approve and user_data and not (user_data[4] if isinstance(user_data, tuple) else user_data['is_approved']):
        db.approve_user(user_id)
        user_data = db.get_user(user_id)
    
    is_approved = False
    if user_data:
        if isinstance(user_data, tuple):  # SQLite
            is_approved = user_data[4] == 1
        else:  # Firebase
            is_approved = user_data.get('is_approved', False)
    
    if is_approved:
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
        db.local_db.conn.execute('INSERT OR REPLACE INTO join_requests (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
                       (user_id, user.username, user.first_name, user.last_name))
        db.local_db.conn.commit()
        
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

# معالجة Callback
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
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 تمت الموافقة على طلبك!",
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
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")
    
    elif data.startswith('content_'):
        content_id = data.split('_')[1]
        content = db.get_content(int(content_id)) if content_id.isdigit() else None
        
        if content:
            if isinstance(content, tuple):  # SQLite
                content_title = content[1]
                content_text = content[2]
                content_type = content[3]
                file_id = content[5]
            else:  # Firebase
                content_title = content['title']
                content_text = content['content']
                content_type = content['content_type']
                file_id = content.get('file_id')
            
            if content_type == 'text':
                await query.message.reply_text(
                    f"📖 {content_title}\n\n{content_text}\n\n---\nنهاية المحتوى 📚"
                )
            elif content_type == 'photo' and file_id:
                await query.message.reply_photo(
                    photo=file_id,
                    caption=f"📸 {content_title}\n\n{content_text}"
                )
            elif content_type == 'video' and file_id:
                await query.message.reply_video(
                    video=file_id,
                    caption=f"🎥 {content_title}\n\n{content_text}"
                )
            else:
                await query.message.reply_text(
                    f"📖 {content_title}\n\n{content_text}\n\n---\nنهاية المحتوى 📚"
                )
        else:
            await query.message.reply_text("❌ المحتوى غير موجود")
    
    elif data == 'back_to_categories':
        categories = db.get_categories()
        if categories:
            await query.message.edit_text("📁 الاقسام المتاحة:\n\nاختر قسم:", reply_markup=user_categories_menu())
        else:
            await query.message.edit_text("⚠️ لا توجد أقسام متاحة حالياً.")

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
            if categories:
                keyboard = []
                for cat in categories:
                    cat_name = cat[1] if isinstance(cat, tuple) else cat['name']
                    keyboard.append([KeyboardButton(cat_name)])
                keyboard.append([KeyboardButton("🔙 إدارة المحتوى")])
                
                await update.message.reply_text(
                    "📁 المرحلة 3 من 3\n\nاختر القسم الذي تريد إضافة المحتوى إليه:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
            else:
                await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
                context.user_data.clear()

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
    
    if not user_data:
        if text == "🔄 تحديث الحالة":
            user_data = db.get_user(user_id)
            if user_data:
                is_approved = user_data[4] if isinstance(user_data, tuple) else user_data.get('is_approved', False)
                if is_approved:
                    await update.message.reply_text("🎉 تمت الموافقة على طلبك!", reply_markup=user_main_menu())
                else:
                    await update.message.reply_text("⏳ لا يزال طلبك قيد المراجعة...")
            else:
                await update.message.reply_text("⏳ لا يزال طلبك قيد المراجعة...")
        return
    
    # معالجة الأوامر الرئيسية
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    elif text == "📁 الاقسام":
        categories = db.get_categories()
        if categories:
            await update.message.reply_text("📁 الاقسام المتاحة:\n\nاختر قسم:", reply_markup=user_categories_menu())
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif text == "👤 الملف الشخصي":
        user_stats = f"👤 الملف الشخصي\n\n"
        user_stats += f"🆔 الرقم: {user_id}\n"
        user_stats += f"👤 الاسم: {user.first_name}\n"
        
        if isinstance(user_data, tuple):  # SQLite
            user_stats += f"📅 تاريخ الانضمام: {user_data[6].split()[0] if user_data[6] else 'غير معروف'}\n"
        else:  # Firebase
            join_date = user_data.get('joined_date')
            if isinstance(join_date, datetime):
                user_stats += f"📅 تاريخ الانضمام: {join_date.strftime('%Y-%m-%d')}\n"
            else:
                user_stats += f"📅 تاريخ الانضمام: غير معروف\n"
        
        user_stats += f"📱 آخر نشاط: الآن\n"
        
        await update.message.reply_text(user_stats)
    
    elif text == "ℹ️ حول البوت":
        about_text = db.get_setting('about_text')
        await update.message.reply_text(about_text)
    
    elif text == "📞 اتصل بنا":
        contact_text = db.get_setting('contact_text')
        await update.message.reply_text(contact_text)
    
    else:
        # التحقق إذا كان النص هو اسم قسم
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

# دوال مساعدة للمدير
async def show_statistics(update: Update, context: CallbackContext):
    total_users = len(db.get_all_users())
    active_users = len(db.get_active_users(30))
    total_content = len(db.get_all_content())
    total_categories = len(db.get_categories())
    pending_requests = len(db.get_pending_requests())
    
    stats_text = f"📊 إحصائيات البوت:\n\n"
    stats_text += f"👥 إجمالي المستخدمين: {total_users}\n"
    stats_text += f"🎯 النشطون: {active_users}\n"
    stats_text += f"📦 المحتوى: {total_content}\n"
    stats_text += f"📁 الأقسام: {total_categories}\n"
    stats_text += f"⏳ طلبات الانتظار: {pending_requests}"
    
    await update.message.reply_text(stats_text)

async def show_storage_info(update: Update, context: CallbackContext):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ ليس لديك صلاحية.")
        return
    
    info_text = "💾 معلومات التخزين:\n\n"
    info_text += f"🔥 حالة Firebase: {'✅ مفعل' if db.firebase.initialized else '❌ معطل'}\n"
    info_text += f"🔄 المزامنة: {'✅ مفعلة' if db.sync_enabled else '❌ معطلة'}\n"
    
    # إحصائيات SQLite
    local_users = len(db.get_all_users())
    local_categories = len(db.get_categories())
    local_content = len(db.get_all_content())
    
    info_text += f"\n💿 SQLite:\n"
    info_text += f"👥 المستخدمون: {local_users}\n"
    info_text += f"📁 الأقسام: {local_categories}\n"
    info_text += f"📦 المحتوى: {local_content}\n"
    
    if db.firebase.initialized:
        # إحصائيات Firebase
        firebase_categories = len(db.firebase.get_categories_firebase())
        firebase_content = len(db.firebase.get_all_content_firebase())
        
        info_text += f"\n🔥 Firebase:\n"
        info_text += f"📁 الأقسام: {firebase_categories}\n"
        info_text += f"📦 المحتوى: {firebase_content}\n"
    
    await update.message.reply_text(info_text)

async def sync_data(update: Update, context: CallbackContext):
    """مزامنة البيانات من SQLite إلى Firebase"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ ليس لديك صلاحية.")
        return
    
    if not db.firebase.initialized:
        await update.message.reply_text("❌ Firebase غير مفعل")
        return
    
    await update.message.reply_text("🔄 بدء مزامنة البيانات...")
    
    # مزامنة الأقسام
    categories = db.local_db.get_categories()
    for cat in categories:
        db.firebase.add_category_firebase({'name': cat[1]})
    
    # مزامنة المحتوى
    content_items = db.local_db.get_all_content()
    for content in content_items:
        content_data = {
            'title': content[1],
            'content': content[2],
            'content_type': content[3],
            'category_id': content[4],
            'file_id': content[5]
        }
        db.firebase.add_content_firebase(content_data)
    
    await update.message.reply_text("✅ تمت مزامنة البيانات بنجاح")

# معالجة رسائل المدير
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if not is_admin(user_id):
        return

    db.update_user_activity(user_id)

    # تنظيف الحالات عند العودة للوحة التحكم
    if text in ["🔙 لوحة التحكم", "🔙 إدارة الأقسام", "🔙 إدارة المحتوى", "🔙 إدارة المستخدمين"]:
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
    
    elif text == "📊 الإحصائيات":
        await show_statistics(update, context)
        return
    
    elif text == "📢 البث الجماعي":
        await update.message.reply_text("أرسل الرسالة للبث لجميع المستخدمين:")
        context.user_data['broadcasting'] = True
        return
    
    elif text == "💾 معلومات التخزين":
        await show_storage_info(update, context)
        return

    elif text == "🔄 مزامنة البيانات":
        await sync_data(update, context)
        return
    
    # إدارة المستخدمين
    elif text == "📋 عرض المستخدمين":
        users = db.get_all_users()
        if users:
            users_text = "👥 المستخدمون:\n\n"
            for user_data in users:
                if isinstance(user_data, tuple):  # SQLite
                    users_text += f"🆔 {user_data[0]} - 👤 {user_data[2]}\n"
                else:  # Firebase
                    users_text += f"🆔 {user_data['user_id']} - 👤 {user_data['first_name']}\n"
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
    
    # إدارة الأقسام
    elif text == "➕ إضافة قسم":
        await update.message.reply_text("أرسل اسم القسم الجديد:")
        context.user_data['adding_category'] = True
        return
    
    elif text == "✏️ تعديل قسم":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                cat_name = cat[1] if isinstance(cat, tuple) else cat['name']
                keyboard.append([KeyboardButton(f"تعديل {cat_name}")])
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
                if isinstance(cat, tuple):  # SQLite
                    cats_text += f"📁 {cat[1]} (ID: {cat[0]})\n"
                else:  # Firebase
                    cats_text += f"📁 {cat['name']} (ID: {cat['id']})\n"
            await update.message.reply_text(cats_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
        return
    
    elif text == "🗑 حذف قسم":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                cat_name = cat[1] if isinstance(cat, tuple) else cat['name']
                cat_id = cat[0] if isinstance(cat, tuple) else cat['id']
                keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"delete_cat_{cat_id}")])
            keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="cancel_delete")])
            await update.message.reply_text("اختر قسم للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
        return
    
    # إدارة المحتوى
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
                if isinstance(content, tuple):  # SQLite
                    content_type_icon = "📝" if content[3] == 'text' else "📸" if content[3] == 'photo' else "🎥"
                    content_text += f"{content_type_icon} {content[1]} - {get_category_name_by_id(content[4])}\n"
                else:  # Firebase
                    content_type_icon = "📝" if content['content_type'] == 'text' else "📸" if content['content_type'] == 'photo' else "🎥"
                    content_text += f"{content_type_icon} {content['title']} - {get_category_name_by_id(content['category_id'])}\n"
            await update.message.reply_text(content_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
        return
    
    elif text == "🗑 حذف محتوى":
        content_items = db.get_all_content()
        if content_items:
            keyboard = []
            for content in content_items[:15]:
                if isinstance(content, tuple):  # SQLite
                    content_title = content[1]
                    content_id = content[0]
                else:  # Firebase
                    content_title = content['title']
                    content_id = content['id']
                
                short_title = content_title[:15] + "..." if len(content_title) > 15 else content_title
                keyboard.append([InlineKeyboardButton(f"🗑 {short_title}", callback_data=f"delete_content_{content_id}")])
            keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="cancel_delete")])
            await update.message.reply_text("اختر محتوى للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("⚠️ لا يوجد محتوى.")
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
    
    elif text == "🔐 نظام الموافقة":
        current = db.get_setting('approval_required')
        new_status = '0' if current == '1' else '1'
        db.update_setting('approval_required', new_status)
        status = "معطل" if new_status == '0' else "مفعل"
        await update.message.reply_text(f"✅ تم {status} نظام الموافقة")
        return
    
    # معالجة مراحل إضافة المحتوى
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
                    cat_name = cat[1] if isinstance(cat, tuple) else cat['name']
                    keyboard.append([KeyboardButton(cat_name)])
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
            
            result = db.add_content(title, description, content_type, category_id, file_id)
            
            content_type_name = "نص" if content_type == 'text' else "صورة" if content_type == 'photo' else "فيديو"
            
            await update.message.reply_text(
                f"✅ تم إضافة المحتوى بنجاح!\n\n"
                f"📝 النوع: {content_type_name}\n"
                f"🎯 العنوان: {title}\n"
                f"📁 القسم: {category_name}\n"
                f"💿 المحلي: {result.get('local_id', 'N/A')}\n"
                f"🔥 Firebase: {result.get('firebase_id', 'N/A')}",
                reply_markup=admin_content_menu()
            )
            context.user_data.clear()
        else:
            await update.message.reply_text("❌ قسم غير موجود. الرجاء اختيار قسم من القائمة.")
        return
    
    # معالجة إدخال البيانات الأخرى
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
        result = db.add_category(text)
        await update.message.reply_text(f"✅ تم إضافة القسم: {text} (المحلي: {result.get('local_id', 'N/A')}, Firebase: {result.get('firebase_id', 'N/A')})", reply_markup=admin_categories_menu())
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
                user_id = user_data[0] if isinstance(user_data, tuple) else user_data['user_id']
                await context.bot.send_message(
                    chat_id=user_id, 
                    text=f"📢 إشعار من الإدارة:\n\n{text}"
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
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت مع دعم Firebase...")
    application.run_polling()

if __name__ == '__main__':
    main()

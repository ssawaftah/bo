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
        self.conn = sqlite3.connect('stories_bot.db', check_same_thread=False)
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

        # جدول القصص
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                category_id INTEGER,
                is_premium INTEGER DEFAULT 0,
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

        # جدول الإشعارات
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                target TEXT,
                sent_count INTEGER DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول الإحصائيات
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                date TEXT PRIMARY KEY,
                new_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                stories_viewed INTEGER DEFAULT 0
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
            ('welcome_message', '🎭 **مرحباً بك في عالم القصص المثير!**'),
            ('approval_required', '1'),
            ('about_text', '🤖 **بوت القصص التفاعلي**\n\nبوت متخصص لمشاركة القصص المميزة.'),
            ('contact_text', '📞 **للتواصل:** @username'),
            ('start_button_text', '🚀 ابدأ الرحلة'),
            ('auto_approve', '0'),
            ('premium_enabled', '1'),
            ('premium_section_name', '⭐ القصص المميزة'),
            ('premium_access_message', '🔒 هذه القصة متاحة للأعضاء المميزين فقط.\n\n💎 لترقية حسابك، تواصل مع الإدارة.'),
            ('broadcast_notification_text', '📢 إشعار من الإدارة'),
            ('admin_contact', '@username'),
            ('max_stories_per_user', '10'),
            ('inactive_days_threshold', '30')
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

    def add_category(self, name, is_premium=False):
        self.conn.execute('INSERT OR IGNORE INTO categories (name, is_premium) VALUES (?, ?)', (name, 1 if is_premium else 0))
        self.conn.commit()

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories ORDER BY name')
        return cursor.fetchall()

    def get_premium_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories WHERE is_premium = 1 ORDER BY name')
        return cursor.fetchall()

    def update_category(self, category_id, name, is_premium):
        self.conn.execute('UPDATE categories SET name = ?, is_premium = ? WHERE id = ?', (name, is_premium, category_id))
        self.conn.commit()

    def delete_category(self, category_id):
        self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.execute('DELETE FROM stories WHERE category_id = ?', (category_id,))
        self.conn.commit()

    def add_story(self, title, content, category_id, is_premium=False):
        self.conn.execute('INSERT INTO stories (title, content, category_id, is_premium) VALUES (?, ?, ?, ?)', 
                         (title, content, category_id, 1 if is_premium else 0))
        self.conn.commit()

    def get_stories_by_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM stories WHERE category_id = ? ORDER BY created_date DESC', (category_id,))
        return cursor.fetchall()

    def get_premium_stories(self):
        cursor = self.conn.execute('SELECT * FROM stories WHERE is_premium = 1 ORDER BY created_date DESC')
        return cursor.fetchall()

    def get_all_stories(self):
        cursor = self.conn.execute('''
            SELECT s.*, c.name as category_name 
            FROM stories s JOIN categories c ON s.category_id = c.id 
            ORDER BY s.created_date DESC
        ''')
        return cursor.fetchall()

    def delete_story(self, story_id):
        self.conn.execute('DELETE FROM stories WHERE id = ?', (story_id,))
        self.conn.commit()

    def add_broadcast(self, title, content, target):
        self.conn.execute('INSERT INTO broadcasts (title, content, target) VALUES (?, ?, ?)', (title, content, target))
        self.conn.commit()

    def get_broadcasts(self):
        cursor = self.conn.execute('SELECT * FROM broadcasts ORDER BY created_date DESC LIMIT 10')
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

# لوحات المفاتيح للمستخدم
def user_main_menu():
    keyboard = [
        [KeyboardButton("📚 اكتشف القصص"), KeyboardButton("⭐ القصص المميزة")],
        [KeyboardButton("👤 الملف الشخصي"), KeyboardButton("⚙️ الإعدادات")],
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_categories_menu():
    categories = db.get_categories()
    keyboard = []
    for cat in categories:
        if not cat[2] or (cat[2] and db.get_user(user_id) and db.get_user(user_id)[6] == 1):
            keyboard.append([KeyboardButton(cat[1])])
    keyboard.append([KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_settings_menu():
    keyboard = [
        [KeyboardButton("🔔 الإشعارات"), KeyboardButton("🌙 الوضع الليلي")],
        [KeyboardButton("🏠 الرئيسية")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحات المفاتيح للمدير - محسنة
def admin_main_menu():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📖 إدارة القصص"), KeyboardButton("⚙️ إعدادات البوت")],
        [KeyboardButton("📊 الإحصائيات المتقدمة"), KeyboardButton("📢 البث الجماعي")],
        [KeyboardButton("🎯 إدارة المميزين"), KeyboardButton("🔧 الإعدادات المتقدمة")],
        [KeyboardButton("🔙 وضع المستخدم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_users_menu():
    keyboard = [
        [KeyboardButton("📋 عرض المستخدمين"), KeyboardButton("⏳ طلبات الانضمام")],
        [KeyboardButton("💎 ترقية مستخدم"), KeyboardButton("🗑 حذف مستخدم")],
        [KeyboardButton("👀 المستخدمين النشطين"), KeyboardButton("📈 إحصائيات المستخدمين")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_categories_menu():
    keyboard = [
        [KeyboardButton("➕ إضافة قسم"), KeyboardButton("✏️ تعديل قسم")],
        [KeyboardButton("🗑 حذف قسم"), KeyboardButton("📋 عرض الأقسام")],
        [KeyboardButton("🔧 تعيين قسم كمميز"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_stories_menu():
    keyboard = [
        [KeyboardButton("➕ إضافة قصة"), KeyboardButton("✏️ تعديل قصة")],
        [KeyboardButton("🗑 حذف قصة"), KeyboardButton("📋 عرض القصص")],
        [KeyboardButton("🔧 تعيين قصة كمميزة"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_settings_menu():
    keyboard = [
        [KeyboardButton("✏️ رسالة الترحيب"), KeyboardButton("📝 حول البوت")],
        [KeyboardButton("📞 اتصل بنا"), KeyboardButton("🔄 زر البدء")],
        [KeyboardButton("🔐 نظام الموافقة"), KeyboardButton("🎯 إعدادات المميزين")],
        [KeyboardButton("📢 إعدادات البث"), KeyboardButton("🔧 جميع الإعدادات")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_premium_menu():
    keyboard = [
        [KeyboardButton("👑 عرض المميزين"), KeyboardButton("💎 ترقية مستخدم")],
        [KeyboardButton("🔻 إزالة التميز"), KeyboardButton("📊 إحصائيات المميزين")],
        [KeyboardButton("✏️ تعديل رسالة المميزين"), KeyboardButton("🔧 تفعيل/تعطيل النظام")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_broadcast_menu():
    keyboard = [
        [KeyboardButton("📢 للجميع"), KeyboardButton("👥 للنشطين")],
        [KeyboardButton("💎 للمميزين فقط"), KeyboardButton("📋 سجل البث")],
        [KeyboardButton("✏️ تعديل نص الإشعار"), KeyboardButton("🔙 لوحة التحكم")]
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

# معالجة Callback للمدير - محسنة
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

# معالجة رسائل المستخدمين - محسنة
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
    
    # معالجة أوامر المستخدم
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 الرئيسية", reply_markup=user_main_menu())
    
    elif text == "📚 اكتشف القصص":
        categories = db.get_categories()
        if categories:
            await update.message.reply_text("📚 اختر تصنيف:", reply_markup=user_categories_menu())
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة.")
    
    elif text == "👤 الملف الشخصي":
        user_stats = f"👤 **الملف الشخصي**\n\n"
        user_stats += f"🆔 الرقم: {user_id}\n"
        user_stats += f"👤 الاسم: {user.first_name}\n"
        user_stats += f"📅 تاريخ الانضمام: {user_data[7].split()[0] if user_data[7] else 'غير معروف'}\n"
        user_stats += f"💎 العضوية: {'مميز 👑' if user_data[6] == 1 else 'عادي ⭐'}\n"
        user_stats += f"📊 الحالة: {'موافق ✅' if user_data[4] == 1 else 'في الانتظار ⏳'}\n"
        
        if user_data[6] == 0:
            user_stats += f"\n💡 لترقية حسابك إلى مميز، تواصل مع: {db.get_setting('admin_contact')}"
        
        await update.message.reply_text(user_stats)
    
    elif text == "⚙️ الإعدادات":
        await update.message.reply_text("⚙️ الإعدادات", reply_markup=user_settings_menu())
    
    elif text == "ℹ️ حول البوت":
        about_text = db.get_setting('about_text')
        await update.message.reply_text(about_text)
    
    elif text == "📞 اتصل بنا":
        contact_text = db.get_setting('contact_text')
        await update.message.reply_text(contact_text)
    
    elif text == "⭐ القصص المميزة":
        if user_data[6] == 1:
            premium_stories = db.get_premium_stories()
            if premium_stories:
                story = premium_stories[0]
                story_text = f"👑 **{story[1]}**\n\n{story[2]}\n\n---\nنهاية القصة 📚"
                await update.message.reply_text(story_text, parse_mode='Markdown')
            else:
                await update.message.reply_text("⚠️ لا توجد قصص مميزة حالياً.")
        else:
            premium_message = db.get_setting('premium_access_message')
            await update.message.reply_text(premium_message)
    
    else:
        # التحقق إذا كان النص هو اسم قسم
        category_id = get_category_id_by_name(text)
        if category_id:
            category_data = next((cat for cat in db.get_categories() if cat[0] == category_id), None)
            
            # التحقق إذا كان القسم مميزاً
            if category_data and category_data[2] == 1 and user_data[6] == 0:
                premium_message = db.get_setting('premium_access_message')
                await update.message.reply_text(premium_message)
                return
            
            stories = db.get_stories_by_category(category_id)
            if stories:
                # إرسال أول قصة كمثال
                story = stories[0]
                
                # التحقق إذا كانت القصة مميزة
                if story[4] == 1 and user_data[6] == 0:
                    premium_message = db.get_setting('premium_access_message')
                    await update.message.reply_text(premium_message)
                    return
                
                story_text = f"📖 **{story[1]}**\n\n{story[2]}\n\n---\nنهاية القصة 📚"
                await update.message.reply_text(story_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"⚠️ لا توجد قصص في {text}.")
        else:
            await update.message.reply_text("❌ لم أفهم طلبك.", reply_markup=user_main_menu())

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
    
    elif text == "📖 إدارة القصص":
        await update.message.reply_text("📖 إدارة القصص", reply_markup=admin_stories_menu())
    
    elif text == "⚙️ إعدادات البوت":
        await update.message.reply_text("⚙️ إعدادات البوت", reply_markup=admin_settings_menu())
    
    elif text == "🎯 إدارة المميزين":
        await update.message.reply_text("🎯 إدارة المميزين", reply_markup=admin_premium_menu())
    
    elif text == "🔧 الإعدادات المتقدمة":
        await show_advanced_settings(update, context)
    
    elif text == "📊 الإحصائيات المتقدمة":
        await show_advanced_statistics(update, context)
    
    elif text == "📢 البث الجماعي":
        await update.message.reply_text("📢 البث الجماعي", reply_markup=admin_broadcast_menu())
    
    # إدارة المستخدمين المتقدمة
    elif text == "📋 عرض المستخدمين":
        users = db.get_all_users()
        if users:
            users_text = "👥 **المستخدمون:**\n\n"
            for user_data in users:
                status = "👑" if user_data[6] == 1 else "⭐"
                users_text += f"{status} {user_data[0]} - {user_data[2]} - {user_data[7].split()[0] if user_data[7] else 'غير معروف'}\n"
            await update.message.reply_text(users_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد مستخدمين.")
    
    elif text == "⏳ طلبات الانضمام":
        requests = db.get_pending_requests()
        if requests:
            req_text = "📩 **طلبات الانضمام:**\n\n"
            for req in requests:
                req_text += f"🆔 {req[0]} - 👤 {req[2]} - 📱 @{req[1] or 'لا يوجد'}\n"
            await update.message.reply_text(req_text)
        else:
            await update.message.reply_text("✅ لا توجد طلبات انتظار.")
    
    elif text == "👀 المستخدمين النشطين":
        active_users = db.get_active_users(30)
        if active_users:
            active_text = "👥 **المستخدمون النشطون (آخر 30 يوم):**\n\n"
            for user_data in active_users:
                active_text += f"🆔 {user_data[0]} - 👤 {user_data[2]} - 📅 {user_data[8].split()[0] if user_data[8] else 'غير معروف'}\n"
            await update.message.reply_text(active_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد مستخدمين نشطين.")
    
    elif text == "📈 إحصائيات المستخدمين":
        total_users = len(db.get_all_users())
        active_users = len(db.get_active_users(30))
        premium_users = len([u for u in db.get_all_users() if u[6] == 1])
        pending_requests = len(db.get_pending_requests())
        
        stats_text = f"📊 **إحصائيات المستخدمين:**\n\n"
        stats_text += f"👥 إجمالي المستخدمين: {total_users}\n"
        stats_text += f"🎯 المستخدمين النشطين: {active_users}\n"
        stats_text += f"💎 الأعضاء المميزين: {premium_users}\n"
        stats_text += f"⏳ طلبات الانتظار: {pending_requests}\n"
        stats_text += f"📈 نسبة النشاط: {(active_users/total_users*100) if total_users > 0 else 0:.1f}%"
        
        await update.message.reply_text(stats_text)
    
    elif text == "💎 ترقية مستخدم":
        await update.message.reply_text("أرسل ID المستخدم للترقية:")
        context.user_data['awaiting_premium_user'] = True
    
    elif text == "🗑 حذف مستخدم":
        await update.message.reply_text("أرسل ID المستخدم للحذف:")
        context.user_data['awaiting_user_delete'] = True
    
    # إدارة الأقسام المتقدمة
    elif text == "📋 عرض الأقسام":
        categories = db.get_categories()
        if categories:
            cats_text = "📁 **الأقسام:**\n\n"
            for cat in categories:
                premium_status = "👑" if cat[2] == 1 else "⭐"
                cats_text += f"{premium_status} {cat[1]} (ID: {cat[0]})\n"
            await update.message.reply_text(cats_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    elif text == "➕ إضافة قسم":
        await update.message.reply_text("أرسل اسم القسم الجديد:\n\nيمكنك إضافة '👑' في البداية لجعله قسم مميز")
        context.user_data['adding_category'] = True
    
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
    
    elif text == "🔧 تعيين قسم كمميز":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                status = "🔓" if cat[2] == 0 else "🔒"
                keyboard.append([KeyboardButton(f"{status} {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة الأقسام")])
            await update.message.reply_text("اختر قسم لتغيير حالة التميز:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
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
    
    # إدارة القصص المتقدمة
    elif text == "📋 عرض القصص":
        stories = db.get_all_stories()
        if stories:
            stories_text = "📖 **القصص:**\n\n"
            for story in stories:
                premium_status = "👑" if story[4] == 1 else "⭐"
                stories_text += f"{premium_status} {story[1]} - {story[5]} (القسم: {story[6]})\n"
            await update.message.reply_text(stories_text)
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    elif text == "➕ إضافة قصة":
        categories = db.get_categories()
        if not categories:
            await update.message.reply_text("⚠️ لا توجد أقسام. أضف قسم أولاً.")
            return
        await update.message.reply_text("أرسل القصة بالتنسيق:\nالقسم: اسم القسم\nالعنوان: عنوان القصة\nالمحتوى: محتوى القصة\n\nأضف '👑' قبل العنوان لجعلها قصة مميزة")
        context.user_data['adding_story'] = True
    
    elif text == "✏️ تعديل قصة":
        stories = db.get_all_stories()
        if stories:
            keyboard = []
            for story in stories:
                keyboard.append([KeyboardButton(f"تعديل {story[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة القصص")])
            await update.message.reply_text("اختر قصة للتعديل:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    elif text == "🔧 تعيين قصة كمميزة":
        stories = db.get_all_stories()
        if stories:
            keyboard = []
            for story in stories:
                status = "🔓" if story[4] == 0 else "🔒"
                keyboard.append([KeyboardButton(f"{status} {story[1]}")])
            keyboard.append([KeyboardButton("🔙 إدارة القصص")])
            await update.message.reply_text("اختر قصة لتغيير حالة التميز:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
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
    
    # إعدادات المميزين
    elif text == "👑 عرض المميزين":
        premium_users = [u for u in db.get_all_users() if u[6] == 1]
        if premium_users:
            premium_text = "👑 **الأعضاء المميزين:**\n\n"
            for user_data in premium_users:
                premium_text += f"🆔 {user_data[0]} - 👤 {user_data[2]} - 📅 {user_data[7].split()[0] if user_data[7] else 'غير معروف'}\n"
            await update.message.reply_text(premium_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد أعضاء مميزين.")
    
    elif text == "🔻 إزالة التميز":
        premium_users = [u for u in db.get_all_users() if u[6] == 1]
        if premium_users:
            keyboard = []
            for user_data in premium_users:
                keyboard.append([KeyboardButton(f"إزالة {user_data[0]}")])
            keyboard.append([KeyboardButton("🔙 إدارة المميزين")])
            await update.message.reply_text("اختر مستخدم لإزالة التميز:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا يوجد أعضاء مميزين.")
    
    elif text == "📊 إحصائيات المميزين":
        premium_users = [u for u in db.get_all_users() if u[6] == 1]
        total_users = len(db.get_all_users())
        premium_percentage = (len(premium_users) / total_users * 100) if total_users > 0 else 0
        
        stats_text = f"💎 **إحصائيات المميزين:**\n\n"
        stats_text += f"👑 عدد المميزين: {len(premium_users)}\n"
        stats_text += f"👥 إجمالي المستخدمين: {total_users}\n"
        stats_text += f"📈 نسبة المميزين: {premium_percentage:.1f}%\n"
        stats_text += f"🔧 النظام: {'مفعل' if db.get_setting('premium_enabled') == '1' else 'معطل'}"
        
        await update.message.reply_text(stats_text)
    
    elif text == "✏️ تعديل رسالة المميزين":
        current = db.get_setting('premium_access_message')
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_premium_message'] = True
    
    elif text == "🔧 تفعيل/تعطيل النظام":
        current = db.get_setting('premium_enabled')
        new_status = '0' if current == '1' else '1'
        db.update_setting('premium_enabled', new_status)
        status = "تعطيل" if new_status == '0' else "تفعيل"
        await update.message.reply_text(f"✅ تم {status} نظام العضوية المميزة", reply_markup=admin_premium_menu())
    
    # البث الجماعي المتقدم
    elif text == "📢 للجميع":
        await update.message.reply_text("أرسل الرسالة للبث لجميع المستخدمين:")
        context.user_data['broadcasting_all'] = True
    
    elif text == "👥 للنشطين":
        await update.message.reply_text("أرسل الرسالة للبث للمستخدمين النشطين:")
        context.user_data['broadcasting_active'] = True
    
    elif text == "💎 للمميزين فقط":
        await update.message.reply_text("أرسل الرسالة للبث للأعضاء المميزين فقط:")
        context.user_data['broadcasting_premium'] = True
    
    elif text == "📋 سجل البث":
        broadcasts = db.get_broadcasts()
        if broadcasts:
            broadcast_text = "📋 **سجل البث:**\n\n"
            for broadcast in broadcasts:
                broadcast_text += f"📢 {broadcast[1]}\n🎯 {broadcast[3]}\n📊 {broadcast[4]} مستخدم\n📅 {broadcast[5].split()[0]}\n\n"
            await update.message.reply_text(broadcast_text)
        else:
            await update.message.reply_text("⚠️ لا توجد عمليات بث سابقة.")
    
    elif text == "✏️ تعديل نص الإشعار":
        current = db.get_setting('broadcast_notification_text')
        await update.message.reply_text(f"النص الحالي: {current}\n\nأرسل النص الجديد:")
        context.user_data['editing_broadcast_text'] = True
    
    # الإعدادات العامة
    elif text == "✏️ رسالة الترحيب":
        current = db.get_setting('welcome_message')
        await update.message.reply_text(f"الرسالة الحالية:\n{current}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_welcome'] = True
    
    elif text == "📝 حول البوت":
        current = db.get_setting('about_text')
        await update.message.reply_text(f"النص الحالي:\n{current}\n\nأرسل النص الجديد:")
        context.user_data['editing_about'] = True
    
    elif text == "📞 اتصل بنا":
        current = db.get_setting('contact_text')
        await update.message.reply_text(f"النص الحالي:\n{current}\n\nأرسل النص الجديد:")
        context.user_data['editing_contact'] = True
    
    elif text == "🔄 زر البدء":
        current = db.get_setting('start_button_text')
        await update.message.reply_text(f"النص الحالي: {current}\n\nأرسل النص الجديد:")
        context.user_data['editing_start_button'] = True
    
    elif text == "🔐 نظام الموافقة":
        current = db.get_setting('approval_required')
        new_status = '0' if current == '1' else '1'
        db.update_setting('approval_required', new_status)
        status = "معطل" if new_status == '0' else "مفعل"
        await update.message.reply_text(f"✅ تم {status} نظام الموافقة", reply_markup=admin_settings_menu())
    
    elif text == "🎯 إعدادات المميزين":
        await update.message.reply_text("🎯 إعدادات المميزين", reply_markup=admin_premium_menu())
    
    elif text == "📢 إعدادات البث":
        await update.message.reply_text("📢 إعدادات البث", reply_markup=admin_broadcast_menu())
    
    elif text == "🔧 جميع الإعدادات":
        await show_all_settings(update, context)
    
    # معالجة إدخال البيانات
    elif context.user_data.get('awaiting_premium_user'):
        try:
            target_user_id = int(text)
            db.make_premium(target_user_id)
            await update.message.reply_text(f"✅ تم ترقية المستخدم {target_user_id} إلى مميز", reply_markup=admin_users_menu())
        except:
            await update.message.reply_text("❌ ID غير صحيح", reply_markup=admin_users_menu())
        context.user_data.clear()
    
    elif context.user_data.get('awaiting_user_delete'):
        try:
            target_user_id = int(text)
            db.delete_user(target_user_id)
            await update.message.reply_text(f"✅ تم حذف المستخدم {target_user_id}", reply_markup=admin_users_menu())
        except:
            await update.message.reply_text("❌ ID غير صحيح", reply_markup=admin_users_menu())
        context.user_data.clear()
    
    elif context.user_data.get('adding_category'):
        is_premium = text.startswith('👑')
        category_name = text.replace('👑', '').strip()
        db.add_category(category_name, is_premium)
        status = "مميز 👑" if is_premium else "عادي ⭐"
        await update.message.reply_text(f"✅ تم إضافة القسم: {category_name} ({status})", reply_markup=admin_categories_menu())
        context.user_data.clear()
    
    elif context.user_data.get('adding_story'):
        try:
            lines = text.split('\n')
            category_name = lines[0].replace('القسم:', '').strip()
            title_line = lines[1].replace('العنوان:', '').strip()
            content = lines[2].replace('المحتوى:', '').strip()
            
            is_premium = title_line.startswith('👑')
            title = title_line.replace('👑', '').strip()
            
            category_id = get_category_id_by_name(category_name)
            if category_id:
                db.add_story(title, content, category_id, is_premium)
                status = "مميزة 👑" if is_premium else "عادية ⭐"
                await update.message.reply_text(f"✅ تم إضافة القصة: {title} ({status})", reply_markup=admin_stories_menu())
            else:
                await update.message.reply_text("❌ قسم غير موجود")
        except Exception as e:
            await update.message.reply_text(f"❌ تنسيق غير صحيح: {e}")
        context.user_data.clear()
    
    elif context.user_data.get('editing_welcome'):
        db.update_setting('welcome_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب", reply_markup=admin_settings_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_about'):
        db.update_setting('about_text', text)
        await update.message.reply_text("✅ تم تحديث حول البوت", reply_markup=admin_settings_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_contact'):
        db.update_setting('contact_text', text)
        await update.message.reply_text("✅ تم تحديث اتصل بنا", reply_markup=admin_settings_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_start_button'):
        db.update_setting('start_button_text', text)
        await update.message.reply_text("✅ تم تحديث زر البدء", reply_markup=admin_settings_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_premium_message'):
        db.update_setting('premium_access_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة المميزين", reply_markup=admin_premium_menu())
        context.user_data.clear()
    
    elif context.user_data.get('editing_broadcast_text'):
        db.update_setting('broadcast_notification_text', text)
        await update.message.reply_text("✅ تم تحديث نص إشعار البث", reply_markup=admin_broadcast_menu())
        context.user_data.clear()
    
    elif context.user_data.get('broadcasting_all'):
        users = db.get_all_users()
        success = 0
        notification_text = db.get_setting('broadcast_notification_text')
        
        for user_data in users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=f"{notification_text}:\n\n{text}")
                success += 1
            except:
                continue
        
        db.add_broadcast("بث لجميع المستخدمين", text, "all")
        await update.message.reply_text(f"✅ تم الإرسال إلى {success} مستخدم", reply_markup=admin_main_menu())
        context.user_data.clear()
    
    elif context.user_data.get('broadcasting_active'):
        users = db.get_active_users(30)
        success = 0
        notification_text = db.get_setting('broadcast_notification_text')
        
        for user_data in users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=f"{notification_text}:\n\n{text}")
                success += 1
            except:
                continue
        
        db.add_broadcast("بث للمستخدمين النشطين", text, "active")
        await update.message.reply_text(f"✅ تم الإرسال إلى {success} مستخدم نشط", reply_markup=admin_main_menu())
        context.user_data.clear()
    
    elif context.user_data.get('broadcasting_premium'):
        premium_users = [u for u in db.get_all_users() if u[6] == 1]
        success = 0
        notification_text = db.get_setting('broadcast_notification_text')
        
        for user_data in premium_users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=f"{notification_text}:\n\n{text}")
                success += 1
            except:
                continue
        
        db.add_broadcast("بث للأعضاء المميزين", text, "premium")
        await update.message.reply_text(f"✅ تم الإرسال إلى {success} عضو مميز", reply_markup=admin_main_menu())
        context.user_data.clear()
    
    # معالجة الحذف والتعديل
    elif text.startswith("حذف "):
        item_name = text.replace("حذف ", "")
        
        # حذف قسم
        category_id = get_category_id_by_name(item_name)
        if category_id:
            db.delete_category(category_id)
            await update.message.reply_text(f"✅ تم حذف القسم: {item_name}", reply_markup=admin_categories_menu())
            return
        
        # حذف قصة
        stories = db.get_all_stories()
        for story in stories:
            if story[1] == item_name:
                db.delete_story(story[0])
                await update.message.reply_text(f"✅ تم حذف القصة: {item_name}", reply_markup=admin_stories_menu())
                return
        
        await update.message.reply_text("❌ لم يتم العثور")
    
    elif text.startswith("تعديل "):
        item_name = text.replace("تعديل ", "")
        # يمكن إضافة منطق التعديل هنا
        await update.message.reply_text(f"⏳ ميزة تعديل {item_name} قيد التطوير")
    
    elif text.startswith("🔓 ") or text.startswith("🔒 "):
        item_name = text[2:]  # إزالة الإيموجي
        new_status = 1 if text.startswith("🔓") else 0
        
        # تغيير حالة قسم
        category_id = get_category_id_by_name(item_name)
        if category_id:
            db.update_category(category_id, item_name, new_status)
            status = "مميز 👑" if new_status == 1 else "عادي ⭐"
            await update.message.reply_text(f"✅ تم تغيير حالة القسم {item_name} إلى {status}", reply_markup=admin_categories_menu())
            return
        
        # تغيير حالة قصة
        stories = db.get_all_stories()
        for story in stories:
            if story[1] == item_name:
                db.conn.execute('UPDATE stories SET is_premium = ? WHERE id = ?', (new_status, story[0]))
                db.conn.commit()
                status = "مميزة 👑" if new_status == 1 else "عادية ⭐"
                await update.message.reply_text(f"✅ تم تغيير حالة القصة {item_name} إلى {status}", reply_markup=admin_stories_menu())
                return
        
        await update.message.reply_text("❌ لم يتم العثور")
    
    elif text.startswith("إزالة "):
        user_id_str = text.replace("إزالة ", "")
        try:
            target_user_id = int(user_id_str)
            db.remove_premium(target_user_id)
            await update.message.reply_text(f"✅ تم إزالة التميز من المستخدم {target_user_id}", reply_markup=admin_premium_menu())
        except:
            await update.message.reply_text("❌ ID غير صحيح")
    
    else:
        await update.message.reply_text("👑 لوحة تحكم المدير المتقدمة", reply_markup=admin_main_menu())

async def show_advanced_settings(update: Update, context: CallbackContext):
    settings = db.get_all_settings()
    settings_text = "🔧 **الإعدادات المتقدمة:**\n\n"
    
    for setting in settings:
        value_preview = setting[1][:50] + "..." if len(setting[1]) > 50 else setting[1]
        settings_text += f"**{setting[0]}:** {value_preview}\n\n"
    
    keyboard = [
        [KeyboardButton("✏️ تعديل إعداد"), KeyboardButton("🔄 إعادة التعيين")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    
    await update.message.reply_text(settings_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def show_all_settings(update: Update, context: CallbackContext):
    settings = db.get_all_settings()
    settings_text = "⚙️ **جميع إعدادات البوت:**\n\n"
    
    for setting in settings:
        settings_text += f"**{setting[0]}:**\n`{setting[1]}`\n\n"
    
    await update.message.reply_text(settings_text, reply_markup=admin_settings_menu())

async def show_advanced_statistics(update: Update, context: CallbackContext):
    total_users = len(db.get_all_users())
    active_users = len(db.get_active_users(30))
    premium_users = len([u for u in db.get_all_users() if u[6] == 1])
    total_stories = len(db.get_all_stories())
    total_categories = len(db.get_categories())
    pending_requests = len(db.get_pending_requests())
    
    # إحصائيات متقدمة
    active_rate = (active_users / total_users * 100) if total_users > 0 else 0
    premium_rate = (premium_users / total_users * 100) if total_users > 0 else 0
    
    stats_text = f"📊 **الإحصائيات المتقدمة:**\n\n"
    stats_text += f"👥 إجمالي المستخدمين: {total_users}\n"
    stats_text += f"🎯 المستخدمين النشطين: {active_users}\n"
    stats_text += f"💎 الأعضاء المميزين: {premium_users}\n"
    stats_text += f"📖 إجمالي القصص: {total_stories}\n"
    stats_text += f"📁 إجمالي الأقسام: {total_categories}\n"
    stats_text += f"⏳ طلبات الانتظار: {pending_requests}\n\n"
    stats_text += f"📈 **النسب:**\n"
    stats_text += f"• نسبة النشاط: {active_rate:.1f}%\n"
    stats_text += f"• نسبة المميزين: {premium_rate:.1f}%\n"
    stats_text += f"• متوسط القصص لكل قسم: {total_stories/total_categories if total_categories > 0 else 0:.1f}"
    
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
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت مع الميزات المتقدمة...")
    application.run_polling()

if __name__ == '__main__':
    main()

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

# فئة قاعدة البيانات المطورة
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('stories_bot.db', check_same_thread=False)
        self.create_tables()
        self.create_admin()
        self.create_default_settings()
        self.create_default_categories()

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
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول الأقسام
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                icon TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_by INTEGER,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # جدول القصص
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                content_type TEXT DEFAULT 'text',
                file_id TEXT,
                category_id INTEGER,
                is_featured INTEGER DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
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

        # جدول الإعدادات
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT
            )
        ''')

        # جدول الإحصائيات
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                new_users INTEGER DEFAULT 0,
                stories_views INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0
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

    def create_default_categories(self):
        default_categories = [
            ('📚 قصص رعب', '👻', 1),
            ('💖 قصص رومانسية', '❤️', 2),
            ('🚀 قصص خيال علمي', '🛸', 3),
            ('😂 قصص كوميدية', '😄', 4),
            ('🔍 قصص غامضة', '🕵️', 5)
        ]
        
        for name, icon, order in default_categories:
            self.conn.execute('''
                INSERT OR IGNORE INTO categories (name, icon, sort_order)
                VALUES (?, ?, ?)
            ''', (name, icon, order))
        self.conn.commit()

    def create_default_settings(self):
        default_settings = [
            ('welcome_message', '🎭 **مرحباً بك في عالم القصص المثير!**\n\nاختر من مجموعتنا المتنوعة من القصص المثيرة والمشوقة.', 'رسالة الترحيب الرئيسية'),
            ('approval_required', '1', 'تفعيل نظام الموافقة على الطلبات (1/0)'),
            ('about_text', '🤖 **بوت القصص التفاعلي**\n\n• 📚 آلاف القصص المتنوعة\n• 🎭 تجربة قراءة فريدة\n• ⭐ قصص حصرية ومميزة\n• 🔄 تحديث مستمر للمحتوى', 'نص قسم حول البوت'),
            ('contact_text', '📞 **للتواصل معنا:**\n\n📧 البريد الإلكتروني: support@stories.com\n📱 الدعم الفني: @stories_support\n🌐 الموقع الإلكتروني: www.stories.com', 'نص قسم اتصل بنا'),
            ('broadcast_template', '🎊 **إشعار مهم** 🎊\n\n{message}\n\nمع خالص التحيات,\nفريق البوت ❤️', 'قالب الرسائل الجماعية'),
            ('start_button_text', '🚀 ابدأ الرحلة', 'نص زر البدء'),
            ('auto_approve', '0', 'الموافقة التلقائية على المستخدمين الجدد (1/0)'),
            ('premium_enabled', '1', 'تفعيل النظام المميز (1/0)'),
            ('daily_story_limit', '5', 'عدد القصص المجانية يومياً'),
            ('welcome_gift', '3', 'عدد القصص المجانية هدية للقادمين الجدد')
        ]
        
        for key, value, description in default_settings:
            self.conn.execute('''
                INSERT OR IGNORE INTO bot_settings (key, value, description)
                VALUES (?, ?, ?)
            ''', (key, value, description))
        self.conn.commit()

    # دوال الإعدادات
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

    # دوال المستخدمين المحسنة
    def add_user(self, user_id, username, first_name, last_name, is_approved=False, is_admin=False):
        self.conn.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, is_approved, is_admin, last_active)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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

    def update_user_activity(self, user_id):
        self.conn.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def get_all_users(self):
        cursor = self.conn.execute('SELECT * FROM users WHERE is_approved = 1 ORDER BY joined_date DESC')
        return cursor.fetchall()

    def get_active_users(self, days=7):
        cursor = self.conn.execute('''
            SELECT * FROM users 
            WHERE is_approved = 1 AND last_active >= datetime("now", ?)
            ORDER BY last_active DESC
        ''', (f"-{days} days",))
        return cursor.fetchall()

    def get_pending_requests(self):
        cursor = self.conn.execute('SELECT * FROM join_requests ORDER BY request_date DESC')
        return cursor.fetchall()

    def delete_user(self, user_id):
        self.conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def make_premium(self, user_id):
        self.conn.execute('UPDATE users SET is_premium = 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def revoke_premium(self, user_id):
        self.conn.execute('UPDATE users SET is_premium = 0 WHERE user_id = ?', (user_id,))
        self.conn.commit()

    # دوال الأقسام المحسنة
    def add_category(self, name, icon, created_by):
        self.conn.execute('INSERT OR IGNORE INTO categories (name, icon, created_by) VALUES (?, ?, ?)', (name, icon, created_by))
        self.conn.commit()

    def get_categories(self):
        cursor = self.conn.execute('SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order, name')
        return cursor.fetchall()

    def get_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        return cursor.fetchone()

    def delete_category(self, category_id):
        self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.commit()

    # دوال القصص المحسنة
    def add_story(self, title, content, content_type, file_id, category_id, created_by, is_featured=False):
        self.conn.execute('''
            INSERT INTO stories (title, content, content_type, file_id, category_id, created_by, is_featured)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, content_type, file_id, category_id, created_by, is_featured))
        self.conn.commit()

    def increment_story_views(self, story_id):
        self.conn.execute('UPDATE stories SET views_count = views_count + 1 WHERE id = ?', (story_id,))
        self.conn.commit()

    def get_stories_by_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM stories WHERE category_id = ? ORDER BY is_featured DESC, created_date DESC', (category_id,))
        return cursor.fetchall()

    def get_featured_stories(self):
        cursor = self.conn.execute('SELECT * FROM stories WHERE is_featured = 1 ORDER BY created_date DESC LIMIT 10')
        return cursor.fetchall()

    def get_popular_stories(self):
        cursor = self.conn.execute('SELECT * FROM stories ORDER BY views_count DESC, likes_count DESC LIMIT 10')
        return cursor.fetchall()

    def get_story(self, story_id):
        cursor = self.conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,))
        return cursor.fetchone()

    def get_all_stories(self):
        cursor = self.conn.execute('''
            SELECT s.*, c.name as category_name, c.icon as category_icon
            FROM stories s 
            JOIN categories c ON s.category_id = c.id
            ORDER BY s.created_date DESC
        ''')
        return cursor.fetchall()

    def delete_story(self, story_id):
        self.conn.execute('DELETE FROM stories WHERE id = ?', (story_id,))
        self.conn.commit()

    def update_story(self, story_id, title, content):
        self.conn.execute('UPDATE stories SET title = ?, content = ? WHERE id = ?', (title, content, story_id))
        self.conn.commit()

    def toggle_featured(self, story_id):
        self.conn.execute('UPDATE stories SET is_featured = NOT is_featured WHERE id = ?', (story_id,))
        self.conn.commit()

    # دوال الإحصائيات
    def update_daily_stats(self):
        today = datetime.now().date()
        cursor = self.conn.execute('SELECT * FROM statistics WHERE date = ?', (today,))
        if not cursor.fetchone():
            self.conn.execute('INSERT INTO statistics (date) VALUES (?)', (today,))
        self.conn.commit()

    def increment_stories_views(self):
        today = datetime.now().date()
        self.conn.execute('UPDATE statistics SET stories_views = stories_views + 1 WHERE date = ?', (today,))
        self.conn.commit()

    def increment_total_messages(self):
        today = datetime.now().date()
        self.conn.execute('UPDATE statistics SET total_messages = total_messages + 1 WHERE date = ?', (today,))
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

def approval_required():
    return db.get_setting('approval_required') == '1'

def auto_approve_enabled():
    return db.get_setting('auto_approve') == '1'

def get_start_button_text():
    return db.get_setting('start_button_text') or '🚀 ابدأ الرحلة'

def premium_enabled():
    return db.get_setting('premium_enabled') == '1'

# لوحات المفاتيح للمستخدم العادي
def main_keyboard(user_id=None):
    user = db.get_user(user_id) if user_id else None
    is_premium = user and user[6] == 1 if user else False
    
    keyboard = [
        [KeyboardButton("📚 اكتشف القصص"), KeyboardButton("⭐ المميزة")],
        [KeyboardButton("🔥 الأكثر شيوعاً"), KeyboardButton("🔍 البحث")],
    ]
    
    if premium_enabled():
        if is_premium:
            keyboard.append([KeyboardButton("👑 العضوية المميزة")])
        else:
            keyboard.append([KeyboardButton("💎 ترقية إلى مميز")])
    
    keyboard.extend([
        [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")],
        [KeyboardButton("⚙️ الإعدادات")]
    ])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def start_keyboard():
    start_text = get_start_button_text()
    keyboard = [
        [KeyboardButton(start_text)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def categories_keyboard():
    categories = db.get_categories()
    keyboard = []
    for i in range(0, len(categories), 2):
        row = categories[i:i+2]
        keyboard.append([KeyboardButton(f"{cat[2]} {cat[1]}") for cat in row])
    keyboard.append([KeyboardButton("🏠 الرئيسية"), KeyboardButton("⭐ المميزة")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def stories_keyboard(category_id, stories):
    keyboard = []
    for i in range(0, len(stories), 2):
        row = stories[i:i+2]
        keyboard.append([KeyboardButton(f"{'⭐ ' if story[7] == 1 else ''}📖 {story[1]}") for story in row])
    keyboard.append([KeyboardButton("🔙 رجوع للأقسام"), KeyboardButton("🏠 الرئيسية")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def settings_keyboard():
    keyboard = [
        [KeyboardButton("👤 الملف الشخصي"), KeyboardButton("🔔 الإشعارات")],
        [KeyboardButton("🌙 الوضع الليلي"), KeyboardButton("🔄 تحديث البيانات")],
        [KeyboardButton("🏠 الرئيسية")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحات المفاتيح للمدير - المطورة بشكل كامل
def admin_main_keyboard():
    keyboard = [
        [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
        [KeyboardButton("📖 إدارة القصص"), KeyboardButton("⭐ إدارة المميز")],
        [KeyboardButton("📊 الإحصائيات المتقدمة"), KeyboardButton("⚙️ الإعدادات المتقدمة")],
        [KeyboardButton("🎯 الحملات التسويقية"), KeyboardButton("🔍 التقارير")],
        [KeyboardButton("📢 البث الجماعي"), KeyboardButton("🔄 تحديث النظام")],
        [KeyboardButton("🔙 وضع المستخدم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_users_keyboard():
    keyboard = [
        [KeyboardButton("📋 جميع المستخدمين"), KeyboardButton("👤 المستخدمون النشطون")],
        [KeyboardButton("⏳ طلبات الانضمام"), KeyboardButton("💎 المستخدمون المميزون")],
        [KeyboardButton("🗑 حذف مستخدم"), KeyboardButton("👑 ترقية مستخدم")],
        [KeyboardButton("📧 مراسلة مستخدم"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_categories_keyboard():
    keyboard = [
        [KeyboardButton("➕ إضافة قسم"), KeyboardButton("🗑 حذف قسم")],
        [KeyboardButton("✏️ تعديل قسم"), KeyboardButton("📋 عرض الأقسام")],
        [KeyboardButton("🔧 إدارة الأقسام"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_stories_keyboard():
    keyboard = [
        [KeyboardButton("➕ إضافة قصة"), KeyboardButton("✏️ تعديل قصة")],
        [KeyboardButton("🗑 حذف قصة"), KeyboardButton("⭐ إدارة المميز")],
        [KeyboardButton("📊 إحصائيات القصص"), KeyboardButton("📋 جميع القصص")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_premium_keyboard():
    keyboard = [
        [KeyboardButton("💎 ترقية مستخدم"), KeyboardButton("🔻 إلغاء الترقية")],
        [KeyboardButton("📋 المستخدمون المميزون"), KeyboardButton("⚙️ إعدادات النظام المميز")],
        [KeyboardButton("🎁 عروض خاصة"), KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_stats_keyboard():
    keyboard = [
        [KeyboardButton("📈 إحصائيات اليوم"), KeyboardButton("📊 إحصائيات الأسبوع")],
        [KeyboardButton("📅 إحصائيات الشهر"), KeyboardButton("📋 التقرير الكامل")],
        [KeyboardButton("👥 نمو المستخدمين"), KeyboardButton("📖 نشاط القصص")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_settings_keyboard():
    approval_status = "✅ مفعل" if approval_required() else "❌ معطل"
    auto_approve_status = "✅ مفعل" if auto_approve_enabled() else "❌ معطل"
    premium_status = "✅ مفعل" if premium_enabled() else "❌ معطل"
    
    keyboard = [
        [KeyboardButton("✏️ تعديل رسالة الترحيب"), KeyboardButton("📝 تعديل حول البوت")],
        [KeyboardButton("📞 تعديل اتصل بنا"), KeyboardButton("📋 تعديل قالب الإشعارات")],
        [KeyboardButton("🔄 تعديل زر البدء"), KeyboardButton("⚙️ الإعدادات العامة")],
        [KeyboardButton(f"🔐 نظام الموافقة: {approval_status}"), KeyboardButton(f"🤖 الموافقة التلقائية: {auto_approve_status}")],
        [KeyboardButton(f"💎 النظام المميز: {premium_status}"), KeyboardButton("📁 عرض كل الإعدادات")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_broadcast_keyboard():
    keyboard = [
        [KeyboardButton("📢 بث لجميع المستخدمين"), KeyboardButton("👥 بث للمستخدمين النشطين")],
        [KeyboardButton("💎 بث للمستخدمين المميزين"), KeyboardButton("🆕 بث للقادمين الجدد")],
        [KeyboardButton("🔙 لوحة التحكم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# دوال مساعدة إضافية
def admin_add_story_keyboard():
    categories = db.get_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([KeyboardButton(f"{cat[2]} إضافة في {cat[1]}")])
    keyboard.append([KeyboardButton("🔙 إدارة القصص")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_story_type_keyboard():
    keyboard = [
        [KeyboardButton("📝 قصة نصية"), KeyboardButton("🎥 قصة فيديو")],
        [KeyboardButton("🖼️ قصة صورة"), KeyboardButton("🎵 قصة صوتية")],
        [KeyboardButton("🔙 إضافة قصة")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_feature_stories_keyboard():
    stories = db.get_all_stories()
    keyboard = []
    for story in stories:
        featured_icon = "✅" if story[7] == 1 else "❌"
        keyboard.append([KeyboardButton(f"{featured_icon} {story[1]}")])
    keyboard.append([KeyboardButton("🔙 إدارة القصص")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# معالجة الأوامر للمستخدمين - الإصدار المحسن
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    context.user_data.clear()
    db.update_user_activity(user_id)
    
    if user_id == get_admin_id():
        db.add_user(user_id, user.username, user.first_name, user.last_name, True, True, True)
        await update.message.reply_text(
            f"👑 **مرحباً kembali آلة المدير {user.first_name}!**\n\n"
            "لوحة التحكم المتكاملة جاهزة للاستخدام.",
            reply_markup=admin_main_keyboard()
        )
        return
    
    user_data = db.get_user(user_id)
    
    # إذا كان المستخدم معتمداً بالفعل
    if user_data and user_data[4] == 1:
        welcome_message = db.get_setting('welcome_message') or 'مرحباً بك في بوت القصص! 🎭'
        await update.message.reply_text(
            f"{welcome_message}\n\nمرحباً kembali {user.first_name}! 👋",
            reply_markup=main_keyboard(user_id)
        )
        return
    
    # إذا لم يكن معتمداً بعد
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    if auto_approve_enabled():
        db.approve_user(user_id)
        welcome_message = db.get_setting('welcome_message') or 'مرحباً بك في بوت القصص! 🎭'
        await update.message.reply_text(
            f"🎉 {welcome_message}\n\nأهلاً وسهلاً بك {user.first_name}! 👋",
            reply_markup=main_keyboard(user_id)
        )
    elif approval_required():
        # التحقق إذا كان هناك طلب pending بالفعل
        pending_requests = db.get_pending_requests()
        user_has_pending = any(req[0] == user_id for req in pending_requests)
        
        if not user_has_pending:
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
                    text=f"📩 **طلب انضمام جديد**\n\n"
                         f"👤 **الاسم:** {user.first_name} {user.last_name or ''}\n"
                         f"📱 **Username:** @{user.username or 'لا يوجد'}\n"
                         f"🆔 **ID:** {user_id}\n"
                         f"🕒 **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"خطأ في إرسال الرسالة للمدير: {e}")
        
        await update.message.reply_text(
            "📋 **تم إرسال طلب انضمامك إلى المدير**\n\n"
            "سوف نراجع طلبك في أقرب وقت ممكن وستصلك رسالة تأكيد عند الموافقة.\n\n"
            "شكراً لصبرك! ⏳",
            reply_markup=start_keyboard()
        )
    else:
        # إذا كان نظام الموافقة معطلاً
        db.approve_user(user_id)
        welcome_message = db.get_setting('welcome_message') or 'مرحباً بك في بوت القصص! 🎭'
        await update.message.reply_text(
            f"🎉 {welcome_message}\n\nأهلاً وسهلاً بك {user.first_name}! 👋",
            reply_markup=main_keyboard(user_id)
        )

# معالجة ضغطات الأزرار للمدير - الإصدار المحسن
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
            welcome_message = db.get_setting('welcome_message') or 'مرحباً بك في بوت القصص! 🎭'
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **تمت الموافقة على طلب انضمامك!**\n\n{welcome_message}",
                reply_markup=main_keyboard(target_user_id)
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
        
        await query.edit_message_text(
            f"✅ **تمت الموافقة على المستخدم**\n\n"
            f"🆔 ID: {target_user_id}\n"
            f"✅ تم إرسال رسالة ترحيب للمستخدم"
        )
        
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        db.reject_user(target_user_id)
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")

# معالجة الوسائط
async def handle_media(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    
    if user_id != get_admin_id():
        return
    
    if context.user_data.get('adding_story'):
        content_type = context.user_data.get('story_content_type')
        category_id = context.user_data.get('story_category_id')
        title = context.user_data.get('story_title')
        is_featured = context.user_data.get('story_featured', False)
        
        if content_type == 'video' and update.message.video:
            file_id = update.message.video.file_id
            db.add_story(title, "فيديو", "video", file_id, category_id, user_id, is_featured)
            await update.message.reply_text(f"✅ تم إضافة القصة الفيديوية: {title}", reply_markup=admin_stories_keyboard())
            
        elif content_type == 'photo' and update.message.photo:
            file_id = update.message.photo[-1].file_id
            db.add_story(title, "صورة", "photo", file_id, category_id, user_id, is_featured)
            await update.message.reply_text(f"✅ تم إضافة القصة المصورة: {title}", reply_markup=admin_stories_keyboard())
        
        elif content_type == 'audio' and update.message.audio:
            file_id = update.message.audio.file_id
            db.add_story(title, "صوتية", "audio", file_id, category_id, user_id, is_featured)
            await update.message.reply_text(f"✅ تم إضافة القصة الصوتية: {title}", reply_markup=admin_stories_keyboard())
        
        context.user_data.clear()

# معالجة الرسائل للمستخدمين - الإصدار المحسن بشكل كامل
async def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    # تحديث نشاط المستخدم
    db.update_user_activity(user_id)
    db.increment_total_messages()
    
    if user_id == get_admin_id():
        await handle_admin_message(update, context)
        return
    
    user_data = db.get_user(user_id)
    start_button_text = get_start_button_text()
    
    # معالجة زر البدء الديناميكي
    if text == start_button_text:
        if not user_data or user_data[4] == 0:
            if auto_approve_enabled():
                db.approve_user(user_id)
                welcome_message = db.get_setting('welcome_message') or 'مرحباً بك في بوت القصص! 🎭'
                await update.message.reply_text(f"🎉 {welcome_message}", reply_markup=main_keyboard(user_id))
            else:
                await update.message.reply_text(
                    "⏳ **لم يتم الموافقة على حسابك بعد**\n\n"
                    "نقوم بمراجعة طلبك وسنعلمك فور الموافقة.\n"
                    "شكراً لصبرك! 🙏",
                    reply_markup=start_keyboard()
                )
        else:
            # إذا كان المستخدم معتمداً بالفعل
            welcome_message = db.get_setting('welcome_message') or 'مرحباً بك في بوت القصص! 🎭'
            await update.message.reply_text(f"🎭 {welcome_message}", reply_markup=main_keyboard(user_id))
        return
    
    # إذا لم يكن المستخدم معتمداً بعد
    if not user_data or user_data[4] == 0:
        await update.message.reply_text(
            "⏳ **جاري مراجعة طلبك**\n\n"
            "لم يتم الموافقة على حسابك بعد. يرجى الانتظار حتى يتم مراجعة طلبك من قبل الإدارة.",
            reply_markup=start_keyboard()
        )
        return
    
    # معالجة رسائل المستخدم العادي المعتمد
    if text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 **الصفحة الرئيسية**", reply_markup=main_keyboard(user_id))
    
    elif text == "📚 اكتشف القصص":
        categories = db.get_categories()
        if categories:
            await update.message.reply_text(
                "📚 **اختر تصنيف القصص:**\n\n"
                "استكشف عالمنا الرائع من القصص المتنوعة!",
                reply_markup=categories_keyboard()
            )
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif text == "⭐ المميزة":
        stories = db.get_featured_stories()
        if stories:
            stories_text = "⭐ **القصص المميزة:**\n\n"
            for story in stories:
                stories_text += f"🌟 {story[1]}\n"
            await update.message.reply_text(stories_text)
            # عرض القصص المميزة
            for story in stories[:5]:  # عرض أول 5 قصص فقط
                if story[3] == 'text':
                    await update.message.reply_text(f"⭐ {story[1]}\n\n{story[2][:200]}...")
                elif story[3] == 'video':
                    await update.message.reply_video(story[4], caption=f"⭐ {story[1]}")
                elif story[3] == 'photo':
                    await update.message.reply_photo(story[4], caption=f"⭐ {story[1]}")
        else:
            await update.message.reply_text("⚠️ لا توجد قصص مميزة حالياً.")
    
    elif text == "🔥 الأكثر شيوعاً":
        stories = db.get_popular_stories()
        if stories:
            stories_text = "🔥 **القصص الأكثر شيوعاً:**\n\n"
            for i, story in enumerate(stories[:10], 1):
                stories_text += f"{i}️⃣ {story[1]} 👁️ {story[8]}\n"
            await update.message.reply_text(stories_text)
        else:
            await update.message.reply_text("⚠️ لا توجد قصص مشهورة حالياً.")
    
    elif text == "🔍 البحث":
        await update.message.reply_text("🔍 **أدخل كلمة البحث:**\n\nاكتب الكلمة التي تريد البحث عنها في عناوين القصص:")
        context.user_data['searching'] = True
    
    elif text == "⚙️ الإعدادات":
        user_data = db.get_user(user_id)
        is_premium = user_data[6] == 1 if user_data else False
        
        settings_text = f"⚙️ **الإعدادات الشخصية**\n\n"
        settings_text += f"👤 **الاسم:** {user.first_name}\n"
        settings_text += f"📱 **Username:** @{user.username or 'غير متوفر'}\n"
        settings_text += f"💎 **العضوية:** {'مميز 👑' if is_premium else 'عادي ⭐'}\n"
        settings_text += f"📅 **تاريخ الانضمام:** {user_data[8][:10] if user_data else 'غير معروف'}\n"
        
        await update.message.reply_text(settings_text, reply_markup=settings_keyboard())
    
    elif text == "💎 ترقية إلى مميز":
        if premium_enabled():
            await update.message.reply_text(
                "💎 **ترقية إلى العضوية المميزة**\n\n"
                "مزايا العضوية المميزة:\n"
                "• 📚 وصول غير محدود للقصص\n"
                "• ⭐ قصص حصرية ومميزة\n"
                "• 🚀 أولوية في التحديثات\n"
                "• 🎁 هدايا وعروض خاصة\n\n"
                "للترقية يرجى التواصل مع الإدارة: @stories_support"
            )
        else:
            await update.message.reply_text("⚠️ النظام المميز غير مفعل حالياً.")
    
    elif text == "👑 العضوية المميزة":
        await update.message.reply_text(
            "👑 **أنت عضو مميز!**\n\n"
            "شكراً لثقتك بنا! استمتع بمزايا العضوية المميزة:\n"
            "• 📚 وصول غير محدود\n"
            "• ⭐ قصص حصرية\n"
            "• 🚀 أولوية في الخدمة\n"
            "• 🎁 عروض خاصة"
        )
    
    elif text == "🔙 رجوع للأقسام":
        await update.message.reply_text("📚 **الأقسام:**", reply_markup=categories_keyboard())
    
    elif text == "👤 الملف الشخصي":
        user_data = db.get_user(user_id)
        is_premium = user_data[6] == 1 if user_data else False
        
        profile_text = f"👤 **الملف الشخصي**\n\n"
        profile_text += f"🆔 **الرقم:** {user_id}\n"
        profile_text += f"👤 **الاسم:** {user.first_name} {user.last_name or ''}\n"
        profile_text += f"📱 **Username:** @{user.username or 'غير متوفر'}\n"
        profile_text += f"💎 **العضوية:** {'مميز 👑' if is_premium else 'عادي ⭐'}\n"
        profile_text += f"📅 **تاريخ الانضمام:** {user_data[8][:10] if user_data else 'غير معروف'}\n"
        profile_text += f"🕒 **آخر نشاط:** {user_data[7][:16] if user_data else 'غير معروف'}\n"
        
        await update.message.reply_text(profile_text)
    
    # البحث في الأقسام
    elif any(cat[2] + " " + cat[1] == text for cat in db.get_categories()):
        for cat in db.get_categories():
            if cat[2] + " " + cat[1] == text:
                stories = db.get_stories_by_category(cat[0])
                if stories:
                    await update.message.reply_text(
                        f"{cat[2]} **{cat[1]}**\n\n"
                        f"اختر القصة التي تريد قراءتها:",
                        reply_markup=stories_keyboard(cat[0], stories)
                    )
                else:
                    await update.message.reply_text(f"⚠️ لا توجد قصص في قسم {cat[1]} حالياً.")
                return
    
    # البحث في القصص
    elif text.startswith("📖 ") or text.startswith("⭐ 📖 "):
        story_title = text.replace("⭐ 📖 ", "").replace("📖 ", "")
        all_stories = db.get_all_stories()
        for story in all_stories:
            if story[1] == story_title:
                db.increment_story_views(story[0])
                db.increment_stories_views()
                
                if story[3] == 'text':
                    await update.message.reply_text(
                        f"{'⭐ ' if story[7] == 1 else ''}📖 **{story[1]}**\n\n"
                        f"{story[2]}\n\n"
                        f"---\n"
                        f"👁️ {story[8] + 1} مشاهدة | ❤️ {story[9]} إعجاب\n"
                        f"📅 {story[11][:10]}\n"
                        f"نهاية القصة 📚"
                    )
                elif story[3] == 'video':
                    await update.message.reply_video(
                        story[4], 
                        caption=f"{'⭐ ' if story[7] == 1 else ''}🎥 **{story[1]}**\n\n👁️ {story[8] + 1} مشاهدة | ❤️ {story[9]} إعجاب"
                    )
                elif story[3] == 'photo':
                    await update.message.reply_photo(
                        story[4], 
                        caption=f"{'⭐ ' if story[7] == 1 else ''}🖼️ **{story[1]}**\n\n👁️ {story[8] + 1} مشاهدة | ❤️ {story[9]} إعجاب"
                    )
                elif story[3] == 'audio':
                    await update.message.reply_audio(
                        story[4], 
                        caption=f"{'⭐ ' if story[7] == 1 else ''}🎵 **{story[1]}**\n\n👁️ {story[8] + 1} مشاهدة | ❤️ {story[9]} إعجاب"
                    )
                return
        
        await update.message.reply_text("❌ القصة غير موجودة.", reply_markup=main_keyboard(user_id))
    
    # البحث
    elif context.user_data.get('searching'):
        search_term = text.lower()
        all_stories = db.get_all_stories()
        found_stories = [s for s in all_stories if search_term in s[1].lower()]
        
        if found_stories:
            search_text = f"🔍 **نتائج البحث عن: '{text}'**\n\n"
            for i, story in enumerate(found_stories[:10], 1):
                search_text += f"{i}️⃣ {story[1]}\n"
            
            await update.message.reply_text(search_text)
            
            # عرض بعض النتائج
            for story in found_stories[:3]:
                if story[3] == 'text':
                    await update.message.reply_text(f"📖 {story[1]}\n\n{story[2][:150]}...")
        else:
            await update.message.reply_text(f"❌ لم يتم العثور على قصص تحتوي على: '{text}'")
        
        context.user_data['searching'] = False
    
    else:
        await update.message.reply_text(
            "❌ **لم أفهم طلبك**\n\n"
            "يرجى استخدام الأزرار المتاحة للتنقل بين خيارات البوت.",
            reply_markup=main_keyboard(user_id)
        )

# معالجة رسائل المدير - النسخة الكاملة المحسنة
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if user_id != get_admin_id():
        await update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى لوحة التحكم.")
        return

    # تحديث الإحصائيات
    db.update_daily_stats()
    
    # تنظيف الحالات القديمة إذا كان المستخدم يبدأ من جديد
    if text in ["🔙 لوحة التحكم", "🏠 الرئيسية", "⚙️ الإعدادات المتقدمة"]:
        context.user_data.clear()

    # === معالجة حالات إدخال البيانات للمدير ===
    
    # حالة تعديل رسالة الترحيب
    if context.user_data.get('editing_welcome'):
        db.update_setting('welcome_message', text)
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب بنجاح!", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
        return
    
    # حالة تعديل حول البوت
    elif context.user_data.get('editing_about'):
        db.update_setting('about_text', text)
        await update.message.reply_text("✅ تم تحديث نص 'حول البوت' بنجاح!", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
        return
    
    # حالة تعديل اتصل بنا
    elif context.user_data.get('editing_contact'):
        db.update_setting('contact_text', text)
        await update.message.reply_text("✅ تم تحديث نص 'اتصل بنا' بنجاح!", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
        return
    
    # حالة تعديل قالب الإشعارات - الإصدار المصحح
    elif context.user_data.get('editing_broadcast_template'):
        # التحقق من أن القالب يحتوي على {message}
        if '{message}' not in text:
            await update.message.reply_text("❌ يجب أن يحتوي القالب على {message} مكان النص الرئيسي. أرسل القالب مرة أخرى:")
            return
        
        db.update_setting('broadcast_template', text)
        await update.message.reply_text("✅ تم تحديث قالب الإشعارات بنجاح!", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
        return
    
    # حالة تعديل زر البدء
    elif context.user_data.get('editing_start_button'):
        db.update_setting('start_button_text', text)
        await update.message.reply_text("✅ تم تحديث نص زر البدء بنجاح!", reply_markup=admin_settings_keyboard())
        context.user_data.clear()
        return
    
    # حالة إضافة قسم جديد
    elif context.user_data.get('adding_category'):
        parts = text.split(' ', 1)
        if len(parts) == 2:
            icon, name = parts
            db.add_category(name, icon, user_id)
            await update.message.reply_text(f"✅ تم إضافة القسم: {icon} {name}", reply_markup=admin_categories_keyboard())
        else:
            await update.message.reply_text("❌ التنسيق غير صحيح. استخدم: أيقونة اسم القسم")
        context.user_data.clear()
        return
    
    # حالة البث الجماعي
    elif context.user_data.get('broadcasting'):
        target = context.user_data.get('broadcast_target', 'all')
        users = []
        
        if target == 'all':
            users = db.get_all_users()
        elif target == 'active':
            users = db.get_active_users(7)
        elif target == 'premium':
            users = [u for u in db.get_all_users() if u[6] == 1]
        elif target == 'new':
            users = [u for u in db.get_all_users() if datetime.now() - datetime.strptime(u[8], '%Y-%m-%d %H:%M:%S') < timedelta(days=7)]
        
        success = 0
        broadcast_template = db.get_setting('broadcast_template') or '📢 إشعار من الإدارة:\n\n{message}'
        
        # استخدام القالب بشكل صحيح
        try:
            message_content = broadcast_template.format(message=text)
        except:
            message_content = f"📢 إشعار من الإدارة:\n\n{text}"
        
        for user_data in users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=message_content)
                success += 1
            except:
                continue
        
        await update.message.reply_text(
            f"✅ **تم إرسال الإشعار بنجاح**\n\n"
            f"📊 **النتائج:**\n"
            f"• 👥 عدد المستهدفين: {len(users)}\n"
            f"• ✅ تم الإرسال: {success}\n"
            f"• ❌ فشل الإرسال: {len(users) - success}",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return

    # === الأوامر الرئيسية للمدير ===
    
    if text == "🔙 وضع المستخدم":
        context.user_data.clear()
        await update.message.reply_text("تم التبديل إلى وضع المستخدم", reply_markup=main_keyboard(user_id))
    
    elif text == "👥 إدارة المستخدمين":
        context.user_data.clear()
        await update.message.reply_text("👥 **لوحة إدارة المستخدمين**", reply_markup=admin_users_keyboard())
    
    elif text == "📁 إدارة الأقسام":
        context.user_data.clear()
        await update.message.reply_text("📁 **لوحة إدارة الأقسام**", reply_markup=admin_categories_keyboard())
    
    elif text == "📖 إدارة القصص":
        context.user_data.clear()
        await update.message.reply_text("📖 **لوحة إدارة القصص**", reply_markup=admin_stories_keyboard())
    
    elif text == "⭐ إدارة المميز":
        context.user_data.clear()
        await update.message.reply_text("💎 **لوحة إدارة النظام المميز**", reply_markup=admin_premium_keyboard())
    
    elif text == "📊 الإحصائيات المتقدمة":
        context.user_data.clear()
        await update.message.reply_text("📊 **لوحة الإحصائيات المتقدمة**", reply_markup=admin_stats_keyboard())
    
    elif text == "⚙️ الإعدادات المتقدمة":
        context.user_data.clear()
        await update.message.reply_text("⚙️ **لوحة الإعدادات المتقدمة**", reply_markup=admin_settings_keyboard())
    
    elif text == "📢 البث الجماعي":
        context.user_data.clear()
        await update.message.reply_text("📢 **لوحة البث الجماعي**", reply_markup=admin_broadcast_keyboard())
    
    elif text == "🔍 التقارير":
        # تقرير سريع
        total_users = len(db.get_all_users())
        active_users = len(db.get_active_users(7))
        premium_users = len([u for u in db.get_all_users() if u[6] == 1])
        total_stories = len(db.get_all_stories())
        pending_requests = len(db.get_pending_requests())
        
        report_text = f"📋 **تقرير سريع**\n\n"
        report_text += f"👥 **المستخدمون:**\n"
        report_text += f"• 📊 الإجمالي: {total_users}\n"
        report_text += f"• 🎯 النشطون: {active_users}\n"
        report_text += f"• 💎 المميزون: {premium_users}\n"
        report_text += f"• ⏳ قيد الانتظار: {pending_requests}\n\n"
        report_text += f"📖 **المحتوى:**\n"
        report_text += f"• 📚 القصص: {total_stories}\n"
        report_text += f"• ⭐ المميزة: {len(db.get_featured_stories())}\n\n"
        report_text += f"🕒 **آخر تحديث:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        await update.message.reply_text(report_text)
    
    elif text == "🔄 تحديث النظام":
        db.update_daily_stats()
        await update.message.reply_text("✅ تم تحديث بيانات النظام بنجاح!", reply_markup=admin_main_keyboard())
    
    elif text == "🎯 الحملات التسويقية":
        await update.message.reply_text(
            "🎯 **إدارة الحملات التسويقية**\n\n"
            "ميزة قادمة قريباً...\n"
            "ستتيح لك إنشاء وإدارة حملات تسويقية متقدمة."
        )

    # === الإعدادات المتقدمة ===
    elif text == "✏️ تعديل رسالة الترحيب":
        current_welcome = db.get_setting('welcome_message') or 'مرحباً بك في بوت القصص! 🎭'
        await update.message.reply_text(f"📝 **الرسالة الحالية:**\n{current_welcome}\n\nأرسل الرسالة الجديدة:")
        context.user_data['editing_welcome'] = True
    
    elif text == "📝 تعديل حول البوت":
        current_about = db.get_setting('about_text') or '🤖 بوت القصص التفاعلي'
        await update.message.reply_text(f"ℹ️ **النص الحالي:**\n{current_about}\n\nأرسل النص الجديد:")
        context.user_data['editing_about'] = True
    
    elif text == "📞 تعديل اتصل بنا":
        current_contact = db.get_setting('contact_text') or '📞 للتواصل: @username'
        await update.message.reply_text(f"📞 **النص الحالي:**\n{current_contact}\n\nأرسل النص الجديد:")
        context.user_data['editing_contact'] = True
    
    elif text == "📋 تعديل قالب الإشعارات":
        current_template = db.get_setting('broadcast_template') or '📢 إشعار من الإدارة:\n\n{message}'
        await update.message.reply_text(
            f"📢 **القالب الحالي:**\n{current_template}\n\n"
            f"أرسل القالب الجديد (يجب أن يحتوي على {message} مكان النص):\n\n"
            f"**مثال:**\n🎊 إشعار خاص 🎊\n\n{message}\n\nمع التحية\nفريق البوت"
        )
        context.user_data['editing_broadcast_template'] = True
    
    elif text == "🔄 تعديل زر البدء":
        current_button = get_start_button_text()
        await update.message.reply_text(f"🔄 **النص الحالي:** {current_button}\n\nأرسل النص الجديد لزر البدء:")
        context.user_data['editing_start_button'] = True
    
    elif text.startswith("🔐 نظام الموافقة:"):
        current_status = approval_required()
        new_status = '0' if current_status else '1'
        db.update_setting('approval_required', new_status)
        status_text = "تعطيل" if current_status else "تفعيل"
        await update.message.reply_text(f"✅ تم {status_text} نظام الموافقة على الطلبات", reply_markup=admin_settings_keyboard())
    
    elif text.startswith("🤖 الموافقة التلقائية:"):
        current_status = auto_approve_enabled()
        new_status = '0' if current_status else '1'
        db.update_setting('auto_approve', new_status)
        status_text = "تعطيل" if current_status else "تفعيل"
        await update.message.reply_text(f"✅ تم {status_text} الموافقة التلقائية", reply_markup=admin_settings_keyboard())
    
    elif text.startswith("💎 النظام المميز:"):
        current_status = premium_enabled()
        new_status = '0' if current_status else '1'
        db.update_setting('premium_enabled', new_status)
        status_text = "تعطيل" if current_status else "تفعيل"
        await update.message.reply_text(f"✅ تم {status_text} النظام المميز", reply_markup=admin_settings_keyboard())
    
    elif text == "📁 عرض كل الإعدادات":
        settings = db.get_all_settings()
        settings_text = "⚙️ **جميع إعدادات البوت:**\n\n"
        for setting in settings:
            settings_text += f"🔧 **{setting[2]}:**\n`{setting[1]}`\n\n"
        await update.message.reply_text(settings_text)
    
    elif text == "⚙️ الإعدادات العامة":
        # عرض الإعدادات الرئيسية
        settings_text = "⚙️ **الإعدادات العامة:**\n\n"
        settings_text += f"🔐 **نظام الموافقة:** {'مفعل ✅' if approval_required() else 'معطل ❌'}\n"
        settings_text += f"🤖 **الموافقة التلقائية:** {'مفعل ✅' if auto_approve_enabled() else 'معطل ❌'}\n"
        settings_text += f"💎 **النظام المميز:** {'مفعل ✅' if premium_enabled() else 'معطل ❌'}\n"
        settings_text += f"🚀 **زر البدء:** {get_start_button_text()}\n"
        settings_text += f"📚 **الحد اليومي:** {db.get_setting('daily_story_limit') or '5'} قصة\n"
        
        await update.message.reply_text(settings_text)

    # === البث الجماعي ===
    elif text == "📢 بث لجميع المستخدمين":
        context.user_data['broadcasting'] = True
        context.user_data['broadcast_target'] = 'all'
        await update.message.reply_text("📢 **البث لجميع المستخدمين**\n\nأرسل الرسالة التي تريد إرسالها:")
    
    elif text == "👥 بث للمستخدمين النشطين":
        context.user_data['broadcasting'] = True
        context.user_data['broadcast_target'] = 'active'
        await update.message.reply_text("👥 **البث للمستخدمين النشطين**\n\nأرسل الرسالة التي تريد إرسالها:")
    
    elif text == "💎 بث للمستخدمين المميزين":
        context.user_data['broadcasting'] = True
        context.user_data['broadcast_target'] = 'premium'
        await update.message.reply_text("💎 **البث للمستخدمين المميزين**\n\nأرسل الرسالة التي تريد إرسالها:")
    
    elif text == "🆕 بث للقادمين الجدد":
        context.user_data['broadcasting'] = True
        context.user_data['broadcast_target'] = 'new'
        await update.message.reply_text("🆕 **البث للقادمين الجدد**\n\nأرسل الرسالة التي تريد إرسالها:")

    # ... (يتبع باقي الأوامر في الرد التالي)

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
    application.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO | filters.AUDIO, handle_media))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت الاحترافي مع المميزات المتقدمة...")
    application.run_polling()

if __name__ == '__main__':
    main()

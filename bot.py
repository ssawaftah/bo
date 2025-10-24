import os
import logging
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """مدير قاعدة البيانات مع أفضل الممارسات"""
    
    def __init__(self):
        self.conn = sqlite3.connect('stories_bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._create_default_data()

    def _create_tables(self):
        """إنشاء الجداول مع العلاقات"""
        tables = [
            # المستخدمون
            '''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT DEFAULT 'ar',
                is_approved INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                daily_stories_read INTEGER DEFAULT 0,
                last_story_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # الأقسام
            '''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                icon TEXT,
                color TEXT DEFAULT '#3498db',
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                story_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # القصص
            '''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                content_type TEXT DEFAULT 'text',
                file_id TEXT,
                category_id INTEGER NOT NULL,
                author TEXT DEFAULT 'مجهول',
                reading_time INTEGER DEFAULT 5,
                is_featured INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                views_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
            ''',
            # طلبات الانضمام
            '''
            CREATE TABLE IF NOT EXISTS join_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                status TEXT DEFAULT 'pending',
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # الإعدادات
            '''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                data_type TEXT DEFAULT 'text',
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # الإحصائيات
            '''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                new_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                stories_read INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                premium_conversions INTEGER DEFAULT 0
            )
            ''',
            # الجلسات
            '''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                current_category INTEGER,
                current_story INTEGER,
                search_query TEXT,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''',
            # الإعجابات
            '''
            CREATE TABLE IF NOT EXISTS story_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                story_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, story_id)
            )
            '''
        ]
        
        for table in tables:
            self.conn.execute(table)
        self.conn.commit()

    def _create_default_data(self):
        """إنشاء البيانات الافتراضية"""
        # الإعدادات الافتراضية
        default_settings = [
            ('bot_name', 'بوت القصص التفاعلي', 'text', 'اسم البوت'),
            ('welcome_message', '🎭 **مرحباً بك في عالم القصص المثير!**\n\nاستكشف آلاف القصص المتنوعة والمشوقة من مختلف الأنواع والأصناف.', 'text', 'رسالة الترحيب'),
            ('approval_required', '1', 'boolean', 'تفعيل نظام الموافقة'),
            ('auto_approve', '0', 'boolean', 'الموافقة التلقائية'),
            ('premium_enabled', '1', 'boolean', 'تفعيل النظام المميز'),
            ('daily_free_stories', '5', 'number', 'عدد القصص المجانية يومياً'),
            ('welcome_free_stories', '3', 'number', 'قصص ترحيب مجانية'),
            ('about_text', '🤖 **بوت القصص التفاعلي**\n\n• 📚 آلاف القصص المتنوعة\n• 🎭 تجربة قراءة فريدة\n• ⭐ قصص حصرية ومميزة\n• 🔄 تحديث مستمر للمحتوى\n• 💎 نظام عضوية مميزة', 'text', 'نص حول البوت'),
            ('contact_text', '📞 **مركز الدعم والاتصال**\n\n📍 للاستفسارات والدعم:\n✉️ البريد: support@stories.com\n📱 التليجرام: @stories_support\n🌐 الموقع: www.stories.com\n\n⏰ ساعات العمل: 9 ص - 12 م', 'text', 'نص اتصل بنا'),
            ('broadcast_template', '🎊 **إشعار هام** 🎊\n\n{message}\n\nمع خالص التحيات,\nفريق {bot_name} ❤️', 'text', 'قالب البث الجماعي'),
            ('start_button_text', '🚀 ابدأ الرحلة', 'text', 'نص زر البدء'),
            ('premium_price', '9.99', 'text', 'سعر العضوية المميزة'),
            ('premium_features', '📚 وصول غير محدود\n⭐ قصص حصرية\n🚀 أولوية في الخدمة\n🎁 عروض خاصة', 'text', 'مميزات العضوية'),
            ('admin_contact', '@stories_admin', 'text', 'تواصل المدير')
        ]
        
        for key, value, data_type, description in default_settings:
            self.conn.execute('''
                INSERT OR IGNORE INTO bot_settings (key, value, data_type, description)
                VALUES (?, ?, ?, ?)
            ''', (key, value, data_type, description))
        
        # الأقسام الافتراضية
        default_categories = [
            ('📚 قصص رعب', 'قصص مرعبة تثير الرعب في النفوس', '👻', '#8e44ad'),
            ('💖 قصص رومانسية', 'قصص حب وعاطفة مؤثرة', '❤️', '#e74c3c'),
            ('🚀 قصص خيال علمي', 'رحلات في عالم المستقبل والتكنولوجيا', '🛸', '#3498db'),
            ('😂 قصص كوميدية', 'قصص مضحكة ومسلية', '😄', '#f39c12'),
            ('🔍 قصص غامضة', 'ألغاز وحقائق غامضة', '🕵️', '#2c3e50'),
            ('🏰 قصص تاريخية', 'أحداث من صفحات التاريخ', '🏛️', '#d35400'),
            ('🧙 قصص خيال', 'عوالم سحرية وخيالية', '✨', '#9b59b6'),
            ('👨‍👩‍👧‍👦 قصص عائلية', 'قصص عن العلاقات الأسرية', '🏠', '#27ae60')
        ]
        
        for name, description, icon, color in default_categories:
            self.conn.execute('''
                INSERT OR IGNORE INTO categories (name, description, icon, color)
                VALUES (?, ?, ?, ?)
            ''', (name, description, icon, color))
        
        self.conn.commit()

    def get_setting(self, key: str, default=None):
        """الحصول على إعداد"""
        cursor = self.conn.execute('SELECT value, data_type FROM bot_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        if result:
            value, data_type = result
            if data_type == 'boolean':
                return value == '1'
            elif data_type == 'number':
                return int(value)
            return value
        return default

    def update_setting(self, key: str, value: str):
        """تحديث إعداد"""
        self.conn.execute('''
            UPDATE bot_settings SET value = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE key = ?
        ''', (str(value), key))
        self.conn.commit()

    def get_all_settings(self):
        """الحصول على كل الإعدادات"""
        cursor = self.conn.execute('SELECT * FROM bot_settings ORDER BY key')
        return [dict(row) for row in cursor.fetchall()]

# إنشاء مدير قاعدة البيانات
db = DatabaseManager()

class UserManager:
    """مدير المستخدمين"""
    
    @staticmethod
    def create_or_update_user(user_id: int, username: str, first_name: str, last_name: str = ""):
        """إنشاء أو تحديث مستخدم"""
        db.conn.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, last_active) 
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, last_name))
        db.conn.commit()

    @staticmethod
    def get_user(user_id: int):
        """الحصول على بيانات مستخدم"""
        cursor = db.conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return dict(result) if result else None

    @staticmethod
    def approve_user(user_id: int):
        """الموافقة على مستخدم"""
        db.conn.execute('''
            UPDATE users SET is_approved = 1 WHERE user_id = ?
        ''', (user_id,))
        db.conn.execute('''
            DELETE FROM join_requests WHERE user_id = ?
        ''', (user_id,))
        db.conn.commit()

    @staticmethod
    def get_user_stats(user_id: int):
        """إحصائيات المستخدم"""
        user = UserManager.get_user(user_id)
        if not user:
            return None
            
        # التحقق من إعادة تعيين القصص اليومية
        last_reset = datetime.fromisoformat(user['last_story_reset'])
        if datetime.now().date() > last_reset.date():
            db.conn.execute('''
                UPDATE users SET daily_stories_read = 0, last_story_reset = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (user_id,))
            db.conn.commit()
        
        cursor = db.conn.execute('''
            SELECT COUNT(*) as total_likes FROM story_likes WHERE user_id = ?
        ''', (user_id,))
        likes = cursor.fetchone()[0]
        
        return {
            'stories_read_today': user['daily_stories_read'],
            'daily_limit': db.get_setting('daily_free_stories', 5),
            'total_likes': likes,
            'is_premium': user['is_premium'],
            'joined_date': user['created_at']
        }

class StoryManager:
    """مدير القصص"""
    
    @staticmethod
    def get_categories():
        """الحصول على الأقسام"""
        cursor = db.conn.execute('''
            SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order, name
        ''')
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_stories_by_category(category_id: int, user_is_premium: bool = False):
        """الحصول على قصص قسم معين"""
        query = '''
            SELECT * FROM stories 
            WHERE category_id = ? AND is_active = 1
        '''
        if not user_is_premium:
            query += ' AND is_premium = 0'
        
        query += ' ORDER BY is_featured DESC, created_at DESC'
        
        cursor = db.conn.execute(query, (category_id,))
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_featured_stories(limit: int = 10):
        """الحصول على القصص المميزة"""
        cursor = db.conn.execute('''
            SELECT s.*, c.name as category_name, c.icon as category_icon
            FROM stories s 
            JOIN categories c ON s.category_id = c.id
            WHERE s.is_featured = 1 AND s.is_active = 1
            ORDER BY s.created_at DESC LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def increment_views(story_id: int):
        """زيادة مشاهدات القصة"""
        db.conn.execute('''
            UPDATE stories SET views_count = views_count + 1 
            WHERE id = ?
        ''', (story_id,))
        db.conn.commit()

    @staticmethod
    def toggle_like(story_id: int, user_id: int):
        """تبديل الإعجاب"""
        try:
            db.conn.execute('''
                INSERT INTO story_likes (user_id, story_id) VALUES (?, ?)
            ''', (user_id, story_id))
            db.conn.execute('''
                UPDATE stories SET likes_count = likes_count + 1 WHERE id = ?
            ''', (story_id,))
        except sqlite3.IntegrityError:
            # الإعجاب موجود بالفعل، نقوم بإزالته
            db.conn.execute('DELETE FROM story_likes WHERE user_id = ? AND story_id = ?', (user_id, story_id))
            db.conn.execute('''
                UPDATE stories SET likes_count = likes_count - 1 WHERE id = ?
            ''', (story_id,))
        db.conn.commit()

class KeyboardManager:
    """مدير لوحات المفاتيح"""
    
    @staticmethod
    def user_main_menu(user_stats: dict = None):
        """القائمة الرئيسية للمستخدم"""
        keyboard = [
            [KeyboardButton("📚 اكتشف القصص"), KeyboardButton("⭐ المميزة")],
            [KeyboardButton("🔥 الأكثر شيوعاً"), KeyboardButton("🔍 البحث")],
        ]
        
        if user_stats and not user_stats['is_premium'] and db.get_setting('premium_enabled'):
            keyboard.append([KeyboardButton("💎 ترقية إلى مميز")])
        
        keyboard.extend([
            [KeyboardButton("👤 الملف الشخصي"), KeyboardButton("⚙️ الإعدادات")],
            [KeyboardButton("ℹ️ حول البوت"), KeyboardButton("📞 اتصل بنا")]
        ])
        
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    @staticmethod
    def user_categories_menu():
        """قائمة الأقسام"""
        categories = StoryManager.get_categories()
        keyboard = []
        
        for i in range(0, len(categories), 2):
            row = categories[i:i+2]
            keyboard.append([KeyboardButton(f"{cat['icon']} {cat['name']}") for cat in row])
        
        keyboard.append([KeyboardButton("🏠 الرئيسية"), KeyboardButton("⭐ المميزة")])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    @staticmethod
    def admin_main_menu():
        """القائمة الرئيسية للمدير"""
        keyboard = [
            [KeyboardButton("👥 إدارة المستخدمين"), KeyboardButton("📁 إدارة الأقسام")],
            [KeyboardButton("📖 إدارة القصص"), KeyboardButton("⭐ النظام المميز")],
            [KeyboardButton("📊 الإحصائيات المتقدمة"), KeyboardButton("⚙️ الإعدادات المتقدمة")],
            [KeyboardButton("📢 البث الجماعي"), KeyboardButton("🔍 التقارير")],
            [KeyboardButton("🔄 تحديث النظام"), KeyboardButton("🔙 وضع المستخدم")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    @staticmethod
    def admin_settings_menu():
        """قائمة إعدادات المدير"""
        approval_status = "✅ مفعل" if db.get_setting('approval_required') else "❌ معطل"
        auto_approve_status = "✅ مفعل" if db.get_setting('auto_approve') else "❌ معطل"
        premium_status = "✅ مفعل" if db.get_setting('premium_enabled') else "❌ معطل"
        
        keyboard = [
            [KeyboardButton("✏️ رسالة الترحيب"), KeyboardButton("📝 حول البوت")],
            [KeyboardButton("📞 اتصل بنا"), KeyboardButton("📢 قالب الإشعارات")],
            [KeyboardButton("🔄 زر البدء"), KeyboardButton("💎 إعدادات المميز")],
            [KeyboardButton(f"🔐 الموافقة: {approval_status}"), KeyboardButton(f"🤖 تلقائي: {auto_approve_status}")],
            [KeyboardButton(f"⭐ مميز: {premium_status}"), KeyboardButton("📋 كل الإعدادات")],
            [KeyboardButton("🔙 لوحة التحكم")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

class MessageHandler:
    """معالج الرسائل المركزي"""
    
    @staticmethod
    async def send_welcome_message(update: Update, context: CallbackContext, user_id: int):
        """إرسال رسالة ترحيب"""
        user = UserManager.get_user(user_id)
        welcome_message = db.get_setting('welcome_message')
        
        if user and user['is_premium']:
            welcome_message += "\n\n👑 **أنت عضو مميز!** استمتع بمزايا العضوية الحصرية."
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=KeyboardManager.user_main_menu(UserManager.get_user_stats(user_id)),
            parse_mode='Markdown'
        )

    @staticmethod
    async def send_story(update: Update, context: CallbackContext, story: dict, user_id: int):
        """إرسال قصة"""
        # زيادة العداد اليومي
        db.conn.execute('''
            UPDATE users SET daily_stories_read = daily_stories_read + 1 
            WHERE user_id = ?
        ''', (user_id,))
        db.conn.commit()
        
        # زيادة المشاهدات
        StoryManager.increment_views(story['id'])
        
        # بناء نص القصة
        story_text = f"📖 **{story['title']}**\n\n"
        if story['summary']:
            story_text += f"*{story['summary']}*\n\n"
        
        story_text += f"{story['content']}\n\n"
        story_text += f"---\n"
        story_text += f"👤 المؤلف: {story['author']}\n"
        story_text += f"⏰ وقت القراءة: {story['reading_time']} دقائق\n"
        story_text += f"👁️ المشاهدات: {story['views_count'] + 1}\n"
        story_text += f"❤️ الإعجابات: {story['likes_count']}\n"
        
        # أزرار التفاعل
        keyboard = [
            [
                InlineKeyboardButton("❤️ أعجبني", callback_data=f"like_{story['id']}"),
                InlineKeyboardButton("📤 مشاركة", callback_data=f"share_{story['id']}")
            ],
            [InlineKeyboardButton("📖 قصة أخرى", callback_data="another_story")]
        ]
        
        await update.message.reply_text(
            story_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# الكود الرئيسي للمعالجات
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    # تنظيف البيانات المؤقتة
    context.user_data.clear()
    
    # تحديث بيانات المستخدم
    UserManager.create_or_update_user(user_id, user.username, user.first_name, user.last_name)
    
    # إذا كان المدير
    if user_id == int(os.getenv('ADMIN_ID', 123456789)):
        db.conn.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, is_approved, is_admin, is_premium)
            VALUES (?, ?, ?, ?, 1, 1, 1)
        ''', (user_id, user.username, user.first_name, user.last_name))
        db.conn.commit()
        
        await update.message.reply_text(
            "👑 **مرحباً بك آلة المدير!**\n\n"
            "لوحة التحكم المتكاملة جاهزة للاستخدام.",
            reply_markup=KeyboardManager.admin_main_menu()
        )
        return
    
    user_data = UserManager.get_user(user_id)
    
    # إذا كان المستخدم معتمداً
    if user_data and user_data['is_approved']:
        await MessageHandler.send_welcome_message(update, context, user_id)
        return
    
    # نظام الموافقة
    if db.get_setting('approval_required'):
        # إرسال طلب انضمام للمدير
        admin_id = int(os.getenv('ADMIN_ID', 123456789))
        
        keyboard = [
            [
                InlineKeyboardButton("✅ الموافقة", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}"),
                InlineKeyboardButton("💎 مميز مباشرة", callback_data=f"premium_{user_id}")
            ]
        ]
        
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 **طلب انضمام جديد**\n\n"
                     f"👤 **المستخدم:** {user.first_name} {user.last_name or ''}\n"
                     f"📱 **Username:** @{user.username or 'لا يوجد'}\n"
                     f"🆔 **ID:** {user_id}\n"
                     f"🌐 **اللغة:** {user.language_code or 'غير معروفة'}\n"
                     f"🕒 **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة للمدير: {e}")
        
        await update.message.reply_text(
            "📋 **تم إرسال طلب انضمامك**\n\n"
            "جاري مراجعة طلبك من قبل الإدارة...\n"
            "ستصلك رسالة تأكيد عند الموافقة.\n\n"
            "شكراً لصبرك! ⏳",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔄 تحديث الحالة")]], resize_keyboard=True)
        )
    else:
        # الموافقة التلقائية
        UserManager.approve_user(user_id)
        await MessageHandler.send_welcome_message(update, context, user_id)

async def handle_admin_callback(update: Update, context: CallbackContext) -> None:
    """معالجة actions المدير"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    # التحقق من صلاحية المدير
    if user_id != int(os.getenv('ADMIN_ID', 123456789)):
        await query.edit_message_text("❌ ليس لديك صلاحية لهذا الإجراء.")
        return
    
    if data.startswith('approve_'):
        target_user_id = int(data.split('_')[1])
        UserManager.approve_user(target_user_id)
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 **تمت الموافقة على طلبك!**\n\nمرحباً بك في عالم القصص المثير!",
                reply_markup=KeyboardManager.user_main_menu()
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
        
        await query.edit_message_text(f"✅ تمت الموافقة على المستخدم {target_user_id}")
    
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        db.conn.execute('DELETE FROM join_requests WHERE user_id = ?', (target_user_id,))
        db.conn.commit()
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")
    
    elif data.startswith('premium_'):
        target_user_id = int(data.split('_')[1])
        UserManager.approve_user(target_user_id)
        db.conn.execute('UPDATE users SET is_premium = 1 WHERE user_id = ?', (target_user_id,))
        db.conn.commit()
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 **تمت الموافقة على طلبك!**\n\n👑 **تم ترقيتك إلى عضوية مميزة!**\nاستمتع بجميع المزايا الحصرية.",
                reply_markup=KeyboardManager.user_main_menu()
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للمستخدم: {e}")
        
        await query.edit_message_text(f"💎 تمت الموافقة وترقية المستخدم {target_user_id} إلى مميز")

async def handle_user_message(update: Update, context: CallbackContext) -> None:
    """معالجة رسائل المستخدمين"""
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    # إذا كان المدير
    if user_id == int(os.getenv('ADMIN_ID', 123456789)):
        await handle_admin_message(update, context)
        return
    
    user_data = UserManager.get_user(user_id)
    
    # إذا لم يكن المستخدم معتمداً
    if not user_data or not user_data['is_approved']:
        if text == "🔄 تحديث الحالة":
            user_data = UserManager.get_user(user_id)
            if user_data and user_data['is_approved']:
                await MessageHandler.send_welcome_message(update, context, user_id)
            else:
                await update.message.reply_text("⏳ لا يزال طلبك قيد المراجعة...")
        else:
            await update.message.reply_text("⏳ لم يتم الموافقة على حسابك بعد.")
        return
    
    # معالجة الأوامر الرئيسية
    if text == "🏠 الرئيسية":
        await update.message.reply_text(
            "🏠 **الصفحة الرئيسية**",
            reply_markup=KeyboardManager.user_main_menu(UserManager.get_user_stats(user_id))
        )
    
    elif text == "📚 اكتشف القصص":
        categories = StoryManager.get_categories()
        if categories:
            await update.message.reply_text(
                "📚 **اختر تصنيف القصص:**\n\nاستكشف عالمنا الرائع من القصص المتنوعة!",
                reply_markup=KeyboardManager.user_categories_menu()
            )
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام متاحة حالياً.")
    
    elif text == "👤 الملف الشخصي":
        stats = UserManager.get_user_stats(user_id)
        if stats:
            profile_text = f"👤 **الملف الشخصي**\n\n"
            profile_text += f"🆔 **رقم العضوية:** {user_id}\n"
            profile_text += f"👤 **الاسم:** {user.first_name}\n"
            profile_text += f"💎 **العضوية:** {'مميز 👑' if stats['is_premium'] else 'عادي ⭐'}\n"
            profile_text += f"📖 **القصص المقروءة اليوم:** {stats['stories_read_today']}/{stats['daily_limit']}\n"
            profile_text += f"❤️ **الإعجابات:** {stats['total_likes']}\n"
            profile_text += f"📅 **تاريخ الانضمام:** {stats['joined_date'][:10]}\n"
            
            await update.message.reply_text(profile_text)
    
    elif text == "ℹ️ حول البوت":
        about_text = db.get_setting('about_text')
        await update.message.reply_text(about_text, parse_mode='Markdown')
    
    elif text == "📞 اتصل بنا":
        contact_text = db.get_setting('contact_text')
        await update.message.reply_text(contact_text, parse_mode='Markdown')
    
    else:
        await update.message.reply_text(
            "❌ **لم أفهم طلبك**\n\nيرجى استخدام الأزرار المتاحة للتنقل.",
            reply_markup=KeyboardManager.user_main_menu(UserManager.get_user_stats(user_id))
        )

async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    """معالجة رسائل المدير"""
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    if text == "🔙 وضع المستخدم":
        await update.message.reply_text(
            "تم التبديل إلى وضع المستخدم",
            reply_markup=KeyboardManager.user_main_menu()
        )
        return
    
    elif text == "👥 إدارة المستخدمين":
        users_count = len(db.conn.execute('SELECT * FROM users WHERE is_approved = 1').fetchall())
        pending_count = len(db.conn.execute('SELECT * FROM join_requests').fetchall())
        premium_count = len(db.conn.execute('SELECT * FROM users WHERE is_premium = 1').fetchall())
        
        stats_text = f"👥 **إدارة المستخدمين**\n\n"
        stats_text += f"📊 **الإحصائيات:**\n"
        stats_text += f"• 👥 المستخدمون: {users_count}\n"
        stats_text += f"• ⏳ في الانتظار: {pending_count}\n"
        stats_text += f"• 💎 المميزون: {premium_count}\n\n"
        stats_text += f"🔧 **الأدوات:**\n"
        stats_text += f"• 📋 عرض المستخدمين\n"
        stats_text += f"• ⏳ طلبات الانضمام\n"
        stats_text += f"• 💎 ترقية مستخدمين\n"
        stats_text += f"• 🗑 حذف مستخدمين"
        
        await update.message.reply_text(stats_text)
    
    elif text == "⚙️ الإعدادات المتقدمة":
        await update.message.reply_text(
            "⚙️ **الإعدادات المتقدمة**\n\nاختر الإعداد الذي تريد تعديله:",
            reply_markup=KeyboardManager.admin_settings_menu()
        )
    
    else:
        await update.message.reply_text(
            "👑 **لوحة تحكم المدير**\n\nاختر من الخيارات المتاحة:",
            reply_markup=KeyboardManager.admin_main_menu()
        )

async def error_handler(update: Update, context: CallbackContext) -> None:
    """معالج الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")

def main():
    """الدالة الرئيسية"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("❌ لم يتم تعيين TELEGRAM_BOT_TOKEN")
    
    application = Application.builder().token(token).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت الاحترافي...")
    application.run_polling()

if __name__ == '__main__':
    main()

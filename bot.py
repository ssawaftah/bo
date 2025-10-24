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

# فئة قاعدة البيانات
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

        # جدول القصص
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
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
        # إضافة المدير الرئيسي (ضع رقمك هنا)
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

    def delete_category(self, category_id):
        self.conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        self.conn.execute('DELETE FROM stories WHERE category_id = ?', (category_id,))
        self.conn.commit()

    # دوال القصص
    def add_story(self, title, content, category_id, created_by):
        self.conn.execute('''
            INSERT INTO stories (title, content, category_id, created_by)
            VALUES (?, ?, ?, ?)
        ''', (title, content, category_id, created_by))
        self.conn.commit()

    def get_stories_by_category(self, category_id):
        cursor = self.conn.execute('SELECT * FROM stories WHERE category_id = ?', (category_id,))
        return cursor.fetchall()

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
        keyboard.append([KeyboardButton(story[1]) for story in row])
    keyboard.append([KeyboardButton("🔙 رجوع")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# لوحات المفاتيح للمدير
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

# دوال المساعدة
def is_admin(user_id):
    user = db.get_user(user_id)
    return user and user[5] == 1  # العمود 5 هو is_admin

def get_category_id_by_name(name):
    categories = db.get_categories()
    for cat in categories:
        if cat[1] == name:
            return cat[0]
    return None

# معالجة الأوامر للمستخدمين
async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    
    # إضافة المستخدم إلى قاعدة البيانات
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    user_data = db.get_user(user_id)
    
    if user_data and user_data[4] == 1:  # إذا كان مفعل
        if is_admin(user_id):
            await update.message.reply_text(
                f"مرحباً kembali آلة المدير {user.first_name}! 👑",
                reply_markup=admin_main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"مرحباً kembali {user.first_name}! 👋",
                reply_markup=main_keyboard()
            )
    else:
        # إرسال طلب انضمام للمدير
        admin_id = int(os.getenv('ADMIN_ID', 123456789))
        
        # حفظ طلب الانضمام
        db.conn.execute('''
            INSERT OR REPLACE INTO join_requests (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, user.username, user.first_name, user.last_name))
        db.conn.commit()
        
        # إرسال رسالة للمدير
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
        except:
            pass
        
        await update.message.reply_text(
            "📋 تم إرسال طلب انضمامك إلى المدير. ستصلك رسالة تأكيد عند الموافقة على طلبك."
        )

# معالجة ضغطات الأزرار للمدير
async def handle_admin_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("❌ ليس لديك صلاحية للقيام بهذا الإجراء.")
        return
    
    if data.startswith('approve_'):
        target_user_id = int(data.split('_')[1])
        db.approve_user(target_user_id)
        
        # إرسال رسالة للمستخدم المعتمد
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 تمت الموافقة على طلب انضمامك!\n\nانقر على الزر أدناه لبدء الاستخدام:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🚀 بدء الاستخدام")]], resize_keyboard=True)
            )
        except:
            pass
        
        await query.edit_message_text(f"✅ تمت الموافقة على المستخدم {target_user_id}")
        
    elif data.startswith('reject_'):
        target_user_id = int(data.split('_')[1])
        db.reject_user(target_user_id)
        await query.edit_message_text(f"❌ تم رفض طلب المستخدم {target_user_id}")

# معالجة الرسائل للمستخدمين
async def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    user_data = db.get_user(user_id)
    if not user_data or user_data[4] == 0:
        if text == "🚀 بدء الاستخدام":
            db.approve_user(user_id)
            if is_admin(user_id):
                await update.message.reply_text("مرحباً آلة المدير! 👑", reply_markup=admin_main_keyboard())
            else:
                await update.message.reply_text("أهلاً وسهلاً! 🌟", reply_markup=main_keyboard())
        return
    
    # إذا كان مديراً
    if is_admin(user_id):
        await handle_admin_message(update, context)
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
        
        # البحث في القصص
        all_stories = db.get_all_stories()
        for story in all_stories:
            if story[1] == text:  # title
                await update.message.reply_text(f"📖 {text}\n\n{story[2]}\n\n---\nنهاية القصة 📚")
                return
        
        await update.message.reply_text("⚠️ لم أفهم طلبك.", reply_markup=main_keyboard())

# معالجة رسائل المدير
async def handle_admin_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    
    # الأوامر الرئيسية للمدير
    if text == "🔙 وضع المستخدم":
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
    
    # إدارة المستخدمين
    elif text == "📋 عرض المستخدمين":
        users = db.get_all_users()
        if users:
            users_text = "👥 قائمة المستخدمين:\n\n"
            for user_data in users:
                users_text += f"🆔 {user_data[0]} - 👤 {user_data[2]} - 📱 @{user_data[1] or 'لا يوجد'}\n"
            await update.message.reply_text(users_text)
        else:
            await update.message.reply_text("⚠️ لا يوجد مستخدمين.")
    
    elif text == "⏳ طلبات الانضمام":
        requests = db.get_pending_requests()
        if requests:
            req_text = "📩 طلبات الانضمام pending:\n\n"
            for req in requests:
                req_text += f"🆔 {req[0]} - 👤 {req[2]} - 📱 @{req[1] or 'لا يوجد'}\n"
            await update.message.reply_text(req_text)
        else:
            await update.message.reply_text("✅ لا توجد طلبات انضمام pending.")
    
    elif text == "🗑 حذف مستخدم":
        await update.message.reply_text("أرسل رقم ID المستخدم الذي تريد حذفه:")
        context.user_data['awaiting_user_id'] = True
    
    # إدارة الأقسام
    elif text == "📋 عرض الأقسام":
        categories = db.get_categories()
        if categories:
            cats_text = "📁 الأقسام المتاحة:\n\n"
            for cat in categories:
                cats_text += f"📂 {cat[1]} (ID: {cat[0]})\n"
            await update.message.reply_text(cats_text)
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    elif text == "➕ إضافة قسم":
        await update.message.reply_text("أرسل اسم القسم الجديد:")
        context.user_data['awaiting_category'] = True
    
    elif text == "🗑 حذف قسم":
        categories = db.get_categories()
        if categories:
            keyboard = []
            for cat in categories:
                keyboard.append([KeyboardButton(f"حذف قسم: {cat[1]}")])
            keyboard.append([KeyboardButton("🔙 لوحة التحكم")])
            await update.message.reply_text("اختر القسم للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد أقسام.")
    
    # إدارة القصص
    elif text == "📋 عرض القصص":
        stories = db.get_all_stories()
        if stories:
            stories_text = "📖 جميع القصص:\n\n"
            for story in stories:
                stories_text += f"📚 {story[1]} - 📂 {story[5]}\n"
            await update.message.reply_text(stories_text)
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    elif text == "➕ إضافة قصة":
        await update.message.reply_text("لإضافة قصة جديدة، أرسل الرسالة بالتنسيق التالي:\n\nإضافة قصة:\nالقسم: اسم القسم\nالعنوان: عنوان القصة\nالمحتوى: محتوى القصة هنا")
    
    elif text == "🗑 حذف قصة":
        stories = db.get_all_stories()
        if stories:
            keyboard = []
            for story in stories:
                keyboard.append([KeyboardButton(f"حذف قصة: {story[1]}")])
            keyboard.append([KeyboardButton("🔙 لوحة التحكم")])
            await update.message.reply_text("اختر القصة للحذف:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        else:
            await update.message.reply_text("⚠️ لا توجد قصص.")
    
    elif text == "📢 إرسال إشعار":
        await update.message.reply_text("أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
        context.user_data['awaiting_broadcast'] = True
    
    elif text == "📊 إحصائيات":
        users_count = len(db.get_all_users())
        categories_count = len(db.get_categories())
        stories_count = len(db.get_all_stories())
        pending_count = len(db.get_pending_requests())
        
        stats_text = f"""
📊 إحصائيات البوت:

👥 عدد المستخدمين: {users_count}
⏳ طلبات pending: {pending_count}
📁 عدد الأقسام: {categories_count}
📖 عدد القصص: {stories_count}
        """
        await update.message.reply_text(stats_text)
    
    # معالجة الإدخالات النصية للمدير
    elif context.user_data.get('awaiting_user_id'):
        try:
            target_user_id = int(text)
            db.delete_user(target_user_id)
            await update.message.reply_text(f"✅ تم حذف المستخدم {target_user_id}")
            context.user_data['awaiting_user_id'] = False
        except:
            await update.message.reply_text("❌ رقم ID غير صحيح")
    
    elif context.user_data.get('awaiting_category'):
        db.add_category(text, user_id)
        await update.message.reply_text(f"✅ تم إضافة القسم: {text}")
        context.user_data['awaiting_category'] = False
    
    elif context.user_data.get('awaiting_broadcast'):
        users = db.get_all_users()
        success = 0
        for user_data in users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=f"📢 إشعار من الإدارة:\n\n{text}")
                success += 1
            except:
                continue
        await update.message.reply_text(f"✅ تم إرسال الإشعار إلى {success} مستخدم")
        context.user_data['awaiting_broadcast'] = False
    
    elif text.startswith("حذف قسم: "):
        category_name = text.replace("حذف قسم: ", "")
        category_id = get_category_id_by_name(category_name)
        if category_id:
            db.delete_category(category_id)
            await update.message.reply_text(f"✅ تم حذف القسم: {category_name}")
        else:
            await update.message.reply_text("❌ قسم غير موجود")
    
    elif text.startswith("حذف قصة: "):
        story_title = text.replace("حذف قصة: ", "")
        stories = db.get_all_stories()
        for story in stories:
            if story[1] == story_title:
                db.delete_story(story[0])
                await update.message.reply_text(f"✅ تم حذف القصة: {story_title}")
                return
        await update.message.reply_text("❌ قصة غير موجودة")
    
    elif text.startswith("إضافة قصة:"):
        try:
            lines = text.split('\n')
            category_name = lines[1].replace('القسم:', '').strip()
            title = lines[2].replace('العنوان:', '').strip()
            content = lines[3].replace('المحتوى:', '').strip()
            
            category_id = get_category_id_by_name(category_name)
            if category_id:
                db.add_story(title, content, category_id, user_id)
                await update.message.reply_text(f"✅ تم إضافة القصة: {title}")
            else:
                await update.message.reply_text("❌ قسم غير موجود")
        except:
            await update.message.reply_text("❌ تنسيق غير صحيح")
    
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
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 بدء تشغيل البوت الاحترافي...")
    application.run_polling()

if __name__ == '__main__':
    main()

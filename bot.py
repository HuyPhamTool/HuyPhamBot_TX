import os
import hashlib
import random
import time
import re
import logging
import uuid
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import pickle
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import sqlite3
from datetime import datetime, timedelta

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Token bot Telegram
TOKEN = "7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8"

# Danh sách admin
ADMIN_IDS = [7505331567]

# Đường dẫn lưu mô hình ML
MODEL_PATH = "taixiu_model.pkl"

# Kết nối database
def get_db_connection():
    conn = sqlite3.connect('md5_bot.db')
    conn.row_factory = sqlite3.Row
    return conn

# Khởi tạo database
def init_db():
    conn = get_db_connection()
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS md5_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        md5_hash TEXT NOT NULL,
        original_value TEXT,
        result TEXT,
        prediction TEXT,
        prediction_correct INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS md5_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern TEXT NOT NULL,
        tai_count INTEGER DEFAULT 0,
        xiu_count INTEGER DEFAULT 0,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS license_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_code TEXT NOT NULL UNIQUE,
        created_by INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        valid_until DATETIME NOT NULL,
        max_activations INTEGER DEFAULT 1,
        current_activations INTEGER DEFAULT 0,
        notes TEXT
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 0,
        active_key TEXT,
        subscription_end DATETIME,
        last_activity DATETIME
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS key_usage_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_code TEXT NOT NULL,
        telegram_id INTEGER NOT NULL,
        activated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        valid_until DATETIME NOT NULL,
        FOREIGN KEY (key_code) REFERENCES license_keys (key_code),
        FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Kiểm tra thời hạn người dùng
def check_user_subscription(telegram_id):
    conn = get_db_connection()
    cursor = conn.execute('SELECT subscription_end, is_active FROM users WHERE telegram_id = ?', (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return False, "Bạn chưa đăng ký. Sử dụng /register để đăng ký và /activate để kích hoạt key."
    
    if not row['is_active']:
        return False, "Tài khoản của bạn chưa được kích hoạt. Sử dụng /activate để kích hoạt key."
    
    subscription_end = datetime.strptime(row['subscription_end'], '%Y-%m-%d %H:%M:%S')
    if subscription_end < datetime.now():
        conn = get_db_connection()
        conn.execute('UPDATE users SET is_active = 0 WHERE telegram_id = ?', (telegram_id,))
        conn.commit()
        conn.close()
        return False, "Key của bạn đã hết hạn. Vui lòng sử dụng /activate với key mới."
    
    conn = get_db_connection()
    conn.execute('UPDATE users SET last_activity = ? WHERE telegram_id = ?', (datetime.now(), telegram_id))
    conn.commit()
    conn.close()
    
    return True, f"Key còn hiệu lực đến: {subscription_end.strftime('%d/%m/%Y %H:%M')}"

# Kiểm tra admin
def is_admin(telegram_id):
    return telegram_id in ADMIN_IDS

# Đăng ký người dùng
async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        conn.close()
        await update.message.reply_text("Bạn đã đăng ký rồi. Sử dụng /activate để kích hoạt key hoặc /status để kiểm tra trạng thái.")
        return
    
    conn.execute(
        'INSERT INTO users (telegram_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
        (telegram_id, username, first_name, last_name)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"Đăng ký thành công!\n\n"
        f"Telegram ID: {telegram_id}\n"
        f"Username: {username or 'Không có'}\n\n"
        f"Để sử dụng bot, bạn cần kích hoạt key. Sử dụng lệnh:\n"
        f"/activate YOUR_KEY_CODE"
    )

# Kích hoạt key
async def activate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Vui lòng nhập key. Ví dụ: /activate YOUR_KEY_CODE")
        return
    
    key_code = context.args[0].strip()
    telegram_id = update.effective_user.id
    
    conn = get_db_connection()
    
    cursor = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        await update.message.reply_text("Bạn chưa đăng ký. Vui lòng sử dụng lệnh /register trước.")
        return
    
    cursor = conn.execute('SELECT * FROM license_keys WHERE key_code = ?', (key_code,))
    key = cursor.fetchone()
    
    if not key:
        conn.close()
        await update.message.reply_text("❌ Key không hợp lệ. Vui lòng kiểm tra lại hoặc liên hệ admin.")
        return
    
    if key['current_activations'] >= key['max_activations']:
        conn.close()
        await update.message.reply_text("❌ Key này đã đạt số lượng kích hoạt tối đa. Vui lòng liên hệ admin.")
        return
    
    valid_until = datetime.strptime(key['valid_until'], '%Y-%m-%d %H:%M:%S')
    if valid_until < datetime.now():
        conn.close()
        await update.message.reply_text("❌ Key này đã hết hạn. Vui lòng liên hệ admin để nhận key mới.")
        return
    
    cursor = conn.execute('SELECT * FROM key_usage_history WHERE key_code = ? AND telegram_id = ?', (key_code, telegram_id))
    usage = cursor.fetchone()
    
    if usage:
        conn.close()
        await update.message.reply_text("❌ Bạn đã sử dụng key này trước đó. Mỗi key chỉ có thể sử dụng một lần cho mỗi người dùng.")
        return
    
    conn.execute(
        'UPDATE users SET is_active = 1, active_key = ?, subscription_end = ? WHERE telegram_id = ?',
        (key_code, valid_until, telegram_id)
    )
    
    conn.execute(
        'UPDATE license_keys SET current_activations = current_activations + 1 WHERE key_code = ?',
        (key_code,)
    )
    
    conn.execute(
        'INSERT INTO key_usage_history (key_code, telegram_id, valid_until) VALUES (?, ?, ?)',
        (key_code, telegram_id, valid_until)
    )
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Kích hoạt key thành công!\n\n"
        f"Key: {key_code}\n"
        f"Có hiệu lực đến: {valid_until.strftime('%d/%m/%Y %H:%M')}\n\n"
        f"Bây giờ bạn có thể sử dụng bot. Thử sử dụng lệnh /analyze để phân tích mã MD5."
    )

# Trạng thái người dùng
async def user_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await update.message.reply_text("Bạn chưa đăng ký. Vui lòng sử dụng lệnh /register trước.")
        return
    
    status = "✅ Đã kích hoạt" if user['is_active'] else "❌ Chưa kích hoạt"
    subscription_end = datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S') if user['subscription_end'] else None
    
    subscription_info = ""
    if subscription_end:
        if subscription_end > datetime.now():
            days_left = (subscription_end - datetime.now()).days
            hours_left = ((subscription_end - datetime.now()).seconds // 3600)
            subscription_info = f"Còn lại: {days_left} ngày {hours_left} giờ"
        else:
            subscription_info = "Đã hết hạn"
    
    await update.message.reply_text(
        f"*Thông tin tài khoản của bạn:*\n\n"
        f"ID: `{telegram_id}`\n"
        f"Username: @{user['username'] if user['username'] else 'Không có'}\n"
        f"Trạng thái: {status}\n"
        f"Key đang dùng: `{user['active_key'] if user['active_key'] else 'Không có'}`\n"
        f"Ngày hết hạn: {subscription_end.strftime('%d/%m/%Y %H:%M') if subscription_end else 'Không có'}\n"
        f"{subscription_info}\n\n"
        f"Để kích hoạt key mới, sử dụng: /activate YOUR_KEY_CODE",
        parse_mode='Markdown'
    )

# --- CHỨC NĂNG QUẢN LÝ KEY CHO ADMIN ---

async def create_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Vui lòng sử dụng đúng cú pháp:\n"
            "/create_key [số_ngày] [số_lần_kích_hoạt] [ghi_chú]\n\n"
            "Ví dụ: /create_key 7 1 VIP user"
        )
        return
    
    try:
        days = int(context.args[0])
        max_activations = int(context.args[1])
        notes = " ".join(context.args[2:]) if len(context.args) > 2 else "N/A"
        
        key_code = str(uuid.uuid4()).replace("-", "")[:16].upper()
        valid_until = datetime.now() + timedelta(days=days)
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO license_keys (key_code, created_by, valid_until, max_activations, notes) VALUES (?, ?, ?, ?, ?)',
            (key_code, telegram_id, valid_until, max_activations, notes)
        )
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Đã tạo key thành công!\n\n"
            f"📌 *Key:* `{key_code}`\n"
            f"⏳ Thời hạn: {days} ngày\n"
            f"🔄 Số lần kích hoạt tối đa: {max_activations}\n"
            f"📝 Ghi chú: {notes}\n"
            f"📅 Hết hạn: {valid_until.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Người dùng có thể kích hoạt key này bằng lệnh:\n"
            f"`/activate {key_code}`",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Số ngày và số lần kích hoạt phải là số. Vui lòng thử lại.")

async def create_multiple_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "Vui lòng sử dụng đúng cú pháp:\n"
            "/create_keys [số_lượng] [số_ngày] [số_lần_kích_hoạt] [ghi_chú]\n\n"
            "Ví dụ: /create_keys 5 7 1 Batch VIP keys"
        )
        return
    
    try:
        count = int(context.args[0])
        days = int(context.args[1])
        max_activations = int(context.args[2])
        notes = " ".join(context.args[3:]) if len(context.args) > 3 else "Batch generated"
        
        if count > 20:
            await update.message.reply_text("❌ Số lượng key tối đa có thể tạo cùng lúc là 20.")
            return
        
        keys = []
        valid_until = datetime.now() + timedelta(days=days)
        
        conn = get_db_connection()
        for _ in range(count):
            key_code = str(uuid.uuid4()).replace("-", "")[:16].upper()
            conn.execute(
                'INSERT INTO license_keys (key_code, created_by, valid_until, max_activations, notes) VALUES (?, ?, ?, ?, ?)',
                (key_code, telegram_id, valid_until, max_activations, notes)
            )
            keys.append(key_code)
        
        conn.commit()
        conn.close()
        
        message = f"✅ Đã tạo {count} key thành công!\n\n"
        message += f"⏳ Thời hạn: {days} ngày\n"
        message += f"🔄 Số lần kích hoạt tối đa: {max_activations}\n"
        message += f"📝 Ghi chú: {notes}\n"
        message += f"📅 Hết hạn: {valid_until.strftime('%d/%m/%Y %H:%M')}\n\n"
        message += "📋 Danh sách key:\n"
        
        for i, key in enumerate(keys, 1):
            message += f"{i}. `{key}`\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Số lượng, số ngày và số lần kích hoạt phải là số. Vui lòng thử lại.")

async def create_key_with_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Vui lòng sử dụng đúng cú pháp:\n"
            "/create_key_hours [số_giờ] [số_lần_kích_hoạt] [ghi_chú]\n\n"
            "Ví dụ: /create_key_hours 24 1 Key 1 ngày"
        )
        return
    
    try:
        hours = int(context.args[0])
        max_activations = int(context.args[1])
        notes = " ".join(context.args[2:]) if len(context.args) > 2 else "Hourly key"
        
        key_code = str(uuid.uuid4()).replace("-", "")[:16].upper()
        valid_until = datetime.now() + timedelta(hours=hours)
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO license_keys (key_code, created_by, valid_until, max_activations, notes) VALUES (?, ?, ?, ?, ?)',
            (key_code, telegram_id, valid_until, max_activations, notes)
        )
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Đã tạo key thành công!\n\n"
            f"📌 *Key:* `{key_code}`\n"
            f"⏳ Thời hạn: {hours} giờ\n"
            f"🔄 Số lần kích hoạt tối đa: {max_activations}\n"
            f"📝 Ghi chú: {notes}\n"
            f"📅 Hết hạn: {valid_until.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Người dùng có thể kích hoạt key này bằng lệnh:\n"
            f"`/activate {key_code}`",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Số giờ và số lần kích hoạt phải là số. Vui lòng thử lại.")

async def list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM license_keys ORDER BY created_at DESC LIMIT 30')
    keys = cursor.fetchall()
    conn.close()
    
    if not keys:
        await update.message.reply_text("📝 Chưa có key nào được tạo.")
        return
    
    message = "📋 *Danh sách 30 key gần đây nhất:*\n\n"
    for key in keys:
        valid_until = datetime.strptime(key['valid_until'], '%Y-%m-%d %H:%M:%S')
        status = "✅ Còn hạn" if valid_until > datetime.now() else "❌ Hết hạn"
        
        message += f"Key: `{key['key_code']}`\n"
        message += f"Trạng thái: {status}\n"
        message += f"Đã kích hoạt: {key['current_activations']}/{key['max_activations']}\n"
        message += f"Hết hạn: {valid_until.strftime('%d/%m/%Y %H:%M')}\n"
        message += f"Ghi chú: {key['notes']}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def key_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Vui lòng nhập key cần kiểm tra. Ví dụ: /key_info YOUR_KEY_CODE")
        return
    
    key_code = context.args[0].strip().upper()
    
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM license_keys WHERE key_code = ?', (key_code,))
    key = cursor.fetchone()
    
    if not key:
        conn.close()
        await update.message.reply_text("❌ Không tìm thấy key này.")
        return
    
    cursor = conn.execute('''
        SELECT u.telegram_id, u.username, u.first_name, u.last_name, k.activated_at
        FROM key_usage_history k
        JOIN users u ON k.telegram_id = u.telegram_id
        WHERE k.key_code = ?
    ''', (key_code,))
    activations = cursor.fetchall()
    conn.close()
    
    valid_until = datetime.strptime(key['valid_until'], '%Y-%m-%d %H:%M:%S')
    status = "✅ Còn hạn" if valid_until > datetime.now() else "❌ Hết hạn"
    
    message = f"🔑 *Thông tin chi tiết key:*\n\n"
    message += f"Key: `{key['key_code']}`\n"
    message += f"Trạng thái: {status}\n"
    message += f"Đã kích hoạt: {key['current_activations']}/{key['max_activations']}\n"
    message += f"Ngày tạo: {datetime.strptime(key['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}\n"
    message += f"Hết hạn: {valid_until.strftime('%d/%m/%Y %H:%M')}\n"
    message += f"Ghi chú: {key['notes']}\n\n"
    
    if activations:
        message += "*Danh sách người dùng đã kích hoạt:*\n"
        for user in activations:
            username = user['username'] if user['username'] else f"{user['first_name']} {user['last_name'] or ''}"
            activated_at = datetime.strptime(user['activated_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
            message += f"- ID: `{user['telegram_id']}` | @{username} | {activated_at}\n"
    else:
        message += "*Chưa có người dùng nào kích hoạt key này.*"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def extend_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Vui lòng sử dụng đúng cú pháp:\n"
            "/extend_key [key_code] [số_ngày]\n\n"
            "Ví dụ: /extend_key ABC123 7"
        )
        return
    
    key_code = context.args[0].strip().upper()
    
    try:
        days = int(context.args[1])
        
        conn = get_db_connection()
        cursor = conn.execute('SELECT * FROM license_keys WHERE key_code = ?', (key_code,))
        key = cursor.fetchone()
        
        if not key:
            conn.close()
            await update.message.reply_text("❌ Không tìm thấy key này.")
            return
        
        current_valid_until = datetime.strptime(key['valid_until'], '%Y-%m-%d %H:%M:%S')
        new_valid_until = current_valid_until + timedelta(days=days)
        
        conn.execute(
            'UPDATE license_keys SET valid_until = ? WHERE key_code = ?',
            (new_valid_until, key_code)
        )
        
        conn.execute(
            'UPDATE users SET subscription_end = ? WHERE active_key = ?',
            (new_valid_until, key_code)
        )
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Đã gia hạn key thành công!\n\n"
            f"Key: `{key_code}`\n"
            f"Thêm: {days} ngày\n"
            f"Hạn mới: {new_valid_until.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Người dùng đang sử dụng key này cũng đã được gia hạn.",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Số ngày phải là số. Vui lòng thử lại.")

async def shorten_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Vui lòng sử dụng đúng cú pháp:\n"
            "/shorten_key [key_code] [số_ngày]\n\n"
            "Ví dụ: /shorten_key ABC123 2"
        )
        return
    
    key_code = context.args[0].strip().upper()
    
    try:
        days = int(context.args[1])
        
        conn = get_db_connection()
        cursor = conn.execute('SELECT * FROM license_keys WHERE key_code = ?', (key_code,))
        key = cursor.fetchone()
        
        if not key:
            conn.close()
            await update.message.reply_text("❌ Không tìm thấy key này.")
            return
        
        current_valid_until = datetime.strptime(key['valid_until'], '%Y-%m-%d %H:%M:%S')
        new_valid_until = current_valid_until - timedelta(days=days)
        
        if new_valid_until < datetime.now():
            new_valid_until = datetime.now()
        
        conn.execute(
            'UPDATE license_keys SET valid_until = ? WHERE key_code = ?',
            (new_valid_until, key_code)
        )
        
        conn.execute(
            'UPDATE users SET subscription_end = ? WHERE active_key = ?',
            (new_valid_until, key_code)
        )
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Đã rút ngắn thời gian key thành công!\n\n"
            f"Key: `{key_code}`\n"
            f"Đã giảm: {days} ngày\n"
            f"Hạn mới: {new_valid_until.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Người dùng đang sử dụng key này cũng đã bị rút ngắn thời gian.",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Số ngày phải là số. Vui lòng thử lại.")

async def delete_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Vui lòng sử dụng đúng cú pháp:\n"
            "/delete_key [key_code]\n\n"
            "Ví dụ: /delete_key ABC123"
        )
        return
    
    key_code = context.args[0].strip().upper()
    
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM license_keys WHERE key_code = ?', (key_code,))
    key = cursor.fetchone()
    
    if not key:
        conn.close()
        await update.message.reply_text("❌ Không tìm thấy key này.")
        return
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM users WHERE active_key = ?', (key_code,))
    active_users_count = cursor.fetchone()['count']
    
    keyboard = [
        [
            InlineKeyboardButton("🗑️ Xác nhận xóa", callback_data=f"delete_key_{key_code}"),
            InlineKeyboardButton("❌ Hủy", callback_data="cancel_delete")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    conn.close()
    
    await update.message.reply_text(
        f"🔴 Bạn có chắc muốn xóa key `{key_code}` không?\n\n"
        f"⚠️ Có {active_users_count} người dùng đang sử dụng key này. "
        f"Nếu xóa, những người dùng này có thể sẽ mất quyền truy cập.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    telegram_id = query.from_user.id
    
    if not is_admin(telegram_id):
        await query.answer("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    await query.answer()
    
    if query.data.startswith("delete_key_"):
        key_code = query.data.replace("delete_key_", "")
        
        conn = get_db_connection()
        conn.execute('UPDATE users SET is_active = 0 WHERE active_key = ?', (key_code,))
        conn.execute('DELETE FROM license_keys WHERE key_code = ?', (key_code,))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ Đã xóa key `{key_code}` thành công!\n\n"
            f"Tất cả người dùng đang sử dụng key này đã bị vô hiệu hóa.",
            parse_mode='Markdown'
        )
    elif query.data == "cancel_delete":
        await query.edit_message_text("❌ Đã hủy thao tác xóa key.")
    elif query.data.startswith("page_"):
        page = int(query.data.replace("page_", ""))
        context.args = [str(page)]
        await list_users(update, context)
    elif query.data.startswith(("reset_user_", "ban_user_", "unban_user_", "add7days_")):
        await user_action_callback(update, context)

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    page = 1
    if context.args and len(context.args) > 0:
        try:
            page = int(context.args[0])
            if page < 1:
                page = 1
        except ValueError:
            pass
    
    limit = 10
    offset = (page - 1) * limit
    
    conn = get_db_connection()
    cursor = conn.execute('''
        SELECT * FROM users
        ORDER BY registered_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    users = cursor.fetchall()
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM users')
    total_users = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1')
    active_users = cursor.fetchone()['count']
    
    conn.close()
    
    total_pages = (total_users + limit - 1) // limit
    
    if not users:
        await update.message.reply_text("📝 Chưa có người dùng nào đăng ký.")
        return
    
    message = f"👥 *Danh sách người dùng (Trang {page}/{total_pages})*\n\n"
    message += f"Tổng số người dùng: {total_users}\n"
    message += f"Người dùng đang hoạt động: {active_users}\n\n"
    
    for i, user in enumerate(users, 1):
        status = "✅ Đang hoạt động" if user['is_active'] else "❌ Không hoạt động"
        username = user['username'] if user['username'] else f"{user['first_name']} {user['last_name'] or ''}"
        subscription_end = datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S') if user['subscription_end'] else None
        
        message += f"{offset + i}. ID: `{user['telegram_id']}` | @{username}\n"
        message += f"   Trạng thái: {status}\n"
        if subscription_end:
            if subscription_end > datetime.now():
                message += f"   Hết hạn: {subscription_end.strftime('%d/%m/%Y %H:%M')}\n"
            else:
                message += f"   Hết hạn: Đã hết\n"
        message += f"   Key: {user['active_key'] or 'Không có'}\n\n"
    
    keyboard = []
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Trang trước", callback_data=f"page_{page-1}"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ Trang sau", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def system_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    conn = get_db_connection()
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM users')
    total_users = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1')
    active_users = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM license_keys')
    total_keys = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM license_keys WHERE valid_until > ?', (datetime.now(),))
    active_keys = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM md5_results')
    total_analysis = cursor.fetchone()['count']
    
    cursor = conn.execute('''
        SELECT COUNT(*) as count FROM md5_results
        WHERE prediction IS NOT NULL AND prediction_correct IS NOT NULL
    ''')
    total_predictions = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM md5_results WHERE prediction_correct = 1')
    correct_predictions = cursor.fetchone()['count']
    
    accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0
    
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM users WHERE registered_at >= ?', (seven_days_ago,))
    new_users = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM license_keys WHERE created_at >= ?', (seven_days_ago,))
    new_keys = cursor.fetchone()['count']
    
    cursor = conn.execute('SELECT COUNT(*) as count FROM md5_results WHERE timestamp >= ?', (seven_days_ago,))
    recent_analysis = cursor.fetchone()['count']
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 *Thống kê hệ thống*\n\n"
        f"👥 *Người dùng:*\n"
        f"- Tổng số: {total_users}\n"
        f"- Đang hoạt động: {active_users}\n"
        f"- Mới (7 ngày): {new_users}\n\n"
        f"🔑 *Key:*\n"
        f"- Tổng số: {total_keys}\n"
        f"- Còn hiệu lực: {active_keys}\n"
        f"- Mới tạo (7 ngày): {new_keys}\n\n"
        f"🔍 *Phân tích MD5:*\n"
        f"- Tổng số: {total_analysis}\n"
        f"- Gần đây (7 ngày): {recent_analysis}\n"
        f"- Dự đoán: {total_predictions}\n"
        f"- Dự đoán đúng: {correct_predictions}\n"
        f"- Độ chính xác: {accuracy:.2f}%",
        parse_mode='Markdown'
    )

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bạn không có quyền thực hiện chức năng này.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Vui lòng nhập ID hoặc username cần tìm.\n"
            "Ví dụ: /search_user 123456789 hoặc /search_user username"
        )
        return
    
    search_term = context.args[0].strip()
    
    conn = get_db_connection()
    
    try:
        search_id = int(search_term)
        cursor = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (search_id,))
    except ValueError:
        cursor = conn.execute('SELECT * FROM users WHERE username LIKE ?', (f"%{search_term}%",))
    
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text(f"❌ Không tìm thấy người dùng nào phù hợp với '{search_term}'.")
        return
    
    for user in users:
        status = "✅ Đang hoạt động" if user['is_active'] else "❌ Không hoạt động"
        username = user['username'] if user['username'] else f"{user['first_name']} {user['last_name'] or ''}"
        subscription_end = datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S') if user['subscription_end'] else None
        
        message = f"🔍 *Kết quả tìm kiếm cho '{search_term}':*\n\n"
        message += f"👤 *ID:* `{user['telegram_id']}`\n"
        message += f"👤 *Username:* @{username}\n"
        message += f"📅 *Đăng ký:* {datetime.strptime(user['registered_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}\n"
        message += f"⚙️ *Trạng thái:* {status}\n"
        
        if subscription_end:
            if subscription_end > datetime.now():
                days_left = (subscription_end - datetime.now()).days
                hours_left = ((subscription_end - datetime.now()).seconds // 3600)
                message += f"⏳ *Còn lại:* {days_left} ngày {hours_left} giờ\n"
            else:
                message += f"⏳ *Hết hạn:* {subscription_end.strftime('%d/%m/%Y %H:%M')}\n"
        
        message += f"🔑 *Key:* {user['active_key'] or 'Không có'}\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Reset key", callback_data=f"reset_user_{user['telegram_id']}"),
                InlineKeyboardButton("❌ Khóa tài khoản", callback_data=f"ban_user_{user['telegram_id']}")
            ],
            [
                InlineKeyboardButton("✅ Mở khóa", callback_data=f"unban_user_{user['telegram_id']}"),
                InlineKeyboardButton("➕ Thêm 7 ngày", callback_data=f"add7days_{user['telegram_id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def user_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = query.from_user.id
    
    if not is_admin(admin_id---

# Lưu kết quả phân tích
def save_md5_analysis(md5_hash, original_value=None, result=None, prediction=None, prediction_correct=None):
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO md5_results (md5_hash, original_value, result, prediction, prediction_correct) VALUES (?, ?, ?, ?, ?)',
        (md5_hash, original_value, result, prediction, prediction_correct)
    )
    conn.commit()
    conn.close()

# Cập nhật pattern
def update_pattern(pattern, result):
    conn = get_db_connection()
    cursor = conn.execute('SELECT * FROM md5_patterns WHERE pattern = ?', (pattern,))
    row = cursor.fetchone()
    
    if row:
        if result == 'TÀI':
            conn.execute('UPDATE md5_patterns SET tai_count = tai_count + 1, last_updated = ? WHERE pattern = ?', 
                        (datetime.now(), pattern))
        else:
            conn.execute('UPDATE md5_patterns SET xiu_count = xiu_count + 1, last_updated = ? WHERE pattern = ?', 
                        (datetime.now(), pattern))
    else:
        tai_count = 1 if result == 'TÀI' else 0
        xiu_count = 1 if result == 'XỈU' else 0
        conn.execute('INSERT INTO md5_patterns (pattern, tai_count, xiu_count, last_updated) VALUES (?, ?, ?, ?)', 
                    (pattern, tai_count, xiu_count, datetime.now()))
    
    conn.commit()
    conn.close()

# Trích xuất đặc trưng
def extract_patterns(md5_hash):
    patterns = {
        'first_char': md5_hash[0],
        'last_char': md5_hash[-1],
        'first_four': md5_hash[:4],
        'last_four': md5_hash[-4:],
        'num_count': sum(c.isdigit() for c in md5_hash),
        'alpha_count': sum(c.isalpha() for c in md5_hash),
        'has_sequence': any(md5_hash[i] == md5_hash[i+1] == md5_hash[i+2] for i in range(len(md5_hash)-2)),
        'sum_digits': sum(int(c) for c in md5_hash if c.isdigit()),
        'hex_sum': sum(int(c, 16) for c in md5_hash)
    }
    return patterns

# Huấn luyện mô hình ML
def train_model():
    conn = get_db_connection()
    cursor = conn.execute('SELECT md5_hash, result FROM md5_results WHERE result IS NOT NULL')
    data = cursor.fetchall()
    conn.close()
    
    if len(data) < 100:
        return None
    
    X = []
    y = []
    for row in data:
        md5 = row['md5_hash']
        features = extract_features(md5)
        X.append(features)
        y.append(1 if row['result'] == 'TÀI' else 0)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    
    return model

# Tải mô hình ML
def load_model():
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, 'rb') as f:
            return pickle.load(f)
    return None

# Trích xuất đặc trưng cho ML
def extract_features(md5_hash):
    hex_values = [int(c, 16) for c in md5_hash]
    features = [
        sum(hex_values),
        sum(1 for c in md5_hash if c.isdigit()),
        sum(1 for c in md5_hash if c.isalpha()),
        np.mean(hex_values),
        sum(1 for i in range(len(md5_hash)-1) if md5_hash[i] == md5_hash[i+1]),
        len(set(md5_hash)),
        sum(ord(c) for c in md5_hash) % 100
    ]
    return features

# Dự đoán
def get_prediction(md5_hash):
    patterns = extract_patterns(md5_hash)
    
    model = load_model()
    if model:
        features = extract_features(md5_hash)
        pred = model.predict([features])[0]
        confidence = model.predict_proba([features])[0][pred]
        result = "TÀI" if pred == 1 else "XỈU"
        if confidence > 0.8:
            return result, confidence, "Dự đoán từ mô hình ML"
    
    conn = get_db_connection()
    tai_probability = 0
    xiu_probability = 0
    total_weight = 0
    
    for pattern_type, pattern_value in patterns.items():
        pattern_key = f"{pattern_type}_{pattern_value}"
        cursor = conn.execute('SELECT tai_count, xiu_count FROM md5_patterns WHERE pattern = ?', (pattern_key,))
        row = cursor.fetchone()
        
        if row:
            tai_count = row['tai_count']
            xiu_count = row['xiu_count']
            total = tai_count + xiu_count
            if total > 10:
                weight = min(total / 50, 1.0)
                tai_probability += (tai_count / total) * weight
                xiu_probability += (xiu_count / total) * weight
                total_weight += weight
    
    conn.close()
    
    hex_values = [int(c, 16) for c in md5_hash]
    hex_sum = sum(hex_values)
    entropy = -sum((hex_values.count(i) / 32) * np.log2(hex_values.count(i) / 32 + 1e-10) for i in set(hex_values))
    
    if total_weight > 0:
        final_tai_prob = (tai_probability / total_weight) * 0.6 + (hex_sum % 2) * 0.2 + (entropy / 4) * 0.2
    else:
        final_tai_prob = (hex_sum % 2) * 0.5 + (entropy / 4) * 0.3 + (hash(md5_hash) % 100) / 100 * 0.2
    
    confidence = abs(final_tai_prob - 0.5) * 2
    result = "TÀI" if final_tai_prob > 0.5 else "XỈU"
    
    return result, confidence, "Dự đoán từ pattern và đặc trưng"

# Xác minh
def verify_result(md5_hash, original_value):
    calculated_hash = hashlib.md5(original_value.encode()).hexdigest()
    if calculated_hash != md5_hash:
        return False, "Mã MD5 không khớp với giá trị gốc"
    
    try:
        value = int(original_value)
        result = "TÀI" if value > 10 else "XỈU"
        return True, result
    except ValueError:
        original_value = original_value.upper()
        if original_value in ["TÀI", "XỈU"]:
            return True, original_value
        hash_sum = sum(ord(c) for c in original_value)
        result = "TÀI" if hash_sum % 100 > 50 else "XỈU"
        return True, result

# Phân tích MD5
async def analyze_md5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    has_access, message = check_user_subscription(telegram_id)
    if not has_access:
        await update.message.reply_text(message)
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Vui lòng nhập mã MD5. Ví dụ: /analyze d46fc8680d526dcd77c66319c173eef8")
        return
    
    md5_hash = context.args[0].strip().lower()
    
    if not (len(md5_hash) == 32 and all(c in '0123456789abcdef' for c in md5_hash)):
        await update.message.reply_text("❌ Mã MD5 không hợp lệ! Phải là 32 ký tự hex.")
        return
    
    result, confidence, method = get_prediction(md5_hash)
    
    save_md5_analysis(md5_hash, prediction=result)
    
    patterns = extract_patterns(md5_hash)
    for pattern_type, pattern_value in patterns.items():
        pattern_key = f"{pattern_type}_{pattern_value}"
        update_pattern(pattern_key, result)
    
    confidence_percent = confidence * 100
    await update.message.reply_text(
        f"🔍 *Phân tích mã MD5*\n\n"
        f"📌 Mã MD5: `{md5_hash}`\n"
        f"🎯 Dự đoán: **{result}**\n"
        f"📈 Độ tin cậy: {confidence_percent:.2f}%\n"
        f"🔧 Phương pháp: {method}\n\n"
        f"💡 Để xác minh kết quả thực tế, cung cấp giá trị gốc bằng lệnh:\n"
        f"/verify {md5_hash} [giá_trị_gốc]",
        parse_mode='Markdown'
    )

# Xác minh MD5
async def verify_md5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    has_access, message = check_user_subscription(telegram_id)
    if not has_access:
        await update.message.reply_text(message)
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Vui lòng nhập mã MD5 và giá trị gốc. Ví dụ: /verify d46fc8680d526dcd77c66319c173eef8 TÀI")
        return
    
    md5_hash = context.args[0].strip().lower()
    original_value = " ".join(context.args[1:]).strip().upper()
    
    if not (len(md5_hash) == 32 and all(c in '0123456789abcdef' for c in md5_hash)):
        await update.message.reply_text("❌ Mã MD5 không hợp lệ! Phải là 32 ký tự hex.")
        return
    
    is_valid, result = verify_result(md5_hash, original_value)
    
    conn = get_db_connection()
    cursor = conn.execute('SELECT prediction FROM md5_results WHERE md5_hash = ? ORDER BY timestamp DESC LIMIT 1', (md5_hash,))
    row = cursor.fetchone()
    prediction = row['prediction'] if row else None
    
    prediction_correct = 1 if prediction and prediction == result else 0
    conn.execute(
        'UPDATE md5_results SET original_value = ?, result = ?, prediction_correct = ? WHERE md5_hash = ?',
        (original_value, result, prediction_correct, md5_hash)
    )
    conn.commit()
    conn.close()
    
    patterns = extract_patterns(md5_hash)
    for pattern_type, pattern_value in patterns.items():
        pattern_key = f"{pattern_type}_{pattern_value}"
        update_pattern(pattern_key, result)
    
    message = f"🔍 *Xác minh mã MD5*\n\n" f"📌 Mã MD5: `{md5_hash}`\n" f"📝 Giá trị gốc: `{original_value}`\n"
    if is_valid:
        message += f"✅ MD5 hợp lệ!\n" f"🎯 Kết quả thật: **{result}**\n"
        if prediction:
            message += f"🤖 Dự đoán trước: **{prediction}** ({'Đúng' if prediction_correct else 'Sai'})\n"
        else:
            message += f"⚠️ Chưa có dự đoán trước đó.\n"
    else:
        message += f"❌ MD5 không khớp với giá trị gốc!\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')
    
    conn = get_db_connection()
    cursor = conn.execute('SELECT COUNT(*) as count FROM md5_results WHERE result IS NOT NULL')
    count = cursor.fetchone()['count']
    conn.close()
    
    if count % 100 == 0:
        train_model()

# Hàm main
async def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("register", register_user))
    app.add_handler(CommandHandler("activate", activate_key))
    app.add_handler(CommandHandler("status", user_status))
    app.add_handler(CommandHandler("create_key", create_key))
    app.add_handler(CommandHandler("create_keys", create_multiple_keys))
    app.add_handler(CommandHandler("create_key_hours", create_key_with_hours))
    app.add_handler(CommandHandler("list_keys", list_keys))
    app.add_handler(CommandHandler("key_info", key_info))
    app.add_handler(CommandHandler("extend_key", extend_key))
    app.add_handler(CommandHandler("shorten_key", shorten_key))
    app.add_handler(CommandHandler("delete_key", delete_key))
    app.add_handler(CommandHandler("list_users", list_users))
    app.add_handler(CommandHandler("system_stats", system_stats))
    app.add_handler(CommandHandler("search_user", search_user))
    app.add_handler(CommandHandler("analyze", analyze_md5))
    app.add_handler(CommandHandler("verify", verify_md5))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

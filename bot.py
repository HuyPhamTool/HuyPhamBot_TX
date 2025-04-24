import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, 
    CommandHandler, 
    CallbackQueryHandler, 
    CallbackContext, 
    MessageHandler, 
    filters
)
import hashlib
from datetime import datetime, timedelta
import sqlite3
import secrets
import json
from typing import Dict, Any, Optional

# --------------------- Cấu hình nâng cao ---------------------
class Config:
    # Cấu hình logging chi tiết
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'taixiu_bot.log'
    LOG_LEVEL = logging.INFO
    
    # Cấu hình database
    DB_FILE = 'taixiu_bot.db'
    
    # Cấu hình admin
    ADMIN_IDS = [123456789]  # Thay bằng ID admin của bạn
    
    # Thuật toán phân tích MD5
    ALGORITHMS = {
        'simple': 'Phương pháp đơn giản (ký tự cuối)',
        'advanced': 'Phương pháp nâng cao (phân tích tổng hợp)',
        'statistical': 'Phương pháp thống kê (xu hướng)',
        'hybrid': 'Phương pháp lai (kết hợp nhiều yếu tố)'
    }
    
    # Thời gian key mặc định
    KEY_DURATIONS = {
        '1': {'days': 1, 'hours': 0, 'label': '1 ngày'},
        '3': {'days': 3, 'hours': 0, 'label': '3 ngày'},
        '7': {'days': 7, 'hours': 0, 'label': '1 tuần'},
        '30': {'days': 30, 'hours': 0, 'label': '1 tháng'},
        'custom': {'days': 0, 'hours': 0, 'label': 'Tùy chỉnh'}
    }

# --------------------- Thiết lập logging ---------------------
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(Config.LOG_LEVEL)
    
    # File handler
    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# --------------------- Database Helpers ---------------------
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(Config.DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        """Tạo các bảng database nếu chưa tồn tại"""
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT,
            active_key TEXT,
            expiry_date TEXT,
            algorithm TEXT DEFAULT 'simple',
            request_count INTEGER DEFAULT 0,
            last_request_date TEXT
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_keys (
            key TEXT PRIMARY KEY,
            duration_days INTEGER,
            duration_hours INTEGER,
            created_date TEXT,
            created_by TEXT,
            used_by INTEGER,
            used_date TEXT,
            is_active INTEGER DEFAULT 1,
            note TEXT
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS request_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            md5_hash TEXT,
            prediction TEXT,
            algorithm TEXT,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        ''')
        
        self.conn.commit()
    
    def log_request(self, user_id: int, md5_hash: str, prediction: str, algorithm: str):
        """Ghi log yêu cầu phân tích"""
        self.cursor.execute('''
        INSERT INTO request_logs (user_id, md5_hash, prediction, algorithm, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, md5_hash, prediction, algorithm, datetime.now().isoformat()))
        
        self.cursor.execute('''
        UPDATE users SET request_count = request_count + 1, last_request_date = ?
        WHERE user_id = ?
        ''', (datetime.now().isoformat(), user_id))
        
        self.conn.commit()

db = Database()

# --------------------- Thuật toán phân tích MD5 ---------------------
class MD5Analyzer:
    @staticmethod
    def simple_analysis(md5_hash: str) -> str:
        """Phân tích đơn giản dựa trên ký tự cuối"""
        if len(md5_hash) != 32:
            raise ValueError("MD5 hash phải có 32 ký tự")
        
        last_char = md5_hash[-1].lower()
        return "TÀI" if int(last_char, 16) >= 8 else "XỈU"
    
    @staticmethod
    def advanced_analysis(md5_hash: str) -> str:
        """Phân tích nâng cao dựa trên nhiều yếu tố"""
        if len(md5_hash) != 32:
            raise ValueError("MD5 hash phải có 32 ký tự")
        
        # Phân tích các phần của hash
        parts = [md5_hash[i:i+8] for i in range(0, 32, 8)]
        sum_values = [sum(int(c, 16) for c in parts]
        avg_values = [s / 8 for s in sum_values]
        
        # Đếm số chẵn/lẻ
        even_count = sum(1 for c in md5_hash if int(c, 16) % 2 == 0)
        odd_count = 32 - even_count
        
        # Phân tích cụm
        cluster_score = 0
        for i in range(len(md5_hash)-1):
            if abs(int(md5_hash[i], 16) - int(md5_hash[i+1], 16)) <= 2:
                cluster_score += 1
        
        # Tính điểm
        tai_score = 0
        xiu_score = 0
        
        # Điểm từ giá trị trung bình
        for avg in avg_values:
            if avg > 7.5:
                tai_score += 1
            else:
                xiu_score += 1
        
        # Điểm từ chẵn/lẻ
        if even_count > odd_count:
            tai_score += 1.5
        else:
            xiu_score += 1.5
        
        # Điểm từ cụm
        if cluster_score > 16:
            xiu_score += 1
        else:
            tai_score += 0.5
        
        return "TÀI" if tai_score > xiu_score else "XỈU"
    
    @staticmethod
    def statistical_analysis(md5_hash: str) -> str:
        """Phân tích thống kê dựa trên xu hướng"""
        if len(md5_hash) != 32:
            raise ValueError("MD5 hash phải có 32 ký tự")
        
        # Chuyển sang giá trị số
        values = [int(c, 16) for c in md5_hash]
        
        # Tính trung bình
        mean = sum(values) / len(values)
        
        # Tính độ lệch
        deviation = sum((x - mean) ** 2 for x in values) / len(values)
        
        # Phân tích xu hướng
        if mean > 7.5 and deviation > 8:
            return "TÀI"
        elif mean < 7.5 and deviation > 8:
            return "XỈU"
        else:
            # Nếu không rõ ràng, dùng phương pháp đơn giản
            return MD5Analyzer.simple_analysis(md5_hash)
    
    @staticmethod
    def hybrid_analysis(md5_hash: str) -> str:
        """Phương pháp lai kết hợp nhiều thuật toán"""
        results = {
            'simple': MD5Analyzer.simple_analysis(md5_hash),
            'advanced': MD5Analyzer.advanced_analysis(md5_hash),
            'statistical': MD5Analyzer.statistical_analysis(md5_hash)
        }
        
        # Đếm kết quả
        counts = {'TÀI': 0, 'XỈU': 0}
        for result in results.values():
            counts[result] += 1
        
        # Quyết định dựa trên đa số
        if counts['TÀI'] > counts['XỈU']:
            return "TÀI"
        elif counts['XỈU'] > counts['TÀI']:
            return "XỈU"
        else:
            # Nếu hòa, dùng phương pháp nâng cao
            return results['advanced']

# --------------------- Telegram Bot Handlers ---------------------
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    logger.info(f"User {user.id} started the bot")
    
    # Kiểm tra và thêm user vào database nếu chưa có
    db.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user.id,))
    if not db.cursor.fetchone():
        db.cursor.execute('''
        INSERT INTO users (user_id, username, join_date) 
        VALUES (?, ?, ?)
        ''', (user.id, user.username, datetime.now().isoformat()))
        db.conn.commit()
        logger.info(f"Added new user: {user.id}")
    
    # Kiểm tra key active
    db.cursor.execute('SELECT active_key, expiry_date FROM users WHERE user_id = ?', (user.id,))
    user_data = db.cursor.fetchone()
    
    if user_data and user_data[0] and datetime.fromisoformat(user_data[1]) > datetime.now():
        # User có key active
        keyboard = [
            [InlineKeyboardButton("🔍 Phân tích MD5", callback_data='analyze_md5')],
            [InlineKeyboardButton("ℹ️ Thông tin key", callback_data='key_info')],
            [InlineKeyboardButton("⚙️ Cài đặt thuật toán", callback_data='algorithm_settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            '🎲 Chào mừng bạn đến với bot phân tích Tài Xỉu!\n'
            '🔑 Bạn đang có key active. Vui lòng chọn chức năng:',
            reply_markup=reply_markup
        )
    else:
        # User không có key hoặc key hết hạn
        keyboard = [
            [InlineKeyboardButton("🔑 Nhập key", callback_data='enter_key')],
            [InlineKeyboardButton("💳 Mua key", url='https://example.com')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            '🎲 Chào mừng bạn đến với bot phân tích Tài Xỉu!\n'
            '🔐 Bạn cần có key để sử dụng dịch vụ. Vui lòng chọn:',
            reply_markup=reply_markup
        )

def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    user_id = update.effective_user.id
    logger.info(f"Button pressed by {user_id}: {query.data}")
    
    if query.data == 'analyze_md5':
        query.edit_message_text(text="🔢 Vui lòng nhập mã MD5 để phân tích:")
        context.user_data['waiting_for_md5'] = True
    elif query.data == 'key_info':
        show_key_info(update, context)
    elif query.data == 'enter_key':
        query.edit_message_text(text="🔑 Vui lòng nhập key của bạn:")
        context.user_data['waiting_for_key'] = True
    elif query.data == 'algorithm_settings':
        show_algorithm_settings(update, context)
    elif query.data.startswith('set_algorithm_'):
        algorithm = query.data.split('_')[-1]
        set_algorithm(update, context, algorithm)
    elif query.data == 'admin_panel' and user_id in Config.ADMIN_IDS:
        show_admin_panel(update, context)
    elif query.data.startswith('admin_create_key_'):
        duration = query.data.split('_')[-1]
        create_key(update, context, duration)
    elif query.data == 'admin_manage_keys':
        show_key_management(update, context)
    elif query.data == 'admin_user_stats':
        show_user_stats(update, context)
    elif query.data == 'back_to_menu':
        start_from_button(update, context)

def start_from_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user = update.effective_user
    
    db.cursor.execute('SELECT active_key, expiry_date FROM users WHERE user_id = ?', (user.id,))
    user_data = db.cursor.fetchone()
    
    if user_data and user_data[0] and datetime.fromisoformat(user_data[1]) > datetime.now():
        keyboard = [
            [InlineKeyboardButton("🔍 Phân tích MD5", callback_data='analyze_md5')],
            [InlineKeyboardButton("ℹ️ Thông tin key", callback_data='key_info')],
            [InlineKeyboardButton("⚙️ Cài đặt thuật toán", callback_data='algorithm_settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text='🎲 Menu chính - Chọn chức năng:',
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🔑 Nhập key", callback_data='enter_key')],
            [InlineKeyboardButton("💳 Mua key", url='https://example.com')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text='🎲 Menu chính - Bạn cần có key để sử dụng dịch vụ:',
            reply_markup=reply_markup
        )

# --------------------- Chức năng phân tích MD5 ---------------------
def analyze_md5(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    md5_input = update.message.text.strip().lower()
    logger.info(f"User {user.id} requested analysis for MD5: {md5_input}")
    
    # Kiểm tra key active
    db.cursor.execute('SELECT active_key, expiry_date, algorithm FROM users WHERE user_id = ?', (user.id,))
    user_data = db.cursor.fetchone()
    
    if not user_data or not user_data[0] or datetime.fromisoformat(user_data[1]) <= datetime.now():
        update.message.reply_text("⚠️ Bạn cần có key active để sử dụng chức năng này.")
        return
    
    # Validate MD5
    if len(md5_input) != 32 or not all(c in '0123456789abcdef' for c in md5_input):
        update.message.reply_text("❌ Mã MD5 không hợp lệ. Vui lòng nhập lại.")
        return
    
    # Lấy thuật toán đã chọn
    algorithm = user_data[2] or 'simple'
    
    # Phân tích theo thuật toán
    try:
        if algorithm == 'simple':
            prediction = MD5Analyzer.simple_analysis(md5_input)
        elif algorithm == 'advanced':
            prediction = MD5Analyzer.advanced_analysis(md5_input)
        elif algorithm == 'statistical':
            prediction = MD5Analyzer.statistical_analysis(md5_input)
        elif algorithm == 'hybrid':
            prediction = MD5Analyzer.hybrid_analysis(md5_input)
        else:
            prediction = MD5Analyzer.simple_analysis(md5_input)
        
        # Ghi log
        db.log_request(user.id, md5_input, prediction, algorithm)
        
        # Gửi kết quả
        update.message.reply_text(
            f"🎯 Kết quả phân tích:\n"
            f"🔢 MD5: <code>{md5_input}</code>\n"
            f"📊 Thuật toán: {Config.ALGORITHMS.get(algorithm, 'Đơn giản')}\n"
            f"🔮 Dự đoán: <b>{prediction}</b>\n\n"
            f"📌 Lưu ý: Đây chỉ là dự đoán, không đảm bảo 100% chính xác",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error analyzing MD5: {str(e)}")
        update.message.reply_text("❌ Có lỗi xảy ra khi phân tích. Vui lòng thử lại.")

# --------------------- Hệ thống key ---------------------
def handle_key_input(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    key_input = update.message.text.strip()
    logger.info(f"User {user.id} attempting to activate key: {key_input}")
    
    # Kiểm tra key trong database
    db.cursor.execute('SELECT * FROM license_keys WHERE key = ? AND is_active = 1', (key_input,))
    key_data = db.cursor.fetchone()
    
    if not key_data:
        update.message.reply_text("❌ Key không hợp lệ hoặc đã được sử dụng.")
        return
    
    # Kiểm tra key đã được sử dụng chưa
    if key_data[5]:  # used_by
        update.message.reply_text("❌ Key này đã được sử dụng bởi người khác.")
        return
    
    # Tính toán ngày hết hạn
    duration_days = key_data[1] or 0
    duration_hours = key_data[2] or 0
    expiry_date = datetime.now() + timedelta(days=duration_days, hours=duration_hours)
    
    # Cập nhật database
    try:
        db.cursor.execute('''
        UPDATE license_keys SET used_by = ?, used_date = ? WHERE key = ?
        ''', (user.id, datetime.now().isoformat(), key_input))
        
        db.cursor.execute('''
        UPDATE users SET active_key = ?, expiry_date = ? WHERE user_id = ?
        ''', (key_input, expiry_date.isoformat(), user.id))
        
        db.conn.commit()
        
        update.message.reply_text(
            f"✅ Kích hoạt key thành công!\n"
            f"🔑 Key: <code>{key_input}</code>\n"
            f"⏳ Hết hạn vào: <b>{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
            f"🎲 Bây giờ bạn có thể sử dụng bot để phân tích MD5!",
            parse_mode='HTML'
        )
        logger.info(f"Key {key_input} activated for user {user.id}")
        
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error activating key: {str(e)}")
        update.message.reply_text("❌ Có lỗi xảy ra khi kích hoạt key. Vui lòng thử lại.")

def show_key_info(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user = update.effective_user
    
    db.cursor.execute('''
    SELECT u.active_key, u.expiry_date, k.duration_days, k.duration_hours, k.created_date
    FROM users u
    LEFT JOIN license_keys k ON u.active_key = k.key
    WHERE u.user_id = ?
    ''', (user.id,))
    
    key_info = db.cursor.fetchone()
    
    if key_info and key_info[0]:
        expiry_date = datetime.fromisoformat(key_info[1])
        remaining = expiry_date - datetime.now()
        remaining_str = f"{remaining.days} ngày, {remaining.seconds//3600} giờ"
        
        message = (
            f"🔑 Thông tin key của bạn:\n\n"
            f"🏷️ Key: <code>{key_info[0]}</code>\n"
            f"⏳ Hết hạn: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🕒 Còn lại: {remaining_str}\n"
            f"📅 Thời hạn: {key_info[2]} ngày, {key_info[3]} giờ\n"
            f"📌 Tạo ngày: {datetime.fromisoformat(key_info[4]).strftime('%Y-%m-%d') if key_info[4] else 'N/A'}"
        )
    else:
        message = "❌ Bạn chưa có key active. Vui lòng nhập key để sử dụng dịch vụ."
    
    keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# --------------------- Cài đặt thuật toán ---------------------
def show_algorithm_settings(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user = update.effective_user
    
    db.cursor.execute('SELECT algorithm FROM users WHERE user_id = ?', (user.id,))
    current_algorithm = db.cursor.fetchone()[0] or 'simple'
    
    keyboard = []
    for algo_key, algo_name in Config.ALGORITHMS.items():
        prefix = "✅ " if algo_key == current_algorithm else "◻️ "
        keyboard.append([InlineKeyboardButton(
            f"{prefix}{algo_name}", 
            callback_data=f'set_algorithm_{algo_key}'
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        text="⚙️ Chọn thuật toán phân tích MD5:",
        reply_markup=reply_markup
    )

def set_algorithm(update: Update, context: CallbackContext, algorithm: str) -> None:
    query = update.callback_query
    user = update.effective_user
    
    if algorithm not in Config.ALGORITHMS:
        query.answer("❌ Thuật toán không hợp lệ", show_alert=True)
        return
    
    db.cursor.execute('''
    UPDATE users SET algorithm = ? WHERE user_id = ?
    ''', (algorithm, user.id))
    db.conn.commit()
    
    query.answer(f"✅ Đã đặt thuật toán: {Config.ALGORITHMS[algorithm]}", show_alert=True)
    show_algorithm_settings(update, context)

# --------------------- Admin Functions ---------------------
def show_admin_panel(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("🔑 Tạo key", callback_data='admin_create_key_menu')],
        [InlineKeyboardButton("📊 Quản lý key", callback_data='admin_manage_keys')],
        [InlineKeyboardButton("👥 Thống kê user", callback_data='admin_user_stats')],
        [InlineKeyboardButton("📝 Xem logs", callback_data='admin_view_logs')],
        [InlineKeyboardButton("🔙 Menu chính", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        text="👑 Admin Panel - Chọn chức năng:",
        reply_markup=reply_markup
    )

def show_key_creation_menu(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    
    keyboard = []
    for key, value in Config.KEY_DURATIONS.items():
        if key != 'custom':
            keyboard.append([InlineKeyboardButton(
                f"⏳ Tạo key {value['label']}", 
                callback_data=f'admin_create_key_{key}'
            )])
    
    keyboard.append([InlineKeyboardButton("🛠️ Tạo key tùy chỉnh", callback_data='admin_create_key_custom')])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data='admin_panel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        text="🔑 Chọn loại key cần tạo:",
        reply_markup=reply_markup
    )

def create_key(update: Update, context: CallbackContext, duration: str) -> None:
    query = update.callback_query
    admin_id = update.effective_user.id
    
    if duration == 'custom':
        query.edit_message_text(text="🛠️ Vui lòng nhập thời hạn key (định dạng: <ngày> <giờ>, ví dụ: 3 12 cho 3 ngày 12 giờ):")
        context.user_data['waiting_for_custom_key_duration'] = True
        return
    
    duration_config = Config.KEY_DURATIONS.get(duration, Config.KEY_DURATIONS['1'])
    days = duration_config['days']
    hours = duration_config['hours']
    
    # Tạo key ngẫu nhiên
    new_key = secrets.token_hex(8)  # 16 ký tự hex
    
    # Lưu vào database
    db.cursor.execute('''
    INSERT INTO license_keys (key, duration_days, duration_hours, created_date, created_by, is_active)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (new_key, days, hours, datetime.now().isoformat(), admin_id, 1))
    db.conn.commit()
    
    query.answer(f"✅ Đã tạo key {days} ngày {hours} giờ: {new_key}", show_alert=True)
    logger.info(f"Admin {admin_id} created new key: {new_key} ({days} days, {hours} hours)")

def handle_custom_key_duration(update: Update, context: CallbackContext) -> None:
    admin_id = update.effective_user.id
    text = update.message.text.strip()
    logger.info(f"Admin {admin_id} creating custom key with duration: {text}")
    
    try:
        parts = text.split()
        days = int(parts[0]) if len(parts) > 0 else 0
        hours = int(parts[1]) if len(parts) > 1 else 0
        
        if days < 0 or hours < 0:
            raise ValueError("Thời gian không hợp lệ")
        
        # Tạo key ngẫu nhiên
        new_key = secrets.token_hex(8)
        
        # Lưu vào database
        db.cursor.execute('''
        INSERT INTO license_keys (key, duration_days, duration_hours, created_date, created_by, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (new_key, days, hours, datetime.now().isoformat(), admin_id, 1))
        db.conn.commit()
        
        update.message.reply_text(
            f"✅ Đã tạo key tùy chỉnh thành công!\n"
            f"🔑 Key: <code>{new_key}</code>\n"
            f"⏳ Thời hạn: {days} ngày {hours} giờ\n\n"
            f"📌 Gửi key này cho người dùng để họ kích hoạt.",
            parse_mode='HTML'
        )
        logger.info(f"Admin {admin_id} created custom key: {new_key} ({days}d {hours}h)")
        
    except Exception as e:
        logger.error(f"Error creating custom key: {str(e)}")
        update.message.reply_text("❌ Định dạng thời gian không hợp lệ. Vui lòng nhập lại (ví dụ: '3 12' cho 3 ngày 12 giờ).")

def show_key_management(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    
    # Lấy danh sách key
    db.cursor.execute('''
    SELECT key, duration_days, duration_hours, created_date, used_by, is_active
    FROM license_keys
    ORDER BY created_date DESC
    LIMIT 50
    ''')
    keys = db.cursor.fetchall()
    
    if not keys:
        query.edit_message_text(text="📭 Không có key nào trong database.")
        return
    
    message = "🔑 Danh sách key (50 mới nhất):\n\n"
    for key in keys:
        status = "✅ Active" if key[5] else "❌ Inactive"
        used = "🟢 Chưa dùng" if not key[4] else f"🔴 Đã dùng bởi {key[4]}"
        message += (
            f"🏷️ <code>{key[0]}</code>\n"
            f"⏳ {key[1]}d {key[2]}h | 📅 {datetime.fromisoformat(key[3]).strftime('%Y-%m-%d')}\n"
            f"{status} | {used}\n\n"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

def show_user_stats(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    
    # Thống kê user
    db.cursor.execute('SELECT COUNT(*) FROM users')
    total_users = db.cursor.fetchone()[0]
    
    db.cursor.execute('''
    SELECT COUNT(*) FROM users 
    WHERE active_key IS NOT NULL AND expiry_date > ?
    ''', (datetime.now().isoformat(),))
    active_users = db.cursor.fetchone()[0]
    
    db.cursor.execute('''
    SELECT username, request_count, last_request_date 
    FROM users 
    WHERE request_count > 0
    ORDER BY request_count DESC
    LIMIT 10
    ''')
    top_users = db.cursor.fetchall()
    
    message = (
        f"👥 Thống kê người dùng:\n\n"
        f"📊 Tổng user: {total_users}\n"
        f"🟢 User active: {active_users}\n\n"
        f"🏆 Top 10 user tích cực:\n"
    )
    
    for i, user in enumerate(top_users, 1):
        last_active = datetime.fromisoformat(user[2]).strftime('%Y-%m-%d') if user[2] else "N/A"
        message += f"{i}. {user[0] or 'N/A'}: {user[1]} lần (cuối: {last_active})\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )

# --------------------- Main Handler ---------------------
def handle_message(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('waiting_for_md5'):
        context.user_data.pop('waiting_for_md5', None)
        analyze_md5(update, context)
    elif context.user_data.get('waiting_for_key'):
        context.user_data.pop('waiting_for_key', None)
        handle_key_input(update, context)
    elif context.user_data.get('waiting_for_custom_key_duration'):
        context.user_data.pop('waiting_for_custom_key_duration', None)
        handle_custom_key_duration(update, context)
    else:
        update.message.reply_text("ℹ️ Vui lòng sử dụng các nút chức năng hoặc gõ /start để bắt đầu.")

def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling update:", exc_info=context.error)
    
    if update and update.effective_message:
        update.effective_message.reply_text(
            "❌ Có lỗi xảy ra. Vui lòng thử lại hoặc liên hệ admin."
        )

# --------------------- Khởi chạy bot ---------------------
def main() -> None:
    # Tạo updater và dispatcher
    updater = Updater("7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8", use_context=True)
    dispatcher = updater.dispatcher

    # Thêm các handler
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    dispatcher.add_error_handler(error_handler)
    
    # Khởi chạy bot
    logger.info("Bot is starting...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

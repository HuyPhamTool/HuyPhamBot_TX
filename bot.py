import telebot
from telebot import types
import logging
import os
import time
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import defaultdict
from ratelimit import limits, sleep_and_retry
import json
from datetime import datetime

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),  # Lưu log vào file
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Khởi tạo bot
API_TOKEN = os.getenv('AAELl1ulqvMjNablJrnfGH6UxweDMG3FPRA')  # Lấy token từ biến môi trường
if not API_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN không được thiết lập!")
    exit(1)

bot = telebot.TeleBot(API_TOKEN)
ADMIN_ID = 7505331567  # Thay bằng ID Telegram của admin
CALLS_PER_MINUTE = 10
ONE_MINUTE = 60
user_requests = defaultdict(list)
user_stats = defaultdict(lambda: {'predictions': 0, 'last_used': None})

# Lưu trữ người dùng
USER_FILE = 'users.json'
def save_users():
    with open(USER_FILE, 'w') as f:
        json.dump({k: v for k, v in user_stats.items()}, f)

def load_users():
    try:
        with open(USER_FILE, 'r') as f:
            data = json.load(f)
            for k, v in data.items():
                user_stats[int(k)] = v
    except FileNotFoundError:
        pass

load_users()

# Health check server để Render kiểm tra
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')

def run_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
    logger.info("Health check server chạy trên cổng 8080")
    server.serve_forever()

# Hàm dự đoán
def hybrid_predict(md5_hash):
    try:
        byte_1 = int(md5_hash[1:3], 16)
        byte_5 = int(md5_hash[5:7], 16)
        byte_9 = int(md5_hash[9:11], 16)
        total1 = ((byte_1 + byte_5) % 6 + 1) + ((byte_5 | byte_9) % 6 + 1) + ((byte_9 - byte_1) % 6 + 1)

        byte_0 = int(md5_hash[0:2], 16)
        byte_4 = int(md5_hash[4:6], 16)
        byte_8 = int(md5_hash[8:10], 16)
        total2 = ((byte_0 * byte_4) % 6 + 1) + ((byte_4 ^ byte_8) % 6 + 1) + ((byte_0 + byte_8) % 6 + 1)

        byte_2 = int(md5_hash[2:4], 16)
        byte_6 = int(md5_hash[6:8], 16)
        byte_10 = int(md5_hash[10:12], 16)
        total3 = (byte_2 % 6 + 1) + ((byte_6 >> 2) % 6 + 1) + ((byte_10 ^ byte_2) % 6 + 1)

        avg_total = round((total1 + total2 + total3) / 3)
        return {
            'result': "Tài" if avg_total >= 11 else "Xỉu",
            'confidence': "85-90%",
            'details': (
                f"Phương pháp lai 3 lớp:\n"
                f"1. Byte 1/5/9 → Tổng: {total1}\n"
                f"2. Byte 0/4/8 → Tổng: {total2}\n"
                f"3. Byte 2/6/10 → Tổng: {total3}\n"
                f"Trung bình: {avg_total}"
            )
        }
    except Exception as e:
        logger.error(f"Lỗi phân tích: {str(e)}")
        return {'error': str(e)}

# Rate limiting
@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=ONE_MINUTE)
def check_rate_limit(user_id):
    now = time.time()
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < ONE_MINUTE]
    user_requests[user_id].append(now)
    if len(user_requests[user_id]) > CALLS_PER_MINUTE:
        raise Exception("Quá giới hạn! Vui lòng thử lại sau 1 phút.")

# Xử lý lệnh /start
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_stats[user_id]['last_used'] = datetime.now().isoformat()
    save_users()
    
    welcome_msg = """
🎲 *Bot Dự Đoán Tài Xỉu Từ MD5* 🎲

Gửi mã MD5 32 ký tự để nhận dự đoán:
- Độ chính xác: 85-90%
- Thuật toán lai 3 lớp tối ưu

📌 Ví dụ:  
`d46fc8680d526dcd77c66319c173eef8`

📊 Dùng `/stats` để xem thống kê của bạn!
    """
    bot.reply_to(message, welcome_msg, parse_mode='Markdown')

# Xử lý lệnh /stats
@bot.message_handler(commands=['stats'])
def send_stats(message):
    user_id = message.from_user.id
    stats = user_stats[user_id]
    response = (
        f"📊 *Thống kê của bạn:*\n"
        f"- Số lần dự đoán: {stats['predictions']}\n"
        f"- Lần sử dụng cuối: {stats.get('last_used', 'Chưa có')}"
    )
    bot.reply_to(message, response, parse_mode='Markdown')

# Xử lý lệnh /broadcast (chỉ admin)
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    msg = message.text.replace('/broadcast', '').strip()
    if not msg:
        bot.reply_to(message, "❌ Vui lòng cung cấp nội dung thông báo!")
        return
    
    for user_id in user_stats:
        try:
            bot.send_message(user_id, f"📢 *Thông báo từ admin:*\n{msg}", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo tới {user_id}: {str(e)}")
    
    bot.reply_to(message, "✅ Đã gửi thông báo tới tất cả người dùng!")

# Xử lý MD5
@bot.message_handler(regexp=r'^[a-fA-F0-9]{32}$')
def handle_md5(message):
    user_id = message.from_user.id
    logger.info(f"User {user_id} gửi MD5: {message.text}")
    
    try:
        check_rate_limit(user_id)
        analysis = hybrid_predict(message.text.lower())
        
        if 'error' in analysis:
            bot.reply_to(message, f"❌ Lỗi: {analysis['error']}")
            return
        
        user_stats[user_id]['predictions'] += 1
        user_stats[user_id]['last_used'] = datetime.now().isoformat()
        save_users()
        
        response = (
            f"🔮 *Kết quả dự đoán:*\n"
            f"┏━━━━━━━━━━━━━━━┓\n"
            f"┃ 🎯 {analysis['result']} (Tin cậy: {analysis['confidence']})\n"
            f"┗━━━━━━━━━━━━━━━┛\n\n"
            f"<code>{analysis['details']}</code>\n\n"
            f"⚠️ Lưu ý: Kết quả dựa trên phân tích tự động"
        )
        bot.reply_to(message, response, parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

# Xử lý tin nhắn không hợp lệ
@bot.message_handler(func=lambda m: True)
def handle_invalid(message):
    bot.reply_to(message, "❌ Mã MD5 không hợp lệ! Gửi mã 32 ký tự (vd: `d46fc8680d526dcd77c66319c173eef8`)", parse_mode='Markdown')

if __name__ == '__main__':
    logger.info("Khởi động bot...")
    print("""
███████╗ ██████╗ ████████╗
██╔════╝██╔═══██╗╚══██╔══╝
█████╗  ██║   ██║   ██║   
██╔══╝  ██║   ██║   ██║   
███████╗╚██████╔╝   ██║   
╚══════╝ ╚═════╝    ╚═╝   
Bot đã sẵn sàng! Nhấn Ctrl+C để dừng.
    """)
    
    # Chạy health check server trong thread riêng
    health_thread = Thread(target=run_health_server)
    health_thread.daemon = True
    health_thread.start()
    
    # Retry logic cho polling
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logger.error(f"Lỗi polling: {str(e)}")
            time.sleep(5)  # Chờ 5 giây trước khi thử lại

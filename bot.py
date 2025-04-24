# Bot Telegram phan tich Tai/Xiu tu ma MD5 + quan ly secret_key (admin)
# Yeu cau: pip install python-telegram-bot

import hashlib
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ========== Cau hinh ==========
BOT_TOKEN = "7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8"  # Thay bang token bot Telegram cua ban
ADMIN_PASSWORD = "admin1234"   # Mat khau truy cap admin

admin_ids = set()  # Luu ID cua admin da dang nhap
secret_keys = []   # Danh sach cac secret_key da tao

# ========== Ham xu ly ==========
def md5_hash(s):
    return hashlib.md5(s.encode()).hexdigest()

def phan_tich_md5(md5_target, secret_key):
    for x in range(1, 7):
        for y in range(1, 7):
            for z in range(1, 7):
                raw = f"{x},{y},{z}|{secret_key}"
                if md5_hash(raw) == md5_target:
                    total = x + y + z
                    kq = "Tài" if total >= 11 else "Xỉu"
                    return f"\U0001f3b2 Xúc xắc: {x}, {y}, {z}\nTổng: {total} => \U0001f4c8 {kq}"
    return "❌ Không tìm thấy kết quả phù hợp."

# ========== Xu ly lenh ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001f916 Xin chào! Bot phân tích Tài/Xỉu từ mã MD5\n"
        "\nLệnh dùng:\n/phan_tich - Nhập MD5 và secret_key\n/admin - Đăng nhập admin\n/tao_key - Tạo key (admin)",
    )

async def phan_tich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Gửi mã MD5 (32 ký tự) => cách => secret_key")
    context.user_data['mode'] = 'phan_tich'

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 Gửi mật khẩu admin:")
    context.user_data['mode'] = 'admin_login'

async def tao_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admin_ids:
        key = f"key_{random.randint(10000,99999)}"
        secret_keys.append(key)
        await update.message.reply_text(f"🔑 Secret_key mới: {key}")
    else:
        await update.message.reply_text("❌ Bạn không phải admin!")

# ========== Xu ly tin nhan ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('mode') == 'phan_tich':
        if '=>' not in text:
            await update.message.reply_text("⚠️ Vui lòng nhập theo định dạng: maMD5 => secret_key")
            return
        md5_code, key = [x.strip() for x in text.split('=>')]
        if len(md5_code) != 32:
            await update.message.reply_text("⚠️ Mã MD5 không hợp lệ")
            return
        await update.message.reply_text("⏳ Đang phân tích...")
        result = phan_tich_md5(md5_code.lower(), key)
        await update.message.reply_text(result)
        context.user_data.clear()

    elif context.user_data.get('mode') == 'admin_login':
        if text == ADMIN_PASSWORD:
            admin_ids.add(user_id)
            await update.message.reply_text("✅ Đăng nhập admin thành công")
        else:
            await update.message.reply_text("❌ Sai mật khẩu")
        context.user_data.clear()

    else:
        await update.message.reply_text("❓ Dùng /start để xem các lệnh hỗ trợ")

# ========== Main ==========
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("phan_tich", phan_tich))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("tao_key", tao_key))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("\U0001f680 Bot Tài/Xỉu Telegram đang chạy...")
    app.run_polling()

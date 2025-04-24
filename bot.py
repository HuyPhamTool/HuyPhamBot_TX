# Bot Telegram phan tich Tai/Xiu tu ma MD5 + kiem tra key khi bat dau
# Yeu cau: pip install python-telegram-bot

import hashlib
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ========== Cau hinh ==========
BOT_TOKEN = "7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8"  # Thay bang token bot Telegram cua ban
ADMIN_PASSWORD = "7505331567"   # Mat khau truy cap admin
VALID_KEYS = ["key123", "vip456"]  # Danh sach key cho phep

user_keys = {}   # Luu key da nhap theo user_id
admin_ids = set()  # Luu ID cua admin da dang nhap

# ========== Ham xu ly ==========
def md5_hash(s):
    return hashlib.md5(s.encode()).hexdigest()

def phan_tich_md5_chuyen_sau(md5_str):
    try:
        hex_str = md5_str[-5:]  # lấy 5 ký tự cuối
        decimal = int(hex_str, 16)
        digits = [int(d) for d in str(decimal)[-3:]]  # lấy 3 số cuối
        total = sum(digits)
        ket_qua = "Tài" if total >= 11 else "Xỉu"
        return f"🔎 Tổng 3 số cuối ({'+'.join(map(str, digits))}) = {total} → 🎯 {ket_qua}"
    except:
        return "⚠️ Mã MD5 không hợp lệ hoặc không thể phân tích."


# ========== Xu ly lenh ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_keys:
        await update.message.reply_text(
            "\U0001f916 Nhập mã MD5 cần phân tích:")
        context.user_data['mode'] = 'phan_tich'
    else:
        await update.message.reply_text("\U0001f511 Vui lòng nhập key truy cập:")
        context.user_data['mode'] = 'nhap_key'

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 Gửi mật khẩu admin:")
    context.user_data['mode'] = 'admin_login'

async def tao_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admin_ids:
        key = f"key_{random.randint(10000,99999)}"
        VALID_KEYS.append(key)
        await update.message.reply_text(f"🔑 Key mới: {key}")
    else:
        await update.message.reply_text("❌ Bạn không phải admin!")

# ========== Xu ly tin nhan ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get('mode') == 'nhap_key':
        if text in VALID_KEYS:
            user_keys[user_id] = text
            await update.message.reply_text("✅ Nhập key thành công! Nhập mã MD5 cần phân tích:")
            context.user_data['mode'] = 'phan_tich'
        else:
            await update.message.reply_text("❌ Key không hợp lệ. Vui lòng thử lại")

    elif context.user_data.get('mode') == 'phan_tich':
        md5_code = text.lower()
        if len(md5_code) != 32:
            await update.message.reply_text("⚠️ Mã MD5 phải đủ 32 ký tự")
            return
        await update.message.reply_text("⏳ Đang phân tích...")
        result = phan_tich_md5(md5_code)
        await update.message.reply_text(result)

    elif context.user_data.get('mode') == 'admin_login':
        if text == ADMIN_PASSWORD:
            admin_ids.add(user_id)
            await update.message.reply_text("✅ Đăng nhập admin thành công")
        else:
            await update.message.reply_text("❌ Sai mật khẩu")
        context.user_data.clear()

    else:
        await update.message.reply_text("❓ Dùng /start để bắt đầu")

# ========== Main ==========
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("tao_key", tao_key))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("\U0001f680 Bot Tài/Xỉu Telegram đang chạy...")
    app.run_polling()

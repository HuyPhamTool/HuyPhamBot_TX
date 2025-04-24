import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# Thiết lập log
logging.basicConfig(level=logging.INFO)

# Token bot Telegram
TOKEN = "7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8"

# Danh sách user đã được admin kích hoạt
authorized_users = set()

# Thống kê cá nhân: {user_id: {"win": int, "lose": int}}
user_stats = {}

# ID của Admin
ADMIN_ID = 7505331567  

# Hàm phân tích MD5 ra Tài/Xỉu
def analyze_md5(md5: str) -> (str, int):
    try:
        hex_part = md5[-5:]
        decimal = int(hex_part, 16)
        digits = [int(d) for d in str(decimal)[-3:]]
        total = sum(digits)
        result = "Tài" if total >= 11 else "Xỉu"
        return result, total
    except:
        return "Lỗi", 0

# Xử lý lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authorized_users:
        await update.message.reply_text(
            "🔒 Bạn chưa được kích hoạt. Vui lòng chờ admin!"
        )
    else:
        await update.message.reply_text("✅ Bạn đã được kích hoạt. Gửi mã MD5 để phân tích!")

# Lệnh cho admin: /active <user_id>
async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Bạn không có quyền dùng lệnh này.")
        return

    try:
        target_id = int(context.args[0])
        authorized_users.add(target_id)
        await update.message.reply_text(f"✅ Đã kích hoạt cho user ID: {target_id}")
    except:
        await update.message.reply_text("❌ Lỗi! Dùng đúng cú pháp: /active <user_id>")

# Phân tích MD5 khi người dùng gửi
async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in authorized_users:
        await update.message.reply_text("❌ Bạn chưa được kích hoạt. Chờ admin duyệt.")
        return

    if len(text) != 32 or not all(c in "0123456789abcdef" for c in text.lower()):
        await update.message.reply_text("⚠️ Mã MD5 không hợp lệ. Vui lòng gửi mã hợp lệ.")
        return

    result, total = analyze_md5(text)
    if result == "Lỗi":
        await update.message.reply_text("❌ Phân tích thất bại. Hãy thử lại.")
        return

    # Thống kê thắng/thua
    stats = user_stats.get(user_id, {"win": 0, "lose": 0})
    if result == "Tài":
        stats["win"] += 1
    else:
        stats["lose"] += 1

    total_games = stats["win"] + stats["lose"]
    win_rate = (stats["win"] / total_games) * 100 if total_games > 0 else 0
    user_stats[user_id] = stats

    await update.message.reply_text(
        f"🎲 Mã MD5: {text}\n"
        f"🔍 Tổng cuối: {total}\n"
        f"🎯 Kết quả: {result}\n\n"
        f"📊 Thống kê:\n"
        f"- Tài: {stats['win']}\n"
        f"- Xỉu: {stats['lose']}\n"
        f"- Tỷ lệ thắng: {win_rate:.2f}%"
    )

# Khởi tạo bot
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("active", active))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze))

    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()

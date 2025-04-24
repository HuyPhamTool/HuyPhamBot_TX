import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, CallbackQueryHandler
)

logging.basicConfig(level=logging.INFO)
TOKEN = "7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8"  # ← Thay bằng token thật
ADMIN_ID = 7505331567       # ← Thay bằng Telegram user ID của admin

# Danh sách user được kích hoạt
authorized_users = set()

# Thống kê user
user_stats = {}

# Thuật toán chuẩn chuyển MD5 thành Tài/Xỉu (tổng max 18)
def md5_to_tai_xiu(md5: str) -> (str, int):
    try:
        # Chuẩn hóa về chữ thường, lấy 3 cụm cuối
        md5 = md5.lower()
        group = [md5[i:i+2] for i in range(0, len(md5), 2)][-3:]
        numbers = [int(i, 16) for i in group]
        total = sum(numbers) % 14 + 3  # Tài/Xỉu từ 3 đến 18
        result = "Tài" if total >= 11 else "Xỉu"
        return result, total
    except:
        return "Lỗi", 0

# Lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authorized_users:
        await update.message.reply_text("🔒 Bạn chưa được admin kích hoạt.")
        return

    await update.message.reply_text(
        "🎯 Gửi mã MD5 để phân tích kết quả Tài/Xỉu.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Xem thống kê", callback_data="stats")]
        ])
    )

# Lệnh /active (chỉ dành cho admin)
async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Bạn không có quyền.")
        return
    try:
        target = int(context.args[0])
        authorized_users.add(target)
        await update.message.reply_text(f"✅ Đã kích hoạt user {target}")
    except:
        await update.message.reply_text("⚠️ Lỗi cú pháp. Dùng: /active <user_id>")

# Xử lý callback từ button
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "stats":
        stats = user_stats.get(user_id, {"win": 0, "lose": 0})
        total = stats["win"] + stats["lose"]
        win_rate = (stats["win"] / total) * 100 if total else 0
        lose_rate = 100 - win_rate
        suggestion = "📈 NÊN THEO!" if win_rate >= 60 else "📉 KHÔNG NÊN THEO!"

        await query.edit_message_text(
            f"📊 Thống kê cá nhân:\n"
            f"🏆 Thắng (Tài): {stats['win']}\n"
            f"💥 Thua (Xỉu): {stats['lose']}\n"
            f"✅ Tỷ lệ thắng: {win_rate:.2f}%\n"
            f"❌ Tỷ lệ thua: {lose_rate:.2f}%\n\n"
            f"{suggestion}"
        )

# Phân tích MD5
async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()

    if user_id not in authorized_users:
        await update.message.reply_text("🚫 Bạn chưa được kích hoạt.")
        return

    if len(text) != 32 or not all(c in "0123456789abcdef" for c in text):
        await update.message.reply_text("⚠️ Mã MD5 không hợp lệ.")
        return

    result, total = md5_to_tai_xiu(text)
    if result == "Lỗi":
        await update.message.reply_text("❌ Phân tích thất bại.")
        return

    # Cập nhật thống kê
    stats = user_stats.get(user_id, {"win": 0, "lose": 0})
    if result == "Tài":
        stats["win"] += 1
    else:
        stats["lose"] += 1
    user_stats[user_id] = stats

    total_games = stats["win"] + stats["lose"]
    win_rate = (stats["win"] / total_games) * 100 if total_games else 0
    lose_rate = 100 - win_rate
    suggestion = "✅ NÊN THEO!" if win_rate >= 60 else "⚠️ KHÔNG NÊN THEO!"

    await update.message.reply_text(
        f"🔍 Phân tích mã: `{text}`\n"
        f"➤ Tổng cuối: {total}\n"
        f"🎲 Kết quả: *{result}*\n\n"
        f"📊 Tỷ lệ thắng: {win_rate:.2f}%\n"
        f"📉 Tỷ lệ thua: {lose_rate:.2f}%\n"
        f"{suggestion}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Thống kê", callback_data="stats")]
        ])
    )

# Main bot
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("active", active))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze))

    print("🤖 Bot đã khởi động!")
    app.run_polling()

if __name__ == "__main__":
    main()

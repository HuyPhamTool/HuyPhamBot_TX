from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
import hashlib
import json

# ==== QUẢN LÝ KEY ====
admin_id = 7505331567  # Thay bằng Telegram ID admin
allowed_users = set()

# ==== LƯU TỶ LỆ THẮNG ====
stats = {
    'win': 0,
    'lose': 0
}

# ==== HÀM PHÂN TÍCH MD5 ====
def md5_to_tai_xiu(md5: str):
    try:
        last_5 = md5[-5:]
        total = int(last_5, 16) % 14 + 3  # Tổng từ 3 đến 18
        result = 'Tài' if total >= 11 else 'Xỉu'
        return total, result
    except:
        return None, None

# ==== PHÂN TÍCH VÀ TÍNH TỶ LỆ ====
def analyze_md5(md5):
    total, result = md5_to_tai_xiu(md5)
    if result == 'Tài':
        stats['win'] += 1
    else:
        stats['lose'] += 1

    total_games = stats['win'] + stats['lose']
    win_rate = round((stats['win'] / total_games) * 100, 2) if total_games > 0 else 0
    lose_rate = 100 - win_rate
    suggest = '📈 NÊN THEO!' if win_rate >= 50 else '📉 KHÔNG NÊN THEO'

    return total, result, win_rate, lose_rate, suggest

# ==== XỬ LÝ LỆNH /start ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in allowed_users:
        await update.message.reply_text("🚫 Bạn chưa được kích hoạt để sử dụng bot.")
        return

    await update.message.reply_text(
        "👋 Gửi mã MD5 để phân tích Tài/Xỉu",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 Thống kê", callback_data="stats")
        ]])
    )

# ==== NHẬP MÃ MD5 ====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in allowed_users:
        await update.message.reply_text("🚫 Bạn chưa được kích hoạt để sử dụng bot.")
        return

    md5 = update.message.text.strip()
    if len(md5) != 32:
        await update.message.reply_text("❌ Mã MD5 không hợp lệ. Hãy nhập lại!")
        return

    total, result, win_rate, lose_rate, suggest = analyze_md5(md5)
    await update.message.reply_text(
        f"📥 Mã: {md5}\n"
        f"🎯 Tổng: {total}\n"
        f"🎲 Kết quả: {result} {'✅' if result == 'Tài' else '🟥'}\n\n"
        f"📊 Tỷ lệ thắng: {win_rate}%\n"
        f"📉 Tỷ lệ thua: {lose_rate}%\n"
        f"💡 Gợi ý: {suggest}"
    )

# ==== THỐNG KÊ ====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    win = stats['win']
    lose = stats['lose']
    total = win + lose
    win_rate = round((win / total) * 100, 2) if total > 0 else 0
    lose_rate = 100 - win_rate

    await query.edit_message_text(
        f"📊 Thống kê hiện tại:\n"
        f"✔️ Thắng: {win}\n"
        f"❌ Thua: {lose}\n"
        f"📈 Tỷ lệ thắng: {win_rate}%\n"
        f"📉 Tỷ lệ thua: {lose_rate}%"
    )

# ==== ADMIN THÊM NGƯỜI DÙNG ====
async def add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return

    if len(context.args) != 1:
        await update.message.reply_text("❗ Dùng: /addkey user_id")
        return

    user_id = int(context.args[0])
    allowed_users.add(user_id)
    await update.message.reply_text(f"✅ Đã kích hoạt cho ID: {user_id}")

# ==== CHẠY BOT ====
if __name__ == '__main__':
    import os
    TOKEN = os.getenv("7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8")  # Đặt biến môi trường hoặc nhập trực tiếp

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addkey", add_key))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    app.run_polling()

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import hashlib
from itertools import product
import random

# Giao diện menu
main_menu = ReplyKeyboardMarkup([["/phantich", "/dukien"]], resize_keyboard=True)

# Hàm hash MD5
def md5_hash(s):
    return hashlib.md5(s.encode()).hexdigest()

# Phân tích MD5 nếu có key
def crack_md5(md5_target, secret_key):
    for combo in product(range(1, 7), repeat=3):
        test_str = f"{combo[0]},{combo[1]},{combo[2]}|{secret_key}"
        if md5_hash(test_str) == md5_target:
            total = sum(combo)
            return f"""
🎲 Xúc xắc: {combo}
➕ Tổng: {total}
📌 Kết quả: {"Tài" if total >= 11 else "Xỉu"}
🔐 Chuỗi: {test_str}
"""
    return "❌ Không tìm thấy kết quả phù hợp."

# AI dự đoán kết quả từ lịch sử
def smart_predict(history):
    if not history:
        return "🤔 Bạn chưa có lịch sử để dự đoán!"
    count_tai = sum(1 for x in history if x >= 11)
    count_xiu = len(history) - count_tai
    if count_xiu > count_tai:
        return "🔮 Dự đoán: **Tài** (theo xu hướng gần đây)"
    else:
        return "🔮 Dự đoán: **Xỉu** (theo xu hướng gần đây)"

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Xin chào! Bot hỗ trợ phân tích tài/xỉu từ mã MD5.\n\n"
        "📌 Gửi /phantich để phân tích từ MD5 + secret_key.\n"
        "📈 Gửi /dukien để bot dự đoán Tài/Xỉu theo lịch sử.\n",
        reply_markup=main_menu
    )

# /phandoan
async def phandoan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Gửi mã MD5 để bắt đầu phân tích.")
    context.user_data['mode'] = 'phandoan'

# /dukien
async def dukien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = context.user_data.get('history', [])
    await update.message.reply_text(smart_predict(history))

# Xử lý tin nhắn
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if context.user_data.get('mode') == 'phandoan':
        if 'md5' not in context.user_data:
            if len(text) == 32 and all(c in '0123456789abcdef' for c in text.lower()):
                context.user_data['md5'] = text
                await update.message.reply_text("🔐 Gửi secret_key để bot phân tích...")
            else:
                await update.message.reply_text("⚠️ Vui lòng gửi mã MD5 hợp lệ (32 ký tự hex).")
        else:
            secret_key = text.strip()
            await update.message.reply_text("⏳ Đang phân tích...")
            result = crack_md5(context.user_data['md5'], secret_key)
            await update.message.reply_text(result)

            # Lưu lịch sử nếu giải thành công
            if "Xúc xắc" in result:
                lines = result.splitlines()
                for line in lines:
                    if "Tổng:" in line:
                        try:
                            total = int(line.split(":")[1].strip())
                            history = context.user_data.get('history', [])
                            history.append(total)
                            if len(history) > 20:  # chỉ lưu 20 kết quả gần nhất
                                history = history[-20:]
                            context.user_data['history'] = history
                        except: pass

            context.user_data.clear()
    else:
        await update.message.reply_text("📌 Hãy chọn chức năng bằng menu hoặc gõ /start.")

# MAIN
if __name__ == '__main__':
    TOKEN = "7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8"  # Thay bằng token của bạn
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("phantich", phandoan))
    app.add_handler(CommandHandler("dukien", dukien))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 Bot Telegram tài/xỉu đang hoạt động...")
    app.run_polling()

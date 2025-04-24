from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import random, string

# Danh sách key hợp lệ (giả lập) và key của admin
valid_keys = {"key123", "vipkey456"}
admin_id = 7505331567  # Thay bằng Telegram user ID thật của bạn

# Lưu người dùng đã nhập key
user_keys = {}

# Phân tích mã MD5 ra Tài/Xỉu
# Phân tích mã MD5 ra Tài/Xỉu
def phan_tich_md5(md5_code):
    try:
        hex_part = md5_code[-5:]
        decimal = int(hex_part, 16)
        digits = [int(d) for d in str(decimal)[-3:]]
        total = sum(digits)
        result = "Tài" if total >= 11 else "Xỉu"
        return (
            f"🎲 Phân tích MD5: {md5_code}\n"
            f"➡ Hex cuối: {hex_part} → {decimal}\n"
            f"➡ 3 số cuối: {' + '.join(map(str, digits))} = {total}\n"
            f"🎯 Kết quả: {result}"
        )
    except:
        return "⚠️ Mã MD5 không hợp lệ."


# /start
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_keys:
        await update.message.reply_text("✅ Bạn đã kích hoạt key. Gửi mã MD5 để phân tích.")
    else:
        await update.message.reply_text("🔐 Nhập key để sử dụng bot. Gõ: /key <mã_key>")

# /key <mã_key>
async def nhap_key(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if len(context.args) == 0:
        await update.message.reply_text("❗ Dùng: /key <mã_key>")
        return
    key = context.args[0]
    if key in valid_keys:
        user_keys[user_id] = key
        await update.message.reply_text("✅ Kích hoạt key thành công! Gửi mã MD5 để phân tích.")
    else:
        await update.message.reply_text("❌ Key không hợp lệ.")

# /taokey (admin)
async def tao_key(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != admin_id:
        await update.message.reply_text("🚫 Bạn không có quyền tạo key.")
        return
    new_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    valid_keys.add(new_key)
    await update.message.reply_text(f"🔑 Key mới: `{new_key}`", parse_mode="Markdown")

# Phân tích MD5 khi người dùng gửi
async def xu_ly_md5(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if user_id not in user_keys:
        await update.message.reply_text("🔐 Bạn cần nhập key trước. Gõ: /key <mã_key>")
        return
    if len(text) == 32 and all(c in string.hexdigits for c in text):
        kq = phan_tich_md5(text)
        await update.message.reply_text(kq)
    else:
        await update.message.reply_text("⚠️ Hãy gửi đúng 1 mã MD5 (32 ký tự).")

def main():
    application = Application.builder().token("7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8").build()  # Thay bằng token thật

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("key", nhap_key))
    application.add_handler(CommandHandler("taokey", tao_key))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, xu_ly_md5))

    application.run_polling()

if __name__ == '__main__':
    main()

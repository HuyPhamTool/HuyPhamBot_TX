from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import random, string

# Danh sách key hợp lệ (giả lập) và key của admin
valid_keys = {"key123", "vipkey456"}
admin_id = 7505331567  # Thay bằng Telegram user ID thật của bạn

# Lưu người dùng đã nhập key
user_keys = {}

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
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_keys:
        update.message.reply_text("✅ Bạn đã kích hoạt key. Gửi mã MD5 để phân tích.")
    else:
        update.message.reply_text("🔐 Nhập key để sử dụng bot. Gõ: /key <mã_key>")

# /key <mã_key>
def nhap_key(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if len(context.args) == 0:
        update.message.reply_text("❗ Dùng: /key <mã_key>")
        return
    key = context.args[0]
    if key in valid_keys:
        user_keys[user_id] = key
        update.message.reply_text("✅ Kích hoạt key thành công! Gửi mã MD5 để phân tích.")
    else:
        update.message.reply_text("❌ Key không hợp lệ.")

# /taokey (admin)
def tao_key(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != admin_id:
        update.message.reply_text("🚫 Bạn không có quyền tạo key.")
        return
    new_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    valid_keys.add(new_key)
    update.message.reply_text(f"🔑 Key mới: `{new_key}`", parse_mode="Markdown")

# Phân tích MD5 khi người dùng gửi
def xu_ly_md5(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if user_id not in user_keys:
        update.message.reply_text("🔐 Bạn cần nhập key trước. Gõ: /key <mã_key>")
        return
    if len(text) == 32 and all(c in string.hexdigits for c in text):
        kq = phan_tich_md5(text)
        update.message.reply_text(kq)
    else:
        update.message.reply_text("⚠️ Hãy gửi đúng 1 mã MD5 (32 ký tự).")

def main():
    updater = Updater("7749085860:AAE0Hdk-D3OIGb3KjfT9fu5N6Lr7xvAqny8", use_context=True)  # Thay bằng token thật
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("key", nhap_key))
    dp.add_handler(CommandHandler("taokey", tao_key))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, xu_ly_md5))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

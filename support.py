import os
import logging
from dotenv import load_dotenv
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackContext, ContextTypes, filters, CallbackQueryHandler
)
from pymongo import MongoClient
from datetime import datetime

load_dotenv()

# --- ENV CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MONGO INIT ---
client = MongoClient(MONGO_URI)
db = client["support_bot"]
messages = db["messages"]
temp_reply = {}  # user_id: replied_user_id

# --- START COMMAND ---
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    if user.id == OWNER_ID:
        await update.message.reply_text("👑 Selamat datang Admin. Gunakan /inbox untuk melihat pesan.")
    else:
        await update.message.reply_text(
            "🆘 *Bantuan Support*\n\nSilakan ketik atau kirim pesan ke admin. Kami akan membalas secepatnya.",
            parse_mode="Markdown"
        )

# --- HANDLE INCOMING MESSAGE ---
async def handle_message(update: Update, context: CallbackContext):
    user = update.effective_user
    message = update.message

    # Jika owner sedang membalas
    if user.id == OWNER_ID and user.id in temp_reply:
        target_id = temp_reply[user.id]
        await forward_message_to_user(message, target_id, context)
        del temp_reply[user.id]
        return

    # Simpan pesan ke DB dan tampilkan ke admin
    messages.insert_one({
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "text": message.text or None,
        "media": True if message.photo or message.video or message.voice or message.document or message.sticker else False,
        "date": datetime.utcnow()
    })

    if user.id != OWNER_ID:
        await context.bot.send_message(
            OWNER_ID,
            f"✉️ Pesan baru dari [{user.first_name}](tg://user?id={user.id}):\n\n{text_preview(message)}",
            parse_mode="Markdown",
            reply_markup=reply_markup(user.id)
        )
        await message.reply_text("✅ Pesan kamu telah dikirim ke admin. Mohon tunggu balasan ya!")

# --- TEXT PREVIEW ---
def text_preview(message):
    if message.text:
        return message.text
    elif message.photo:
        return "[Foto]"
    elif message.video:
        return "[Video]"
    elif message.voice:
        return "[Voice]"
    elif message.document:
        return "[Dokumen]"
    elif message.sticker:
        return "[Stiker]"
    return "[Pesan]"

# --- REPLY KEYBOARD ---
def reply_markup(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Profil", callback_data=f"profile:{user_id}"),
         InlineKeyboardButton("💬 Balas", callback_data=f"reply:{user_id}")]
    ])

# --- CALLBACK HANDLER ---
async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("profile:"):
        uid = int(data.split(":")[1])
        user_data = await context.bot.get_chat(uid)
        text = f"👤 Profil Pengguna:\nID: {uid}\nUsername: @{user_data.username}\nNama: {user_data.full_name}"
        await query.message.reply_text(text)

    elif data.startswith("reply:"):
        uid = int(data.split(":")[1])
        temp_reply[update.effective_user.id] = uid
        await query.message.reply_text("✏️ Silakan ketik pesan balasan untuk pengguna.")

# --- FORWARD MEDIA TO USER ---
async def forward_message_to_user(message, user_id, context):
    try:
        if message.text:
            await context.bot.send_message(user_id, message.text)
        elif message.photo:
            await context.bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption or "")
        elif message.video:
            await context.bot.send_video(user_id, message.video.file_id, caption=message.caption or "")
        elif message.voice:
            await context.bot.send_voice(user_id, message.voice.file_id)
        elif message.document:
            await context.bot.send_document(user_id, message.document.file_id)
        elif message.sticker:
            await context.bot.send_sticker(user_id, message.sticker.file_id)
        await message.reply_text("✅ Balasan berhasil dikirim.")
        print(f"[OK] Balasan terkirim ke user {user_id}")
    except Exception as e:
        print(f"[ERROR] Gagal kirim ke {user_id} -> {e}")
        await message.reply_text("⚠️ Gagal mengirim balasan. Mungkin pengguna belum mulai bot atau telah memblokir bot.")

# --- INBOX COMMAND ---
async def inbox(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return
    cursor = messages.find().sort("date", -1).limit(10)
    if await messages.count_documents({}) == 0:
        await update.message.reply_text("📭 Tidak ada pesan masuk.")
        return
    for msg in cursor:
        text = f"🕓 {msg['date'].strftime('%Y-%m-%d %H:%M:%S')}\n👤 [{msg['first_name']}](tg://user?id={msg['user_id']})\n"
        text += f"💬 {msg['text'] if msg['text'] else '[Media]'}"
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup(msg['user_id']))

async def start_support_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inbox", inbox))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("🤖 Support Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

import os
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# --- Init ---
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["anon_chat"]
users = db["users"]
queue = []

logging.basicConfig(level=logging.INFO)

GENDER_KEYBOARD = [["Laki-laki", "Perempuan"]]
REPLY_KEYBOARD = [["🔍 Find a Partner", "👥 Search by Gender"], ["⚙️ Settings"]]

# --- TEXTS ---
TEXTS = {
    "start_lang": {
        "id": "🌐 Silakan pilih bahasa: 'id' (Indonesia) / 'en' (English)",
        "en": "🌐 Please choose language: 'id' (Indonesian) / 'en' (English)"
    },
    "set_gender": {
        "id": "👤 Silakan pilih jenis kelamin:",
        "en": "👤 Please select your gender:"
    },
    "saved": {
        "id": "✅ Disimpan.",
        "en": "✅ Saved."
    },
    "welcome": {
        "id": (
            "👋 Selamat datang di *Anonymous Chat Bot*!\n\n"
            "Kamu bisa mencari teman ngobrol secara anonim.\n\n"
            "Gunakan tombol berikut ini:\n\n"
            "📢 *Pasang iklan?* 👉 [Hubungi Admin](https://t.me/suppor2rsfbot)"
        ),
        "en": (
            "👋 Welcome to *Anonymous Chat Bot*!\n\n"
            "You can find anonymous chat partners.\n\n"
            "Use the buttons below:\n\n"
            "📢 *Want to advertise?* 👉 [Contact Admin](https://t.me/suppor2rsfbot)"
        )
    },
    "searching": {
        "id": (
            "⏳ Mencari partner...\n"
            "Ketik pesan untuk dikirim jika partner ditemukan.\n\n"
            "Gunakan /next untuk mencari partner baru atau /stop untuk membatalkan.\n\n"
            "📢 *Pasang iklan?* 👉 [Hubungi Admin](https://t.me/suppor2rsfbot)"
        ),
        "en": (
            "⏳ Searching for a partner...\n"
            "Type a message to send once a partner is found.\n\n"
            "Use /next to find a new partner or /stop to cancel.\n\n"
            "📢 *Want to advertise?* 👉 [Contact Admin](https://t.me/suppor2rsfbot)"
        )
    },
    "found": {
        "id": "Partner ditemukan 😺\n\n/next — cari partner baru\n/stop — akhiri chat",
        "en": "Partner found 😺\n\n/next — find new partner\n/stop — end chat"
    },
    "stopped": {
        "id": "❌ Chat dihentikan.",
        "en": "❌ Chat stopped."
    },
    "cancelled": {
        "id": "❌ Kamu keluar dari antrian.",
        "en": "❌ You have left the queue."
    },
    "not_in_queue": {
        "id": "⚠️ Kamu tidak sedang dalam antrian.",
        "en": "⚠️ You are not in the queue."
    },
    "reported": {
        "id": "✅ Partner telah dilaporkan dan diblokir.",
        "en": "✅ Partner has been reported and blocked."
    },
    "you_reported": {
        "id": "🚫 Kamu telah dilaporkan oleh partner.",
        "en": "🚫 You have been reported by your partner."
    },
    "choose_target_gender": {
        "id": "Pilih gender yang ingin dicari:",
        "en": "Choose the gender you want to chat with:"
    }
}
# --- Helper Functions ---
def t(lang, key):
    return TEXTS.get(key, {}).get(lang, TEXTS.get(key, {}).get("id", key))

def get_user(user_id):
    user = users.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "gender": None, "language": None, "state": "idle", "partner": None, "blocked": [],
                "photo": True, "video": True, "sticker": True, "voice": True, "age": None}
        users.insert_one(user)
    return user

def update_user(user_id, data):
    users.update_one({"_id": user_id}, {"$set": data})

def match_partner(user_id):
    current = get_user(user_id)
    for partner_id in queue:
        partner = get_user(partner_id)
        if partner["state"] == "searching" and partner["language"] == current["language"] and \
           partner_id != user_id and user_id not in partner.get("blocked", []) and partner_id not in current.get("blocked", []):
            queue.remove(partner_id)
            update_user(user_id, {"state": "chatting", "partner": partner_id})
            update_user(partner_id, {"state": "chatting", "partner": user_id})
            return partner_id
    if user_id not in queue:
        queue.append(user_id)
    update_user(user_id, {"state": "searching"})
    return None

def match_partner_by_gender(user_id, target_gender):
    current = get_user(user_id)
    for partner_id in queue:
        partner = get_user(partner_id)
        if partner["state"] == "searching" and partner["language"] == current["language"] and \
           partner["gender"] == target_gender and partner_id != user_id and \
           user_id not in partner.get("blocked", []) and partner_id not in current.get("blocked", []):
            queue.remove(partner_id)
            update_user(user_id, {"state": "chatting", "partner": partner_id})
            update_user(partner_id, {"state": "chatting", "partner": user_id})
            return partner_id
    if user_id not in queue:
        queue.append(user_id)
    update_user(user_id, {"state": "searching"})
    return None

# (Lanjutan dari sebelumnya)

# --- Handlers ---
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user.get("language"):
        await update.message.reply_text(TEXTS["start_lang"]["id"])
        update_user(user_id, {"state": "awaiting_lang"})
        return

    lang = user["language"]
    if not user.get("gender"):
        await update.message.reply_text(t(lang, "set_gender"), reply_markup=ReplyKeyboardMarkup(GENDER_KEYBOARD, resize_keyboard=True))
        return

    await update.message.reply_text(
        t(lang, "welcome"), parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(REPLY_KEYBOARD, resize_keyboard=True)
    )

async def message_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = user.get("language") or "id"

    # Deteksi user baru yang belum pilih bahasa
    if not user.get("language"):
        update_user(user_id, {"state": "awaiting_lang"})
        await update.message.reply_text(TEXTS["start_lang"]["id"])
        return

    text = (update.message.text or "").strip().lower()

    if update.message.text == "⚙️ Settings":
        await settings(update, context)
        return

    if user["state"] == "awaiting_lang":
        if text in ["id", "indonesia"]:
            update_user(user_id, {"language": "id", "state": "idle"})
            await update.message.reply_text("✅ Bahasa diatur ke Indonesia.")
            await start(update, context)
        elif text in ["en", "english"]:
            update_user(user_id, {"language": "en", "state": "idle"})
            await update.message.reply_text("✅ Language set to English.")
            await start(update, context)
        else:
            await update.message.reply_text("❌ Invalid. Type 'id' or 'en'.")
        return

    if update.message.text in ["laki-laki", "perempuan"]:
        update_user(user_id, {"gender": text})
        await update.message.reply_text(t(lang, "saved"), reply_markup=ReplyKeyboardMarkup(REPLY_KEYBOARD, resize_keyboard=True))
        return

    if update.message.text == "🔍 Find a Partner":
        partner_id = match_partner(user_id)
        if partner_id:
            await context.bot.send_message(user_id, t(lang, "found"))
            await context.bot.send_message(partner_id, t(lang, "found"))
        else:
            await update.message.reply_text(t(lang, "searching"))
        return

    if update.message.text == "👥 Search by Gender":
        await update.message.reply_text(t(lang, "choose_target_gender"), reply_markup=ReplyKeyboardMarkup(GENDER_KEYBOARD, resize_keyboard=True))
        update_user(user_id, {"state": "search_gender"})
        return

    if user["state"] == "search_gender" and text in ["laki-laki", "perempuan"]:
        partner_id = match_partner_by_gender(user_id, text)
        update_user(user_id, {"state": "idle"})
        if partner_id:
            await context.bot.send_message(user_id, t(lang, "found"))
            await context.bot.send_message(partner_id, t(lang, "found"))
        else:
            await update.message.reply_text(t(lang, "searching"))
        return

    if text == "/stop" or text == "/next":
        partner_id = user.get("partner")
        if partner_id:
            update_user(partner_id, {"state": "idle", "partner": None})
            partner_lang = get_user(partner_id).get("language", "id")
            await context.bot.send_message(partner_id, t(partner_lang, "stopped"))
        update_user(user_id, {"state": "idle", "partner": None})
        if text == "/next":
            partner_id = match_partner(user_id)
            if partner_id:
                await context.bot.send_message(user_id, t(lang, "found"))
                await context.bot.send_message(partner_id, t(lang, "found"))
            else:
                await update.message.reply_text(t(lang, "searching"))
        else:
            await update.message.reply_text(t(lang, "stopped"))
        return

    if text == "/cancel":
        if user_id in queue:
            queue.remove(user_id)
            update_user(user_id, {"state": "idle"})
            await update.message.reply_text(t(lang, "cancelled"))
        else:
            await update.message.reply_text(t(lang, "not_in_queue"))
        return

    if text == "/report":
        partner_id = user.get("partner")
        if partner_id:
            update_user(user_id, {"blocked": user.get("blocked", []) + [partner_id]})
            update_user(user_id, {"state": "idle", "partner": None})
            update_user(partner_id, {"state": "idle", "partner": None})
            partner_lang = get_user(partner_id).get("language", "id")
            await context.bot.send_message(user_id, t(lang, "reported"))
            await context.bot.send_message(partner_id, t(partner_lang, "you_reported"))
        return

    # Kirim pesan antar user jika sedang chatting
    if user["state"] == "chatting" and user.get("partner"):
        partner_id = user["partner"]
        if update.message.text:
            await context.bot.send_message(partner_id, update.message.text)
        elif update.message.photo:
            await context.bot.send_photo(partner_id, update.message.photo[-1].file_id)
        elif update.message.video:
            await context.bot.send_video(partner_id, update.message.video.file_id)
        elif update.message.voice:
            await context.bot.send_voice(partner_id, update.message.voice.file_id)
        elif update.message.sticker:
            await context.bot.send_sticker(partner_id, update.message.sticker.file_id)

# --- Settings Handler ---
async def settings(update: Update, context: CallbackContext):
    user = get_user(update.effective_user.id)
    lang = user.get("language", "id")
    keyboard = [
        [InlineKeyboardButton("🧑 Jenis Kelamin", callback_data="set_gender"),
         InlineKeyboardButton("🔞 Usia", callback_data="set_age")],
        [InlineKeyboardButton(f"📷 Foto: {'✅' if user.get('photo', True) else '❌'}", callback_data="toggle_photo"),
         InlineKeyboardButton(f"🎥 Video: {'✅' if user.get('video', True) else '❌'}", callback_data="toggle_video")],
        [InlineKeyboardButton(f"🎭 Stiker: {'✅' if user.get('sticker', True) else '❌'}", callback_data="toggle_sticker"),
         InlineKeyboardButton(f"🎤 Voice: {'✅' if user.get('voice', True) else '❌'}", callback_data="toggle_voice")],
        [InlineKeyboardButton("✅ Aktifkan Semua", callback_data="enable_all"),
         InlineKeyboardButton("❌ Blokir Semua", callback_data="disable_all")],
        [InlineKeyboardButton("🌐 Bahasa", callback_data="set_lang")]
    ]
    await update.message.reply_text("⚙️ Pengaturan Media:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Callback Handler ---
async def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    lang = user.get("language", "id")
    data = query.data

    toggles = {
        "toggle_photo": "photo",
        "toggle_video": "video",
        "toggle_sticker": "sticker",
        "toggle_voice": "voice"
    }

    if data in toggles:
        field = toggles[data]
        new_value = not user.get(field, True)
        update_user(user_id, {field: new_value})
    elif data == "enable_all":
        update_user(user_id, {"photo": True, "video": True, "sticker": True, "voice": True})
    elif data == "disable_all":
        update_user(user_id, {"photo": False, "video": False, "sticker": False, "voice": False})
    elif data == "set_gender":
        await context.bot.send_message(user_id, t(lang, "set_gender"), reply_markup=ReplyKeyboardMarkup(GENDER_KEYBOARD, resize_keyboard=True))
        return
    elif data == "set_age":
        update_user(user_id, {"state": "awaiting_age"})
        await context.bot.send_message(user_id, "Masukkan usia kamu (contoh: 20):")
        return
    elif data == "set_lang":
        update_user(user_id, {"state": "awaiting_lang"})
        await context.bot.send_message(user_id, TEXTS["start_lang"][lang])
        return

    updated_user = get_user(user_id)
    keyboard = [
        [InlineKeyboardButton("🧑 Jenis Kelamin", callback_data="set_gender"),
         InlineKeyboardButton("🔞 Usia", callback_data="set_age")],
        [InlineKeyboardButton(f"📷 Foto: {'✅' if updated_user.get('photo', True) else '❌'}", callback_data="toggle_photo"),
         InlineKeyboardButton(f"🎥 Video: {'✅' if updated_user.get('video', True) else '❌'}", callback_data="toggle_video")],
        [InlineKeyboardButton(f"🎭 Stiker: {'✅' if updated_user.get('sticker', True) else '❌'}", callback_data="toggle_sticker"),
         InlineKeyboardButton(f"🎤 Voice: {'✅' if updated_user.get('voice', True) else '❌'}", callback_data="toggle_voice")],
        [InlineKeyboardButton("✅ Aktifkan Semua", callback_data="enable_all"),
         InlineKeyboardButton("❌ Blokir Semua", callback_data="disable_all")],
        [InlineKeyboardButton("🌐 Bahasa", callback_data="set_lang")]
    ]
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()
    from telegram.ext import ApplicationBuilder

async def start_anon_bot():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", message_handler))
    app.add_handler(CommandHandler("report", message_handler))
    app.add_handler(CommandHandler("stop", message_handler))
    app.add_handler(CommandHandler("next", message_handler))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🤖 Anonymous Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()


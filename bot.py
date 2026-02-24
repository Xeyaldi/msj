import os
import random
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient

# --- KONFİQURASİYA (Heroku Config Vars) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")

BOT_KANAL_URL = os.environ.get("BOT_KANAL_URL", "https://t.me/SeninKanalin")
MUSIC_BOT_URL = os.environ.get("MUSIC_BOT_URL", "https://t.me/MisalMusicBot")

# --- MONGODB ---
cluster = MongoClient(MONGO_URL)
db = cluster["MessageScorBot"]
collection = db["scores"]

app = Client("ScoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DÜYMƏLƏR ---

def get_start_buttons():
    """Əsas menyu düymələri"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Komandalar", callback_data="open_commands")],
        [InlineKeyboardButton("📢 Bot Kanalı", url=BOT_KANAL_URL),
         InlineKeyboardButton("🎵 Musiqi Botu", url=MUSIC_BOT_URL)],
        [InlineKeyboardButton("➕ Məni Qrupa Əlavə Et", url=f"https://t.me/{(app.get_me()).username}?startgroup=true")]
    ])

def get_command_help_buttons():
    """Komandalar bölməsindəki düymələr"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Geri", callback_data="back_to_start")]
    ])

def get_top_buttons():
    """Qruplardakı top menyusu düymələri (Silinmədi)"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Gündəlik", callback_data="top_daily"),
            InlineKeyboardButton("🗓️ Həftəlik", callback_data="top_weekly"),
            InlineKeyboardButton("📆 Aylıq", callback_data="top_monthly")
        ],
        [InlineKeyboardButton("📊 Bütün zamanlarda", callback_data="top_total")],
        [InlineKeyboardButton("📢 Bot Kanalı", url=BOT_KANAL_URL),
         InlineKeyboardButton("🎵 Musiqi Botu", url=MUSIC_BOT_URL)]
    ])

# --- TOP SİYAHI (Silinmədi) ---

def generate_top_text(chat_id, category_key, title):
    top_users = collection.find({"chat_id": chat_id}).sort(category_key, -1).limit(13)
    response = f"🏆 **{title} Aktiv İstifadəçilər**\n"
    response += "──────────────────────\n"
    found = False
    for i, user in enumerate(top_users, 1):
        score = user.get(category_key, 0)
        if score == 0: continue
        found = True
        name = user.get('first_name', 'İstifadəçi')
        response += f"{i}. **{name}** — `{score}` mesaj\n"
    
    if not found:
        return f"❌ **{title}** üzrə hələ ki, məlumat yoxdur."
    
    response += "──────────────────────\n💬 *Mesaj yazaraq reytinqə gir!*"
    return response

# --- RESET (SIFIRLAMA) (Silinmədi) ---
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: collection.update_many({}, {"$set": {"daily": 0}}), 'cron', hour=0, minute=0)
scheduler.add_job(lambda: collection.update_many({}, {"$set": {"weekly": 0}}), 'cron', day_of_week='mon', hour=0, minute=0)
scheduler.add_job(lambda: collection.update_many({}, {"$set": {"monthly": 0}}), 'cron', day=1, hour=0, minute=0)
scheduler.start()

# --- KOMANDALAR ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    # Bot menyusunu ( / işarəsi ) qurmaq
    await client.set_bot_commands([
        BotCommand("start", "Botu başladın"),
        BotCommand("top", "Qrup reytinqi"),
        BotCommand("help", "Kömək menyusu")
    ])

    if message.chat.type == types.enums.ChatType.PRIVATE:
        text = (
            "👋 **Salam! Mən Mesaj Sayğacı Botuyam.**\n\n"
            "Məni qrupunuza əlavə edərək aktivliyi ölçə bilərsiniz. "
            "Komandalar və istifadə qaydası üçün aşağıdakı düyməyə baxın."
        )
        await message.reply_text(text, reply_markup=get_start_buttons())
    else:
        # Qrupda start verilərsə birbaşa reytinq menyusu açılsın
        await top_command(client, message)

@app.on_message(filters.command("top") & filters.group)
async def top_command(client, message):
    text = f"👥 **{message.chat.title}** üçün sıralama növünü seçin:"
    await message.reply_text(text, reply_markup=get_top_buttons())

@app.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = "📖 **Bot Komandaları:**\n\n/top - Reytinq menyusu\n/help - Kömək\n/start - Botu başlat"
    await message.reply_text(help_text)

# --- CALLBACK HANDLER (Düymələrin işləməsi) ---

@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    if query.data == "open_commands":
        # Komandalar menyusuna keçid
        help_text = (
            "📖 **Komandalar menyusu:**\n\n"
            "🔹 `/top` - Qrupda mesaj reytinqini göstərir.\n"
            "🔹 `/start` - Botun əsas menyusunu açır.\n"
            "🔹 `/help` - Kömək mətni göstərir.\n\n"
            "📌 **Qeyd:** Bot hər 130 və 800 mesajda sizi təbrik edir!"
        )
        await query.edit_message_text(help_text, reply_markup=get_command_help_buttons())
    
    elif query.data == "back_to_start":
        # Əsas menyuya geri qayıdış
        text = "👋 **Salam! Mən Mesaj Sayğacı Botuyam.**\n\nİstifadə qaydası üçün düymələrdən istifadə edin."
        await query.edit_message_text(text, reply_markup=get_start_buttons())
    
    elif query.data.startswith("top_"):
        # Top siyahıların göstərilməsi (Silinmədi)
        data = query.data.split("_")[1]
        titles = {"daily": "Günlük", "weekly": "Həftəlik", "monthly": "Aylıq", "total": "Toplam"}
        new_text = generate_top_text(query.message.chat.id, data, titles[data])
        try:
            await query.edit_message_text(new_text, reply_markup=get_top_buttons())
        except:
            await query.answer("Siyahı artıq ən son vəziyyətdədir.")

# --- SAYĞAC (Silinmədi) ---

@app.on_message(filters.group & ~filters.bot & ~filters.command(["start", "top", "help"]))
async def message_handler(client, message):
    if not message.from_user: return
    
    u_id = message.from_user.id
    c_id = message.chat.id
    name = message.from_user.first_name

    user_data = collection.find_one_and_update(
        {"user_id": u_id, "chat_id": c_id},
        {"$inc": {"daily": 1, "weekly": 1, "monthly": 1, "total": 1}, "$set": {"first_name": name}},
        upsert=True,
        return_document=True
    )

    total = user_data.get("total", 0)
    # Təbrik mesajları (Silinmədi)
    if total == 130:
        await message.reply_text(f"Afərin {name}, 130 mesajı tamamladın! 🎊")
    elif total == 800:
        await message.reply_text(f"Vay! {name} tam 800 mesaj yazdı! 🏆")

app.run()

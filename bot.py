import os
import random
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from pyrogram.enums import ChatType # Heroku xətası üçün vacib əlavə
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient

# --- KONFİQURASİYA ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
OWNER_ID = 123456789 # Öz ID-ni bura yaz

BOT_KANAL_URL = os.environ.get("BOT_KANAL_URL", "https://t.me/SeninKanalin")
MUSIC_BOT_URL = os.environ.get("MUSIC_BOT_URL", "https://t.me/MisalMusicBot")

cluster = MongoClient(MONGO_URL)
db = cluster["MessageScorBot"]
collection = db["scores"]

app = Client("ScoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DÜYMƏLƏR ---

async def get_start_buttons():
    me = await app.get_me()
    bot_username = me.username
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Komandalar", callback_data="open_commands")],
        [InlineKeyboardButton("📢 Bot Kanalı", url=BOT_KANAL_URL),
         InlineKeyboardButton("🎵 Musiqi Botu", url=MUSIC_BOT_URL)],
        [InlineKeyboardButton("➕ Məni Qrupa Əlavə Et", url=f"https://t.me/{bot_username}?startgroup=true")]
    ])

def get_command_help_buttons():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Geri", callback_data="back_to_start")]])

def get_top_buttons():
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

# --- GÜNÜN QALİBİNİ ELAN EDƏN FUNKSİYA ---
def announce_winner():
    all_chats = collection.distinct("chat_id")
    for c_id in all_chats:
        winner = list(collection.find({"chat_id": c_id}).sort("daily", -1).limit(1))
        if winner and winner[0].get("daily", 0) > 0:
            user = winner[0]
            try:
                app.send_message(c_id, f"🏆 **Günün Qalibi Elan Edildi!**\n\n👤 **{user['first_name']}** bu gün tam `{user['daily']}` mesaj yazaraq günün birincisi oldu! 🎉")
            except: pass

# --- TOP SİYAHI (Medallar və Şəxsi Statistik) ---

def generate_top_text(chat_id, user_id, category_key, title):
    top_users = collection.find({"chat_id": chat_id}).sort(category_key, -1).limit(13)
    response = f"🏆 **{title} Aktiv İstifadəçilər**\n"
    response += "──────────────────────\n"
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    found = False
    for i, user in enumerate(top_users, 1):
        score = user.get(category_key, 0)
        if score == 0: continue
        found = True
        name = user.get('first_name', 'İstifadəçi')
        
        icon = medals.get(i, "🔸")
        response += f"{icon} {i}. **{name}** — `{score}` msg\n"
    
    if not found:
        return f"❌ **{title}** üzrə hələ ki, məlumat yoxdur."
    
    # Siyahını açan adamın statistikası
    requester = collection.find_one({"user_id": user_id, "chat_id": chat_id})
    req_score = requester.get(category_key, 0) if requester else 0
    
    response += "──────────────────────\n"
    response += f"📊 Sənin {title.lower()} mesaj sayın: `{req_score}`\n"
    response += "💬 *Mesaj yazaraq reytinqə gir!*"
    return response

# --- RESET (SIFIRLAMA) ---
scheduler = BackgroundScheduler()
scheduler.add_job(announce_winner, 'cron', hour=23, minute=59) 
scheduler.add_job(lambda: collection.update_many({}, {"$set": {"daily": 0}}), 'cron', hour=0, minute=0)
scheduler.add_job(lambda: collection.update_many({}, {"$set": {"weekly": 0}}), 'cron', day_of_week='mon', hour=0, minute=0)
scheduler.add_job(lambda: collection.update_many({}, {"$set": {"monthly": 0}}), 'cron', day=1, hour=0, minute=0)
scheduler.start()

# --- KOMANDALAR ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await client.set_bot_commands([
        BotCommand("start", "Botu başladın"),
        BotCommand("top", "Qrup reytinqi"),
        BotCommand("me", "Statistikanız"),
        BotCommand("help", "Kömək menyusu")
    ])

    if message.chat.type == ChatType.PRIVATE:
        text = (
            "🤖 **Salam! Mən Mesaj Sayğacı Botuyam.**\n\n"
            "Mən qruplardakı mesaj aktivliyini izləyirəm və reytinq siyahısı hazırlayıram.\n"
            "Aşağıdakı butonlardan istifadə edərək komandaları görə bilərsiniz."
        )
        buttons = await get_start_buttons()
        await message.reply_text(text, reply_markup=buttons)
    else:
        await top_command(client, message)

@app.on_message(filters.command("me") & filters.group)
async def me_command(client, message):
    user = collection.find_one({"user_id": message.from_user.id, "chat_id": message.chat.id})
    if user:
        text = (f"👤 **{message.from_user.first_name} Statistikası:**\n\n"
                f"📅 Gündəlik: `{user.get('daily', 0)}` mesaj\n"
                f"📊 Toplam: `{user.get('total', 0)}` mesaj")
        await message.reply_text(text)
    else:
        await message.reply_text("❌ Hələ ki, statistikəniz yoxdur.")

@app.on_message(filters.command("top") & filters.group)
async def top_command(client, message):
    text = f"👥 **{message.chat.title}** üçün sıralama növünü seçin:"
    await message.reply_text(text, reply_markup=get_top_buttons())

@app.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = "📖 **Bot Komandaları:**\n\n/top - Reytinq\n/me - Statistikanız\n/help - Kömək\n/start - Başlat"
    await message.reply_text(help_text, reply_markup=get_command_help_buttons())

@app.on_message(filters.command("resetall") & filters.user(OWNER_ID))
async def admin_reset(client, message):
    collection.delete_many({"chat_id": message.chat.id})
    await message.reply_text("🗑️ Bu qrupun bütün datası admin tərəfindən təmizləndi.")

# --- CALLBACK HANDLER ---

@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    if query.data == "open_commands":
        help_text = "📖 **Komandalar:**\n\n🔹 `/top` - Reytinq\n🔹 `/me` - Statistikanız\n🔹 `/help` - Kömək"
        await query.edit_message_text(help_text, reply_markup=get_command_help_buttons())
    
    elif query.data == "back_to_start":
        text = "🤖 **Salam! Mən Mesaj Sayğacı Botuyam.**"
        buttons = await get_start_buttons()
        await query.edit_message_text(text, reply_markup=buttons)
    
    elif query.data.startswith("top_"):
        data = query.data.split("_")[1]
        titles = {"daily": "Gündəlik", "weekly": "Həftəlik", "monthly": "Aylıq", "total": "Toplam"}
        new_text = generate_top_text(query.message.chat.id, query.from_user.id, data, titles[data])
        try:
            await query.edit_message_text(new_text, reply_markup=get_top_buttons())
        except:
            await query.answer("Siyahı artıq güncəldir.")

# --- SAYĞAC VƏ REAKSİYA ---

@app.on_message(filters.group & ~filters.bot & ~filters.command(["start", "top", "help", "me", "resetall"]))
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
    
    if total == 130 or total == 800:
        msg = await message.reply_text(f"Afərin {name}, {total} mesajı tamamladın! 🎊")
        try:
            await msg.react("🔥")
        except: pass

app.run()
        

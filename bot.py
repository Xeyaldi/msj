import os
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient

# Heroku Config Vars
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")  # MongoDB linkini buraya yazacaqsan
TAG_BOT_URL = os.environ.get("TAG_BOT_URL", "https://t.me/MisalTagBot")
MUSIC_BOT_URL = os.environ.get("MUSIC_BOT_URL", "https://t.me/MisalMusicBot")

# MongoDB Bağlantısı
cluster = MongoClient(MONGO_URL)
db = cluster["MessageScorBot"]
collection = db["scores"]

app = Client("ScoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Təbrik mesajları
congrats_130 = ["Afərin {}, 130 mesajı tamamladın! 🎊", "Super! {} artıq 130 mesaj yazdı! 🔥"]
congrats_800 = ["Vay! {} tam 800 mesaj yazdı! 🏆", "Rekord sənindir {}! 800 mesaj təbrik edirik! ✨"]

# Reset funksiyaları
def reset_daily():
    collection.update_many({}, {"$set": {"daily": 0}})

def reset_weekly():
    collection.update_many({}, {"$set": {"weekly": 0}})

def reset_monthly():
    collection.update_many({}, {"$set": {"monthly": 0}})

# Zamanlayıcı (Saat 00:00)
scheduler = BackgroundScheduler()
scheduler.add_job(reset_daily, 'cron', hour=0, minute=0)
scheduler.add_job(reset_weekly, 'cron', day_of_week='mon', hour=0, minute=0)
scheduler.add_job(reset_monthly, 'cron', day=1, hour=0, minute=0)
scheduler.start()

@app.on_message(filters.command("start"))
async def start(client, message):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷️ Tağ Botu", url=TAG_BOT_URL)],
        [InlineKeyboardButton("🎵 Musiqi Botu", url=MUSIC_BOT_URL)]
    ])
    text = (
        "📊 **Salam! Mən Mesaj Sayğacı Botuyam.**\n\n"
        "Qrupdakı mesaj aktivliyini qeyd edirəm və reytinq cədvəli hazırlayıram.\n"
        "Aktivliyi görmək üçün `/top` əmrindən istifadə edə bilərsiniz."
    )
    await message.reply_text(text, reply_markup=buttons)

@app.on_message(filters.group & ~filters.bot)
async def handle_msg(client, message):
    u_id = message.from_user.id
    c_id = message.chat.id
    name = message.from_user.first_name
    mention = f"[{name}](tg://user?id={u_id})"

    # İstifadəçini bazada tap və ya yarat
    user_data = collection.find_one({"user_id": u_id, "chat_id": c_id})

    if not user_data:
        collection.insert_one({
            "user_id": u_id, "chat_id": c_id, "first_name": name,
            "daily": 1, "weekly": 1, "monthly": 1, "total": 1
        })
        current_total = 1
    else:
        collection.update_one(
            {"user_id": u_id, "chat_id": c_id},
            {"$inc": {"daily": 1, "weekly": 1, "monthly": 1, "total": 1}, "$set": {"first_name": name}}
        )
        current_total = user_data["total"] + 1

    # Təbriklər
    if current_total == 130:
        await message.reply_text(random.choice(congrats_130).format(mention))
    elif current_total == 800:
        await message.reply_text(random.choice(congrats_800).format(mention))

@app.on_message(filters.command("top"))
async def show_top(client, message):
    # Top 13 çəkmək
    top_users = collection.find({"chat_id": message.chat.id}).sort("total", -1).limit(13)
    
    response = "🏆 **Toplam Top 13 Aktiv İstifadəçi:**\n\n"
    found = False
    for i, user in enumerate(top_users, 1):
        found = True
        m = f"[{user['first_name']}](tg://user?id={user['user_id']})"
        response += f"{i}. {m} : `{user['total']}` mesaj\n"
    
    if not found:
        return await message.reply_text("Hələ ki, məlumat yoxdur.")
        
    await message.reply_text(response, disable_web_page_preview=True)

app.run()

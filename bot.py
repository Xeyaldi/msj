import os
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient

# --- KONFİQURASİYA (Heroku Config Vars) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")

# Botun düymələrində istifadə olunacaq linklər
TAG_BOT_URL = os.environ.get("TAG_BOT_URL", "https://t.me/MisalTagBot")
MUSIC_BOT_URL = os.environ.get("MUSIC_BOT_URL", "https://t.me/MisalMusicBot")

# --- MONGODB BAĞLANTISI ---
cluster = MongoClient(MONGO_URL)
db = cluster["MessageScorBot"]
collection = db["scores"]

app = Client("ScoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- KÖMƏKÇİ FUNKSİYALAR ---

def get_top_buttons():
    """Bütün menyularda istifadə olunacaq düymə strukturunu hazırlayır"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Gündəlik", callback_data="top_daily"),
            InlineKeyboardButton("🗓️ Həftəlik", callback_data="top_weekly"),
            InlineKeyboardButton("📆 Aylıq", callback_data="top_monthly")
        ],
        [
            InlineKeyboardButton("📊 Bütün zamanlarda", callback_data="top_total")
        ],
        [
            InlineKeyboardButton("🏷️ Tağ Botu", url=TAG_BOT_URL),
            InlineKeyboardButton("🎵 Musiqi Botu", url=MUSIC_BOT_URL)
        ]
    ])

def generate_top_text(chat_id, category_key, title):
    """Bazada müvafiq kateqoriya üzrə ən aktiv 13 nəfəri tapıb mətn halına gətirir"""
    top_users = collection.find({"chat_id": chat_id}).sort(category_key, -1).limit(13)
    
    response = f"🏆 **{title} Aktiv İstifadəçilər**\n"
    response += "──────────────────────\n"
    
    found = False
    for i, user in enumerate(top_users, 1):
        score = user.get(category_key, 0)
        if score == 0:
            continue
        found = True
        # İstifadəçinin adını götürürük (mention-suz, sadəcə nick)
        first_name = user.get('first_name', 'Bilinməyən')
        # Siyahını formalaşdırırıq
        response += f"{i}. **{first_name}** — `{score}` mesaj\n"
    
    if not found:
        return f"❌ **{title}** üzrə hələ ki, heç bir aktivlik qeydə alınmayıb."
    
    response += "──────────────────────\n"
    response += "💬 *Mesaj yazaraq reytinqə daxil ola bilərsiniz!*"
    return response

# --- AVTOMATİK SIFIRLAMA (SCHEDULER) ---
# Bu hissə bazanı vaxtı-vaxtında təmizləyir ki, statistikalar düzgün olsun.

def reset_daily():
    collection.update_many({}, {"$set": {"daily": 0}})

def reset_weekly():
    collection.update_many({}, {"$set": {"weekly": 0}})

def reset_monthly():
    collection.update_many({}, {"$set": {"monthly": 0}})

scheduler = BackgroundScheduler()
# Hər gün gecə 00:00-da gündəlik sayğacı sıfırla
scheduler.add_job(reset_daily, 'cron', hour=0, minute=0)
# Hər bazar ertəsi gecə 00:00-da həftəlik sayğacı sıfırla
scheduler.add_job(reset_weekly, 'cron', day_of_week='mon', hour=0, minute=0)
# Hər ayın 1-i gecə 00:00-da aylıq sayğacı sıfırla
scheduler.add_job(reset_monthly, 'cron', day=1, hour=0, minute=0)
scheduler.start()

# --- ƏSAS KOMANDALAR ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    text = (
        "👋 **Salam! Mən Mesaj Sayğacı Botuyam.**\n\n"
        "Məni qrupunuza əlavə edərək aktivliyi izləyə bilərsiniz.\n"
        "İstifadəçilərin yazdığı mesajları sayaraq reytinq cədvəli qururam."
    )
    await message.reply_text(text, reply_markup=get_top_buttons())

@app.on_message(filters.command("top") & filters.group)
async def top_command(client, message):
    # Bu mesaj düymələrlə birlikdə gəlir
    text = f"👥 **{message.chat.title}** qrupu üçün sıralama növünü seçin:"
    await message.reply_text(text, reply_markup=get_top_buttons())

# --- DÜYMƏLƏRİN İŞLƏMƏSİ (CALLBACK QUERY) ---

@app.on_callback_query(filters.regex("^top_"))
async def callback_handler(client, query: CallbackQuery):
    # Hansı düyməyə basıldığını tapırıq
    category_raw = query.data.split("_")[1]
    
    mapping = {
        "daily": ("daily", "Günlük"),
        "weekly": ("weekly", "Həftəlik"),
        "monthly": ("monthly", "Aylıq"),
        "total": ("total", "Toplam")
    }
    
    key, title = mapping.get(category_raw)
    new_text = generate_top_text(query.message.chat.id, key, title)
    
    # Əgər mövcud mətn dəyişibsə, mesajı redaktə et
    try:
        await query.edit_message_text(new_text, reply_markup=get_top_buttons())
    except Exception:
        # Eyni düyməyə təkrar basanda xəta verməməsi üçün
        await query.answer("Siyahı artıq ən son vəziyyətdədir.")

# --- MESAJLARIN SAYILMASI (HANDLE MESSAGES) ---

@app.on_message(filters.group & ~filters.bot & ~filters.command(["start", "top"]))
async def message_handler(client, message):
    if not message.from_user:
        return
    
    u_id = message.from_user.id
    c_id = message.chat.id
    name = message.from_user.first_name

    # Bazada məlumatları yeniləyirik (yoxdursa yaradırıq - upsert=True)
    # find_one_and_update istifadə edirik ki, eyni anda həm artırılsın, həm də köhnə data alınsın
    user_data = collection.find_one_and_update(
        {"user_id": u_id, "chat_id": c_id},
        {
            "$inc": {"daily": 1, "weekly": 1, "monthly": 1, "total": 1},
            "$set": {"first_name": name}
        },
        upsert=True,
        return_document=True # Yenilənmiş rəqəmi geri qaytarır
    )

    current_total = user_data.get("total", 0)

    # Təbrik mesajları məntiqi (Hər 130 və 800 mesajda bir)
    congrats_130 = ["Afərin {}, 130 mesajı tamamladın! 🎊", "Super! {} artıq 130 mesaj yazdı! 🔥"]
    congrats_800 = ["Vay! {} tam 800 mesaj yazdı! 🏆", "Rekord sənindir {}! 800 mesaj təbrik edirik! ✨"]

    if current_total == 130:
        await message.reply_text(random.choice(congrats_130).format(name))
    elif current_total == 800:
        await message.reply_text(random.choice(congrats_800).format(name))

app.run()

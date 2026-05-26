#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║ KENSHIN ANIME BOT — by @kenshin_anime                ║
║ Style     : TMKOC Premium Style                      ║
║ Features  : Search List + Click to Fetch (No Links)  ║
║ Database  : AniList GraphQL Search Engine            ║
║ Hosting   : Render Web Service (Free Tier) Ready     ║
╚══════════════════════════════════════════════════════╝
"""
import os, io, asyncio, logging, re
import aiohttp
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode, ChatAction

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("KenshinBot")

# ── Config ─────────────────────────────────────────────
API_ID    = int(os.environ.get("API_ID", "0"))
API_HASH  = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client(
    "kenshin_anime_bot",
    api_id   = API_ID,
    api_hash = API_HASH,
    bot_token= BOT_TOKEN,
)

ANILIST_URL = "https://graphql.anilist.co"

# ── Helpers ────────────────────────────────────────────
_BOLD_DIGITS = "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
def bold_num(s: str) -> str:
    return "".join(_BOLD_DIGITS[int(c)] if c.isdigit() else c for c in str(s))

def extract_season(title: str) -> str:
    match = re.search(r'(?:Season|S)\s*(\d+)', title, re.IGNORECASE)
    if match:
        return match.group(1).zfill(2)
    if "2nd" in title.lower(): return "02"
    if "3rd" in title.lower(): return "03"
    if "4th" in title.lower(): return "04"
    if "5th" in title.lower(): return "05"
    return "01"

def clean_html(raw_html: str) -> str:
    if not raw_html: return "No synopsis available."
    return re.sub(r'<[^<]+?>', '', raw_html).replace("[Written by MAL Rewrite]", "").strip()

# ════════════════════════════════════════════════════════
# ANILIST GRAPHQL QUERIES
# ════════════════════════════════════════════════════════
LIST_QUERY = """
query ($search: String) {
  Page (perPage: 5) {
    media (search: $search, type: ANIME) {
      id
      title {
        english
        romaji
      }
    }
  }
}
"""

INFO_QUERY = """
query ($id: Int) {
  Media (id: $id, type: ANIME) {
    title {
      english
      romaji
    }
    format
    episodes
    duration
    status
    averageScore
    genres
    studios(isMain: true) {
      nodes {
        name
      }
    }
    description
    coverImage {
      extraLarge
    }
  }
}
"""

# ════════════════════════════════════════════════════════
# BOT LOGIC
# ════════════════════════════════════════════════════════
@app.on_message(filters.command("start") & filters.private)
async def cmd_start(_, msg: Message):
    await msg.reply_text(
        "<b>🎌 Kenshin Search Bot Online!</b>\n\n"
        "Bas anime ka naam likho, main matching list dikhaunga!",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.text & ~filters.command(["start", "help"]) & filters.private)
async def auto_anime_search(_, msg: Message):
    name = msg.text.strip()
    wait_msg = await msg.reply_text("🔍 <i>Matching titles dhoondh raha hoon...</i>", parse_mode=ParseMode.HTML)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ANILIST_URL, json={"query": LIST_QUERY, "variables": {"search": name}}, timeout=10) as r:
                if r.status != 200:
                    return await wait_msg.edit_text("❌ AniList API se connect nahi ho pa raha hoon.")
                
                res = await r.json()
                anime_list = res.get("data", {}).get("Page", {}).get("media", [])
                
                if not anime_list:
                    return await wait_msg.edit_text(f"❌ <b>'{name}'</b> se match karta hua koi anime nahi mila.")
                
                buttons = []
                for anime in anime_list:
                    title = anime["title"]["english"] or anime["title"]["romaji"]
                    if len(title) > 35: title = title[:32] + "..."
                    buttons.append([InlineKeyboardButton(title, callback_data=f"info_{anime['id']}")])
                
                await wait_msg.edit_text(
                    f"🎯 <b>Muche ye matching results mile hain:</b>\n\n"
                    f"Aapko jiski detail chahiye uspar click karein 👇",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            log.error(f"Search Error: {e}")
            await wait_msg.edit_text(f"❌ Error: {e}")

@app.on_callback_query(filters.regex(r"^info_(\d+)"))
async def handle_anime_info(_, query: CallbackQuery):
    anime_id = int(query.data.split("_")[1])
    await query.answer("Fetching premium details...")
    await app.send_chat_action(query.message.chat.id, ChatAction.UPLOAD_PHOTO)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ANILIST_URL, json={"query": INFO_QUERY, "variables": {"id": anime_id}}, timeout=10) as r:
                if r.status != 200:
                    return await query.message.edit_text("❌ Data fetch karne mein dikkat aayi.")
                
                res = await r.json()
                media = res.get("data", {}).get("Media")
                if not media:
                    return await query.message.edit_text("❌ Anime nahi mila.")
                
                title = media["title"]["english"] or media["title"]["romaji"] or "Unknown"
                category = str(media.get("format") or "Anime").replace("_", " ").title()
                season = extract_season(title)
                episodes = str(media.get("episodes") or "?")
                runtime = f"{media.get('duration', '?')} minutes"
                
                raw_score = media.get("averageScore")
                rating = bold_num(f"{raw_score/10:.1f}") if raw_score else "?"
                
                status = str(media.get("status") or "Unknown").replace("_", " ").lower()
                
                studio_nodes = media["studios"]["nodes"]
                studio = ", ".join([s["name"] for s in studio_nodes]).lower() if studio_nodes else "unknown"
                genres = ", ".join(media.get("genres", [])) or "unknown"
                
                synopsis = clean_html(media.get("description"))
                if len(synopsis) > 300:
                    synopsis = synopsis[:297] + "..."
                
                caption = (
                    f"<b>​<blockquote>「 {title.upper()} 」</blockquote>\n"
                    f"═══════════════════\n"
                    f"🌸 Category: {category}\n"
                    f"🍥 Season: {season} \n"
                    f"🧊 Episodes: {episodes} \n"
                    f"🍣 Runtime: {runtime} \n"
                    f"🍡 Rating: {rating}/📯\n"
                    f"🍙 Status: {status} \n"
                    f"🍵 Studio: {studio}\n"
                    f"🎐 Genres: {genres} \n"
                    f"═══════════════════\n"
                    f"<blockquote>🥗 Synopsis: {synopsis}</blockquote>\n\n"
                    f"<blockquote>POWERED BY: [@KENSHIN_ANIME]</blockquote></b>"
                )
                
                thumb_url = media["coverImage"]["extraLarge"]
                await query.message.delete()
                
                if thumb_url:
                    async with session.get(thumb_url) as img_res:
                        img_bytes = await img_res.read()
                    await query.message.reply_photo(photo=io.BytesIO(img_bytes), caption=caption)
                else:
                    await query.message.reply_text(caption)
                    
        except Exception as e:
            log.error(f"Callback Error: {e}")
            await query.message.reply_text(f"❌ Kuch error aaya: {e}")

# ════════════════════════════════════════════════════════
# RENDER DUMMY WEB SERVER (Port Binding Fix)
# ════════════════════════════════════════════════════════
async def start_webserver():
    async def handle(request):
        return web.Response(text="Kenshin Bot is Alive on Render!")
    
    app_web = web.Application()
    app_web.router.add_get('/', handle)
    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"🌐 Dummy Web Server started on port {port}")

async def main():
    await start_webserver()
    await app.start()
    log.info("🎌 Kenshin Bot Started Successfully!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

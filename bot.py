import asyncio
import aiohttp
import cloudscraper

from pyrogram import Client, filters
from pyrogram.types import Message


# -----------------------------
# CONFIG
# -----------------------------

API_ID = 27958870          # <-- put your api_id
API_HASH = "90227e2449ed6924b95f241b0110d1e6"
BOT_TOKEN = "8426633238:AAGTa5eTLy3jueGruhKAad2g8u8bvu8oRGg"


# -----------------------------
# HTTP headers
# -----------------------------

CF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com/",
}


# -----------------------------
# Cloudflare challenge detector
# -----------------------------

def is_cloudflare_challenge(html: str) -> bool:
    if not html:
        return False

    h = html.lower()

    signs = (
        "checking your browser",
        "just a moment",
        "cf-browser-verification",
        "challenge-platform",
        "/cdn-cgi/challenge-platform",
        "__cf_chl",
        "cf-chl-",
        "cloudflare ray id",
    )

    return any(s in h for s in signs)


# -----------------------------
# aiohttp try
# -----------------------------

async def _try_aiohttp(url: str, timeout: int):
    async with aiohttp.ClientSession(headers=CF_HEADERS) as session:
        async with session.get(
            url,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:

            html = await resp.text(errors="ignore")

            return {
                "status_code": resp.status,
                "final_url": str(resp.url),
                "html": html
            }


# -----------------------------
# cloudscraper try
# -----------------------------

def _cloudscraper_request(url: str, timeout: int):
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows"}
    )

    r = scraper.get(url, allow_redirects=True, timeout=timeout)

    return {
        "status_code": r.status_code,
        "final_url": r.url,
        "html": r.text
    }


# -----------------------------
# Combined resolver
# -----------------------------

async def fetch_with_cf_fallback(url: str, timeout: int = 20):

    # 1) Try aiohttp
    try:
        r = await _try_aiohttp(url, timeout)

        if r["status_code"] < 400 and not is_cloudflare_challenge(r["html"]):
            return {
                "status": "success",
                "url": r["final_url"],
                "method": "aiohttp"
            }

    except Exception:
        pass

    # 2) Try cloudscraper
    try:
        loop = asyncio.get_running_loop()

        r = await loop.run_in_executor(
            None, _cloudscraper_request, url, timeout
        )

        if r["status_code"] < 400 and not is_cloudflare_challenge(r["html"]):
            return {
                "status": "success",
                "url": r["final_url"],
                "method": "cloudscraper"
            }

        return {
            "status": "verification_required",
            "url": r["final_url"],
            "message": "Browser / Cloudflare verification detected"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# -----------------------------
# Bot
# -----------------------------

app = Client(
    "cf_resolver_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# -----------------------------
# /start
# -----------------------------

@app.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply_text(
        "Send a link using:\n\n"
        "/bypass <url>\n\n"
        "I will try to resolve the final link.\n"
        "If browser verification is required, I will tell you."
    )


# -----------------------------
# /bypass
# -----------------------------

@app.on_message(filters.command("bypass"))
async def bypass_cmd(_, message: Message):

    if len(message.command) < 2:
        await message.reply_text(
            "Usage:\n\n/bypass https://example.com/..."
        )
        return

    url = message.command[1].strip()

    msg = await message.reply_text("Checking link…")

    result = await fetch_with_cf_fallback(url)

    if result["status"] == "success":
        await msg.edit_text(
            "✅ Link resolved\n\n"
            f"🔗 Final URL:\n{result['url']}\n\n"
            f"Method: {result['method']}"
        )

    elif result["status"] == "verification_required":
        await msg.edit_text(
            "⚠️ This link requires browser / human verification.\n\n"
            "I cannot automatically open this page.\n\n"
            f"Detected URL:\n{result.get('url', url)}"
        )

    else:
        await msg.edit_text(
            "❌ Error while processing link\n\n"
            f"{result.get('message')}"
        )


# -----------------------------
# Run
# -----------------------------

if __name__ == "__main__":
    print("Bot started...")
    app.run()

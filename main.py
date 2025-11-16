import os
import time
import json
import random
import threading
import asyncio
import requests
from flask import Flask
from playwright.async_api import async_playwright

# === CONFIGURATION ===
JOB_PAGE_URL = "https://www.youtube.com/watch?v=GwCsZa-6c9I&list=PLgl-4XwWe41Vcidfx8FrtxQIGVAfjOeXR"

# === TELEGRAM SETTINGS (secure from Render env) ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
CHAT_IDS = [chat.strip() for chat in CHAT_IDS.split(",") if chat.strip()]

if not TELEGRAM_BOT_TOKEN or not CHAT_IDS:
    print("\n⚠️ Missing Telegram credentials — check Render env variables.")
else:
    print(f"\n✅ Telegram config loaded ({len(CHAT_IDS)} chat IDs).")

# === PROXY & USER-AGENT ROTATION ===
PROXIES = [
    "http://185.199.229.156:7492",
    "http://103.155.54.26:83",
    "http://91.92.155.207:3128",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15 Edg/129.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
]

seen_jobs = set()
app = Flask(__name__)

# === TELEGRAM FUNCTION ===
def send_telegram_message(message: str):
    for chat_id in CHAT_IDS:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Telegram send exception: {e}")

# === PLAYWRIGHT TOKEN FETCH ===
async def get_auth_token():
    try:
        proxy = random.choice(PROXIES)
        agent = random.choice(USER_AGENTS)
        print(f"🌐 Using proxy: {proxy}")
        print(f"🧭 Using User-Agent: {agent}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, proxy={"server": proxy})
            context = await browser.new_context(user_agent=agent)
            page = await context.new_page()
            await page.goto(JOB_PAGE_URL, wait_until="load")

            cookies = await context.cookies()
            await browser.close()

            for cookie in cookies:
                if "session" in cookie["name"].lower():
                    return f"Bearer {cookie['value']}"

    except Exception as e:
        print(f"❌ Playwright token fetch failed: {e}")
    return None

# === MAIN JOB LOOP (YOUR ORIGINAL BOT) ===
def job_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    DEFAULT_TOKEN = "Bearer Status|unauthenticated|Session|exampleToken"

    while True:
        try:
            print("⏳ Connected Successfully")
            send_telegram_message("⏳ Connected Successfully")

            token = loop.run_until_complete(get_auth_token())
            if not token:
                send_telegram_message("⚠️ Using fallback token.")
                token = DEFAULT_TOKEN

            # Your function to fetch jobs (not included in snippet)
            # fetch_jobs(token)

            print("🕓 Sleeping 30 mins before next check.\n")
            time.sleep(1800)

        except Exception as e:
            print(f"⚠️ Loop error: {e}")
            time.sleep(180)

# ====================================================================================
# === NEW FEATURE: YOUTUBE SEARCH TASK (RUNS IN PARALLEL, STOPS ON FATAL ERROR) ======
# ====================================================================================

# --- One-time Playwright YouTube search ---
async def yt_search_once():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto("https://www.youtube.com")

            await page.wait_for_selector("input#search")
            await page.fill("input#search", "no limit of masti")
            await page.click("button#search-icon-legacy")

            await page.wait_for_selector("ytd-video-renderer", timeout=15000)

            await browser.close()
            return True

    except Exception as e:
        print("❌ Fatal YouTube search error:", e)
        return False

# --- Loop every 5 minutes, STOP on fatal error ---
def youtube_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        print("🔎 Running YouTube search...")

        success = loop.run_until_complete(yt_search_once())

        if success:
            send_telegram_message("✅ YouTube search completed successfully!")
            print("✅ YouTube search completed successfully!")
        else:
            send_telegram_message("❌ YouTube search failed. Task stopped permanently due to fatal error.")
            print("❌ YouTube task stopped permanently due to fatal error.")
            break  # do NOT retry — your chosen Option 2

        print("⏳ Waiting 5 minutes for next search...")
        time.sleep(300)

# === FLASK ENDPOINTS ===
@app.route("/")
def home():
    return "✅ Bot running."

@app.route("/forcefetch")
def forcefetch():
    token = asyncio.run(get_auth_token())
    if not token:
        token = "Bearer Status|unauthenticated|Session|exampleToken"
    # fetch_jobs(token)
    return "Manual fetch completed."

# === START EVERYTHING ===
if __name__ == "__main__":
    # Start original bot loop
    threading.Thread(target=job_loop, daemon=True).start()

    # Start YouTube loop in parallel
    threading.Thread(target=youtube_loop, daemon=True).start()

    # Run Flask server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

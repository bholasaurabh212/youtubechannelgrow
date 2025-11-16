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
JOB_PAGE_URL = "https://www.youtube.com/@NoLimitOfMasti-Fun"

# === TELEGRAM SETTINGS (secure from Render env) ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
CHAT_IDS = [chat.strip() for chat in CHAT_IDS.split(",") if chat.strip()]

if not TELEGRAM_BOT_TOKEN or not CHAT_IDS:
    print("f\n⚠️ Missing Telegram credentials — check Render env variables.")
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
]

seen_jobs = set()
app = Flask(__name__)

# === TELEGRAM FUNCTION ===
def send_telegram_message(message: str):
    for chat_id in CHAT_IDS:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code != 200:
                print(f"\n⚠️ Telegram send error {chat_id}: {response.text}")
        except Exception as e:
            print(f"\n⚠️ Telegram send exception to {chat_id}: {e}")

# === FETCH TOKEN USING PLAYWRIGHT ===
async def get_auth_token():
    try:
        proxy = random.choice(PROXIES)
        agent = random.choice(USER_AGENTS)
        print(f"🌐 Using proxy: {proxy}")
        print(f"🧭 Using User-Agent: {agent}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": proxy}
            )
            context = await browser.new_context(
                user_agent=agent,
                extra_http_headers={
                    "Accept": "text/html",
                    "Referer": "https://www.youtube.com/"
                }
            )

            page = await context.new_page()
            await page.goto(JOB_PAGE_URL, wait_until="load")

            cookies = await context.cookies()
            await browser.close()

            for cookie in cookies:
                if "session" in cookie["name"].lower():
                    print(f"\n✅ Session cookie found: {cookie['name']}")
                    return f"Bearer {cookie['value']}"

    except Exception as e:
        print(f"\n❌ Playwright token fetch failed: {e}")
    return None

# === BACKGROUND JOB LOOP (with safe delay) ===
def job_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    DEFAULT_TOKEN = "Bearer Status|unauthenticated|Session|exampleToken"

    while True:
        try:
            print(f"\n⏳ Connected Successfully")
            token = loop.run_until_complete(get_auth_token())
            if not token:
                print(f"\n⚠️ Using fallback token.")
                token = DEFAULT_TOKEN

            fetch_jobs(token)
            print("f\n🕓 Sleeping 30 mins before next check.\n")
            time.sleep(1200)  # 30 mins delay
        except Exception as e:
            print(f"\n⚠️ Loop error: {e}")
            time.sleep(180)  # wait 5 mins on error before retry

# === FLASK ENDPOINTS ===
@app.route("/")
def home():
    return "✅ Amazon Job Bot is running online."
    offcheck = (f"\n✅ Amazon Job Bot is running Online..\n" "[☕️ Fuel this bot for running...] (https://buymeacoffee.com/ukjobs)")
    send_telegram_message(offcheck)

@app.route("/forcefetch")
def forcefetch():
    token = asyncio.run(get_auth_token())
    if not token:
        token = "Bearer Status|unauthenticated|Session|exampleToken"
    fetch_jobs(token)
    return "\n✅ Manual job fetch completed."

# === START APP ===
if __name__ == "__main__":
    threading.Thread(target=job_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))








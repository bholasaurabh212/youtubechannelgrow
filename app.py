import os
import time
import datetime
import random
import asyncio
import requests
import threading
from playwright.async_api import async_playwright

# === CONFIGURATION ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
JOB_PAGE_URL = "https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
CHAT_IDS = [chat.strip() for chat in CHAT_IDS.split(",") if chat.strip()]

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
bot_active = False  # Bot starts inactive

# === TELEGRAM ===
def send_telegram(msg: str, chat_id=None):
    targets = [chat_id] if chat_id else CHAT_IDS
    for cid in targets:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            print("⚠️ Telegram error:", e)

# === AUTH FETCH ===
async def get_token():
    try:
        proxy = random.choice(PROXIES)
        agent = random.choice(USER_AGENTS)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, proxy={"server": proxy})
            context = await browser.new_context(user_agent=agent)
            page = await context.new_page()
            await page.goto(JOB_PAGE_URL)
            cookies = await context.cookies()
            await browser.close()

            for cookie in cookies:
                if "session" in cookie["name"].lower():
                    return f"Bearer {cookie['value']}"
    except:
        pass
    return None

# === JOB FETCH ===
def fetch_jobs():
    print("\n⏳ Checking Amazon jobs...")
    token = asyncio.run(get_token())
    if not token:
        print("⚠ No token, skipping job fetch.")
        return

    payload = {
        "operationName": "searchJobCardsByLocation",
        "variables": {
            "searchJobRequest": {
                "locale": "en-GB",
                "country": "United Kingdom",
                "keyWords": "Warehouse Operative",
                "pageSize": 20
            }
        },
        "query": """
        query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
          searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
            jobCards {
              jobId
              jobTitle
              city
              state
              postalCode
              jobType
              employmentType
              totalPayRateMax
            }
          }
        }
        """
    }

    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": random.choice(USER_AGENTS)
    }

    try:
        response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
        data = response.json()
        job_cards = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
        print(f"📦 Found {len(job_cards)} jobs.")

        for job in job_cards:
            job_id = job["jobId"]
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                msg = (
                    f"💼 *{job['jobTitle']}*\n"
                    f"📍 {job['city']}, {job['state']} {job['postalCode']}\n"
                    f"💰 £{job['totalPayRateMax']}/hr\n"
                    f"🕒 {job['jobType']} | {job['employmentType']}\n"
                    f"🔗 [View Job](https://www.jobsatamazon.co.uk/app#/jobDetail?jobId={job_id}&locale=en-GB)"
                )
                send_telegram(msg)
        print("✅ Job fetch complete.")

    except Exception as e:
        print("⚠️ Error fetching jobs:", e)

# === SCHEDULED LOOP ===
def job_loop():
    while bot_active:
        fetch_jobs()
        print("🕓 Sleeping 30 mins before next check...")
        send_telegram_message("🕓 Sleeping 30 mins before next check.\n")
        time.sleep(1800)  # 30 mins

# === TELEGRAM POLLING ===
def telegram_poll():
    global bot_active
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?timeout=60"
            if offset:
                url += f"&offset={offset+1}"
            resp = requests.get(url, timeout=65).json()
            for update in resp.get("result", []):
                offset = update["update_id"]
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "").strip().lower()

                if text == "/start":
                    if not bot_active:
                        bot_active = True
                        send_telegram("✅ Amazon Job Bot started!", chat_id)
                        threading.Thread(target=job_loop, daemon=True).start()
                    else:
                        send_telegram("⚠️ Bot is already running.", chat_id)

                elif text == "/stop":
                    bot_active = False
                    send_telegram("🛑 Amazon Job Bot stopped.", chat_id)

        except Exception as e:
            print("⚠️ Telegram poll error:", e)
        time.sleep(2)

# === MAIN START ===
if __name__ == "__main__":
    print("🤖 Bot ready. Waiting for /start command...")
    telegram_poll()

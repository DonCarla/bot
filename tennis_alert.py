# tennis_alert.py — для бесплатного Render (бот + встроенный веб-сервер)
import aiohttp
import asyncio
import os
import time
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = "7943174014:AAHWqDtjnSgBY2Me8QxgYOolO1fT6L62eAk"  # ← вставь свой токен сюда
TELEGRAM_CHAT_ID = 5892506142
LOCAL_API = "https://node-rvue.onrender.com/live"
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "5"))
sent_alerts = set()

# ----------------- Telegram -----------------
async def send_telegram_message(session, text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        await session.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    except:
        pass

# ----------------- Парсинг сетов -----------------
def extract_sets_from_match(match: dict):
    sets = []
    hs = match.get("homeScore", {})
    ascore = match.get("awayScore", {})

    for i in range(1, 6):
        hk = f"period{i}"
        if hk in hs or hk in ascore:
            h = int(hs.get(hk, 0) or 0)
            a = int(ascore.get(hk, 0) or 0)
            if h or a:
                sets.append({"number": i, "home": h, "away": a})
    return sets

def get_server(match):
    flag = match.get("firstToServe")
    if flag == 1:
        return "home"
    elif flag == 2:
        return "away"
    return None

# ----------------- Основная логика -----------------
async def process_match(session, match):
    tournament = match.get("tournament", {})
    category = tournament.get("category", {}).get("name", "")
    tournament_name = tournament.get("name", "<unknown>")
    home = match.get("homeTeam", {}).get("name", "Home")
    away = match.get("awayTeam", {}).get("name", "Away")
    mid = match.get("id")

    sets = extract_sets_from_match(match)
    server = get_server(match)

    for s in sets:
        hg, ag, set_num = s["home"], s["away"], s["number"]

        # ---------- Сценарий №1: 6–5 / 5–6 (тай-брейк возможен) ----------
        if {hg, ag} == {6, 5}:
            leader = "home" if hg > ag else "away"
            losing = "away" if leader == "home" else "home"

            # уведомляем только если подаёт проигрывающий
            if server == losing:
                key = f"{mid}_set{set_num}_65"
                if key not in sent_alerts:
                    text = (
                        f"🎾 {home} vs {away}\n"
                        f"⚠️ {hg}–{ag} в сете {set_num} — подаёт проигрывающий!\n"
                        f"🏆 {tournament_name} ({category})\n"
                        f"👉 Возможен тай-брейк!"
                    )
                    await send_telegram_message(session, text)
                    sent_alerts.add(key)

        # ---------- Сценарий №2: 2–0 / 0–2 (только ATP + Challenger) ----------
        if {hg, ag} == {2, 0}:
            if category in ("ATP", "Challenger"):
                key = f"{mid}_set{set_num}_20"
                if key not in sent_alerts:
                    text = (
                        f"🔥 {home} vs {away}\n"
                        f"Начало сета {set_num}: {hg}–{ag}\n"
                        f"🏆 {tournament_name} ({category})"
                    )
                    await send_telegram_message(session, text)
                    sent_alerts.add(key)

# ----------------- Фоновая задача (бот) -----------------
async def check_tennis_matches():
    async with aiohttp.ClientSession() as session:
        await send_telegram_message(session, "tele check")
        while True:
            try:
                async with session.get(LOCAL_API) as resp:
                    data = await resp.json()
                    events = data.get("events", [])
                    print(f"[{time.strftime('%H:%M:%S')}] Матчей: {len(events)}")
                    for match in events:
                        await process_match(session, match)
            except Exception as e:
                print("Ошибка:", e)

            await asyncio.sleep(CHECK_INTERVAL)

# ----------------- Веб-сервер для Render FREE -----------------
async def handle(request):
    return web.Response(text="✅ Tennis bot is running")

async def main():
    # Запускаем бота фоном
    asyncio.create_task(check_tennis_matches())

    # Запускаем простой веб-сервер
    app = web.Application()
    app.router.add_get("/", handle)

    port = int(os.environ.get("PORT", 3000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"🌐 Web server running on port {port}")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

# tennis_alert.py — улучшенная логика (версия 2)
import aiohttp
import asyncio
import os
import time
from dotenv import load_dotenv
from aiohttp import web


load_dotenv()

TELEGRAM_TOKEN = "7943174014:AAHWqDtjnSgBY2Me8QxgYOolO1fT6L62eAk"  # ← вставь свой токен сюда
TELEGRAM_CHAT_ID = 5892506142
LOCAL_API = "https://node-rvue.onrender.com/live"
CHECK_INTERVAL = 5
ALLOWED_TOURNAMENTS_2_0 = ("ATP", "Challenger")  # теперь только ATP и Challenger
sent_alerts = set()

async def send_telegram_message(session, text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❗ Telegram не настроен. Сообщение:", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with session.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}) as r:
        if r.status != 200:
            print("Ошибка Telegram:", r.status, await r.text())

def extract_sets_from_match(match: dict):
    sets = []
    hs = match.get("homeScore", {})
    ascore = match.get("awayScore", {})
    for i in range(1, 6):
        hk = f"period{i}"
        if hk in hs or hk in ascore:
            h = hs.get(hk, 0) or 0
            a = ascore.get(hk, 0) or 0
            if h or a:
                sets.append({"number": i, "home": int(h), "away": int(a)})
    return sets

def get_server(match):
    """Определяем, кто сейчас подаёт: home или away"""
    server_flag = match.get("firstToServe")
    if server_flag == 1:
        return "home"
    elif server_flag == 2:
        return "away"
    return None

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
        print(f"{home} vs {away} | Сет {set_num} | {hg}-{ag} | Турнир: {category}")

        # --- 1️⃣ 6–5 / 5–6 (только если подаёт проигрывающий) ---
        if {hg, ag} == {6, 5}:
            leader = "home" if hg > ag else "away"
            losing = "away" if leader == "home" else "home"
            # уведомляем, если подача у проигрывающего
            if server == losing:
                key = f"{mid}_set{set_num}_6-5_serving_loser"
                if key not in sent_alerts:
                    text = (
                        f"🎾 {home} vs {away}\n"
                        f"⚠️ Счёт {hg}–{ag} в сете {set_num}!\n"
                        f"🏆 {tournament_name} ({category})\n"
                        f"👉 Тай-брейк возможен, подача у проигрывающего!"
                    )
                    await send_telegram_message(session, text)
                    sent_alerts.add(key)
                    print(f"[{time.strftime('%H:%M:%S')}] Отправлено: {text}")
            else:
                print(f"[INFO] {home} vs {away} — 6–5, но подаёт ведущий ({leader}), пропускаем.")

        # --- 2️⃣ 2–0 / 0–2 — только для ATP и Challenger ---
        if {hg, ag} == {2, 0}:
            if any(cat in category for cat in ALLOWED_TOURNAMENTS_2_0):
                key = f"{mid}_set{set_num}_2-0"
                if key not in sent_alerts:
                    text = (
                        f"🎾 {home} vs {away}\n"
                        f"🔥 Быстрый старт в сете {set_num}: {hg}–{ag}!\n"
                        f"🏆 {tournament_name} ({category})"
                    )
                    await send_telegram_message(session, text)
                    sent_alerts.add(key)
                    print(f"[{time.strftime('%H:%M:%S')}] Отправлено: {text}")
            else:
                print(f"[INFO] {tournament_name} ({category}) — 2–0, но турнир не в списке (игнор).")

async def check_tennis_matches():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                print(f"Проверяю обновления... {time.strftime('%H:%M:%S')}")
                async with session.get(LOCAL_API) as resp:
                    if resp.status != 200:
                        print("Ошибка proxy:", resp.status)
                        await asyncio.sleep(CHECK_INTERVAL)
                        continue

                    data = await resp.json()
                    events = data.get("events", [])
                    print("Количество матчей:", len(events))

                    for match in events:
                        await process_match(session, match)

                await asyncio.sleep(CHECK_INTERVAL)
            except Exception as e:
                print("Ошибка:", e)
                await asyncio.sleep(5)

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


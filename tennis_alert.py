# tennis_alert.py
import aiohttp
import asyncio
import os
import time
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = "7943174014:AAHWqDtjnSgBY2Me8QxgYOolO1fT6L62eAk"  # ← вставь свой токен сюда
TELEGRAM_CHAT_ID = 5892506142
LOCAL_API = "https://node-rvue.onrender.com/live"
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "5"))
ALLOWED_TOURNAMENTS = ("ATP", "WTA", "Challenger")  # для 2-0/0-2

sent_alerts = set()

async def send_telegram_message(session, text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❗ Telegram не настроен. Сообщение:", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with session.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}) as r:
            if r.status != 200:
                txt = await r.text()
                print("Ошибка отправки Telegram:", r.status, txt)
    except Exception as e:
        print("Ошибка при отправке Telegram:", e)

def extract_sets_from_match(match: dict):
    """
    Возвращает список сетов в виде [{'number':1, 'home':x, 'away':y}, ...]
    Поддерживает разные форматы Sofascore:
      - match.get("periodScores", [])  (массив объектов)
      - поля match["homeScore"]["period1"], period2 ... и аналогично awayScore
    """
    sets = []

    # 1) Если есть periodScores — используем их
    ps = match.get("periodScores")
    if ps and isinstance(ps, list) and len(ps) > 0:
        for s in ps:
            num = s.get("number") if s.get("number") is not None else s.get("set") or len(sets)+1
            home = s.get("home", 0) or 0
            away = s.get("away", 0) or 0
            sets.append({"number": num, "home": int(home), "away": int(away)})
        return sets

    # 2) Если нет periodScores, но есть homeScore / awayScore с period1..period5
    hs = match.get("homeScore", {})
    ascore = match.get("awayScore", {})
    # period keys pattern: 'period1', 'period2', ...
    # попробуем собрать по periodN, где N от 1 до 5 (Sofascore обычно до 5)
    for i in range(1, 6):
        hk = f"period{i}"
        if hk in hs or hk in ascore:
            home_val = hs.get(hk, 0) or 0
            away_val = ascore.get(hk, 0) or 0
            # if both zeros and no data — still include? сюда добавим если хотя бы один > 0
            if (home_val != 0) or (away_val != 0):
                sets.append({"number": i, "home": int(home_val), "away": int(away_val)})
    # 3) как fallback: некоторый провайдер может хранить в fields "periodsScores" или "periods"
    if not sets:
        periods = match.get("periods")  # иногда periods содержит описание, но не счёт
        # нет явных данных — вернём пустой список
    return sets

async def process_match(session, match: dict):
    tournament = match.get("tournament", {})
    category = tournament.get("category", {}).get("name", "") or ""
    tournament_name = tournament.get("name", "<unknown tournament>")

    home = match.get("homeTeam", {}).get("name", "Home")
    away = match.get("awayTeam", {}).get("name", "Away")
    mid = match.get("id") or match.get("slug") or f"m_{hash(home+away)}"

    sets = extract_sets_from_match(match)

    # debug: печатаем все сеты, которые нашли
    if sets:
        for s in sets:
            print(f"{home} vs {away} | Сет {s['number']} | {s['home']}-{s['away']} | Турнир: {category} / {tournament_name}")
    else:
        # если нет сетов, можно вывести текущие очки/point
        hcur = match.get("homeScore", {}).get("current") or match.get("homeScore", {}).get("display")
        acur = match.get("awayScore", {}).get("current") or match.get("awayScore", {}).get("display")
        print(f"{home} vs {away} | Нет сетовых данных. Текущий матч: {hcur}-{acur} | Турнир: {category} / {tournament_name}")

    # Проходим по каждому сету и детектим события
    for s in sets:
        set_num = s["number"]
        hg = s["home"]
        ag = s["away"]

        # 6-5 или 5-6 — для всех турниров (включая ITF)
        if {hg, ag} == {6, 5}:
            key = f"{mid}_set{set_num}_6-5"
            if key not in sent_alerts:
                text = (
                    f"🎾 {home} vs {away}\n"
                    f"⚠️ Счёт {hg}–{ag} в сете {set_num}!\n"
                    f"🏆 {tournament_name} ({category})\n"
                    f"👉 Возможен тай-брейк!"
                )
                await send_telegram_message(session, text)
                sent_alerts.add(key)
                print(f"[{time.strftime('%H:%M:%S')}] Отправлено: {text}")

        # 2-0 или 0-2 — ТОЛЬКО для разрешённых турниров
        if {hg, ag} == {2, 0}:
            if any(cat in category for cat in ALLOWED_TOURNAMENTS):
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
                # для отладки можно вывести, что ITF/неразрешённый турнир, 2-0 игнорируется
                print(f"[INFO] Пропущено (2-0 в неподходящем турнире): {tournament_name} ({category})")

async def check_tennis_matches():
    async with aiohttp.ClientSession() as session:
        await send_telegram_message(session, "Telega fine")
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

                    # --- Отладка: можно временно добавить тестовый матч (раскомментировать при необходимости) ---
                    # fake_event = {
                    #     "id": 999999,
                    #     "homeTeam": {"name": "Test A"},
                    #     "awayTeam": {"name": "Test B"},
                    #     "tournament": {"name": "ATP Test", "category": {"name": "ATP"}},
                    #     "homeScore": {"period1": 6, "period2": 0},
                    #     "awayScore": {"period1": 5, "period2": 0}
                    # }
                    # events.append(fake_event)

                    for match in events:
                        await process_match(session, match)

                await asyncio.sleep(CHECK_INTERVAL)

            except Exception as e:
                print("Ошибка в основном цикле:", e)
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(check_tennis_matches())
    except KeyboardInterrupt:
        print("Остановка.")

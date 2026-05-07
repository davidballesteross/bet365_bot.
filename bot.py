#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime

import aiohttp

from scraper import Bet365Scraper
from notifier import TelegramNotifier
from state import load_state, save_state
from scheduler import check_daily_summary

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8736427026:AAEmZKoAgKgl_W7lX6qx9707O9cfmIRUXEA"
CHAT_ID        = "6421292470"
ODDS_API_KEY   = "4689f9cb119dd0db5cbb9844165a5f0f"

CHECK_INTERVAL = 1800
MAX_MATCHES    = 5
MSG_DELAY      = 3
SPORTS         = ["football", "tennis"]

LIGAS_MAP = {
    "laliga":     "LaLiga",
    "premier":    "Premier",
    "bundesliga": "Bundesliga",
    "seriea":     "Serie A",
    "ligue1":     "Ligue 1",
}

estado = {"pausado": False, "ultimo": "Nunca"}


async def get_updates(token, offset):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params={"offset": offset, "timeout": 5},
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                return data.get("result", [])
    except:
        return []


async def enviar_bloque(notifier, matches, modo, cabecera):
    if not matches:
        return
    await notifier.send_message(cabecera)
    await asyncio.sleep(MSG_DELAY)
    for m in matches[:MAX_MATCHES]:
        await notifier.send_match_alert(m, modo=modo)
        await asyncio.sleep(MSG_DELAY)


async def handle_commands(notifier, scraper, offset, seen):
    updates = await get_updates(TELEGRAM_TOKEN, offset)

    for update in updates:
        offset  = update["update_id"] + 1
        msg     = update.get("message", {})
        text    = msg.get("text", "").strip().lower()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != CHAT_ID:
            continue

        if text in ["/cuotas", "/aseguradas", "/arriesgadas"]:
            await notifier.send_message("Buscando partidos de esta semana...")
            result = await scraper.fetch_odds()
            seg = result.get("asegurada", [])
            arr = result.get("arriesgada", [])

            if text in ["/cuotas", "/aseguradas"]:
                if seg:
                    await enviar_bloque(notifier, seg, "asegurada",
                        "*APUESTAS ASEGURADAS* - Favoritos claros esta semana")
                else:
                    await notifier.send_message("No hay favoritos claros (cuota < 1.5) esta semana.")

            if text in ["/cuotas", "/arriesgadas"]:
                if arr:
                    await enviar_bloque(notifier, arr, "arriesgada",
                        "*APUESTAS ARRIESGADAS* - Partidos equilibrados esta semana")
                else:
                    await notifier.send_message("No hay partidos arriesgados disponibles.")

            seen.update(m["id"] for m in seg + arr)

        elif text.startswith("/liga"):
            liga = text.replace("/liga", "").strip()
            if not liga:
                await notifier.send_message(
                    "Ligas disponibles:\n"
                    "/liga laliga\n"
                    "/liga premier\n"
                    "/liga bundesliga\n"
                    "/liga seriea\n"
                    "/liga ligue1"
                )
            else:
                nombre = LIGAS_MAP.get(liga.replace(" ", ""), liga)
                await notifier.send_message(f"Buscando partidos de {nombre}...")
                result = await scraper.fetch_odds(liga_filter=liga)
                seg = result.get("asegurada", [])
                arr = result.get("arriesgada", [])
                if seg:
                    await enviar_bloque(notifier, seg, "asegurada", f"*ASEGURADAS - {nombre}*")
                if arr:
                    await enviar_bloque(notifier, arr, "arriesgada", f"*ARRIESGADAS - {nombre}*")
                if not seg and not arr:
                    await notifier.send_message(f"No hay partidos de {nombre} esta semana.")

        elif text == "/estado":
            p = "Pausado" if estado["pausado"] else "Activo"
            await notifier.send_message(
                f"*Estado del bot*\n"
                f"{p}\n"
                f"Ultima revision: *{estado['ultimo']}*\n"
                f"Intervalo: *{CHECK_INTERVAL // 60} minutos*"
            )

        elif text == "/parar":
            estado["pausado"] = True
            save_state(seen, True)
            await notifier.send_message("Bot pausado. Escribe /arrancar para reanudar.")

        elif text == "/arrancar":
            estado["pausado"] = False
            save_state(seen, False)
            await notifier.send_message("Bot reanudado.")

        elif text in ["/ayuda", "/start"]:
            await notifier.send_message(
                "*Comandos disponibles:*\n"
                "/cuotas - Aseguradas + arriesgadas\n"
                "/aseguradas - Solo favoritos claros\n"
                "/arriesgadas - Solo partidos equilibrados\n"
                "/liga - Filtrar por liga\n"
                "/estado - Ver estado del bot\n"
                "/parar - Pausar alertas\n"
                "/arrancar - Reanudar alertas\n"
                "/ayuda - Ver esta ayuda"
            )

    return offset


async def main():
    logger.info("Bot iniciado")
    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    scraper  = Bet365Scraper(sports=SPORTS, min_odds=0.0, api_key=ODDS_API_KEY)

    _s = load_state()
    seen = set(_s["seen_matches"])
    estado["pausado"] = _s["pausado"]

    await notifier.send_message(
        "*Bot de cuotas iniciado*\n"
        "LaLiga | Premier | Bundesliga\n"
        "Serie A | Ligue 1 | Tenis\n"
        "Solo partidos de esta semana\n"
        "Escribe /ayuda para ver comandos"
    )

    offset = 0
    last_check = 0
    last_summary = None

    while True:
        offset = await handle_commands(notifier, scraper, offset, seen)

        now = asyncio.get_event_loop().time()

        if not estado["pausado"] and (now - last_check) >= CHECK_INTERVAL:
            last_check = now
            estado["ultimo"] = datetime.now().strftime("%H:%M")

            try:
                result = await scraper.fetch_odds()
                seg = [m for m in result.get("asegurada", []) if m["id"] not in seen]
                arr = [m for m in result.get("arriesgada", []) if m["id"] not in seen]

                if seg:
                    await enviar_bloque(notifier, seg, "asegurada",
                        "*APUESTAS ASEGURADAS* - Favoritos claros esta semana")
                if arr:
                    await enviar_bloque(notifier, arr, "arriesgada",
                        "*APUESTAS ARRIESGADAS* - Partidos equilibrados esta semana")

                for m in result.get("asegurada", []) + result.get("arriesgada", []):
                    seen.add(m["id"])

                save_state(seen, estado["pausado"])

                if len(seen) > 500:
                    seen.clear()

            except Exception as e:
                logger.error(f"Error: {e}")

        last_summary = await check_daily_summary(notifier, scraper, last_summary)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
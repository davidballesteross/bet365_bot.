import os
from dotenv import load_dotenv
load_dotenv()
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("CHAT_ID")
ODDS_API_KEY   = os.getenv("ODDS_API_KEY")

CHECK_INTERVAL = 10800
CACHE_TTL = 1800
_cache = {"data": None, "timestamp": 0}
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


async def fetch_with_cache(scraper):
    now = asyncio.get_event_loop().time()
    if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["data"]
    result = await scraper.fetch_odds()
    _cache["data"] = result
    _cache["timestamp"] = now
    return result

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
            result = await fetch_with_cache(scraper)
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

        elif text == "/combinada":
            await notifier.send_message(
                "🎰 *¿Qué combinada quieres?*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🟢 /combinada\_baja — 4 partidos seguros\n"
                "🟡 /combinada\_media — 5 partidos equilibrados\n"
                "🔴 /combinada\_alta — 6 partidos arriesgados"
            )

        elif text.startswith("/liga"):
            liga = text.replace("/liga", "").strip()
            if not liga:
                await notifier.send_message(
                    "Ligas disponibles:\n"
                    "/liga laliga\n"
                    "/liga premier\n"
                    "/liga bundesliga\n"
                    "/liga seriea\n"
                    "/liga ligue1\n"
                    "/liga champions\n"
                    "/liga europa\n"
                    "/liga nba"
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

        elif text in ["/combinada_baja", "/combinada_media", "/combinada_alta"]:
            result = await fetch_with_cache(scraper)
            seg = result.get("asegurada", [])
            arr = result.get("arriesgada", [])
            if text == "/combinada_baja":
                titulo = "🟢 COMBINADA BAJA"
                pool = sorted([m for m in seg + arr if 1.40 <= m["odd_favorito"] <= 1.80], key=lambda m: m.get("confianza", 0), reverse=True)
                n = 4
            elif text == "/combinada_alta":
                titulo = "🔴 COMBINADA ALTA"
                pool = sorted([m for m in seg + arr if m["odd_favorito"] >= 1.60], key=lambda m: m.get("confianza", 0), reverse=True)
                n = 6
            else:
                titulo = "🟡 COMBINADA MEDIA"
                pool = sorted([m for m in seg + arr if 1.40 <= m["odd_favorito"] <= 2.20], key=lambda m: m.get("confianza", 0), reverse=True)
                n = 5
            await notifier.send_message(f"Buscando {titulo.lower()}...")
            combinada = pool[:n]
            if len(combinada) >= 2:
                cuota_total = 1.0
                for m in combinada:
                    cuota_total *= m["odd_favorito"]
                cuota_total = round(cuota_total, 2)
                confianza_media = int(sum(m.get("confianza", 0) for m in combinada) / len(combinada))
                if confianza_media >= 75:
                    conf_emoji = "🟢"
                elif confianza_media >= 50:
                    conf_emoji = "🟡"
                else:
                    conf_emoji = "🔴"
                lineas = "\n".join([f"  • {m['favorito']} ({m['odd_favorito']:.2f}) — {m['liga']}" for m in combinada])
                await notifier.send_message(
                    f"🎰 *{titulo}*\n"
                    f"{'─' * 28}\n"
                    f"{lineas}\n"
                    f"{'─' * 28}\n"
                    f"💰 Cuota total: *{cuota_total}*\n"
                    f"{conf_emoji} Confianza media: *{confianza_media}%*\n"
                    f"{'─' * 28}\n"
                    f"⚠️ Apuesta responsablemente"
                )
            else:
                await notifier.send_message("No hay suficientes partidos para esta combinada ahora mismo.")

        elif text == "/mejor":
            await notifier.send_message("Buscando las 5 mejores apuestas del día...")
            result = await fetch_with_cache(scraper)
            seg = result.get("asegurada", [])
            arr = result.get("arriesgada", [])
            todos = sorted(seg + arr, key=lambda m: m.get("confianza", 0), reverse=True)
            top5 = todos[:5]
            if top5:
                await notifier.send_message("🏆 *TOP 5 APUESTAS DEL DÍA*\nOrdenadas por confianza")
                for m in top5:
                    modo = "asegurada" if m in seg else "arriesgada"
                    await notifier.send_match_alert(m, modo=modo)
                    await asyncio.sleep(MSG_DELAY)
            else:
                await notifier.send_message("No hay apuestas disponibles ahora mismo.")

        elif text in ["/ayuda", "/start"]:
            await notifier.send_message(
                "*Comandos disponibles:*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📊 /cuotas — Todos los partidos\n"
                "🔒 /aseguradas — Solo favoritos\n"
                "🔥 /arriesgadas — Partidos parejos\n"
                "🏆 /mejor — Top 5 del día\n"
                "🎰 /combinada — Ver opciones\n"
                "🌍 /liga — Filtrar por liga\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚙️ /estado — Estado del bot\n"
                "/parar | /arrancar"
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
                _cache["data"] = result
                _cache["timestamp"] = asyncio.get_event_loop().time()
                seg = [m for m in result.get("asegurada", []) if m["id"] not in seen]
                arr = [m for m in result.get("arriesgada", []) if m["id"] not in seen]

                # Solo alertas automáticas con confianza >= 50
                seg_top = [m for m in seg if m.get("confianza", 0) >= 50]
                arr_top = [m for m in arr if m.get("confianza", 0) >= 50]
                if seg_top:
                    await enviar_bloque(notifier, seg_top, "asegurada",
                        "*APUESTAS ASEGURADAS* - Favoritos claros esta semana")
                if arr_top:
                    await enviar_bloque(notifier, arr_top, "arriesgada",
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
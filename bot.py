#!/usr/bin/env python3
"""
Bet365 Odds Alert Bot
- Envia primero cuotas aseguradas, luego arriesgadas
- 3 segundos entre mensajes
- Comandos: /cuotas /aseguradas /arriesgadas /estado /parar /arrancar /minima /ayuda
"""

import asyncio
import logging
import aiohttp
from datetime import datetime

from scraper import Bet365Scraper
from notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ─── CONFIGURACIÓN ─────────────────────────────────────────────
TELEGRAM_TOKEN = "8736427026:AAEmZKoAgKgl_W7lX6qx9707O9cfmIRUXEA"
CHAT_ID        = "6421292470"
ODDS_API_KEY   = "4689f9cb119dd0db5cbb9844165a5f0f"

CHECK_INTERVAL = 300   # 5 minutos
MAX_MATCHES    = 5     # máximo por modo
MSG_DELAY      = 3     # segundos entre mensajes
SPORTS         = ["football", "tennis"]
# ───────────────────────────────────────────────────────────────

estado = {
    "pausado":  False,
    "ultimo":   "Nunca",
}


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


async def enviar_cuotas(notifier, scraper, modo="ambas"):
    """Obtiene y envía cuotas: primero aseguradas, luego arriesgadas."""
    await notifier.send_message("🔍 Buscando cuotas en las 5 grandes ligas...")
    result = await scraper.fetch_odds()

    aseguradas  = result.get("asegurada", [])[:MAX_MATCHES]
    arriesgadas = result.get("arriesgada", [])[:MAX_MATCHES]

    if modo == "asegurada":
        arriesgadas = []
    elif modo == "arriesgada":
        aseguradas = []

    total = len(aseguradas) + len(arriesgadas)
    if total == 0:
        await notifier.send_message("😔 No hay partidos disponibles ahora mismo.")
        return set()

    enviados = set()

    if aseguradas:
        await notifier.send_message("🔒 *CUOTAS ASEGURADAS* — Favoritos del momento")
        await asyncio.sleep(MSG_DELAY)
        for m in aseguradas:
            await notifier.send_match_alert(m)
            enviados.add(m["id"])
            await asyncio.sleep(MSG_DELAY)

    if arriesgadas:
        await notifier.send_message("🔥 *CUOTAS ARRIESGADAS* — Alta rentabilidad")
        await asyncio.sleep(MSG_DELAY)
        for m in arriesgadas:
            await notifier.send_match_alert(m)
            enviados.add(m["id"])
            await asyncio.sleep(MSG_DELAY)

    return enviados


async def handle_commands(notifier, scraper, offset, seen_matches):
    updates = await get_updates(TELEGRAM_TOKEN, offset)

    for update in updates:
        offset = update["update_id"] + 1
        msg    = update.get("message", {})
        text   = msg.get("text", "").strip().lower()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != CHAT_ID:
            continue

        if text == "/cuotas":
            nuevos = await enviar_cuotas(notifier, scraper, modo="ambas")
            seen_matches.update(nuevos)

        elif text == "/aseguradas":
            nuevos = await enviar_cuotas(notifier, scraper, modo="asegurada")
            seen_matches.update(nuevos)

        elif text == "/arriesgadas":
            nuevos = await enviar_cuotas(notifier, scraper, modo="arriesgada")
            seen_matches.update(nuevos)

        elif text == "/estado":
            p = "⏸ Pausado" if estado["pausado"] else "▶️ Activo"
            await notifier.send_message(
                f"📊 *Estado del bot*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{p}\n"
                f"🕐 Última revisión: *{estado['ultimo']}*\n"
                f"🔄 Intervalo: *{CHECK_INTERVAL // 60} minutos*\n"
                f"⏱ Retraso entre mensajes: *{MSG_DELAY}s*"
            )

        elif text == "/parar":
            estado["pausado"] = True
            await notifier.send_message("⏸ *Bot pausado.* Escribe /arrancar para reanudar.")

        elif text == "/arrancar":
            estado["pausado"] = False
            await notifier.send_message("▶️ *Bot reanudado.*")

        elif text in ["/ayuda", "/start"]:
            await notifier.send_message(
                "🤖 *Comandos disponibles:*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "/cuotas — Aseguradas + arriesgadas ahora\n"
                "/aseguradas — Solo favoritos (cuota baja)\n"
                "/arriesgadas — Solo cuotas altas (> 2.0)\n"
                "/estado — Ver estado del bot\n"
                "/parar — Pausar alertas automáticas\n"
                "/arrancar — Reanudar alertas\n"
                "/ayuda — Ver esta ayuda"
            )

    return offset


async def main():
    logger.info("Bot iniciado")
    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    scraper  = Bet365Scraper(sports=SPORTS, min_odds=0.0, api_key=ODDS_API_KEY)

    await notifier.send_message(
        "✅ *Bot de cuotas iniciado*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🇪🇸 LaLiga | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier | 🇩🇪 Bundesliga\n"
        "🇮🇹 Serie A | 🇫🇷 Ligue 1 | 🎾 Tenis\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 Primero aseguradas, luego arriesgadas\n"
        f"🔄 Revisando cada *{CHECK_INTERVAL // 60} minutos*\n"
        "📱 Escribe /ayuda para ver comandos"
    )

    seen_matches = set()
    offset = 0
    last_check = 0

    while True:
        offset = await handle_commands(notifier, scraper, offset, seen_matches)

        now = asyncio.get_event_loop().time()

        if not estado["pausado"] and (now - last_check) >= CHECK_INTERVAL:
            last_check = now
            estado["ultimo"] = datetime.now().strftime("%H:%M")

            try:
                result = await scraper.fetch_odds()
                aseguradas  = [m for m in result.get("asegurada",  []) if m["id"] not in seen_matches][:MAX_MATCHES]
                arriesgadas = [m for m in result.get("arriesgada", []) if m["id"] not in seen_matches][:MAX_MATCHES]

                total = len(aseguradas) + len(arriesgadas)

                if total > 0:
                    if aseguradas:
                        await notifier.send_message("🔒 *CUOTAS ASEGURADAS* — Favoritos del momento")
                        await asyncio.sleep(MSG_DELAY)
                        for m in aseguradas:
                            await notifier.send_match_alert(m)
                            seen_matches.add(m["id"])
                            await asyncio.sleep(MSG_DELAY)

                    if arriesgadas:
                        await notifier.send_message("🔥 *CUOTAS ARRIESGADAS* — Alta rentabilidad")
                        await asyncio.sleep(MSG_DELAY)
                        for m in arriesgadas:
                            await notifier.send_match_alert(m)
                            seen_matches.add(m["id"])
                            await asyncio.sleep(MSG_DELAY)

                    # Marcar todos como vistos
                    for m in result.get("asegurada", []):
                        seen_matches.add(m["id"])
                    for m in result.get("arriesgada", []):
                        seen_matches.add(m["id"])
                else:
                    logger.info("Sin partidos nuevos")

                if len(seen_matches) > 500:
                    seen_matches.clear()

            except Exception as e:
                logger.error(f"Error: {e}")
                try:
                    await notifier.send_message(f"⚠️ Error: {e}")
                except:
                    pass

        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())




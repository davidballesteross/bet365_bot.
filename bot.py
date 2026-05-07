#!/usr/bin/env python3
"""
Bet365 Odds Alert Bot for Telegram
- Alertas automáticas cada 5 minutos (máx 5 partidos)
- Comandos desde el móvil: /cuotas /estado /parar /arrancar /minima
"""

import asyncio
import logging
import aiohttp

from scraper import Bet365Scraper
from notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ─── CONFIGURACIÓN ─────────────────────────────────────────────

TELEGRAM_TOKEN = "8736427026:AAEmZKoAgKgl_W7lX6qx9707O9cfmIRUXEA"
CHAT_ID        = "6421292470"
ODDS_API_KEY   = "4689f9cb119dd0db5cbb9844165a5f0f"

MIN_ODDS       = 2.0
CHECK_INTERVAL = 300   # segundos (5 minutos)
MAX_MATCHES    = 5     # máximo de partidos por ciclo

SPORTS = ["football", "tennis"]

# ───────────────────────────────────────────────────────────────

estado = {
    "activo":  True,
    "min_odds": MIN_ODDS,
    "ultimo":  "Nunca",
    "pausado": False,
}


async def get_updates(token: str, offset: int) -> list:
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": 10}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                return data.get("result", [])
    except Exception:
        return []


async def handle_commands(notifier, scraper, offset: int) -> int:
    updates = await get_updates(TELEGRAM_TOKEN, offset)

    for update in updates:
        offset = update["update_id"] + 1
        message = update.get("message", {})
        text = message.get("text", "").strip().lower()
        chat_id = str(message.get("chat", {}).get("id", ""))

        if chat_id != CHAT_ID:
            continue

        if text == "/cuotas":
            await notifier.send_message("🔍 Buscando mejores cuotas ahora...")
            matches = await scraper.fetch_odds()
            top = sorted(matches, key=lambda m: m["best_odd"], reverse=True)[:MAX_MATCHES]
            if top:
                for m in top:
                    await notifier.send_match_alert(m)
            else:
                await notifier.send_message("😔 No hay partidos con cuota ≥ " + str(estado["min_odds"]) + " ahora mismo.")

        elif text == "/estado":
            pausado = "⏸ Pausado" if estado["pausado"] else "▶️ Activo"
            await notifier.send_message(
                f"📊 *Estado del bot*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Estado: {pausado}\n"
                f"💰 Cuota mínima: *{estado['min_odds']}*\n"
                f"🕐 Última revisión: *{estado['ultimo']}*\n"
                f"🔄 Intervalo: *{CHECK_INTERVAL // 60} minutos*"
            )

        elif text == "/parar":
            estado["pausado"] = True
            await notifier.send_message("⏸ *Bot pausado.* Las alertas automáticas se han detenido.\nEscribe /arrancar para reanudar.")

        elif text == "/arrancar":
            estado["pausado"] = False
            await notifier.send_message("▶️ *Bot reanudado.* Volviendo a monitorear cuotas.")

        elif text.startswith("/minima"):
            parts = text.split()
            if len(parts) == 2:
                try:
                    nueva = float(parts[1])
                    if nueva < 1.0 or nueva > 20.0:
                        await notifier.send_message("⚠️ La cuota mínima debe estar entre 1.0 y 20.0")
                    else:
                        estado["min_odds"] = nueva
                        scraper.min_odds = nueva
                        await notifier.send_message(f"✅ Cuota mínima actualizada a *{nueva}*")
                except ValueError:
                    await notifier.send_message("⚠️ Uso correcto: `/minima 2.5`")
            else:
                await notifier.send_message("⚠️ Uso correcto: `/minima 2.5`")

        elif text in ["/ayuda", "/start"]:
            await notifier.send_message(
                "🤖 *Comandos disponibles:*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "/cuotas — Ver los 5 mejores partidos ahora\n"
                "/estado — Ver estado del bot\n"
                "/parar — Pausar alertas automáticas\n"
                "/arrancar — Reanudar alertas automáticas\n"
                "/minima X — Cambiar cuota mínima (ej: /minima 2.5)\n"
                "/ayuda — Ver esta ayuda"
            )

    return offset


async def main():
    logger.info("Bot iniciado — usando The Odds API")

    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    scraper  = Bet365Scraper(sports=SPORTS, min_odds=MIN_ODDS, api_key=ODDS_API_KEY)

    await notifier.send_message(
        f"✅ *Bot de cuotas iniciado*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚽ Fútbol | 🎾 Tenis\n"
        f"💰 Cuota mínima: *{MIN_ODDS}*\n"
        f"🔄 Revisando cada *{CHECK_INTERVAL // 60} minutos*\n"
        f"📱 Escribe /ayuda para ver comandos"
    )

    seen_matches = set()
    offset = 0
    last_check = 0

    while True:
        offset = await handle_commands(notifier, scraper, offset)

        now = asyncio.get_event_loop().time()

        if not estado["pausado"] and (now - last_check) >= CHECK_INTERVAL:
            last_check = now

            try:
                from datetime import datetime
                estado["ultimo"] = datetime.now().strftime("%H:%M")
                logger.info("Buscando partidos con buenas cuotas...")
                matches = await scraper.fetch_odds()

                new_matches = [m for m in matches if m["id"] not in seen_matches]
                top_new = sorted(new_matches, key=lambda m: m["best_odd"], reverse=True)[:MAX_MATCHES]

                if top_new:
                    logger.info(f"{len(top_new)} partidos enviados (de {len(new_matches)} encontrados)")
                    for match in top_new:
                        await notifier.send_match_alert(match)
                        seen_matches.add(match["id"])
                        await asyncio.sleep(0.5)
                    for m in new_matches:
                        seen_matches.add(m["id"])
                else:
                    logger.info("Sin nuevas cuotas por encima del umbral")

                if len(seen_matches) > 500:
                    seen_matches.clear()
                    logger.info("Cache reiniciada")

            except Exception as e:
                logger.error(f"Error en el ciclo principal: {e}")
                try:
                    await notifier.send_message(f"⚠️ Error monitoreando: {e}")
                except:
                    pass

        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())



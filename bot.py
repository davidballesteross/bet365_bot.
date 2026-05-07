#!/usr/bin/env python3
"""
Bet365 Odds Alert Bot for Telegram
Usa The Odds API para obtener cuotas en tiempo real.
"""

import asyncio
import logging

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

# Pega aquí tu API key de https://the-odds-api.com
ODDS_API_KEY   = "4689f9cb119dd0db5cbb9844165a5f0f"

MIN_ODDS       = 2.0
CHECK_INTERVAL = 300  # segundos (5 minutos)

# Ligas disponibles en scraper.py → SPORT_KEYS
SPORTS = [
    "football",
    "tennis",
]

# ───────────────────────────────────────────────────────────────


async def main():
    logger.info("Bot iniciado — usando The Odds API")

    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    scraper  = Bet365Scraper(sports=SPORTS, min_odds=MIN_ODDS, api_key=ODDS_API_KEY)

    await notifier.send_message(
        f"✅ *Bot de cuotas iniciado*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚽ Fútbol | 🎾 Tenis\n"
        f"💰 Cuota mínima: *{MIN_ODDS}*\n"
        f"🔄 Revisando cada *{CHECK_INTERVAL // 60} minutos*"
    )

    seen_matches = set()

    while True:
        try:
            logger.info("Buscando partidos con buenas cuotas...")
            matches = await scraper.fetch_odds()

            new_matches = [m for m in matches if m["id"] not in seen_matches]

            if new_matches:
                logger.info(f"{len(new_matches)} nuevos partidos encontrados")
                for match in new_matches:
                    await notifier.send_match_alert(match)
                    seen_matches.add(match["id"])
                    await asyncio.sleep(0.5)
            else:
                logger.info("Sin nuevas cuotas por encima del umbral")

            # Limpiar cache si crece demasiado
            if len(seen_matches) > 500:
                seen_matches.clear()
                logger.info("Cache reiniciada")

        except Exception as e:
            logger.error(f"Error en el ciclo principal: {e}")
            try:
                await notifier.send_message(f"⚠️ Error monitoreando: {e}")
            except:
                pass

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())

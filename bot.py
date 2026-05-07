#!/usr/bin/env python3
"""
Bet365 Odds Alert Bot for Telegram
Monitors football and tennis odds, alerts when odds >= 2.0
"""

import asyncio
import logging
import os

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

# ─── CONFIGURATION ─────────────────────────────────────────────

# PON AQUI TU TOKEN REAL
TELEGRAM_TOKEN = 8736427026:AAEmZKoAgKgl_W7lX6qx9707O9cfmIRUXEA

# PON AQUI TU CHAT ID REAL
CHAT_ID = 6421292470

MIN_ODDS = 2.0
CHECK_INTERVAL = 300

SPORTS = [
    "football",
    "tennis"
]

# ───────────────────────────────────────────────────────────────


async def main():

    logger.info("Bot iniciado - monitoreando Bet365...")

    notifier = TelegramNotifier(
        TELEGRAM_TOKEN,
        CHAT_ID
    )

    scraper = Bet365Scraper(
        sports=SPORTS,
        min_odds=MIN_ODDS
    )

    await notifier.send_message(
        f"""
Bot de cuotas Bet365 iniciado

Deportes:
- Futbol
- Tenis

Cuota minima: {MIN_ODDS}

Revisando cada {CHECK_INTERVAL // 60} minutos
"""
    )

    seen_matches = set()

    while True:

        try:

            logger.info("Buscando partidos con buenas cuotas...")

            matches = await scraper.fetch_odds()

            new_matches = [
                m for m in matches
                if m["id"] not in seen_matches
            ]

            if new_matches:

                logger.info(
                    f"{len(new_matches)} nuevos partidos encontrados"
                )

                for match in new_matches:

                    await notifier.send_match_alert(match)

                    seen_matches.add(match["id"])

                    await asyncio.sleep(0.5)

            else:

                logger.info(
                    "Sin nuevas cuotas por encima del umbral"
                )

            if len(seen_matches) > 500:

                seen_matches.clear()

                logger.info(
                    "Cache de partidos reiniciada"
                )

        except Exception as e:

            logger.error(
                f"Error en el ciclo principal: {e}"
            )

            try:
                await notifier.send_message(
                    f"Error monitoreando: {e}"
                )
            except:
                pass

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
El archivo bot.py está vacío. Por eso se cierra inmediatamente. Vamos a escribirlo directamente desde la terminal:
bashcat > bot.py << 'EOF'
#!/usr/bin/env python3
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

TELEGRAM_TOKEN = "8736427026:AAEmZKoAgKgl_W7lX6qx9707O9cfmIRUXEA"
CHAT_ID        = "6421292470"
ODDS_API_KEY   = "4689f9cb119dd0db5cbb9844165a5f0f"
MIN_ODDS       = 2.0
CHECK_INTERVAL = 300
MAX_MATCHES    = 5
SPORTS         = ["football", "tennis"]

estado = {"pausado": False, "min_odds": MIN_ODDS, "ultimo": "Nunca"}

async def get_updates(token, offset):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params={"offset": offset, "timeout": 5}, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                return data.get("result", [])
    except:
        return []

async def handle_commands(notifier, scraper, offset):
    updates = await get_updates(TELEGRAM_TOKEN, offset)
    for update in updates:
        offset = update["update_id"] + 1
        msg = update.get("message", {})
        text = msg.get("text", "").strip().lower()
        chat_id = str(msg.get("chat", {}).get("id", ""))
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
                await notifier.send_message(f"😔 No hay partidos con cuota ≥ {estado['min_odds']}")
        elif text == "/estado":
            p = "⏸ Pausado" if estado["pausado"] else "▶️ Activo"
            await notifier.send_message(f"📊 *Estado del bot*\n{p}\n💰 Cuota mínima: *{estado['min_odds']}*\n🕐 Última revisión: *{estado['ultimo']}*")
        elif text == "/parar":
            estado["pausado"] = True
            await notifier.send_message("⏸ *Bot pausado.* Escribe /arrancar para reanudar.")
        elif text == "/arrancar":
            estado["pausado"] = False
            await notifier.send_message("▶️ *Bot reanudado.*")
        elif text.startswith("/minima"):
            parts = text.split()
            if len(parts) == 2:
                try:
                    nueva = float(parts[1])
                    estado["min_odds"] = nueva
                    scraper.min_odds = nueva
                    await notifier.send_message(f"✅ Cuota mínima actualizada a *{nueva}*")
                except:
                    await notifier.send_message("⚠️ Uso: /minima 2.5")
        elif text in ["/ayuda", "/start"]:
            await notifier.send_message(
                "🤖 *Comandos disponibles:*\n"
                "/cuotas — Ver los 5 mejores ahora\n"
                "/estado — Ver estado del bot\n"
                "/parar — Pausar alertas\n"
                "/arrancar — Reanudar alertas\n"
                "/minima X — Cambiar cuota mínima\n"
                "/ayuda — Ver esta ayuda"
            )
    return offset

async def main():
    logger.info("Bot iniciado")
    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    scraper  = Bet365Scraper(sports=SPORTS, min_odds=MIN_ODDS, api_key=ODDS_API_KEY)
    await notifier.send_message(
        f"✅ *Bot iniciado*\n⚽ Fútbol | 🎾 Tenis\n💰 Cuota mínima: *{MIN_ODDS}*\n📱 Escribe /ayuda para ver comandos"
    )
    seen_matches = set()
    offset = 0
    last_check = 0
    while True:
        offset = await handle_commands(notifier, scraper, offset)
        now = asyncio.get_event_loop().time()
        if not estado["pausado"] and (now - last_check) >= CHECK_INTERVAL:
            last_check = now
            estado["ultimo"] = datetime.now().strftime("%H:%M")
            try:
                matches = await scraper.fetch_odds()
                new_matches = [m for m in matches if m["id"] not in seen_matches]
                top_new = sorted(new_matches, key=lambda m: m["best_odd"], reverse=True)[:MAX_MATCHES]
                if top_new:
                    for match in top_new:
                        await notifier.send_match_alert(match)
                        seen_matches.add(match["id"])
                        await asyncio.sleep(0.5)
                    for m in new_matches:
                        seen_matches.add(m["id"])
                if len(seen_matches) > 500:
                    seen_matches.clear()
            except Exception as e:
                logger.error(f"Error: {e}")
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
EOF

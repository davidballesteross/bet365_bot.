"""
Telegram Notifier — formato claro con favorito, rival y cuotas reales.
"""
import logging
import aiohttp
from typing import Dict

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = chat_id
        self.base    = f"https://api.telegram.org/bot{token}"

    async def send_message(self, text: str) -> bool:
        url     = f"{self.base}/sendMessage"
        payload = {
            "chat_id":    self.chat_id,
            "text":       text,
            "parse_mode": "Markdown",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    if not data.get("ok"):
                        logger.error(f"Telegram error: {data}")
                    return data.get("ok", False)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            return False

    async def send_match_alert(self, match: Dict, modo: str = "asegurada") -> bool:
        liga        = match["liga"]
        favorito    = match["favorito"]
        rival       = match["rival"]
        odd_fav     = match["odd_favorito"]
        odd_riv     = match["odd_rival"]
        odd_emp     = match.get("odd_empate")
        fecha       = match["fecha"]
        confianza   = match.get("confianza", 0)
        bookmakers  = match.get("bookmakers", 0)

        if modo == "asegurada":
            emoji  = "🔒"
            titulo = f"APUESTA ASEGURADA — Gana *{favorito}*"
        else:
            emoji  = "🔥"
            titulo = f"APUESTA ARRIESGADA — Gana *{favorito}*"

        if confianza >= 75:
            conf_emoji = "🟢"
        elif confianza >= 50:
            conf_emoji = "🟡"
        else:
            conf_emoji = "🔴"

        empate_linea = f"🤝 Empate: *{odd_emp:.2f}*\n" if odd_emp else ""
        text = (
            f"{emoji} {titulo}\n"
            f"{'─' * 28}\n"
            f"{liga}\n"
            f"📅 {fecha} (hora España)\n"
            f"{'─' * 28}\n"
            f"✅ Gana *{favorito}*: *{odd_fav:.2f}*\n"
            f"{empate_linea}"
            f"❌ Gana *{rival}*: *{odd_riv:.2f}*\n"
            f"{'─' * 28}\n"
            f"{conf_emoji} Confianza: *{confianza}%* | 📚 {bookmakers} bookmakers\n"
            f"{'─' * 28}\n"
            f"[Ver en Bet365](https://www.bet365.com)"
        )
        return await self.send_message(text)

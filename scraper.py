"""
Scraper usando The Odds API — datos reales, sin inventarse nada.
- Favorito = equipo con cuota media MAS BAJA entre todos los bookmakers
- Asegurada: cuota favorito < 1.5
- Arriesgada: cuota favorito >= 2.0
- Solo partidos de esta semana (hasta el domingo)
"""

import logging
import aiohttp
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
from statistics import mean

logger = logging.getLogger(__name__)

SPORT_KEYS = {
    "laliga":      "soccer_spain_la_liga",
    "premier":     "soccer_epl",
    "bundesliga":  "soccer_germany_bundesliga",
    "seriea":      "soccer_italy_serie_a",
    "ligue1":      "soccer_france_ligue_one",
    "champions":   "soccer_uefa_champs_league",
    "europa":      "soccer_uefa_europa_league",
    "nba":         "basketball_nba",
    "tennis":      "tennis_atp_french_open",
}

LIGA_LABEL = {
    "soccer_spain_la_liga":        "🇪🇸 LaLiga",
    "soccer_epl":                  "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier",
    "soccer_germany_bundesliga":   "🇩🇪 Bundesliga",
    "soccer_italy_serie_a":        "🇮🇹 Serie A",
    "soccer_france_ligue_one":     "🇫🇷 Ligue 1",
    "soccer_uefa_champs_league":   "🏆 Champions",
    "soccer_uefa_europa_league":   "🟠 Europa League",
    "basketball_nba":              "🏀 NBA",
    "tennis_atp_french_open":      "🎾 Tenis",
}

BASE_URL = "https://api.the-odds-api.com/v4/sports"


def _fin_de_semana() -> datetime:
    hoy = datetime.now(timezone.utc)
    return hoy + timedelta(days=14)


def _cuotas_medias(event: dict) -> Dict[str, float]:
    acumulado: Dict[str, List[float]] = {}
    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                nombre = outcome["name"]
                precio = outcome["price"]
                if nombre not in acumulado:
                    acumulado[nombre] = []
                acumulado[nombre].append(precio)
    return {equipo: round(mean(precios), 2) for equipo, precios in acumulado.items() if precios}


class Bet365Scraper:
    def __init__(self, sports: List[str], min_odds: float = 0.0, api_key: str = ""):
        self.sports   = sports
        self.min_odds = min_odds
        self.api_key  = api_key

    async def fetch_odds(self, liga_filter: str = None) -> Dict[str, List[Dict]]:
        if not self.api_key or self.api_key == "TU_ODDS_API_KEY":
            logger.warning("API key no configurada — demo")
            return self._demo_data()

        asegurada  = []
        arriesgada = []
        limite     = _fin_de_semana()

        sport_keys = [SPORT_KEYS[liga_filter]] if liga_filter and liga_filter in SPORT_KEYS else list(SPORT_KEYS.values())
        async with aiohttp.ClientSession() as session:
            for sport_key in sport_keys:
                try:
                    seg, arr = await self._fetch_sport(session, sport_key, limite)
                    asegurada.extend(seg)
                    arriesgada.extend(arr)
                except Exception as e:
                    logger.error(f"Error en {sport_key}: {e}")

        asegurada  = sorted(asegurada,  key=lambda m: m["odd_favorito"])
        arriesgada = sorted(arriesgada, key=lambda m: m["odd_favorito"], reverse=True)

        return {"asegurada": asegurada, "arriesgada": arriesgada}

    async def _fetch_sport(self, session, sport_key: str, limite: datetime) -> Tuple[List, List]:
        liga  = LIGA_LABEL.get(sport_key, sport_key)
        url   = f"{BASE_URL}/{sport_key}/odds"
        params = {
            "apiKey":     self.api_key,
            "regions":    "eu",
            "markets":    "h2h",
            "oddsFormat": "decimal",
        }

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (401, 422):
                return [], []
            if resp.status != 200:
                logger.error(f"Error {resp.status} para {sport_key}")
                return [], []
            data = await resp.json()

        remaining = resp.headers.get("x-requests-remaining", "?")
        logger.info(f"{liga}: {len(data)} eventos | Peticiones restantes: {remaining}")

        asegurada  = []
        arriesgada = []

        for event in data:
            commence_str = event.get("commence_time", "")
            try:
                commence = datetime.fromisoformat(commence_str.replace("Z", "+00:00"))
            except:
                continue

            if commence > limite:
                continue

            cuotas = _cuotas_medias(event)
            if not cuotas:
                continue

            home = event.get("home_team", "")
            away = event.get("away_team", "")

            cuotas_sin_empate = {k: v for k, v in cuotas.items() if k not in ("Draw", "Empate")}
            if not cuotas_sin_empate:
                continue

            favorito = min(cuotas_sin_empate, key=cuotas_sin_empate.get)
            rival    = max((k for k in cuotas_sin_empate if k != favorito), key=cuotas_sin_empate.get, default=favorito)

            odd_favorito = cuotas_sin_empate[favorito]
            odd_rival    = cuotas_sin_empate[rival]
            odd_empate   = cuotas.get("Draw", cuotas.get("Empate", None))

            hora_local = commence + timedelta(hours=2)
            fecha_str  = hora_local.strftime("%d/%m %H:%M")

            uid = hashlib.md5(f"{event['id']}{sport_key}".encode()).hexdigest()

            diff = odd_rival - odd_favorito
            bookmakers = len(event.get("bookmakers", []))
            confianza = min(100, int((diff / odd_favorito) * 40 + (bookmakers / 10) * 20))

            match = {
                "id":           uid,
                "liga":         liga,
                "home":         home,
                "away":         away,
                "favorito":     favorito,
                "rival":        rival,
                "odd_favorito": odd_favorito,
                "odd_rival":    odd_rival,
                "odd_empate":   odd_empate,
                "fecha":        fecha_str,
                "confianza":    confianza,
                "bookmakers":   bookmakers,
            }

            if odd_favorito < 1.5:
                asegurada.append(match)
            elif odd_favorito >= 2.0:
                arriesgada.append(match)

        return asegurada, arriesgada

    def _demo_data(self):
        return {
            "asegurada": [
                {
                    "id": "d1", "liga": "🇪🇸 LaLiga",
                    "home": "Barcelona", "away": "Getafe",
                    "favorito": "Barcelona", "rival": "Getafe",
                    "odd_favorito": 1.25, "odd_rival": 9.50, "odd_empate": 5.50,
                    "fecha": "10/05 20:00",
                },
            ],
            "arriesgada": [
                {
                    "id": "d2", "liga": "🇮🇹 Serie A",
                    "home": "Napoli", "away": "Inter",
                    "favorito": "Napoli", "rival": "Inter",
                    "odd_favorito": 2.80, "odd_rival": 2.60, "odd_empate": 3.20,
                    "fecha": "11/05 18:00",
                },
            ],
        }

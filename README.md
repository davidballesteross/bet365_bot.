# 🤖 Bot de Cuotas → Telegram

Recibe alertas automáticas en Telegram con los mejores partidos de la semana ordenados por confianza. Usa datos reales de múltiples casas de apuestas a través de **The Odds API**.

## ✨ Qué hace

- Monitoriza **LaLiga, Premier, Bundesliga, Serie A, Ligue 1, Champions, Europa League, NBA y Tenis**
- Clasifica los partidos en **apuestas aseguradas** (favorito claro, cuota < 1.5) y **arriesgadas** (partido equilibrado, cuota ≥ 2.0)
- Calcula la **confianza** de cada apuesta cruzando datos de múltiples bookmakers
- Envía alertas automáticas cada 3 horas y responde a comandos en tiempo real

---

## 📋 Requisitos

- Python 3.11+ **o** Docker
- Una cuenta de Telegram
- API Key gratuita de [The Odds API](https://the-odds-api.com) (500 peticiones/mes gratis)

---

## 🚀 Instalación

### 1. Clona el repositorio

```bash
git clone https://github.com/TU_USUARIO/bet365_bot.git
cd bet365_bot
```

### 2. Instala las dependencias

```bash
pip install -r requirements.txt
```

### 3. Configura tus credenciales

```bash
cp .env.example .env
nano .env
```

Rellena los tres valores (ver sección **Cómo obtener las credenciales** más abajo).

### 4. Arranca el bot

```bash
python bot.py
```

O en segundo plano:

```bash
bash start.sh
tail -f bot.log
```

---

## 🐳 Instalación con Docker

```bash
cp .env.example .env
# edita .env con tus datos
docker-compose up -d
```

---

## 🔑 Cómo obtener las credenciales

### Token de Telegram (`TELEGRAM_TOKEN`)
1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot` y sigue los pasos
3. BotFather te dará un token con el formato `123456789:AAxxxxxxx...`
4. Cópialo en `.env` como `TELEGRAM_TOKEN=...`

### Tu Chat ID (`CHAT_ID`)
1. Busca **@userinfobot** en Telegram
2. Escribe `/start`
3. Te mostrará tu ID numérico (ej. `987654321`)
4. Cópialo en `.env` como `CHAT_ID=...`

### API Key de The Odds API (`ODDS_API_KEY`)
1. Regístrate gratis en [the-odds-api.com](https://the-odds-api.com)
2. En tu dashboard verás tu API key
3. El plan gratuito incluye **500 peticiones/mes**
4. Cópiala en `.env` como `ODDS_API_KEY=...`

---

## ⚙️ Variables de configuración (`.env`)

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `TELEGRAM_TOKEN` | Token de tu bot de Telegram | — |
| `CHAT_ID` | Tu ID de chat donde llegan las alertas | — |
| `ODDS_API_KEY` | API key de the-odds-api.com | — |
| `MIN_ODDS` | Cuota mínima para recibir alerta | `2.0` |
| `CHECK_INTERVAL` | Segundos entre comprobaciones | `10800` (3h) |

---

## 📱 Comandos disponibles en Telegram

| Comando | Descripción |
|---|---|
| `/cuotas` | Todos los partidos de la semana |
| `/aseguradas` | Solo favoritos claros (cuota < 1.5) |
| `/arriesgadas` | Partidos equilibrados (cuota ≥ 2.0) |
| `/mejor` | Top 5 apuestas por confianza |
| `/combinada` | Ver opciones de combinadas |
| `/combinada_baja` | Combinada de 4 partidos seguros |
| `/combinada_media` | Combinada de 5 partidos equilibrados |
| `/combinada_alta` | Combinada de 6 partidos arriesgados |
| `/liga laliga` | Filtrar por liga (laliga, premier, bundesliga, seriea, ligue1, champions, europa, nba) |
| `/estado` | Estado actual del bot |
| `/parar` | Pausar alertas automáticas |
| `/arrancar` | Reanudar alertas automáticas |

---

## 📨 Ejemplo de alerta

```
🔒 APUESTA ASEGURADA — Gana Barcelona
────────────────────────────────
🇪🇸 LaLiga
📅 10/05 20:00 (hora España)
────────────────────────────────
✅ Gana Barcelona: 1.28
🤝 Empate: 5.50
❌ Gana Getafe: 9.50
────────────────────────────────
🟢 Confianza: 82% | 📚 12 bookmakers
────────────────────────────────
Ver en Bet365
```

---

## 📁 Estructura del proyecto

```
bet365_bot/
├── bot.py             # Loop principal y gestión de comandos
├── scraper.py         # Obtención y análisis de cuotas (The Odds API)
├── notifier.py        # Envío de alertas por Telegram
├── scheduler.py       # Resumen diario automático
├── state.py           # Persistencia del estado entre reinicios
├── requirements.txt   # Dependencias Python
├── .env.example       # Plantilla de configuración (rellena y renombra a .env)
├── Dockerfile         # Imagen Docker
├── docker-compose.yml
└── start.sh           # Script de arranque en segundo plano
```

---

## 🔧 Solución de problemas

| Problema | Solución |
|---|---|
| `Telegram error 401` | Token incorrecto — revisa `TELEGRAM_TOKEN` en `.env` |
| `Telegram error 400` | Chat ID incorrecto — usa @userinfobot para obtenerlo |
| Sin partidos disponibles | API key incorrecta o sin peticiones restantes |
| El bot no arranca | Comprueba dependencias: `pip install -r requirements.txt` |

---

## ⚠️ Aviso

Este bot usa datos públicos de cuotas para informar, no para garantizar resultados. Apuesta siempre de forma responsable.

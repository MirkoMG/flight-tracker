# ✈️ BoA Flight Price Tracker

Automated flight price tracker for **Boliviana de Aviación (BoA)** routes — and any other airline, as long as you have the correct IATA airport codes. Polls Google Flights on a configurable interval and sends **Telegram notifications** when prices go up or down.

No paid API needed — built on [`fast-flights`](https://github.com/AWeirdDev/flights), a free open-source library that reverse-engineers Google Flights' internal Protobuf encoding.

---

## How it works

```
Every N minutes
  └── Query Google Flights for each tracked route (via fast-flights)
  └── Compare current price to last stored price
  └── If change ≥ threshold → send Telegram alert
  └── Save price history to JSON
```

Telegram alert example:
```
✈️ Tarija → Cochabamba — 2026-07-15
💰 BOB 714  🔴 UP +151
🕐 20:50 → 21:50  (Direct)
🛫 BoA OB533
📊 Previous: BOB 563
🕓 2026-06-10 23:40
```

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/mirkomg/boa-flight-tracker
cd boa-flight-tracker

python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 2. Create a Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **token** it gives you (e.g. `123456:ABC-DEF...`)
4. Send any message to your new bot, something like "hello bot"
5. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
6. Find `"chat":{"id": 123456789}` — that number is your chat ID

### 3. Configure environment variables

Create a `.env` file in the project root:

You can copy the `.env.example` with this command and fill your secrets. 

```bash
cp .env.example .env
```

```
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=987654321
```

### 4. Add routes to track

Edit the `FLIGHTS_TO_TRACK` list in `tracker.py`:

```python
FLIGHTS_TO_TRACK = [
    {
        "origin": "TJA",           # IATA airport code
        "destination": "CBB",
        "date": "2026-07-15",      # YYYY-MM-DD
        "label": "Tarija → Cochabamba",
    },
    {
        "origin": "CBB",
        "destination": "LPB",
        "date": "2026-07-20",
        "label": "Cbba → La Paz",
    },
]
```

## Finding airport codes

Use any of these to look up IATA codes for any airport in the world:

- **[IATA official search](https://www.iata.org/en/publications/directories/code-search/)** — the authoritative source
- **[Nations Online — full alphabetical list](https://www.nationsonline.org/oneworld/IATA_Codes/airport_code_list.htm)** — comprehensive browsable list
- **Google** — just search `"city name" airport IATA code`, it shows instantly


Common BoA airport codes:

| City | Code |
|------|------|
| Cochabamba | CBB |
| La Paz | LPB |
| Santa Cruz | VVI |
| Tarija | TJA |
| Sucre | SRE |
| Oruro | ORU |
| Trinidad | TDD |
| Cobija | CIJ |


### 5. Run

```bash
python tracker.py
```

---

## Configuration

All options are at the top of `tracker.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CHECK_INTERVAL_MINUTES` | `60` | How often to poll in minutes |
| `MIN_CHANGE_THRESHOLD` | `100` | Minimum BOB change to trigger a notification |
| `HISTORY_FILE` | `price_history.json` | Where price history is stored |

---

## Deploy to a server (no laptop needed)

### Railway (easiest)

```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

Add `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` under Variables in the Railway dashboard.

### Render

1. Push this repo to GitHub
2. Create a new **Background Worker** on [render.com](https://render.com)
3. Build command: `pip install -r requirements.txt`
4. Start command: `python tracker.py`
5. Add env vars in the Render dashboard

---

## Project structure

```
boa-flight-tracker/
├── tracker.py          # main script
├── requirements.txt
├── .env                # your credentials 
├── .env.example
├── .gitignore
├── price_history.json  # auto-generated, stores last known prices
└── README.md
```

---

## Roadmap

- [ ] Telegram bot commands to add/remove routes without editing code
- [ ] Multi-user support with database (SQLite → Postgres)
- [ ] Add Multi Currency
- [ ] Round-trip flight tracking
- [ ] Price history chart
- [ ] Track cheapest date in a range

---

## Disclaimer

Prices are sourced from Google Flights and may differ from BoA's website due to GDS cache delays. Always confirm availability and price directly on [boa.bo](https://www.boa.bo) before booking.

---

## Tech stack

- **Python 3.11+**
- [`fast-flights`](https://github.com/AWeirdDev/flights) — free Google Flights scraper via Protobuf reverse engineering
- [`schedule`](https://github.com/dbader/schedule) — lightweight Python job scheduler
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) — environment variable management
- [Telegram Bot API](https://core.telegram.org/bots/api) — push notifications

---

## License

MIT
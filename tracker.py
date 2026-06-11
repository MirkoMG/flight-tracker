"""
BoA Flight Price Tracker
Uses fast-flights (free, no API key) to poll Google Flights for BoA routes
and sends Telegram notifications when prices change.

Setup:
  pip install fast-flights schedule requests
"""

import json
import os
import time
import schedule
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv


from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter

# ─────────────────────────────────────────────
# CONFIG — edit these or set as env vars
# ─────────────────────────────────────────────

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Flights to track — add as many routes/dates as you want
FLIGHTS_TO_TRACK = [
    {
        "origin": "TJA",  # IATA code
        "destination": "CBB",  # IATA code
        "date": "2026-06-20",  # YYYY-MM-DD
        "label": "Tarija → Cochabamba",
    },
    {
        "origin": "CBB",
        "destination": "TJA",
        "date": "2026-06-20",
        "label": "Cochabamba → Tarija",
    },
]

# How often to check (in minutes)
CHECK_INTERVAL_MINUTES = 60

# Only notify if price changes by at least this much (in whatever currency returned)
# Set to 0 to notify on any change at all
MIN_CHANGE_THRESHOLD = 100

# File to persist price history between runs
HISTORY_FILE = Path("price_history.json")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────


def load_history() -> dict:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return {}


def save_history(history: dict):
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def flight_key(flight: dict) -> str:
    return f"{flight['origin']}-{flight['destination']}-{flight['date']}"


def parse_price(price_str: str) -> float | None:
    """
    Converts a price string like 'BOB876' or '$120' or '876' into a float.
    Returns None if it can't be parsed.
    """
    if not price_str:
        return None
    # Strip currency symbols and letters, keep digits and decimal point
    cleaned = ""
    for ch in str(price_str):
        if ch.isdigit() or ch == ".":
            cleaned += ch
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def fetch_price(origin: str, destination: str, date: str) -> dict | None:
    """
    Uses fast-flights to query Google Flights.
    Returns a dict with price and flight details, or None on error.
    """
    try:
        flight_filter = create_filter(
            flight_data=[
                FlightData(date=date, from_airport=origin, to_airport=destination)
            ],
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=1),
        )
        result = get_flights_from_filter(flight_filter, currency="BOB", mode="fallback")
    except Exception as e:
        print(f"  [ERROR] fast-flights request failed: {e}")
        return None

    if not result or not result.flights:
        print(f"  [WARN] No flights returned for {origin}→{destination} on {date}")
        return None

    # current_price is the price label Google shows (e.g. "typical", "low", "high")
    # The actual cheapest price is on result.flights[0]
    cheapest = result.flights[0]

    raw_price = getattr(cheapest, "price", None)
    price_val = parse_price(str(raw_price)) if raw_price else None

    # Grab departure/arrival from first leg if available
    departure_time = "?"
    arrival_time = "?"
    airline = "BoA"
    flight_number = "?"
    stops = 0

    if hasattr(cheapest, "segments") and cheapest.segments:
        seg = cheapest.segments[0]
        departure_time = getattr(seg, "departure_time", "?") or "?"
        arrival_time = getattr(seg, "arrival_time", "?") or "?"
        airline = getattr(seg, "airline", "BoA") or "BoA"
        flight_number = getattr(seg, "flight_number", "?") or "?"
    elif hasattr(cheapest, "departure"):
        departure_time = str(getattr(cheapest, "departure", "?"))
        arrival_time = str(getattr(cheapest, "arrival", "?"))

    if hasattr(cheapest, "stops"):
        stops = cheapest.stops or 0

    return {
        "price": price_val,
        "price_raw": str(raw_price),
        "price_label": getattr(result, "current_price", ""),  # "typical", "low", etc.
        "departure_time": str(departure_time),
        "arrival_time": str(arrival_time),
        "airline": str(airline),
        "flight_number": str(flight_number),
        "stops": stops,
        "checked_at": datetime.now().isoformat(),
    }


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"  [TELEGRAM] Notification sent ✓")
    except Exception as e:
        print(f"  [ERROR] Telegram failed: {e}")


def format_message(
    label: str,
    date: str,
    current: dict,
    previous: dict | None,
    change: float | None,
) -> str:
    direction = ""
    if change is not None:
        if change < 0:
            direction = f"🟢 DOWN {abs(change):.0f}"
        elif change > 0:
            direction = f"🔴 UP +{change:.0f}"
        else:
            direction = "⚪ no change"

    stops_label = "Direct" if current["stops"] == 0 else f"{current['stops']} stop(s)"
    price_label = (
        f"  <i>({current['price_label']})</i>" if current.get("price_label") else ""
    )

    lines = [
        f"✈️  <b>{label}</b> — {date}",
        f"💰 <b>{current['price_raw']}</b>{price_label}  {direction}",
        f"🕐 {current['departure_time']} → {current['arrival_time']}  ({stops_label})",
        f"🛫 {current['airline']} {current['flight_number']}",
    ]
    if previous and previous.get("price_raw"):
        lines.append(f"📊 Previous: {previous['price_raw']}")
    lines.append(f"🕓 {current['checked_at'][:16].replace('T', ' ')}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# CORE LOOP
# ─────────────────────────────────────────────


def check_flight(flight: dict, history: dict, notify_always: bool = False):
    key = flight_key(flight)
    label = flight["label"]
    date = flight["date"]

    print(f"  Checking {label} on {date}...")

    current = fetch_price(flight["origin"], flight["destination"], date)
    if not current:
        print(f"  Skipping {key} — could not fetch price.")
        return

    previous = history.get(key)
    change = None

    if previous and previous.get("price") and current.get("price"):
        change = current["price"] - previous["price"]
        significant = abs(change) >= MIN_CHANGE_THRESHOLD

        print(
            f"  Previous: {previous['price_raw']}  |  Current: {current['price_raw']}  |  Δ {change:+.0f}"
        )

        if significant or notify_always:
            send_telegram(format_message(label, date, current, previous, change))
        else:
            print(f"  No significant change (threshold: ±{MIN_CHANGE_THRESHOLD})")
    else:
        # First time seeing this route
        print(f"  First check — price: {current['price_raw']}")
        msg = format_message(label, date, current, None, None)
        msg += "\n\n📌 <i>Now tracking this route.</i>"
        send_telegram(msg)

    history[key] = current
    save_history(history)


def run_checks(notify_always: bool = False):
    print(f"\n{'─' * 50}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running checks...")
    print(f"{'─' * 50}")

    history = load_history()
    for flight in FLIGHTS_TO_TRACK:
        check_flight(flight, history, notify_always=notify_always)
        time.sleep(2)  # small pause between routes


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🛫 BoA Flight Price Tracker")
    print(f"   {len(FLIGHTS_TO_TRACK)} route(s) tracked")
    print(f"   Interval: every {CHECK_INTERVAL_MINUTES} minute(s)")
    print(f"   Notify threshold: ±{MIN_CHANGE_THRESHOLD}")
    print(f"   No API key needed (powered by fast-flights)\n")

    # Run immediately on start
    run_checks(notify_always=True)

    # Then on schedule
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_checks)

    print(f"\n⏰ Next check in {CHECK_INTERVAL_MINUTES} min. Ctrl+C to stop.\n")
    while True:
        schedule.run_pending()
        time.sleep(30)

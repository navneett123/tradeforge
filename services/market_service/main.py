from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import csv
import io
import re
import requests
import time

app = FastAPI(title="TradeForge Market Service", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

COINGECKO = "https://api.coingecko.com/api/v3"
STOOQ_QUOTE = "https://stooq.com/q/l/"
CACHE = {}
TTL = 45
REQUEST_TIMEOUT = 4

POPULAR_EQUITIES = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "NVDA": "NVIDIA Corp.", "TSLA": "Tesla Inc.",
    "AMZN": "Amazon.com Inc.", "GOOGL": "Alphabet Inc.", "META": "Meta Platforms Inc.", "NFLX": "Netflix Inc.",
    "AMD": "Advanced Micro Devices Inc.", "JPM": "JPMorgan Chase & Co.", "V": "Visa Inc.", "WMT": "Walmart Inc."
}

POPULAR_CRYPTO = {
    "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "dogecoin": "DOGE", "ripple": "XRP", "cardano": "ADA",
    "avalanche-2": "AVAX", "chainlink": "LINK", "polkadot": "DOT", "litecoin": "LTC"
}

# Dashboard bootstrap only. Search tries external APIs first for dynamic discovery.
BOOTSTRAP_ASSETS = [
    {"id":"bitcoin","symbol":"BTC","name":"Bitcoin","type":"crypto","price":65000.00,"change_pct":1.20,"currency":"USD","source":"bootstrap"},
    {"id":"ethereum","symbol":"ETH","name":"Ethereum","type":"crypto","price":3200.00,"change_pct":0.70,"currency":"USD","source":"bootstrap"},
    {"id":"solana","symbol":"SOL","name":"Solana","type":"crypto","price":145.00,"change_pct":-0.90,"currency":"USD","source":"bootstrap"},
    {"id":"dogecoin","symbol":"DOGE","name":"Dogecoin","type":"crypto","price":0.16,"change_pct":2.10,"currency":"USD","source":"bootstrap"},
    {"id":"AAPL","symbol":"AAPL","name":"Apple Inc.","type":"equity","price":190.10,"change_pct":0.40,"currency":"USD","source":"bootstrap"},
    {"id":"MSFT","symbol":"MSFT","name":"Microsoft Corp.","type":"equity","price":425.20,"change_pct":0.65,"currency":"USD","source":"bootstrap"},
    {"id":"NVDA","symbol":"NVDA","name":"NVIDIA Corp.","type":"equity","price":910.30,"change_pct":1.85,"currency":"USD","source":"bootstrap"},
    {"id":"TSLA","symbol":"TSLA","name":"Tesla Inc.","type":"equity","price":175.40,"change_pct":-1.10,"currency":"USD","source":"bootstrap"},
    {"id":"AMZN","symbol":"AMZN","name":"Amazon.com Inc.","type":"equity","price":184.60,"change_pct":0.25,"currency":"USD","source":"bootstrap"},
    {"id":"GOOGL","symbol":"GOOGL","name":"Alphabet Inc.","type":"equity","price":165.80,"change_pct":-0.30,"currency":"USD","source":"bootstrap"},
]

ALIASES = {
    "TESLA": "TSLA", "APPLE": "AAPL", "MICROSOFT": "MSFT", "NVIDIA": "NVDA", "AMAZON": "AMZN",
    "GOOGLE": "GOOGL", "ALPHABET": "GOOGL", "META": "META", "FACEBOOK": "META", "NETFLIX": "NFLX"
}

def cached(key, fetcher):
    now = time.time()
    if key in CACHE and now - CACHE[key][0] < TTL:
        return CACHE[key][1]
    data = fetcher()
    CACHE[key] = (now, data)
    return data

def unique_assets(items):
    seen = set()
    output = []
    for item in items:
        key = f"{item.get('type')}:{item.get('symbol')}"
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output

def stooq_quote(symbol: str):
    symbol = symbol.upper().strip()
    response = requests.get(
        STOOQ_QUOTE,
        params={"s": f"{symbol.lower()}.us", "f": "sd2t2ohlcv", "h": "", "e": "csv"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows:
        raise ValueError("No quote returned")
    row = rows[0]
    close = row.get("Close")
    if not close or close == "N/D":
        raise ValueError(f"No US equity quote available for {symbol}")
    open_raw = row.get("Open")
    open_price = float(open_raw if open_raw and open_raw != "N/D" else close)
    close_price = float(close)
    change_pct = ((close_price - open_price) / open_price) * 100 if open_price else 0
    return {
        "id": symbol,
        "symbol": symbol,
        "name": POPULAR_EQUITIES.get(symbol, symbol),
        "type": "equity",
        "price": round(close_price, 2),
        "change_pct": round(change_pct, 2),
        "currency": "USD",
        "source": "stooq-external-api",
    }

def coingecko_search(query: str):
    response = requests.get(f"{COINGECKO}/search", params={"query": query}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    coins = response.json().get("coins", [])[:6]
    results = []
    for coin in coins:
        coin_id = coin.get("id")
        if not coin_id:
            continue
        price_response = requests.get(
            f"{COINGECKO}/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=REQUEST_TIMEOUT,
        )
        price_response.raise_for_status()
        price = price_response.json().get(coin_id, {})
        if "usd" in price:
            results.append({
                "id": coin_id,
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", coin_id),
                "type": "crypto",
                "price": round(float(price["usd"]), 6),
                "change_pct": round(float(price.get("usd_24h_change") or 0), 2),
                "currency": "USD",
                "source": "coingecko-external-api",
            })
    return results

def bootstrap_crypto_prices():
    ids = ",".join(POPULAR_CRYPTO.keys())
    response = requests.get(
        f"{COINGECKO}/simple/price",
        params={"ids": ids, "vs_currencies": "usd", "include_24hr_change": "true"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    raw = response.json()
    output = []
    for coin_id, symbol in POPULAR_CRYPTO.items():
        val = raw.get(coin_id, {})
        if "usd" in val:
            output.append({
                "id": coin_id,
                "symbol": symbol,
                "name": coin_id.replace("-2", "").replace("-", " ").title(),
                "type": "crypto",
                "price": round(float(val["usd"]), 6),
                "change_pct": round(float(val.get("usd_24h_change") or 0), 2),
                "currency": "USD",
                "source": "coingecko-external-api",
            })
    return output

@app.get("/health")
def health():
    return {"status": "ok", "service": "market-service"}

@app.get("/assets")
def assets():
    # Dashboard bootstrap is kept stable; live search is handled by /search.
    try:
        live_crypto = cached("bootstrap_crypto", bootstrap_crypto_prices)
        merged = unique_assets(live_crypto + BOOTSTRAP_ASSETS)
        return merged[:12]
    except Exception:
        return BOOTSTRAP_ASSETS

@app.get("/search")
def search(q: str = Query("", min_length=0)):
    query = q.strip()
    if not query:
        return assets()

    normalized = re.sub(r"[^A-Za-z0-9]", "", query).upper()
    results = []

    # 1) Dynamic crypto discovery from CoinGecko.
    try:
        results.extend(cached(f"crypto:{query.lower()}", lambda: coingecko_search(query)))
    except Exception:
        pass

    # 2) Dynamic US equity quote lookup from Stooq. Works for ticker-style searches like META, AAPL, NVDA.
    possible_symbols = []
    if normalized in ALIASES:
        possible_symbols.append(ALIASES[normalized])
    if 1 <= len(normalized) <= 5 and normalized.isalpha():
        possible_symbols.append(normalized)

    for symbol in dict.fromkeys(possible_symbols):
        try:
            results.append(cached(f"equity:{symbol}", lambda symbol=symbol: stooq_quote(symbol)))
        except Exception:
            pass

    # 3) Local bootstrap match only supplements results; it is not the only search path anymore.
    local_matches = [
        item for item in BOOTSTRAP_ASSETS
        if query.lower() in item["symbol"].lower() or query.lower() in item["name"].lower()
    ]
    results.extend(local_matches)
    return unique_assets(results)[:20]

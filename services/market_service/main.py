from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import csv
import io
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

app = FastAPI(title="TradeForge Market Service", version="1.0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

COINGECKO = "https://api.coingecko.com/api/v3"
CACHE = {}
TTL = 45
REQUEST_TIMEOUT = 2.5

POPULAR_EQUITIES = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "NVDA": "NVIDIA Corp.", "TSLA": "Tesla Inc.",
    "AMZN": "Amazon.com Inc.", "GOOGL": "Alphabet Inc.", "META": "Meta Platforms", "NFLX": "Netflix Inc.",
    "AMD": "Advanced Micro Devices", "JPM": "JPMorgan Chase", "V": "Visa Inc.", "WMT": "Walmart Inc."
}

POPULAR_CRYPTO = {
    "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "dogecoin": "DOGE", "ripple": "XRP", "cardano": "ADA",
    "avalanche-2": "AVAX", "chainlink": "LINK", "polkadot": "DOT", "litecoin": "LTC"
}

# Used when external APIs are slow, unavailable, or rate-limited. This keeps the app demo-ready.
FALLBACK_ASSETS = [
    {"id":"bitcoin","symbol":"BTC","name":"Bitcoin","type":"crypto","price":65000.00,"change_pct":1.20,"currency":"USD"},
    {"id":"ethereum","symbol":"ETH","name":"Ethereum","type":"crypto","price":3200.00,"change_pct":0.70,"currency":"USD"},
    {"id":"solana","symbol":"SOL","name":"Solana","type":"crypto","price":145.00,"change_pct":-0.90,"currency":"USD"},
    {"id":"dogecoin","symbol":"DOGE","name":"Dogecoin","type":"crypto","price":0.16,"change_pct":2.10,"currency":"USD"},
    {"id":"AAPL","symbol":"AAPL","name":"Apple Inc.","type":"equity","price":190.10,"change_pct":0.40,"currency":"USD"},
    {"id":"MSFT","symbol":"MSFT","name":"Microsoft Corp.","type":"equity","price":425.20,"change_pct":0.65,"currency":"USD"},
    {"id":"NVDA","symbol":"NVDA","name":"NVIDIA Corp.","type":"equity","price":910.30,"change_pct":1.85,"currency":"USD"},
    {"id":"TSLA","symbol":"TSLA","name":"Tesla Inc.","type":"equity","price":175.40,"change_pct":-1.10,"currency":"USD"},
    {"id":"AMZN","symbol":"AMZN","name":"Amazon.com Inc.","type":"equity","price":184.60,"change_pct":0.25,"currency":"USD"},
    {"id":"GOOGL","symbol":"GOOGL","name":"Alphabet Inc.","type":"equity","price":165.80,"change_pct":-0.30,"currency":"USD"},
]

def cached(key, fetcher):
    now = time.time()
    if key in CACHE and now - CACHE[key][0] < TTL:
        return CACHE[key][1]
    data = fetcher()
    CACHE[key] = (now, data)
    return data

def stooq_quote(symbol: str):
    stooq_symbol = f"{symbol.lower()}.us"
    url = f"https://stooq.com/q/l/?s={stooq_symbol}&f=sd2t2ohlcv&h&e=csv"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    row = next(csv.DictReader(io.StringIO(r.text)))
    close = row.get("Close")
    if not close or close == "N/D":
        raise ValueError("quote not available")
    open_raw = row.get("Open")
    open_price = float(open_raw if open_raw and open_raw != "N/D" else close)
    close_price = float(close)
    change_pct = ((close_price - open_price) / open_price) * 100 if open_price else 0
    return {
        "id": symbol.upper(), "symbol": symbol.upper(), "name": POPULAR_EQUITIES.get(symbol.upper(), symbol.upper()),
        "type": "equity", "price": round(close_price, 2), "change_pct": round(change_pct, 2), "currency": "USD"
    }

def crypto_prices():
    ids = ",".join(POPULAR_CRYPTO.keys())
    url = f"{COINGECKO}/simple/price"
    params = {"ids": ids, "vs_currencies": "usd", "include_24hr_change": "true"}
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    raw = r.json()
    out = []
    for cid, sym in POPULAR_CRYPTO.items():
        val = raw.get(cid, {})
        if "usd" in val:
            out.append({
                "id": cid, "symbol": sym, "name": cid.replace("-2", "").replace("-", " ").title(),
                "type": "crypto", "price": round(float(val["usd"]), 4),
                "change_pct": round(float(val.get("usd_24h_change") or 0), 2), "currency": "USD"
            })
    return out

def unique_assets(items):
    seen = set()
    output = []
    for item in items:
        key = f"{item.get('type')}:{item.get('symbol')}"
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output

@app.get("/health")
def health():
    return {"status": "ok", "service": "market-service"}

@app.get("/assets")
def assets():
    # Keep the dashboard fast and reliable for demos.
    # Search still attempts external API enrichment, but bootstrap never blocks on network calls.
    return cached("assets", lambda: FALLBACK_ASSETS)

@app.get("/search")
def search(q: str = Query("", min_length=0)):
    ql = q.lower().strip()
    base = assets()
    if not ql:
        return base

    results = [x for x in base if ql in x["symbol"].lower() or ql in x["name"].lower()]

    # Optional external CoinGecko enrichment for crypto search. If it fails, local results still work.
    try:
        r = requests.get(f"{COINGECKO}/search", params={"query": q}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        for coin in r.json().get("coins", [])[:5]:
            cid = coin["id"]
            price_resp = requests.get(
                f"{COINGECKO}/simple/price",
                params={"ids": cid, "vs_currencies": "usd", "include_24hr_change": "true"},
                timeout=REQUEST_TIMEOUT,
            )
            price = price_resp.json().get(cid, {})
            if "usd" in price:
                results.append({
                    "id": cid,
                    "symbol": coin.get("symbol", "").upper(),
                    "name": coin.get("name", cid),
                    "type": "crypto",
                    "price": price["usd"],
                    "change_pct": round(price.get("usd_24h_change") or 0, 2),
                    "currency": "USD",
                })
    except Exception:
        pass
    return unique_assets(results)[:20]

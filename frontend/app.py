from flask import Flask, render_template, request, jsonify
import os, requests

app = Flask(__name__)
MARKET_URL = os.getenv("MARKET_URL", "http://market-service:8001")
WALLET_URL = os.getenv("WALLET_URL", "http://wallet-service:8004")
ORDER_URL = os.getenv("ORDER_URL", "http://order-service:8005")
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "http://portfolio-service:8002")
RECO_URL = os.getenv("RECO_URL", "http://recommendation-service:8003")

def safe_get(url, fallback):
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        return response.json()
    except Exception:
        return fallback

def merged_portfolio():
    wallet = safe_get(f"{WALLET_URL}/wallet", {"cash": 0, "starting_cash": 0, "movements": []})
    portfolio = safe_get(f"{PORTFOLIO_URL}/portfolio", {"invested_value": 0, "holdings": [], "transactions": []})
    transactions = (portfolio.get("transactions", []) + wallet.get("movements", []))
    transactions = sorted(transactions, key=lambda item: item.get("time", ""), reverse=True)[:30]
    invested = portfolio.get("invested_value", 0)
    return {
        "wallet": {
            "cash": round(wallet.get("cash", 0), 2),
            "starting_cash": round(wallet.get("starting_cash", 0), 2),
            "invested_value": round(invested, 2),
            "net_worth": round(wallet.get("cash", 0) + invested, 2),
        },
        "holdings": portfolio.get("holdings", []),
        "transactions": transactions,
    }

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/bootstrap")
def bootstrap():
    assets = safe_get(f"{MARKET_URL}/assets", [])
    portfolio = merged_portfolio()
    recs = []
    try:
        recs = requests.post(f"{RECO_URL}/recommendations", json={"assets": assets, "wallet": portfolio.get("wallet",{})}, timeout=8).json()
    except Exception:
        pass
    return jsonify({"assets": assets, "portfolio": portfolio, "recommendations": recs})

@app.get("/api/search")
def search():
    q = request.args.get("q", "")
    return jsonify(safe_get(f"{MARKET_URL}/search?q={q}", []))

@app.post("/api/trade")
def trade():
    data = request.get_json(force=True)
    r = requests.post(f"{ORDER_URL}/orders", json=data, timeout=8)
    if not r.ok:
        return (r.text, r.status_code, {"Content-Type": "application/json"})
    body = r.json()
    body["portfolio"] = merged_portfolio()
    return jsonify(body)

@app.post("/api/wallet")
def wallet():
    data = request.get_json(force=True)
    r = requests.post(f"{WALLET_URL}/wallet", json=data, timeout=8)
    if not r.ok:
        return (r.text, r.status_code, {"Content-Type": "application/json"})
    body = r.json()
    body["portfolio"] = merged_portfolio()
    return jsonify(body)

@app.get("/health")
def health():
    return {"status":"ok", "service":"frontend"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")

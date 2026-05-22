from flask import Flask, render_template, request, jsonify
import os
import requests

app = Flask(__name__)

# AKS service DNS names. These are the only defaults used by the frontend proxy.
MARKET_URL = os.getenv("MARKET_SERVICE_URL", "http://market-service:8000").rstrip("/")
WALLET_URL = os.getenv("WALLET_SERVICE_URL", "http://wallet-service:8000").rstrip("/")
ORDER_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8000").rstrip("/")
PORTFOLIO_URL = os.getenv("PORTFOLIO_SERVICE_URL", "http://portfolio-service:8000").rstrip("/")
RECO_URL = os.getenv("RECOMMENDATION_SERVICE_URL", "http://recommendation-service:8000").rstrip("/")
TIMEOUT = int(os.getenv("SERVICE_TIMEOUT", "8"))


def normalize_list(payload, key=None):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if key and isinstance(payload.get(key), list):
            return payload[key]
        for candidate in ("assets", "results", "recommendations", "holdings", "transactions", "movements", "items"):
            if isinstance(payload.get(candidate), list):
                return payload[candidate]
    return []


def parse_json_response(response):
    try:
        body = response.json()
    except Exception:
        body = {"detail": response.text or "Non-JSON response from upstream service"}
    return body


def upstream_get(url, fallback=None):
    try:
        response = requests.get(url, timeout=TIMEOUT)
        body = parse_json_response(response)
        if not response.ok:
            app.logger.warning("GET upstream failed url=%s status=%s body=%s", url, response.status_code, body)
            return fallback if fallback is not None else {"detail": body}
        return body
    except Exception as exc:
        app.logger.exception("GET upstream exception url=%s", url)
        return fallback if fallback is not None else {"detail": str(exc)}


def upstream_post(url, payload):
    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT)
        body = parse_json_response(response)
        if not response.ok:
            detail = body.get("detail") if isinstance(body, dict) else str(body)
            return None, (jsonify({"detail": detail or "Upstream request failed"}), response.status_code)
        return body, None
    except Exception as exc:
        app.logger.exception("POST upstream exception url=%s", url)
        return None, (jsonify({"detail": f"Upstream service unavailable at {url}: {exc}"}), 502)


def merged_portfolio():
    wallet = upstream_get(f"{WALLET_URL}/wallet", {"cash": 0, "starting_cash": 0, "movements": []}) or {}
    portfolio = upstream_get(f"{PORTFOLIO_URL}/portfolio", {"invested_value": 0, "holdings": [], "transactions": []}) or {}

    wallet_cash = float(wallet.get("cash", 0) or 0)
    invested = float(portfolio.get("invested_value", 0) or 0)
    transactions = normalize_list(portfolio.get("transactions", [])) + normalize_list(wallet.get("movements", []))
    transactions = sorted(transactions, key=lambda item: item.get("time", ""), reverse=True)[:30]

    return {
        "wallet": {
            "cash": round(wallet_cash, 2),
            "starting_cash": round(float(wallet.get("starting_cash", 0) or 0), 2),
            "invested_value": round(invested, 2),
            "net_worth": round(wallet_cash + invested, 2),
        },
        "holdings": normalize_list(portfolio.get("holdings", [])),
        "transactions": transactions,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def config():
    return jsonify({
        "market_url": MARKET_URL,
        "wallet_url": WALLET_URL,
        "order_url": ORDER_URL,
        "portfolio_url": PORTFOLIO_URL,
        "recommendation_url": RECO_URL,
        "timeout": TIMEOUT,
    })


@app.get("/api/health")
def api_health():
    return jsonify({
        "frontend": {"status": "ok"},
        "market": upstream_get(f"{MARKET_URL}/health", {}),
        "wallet": upstream_get(f"{WALLET_URL}/health", {}),
        "order": upstream_get(f"{ORDER_URL}/health", {}),
        "portfolio": upstream_get(f"{PORTFOLIO_URL}/health", {}),
        "recommendation": upstream_get(f"{RECO_URL}/health", {}),
    })


@app.get("/api/bootstrap")
def bootstrap():
    assets = normalize_list(upstream_get(f"{MARKET_URL}/assets", []))
    portfolio = merged_portfolio()
    recs = []
    body, error = upstream_post(f"{RECO_URL}/recommendations", {"assets": assets, "wallet": portfolio.get("wallet", {})})
    if not error:
        recs = normalize_list(body)
    return jsonify({"assets": assets, "portfolio": portfolio, "recommendations": recs})


@app.get("/api/search")
def search():
    query = request.args.get("q", "")
    try:
        response = requests.get(f"{MARKET_URL}/search", params={"q": query}, timeout=TIMEOUT)
        body = parse_json_response(response)
        if not response.ok:
            detail = body.get("detail") if isinstance(body, dict) else str(body)
            return jsonify({"detail": detail or "Market search failed"}), response.status_code
        return jsonify(normalize_list(body))
    except Exception as exc:
        app.logger.exception("market search failed")
        return jsonify({"detail": f"Market search failed via {MARKET_URL}: {exc}"}), 502


@app.post("/api/wallet")
def wallet():
    payload = request.get_json(force=True) or {}
    body, error = upstream_post(f"{WALLET_URL}/wallet", payload)
    if error:
        return error
    body["portfolio"] = merged_portfolio()
    return jsonify(body)


@app.post("/api/trade")
def trade():
    payload = request.get_json(force=True) or {}
    body, error = upstream_post(f"{ORDER_URL}/orders", payload)
    if error:
        return error
    body["portfolio"] = merged_portfolio()
    return jsonify(body)


@app.get("/health")
def health():
    return {"status": "ok", "service": "frontend"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")

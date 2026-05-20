from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="TradeForge Recommendation Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "recommendation-service"}

@app.post("/recommendations")
def recommendations(payload: dict = Body(default={})): 
    assets = payload.get("assets", [])
    wallet = payload.get("wallet", {})
    cash = float(wallet.get("cash", 0))
    sorted_assets = sorted(assets, key=lambda x: x.get("change_pct", 0), reverse=True)
    winners = sorted_assets[:3]
    dips = sorted(assets, key=lambda x: x.get("change_pct", 0))[:3]
    recs = []
    if cash > 20000:
        recs.append({"title":"Deploy cash gradually", "tag":"Wallet", "message":"You have high idle cash. Consider splitting dummy buys across 2-3 assets instead of one large entry."})
    if winners:
        recs.append({"title":"Momentum watchlist", "tag":"Trend", "message":"Strong movers today: " + ", ".join([a["symbol"] for a in winners]) + ". Use smaller quantities because momentum can reverse."})
    if dips:
        recs.append({"title":"Dip candidates", "tag":"Risk", "message":"Weak movers: " + ", ".join([a["symbol"] for a in dips]) + ". Suitable only for watchlist or staggered dummy entry."})
    recs.append({"title":"Portfolio discipline", "tag":"Rule", "message":"Avoid putting more than 20% of wallet value into one asset in this simulation."})
    return recs

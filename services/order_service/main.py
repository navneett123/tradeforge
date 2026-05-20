from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os, requests

app = FastAPI(title="TradeForge Order Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WALLET_URL = os.getenv("WALLET_URL", "http://wallet-service:8004")
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "http://portfolio-service:8002")

class Trade(BaseModel):
    asset_id: str
    symbol: str
    name: str
    asset_type: str
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)

@app.get("/health")
def health():
    return {"status": "ok", "service": "order-service"}

@app.post("/orders")
def create_order(t: Trade):
    value = round(t.quantity * t.price, 2)
    payload = t.model_dump()
    try:
        if t.side == "buy":
            wallet_response = requests.post(f"{WALLET_URL}/wallet/debit", json={"amount": value, "reason": f"BUY {t.symbol}"}, timeout=8)
            if not wallet_response.ok:
                raise HTTPException(wallet_response.status_code, wallet_response.json().get("detail", "Wallet debit failed"))
            portfolio_response = requests.post(f"{PORTFOLIO_URL}/positions", json=payload, timeout=8)
            if not portfolio_response.ok:
                requests.post(f"{WALLET_URL}/wallet/credit", json={"amount": value, "reason": f"Rollback failed BUY {t.symbol}"}, timeout=8)
                raise HTTPException(portfolio_response.status_code, portfolio_response.json().get("detail", "Portfolio update failed"))
        else:
            portfolio_response = requests.post(f"{PORTFOLIO_URL}/positions", json=payload, timeout=8)
            if not portfolio_response.ok:
                raise HTTPException(portfolio_response.status_code, portfolio_response.json().get("detail", "Portfolio update failed"))
            wallet_response = requests.post(f"{WALLET_URL}/wallet/credit", json={"amount": value, "reason": f"SELL {t.symbol}"}, timeout=8)
            if not wallet_response.ok:
                raise HTTPException(wallet_response.status_code, wallet_response.json().get("detail", "Wallet credit failed"))
        return {"message": f"{t.side.title()} order executed", "order": {**payload, "value": value}, "wallet": wallet_response.json().get("wallet"), "portfolio": portfolio_response.json().get("portfolio")}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Order service error: {exc}")

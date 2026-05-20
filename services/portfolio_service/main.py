from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

app = FastAPI(title="TradeForge Portfolio Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE = {"holdings": {}, "transactions": []}

class PositionUpdate(BaseModel):
    asset_id: str
    symbol: str
    name: str
    asset_type: str
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)


def _record(payload: dict):
    tx = {"id": str(uuid4())[:8], "time": datetime.utcnow().isoformat(timespec="seconds") + "Z", **payload}
    STATE["transactions"].append(tx)
    return tx

@app.get("/health")
def health():
    return {"status": "ok", "service": "portfolio-service"}

@app.get("/portfolio")
def portfolio():
    invested_value = sum(h["quantity"] * h["avg_price"] for h in STATE["holdings"].values())
    return {
        "invested_value": round(invested_value, 2),
        "holdings": list(STATE["holdings"].values()),
        "transactions": STATE["transactions"][-30:][::-1],
    }

@app.post("/positions")
def update_position(t: PositionUpdate):
    cost = round(t.quantity * t.price, 2)
    key = f"{t.asset_type}:{t.symbol}"
    if t.side == "buy":
        old = STATE["holdings"].get(key, {"asset_id": t.asset_id, "symbol": t.symbol, "name": t.name, "asset_type": t.asset_type, "quantity": 0, "avg_price": 0})
        new_qty = old["quantity"] + t.quantity
        old_cost = old["quantity"] * old["avg_price"]
        old["quantity"] = round(new_qty, 6)
        old["avg_price"] = round((old_cost + cost) / new_qty, 4)
        STATE["holdings"][key] = old
    else:
        old = STATE["holdings"].get(key)
        if not old or old["quantity"] < t.quantity:
            raise HTTPException(400, "Not enough quantity to sell")
        old["quantity"] = round(old["quantity"] - t.quantity, 6)
        if old["quantity"] <= 0:
            STATE["holdings"].pop(key, None)
    tx = _record({"type": "trade", **t.model_dump(), "value": cost})
    return {"message": "Portfolio updated", "transaction": tx, "portfolio": portfolio()}

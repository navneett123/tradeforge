from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

app = FastAPI(title="TradeForge Wallet Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE = {"cash": 100000.0, "starting_cash": 100000.0, "movements": []}

class CashMovement(BaseModel):
    movement_type: str = Field(pattern="^(deposit|withdraw)$")
    amount: float = Field(gt=0)
    note: str | None = None

class ReserveRequest(BaseModel):
    amount: float = Field(gt=0)
    reason: str = "order"

class CreditRequest(BaseModel):
    amount: float = Field(gt=0)
    reason: str = "order"


def _record(payload: dict):
    item = {"id": str(uuid4())[:8], "time": datetime.utcnow().isoformat(timespec="seconds") + "Z", **payload}
    STATE["movements"].append(item)
    return item

@app.get("/health")
def health():
    return {"status": "ok", "service": "wallet-service"}

@app.get("/wallet")
def get_wallet():
    return {
        "cash": round(STATE["cash"], 2),
        "starting_cash": round(STATE["starting_cash"], 2),
        "movements": STATE["movements"][-30:][::-1],
    }

@app.post("/wallet")
def wallet_movement(m: CashMovement):
    amount = round(m.amount, 2)
    if m.movement_type == "withdraw":
        if STATE["cash"] < amount:
            raise HTTPException(400, "Insufficient wallet balance for withdrawal")
        STATE["cash"] -= amount
        message = "Withdrawal completed"
    else:
        STATE["cash"] += amount
        STATE["starting_cash"] += amount
        message = "Deposit completed"
    movement = _record({"type": "wallet", "movement_type": m.movement_type, "amount": amount, "note": m.note or "Manual wallet update", "value": amount})
    return {"message": message, "movement": movement, "wallet": get_wallet()}

@app.post("/wallet/debit")
def debit(req: ReserveRequest):
    amount = round(req.amount, 2)
    if STATE["cash"] < amount:
        raise HTTPException(400, "Insufficient wallet balance")
    STATE["cash"] -= amount
    movement = _record({"type": "wallet", "movement_type": "debit", "amount": amount, "note": req.reason, "value": amount})
    return {"message": "Wallet debited", "movement": movement, "wallet": get_wallet()}

@app.post("/wallet/credit")
def credit(req: CreditRequest):
    amount = round(req.amount, 2)
    STATE["cash"] += amount
    movement = _record({"type": "wallet", "movement_type": "credit", "amount": amount, "note": req.reason, "value": amount})
    return {"message": "Wallet credited", "movement": movement, "wallet": get_wallet()}

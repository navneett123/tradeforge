# TradeForge

Python-only microservices demo for AKS learning: market search, wallet, dummy buy/sell orders, portfolio tracking, and custom recommendations.

## Clean layout

```text
tradeforge/
├── frontend/
│   ├── app.py
│   ├── Dockerfile
│   ├── static/
│   └── templates/
├── services/
│   ├── market_service/
│   ├── wallet_service/
│   ├── order_service/
│   ├── portfolio_service/
│   └── recommendation_service/
├── k8s/
│   ├── dev/
│   └── prod/
├── scripts/
├── .github/workflows/
├── docker-compose.yml
└── requirements.txt
```

## Services

| Service | Purpose |
|---|---|
| `frontend` | Flask web UI and API gateway for the browser |
| `market_service` | Searches coins/equities using external APIs with fallback data |
| `wallet_service` | Deposit, withdraw, debit, credit, wallet balance |
| `order_service` | Dummy buy/sell order orchestration |
| `portfolio_service` | Holdings, average price, trade history |
| `recommendation_service` | Custom recommendations based on assets and wallet |

## Run locally

```bash
docker compose up --build
```

Open:

```text
http://localhost:8080
```

## Starter workflow intent

Current workflows are starter-level only. Later you can wire ACR, AKS credentials, namespaces, image tags, approvals, and secrets.

Target flow:

```text
Pull Request -> review/approval -> merge to main
-> build/test images
-> deploy automatically to dev namespace
-> manual approval via GitHub Environment for prod
-> rolling update in prod
-> health check
-> rollback to previous deployment if prod health fails
```

## Deployment strategy

Kubernetes manifests use RollingUpdate. Rollback is handled by:

```bash
kubectl rollout undo deployment/<deployment-name> -n tradeforge-prod
```

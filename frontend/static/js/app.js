let state = {
  assets: [],
  portfolio: {},
  recommendations: [],
};

let selected = null;
let side = "buy";
let walletMode = "deposit";
let timer = null;

const money = (value) =>
  "$" +
  Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });

const getEl = (id) => document.getElementById(id);

function normalizeAssets(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.assets)) return data.assets;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail ||
      data.message ||
      `Request failed with status ${response.status}`
    );
  }

  return data;
}

async function load() {
  try {
    const data = await fetchJson("/api/bootstrap");

    state.assets = normalizeAssets(data.assets || data);
    state.portfolio = data.portfolio || {};
    state.recommendations = data.recommendations || [];

    render();
  } catch (error) {
    getEl("assets").innerHTML = `
      <div class="empty">
        Failed to load dashboard: ${error.message}
      </div>
    `;
  }
}

function render() {
  const wallet = state.portfolio.wallet || {};
  const holdings = state.portfolio.holdings || [];

  getEl("cash").textContent = money(wallet.cash);
  getEl("invested").textContent = money(wallet.invested_value);
  getEl("netWorth").textContent = money(wallet.net_worth);
  getEl("assetCount").textContent = state.assets.length;
  getEl("holdingCount").textContent = holdings.length;

  renderAssets(state.assets);
  renderRecommendations();
  renderPortfolio();
  renderTransactions();
}

function renderAssets(items) {
  const assets = normalizeAssets(items);
  const container = getEl("assets");

  if (!assets.length) {
    container.innerHTML = `
      <div class="empty">
        No assets found.
      </div>
    `;
    return;
  }

  container.innerHTML = assets
    .map(
      (asset) => `
        <div class="asset">
          <div class="asset-top">
            <div>
              <div class="symbol">${asset.symbol || "-"}</div>
              <div class="name">
                ${asset.name || asset.symbol || "Unknown Asset"}
              </div>
            </div>

            <span class="badge">
              ${asset.type || "asset"}
              ${asset.source ? " · live" : ""}
            </span>
          </div>

          <div class="price">
            ${money(asset.price)}
          </div>

          <div class="change ${
            Number(asset.change_pct || 0) >= 0 ? "good" : "bad"
          }">
            ${
              Number(asset.change_pct || 0) >= 0
                ? "▲"
                : "▼"
            }
            ${Math.abs(Number(asset.change_pct || 0))}%
          </div>

          <div class="actions">
            <button
              class="buy"
              onclick='openTrade(${JSON.stringify(asset)}, "buy")'
            >
              Buy
            </button>

            <button
              class="sell"
              onclick='openTrade(${JSON.stringify(asset)}, "sell")'
            >
              Sell
            </button>
          </div>
        </div>
      `
    )
    .join("");
}

function renderRecommendations() {
  const recommendations = state.recommendations || [];

  getEl("recommendations").innerHTML =
    recommendations
      .map(
        (rec) => `
          <div class="rec">
            <span class="tag">
              ${rec.tag || "Signal"}
            </span>

            <b>
              ${rec.title || "Recommendation"}
            </b>

            <p class="muted">
              ${rec.message || ""}
            </p>
          </div>
        `
      )
      .join("") ||
    `
      <div class="empty">
        No recommendations yet.
      </div>
    `;
}

function renderPortfolio() {
  const holdings = state.portfolio.holdings || [];

  getEl("holdings").innerHTML =
    holdings
      .map(
        (holding) => `
          <div class="row">
            <div>
              <b>${holding.symbol}</b>

              <small>
                ${holding.name || holding.symbol}
                · Qty ${holding.quantity}
              </small>
            </div>

            <strong>
              ${money(holding.avg_price)}
            </strong>
          </div>
        `
      )
      .join("") ||
    `
      <div class="empty">
        No holdings yet.
      </div>
    `;
}

function renderTransactions() {
  const transactions = state.portfolio.transactions || [];

  getEl("transactions").innerHTML =
    transactions
      .map((tx) => {
        if (tx.type === "wallet") {
          return `
            <div class="row wallet-row">
              <div>
                <b>
                  ${String(tx.movement_type || "").toUpperCase()} FUNDS
                </b>

                <small>
                  ${tx.note || "Wallet update"}
                  · ${tx.time || ""}
                </small>
              </div>

              <strong>
                ${money(tx.amount)}
              </strong>
            </div>
          `;
        }

        return `
          <div class="row">
            <div>
              <b>
                ${String(tx.side || "").toUpperCase()}
                ${tx.symbol || ""}
              </b>

              <small>
                ${tx.quantity || 0} units
                · ${tx.time || ""}
              </small>
            </div>

            <strong>
              ${money(tx.value)}
            </strong>
          </div>
        `;
      })
      .join("") ||
    `
      <div class="empty">
        No wallet or order activity yet.
      </div>
    `;
}

function openTrade(asset, tradeSide) {
  selected = asset;
  setSide(tradeSide);

  getEl("tradeTitle").textContent =
    `${asset.symbol} ${tradeSide.toUpperCase()} Order`;

  getEl("tradeSub").textContent =
    `${asset.name} · ${asset.type} · ${money(asset.price)}`;

  getEl("tradeModal").classList.remove("hidden");

  updateEstimate();
}

function closeTrade() {
  getEl("tradeModal").classList.add("hidden");
  getEl("tradeMsg").textContent = "";
}

function setSide(newSide) {
  side = newSide;

  getEl("buyBtn").classList.toggle(
    "selected",
    newSide === "buy"
  );

  getEl("sellBtn").classList.toggle(
    "selected",
    newSide === "sell"
  );
}

function updateEstimate() {
  const quantity = Number(getEl("qty").value || 0);

  getEl("estimate").textContent = money(
    quantity * Number(selected?.price || 0)
  );
}

async function submitTrade() {
  const msg = getEl("tradeMsg");

  msg.className = "msg";
  msg.textContent = "Processing...";

  const quantity = Number(getEl("qty").value);

  if (!selected) {
    msg.textContent = "Select an asset first.";
    msg.classList.add("err");
    return;
  }

  if (!quantity || quantity <= 0) {
    msg.textContent = "Enter a quantity greater than 0.";
    msg.classList.add("err");
    return;
  }

  const payload = {
    asset_id: selected.id,
    symbol: selected.symbol,
    name: selected.name,
    asset_type: selected.type,
    side,
    quantity,
    price: Number(selected.price),
  };

  try {
    const data = await fetchJson("/api/trade", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    msg.textContent =
      data.message || "Order completed.";

    msg.classList.add("ok");

    state.portfolio =
      data.portfolio || state.portfolio;

    render();
  } catch (error) {
    msg.textContent =
      error.message || "Order failed.";

    msg.classList.add("err");
  }
}

function openWallet(mode) {
  setWalletMode(mode);
  getEl("walletModal").classList.remove("hidden");
}

function closeWallet() {
  getEl("walletModal").classList.add("hidden");
  getEl("walletMsg").textContent = "";
}

function setWalletMode(mode) {
  walletMode = mode;

  getEl("depositBtn").classList.toggle(
    "selected",
    mode === "deposit"
  );

  getEl("withdrawBtn").classList.toggle(
    "selected",
    mode === "withdraw"
  );

  getEl("walletTitle").textContent =
    mode === "deposit"
      ? "Deposit Funds"
      : "Withdraw Funds";

  getEl("walletSub").textContent =
    mode === "deposit"
      ? "Add dummy capital to your wallet."
      : "Withdraw dummy capital from your wallet.";
}

async function submitWallet() {
  const msg = getEl("walletMsg");

  msg.className = "msg";
  msg.textContent = "Processing...";

  const amount = Number(getEl("walletAmount").value);

  if (!amount || amount <= 0) {
    msg.textContent =
      "Enter an amount greater than 0.";

    msg.classList.add("err");
    return;
  }

  const payload = {
    movement_type: walletMode,
    amount,
    note: getEl("walletNote").value,
  };

  try {
    const data = await fetchJson("/api/wallet", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    msg.textContent =
      data.message || "Wallet updated.";

    msg.classList.add("ok");

    state.portfolio =
      data.portfolio || state.portfolio;

    render();
  } catch (error) {
    msg.textContent =
      error.message || "Wallet action failed.";

    msg.classList.add("err");
  }
}

async function searchAssets(query) {
  const cleanQuery = query.trim();

  if (!cleanQuery) {
    renderAssets(state.assets);
    return;
  }

  try {
    const data = await fetchJson(
      `/api/search?q=${encodeURIComponent(cleanQuery)}`
    );

    const assets = normalizeAssets(data);

    renderAssets(assets);
  } catch (error) {
    getEl("assets").innerHTML = `
      <div class="empty">
        Market search failed: ${error.message}
      </div>
    `;
  }
}

getEl("qty").addEventListener("input", updateEstimate);

getEl("search").addEventListener("input", (event) => {
  clearTimeout(timer);

  timer = setTimeout(() => {
    searchAssets(event.target.value);
  }, 300);
});

load();

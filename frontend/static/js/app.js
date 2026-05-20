let state = { assets: [], portfolio: {}, recommendations: [] };
let selected = null;
let side = 'buy';
let walletMode = 'deposit';
const money = n => '$' + Number(n || 0).toLocaleString(undefined,{maximumFractionDigits:2});

async function load(){
  const res = await fetch('/api/bootstrap');
  state = await res.json();
  render();
}
function render(){
  const wallet = state.portfolio.wallet || {};
  document.getElementById('cash').textContent = money(wallet.cash);
  document.getElementById('invested').textContent = money(wallet.invested_value);
  document.getElementById('netWorth').textContent = money(wallet.net_worth);
  document.getElementById('assetCount').textContent = state.assets.length;
  document.getElementById('holdingCount').textContent = (state.portfolio.holdings || []).length;
  renderAssets(state.assets); renderRecs(); renderPortfolio(); renderTransactions();
}
function renderAssets(items){
  const box = document.getElementById('assets');
  box.innerHTML = items.map(a => `
    <div class="asset">
      <div class="asset-top"><div><div class="symbol">${a.symbol}</div><div class="name">${a.name}</div></div><span class="badge">${a.type}${a.source ? " · live" : ""}</span></div>
      <div class="price">${money(a.price)}</div>
      <div class="change ${a.change_pct >= 0 ? 'good':'bad'}">${a.change_pct >= 0 ? '▲':'▼'} ${Math.abs(a.change_pct || 0)}%</div>
      <div class="actions"><button class="buy" onclick='openTrade(${JSON.stringify(a)},"buy")'>Buy</button><button class="sell" onclick='openTrade(${JSON.stringify(a)},"sell")'>Sell</button></div>
    </div>`).join('') || '<div class="empty">No assets found.</div>';
}
function renderRecs(){
  document.getElementById('recommendations').innerHTML = (state.recommendations || []).map(r => `<div class="rec"><span class="tag">${r.tag}</span><b>${r.title}</b><p class="muted">${r.message}</p></div>`).join('') || '<div class="empty">No recommendations yet.</div>';
}
function renderPortfolio(){
  const h = state.portfolio.holdings || [];
  document.getElementById('holdings').innerHTML = h.map(x => `<div class="row"><div><b>${x.symbol}</b><small>${x.name} · Qty ${x.quantity}</small></div><strong>${money(x.avg_price)}</strong></div>`).join('') || '<div class="empty">No holdings yet. Execute a dummy buy order.</div>';
}
function renderTransactions(){
  const tx = state.portfolio.transactions || [];
  document.getElementById('transactions').innerHTML = tx.map(t => {
    if(t.type === 'wallet') return `<div class="row wallet-row"><div><b>${t.movement_type.toUpperCase()} FUNDS</b><small>${t.note || 'Wallet update'} · ${t.time}</small></div><strong>${money(t.amount)}</strong></div>`;
    return `<div class="row"><div><b>${t.side.toUpperCase()} ${t.symbol}</b><small>${t.quantity} units · ${t.time}</small></div><strong>${money(t.value)}</strong></div>`;
  }).join('') || '<div class="empty">No wallet or order activity yet.</div>';
}
function openTrade(asset, s){ selected = asset; setSide(s); document.getElementById('tradeTitle').textContent = `${asset.symbol} ${s.toUpperCase()} Order`; document.getElementById('tradeSub').textContent = `${asset.name} · ${asset.type} · ${money(asset.price)}`; document.getElementById('tradeModal').classList.remove('hidden'); updateEstimate(); }
function closeTrade(){ document.getElementById('tradeModal').classList.add('hidden'); document.getElementById('tradeMsg').textContent=''; }
function setSide(s){ side=s; document.getElementById('buyBtn').classList.toggle('selected',s==='buy'); document.getElementById('sellBtn').classList.toggle('selected',s==='sell'); }
function updateEstimate(){ const q = Number(document.getElementById('qty').value || 0); document.getElementById('estimate').textContent = money(q * (selected?.price || 0)); }
async function submitTrade(){
  const msg = document.getElementById('tradeMsg'); msg.className='msg'; msg.textContent='Processing...';
  const quantity = Number(document.getElementById('qty').value);
  if(!quantity || quantity <= 0){ msg.textContent='Enter a quantity greater than 0'; msg.classList.add('err'); return; }
  const payload = { asset_id:selected.id, symbol:selected.symbol, name:selected.name, asset_type:selected.type, side, quantity, price:Number(selected.price) };
  const res = await fetch('/api/trade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data = await res.json();
  if(!res.ok){ msg.textContent = data.detail || 'Order failed'; msg.classList.add('err'); return; }
  msg.textContent = data.message; msg.classList.add('ok');
  state.portfolio = data.portfolio; render();
}
function openWallet(mode){ setWalletMode(mode); document.getElementById('walletModal').classList.remove('hidden'); }
function closeWallet(){ document.getElementById('walletModal').classList.add('hidden'); document.getElementById('walletMsg').textContent=''; }
function setWalletMode(mode){
  walletMode = mode;
  document.getElementById('depositBtn').classList.toggle('selected', mode === 'deposit');
  document.getElementById('withdrawBtn').classList.toggle('selected', mode === 'withdraw');
  document.getElementById('walletTitle').textContent = mode === 'deposit' ? 'Deposit Funds' : 'Withdraw Funds';
  document.getElementById('walletSub').textContent = mode === 'deposit' ? 'Add dummy capital to your trading wallet.' : 'Remove available dummy cash from your trading wallet.';
}
async function submitWallet(){
  const msg = document.getElementById('walletMsg'); msg.className='msg'; msg.textContent='Processing...';
  const payload = { movement_type: walletMode, amount: Number(document.getElementById('walletAmount').value), note: document.getElementById('walletNote').value };
  const res = await fetch('/api/wallet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data = await res.json();
  if(!res.ok){ msg.textContent = data.detail || 'Wallet action failed'; msg.classList.add('err'); return; }
  msg.textContent = data.message; msg.classList.add('ok');
  state.portfolio = data.portfolio; render();
}
document.getElementById('qty').addEventListener('input', updateEstimate);
let timer; document.getElementById('search').addEventListener('input', e => { clearTimeout(timer); timer=setTimeout(async()=>{ const r=await fetch('/api/search?q='+encodeURIComponent(e.target.value)); const data=await r.json();
    if(!r.ok || data.detail){ document.getElementById('assets').innerHTML = `<div class="empty">${data.detail || 'Search failed.'}</div>`; return; }
    renderAssets(data); },300); });
load();

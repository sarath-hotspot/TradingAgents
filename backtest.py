"""
AAPL Trade Simulation & PnL Calculator
Reads decisions from aapl_jan_march_2024.csv, fetches real prices via yfinance,
and simulates trades with a 5-tier position sizing model.

Position sizing:
    Buy         → +1.0  (full long)
    Overweight  → +0.5  (half long)
    Hold        →  0.0  (flat / exit)
    Underweight → -0.5  (half short)
    Sell        → -1.0  (full short)

Execution model:
    Signal on date D → enter at D's open, exit at D+1's open.
    PnL per day = position_size * SHARES * (open_D+1 - open_D)
"""

import csv
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Config ──────────────────────────────────────────────────────────────────
DECISIONS_FILE = "aapl_jan_march_2024.csv"
TICKER = "AAPL"
SHARES = 100  # notional shares per full position unit

POSITION_MAP = {
    "Buy":         1.0,
    "Overweight":  0.5,
    "Hold":        0.0,
    "Underweight": -0.5,
    "Sell":        -1.0,
}

# ── Load decisions ───────────────────────────────────────────────────────────
decisions = {}
with open(DECISIONS_FILE, newline="") as f:
    for row in csv.DictReader(f):
        decisions[row["date"]] = row["decision"]

dates = sorted(decisions.keys())
start = dates[0]
# Fetch one extra week of prices to ensure we have D+1 close for the last signal
end_dt = datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=7)
end = end_dt.strftime("%Y-%m-%d")

# ── Fetch OHLCV data ─────────────────────────────────────────────────────────
print(f"Fetching {TICKER} prices from {start} to {end} …")
ticker_obj = yf.Ticker(TICKER)
raw = ticker_obj.history(start=start, end=end, auto_adjust=True)
# history() returns a simple DatetimeIndex (tz-aware); normalize to date strings
index_strs = pd.to_datetime(raw.index).normalize().strftime("%Y-%m-%d")
raw.index = index_strs
open_prices  = raw["Open"].dropna()
price_dict = open_prices.to_dict()

# ── Simulate trades ──────────────────────────────────────────────────────────
results = []
cumulative_pnl = 0.0
sorted_price_dates = sorted(price_dict.keys())

for signal_date in dates:
    decision = decisions[signal_date]
    position = POSITION_MAP.get(decision, 0.0)

    if position == 0.0:
        results.append({
            "date": signal_date,
            "decision": decision,
            "position": position,
            "entry_price": None,
            "exit_price": None,
            "daily_pnl": 0.0,
            "cumulative_pnl": cumulative_pnl,
        })
        continue

    # Find entry price (open on signal_date)
    entry_price = price_dict.get(signal_date)
    if entry_price is None:
        print(f"  [skip] No price for signal date {signal_date}")
        continue

    # Find exit price (open on next available trading day)
    idx = sorted_price_dates.index(signal_date) if signal_date in sorted_price_dates else -1
    exit_price = None
    if idx != -1 and idx + 1 < len(sorted_price_dates):
        exit_price = price_dict[sorted_price_dates[idx + 1]]

    if exit_price is None:
        print(f"  [skip] No next-day price after {signal_date}")
        continue

    daily_pnl = position * SHARES * (exit_price - entry_price)
    cumulative_pnl += daily_pnl

    results.append({
        "date": signal_date,
        "decision": decision,
        "position": position,
        "entry_price": round(float(entry_price), 4),
        "exit_price": round(float(exit_price), 4),
        "daily_pnl": round(daily_pnl, 2),
        "cumulative_pnl": round(cumulative_pnl, 2),
    })

# ── Print summary ────────────────────────────────────────────────────────────
print(f"\n{'Date':<12} {'Decision':<12} {'Pos':>5} {'Entry':>8} {'Exit':>8} {'Day PnL':>10} {'Cum PnL':>12}")
print("-" * 75)
for r in results:
    if r["entry_price"] is None:
        cum = f"${r['cumulative_pnl']:,.2f}"
        print(f"{r['date']:<12} {r['decision']:<12} {'0.0':>5} {'—':>8} {'—':>8} {'$0.00':>10} {cum:>12}")
    else:
        print(
            f"{r['date']:<12} {r['decision']:<12} {r['position']:>5.1f} "
            f"{r['entry_price']:>8.2f} {r['exit_price']:>8.2f} "
            f"${r['daily_pnl']:>9,.2f} ${r['cumulative_pnl']:>11,.2f}"
        )

# ── Trade stats ──────────────────────────────────────────────────────────────
active_trades = [r for r in results if r["entry_price"] is not None]
winners = [r for r in active_trades if r["daily_pnl"] > 0]
losers  = [r for r in active_trades if r["daily_pnl"] < 0]

print("\n── Summary ─────────────────────────────────────────────────────────────")
print(f"  Total trading days   : {len(results)}")
print(f"  Active trades        : {len(active_trades)}")
print(f"  Flat (Hold) days     : {len(results) - len(active_trades)}")
print(f"  Winners              : {len(winners)}")
print(f"  Losers               : {len(losers)}")
win_rate = len(winners) / len(active_trades) * 100 if active_trades else 0
print(f"  Win rate             : {win_rate:.1f}%")
print(f"  Total PnL            : ${cumulative_pnl:,.2f}")
if active_trades:
    avg_win  = sum(r["daily_pnl"] for r in winners)  / len(winners)  if winners else 0
    avg_loss = sum(r["daily_pnl"] for r in losers)   / len(losers)   if losers  else 0
    print(f"  Avg win              : ${avg_win:,.2f}")
    print(f"  Avg loss             : ${avg_loss:,.2f}")
    if avg_loss != 0:
        print(f"  Profit factor        : {abs(avg_win / avg_loss):.2f}")

# ── Write results CSV ────────────────────────────────────────────────────────
out_file = "aapl_backtest_results.csv"
with open(out_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "decision", "position",
                                            "entry_price", "exit_price",
                                            "daily_pnl", "cumulative_pnl"])
    writer.writeheader()
    writer.writerows(results)

print(f"\nDetailed results written to {out_file}")

# ── Chart: OHLC + signals + cumulative PnL ───────────────────────────────────
# Rebuild OHLC with a proper DatetimeIndex for mplfinance
ohlc = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
ohlc.index = pd.to_datetime(raw.index)  # raw.index already normalized to date strings → back to DatetimeIndex
ohlc.index.name = "Date"

# Build signal markers keyed by date string
signal_opens = {r["date"]: r["entry_price"] for r in results if r["entry_price"] is not None}

long_dates, long_prices   = [], []  # Overweight / Buy
short_dates, short_prices = [], []  # Underweight / Sell
for r in results:
    if r["entry_price"] is None:
        continue
    if r["position"] > 0:
        long_dates.append(r["date"])
        long_prices.append(r["entry_price"])
    else:
        short_dates.append(r["date"])
        short_prices.append(r["entry_price"])

def dates_to_idx(date_list, ohlc_df):
    """Convert date strings to positional index in ohlc_df."""
    index_strs = ohlc_df.index.strftime("%Y-%m-%d").tolist()
    return [index_strs.index(d) for d in date_list if d in index_strs]

long_idx  = dates_to_idx(long_dates, ohlc)
short_idx = dates_to_idx(short_dates, ohlc)

# Build addplot scatter series aligned to ohlc index
n = len(ohlc)
long_series  = pd.Series([float("nan")] * n, index=ohlc.index)
short_series = pd.Series([float("nan")] * n, index=ohlc.index)
for i, d in zip(long_idx, [d for d in long_dates if d in ohlc.index.strftime("%Y-%m-%d").tolist()]):
    long_series.iloc[i] = long_prices[long_dates.index(d)] * 0.993   # just below open
for i, d in zip(short_idx, [d for d in short_dates if d in ohlc.index.strftime("%Y-%m-%d").tolist()]):
    short_series.iloc[i] = short_prices[short_dates.index(d)] * 1.007  # just above open

# Cumulative PnL panel
pnl_by_date = {r["date"]: r["cumulative_pnl"] for r in results}
pnl_series = pd.Series(
    [pnl_by_date.get(d.strftime("%Y-%m-%d"), float("nan")) for d in ohlc.index],
    index=ohlc.index,
)
pnl_series = pnl_series.ffill()

ap = [
    mpf.make_addplot(long_series,  type="scatter", markersize=80, marker="^", color="lime",   panel=0),
    mpf.make_addplot(short_series, type="scatter", markersize=80, marker="v", color="red",    panel=0),
    mpf.make_addplot(pnl_series,   type="line",    color="gold",  width=1.5, panel=1,
                     ylabel="Cum PnL ($)"),
]

long_patch  = mpatches.Patch(color="lime", label="Long (Overweight / Buy)")
short_patch = mpatches.Patch(color="red",  label="Short (Underweight / Sell)")
pnl_patch   = mpatches.Patch(color="gold", label="Cumulative PnL")

fig, axes = mpf.plot(
    ohlc,
    type="candle",
    style="nightclouds",
    title=f"{TICKER}  Jan–Mar 2024  |  Signal Backtest",
    ylabel="Price (USD)",
    volume=False,
    addplot=ap,
    panel_ratios=(3, 1),
    figsize=(16, 9),
    returnfig=True,
)

axes[0].legend(handles=[long_patch, short_patch, pnl_patch], loc="upper left", fontsize=9)

chart_file = "aapl_backtest_chart.png"
fig.savefig(chart_file, dpi=150, bbox_inches="tight")
print(f"Chart saved to {chart_file}")
plt.show()

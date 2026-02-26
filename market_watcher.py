import asyncio
import json
import os
import yfinance as yf
from datetime import datetime
import subprocess
import pandas as pd

PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"]
BALANCE = 10000
RISK_PCT = 2.0
PATH = "data/trades.json"

def get_risk_calculation(balance, risk, entry, sl):
    try:
        cmd = ["trading_tools/venv/bin/python3", "risk_calc.py", 
               str(balance), str(risk), str(entry), str(sl)]
        result = subprocess.check_output(cmd).decode()
        for line in result.splitlines():
            if "SUGGESTED LOT SIZE" in line:
                return float(line.split(":")[-1].replace("-", "").strip())
    except:
        pass
    return 0.1

async def monitor_market():
    print(f"[{datetime.now()}] Tice 'Sniper Mode' Watcher Started...")
    
    while True:
        if os.path.exists(PATH):
            with open(PATH, "r") as f:
                try:
                    trades = json.load(f)
                except:
                    trades = []
        else:
            trades = []
            
        current_prices = {}
        
        # 1. Fetch Market Data & Technicals
        for symbol in PAIRS:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="5d", interval="15m")
                if df.empty or len(df) < 50: continue
                
                # Institutional Level Technicals
                df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
                df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                current_price = float(df['Close'].iloc[-1])
                pair_name = symbol.replace("=X", "")
                current_prices[pair_name] = {
                    'price': current_price,
                    'ema20': float(df['EMA20'].iloc[-1]),
                    'ema50': float(df['EMA50'].iloc[-1]),
                    'rsi': float(df['RSI'].iloc[-1])
                }
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")

        # 2. Manage Open Positions (Update floating profit & close conditions)
        for t in trades:
            if t['status'] == 'OPEN' and t['pair'] in current_prices:
                cp = current_prices[t['pair']]['price']
                pip_multiplier = 100 if "JPY" in t['pair'] else 10000
                
                if t['type'] == 'BUY':
                    pips = (cp - t['entry']) * pip_multiplier
                else:
                    pips = (t['entry'] - cp) * pip_multiplier
                
                # 1 Lot = approx $10 per pip
                profit = pips * (t['lots'] * 10)
                
                t['pips'] = round(pips, 1)
                t['profit'] = round(profit, 2)
                
                # Check Take Profit / Stop Loss
                if (t['type'] == 'BUY' and cp >= t['tp']) or (t['type'] == 'SELL' and cp <= t['tp']):
                    t['status'] = 'CLOSED_WIN'
                    print(f"[{datetime.now()}] 🎯 WIN! {t['pair']} hit TP for ${t['profit']}")
                elif (t['type'] == 'BUY' and cp <= t['sl']) or (t['type'] == 'SELL' and cp >= t['sl']):
                    t['status'] = 'CLOSED_LOSS'
                    print(f"[{datetime.now()}] 🛡️ STOP OUT: {t['pair']} closed at loss for ${t['profit']}")

        # 3. Sniper Entry Logic (High Probability Only)
        for pair_name, data in current_prices.items():
            # Restrict to 1 open trade per pair
            open_trades = [t for t in trades if t['pair'] == pair_name and t['status'] == 'OPEN']
            if len(open_trades) > 0:
                continue
                
            cp = data['price']
            ema20 = data['ema20']
            ema50 = data['ema50']
            rsi = data['rsi']
            
            trade_type = None
            # Tighter spreads/SL for high precision
            sl_dist = 0.0025 if "JPY" not in pair_name else 0.25
            tp_dist = sl_dist * 2.5  # Aggressive 1:2.5 Risk/Reward
            
            # Smart Money Concepts / Trend + Momentum Strategy
            if ema20 > ema50 and rsi < 45: # Uptrend but currently pulled back (buy the dip)
                trade_type = "BUY"
                sl = cp - sl_dist
                tp = cp + tp_dist
            elif ema20 < ema50 and rsi > 55: # Downtrend but rallied (sell the rip)
                trade_type = "SELL"
                sl = cp + sl_dist
                tp = cp - tp_dist
                
            if trade_type:
                lots = get_risk_calculation(BALANCE, RISK_PCT, cp, sl)
                lots = min(lots, 5.0) # Cap lot size
                
                trade = {
                    "timestamp": datetime.now().isoformat(),
                    "agent": "Tice (Sniper)",
                    "pair": pair_name,
                    "type": trade_type,
                    "entry": round(cp, 5),
                    "sl": round(sl, 5),
                    "tp": round(tp, 5),
                    "lots": round(lots, 2),
                    "status": "OPEN",
                    "pips": 0,
                    "profit": 0.0
                }
                trades.append(trade)
                print(f"[{datetime.now()}] ⚡ SNIPER ENTRY: {trade_type} {pair_name} at {cp} (RSI: {rsi:.1f})")

        with open(PATH, "w") as f:
            json.dump(trades[-200:], f, indent=2)
            
        await asyncio.sleep(30) # Very fast updates for the dashboard

if __name__ == "__main__":
    asyncio.run(monitor_market())

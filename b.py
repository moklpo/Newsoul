import pandas as pd
import numpy as np
import datetime
import time
import requests
import re
import argparse
import sys
from fyers_apiv3 import fyersModel

# --- INPUT HANDLING ---
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Fyers Redirect URL")
args = parser.parse_args()

# --- CONFIGURATION ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

# AlphaTrend Inputs
COEFF = 1.0
AP = 14

notified_stocks = {}

# --- INDICATOR CALCULATIONS (Exact Pine Script Logic) ---
def get_mfi(df, period):
    tp = (df['high'] + df['low'] + df['close']) / 3
    mf = tp * df['volume']
    pos_f = mf.where(tp > tp.shift(1), 0).rolling(window=period).sum()
    neg_f = mf.where(tp < tp.shift(1), 0).rolling(window=period).sum()
    # Avoid div by zero
    res = 100 - (100 / (1 + (pos_f / neg_f.replace(0, np.nan))))
    return res.fillna(100)

def calculate_alphatrend(df):
    tr = pd.concat([df['high']-df['low'], (df['high']-df['close'].shift()).abs(), (df['low']-df['close'].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=AP).mean()
    upT = df['low'] - atr * COEFF
    downT = df['high'] + atr * COEFF
    mfi = get_mfi(df, AP)
    
    at = np.zeros(len(df))
    for i in range(1, len(df)):
        prev_at = at[i-1]
        if mfi.iloc[i] >= 50:
            at[i] = upT.iloc[i] if upT.iloc[i] > prev_at else prev_at
        else:
            at[i] = downT.iloc[i] if downT.iloc[i] < prev_at else prev_at
    
    df['at'] = at
    df['at2'] = df['at'].shift(2) # AlphaTrend[2]
    return df

# --- TOP MOVERS LOGIC (Day Open Based) ---
def get_top_movers(fyers, all_stocks):
    movers = []
    print(f"🔍 Finding Top 20 Gainers & Losers from Day Open...")
    batch_size = 50
    for i in range(0, len(all_stocks), batch_size):
        batch = all_stocks[i:i + batch_size]
        symbols_str = ",".join([f"NSE:{s}-EQ" for s in batch])
        try:
            res = fyers.quotes({"symbols": symbols_str})
            if res['s'] == 'ok' and 'd' in res:
                for d in res['d']:
                    if 'v' in d and 'lp' in d['v'] and 'open_price' in d['v']:
                        sym = d['n'].split(":")[1].replace("-EQ", "")
                        lp = d['v']['lp']
                        today_open = d['v']['open_price']
                        if today_open != 0:
                            change = ((lp - today_open) / today_open) * 100
                            movers.append({'symbol': sym, 'change': change})
        except: continue

    if not movers: return all_stocks[:40]
    
    df_movers = pd.DataFrame(movers)
    # Top 20 Gainer + Top 20 Loser = 40 Target Stocks
    top_gainers = df_movers.nlargest(20, 'change')['symbol'].tolist()
    top_losers = df_movers.nsmallest(20, 'change')['symbol'].tolist()
    
    final_list = list(set(top_gainers + top_losers))
    print(f"🎯 Scanning started for {len(final_list)} High-Momentum stocks.")
    return final_list

# --- TELEGRAM ---
def send_telegram(msg):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

# --- LOGIN ---
def get_access_token():
    if not args.url: return None
    try:
        auth_code = re.search(r'auth_code=([^&]+)', args.url).group(1)
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
        session.set_token(auth_code)
        return session.generate_token().get("access_token")
    except: return None

# --- CORE SCANNER (Exact Pine Logic) ---
def scan(fyers, active_stocks):
    today = datetime.date.today()
    start_dt = (today - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    
    for s in active_stocks:
        try:
            res = fyers.history({"symbol":f"NSE:{s}-EQ","resolution":"5","date_format":"1","range_from":start_dt,"range_to":today.strftime('%Y-%m-%d')})
            if res['s'] != 'ok': continue
            
            df = pd.DataFrame(res['candles'], columns=['time','open','high','low','close','volume'])
            df = calculate_alphatrend(df)
            
            # Signals
            df['buySig'] = (df['at'] > df['at2']) & (df['at'].shift(1) <= df['at2'].shift(1))
            df['sellSig'] = (df['at'] < df['at2']) & (df['at'].shift(1) >= df['at2'].shift(1))
            
            # BarsSince simulation
            df['K1'] = df.index.where(df['buySig']).to_series().ffill()
            df['K2'] = df.index.where(df['sellSig']).to_series().ffill()
            
            curr_idx = len(df) - 1
            k1_val = curr_idx - df['K1'].iloc[-1] if not pd.isna(df['K1'].iloc[-1]) else 999
            k2_val = curr_idx - df['K2'].iloc[-1] if not pd.isna(df['K2'].iloc[-1]) else 999
            
            o1_idx = df.index.where(df['buySig'].shift(1)).to_series().ffill().iloc[-1]
            o1_val = curr_idx - o1_idx if not pd.isna(o1_idx) else 999
            
            o2_idx = df.index.where(df['sellSig'].shift(1)).to_series().ffill().iloc[-1]
            o2_val = curr_idx - o2_idx if not pd.isna(o2_idx) else 999

            df_today = df[pd.to_datetime(df['time'], unit='s').dt.date == today]
            if df_today.empty: continue
            day_open = df_today.iloc[0]['open']
            curr = df.iloc[-1]

            # Re-entry logic
            gap = abs(curr['at'] - curr['at2'])
            avgP = (curr['at'] + curr['at2']) / 2
            isTouching_prev = (abs(df['at'].iloc[-2] - df['at2'].iloc[-2]) / ((df['at'].iloc[-2] + df['at2'].iloc[-2])/2)) < 0.0002
            
            signal_type = None
            if curr['buySig'] and o1_val > k2_val and curr['close'] >= (day_open * 1.012):
                signal_type = "🚀 *ALPHA BUY*"
            elif curr['sellSig'] and o2_val > k1_val and curr['close'] <= (day_open * 0.988):
                signal_type = "📉 *ALPHA SELL*"
            elif isTouching_prev and curr['at'] > df['at'].iloc[-2] and curr['at'] > curr['at2'] and curr['close'] >= (day_open * 1.012):
                signal_type = "🔼 *RE-ENTRY BUY*"
            elif isTouching_prev and curr['at'] < df['at'].iloc[-2] and curr['at'] < curr['at2'] and curr['close'] <= (day_open * 0.988):
                signal_type = "🔽 *RE-ENTRY SELL*"

            if signal_type and (s not in notified_stocks or time.time() - notified_stocks[s] > 600):
                notified_stocks[s] = time.time()
                send_telegram(f"{signal_type}: {s}\nPrice: {curr['close']}\nIntraday: {((curr['close']-day_open)/day_open)*100:.2f}%")
            time.sleep(0.01)
        except: continue

# --- MAIN LOOP ---
token = get_access_token()
if not token: sys.exit("🔴 Login Failed.")
fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
send_telegram("✅ *Bot Started: Top Movers + Kivanc Logic*")

full_watchlist = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [s.strip() for s in full_watchlist.split(",")]

while True:
    now = datetime.datetime.now()
    if now.hour == 15 and now.minute >= 31: break
    if now.minute % 5 == 0 and now.second == 1:
        active = get_top_movers(fyers, stocks)
        scan(fyers, active)
        time.sleep(10)
    time.sleep(1)

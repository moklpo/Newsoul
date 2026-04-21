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

COEFF = 1.0
AP = 14
CHANGE_FILTER = 1.012 
SELL_FILTER = 0.988    

notified_stocks = {}

# --- INDICATOR CALCULATIONS ---
def get_mfi(df, period):
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volume']
    pos_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    neg_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    return 100 - (100 / (1 + (pos_flow / neg_flow)))

def calculate_alphatrend(df):
    tr = pd.concat([df['high']-df['low'], (df['high']-df['close'].shift()).abs(), (df['low']-df['close'].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=AP).mean()
    upT = df['low'] - atr * COEFF
    downT = df['high'] + atr * COEFF
    mfi = get_mfi(df, AP)
    at = np.zeros(len(df))
    for i in range(1, len(df)):
        if mfi.iloc[i] >= 50:
            at[i] = upT.iloc[i] if upT.iloc[i] > at[i-1] else at[i-1]
        else:
            at[i] = downT.iloc[i] if downT.iloc[i] < at[i-1] else at[i-1]
    return pd.Series(at, index=df.index)

# --- UTILS ---
def send_telegram(msg):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def get_access_token():
    if not args.url: return None
    try:
        auth_code = re.search(r'auth_code=([^&]+)', args.url).group(1)
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
        session.set_token(auth_code)
        return session.generate_token().get("access_token")
    except: return None

# --- TOP MOVERS (From Open) ---
def get_top_movers(fyers, all_stocks):
    movers = []
    batch_size = 50
    for i in range(0, len(all_stocks), batch_size):
        batch = all_stocks[i:i + batch_size]
        res = fyers.quotes({"symbols": ",".join([f"NSE:{s}-EQ" for s in batch])})
        if res['s'] == 'ok':
            for d in res['d']:
                if 'lp' in d['v'] and 'open_price' in d['v']:
                    if d['v']['open_price'] != 0:
                        change = ((d['v']['lp'] - d['v']['open_price']) / d['v']['open_price']) * 100
                        movers.append({'symbol': d['n'].split(":")[1].replace("-EQ", ""), 'change': change})
    df = pd.DataFrame(movers)
    if df.empty: return all_stocks[:40]
    return list(set(df.nlargest(20, 'change')['symbol'].tolist() + df.nsmallest(20, 'change')['symbol'].tolist()))

# --- CORE SCANNER ---
def scan(fyers, active_stocks):
    today = datetime.date.today()
    start_dt = (today - datetime.timedelta(days=5)).strftime('%Y-%m-%d')
    
    for s in active_stocks:
        try:
            res = fyers.history({"symbol":f"NSE:{s}-EQ","resolution":"5","date_format":"1","range_from":start_dt,"range_to":today.strftime('%Y-%m-%d')})
            if res['s'] != 'ok': continue
            
            df = pd.DataFrame(res['candles'], columns=['time','open','high','low','close','volume'])
            df['at'] = calculate_alphatrend(df)
            df['at_delayed'] = df['at'].shift(2)
            
            df_today = df[pd.to_datetime(df['time'], unit='s').dt.date == today].copy()
            if df_today.empty: continue
            
            day_open = df_today.iloc[0]['open']
            curr = df_today.iloc[-1]
            prev = df_today.iloc[-2]

            signal_type = None
            
            # 1.2% Filter Check
            buy_zone = curr['close'] >= (day_open * CHANGE_FILTER)
            sell_zone = curr['close'] <= (day_open * SELL_FILTER)

            # Signal Logic
            if buy_zone:
                # Main Crossover
                if prev['at'] <= prev['at_delayed'] and curr['at'] > curr['at_delayed']:
                    signal_type = "🚀 ALPHA BUY"
                # Re-entry (Touch & Go)
                elif (abs(curr['at']-curr['at_delayed'])/curr['at'] < 0.0002) and curr['at'] > prev['at']:
                    signal_type = "🔼 RE-ENTRY BUY"

            elif sell_zone:
                # Main Crossunder
                if prev['at'] >= prev['at_delayed'] and curr['at'] < curr['at_delayed']:
                    signal_type = "📉 ALPHA SELL"
                # Re-entry (Touch & Go)
                elif (abs(curr['at']-curr['at_delayed'])/curr['at'] < 0.0002) and curr['at'] < prev['at']:
                    signal_type = "🔽 RE-ENTRY SELL"

            if signal_type and (s not in notified_stocks or time.time() - notified_stocks[s] > 300):
                notified_stocks[s] = time.time()
                send_telegram(f"{signal_type}: *{s}*\nPrice: {curr['close']}\nMove: {((curr['close']-day_open)/day_open)*100:.2f}%")
            time.sleep(0.01)
        except: continue

# --- MAIN LOOP ---
token = get_access_token()
if not token: sys.exit("🔴 Login Failed.")
fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
send_telegram("🚀 *Bot Online: Top Movers + AlphaTrend Mode*")

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

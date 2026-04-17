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

# AlphaTrend Parameters (As per your Pine Script)
COEFF = 1.0
AP = 14
CHANGE_FILTER = 1.012  # 1.2% for Buy
SELL_FILTER = 0.988    # 1.2% for Sell

notified_stocks = {}

# --- INDICATOR CALCULATIONS ---
def get_rsi(series, period):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_mfi(df, period):
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volume']
    positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=period).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=period).sum()
    return 100 - (100 / (1 + (positive_flow / negative_flow)))

def calculate_alphatrend(df):
    # ATR Calculation
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=AP).mean()

    upT = df['low'] - atr * COEFF
    downT = df['high'] + atr * COEFF
    
    # RSI or MFI based on volume availability
    mfi_rsi = get_mfi(df, AP) if 'volume' in df else get_rsi(df['close'], AP)
    
    at = np.zeros(len(df))
    for i in range(1, len(df)):
        if mfi_rsi.iloc[i] >= 50:
            at[i] = upT.iloc[i] if upT.iloc[i] > at[i-1] else at[i-1]
        else:
            at[i] = downT.iloc[i] if downT.iloc[i] < at[i-1] else at[i-1]
    return pd.Series(at, index=df.index)

# --- UTILS ---
def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def get_access_token():
    if not args.url: return None
    try:
        auth_code = re.search(r'auth_code=([^&]+)', args.url).group(1)
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
        session.set_token(auth_code)
        return session.generate_token().get("access_token")
    except Exception as e:
        print(f"❌ Login Error: {e}")
    return None

# --- CORE SCANNER ---
def scan(fyers, stocks):
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=5)).strftime('%Y-%m-%d')
    
    for s in stocks:
        try:
            symbol = f"NSE:{s}-EQ"
            res = fyers.history({"symbol":symbol,"resolution":"5","date_format":"1","range_from":start_date,"range_to":today.strftime('%Y-%m-%d')})
            if res['s'] != 'ok': continue
            
            df = pd.DataFrame(res['candles'], columns=['time','open','high','low','close','volume'])
            df['at'] = calculate_alphatrend(df)
            df['at_delayed'] = df['at'].shift(2)
            
            # Day Open for 1.2% Filter
            df_today = df[pd.to_datetime(df['time'], unit='s').dt.date == today]
            if df_today.empty: continue
            day_open = df_today.iloc[0]['open']
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Logic conditions
            buy_zone = curr['close'] >= (day_open * CHANGE_FILTER)
            sell_zone = curr['close'] <= (day_open * SELL_FILTER)
            
            # Main Crossovers
            buy_signal = (prev['at'] <= prev['at_delayed']) and (curr['at'] > curr['at_delayed'])
            sell_signal = (prev['at'] >= prev['at_delayed']) and (curr['at'] < curr['at_delayed'])
            
            # Re-entry Logic (Touch & Go)
            gap = abs(curr['at'] - curr['at_delayed'])
            is_touching = (gap / ((curr['at'] + curr['at_delayed'])/2)) < 0.0002
            is_bullish = curr['at'] > curr['at_delayed']
            
            re_entry_buy = is_touching and curr['at'] > prev['at'] and is_bullish
            re_entry_sell = is_touching and curr['at'] < prev['at'] and not is_bullish

            signal_type = None
            if buy_zone:
                if buy_signal: signal_type = "🚀 ALPHA BUY"
                elif re_entry_buy: signal_type = "🔼 RE-ENTRY BUY"
            elif sell_zone:
                if sell_signal: signal_type = "📉 ALPHA SELL"
                elif re_entry_sell: signal_type = "🔽 RE-ENTRY SELL"

            if signal_type and (s not in notified_stocks or time.time() - notified_stocks[s] > 300):
                notified_stocks[s] = time.time()
                msg = (f"{signal_type}: *{s}*\n"
                       f"Price: {curr['close']}\n"
                       f"Open: {day_open}\n"
                       f"Move: {((curr['close']-day_open)/day_open)*100:.2f}%")
                send_telegram(msg)
            
            time.sleep(0.02)
        except: continue

# --- MAIN EXECUTION ---
token = get_access_token()
if not token: sys.exit("🔴 Login Failed.")
fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)

stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [s.strip() for s in stocks_list.split(",")]

print("🚀 Bot Started: AlphaTrend + 1.2% Filter")
while True:
    now = datetime.datetime.now()
    if now.hour == 15 and now.minute >= 31: break
    if now.minute % 5 == 0 and now.second == 1:
        scan(fyers, stocks)
        time.sleep(10)
    time.sleep(1)

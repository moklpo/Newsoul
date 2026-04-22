import pandas as pd
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
CHANGE_PCT = 1.2  
TOP_COUNT = 20  # Top 20 from TODAY'S OPEN

notified_stocks = {}

# --- INDICATORS ---
def get_mfi(df, period=14):
    tp = (df['high'] + df['low'] + df['close']) / 3
    mf = tp * df['volume']
    pos_mf = mf.where(tp > tp.shift(1), 0).rolling(window=period).sum()
    neg_mf = mf.where(tp < tp.shift(1), 0).rolling(window=period).sum()
    mfr = pos_mf / neg_mf
    return 100 - (100 / (1 + mfr))

def get_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).rolling(window=period).mean()

def calculate_alphatrend(df):
    df['atr'] = get_atr(df, AP)
    df['mfi'] = get_mfi(df, AP)
    up_t = df['low'] - df['atr'] * COEFF
    down_t = df['high'] + df['atr'] * COEFF
    at = [0.0] * len(df)
    for i in range(1, len(df)):
        if df['mfi'].iloc[i] >= 50:
            at[i] = up_t.iloc[i] if up_t.iloc[i] > at[i-1] else at[i-1]
        else:
            at[i] = down_t.iloc[i] if down_t.iloc[i] < at[i-1] else at[i-1]
    df['at'] = at
    return df

# --- DYNAMIC INTRADAY FILTER (OPEN VS LTP) ---
def get_filtered_watchlist(full_list):
    try:
        data = {"symbols": ",".join(full_list)}
        quotes = fyers.quotes(data)
        if quotes['s'] != 'ok': return full_list
        
        stock_data = []
        for item in quotes['d']:
            symbol = item['n']
            ltp = item['v']['lp'] 
            open_price = item['v']['op'] # Current Day Open
            
            if open_price > 0:
                intraday_chg = ((ltp - open_price) / open_price) * 100
                stock_data.append({'symbol': symbol, 'chg': intraday_chg})
        
        df_movers = pd.DataFrame(stock_data)
        top_gainers = df_movers.nlargest(TOP_COUNT, 'chg')['symbol'].tolist()
        top_losers = df_movers.nsmallest(TOP_COUNT, 'chg')['symbol'].tolist()
        return list(set(top_gainers + top_losers))
    except: return full_list

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def get_access_token():
    if not args.url: return None
    try:
        match = re.search(r'auth_code=([^&]+)', args.url)
        if match:
            auth_code = match.group(1)
            session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
            session.set_token(auth_code)
            return session.generate_token().get("access_token")
    except Exception as e: print(f"❌ Login Error: {e}")
    return None

# --- LOGIN ---
token = get_access_token()
if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("✅ SYSTEM LIVE: AlphaTrend + Intraday Open Filter")
else:
    sys.exit("🔴 Login Failed.")

stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
master_watchlist = [f"NSE:{s.strip()}-EQ" for s in stocks_list.split(",")]

def scan():
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    active_scan_list = get_filtered_watchlist(master_watchlist)

    for symbol in active_scan_list:
        try:
            res = fyers.history({"symbol":symbol,"resolution":"5","date_format":"1","range_from":start_date,"range_to":today})
            if res['s'] != 'ok': continue
            df = pd.DataFrame(res['candles'], columns=['time','open','high','low','close','volume'])
            df = calculate_alphatrend(df)
            
            df_today = df[pd.to_datetime(df['time'], unit='s').dt.date == datetime.date.today()]
            if len(df_today) < 2: continue
            
            day_open = df_today.iloc[0]['open']
            curr_price = df.iloc[-1]['close']
            day_move = ((curr_price - day_open) / day_open) * 100

            at_curr, at_prev1, at_prev2, at_prev3 = df['at'].iloc[-1], df['at'].iloc[-2], df['at'].iloc[-3], df['at'].iloc[-4]

            buy_signal = at_curr > at_prev2 and at_prev1 <= at_prev3 and day_move >= CHANGE_PCT
            sell_signal = at_curr < at_prev2 and at_prev1 >= at_prev3 and day_move <= -CHANGE_PCT

            clean_name = symbol.replace("NSE:","").replace("-EQ","")
            if (buy_signal or sell_signal) and clean_name not in notified_stocks:
                side = "BUY" if buy_signal else "SELL"
                msg = (f"{'🚀' if side == 'BUY' else '📉'} *AlphaTrend {side}*: {clean_name}\n"
                       f"📊 Move from Open: {day_move:.2f}%\n💰 Price: {curr_price}")
                send_telegram(msg)
                notified_stocks[clean_name] = time.time()
            time.sleep(0.05)
        except: continue

while True:
    now = datetime.datetime.now()
    if now.hour == 15 and now.minute >= 31: break
    if now.minute % 5 == 0 and now.second == 5:
        scan()
        time.sleep(10)
    time.sleep(1)

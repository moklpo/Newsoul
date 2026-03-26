from fyers_apiv3 import fyersModel
import pandas as pd
import datetime
import time
import requests
import re
import argparse
import sys

# --- INPUT HANDLING ---
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Fyers Redirect URL")
args = parser.parse_args()

# --- STRATEGY CONFIG ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

CHANGE_THRESHOLD = 1.2
BODY_RATIO_MIN = 0.6
LOOKBACK = 15
NIFTY_LIMIT = 0.15
SL_PCT = 0.5
TP_PCT = 1.0
EMA_LEN = 5
PULLBACK_BUFFER = 0.20
ATR_MULTIPLIER = 2.0
MAX_SIGNALS = 3

notified_stocks = {}

# --- MANUAL INDICATORS (No pandas_ta needed) ---
def get_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def get_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=length).mean()

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

def send_telegram(msg):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def get_perfect_strike(symbol, price, side):
    if "NIFTY" in symbol and "BANK" not in symbol: step = 50
    elif "BANKNIFTY" in symbol: step = 100
    elif price > 1000: step = 10
    elif price > 500: step = 5
    else: step = 2.5
    atm = round(price / step) * step
    return f"{atm + step if side == 'BUY' else atm - step} {'CE' if side == 'BUY' else 'PE'}"

# --- LOGIN ---
token = get_access_token()
if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    send_telegram("🚀 *Bot Online:* 5 EMA Logic Active (No-Library Mode)")
else:
    sys.exit("🔴 Login Failed.")

stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [s.strip() for s in stocks_list.split(",")]

def scan():
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    
    n_res = fyers.history({"symbol":"NSE:NIFTY50-INDEX","resolution":"5","date_format":"1","range_from":start_date,"range_to":today.strftime('%Y-%m-%d')})
    if n_res['s'] != 'ok': return
    df_nifty = pd.DataFrame(n_res['candles'], columns=['time','open','high','low','close','volume'])
    df_nifty_today = df_nifty[pd.to_datetime(df_nifty['time'], unit='s').dt.date == today]
    if len(df_nifty_today) < 3: return
    
    nifty_m_open = df_nifty_today.iloc[0]['open']
    nifty_day_move = ((df_nifty_today.iloc[-1]['close'] - nifty_m_open) / nifty_m_open) * 100

    for s in stocks:
        try:
            symbol = f"NSE:{s}-EQ"
            res = fyers.history({"symbol":symbol,"resolution":"5","date_format":"1","range_from":start_date,"range_to":today.strftime('%Y-%m-%d')})
            if res['s'] != 'ok': continue
            
            df = pd.DataFrame(res['candles'], columns=['time','open','high','low','close','volume'])
            df['ema5'] = get_ema(df['close'], EMA_LEN)
            df['atr'] = get_atr(df, 14)
            
            curr = df.iloc[-2]
            df_today = df[pd.to_datetime(df['time'], unit='s').dt.date == today]
            if len(df_today) < 3: continue

            m_open = df_today.iloc[0]['open']
            stock_move = ((curr['close'] - m_open) / m_open) * 100
            
            # Logic
            is_fresh_high = curr['close'] > df.iloc[-(LOOKBACK+2):-2]['high'].max()
            is_fresh_low = curr['close'] < df.iloc[-(LOOKBACK+2):-2]['low'].min()
            
            c_rng = curr['high'] - curr['low']
            is_strong = c_rng > 0 and (abs(curr['close'] - curr['open']) / c_rng) >= BODY_RATIO_MIN
            is_not_spike = c_rng <= (curr['atr'] * ATR_MULTIPLIER)
            
            dist_ema_buy = (curr['low'] - curr['ema5']) / curr['ema5'] * 100
            dist_ema_sell = (curr['ema5'] - curr['high']) / curr['ema5'] * 100
            is_buy_pb = curr['low'] <= curr['ema5'] or (dist_ema_buy <= PULLBACK_BUFFER and curr['low'] > curr['ema5'])
            is_sell_pb = curr['high'] >= curr['ema5'] or (dist_ema_sell <= PULLBACK_BUFFER and curr['high'] < curr['ema5'])

            resilient_buy = not (nifty_day_move < -NIFTY_LIMIT and stock_move < (nifty_day_move * 0.4))
            weak_sell = not (nifty_day_move > NIFTY_LIMIT and stock_move > (nifty_day_move * 0.4))

            if s not in notified_stocks: notified_stocks[s] = {'b_count': 0, 's_count': 0, 'last_bar': 0}

            signal = None
            if stock_move >= CHANGE_THRESHOLD and is_fresh_high and is_strong and resilient_buy and is_buy_pb and curr['close'] > curr['ema5'] and is_not_spike and notified_stocks[s]['b_count'] < MAX_SIGNALS:
                signal = "BUY"
            elif stock_move <= -CHANGE_THRESHOLD and is_fresh_low and is_strong and weak_sell and is_sell_pb and curr['close'] < curr['ema5'] and is_not_huge_spike and notified_stocks[s]['s_count'] < MAX_SIGNALS:
                signal = "SELL"

            if signal and curr['time'] > notified_stocks[s]['last_bar'] + 300:
                notified_stocks[s]['last_bar'] = curr['time']
                if signal == "BUY": notified_stocks[s]['b_count'] += 1
                else: notified_stocks[s]['s_count'] += 1
                
                strike = get_perfect_strike(s, curr['close'], signal)
                msg = f"{'🚀' if signal=='BUY' else '📉'} *{signal}*: {s}\nPrice: {curr['close']}\nMove: {stock_move:.2f}%\nStrike: `{strike}`"
                send_telegram(msg)
            time.sleep(0.02)
        except: continue

# --- MAIN LOOP ---
while True:
    now = datetime.datetime.now()
    if now.hour == 15 and now.minute >= 31: break
    if now.minute % 5 == 0 and now.second == 5:
        scan()
        time.sleep(10)
    time.sleep(1)

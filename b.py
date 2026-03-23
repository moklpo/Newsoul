from fyers_apiv3 import fyersModel
import pandas as pd
import datetime
import time
import requests
import re
import argparse
import sys

# --- INPUT HANDLING FOR GITHUB ---
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Fyers Redirect URL from GitHub Input")
args = parser.parse_args()

# --- STRATEGY CONFIGURATION (Pinescript logic) ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

CHANGE_THRESHOLD = 1.2    # Min 1.2% move from 9:15 open
BODY_RATIO_MIN = 0.6     # 60% Candle Body/Range
LOOKBACK = 15            # 15 Candles for Fresh High/Low
NIFTY_LIMIT = 0.15       # Nifty RS Threshold
SL_PCT = 0.5             # 0.5% Fixed SL
TP_PCT = 1.0             # 1.0% Target

# Tracker to prevent duplicate alerts
notified_stocks = {}

def get_access_token():
    if not args.url: return None
    try:
        match = re.search(r'auth_code=([^&]+)', args.url)
        if match:
            auth_code = match.group(1)
            session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
            session.set_token(auth_code)
            return session.generate_token().get("access_token")
    except Exception as e:
        print(f"❌ Login Error: {e}")
    return None

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def get_best_strike(price, side):
    """
    Calculates affordable, lower-theta strike price.
    Uses generic step sizes for stocks.
    """
    if price > 5000: step = 100
    elif price > 2000: step = 50
    elif price > 1000: step = 20
    elif price > 500: step = 10
    else: step = 5
    
    # Round to nearest ATM
    atm = round(price / step) * step
    
    if side == "BUY":
        # Slight OTM Call (Higher strike) for lower premium/theta
        strike = atm + step
        return f"{int(strike)} CE"
    else:
        # Slight OTM Put (Lower strike)
        strike = atm - step
        return f"{int(strike)} PE"

# --- LOGIN ---
token = get_access_token()
if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("✅ SYSTEM LIVE: Nifty Resilience & Strike Suggester Active")
    send_telegram("🚀 *Bot Online:* Scanning with +1.2%/-1.2% RS Filter & Strike Suggester...")
else:
    sys.exit("🔴 Login Failed.")

# --- STOCKS ---
stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [s.strip() for s in stocks_list.split(",")]

def scan():
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    # 1. Fetch Nifty 50 Index Data
    nifty_h5 = fyers.history({"symbol":"NSE:NIFTY50-INDEX","resolution":"5","date_format":"1","range_from":start_date,"range_to":today_str})
    if nifty_h5['s'] != 'ok': return
    
    df_nifty = pd.DataFrame(nifty_h5['candles'], columns=['time','open','high','low','close','volume'])
    df_nifty['time'] = pd.to_datetime(df_nifty['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
    df_nifty_today = df_nifty[df_nifty['time'].dt.date == today]
    
    if len(df_nifty_today) < 3: return # 🛡️ Safety: No signals before 9:30 AM

    nifty_m_open = df_nifty_today.iloc[0]['open']
    nifty_close = df_nifty_today.iloc[-1]['close']
    nifty_day_move = ((nifty_close - nifty_m_open) / nifty_m_open) * 100

    for s in stocks:
        try:
            symbol = f"NSE:{s}-EQ"
            h5 = fyers.history({"symbol":symbol,"resolution":"5","date_format":"1","range_from":start_date,"range_to":today_str})
            if h5['s'] != 'ok': continue
            
            df = pd.DataFrame(h5['candles'], columns=['time','open','high','low','close','volume'])
            df['time'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
            df_today = df[df['time'].dt.date == today]
            
            if len(df_today) < 3: continue 

            m_open = df_today.iloc[0]['open']
            curr = df.iloc[-2]
            c_close, c_open, c_high, c_low = curr['close'], curr['open'], curr['high'], curr['low']
            
            stock_day_move = ((c_close - m_open) / m_open) * 100
            
            # 2. Fresh High/Low (15 candle lookback)
            is_fresh_high = c_close > df.iloc[-(LOOKBACK+2):-2]['high'].max()
            is_fresh_low = c_close < df.iloc[-(LOOKBACK+2):-2]['low'].min()
            
            # 3. Candle Strength
            c_rng = c_high - c_low
            is_strong = c_rng > 0 and (abs(c_close - c_open) / c_rng) >= BODY_RATIO_MIN
            
            # 4. Resilience Logic (Nifty RS)
            resilient_buy = True
            if nifty_day_move < -NIFTY_LIMIT and stock_day_move < (nifty_day_move * 0.4): resilient_buy = False
            
            weak_sell = True
            if nifty_day_move > NIFTY_LIMIT and stock_day_move > (nifty_day_move * 0.4): weak_sell = False

            # --- SIGNAL CHECK ---
            signal = None
            if stock_day_move >= CHANGE_THRESHOLD and is_fresh_high and is_strong and resilient_buy and c_close > c_open:
                signal = "BUY"
            elif stock_day_move <= -CHANGE_THRESHOLD and is_fresh_low and is_strong and weak_sell and c_close < c_open:
                signal = "SELL"

            if signal and notified_stocks.get(s) != signal:
                sl = round(c_close * (1 - SL_PCT/100 if signal == "BUY" else 1 + SL_PCT/100), 2)
                tp = round(c_close * (1 + TP_PCT/100 if signal == "BUY" else 1 - TP_PCT/100), 2)
                
                # Strike Suggestion
                best_strike = get_best_strike(c_close, signal)
                
                emoji = "🟢" if signal == "BUY" else "🔴"
                msg = (f"{emoji} *{signal} SIGNAL*: {s}\n"
                       f"💰 Price: {c_close}\n"
                       f"📈 Day Move: {stock_day_move:.2f}%\n"
                       f"🎯 *Option:* {best_strike}\n"
                       f"🛡 SL: {sl} | 🎯 TP: {tp}")
                
                send_telegram(msg)
                notified_stocks[s] = signal

            time.sleep(0.04)
        except: continue

# --- LOOP ---
while True:
    now = datetime.datetime.now()
    if now.hour == 15 and now.minute >= 31: break
    if now.minute % 5 == 0 and now.second == 5:
        scan()
        time.sleep(10)
    time.sleep(1)

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

# --- CONFIGURATION (Strategy Constants from PineScript) ---
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

# To prevent duplicate alerts for the same stock in the same direction
notified_stocks = {}

def get_access_token():
    full_url = args.url
    if not full_url:
        print("❌ Error: No URL provided!")
        return None
    try:
        match = re.search(r'auth_code=([^&]+)', full_url)
        if match:
            auth_code = match.group(1)
            session = fyersModel.SessionModel(
                client_id=APP_ID, secret_key=SECRET_ID, 
                redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code"
            )
            session.set_token(auth_code)
            response = session.generate_token()
            return response.get("access_token")
    except Exception as e:
        print(f"❌ Login Error: {e}")
    return None

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- MAIN ENGINE ---
token = get_access_token()

if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("✅ LOGIN SUCCESSFUL! Nifty Resilience Bot is live.")
    send_telegram("🚀 *Bot Online:* Scanning with Nifty Resilience & 0.5% SL Filter...")
else:
    sys.exit("🔴 Login Failed. Check URL/Credentials.")

stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [s.strip() for s in stocks_list.split(",")]

def scan():
    today_date = datetime.date.today()
    today_str = today_date.strftime('%Y-%m-%d')
    start_date = (today_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    
    # 1. Fetch Nifty Data for RS Check
    nifty_h5 = fyers.history({"symbol":"NSE:NIFTY50-INDEX","resolution":"5","date_format":"1","range_from":start_date,"range_to":today_str})
    if nifty_h5['s'] != 'ok': return
    
    df_nifty = pd.DataFrame(nifty_h5['candles'], columns=['time','open','high','low','close','volume'])
    df_nifty['time'] = pd.to_datetime(df_nifty['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
    df_nifty_today = df_nifty[df_nifty['time'].dt.date == today_date]
    
    if len(df_nifty_today) < 3: return # 🛡️ Safety Filter: Wait for 9:30 AM (3 candles)

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
            df_today = df[df['time'].dt.date == today_date]
            
            if len(df_today) < 3: continue 

            m_open = df_today.iloc[0]['open']
            curr_candle = df.iloc[-2] # Last completed 5m candle
            c_close, c_open, c_high, c_low = curr_candle['close'], curr_candle['open'], curr_candle['high'], curr_candle['low']
            
            stock_day_move = ((c_close - m_open) / m_open) * 100
            
            # 2. Fresh High/Low (15 candle lookback)
            is_fresh_high = c_close > df.iloc[-(LOOKBACK+2):-2]['high'].max()
            is_fresh_low = c_close < df.iloc[-(LOOKBACK+2):-2]['low'].min()
            
            # 3. Candle Strength
            c_range = c_high - c_low
            is_strong = c_range > 0 and (abs(c_close - c_open) / c_range) >= BODY_RATIO_MIN
            
            # 4. Resilience Logic
            is_resilient_buy = True
            if nifty_day_move < -NIFTY_LIMIT:
                if stock_day_move < (nifty_day_move * 0.4): is_resilient_buy = False

            is_weak_sell = True
            if nifty_day_move > NIFTY_LIMIT:
                if stock_day_move > (nifty_day_move * 0.4): is_weak_sell = False

            # --- SIGNAL CHECKS ---
            current_signal = None
            
            if stock_day_move >= CHANGE_THRESHOLD and is_fresh_high and is_strong and is_resilient_buy and c_close > c_open:
                current_signal = "BUY"
            elif stock_day_move <= -CHANGE_THRESHOLD and is_fresh_low and is_strong and is_weak_sell and c_close < c_open:
                current_signal = "SELL"

            # Avoid double notifications for same stock today
            if current_signal and notified_stocks.get(s) != current_signal:
                sl = round(c_close * (1 - SL_PCT/100 if current_signal == "BUY" else 1 + SL_PCT/100), 2)
                tp = round(c_close * (1 + TP_PCT/100 if current_signal == "BUY" else 1 - TP_PCT/100), 2)
                
                emoji = "🟢" if current_signal == "BUY" else "🔴"
                msg = f"{emoji} *{current_signal} SIGNAL*: {s}\nPrice: {c_close}\nMove: {stock_day_move:.2f}%\n🛡 SL: {sl}\n🎯 TP: {tp}"
                
                send_telegram(msg)
                notified_stocks[s] = current_signal

            time.sleep(0.05)
        except: continue

# --- MAIN LOOP ---
while True:
    now = datetime.datetime.now()
    if now.hour == 15 and now.minute >= 31:
        break
    
    # Run scan every 5 minutes at the 5th second of the candle
    if now.minute % 5 == 0 and now.second == 5:
        scan()
        time.sleep(10)
    time.sleep(1)

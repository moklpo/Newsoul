import fyers_apiv3.fyersModel as fyersModel
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

# --- CONFIGURATION ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def get_access_token():
    full_url = args.url
    if not full_url: return None
    try:
        match = re.search(r'auth_code=([^&]+)', full_url)
        if match:
            auth_code = match.group(1)
            session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
            session.set_token(auth_code)
            return session.generate_token().get("access_token")
    except Exception as e:
        print(f"Login Error: {e}")
    return None

token = get_access_token()
if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("✅ LOGIN SUCCESS")
    send_telegram("🚀 *Resilience Bot Live:* Scanning 200 Stocks (1.2% Logic)...")
else:
    sys.exit("🔴 Login Failed")

# --- STOCKS LIST ---
stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [f"NSE:{s.strip()}-EQ" for s in stocks_list.split(",")]

def scan():
    today = datetime.date.today().strftime('%Y-%m-%d')
    # Nifty 50 Data for Resilience Check
    n_data = fyers.history({"symbol":"NSE:NIFTY50-INDEX","resolution":"5","date_format":"1","range_from":today,"range_to":today})
    if n_data['s'] != 'ok': return
    df_nifty = pd.DataFrame(n_data['candles'], columns=['time','open','high','low','close','vol'])
    nifty_open = df_nifty.iloc[0]['open']
    nifty_close = df_nifty.iloc[-1]['close']
    nifty_move = ((nifty_close - nifty_open) / nifty_open) * 100

    for s in stocks:
        try:
            h5 = fyers.history({"symbol":s,"resolution":"5","date_format":"1","range_from":today,"range_to":today})
            if h5['s'] == 'ok' and len(h5['candles']) > 15:
                df = pd.DataFrame(h5['candles'], columns=['time','open','high','low','close','volume'])
                
                m_open = df.iloc[0]['open'] # 9:15 Open
                c_close = df.iloc[-1]['close']
                c_high = df.iloc[-1]['high']
                c_low = df.iloc[-1]['low']
                c_open = df.iloc[-1]['open']
                
                # --- LOGIC 1: 1.2% MOVE ---
                change_pct = ((c_close - m_open) / m_open) * 100
                
                # --- LOGIC 2: FRESH HIGH (15 CANDLES) ---
                is_fresh_high = c_close > df.iloc[-16:-1]['high'].max()
                is_fresh_low = c_close < df.iloc[-16:-1]['low'].min()
                
                # --- LOGIC 3: NIFTY RESILIENCE ---
                is_resilient_buy = True
                if nifty_move < -0.15:
                    if change_pct < (nifty_move * 0.4): is_resilient_buy = False
                
                is_weak_sell = True
                if nifty_move > 0.15:
                    if change_pct > (nifty_move * 0.4): is_weak_sell = False

                # --- LOGIC 4: CANDLE STRENGTH (60% BODY) ---
                body = abs(c_close - c_open)
                rng = c_high - c_low
                is_strong = rng > 0 and (body/rng) >= 0.6

                # --- TRIGGER CHECK ---
                if change_pct >= 1.2 and is_fresh_high and is_strong and is_resilient_buy:
                    msg = f"🟢 *BUY ALERT* : {s}\nPrice: {c_close}\nChange: {change_pct:.2f}%\nSL: {c_close*0.995:.2f} (0.5%)\nTarget: {c_close*1.01:.2f} (1%)"
                    send_telegram(msg)
                    time.sleep(1) # Delay to avoid spam

                elif change_pct <= -1.2 and is_fresh_low and is_strong and is_weak_sell:
                    msg = f"🔴 *SELL ALERT* : {s}\nPrice: {c_close}\nChange: {change_pct:.2f}%\nSL: {c_close*1.005:.2f} (0.5%)\nTarget: {c_close*0.99:.2f} (1%)"
                    send_telegram(msg)
                    time.sleep(1)
            time.sleep(0.02)
        except: continue

# --- LOOP ---
while True:
    now = datetime.datetime.now()
    # Entry Window: 9:25 AM to 11:00 AM
    if (now.hour == 9 and now.minute >= 25) or (now.hour == 10):
        scan()
        time.sleep(60) # Scan every 1 minute
    elif now.hour >= 11:
        print("Market window over. Bot sleeping.")
        time.sleep(300)

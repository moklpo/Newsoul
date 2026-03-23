import fyers_apiv3.fyersModel as fyersModel
import pandas as pd
import datetime
import time
import requests
import re
import argparse
import sys

# --- CONFIGURATION ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

# --- INPUT HANDLING FOR GITHUB ---
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Fyers Redirect URL from GitHub Input")
args = parser.parse_args()

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def get_access_token():
    full_url = args.url
    if not full_url: return None
    try:
        match = re.search(r'auth_code=([^&]+)', full_url)
        if match:
            auth_code = match.group(1)
            session = fyersModel.SessionModel(
                client_id=APP_ID, secret_key=SECRET_ID, 
                redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code"
            )
            session.set_token(auth_code)
            return session.generate_token().get("access_token")
    except Exception as e:
        print(f"❌ Login Error: {e}")
    return None

# --- INITIALIZE ---
token = get_access_token()
if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("✅ LOGIN SUCCESSFUL")
    send_telegram("🚀 *Fast-Track Resilience Bot:* Online (No Lookback Filter)...")
else:
    sys.exit("🔴 Login Failed.")

# --- STOCKS LIST ---
stocks_raw = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [f"NSE:{s.strip()}-EQ" for s in stocks_raw.split(",")]

def scan():
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    # 1. Nifty Performance Check
    n_res = fyers.history({"symbol":"NSE:NIFTY50-INDEX","resolution":"5","date_format":"1","range_from":today,"range_to":today})
    if n_res['s'] != 'ok' or not n_res['candles']: return
    n_df = pd.DataFrame(n_res['candles'], columns=['t','o','h','l','c','v'])
    n_open = n_df.iloc[0]['o']
    n_curr = n_df.iloc[-1]['c']
    nifty_move = ((n_curr - n_open) / n_open) * 100

    # 2. Loop Stocks
    for s in stocks:
        try:
            h5 = fyers.history({"symbol":s, "resolution":"5", "date_format":"1", "range_from":today, "range_to":today})
            if h5['s'] == 'ok' and len(h5['candles']) > 0:
                df = pd.DataFrame(h5['candles'], columns=['t','o','h','l','c','v'])
                
                # 9:15 Open
                m_open = df.iloc[0]['o']
                
                # Current completed candle
                curr = df.iloc[-1]
                c_o, c_h, c_l, c_c = curr['o'], curr['h'], curr['l'], curr['c']
                
                # Move from Morning
                change_pct = ((c_c - m_open) / m_open) * 100
                
                # Candle Strength (60% Body)
                body, rng = abs(c_c - c_o), c_h - c_l
                is_strong = rng > 0 and (body/rng) >= 0.6
                
                # Resilience Check
                is_resilient_buy = (change_pct >= (nifty_move * 0.4)) if nifty_move < -0.15 else True
                is_weak_sell = (change_pct <= (nifty_move * 0.4)) if nifty_move > 0.15 else True
                
                # TRIGGERS
                if change_pct >= 1.2 and is_strong and is_resilient_buy:
                    send_telegram(f"🟢 *BUY*: {s}\nPrice: {c_c}\nMove: {change_pct:.2f}%\nNifty: {nifty_move:.2f}%")
                elif change_pct <= -1.2 and is_strong and is_weak_sell:
                    send_telegram(f"🔴 *SELL*: {s}\nPrice: {c_c}\nMove: {change_pct:.2f}%\nNifty: {nifty_move:.2f}%")
            
            time.sleep(0.01) # API protection
        except: continue

# --- MAIN LOOP ---
while True:
    now = datetime.datetime.now()
    if (now.hour == 9 and now.minute >= 25) or (now.hour == 10):
        scan()
        time.sleep(60)
    elif now.hour >= 11:
        print("Scanning window closed.")
        break
    time.sleep(1)

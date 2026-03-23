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

parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Fyers Redirect URL")
args = parser.parse_args()

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_access_token():
    if not args.url: return None
    try:
        match = re.search(r'auth_code=([^&]+)', args.url)
        if match:
            session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
            session.set_token(match.group(1))
            return session.generate_token().get("access_token")
    except: return None

token = get_access_token()
if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    send_telegram("🚀 *Bot Live:* Scanning Started at 9:25 AM...")
else:
    sys.exit("🔴 Login Failed.")

stocks_raw = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [f"NSE:{s.strip()}-EQ" for s in stocks_raw.split(",")]

def scan():
    today = datetime.date.today().strftime('%Y-%m-%d')
    n_q = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX"})
    if n_q['s'] != 'ok': return
    nifty_curr = n_q['d'][0]['v']['lp']
    nifty_open = n_q['d'][0]['v']['open_price']
    nifty_move = ((nifty_curr - nifty_open) / nifty_open) * 100

    near_miss_count = 0 # Debug counter

    for i in range(0, len(stocks), 50):
        batch = ",".join(stocks[i:i+50])
        q_resp = fyers.quotes({"symbols": batch})
        
        if q_resp['s'] == 'ok':
            for stock_data in q_resp['d']:
                v = stock_data['v']
                sym = stock_data['n']
                curr_p = v['lp']
                m_open = v['open_price']
                change_pct = ((curr_p - m_open) / m_open) * 100
                
                # Agar stock 1% ke uupar hai toh check karega
                if abs(change_pct) >= 1.0:
                    near_miss_count += 1
                    h = fyers.history({"symbol":sym, "resolution":"5", "date_format":"1", "range_from":today, "range_to":today})
                    if h['s'] == 'ok' and len(h['candles']) > 0:
                        last_c = h['candles'][-1]
                        c_o, c_h, c_l, c_c = last_c[1], last_c[2], last_c[3], last_c[4]
                        
                        body, rng = abs(c_c - c_o), c_h - c_l
                        # Condition Relaxed to 50% Body instead of 60%
                        is_strong = (body/rng) >= 0.5 if rng > 0 else False
                        
                        is_res_buy = (change_pct >= (nifty_move * 0.4)) if nifty_move < -0.15 else True
                        is_weak_sell = (change_pct <= (nifty_move * 0.4)) if nifty_move > 0.15 else True

                        if change_pct >= 1.2 and is_strong and is_res_buy:
                            send_telegram(f"🟢 *BUY*: {sym}\nPrice: {curr_p}\nMove: {change_pct:.2f}%\nNifty: {nifty_move:.2f}%")
                        elif change_pct <= -1.2 and is_strong and is_weak_sell:
                            send_telegram(f"🔴 *SELL*: {sym}\nPrice: {curr_p}\nMove: {change_pct:.2f}%\nNifty: {nifty_move:.2f}%")
        time.sleep(0.5)
    
    # Har scan ke baad console pe update dega
    print(f"Scan Finished. Nifty: {nifty_move:.2f}%. Interesting Stocks found: {near_miss_count}")

while True:
    now = datetime.datetime.now()
    if (now.hour == 9 and now.minute >= 25) or (now.hour == 10):
        scan()
        time.sleep(60) # Har minute scan karega
    elif now.hour >= 11: break
    time.sleep(1)

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

# --- CONFIGURATION ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

def get_access_token():
    full_url = args.url
    if not full_url:
        print("❌ Error: No URL provided from GitHub Actions!")
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
        else:
            print("❌ Invalid URL: auth_code not found.")
            return None
    except Exception as e:
        print(f"❌ Login Error: {e}")
        return None

# --- MAIN ENGINE ---
token = get_access_token()

if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("✅ LOGIN SUCCESSFUL! Bot is live on GitHub.")
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": "🚀 *Bot Online:* Scanning with +2%/-2% Directional Filter...", "parse_mode": "Markdown"})
else:
    sys.exit("🔴 Login Failed. Check URL/Credentials.")

# --- STOCKS LIST ---
stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [s.strip() for s in stocks_list.split(",")]

def scan():
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    
    for s in stocks:
        try:
            symbol = f"NSE:{s}-EQ"
            h5 = fyers.history({"symbol":symbol,"resolution":"5","date_format":"1","range_from":start_date,"range_to":today,"cont_flag":"1"})
            hd = fyers.history({"symbol":symbol,"resolution":"D","date_format":"1","range_from":start_date,"range_to":today,"cont_flag":"1"})

            if h5['s'] == 'ok' and hd['s'] == 'ok':
                df5 = pd.DataFrame(h5['candles'], columns=['time','open','high','low','close','volume'])
                dfd = pd.DataFrame(hd['candles'], columns=['time','open','high','low','close','volume'])
                
                day_open = dfd.iloc[-1]['open']
                curr_price = df5.iloc[-2]['close']
                
                # change_pct: Positive (+) means up from open, Negative (-) means down from open
                change_pct = ((curr_price - day_open) / day_open) * 100
                
              # --- Pivot Calc (Standard Floor Pivots) ---
prev = dfd.iloc[-2]
ph, pl, pc = prev['high'], prev['low'], prev['close']
p = (ph + pl + pc) / 3

# Sabhi R1-R5 aur S1-S5 levels add kar diye hain
levels = {
    "P": p,
    "R1": (2*p)-pl, "R2": p+(ph-pl), "R3": ph+2*(p-pl), "R4": ph+3*(p-pl), "R5": ph+4*(p-pl),
    "S1": (2*p)-ph, "S2": p-(ph-pl), "S3": pl-2*(ph-p), "S4": pl-3*(ph-p), "S5": pl-4*(ph-p)
}
                
                c_open, c_high, c_low, c_close = df5.iloc[-2]['open'], df5.iloc[-2]['high'], df5.iloc[-2]['low'], df5.iloc[-2]['close']
                body = abs(c_close - c_open)
                rng = c_high - c_low
                
                if rng > 0 and (body/rng) >= 0.6:
                    # ✅ BUY: If Stock is Up > 2% AND Candle is Bullish AND level cross
                    if change_pct >= 2.0 and c_close > c_open:
                        for name, val in levels.items():
                            if c_low <= val and c_close > val:
                                msg = f"🟢 *BULLISH BUY*: {s}\nPrice: {c_close}\nLevel: {name}\nChange: +{change_pct:.2f}%"
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                              json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                                break
                    
                    # ✅ SELL: If Stock is Down < -2% AND Candle is Bearish AND level cross
                    elif change_pct <= -2.0 and c_close < c_open:
                        for name, val in levels.items():
                            if c_high >= val and c_close < val:
                                msg = f"🔴 *BEARISH SELL*: {s}\nPrice: {c_close}\nLevel: {name}\nChange: {change_pct:.2f}%"
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                              json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                                break
            time.sleep(0.04)
        except: continue

# --- MAIN LOOP ---
while True:
    now = datetime.datetime.now()
    if now.hour == 15 and now.minute >= 31:
        break
        
    if now.minute % 5 == 0 and now.second == 5:
        scan()
        time.sleep(10)
    time.sleep(1)


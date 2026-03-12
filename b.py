from fyers_apiv3 import fyersModel
import pandas as pd
import datetime
import time
import requests
import re

# --- FIXED CONFIG ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

def get_access_token():
    print("\n" + "="*50)
    print("🚀 FYERS BOT LOGIN HELPER")
    print("="*50)
    print(f"1. Is link ko browser mein kholein:\nhttps://api-t1.fyers.in/api/v3/generate-authcode?client_id={APP_ID}&redirect_uri={REDIRECT_URL}&response_type=code&state=None")
    print("-" * 50)
    
    full_url = input("2. Login ke baad Google ka poora URL yahan Paste karein aur Enter dabayein:\n> ").strip()
    
    # URL se Auth Code nikalne ka automatic tarika
    try:
        match = re.search(r'auth_code=([^&]+)', full_url)
        if match:
            auth_code = match.group(1)
        else:
            print("❌ URL mein auth_code nahi mila! Kya aapne sahi URL copy kiya?")
            return None

        session = fyersModel.SessionModel(
            client_id=APP_ID, secret_key=SECRET_ID, 
            redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code"
        )
        session.set_token(auth_code)
        response = session.generate_token()
        
        if "access_token" in response:
            return response["access_token"]
        else:
            print(f"❌ Login Failed: {response}")
            return None
    except Exception as e:
        print(f"❌ Error during login: {e}")
        return None

# --- MAIN ENGINE ---
token = get_access_token()

if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("\n✅ LOGIN SUCCESSFUL! Bot is now scanning with 2% Movement Filter.")
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": "🚀 *Bot Online:* Login Successful! Scanning started.", "parse_mode": "Markdown"})
else:
    print("🔴 Bot band ho gaya kyunki login nahi ho paya.")
    exit()

# --- SCANNING LOGIC ---
stocks_list = "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
stocks = [s.strip() for s in stocks_list.split(",")]

def scan():
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    print(f"🔍 [{datetime.datetime.now().strftime('%H:%M:%S')}] Scanning 200+ Stocks...")
    
    for s in stocks:
        try:
            symbol = f"NSE:{s}-EQ"
            h5 = fyers.history({"symbol":symbol,"resolution":"5","date_format":"1","range_from":start_date,"range_to":today,"cont_flag":"1"})
            hd = fyers.history({"symbol":symbol,"resolution":"D","date_format":"1","range_from":start_date,"range_to":today,"cont_flag":"1"})

            if h5['s'] == 'ok' and hd['s'] == 'ok':
                df5 = pd.DataFrame(h5['candles'], columns=['time','open','high','low','close','volume'])
                dfd = pd.DataFrame(hd['candles'], columns=['time','open','high','low','close','volume'])
                
                # Daily Info
                day_open = dfd.iloc[-1]['open']
                curr_price = df5.iloc[-2]['close']
                move_pct = abs((curr_price - day_open) / day_open) * 100
                
                # Pivot Calc
                prev = dfd.iloc[-2]
                p = (prev['high'] + prev['low'] + prev['close']) / 3
                levels = {"P":p, "R1":(2*p)-prev['low'], "S1":(2*p)-prev['high']}
                
                # Filter: Movement >= 2%
                if move_pct >= 2.0:
                    c_open, c_high, c_low, c_close = df5.iloc[-2]['open'], df5.iloc[-2]['high'], df5.iloc[-2]['low'], df5.iloc[-2]['close']
                    body = abs(c_close - c_open)
                    rng = c_high - c_low
                    
                    if rng > 0 and (body/rng) >= 0.6:
                        for name, val in levels.items():
                            if c_close > c_open and c_low <= val and c_close > val:
                                msg = f"🟢 *BUY*: {s}\nPrice: {c_close}\nLevel: {name}\nMove: {move_pct:.2f}%"
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                            elif c_close < c_open and c_high >= val and c_close < val:
                                msg = f"🔴 *SELL*: {s}\nPrice: {c_close}\nLevel: {name}\nMove: {move_pct:.2f}%"
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            time.sleep(0.04)
        except: continue

# Loop
while True:
    now = datetime.datetime.now()
    if now.minute % 5 == 0 and now.second == 5:
        scan()
        time.sleep(10)
    time.sleep(1)

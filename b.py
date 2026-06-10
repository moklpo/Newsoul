from fyers_apiv3 import fyersModel
import pandas as pd
import numpy as np
import datetime
import time
import requests
import re
import argparse
import sys
import os

# --- INPUT HANDLING FOR GITHUB ---
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Fyers Redirect URL from GitHub Input")
args = parser.parse_args()

# ============================================================
#   CONFIGURATION — put real values in env vars or here
# ============================================================
APP_ID       = os.getenv("FYERS_APP_ID",      "ESUCFMYU9Q-100")
SECRET_ID    = os.getenv("FYERS_SECRET_ID",   "1ESVP5WA71") # regenerate this!
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw")  # regenerate this!
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1250330319")

# ============================================================
#   STRATEGY PARAMETERS
# ============================================================
# --- existing filters ---
CHANGE_THRESHOLD = 1.2      # min % day move to consider
BODY_RATIO_MIN   = 0.5      # candle body / range ratio
LOOKBACK         = 15       # candles for fresh high/low check
NIFTY_LIMIT      = 0.15     # nifty move filter
MAX_SIGNALS      = 3        # max alerts per stock per day

# --- SL / TP (ATR based now) ---
ATR_SL_MULT = 1.5           # SL = price ± ATR * 1.5
ATR_TP_MULT = 3.0           # TP = price ± ATR * 3.0  (1:2 RR)
ATR_SPIKE_MULT = 2.0        # candle range > ATR*2 = spike, skip

# --- EMA pullback ---
EMA_LEN        = 5
PULLBACK_BUFFER = 0.25

# --- NEW: Slope / angle filter (5-min candles) ---
SLOPE_PERIOD  = 6           # last 6 candles for slope calc
SLOPE_MIN     = 0.06        # min % per candle — not sideways
SLOPE_MAX     = 0.40        # max % per candle — not a spike

# --- NEW: Slow accumulation (before 10:30 AM) ---
ACCUM_MOVE_MIN = 0.8        # min % move by 10:30 AM
ACCUM_MOVE_MAX = 2.5        # max % move by 10:30 AM (controlled)
ACCUM_BODY_AVG = 0.40       # avg candle body ratio — consistent

# --- NEW: Volume surge ---
VOL_AVG_PERIOD  = 20        # rolling avg candles
VOL_SURGE_MULT  = 1.4       # current vol > avg * 1.4

# --- NEW: OI confirmation ---
OI_STRIKE_COUNT = 5         # strikes each side for OI scan
OI_MIN_SCORE_BUY  = 2       # min score out of 3 for BUY
OI_MIN_SCORE_SELL = 1       # min score out of 2 for SELL

# ============================================================
notified_stocks = {}

# ============================================================
#   INDICATORS
# ============================================================
def get_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def get_atr(df, length=14):
    high_low    = df['high'] - df['low']
    high_close  = (df['high'] - df['close'].shift()).abs()
    low_close   = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def get_slope_pct(series, period=6):
    """
    Linear regression slope over last `period` candles.
    Returns slope as % of starting price per candle.
    45-degree steady climb = 0.06 to 0.40 range.
    """
    y = series.iloc[-period:].values.astype(float)
    x = np.arange(period)
    if len(y) < period:
        return 0.0
    slope, _ = np.polyfit(x, y, 1)
    base = y[0] if y[0] != 0 else 1.0
    return (slope / base) * 100

# ============================================================
#   OI CONFIRMATION  (Fyers option chain)
# ============================================================
def get_oi_confirmation(fyers_client, raw_symbol, signal_side):
    """
    Fetch ATM option chain OI change from Fyers.
    BUY  → CE OI rising (fresh longs) + PE OI falling (put unwinding)
    SELL → PE OI rising (fresh shorts) + CE OI falling (call unwinding)
    Returns (confirmed: bool, message: str, score: int)
    """
    try:
        stock = raw_symbol.replace("NSE:", "").replace("-EQ", "")
        resp = fyers_client.optionchain({
            "symbol":      f"NSE:{stock}-EQ",
            "strikecount": OI_STRIKE_COUNT,
            "timestamp":   ""
        })

        if resp.get('s') != 'ok':
            return False, "OI N/A", 0

        # Fyers v3: optionsChain directly inside data, first entry is equity (skip it)
        full_chain = resp['data']['optionsChain']
        chain = [x for x in full_chain if x.get('option_type') in ('CE', 'PE')]

        if not chain:
            return False, "OI empty", 0

        # Find ATM strike closest to LTP
        ltp_entry = next((x for x in full_chain if x.get('option_type') == ''), None)
        ltp = ltp_entry.get('ltp', 0) if ltp_entry else 0
        strikes = sorted(set(x['strike_price'] for x in chain))
        atm_strike = min(strikes, key=lambda x: abs(x - ltp)) if ltp else strikes[len(strikes)//2]

        # ATM ± 2 strikes
        atm_idx   = strikes.index(atm_strike)
        atm_range = set(strikes[max(0, atm_idx-2): atm_idx+3])
        atm_slice = [x for x in chain if x['strike_price'] in atm_range]

        # oich = OI change field in Fyers v3
        ce_oi_chg = sum(x.get('oich', 0) or 0 for x in atm_slice if x['option_type'] == 'CE')
        pe_oi_chg = sum(x.get('oich', 0) or 0 for x in atm_slice if x['option_type'] == 'PE')

        score = 0
        detail = []

        if signal_side == "BUY":
            if ce_oi_chg > 0:
                score += 1
                detail.append("CE OI↑")          # fresh call buyers
            if pe_oi_chg < 0:
                score += 1
                detail.append("PE OI↓")          # put unwinding
            if ce_oi_chg > abs(pe_oi_chg) * 0.5:
                score += 1
                detail.append("CE dominant")
            confirmed = score >= OI_MIN_SCORE_BUY

        else:  # SELL
            if pe_oi_chg > 0:
                score += 1
                detail.append("PE OI↑")          # fresh put buyers
            if ce_oi_chg < 0:
                score += 1
                detail.append("CE OI↓")          # call unwinding
            confirmed = score >= OI_MIN_SCORE_SELL

        msg = f"OI {score}✓ ({', '.join(detail)})" if detail else f"OI {score}✓"
        return confirmed, msg, score

    except Exception as e:
        print(f"  ⚠ OI error [{raw_symbol}]: {e}")
        return False, "OI err", 0

# ============================================================
#   SLOW ACCUMULATION CHECK
# ============================================================
def is_slow_accumulation(df_today):
    """
    Before 10:30 AM: stock should have moved 0.8–2.5% steadily.
    After 10:30 AM: bypass this filter (normal momentum logic).
    Consistent candle bodies = genuine buying, not noise.
    """
    now = datetime.datetime.now()
    if now.hour > 10 or (now.hour == 10 and now.minute >= 30):
        return True  # after 10:30 AM — skip this filter

    if len(df_today) < 3:
        return False

    m_open = df_today.iloc[0]['open']
    c_price = df_today.iloc[-1]['close']
    move_pct = ((c_price - m_open) / m_open) * 100 if m_open != 0 else 0

    move_ok = ACCUM_MOVE_MIN <= move_pct <= ACCUM_MOVE_MAX

    ranges = df_today['high'] - df_today['low']
    bodies = (df_today['close'] - df_today['open']).abs()
    avg_body_ratio = (bodies / ranges.replace(0, np.nan)).mean()
    body_ok = avg_body_ratio >= ACCUM_BODY_AVG

    return move_ok and body_ok

# ============================================================
#   AUTH & TELEGRAM
# ============================================================
def get_access_token():
    if not args.url:
        return None
    try:
        match = re.search(r'auth_code=([^&]+)', args.url)
        if match:
            auth_code = match.group(1)
            session = fyersModel.SessionModel(
                client_id=APP_ID, secret_key=SECRET_ID,
                redirect_uri=REDIRECT_URL,
                response_type="code", grant_type="authorization_code"
            )
            session.set_token(auth_code)
            return session.generate_token().get("access_token")
    except Exception as e:
        print(f"Login Error: {e}")
    return None

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception as e:
        print(f"Telegram error: {e}")

# ============================================================
#   OPTION STRIKE SELECTOR
# ============================================================
def get_perfect_strike(symbol, price, side):
    if "NIFTY" in symbol and "BANK" not in symbol: step = 50
    elif "BANKNIFTY" in symbol:                    step = 100
    elif price > 1000:                             step = 10
    elif price > 500:                              step = 5
    else:                                          step = 2.5
    atm = round(price / step) * step
    return f"{int(atm + step)} CE" if side == "BUY" else f"{int(atm - step)} PE"

# ============================================================
#   DAILY RESET
# ============================================================
def maybe_reset_daily():
    now = datetime.datetime.now()
    if now.hour == 9 and 15 <= now.minute <= 16:
        if notified_stocks:
            notified_stocks.clear()
            print("✅ Daily reset done — notified_stocks cleared")

# ============================================================
#   LOGIN
# ============================================================
token = get_access_token()
if token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
    print("✅ SYSTEM LIVE: Slope + OI + Volume filters active")
    send_telegram("🚀 *Bot Online v2*: Slope + OI Confirmation + Volume Filter Active")
else:
    sys.exit("🔴 Login Failed.")

# ============================================================
#   STOCK UNIVERSE
# ============================================================
stocks_list = (
    "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,"
    "AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,"
    "AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,"
    "BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,"
    "BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,"
    "COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,"
    "DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,"
    "GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,"
    "HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,"
    "ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,"
    "INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,"
    "JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,"
    "KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,"
    "MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,"
    "MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,"
    "NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,"
    "PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,"
    "POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,"
    "RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,"
    "SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,"
    "TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,"
    "TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,"
    "UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
)
stocks = [s.strip() for s in stocks_list.split(",")]

# ============================================================
#   MAIN SCAN
# ============================================================
def scan():
    maybe_reset_daily()

    now = datetime.datetime.now()

    # Skip first 15 minutes — opening noise
    if now.hour == 9 and now.minute < 30:
        print("⏳ Waiting for market to settle (9:30 AM)...")
        return

    today      = datetime.date.today()
    start_date = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    today_str  = today.strftime('%Y-%m-%d')

    # --- Nifty regime filter ---
    try:
        n_res = fyers.history({
            "symbol": "NSE:NIFTY50-INDEX", "resolution": "5",
            "date_format": "1", "range_from": start_date, "range_to": today_str
        })
        if n_res['s'] != 'ok':
            print("Nifty data failed"); return

        df_nifty  = pd.DataFrame(n_res['candles'], columns=['time','open','high','low','close','volume'])
        df_n_today = df_nifty[pd.to_datetime(df_nifty['time'], unit='s').dt.date == today]
        if len(df_n_today) < 3:
            return

        n_m_open = df_n_today.iloc[0]['open']
        n_move   = ((df_n_today.iloc[-1]['close'] - n_m_open) / n_m_open) * 100
    except Exception as e:
        print(f"Nifty fetch error: {e}"); return

    print(f"\n🔍 Scanning {len(stocks)} stocks | Nifty move: {n_move:.2f}% | {now.strftime('%H:%M:%S')}")

    signals_found = 0

    for s in stocks:
        try:
            symbol = f"NSE:{s}-EQ"

            # --- Fetch 5-min data ---
            h5 = fyers.history({
                "symbol": symbol, "resolution": "5",
                "date_format": "1", "range_from": start_date, "range_to": today_str
            })
            if h5['s'] != 'ok':
                continue

            df = pd.DataFrame(h5['candles'], columns=['time','open','high','low','close','volume'])
            if len(df) < 30:
                continue

            df['ema5'] = get_ema(df['close'], EMA_LEN)
            df['atr']  = get_atr(df, 14)

            curr   = df.iloc[-2]   # last completed candle
            df_t   = df[pd.to_datetime(df['time'], unit='s').dt.date == today]
            if len(df_t) < 3:
                continue

            # ── Day move ──
            m_open  = df_t.iloc[0]['open']
            s_move  = ((curr['close'] - m_open) / m_open) * 100 if m_open != 0 else 0

            # ── Fresh high / low ──
            is_fresh_high = curr['close'] > df.iloc[-(LOOKBACK+2):-2]['high'].max()
            is_fresh_low  = curr['close'] < df.iloc[-(LOOKBACK+2):-2]['low'].min()

            # ── Strong candle body ──
            c_rng     = curr['high'] - curr['low']
            is_strong = c_rng > 0 and (abs(curr['close'] - curr['open']) / c_rng) >= BODY_RATIO_MIN

            # ── ATR spike filter ──
            is_not_spike = c_rng <= (curr['atr'] * ATR_SPIKE_MULT)

            # ── EMA pullback ──
            d_ema_b   = (curr['low']  - curr['ema5']) / curr['ema5'] * 100
            d_ema_s   = (curr['ema5'] - curr['high']) / curr['ema5'] * 100
            is_buy_pb = curr['low'] <= curr['ema5'] or (d_ema_b <= PULLBACK_BUFFER and curr['low'] > curr['ema5'])
            is_sell_pb= curr['high'] >= curr['ema5'] or (d_ema_s <= PULLBACK_BUFFER and curr['high'] < curr['ema5'])

            # ── Nifty regime ──
            r_buy  = not (n_move < -NIFTY_LIMIT and s_move < (n_move * 0.4))
            w_sell = not (n_move >  NIFTY_LIMIT and s_move > (n_move * 0.4))

            # ── NEW: Volume surge ──
            avg_vol      = df['volume'].rolling(VOL_AVG_PERIOD).mean().iloc[-2]
            is_vol_surge = curr['volume'] > avg_vol * VOL_SURGE_MULT

            # ── NEW: Slope / 45° angle ──
            slope         = get_slope_pct(df['close'], SLOPE_PERIOD)
            is_45_buy     = SLOPE_MIN <=  slope <= SLOPE_MAX
            is_45_sell    = SLOPE_MIN <= -slope <= SLOPE_MAX  # negative slope for sell

            # ── NEW: Slow accumulation (morning filter) ──
            accum_ok = is_slow_accumulation(df_t)

            # ── ATR-based SL and TP ──
            atr_val = curr['atr']
            buy_sl  = round(curr['close'] - atr_val * ATR_SL_MULT, 2)
            buy_tp  = round(curr['close'] + atr_val * ATR_TP_MULT, 2)
            sell_sl = round(curr['close'] + atr_val * ATR_SL_MULT, 2)
            sell_tp = round(curr['close'] - atr_val * ATR_TP_MULT, 2)

            # ── Notified tracker init ──
            if s not in notified_stocks:
                notified_stocks[s] = {'b': 0, 's': 0, 'last': 0}

            # ── SIGNAL DECISION ──
            signal = None

            buy_base = (
                s_move >= CHANGE_THRESHOLD
                and is_fresh_high
                and is_strong
                and is_not_spike
                and r_buy
                and is_buy_pb
                and curr['close'] > curr['ema5']
                and is_vol_surge      # volume confirm
                and is_45_buy         # steady slope
                and accum_ok          # morning accumulation
                and notified_stocks[s]['b'] < MAX_SIGNALS
            )

            sell_base = (
                s_move <= -CHANGE_THRESHOLD
                and is_fresh_low
                and is_strong
                and is_not_spike
                and w_sell
                and is_sell_pb
                and curr['close'] < curr['ema5']
                and is_vol_surge
                and is_45_sell
                and accum_ok
                and notified_stocks[s]['s'] < MAX_SIGNALS
            )

            if buy_base:
                signal = "BUY"
            elif sell_base:
                signal = "SELL"

            # ── OI confirmation (only if base signal fires) ──
            if signal and curr['time'] > notified_stocks[s]['last'] + 300:

                oi_confirmed, oi_msg, oi_score = get_oi_confirmation(fyers, symbol, signal)
                signal_strength = "🔥 STRONG" if oi_confirmed else "⚡ MODERATE"

                # Only send STRONG signals — or allow MODERATE too?
                # Comment out next 2 lines to allow MODERATE signals too
                if not oi_confirmed:
                    print(f"  ⚡ {s} {signal} — OI not confirmed ({oi_msg}), skipping")
                    continue

                notified_stocks[s]['last'] = curr['time']
                if signal == "BUY":
                    notified_stocks[s]['b'] += 1
                    sl, tp = buy_sl, buy_tp
                else:
                    notified_stocks[s]['s'] += 1
                    sl, tp = sell_sl, sell_tp

                rr = round(abs(tp - curr['close']) / abs(sl - curr['close']), 1) if abs(sl - curr['close']) > 0 else 0
                perfect_option = get_perfect_strike(s, curr['close'], signal)

                msg = (
                    f"{'🚀' if signal == 'BUY' else '📉'} {signal_strength} *{signal}*: `{s}`\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Price  : ₹{curr['close']}\n"
                    f"📊 Day Move: {s_move:.2f}%\n"
                    f"📐 Slope  : {slope:+.3f}% per candle\n"
                    f"📦 Volume : {curr['volume']:,.0f} ({curr['volume']/avg_vol:.1f}x avg)\n"
                    f"🔄 OI     : {oi_msg}\n"
                    f"🎯 Option : `{perfect_option}`\n"
                    f"🛡 SL     : ₹{sl}  |  🎯 TP: ₹{tp}\n"
                    f"⚖️ RR     : 1:{rr}"
                )
                send_telegram(msg)
                print(f"  ✅ Alert sent: {s} {signal} | OI: {oi_msg} | Slope: {slope:.3f}")
                signals_found += 1

            time.sleep(0.05)

        except Exception as e:
            print(f"  ⚠ Error [{s}]: {e}")
            continue

    print(f"  → Scan complete. {signals_found} signal(s) sent.")

# ============================================================
#   MAIN LOOP
# ============================================================
print("=" * 50)
print("  TRADING BOT v2 — Slope + OI + Volume")
print("=" * 50)

while True:
    now = datetime.datetime.now()

    # Stop after 3:30 PM
    if now.hour == 15 and now.minute >= 30:
        send_telegram("🔴 *Bot Offline* — Market closed (3:30 PM)")
        print("Market closed. Bot stopping.")
        break

    # Run scan every 5 minutes at :05 seconds
    if now.minute % 5 == 0 and 4 <= now.second <= 8:
        scan()
        time.sleep(15)  # prevent double-trigger in same minute

    time.sleep(1)

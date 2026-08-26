import os
import datetime

import requests
import pandas as pd
import yfinance as yf


# ============================================================
# CONFIGURAZIONE
# ============================================================

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ============================================================
# TITOLI
# ============================================================

FTSE_MIB = [
    "A2A.MI", "AMP.MI", "ARISTON.MI", "AZM.MI",
    "BAMI.MI", "BCA.MI", "BPE.MI", "BZZ.MI",
    "CPR.MI", "DIA.MI", "ENEL.MI", "ENI.MI",
    "ERG.MI", "RACE.MI", "FBK.MI", "G.MI",
    "HER.MI", "INW.MI", "ISP.MI", "LDO.MI",
    "MB.MI", "MONC.MI", "NEXI.MI", "PIR.MI",
    "PNT.MI", "PRY.MI", "REC.MI", "RWAY.MI",
    "SRG.MI", "STLAM.MI", "STMMI.MI", "TIT.MI",
    "TEN.MI", "TRN.MI", "UCG.MI", "US.MI"
]

DOW_JONES = [
    "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT",
    "CRM", "CSCO", "CVX", "DIS", "DOW", "GS",
    "HD", "HON", "IBM", "INTC", "JNJ", "JPM",
    "KO", "MCD", "MMM", "MRK", "MSFT", "NKE",
    "PG", "TRV", "UNH", "V", "VZ", "WMT"
]


# ============================================================
# FINNHUB
# ============================================================

def finnhub_get(endpoint, params=None):

    if not FINNHUB_API_KEY:
        print("ERRORE: FINNHUB_API_KEY non configurata.")
        return None

    if params is None:
        params = {}

    params["token"] = FINNHUB_API_KEY

    url = f"https://finnhub.io/api/v1/{endpoint}"

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            print(
                f"Finnhub HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )
            return None

        return response.json()

    except Exception as error:
        print(f"Errore Finnhub: {error}")
        return None


# ============================================================
# EARNINGS
# ============================================================

def get_upcoming_earnings(days_ahead=30):

    today = datetime.date.today()
    future = today + datetime.timedelta(days=days_ahead)

    data = finnhub_get(
        "calendar/earnings",
        {
            "from": today.isoformat(),
            "to": future.isoformat()
        }
    )

    if not data:
        return []

    return data.get("earningsCalendar", [])


# ============================================================
# INSIDER TRADING
# ============================================================

def check_insider_trading(ticker):

    symbol = ticker.replace(".MI", "")

    data = finnhub_get(
        "stock/insider-transactions",
        {
            "symbol": symbol
        }
    )

    if not data:
        return {
            "status": "NEUTRAL",
            "msg": None
        }

    transactions = data.get("data", [])

    buys = 0
    sells = 0
    net_shares = 0

    for item in transactions[:20]:

        try:
            change = float(
                item.get("change", 0) or 0
            )
        except Exception:
            change = 0

        if change > 0:
            buys += 1
            net_shares += change

        elif change < 0:
            sells += 1
            net_shares += change

    if buys > sells and net_shares > 0:
        return {
            "status": "BUY",
            "msg": "🟢 Insider Buying: acquisti insider superiori alle vendite"
        }

    if sells > buys and net_shares < 0:
        return {
            "status": "SELL",
            "msg": "🔴 Insider Selling: vendite insider superiori agli acquisti"
        }

    return {
        "status": "NEUTRAL",
        "msg": None
    }


# ============================================================
# SHORT INTEREST
# ============================================================

def check_short_interest(info):

    if not isinstance(info, dict):
        return {
            "high_short": False,
            "msg": None
        }

    try:

        short_percent = info.get(
            "shortPercentOfFloat"
        )

        if short_percent is None:
            return {
                "high_short": False,
                "msg": None
            }

        short_percent = float(short_percent)

        if short_percent > 0.05:

            return {
                "high_short": True,
                "msg": (
                    f"⚡ Alto Short Interest "
                    f"({short_percent * 100:.1f}%)"
                )
            }

    except Exception:
        pass

    return {
        "high_short": False,
        "msg": None
    }


# ============================================================
# CAMBI EXECUTIVE
# ============================================================

def check_executive_changes(ticker):

    symbol = ticker.replace(".MI", "")

    data = finnhub_get(
        "stock/executive",
        {
            "symbol": symbol
        }
    )

    if not data:
        return []

    executives = data.get(
        "executive",
        []
    )

    results = []

    current_year = str(
        datetime.date.today().year
    )

    for executive in executives[:10]:

        title = str(
            executive.get("title", "")
        ).upper()

        if not any(
            role in title
            for role in [
                "CEO",
                "CFO",
                "CHIEF EXECUTIVE",
                "CHIEF FINANCIAL",
                "PRESIDENT"
            ]
        ):
            continue

        since = str(
            executive.get("since", "")
        )

        if current_year in since:

            name = executive.get(
                "name",
                "N/D"
            )

            results.append(
                f"⚠️ Cambio vertici: "
                f"{name} ({executive.get('title', '')})"
            )

    return results


# ============================================================
# ANALISI
# ============================================================

def analyze_stock(
    ticker,
    release_date,
    market
):

    print(f"Analisi {ticker}...")

    try:

        stock = yf.Ticker(ticker)

        df = stock.history(
            period="6mo",
            auto_adjust=False
        )

        if df.empty or len(df) < 20:
            print(f"{ticker}: dati insufficienti.")
            return None

        try:
            info = stock.info
        except Exception:
            info = {}

        # ----------------------------------------------------
        # DATA EARNINGS
        # ----------------------------------------------------

        try:

            earnings_date = datetime.datetime.strptime(
                str(release_date),
                "%Y-%m-%d"
            ).date()

        except Exception:

            print(
                f"{ticker}: data earnings non valida."
            )

            return None

        today = datetime.date.today()

        days_left = (
            earnings_date - today
        ).days

        # ----------------------------------------------------
        # SMA20
        # ----------------------------------------------------

        df["SMA20"] = (
            df["Close"]
            .rolling(20)
            .mean()
        )

        latest = df.iloc[-1]

        close = float(
            latest["Close"]
        )

        sma20 = latest["SMA20"]

        # ----------------------------------------------------
        # VOLUME
        # ----------------------------------------------------

        volume_average = (
            df["Volume"]
            .tail(20)
            .mean()
        )

        current_volume = latest["Volume"]

        high_volume = (
            pd.notna(volume_average)
            and volume_average > 0
            and current_volume > volume_average * 1.20
        )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = 3

        reasons = []

        # TREND

        if pd.notna(sma20):

            if close > sma20 and high_volume:

                score += 1

                reasons.append(
                    "🟢 Prezzo sopra SMA20 "
                    "con volume superiore alla media"
                )

            elif close < sma20:

                score -= 1

                reasons.append(
                    "🔴 Prezzo sotto SMA20"
                )

            else:

                reasons.append(
                    "🟡 Prezzo sopra SMA20 "
                    "senza volume anomalo"
                )

        # INSIDER

        insider = check_insider_trading(
            ticker
        )

        if insider["msg"]:

            reasons.append(
                insider["msg"]
            )

            if insider["status"] == "BUY":
                score += 1

            elif insider["status"] == "SELL":
                score -= 1

        # SHORT

        short_data = check_short_interest(
            info
        )

        if short_data["msg"]:
            reasons.append(
                short_data["msg"]
            )

        # EXECUTIVE

        executive_changes = (
            check_executive_changes(ticker)
        )

        if executive_changes:

            reasons.extend(
                executive_changes
            )

            if days_left <= 15:

                reasons.append(
                    "⚠️ Cambio vertici vicino "
                    "alla trimestrale"
                )

        # LIMIT SCORE

        score = max(
            1,
            min(5, score)
        )

        # ----------------------------------------------------
        # BIAS
        # ----------------------------------------------------

        if score >= 4:

            bias = "🚀 SEGNALE RIALZISTA"

            advice = (
                "💡 *Segnale:* struttura favorevole "
                "in prossimità della trimestrale."
            )

        elif score <= 2:

            bias = "🔻 SEGNALE RIBASSISTA"

            advice = (
                "💡 *Segnale:* struttura debole "
                "in prossimità della trimestrale."
            )

        else:

            bias = "⚖️ NEUTRO"

            advice = (
                "💡 *Segnale:* nessun vantaggio "
                "operativo evidente."
            )

        return {
            "symbol": ticker,
            "name": info.get(
                "shortName",
                ticker
            ),
            "market": market,
            "days_left": days_left,
            "release_date": release_date,
            "score": score,
            "bias": bias,
            "reasons": reasons,
            "advice": advice
        }

    except Exception as error:

        print(
            f"Errore {ticker}: {error}"
        )

        return None


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN mancante.")
        return False

    if not TELEGRAM_CHAT_ID:
        print("TELEGRAM_CHAT_ID mancante.")
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    success = True

    for chat_id in TELEGRAM_CHAT_ID.split(","):

        chat_id = chat_id.strip()

        if not chat_id:
            continue

        try:

            response = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                },
                timeout=15
            )

            if response.status_code == 200:

                print(
                    f"Telegram inviato a {chat_id}"
                )

            else:

                success = False

                print(
                    f"Errore Telegram "
                    f"{response.status_code}: "
                    f"{response.text[:300]}"
                )

        except Exception as error:

            success = False

            print(
                f"Errore Telegram: {error}"
            )

    return success


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("AUTOMATIC TRADING SIGNALS")
    print("EARNINGS & CATALYST SCANNER")
    print("=" * 60)

    if not FINNHUB_API_KEY:

        print(
            "ERRORE: FINNHUB_API_KEY non configurata."
        )

        return

    earnings = get_upcoming_earnings(
        days_ahead=30
    )

    if not earnings:

        print(
            "Nessun dato earnings disponibile."
        )

        return

    earnings_dict = {}

    for event in earnings:

        symbol = event.get("symbol")
        date = event.get("date")

        if symbol and date:

            earnings_dict[
                symbol.upper()
            ] = date

    targets = []

    # --------------------------------------------------------
    # FTSE MIB
    # --------------------------------------------------------

    for ticker in FTSE_MIB:

        clean_symbol = (
            ticker
            .replace(".MI", "")
            .upper()
        )

        if clean_symbol in earnings_dict:

            targets.append(
                (
                    ticker,
                    earnings_dict[clean_symbol],
                    "🇮🇹 FTSE MIB"
                )
            )

    # --------------------------------------------------------
    # DOW JONES
    # --------------------------------------------------------

    for ticker in DOW_JONES:

        if ticker.upper() in earnings_dict:

            targets.append(
                (
                    ticker,
                    earnings_dict[ticker.upper()],
                    "🇺🇸 DOW JONES"
                )
            )

    print(
        f"Titoli trovati: {len(targets)}"
    )

    signals = []

    for ticker, date, market in targets:

        result = analyze_stock(
            ticker,
            date,
            market
        )

        if result:

            if (
                result["score"] >= 4
                or result["score"] <= 2
            ):

                signals.append(result)

    # --------------------------------------------------------
    # NESSUN SEGNALE
    # --------------------------------------------------------

    if not signals:

        print(
            "Nessun segnale ad alta priorità."
        )

        return

    # --------------------------------------------------------
    # ORDINA
    # --------------------------------------------------------

    signals.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    report = (
        "🚨 *AUTOMATIC TRADING SIGNALS*\n"
        "*BILANCI & CATALIZZATORI*\n\n"
    )

    report += (
        f"📊 Segnali trovati: "
        f"*{len(signals)}*\n\n"
    )

    for signal in signals:

        stars = (
            "⭐" * signal["score"]
        )

        report += (
            f"{signal['market']}\n"
            f"📅 Trimestrale: "
            f"*{signal['release_date']}* "
            f"(tra {signal['days_left']} gg)\n"
            f"🏢 *{signal['name']}* "
            f"(`{signal['symbol']}`)\n"
            f"Rating: {stars} "
            f"({signal['score']}/5)\n"
            f"*{signal['bias']}*\n"
            f"Motivi:\n"
        )

        for reason in signal["reasons"]:

            report += (
                f"• {reason}\n"
            )

        report += (
            f"{signal['advice']}\n\n"
        )

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    if (
        TELEGRAM_BOT_TOKEN
        and TELEGRAM_CHAT_ID
    ):

        send_telegram(report)

    else:

        print(
            "Telegram non configurato."
        )

        print(report)


if __name__ == "__main__":
    main()

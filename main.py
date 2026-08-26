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
# FTSE MIB
# ============================================================

FTSE_MIB = [
    "A2A.MI",
    "AMP.MI",
    "ARISTON.MI",
    "AZM.MI",
    "BAMI.MI",
    "BCA.MI",
    "BPE.MI",
    "BZZ.MI",
    "CPR.MI",
    "DIA.MI",
    "ENEL.MI",
    "ENI.MI",
    "ERG.MI",
    "RACE.MI",
    "FBK.MI",
    "G.MI",
    "HER.MI",
    "INW.MI",
    "ISP.MI",
    "LDO.MI",
    "MB.MI",
    "MONC.MI",
    "NEXI.MI",
    "PIR.MI",
    "PNT.MI",
    "PRY.MI",
    "REC.MI",
    "RWAY.MI",
    "SRG.MI",
    "STLAM.MI",
    "STMMI.MI",
    "TIT.MI",
    "TEN.MI",
    "TRN.MI",
    "UCG.MI",
    "US.MI",
]


# ============================================================
# DOW JONES
# ============================================================

DOW_JONES = [
    "AAPL",
    "AMGN",
    "AMZN",
    "AXP",
    "BA",
    "CAT",
    "CRM",
    "CSCO",
    "CVX",
    "DIS",
    "DOW",
    "GS",
    "HD",
    "HON",
    "IBM",
    "INTC",
    "JNJ",
    "JPM",
    "KO",
    "MCD",
    "MMM",
    "MRK",
    "MSFT",
    "NKE",
    "PG",
    "TRV",
    "UNH",
    "V",
    "VZ",
    "WMT",
]


# ============================================================
# FUNZIONE GENERALE FINNHUB
# ============================================================

def finnhub_get(endpoint, params=None):

    if not FINNHUB_API_KEY:
        print("❌ ERRORE: FINNHUB_API_KEY non configurata.")
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
                f"❌ Finnhub HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

            return None

        return response.json()

    except requests.exceptions.Timeout:

        print(
            f"❌ Timeout Finnhub: {endpoint}"
        )

        return None

    except requests.exceptions.RequestException as error:

        print(
            f"❌ Errore Finnhub: {error}"
        )

        return None

    except ValueError:

        print(
            "❌ Risposta JSON Finnhub non valida."
        )

        return None


# ============================================================
# CALENDARIO TRIMESTRALI
# ============================================================

def get_upcoming_earnings(days_ahead=30):

    today = datetime.date.today()

    future = (
        today
        + datetime.timedelta(days=days_ahead)
    )

    print(
        f"📅 Ricerca trimestrali dal "
        f"{today} al {future}"
    )

    data = finnhub_get(
        "calendar/earnings",
        {
            "from": today.isoformat(),
            "to": future.isoformat()
        }
    )

    if not data:

        print(
            "⚠️ Nessun dato earnings ricevuto."
        )

        return []

    earnings = data.get(
        "earningsCalendar",
        []
    )

    print(
        f"📊 Trimestrali trovate: "
        f"{len(earnings)}"
    )

    return earnings


# ============================================================
# INSIDER TRADING
# ============================================================

def check_insider_trading(ticker):

    clean_ticker = ticker.replace(
        ".MI",
        ""
    )

    data = finnhub_get(
        "stock/insider-transactions",
        {
            "symbol": clean_ticker
        }
    )

    if not data:

        return {
            "status": "NEUTRAL",
            "msg": None
        }

    transactions = data.get(
        "data",
        []
    )

    net_shares = 0
    buys = 0
    sells = 0

    for item in transactions[:20]:

        try:

            change = float(
                item.get(
                    "change",
                    0
                ) or 0
            )

        except Exception:

            change = 0

        if change > 0:

            net_shares += change
            buys += 1

        elif change < 0:

            net_shares += change
            sells += 1

    if (
        buys > sells
        and net_shares > 0
    ):

        return {
            "status": "BUY",
            "msg": (
                "🟢 Insider Buying: "
                "acquisti insider superiori alle vendite"
            )
        }

    if (
        sells > buys
        and net_shares < 0
    ):

        return {
            "status": "SELL",
            "msg": (
                "🔴 Insider Selling: "
                "vendite insider superiori agli acquisti"
            )
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

        short_percent = float(
            short_percent
        )

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
# CAMBI NEI VERTICI
# ============================================================

def check_executive_changes(ticker):

    clean_ticker = ticker.replace(
        ".MI",
        ""
    )

    data = finnhub_get(
        "stock/executive",
        {
            "symbol": clean_ticker
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
            executive.get(
                "title",
                ""
            )
        ).upper()

        important_role = any(
            role in title
            for role in [
                "CEO",
                "CFO",
                "CHIEF EXECUTIVE",
                "CHIEF FINANCIAL",
                "PRESIDENT"
            ]
        )

        if not important_role:
            continue

        since = str(
            executive.get(
                "since",
                ""
            )
        )

        if current_year in since:

            name = executive.get(
                "name",
                "N/D"
            )

            results.append(
                f"⚠️ Cambio vertici: "
                f"{name} "
                f"({executive.get('title', '')})"
            )

    return results


# ============================================================
# ANALISI DEL TITOLO
# ============================================================

def analyze_stock(
    ticker,
    release_date,
    market
):

    print(
        f"\n🔎 Analisi {ticker}..."
    )

    try:

        stock = yf.Ticker(
            ticker
        )

        df = stock.history(
            period="6mo",
            auto_adjust=False
        )

        if df.empty:

            print(
                f"⚠️ {ticker}: "
                "nessun dato Yahoo Finance."
            )

            return None

        if len(df) < 20:

            print(
                f"⚠️ {ticker}: "
                "dati insufficienti."
            )

            return None

        # ----------------------------------------------------
        # INFORMAZIONI TITOLO
        # ----------------------------------------------------

        try:

            info = stock.info

        except Exception:

            info = {}

        if not isinstance(
            info,
            dict
        ):

            info = {}

        # ----------------------------------------------------
        # DATA TRIMESTRALE
        # ----------------------------------------------------

        try:

            earnings_date = (
                datetime.datetime.strptime(
                    str(release_date),
                    "%Y-%m-%d"
                ).date()
            )

        except Exception:

            print(
                f"⚠️ {ticker}: "
                "data earnings non valida."
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
            .rolling(
                window=20
            )
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

        current_volume = (
            latest["Volume"]
        )

        high_volume = False

        if (
            pd.notna(volume_average)
            and volume_average > 0
        ):

            high_volume = (
                current_volume
                > volume_average * 1.20
            )

        # ----------------------------------------------------
        # SCORE INIZIALE
        # ----------------------------------------------------

        score = 3

        reasons = []

        # ----------------------------------------------------
        # ANALISI TREND
        # ----------------------------------------------------

        if pd.notna(sma20):

            if (
                close > sma20
                and high_volume
            ):

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

        # ----------------------------------------------------
        # INSIDER
        # ----------------------------------------------------

        insider_data = (
            check_insider_trading(
                ticker
            )
        )

        if insider_data["msg"]:

            reasons.append(
                insider_data["msg"]
            )

            if (
                insider_data["status"]
                == "BUY"
            ):

                score += 1

            elif (
                insider_data["status"]
                == "SELL"
            ):

                score -= 1

        # ----------------------------------------------------
        # SHORT INTEREST
        # ----------------------------------------------------

        short_data = (
            check_short_interest(
                info
            )
        )

        if short_data["msg"]:

            reasons.append(
                short_data["msg"]
            )

        # ----------------------------------------------------
        # CAMBI VERTICI
        # ----------------------------------------------------

        executive_changes = (
            check_executive_changes(
                ticker
            )
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

        # ----------------------------------------------------
        # LIMITAZIONE SCORE
        # ----------------------------------------------------

        score = max(
            1,
            min(
                5,
                score
            )
        )

        # ----------------------------------------------------
        # SEGNALE
        # ----------------------------------------------------

        if score >= 4:

            bias = (
                "🚀 SEGNALE RIALZISTA"
            )

            advice = (
                "💡 *Segnale:* struttura favorevole "
                "in prossimità della trimestrale."
            )

        elif score <= 2:

            bias = (
                "🔻 SEGNALE RIBASSISTA"
            )

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
            f"❌ Errore analizzando "
            f"{ticker}: {error}"
        )

        return None


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    print("\n" + "=" * 60)
    print("TELEGRAM")
    print("=" * 60)

    if not TELEGRAM_BOT_TOKEN:

        print(
            "❌ TELEGRAM_BOT_TOKEN NON TROVATO"
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "❌ TELEGRAM_CHAT_ID NON TROVATO"
        )

        return False

    print(
        "✅ TELEGRAM_BOT_TOKEN trovato"
    )

    print(
        "✅ TELEGRAM_CHAT_ID trovato"
    )

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    success = True

    chat_ids = (
        TELEGRAM_CHAT_ID.split(",")
    )

    for chat_id in chat_ids:

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

            print(
                f"Telegram HTTP status: "
                f"{response.status_code}"
            )

            if response.status_code == 200:

                print(
                    "✅ MESSAGGIO TELEGRAM INVIATO"
                )

            else:

                success = False

                print(
                    f"❌ ERRORE TELEGRAM: "
                    f"{response.text[:500]}"
                )

        except Exception as error:

            success = False

            print(
                f"❌ ERRORE CONNESSIONE TELEGRAM: "
                f"{error}"
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

    today = datetime.date.today()

    print(
        f"📅 Data scansione: "
        f"{today.strftime('%d/%m/%Y')}"
    )

    # --------------------------------------------------------
    # CONTROLLO FINNHUB
    # --------------------------------------------------------

    if not FINNHUB_API_KEY:

        print(
            "❌ FINNHUB_API_KEY non configurata."
        )

        return

    # --------------------------------------------------------
    # EARNINGS
    # --------------------------------------------------------

    upcoming_events = (
        get_upcoming_earnings(
            days_ahead=30
        )
    )

    # Se Finnhub non restituisce dati,
    # inviamo comunque una notifica.

    if not upcoming_events:

        report = (
            "🟢 *SCANSIONE BORSA COMPLETATA*\n\n"
            f"📅 {today.strftime('%d/%m/%Y')}\n\n"
            "📊 Per oggi non abbiamo titoli da proporti.\n\n"
            "⚠️ Il calendario delle trimestrali "
            "non ha restituito titoli disponibili."
        )

        print(report)

        send_telegram(report)

        return

    # --------------------------------------------------------
    # CREAZIONE DIZIONARIO EARNINGS
    # --------------------------------------------------------

    upcoming_dict = {}

    for item in upcoming_events:

        symbol = item.get(
            "symbol"
        )

        date = item.get(
            "date"
        )

        if symbol and date:

            upcoming_dict[
                symbol.upper()
            ] = date

    # --------------------------------------------------------
    # CREAZIONE TARGET
    # --------------------------------------------------------

    targets = []

    # FTSE MIB

    for ticker in FTSE_MIB:

        clean_symbol = (
            ticker
            .replace(
                ".MI",
                ""
            )
            .upper()
        )

        if (
            clean_symbol
            in upcoming_dict
        ):

            targets.append(
                (
                    ticker,
                    upcoming_dict[
                        clean_symbol
                    ],
                    "🇮🇹 FTSE MIB"
                )
            )

    # DOW JONES

    for ticker in DOW_JONES:

        if (
            ticker.upper()
            in upcoming_dict
        ):

            targets.append(
                (
                    ticker,
                    upcoming_dict[
                        ticker.upper()
                    ],
                    "🇺🇸 DOW JONES"
                )
            )

    print(
        f"🎯 Titoli con trimestrale "
        f"nei prossimi 30 giorni: "
        f"{len(targets)}"
    )

    # --------------------------------------------------------
    # ANALISI
    # --------------------------------------------------------

    signals = []

    for (
        ticker,
        release_date,
        market
    ) in targets:

        analysis = analyze_stock(
            ticker,
            release_date,
            market
        )

        if analysis is None:
            continue

        if (
            analysis["score"] >= 4
            or analysis["score"] <= 2
        ):

            signals.append(
                analysis
            )

    # --------------------------------------------------------
    # NESSUN SEGNALE
    # --------------------------------------------------------

    if not signals:

        report = (
            "🟢 *SCANSIONE BORSA COMPLETATA*\n\n"
            f"📅 {today.strftime('%d/%m/%Y')}\n\n"
            "📊 *Per oggi non abbiamo titoli da proporti.*\n\n"
            "🔎 La scansione di FTSE MIB e "
            "Dow Jones è stata completata "
            "correttamente.\n\n"
            "Nessun titolo ha raggiunto il "
            "livello di segnale richiesto."
        )

        print("\n" + report)

        send_telegram(
            report
        )

        return

    # --------------------------------------------------------
    # ORDINA SEGNALI
    # --------------------------------------------------------

    signals.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # CREAZIONE REPORT
    # --------------------------------------------------------

    report = (
        "🚨 *AUTOMATIC TRADING SIGNALS*\n"
        "*BILANCI & CATALIZZATORI*\n\n"
    )

    report += (
        f"📅 {today.strftime('%d/%m/%Y')}\n"
        f"📊 Segnali trovati: "
        f"*{len(signals)}*\n\n"
    )

    for signal in signals:

        stars = (
            "⭐"
            * signal["score"]
        )

        report += (
            f"{signal['market']}\n"
        )

        report += (
            f"📅 Trimestrale: "
            f"*{signal['release_date']}* "
            f"(tra {signal['days_left']} gg)\n"
        )

        report += (
            f"🏢 *{signal['name']}* "
            f"(`{signal['symbol']}`)\n"
        )

        report += (
            f"Rating: {stars} "
            f"({signal['score']}/5)\n"
        )

        report += (
            f"*{signal['bias']}*\n\n"
        )

        report += (
            "*Motivi del segnale:*\n"
        )

        for reason in signal["reasons"]:

            report += (
                f"• {reason}\n"
            )

        report += (
            f"\n{signal['advice']}\n\n"
        )

    # --------------------------------------------------------
    # INVIO TELEGRAM
    # --------------------------------------------------------

    send_telegram(
        report
    )


# ============================================================
# AVVIO
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print(
            f"❌ ERRORE GENERALE: {error}"
        )

        # Anche in caso di errore generale,
        # proviamo ad avvisare Telegram.

        error_message = (
            "🔴 *ERRORE SCANSIONE BORSA*\n\n"
            f"📅 {datetime.date.today().strftime('%d/%m/%Y')}\n\n"
            "La scansione automatica ha riscontrato "
            "un errore durante l'esecuzione.\n\n"
            f"Errore: `{str(error)[:500]}`"
        )

        send_telegram(
            error_message
        )

import os
import requests


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


print("====================================")
print("TEST TELEGRAM")
print("====================================")

print("Token presente:", bool(TELEGRAM_BOT_TOKEN))
print("Chat ID presente:", bool(TELEGRAM_CHAT_ID))


if not TELEGRAM_BOT_TOKEN:
    print("ERRORE: TELEGRAM_BOT_TOKEN non trovato")
    exit(1)

if not TELEGRAM_CHAT_ID:
    print("ERRORE: TELEGRAM_CHAT_ID non trovato")
    exit(1)


url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


message = (
    "🟢 TEST TELEGRAM RIUSCITO!\n\n"
    "Il bot GitHub Actions riesce a comunicare "
    "correttamente con Telegram."
)


for chat_id in TELEGRAM_CHAT_ID.split(","):

    chat_id = chat_id.strip()

    if not chat_id:
        continue

    print(f"Invio messaggio a: {chat_id}")

    try:

        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message
            },
            timeout=20
        )

        print("HTTP:", response.status_code)
        print("RISPOSTA TELEGRAM:")
        print(response.text)

        if response.status_code == 200:
            print("====================================")
            print("✅ TELEGRAM FUNZIONA")
            print("====================================")
        else:
            print("====================================")
            print("❌ TELEGRAM HA RIFIUTATO LA RICHIESTA")
            print("====================================")

    except Exception as error:

        print("====================================")
        print("❌ ERRORE DI CONNESSIONE")
        print(error)
        print("====================================")

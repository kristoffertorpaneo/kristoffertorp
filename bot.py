import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta

# 1. Last inn miljøvariabler
load_dotenv()
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# --- KONFIGURASJON ---
DAYS_INACTIVE = 30
MY_USER_ID = "U05R136AFNJ" # Erstatt med din medlems-ID
WHITELIST = ["general", "announcements", "random"]
# ----------------------

def get_inactive_channels():
    print("Starter smart sjekk av kanaler (ignorerer botter/systemmeldinger)...")
    report = []
    threshold = datetime.now() - timedelta(days=DAYS_INACTIVE)
    
    channels = []
    cursor = None
    
    # Hent alle offentlige kanaler (Paginering)
    while True:
        try:
            response = client.conversations_list(
                types="public_channel", 
                exclude_archived=True, 
                cursor=cursor,
                limit=200
            )
            channels.extend(response["channels"])
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            print(f"Feil ved henting av kanaler: {e.response['error']}")
            break

    print(f"Fant totalt {len(channels)} åpne kanaler. Analyserer historikk...")

    for channel in channels:
        c_id = channel["id"]
        c_name = channel["name"]
        
        if c_name in WHITELIST:
            continue

        try:
            # Boten må være medlem
            if not channel["is_member"]:
                client.conversations_join(channel=c_id)

            # Henter de siste 10 meldingene for å finne et menneske
            history = client.conversations_history(channel=c_id, limit=10)
            messages = history.get("messages", [])
            
            last_human_date = None
            
            for msg in messages:
                # FILTER: Ignorer hvis det er en bot eller en system-event (subtype)
                is_bot = "bot_id" in msg or msg.get("user") == "USLACKBOT"
                is_system = msg.get("subtype") is not None 
                
                if not is_bot and not is_system:
                    last_human_date = datetime.fromtimestamp(float(msg["ts"]))
                    break # Fant den nyeste menneskelige meldingen, stopper her.

            if last_human_date:
                if last_human_date < threshold:
                    days_ago = (datetime.now() - last_human_date).days
                    report.append(f"• *#{c_name}*: {days_ago} dager siden sist et *menneske* skrev noe.")
            else:
                # Ingen menneskelige meldinger blant de siste 10
                report.append(f"• *#{c_name}*: Ingen menneskelig aktivitet funnet nylig (kun botter/system).")
                
        except SlackApiError as e:
            print(f"Kunne ikke sjekke #{c_name}: {e.response['error']}")
            
    return report

def send_report():
    inactive_list = get_inactive_channels()
    
    if inactive_list:
        header = f"🚀 *Smart Rapport: Inaktive kanaler (> {DAYS_INACTIVE} dager)*\n"
        header += "_Botter og systemmeldinger er filtrert ut._\n\n"
        
        # Hvis listen er for lang for én melding, deler vi den opp
        current_chunk = header
        for entry in inactive_list:
            if len(current_chunk) + len(entry) > 3500: # Slack grense er ca 4000
                client.chat_postMessage(channel=MY_USER_ID, text=current_chunk)
                current_chunk = ""
            current_chunk += entry + "\n"
        
        client.chat_postMessage(channel=MY_USER_ID, text=current_chunk)
        print("Rapport sendt!")
    else:
        client.chat_postMessage(channel=MY_USER_ID, text="✅ Fant ingen inaktive kanaler med de valgte kriteriene.")

if __name__ == "__main__":
    send_report()
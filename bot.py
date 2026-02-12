import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta

# 1. Last inn miljøvariabler
load_dotenv()
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# --- KONFIGURASJON ---
DAYS_INACTIVE = 90
MY_USER_ID = "U05R136AFNJ" # Husk din personlige medlems-ID
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

            # Henter de siste 10 meldingene
            history = client.conversations_history(channel=c_id, limit=10)
            messages = history.get("messages", [])
            
            last_human_date = None
            
            for msg in messages:
                is_bot = "bot_id" in msg or msg.get("user") == "USLACKBOT"
                is_system = msg.get("subtype") is not None 
                
                if not is_bot and not is_system:
                    last_human_date = datetime.fromtimestamp(float(msg["ts"]))
                    break

            if last_human_date:
                if last_human_date < threshold:
                    # HER ER FIKSEN: Vi definerer days_ago rett før den brukes
                    days_ago = (datetime.now() - last_human_date).days
                    report.append(f"• <#{c_id}>: {days_ago} dager siden sist et *menneske* skrev noe.")
            else:
                report.append(f"• <#{c_id}>: Ingen menneskelig aktivitet funnet nylig (kun botter/system).")
                
        except SlackApiError as e:
            print(f"Kunne ikke sjekke #{c_name}: {e.response['error']}")
            
    return report

def send_report():
    inactive_list = get_inactive_channels()
    
    if inactive_list:
        header = f"🚀 *Smart Rapport: Inaktive kanaler (> {DAYS_INACTIVE} dager)*\n"
        header += "_Klikk på kanalnavnet for å gå rett til kanalen._\n\n"
        
        current_chunk = header
        for entry in inactive_list:
            if len(current_chunk) + len(entry) > 3500:
                client.chat_postMessage(channel=MY_USER_ID, text=current_chunk)
                current_chunk = ""
            current_chunk += entry + "\n"
        
        client.chat_postMessage(channel=MY_USER_ID, text=current_chunk)
        print("Rapport sendt!")
    else:
        client.chat_postMessage(channel=MY_USER_ID, text="✅ Fant ingen inaktive kanaler.")

if __name__ == "__main__":
    send_report()
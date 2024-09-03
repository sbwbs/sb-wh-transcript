from fastapi import FastAPI, Request, HTTPException
import uvicorn
import json
from datetime import datetime
import httpx
import os
import traceback  

app = FastAPI()

latest_payload = None
latest_email = None

SENDBIRD_API_TOKEN = os.environ.get("SENDBIRD_API_TOKEN")
if not SENDBIRD_API_TOKEN:
    raise ValueError("SENDBIRD_API_TOKEN environment variable is not set")
else:
    print(f"SENDBIRD_API_TOKEN is set: {SENDBIRD_API_TOKEN[:5]}...")  # Partially log the token

# Zapier webhook URL
ZAPIER_WEBHOOK_URL = os.environ.get("ZAPIER_WEBHOOK_URL")
if not ZAPIER_WEBHOOK_URL:
    raise ValueError("ZAPIER_WEBHOOK_URL environment variable is not set")
else:
    print(f"ZAPIER_WEBHOOK_URL is set: {ZAPIER_WEBHOOK_URL}")

async def get_sendbird_messages(app_id: str, channel_url: str, message_ts: int = None):
    url = f"https://api-{app_id}.sendbird.com/v3/group_channels/{channel_url}/messages"
    headers = {
        "Api-Token": SENDBIRD_API_TOKEN,
        "Content-Type": "application/json"
    }
    params = {
        "prev_limit": 30,
        "next_limit": 30,
        "include": True,
        "message_ts": message_ts if message_ts else int(datetime.now().timestamp() * 1000)
    }

    print(f"Requesting Sendbird messages with URL: {url} and params: {params}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        print(f"Sendbird response status: {response.status_code}")
        response.raise_for_status()
        return response.json()

async def send_to_zapier(email: str, transcript: str):
    payload = {
        "email": email,
        "transcript": transcript
    }
    print(f"Sending payload to Zapier: {json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient() as client:
        response = await client.post(ZAPIER_WEBHOOK_URL, json=payload)
        print(f"Zapier response status: {response.status_code}")
        response.raise_for_status()
        return response.json()

def format_transcript(messages: list) -> str:
    transcript = []
    for message in messages:
        nickname = message['user']['nickname']
        content = message['message']
        transcript.append(f"{nickname}: {content}")
    return "\n".join(transcript)

@app.post("/sbwebhook")
async def handle_sendbird_webhook(request: Request):
    global latest_payload, latest_email
    try:
        payload = await request.json()
        print(f"Received webhook payload: {json.dumps(payload, indent=2)}")

        if payload.get('category') in ['form:submit']:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            category = payload.get('category')
            print(f"[{timestamp}] Processing {category} webhook...")

            latest_payload = payload
            
            # Extract email from the payload
            for form in payload.get('forms', []):
                for data in form.get('data', []):
                    if data.get('name') == 'Email':
                        latest_email = data.get('value')
                        print(f"Extracted email: {latest_email}")
            
            # Extract channel_url, app_id, and message_id
            channel_url = payload.get('form_message', {}).get('channel_url')
            app_id = payload.get('app_id')
            message_id = payload.get('form_message', {}).get('message_id')
            
            if channel_url and app_id and latest_email:
                try:
                    # Convert message_id to timestamp (milliseconds)
                    message_ts = int(message_id)
                    messages_data = await get_sendbird_messages(app_id, channel_url, message_ts)
                    messages = messages_data.get('messages', [])
                    
                    # Format the transcript
                    transcript = format_transcript(messages)
                    
                    # Send to Zapier webhook
                    await send_to_zapier(latest_email, transcript)
                    print("Successfully sent transcript to Zapier webhook.")
                except Exception as e:
                    print(f"Error processing messages or sending to webhook: {str(e)}")
                    print(traceback.format_exc())  # Log the full traceback for debugging
            else:
                print("Missing channel_url, app_id, or latest_email.")
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from request: {str(e)}")
        print(traceback.format_exc())
    except Exception as e:
        print(f"Unexpected error handling webhook: {str(e)}")
        print(traceback.format_exc())
    
    return {"status": "ok"}

@app.get("/latest_webhook")
async def get_latest_webhook():
    if latest_payload:
        return latest_payload
    else:
        return {"message": "No webhook payload received yet"}

@app.get("/latest_email")
async def get_latest_email():
    if latest_email:
        return {"email": latest_email}
    else:
        return {"message": "No email received yet"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
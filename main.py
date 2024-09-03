from fastapi import FastAPI, Request, HTTPException
import uvicorn
import json
from datetime import datetime
import httpx
import os
import time

app = FastAPI()

# Global variables to store the latest webhook payload and email
latest_payload = None
latest_email = None

SENDBIRD_API_TOKEN = os.environ.get("SENDBIRD_API_TOKEN")
if not SENDBIRD_API_TOKEN:
    raise ValueError("SENDBIRD_API_TOKEN environment variable is not set")

async def get_sendbird_messages(app_id: str, channel_url: str, message_ts: int = None):
    url = f"https://api-{app_id}.sendbird.com/v3/group_channels/{channel_url}/messages"
    headers = {
        "Api-Token": SENDBIRD_API_TOKEN,
        "Content-Type": "application/json"
    }
    params = {
        "prev_limit": 30,  # Adjust this value to get more or fewer messages
        "next_limit": 30,
        "include": True
    }
    
    if message_ts:
        params["message_ts"] = message_ts
    else:
        # If no timestamp is provided, use the current time
        params["message_ts"] = int(time.time() * 1000)

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

@app.post("/sbwebhook")
async def handle_sendbird_webhook(request: Request):
    global latest_payload, latest_email
    payload = await request.json()
    
    if payload.get('category') in ['form:submit']:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        category = payload.get('category')
        print(f"[{timestamp}] Received {category} webhook:")
        print(json.dumps(payload, indent=2))
        print("-" * 50)  # Separator line
        
        latest_payload = payload
        
        # Extract email from the payload
        for form in payload.get('forms', []):
            for data in form.get('data', []):
                if data.get('name') == 'Email':
                    latest_email = data.get('value')
                    print(f"Saved email: {latest_email}")
        
        channel_url = payload.get('form_message', {}).get('channel_url')
        app_id = payload.get('app_id')
        message_id = payload.get('form_message', {}).get('message_id')
        
        if channel_url and app_id:
            try:
                message_ts = int(message_id / 1000) if message_id else None
                messages = await get_sendbird_messages(app_id, channel_url, message_ts)
                print("Retrieved messages:")
                print(json.dumps(messages, indent=2))
            except Exception as e:
                print(f"Error retrieving messages: {str(e)}")
        
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
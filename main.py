from fastapi import FastAPI, Request
import uvicorn
import json
from datetime import datetime

app = FastAPI()

# Global variable to store the latest webhook payload
latest_payload = None

@app.post("/sbwebhook")
async def handle_sendbird_webhook(request: Request):
    global latest_payload
    payload = await request.json()
    if payload.get('category') in ['form:submit']:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        category = payload.get('category')
        print(f"[{timestamp}] Received {category} webhook:")
        print(json.dumps(payload, indent=2))
        print("-" * 50)  # Separator line
        latest_payload = payload
    return {"status": "ok"}

@app.get("/latest_webhook")
async def get_latest_webhook():
    if latest_payload:
        return latest_payload
    else:
        return {"message": "No webhook payload received yet"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)    
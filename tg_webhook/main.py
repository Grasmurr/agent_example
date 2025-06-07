import aioredis
import os
import json
from fastapi import FastAPI, Request

app = FastAPI()
redis = aioredis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, decode_responses=True, password=os.getenv('REDIS_PASSWORD', None))

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    await redis.publish("bot_updates_channel", json.dumps(data))
    return {"status": "ok"}

@app.get('/test')
async def test():
    return {"status": "ok"}

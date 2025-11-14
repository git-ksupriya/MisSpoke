import os
import time
from fastapi import FastAPI
from agora_token_builder import RtcTokenBuilder, Role

app = FastAPI()

AGORA_APP_ID = os.environ.get("AGORA_APP_ID")
AGORA_APP_CERTIFICATE = os.environ.get("AGORA_APP_CERTIFICATE")

@app.get("/token")
def generate_token(channel: str, uid: int):
    expire_seconds = 3600
    current_ts = int(time.time())
    privilege_expired_ts = current_ts + expire_seconds

    token = RtcTokenBuilder.build_token_with_uid(
        AGORA_APP_ID,
        AGORA_APP_CERTIFICATE,
        channel,
        uid,
        Role.PUBLISHER,
        privilege_expired_ts
    )

    return {"rtcToken": token}

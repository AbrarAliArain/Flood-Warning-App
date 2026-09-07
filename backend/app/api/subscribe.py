from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..storage.db import get_conn

router = APIRouter(prefix="/api", tags=["subscribe"])


class SubscribeRequest(BaseModel):
    name: str
    email: str
    organization: str | None = None


@router.post("/subscribe", status_code=201)
def subscribe(body: SubscribeRequest):
    if "@" not in body.email or "." not in body.email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="invalid email address")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO subscriptions (name, email, organization, created_at) VALUES (?, ?, ?, ?)",
            (body.name.strip(), body.email.strip(), body.organization, datetime.now(timezone.utc).isoformat()),
        )
    return {"status": "subscribed"}

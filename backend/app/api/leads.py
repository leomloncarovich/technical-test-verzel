from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class Lead(BaseModel):
    name: str | None = None
    email: str | None = None
    company: str | None = None
    need: str | None = None
    interestConfirmed: bool | None = None

class LeadIn(BaseModel):
    lead: Lead
    sessionId: str

@router.post("/leads")
def upsert_lead(body: LeadIn):
    # placeholder para Pipefy real
    return {"ok": True}

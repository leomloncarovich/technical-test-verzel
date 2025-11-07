from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from datetime import datetime

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    role: str
    content: str
    ts: datetime = Field(default_factory=datetime.utcnow)

class Meeting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    link: str
    datetime_iso: str
    booking_id: Optional[str] = Field(default=None, index=True)
    canceled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None

class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    need: Optional[str] = None
    interest_confirmed: Optional[bool] = None

engine = create_engine("sqlite:///data.db", echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)

def get_lead_by_session(db: Session, session_id: str) -> Lead:
    stmt = select(Lead).where(Lead.session_id == session_id)
    lead = db.exec(stmt).first()
    if not lead:
        lead = Lead(session_id=session_id)
        db.add(lead)
        db.commit()
        db.refresh(lead)
    return lead

def merge_lead(lead: Lead, partial: dict) -> Lead:
    if not partial:
        return lead
    if "name" in partial and partial["name"]:
        lead.name = partial["name"]
    if "email" in partial and partial["email"]:
        lead.email = partial["email"]
    if "company" in partial and partial["company"]:
        lead.company = partial["company"]
    if "need" in partial and partial["need"]:
        lead.need = partial["need"]
    if "interestConfirmed" in partial and partial["interestConfirmed"] is not None:
        lead.interest_confirmed = bool(partial["interestConfirmed"])
    return lead

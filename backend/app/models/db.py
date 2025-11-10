from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from datetime import datetime
import os

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

# Para Vercel/serverless, usa /tmp que é writable
# Para local, usa data.db no diretório atual
db_path = os.getenv("DB_URL", "sqlite:///data.db")
if os.getenv("VERCEL"):
    # Vercel/serverless: usa /tmp
    db_path = "sqlite:////tmp/data.db"

engine = create_engine(db_path, echo=False)

def init_db():
    try:
        SQLModel.metadata.create_all(engine)
        print(f"[DB] ✅ Banco de dados inicializado: {db_path}")
    except Exception as e:
        # Em serverless, pode falhar na primeira vez, mas não é crítico
        import sys
        print(f"[DB] ⚠️ Erro ao inicializar DB (pode ser normal em serverless): {e}", file=sys.stderr)
        # Não levanta exceção para não quebrar a inicialização

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
        print(f"[MERGE] ⚠️ partial vazio ou None, retornando lead sem alterações")
        return lead
    
    updated_fields = []
    if "name" in partial and partial["name"]:
        old_value = lead.name
        lead.name = partial["name"]
        if old_value != lead.name:
            updated_fields.append(f"name: {old_value} -> {lead.name}")
    
    if "email" in partial and partial["email"]:
        old_value = lead.email
        lead.email = partial["email"]
        if old_value != lead.email:
            updated_fields.append(f"email: {old_value} -> {lead.email}")
    
    if "company" in partial and partial["company"]:
        old_value = lead.company
        lead.company = partial["company"]
        if old_value != lead.company:
            updated_fields.append(f"company: {old_value} -> {lead.company}")
    
    if "need" in partial and partial["need"]:
        old_value = lead.need
        lead.need = partial["need"]
        if old_value != lead.need:
            updated_fields.append(f"need: {old_value} -> {lead.need}")
    
    if "interestConfirmed" in partial and partial["interestConfirmed"] is not None:
        old_value = lead.interest_confirmed
        lead.interest_confirmed = bool(partial["interestConfirmed"])
        if old_value != lead.interest_confirmed:
            updated_fields.append(f"interest_confirmed: {old_value} -> {lead.interest_confirmed}")
    
    if updated_fields:
        print(f"[MERGE] ✅ Campos atualizados: {', '.join(updated_fields)}")
    else:
        print(f"[MERGE] ⚠️ Nenhum campo foi atualizado. partial recebido: {partial}")
    
    return lead

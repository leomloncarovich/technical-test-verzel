from dotenv import load_dotenv
load_dotenv()  # Carrega ANTES de importar os módulos

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat, schedule, leads, health, pipefy

app = FastAPI(title="SDR Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(schedule.router, prefix="/api", tags=["schedule"])
app.include_router(leads.router, prefix="/api", tags=["leads"])
app.include_router(pipefy.router, prefix="/api", tags=["pipefy"])

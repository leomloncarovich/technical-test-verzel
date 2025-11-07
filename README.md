# SDR Agent - Chat de Pré-vendas Automatizado

Sistema de chat automatizado para pré-vendas que integra com Pipefy e Cal.com para gerenciar leads e agendar reuniões.

## 🚀 Funcionalidades

- **Chat automatizado** com LLM (Gemini) para conversar com leads
- **Integração com Pipefy** para sincronização de dados em tempo real
- **Integração com Cal.com** para agendamento de reuniões
- **Sincronização bidirecional** entre chat, Pipefy e Cal.com

## 📁 Estrutura do Projeto

```
test-coding-sdr/
├── backend/          # API FastAPI
│   ├── app/
│   │   ├── api/      # Endpoints
│   │   ├── core/     # Lógica de negócio (LLM, Cal.com, Pipefy)
│   │   └── models/   # Modelos de banco de dados
│   └── requirements.txt
└── frontend/         # Interface React/TypeScript
    └── src/
        └── components/
```

## 🛠️ Tecnologias

### Backend
- **FastAPI** - Framework web
- **SQLModel** - ORM para SQLite
- **Gemini API** - LLM para chat
- **HTTPX** - Cliente HTTP assíncrono

### Frontend
- **React** + **TypeScript**
- **Vite** - Build tool

## 📦 Instalação

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## ⚙️ Configuração

### Variáveis de Ambiente (Backend)

Crie um arquivo `.env` no diretório `backend/`:

```bash
# LLM
GEMINI_API_KEY=sua_chave_gemini

# Cal.com
CAL_API_KEY=sua_chave_cal
CAL_USERNAME=seu-username
CAL_EVENT_TYPE_SLUG=30min
CAL_EVENT_TYPE_ID=123456  # opcional

# Pipefy
PIPEFY_TOKEN=seu_token_pipefy
PIPEFY_PIPE_ID=306783445

# Opcional
MOCK_EXTERNALS=false  # true para usar mocks
API_BASE_URL=http://localhost:8000
```

## 🚀 Execução

### Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

## 📚 Documentação

- [PIPEFY.md](backend/PIPEFY.md) - Integração com Pipefy
- [DEPLOY_VERCEL.md](backend/DEPLOY_VERCEL.md) - Deploy no Vercel
- [CRIAR_WEBHOOK.md](backend/CRIAR_WEBHOOK.md) - Configurar webhooks
- [TESTE_PIPEFY.md](backend/TESTE_PIPEFY.md) - Como testar integrações

## 🔗 Endpoints da API

- `GET /health` - Health check
- `POST /api/chat` - Enviar mensagem no chat
- `POST /api/schedule` - Agendar reunião
- `POST /api/pipefy/webhook` - Webhook do Pipefy
- `POST /api/pipefy/updateBooking` - Atualizar booking no Pipefy

## 📝 Licença

Este projeto é um teste técnico.


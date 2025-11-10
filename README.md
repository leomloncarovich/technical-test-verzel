# SDR Agent - Chat de Pré-vendas Automatizado

Sistema de chat automatizado para pré-vendas que integra com Pipefy e Cal.com para gerenciar leads e agendar reuniões.

## 🚀 Funcionalidades

- **Chat automatizado** com LLM (Gemini) para conversar com leads
- **Integração com Pipefy** para sincronização de dados em tempo real
- **Integração com Cal.com** para agendamento de reuniões
- **Sincronização bidirecional** entre chat, Pipefy e Cal.com
- **Gerenciamento de sessão** com timeout configurável
- **Cache local de mensagens** para melhor experiência do usuário
- **Acessibilidade completa** com navegação por teclado (Tab, Enter, Esc, setas)
- **Interface responsiva** com Tailwind CSS (mobile-first)

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
- **Tailwind CSS** - Framework CSS utilitário

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

# Session Management
SESSION_TTL_HOURS=2  # Padrão recomendado para ambiente de teste técnico

# Opcional
MOCK_EXTERNALS=false  # IMPORTANTE: defina como "false" para agendar reuniões reais no Cal.com
API_BASE_URL=http://localhost:8000
TIMEZONE=America/Sao_Paulo  # Timezone para agendamentos
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

## 🚀 Deploy no Vercel

O projeto está configurado para deploy completo (frontend + backend) no Vercel.

### Configuração

1. **Conecte o repositório ao Vercel:**
   - Acesse [vercel.com](https://vercel.com)
   - Importe o repositório
   - O Vercel detectará automaticamente a configuração do `vercel.json`

2. **Configure as variáveis de ambiente:**
   - No painel do Vercel, vá em Settings → Environment Variables
   - Adicione todas as variáveis necessárias:
     - `GEMINI_API_KEY`
     - `CAL_API_KEY`
     - `CAL_USERNAME`
     - `CAL_EVENT_TYPE_SLUG`
     - `PIPEFY_TOKEN`
     - `PIPEFY_PIPE_ID`
     - `SESSION_TTL_HOURS` (opcional, padrão: 2)

3. **Deploy:**
   - O Vercel fará o build automaticamente:
     - Frontend: build do Vite em `frontend/dist`
     - Backend: serverless functions Python em `/api/*`
   - As rotas `/api/*` são direcionadas para o backend Python
   - Todas as outras rotas servem o frontend React

### Estrutura de Deploy

- **Frontend:** Servido como arquivos estáticos do build do Vite
- **Backend:** Serverless functions Python (FastAPI)
- **Rotas:**
  - `/api/*` → Backend Python
  - `/*` → Frontend React (SPA)

## 📚 Documentação

- [PIPEFY.md](backend/PIPEFY.md) - Integração com Pipefy
- [CRIAR_WEBHOOK.md](backend/CRIAR_WEBHOOK.md) - Configurar webhooks
- [TESTE_PIPEFY.md](backend/TESTE_PIPEFY.md) - Como testar integrações

## 🔗 Endpoints da API

- `GET /health` - Health check
- `POST /api/chat` - Enviar mensagem no chat
- `POST /api/schedule` - Agendar reunião
- `POST /api/pipefy/webhook` - Webhook do Pipefy
- `POST /api/pipefy/updateBooking` - Atualizar booking no Pipefy

## ⏰ Gerenciamento de Sessão

O sistema implementa um timeout de sessão configurável via variável de ambiente `SESSION_TTL_HOURS`. O padrão recomendado para ambiente de teste técnico é **2 horas** (`SESSION_TTL_HOURS=2`), que é curto o suficiente para parecer profissional e não poluir o banco de dados, mas longo o suficiente para permitir testes sem que a sessão expire frequentemente.

Quando uma sessão expira por inatividade, o sistema retorna uma mensagem informando ao usuário que a sessão expirou e que é necessário recarregar a página para iniciar uma nova conversa.

## 💾 Cache Local de Mensagens

O frontend implementa um cache local das mensagens usando `localStorage` para melhorar a experiência do usuário. As mensagens são automaticamente carregadas do cache quando o usuário recarrega a página, permitindo continuidade da conversa sem perder o histórico.

**Nota:** Para produção, poderíamos reduzir a retenção local dependendo das políticas de privacidade da empresa.

## ♿ Acessibilidade

O chat implementa recursos de acessibilidade completos seguindo as diretrizes WCAG:

### Navegação por Teclado

- **Tab**: Navega entre elementos interativos (input, botão enviar, slots de horário)
- **Enter**: Envia mensagem no input ou seleciona um horário disponível
- **Esc**: Cancela seleção de horários e retorna o foco para o input
- **Setas ↑↓**: Navega entre os slots de horário disponíveis
- **Home/End**: Vai para o primeiro/último slot de horário

### Recursos ARIA

- `role="log"` e `aria-live="polite"` no container de mensagens
- `aria-label` em todos os elementos interativos
- `aria-describedby` para descrições contextuais
- `role="group"` para grupos de elementos relacionados (slots)
- Classes `sr-only` para texto acessível apenas a leitores de tela

### Indicadores Visuais

- Foco visível em todos os elementos interativos (ring azul)
- Estados hover e focus distintos
- Feedback visual durante carregamento
- Suporte a modo escuro/claro (prefers-color-scheme)

### Responsividade

- Design mobile-first com Tailwind CSS
- Breakpoints responsivos para diferentes tamanhos de tela
- Layout adaptável que funciona em dispositivos móveis e desktop

## 📝 Licença

Este projeto é um teste técnico.


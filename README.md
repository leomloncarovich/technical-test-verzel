# SDR Agent - Agente de Pré-vendas Automatizado

Sistema completo de agente SDR (Sales Development Representative) automatizado que conduz conversas naturais com leads, coleta informações, agenda reuniões e gerencia leads no Pipefy. Desenvolvido como parte do desafio técnico Elite Dev IA.

🔗 **Demo:** [Link do Vercel aqui após deploy]

## 🚀 TL;DR (5 minutos)

1. **Backend:** `cd backend && cp .env.example .env && uvicorn app.main:app --port 8000`
2. **Frontend:** `cd frontend && npm i && npm run dev`
3. Acesse `http://localhost:5173` e envie: **"quero agendar"**

> ⚠️ **Importante:** Configure as variáveis de ambiente no arquivo `backend/.env` antes de iniciar (veja seção [Configuração](#-configuração)).

## ✅ Conformidade com o Desafio

- [X] **Conversa natural** com coleta progressiva (nome, e-mail, empresa, necessidade)
- [X] **Confirmação explícita de interesse** como gatilho para agendamento
- [X] **Sugere 2-3 horários** e agenda automaticamente via Cal.com
- [X] **Retorna link de reunião** ao cliente após agendamento
- [X] **Persiste todos os leads no Pipefy** (evita duplicatas por e-mail)
- [X] **Recontato atualiza card existente** quando mesmo e-mail é usado
- [X] **Webchat responsivo** (mobile-first) com acessibilidade essencial

## 📋 Índice

- [Descrição](#-descrição)
- [Funcionalidades](#-funcionalidades)
- [Tecnologias](#-tecnologias)
- [Requisitos do Sistema](#-requisitos-do-sistema)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Como Executar](#-como-executar)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Integrações](#-integrações)
- [Deploy](#-deploy)
- [Critérios de Sucesso](#-critérios-de-sucesso)
- [Observações Importantes](#-observações-importantes)

## 🎯 Descrição

Este projeto implementa um agente SDR automatizado que:

1. **Atende leads** interessados em consultoria para solução de problemas em logística
2. **Conduz conversas naturais** para entender o interesse e coletar informações básicas do cliente
3. **Agenda automaticamente reuniões** via Cal.com quando o cliente confirma interesse
4. **Registra todos os leads** no Pipefy, criando ou atualizando cards no funil de pré-vendas

O sistema utiliza LLM (Gemini) para processar conversas naturais, valida se o lead é do perfil ideal (ICP - Ideal Customer Profile), coleta dados progressivamente e oferece agendamento apenas quando há confirmação explícita de interesse.

## ✨ Funcionalidades

### MVP Implementado

- ✅ **Agente conversacional funcional** com diálogo natural (texto)
- ✅ **Coleta de dados principais**: nome, e-mail, empresa, necessidade/dor, confirmação de interesse
- ✅ **Agendamento automático**:
  - Sugere horários disponíveis de reunião
  - Agenda automaticamente via API do Cal.com
  - Retorna o link de reunião ao cliente
- ✅ **Integração com Pipefy** para criação/atualização de cards com os dados coletados
- ✅ **Webchat responsivo** com UI/UX moderna

### Funcionalidades Adicionais

- ✅ **Validação de ICP**: Sistema identifica se o lead é do perfil ideal (empresas de logística)
- ✅ **Reconhecimento de termos técnicos**: CRC, WMS, picking, packing, cross-docking, etc.
- ✅ **Gerenciamento de sessão** com timeout configurável (padrão: 2 horas)
- ✅ **Cache local de mensagens** para melhor experiência do usuário
- ✅ **Acessibilidade essencial**: ARIA básica (aria-live, labels), handlers de teclado (Enter para enviar, Esc para cancelar, setas para navegar slots)
- ✅ **Interface responsiva** mobile-first com Tailwind CSS
- ✅ **Suporte a light/dark mode** baseado na preferência do sistema
- ✅ **Re-engagement**: Leads que retornam com o mesmo email atualizam o card existente
- ✅ **Tratamento de leads não interessados**: Move para fase específica no Pipefy e coleta motivo

## 🛠️ Tecnologias

### Backend

- **FastAPI** - Framework web assíncrono
- **SQLModel** - ORM para SQLite
- **Gemini API** (Google Generative AI) - LLM para processamento de conversas
- **HTTPX** - Cliente HTTP assíncrono para integrações
- **Python 3.9+** - Linguagem de programação
- **Uvicorn** - Servidor ASGI

### Frontend

- **React 19+** - Biblioteca UI
- **TypeScript 5+** - Tipagem estática
- **Vite 7+** - Build tool e dev server
- **Tailwind CSS 4+** - Framework CSS utilitário
- **PostCSS** - Processamento de CSS

### Integrações

- **Cal.com API** - Agendamento de reuniões
- **Pipefy GraphQL API** - Gerenciamento de leads
- **Gemini API** - Processamento de linguagem natural

## 📦 Requisitos do Sistema

### Software Necessário

- **Python 3.9 ou superior**
- **Node.js 18+ e npm** (ou yarn/pnpm)
- **Git** para clonar o repositório

### Contas e APIs Necessárias

- **Conta Google** com acesso à API Gemini (tier gratuito disponível)
- **Conta Cal.com** com API key configurada
- **Conta Pipefy** com token de API e pipe configurado

## 🚀 Instalação

### 1. Clonar o Repositório

```bash
git clone <url-do-repositório>
cd test-coding-sdr
```

### 2. Instalar Dependências do Backend

```bash
# Criar ambiente virtual
cd backend
python3 -m venv .venv

# Ativar ambiente virtual
# Linux/Mac:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

### 3. Instalar Dependências do Frontend

```bash
# Voltar para a raiz do projeto
cd ..

# Instalar dependências do frontend
cd frontend
npm install
```

## ⚙️ Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` no diretório `backend/` com as seguintes variáveis:

| Variável                                | Exemplo                   | Obrigatória | Observações                                               |
| ---------------------------------------- | ------------------------- | ------------ | ----------------------------------------------------------- |
| `GEMINI_API_KEY`                       | `AIza...`               | ✅           | Obtenha em: https://makersuite.google.com/app/apikey        |
| `CAL_API_KEY`                          | `cal_...`               | ✅           | Obtenha em: https://app.cal.com/settings/developer/api-keys |
| `CAL_USERNAME`                         | `seu-usuario`           | ✅           | Username do Cal.com                                         |
| `CAL_EVENT_TYPE_SLUG`                  | `30min`                 | ✅           | Slug do tipo de evento                                      |
| `CAL_EVENT_TYPE_ID`                    | `3830730`               | 🔸           | Recomendado para melhor performance                         |
| `TIMEZONE`                             | `America/Sao_Paulo`     | 🔸           | Padrão:`America/Sao_Paulo`                               |
| `PIPEFY_API_TOKEN` ou `PIPEFY_TOKEN` | `eyJ...`                | ✅           | Obtenha em: https://app.pipefy.com/tokens                   |
| `PIPEFY_PIPE_ID`                       | `306783445`             | ✅           | ID do pipe (encontre na URL)                                |
| `SESSION_TTL_HOURS`                    | `2`                     | 🔸           | Padrão: 2 horas (recomendado para teste)                   |
| `MOCK_EXTERNALS`                       | `false`                 | 🔸           | `false` para agendar reuniões reais                      |
| `API_BASE_URL`                         | `http://localhost:8000` | 🔸           | Apenas para desenvolvimento local                           |
| `DB_URL`                               | `sqlite:///./data.db`   | 🔸           | Padrão: SQLite                                             |

**Exemplo de arquivo `.env`:**

```bash
GEMINI_API_KEY=AIzaSyC...
CAL_API_KEY=cal_live_...
CAL_USERNAME=seu-usuario
CAL_EVENT_TYPE_SLUG=30min
CAL_EVENT_TYPE_ID=3830730
PIPEFY_API_TOKEN=eyJhbGc...
PIPEFY_PIPE_ID=306783445
SESSION_TTL_HOURS=2
MOCK_EXTERNALS=false
TIMEZONE=America/Sao_Paulo
```

### Configuração do Pipefy

O sistema espera os seguintes campos no pipe do Pipefy:

- **Nome do Lead** (text)
- **Email do Lead** (email)
- **Empresa do Lead** (text)
- **Necessidade do Lead** (long_text)
- **Interesse Confirmado** (radio_vertical) - valores: "Sim" / "Não"
- **Motivo de Não Interesse** (long_text) - opcional, na fase "Não Interessado"

**Fases necessárias no Pipefy:**

- **Caixa de entrada** (fase inicial)
- **Agendado** (para leads com reunião agendada)
- **Não Interessado** (para leads que não demonstraram interesse)

### Configuração do Cal.com

1. Crie um tipo de evento no Cal.com (ex: "30min")
2. Obtenha o `eventTypeSlug` (ex: "30min")
3. Obtenha o `eventTypeId` (opcional, mas recomendado para melhor performance)
4. Configure a API key nas variáveis de ambiente

## 🏃 Como Executar

### Desenvolvimento Local

#### 1. Iniciar o Backend

```bash
cd backend
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

uvicorn app.main:app --reload --port 8000
```

O backend estará disponível em: `http://localhost:8000`

#### 2. Iniciar o Frontend

Em outro terminal:

```bash
cd frontend
npm run dev
```

O frontend estará disponível em: `http://localhost:5173` (porta padrão do Vite)

### Verificar se está Funcionando

1. Acesse `http://localhost:5173` no navegador
2. Você verá a interface do chat
3. Digite uma mensagem para testar o agente

### Testes com cURL

#### Health Check

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status": "ok"}
```

#### Testar Chat

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"local-test","message":"Tenho problemas de rota em SP"}'
```

#### Agendar Reunião (exemplo)

```bash
curl -X POST http://localhost:8000/api/schedule \
  -H 'Content-Type: application/json' \
  -d '{
    "slotId": "cal-0-2025-11-12T14:00:00.000-03:00",
    "sessionId": "local-test",
    "startIso": "2025-11-12T17:00:00Z"
  }'
```

## 🏗️ Arquitetura

```
Frontend (React) ──fetch/POST──▶ FastAPI
                                 ├─▶ Gemini (LLM)
                                 ├─▶ Cal.com (slots/booking)
                                 ├─▶ Pipefy (GraphQL)
                                 └─▶ SQLite (SQLModel)
```

## 📁 Estrutura do Projeto

```
test-coding-sdr/
├── backend/                    # API FastAPI
│   ├── app/
│   │   ├── api/               # Endpoints da API
│   │   │   ├── chat.py        # Endpoint principal do chat
│   │   │   ├── schedule.py    # Endpoint de agendamento
│   │   │   ├── pipefy.py      # Endpoint de webhook/atualização Pipefy
│   │   │   └── health.py      # Health check
│   │   ├── core/              # Lógica de negócio
│   │   │   ├── llm.py         # Integração com Gemini
│   │   │   ├── calendar.py    # Integração com Cal.com
│   │   │   ├── pipefy.py      # Integração com Pipefy
│   │   │   └── config.py      # Configurações
│   │   ├── models/            # Modelos de banco de dados
│   │   │   └── db.py          # Modelos SQLModel
│   │   └── main.py            # Aplicação FastAPI
│   ├── data.db                # Banco de dados SQLite (gerado automaticamente)
│   └── requirements.txt       # Dependências Python
│
├── frontend/                   # Interface React
│   ├── src/
│   │   ├── components/        # Componentes React
│   │   │   ├── Chat.tsx       # Componente principal do chat
│   │   │   └── HeroConsultoria.tsx  # Hero section
│   │   ├── lib/               # Utilitários
│   │   │   ├── api.ts         # Cliente API
│   │   │   └── session.ts     # Gerenciamento de sessão
│   │   ├── App.tsx            # Componente raiz
│   │   └── main.tsx           # Entry point
│   ├── public/                # Arquivos estáticos
│   │   └── sdr-logistics.svg  # Favicon
│   ├── index.html             # HTML principal
│   └── package.json           # Dependências Node
│
├── api/                       # Serverless functions para Vercel
│   ├── index.py              # Entry point para Vercel
│   └── requirements.txt       # Dependências Python
│
├── vercel.json                # Configuração do Vercel
├── requirements.txt           # Dependências Python (raiz, para Vercel)
└── README.md                  # Este arquivo
```

## 🔌 Integrações

### Gemini API (LLM)

O sistema utiliza a API do Gemini (Google) para processar conversas naturais. O prompt do sistema foi cuidadosamente configurado para:

- Validar se o lead é do perfil ideal (ICP)
- Coletar dados progressivamente (nome, email, empresa, necessidade)
- Confirmar interesse explicitamente antes de oferecer agendamento
- Reconhecer termos técnicos logísticos (CRC, WMS, picking, packing, etc.)

**Configuração:**

- Variável: `GEMINI_API_KEY`
- Modelo: `gemini-2.5-flash`
- Formato de resposta: JSON estruturado

### Cal.com

Integração completa com Cal.com para:

- Buscar slots disponíveis (próximos 7 dias)
- Criar eventos automaticamente
- Retornar link de reunião ao cliente
- Atualizar card no Pipefy com link e data/hora

**Configuração:**

- Variáveis: `CAL_API_KEY`, `CAL_USERNAME`, `CAL_EVENT_TYPE_SLUG`, `CAL_EVENT_TYPE_ID`
- API Version: v2 (2024-08-13 para bookings, 2024-09-04 para slots)

### Pipefy

Integração com Pipefy GraphQL API para:

- Criar cards no funil de pré-vendas
- Atualizar cards existentes (evita duplicatas usando email como chave)
- Mover cards entre fases (Caixa de entrada → Agendado → Não Interessado)
- Atualizar campos: nome, email, empresa, necessidade, interesse confirmado, motivo de não interesse
- Atualizar título do card dinamicamente (formato: "Nome - Email")

**Configuração:**

- Variáveis: `PIPEFY_API_TOKEN` ou `PIPEFY_TOKEN`, `PIPEFY_PIPE_ID`
- Campos necessários: nome, email, empresa, necessidade, interesse_confirmado, motivo_nao_interesse
- Fases necessárias: Caixa de entrada, Agendado, Não Interessado

## 🚀 Deploy

### Deploy no Vercel

O projeto está configurado para deploy completo (frontend + backend) no Vercel.

#### 1. Preparação

1. Certifique-se de que todas as variáveis de ambiente estão configuradas no arquivo `.env`
2. Faça commit e push de todas as alterações para o repositório GitHub

#### 2. Conectar ao Vercel

1. Acesse [vercel.com](https://vercel.com)
2. Faça login com sua conta GitHub
3. Clique em "Add New Project"
4. Importe o repositório do projeto

#### 3. Configurar Variáveis de Ambiente

No painel do Vercel, vá em **Settings → Environment Variables** e adicione todas as variáveis:

```
GEMINI_API_KEY
CAL_API_KEY
CAL_USERNAME
CAL_EVENT_TYPE_SLUG
CAL_EVENT_TYPE_ID (opcional)
PIPEFY_API_TOKEN (ou PIPEFY_TOKEN)
PIPEFY_PIPE_ID
SESSION_TTL_HOURS (opcional, padrão: 2)
MOCK_EXTERNALS (opcional, padrão: false)
TIMEZONE (opcional, padrão: America/Sao_Paulo)
```

#### 4. Deploy

O Vercel detectará automaticamente a configuração do `vercel.json` e fará:

- **Build do Frontend**: Compila o React com Vite em `frontend/dist`
- **Deploy do Backend**: Cria serverless functions Python em `/api/*`
- **Configuração de Rotas**:
  - `/api/*` → Backend Python (FastAPI)
  - `/*` → Frontend React (SPA)

#### 5. Verificar Deploy

Após o deploy, acesse a URL fornecida pelo Vercel e teste o chat.

### Estrutura de Deploy no Vercel

- **Frontend**: Servido como arquivos estáticos do build do Vite
- **Backend**: Serverless functions Python (FastAPI)
- **Rotas**:
  - `/api/*` → Backend Python
  - `/*` → Frontend React (SPA com fallback para `index.html`)

## ✅ Critérios de Sucesso

### Implementados (Requisitos do Desafio)

- ✅ **Conversa natural** com perguntas progressivas e resumos claros
- ✅ **Confirmação explícita de interesse** como gatilho para agendamento
- ✅ **Agendamento criado e confirmado** na API do Cal.com
- ✅ **Todos os leads persistidos no Pipefy** com status adequado
- ✅ **Recontato com mesmo email atualiza** o card existente
- ✅ **Código bem estruturado e documentado**

### Funcionalidades Extras

- ✅ **Validação de ICP**: Sistema identifica se o lead é do perfil ideal
- ✅ **Reconhecimento de termos técnicos**: CRC, WMS, picking, packing, etc.
- ✅ **Tratamento de leads não interessados**: Coleta motivo e move para fase específica
- ✅ **Acessibilidade essencial**: ARIA básica, handlers de teclado
- ✅ **Interface responsiva**: Mobile-first, Tailwind CSS
- ✅ **Suporte a light/dark mode**: Baseado na preferência do sistema
- ✅ **Cache local de mensagens**: Melhora UX e permite continuidade da conversa
- ✅ **Timeout de sessão configurável**: Previne poluição do banco de dados

## ⚠️ Observações Importantes

### Funcionamento Esperado

1. **Primeira mensagem**: O agente pergunta sobre o problema/necessidade do lead
2. **Validação de ICP**: Se não for relacionado a logística, o agente explica educadamente e não coleta dados
3. **Coleta de dados**: Nome, email, empresa, necessidade (problema logístico)
4. **Confirmação de interesse**: Agente pergunta explicitamente se o lead tem interesse
5. **Agendamento**: Se confirmar interesse, oferece horários e agenda automaticamente
6. **Pipefy**: Todos os leads são registrados, independente do resultado

### Limitações Conhecidas

1. **Mock Mode**: Por padrão, `MOCK_EXTERNALS=true` está ativo. Para agendar reuniões reais, defina `MOCK_EXTERNALS=false` no `.env`
2. **Banco de Dados**: SQLite é usado por padrão. Para produção, considere PostgreSQL ou MySQL
3. **Sessão**: Timeout padrão de 2 horas. Ajuste `SESSION_TTL_HOURS` conforme necessário
4. **Pipefy**: Certifique-se de que os campos e fases estão configurados corretamente no pipe

### Troubleshooting

#### Backend não inicia

- Verifique se o ambiente virtual está ativado
- Verifique se todas as dependências foram instaladas: `pip install -r requirements.txt`
- Verifique se o arquivo `.env` existe e está no diretório `backend/`

#### Frontend não inicia

- Verifique se o Node.js está instalado: `node --version`
- Reinstale as dependências: `rm -rf node_modules && npm install`
- Verifique se a porta 5173 está disponível

#### Integrações não funcionam

- Verifique se as variáveis de ambiente estão configuradas corretamente
- Verifique se `MOCK_EXTERNALS=false` para integrações reais
- Verifique os logs do backend para mensagens de erro
- Teste as APIs manualmente (Cal.com, Pipefy) para verificar credenciais

#### Cards não são criados no Pipefy

- Verifique se o `PIPEFY_PIPE_ID` está correto
- Verifique se o token tem permissões para criar/atualizar cards
- Verifique se os campos necessários existem no pipe
- Verifique os logs do backend para erros específicos

### Próximos Passos (Melhorias Futuras)

- [ ] Suporte a múltiplos idiomas
- [ ] Integração com outros provedores de calendário (Google Calendar, Outlook)
- [ ] Dashboard de analytics de leads
- [ ] Notificações por email/SMS
- [ ] Suporte a upload de arquivos no chat
- [ ] Integração com CRM adicional
- [ ] Testes automatizados (unitários e integração)

## 📸 Screenshots

> 💡 **Nota:** Adicione screenshots do projeto em funcionamento:
>
> - Interface do chat (Hero + Chat)
> - Booking criado no Cal.com
> - Card criado/atualizado no Pipefy

## 📝 Licença

Este projeto foi desenvolvido como parte de um teste técnico.

## 👤 Autor

Desenvolvido como parte do desafio técnico Elite Dev IA.

---

**Última atualização**: 2025-11-10

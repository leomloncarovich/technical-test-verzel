#!/usr/bin/env python3
"""
Script para criar webhook no Pipefy via GraphQL.

Uso:
    # Com venv ativado:
    source .venv/bin/activate
    python criar_webhook.py
    
    # Ou diretamente:
    .venv/bin/python criar_webhook.py

Requisitos:
    - PIPEFY_TOKEN no .env
    - PIPEFY_PIPE_ID no .env (opcional, padrão: 306783445)
    - WEBHOOK_URL no .env (opcional)
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Adiciona o diretório do backend ao path
backend_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(backend_dir))

load_dotenv()

# Verifica se httpx está disponível
try:
    import httpx
except ImportError:
    venv_python = backend_dir / ".venv" / "bin" / "python"
    if venv_python.exists():
        print("❌ httpx não encontrado no Python atual")
        print(f"💡 Use o Python do venv:")
        print(f"   {venv_python} criar_webhook.py")
        print(f"\n   Ou ative o venv primeiro:")
        print(f"   source .venv/bin/activate")
        print(f"   python criar_webhook.py")
        sys.exit(1)
    else:
        print("❌ httpx não encontrado e venv não encontrado")
        print("💡 Instale as dependências:")
        print("   pip install -r requirements.txt")
        sys.exit(1)

def main():
    try:
        from app.core.pipefy import create_pipe_webhook
    except ImportError as e:
        print("❌ Erro: Não foi possível importar create_pipe_webhook")
        print(f"   Erro detalhado: {e}")
        print(f"   Diretório atual: {os.getcwd()}")
        print(f"   Backend dir: {backend_dir}")
        print("\n💡 Soluções:")
        print("   1. Ative o venv: source .venv/bin/activate")
        print("   2. Ou use: .venv/bin/python criar_webhook.py")
        print("   3. Se ainda não funcionar, recrie o venv (veja FIX_VENV.md)")
        print("   4. OU use a automação HTTP no Pipefy (mais fácil - veja CRIAR_WEBHOOK.md)")
        sys.exit(1)
    
    # Configurações
    PIPE_ID = os.getenv("PIPEFY_PIPE_ID", "306783445")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    
    if not os.getenv("PIPEFY_TOKEN"):
        print("❌ PIPEFY_TOKEN não configurado no .env")
        print("   Adicione: PIPEFY_TOKEN=seu_token")
        sys.exit(1)
    
    if not WEBHOOK_URL:
        print("⚠️  WEBHOOK_URL não configurado no .env")
        print("   Digite a URL do webhook:")
        WEBHOOK_URL = input("URL: ").strip()
        if not WEBHOOK_URL:
            print("❌ URL é obrigatória")
            sys.exit(1)
    
    print(f"\n🔧 Criando webhook para pipe {PIPE_ID}...")
    print(f"📍 URL: {WEBHOOK_URL}")
    print(f"🎯 Ação: card.create\n")
    
    try:
        result = create_pipe_webhook(
            pipe_id=PIPE_ID,
            webhook_url=WEBHOOK_URL,
            actions=["card.create"],
            name="SDR Webhook"
        )
        
        webhook = result.get("webhook", {})
        print(f"✅ Webhook criado com sucesso!\n")
        print(f"   ID: {webhook.get('id')}")
        print(f"   Nome: {webhook.get('name')}")
        print(f"   URL: {webhook.get('url')}")
        print(f"   Ações: {webhook.get('actions')}\n")
        
        print("💡 Próximos passos:")
        print("   1. Crie um card no Pipefy para testar")
        print("   2. Verifique os logs do backend")
        print("   3. O chat deve iniciar automaticamente")
        
    except Exception as e:
        print(f"\n❌ Erro ao criar webhook: {type(e).__name__}: {e}")
        print("\n💡 Possíveis causas:")
        print("   - Token inválido ou sem permissões")
        print("   - Pipe ID incorreto")
        print("   - URL do webhook inacessível")
        print("   - Mutation GraphQL não disponível na sua conta")
        print("\n💡 Alternativa: Use automação HTTP no Pipefy (veja CRIAR_WEBHOOK.md)")
        sys.exit(1)

if __name__ == "__main__":
    main()


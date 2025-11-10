"""
FastAPI app para Vercel serverless functions
"""
import os
import sys

# Configura variável de ambiente para Vercel
os.environ.setdefault("VERCEL", "1")

# Carrega .env apenas se existir (não necessário no Vercel)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Tratamento de erros na importação
app = None
import_error = None

try:
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
    
    try:
        app.include_router(health.router, tags=["health"])
        app.include_router(chat.router, prefix="/api", tags=["chat"])
        app.include_router(schedule.router, prefix="/api", tags=["schedule"])
        app.include_router(leads.router, prefix="/api", tags=["leads"])
        app.include_router(pipefy.router, prefix="/api", tags=["pipefy"])
        print("[MAIN] ✅ Routers registrados com sucesso", file=sys.stderr)
        
        # Inicializa field IDs do Pipefy na inicialização do app
        @app.on_event("startup")
        async def startup_event():
            try:
                from app.core.pipefy import initialize_field_ids
                print("[MAIN] 🔄 Inicializando field IDs do Pipefy...", file=sys.stderr)
                initialize_field_ids()
                print("[MAIN] ✅ Field IDs do Pipefy inicializados", file=sys.stderr)
            except Exception as e:
                # Não falha a inicialização se não conseguir buscar field IDs
                print(f"[MAIN] ⚠️ Erro ao inicializar field IDs (não crítico): {type(e).__name__}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
    except Exception as e:
        print(f"[MAIN] ❌ Erro ao registrar routers: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        import_error = f"Router registration error: {e}"
        
except Exception as e:
    import_error = f"Import error: {type(e).__name__}: {e}"
    print(f"[MAIN] ❌ Erro ao importar módulos: {import_error}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    # Cria um app mínimo para retornar erros
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi import Request
    
    app = FastAPI(title="SDR Agent API - Error Mode")
    
    @app.get("/")
    @app.get("/{path:path}")
    async def error_handler(request: Request, path: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "error": import_error or "Unknown initialization error",
                "type": "InitializationError",
                "path": str(request.url.path)
            }
        )

# Garante que app sempre está definido
if app is None:
    print("[MAIN] ❌ CRÍTICO: App não foi definido! Criando app de emergência.", file=sys.stderr)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi import Request
    
    app = FastAPI(title="SDR Agent API - Emergency Mode")
    
    @app.get("/")
    @app.get("/{path:path}")
    async def emergency_handler(request: Request, path: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Application failed to initialize",
                "type": "EmergencyMode",
                "path": str(request.url.path)
            }
        )
app = app
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.database import init_db
from src.api import router
from src.telemetry import setup_telemetry, TelemetryMiddleware
from src.integration import integration_router
from fastapi.staticfiles import StaticFiles
import os
import threading

def _setup_sentry() -> bool:
    """
    Observabilidade opcional: sem SENTRY_DSN a aplicação sobe normalmente.
    Existe porque hoje um erro de render vira tela preta silenciosa e um erro
    de servidor só aparece se alguém for ler o log.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("EOS_ENV", "development"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            integrations=[FastApiIntegration()],
            send_default_pii=False,        # nada de dado pessoal nos eventos
        )
        return True
    except ImportError:
        print("SENTRY_DSN definido mas sentry-sdk não está instalado — seguindo sem.")
        return False


def _run_migrations() -> None:
    """
    Aplica as migrações no boot da própria aplicação.
    Fica aqui, e não no comando de start da plataforma, porque encadear
    `alembic upgrade && uvicorn` num startCommand deixa o processo morrer em
    silêncio se a primeira parte falhar — foi o que aconteceu no Railway: o
    log terminava na migração e o servidor nunca subia.
    """
    try:
        from alembic import command
        from alembic.config import Config
        cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        # O env.py chama asyncio.run(), o que estoura dentro do loop do
        # lifespan ("cannot be called from a running event loop"). Rodar numa
        # thread dá ao alembic um loop só dele.
        erro: list = []

        def _executar():
            try:
                command.upgrade(cfg, "head")
            except Exception as exc:  # noqa: BLE001
                erro.append(exc)

        t = threading.Thread(target=_executar, daemon=True)
        t.start()
        t.join(timeout=120)
        if erro:
            raise erro[0]
        if t.is_alive():
            raise TimeoutError("migração excedeu 120s")
        print("Migrações aplicadas.")
    except Exception as e:  # noqa: BLE001
        # Não derruba o processo: sem servidor no ar não há como diagnosticar,
        # e /health/ready denuncia o estado real do banco de qualquer forma.
        print(f"AVISO: falha ao aplicar migrações: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry()
    if _setup_sentry():
        print("Sentry ativo.")
    if os.getenv("EOS_RUN_MIGRATIONS", "1") not in ("0", "false"):
        _run_migrations()
    # Inicializa o banco de dados e cria tabelas no startup
    print("Inicializando banco de dados EngineeringOS...")
    await init_db()
    # Garante que o banco de desafios do CCE existe para as KUs presentes
    from src.database import AsyncSessionLocal
    from src.curriculum_seed import seed_challenge_bank
    async with AsyncSessionLocal() as session:
        inserted = await seed_challenge_bank(session)
        if inserted:
            print(f"CCE: {inserted} desafios padrão inseridos.")
    print("Banco de dados pronto.")
    yield

app = FastAPI(
    title="EngineeringOS API",
    version="2.0.0",
    description="Constitutional reference implementation of the EngineeringOS adaptive learning specification.",
    lifespan=lifespan
)

import math
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

def _sanitize_validation_errors(errors):
    """Substitui floats Infinity/NaN por string para evitar crash do json.dumps()"""
    sanitized = []
    for err in errors:
        err_copy = dict(err)
        if 'input' in err_copy:
            val = err_copy['input']
            if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                err_copy['input'] = str(val)
        sanitized.append(err_copy)
    return sanitized

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitize_validation_errors(exc.errors())},
    )


# Adiciona middleware de CORS para permitir acesso do React (Vite)
# CORS restrito por origem. `allow_origins=["*"]` junto com
# `allow_credentials=True` é proibido pela especificação e faz o navegador
# aceitar chamadas credenciadas de qualquer site.
_origins = os.getenv(
    "EOS_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
)
ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-ID"],
    max_age=600,
)

# Registra as rotas da API
app.include_router(router, prefix="/api")
app.include_router(integration_router, prefix="/api/integration")
app.add_middleware(TelemetryMiddleware)

@app.get("/api/status", tags=["health"])
async def status():
    """
    Identificação da API. Vive sob /api porque a raiz precisa entregar o
    dashboard: com `@app.get("/")` registrado, a rota vencia o StaticFiles e
    quem abrisse o site recebia este JSON em vez da interface.
    """
    return {
        "status": "online",
        "specification": "EngineeringOS v3.4.0",
        "message": "Welcome to the constitutional learning core.",
    }


@app.get("/health/live", tags=["health"])
async def health_live():
    """Liveness: o processo responde. Não toca o banco de propósito —
    se o banco cair, reiniciar o container não resolve nada."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def health_ready():
    """
    Readiness: a aplicação consegue MESMO atender — verifica o banco.
    É o que o orquestrador deve consultar antes de mandar tráfego.
    """
    from sqlalchemy import text
    from src.database import AsyncSessionLocal

    detalhes = {"database": "unknown"}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            kus = await session.execute(text("SELECT COUNT(*) FROM knowledge_units"))
            detalhes["database"] = "ok"
            detalhes["knowledge_units"] = kus.scalar_one()
    except Exception as e:  # noqa: BLE001
        detalhes["database"] = "erro"
        detalhes["detail"] = str(e)[:200]
        return JSONResponse(status_code=503, content={"status": "not_ready", **detalhes})

    return {"status": "ready", "environment": os.getenv("EOS_ENV", "development"), **detalhes}

# O dashboard é servido pelo próprio backend (mesma origem ⇒ o frontend usa
# "/api" relativo e não precisa de CORS). Montado por ÚLTIMO para não capturar
# /api/* nem /health/*, que já estão registrados acima.
frontend_path = os.path.join(os.path.dirname(__file__), "dashboard", "dist")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    @app.get("/")
    async def sem_dashboard():
        return {
            "status": "online",
            "message": "API no ar. Dashboard não compilado — rode "
                       "'npm run build' em dashboard/ para servi-lo aqui.",
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

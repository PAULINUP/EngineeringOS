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

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry()
    # Inicializa o banco de dados e cria tabelas no startup
    print("Inicializando banco de dados EngineeringOS...")
    await init_db()
    print("Banco de dados pronto.")
    yield

app = FastAPI(
    title="EngineeringOS API",
    version="2.0.0",
    description="Constitutional reference implementation of the EngineeringOS adaptive learning specification.",
    lifespan=lifespan
)

# Adiciona middleware de CORS para permitir acesso do React (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra as rotas da API
app.include_router(router, prefix="/api")
app.include_router(integration_router, prefix="/api/integration")
app.add_middleware(TelemetryMiddleware)

@app.get("/")
async def root():
    return {
        "status": "online",
        "specification": "EngineeringOS v2.0.0",
        "message": "Welcome to the constitutional learning core."
    }

# Serve React Dashboard from FastAPI (for Railway)
frontend_path = os.path.join(os.path.dirname(__file__), "dashboard", "dist")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

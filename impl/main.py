import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.database import init_db
from src.api import router

@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.get("/")
async def root():
    return {
        "status": "online",
        "specification": "EngineeringOS v2.0.0",
        "message": "Welcome to the constitutional learning core."
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

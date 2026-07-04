import os
from celery import Celery
import asyncio

# A URL do Redis será injetada pelo docker-compose.yml
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "engineeringos_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="process_cognitive_frontier")
def process_cognitive_frontier(self, learner_id: str, ku_id: str, new_mastery: float):
    """
    Desacopla a validação da fronteira do Conhecimento da Thread principal do FastAPI.
    Este worker consumirá o Jaccard Spread e a matriz do Neo4j em background.
    """
    # IMPORTANTE: Como Celery é síncrono e muito do nosso stack é assíncrono (asyncpg),
    # nós usamos asyncio.run para engatar as corrotinas matemáticas pesadas.
    from src.cognitive_engine import run_heavy_math_simulation
    
    try:
        # Chamada assíncrona encapsulada para o motor Neo4j/Cognitivo
        result = asyncio.run(run_heavy_math_simulation(learner_id, ku_id, new_mastery))
        return {"status": "success", "data": result}
    except Exception as exc:
        # Se ocorrer uma dependência cíclica não tratada ou erro de matriz, faz retry 
        raise self.retry(exc=exc, countdown=5, max_retries=3)

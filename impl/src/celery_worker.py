import os
import json
from celery import Celery
import asyncio

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
    """
    from src.cognitive_engine import run_heavy_math_simulation

    try:
        result = asyncio.run(run_heavy_math_simulation(learner_id, ku_id, new_mastery))
        return {"status": "success", "data": result}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@celery_app.task(bind=True, name="compute_learning_trajectory")
def compute_learning_trajectory(
    self,
    relations: list,
    all_kus_dict: dict,
    mastery_dict: dict,
    mission_required_kus: list,
    cost_weights: dict,
    mission_id: str,
    mission_label: str,
    terminal_threshold: float,
):
    """
    Executa optimize_learning_trajectory em background.
    O FastAPI devolve imediatamente o task_id; o React consulta /api/tasks/{task_id}.
    """
    from src import cognitive_engine

    try:
        dag = cognitive_engine.build_prerequisite_dag(relations)
        path = cognitive_engine.optimize_learning_trajectory(
            graph=dag,
            current_mastery=mastery_dict,
            all_kus_dict=all_kus_dict,
            relations=relations,
            mission_required_kus=mission_required_kus,
            cost_weights=cost_weights,
        )

        detailed_path = []
        for node_id in path:
            ku = all_kus_dict.get(node_id)
            if ku:
                detailed_path.append(ku)

        satisfied = all(
            mastery_dict.get(k, 0.0) >= terminal_threshold
            for k in mission_required_kus
        )

        return {
            "mission_id": mission_id,
            "label": mission_label,
            "path": detailed_path,
            "satisfied": satisfied,
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5, max_retries=3)

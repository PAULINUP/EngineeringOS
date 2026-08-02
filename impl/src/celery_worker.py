import os
import json
from celery import Celery
import asyncio

REDIS_URL = os.getenv("REDIS_URL", "").strip()

# Modo eager = a tarefa roda dentro do request, na mesma thread. A "fila"
# existia só no papel: o cálculo pesado bloqueava a resposta da API.
# Com REDIS_URL definido, o trabalho vai de fato para um worker separado.
# Sem Redis (desenvolvimento local, testes), cai para eager — que é honesto
# e continua funcionando, só que sem desacoplamento.
EAGER = not REDIS_URL or os.getenv("CELERY_ALWAYS_EAGER", "0") in ("1", "true")

celery_app = Celery(
    "engineeringos_worker",
    broker=REDIS_URL or None,
    backend=REDIS_URL or None,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=EAGER,
    task_eager_propagates=True,
    # A trajetória é cara; sem teto, uma tarefa travada segura o worker
    task_time_limit=300,
    task_soft_time_limit=240,
    result_expires=3600,
    worker_max_tasks_per_child=200,      # recicla o processo: evita vazamento
    broker_connection_retry_on_startup=True,
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

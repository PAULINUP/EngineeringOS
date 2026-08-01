"""
Testes de integração do EngineeringOS.

Cada teste aqui trava uma garantia que JÁ FOI QUEBRADA neste projeto. Eles
existem para que a mesma falha não volte silenciosamente:

  segurança  — identidade vinha do corpo da requisição (qualquer um escrevia
               no progresso de qualquer aluno); rotas destrutivas abertas
  pedagogia  — prereq_factor zerava o aprendizado; repetir o mesmo exercício
               validava a competência; auto-estudo passava do teto
  dados      — cadastro fragmentava em cópias do mesmo aluno

Execução:
    pytest tests/ -v
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

IMPL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IMPL))

# Banco isolado: nenhum teste toca o banco real
TEST_DB = IMPL / "test_integration.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["EOS_ENV"] = "development"
os.environ["BCRYPT_ROUNDS"] = "4"          # hashing rápido nos testes

from main import app                        # noqa: E402
from src.database import engine             # noqa: E402
from src.models import Base                 # noqa: E402


@pytest_asyncio.fixture(scope="function")
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as c:
        yield c


async def _registrar(client, nome: str, email: str, senha: str = "senhaSegura123"):
    r = await client.post("/auth/register", json={"name": nome, "email": email, "password": senha})
    assert r.status_code == 201, r.text
    return r.json()


async def _criar_ku(client, ku_id: str = "ku.teste.v1"):
    """Cria uma KU direto no banco (a API não expõe criação avulsa de KU)."""
    from src.database import AsyncSessionLocal
    from src import models
    async with AsyncSessionLocal() as db:
        db.add(models.KnowledgeUnit(
            id=ku_id, title="KU de teste", domain="teste", concept="teste",
            level="foundational", definition="unidade usada nos testes",
            element_interactivity=3,
        ))
        await db.commit()
    return ku_id


# ===========================================================================
# SEGURANÇA
# ===========================================================================
@pytest.mark.asyncio
async def test_registro_e_login(client):
    conta = await _registrar(client, "Ana", "ana@teste.com")
    assert conta["learner_id"] and conta["access_token"]

    r = await client.post("/auth/login", json={"email": "ana@teste.com", "password": "senhaSegura123"})
    assert r.status_code == 200

    r = await client.post("/auth/login", json={"email": "ana@teste.com", "password": "errada"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_nao_revela_quais_emails_existem(client):
    await _registrar(client, "Ana", "ana@teste.com")
    inexistente = await client.post("/auth/login", json={"email": "ninguem@teste.com", "password": "x" * 10})
    senha_errada = await client.post("/auth/login", json={"email": "ana@teste.com", "password": "x" * 10})
    assert inexistente.status_code == senha_errada.status_code == 401
    assert inexistente.json()["detail"] == senha_errada.json()["detail"]


@pytest.mark.asyncio
async def test_aluno_nao_escreve_no_progresso_de_outro(client):
    """A falha crítica: learner_id vinha do corpo e ninguém conferia o token."""
    ku = await _criar_ku(client)
    ana = await _registrar(client, "Ana", "ana@teste.com")
    bob = await _registrar(client, "Bob", "bob@teste.com")

    evidencia = {
        "learner_id": bob["learner_id"], "ku_id": ku, "type": "explanation",
        "source_weight": 0.4, "reviewer_agreement": 1.0, "recency_factor": 1.0, "reviewers": [],
    }
    r = await client.post("/evidence", json=evidencia,
                          headers={"Authorization": f"Bearer {ana['access_token']}"})
    assert r.status_code == 403

    evidencia["learner_id"] = ana["learner_id"]
    r = await client.post("/evidence", json=evidencia,
                          headers={"Authorization": f"Bearer {ana['access_token']}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rotas_destrutivas_exigem_admin(client):
    ana = await _registrar(client, "Ana", "ana@teste.com")
    r = await client.post("/seed", headers={"Authorization": f"Bearer {ana['access_token']}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_token_invalido_e_ausente(client):
    ku = await _criar_ku(client)
    corpo = {"learner_id": str(uuid.uuid4()), "ku_id": ku, "type": "explanation",
             "source_weight": 0.4, "reviewer_agreement": 1.0, "recency_factor": 1.0, "reviewers": []}
    # sem header e com token forjado: ambos negados (401 Unauthorized)
    assert (await client.post("/evidence", json=corpo)).status_code == 401
    assert (await client.post("/evidence", json=corpo,
            headers={"Authorization": "Bearer token.forjado"})).status_code == 401


# ===========================================================================
# INVARIANTES PEDAGÓGICAS
# ===========================================================================
@pytest.mark.asyncio
async def test_auto_estudo_nao_passa_do_teto_p9(client):
    """Auto-estudo pratica, não valida: trava em 0.60 por mais que se insista."""
    ku = await _criar_ku(client)
    ana = await _registrar(client, "Ana", "ana@teste.com")
    h = {"Authorization": f"Bearer {ana['access_token']}"}
    corpo = {"learner_id": ana["learner_id"], "ku_id": ku, "type": "explanation",
             "source_weight": 0.9,          # tenta forjar peso alto
             "reviewer_agreement": 1.0, "recency_factor": 1.0, "reviewers": []}

    for _ in range(20):
        r = await client.post("/evidence", json=corpo, headers=h)
        assert r.status_code == 200
        assert r.json()["confidence"] <= 0.4 + 1e-9      # servidor clampa o peso

    r = await client.get(f"/learners/{ana['learner_id']}/competences")
    mastery = r.json()[0]["mastery_score"]
    assert mastery <= 0.6 + 1e-6, f"auto-estudo passou do teto: {mastery}"


@pytest.mark.asyncio
async def test_evidencia_objetiva_sempre_move_a_maestria(client):
    """
    Regressão do deadlock: com prereq_factor multiplicativo, uma KU cujo
    pré-requisito estava zerado acumulava evidência com delta exatamente 0.
    """
    from src.database import AsyncSessionLocal
    from src import models

    base = await _criar_ku(client, "ku.base.v1")
    dependente = await _criar_ku(client, "ku.dependente.v1")
    async with AsyncSessionLocal() as db:
        db.add(models.KURelation(source_id=base, target_id=dependente,
                                 type="prerequisite", weight=1.0))
        await db.commit()

    ana = await _registrar(client, "Ana", "ana@teste.com")
    h = {"Authorization": f"Bearer {ana['access_token']}"}
    corpo = {"learner_id": ana["learner_id"], "ku_id": dependente, "type": "solution",
             "source_weight": 0.4, "reviewer_agreement": 1.0, "recency_factor": 1.0,
             "reviewers": []}

    await client.post("/evidence", json=corpo, headers=h)
    r = await client.get(f"/learners/{ana['learner_id']}/competences")
    estado = next(c for c in r.json() if c["ku_id"] == dependente)
    assert estado["mastery_score"] > 0, (
        "base zerada anulou o aprendizado — o deadlock voltou"
    )


@pytest.mark.asyncio
async def test_repetir_o_mesmo_exercicio_nao_valida(client):
    """P10: uma única origem satura em 0.60; validar exige exercícios distintos."""
    ku = await _criar_ku(client)
    ana = await _registrar(client, "Ana", "ana@teste.com")
    h = {"Authorization": f"Bearer {ana['access_token']}"}
    mesma_origem = {"learner_id": ana["learner_id"], "ku_id": ku, "type": "solution",
                    "source_weight": 0.6, "reviewer_agreement": 1.0, "recency_factor": 1.0,
                    "reviewers": [], "source_ref": "challenge:sempre-o-mesmo"}

    for _ in range(25):
        assert (await client.post("/evidence", json=mesma_origem, headers=h)).status_code == 200

    r = await client.get(f"/learners/{ana['learner_id']}/competences")
    mastery = r.json()[0]["mastery_score"]
    assert mastery < 0.85, f"repetir o mesmo exercício validou a KU ({mastery})"
    assert mastery <= 0.61, f"maestria passou do teto de uma origem única ({mastery})"


@pytest.mark.asyncio
async def test_cliente_nao_forja_evidencia_objetiva(client):
    """Peso >= 0.60 só nasce de processo verificável; cliente é clampado a 0.40."""
    ku = await _criar_ku(client)
    ana = await _registrar(client, "Ana", "ana@teste.com")
    r = await client.post("/evidence", headers={"Authorization": f"Bearer {ana['access_token']}"},
                          json={"learner_id": ana["learner_id"], "ku_id": ku, "type": "solution",
                                "source_weight": 1.0, "reviewer_agreement": 1.0,
                                "recency_factor": 1.0, "reviewers": [],
                                "source_ref": "challenge:forjado"})
    assert r.status_code == 200
    assert r.json()["confidence"] <= 0.4 + 1e-9


@pytest.mark.asyncio
async def test_exercicios_distintos_validam_pelo_fluxo_real(client):
    """
    O outro lado do P10, pelo caminho que um aluno percorre: responder
    desafios DIFERENTES corretamente leva a competência acima de theta.
    """
    from src.database import AsyncSessionLocal
    from src import models

    ku = await _criar_ku(client)
    desafios = []
    async with AsyncSessionLocal() as db:
        for i in range(4):
            c = models.Challenge(ku_id=ku, prompt=f"Quanto é {i}+{i}?", answer_type="numeric",
                                 expected_answer=str(i * 2), tolerance=0.01,
                                 feedback="ok", difficulty=0.5)
            db.add(c)
            desafios.append(c)
        await db.commit()
        for c in desafios:
            await db.refresh(c)
        ids_respostas = [(str(c.id), c.expected_answer) for c in desafios]

    ana = await _registrar(client, "Ana", "ana@teste.com")
    h = {"Authorization": f"Bearer {ana['access_token']}"}

    for _ in range(4):                       # revisões reforçam a convergência
        for cid, resposta in ids_respostas:
            r = await client.post(f"/challenges/{cid}/attempt",
                                  json={"learner_id": ana["learner_id"], "answer": resposta},
                                  headers=h)
            assert r.status_code == 200 and r.json()["correct"] is True

    r = await client.get(f"/learners/{ana['learner_id']}/competences")
    mastery = r.json()[0]["mastery_score"]
    assert mastery >= 0.85, f"4 exercícios distintos corretos não validaram ({mastery})"


@pytest.mark.asyncio
async def test_nao_responde_desafio_em_nome_de_outro(client):
    """A mesma regra de identidade vale para o corretor de desafios."""
    from src.database import AsyncSessionLocal
    from src import models

    ku = await _criar_ku(client)
    async with AsyncSessionLocal() as db:
        c = models.Challenge(ku_id=ku, prompt="1+1?", answer_type="numeric",
                             expected_answer="2", tolerance=0.01, feedback="ok", difficulty=0.5)
        db.add(c)
        await db.commit()
        await db.refresh(c)
        cid = str(c.id)

    ana = await _registrar(client, "Ana", "ana@teste.com")
    bob = await _registrar(client, "Bob", "bob@teste.com")
    r = await client.post(f"/challenges/{cid}/attempt",
                          json={"learner_id": bob["learner_id"], "answer": "2"},
                          headers={"Authorization": f"Bearer {ana['access_token']}"})
    assert r.status_code == 403


# ===========================================================================
# INTEGRIDADE DE DADOS
# ===========================================================================
@pytest.mark.asyncio
async def test_cadastro_nao_fragmenta(client):
    """O banco chegou a ter 20 cópias do mesmo aluno, cada uma com um pedaço."""
    await _registrar(client, "Ana", "ana@teste.com")
    r = await client.post("/auth/register",
                          json={"name": "Ana", "email": "outra@teste.com", "password": "senhaSegura123"})
    assert r.status_code == 409

    r = await client.get("/learners")
    assert len([l for l in r.json() if l["name"] == "Ana"]) == 1

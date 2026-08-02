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


def test_nenhuma_rota_pede_request_como_query():
    """
    O FastAPI lê `call.__globals__` para resolver anotações de dependência.
    Instância de classe não tem `__globals__`; com anotações adiadas o
    `request: Request` do rate limiter virava parâmetro de QUERY e TODA rota
    limitada respondia 422 — login, registro e correção de desafio inclusive.
    Depende de versão de Python, então passa despercebido até não passar.
    """
    from main import app

    quebradas = []
    for rota in app.routes:
        dependant = getattr(rota, "dependant", None)
        if dependant is None:
            continue
        pendentes = [dependant]
        while pendentes:
            d = pendentes.pop()
            for p in d.query_params:
                if p.name == "request":
                    quebradas.append(f"{getattr(rota, 'path', '?')} ({d.call})")
            pendentes.extend(d.dependencies)

    assert not quebradas, "dependências com Request não resolvido: " + "; ".join(quebradas)


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
# QUALIDADE DO CATÁLOGO
# ===========================================================================
def test_fracao_e_um_valor_so():
    """
    "2/3" é um número. Lido como dois, o gabarito de 45 desafios importados
    virou o conjunto "2;3" e nenhuma resposta certa passava.
    """
    from src.cce import grade_answer

    assert grade_answer("numeric", "0.666667", 0.01, "2/3")[0]
    assert grade_answer("numeric", "0.666667", 0.01, "0,67")[0]        # vírgula decimal
    assert grade_answer("numeric", "7.59375", 0.01, "243 / 32")[0]
    assert not grade_answer("numeric", "0.666667", 0.01, "3")[0]


def test_separador_de_milhar_nao_engole_lista():
    """
    "(a) 5, 125" virou o número 5125 — resposta que não existe em lugar
    nenhum. O espaço antes da vírgula é o que distingue número mutilado
    ("2 , 162") de vírgula de lista ("5, 125").
    """
    from tools.openstax_exercises import clean_math_html

    assert clean_math_html("2 , 162") == "2162"
    assert clean_math_html("2,162") == "2162"
    assert clean_math_html("(a) 5, 125") == "(a) 5, 125"


def test_resposta_em_partes_nao_vira_desafio():
    """Duas perguntas fundidas num gabarito só não têm resposta certa."""
    from tools.openstax_exercises import profile_challenge

    enunciado = "Determine quais dos seguintes números são inteiros: 0, 5, 125."
    assert profile_challenge(enunciado, "(a) 7, 9 (b) 11") is None
    assert profile_challenge(enunciado, "42") is not None


@pytest.mark.asyncio
async def test_denuncia_com_quorum_tira_o_desafio_do_ar(client):
    """
    Sem professores, quem julga o conteúdo é o conjunto dos alunos — mas um
    clique isolado não apaga material de todo mundo.
    """
    from src.api import QUORUM_DENUNCIA
    from src.database import AsyncSessionLocal
    from src import models

    ku = await _criar_ku(client)
    async with AsyncSessionLocal() as db:
        c = models.Challenge(ku_id=ku, prompt="enunciado corrompido", answer_type="numeric",
                             expected_answer="5125", tolerance=0.01, feedback="", difficulty=0.5)
        db.add(c)
        await db.commit()
        await db.refresh(c)
        cid = str(c.id)

    alunos = [await _registrar(client, f"Aluno{i}", f"aluno{i}@teste.com")
              for i in range(QUORUM_DENUNCIA)]

    for i, aluno in enumerate(alunos, start=1):
        h = {"Authorization": f"Bearer {aluno['access_token']}"}
        r = await client.post(f"/challenges/{cid}/report",
                              json={"learner_id": aluno["learner_id"], "reason": "gabarito impossível"},
                              headers=h)
        assert r.status_code == 200
        assert r.json()["reports"] == i
        # só o último cruza o quórum
        assert r.json()["quarantined"] is (i >= QUORUM_DENUNCIA)

    # em quarentena: some da listagem e não gera mais evidência
    r = await client.get(f"/kus/{ku}/challenges")
    assert cid not in [c["id"] for c in r.json()]

    h = {"Authorization": f"Bearer {alunos[0]['access_token']}"}
    r = await client.post(f"/challenges/{cid}/attempt",
                          json={"learner_id": alunos[0]["learner_id"], "answer": "5125"},
                          headers=h)
    assert r.status_code == 410


@pytest.mark.asyncio
async def test_denuncia_repetida_nao_conta_duas_vezes(client):
    """Um aluno, um voto — senão o quórum é decorativo."""
    from src.database import AsyncSessionLocal
    from src import models

    ku = await _criar_ku(client)
    async with AsyncSessionLocal() as db:
        c = models.Challenge(ku_id=ku, prompt="x", answer_type="numeric",
                             expected_answer="1", tolerance=0.01, feedback="", difficulty=0.5)
        db.add(c)
        await db.commit()
        await db.refresh(c)
        cid = str(c.id)

    ana = await _registrar(client, "Ana", "ana@teste.com")
    h = {"Authorization": f"Bearer {ana['access_token']}"}
    for _ in range(5):
        r = await client.post(f"/challenges/{cid}/report",
                              json={"learner_id": ana["learner_id"], "reason": ""},
                              headers=h)
        assert r.status_code == 200
        assert r.json()["reports"] == 1
        assert r.json()["quarantined"] is False


@pytest.mark.asyncio
async def test_apagar_desafio_exige_admin(client):
    """
    O catálogo é compartilhado: apagar aqui apaga para todos. Antes desta
    checagem a rota não pedia sequer autenticação.
    """
    from src.database import AsyncSessionLocal
    from src import models

    ku = await _criar_ku(client)
    async with AsyncSessionLocal() as db:
        c = models.Challenge(ku_id=ku, prompt="x", answer_type="numeric",
                             expected_answer="1", tolerance=0.01, feedback="", difficulty=0.5)
        db.add(c)
        await db.commit()
        await db.refresh(c)
        cid = str(c.id)

    assert (await client.delete(f"/challenges/{cid}")).status_code == 401

    ana = await _registrar(client, "Ana", "ana@teste.com")
    r = await client.delete(f"/challenges/{cid}",
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

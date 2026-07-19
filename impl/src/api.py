import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, field_validator

from src.database import get_session
from src import models
from src.eos_parser import parse_dsl_content
from src import cognitive_engine
from src.memory_framework import MemoryManager
from src.integration import mock_webhooks_db
from src.curriculum_seed import seed_user_curriculum, seed_challenge_bank
from src.cce import grade_answer, AUTO_GRADED_SOURCE_WEIGHT
from src.security import verify_token, create_access_token
import httpx
import asyncio

logger = logging.getLogger("api")

router = APIRouter()

# ===========================================================================
# Pydantic Schemas

class LearnerCreate(BaseModel):
    name: str

class LearnerResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class CompetenceResponse(BaseModel):
    ku_id: str
    mastery_score: float
    confidence: float
    decay_factor: float
    effective_mastery: float
    last_updated: datetime.datetime

class EvidenceSubmit(BaseModel):
    learner_id: uuid.UUID
    ku_id: str = Field(..., max_length=255)
    type: str = Field(..., max_length=50)
    source_weight: float = Field(0.4, ge=0.0, le=1.0)
    reviewer_agreement: float = Field(1.0, ge=0.0, le=1.0)
    recency_factor: float = Field(1.0, ge=0.0, le=1.0)
    reviewers: List[Dict[str, Any]] = Field(default=[], max_length=10)

    @field_validator('source_weight', 'reviewer_agreement', 'recency_factor')
    @classmethod
    def reject_non_finite(cls, v: float) -> float:
        import math
        if not math.isfinite(v):
            raise ValueError('Value must be finite')
        return v

class EvidenceResponse(BaseModel):
    id: uuid.UUID
    learner_id: uuid.UUID
    ku_id: str
    type: str
    confidence: float
    status: str
    timestamp: datetime.datetime

# ===========================================================================
# API Endpoints

class TokenRequest(BaseModel):
    username: str
    password: str

@router.post("/token")
async def login_for_access_token(data: TokenRequest):
    # Rota de desenvolvimento: aceita qualquer username/password e gera um token JWT
    token = create_access_token(data={"sub": data.username, "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/learners", response_model=LearnerResponse)
async def create_learner(
    data: LearnerCreate,
    db: AsyncSession = Depends(get_session),
    token: dict = Depends(verify_token)
):
    learner = models.Learner(name=data.name)
    db.add(learner)
    await db.commit()
    await db.refresh(learner)
    return learner

@router.get("/learners", response_model=List[LearnerResponse])
async def list_learners(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(models.Learner))
    return result.scalars().all()

@router.get("/learners/{learner_id}/competences", response_model=List[CompetenceResponse])
async def get_learner_competences(learner_id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    # Verifica se o learner existe
    learner = await db.get(models.Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner não encontrado")
    
    result = await db.execute(
        select(models.Competence).where(models.Competence.learner_id == learner_id)
    )
    return result.scalars().all()

@router.get("/kus")
async def list_kus(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(models.KnowledgeUnit))
    return result.scalars().all()

@router.get("/missions")
async def list_missions(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(models.Mission))
    return result.scalars().all()

@router.get("/graph")
async def get_graph_data(learner_id: Optional[uuid.UUID] = None, db: AsyncSession = Depends(get_session)):
    """Retorna os nós (KUs) e arestas (Relações) formatados para renderização no grafo do dashboard."""
    # Busca KUs e Relações
    ku_result = await db.execute(select(models.KnowledgeUnit))
    kus = ku_result.scalars().all()
    
    rel_result = await db.execute(select(models.KURelation))
    relations = rel_result.scalars().all()
    
    # Busca estados do learner se fornecido
    states_dict = {}
    if learner_id:
        states_result = await db.execute(
            select(models.Competence).where(models.Competence.learner_id == learner_id)
        )
        for state in states_result.scalars().all():
            states_dict[state.ku_id] = state
            
    nodes = []
    for ku in kus:
        state = states_dict.get(ku.id)
        nodes.append({
            "id": ku.id,
            "title": ku.title,
            "domain": ku.domain,
            "concept": ku.concept,
            "level": ku.level,
            "definition": ku.definition,
            "element_interactivity": ku.element_interactivity,
            "mastery_score": state.mastery_score if state else 0.0,
            "effective_mastery": state.effective_mastery if state else 0.0,
            "confidence": state.confidence if state else 0.0,
            "decay_factor": state.decay_factor if state else 0.0,
            "mastery": state.mastery_score if state else 0.0 # kept for backward compatibility with graph visualizer
        })
        
    edges = []
    for rel in relations:
        edges.append({
            "id": rel.id,
            "source": rel.source_id,
            "target": rel.target_id,
            "type": rel.type,
            "weight": rel.weight
        })
        
    return {"nodes": nodes, "edges": edges}

@router.get("/learners/{learner_id}/frontier")
async def get_learner_frontier(learner_id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    # Carrega relações e KUs para montar o DAG
    rel_res = await db.execute(select(models.KURelation))
    relations = [{"source_id": r.source_id, "target_id": r.target_id, "type": r.type} for r in rel_res.scalars().all()]
    dag = cognitive_engine.build_prerequisite_dag(relations)
    
    ku_res = await db.execute(select(models.KnowledgeUnit.id))
    all_kus = [ku[0] for ku in ku_res.all()]
    
    # Carrega maestria atual
    states_res = await db.execute(
        select(models.Competence).where(models.Competence.learner_id == learner_id)
    )
    mastery_dict = {state.ku_id: state.mastery_score for state in states_res.scalars().all()}
    
    frontier_ids = cognitive_engine.get_knowledge_frontier(dag, mastery_dict, all_kus)
    
    # Retorna detalhes completos da fronteira
    if frontier_ids:
        ku_details_res = await db.execute(
            select(models.KnowledgeUnit).where(models.KnowledgeUnit.id.in_(frontier_ids))
        )
        return ku_details_res.scalars().all()
    return []

@router.get("/learners/{learner_id}/missions/{mission_id}/path")
async def get_mission_path(
    learner_id: uuid.UUID,
    mission_id: str,
    db: AsyncSession = Depends(get_session)
):
    mission = await db.get(models.Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Missão não encontrada")
        
    # Carrega dados do banco
    rel_res = await db.execute(select(models.KURelation))
    relations_models = rel_res.scalars().all()
    relations = [{"source_id": r.source_id, "target_id": r.target_id, "type": r.type, "weight": r.weight} for r in relations_models]
    
    ku_res = await db.execute(select(models.KnowledgeUnit))
    kus = ku_res.scalars().all()
    all_kus_dict = {
        ku.id: {
            "id": ku.id,
            "title": ku.title,
            "level": ku.level,
            "element_interactivity": ku.element_interactivity,
            "definition": ku.definition,
        }
        for ku in kus
    }
    
    # Carrega maestria actual
    states_res = await db.execute(
        select(models.Competence).where(models.Competence.learner_id == learner_id)
    )
    mastery_dict = {state.ku_id: state.mastery_score for state in states_res.scalars().all()}
    
    # Despacha para o Celery (agora em modo Eager - sincrono)
    from src.celery_worker import compute_learning_trajectory
    task = compute_learning_trajectory.delay(
        relations=relations,
        all_kus_dict=all_kus_dict,
        mastery_dict=mastery_dict,
        mission_required_kus=mission.required_kus,
        cost_weights=mission.cost_weights,
        mission_id=mission.id,
        mission_label=mission.label,
        terminal_threshold=mission.terminal_threshold,
    )
    
    return task.result
@router.get("/tasks/{task_id}")
async def get_task_result(task_id: str):
    """Consulta o resultado de uma tarefa assíncrona despachada pelo Celery."""
    from src.celery_worker import celery_app
    result = celery_app.AsyncResult(task_id)
    if result.ready():
        return {"status": "completed", "result": result.get(timeout=1)}
    elif result.failed():
        return {"status": "failed", "error": str(result.result)}
    else:
        return {"status": "processing", "task_id": task_id}

@router.post("/evidence", response_model=EvidenceResponse)
async def submit_evidence(
    data: EvidenceSubmit, 
    db: AsyncSession = Depends(get_session),
    token: dict = Depends(verify_token)
):
    """
    Registra uma nova evidência no banco após checar validações do Motor Cognitivo.
    ROTA PROTEGIDA: Apenas agentes/usuários autenticados podem submeter evidência.
    """
    learner = await db.get(models.Learner, data.learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner não encontrado")
        
    ku = await db.get(models.KnowledgeUnit, data.ku_id)
    if not ku:
        raise HTTPException(status_code=404, detail="KnowledgeUnit não encontrada")
        
    # Calcula a confiança individual deste registro
    conf = cognitive_engine.calculate_evidence_confidence(
        data.source_weight, data.reviewer_agreement, data.recency_factor
    )
    
    # Decide o status do registro com base nos thresholds da especificação (Definition 10.4)
    # Se houver reviewers, podemos computar o status
    status = "pending"
    if conf >= 0.85:
        status = "validated"
    elif conf < 0.40:
        status = "rejected"
    elif 0.40 <= conf < 0.60:
        status = "contested"
        
    # Salva o registro de evidência no banco
    record = models.EvidenceRecord(
        learner_id=data.learner_id,
        ku_id=data.ku_id,
        type=data.type,
        source_weight=data.source_weight,
        reviewer_agreement=data.reviewer_agreement,
        recency_factor=data.recency_factor,
        confidence=conf,
        reviewers=data.reviewers,
        status=status
    )
    db.add(record)
    await db.flush()
    
    curr_state = None
    # Se a evidência for válida, atualiza a maestria do Learner usando a função de aprendizado
    if status == "validated" or conf >= 0.60:
        # Busca todas as evidências deste learner para esta KU para fazer a agregação (Definition 10.3)
        ev_result = await db.execute(
            select(models.EvidenceRecord).where(
                models.EvidenceRecord.learner_id == data.learner_id,
                models.EvidenceRecord.ku_id == data.ku_id
            )
        )
        all_evs = ev_result.scalars().all()
        ev_list = [
            {"source_weight": e.source_weight, "reviewer_agreement": e.reviewer_agreement, "recency_factor": e.recency_factor}
            for e in all_evs
        ]
        conf_agg = cognitive_engine.aggregate_evidence_confidence(ev_list)
        
        # Carrega pré-requisitos para computar delta e delta factor
        rel_result = await db.execute(
            select(models.KURelation).where(models.KURelation.target_id == data.ku_id, models.KURelation.type == "prerequisite")
        )
        prereq_ids = [rel.source_id for rel in rel_result.scalars().all()]
        
        # Carrega estados dos pré-requisitos
        prereq_masteries = []
        if prereq_ids:
            st_result = await db.execute(
                select(models.Competence).where(
                    models.Competence.learner_id == data.learner_id,
                    models.Competence.ku_id.in_(prereq_ids)
                )
            )
            states = {st.ku_id: st.mastery_score for st in st_result.scalars().all()}
            for pid in prereq_ids:
                prereq_masteries.append(states.get(pid, 0.0))
        else:
            prereq_masteries = [1.0] # se não há pré-requisitos, delta factor é 1.0
            
        prereq_factor = 1.0
        for m in prereq_masteries:
            prereq_factor *= m # produto de maestrias
            
        # Carrega estado atual
        curr_state_res = await db.execute(
            select(models.Competence).where(
                models.Competence.learner_id == data.learner_id,
                models.Competence.ku_id == data.ku_id
            )
        )
        curr_state = curr_state_res.scalar_one_or_none()
        current_mastery = curr_state.mastery_score if curr_state else 0.0
        
        # Calcula taxa de aprendizado efetiva considerando transferência semântica (Definition 13.2)
        # Carrega KUs validadas do learner para computar transferência
        validated_states_res = await db.execute(
            select(models.Competence).where(
                models.Competence.learner_id == data.learner_id,
                models.Competence.mastery_score >= 0.85
            )
        )
        validated_kus = {st.ku_id: st.mastery_score for st in validated_states_res.scalars().all()}
        
        # Carrega todas as relações para calcular os coeficientes de transferência
        all_rels_res = await db.execute(select(models.KURelation))
        all_rels_models = all_rels_res.scalars().all()
        all_rels = [{"source_id": r.source_id, "target_id": r.target_id, "type": r.type, "weight": r.weight} for r in all_rels_models]
        dag = cognitive_engine.build_prerequisite_dag(all_rels)
        
        base_eta = 0.4 # taxa de aprendizado base
        max_transfer = 0.0
        for val_id in validated_kus:
            rel_type = "none"
            for r in all_rels:
                if r["source_id"] == val_id and r["target_id"] == data.ku_id:
                    rel_type = r["type"]
                    break
                elif r["target_id"] == val_id and r["source_id"] == data.ku_id:
                    if r["type"] == "extends":
                        rel_type = "extended_by"
                    break
            
            trans = cognitive_engine.calculate_transfer_coefficient(dag, val_id, data.ku_id, rel_type)
            if trans > max_transfer:
                max_transfer = trans
                
        eta_eff = base_eta * (1.0 + max_transfer)
        
        # Calcula novo nível de maestria
        delta = cognitive_engine.calculate_learning_delta(current_mastery, conf_agg, prereq_factor, eta_eff)
        new_mastery = min(1.0, max(0.0, current_mastery + delta))
        
        # Novo cálculo de competência v3.0.0
        decay = 0.05
        eff_mastery = new_mastery * (1.0 - decay)
        
        # Atualiza ou cria o registro Competence
        if not curr_state:
            curr_state = models.Competence(
                learner_id=data.learner_id,
                ku_id=data.ku_id,
                mastery_score=new_mastery,
                confidence=conf_agg,
                decay_factor=decay,
                effective_mastery=eff_mastery
            )
            db.add(curr_state)
        else:
            if new_mastery > curr_state.mastery_score:
                curr_state.mastery_score = new_mastery
            curr_state.confidence = conf_agg
            curr_state.effective_mastery = curr_state.mastery_score * (1.0 - curr_state.decay_factor)
                
    await db.commit()
    await db.refresh(record)
    if curr_state:
        await db.refresh(curr_state)
    
    # ---------------------------------------------------------
    # TRIGGER MEMORY FRAMEWORK AND WEBHOOKS (TELEMETRY/GIT SYNC)
    # ---------------------------------------------------------
    if status == "validated" or conf >= 0.60:
        # 1. Audit log via banco de dados (sem ficheiros JSON)
        try:
            mm = MemoryManager()
            audit = await mm.get_full_state(db)
            logger.info("Audit snapshot after evidence %s: %s", record.id, audit)
        except Exception as e:
            logger.warning("Audit snapshot failed: %s", e)
            
        # 2. Trigger Registered Webhooks (Integration)
        async def trigger_webhooks():
            async with httpx.AsyncClient() as client:
                for webhook_id, url in mock_webhooks_db.items():
                    try:
                        await client.post(url, json={"event": "competence_validated", "ku_id": data.ku_id, "learner_id": str(data.learner_id)})
                    except Exception as e:
                        print(f"Webhook {url} failed: {e}")
                        
        asyncio.create_task(trigger_webhooks())
        
    return record
@router.post("/seed")
async def seed_database(
    db: AsyncSession = Depends(get_session),
    token: dict = Depends(verify_token)
):
    """Limpa e popula o banco de dados com a estrutura de exemplo do EngineeringOS (Linear Algebra & ML)."""
    # 1. Limpa tabelas
    await db.execute(delete(models.KURelation))
    await db.execute(delete(models.ku_skill_association))
    await db.execute(delete(models.ku_topic_association))
    await db.execute(delete(models.EvidenceRecord))
    await db.execute(delete(models.Competence))
    await db.execute(delete(models.KnowledgeUnit))
    await db.execute(delete(models.Skill))
    await db.execute(delete(models.Topic))
    await db.execute(delete(models.Mission))
    await db.commit()
    
    # 2. Define DSLs padrão de exemplo
    dsl_content = """
    # Skills
    SKILL skill.compute {
        label: "Calcular operações matemáticas"
        domain: "mathematics"
    }
    SKILL skill.explain {
        label: "Explicar conceitos intuitivos e formalismos"
        domain: "mathematics"
    }
    SKILL skill.verify {
        label: "Verificar exatidão de provas e resultados"
        domain: "mathematics"
    }

    # Topics
    TOPIC topic.linear_algebra {
        label: "Álgebra Linear"
        domain: "mathematics"
    }
    TOPIC topic.calculus {
        label: "Cálculo"
        domain: "mathematics"
    }
    TOPIC topic.ml {
        label: "Machine Learning"
        domain: "computer_science"
    }

    # KUs
    KNOWLEDGE linear_algebra.matrix_definition.v1 {
        title: "Definição de Matrizes"
        domain: "linear_algebra"
        level: "foundational"
        definition: "Estruturas retangulares bidimensionais de números ordenados em linhas e colunas."
        element_interactivity: 2
        sources: [
            { type: "academic", reference: "Strang, G. (2016). Intro to Linear Algebra", weight: 1.0 }
        ]
    }

    KNOWLEDGE linear_algebra.dot_product.v1 {
        title: "Produto Escalar"
        domain: "linear_algebra"
        level: "foundational"
        definition: "Operação algébrica que toma duas sequências de números de mesmo comprimento e retorna um único número."
        element_interactivity: 3
        sources: [
            { type: "academic", reference: "Strang, G. (2016). Intro to Linear Algebra", weight: 1.0 }
        ]
    }

    KNOWLEDGE linear_algebra.matrix_multiplication.v1 {
        title: "Multiplicação de Matrizes"
        domain: "linear_algebra"
        level: "intermediate"
        definition: "Operação linear (A.B)ij = sum_k Aik.Bkj para matrizes compatíveis."
        prerequisites: [
            linear_algebra.matrix_definition.v1,
            linear_algebra.dot_product.v1
        ]
        element_interactivity: 4
        sources: [
            { type: "academic", reference: "Strang, G. (2016). Intro to Linear Algebra", weight: 1.0 }
        ]
    }

    KNOWLEDGE linear_algebra.eigenvalues.v1 {
        title: "Autovalores e Autovetores"
        domain: "linear_algebra"
        level: "advanced"
        definition: "Escalares e vetores não-nulos tais que A.v = lambda.v."
        prerequisites: [
            linear_algebra.matrix_multiplication.v1
        ]
        element_interactivity: 5
        sources: [
            { type: "academic", reference: "Strang, G. (2016). Intro to Linear Algebra", weight: 1.0 }
        ]
    }

    KNOWLEDGE calculus.partial_derivatives.v1 {
        title: "Derivadas Parciais"
        domain: "calculus"
        level: "intermediate"
        definition: "Derivadas de funções de múltiplas variáveis em relação a uma única variável, mantendo as demais constantes."
        element_interactivity: 4
        sources: [
            { type: "academic", reference: "Stewart, J. (2015). Calculus", weight: 1.0 }
        ]
    }

    KNOWLEDGE ml.gradient_descent.v1 {
        title: "Gradiente Descendente"
        domain: "ml"
        level: "advanced"
        definition: "Algoritmo de otimização de primeira ordem para encontrar mínimos de funções de custo."
        prerequisites: [
            linear_algebra.matrix_multiplication.v1,
            calculus.partial_derivatives.v1
        ]
        element_interactivity: 6
        sources: [
            { type: "academic", reference: "Goodfellow et al. (2016). Deep Learning", weight: 1.0 }
        ]
    }

    # Missions
    MISSION ml_foundations.v1 {
        label: "Machine Learning Foundations"
        required_kus: [
            linear_algebra.matrix_definition.v1,
            linear_algebra.dot_product.v1,
            linear_algebra.matrix_multiplication.v1,
            linear_algebra.eigenvalues.v1,
            calculus.partial_derivatives.v1,
            ml.gradient_descent.v1
        ]
        terminal_threshold: 0.85
        critical_kus: [
            ml.gradient_descent.v1
        ]
        critical_threshold: 0.90
        cost_weights: {
            alpha: 0.4,
            beta: 0.3,
            gamma: 0.3
        }
    }
    """
    
    declarations = parse_dsl_content(dsl_content)
    
    # Listas temporárias para mapear os links
    ku_objs = {}
    prereqs_map = {}
    
    # 3. Adiciona as entidades parseadas
    for dec in declarations:
        dtype = dec["type"]
        did = dec["id"]
        data = dec["data"]
        
        if dtype == "SKILL":
            skill = models.Skill(id=did, label=data["label"], domain=data["domain"])
            db.add(skill)
            
        elif dtype == "TOPIC":
            topic = models.Topic(id=did, label=data["label"], domain=data["domain"])
            db.add(topic)
            
        elif dtype == "KNOWLEDGE":
            ku = models.KnowledgeUnit(
                id=did,
                title=data["title"],
                domain=data["domain"],
                concept=did.split(".")[1], # e.g. matrix_multiplication
                level=data["level"],
                definition=data["definition"],
                element_interactivity=data.get("element_interactivity", 4),
                domain_decay_rate=data.get("domain_decay_rate", 0.05),
                sources=data.get("sources", [])
            )
            db.add(ku)
            ku_objs[did] = ku
            
            # Guarda pré-requisitos para processamento posterior
            if "prerequisites" in data:
                prereqs_map[did] = data["prerequisites"]
                
        elif dtype == "MISSION":
            mission = models.Mission(
                id=did,
                label=data["label"],
                required_kus=data["required_kus"],
                terminal_threshold=data.get("terminal_threshold", 0.85),
                critical_kus=data.get("critical_kus", []),
                critical_threshold=data.get("critical_threshold", 0.90),
                cost_weights=data.get("cost_weights", {"alpha": 0.4, "beta": 0.3, "gamma": 0.3})
            )
            db.add(mission)
            
    await db.flush()
    
    # 4. Adiciona as relações de pré-requisitos
    for ku_id, prereqs in prereqs_map.items():
        for pr_id in prereqs:
            relation = models.KURelation(
                source_id=pr_id,
                target_id=ku_id,
                type="prerequisite",
                weight=1.0
            )
            db.add(relation)
            
    # 5. Adiciona conexões implícitas com tópicos com base no domínio
    for ku_id, ku in ku_objs.items():
        # Associa com tópicos correspondentes ao domínio
        target_topic = ""
        if ku.domain == "linear_algebra":
            target_topic = "topic.linear_algebra"
        elif ku.domain == "calculus":
            target_topic = "topic.calculus"
        elif ku.domain == "ml":
            target_topic = "topic.ml"
            
        if target_topic:
            await db.execute(models.ku_topic_association.insert().values(ku_id=ku.id, topic_id=target_topic))
                
        # Associa skills genéricas
        await db.execute(models.ku_skill_association.insert().values(ku_id=ku.id, skill_id="skill.compute"))
        await db.execute(models.ku_skill_association.insert().values(ku_id=ku.id, skill_id="skill.explain"))
            
    await db.commit()

    # Repovoa o banco de desafios do CCE para as KUs recém-criadas
    await db.execute(delete(models.Challenge))
    await db.commit()
    n_challenges = await seed_challenge_bank(db)
    return {"message": f"Database seeded via DSL ({n_challenges} desafios CCE)."}

@router.post("/seed-curriculum")
async def seed_curriculum_endpoint(
    db: AsyncSession = Depends(get_session),
    token: dict = Depends(verify_token)
):
    """Limpa e popula o banco de dados com a grade curricular de Engenharia de Computação do aluno e os Materiais Base."""
    await db.execute(delete(models.StudyMaterial))
    await db.execute(delete(models.KURelation))
    await db.execute(delete(models.KnowledgeUnit))
    await db.execute(delete(models.Mission))
    await db.commit()
    
    await seed_user_curriculum(db)
    return {"message": "Computer Engineering Curriculum seeded successfully with infinite materials."}

@router.get("/kus/{ku_id}/materials")
async def get_ku_materials(ku_id: str, db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(models.StudyMaterial).where(models.StudyMaterial.ku_id == ku_id))
    materials = res.scalars().all()
    return materials

class MaterialCreate(BaseModel):
    title: str = Field(..., max_length=255)
    type: str = Field(..., max_length=50)  # video, pdf, article, link
    url: Optional[str] = Field(None, max_length=1000)
    content: Optional[str] = None
    quality_score: float = Field(1.0, ge=0.0, le=1.0)

@router.post("/kus/{ku_id}/materials")
async def add_ku_material(
    ku_id: str,
    data: MaterialCreate,
    db: AsyncSession = Depends(get_session),
    token: dict = Depends(verify_token),
):
    """Cadastra um material de estudo (Base Infinita) para uma KU existente."""
    ku = await db.get(models.KnowledgeUnit, ku_id)
    if not ku:
        raise HTTPException(status_code=404, detail="KnowledgeUnit não encontrada")
    material = models.StudyMaterial(
        ku_id=ku_id,
        title=data.title,
        type=data.type,
        url=data.url,
        content=data.content or "",
        quality_score=data.quality_score,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material

# ===========================================================================
# CCE — Desafios corrigidos pelo servidor
# ===========================================================================

class ChallengeResponse(BaseModel):
    """Desafio exposto ao cliente. A resposta esperada NUNCA sai do servidor."""
    id: uuid.UUID
    ku_id: str
    prompt: str
    answer_type: str
    difficulty: float

    class Config:
        from_attributes = True

class AttemptRequest(BaseModel):
    learner_id: uuid.UUID
    answer: str = Field(..., max_length=5000)

@router.get("/kus/{ku_id}/challenges", response_model=List[ChallengeResponse])
async def get_ku_challenges(ku_id: str, db: AsyncSession = Depends(get_session)):
    """Lista os desafios de uma KU (sem os gabaritos)."""
    res = await db.execute(
        select(models.Challenge).where(models.Challenge.ku_id == ku_id).order_by(models.Challenge.difficulty)
    )
    return res.scalars().all()

@router.post("/challenges/{challenge_id}/attempt")
async def attempt_challenge(
    challenge_id: uuid.UUID,
    data: AttemptRequest,
    db: AsyncSession = Depends(get_session),
    token: dict = Depends(verify_token),
):
    """
    Corrige a resposta no servidor (CCE). Se correta, gera um EvidenceRecord
    com peso de benchmark reprodutível (0.60) — o aluno não declara o próprio
    peso. Pela agregação noisy-OR, ~3 desafios distintos corretos cruzam θ=0.85.
    """
    challenge = await db.get(models.Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Desafio não encontrado")

    learner = await db.get(models.Learner, data.learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner não encontrado")

    correct, detail = grade_answer(
        challenge.answer_type, challenge.expected_answer, challenge.tolerance, data.answer
    )

    # Registra a tentativa como Assessment (auditoria de todas as tentativas)
    db.add(models.Assessment(
        challenge_id=str(challenge.id),
        agent_id=str(data.learner_id),
        response=data.answer[:5000],
        rubric_id=f"auto:{challenge.answer_type}",
        score=1.0 if correct else 0.0,
        reasoning_mode="auto_graded",
    ))
    await db.commit()

    evidence_status = None
    new_mastery = None
    if correct:
        # Reusa o pipeline constitucional de evidência (noisy-OR + delta de aprendizado)
        record = await submit_evidence(
            EvidenceSubmit(
                learner_id=data.learner_id,
                ku_id=challenge.ku_id,
                type="solution",
                source_weight=AUTO_GRADED_SOURCE_WEIGHT,
                reviewer_agreement=1.0,
                recency_factor=1.0,
                reviewers=[{
                    "reviewer_id": "cce_auto_grader",
                    "reviewer_type": "machine",
                    "verdict": "accept",
                }],
            ),
            db=db,
            token=token,
        )
        evidence_status = record.status

        state = await db.execute(
            select(models.Competence).where(
                models.Competence.learner_id == data.learner_id,
                models.Competence.ku_id == challenge.ku_id,
            )
        )
        comp = state.scalar_one_or_none()
        new_mastery = comp.mastery_score if comp else None

    return {
        "correct": correct,
        "detail": detail,
        "feedback": challenge.feedback if correct else None,
        "evidence_status": evidence_status,
        "new_mastery": new_mastery,
    }

@router.post("/seed-challenges")
async def seed_challenges_endpoint(
    db: AsyncSession = Depends(get_session),
    token: dict = Depends(verify_token),
):
    """Insere o banco de desafios padrão para as KUs existentes (idempotente)."""
    inserted = await seed_challenge_bank(db)
    return {"message": f"{inserted} desafios inseridos."}

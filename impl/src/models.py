import datetime
import uuid
from typing import Any, List, Optional
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Table,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# Tabela de associação entre KUs e Skills
ku_skill_association = Table(
    "ku_skill_links",
    Base.metadata,
    Column("ku_id", String(255), ForeignKey("knowledge_units.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String(255), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)

# Tabela de associação entre KUs e Topics
ku_topic_association = Table(
    "ku_topic_links",
    Base.metadata,
    Column("ku_id", String(255), ForeignKey("knowledge_units.id", ondelete="CASCADE"), primary_key=True),
    Column("topic_id", String(255), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # Relationships
    competences: Mapped[List["Competence"]] = relationship("Competence", back_populates="learner", cascade="all, delete-orphan")
    evidence: Mapped[List["EvidenceRecord"]] = relationship("EvidenceRecord", back_populates="learner", cascade="all, delete-orphan")

class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # URI like 'ku:linear_algebra:matrix_multiplication:v1'
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    concept: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)  # foundational, intermediate, advanced, expert
    definition: Mapped[str] = mapped_column(String(1000), nullable=False)
    element_interactivity: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    domain_decay_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft") # draft, review, validated, deprecated
    provenance: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    sources: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # Relationships
    skills: Mapped[List["Skill"]] = relationship(
        "Skill", secondary=ku_skill_association, back_populates="kus"
    )
    topics: Mapped[List["Topic"]] = relationship(
        "Topic", secondary=ku_topic_association, back_populates="kus"
    )
    
    # Relações de saída (este nó aponta para outros)
    outgoing_relations: Mapped[List["KURelation"]] = relationship(
        "KURelation", foreign_keys="[KURelation.source_id]", back_populates="source", cascade="all, delete-orphan"
    )
    # Relações de entrada (outros nós apontam para este)
    incoming_relations: Mapped[List["KURelation"]] = relationship(
        "KURelation", foreign_keys="[KURelation.target_id]", back_populates="target", cascade="all, delete-orphan"
    )
    
    # Study Materials (Base Infinita)
    materials: Mapped[List["StudyMaterial"]] = relationship(
        "StudyMaterial", back_populates="ku", cascade="all, delete-orphan"
    )

class KURelation(Base):
    __tablename__ = "ku_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(255), ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # prerequisite, extends, contradicts, equivalent
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Relationships
    source: Mapped["KnowledgeUnit"] = relationship("KnowledgeUnit", foreign_keys=[source_id], back_populates="outgoing_relations")
    target: Mapped["KnowledgeUnit"] = relationship("KnowledgeUnit", foreign_keys=[target_id], back_populates="incoming_relations")

class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # skill:linear_algebra:compute
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)

    kus: Mapped[List["KnowledgeUnit"]] = relationship(
        "KnowledgeUnit", secondary=ku_skill_association, back_populates="skills"
    )

class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)

    kus: Mapped[List["KnowledgeUnit"]] = relationship(
        "KnowledgeUnit", secondary=ku_topic_association, back_populates="topics"
    )

class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    ku_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # artifact, explanation, solution, decision, benchmark
    artifact_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewers: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    source_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    reviewer_agreement: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    recency_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, validated, contested, rejected

    # Relationships
    learner: Mapped["Learner"] = relationship("Learner", back_populates="evidence")
    ku: Mapped["KnowledgeUnit"] = relationship("KnowledgeUnit")

class Competence(Base):
    __tablename__ = "competences"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True
    )
    ku_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"), primary_key=True
    )
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    decay_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    effective_mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    last_updated: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    # Relationships
    learner: Mapped["Learner"] = relationship("Learner", back_populates="competences")
    ku: Mapped["KnowledgeUnit"] = relationship("KnowledgeUnit")

class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active") # draft, active, archived
    required_kus: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)  # list of KU IDs
    optional_kus: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)  # list of KU IDs
    terminal_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    critical_kus: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)  # subset of required KU IDs
    critical_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.90)
    cost_weights: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)  # {alpha, beta, gamma}

class Assessment(Base):
    __tablename__ = "assessments"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    response: Mapped[str] = mapped_column(String, nullable=False)
    rubric_id: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reasoning_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

class Project(Base):
    __tablename__ = "projects"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    required_competences: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    required_skills: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    deliverables: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    evaluation_rubric: Mapped[str] = mapped_column(String(255), nullable=False)

class Challenge(Base):
    """
    Desafio de competência gerado pelo CCE e corrigido pelo servidor.
    A resposta esperada NUNCA é exposta pela API (correção server-side),
    fechando o buraco de evidência autodeclarada para casos objetivos.
    """
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ku_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False
    )
    prompt: Mapped[str] = mapped_column(String(2000), nullable=False)
    answer_type: Mapped[str] = mapped_column(String(20), nullable=False, default="numeric")  # numeric, keywords
    expected_answer: Mapped[str] = mapped_column(String(500), nullable=False)  # numeric: valor; keywords: termos separados por ';'
    tolerance: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)  # apenas numeric
    feedback: Mapped[str] = mapped_column(String(2000), nullable=False, default="")  # explicação exibida após a correção
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)  # 0..1
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    ku: Mapped["KnowledgeUnit"] = relationship("KnowledgeUnit")

class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ku_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # video, pdf, article, link
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    content: Mapped[str] = mapped_column(String, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # Relationships
    ku: Mapped["KnowledgeUnit"] = relationship("KnowledgeUnit", back_populates="materials")

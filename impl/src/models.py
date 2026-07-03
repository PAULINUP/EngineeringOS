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
    states: Mapped[List["LearnerState"]] = relationship("LearnerState", back_populates="learner", cascade="all, delete-orphan")
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

class LearnerState(Base):
    __tablename__ = "learner_states"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True
    )
    ku_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_units.id", ondelete="CASCADE"), primary_key=True
    )
    mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_updated: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    # Relationships
    learner: Mapped["Learner"] = relationship("Learner", back_populates="states")
    ku: Mapped["KnowledgeUnit"] = relationship("KnowledgeUnit")

class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    required_kus: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)  # list of KU IDs
    terminal_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)
    critical_kus: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)  # subset of required KU IDs
    critical_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.90)
    cost_weights: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)  # {alpha, beta, gamma}

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

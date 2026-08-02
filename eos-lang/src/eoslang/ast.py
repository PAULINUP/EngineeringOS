"""
Árvore sintática da linguagem EOS.

As estruturas são imutáveis por padrão (dataclass frozen) — um currículo
compilado não deve ser alterado por acidente por quem o consome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Level(str, Enum):
    """Nível cognitivo declarado da unidade."""
    FOUNDATIONAL = "foundational"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

    @classmethod
    def parse(cls, value: str) -> "Level":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"nível desconhecido: {value!r}. "
                f"Use um de: {', '.join(l.value for l in cls)}"
            )


class RelationType(str, Enum):
    """Como duas unidades se relacionam."""
    PREREQUISITE = "prerequisite"   # a origem precisa vir antes
    EXTENDS = "extends"             # o destino aprofunda a origem
    APPLIES_TO = "applies_to"       # a origem é instrumental para o destino
    EQUIVALENT = "equivalent"       # mesma competência, formulações diferentes
    CONTRADICTS = "contradicts"     # conteúdos mutuamente excludentes


@dataclass(frozen=True)
class Source:
    """Proveniência: de onde o conhecimento veio e quanto ele pesa."""
    reference: str
    type: str = "unspecified"
    weight: float = 1.0

    def __post_init__(self):
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"peso da fonte fora de [0,1]: {self.weight}")


@dataclass(frozen=True)
class Knowledge:
    """
    Unidade de conhecimento: a menor coisa que se pode aprender e demonstrar.

    `requires` guarda os identificadores dos pré-requisitos; a validação
    confere que existem e que não formam ciclo.
    """
    id: str
    title: str = ""
    definition: str = ""
    domain: str = ""
    level: Level = Level.FOUNDATIONAL
    requires: List[str] = field(default_factory=list)
    enables: List[str] = field(default_factory=list)
    interactivity: int = 4          # carga intrínseca estimada (1–10)
    decay_rate: float = 0.05        # esquecimento por dia
    sources: List[Source] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    line: int = 0

    def __post_init__(self):
        if not 1 <= self.interactivity <= 10:
            raise ValueError(
                f"interactivity de '{self.id}' fora de [1,10]: {self.interactivity}"
            )
        if not 0.0 <= self.decay_rate <= 1.0:
            raise ValueError(
                f"decay_rate de '{self.id}' fora de [0,1]: {self.decay_rate}"
            )


@dataclass(frozen=True)
class Mission:
    """Objetivo terminal: o conjunto de unidades que define 'pronto'."""
    id: str
    label: str = ""
    requires: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    critical: List[str] = field(default_factory=list)
    threshold: float = 0.85
    critical_threshold: float = 0.90
    cost_weights: Dict[str, float] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    line: int = 0

    def __post_init__(self):
        if not 0.0 < self.threshold <= 1.0:
            raise ValueError(f"threshold de '{self.id}' fora de (0,1]: {self.threshold}")


@dataclass(frozen=True)
class Skill:
    """Capacidade operacional desenvolvida por uma ou mais unidades."""
    id: str
    label: str = ""
    domain: str = ""
    line: int = 0


@dataclass(frozen=True)
class Topic:
    """Agrupamento temático — navegação, não dependência."""
    id: str
    label: str = ""
    domain: str = ""
    line: int = 0


@dataclass(frozen=True)
class Relation:
    """Aresta explícita entre unidades."""
    source: str
    target: str
    type: RelationType = RelationType.PREREQUISITE
    weight: float = 1.0


@dataclass
class Curriculum:
    """
    Um currículo compilado: o resultado de ler um ou mais arquivos .eos.

    É o objeto que se entrega a quem consome — uma plataforma, um relatório,
    um gerador de material.
    """
    knowledge: Dict[str, Knowledge] = field(default_factory=dict)
    missions: Dict[str, Mission] = field(default_factory=dict)
    skills: Dict[str, Skill] = field(default_factory=dict)
    topics: Dict[str, Topic] = field(default_factory=dict)
    directives: Dict[str, Any] = field(default_factory=dict)
    source_files: List[str] = field(default_factory=list)

    # ---- consultas ----
    @property
    def relations(self) -> List[Relation]:
        """Todas as arestas, derivadas dos `requires` de cada unidade."""
        saida: List[Relation] = []
        for ku in self.knowledge.values():
            for req in ku.requires:
                saida.append(Relation(source=req, target=ku.id))
        return saida

    def roots(self) -> List[str]:
        """Unidades sem pré-requisito — por onde um iniciante pode começar."""
        return sorted(k.id for k in self.knowledge.values() if not k.requires)

    def leaves(self) -> List[str]:
        """Unidades que ninguém exige — os destinos finais do currículo."""
        exigidos = {r for k in self.knowledge.values() for r in k.requires}
        return sorted(k.id for k in self.knowledge.values() if k.id not in exigidos)

    def dependents_of(self, ku_id: str) -> List[str]:
        """O que fica destravado ao dominar esta unidade."""
        return sorted(k.id for k in self.knowledge.values() if ku_id in k.requires)

    def path_to(self, ku_id: str) -> List[str]:
        """
        Ordem de estudo até a unidade pedida: todos os pré-requisitos
        transitivos, em ordem topológica, terminando nela.
        """
        visitados: List[str] = []
        marcados: set = set()

        def visitar(node: str) -> None:
            if node in marcados or node not in self.knowledge:
                return
            marcados.add(node)
            for req in self.knowledge[node].requires:
                visitar(req)
            visitados.append(node)

        visitar(ku_id)
        return visitados

    def stats(self) -> Dict[str, Any]:
        niveis: Dict[str, int] = {}
        dominios: Dict[str, int] = {}
        for k in self.knowledge.values():
            niveis[k.level.value] = niveis.get(k.level.value, 0) + 1
            if k.domain:
                dominios[k.domain] = dominios.get(k.domain, 0) + 1
        return {
            "knowledge_units": len(self.knowledge),
            "missions": len(self.missions),
            "skills": len(self.skills),
            "topics": len(self.topics),
            "relations": len(self.relations),
            "roots": len(self.roots()),
            "leaves": len(self.leaves()),
            "by_level": niveis,
            "by_domain": dominios,
        }

    def __len__(self) -> int:
        return len(self.knowledge)

    def __contains__(self, ku_id: object) -> bool:
        return ku_id in self.knowledge

    def __getitem__(self, ku_id: str) -> Knowledge:
        return self.knowledge[ku_id]

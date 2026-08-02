"""
Alvos de compilação: o que sai depois que o currículo é validado.

  to_dict / to_json  — estrutura portátil, para qualquer consumidor
  to_graph           — grafo NetworkX (opcional), para análise topológica
  to_mermaid         — diagrama para documentação e revisão humana
  to_dot             — Graphviz

Compilar sem validar não é permitido por padrão: entregar um currículo com
ciclo a jusante é entregar um problema silencioso.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .ast import Curriculum
from .validator import validate


def _knowledge_dict(cur: Curriculum) -> List[Dict[str, Any]]:
    saida = []
    for ku in cur.knowledge.values():
        saida.append({
            "id": ku.id,
            "title": ku.title,
            "definition": ku.definition,
            "domain": ku.domain,
            "level": ku.level.value,
            "requires": list(ku.requires),
            "enables": list(ku.enables),
            "interactivity": ku.interactivity,
            "decay_rate": ku.decay_rate,
            "sources": [{"reference": s.reference, "type": s.type, "weight": s.weight}
                        for s in ku.sources],
            "tags": list(ku.tags),
            **({"extra": ku.extra} if ku.extra else {}),
        })
    return saida


def to_dict(cur: Curriculum, validate_first: bool = True) -> Dict[str, Any]:
    if validate_first:
        validate(cur).raise_if_invalid()
    return {
        "directives": cur.directives,
        "knowledge": _knowledge_dict(cur),
        "missions": [{
            "id": m.id, "label": m.label, "requires": list(m.requires),
            "optional": list(m.optional), "critical": list(m.critical),
            "threshold": m.threshold, "critical_threshold": m.critical_threshold,
            "cost_weights": m.cost_weights,
        } for m in cur.missions.values()],
        "skills": [{"id": s.id, "label": s.label, "domain": s.domain}
                   for s in cur.skills.values()],
        "topics": [{"id": t.id, "label": t.label, "domain": t.domain}
                   for t in cur.topics.values()],
        "relations": [{"source": r.source, "target": r.target,
                       "type": r.type.value, "weight": r.weight}
                      for r in cur.relations],
        "stats": cur.stats(),
    }


def to_json(cur: Curriculum, indent: int = 2, validate_first: bool = True) -> str:
    return json.dumps(to_dict(cur, validate_first), ensure_ascii=False, indent=indent)


def to_graph(cur: Curriculum, validate_first: bool = True):
    """Grafo dirigido NetworkX (requer o extra 'graph')."""
    if validate_first:
        validate(cur).raise_if_invalid()
    try:
        import networkx as nx
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "to_graph precisa do NetworkX. Instale com: pip install eos-lang[graph]"
        ) from e

    g = nx.DiGraph()
    for ku in cur.knowledge.values():
        g.add_node(ku.id, title=ku.title, level=ku.level.value, domain=ku.domain,
                   interactivity=ku.interactivity)
    for r in cur.relations:
        g.add_edge(r.source, r.target, type=r.type.value, weight=r.weight)
    return g


def to_mermaid(cur: Curriculum, direction: str = "LR",
               max_nodes: Optional[int] = 60) -> str:
    """
    Diagrama Mermaid. Currículos grandes viram um borrão ilegível, por isso o
    corte padrão — e ele é anunciado no próprio diagrama, nunca silencioso.
    """
    linhas = [f"graph {direction}"]
    unidades = list(cur.knowledge.values())
    cortou = max_nodes is not None and len(unidades) > max_nodes
    if cortou:
        unidades = unidades[:max_nodes]
    visiveis = {k.id for k in unidades}

    def seguro(ident: str) -> str:
        return ident.replace(".", "_").replace("-", "_")

    for ku in unidades:
        rotulo = (ku.title or ku.id).replace('"', "'")
        linhas.append(f'    {seguro(ku.id)}["{rotulo}"]')
    for r in cur.relations:
        if r.source in visiveis and r.target in visiveis:
            linhas.append(f"    {seguro(r.source)} --> {seguro(r.target)}")
    if cortou:
        linhas.append(f'    corte["... {len(cur.knowledge) - max_nodes} unidades omitidas"]')
    return "\n".join(linhas)


def to_dot(cur: Curriculum) -> str:
    """Graphviz DOT."""
    linhas = ["digraph curriculo {", '  rankdir="LR";',
              '  node [shape=box, style=rounded];']
    for ku in cur.knowledge.values():
        rotulo = (ku.title or ku.id).replace('"', r"\"")
        linhas.append(f'  "{ku.id}" [label="{rotulo}"];')
    for r in cur.relations:
        linhas.append(f'  "{r.source}" -> "{r.target}";')
    linhas.append("}")
    return "\n".join(linhas)

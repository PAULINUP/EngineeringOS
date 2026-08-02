"""
Validação semântica.

O que separa esta linguagem de um formato de dados qualquer: um currículo que
compila é um currículo **percorrível**. As duas garantias centrais:

  1. Toda referência aponta para algo que existe.
  2. Não há ciclo entre pré-requisitos — se houvesse, nenhuma das unidades
     envolvidas poderia ser a primeira, e o currículo seria impossível.

A detecção de ciclo devolve o caminho exato, não só "existe um ciclo".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .ast import Curriculum
from .errors import EOSCycleError, EOSReferenceError, EOSValidationError


@dataclass
class ValidationResult:
    """Resultado da validação: erros impedem o uso, avisos não."""
    errors: List[EOSValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_invalid(self) -> None:
        if self.errors:
            raise self.errors[0]

    def report(self) -> str:
        linhas: List[str] = []
        for e in self.errors:
            linhas.append(f"erro: {e.formatted()}")
        for w in self.warnings:
            linhas.append(f"aviso: {w}")
        return "\n".join(linhas) or "sem problemas"


def find_cycle(grafo: Dict[str, List[str]]) -> Optional[List[str]]:
    """
    Devolve o primeiro ciclo encontrado, como lista de nós na ordem do
    percurso, ou None. Busca em profundidade com marcação de caminho ativo.
    """
    BRANCO, CINZA, PRETO = 0, 1, 2
    cor: Dict[str, int] = {n: BRANCO for n in grafo}
    pilha: List[str] = []

    def visitar(n: str) -> Optional[List[str]]:
        cor[n] = CINZA
        pilha.append(n)
        for viz in grafo.get(n, []):
            if viz not in cor:
                continue
            if cor[viz] == CINZA:                    # voltou ao caminho ativo
                return pilha[pilha.index(viz):]
            if cor[viz] == BRANCO:
                achado = visitar(viz)
                if achado:
                    return achado
        pilha.pop()
        cor[n] = PRETO
        return None

    for n in grafo:
        if cor[n] == BRANCO:
            achado = visitar(n)
            if achado:
                return achado
    return None


def validate(cur: Curriculum, strict: bool = False) -> ValidationResult:
    """
    Valida o currículo. Com `strict`, avisos viram erros — útil no CI, onde
    um currículo meia-boca não deveria entrar.
    """
    res = ValidationResult()

    arquivo = cur.source_files[0] if cur.source_files else None

    # 1. auto-referência — verificada ANTES do ciclo porque "declara a si
    # mesmo" diz muito mais a quem escreve do que "dependência circular: a → a"
    for ku in cur.knowledge.values():
        if ku.id in ku.requires:
            res.errors.append(
                EOSValidationError(f"'{ku.id}' declara a si mesmo como pré-requisito",
                                   line=ku.line, file=arquivo)
            )
    if res.errors:
        return res

    # 2. referências de pré-requisito
    for ku in cur.knowledge.values():
        for req in ku.requires:
            if req not in cur.knowledge:
                res.errors.append(
                    EOSReferenceError(req, ku.id, line=ku.line, file=arquivo)
                )

    # 3. ciclos entre pré-requisitos
    grafo = {ku_id: list(ku.requires) for ku_id, ku in cur.knowledge.items()}
    ciclo = find_cycle(grafo)
    if ciclo:
        linha = cur.knowledge[ciclo[0]].line if ciclo[0] in cur.knowledge else 0
        res.errors.append(EOSCycleError(ciclo, line=linha,
                                        file=cur.source_files[0] if cur.source_files else None))

    # 4. referências das missões
    for m in cur.missions.values():
        for grupo, nome in ((m.requires, "requires"), (m.optional, "optional"),
                            (m.critical, "critical")):
            for ku_id in grupo:
                if ku_id not in cur.knowledge:
                    res.errors.append(
                        EOSReferenceError(ku_id, f"{m.id}.{nome}", line=m.line)
                    )
        for c in m.critical:
            if c not in m.requires:
                res.warnings.append(
                    f"missão '{m.id}': '{c}' está em critical mas não em requires"
                )

    # 5. avisos de qualidade — não impedem o uso, mas sinalizam currículo cru
    for ku in cur.knowledge.values():
        if not ku.definition:
            res.warnings.append(f"'{ku.id}' não tem definition")
        if not ku.sources:
            res.warnings.append(f"'{ku.id}' não declara fonte (proveniência)")
        if not ku.title:
            res.warnings.append(f"'{ku.id}' não tem title")

    # 6. unidades órfãs: existem mas nenhuma missão as alcança
    alcancadas: Set[str] = set()
    for m in cur.missions.values():
        for ku_id in list(m.requires) + list(m.optional):
            for passo in cur.path_to(ku_id):
                alcancadas.add(passo)
    if cur.missions:
        for ku_id in cur.knowledge:
            if ku_id not in alcancadas:
                res.warnings.append(f"'{ku_id}' não é exigido por nenhuma missão")

    if strict and res.warnings:
        for w in res.warnings:
            res.errors.append(EOSValidationError(w))
        res.warnings = []

    return res

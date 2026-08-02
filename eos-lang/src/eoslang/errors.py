"""
Erros da linguagem EOS.

Todo erro carrega a posição no arquivo e, quando possível, a linha de origem —
uma mensagem que não diz onde o problema está obriga quem escreve currículo a
caçar no escuro.
"""
from __future__ import annotations

from typing import List, Optional


class EOSError(Exception):
    """Base de todos os erros da linguagem."""

    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: Optional[str] = None, file: Optional[str] = None):
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line
        self.file = file
        super().__init__(self.formatted())

    def formatted(self) -> str:
        local = self.file or "<eos>"
        cabecalho = f"{local}:{self.line}:{self.column}: {self.message}"
        if not self.source_line:
            return cabecalho
        marcador = " " * max(0, self.column - 1) + "^"
        return f"{cabecalho}\n  {self.source_line}\n  {marcador}"


class EOSSyntaxError(EOSError):
    """O texto não forma um programa EOS válido."""


class EOSValidationError(EOSError):
    """O programa é sintaticamente válido, mas viola uma regra semântica."""


class EOSCycleError(EOSValidationError):
    """
    Dependência circular entre pré-requisitos.

    É erro fatal, e não aviso, por um motivo pedagógico: um ciclo significa
    que nenhuma das unidades envolvidas pode ser a primeira, logo o currículo
    é impossível de percorrer.
    """

    def __init__(self, cycle: List[str], **kwargs):
        self.cycle = cycle
        caminho = " → ".join(cycle + [cycle[0]]) if cycle else "?"
        super().__init__(f"dependência circular: {caminho}", **kwargs)


class EOSReferenceError(EOSValidationError):
    """Referência a uma unidade que não existe."""

    def __init__(self, referencia: str, origem: str, **kwargs):
        self.reference = referencia
        self.origin = origem
        super().__init__(
            f"'{origem}' referencia '{referencia}', que não foi declarado",
            **kwargs,
        )

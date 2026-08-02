"""
Analisador léxico da linguagem EOS.

Cada token guarda linha, coluna e o texto da linha de origem, para que
qualquer erro possa apontar exatamente onde está o problema.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .errors import EOSSyntaxError


class TokenType(str, Enum):
    DIRECTIVE = "DIRECTIVE"      # @version, @domain
    IDENT = "IDENT"              # knowledge, mat.algebra.v1
    STRING = "STRING"
    NUMBER = "NUMBER"
    VERSION = "VERSION"          # 1.2.3
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    COLON = "COLON"
    COMMA = "COMMA"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: object
    line: int
    column: int
    source_line: str = ""

    def __repr__(self) -> str:
        return f"Token({self.type.value}, {self.value!r}, {self.line}:{self.column})"


# A ordem importa: VERSION antes de NUMBER (senão "1.2.3" vira 1.2 e .3),
# e DIRECTIVE antes de IDENT.
_SPEC = [
    ("COMMENT", r"(?:--|#)[^\n]*"),
    ("NEWLINE", r"\n"),
    ("SKIP", r"[ \t\r]+"),
    ("DIRECTIVE", r"@[A-Za-z_][A-Za-z0-9_]*"),
    ("STRING", r'"(?:[^"\\]|\\.)*"'),
    ("VERSION", r"\d+\.\d+\.\d+"),
    ("NUMBER", r"-?\d+(?:\.\d+)?"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("COLON", r":"),
    ("COMMA", r","),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_.\-]*"),
    ("MISMATCH", r"."),
]
_REGEX = re.compile("|".join(f"(?P<{nome}>{padrao})" for nome, padrao in _SPEC))

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _unescape(raw: str) -> str:
    """Converte o conteúdo de uma string literal, resolvendo escapes."""
    saida: List[str] = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw):
            saida.append(_ESCAPES.get(raw[i + 1], raw[i + 1]))
            i += 2
        else:
            saida.append(c)
            i += 1
    return "".join(saida)


def tokenize(text: str, file: Optional[str] = None) -> List[Token]:
    """Transforma o texto em uma lista de tokens, terminada por EOF."""
    linhas = text.split("\n")
    tokens: List[Token] = []
    linha_num = 1
    inicio_linha = 0

    for m in _REGEX.finditer(text):
        tipo = m.lastgroup
        valor = m.group()
        coluna = m.start() - inicio_linha + 1
        origem = linhas[linha_num - 1] if linha_num - 1 < len(linhas) else ""

        if tipo == "NEWLINE":
            linha_num += 1
            inicio_linha = m.end()
            continue
        if tipo in ("SKIP", "COMMENT"):
            continue
        if tipo == "MISMATCH":
            raise EOSSyntaxError(
                f"caractere inesperado: {valor!r}",
                line=linha_num, column=coluna, source_line=origem, file=file,
            )

        convertido: object = valor
        if tipo == "STRING":
            convertido = _unescape(valor[1:-1])
        elif tipo == "NUMBER":
            convertido = float(valor) if "." in valor else int(valor)

        tokens.append(Token(TokenType(tipo), convertido, linha_num, coluna, origem))

    tokens.append(Token(TokenType.EOF, None, linha_num, 1,
                        linhas[-1] if linhas else ""))
    return tokens

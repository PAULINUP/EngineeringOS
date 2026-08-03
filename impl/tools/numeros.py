"""
Leitura de números escritos por humanos, nas duas convenções.

O acervo veio de livros em inglês (`1,234.56` — vírgula agrupa milhar, ponto
separa decimal) e é lido por gente que escreve em português (`1.234,56` — o
inverso). Um analisador que assuma uma das duas está errado metade do tempo, e
o erro é silencioso: `7,173,000,000` lido como decimal vira 7,173 — plausível,
e menor que o correto por um fator de um milhão.

A regra usada aqui não depende de idioma: **o último separador é o decimal, se
o que vem depois dele não for um grupo de exatamente três dígitos**. Grupos de
três só aparecem em agrupamento de milhar; um separador seguido de 1, 2, 4 ou
mais dígitos só pode ser decimal.

Casos que ficam ambíguos por natureza — `1.234`, que é mil duzentos e trinta e
quatro em português e um vírgula dois em inglês — são devolvidos como
ambíguos, para quem chamou decidir. Chutar aqui é o que produziu os gabaritos
errados em primeiro lugar.
"""
import re
from typing import List, Optional, Tuple

# Número com separadores: dígitos, grupos e um possível sinal.
NUMERO_RE = re.compile(r"-?\d[\d.,]*\d|-?\d")

# Fração a/b — "2/3" é um valor, não dois números.
FRACAO_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*/\s*(-?\d+(?:[.,]\d+)?)")


def interpretar(texto: str) -> Tuple[Optional[float], bool]:
    """
    Interpreta UM número escrito com separadores.

    Devolve (valor, ambiguo). `ambiguo` marca os casos em que as duas
    convenções dão respostas diferentes e nada no texto permite decidir.
    """
    t = texto.strip().replace(" ", "")
    if not t:
        return None, False

    negativo = t.startswith("-")
    t = t.lstrip("+-")
    if not t or not t[0].isdigit():
        return None, False

    sinal = -1 if negativo else 1
    separadores = [c for c in t if c in ".,"]

    if not separadores:
        try:
            return sinal * float(t), False
        except ValueError:
            return None, False

    ultimo = t[max(t.rfind("."), t.rfind(","))]
    depois = t.split(ultimo)[-1]
    tipos = set(separadores)

    # Duas espécies de separador: o último é sempre o decimal.
    if len(tipos) == 2:
        inteiro = t[: t.rfind(ultimo)].replace(".", "").replace(",", "")
        return _montar(sinal, inteiro, depois), False

    # Uma espécie só, repetida: agrupamento de milhar. "1,234,567" ou "1.234.567"
    if len(separadores) > 1:
        return _montar(sinal, t.replace(ultimo, ""), ""), False

    # Uma espécie, uma vez. O tamanho do que vem depois decide.
    if len(depois) == 3:
        # Ambíguo de verdade: 1.234 é mil e duzentos (pt) ou 1,234 (en).
        antes = t[: t.rfind(ultimo)]
        milhar = _montar(sinal, antes + depois, "")
        return milhar, True
    return _montar(sinal, t[: t.rfind(ultimo)], depois), False


def _montar(sinal: int, inteiro: str, decimal: str) -> Optional[float]:
    inteiro = inteiro or "0"
    if not inteiro.isdigit() or (decimal and not decimal.isdigit()):
        return None
    try:
        return sinal * float(f"{inteiro}.{decimal}" if decimal else inteiro)
    except ValueError:
        return None


def extrair(texto: str) -> List[float]:
    """
    Todos os números de um texto, com frações resolvidas e separadores
    interpretados. Ambíguos entram pela leitura de milhar, que é a mais comum
    em enunciado de livro didático.
    """
    if not texto:
        return []

    def _fracao(m: "re.Match[str]") -> str:
        num, _ = interpretar(m.group(1))
        den, _ = interpretar(m.group(2))
        if num is None or not den:
            return " "
        return f" {num / den!r} "

    texto = FRACAO_RE.sub(_fracao, texto)

    valores: List[float] = []
    for m in NUMERO_RE.finditer(texto):
        v, _ = interpretar(m.group(0))
        if v is not None:
            valores.append(v)
    return valores


def formatar(v: float) -> str:
    """Texto curto e exato: inteiro sem casas, decimal sem lixo de ponto flutuante."""
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return f"{v:.10g}"

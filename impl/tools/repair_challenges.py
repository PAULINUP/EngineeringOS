"""
Conserta e põe em quarentena os desafios corrompidos na extração do OpenStax.

Três defeitos do importador vazaram para o banco antes de serem corrigidos.
Este script os trata com regras determinísticas — nada de LLM, nada de
adivinhação: cada decisão sai do texto original do gabarito, que ficou
preservado no campo `feedback` ("Resposta do livro: …").

  1. FRAÇÃO PARTIDA (reparável)
     "Resposta do livro: (243/32)" virou o conjunto "243;32", pedindo dois
     números onde havia um só valor. O gabarito é recalculado como 7.59375.

  2. RESPOSTA EM PARTES (quarentena)
     "(a) 5, 125 (b) 0, 5, 125" foi fundido num único conjunto numérico. Não
     há resposta certa possível: são duas perguntas diferentes.

  3. VARIÁVEL TRADUZIDA (quarentena)
     O tradutor leu o vetor "u" como pronome e escreveu "você = i + j".
     O enunciado ficou sem sentido.

Quarentena é `active = false`: o desafio some do catálogo mas continua
existindo, porque evidências já registradas o referenciam por source_ref e
uma decisão errada precisa ser reversível.

    python tools/repair_challenges.py              # relatório, não grava
    python tools/repair_challenges.py --execute    # aplica
    python tools/repair_challenges.py --restore    # tira todos da quarentena
"""
import argparse
import asyncio
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from src.database import AsyncSessionLocal  # noqa: E402
from src.models import Challenge  # noqa: E402

PREFIXO = "Resposta do livro:"
FRACAO_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)")
ITEM_LABEL_RE = re.compile(r"\(\s*[a-dA-D]\s*\)")
VARIAVEL_TRADUZIDA_RE = re.compile(r"\bvoc[eê]\s*[=·+\-]", re.IGNORECASE)


def _fmt(v: float) -> str:
    return f"{v:g}"


def gabarito_reparado(expected: str, feedback: str):
    """
    Se o gabarito for uma fração desmontada em dois números, devolve o valor
    correto. Caso contrário, None.

    A checagem é conservadora: só repara quando numerador e denominador do
    texto original aparecem, os dois, como itens do conjunto esperado — a
    assinatura exata do defeito.
    """
    itens = [v.strip() for v in (expected or "").split(";") if v.strip()]
    if len(itens) < 2:
        return None

    novos = []
    for m in FRACAO_RE.finditer(feedback or ""):
        num, den = m.group(1), m.group(2)
        if num in itens and den in itens and float(den) != 0:
            novos.append(float(num) / float(den))

    if not novos:
        return None
    # Todo item do conjunto tem de ser explicado por alguma fração; se sobrar
    # número solto, o gabarito é outra coisa e não cabe reparo automático.
    explicados = set()
    for m in FRACAO_RE.finditer(feedback or ""):
        explicados.update({m.group(1), m.group(2)})
    if set(itens) - explicados:
        return None

    return ";".join(_fmt(v) for v in dict.fromkeys(novos))


def motivo_quarentena(prompt: str, feedback: str):
    """Devolve o motivo da quarentena, ou None se o desafio parece íntegro."""
    if len(ITEM_LABEL_RE.findall(feedback or "")) > 1:
        return "resposta em partes (a)/(b) fundida num único gabarito"
    if VARIAVEL_TRADUZIDA_RE.search(prompt or ""):
        return "variável do enunciado traduzida como pronome ('você = …')"
    return None


async def restaurar():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Challenge).where(Challenge.active.is_(False)))
        inativos = res.scalars().all()
        for ch in inativos:
            ch.active = True
        await db.commit()
        print(f"{len(inativos)} desafio(s) devolvido(s) ao catálogo.")


async def executar(aplicar: bool):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Challenge))
        desafios = res.scalars().all()

        reparados, quarentenados = [], []
        for ch in desafios:
            feedback = (ch.feedback or "").replace(PREFIXO, "")

            motivo = motivo_quarentena(ch.prompt, feedback)
            if motivo:
                if ch.active:
                    quarentenados.append((ch, motivo))
                    if aplicar:
                        ch.active = False
                continue

            novo = gabarito_reparado(ch.expected_answer, feedback)
            if novo and novo != ch.expected_answer:
                reparados.append((ch, ch.expected_answer, novo))
                if aplicar:
                    ch.expected_answer = novo

        if aplicar:
            await db.commit()

        print(f"Desafios no catálogo: {len(desafios)}\n")

        print(f"── Gabaritos reparados: {len(reparados)}")
        for ch, antes, depois in reparados[:10]:
            print(f"   {antes:>18}  →  {depois:<12} | {ch.feedback[:60]}")
        if len(reparados) > 10:
            print(f"   … e mais {len(reparados) - 10}")

        print(f"\n── Postos em quarentena: {len(quarentenados)}")
        motivos: dict = {}
        for _ch, motivo in quarentenados:
            motivos[motivo] = motivos.get(motivo, 0) + 1
        for motivo, n in sorted(motivos.items(), key=lambda kv: -kv[1]):
            print(f"   {n:>4}  {motivo}")

        ativos = sum(1 for c in desafios if c.active)
        print(f"\nDesafios servíveis ao final: {ativos}")
        if not aplicar:
            print("\n(simulação — nada foi gravado; use --execute para aplicar)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true", help="grava as mudanças")
    p.add_argument("--restore", action="store_true", help="tira todos da quarentena")
    args = p.parse_args()

    asyncio.run(restaurar() if args.restore else executar(args.execute))

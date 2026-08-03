"""
Conserta os gabaritos da família "escreva como número inteiro usando dígitos".

O livro escreve `7,173,000,000`. A limpeza do MathML juntou só o primeiro grupo
e deixou o resto, virando `7173,000000`. Depois a leitura tratou a vírgula como
decimal e gravou **7173** — plausível à vista, e menor que o correto por um
fator de um milhão. O aluno digita certo e o sistema diz que errou.

O QUE DESFAZ A AMBIGUIDADE: não é a forma do número, é o enunciado.
`11044,167` sozinho pode ser onze mil vírgula cento e sessenta e sete ou onze
milhões e quarenta e quatro mil. Só o enunciado decide — e nesta família ele
pede explicitamente **um número inteiro**. Resposta com casa decimal aqui é,
por definição do exercício, um gabarito quebrado.

Duas tentativas anteriores erraram por ignorar isso:
  1ª — comparava com "todos os números da resposta do livro": 525 falsos
       positivos, porque o importador guarda só o que a resposta ACRESCENTA ao
       enunciado e o MathML chega fragmentado.
  2ª — usava a forma do número (grupos de 3 dígitos): pegou `4.493`, decimal
       legítimo de física, achando que era milhar.

Por isso o escopo é semântico e não sintático: só a família onde a própria
pergunta garante que a resposta é inteira.

    python tools/auditar_gabaritos.py             # relatório
    python tools/auditar_gabaritos.py --execute   # aplica
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
FAMILIA = re.compile(r"como um n[uú]mero inteiro usando d[ií]gitos", re.I)
NUMERO_EM_GRUPOS = re.compile(r"(?<![\d.,])(\d+)((?:[.,]\d+)+)(?![\d.,])")


def valor_inteiro_do_livro(livro: str):
    """
    Reconstrói o inteiro a partir do texto do livro, juntando os grupos.

    Seguro nesta família porque a pergunta garante resposta inteira: qualquer
    separador só pode ser agrupamento de milhar.
    """
    m = NUMERO_EM_GRUPOS.search(livro or "")
    if not m:
        return None
    grupos = re.findall(r"[.,](\d+)", m.group(2))
    if not grupos:
        return None
    return int(m.group(1) + "".join(grupos)), m.group(0)


async def auditar(aplicar: bool):
    async with AsyncSessionLocal() as db:
        desafios = (await db.execute(select(Challenge))).scalars().all()

    familia = [c for c in desafios
               if c.answer_type == "numeric" and FAMILIA.search(c.prompt or "")]
    afetados = []

    for ch in familia:
        if PREFIXO not in (ch.feedback or ""):
            continue
        livro = ch.feedback.split(PREFIXO, 1)[-1].strip()
        achado = valor_inteiro_do_livro(livro)
        if not achado:
            continue                     # sem separador: gabarito já é o inteiro
        valor, texto = achado

        atual = (ch.expected_answer or "").split(";")[0]
        try:
            if abs(float(atual) - valor) <= 0.5:
                continue                 # já correto
        except ValueError:
            pass
        afetados.append((ch, texto, valor))

    print(f'Família "escreva como número inteiro": {len(familia)} desafios')
    print(f"  gabarito quebrado pelo separador : {len(afetados)}\n")

    for ch, texto, valor in afetados:
        item = re.sub(r"\s+", " ", (ch.prompt or ""))[-70:]
        print(f"  livro {texto:>18}  gravado {ch.expected_answer:>12}  →  {valor:,}"
              .replace(",", ".") + f"\n     …{item}")

    if aplicar and afetados:
        async with AsyncSessionLocal() as db:
            for ch, _t, valor in afetados:
                atual = (await db.execute(
                    select(Challenge).where(Challenge.id == ch.id))).scalar_one()
                atual.expected_answer = str(valor)
                atual.tolerance = 0.5
            await db.commit()
        print(f"\n{len(afetados)} gabarito(s) corrigido(s).")
    elif not aplicar:
        print("\n(simulação — nada gravado; use --execute)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true")
    asyncio.run(auditar(p.parse_args().execute))

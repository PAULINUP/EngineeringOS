"""corrige gabaritos com agrupamento de milhar colapsado

Migração de DADOS.

O livro escreve `7,173,000,000`. A limpeza do MathML juntava só o primeiro
grupo, deixando `7173,000000`; a vírgula restante era lida como decimal e o
gabarito virava **7173** — menor que o correto por um fator de um milhão, e
plausível o bastante para ninguém desconfiar. Quem respondia certo era
reprovado, e a tela dizia que o erro era dele.

Escopo: só a família "escreva cada número como um número inteiro usando
dígitos". É o enunciado que desfaz a ambiguidade — `11044,167` sozinho pode ser
decimal, mas nesta família a pergunta garante resposta inteira, então qualquer
separador só pode ser agrupamento de milhar.

Seis gabaritos, todos conferíveis lendo o enunciado por extenso:
    onze milhões, quarenta e quatro mil, cento e sessenta e sete  → 11.044.167
    três bilhões, duzentos e vinte e seis milhões, ...            → 3.226.512.017
    sete bilhões e cento e setenta e três milhões                 → 7.173.000.000
    trinta e nove trilhões                                        → 39.000.000.000.000

Revision ID: f3b8d21e5a94
Revises: e2a5b81c4d17
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3b8d21e5a94"
down_revision: Union[str, None] = "e2a5b81c4d17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREFIXO = "Resposta do livro:"
FAMILIA = re.compile(r"como um n[uú]mero inteiro usando d[ií]gitos", re.I)
NUMERO_EM_GRUPOS = re.compile(r"(?<![\d.,])(\d+)((?:[.,]\d+)+)(?![\d.,])")

challenges = sa.table(
    "challenges",
    sa.column("id", sa.Uuid),
    sa.column("prompt", sa.String),
    sa.column("expected_answer", sa.String),
    sa.column("feedback", sa.String),
    sa.column("tolerance", sa.Float),
    sa.column("answer_type", sa.String),
)


def upgrade() -> None:
    conn = op.get_bind()
    linhas = conn.execute(
        sa.select(challenges.c.id, challenges.c.prompt,
                  challenges.c.expected_answer, challenges.c.feedback,
                  challenges.c.answer_type)
    ).fetchall()

    corrigidos = 0
    for id_, prompt, esperado, feedback, tipo in linhas:
        if tipo != "numeric" or not FAMILIA.search(prompt or ""):
            continue
        if PREFIXO not in (feedback or ""):
            continue

        livro = feedback.split(PREFIXO, 1)[-1].strip()
        m = NUMERO_EM_GRUPOS.search(livro)
        if not m:
            continue                       # sem separador: já é o inteiro
        grupos = re.findall(r"[.,](\d+)", m.group(2))
        if not grupos:
            continue
        valor = int(m.group(1) + "".join(grupos))

        try:
            if abs(float((esperado or "").split(";")[0]) - valor) <= 0.5:
                continue                   # já correto
        except ValueError:
            pass

        conn.execute(
            challenges.update()
            .where(challenges.c.id == id_)
            .values(expected_answer=str(valor), tolerance=0.5)
        )
        corrigidos += 1

    print(f"Gabaritos de números grandes corrigidos: {corrigidos}")


def downgrade() -> None:
    """Sem volta: o estado anterior era um valor que nenhuma resposta certa alcançava."""

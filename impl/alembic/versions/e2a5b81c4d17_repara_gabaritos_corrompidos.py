"""repara gabaritos corrompidos na extração do OpenStax

Migração de DADOS, não de esquema.

Três defeitos do importador chegaram ao banco (ver META/QUALIDADE_DO_CATALOGO.md):

  1. Fração lida como dois números: "(243/32)" virou o conjunto "243;32".
     Reparável — o gabarito é recalculado a partir do texto original, que
     ficou preservado em `feedback`.
  2. Resposta em partes: "(a) … (b) …" foi fundida num conjunto só. São duas
     perguntas; não existe gabarito único. Vai para quarentena.
  3. Variável traduzida como pronome: o vetor "u" virou "você = i + j".
     Enunciado sem sentido. Quarentena.

As mesmas regras estão em tools/repair_challenges.py, que serve para rodar sob
demanda; aqui elas viajam junto com o esquema e se aplicam uma vez só, em
qualquer ambiente, sem depender de alguém lembrar de executar o script.

O downgrade tira todos da quarentena. Os gabaritos reparados não voltam ao
estado anterior de propósito: o estado anterior era um valor que nenhuma
resposta certa alcançava.

Revision ID: e2a5b81c4d17
Revises: d1f4a7b93c02
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2a5b81c4d17"
down_revision: Union[str, None] = "d1f4a7b93c02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FRACAO_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)")
ITEM_LABEL_RE = re.compile(r"\(\s*[a-dA-D]\s*\)")
VARIAVEL_TRADUZIDA_RE = re.compile(r"\bvoc[eê]\s*[=·+\-]", re.IGNORECASE)

challenges = sa.table(
    "challenges",
    sa.column("id", sa.Uuid),
    sa.column("prompt", sa.String),
    sa.column("expected_answer", sa.String),
    sa.column("feedback", sa.String),
    sa.column("active", sa.Boolean),
)


def _gabarito_reparado(expected: str, feedback: str):
    """Valor correto quando o gabarito é uma fração desmontada; senão None."""
    itens = [v.strip() for v in (expected or "").split(";") if v.strip()]
    if len(itens) < 2:
        return None

    novos, explicados = [], set()
    for m in FRACAO_RE.finditer(feedback or ""):
        num, den = m.group(1), m.group(2)
        explicados.update({num, den})
        if num in itens and den in itens and float(den) != 0:
            novos.append(float(num) / float(den))

    # Número solto fora das frações significa que o gabarito é outra coisa;
    # nesse caso o reparo automático não se aplica.
    if not novos or set(itens) - explicados:
        return None
    return ";".join(f"{v:g}" for v in dict.fromkeys(novos))


def _motivo_quarentena(prompt: str, feedback: str):
    if len(ITEM_LABEL_RE.findall(feedback or "")) > 1:
        return "resposta em partes"
    if VARIAVEL_TRADUZIDA_RE.search(prompt or ""):
        return "variável traduzida como pronome"
    return None


def upgrade() -> None:
    conn = op.get_bind()
    linhas = conn.execute(
        sa.select(challenges.c.id, challenges.c.prompt,
                  challenges.c.expected_answer, challenges.c.feedback)
    ).fetchall()

    reparados = quarentena = 0
    for id_, prompt, expected, feedback in linhas:
        texto = (feedback or "").replace("Resposta do livro:", "")

        if _motivo_quarentena(prompt, texto):
            conn.execute(
                challenges.update().where(challenges.c.id == id_).values(active=False)
            )
            quarentena += 1
            continue

        novo = _gabarito_reparado(expected, texto)
        if novo and novo != expected:
            conn.execute(
                challenges.update().where(challenges.c.id == id_).values(expected_answer=novo)
            )
            reparados += 1

    print(f"Desafios: {reparados} gabarito(s) reparado(s), {quarentena} em quarentena.")


def downgrade() -> None:
    op.get_bind().execute(challenges.update().values(active=True))

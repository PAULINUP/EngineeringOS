"""amplia concept para 255 (slugs longos da OpenStax)

Escrita à mão, de propósito. O autogenerate compara o modelo com o banco de
DESENVOLVIMENTO e traz junto operações que só fazem sentido lá — foi assim que
a versão anterior chegou a produção tentando remover `ix_evidence_source_ref`,
um índice que nunca existiu no PostgreSQL.

Esta migração faz uma coisa só: `knowledge_units.concept` sai de 100 para 255
caracteres, porque os slugs de seção da OpenStax chegam a 106 e o PostgreSQL
(diferente do SQLite) recusa o valor.

Revision ID: cb32b402af5a
Revises: 257a6dc666ec
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'cb32b402af5a'
down_revision: Union[str, Sequence[str], None] = '257a6dc666ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_units") as batch_op:
        batch_op.alter_column(
            "concept",
            existing_type=sa.String(length=100),
            type_=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_units") as batch_op:
        batch_op.alter_column(
            "concept",
            existing_type=sa.String(length=255),
            type_=sa.String(length=100),
            existing_nullable=False,
        )

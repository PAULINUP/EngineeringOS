"""
Transferência de dados entre ambientes (exportar/importar).

Serve para levar o acervo local ao banco de produção quando não há acesso
direto ao PostgreSQL de fora (o proxy TCP do Railway não vem habilitado por
padrão): exporta-se aqui, o arquivo viaja junto com a imagem, e a importação
roda de dentro do contêiner, que enxerga o banco pela rede interna.

  python tools/data_transfer.py exportar            # gera data_export.json.gz
  python tools/data_transfer.py importar            # carrega no DATABASE_URL atual
  python tools/data_transfer.py importar --recriar  # limpa as tabelas antes

A importação é idempotente (merge por chave primária) e verifica as contagens
no fim. Nunca apaga nada sem --recriar.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import gzip
import json
import sys
import uuid
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IMPL))

from sqlalchemy import delete, func, select  # noqa: E402

from src import models  # noqa: E402
from src.database import AsyncSessionLocal, engine  # noqa: E402
from src.models import Base  # noqa: E402

ARQUIVO = IMPL / "data_export.json.gz"

# Ordem de dependência: pai antes de filho
ORDEM = [
    models.Learner, models.KnowledgeUnit, models.Skill, models.Topic,
    models.KURelation, models.Mission, models.Challenge, models.StudyMaterial,
    models.EvidenceRecord, models.Competence, models.Assessment, models.Project,
]


def _serializar(valor):
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return {"__tipo__": "datetime", "v": valor.isoformat()}
    if isinstance(valor, uuid.UUID):
        return {"__tipo__": "uuid", "v": str(valor)}
    return valor


def _desserializar(valor):
    if isinstance(valor, dict) and "__tipo__" in valor:
        if valor["__tipo__"] == "datetime":
            return datetime.datetime.fromisoformat(valor["v"])
        if valor["__tipo__"] == "uuid":
            return uuid.UUID(valor["v"])
    return valor


async def exportar():
    dados = {}
    async with AsyncSessionLocal() as db:
        for modelo in ORDEM:
            registros = (await db.execute(select(modelo))).scalars().all()
            dados[modelo.__tablename__] = [
                {c.name: _serializar(getattr(r, c.name)) for c in modelo.__table__.columns}
                for r in registros
            ]
            if registros:
                print(f"  {modelo.__tablename__}: {len(registros)}")

    bruto = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    with gzip.open(ARQUIVO, "wb", compresslevel=9) as f:
        f.write(bruto)
    print(f"\nexportado: {ARQUIVO.name} "
          f"({ARQUIVO.stat().st_size/1_048_576:.1f} MB comprimido, "
          f"{len(bruto)/1_048_576:.1f} MB cru)")


async def importar(recriar: bool):
    if not ARQUIVO.exists():
        sys.exit(f"arquivo não encontrado: {ARQUIVO}")
    with gzip.open(ARQUIVO, "rb") as f:
        dados = json.loads(f.read().decode("utf-8"))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    total = 0
    async with AsyncSessionLocal() as db:
        if recriar:
            for modelo in reversed(ORDEM):        # filho antes do pai
                await db.execute(delete(modelo))
            await db.commit()
            print("tabelas limpas (--recriar)")

        for modelo in ORDEM:
            linhas = dados.get(modelo.__tablename__, [])
            if not linhas:
                continue
            for i in range(0, len(linhas), 500):
                for linha in linhas[i:i + 500]:
                    await db.merge(modelo(**{k: _desserializar(v) for k, v in linha.items()}))
                await db.commit()
            print(f"  {modelo.__tablename__}: {len(linhas)}")
            total += len(linhas)

        print(f"\nimportado: {total} linhas")
        print("verificação:")
        divergentes = []
        for modelo in ORDEM:
            esperado = len(dados.get(modelo.__tablename__, []))
            atual = await db.scalar(select(func.count()).select_from(modelo)) or 0
            if esperado or atual:
                marca = "ok " if atual >= esperado else "XX "
                print(f"  {marca}{modelo.__tablename__:22s} {esperado:6d} → {atual:6d}")
                if atual < esperado:
                    divergentes.append(modelo.__tablename__)
        if divergentes:
            sys.exit(f"FALHOU: faltam linhas em {divergentes}")
        print("\ntodas as contagens conferem.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("comando", choices=["exportar", "importar"])
    ap.add_argument("--recriar", action="store_true")
    args = ap.parse_args()
    asyncio.run(exportar() if args.comando == "exportar" else importar(args.recriar))


if __name__ == "__main__":
    main()

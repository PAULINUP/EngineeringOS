"""
Migração SQLite → PostgreSQL, com verificação.

Por que isto existe: em plataformas como Railway o sistema de arquivos do
contêiner é **efêmero**. Subir com SQLite significa perder todo o acervo
(1.814 unidades, evidências, progresso) no primeiro reinício — sem aviso.

O script copia respeitando a ordem das chaves estrangeiras, em lotes, e ao
final **compara as contagens tabela a tabela**. Se algo divergir, ele diz
exatamente onde.

Uso:
  # 1. Suba o Postgres (docker compose up -d db)
  # 2. Aponte o destino e rode:
  set TARGET_DATABASE_URL=postgresql+asyncpg://eos_user:senha@localhost:5432/engineeringos
  python tools/migrate_to_postgres.py --verificar-antes
  python tools/migrate_to_postgres.py            # executa
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IMPL))

from sqlalchemy import func, select                      # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src import models                                    # noqa: E402
from src.models import Base                               # noqa: E402

ORIGEM = os.getenv("SOURCE_DATABASE_URL", f"sqlite+aiosqlite:///{(IMPL / 'engineeringos.db').as_posix()}")
DESTINO = os.getenv("TARGET_DATABASE_URL", "")

# Ordem importa: pai antes de filho, senão a chave estrangeira rejeita
ORDEM = [
    models.Learner,
    models.KnowledgeUnit,
    models.Skill,
    models.Topic,
    models.KURelation,
    models.Mission,
    models.Challenge,
    models.StudyMaterial,
    models.EvidenceRecord,
    models.Competence,
    models.Assessment,
    models.Project,
]
LOTE = 500


async def _contar(sessionmaker, modelo) -> int:
    async with sessionmaker() as s:
        return await s.scalar(select(func.count()).select_from(modelo)) or 0


async def migrar(args):
    if not DESTINO:
        sys.exit("Defina TARGET_DATABASE_URL com a URL do PostgreSQL de destino.")
    if not DESTINO.startswith("postgresql") and not args.permitir_destino_nao_postgres:
        sys.exit(f"Destino não parece PostgreSQL: {DESTINO[:40]}\n"
                 "(use --permitir-destino-nao-postgres para ensaiar a migração)")

    eng_origem = create_async_engine(ORIGEM, echo=False)
    eng_destino = create_async_engine(DESTINO, echo=False)
    S_origem = async_sessionmaker(eng_origem, expire_on_commit=False)
    S_destino = async_sessionmaker(eng_destino, expire_on_commit=False)

    print(f"origem : {ORIGEM.split('///')[-1]}")
    print(f"destino: {DESTINO.split('@')[-1]}\n")

    origem_contagens = {m.__tablename__: await _contar(S_origem, m) for m in ORDEM}
    print("na origem: " + " · ".join(f"{t}={n}" for t, n in origem_contagens.items() if n))

    if args.verificar_antes:
        try:
            async with eng_destino.connect():
                print("\nconexão com o destino: ok (nada foi alterado)")
        except Exception as e:  # noqa: BLE001
            sys.exit(f"\nnão consegui conectar no destino: {e}")
        return

    print("\ncriando esquema no destino…")
    async with eng_destino.begin() as conn:
        if args.recriar:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    total = 0
    for modelo in ORDEM:
        tabela = modelo.__tablename__
        existentes = await _contar(S_destino, modelo)
        if existentes:
            print(f"  {tabela}: já tem {existentes} linhas — pulando "
                  f"(use --recriar para sobrescrever)")
            continue

        copiadas = 0
        async with S_origem() as origem:
            resultado = await origem.execute(select(modelo))
            registros = resultado.scalars().all()

        for i in range(0, len(registros), LOTE):
            fatia = registros[i:i + LOTE]
            async with S_destino() as destino:
                for r in fatia:
                    dados = {c.name: getattr(r, c.name) for c in modelo.__table__.columns}
                    await destino.merge(modelo(**dados))
                await destino.commit()
            copiadas += len(fatia)
            if len(registros) > LOTE:
                print(f"    {tabela}: {copiadas}/{len(registros)}")
        if copiadas:
            print(f"  {tabela}: {copiadas} linhas")
        total += copiadas

    print(f"\ntotal copiado: {total} linhas")

    print("\nverificação final (origem × destino):")
    divergencias = []
    for modelo in ORDEM:
        t = modelo.__tablename__
        o, d = origem_contagens[t], await _contar(S_destino, modelo)
        if o or d:
            marca = "ok " if o == d else "XX "
            print(f"  {marca}{t:22s} {o:6d} → {d:6d}")
            if o != d:
                divergencias.append(t)

    await eng_origem.dispose()
    await eng_destino.dispose()

    if divergencias:
        sys.exit(f"\nFALHOU: contagens divergentes em {divergencias}")
    print("\nmigração verificada: todas as contagens conferem.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar-antes", action="store_true",
                    help="só testa a conexão com o destino")
    ap.add_argument("--permitir-destino-nao-postgres", action="store_true",
                    help="ensaio da migração contra outro SQLite (validação da lógica)")
    ap.add_argument("--recriar", action="store_true",
                    help="APAGA as tabelas do destino antes de copiar")
    args = ap.parse_args()
    asyncio.run(migrar(args))


if __name__ == "__main__":
    main()

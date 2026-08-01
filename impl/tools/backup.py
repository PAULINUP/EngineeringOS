"""
Backup do banco com verificação de integridade e restauração testada.

Regra que este script implementa: **backup não verificado não é backup**.
Cada cópia é conferida (`PRAGMA integrity_check`), tem a contagem de linhas
comparada com a origem, e o comando `verify` restaura de fato num arquivo
temporário antes de declarar o backup válido.

Uso:
  python tools/backup.py criar               # cria e verifica
  python tools/backup.py listar
  python tools/backup.py verificar <arquivo> # restaura e confere
  python tools/backup.py restaurar <arquivo> # substitui o banco (faz cópia de segurança antes)
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
DB = IMPL / "engineeringos.db"
BACKUP_DIR = IMPL / "backups"
TABELAS = ["learners", "knowledge_units", "challenges", "evidence_records",
           "competences", "study_materials", "missions", "ku_relations"]
MANTER = 10          # quantidade de backups preservados


def _contagens(caminho: Path) -> dict:
    con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    out = {}
    for t in TABELAS:
        try:
            out[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.Error:
            out[t] = None
    con.close()
    return out


def _integro(caminho: Path) -> bool:
    con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        con.close()


def criar() -> Path:
    if not DB.exists():
        sys.exit(f"banco não encontrado: {DB}")
    BACKUP_DIR.mkdir(exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = BACKUP_DIR / f"engineeringos-{carimbo}.db"

    # API de backup do SQLite: consistente mesmo com escrita concorrente
    origem = sqlite3.connect(str(DB))
    copia = sqlite3.connect(str(destino))
    with copia:
        origem.backup(copia)
    copia.close()
    origem.close()

    if not _integro(destino):
        destino.unlink(missing_ok=True)
        sys.exit("FALHA: cópia corrompida (integrity_check)")

    antes, depois = _contagens(DB), _contagens(destino)
    divergentes = {t: (antes[t], depois[t]) for t in TABELAS if antes[t] != depois[t]}
    if divergentes:
        print(f"  [aviso] contagens divergentes (escrita concorrente?): {divergentes}")

    tamanho = destino.stat().st_size / 1_048_576
    print(f"backup criado: {destino.name} ({tamanho:.1f} MB)")
    print(f"  integridade: ok | " + " · ".join(f"{t}={depois[t]}" for t in TABELAS if depois[t]))

    antigos = sorted(BACKUP_DIR.glob("engineeringos-*.db"))[:-MANTER]
    for a in antigos:
        a.unlink()
        print(f"  removido antigo: {a.name}")
    return destino


def verificar(caminho: Path) -> bool:
    """Restaura de verdade num arquivo temporário e confere — o único teste que vale."""
    if not caminho.exists():
        sys.exit(f"arquivo não encontrado: {caminho}")
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "restaurado.db"
        shutil.copy2(caminho, alvo)
        if not _integro(alvo):
            print("FALHA: integridade")
            return False
        cont = _contagens(alvo)
        if not cont.get("knowledge_units"):
            print("FALHA: banco restaurado sem unidades de conhecimento")
            return False
        con = sqlite3.connect(f"file:{alvo}?mode=ro", uri=True)
        amostra = con.execute("SELECT id, title FROM knowledge_units LIMIT 1").fetchone()
        con.close()
        print(f"restauração verificada: {caminho.name}")
        print(f"  " + " · ".join(f"{t}={v}" for t, v in cont.items() if v))
        print(f"  amostra legível: {amostra[1][:48]!r}")
        return True


def listar() -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    arquivos = sorted(BACKUP_DIR.glob("engineeringos-*.db"), reverse=True)
    if not arquivos:
        print("nenhum backup ainda — rode: python tools/backup.py criar")
        return
    for f in arquivos:
        idade = (time.time() - f.stat().st_mtime) / 3600
        print(f"  {f.name}  {f.stat().st_size/1_048_576:6.1f} MB  há {idade:5.1f}h")


def restaurar(caminho: Path) -> None:
    if not verificar(caminho):
        sys.exit("recusando restaurar um backup que não passou na verificação")
    if DB.exists():
        seguranca = DB.with_suffix(f".db.antes-de-restaurar-{int(time.time())}")
        shutil.copy2(DB, seguranca)
        print(f"cópia do banco atual: {seguranca.name}")
    shutil.copy2(caminho, DB)
    print(f"banco restaurado a partir de {caminho.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("comando", choices=["criar", "listar", "verificar", "restaurar"])
    ap.add_argument("arquivo", nargs="?")
    args = ap.parse_args()

    if args.comando == "criar":
        destino = criar()
        verificar(destino)          # criar sempre verifica
    elif args.comando == "listar":
        listar()
    else:
        if not args.arquivo:
            sys.exit("informe o arquivo de backup")
        alvo = Path(args.arquivo)
        if not alvo.is_absolute():
            alvo = BACKUP_DIR / alvo
        (verificar if args.comando == "verificar" else restaurar)(alvo)


if __name__ == "__main__":
    main()

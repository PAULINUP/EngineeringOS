"""
Consolida e limpa a base de alunos.

O cadastro acumulou 291 alunos: ~270 "Stress Test Learner" de execuções
automatizadas e 20 cópias do mesmo nome real, cada uma segurando um pedaço do
progresso (o POST /learners criava um novo em vez de reabrir o existente).

O que este script faz, nesta ordem:
  1. faz backup do banco (engineeringos.db.bak-<timestamp>)
  2. para cada nome a MANTER: elege o cadastro com mais evidências como
     canônico e MIGRA evidências, competências e avaliações dos clones
     (competência duplicada fica com a maior maestria — nada de progresso
     é perdido)
  3. apaga os cadastros restantes (testes) em cascata
  4. cria índice único em learners.name para o problema não voltar

Uso:
  python tools/consolidate_learners.py --keep "PAULO GEOVANE DA SILVA SOUZA,Impontuality"
  python tools/consolidate_learners.py --keep "..." --dry-run
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import time
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
DB = IMPL / "engineeringos.db"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", required=True, help="nomes a manter, separados por vírgula")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    keep_names = [n.strip() for n in args.keep.split(",") if n.strip()]
    if not DB.exists():
        sys.exit(f"banco não encontrado: {DB}")

    if not args.dry_run:
        backup = DB.with_suffix(f".db.bak-{int(time.time())}")
        shutil.copy2(DB, backup)
        print(f"backup: {backup.name}")

    con = sqlite3.connect(str(DB))
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    total_before = cur.execute("SELECT COUNT(*) FROM learners").fetchone()[0]
    print(f"alunos antes: {total_before}")

    canonical_ids = []
    for name in keep_names:
        rows = cur.execute(
            """SELECT l.id, (SELECT COUNT(*) FROM evidence_records e WHERE e.learner_id = l.id)
               FROM learners l WHERE l.name = ? ORDER BY 2 DESC""",
            (name,),
        ).fetchall()
        if not rows:
            print(f"  [aviso] nenhum cadastro com o nome {name!r}")
            continue
        canonical, n_ev = rows[0]
        clones = [r[0] for r in rows[1:]]
        canonical_ids.append(canonical)
        print(f"  {name}: {len(rows)} cadastros → canônico com {n_ev} evidências, "
              f"{len(clones)} clones a fundir")

        for clone in clones:
            if args.dry_run:
                continue
            # evidências e avaliações migram direto
            cur.execute("UPDATE evidence_records SET learner_id=? WHERE learner_id=?",
                        (canonical, clone))
            cur.execute("UPDATE assessments SET agent_id=? WHERE agent_id=?",
                        (str(canonical), str(clone)))
            # competências: mantém a maior maestria por KU
            for ku_id, mastery, conf, decay, eff in cur.execute(
                "SELECT ku_id, mastery_score, confidence, decay_factor, effective_mastery "
                "FROM competences WHERE learner_id=?", (clone,)
            ).fetchall():
                existing = cur.execute(
                    "SELECT mastery_score FROM competences WHERE learner_id=? AND ku_id=?",
                    (canonical, ku_id),
                ).fetchone()
                if existing is None:
                    cur.execute(
                        "INSERT INTO competences (learner_id, ku_id, mastery_score, confidence,"
                        " decay_factor, effective_mastery, last_updated)"
                        " VALUES (?,?,?,?,?,?, CURRENT_TIMESTAMP)",
                        (canonical, ku_id, mastery, conf, decay, eff),
                    )
                elif mastery > existing[0]:
                    cur.execute(
                        "UPDATE competences SET mastery_score=?, confidence=?, decay_factor=?,"
                        " effective_mastery=? WHERE learner_id=? AND ku_id=?",
                        (mastery, conf, decay, eff, canonical, ku_id),
                    )
            cur.execute("DELETE FROM competences WHERE learner_id=?", (clone,))
            cur.execute("DELETE FROM learners WHERE id=?", (clone,))

    if not canonical_ids:
        sys.exit("nenhum cadastro canônico encontrado — nada foi alterado")

    placeholders = ",".join("?" * len(canonical_ids))

    # Cadastros fora da lista que TÊM progresso são absorvidos pelo primeiro
    # canônico — apagar estudo real seria perda de dados; só some o que está vazio.
    primary = canonical_ids[0]
    orphans_with_progress = cur.execute(
        f"""SELECT l.id, l.name, COUNT(e.id) FROM learners l
            JOIN evidence_records e ON e.learner_id = l.id
            WHERE l.id NOT IN ({placeholders})
            GROUP BY l.id HAVING COUNT(e.id) > 0""",
        canonical_ids,
    ).fetchall()
    for oid, oname, n_ev in orphans_with_progress:
        print(f"  absorvendo {oname!r} ({n_ev} evidências) no cadastro principal")
        if args.dry_run:
            continue
        cur.execute("UPDATE evidence_records SET learner_id=? WHERE learner_id=?", (primary, oid))
        cur.execute("UPDATE assessments SET agent_id=? WHERE agent_id=?", (str(primary), str(oid)))
        for ku_id, mastery, conf, decay, eff in cur.execute(
            "SELECT ku_id, mastery_score, confidence, decay_factor, effective_mastery "
            "FROM competences WHERE learner_id=?", (oid,)
        ).fetchall():
            existing = cur.execute(
                "SELECT mastery_score FROM competences WHERE learner_id=? AND ku_id=?",
                (primary, ku_id)).fetchone()
            if existing is None:
                cur.execute(
                    "INSERT INTO competences (learner_id, ku_id, mastery_score, confidence,"
                    " decay_factor, effective_mastery, last_updated)"
                    " VALUES (?,?,?,?,?,?, CURRENT_TIMESTAMP)",
                    (primary, ku_id, mastery, conf, decay, eff))
            elif mastery > existing[0]:
                cur.execute(
                    "UPDATE competences SET mastery_score=?, confidence=?, decay_factor=?,"
                    " effective_mastery=? WHERE learner_id=? AND ku_id=?",
                    (mastery, conf, decay, eff, primary, ku_id))
        cur.execute("DELETE FROM competences WHERE learner_id=?", (oid,))

    to_delete = cur.execute(
        f"SELECT COUNT(*) FROM learners WHERE id NOT IN ({placeholders})", canonical_ids
    ).fetchone()[0]
    print(f"cadastros vazios a remover: {to_delete}")

    if not args.dry_run:
        cur.execute(f"DELETE FROM competences WHERE learner_id NOT IN ({placeholders})",
                    canonical_ids)
        cur.execute(f"DELETE FROM evidence_records WHERE learner_id NOT IN ({placeholders})",
                    canonical_ids)
        cur.execute(f"DELETE FROM learners WHERE id NOT IN ({placeholders})", canonical_ids)
        # trava para o banco não voltar a fragmentar
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_learners_name ON learners(name)")
        con.commit()
        cur.execute("VACUUM")

    print(f"\nalunos depois: {cur.execute('SELECT COUNT(*) FROM learners').fetchone()[0]}")
    for lid, name in cur.execute("SELECT id, name FROM learners").fetchall():
        n_ev = cur.execute("SELECT COUNT(*) FROM evidence_records WHERE learner_id=?",
                           (lid,)).fetchone()[0]
        n_val = cur.execute(
            "SELECT COUNT(*) FROM competences WHERE learner_id=? AND mastery_score>=0.85",
            (lid,)).fetchone()[0]
        n_comp = cur.execute("SELECT COUNT(*) FROM competences WHERE learner_id=?",
                             (lid,)).fetchone()[0]
        print(f"  {name}: {n_ev} evidências · {n_comp} competências · {n_val} validadas")
    con.close()
    if args.dry_run:
        print("\n(dry-run — nada foi alterado)")


if __name__ == "__main__":
    main()

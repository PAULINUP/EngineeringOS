"""
Boletim do Impontuality — o que o agente sabe, como resolve e o que domina.

Diferente do analyze.py (que audita a plataforma), este olha para o AGENTE:
o conhecimento que ele carrega no HD, o desempenho por unidade da trilha e a
curva de aprendizado ao longo das gerações.

Uso: python agents/impontuality/boletim.py [--trilha mbas]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

AGENT = Path(__file__).resolve().parent
HD = AGENT / "memory"
DB = AGENT.parent.parent / "engineeringos.db"


def jl(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trilha", default="mbas", help="prefixo das KUs do curso")
    args = ap.parse_args()
    pref = args.trilha

    ident = json.loads((HD / "identity.json").read_text(encoding="utf-8"))
    skills = json.loads((HD / "skills.json").read_text(encoding="utf-8"))
    episodes = jl(HD / "episodes.jsonl")
    knowledge = jl(HD / "knowledge.jsonl")

    con = sqlite3.connect(str(DB))
    lid = con.execute("SELECT id FROM learners WHERE name='Impontuality'").fetchone()[0]

    print("=" * 70)
    print(f"BOLETIM DE {ident['name'].upper()}  ·  geração {ident['generation']}  ·  {ident['xp']} XP")
    print("=" * 70)

    # ---- 1. Situação no curso ----
    total = con.execute("SELECT COUNT(*) FROM knowledge_units WHERE id LIKE ?", (pref + ".%",)).fetchone()[0]
    com_desafio = con.execute(
        "SELECT COUNT(DISTINCT ku_id) FROM challenges WHERE ku_id LIKE ?", (pref + ".%",)).fetchone()[0]
    val, prog = con.execute(
        "SELECT SUM(mastery_score>=0.85), SUM(mastery_score>0 AND mastery_score<0.85) "
        "FROM competences WHERE learner_id=? AND ku_id LIKE ?", (lid, pref + ".%")).fetchone()
    val, prog = val or 0, prog or 0
    print(f"\n1. CURSO ({pref})")
    print(f"   Unidades: {total} | avaliáveis: {com_desafio} | "
          f"validadas: {val} ({val/max(1,com_desafio)*100:.0f}% do avaliável)")
    print(f"   Em progresso: {prog} | intocadas: {total - val - prog}")
    barra = int(val / max(1, com_desafio) * 40)
    print(f"   [{'█'*barra}{'░'*(40-barra)}]")

    # ---- 2. O que domina ----
    print(f"\n2. UNIDADES DOMINADAS (≥85%)")
    dominadas = con.execute(
        "SELECT c.ku_id, c.mastery_score, k.title FROM competences c "
        "JOIN knowledge_units k ON k.id=c.ku_id "
        "WHERE c.learner_id=? AND c.ku_id LIKE ? AND c.mastery_score>=0.85 "
        "ORDER BY c.mastery_score DESC", (lid, pref + ".%")).fetchall()
    for ku, m, title in dominadas[:15]:
        distintos = con.execute(
            "SELECT COUNT(DISTINCT source_ref) FROM evidence_records "
            "WHERE learner_id=? AND ku_id=? AND source_ref IS NOT NULL", (lid, ku)).fetchone()[0]
        print(f"   {m*100:5.1f}%  ({distintos} exercícios distintos)  {title[:46]}")
    if not dominadas:
        print("   (nenhuma ainda)")

    # ---- 3. Onde emperra ----
    print(f"\n3. ONDE EMPERRA (unidades sem nenhum acerto)")
    tentadas = defaultdict(lambda: [0, 0])
    for e in episodes:
        if e.get("kind") == "attempt" and str(e.get("ku_id", "")).startswith(pref + "."):
            tentadas[e["ku_id"]][0] += 1
            tentadas[e["ku_id"]][1] += 1 if e.get("correct") else 0
    travadas = [(k, v[0]) for k, v in tentadas.items() if v[1] == 0]
    for ku, n in sorted(travadas, key=lambda kv: -kv[1])[:8]:
        t = con.execute("SELECT title FROM knowledge_units WHERE id=?", (ku,)).fetchone()
        print(f"   {n:4d} tentativas, 0 acertos  ·  {(t[0] if t else ku)[:46]}")
    print(f"   total de unidades travadas: {len(travadas)}")

    # ---- 4. Como raciocina ----
    print(f"\n4. COMO RESOLVE")
    for s, d in sorted(skills.items(), key=lambda kv: -(kv[1]['hits'] / max(1, kv[1]['tries']))):
        if not d["tries"]:
            continue
        taxa = d["hits"] / d["tries"] * 100
        print(f"   {s:15s} {d['hits']:5d}/{d['tries']:<6d} {taxa:5.1f}% {'█' * int(taxa/5)}")

    # tentativa em que costuma acertar
    tent = Counter(e.get("tentativa", 1) for e in episodes
                   if e.get("kind") == "attempt" and e.get("correct"))
    if tent:
        print(f"   acertos por tentativa: " +
              " · ".join(f"{n}ª: {c}" for n, c in sorted(tent.items())))

    # ---- 5. Conhecimento acumulado ----
    respostas = [k for k in knowledge if k.get("kind") == "answer"]
    conceitos = [k for k in knowledge if k.get("kind") == "concept"]
    print(f"\n5. CONHECIMENTO NO HD")
    print(f"   {len(respostas)} respostas aprendidas · {len(conceitos)} conceitos estudados")
    via = Counter(r.get("learned_via") for r in respostas)
    print(f"   aprendidas via: {dict(via.most_common())}")
    dominios = Counter(c.get("domain") for c in conceitos)
    print(f"   conceitos por domínio: {dict(dominios.most_common(6))}")

    # ---- 6. Evolução ----
    print(f"\n6. EVOLUÇÃO")
    for s in ident.get("sessions", [])[-8:]:
        a = (s["correct"] / s["attempts"] * 100) if s["attempts"] else 0
        print(f"   gen {s['generation']:2d}: {s['studied']:4d} KUs · "
              f"{s['correct']:4d}/{s['attempts']:<5d} ({a:5.1f}%) · {s['kus_validated']} validadas")
    con.close()


if __name__ == "__main__":
    main()

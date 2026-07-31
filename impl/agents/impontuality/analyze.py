"""
Análise consolidada: HD do Impontuality × banco da plataforma × logs do servidor.

Junta três fontes que normalmente ninguém cruza:
  1. a experiência do aprendiz (episodes/knowledge/skills)
  2. o estado real do acervo (KUs, desafios, cobertura, competências)
  3. a telemetria do servidor (latências, erros)

Saída: relatório em texto + relatorio.json para consumo posterior.

Uso: python agents/impontuality/analyze.py
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
HD = AGENT_DIR / "memory"
IMPL = AGENT_DIR.parent.parent
DB = IMPL / "engineeringos.db"
LOG = IMPL / "system.log"
OUT = AGENT_DIR / "relatorio.json"


def load_jsonl(path: Path):
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


def section(title: str):
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def main():
    report = {}

    identity = json.loads((HD / "identity.json").read_text(encoding="utf-8")) \
        if (HD / "identity.json").exists() else {}
    skills = json.loads((HD / "skills.json").read_text(encoding="utf-8")) \
        if (HD / "skills.json").exists() else {}
    episodes = load_jsonl(HD / "episodes.jsonl")
    findings = load_jsonl(HD / "findings.jsonl")
    knowledge = load_jsonl(HD / "knowledge.jsonl")

    attempts = [e for e in episodes if e.get("kind") == "attempt"]
    self_study = [e for e in episodes if e.get("kind") == "self_study"]

    # ---------------- 1. O aprendiz ----------------
    section("1. O APRENDIZ — quem o Impontuality se tornou")
    lt = identity.get("lifetime", {})
    acc = (lt.get("correct", 0) / lt["attempts"] * 100) if lt.get("attempts") else 0
    print(f"Geração atual: {identity.get('generation')} | XP: {identity.get('xp')}")
    print(f"Vida toda: {lt.get('studied')} KUs estudadas · "
          f"{lt.get('correct')}/{lt.get('attempts')} acertos ({acc:.1f}%)")
    print(f"Memória: {sum(1 for k in knowledge if k.get('kind') == 'answer')} respostas · "
          f"{sum(1 for k in knowledge if k.get('kind') == 'concept')} conceitos")
    report["learner"] = {"generation": identity.get("generation"), "xp": identity.get("xp"),
                         "lifetime": lt, "accuracy": round(acc, 2)}

    print("\nEvolução entre gerações:")
    gens = []
    for s in identity.get("sessions", []):
        a = (s["correct"] / s["attempts"] * 100) if s["attempts"] else 0
        gens.append({"gen": s["generation"], "studied": s["studied"],
                     "attempts": s["attempts"], "correct": s["correct"],
                     "accuracy": round(a, 1), "validated": s["kus_validated"]})
        print(f"  gen {s['generation']}: {s['studied']:4d} KUs · "
              f"{s['correct']:4d}/{s['attempts']:<4d} ({a:5.1f}%) · "
              f"{s['kus_validated']} validadas")
    report["generations"] = gens

    # ---------------- 2. Como ele raciocina ----------------
    section("2. RACIOCÍNIO — quais estratégias funcionam")
    rank = sorted(skills.items(), key=lambda kv: -(kv[1]["hits"] / max(1, kv[1]["tries"])))
    for name, d in rank:
        r = (d["hits"] / d["tries"] * 100) if d["tries"] else 0
        bar = "█" * int(r / 5)
        print(f"  {name:16s} {d['hits']:5d}/{d['tries']:<5d} {r:5.1f}% {bar}")
    report["strategies"] = skills

    # ---------------- 3. Desempenho por domínio ----------------
    section("3. DESEMPENHO POR DOMÍNIO — onde a plataforma ensina de fato")
    by_dom = defaultdict(lambda: {"attempts": 0, "correct": 0, "kus": set(), "self_study": 0})
    for e in attempts:
        d = by_dom[e.get("domain", "?")]
        d["attempts"] += 1
        d["correct"] += 1 if e.get("correct") else 0
        d["kus"].add(e.get("ku_id"))
    for e in self_study:
        by_dom[e.get("domain", "?")]["self_study"] += 1
    dom_report = {}
    print(f"{'domínio':26s} {'KUs':>5s} {'tent.':>6s} {'acerto':>7s} {'só auto-estudo':>15s}")
    for dom, d in sorted(by_dom.items(), key=lambda kv: -kv[1]["attempts"]):
        r = (d["correct"] / d["attempts"] * 100) if d["attempts"] else 0
        print(f"{dom:26s} {len(d['kus']):5d} {d['attempts']:6d} {r:6.1f}% {d['self_study']:15d}")
        dom_report[dom] = {"kus": len(d["kus"]), "attempts": d["attempts"],
                           "accuracy": round(r, 1), "self_study_only": d["self_study"]}
    report["by_domain"] = dom_report

    # ---------------- 4. Achados de QA ----------------
    section("4. ACHADOS DE QA — o que o agente encontrou na plataforma")
    kinds = Counter(f["kind"] for f in findings)
    sev = Counter(f["severity"] for f in findings)
    print(f"Total: {len(findings)} achados · por severidade: {dict(sev)}")
    for kind, n in kinds.most_common():
        ex = next(f for f in findings if f["kind"] == kind)
        print(f"  {kind:18s} {n:5d}  ex: {ex['detail'][:70]}")
    report["findings"] = {"total": len(findings), "by_kind": dict(kinds),
                          "by_severity": dict(sev)}

    # ---------------- 5. O acervo real ----------------
    section("5. ACERVO — cobertura de conteúdo e de avaliação")
    if DB.exists():
        con = sqlite3.connect(str(DB))
        total_kus = con.execute("SELECT COUNT(*) FROM knowledge_units").fetchone()[0]
        kus_ch = con.execute("SELECT COUNT(DISTINCT ku_id) FROM challenges").fetchone()[0]
        total_ch = con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
        kus_mat = con.execute("SELECT COUNT(DISTINCT ku_id) FROM study_materials").fetchone()[0]
        print(f"KUs: {total_kus} | com desafio: {kus_ch} ({kus_ch/total_kus*100:.1f}%) "
              f"| com material: {kus_mat} ({kus_mat/total_kus*100:.1f}%)")
        print(f"Desafios: {total_ch}\n")
        print(f"{'domínio':26s} {'KUs':>5s} {'c/ desafio':>11s} {'cobertura':>10s}")
        cov = {}
        rows = con.execute("""
            SELECT k.domain, COUNT(DISTINCT k.id),
                   COUNT(DISTINCT CASE WHEN c.ku_id IS NOT NULL THEN k.id END)
            FROM knowledge_units k LEFT JOIN challenges c ON c.ku_id = k.id
            GROUP BY k.domain ORDER BY COUNT(DISTINCT k.id) DESC
        """).fetchall()
        for dom, n, withc in rows:
            pct = withc / n * 100 if n else 0
            print(f"{dom:26s} {n:5d} {withc:11d} {pct:9.1f}%")
            cov[dom] = {"kus": n, "with_challenges": withc, "coverage_pct": round(pct, 1)}
        report["coverage"] = {"total_kus": total_kus, "kus_with_challenges": kus_ch,
                              "total_challenges": total_ch, "by_domain": cov}

        # competências efetivamente movidas
        comp = con.execute("""
            SELECT COUNT(*), SUM(mastery_score >= 0.85), SUM(mastery_score >= 0.595 AND mastery_score < 0.85)
            FROM competences
        """).fetchone()
        print(f"\nCompetências registradas: {comp[0]} | validadas (>=85%): {comp[1] or 0}"
              f" | travadas no teto P9 (~60%): {comp[2] or 0}")
        report["competences"] = {"total": comp[0], "validated": comp[1] or 0,
                                 "capped_at_p9": comp[2] or 0}
        con.close()

    # ---------------- 6. Telemetria do servidor ----------------
    section("6. TELEMETRIA DO SERVIDOR")
    if LOG.exists():
        lat_by_path = defaultdict(list)
        errors = Counter()
        text = LOG.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'"path": "([^"]+)".*?"status_code": (\d+), "latency": ([\d.]+)', text):
            path, status, lat = m.group(1), int(m.group(2)), float(m.group(3))
            key = re.sub(r"/[0-9a-f-]{16,}", "/{id}", path)
            key = re.sub(r"/[^/]+\.v1", "/{ku}", key)
            lat_by_path[key].append(lat)
            if status >= 400:
                errors[f"{status} {key}"] += 1
        print(f"{'rota':45s} {'req':>6s} {'média':>8s} {'p95':>8s}")
        rank = sorted(lat_by_path.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))[:10]
        slow = {}
        for path, lats in rank:
            lats_sorted = sorted(lats)
            p95 = lats_sorted[int(len(lats) * 0.95) - 1] if len(lats) > 1 else lats[0]
            avg = sum(lats) / len(lats)
            print(f"{path[:45]:45s} {len(lats):6d} {avg:7.3f}s {p95:7.3f}s")
            slow[path] = {"requests": len(lats), "avg": round(avg, 3), "p95": round(p95, 3)}
        if errors:
            print(f"\nErros HTTP: {dict(errors.most_common(5))}")
        report["telemetry"] = {"slowest_routes": slow, "http_errors": dict(errors)}

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ relatório salvo em {OUT}")


if __name__ == "__main__":
    main()

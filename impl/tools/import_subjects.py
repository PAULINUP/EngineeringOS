"""
Importa as demais matérias OpenStax (todos os níveis disponíveis por área),
encadeadas à escada de matemática/física já importada.

Áreas:  Química (faculdade) · Biologia (básica → faculdade) ·
        Estatística (média → faculdade) · Astronomia (faculdade) ·
        Programação Python (intro) · Economia (faculdade)

Uso:  python tools/import_subjects.py [--no-content] [--max-chapters N]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
PY = sys.executable

# Pontos de ancoragem na escada já importada (pré-requisitos externos)
MMED_LAST = "mmed.10-5-graphing-quadratic-equations-in-two-variables.v1"  # álgebra elementar
MBAS_LAST = "mbas.11-4-understand-slope-of-a-line.v1"                     # matemática básica
FMED_LAST = "fmed.34-7-some-questions-we-know-to-ask.v1"                  # física média

# (slug, prefix, domain, level, interactivity, label, after: str fixo | "@prefix" runtime | None)
SUBJECTS = [
    ("chemistry-2e", "quim", "quimica_faculdade", "ADVANCED", 6,
     "Faculdade: Química Geral", MMED_LAST),
    ("concepts-biology", "bio1", "biologia_basica", "FOUNDATIONAL", 4,
     "Biologia Básica (Concepts of Biology)", None),
    ("biology-2e", "bio2", "biologia_faculdade", "ADVANCED", 6,
     "Faculdade: Biologia", "@bio1"),
    ("statistics", "est1", "estatistica_media", "INTERMEDIATE", 4,
     "Estatística Média (High School)", MMED_LAST),
    ("introductory-statistics-2e", "est2", "estatistica_faculdade", "ADVANCED", 5,
     "Faculdade: Estatística Introdutória", "@est1"),
    ("astronomy-2e", "astro", "astronomia_faculdade", "ADVANCED", 5,
     "Faculdade: Astronomia", FMED_LAST),
    ("introduction-python-programming", "py", "programacao", "INTERMEDIATE", 5,
     "Programação: Introdução a Python", None),
    ("principles-economics-3e", "eco", "economia_faculdade", "INTERMEDIATE", 5,
     "Faculdade: Princípios de Economia", MBAS_LAST),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-content", action="store_true")
    ap.add_argument("--max-chapters", type=int, default=None)
    args = ap.parse_args()

    last_ku_by_prefix = {}
    summary = []

    for slug, prefix, domain, level, inter, label, after in SUBJECTS:
        if after and after.startswith("@"):
            after = last_ku_by_prefix.get(after[1:])

        cmd = [
            PY, "-X", "utf8", str(IMPL / "tools" / "openstax_importer.py"), slug,
            "--prefix", prefix, "--domain", domain, "--level", level,
            "--interactivity", str(inter), "--label", label,
        ]
        if after:
            cmd += ["--after", after]
        if args.no_content:
            cmd += ["--no-content"]
        if args.max_chapters:
            cmd += ["--max-chapters", str(args.max_chapters)]

        print(f"\n{'='*70}\n>>> {label} ({slug})\n{'='*70}", flush=True)
        proc = subprocess.run(cmd, cwd=str(IMPL), capture_output=True, text=True, encoding="utf-8")
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr)
            print(f"[ERRO] {slug} falhou — lote interrompido.")
            sys.exit(1)

        m = re.search(r"Última KU do livro.*?:\s*(\S+)", proc.stdout)
        if m:
            last_ku_by_prefix[prefix] = m.group(1)
        seed_file = IMPL / "seeds" / f"openstax_{slug.replace('-','_')}.eos"
        n = len(re.findall(r"KNOWLEDGE ", seed_file.read_text(encoding="utf-8")))
        summary.append((label, n))

    print(f"\n{'='*70}\nMATÉRIAS COMPLETAS\n{'='*70}")
    total = 0
    for label, n in summary:
        print(f"  {n:4d} KUs — {label}")
        total += n
    print(f"  {total:4d} KUs no total")


if __name__ == "__main__":
    main()

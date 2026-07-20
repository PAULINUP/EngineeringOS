"""
Importa a escada completa de currículos OpenStax para o EngineeringOS.

Escada de matemática:  básica → média → avançada → faculdade (Cálculo 1-3)
Escada de física:      média (College Physics) → faculdade (University Physics 1-3)

Cada livro é encadeado ao anterior via --after (a primeira KU do livro N+1
requer a última KU do livro N), formando a espinha curricular.

Uso:  python tools/import_ladder.py [--no-content] [--max-chapters N]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
PY = sys.executable

# (slug, prefix, domain, level, interactivity, label, after_key)
# after_key: prefixo do livro anterior na escada (None = raiz da escada)
LADDER = [
    ("prealgebra-2e", "mbas", "matematica_basica", "FOUNDATIONAL", 3,
     "Matemática Básica (Prealgebra)", None),
    ("elementary-algebra-2e", "mmed", "matematica_media", "FOUNDATIONAL", 4,
     "Matemática Média (Álgebra Elementar)", "mbas"),
    ("precalculus-2e", "mava", "matematica_avancada", "INTERMEDIATE", 5,
     "Matemática Avançada (Pré-Cálculo)", "mmed"),
    ("calculus-volume-1", "calc1", "matematica_faculdade", "ADVANCED", 6,
     "Faculdade: Cálculo Volume 1", "mava"),
    ("calculus-volume-2", "calc2", "matematica_faculdade", "ADVANCED", 6,
     "Faculdade: Cálculo Volume 2", "calc1"),
    ("calculus-volume-3", "calc3", "matematica_faculdade", "ADVANCED", 7,
     "Faculdade: Cálculo Volume 3", "calc2"),
    ("college-physics-2e", "fmed", "fisica_media", "INTERMEDIATE", 5,
     "Física Média (College Physics)", "mmed"),
    ("university-physics-volume-1", "ufis1", "fisica_faculdade", "ADVANCED", 6,
     "Faculdade: Física Universitária Volume 1", "mava"),
    ("university-physics-volume-2", "ufis2", "fisica_faculdade", "ADVANCED", 6,
     "Faculdade: Física Universitária Volume 2", "ufis1"),
    ("university-physics-volume-3", "ufis3", "fisica_faculdade", "ADVANCED", 7,
     "Faculdade: Física Universitária Volume 3", "ufis2"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-content", action="store_true")
    ap.add_argument("--max-chapters", type=int, default=None)
    args = ap.parse_args()

    last_ku_by_prefix = {}
    summary = []

    for slug, prefix, domain, level, inter, label, after_key in LADDER:
        cmd = [
            PY, "-X", "utf8", str(IMPL / "tools" / "openstax_importer.py"), slug,
            "--prefix", prefix, "--domain", domain, "--level", level,
            "--interactivity", str(inter), "--label", label,
        ]
        if after_key and after_key in last_ku_by_prefix:
            cmd += ["--after", last_ku_by_prefix[after_key]]
        if args.no_content:
            cmd += ["--no-content"]
        if args.max_chapters:
            cmd += ["--max-chapters", str(args.max_chapters)]

        print(f"\n{'='*70}\n>>> {label} ({slug})\n{'='*70}", flush=True)
        proc = subprocess.run(cmd, cwd=str(IMPL), capture_output=True, text=True, encoding="utf-8")
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr)
            print(f"[ERRO] {slug} falhou — escada interrompida.")
            sys.exit(1)

        m = re.search(r"Última KU do livro.*?:\s*(\S+)", proc.stdout)
        if m:
            last_ku_by_prefix[prefix] = m.group(1)
        n = len(re.findall(r"KNOWLEDGE ", (IMPL / "seeds" / f"openstax_{slug.replace('-','_')}.eos").read_text(encoding="utf-8")))
        summary.append((label, n))

    print(f"\n{'='*70}\nESCADA COMPLETA\n{'='*70}")
    total = 0
    for label, n in summary:
        print(f"  {n:4d} KUs — {label}")
        total += n
    print(f"  {total:4d} KUs no total")


if __name__ == "__main__":
    main()

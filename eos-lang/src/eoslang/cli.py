"""
Linha de comando do eos-lang.

    eos validate curso/*.eos          # verifica (código de saída != 0 se falhar)
    eos compile curso/*.eos -o out.json
    eos graph curso.eos --format mermaid
    eos path curso.eos algebra_linear # o que estudar antes
    eos stats curso/*.eos

O `validate` existe para entrar em CI: currículo que não compila não deve ser
publicado, do mesmo jeito que código que não compila não entra em produção.
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path
from typing import List

from . import __version__, compile_files, parse
from .compiler import to_dot, to_json, to_mermaid
from .errors import EOSError
from .validator import validate


def _expandir(padroes: List[str]) -> List[Path]:
    arquivos: List[Path] = []
    for p in padroes:
        achados = [Path(x) for x in glob.glob(p, recursive=True)]
        if achados:
            arquivos.extend(achados)
        elif Path(p).exists():
            arquivos.append(Path(p))
        else:
            print(f"aviso: nada corresponde a {p!r}", file=sys.stderr)
    return sorted(set(arquivos))


def cmd_validate(args) -> int:
    arquivos = _expandir(args.files)
    if not arquivos:
        print("nenhum arquivo .eos encontrado", file=sys.stderr)
        return 2

    combinado = None
    for f in arquivos:
        try:
            parcial = parse(f.read_text(encoding="utf-8"), str(f))
        except EOSError as e:
            print(f"FALHOU {f}\n  {e.formatted()}", file=sys.stderr)
            return 1
        if combinado is None:
            combinado = parcial
        else:
            combinado.knowledge.update(parcial.knowledge)
            combinado.missions.update(parcial.missions)
            combinado.skills.update(parcial.skills)
            combinado.topics.update(parcial.topics)
            combinado.source_files.append(str(f))

    resultado = validate(combinado, strict=args.strict)
    for e in resultado.errors:
        print(f"erro: {e.formatted()}", file=sys.stderr)
    if not args.quiet:
        for w in resultado.warnings:
            print(f"aviso: {w}", file=sys.stderr)

    s = combinado.stats()
    if resultado.ok:
        print(f"OK — {len(arquivos)} arquivo(s), {s['knowledge_units']} unidades, "
              f"{s['relations']} relações, {s['missions']} missões")
        if resultado.warnings and not args.quiet:
            print(f"     ({len(resultado.warnings)} aviso(s))")
        return 0
    print(f"\n{len(resultado.errors)} erro(s)", file=sys.stderr)
    return 1


def cmd_compile(args) -> int:
    arquivos = _expandir(args.files)
    if not arquivos:
        return 2
    try:
        cur = compile_files(arquivos, strict=args.strict)
    except EOSError as e:
        print(f"erro: {e.formatted()}", file=sys.stderr)
        return 1
    saida = to_json(cur, indent=args.indent, validate_first=False)
    if args.output:
        Path(args.output).write_text(saida, encoding="utf-8")
        print(f"escrito: {args.output} ({len(cur)} unidades)")
    else:
        print(saida)
    return 0


def cmd_graph(args) -> int:
    arquivos = _expandir(args.files)
    if not arquivos:
        return 2
    try:
        cur = compile_files(arquivos)
    except EOSError as e:
        print(f"erro: {e.formatted()}", file=sys.stderr)
        return 1
    saida = (to_mermaid(cur, direction=args.direction, max_nodes=args.max_nodes)
             if args.format == "mermaid" else to_dot(cur))
    if args.output:
        Path(args.output).write_text(saida, encoding="utf-8")
        print(f"escrito: {args.output}")
    else:
        print(saida)
    return 0


def cmd_path(args) -> int:
    arquivos = _expandir(args.files)
    if not arquivos:
        return 2
    try:
        cur = compile_files(arquivos)
    except EOSError as e:
        print(f"erro: {e.formatted()}", file=sys.stderr)
        return 1
    if args.target not in cur:
        print(f"unidade não encontrada: {args.target}", file=sys.stderr)
        return 1
    caminho = cur.path_to(args.target)
    print(f"ordem de estudo até '{args.target}' ({len(caminho)} unidades):\n")
    for i, ku_id in enumerate(caminho, 1):
        ku = cur[ku_id]
        print(f"  {i:3d}. {ku.title or ku.id}")
        if args.verbose and ku.definition:
            print(f"       {ku.definition[:90]}")
    return 0


def cmd_stats(args) -> int:
    arquivos = _expandir(args.files)
    if not arquivos:
        return 2
    try:
        cur = compile_files(arquivos, validate_output=False)
    except EOSError as e:
        print(f"erro: {e.formatted()}", file=sys.stderr)
        return 1
    s = cur.stats()
    print(f"unidades: {s['knowledge_units']} | relações: {s['relations']} | "
          f"missões: {s['missions']} | skills: {s['skills']}")
    print(f"pontos de entrada (sem pré-requisito): {s['roots']} | "
          f"destinos finais: {s['leaves']}")
    if s["by_level"]:
        print("\npor nível:")
        for nivel, n in sorted(s["by_level"].items(), key=lambda kv: -kv[1]):
            print(f"  {nivel:15s} {n}")
    if s["by_domain"]:
        print("\npor domínio:")
        for dom, n in sorted(s["by_domain"].items(), key=lambda kv: -kv[1])[:12]:
            print(f"  {dom:24s} {n}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="eos",
        description="eos-lang — currículo como código, com pré-requisitos verificados.",
    )
    ap.add_argument("--version", action="version", version=f"eos-lang {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="verifica sintaxe, referências e ciclos")
    v.add_argument("files", nargs="+")
    v.add_argument("--strict", action="store_true", help="avisos viram erros")
    v.add_argument("-q", "--quiet", action="store_true", help="omite avisos")
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("compile", help="compila para JSON")
    c.add_argument("files", nargs="+")
    c.add_argument("-o", "--output")
    c.add_argument("--indent", type=int, default=2)
    c.add_argument("--strict", action="store_true")
    c.set_defaults(func=cmd_compile)

    g = sub.add_parser("graph", help="gera diagrama do currículo")
    g.add_argument("files", nargs="+")
    g.add_argument("--format", choices=["mermaid", "dot"], default="mermaid")
    g.add_argument("--direction", default="LR", choices=["LR", "TB", "RL", "BT"])
    g.add_argument("--max-nodes", type=int, default=60)
    g.add_argument("-o", "--output")
    g.set_defaults(func=cmd_graph)

    p = sub.add_parser("path", help="ordem de estudo até uma unidade")
    p.add_argument("files", nargs="+")
    p.add_argument("target")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_path)

    s = sub.add_parser("stats", help="resumo do currículo")
    s.add_argument("files", nargs="+")
    s.set_defaults(func=cmd_stats)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

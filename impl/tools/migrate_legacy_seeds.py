"""
Migração one-off dos seeds legados para o dialeto recomendado (eos-lang).

Converte o dialeto antigo:

    module NomeDoModulo
    description "..."

    ku IdDoKU
    @prerequisite Antecedente
    @content "texto"

para o dialeto recomendado:

    @version 1.0.0
    @domain "<stem-do-arquivo>"

    KNOWLEDGE <stem>.IdDoKU {
      title: "IdDoKU"
      domain: "<stem-do-arquivo>"
      definition: "texto"
      requires: [<stem>.Antecedente]
    }

Os ids são prefixados pelo nome do arquivo para permanecerem únicos quando todos os
curriculos são compilados juntos (eos validate impl/seeds/*.eos).

Idempotente: arquivos que não começam com `module` são ignorados.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

SEEDS = Path(__file__).resolve().parent.parent / "seeds"


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalize_id(identifier: str) -> str:
    # A DSL só aceita identificadores ASCII sem espaços: remove acentos e
    # caracteres não alfanuméricos de ids legados ("Álgebra Elementar" →
    # "AlgebraElementar").
    ascii_id = (
        unicodedata.normalize("NFKD", identifier)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_id = "".join(c for c in ascii_id if c.isalnum() or c in "_-")
    return ascii_id or identifier


def _directive_value(line: str, directive: str) -> str | None:
    match = re.match(rf"^{directive}\s+(.+)$", line)
    if not match:
        return None
    value = match.group(1).strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value


def convert(text: str, stem: str) -> str:
    lines = text.splitlines()
    module_name = stem
    description: str | None = None
    kus: list[dict] = []
    current: dict | None = None

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("module "):
            module_name = line[len("module "):].strip()
            continue
        if line.startswith("description "):
            description = _directive_value(line, "description")
            continue
        if line.startswith("ku "):
            current = {"id": line[len("ku "):].strip(), "reqs": [], "content": ""}
            kus.append(current)
            continue
        if current is not None and line.startswith("@prerequisite "):
            current["reqs"].append(line[len("@prerequisite "):].strip())
            continue
        if current is not None and line.startswith("@content "):
            current["content"] = _directive_value(line, "@content") or ""
            continue

    out: list[str] = [
        "@version 1.0.0",
        f"@domain {_quote(stem)}",
        "",
    ]
    if description:
        out.append(f"# {module_name} — {description}")
    else:
        out.append(f"# {module_name}")
    out.append("")

    for ku in kus:
        ku_id = f"{stem}.{_normalize_id(ku['id'])}"
        out.append(f"KNOWLEDGE {ku_id} {{")
        out.append(f"  title: {_quote(ku['id'])}")
        out.append(f"  domain: {_quote(stem)}")
        out.append(f"  definition: {_quote(ku['content'])}")
        if ku["reqs"]:
            requisitos = ", ".join(f"{stem}.{_normalize_id(r)}" for r in ku["reqs"])
            out.append(f"  requires: [{requisitos}]")
        else:
            out.append("  requires: []")
        out.append("}")
        out.append("")

    return "\n".join(out)


def main() -> None:
    converted: list[str] = []
    skipped: list[str] = []
    for path in sorted(SEEDS.glob("*.eos")):
        text = path.read_text(encoding="utf-8")
        if not text.lstrip().startswith("module "):
            skipped.append(path.name)
            continue
        stem = path.stem
        novo = convert(text, stem)
        path.write_text(novo + "\n", encoding="utf-8")
        converted.append(path.name)

    print("Convertidos:", len(converted))
    for name in converted:
        print("  -", name)
    print("Ignorados (já no dialeto novo ou sem 'module'):", len(skipped))


if __name__ == "__main__":
    main()

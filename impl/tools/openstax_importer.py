"""
OpenStax Importer — UCEF ingestion pipeline
============================================
Puxa um livro inteiro da OpenStax (CC BY 4.0), perfila o sumário e gera:

  1. Um arquivo .eos constitucional em impl/seeds/openstax_<slug>.eos
     (1 seção numerada = 1 KU; definição = Learning Objectives da seção;
      pré-requisitos = espinha do livro: seção anterior do capítulo,
      e abertura de capítulo ligada ao fim do capítulo anterior)
  2. Uma MISSION cobrindo o livro inteiro
  3. StudyMaterials com a URL de cada seção (Base Infinita)

Uso:
  python tools/openstax_importer.py <book-slug> --prefix calc1 --domain calculo \
      --level ADVANCED --interactivity 6 [--after <ku_id_do_livro_anterior>] \
      [--no-content] [--no-inject] [--label "Cálculo Volume 1"]

Atribuição (exigência da licença CC BY 4.0): o campo `source.ref` de cada KU
cita o livro e a seção de origem.
"""
import argparse
import asyncio
import html as htmllib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

IMPL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IMPL_ROOT))

USER_AGENT = "Mozilla/5.0 (EngineeringOS curriculum importer; CC-BY attribution kept)"
BASE = "https://openstax.org"


def fetch(url: str, retries: int = 3) -> str:
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Falha ao buscar {url}: {last_err}")


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return htmllib.unescape(re.sub(r"\s+", " ", text)).strip()


def parse_book_tree(book_slug: str):
    """Extrai o sumário completo: CMS API → primeira página → __PRELOADED_STATE__."""
    cms = json.loads(fetch(
        f"{BASE}/apps/cms/api/v2/pages/?type=books.Book&slug={book_slug}"
        "&fields=webview_rex_link&format=json"
    ))
    if not cms.get("items"):
        raise RuntimeError(f"Livro '{book_slug}' não encontrado na CMS API da OpenStax")
    first_page_url = cms["items"][0]["webview_rex_link"]
    html = fetch(first_page_url)
    m = re.search(r"__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*</script>", html, re.DOTALL)
    if not m:
        raise RuntimeError("__PRELOADED_STATE__ não encontrado — layout do site mudou?")
    state = json.loads(m.group(1))
    book = state["content"]["book"]
    book_title = strip_tags(book["title"])

    # Achata "units" (ex: University Physics agrupa capítulos em unidades)
    top_nodes = []
    for node in book["tree"].get("contents", []):
        if node.get("toc_type") == "unit":
            top_nodes.extend(node.get("contents", []))
        else:
            top_nodes.append(node)

    chapters = []
    for node in top_nodes:
        if node.get("toc_type") != "chapter":
            continue
        ch_title = strip_tags(node.get("title", ""))
        # Pula apêndices (capítulos sem número decimal: "A", "B", ...)
        num_match = re.match(r"^(\d+)\s", ch_title)
        if not num_match:
            continue
        sections = []
        for sec in node.get("contents", []):
            if sec.get("toc_target_type") != "numbered-section":
                continue
            sections.append({
                "slug": sec["slug"],
                "title": strip_tags(sec.get("title", "")),
            })
        if sections:
            chapters.append({"number": int(num_match.group(1)), "title": ch_title, "sections": sections})
    return book_title, chapters


def fetch_section_definition(book_slug: str, section_slug: str, fallback: str, delay: float) -> str:
    """Busca a página da seção e extrai os Learning Objectives como definição."""
    try:
        html = fetch(f"{BASE}/books/{book_slug}/pages/{section_slug}")
        time.sleep(delay)
        m = re.search(r"data-type=.abstract.(.*?)</(?:section|div)>", html, re.DOTALL)
        if m:
            items = [strip_tags(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.DOTALL)]
            items = [i for i in items if i]
            if items:
                text = "Ao final desta secao, voce sera capaz de: " + "; ".join(items) + "."
                return text[:950]
    except Exception as e:  # noqa: BLE001
        print(f"    [aviso] conteudo de {section_slug} indisponivel: {e}")
    return fallback


def eos_escape(text: str) -> str:
    return text.replace("\\", " ").replace('"', "'").strip()


def slug_to_ku_id(prefix: str, slug: str) -> str:
    return f"{prefix}.{slug}.v1"


def build_eos(args, book_title, chapters, definitions):
    lines = [
        "@version 1.0.0",
        f'@domain "{args.domain}"',
        f'@author "OpenStax (CC BY 4.0) - importado por openstax_importer"',
        "",
        f"# Livro: {book_title}",
        f"# Fonte: {BASE}/books/{args.book_slug}  (licenca CC BY 4.0)",
        f"# Gerado automaticamente - revise antes de alterar a mao.",
        "",
    ]
    all_ku_ids = []
    prev_section_ku = args.after  # encadeamento entre livros (escada)

    for ch in chapters:
        lines.append(f"# {'-'*60}")
        lines.append(f"# CAPITULO {ch['number']}: {eos_escape(ch['title'])}")
        lines.append(f"# {'-'*60}")
        for sec in ch["sections"]:
            ku_id = slug_to_ku_id(args.prefix, sec["slug"])
            all_ku_ids.append(ku_id)
            definition = eos_escape(definitions.get(sec["slug"]) or f"{sec['title']} - {book_title}.")
            requires = f"[{prev_section_ku}]" if prev_section_ku else "[]"
            lines += [
                f"KNOWLEDGE {ku_id} {args.level} {{",
                f'  title: "{eos_escape(sec["title"])}"',
                f'  domain: "{args.domain}"',
                f'  definition: "{definition}"',
                f"  requires: {requires}",
                f"  interactivity: {args.interactivity}",
                f"  decay_rate: 0.03",
                f'  source: {{ type: "standard", ref: "OpenStax: {eos_escape(book_title)} - {eos_escape(sec["title"])}", weight: 0.90 }}',
                "}",
                "",
            ]
            prev_section_ku = ku_id

    label = args.label or book_title
    lines += [
        f"MISSION mission.{args.prefix}.v1 {{",
        f'  label: "{eos_escape(label)}"',
        f"  requires: [",
    ]
    lines += [f"    {kid}," for kid in all_ku_ids]
    lines += ["  ]", "  threshold: 0.85", "}", ""]
    return "\n".join(lines), all_ku_ids, prev_section_ku


async def register_materials(args, book_title, chapters):
    from src.database import AsyncSessionLocal
    from src import models
    from sqlalchemy import select

    added = 0
    async with AsyncSessionLocal() as db:
        for ch in chapters:
            for sec in ch["sections"]:
                ku_id = slug_to_ku_id(args.prefix, sec["slug"])
                url = f"{BASE}/books/{args.book_slug}/pages/{sec['slug']}"
                exists = await db.execute(
                    select(models.StudyMaterial.id).where(
                        models.StudyMaterial.ku_id == ku_id,
                        models.StudyMaterial.url == url,
                    )
                )
                if exists.first():
                    continue
                ku = await db.get(models.KnowledgeUnit, ku_id)
                if not ku:
                    continue
                db.add(models.StudyMaterial(
                    ku_id=ku_id,
                    title=f"OpenStax: {book_title} — {sec['title']}"[:255],
                    type="article",
                    url=url,
                    quality_score=0.95,
                ))
                added += 1
        await db.commit()
    return added


def main():
    ap = argparse.ArgumentParser(description="Importa um livro OpenStax como currículo .eos")
    ap.add_argument("book_slug", help="ex: calculus-volume-1")
    ap.add_argument("--prefix", required=True, help="prefixo dos IDs de KU, ex: calc1")
    ap.add_argument("--domain", required=True, help="domínio, ex: matematica_faculdade")
    ap.add_argument("--level", default="INTERMEDIATE",
                    choices=["FOUNDATIONAL", "INTERMEDIATE", "ADVANCED", "EXPERT"])
    ap.add_argument("--interactivity", type=int, default=5)
    ap.add_argument("--after", default=None, help="KU final do livro anterior na escada")
    ap.add_argument("--label", default=None, help="rótulo da missão")
    ap.add_argument("--no-content", action="store_true", help="não busca Learning Objectives (rápido)")
    ap.add_argument("--no-inject", action="store_true", help="só gera o .eos, não toca o banco")
    ap.add_argument("--delay", type=float, default=0.15, help="pausa entre requisições de conteúdo")
    ap.add_argument("--max-chapters", type=int, default=None, help="limita capítulos (teste)")
    args = ap.parse_args()

    print(f"[1/4] Buscando sumário de {args.book_slug}…")
    book_title, chapters = parse_book_tree(args.book_slug)
    if args.max_chapters:
        chapters = chapters[: args.max_chapters]
    n_sections = sum(len(c["sections"]) for c in chapters)
    print(f"      {book_title}: {len(chapters)} capítulos, {n_sections} seções")

    definitions = {}
    if not args.no_content:
        print(f"[2/4] Buscando Learning Objectives de {n_sections} seções…")
        done = 0
        for ch in chapters:
            for sec in ch["sections"]:
                definitions[sec["slug"]] = fetch_section_definition(
                    args.book_slug, sec["slug"], f"{sec['title']} — {book_title}.", args.delay
                )
                done += 1
                if done % 20 == 0:
                    print(f"      {done}/{n_sections}…")
    else:
        print("[2/4] (pulado — --no-content)")

    print("[3/4] Gerando .eos…")
    eos_text, ku_ids, last_ku = build_eos(args, book_title, chapters, definitions)
    out_path = IMPL_ROOT / "seeds" / f"openstax_{args.book_slug.replace('-', '_')}.eos"
    out_path.write_text(eos_text, encoding="utf-8")
    print(f"      {out_path} ({len(ku_ids)} KUs)")

    # Valida compilação (dry-run anti-ciclo do parser)
    from src.eos_parser import parse_dsl_content
    parse_dsl_content(eos_text)
    print("      compilação OK (DAG válido)")

    if not args.no_inject:
        print("[4/4] Injetando no banco + materiais…")
        from inject_seed import inject
        asyncio.run(inject(str(out_path)))
        added = asyncio.run(register_materials(args, book_title, chapters))
        print(f"      {added} materiais registrados")
    else:
        print("[4/4] (injeção pulada — --no-inject)")

    print(f"\nÚltima KU do livro (use como --after do próximo): {last_ku}")


if __name__ == "__main__":
    main()

"""
Exercícios de FIM DE CAPÍTULO → desafios do CCE
================================================
Complementa `openstax_exercises.py`. Nas ciências, a OpenStax não coloca os
exercícios dentro da seção: eles ficam em páginas próprias de fim de capítulo
(`{N}-problems-exercises`, `{N}-exercises`, `{N}-problems`), agrupados por
cabeçalhos de seção ("2.1 Displacement") e com gabarito no Answer Key do
capítulo.

Sem isso, física/química/astronomia ficam com 0% de cobertura de avaliação e
travam no teto de 60% do P9 — a maior lacuna medida pelo agente Impontuality
(1.061 achados `sem_desafio`).

Fluxo por livro:
  1. lê o sumário (capítulos e seções)
  2. baixa o Answer Key de cada capítulo
  3. baixa a página de exercícios do capítulo
  4. segmenta os exercícios pelos cabeçalhos de seção → KU correspondente
  5. casa número ↔ gabarito e aplica o mesmo filtro de qualidade

Uso:
  python tools/openstax_chapter_exercises.py --books college-physics-2e:fmed
  python tools/openstax_chapter_exercises.py --all [--dry-run] [--max-per-ku 6]
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

IMPL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IMPL_ROOT))
sys.path.insert(0, str(IMPL_ROOT / "tools"))

from openstax_importer import fetch, BASE, parse_book_tree  # noqa: E402
from openstax_exercises import (  # noqa: E402
    clean_math_html, parse_answer_key_page, get_answer_key_slugs, profile_challenge,
)

# livro -> prefixo das KUs já importadas
DEFAULT_BOOKS = [
    ("college-physics-2e", "fmed"),
    ("university-physics-volume-1", "ufis1"),
    ("university-physics-volume-2", "ufis2"),
    ("university-physics-volume-3", "ufis3"),
    ("chemistry-2e", "quim"),
    ("astronomy-2e", "astro"),
    ("introductory-statistics-2e", "est2"),
    ("statistics", "est1"),
]

EXERCISE_PAGE_PATTERNS = [
    "{n}-problems-exercises",
    "{n}-exercises",
    "{n}-problems",
    "{n}-section-exercises",
]

# Unidades comuns — presença é aceitável, o aluno responde só o número
UNIT_RE = re.compile(
    r"\b(m|cm|mm|km|s|ms|min|h|kg|g|mg|N|J|kJ|W|kW|V|A|C|K|Pa|kPa|atm|mol|L|mL|"
    r"Hz|kHz|MHz|rad|rev|eV|MeV|nm|km/h|m/s|m/s2|years?|days?|anos?|graus?|º|°)\b",
    re.IGNORECASE,
)


def normalize_science_answer(text: str) -> str:
    """
    Reconstitui números que o MathML fragmenta:
      "3 . 0"      -> "3.0"      (ponto decimal separado)
      "× 10 4"     -> "e4"       (notação científica sem expoente)
      "1 , 250"    -> "1250"     (separador de milhar)
    Sem isso, "3 . 0 × 10 4 m/s" viraria o gabarito "3;0;10;4" — errado.
    """
    # sinais unicode (−, –, —) viram hífen: sem isso "− 2.50 kg" perderia o
    # sinal e o gabarito sairia positivo — erro silencioso e grave
    t = text.replace("−", "-").replace("–", "-").replace("—", "-")
    t = re.sub(r"-\s+(?=[\d.])", "-", t)
    t = re.sub(r"(\d)\s*,\s*(\d{3})(?!\d)", r"\1\2", t)
    t = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", t)
    t = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", t)
    # notação científica: o espaço antes do "e" precisa sumir, senão "3.0 e4"
    # é lido como dois números (3.0 e 4)
    t = re.sub(r"\s*[×x]\s*10\s*(-?\s*\d+)",
               lambda m: "e" + m.group(1).replace(" ", ""), t)
    # expoente de unidade solto: "m/s 2" é m/s², não o número 2
    t = re.sub(r"\b(m/s|m/s\^?|cm/s|km/h|s|m)\s+([23])\b", r"\1^\2", t)
    return re.sub(r"\s+", " ", t).strip()


def profile_science_challenge(problem: str, answer: str):
    """
    Aceita apenas respostas de valor único (número + unidade opcional).
    Respostas com vários itens (a)(b)(c), intervalos ou prosa ficam de fora:
    é melhor ter menos desafios do que gabaritos errados.
    """
    raw = answer.strip()
    if re.search(r"\(\s*[abcd]\s*\)|\b[abcd]\s*\.", raw, re.IGNORECASE):
        return None                                  # multi-item
    if len(raw) > 60 or len(problem) < 25 or len(problem) > 700:
        return None
    norm = normalize_science_answer(raw)
    stripped = UNIT_RE.sub(" ", norm)
    stripped = re.sub(r"[=~≈±<>/·º°%,;:\s]", " ", stripped)
    if re.search(r"[A-Za-zÀ-ÿ]{2,}", stripped.replace("e", " ")):
        return None                                  # sobrou prosa
    nums = re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", norm)
    if len(nums) != 1:
        return None                                  # valor único apenas
    try:
        value = float(nums[0])
    except ValueError:
        return None
    # fora desta faixa o valor exigiria notação científica, que o corretor
    # (que só lê dígitos) interpretaria como dois números separados
    if value != 0 and not (1e-6 <= abs(value) < 1e15):
        return None

    unidade = UNIT_RE.search(norm)
    dica = f" (responda o valor numérico{' em ' + unidade.group(0) if unidade else ''})"
    tol = max(abs(value) * 0.02, 0.01)               # 2% — arredondamento do livro
    plain = f"{value:.10f}".rstrip("0").rstrip(".") or "0"
    return {
        "prompt": (problem + dica)[:1900],
        "answer_type": "numeric",
        "expected_answer": plain,
        "tolerance": round(tol, 6),
        "feedback": f"Resposta do livro: {raw}"[:1900],
    }


def fetch_exercise_page(book_slug: str, chapter: int) -> str | None:
    for pat in EXERCISE_PAGE_PATTERNS:
        slug = pat.format(n=chapter)
        try:
            return fetch(f"{BASE}/books/{book_slug}/pages/{slug}", retries=1)
        except Exception:  # noqa: BLE001
            continue
    return None


def extract_by_section(page_html: str):
    """
    [(secao, numero, enunciado)] — segmenta os exercícios pelos cabeçalhos de
    seção da página ("2.1 Displacement" ⇒ secao "2.1").
    """
    events = []
    for m in re.finditer(r"<h[234][^>]*>(.*?)</h[234]>", page_html, re.DOTALL):
        events.append((m.start(), "head", clean_math_html(m.group(1))))
    for m in re.finditer(r'data-type="exercise"', page_html):
        events.append((m.start(), "ex", m.start()))
    events.sort(key=lambda e: e[0])

    starts = [e[0] for e in events if e[1] == "ex"] + [len(page_html)]
    results, current, si = [], None, 0
    for pos, kind, payload in events:
        if kind == "head":
            sm = re.match(r"^(\d+\.\d+)\s", payload)
            current = sm.group(1) if sm else current
            continue
        # bloco do exercício vai até o próximo exercício
        end = next((s for s in starts if s > pos), len(page_html))
        chunk = page_html[pos:end]
        if not current:
            continue
        nm = re.search(r'class="os-number"[^>]*>\s*(\d+)\s*\.?\s*<', chunk)
        pm = re.search(r'data-type="problem"[^>]*>(.*?)$', chunk, re.DOTALL)
        if not nm or not pm or "<img" in pm.group(1):
            continue
        problem = clean_math_html(pm.group(1))
        problem = re.sub(rf"^{re.escape(nm.group(1))}\s*\.?\s*", "", problem).strip()
        if problem:
            results.append((current, nm.group(1), problem))
    return results


async def run(args):
    from sqlalchemy import select
    from src.database import AsyncSessionLocal
    from src import models

    books = []
    if args.books:
        for spec in args.books.split(","):
            slug, prefix = spec.split(":")
            books.append((slug, prefix))
    else:
        books = DEFAULT_BOOKS

    total_created = 0
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(models.Challenge.ku_id).distinct())
        have = {row[0] for row in existing.all()}

        for book_slug, prefix in books:
            print(f"\n{'='*66}\n### {book_slug} (prefixo {prefix})\n{'='*66}", flush=True)
            try:
                book_title, chapters = parse_book_tree(book_slug)
            except Exception as e:  # noqa: BLE001
                print(f"  [erro] sumário: {e}")
                continue

            # seção "2.1" -> ku_id (usa o slug numerado da seção)
            section_to_ku = {}
            for ch in chapters:
                for sec in ch["sections"]:
                    parts = sec["slug"].split("-")
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                        section_to_ku[f"{parts[0]}.{parts[1]}"] = f"{prefix}.{sec['slug']}.v1"

            answer_keys = {}
            for ak_slug in get_answer_key_slugs(book_slug):
                cm = re.search(r"(\d+)", ak_slug)
                if cm:
                    answer_keys[cm.group(1)] = parse_answer_key_page(book_slug, ak_slug)
                    time.sleep(args.delay)
            n_ans = sum(len(g) + sum(len(v) for v in s.values()) for s, g in answer_keys.values())
            print(f"  Answer Key: {n_ans} respostas em {len(answer_keys)} capítulos")

            created_book = 0
            per_ku = {}
            for ch in chapters:
                page = fetch_exercise_page(book_slug, ch["number"])
                if not page:
                    continue
                time.sleep(args.delay)
                scoped, global_ = answer_keys.get(str(ch["number"]), ({}, {}))

                for section, num, problem in extract_by_section(page):
                    ku_id = section_to_ku.get(section)
                    if not ku_id or ku_id in have:
                        continue
                    answer = (scoped.get(section, {}) or {}).get(num) or global_.get(num)
                    if not answer:
                        continue
                    ch_obj = profile_science_challenge(problem, answer)
                    if not ch_obj:
                        continue
                    bucket = per_ku.setdefault(ku_id, [])
                    if len(bucket) >= args.max_per_ku:
                        continue
                    bucket.append(ch_obj)

            for ku_id, items in per_ku.items():
                ku = await db.get(models.KnowledgeUnit, ku_id)
                if not ku:
                    continue
                for rank, ch_obj in enumerate(items):
                    ch_obj["difficulty"] = round(0.3 + 0.4 * rank / max(1, len(items) - 1), 2) \
                        if len(items) > 1 else 0.5
                    if not args.dry_run:
                        db.add(models.Challenge(ku_id=ku_id, **ch_obj))
                created_book += len(items)
            if not args.dry_run:
                await db.commit()
            print(f"  → {created_book} desafios em {len(per_ku)} KUs")
            total_created += created_book

    print(f"\nTOTAL: {total_created} desafios criados"
          f"{' (dry-run, nada gravado)' if args.dry_run else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default=None, help="slug:prefixo,slug:prefixo")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-per-ku", type=int, default=6)
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

"""
OpenStax Exercises → CCE Challenges
====================================
Correlaciona os exercícios numerados das seções OpenStax com o gabarito
oficial do Answer Key do livro, convertendo os objetivamente corrigíveis
em desafios do CCE (correção automática server-side).

Fontes de (problema, resposta):
  1. "Try It" numerados (X.Y) ↔ resposta no Answer Key do capítulo
  2. Exercícios de fim de seção (ímpares) ↔ Answer Key do capítulo
  3. Fallback: exercícios com solução inline curta (data-type="solution")

Perfilagem (só entra o que dá para corrigir com segurança):
  - resposta curta e numérica (1 a 4 valores)
  - enunciado textual sem dependência de imagem
Todo o resto fica de fora (permanece como evidência aberta para revisão).

Uso:
  python tools/openstax_exercises.py [--limit-kus N] [--max-per-ku 6]
      [--delay 0.15] [--dry-run] [--prefix-filter mbas]
"""
import argparse
import asyncio
import html as htmllib
import json
import re
import sys
import time
from pathlib import Path

IMPL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IMPL_ROOT))
sys.path.insert(0, str(IMPL_ROOT / "tools"))

from openstax_importer import fetch, BASE  # noqa: E402

MAX_ANSWER_CHARS = 90
MAX_PROBLEM_CHARS = 700
MIN_PROBLEM_CHARS = 15
DEFAULT_MAX_PER_KU = 6


# ---------------------------------------------------------------------------
# Limpeza de HTML/MathML
# ---------------------------------------------------------------------------

def clean_math_html(fragment: str) -> str:
    fragment = re.sub(r"<annotation(?:-xml)?[^>]*>.*?</annotation(?:-xml)?>",
                      "", fragment, flags=re.DOTALL)
    fragment = re.sub(r"<[a-zA-Z][^>]*$", " ", fragment)
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = htmllib.unescape(text)
    text = text.replace("ⓐ", "(a)").replace("ⓑ", "(b)").replace("ⓒ", "(c)").replace("ⓓ", "(d)")
    text = re.sub(r"If you missed this problem,\s*review\s*Example\s*[\d.]+\s*\.?", "", text)
    text = re.sub(r"\b(Try It|Be Prepared|Checkpoint|Check Your Understanding)\s*[\d.]*\s*", "", text)
    text = re.sub(r'^["\'>\s]+', "", text)
    # separador de milhar mutilado pelo MathML: "2 , 162" -> "2162"
    text = re.sub(r"(\d)\s*,\s*(\d{3})(?!\d)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_numbers(text: str):
    normalized = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", normalized)]


# ---------------------------------------------------------------------------
# Answer Key do livro: {"1.1": "215", "347": "4", ...} por capítulo
# ---------------------------------------------------------------------------

def get_answer_key_slugs(book_slug: str):
    """Encontra as páginas do Answer Key na árvore do livro."""
    cms = json.loads(fetch(
        f"{BASE}/apps/cms/api/v2/pages/?type=books.Book&slug={book_slug}"
        "&fields=webview_rex_link&format=json"
    ))
    if not cms.get("items"):
        return []
    html = fetch(cms["items"][0]["webview_rex_link"])
    m = re.search(r"__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*</script>", html, re.DOTALL)
    if not m:
        return []
    tree = json.loads(m.group(1))["content"]["book"]["tree"]

    slugs = []

    def walk(node):
        title = re.sub(r"<[^>]+>", "", node.get("title", "")).lower()
        if "answer" in title and node.get("contents"):
            for child in node["contents"]:
                slugs.append(child["slug"])
        for child in node.get("contents", []):
            walk(child)

    walk(tree)
    return slugs


def parse_answer_key_page(book_slug: str, page_slug: str):
    """
    Extrai as respostas de uma página do Answer Key com escopo correto:
      retorna (scoped, global_) onde
      - scoped  = {"1.2": {"5": resposta}}  (livros que reiniciam a numeração
                  por seção; cabeçalhos "1.2 Section Exercises" delimitam)
      - global_ = {"347": resposta}          (livros de numeração contínua por
                  capítulo, sem cabeçalhos de seção)
    Respostas sob "Review Exercises"/"Practice Test" são descartadas — a
    numeração desses grupos colide com a das seções.
    """
    scoped: dict = {}
    global_: dict = {}
    try:
        page = fetch(f"{BASE}/books/{book_slug}/pages/{page_slug}")
    except Exception:  # noqa: BLE001
        return scoped, global_

    events = []  # (pos, 'heading'|'solution', payload)
    for m in re.finditer(r"<h[234][^>]*>(.*?)</h[234]>", page, re.DOTALL):
        events.append((m.start(), "heading", clean_math_html(m.group(1))))
    for m in re.finditer(
        r'data-type="solution"[^>]*>(.*?)(?=data-type="solution"|</section>|<h[234])',
        page, re.DOTALL,
    ):
        events.append((m.start(), "solution", m.group(1)))
    events.sort(key=lambda e: e[0])

    current_scope = None      # "1.2" quando dentro de um grupo de seção
    excluded = False          # dentro de Review Exercises / Practice Test
    for _pos, kind, payload in events:
        if kind == "heading":
            h = payload
            sm = re.search(r"(?:Section\s+)?(\d+\.\d+)\s+(?:Section\s+)?Exercises", h)
            if sm:
                current_scope, excluded = sm.group(1), False
            elif re.search(r"Review Exercises|Practice Test|Chapter Review", h, re.IGNORECASE):
                current_scope, excluded = None, True
            elif re.match(r"^\d+\.\d+\s", h):
                # cabeçalho de grupo "Try It" ("1.2 Domain and Range") — fora
                current_scope, excluded = None, True
            continue

        if excluded:
            continue
        text = clean_math_html(payload)
        m = re.match(r"^(\d+(?:\.\d+)?)\s*\.?\s+(.*)$", text)
        if not m:
            continue
        num, ans = m.group(1), m.group(2).strip()
        if "." in num:
            continue  # respostas de Try It (X.Y) — ambíguas, fora
        if current_scope:
            scoped.setdefault(current_scope, {})[num] = ans
        else:
            global_[num] = ans
    return scoped, global_


# ---------------------------------------------------------------------------
# Problemas numerados das seções
# ---------------------------------------------------------------------------

def extract_numbered_problems(page_html: str):
    """
    [(numero, problema)] dos exercícios de fim de seção (numeração inteira,
    única e sem ambiguidade dentro do capítulo), cujo gabarito ímpar está no
    Answer Key. Try It / Be Prepared (numeração X.Y) são ignorados — o REX
    marca ambos de forma indistinguível e a correlação sairia errada.
    A instrução do grupo ("In the following exercises, add.") é prefixada ao
    enunciado, senão "2 + 4" fica sem contexto para o estudante.
    """
    # Instruções de grupo com suas posições na página
    instructions = []
    for m in re.finditer(r"<p[^>]*>((?:(?!</p>).){0,400}?(?:In|For) the following exercises.{0,300}?)</p>",
                         page_html, re.DOTALL):
        instructions.append((m.start(), clean_math_html(m.group(1))))

    def instruction_before(pos: int) -> str:
        best = ""
        for ipos, text in instructions:
            if ipos < pos:
                best = text
            else:
                break
        return best

    results = []
    starts = [m.start() for m in re.finditer(r'data-type="exercise"', page_html)]
    starts.append(len(page_html))
    for idx in range(len(starts) - 1):
        chunk = page_html[starts[idx]: starts[idx + 1]]
        head = chunk[:200]
        cm = re.search(r'class="([^"]*)"', head)
        classes = cm.group(1) if cm else ""
        if "unnumbered" in classes or 'data-type="solution"' in chunk[:3000]:
            continue

        nm = re.search(r'class="os-number"[^>]*>\s*(\d+)\s*\.?\s*<', chunk)
        pm = re.search(r'data-type="problem"[^>]*>(.*?)$', chunk, re.DOTALL)
        if not nm or not pm:
            continue
        num = nm.group(1)
        frag = pm.group(1)
        if "<img" in frag:
            continue
        problem = clean_math_html(frag)
        problem = re.sub(rf"^{re.escape(num)}\s*\.?\s*", "", problem).strip()
        if not problem:
            continue
        instr = instruction_before(starts[idx])
        if instr and len(problem) < 400:
            problem = f"{instr} — {problem}"
        results.append((num, problem))
    return results


def extract_inline_pairs(page_html: str):
    """Fallback: exercícios com solução inline (ex.: Examples com resposta curta)."""
    pairs = []
    chunks = re.split(r'data-type="exercise"', page_html)[1:]
    for chunk in chunks:
        pm = re.search(r'data-type="problem"[^>]*>(.*?)(?=data-type="solution"|$)',
                       chunk, re.DOTALL)
        sm = re.search(r'data-type="solution"[^>]*>(.*?)(?=data-type="exercise"|</section>|$)',
                       chunk, re.DOTALL)
        if not pm or not sm or "<img" in pm.group(1):
            continue
        problem = clean_math_html(pm.group(1))
        solution = re.sub(r"^\s*Solution\s*", "", clean_math_html(sm.group(1)),
                          flags=re.IGNORECASE).strip()
        if problem and solution:
            pairs.append((problem, solution))
    return pairs


# Resposta aceitável = essencialmente numérica: dígitos, separadores, sinais,
# rótulos de item (a)-(d) e incógnitas x/y. Interval notation (∞, ∪, colchetes),
# prosa ("five plus two") e fórmulas simbólicas ficam de fora.
GRADABLE_ANSWER_RE = re.compile(r"[0-9\s.,;:=+\-/×·°%()abcdxyABCDXY]*\Z")


def profile_challenge(problem: str, answer: str):
    if not (MIN_PROBLEM_CHARS <= len(problem) <= MAX_PROBLEM_CHARS):
        return None
    if len(answer) > MAX_ANSWER_CHARS:
        return None
    if not GRADABLE_ANSWER_RE.fullmatch(answer):
        return None
    numbers = extract_numbers(answer)
    if not numbers or len(numbers) > 6:
        return None
    # Só os números que a resposta ACRESCENTA ao enunciado contam como gabarito.
    # Evita desafios degenerados ("traduza 5 + 2" → gabarito 5;2) e permite que
    # em "2 + 4 = 6" o esperado seja apenas o resultado (6).
    problem_numbers = extract_numbers(problem)
    novel = [n for n in numbers
             if not any(abs(n - p) <= 1e-9 for p in problem_numbers)]
    novel = list(dict.fromkeys(novel))
    if not novel or len(novel) > 4:
        return None
    expected = ";".join(f"{n:g}" for n in novel)
    return {
        "prompt": problem[:1900],
        "answer_type": "numeric",
        "expected_answer": expected[:500],
        "tolerance": 0.01,
        "feedback": f"Resposta do livro: {answer}"[:1900],
    }


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

async def run(args):
    from sqlalchemy import select
    from src.database import AsyncSessionLocal
    from src import models

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(models.StudyMaterial.ku_id, models.StudyMaterial.url)
            .where(models.StudyMaterial.url.like("https://openstax.org/books/%"))
        )
        ku_urls = {}
        for ku_id, url in res.all():
            ku_urls.setdefault(ku_id, url)
        if args.prefix_filter:
            ku_urls = {k: v for k, v in ku_urls.items() if k.startswith(args.prefix_filter)}

        existing = await db.execute(select(models.Challenge.ku_id).distinct())
        have = {row[0] for row in existing.all()}
        todo = [(k, v) for k, v in sorted(ku_urls.items()) if k not in have]
        if args.limit_kus:
            todo = todo[: args.limit_kus]

        # agrupa por livro para carregar cada Answer Key uma única vez
        books = {}
        for ku_id, url in todo:
            m = re.match(r"https://openstax\.org/books/([^/]+)/pages/(.+)$", url)
            if m:
                books.setdefault(m.group(1), []).append((ku_id, m.group(2)))

        print(f"KUs com material OpenStax: {len(ku_urls)} | já com desafios: {len(have)} | "
              f"a processar: {len(todo)} em {len(books)} livros")

        total, kus_covered = 0, 0
        for book_slug, entries in books.items():
            print(f"\n### {book_slug} ({len(entries)} KUs)")
            # Answer Key por capítulo: (scoped_por_seção, global_contínuo)
            answer_keys = {}
            for ak_slug in get_answer_key_slugs(book_slug):
                cm = re.search(r"(\d+)", ak_slug)
                if not cm:
                    continue
                answer_keys[cm.group(1)] = parse_answer_key_page(book_slug, ak_slug)
                time.sleep(args.delay)
            n_answers = sum(len(s) and sum(len(v) for v in s.values()) or len(g)
                            for s, g in answer_keys.values())
            print(f"    Answer Key: {n_answers} respostas em {len(answer_keys)} capítulos")

            for i, (ku_id, section_slug) in enumerate(entries, 1):
                try:
                    page = fetch(f"{BASE}/books/{book_slug}/pages/{section_slug}")
                except Exception as e:  # noqa: BLE001
                    print(f"    [{i}] {ku_id}: fetch falhou ({e})")
                    continue
                time.sleep(args.delay)

                slug_parts = section_slug.split("-")
                chapter = slug_parts[0]
                scoped, global_ = answer_keys.get(chapter, ({}, {}))
                if scoped:
                    # livro com numeração reiniciada por seção: usa SÓ o escopo da seção
                    sec_id = (f"{slug_parts[0]}.{slug_parts[1]}"
                              if len(slug_parts) > 1 and slug_parts[1].isdigit() else None)
                    section_key = scoped.get(sec_id, {}) if sec_id else {}
                else:
                    # livro de numeração contínua por capítulo
                    section_key = global_

                challenges = []
                # exercícios numerados casados com o gabarito do escopo correto
                for num, problem in extract_numbered_problems(page):
                    answer = section_key.get(num)
                    if not answer:
                        continue
                    ch = profile_challenge(problem, answer)
                    if ch:
                        challenges.append(ch)
                    if len(challenges) >= args.max_per_ku:
                        break
                # 3) fallback: soluções inline curtas
                if len(challenges) < args.max_per_ku:
                    for problem, solution in extract_inline_pairs(page):
                        ch = profile_challenge(problem, solution)
                        if ch:
                            challenges.append(ch)
                        if len(challenges) >= args.max_per_ku:
                            break

                if not challenges:
                    continue
                for rank, ch in enumerate(challenges):
                    ch["difficulty"] = round(0.3 + 0.4 * rank / max(1, len(challenges) - 1), 2) \
                        if len(challenges) > 1 else 0.5
                    if not args.dry_run:
                        db.add(models.Challenge(ku_id=ku_id, **ch))
                total += len(challenges)
                kus_covered += 1
                if not args.dry_run and kus_covered % 25 == 0:
                    await db.commit()

            print(f"    subtotal geral: {total} desafios em {kus_covered} KUs")
            if not args.dry_run:
                await db.commit()

        print(f"\nConcluído: {total} desafios auto-corrigíveis em {kus_covered} KUs"
              f"{' (dry-run, nada gravado)' if args.dry_run else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-kus", type=int, default=None)
    ap.add_argument("--max-per-ku", type=int, default=DEFAULT_MAX_PER_KU)
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prefix-filter", default=None)
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

"""
Tradutor de conteúdo EN → PT-BR para o acervo OpenStax do EngineeringOS.

Traduz no banco de dados:
  - KnowledgeUnit.title e .definition (somente KUs importadas da OpenStax)
  - Challenge.prompt e .feedback (somente desafios gerados pelo extrator)

Não toca: KUs de referência e desafios curados (já em PT), StudyMaterials
(títulos são citações bibliográficas) e os arquivos .eos (fonte canônica —
re-seed reverte para EN; rode este script de novo após um re-seed, o cache
torna a segunda passada quase instantânea).

Uso:
  python tools/translate_content.py [--limit N] [--dry-run] [--delay 0.2]
"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path

IMPL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IMPL_ROOT))

from deep_translator import GoogleTranslator  # noqa: E402

CACHE_PATH = IMPL_ROOT / "tools" / "translation_cache.json"

# Prefixos de KU importados da OpenStax (conteúdo em inglês)
OPENSTAX_PREFIXES = (
    "mbas.", "mmed.", "mava.", "calc1.", "calc2.", "calc3.",
    "fmed.", "ufis1.", "ufis2.", "ufis3.",
    "quim.", "bio1.", "bio2.", "est1.", "est2.", "astro.", "py.", "eco.",
)

DEF_PREFIX_RAW = "Ao final desta secao, voce sera capaz de:"
DEF_PREFIX_PT = "Ao final desta seção, você será capaz de:"
FB_PREFIX = "Resposta do livro:"


class Translator:
    def __init__(self, delay: float):
        self.gt = GoogleTranslator(source="en", target="pt")
        self.delay = delay
        self.cache = {}
        self.dirty = 0
        if CACHE_PATH.exists():
            self.cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        self.hits = 0
        self.misses = 0

    def _key(self, text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def save(self):
        if self.dirty:
            CACHE_PATH.write_text(
                json.dumps(self.cache, ensure_ascii=False), encoding="utf-8"
            )
            self.dirty = 0

    def translate(self, text: str) -> str:
        text = text.strip()
        if not text or not re.search(r"[A-Za-z]{3}", text):
            return text  # nada textual para traduzir (ex.: "2 + 4")
        k = self._key(text)
        if k in self.cache:
            self.hits += 1
            return self.cache[k]
        self.misses += 1
        for attempt in range(3):
            try:
                out = self.gt.translate(text[:4500]) or text
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"    [aviso] tradução falhou, mantendo EN: {e}")
                    return text
                time.sleep(2.0 * (attempt + 1))
        time.sleep(self.delay)
        self.cache[k] = out
        self.dirty += 1
        if self.dirty >= 50:
            self.save()
        return out


async def run(args):
    from sqlalchemy import select
    from src.database import AsyncSessionLocal
    from src import models

    tr = Translator(args.delay)

    async with AsyncSessionLocal() as db:
        # ------------------- KnowledgeUnits -------------------
        res = await db.execute(select(models.KnowledgeUnit))
        kus = [k for k in res.scalars().all() if k.id.startswith(OPENSTAX_PREFIXES)]
        if args.limit:
            kus = kus[: args.limit]
        print(f"KUs a traduzir: {len(kus)}")

        for i, ku in enumerate(kus, 1):
            new_title = tr.translate(ku.title)
            definition = ku.definition or ""
            if definition.startswith(DEF_PREFIX_RAW):
                body = definition[len(DEF_PREFIX_RAW):].strip()
                new_def = f"{DEF_PREFIX_PT} {tr.translate(body)}"
            elif definition.startswith(DEF_PREFIX_PT):
                new_def = definition  # já traduzida
            else:
                new_def = tr.translate(definition)
            if not args.dry_run:
                ku.title = new_title[:255]
                ku.definition = new_def[:1000]
            if i % 50 == 0:
                if not args.dry_run:
                    await db.commit()
                tr.save()
                print(f"  KUs {i}/{len(kus)} (cache: {tr.hits} hits, {tr.misses} novas)")
        if not args.dry_run:
            await db.commit()
        tr.save()

        # ------------------- Challenges -------------------
        res = await db.execute(
            select(models.Challenge).where(models.Challenge.feedback.like(f"{FB_PREFIX}%"))
        )
        challenges = res.scalars().all()
        if args.limit:
            challenges = challenges[: args.limit]
        print(f"Desafios a traduzir: {len(challenges)}")

        for i, ch in enumerate(challenges, 1):
            new_prompt = tr.translate(ch.prompt)
            fb_body = ch.feedback[len(FB_PREFIX):].strip()
            new_fb = f"{FB_PREFIX} {tr.translate(fb_body)}"
            if not args.dry_run:
                ch.prompt = new_prompt[:2000]
                ch.feedback = new_fb[:2000]
            if i % 50 == 0:
                if not args.dry_run:
                    await db.commit()
                tr.save()
                print(f"  Desafios {i}/{len(challenges)} (cache: {tr.hits} hits, {tr.misses} novas)")
        if not args.dry_run:
            await db.commit()
        tr.save()

    print(f"\nConcluído. Traduções novas: {tr.misses} | reaproveitadas do cache: {tr.hits}"
          f"{' (dry-run, nada gravado)' if args.dry_run else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

"""
IMPONTUALITY — agente autônomo de estudo e teste do EngineeringOS
==================================================================
Um aprendiz sintético que percorre TODAS as trilhas da plataforma, estuda cada
unidade de conhecimento, tenta os desafios, aprende com o resultado e evolui
entre sessões.

O "HD" (memory/) é persistente e cresce a cada execução:
  identity.json    — quem ele é: geração, XP, competências, evolução
  knowledge.jsonl  — o que aprendeu (respostas corretas, padrões, definições)
  episodes.jsonl   — histórico completo de execução (toda tentativa, timestamp)
  skills.json      — estratégias de resolução e seu desempenho (reforço)
  findings.jsonl   — anomalias/bugs observados na plataforma (QA autônomo)

Evolução: as estratégias são escolhidas por taxa de sucesso (bandit
epsilon-greedy) e a memória de respostas corretas transforma erro de hoje em
acerto de amanhã. Rodar duas vezes ⇒ a segunda geração é mensuravelmente melhor.

Uso:
  python agents/impontuality/agent.py                    # sessão completa
  python agents/impontuality/agent.py --max-kus 40       # sessão curta
  python agents/impontuality/agent.py --missions mission.mbas.v1
  python agents/impontuality/agent.py --report           # só relatório do HD
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AGENT_DIR = Path(__file__).resolve().parent
HD = AGENT_DIR / "memory"
HD.mkdir(parents=True, exist_ok=True)

IDENTITY_PATH = HD / "identity.json"
KNOWLEDGE_PATH = HD / "knowledge.jsonl"
EPISODES_PATH = HD / "episodes.jsonl"
SKILLS_PATH = HD / "skills.json"
FINDINGS_PATH = HD / "findings.jsonl"

# 127.0.0.1 e não "localhost": no Windows o resolvedor tenta ::1 primeiro e
# custa ~2s de timeout por requisição (medido pelo próprio agente).
API = "http://127.0.0.1:8000/api"
AGENT_NAME = "Impontuality"

# Estratégias de resolução disponíveis (evoluem por reforço)
STRATEGIES = [
    "memoria",           # já acertou este desafio antes
    "aritmetica",        # resolve a operação explícita no enunciado
    "extenso",           # número por extenso -> dígitos
    "arredondamento",    # arredonda para a casa pedida
    "ultimo_numero",     # heurística: último número citado
    "soma_numeros",      # heurística: soma dos números do enunciado
]

EPSILON = 0.15  # exploração


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# HD — memória persistente
# ---------------------------------------------------------------------------
class MemoryHD:
    def __init__(self):
        self.identity = self._load_json(IDENTITY_PATH, {
            "name": AGENT_NAME,
            "born_at": now_iso(),
            "generation": 0,
            "xp": 0,
            "sessions": [],
            "lifetime": {"studied": 0, "attempts": 0, "correct": 0, "validated_kus": 0},
        })
        self.skills = self._load_json(SKILLS_PATH, {
            s: {"tries": 0, "hits": 0} for s in STRATEGIES
        })
        for s in STRATEGIES:                       # migra HDs antigos
            self.skills.setdefault(s, {"tries": 0, "hits": 0})
        self.answers: Dict[str, str] = {}          # challenge_id -> resposta certa
        self.concepts: Dict[str, dict] = {}        # ku_id -> o que sabe
        self._load_knowledge()

    @staticmethod
    def _load_json(path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return default

    def _load_knowledge(self):
        if not KNOWLEDGE_PATH.exists():
            return
        for line in KNOWLEDGE_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("kind") == "answer":
                self.answers[rec["challenge_id"]] = rec["answer"]
            elif rec.get("kind") == "concept":
                self.concepts[rec["ku_id"]] = rec

    # --- escrita ---
    def append(self, path: Path, record: dict):
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def learn_answer(self, challenge_id: str, prompt: str, answer: str, strategy: str):
        if self.answers.get(challenge_id) == answer:
            return
        self.answers[challenge_id] = answer
        self.append(KNOWLEDGE_PATH, {
            "kind": "answer", "challenge_id": challenge_id, "answer": answer,
            "prompt": prompt[:300], "learned_via": strategy, "at": now_iso(),
        })

    def learn_concept(self, ku: dict):
        if ku["id"] in self.concepts:
            return
        rec = {
            "kind": "concept", "ku_id": ku["id"], "title": ku.get("title", ""),
            "domain": ku.get("domain", ""), "level": ku.get("level", ""),
            "definition": (ku.get("definition") or "")[:400],
            "interactivity": ku.get("element_interactivity"),
            "at": now_iso(),
        }
        self.concepts[ku["id"]] = rec
        self.append(KNOWLEDGE_PATH, rec)

    def episode(self, rec: dict):
        rec["at"] = now_iso()
        self.append(EPISODES_PATH, rec)

    def finding(self, severity: str, kind: str, detail: str, ctx: dict | None = None):
        self.append(FINDINGS_PATH, {
            "severity": severity, "kind": kind, "detail": detail,
            "context": ctx or {}, "at": now_iso(),
        })

    def reinforce(self, strategy: str, hit: bool):
        s = self.skills.setdefault(strategy, {"tries": 0, "hits": 0})
        s["tries"] += 1
        if hit:
            s["hits"] += 1

    def strategy_rank(self) -> List[str]:
        def score(s: str) -> float:
            d = self.skills[s]
            # Laplace smoothing: estratégias novas têm chance de serem testadas
            return (d["hits"] + 1) / (d["tries"] + 2)
        return sorted(STRATEGIES, key=score, reverse=True)

    def save(self):
        IDENTITY_PATH.write_text(json.dumps(self.identity, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        SKILLS_PATH.write_text(json.dumps(self.skills, ensure_ascii=False, indent=2),
                               encoding="utf-8")


# ---------------------------------------------------------------------------
# Raciocínio — as estratégias de resolução
# ---------------------------------------------------------------------------
UNITS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
    "setenta": 70, "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100,
    "duzentos": 200, "trezentos": 300, "quatrocentos": 400, "quinhentos": 500,
    "seiscentos": 600, "setecentos": 700, "oitocentos": 800, "novecentos": 900,
}
SCALES = {"mil": 1000, "milhao": 10**6, "milhoes": 10**6, "bilhao": 10**9, "bilhoes": 10**9}


def deaccent(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def numbers_in(text: str) -> List[float]:
    norm = re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", text)   # 1.234 -> 1234
    norm = re.sub(r"(?<=\d),(?=\d)", ".", norm)           # 3,5 -> 3.5
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", norm)]


def fmt(n: float) -> str:
    return f"{int(n)}" if abs(n - round(n)) < 1e-9 else f"{n:g}"


def words_to_number(phrase: str) -> Optional[float]:
    """Converte 'trezentos e quarenta e dois mil e seis' -> 342006."""
    words = [w for w in re.split(r"[\s\-]+", deaccent(phrase)) if w and w != "e"]
    if not words:
        return None
    total, current, seen = 0, 0, False
    for w in words:
        if w in UNITS:
            current += UNITS[w]
            seen = True
        elif w in SCALES:
            scale = SCALES[w]
            current = current or 1
            total += current * scale
            current = 0
            seen = True
        elif seen:
            break  # terminou o trecho numérico
    if not seen:
        return None
    return total + current


def strat_aritmetica(prompt: str) -> Optional[str]:
    body = prompt.split("—")[-1] if "—" in prompt else prompt
    body = body.split("-")[-1] if body.count("-") == 1 and "—" not in prompt else body
    m = re.search(r"(-?\d[\d.,]*)\s*([+\-×x*÷/])\s*(-?\d[\d.,]*)", body)
    if not m:
        return None
    a = numbers_in(m.group(1))
    b = numbers_in(m.group(3))
    if not a or not b:
        return None
    a, b, op = a[0], b[0], m.group(2)
    try:
        if op == "+":
            return fmt(a + b)
        if op == "-":
            return fmt(a - b)
        if op in "×x*":
            return fmt(a * b)
        if op in "÷/" and b:
            return fmt(a / b)
    except Exception:
        return None
    return None


def strat_extenso(prompt: str) -> Optional[str]:
    body = prompt.split("—")[-1] if "—" in prompt else prompt
    if not re.search(r"\b(mil|cem|cento|vinte|trinta|quarenta|dois|tres|três|quatro)\b",
                     deaccent(body)):
        return None
    val = words_to_number(body)
    return fmt(val) if val else None


def strat_arredondamento(prompt: str) -> Optional[str]:
    d = deaccent(prompt)
    if "arredond" not in d:
        return None
    nums = numbers_in(prompt.split("—")[-1] if "—" in prompt else prompt)
    if not nums:
        return None
    n = nums[0]
    place = 10
    if "centena" in d:
        place = 100
    elif "milhar" in d or "mil" in d:
        place = 1000
    return fmt(round(n / place) * place)


def strat_ultimo_numero(prompt: str) -> Optional[str]:
    nums = numbers_in(prompt.split("—")[-1] if "—" in prompt else prompt)
    return fmt(nums[-1]) if nums else None


def strat_soma_numeros(prompt: str) -> Optional[str]:
    nums = numbers_in(prompt.split("—")[-1] if "—" in prompt else prompt)
    return fmt(sum(nums)) if len(nums) >= 2 else None


SOLVERS = {
    "aritmetica": strat_aritmetica,
    "extenso": strat_extenso,
    "arredondamento": strat_arredondamento,
    "ultimo_numero": strat_ultimo_numero,
    "soma_numeros": strat_soma_numeros,
}


# ---------------------------------------------------------------------------
# Cliente da plataforma (com telemetria de QA)
# ---------------------------------------------------------------------------
class Platform:
    def __init__(self, hd: MemoryHD):
        self.hd = hd
        self.token: Optional[str] = None
        self.latencies: List[Tuple[str, float]] = []

    def call(self, method: str, path: str, payload: dict | None = None,
             auth: bool = False, timeout: float = 120.0) -> Any:
        url = f"{API}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read().decode("utf-8"))
            dt = time.time() - t0
            self.latencies.append((path, dt))
            if dt > 10.0:
                self.hd.finding("medium", "latencia_alta",
                                f"{method} {path} levou {dt:.1f}s", {"path": path})
            return out
        except urllib.error.HTTPError as e:
            dt = time.time() - t0
            body = e.read().decode("utf-8", errors="replace")[:300]
            self.hd.finding("high", "http_error",
                            f"{method} {path} -> {e.code}: {body}", {"path": path})
            raise
        except Exception as e:  # noqa: BLE001
            self.hd.finding("high", "conexao",
                            f"{method} {path} falhou: {e}", {"path": path})
            raise

    def login(self):
        self.token = self.call("POST", "/token",
                               {"username": "impontuality", "password": "agent"})["access_token"]

    def ensure_learner(self) -> str:
        learners = self.call("GET", "/learners", auth=True)
        for l in learners:
            if l["name"] == AGENT_NAME:
                return l["id"]
        return self.call("POST", "/learners", {"name": AGENT_NAME}, auth=True)["id"]


# ---------------------------------------------------------------------------
# O agente
# ---------------------------------------------------------------------------
class Impontuality:
    def __init__(self, args):
        self.args = args
        self.hd = MemoryHD()
        self.api = Platform(self.hd)
        self.session = {
            "generation": self.hd.identity["generation"] + 1,
            "started_at": now_iso(),
            "studied": 0, "attempts": 0, "correct": 0,
            "kus_validated": 0, "missions": [], "by_domain": {},
            "strategy_usage": {},
        }

    # --- raciocínio com evolução ---
    def think(self, challenge: dict) -> Tuple[str, str]:
        """Devolve (resposta, estratégia). Ordem guiada por desempenho histórico."""
        cid = challenge["id"]
        prompt = challenge["prompt"]

        if cid in self.hd.answers:
            return self.hd.answers[cid], "memoria"

        ranking = self.hd.strategy_rank()
        if random.random() < EPSILON:                 # exploração
            random.shuffle(ranking)
        for strat in ranking:
            solver = SOLVERS.get(strat)
            if not solver:
                continue
            try:
                ans = solver(prompt)
            except Exception:
                ans = None
            if ans is not None:
                return ans, strat
        return "0", "ultimo_numero"

    def study_ku(self, ku: dict, learner_id: str) -> dict:
        """Estuda uma KU: lê definição, materiais e enfrenta os desafios."""
        ku_id = ku["id"]
        self.hd.learn_concept(ku)
        self.session["studied"] += 1
        domain = ku.get("domain", "?")
        dom = self.session["by_domain"].setdefault(
            domain, {"studied": 0, "attempts": 0, "correct": 0, "validated": 0})
        dom["studied"] += 1

        # QA: a unidade tem material de apoio?
        try:
            materials = self.api.call("GET", f"/kus/{ku_id}/materials")
        except Exception:
            materials = []
        if not materials:
            self.hd.finding("low", "sem_material",
                            f"KU sem material de estudo: {ku_id}", {"ku_id": ku_id})

        try:
            challenges = self.api.call("GET", f"/kus/{ku_id}/challenges")
        except Exception:
            challenges = []

        if not challenges:
            self.hd.finding("medium", "sem_desafio",
                            f"KU sem desafio objetivo (teto P9 de 60%): {ku_id}",
                            {"ku_id": ku_id, "domain": domain})
            # Estuda mesmo assim: registra auto-estudo (peso 0.40)
            try:
                self.api.call("POST", "/evidence", {
                    "learner_id": learner_id, "ku_id": ku_id, "type": "explanation",
                    "source_weight": 0.4, "reviewer_agreement": 1.0,
                    "recency_factor": 1.0, "reviewers": [],
                }, auth=True)
            except Exception:
                pass
            self.hd.episode({"kind": "self_study", "ku_id": ku_id, "domain": domain,
                             "generation": self.session["generation"]})
            return {"validated": False, "attempts": 0, "correct": 0}

        attempts = correct = 0
        mastery = 0.0
        for ch in challenges:
            answer, strategy = self.think(ch)
            try:
                res = self.api.call("POST", f"/challenges/{ch['id']}/attempt",
                                    {"learner_id": learner_id, "answer": answer}, auth=True)
            except Exception:
                continue
            attempts += 1
            dom["attempts"] += 1
            hit = bool(res.get("correct"))
            self.hd.reinforce(strategy, hit)
            self.session["strategy_usage"][strategy] = \
                self.session["strategy_usage"].get(strategy, 0) + 1
            if hit:
                correct += 1
                dom["correct"] += 1
                self.hd.identity["xp"] += 10
                self.hd.learn_answer(ch["id"], ch["prompt"], answer, strategy)
                if res.get("new_mastery") is not None:
                    mastery = res["new_mastery"]
            else:
                self.hd.identity["xp"] += 1   # errar também ensina
            self.hd.episode({
                "kind": "attempt", "ku_id": ku_id, "domain": domain,
                "challenge_id": ch["id"], "prompt": ch["prompt"][:160],
                "answer": answer, "strategy": strategy, "correct": hit,
                "mastery_after": res.get("new_mastery"),
                "generation": self.session["generation"],
            })

        self.session["attempts"] += attempts
        self.session["correct"] += correct
        validated = mastery >= 0.85
        if validated:
            self.session["kus_validated"] += 1
            dom["validated"] += 1
        return {"validated": validated, "attempts": attempts, "correct": correct}

    def run(self):
        print(f"=== IMPONTUALITY — geração {self.session['generation']} ===")
        self.api.login()
        learner_id = self.api.ensure_learner()
        print(f"Learner: {learner_id}")

        missions = self.api.call("GET", "/missions")
        if self.args.missions:
            wanted = set(self.args.missions.split(","))
            missions = [m for m in missions if m["id"] in wanted]
        print(f"Trilhas a estudar: {len(missions)}")

        all_kus = {k["id"]: k for k in self.api.call("GET", "/kus")}

        for mi, mission in enumerate(missions, 1):
            required = mission.get("required_kus") or []
            plan = [k for k in required if k in all_kus][: self.args.max_kus]
            print(f"\n[{mi}/{len(missions)}] {mission['label']} — {len(plan)} KUs")
            mrec = {"mission": mission["label"], "id": mission["id"],
                    "planned": len(plan), "attempts": 0, "correct": 0, "validated": 0}
            t0 = time.time()

            for i, ku_id in enumerate(plan, 1):
                r = self.study_ku(all_kus[ku_id], learner_id)
                mrec["attempts"] += r["attempts"]
                mrec["correct"] += r["correct"]
                mrec["validated"] += 1 if r["validated"] else 0
                if i % 25 == 0:
                    acc = (mrec["correct"] / mrec["attempts"] * 100) if mrec["attempts"] else 0
                    print(f"    {i}/{len(plan)} · acertos {mrec['correct']}/{mrec['attempts']}"
                          f" ({acc:.0f}%) · validadas {mrec['validated']}")
                    self.hd.save()

            mrec["seconds"] = round(time.time() - t0, 1)
            self.session["missions"].append(mrec)
            acc = (mrec["correct"] / mrec["attempts"] * 100) if mrec["attempts"] else 0
            print(f"    fim: {mrec['correct']}/{mrec['attempts']} ({acc:.0f}%)"
                  f" · {mrec['validated']} validadas · {mrec['seconds']}s")
            self.hd.save()

        self.finish()

    def finish(self):
        self.session["ended_at"] = now_iso()
        lat = [d for _, d in self.api.latencies]
        self.session["telemetry"] = {
            "requests": len(lat),
            "avg_latency": round(sum(lat) / len(lat), 3) if lat else 0,
            "max_latency": round(max(lat), 3) if lat else 0,
        }
        ident = self.hd.identity
        ident["generation"] = self.session["generation"]
        ident["sessions"].append(self.session)
        lt = ident["lifetime"]
        lt["studied"] += self.session["studied"]
        lt["attempts"] += self.session["attempts"]
        lt["correct"] += self.session["correct"]
        lt["validated_kus"] += self.session["kus_validated"]
        ident["accuracy_lifetime"] = round(lt["correct"] / lt["attempts"], 4) if lt["attempts"] else 0
        self.hd.save()

        acc = (self.session["correct"] / self.session["attempts"] * 100) \
            if self.session["attempts"] else 0
        print(f"\n=== FIM DA GERAÇÃO {self.session['generation']} ===")
        print(f"Estudadas: {self.session['studied']} KUs | "
              f"Tentativas: {self.session['attempts']} | Acertos: {self.session['correct']} ({acc:.1f}%)")
        print(f"KUs validadas: {self.session['kus_validated']} | XP: {ident['xp']}")
        print(f"Memória: {len(self.hd.answers)} respostas, {len(self.hd.concepts)} conceitos")
        print("Estratégias:", {s: f"{d['hits']}/{d['tries']}" for s, d in self.hd.skills.items()})


def report():
    hd = MemoryHD()
    ident = hd.identity
    print(f"=== HD DE {ident['name']} ===")
    print(f"Nascido em {ident['born_at']} | geração {ident['generation']} | XP {ident['xp']}")
    lt = ident["lifetime"]
    acc = (lt["correct"] / lt["attempts"] * 100) if lt["attempts"] else 0
    print(f"Vida toda: {lt['studied']} KUs estudadas, {lt['correct']}/{lt['attempts']} "
          f"acertos ({acc:.1f}%), {lt['validated_kus']} validadas")
    print(f"Memória: {len(hd.answers)} respostas | {len(hd.concepts)} conceitos")
    print("\nEvolução por geração:")
    for s in ident["sessions"]:
        a = (s["correct"] / s["attempts"] * 100) if s["attempts"] else 0
        print(f"  gen {s['generation']}: {s['studied']} KUs · {s['correct']}/{s['attempts']}"
              f" ({a:.1f}%) · {s['kus_validated']} validadas")
    print("\nEstratégias (hits/tries):")
    for s, d in sorted(hd.skills.items(), key=lambda kv: -kv[1]["hits"]):
        r = (d["hits"] / d["tries"] * 100) if d["tries"] else 0
        print(f"  {s:16s} {d['hits']:5d}/{d['tries']:<5d} ({r:.0f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-kus", type=int, default=25, help="KUs por trilha")
    ap.add_argument("--missions", default=None, help="ids separados por vírgula")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        report()
        return
    Impontuality(args).run()


if __name__ == "__main__":
    main()

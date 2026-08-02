"""
Rate limiting por IP, em memória (janela deslizante).

Motivo concreto: `/challenges/{id}/attempt` corrige respostas numéricas. Sem
limite, dá para varrer valores até acertar — o que transformaria a "evidência
objetiva" (peso 0.60) em força bruta. Login e registro também precisam de
freio contra tentativa massiva de senha.

Escopo honesto: guarda o estado no processo. Serve para uma instância; com
múltiplas réplicas, trocar por Redis (`slowapi` + backend Redis) sem mudar as
chamadas — a interface aqui é a mesma.
"""
# SEM `from __future__ import annotations` aqui, de propósito.
#
# O FastAPI resolve as anotações de uma dependência lendo `call.__globals__`.
# Uma instância de classe não tem `__globals__`, então com anotações adiadas a
# string 'Request' não resolve e `request` vira parâmetro de QUERY: toda rota
# com rate limit passa a exigir `?request=` e devolve 422. Só se manifesta em
# certas combinações de versão — no Python 3.14 local quebra, no 3.12 do
# contêiner não. Anotação avaliada na hora é imune.
import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

ENABLED = os.getenv("EOS_RATE_LIMIT", "1") not in ("0", "false", "False")

# Backend Redis quando disponível: com o estado em memória, cada réplica tinha
# o próprio contador — 3 instâncias significavam 3× o limite anunciado, e um
# reinício zerava tudo. Com Redis a contagem é compartilhada e persistente.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
_redis = None
if ENABLED and REDIS_URL:
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    except ImportError:
        print("REDIS_URL definido mas 'redis' não instalado — rate limit em memória.")

_hits: Dict[str, Deque[float]] = defaultdict(deque)
_LAST_SWEEP = time.monotonic()
_SWEEP_EVERY = 300.0          # limpeza periódica para o dicionário não crescer sem fim


def _client_key(request: Request, bucket: str) -> str:
    # X-Forwarded-For só é confiável atrás de proxy próprio; usa o primeiro salto
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
    return f"{bucket}:{ip}"


def _sweep(now: float) -> None:
    global _LAST_SWEEP
    if now - _LAST_SWEEP < _SWEEP_EVERY:
        return
    _LAST_SWEEP = now
    vazios = [k for k, dq in _hits.items() if not dq or now - dq[-1] > 3600]
    for k in vazios:
        _hits.pop(k, None)


class RateLimit:
    """
    Dependência do FastAPI:
        @router.post(..., dependencies=[Depends(RateLimit("login", 10, 60))])
    """

    def __init__(self, bucket: str, limite: int, janela_seg: float):
        self.bucket = bucket
        self.limite = limite
        self.janela = janela_seg

    async def __call__(self, request: Request) -> None:
        if not ENABLED:
            return
        chave = _client_key(request, self.bucket)
        if _redis is not None:
            await self._checar_redis(chave)
        else:
            self._checar_memoria(chave)

    async def _checar_redis(self, chave: str) -> None:
        """
        Janela deslizante em sorted set: remove o que saiu da janela, conta o
        que sobrou, registra a chamada — tudo num pipeline, então réplicas
        concorrentes veem a mesma contagem.
        """
        agora = time.time()
        try:
            pipe = _redis.pipeline()
            pipe.zremrangebyscore(chave, 0, agora - self.janela)
            pipe.zcard(chave)
            pipe.zadd(chave, {f"{agora}:{os.urandom(4).hex()}": agora})
            pipe.expire(chave, int(self.janela) + 1)
            _, usados, _, _ = await pipe.execute()
        except Exception:
            # Redis fora do ar não pode derrubar a API: cai para memória
            self._checar_memoria(chave)
            return
        if usados >= self.limite:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Muitas requisições. Aguarde {int(self.janela)}s.",
                headers={"Retry-After": str(int(self.janela))},
            )

    def _checar_memoria(self, chave: str) -> None:
        agora = time.monotonic()
        _sweep(agora)
        dq = _hits[chave]
        while dq and agora - dq[0] > self.janela:
            dq.popleft()
        if len(dq) >= self.limite:
            espera = int(self.janela - (agora - dq[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Muitas requisições. Tente novamente em {espera}s.",
                headers={"Retry-After": str(espera)},
            )
        dq.append(agora)


# Perfis usados na API
limite_login = RateLimit("login", limite=10, janela_seg=60)          # senha por força bruta
limite_registro = RateLimit("registro", limite=5, janela_seg=300)    # criação em massa
limite_tentativa = RateLimit("attempt", limite=60, janela_seg=60)    # varredura de gabarito
limite_escrita = RateLimit("escrita", limite=120, janela_seg=60)

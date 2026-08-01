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
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

ENABLED = os.getenv("EOS_RATE_LIMIT", "1") not in ("0", "false", "False")

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
        agora = time.monotonic()
        _sweep(agora)
        chave = _client_key(request, self.bucket)
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

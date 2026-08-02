"""
Segurança do EngineeringOS.

Regras que este módulo garante:
  1. Segredo NUNCA tem valor padrão fora de desenvolvimento — a aplicação
     recusa-se a subir sem `JWT_SECRET_KEY` quando EOS_ENV=production.
  2. O token carrega o `learner_id`. A identidade dos dados vem do token,
     jamais do corpo da requisição (antes, qualquer autenticado escrevia
     progresso em nome de qualquer aluno).
  3. Senha só existe como hash bcrypt.
"""
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

ENV = os.getenv("EOS_ENV", "development").lower()
IS_PRODUCTION = ENV in ("production", "prod")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))


def _load_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if secret:
        if IS_PRODUCTION and len(secret) < 32:
            raise RuntimeError(
                "JWT_SECRET_KEY tem menos de 32 caracteres — insuficiente para produção."
            )
        return secret
    if IS_PRODUCTION:
        # Falhar alto é melhor que subir com segredo conhecido: com um segredo
        # padrão publicado no repositório, qualquer pessoa forja um token admin.
        raise RuntimeError(
            "JWT_SECRET_KEY é obrigatório quando EOS_ENV=production. "
            "Gere um com: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    # Desenvolvimento: segredo efêmero por processo (reiniciar invalida tokens,
    # que é o comportamento seguro — nada de chave fixa em código).
    return secrets.token_urlsafe(48)


SECRET_KEY = _load_secret()

# auto_error=False de propósito: com auto_error=True o FastAPI responde 403 a
# requisição SEM credencial nenhuma, e 403 quer dizer "identificado, mas sem
# permissão". Quem não se identificou merece 401 com WWW-Authenticate — é o que
# diz a RFC 7235 e é o que um cliente precisa para saber que deve autenticar.
security = HTTPBearer(auto_error=False)

# bcrypt direto, sem passlib: o passlib 1.7.4 é incompatível com bcrypt >= 4 e
# levanta "password cannot be longer than 72 bytes" mesmo para senhas curtas.
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))
_MAX_PASSWORD_BYTES = 72          # limite do algoritmo


# ---------------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------------
def _encode(password: str) -> bytes:
    data = password.encode("utf-8")
    if len(data) > _MAX_PASSWORD_BYTES:
        # Recusar em vez de truncar em silêncio: truncar aceitaria uma senha
        # cujo final digitado é ignorado na verificação.
        raise ValueError("Senha muito longa (máximo 72 bytes).")
    return data


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_encode(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas ou token expirado",
    headers={"WWW-Authenticate": "Bearer"},
)


async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Valida o token e devolve o payload (sub, learner_id, role)."""
    if credentials is None:
        raise CREDENTIALS_EXCEPTION
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise CREDENTIALS_EXCEPTION
    if not payload.get("sub") or not payload.get("role"):
        raise CREDENTIALS_EXCEPTION
    return payload


def token_learner_id(payload: dict) -> Optional[uuid.UUID]:
    raw = payload.get("learner_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


async def require_admin(payload: dict = Depends(verify_token)) -> dict:
    """
    Rotas destrutivas (seed apaga TODAS as tabelas) exigem admin.
    Antes, qualquer conta autenticada podia zerar o acervo inteiro.
    """
    if payload.get("role") != "admin" and not payload.get("internal"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operação restrita a administradores.",
        )
    return payload


def authorize_learner(payload: dict, learner_id: uuid.UUID) -> None:
    """
    Autorização por recurso: só o próprio aluno (ou um admin) escreve no seu
    progresso. Processos internos do servidor usam `internal=True`.
    """
    if payload.get("internal") or payload.get("role") == "admin":
        return
    if token_learner_id(payload) == learner_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Você só pode registrar evidência no seu próprio progresso.",
    )

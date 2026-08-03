// Endereço da API do EngineeringOS.
//
// Produção: caminho relativo. O backend serve o próprio dashboard (StaticFiles
// em main.py), então "/api" aponta para a mesma origem — funciona em qualquer
// domínio e dispensa CORS. Um endereço absoluto aqui apontaria para a máquina
// de quem abre o site, não para o servidor: a aplicação inteira quebraria.
//
// Desenvolvimento: o Vite roda em 5173 e a API em 8000, então precisa ser
// absoluto. E 127.0.0.1 em vez de "localhost" porque no Windows o resolvedor
// tenta o IPv6 ::1 primeiro e custa ~2s de timeout por requisição.
const DEV_API = "http://127.0.0.1:8000/api";

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  (import.meta.env.DEV ? DEV_API : "/api");

// ---------------------------------------------------------------------------
// Chamada autenticada
//
// Existe porque cada componente fazia `const dados = await res.json()` sem
// olhar o status. Com token expirado, o corpo do 401 — `{"detail": "..."}` —
// virava o "resultado" e a tela mostrava *Ainda não… Credenciais inválidas*
// como se a RESPOSTA do aluno estivesse errada. Ele revia a matéria; o
// problema era a sessão.
//
// Só o 401 derruba a sessão. 403 é "identificado, mas sem permissão" — sair
// nesse caso esconderia um erro de autorização atrás de uma tela de login.
// ---------------------------------------------------------------------------

export class SessaoExpirada extends Error {
  constructor() {
    super("Sua sessão expirou. Entre novamente para continuar.");
    this.name = "SessaoExpirada";
  }
}

export class ErroDaApi extends Error {
  status: number;
  constructor(status: number, detalhe: string) {
    super(detalhe);
    this.name = "ErroDaApi";
    this.status = status;
  }
}

type Ouvinte = () => void;
let aoExpirarSessao: Ouvinte | null = null;

/** A aplicação registra o que fazer quando a sessão cair. */
export function aoPerderSessao(fn: Ouvinte | null) {
  aoExpirarSessao = fn;
}

export function limparSessao() {
  localStorage.removeItem("eos_token");
  localStorage.removeItem("eos_sessao");
}

export async function apiFetch<T = unknown>(
  caminho: string,
  opcoes: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem("eos_token");
  const res = await fetch(`${API_BASE}${caminho}`, {
    ...opcoes,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opcoes.headers ?? {}),
    },
  });

  if (res.status === 401) {
    limparSessao();
    aoExpirarSessao?.();
    throw new SessaoExpirada();
  }

  let corpo: any = null;
  try {
    corpo = await res.json();
  } catch {
    corpo = null;
  }

  if (!res.ok) {
    const detalhe =
      (typeof corpo?.detail === "string" && corpo.detail) ||
      `Falha na requisição (HTTP ${res.status})`;
    throw new ErroDaApi(res.status, detalhe);
  }

  return corpo as T;
}

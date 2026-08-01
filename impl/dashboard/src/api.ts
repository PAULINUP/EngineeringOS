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
